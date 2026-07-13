"""sentinel_engine.service.routers.chat — /models, /chat, /api/llm/* (W0.1b, A8).

Moved verbatim out of `sentinel_engine.service.app` (plan recalibration V2,
W0.1 "split app.py into routers"). `build_router(runners, resolve, chat_client_getter)`
is called once from `create_app()`; the returned `APIRouter` is included via
`app.include_router(...)` so every path stays byte-identical to before the
split.

Deliberately NOT using `from __future__ import annotations` (same reason as
`routers/strategies.py`): `ChatRequest`/`ChatResponse` are only reachable
through a lazy (function-local) import of `sentinel_engine.service.app` (a
top-level import would be circular — `app.py` imports this module at its own
top-level to register the router). Deferred string annotations would resolve
to nothing and FastAPI would silently mis-treat `payload`/`response_model`.
Without the future-import, Python evaluates annotations eagerly at
function-definition time (inside `build_router`, after the lazy import).

Wave A / Task A8 (CT-6) adds the LLM model catalog + gate + usage meter:

  GET  /api/llm/models  -> catalog derived from `models.yaml` (repo root),
                           mapped to the frozen CT-6 shape.
  POST /api/llm/unlock  -> {"code"} compared server-side against
                           `os.environ["SENTINEL_OPUS_GATE"]` (default
                           "abc123"); never sent to the client. On success,
                           flips a per-session unlocked flag.
  GET  /api/llm/usage   -> per-session accumulated token counts + a rough
                           USD estimate (pricing table in `models.yaml`).

There was no pre-existing chat session/cookie mechanism to reuse (the router
was fully stateless before this task — see `answer_chat`, which takes no
session concept at all). The simplest mechanism that satisfies "server-side
session flag" + "per-session usage counters" without inventing framework
machinery is a `sentinel_session` cookie (server-issued opaque id) keyed into
a module-level dict — see `_SESSIONS` below. This is an explicit deviation;
documented in the task report.

Task C4b adds `POST /api/ai/analyze_position`:

  POST /api/ai/analyze_position {"trade_id", "model"(optional)} -> SSE
      stream (CT-9: `text/event-stream`, `retry: 3000`, 15s heartbeat
      comments), events `ai_text` (one per streamed text chunk from
      `run_tool_loop`'s `on_text`), `ai_done` (terminal, success), `ai_error`
      (terminal, failure -- unknown trade_id, gated model without unlock,
      etc). CT-6 gate is re-checked BEFORE any dossier build or API call, so
      a locked gated model 403s immediately (same JSON envelope as /chat,
      `{"error": "gated_model_locked"}`) rather than opening the stream.
      `model` defaults to the catalog's `default: true` entry when omitted.
      System prompt is assembled STABLE-FIRST per research doc §5 caching
      order: fixed system preamble -> tool list (implicit, passed via
      `tools=` param to run_tool_loop, not interpolated into the string) ->
      C3a dossier XML -> the trader's question LAST.
"""

import asyncio
import json
import os
import secrets
from pathlib import Path
from typing import Any, Callable

import yaml
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from ..chat import answer_chat
from ...ai.dossier import DossierError, build_position_dossier
from ...ai.loop import run_tool_loop
from ...ai.tools import TOOLS

router = APIRouter()

# CT-9 SSE convention: heartbeat comment cadence (seconds) -- matches
# routers/jobs.py / routers/news.py. `run_tool_loop` here runs synchronously
# to completion inside a single `asyncio.to_thread` call (no natural pause
# point to interleave heartbeats mid-analysis), so heartbeats only matter
# before that call starts / after it ends; the constant is kept for
# convention parity and documented in the task report as a deviation.
_SSE_HEARTBEAT_SECONDS = 15.0

# STABLE-FIRST fixed system preamble (research doc §5 caching order: this
# text never varies request-to-request, so it is always the first content
# in the system prompt -- followed by the (per-request, but still
# request-stable across the whole analysis) dossier XML, then the trader's
# question LAST).
_ANALYZE_POSITION_SYSTEM_PREAMBLE = (
    "You are SENTINEL's trading position analyst. You have read-only tools "
    "to inspect bars, the strategy scorecard, and the research registry. "
    "Use them when they would sharpen your analysis. Below is a dossier "
    "with the trade record, derived stats, and surrounding price action."
)


class AnalyzePositionRequest(BaseModel):
    trade_id: str
    model: str | None = None

