"""sentinel_engine.service.routers.chat — /models, /chat (W0.1b).

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
"""

from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ..chat import answer_chat

router = APIRouter()


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

    @r.post("/chat", response_model=ChatResponse)
    def post_chat(payload: ChatRequest) -> ChatResponse:
        runner = resolve(payload.instrument)
        if runner.latest_snapshot is None:
            raise HTTPException(status_code=503, detail="snapshot not ready")
        positions_fn = getattr(runner.feed, "positions", None)
        positions = positions_fn() if positions_fn is not None else []
        reply = answer_chat(
            payload.question,
            runner.latest_snapshot,
            runner.cfg,
            positions,
            client=app_state.chat_client,
        )
        return ChatResponse(content=reply.content, error=reply.error)

    return r