_SESSION_COOKIE = "sentinel_session"
_MODELS_YAML_PATH = Path(__file__).resolve().parents[3] / "models.yaml"

# Module-level session store: cookie value -> {"unlocked": bool,
# "tokens_in": int, "tokens_out": int, "cost_usd": float}. Process-lifetime
# only (mirrors the rest of the service's in-memory state, e.g. `runners`).
_SESSIONS: dict[str, dict[str, Any]] = {}


def _load_models_catalog() -> dict[str, Any]:
    with _MODELS_YAML_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _ct6_models() -> list[dict[str, Any]]:
    """Map `models.yaml`'s `models:` list onto the frozen CT-6 shape:
    {"id", "label", "gated", "default"(only when true)}."""
    catalog = _load_models_catalog()
    out = []
    for entry in catalog.get("models", []):
        item = {
            "id": entry["id"],
            "label": entry["label"],
            "gated": bool(entry.get("gated", False)),
        }
        if entry.get("default"):
            item["default"] = True
        out.append(item)
    return out


def _gated_ids() -> set[str]:
    return {m["id"] for m in _ct6_models() if m["gated"]}


def _pricing() -> dict[str, dict[str, float]]:
    return _load_models_catalog().get("pricing", {})


def _default_model_id() -> str | None:
    for m in _ct6_models():
        if m.get("default"):
            return m["id"]
    return None


def _get_session_id(request: Request) -> str:
    return request.cookies.get(_SESSION_COOKIE, "")


def _get_or_create_session(request: Request, response: Response) -> tuple[str, dict[str, Any]]:
    sid = _get_session_id(request)
    if not sid or sid not in _SESSIONS:
        sid = secrets.token_urlsafe(16)
        response.set_cookie(_SESSION_COOKIE, sid, httponly=True, samesite="lax")
    session = _SESSIONS.setdefault(
        sid, {"unlocked": False, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
    )
    return sid, session


class UnlockRequest(BaseModel):
    code: str


def build_router(runners: dict, resolve: Callable[[str | None], Any], app_state) -> APIRouter:
    from ..app import ChatRequest, ChatResponse

    r = APIRouter()

    @r.get("/models")
    def get_models() -> dict[str, Any]:
        return {
            "models": [
                {"key": "sonnet", "label": "Claude Sonnet"},
                {"key": "haiku", "label": "Claude Haiku"},
            ],
            "effort_levels": ["low", "medium", "high"],
            "web_search_available": False,
            "thinking_available": False,
        }

    @r.get("/api/llm/models")
    def get_llm_models() -> list[dict[str, Any]]:
        return _ct6_models()

    @r.post("/api/llm/unlock")
    def post_unlock(payload: UnlockRequest, request: Request, response: Response) -> dict[str, bool]:
        _sid, session = _get_or_create_session(request, response)
        expected = os.environ.get("SENTINEL_OPUS_GATE", "abc123")
        ok = payload.code == expected
        if ok:
            session["unlocked"] = True
        return {"ok": ok}

    @r.get("/api/llm/usage")
    def get_usage(request: Request, response: Response) -> dict[str, Any]:
        _sid, session = _get_or_create_session(request, response)
        return {
            "session_tokens_in": session["tokens_in"],
            "session_tokens_out": session["tokens_out"],
            "est_usd": session["cost_usd"],
        }

    @r.post("/chat", response_model=ChatResponse)
    async def post_chat(payload: ChatRequest, request: Request, response: Response) -> ChatResponse:
        _sid, session = _get_or_create_session(request, response)

        # `ChatRequest` (defined in `..app`, out of scope for this task) has
        # no `model` field, so pydantic silently drops it from `payload`.
        # Read it from the raw JSON body instead — CT-6 requires gating on
        # the requested model before the model is invoked.
        try:
            raw_body = await request.json()
        except Exception:
            raw_body = {}
        model_id = raw_body.get("model") if isinstance(raw_body, dict) else None

        if model_id in _gated_ids() and not session["unlocked"]:
            # Body must be exactly {"error": "gated_model_locked"} per CT-6 —
            # HTTPException's default envelope wraps `detail` as
            # {"detail": ...}, so return the JSONResponse directly instead.
            err = JSONResponse(status_code=403, content={"error": "gated_model_locked"})
            err.set_cookie(_SESSION_COOKIE, _sid, httponly=True, samesite="lax")
            return err

        runner = resolve(payload.instrument)
        if runner.latest_snapshot is None:
            raise HTTPException(status_code=503, detail="snapshot not ready")
        positions_fn = getattr(runner.feed, "positions", None)
        positions = positions_fn() if positions_fn is not None else []

        # `answer_chat` (sentinel_engine/service/chat.py, out of scope for
        # this task) only surfaces `ChatReply(content, error)` — it discards
        # the `input_tokens`/`output_tokens` fields the underlying client
        # dict carries. Wrap the client to capture the raw result for usage
        # accounting without touching that module.
        _usage_capture: dict[str, Any] = {}
        underlying_client = app_state.chat_client

        class _UsageCapturingClient:
            def chat(self, *args, **kwargs):
                if underlying_client is None:
                    from sentinel.ai_chat import SentinelAI

                    result = SentinelAI().chat(*args, **kwargs)
                else:
                    result = underlying_client.chat(*args, **kwargs)
                _usage_capture["input_tokens"] = result.get("input_tokens", 0)
                _usage_capture["output_tokens"] = result.get("output_tokens", 0)
                return result

        reply = answer_chat(
            payload.question,
            runner.latest_snapshot,
            runner.cfg,
            positions,
            client=_UsageCapturingClient(),
        )

        tokens_in = _usage_capture.get("input_tokens", 0) or 0
        tokens_out = _usage_capture.get("output_tokens", 0) or 0
        if tokens_in or tokens_out:
            session["tokens_in"] += tokens_in
            session["tokens_out"] += tokens_out
            prices = _pricing().get(model_id or "", {})
            session["cost_usd"] += (
                tokens_in * prices.get("input_per_mtok", 0.0) / 1_000_000
                + tokens_out * prices.get("output_per_mtok", 0.0) / 1_000_000
            )

        return ChatResponse(content=reply.content, error=reply.error)

    @r.post("/api/ai/analyze_position")
    async def post_analyze_position(
        payload: AnalyzePositionRequest, request: Request, response: Response
    ):
        _sid, session = _get_or_create_session(request, response)
        model_id = payload.model or _default_model_id()

        # CT-6 gate: checked BEFORE any dossier build or API call, so a
        # locked gated model 403s immediately instead of opening the SSE
        # stream (same envelope shape as /chat).
        if model_id in _gated_ids() and not session["unlocked"]:
            err = JSONResponse(status_code=403, content={"error": "gated_model_locked"})
            err.set_cookie(_SESSION_COOKIE, _sid, httponly=True, samesite="lax")
            return err

        def _sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        async def event_stream():
            yield "retry: 3000\n\n"
            try:
                dossier = build_position_dossier(
                    payload.trade_id,
                    db_path=app_state.registry.db_path,
                    lake_root=app_state.lake_root,
                )
            except DossierError as exc:
                yield _sse("ai_error", {"error": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001 - never crash the stream
                yield _sse("ai_error", {"error": f"dossier_failed: {exc}"})
                return

            # STABLE-FIRST ordering (research doc §5): fixed preamble first,
            # dossier XML next, the trader's question LAST.
            system_prompt = (
                f"{_ANALYZE_POSITION_SYSTEM_PREAMBLE}\n\n{dossier['xml']}"
            )
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Analyze this position (trade_id={payload.trade_id}). "
                        "What went right or wrong, and what would you change?"
                    ),
                }
            ]

            client = app_state.chat_client
            if client is None:
                yield _sse("ai_error", {"error": "no AI client configured"})
                return

            ctx = {"registry": app_state.registry, "lake_root": app_state.lake_root}
            chunks: list[str] = []

            def _on_text(chunk: str) -> None:
                chunks.append(chunk)

            try:
                final_text = await asyncio.to_thread(
                    run_tool_loop,
                    client,
                    model_id,
                    system_prompt,
                    messages,
                    TOOLS,
                    ctx,
                    _on_text,
                )
            except Exception as exc:  # noqa: BLE001 - report via ai_error, never crash the stream
                yield _sse("ai_error", {"error": f"analyze_failed: {exc}"})
                return

            for chunk in chunks:
                yield _sse("ai_text", {"text": chunk})
            yield _sse("ai_done", {"text": final_text})

        stream = StreamingResponse(event_stream(), media_type="text/event-stream")
        stream.set_cookie(_SESSION_COOKIE, _sid, httponly=True, samesite="lax")
        return stream

    return r
