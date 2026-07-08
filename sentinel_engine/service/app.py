"""
sentinel_engine.service.app — FastAPI service wrapping the headless Engine
(P3, Tasks 3.1/3.3).

`create_app(feed_factory, instruments=...)` builds one uvicorn-servable app
that scores every requested instrument via `sentinel_engine.engine.Engine`
against a caller-supplied `Feed` (production: `LiveMT5Feed`; tests:
`tests/golden/fake_feed.FakeFeed` — the service is feed-injectable by
construction, there is no MT5 import in this module).

State-consistency correctness fix (Task 3.3): each instrument has exactly
ONE `InstrumentRunner` producing ONE snapshot per tick (`Engine.step()`),
held in `runner.latest` and fanned out via `Broadcaster.broadcast` — every
HTTP GET and every connected WS client for that instrument sees the
identical dict for a given `seq`, never a per-caller recompute.

Endpoints:
    GET  /snapshot?instrument=<name>   -> Snapshot.to_dict() (JSON-safe)
    GET  /config?instrument=<name>     -> config_hash + full config + known instruments
    WS   /stream?instrument=<name>     -> pushes each new snapshot as it is computed
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from sentinel_engine.config import InstrumentConfig, config_hash, load_instrument
from sentinel_engine.engine import Engine, Snapshot
from sentinel_engine.feed import Feed
from sentinel_engine.opt.levers import LEVER_GROUPS, priors_for

from .chat import answer_chat
from .stream import Broadcaster

DEFAULT_INSTRUMENTS: tuple[str, ...] = ("usdclp", "gold", "nasdaq")
WEB_DIR = Path(__file__).resolve().parents[2] / "web"


class ChatRequest(BaseModel):
    question: str
    instrument: str | None = None


class ChatResponse(BaseModel):
    content: str
    error: str | None = None


def _snapshot_to_json(snap_dict: dict) -> dict:
    """`Snapshot.to_dict()` is JSON-safe except `ts`, which is a
    `datetime | None` — isoformat it (or leave None) for the wire."""
    out = dict(snap_dict)
    ts = out.get("ts")
    if ts is not None and hasattr(ts, "isoformat"):
        out["ts"] = ts.isoformat()
    return out


def _infer_data_source(feed: Feed) -> str:
    """Best-effort, additive-only classification of the feed backing this
    runner — used purely for the UI's data-source badge (spec §7). No new
    Feed protocol method is added; this reads the feed's class name only."""
    name = type(feed).__name__.lower()
    if "mt5" in name:
        return "mt5"
    if "historical" in name:
        return "historical"
    if "fake" in name:
        return "fake"
    return "yahoo"


def _compute_stale_seconds(ts) -> float:
    if ts is None:
        return 0.0
    now = datetime.now(timezone.utc)
    try:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, (now - ts).total_seconds())
    except Exception:
        return 0.0


class InstrumentRunner:
    """Owns one `Engine` for one instrument: a monotonic seq counter and the
    single latest computed snapshot (shared by every reader)."""

    def __init__(self, name: str, cfg: InstrumentConfig, feed: Feed):
        self.name = name
        self.cfg = cfg
        self.feed = feed
        self.engine = Engine(cfg, feed)
        self._seq = 0
        self.latest: dict | None = None
        self.latest_snapshot: Snapshot | None = None

    def compute(self) -> dict:
        snap = self.engine.step(seq=self._seq)
        snap = replace(
            snap,
            data_source=_infer_data_source(self.feed),
            stale_seconds=_compute_stale_seconds(snap.ts),
        )
        self._seq += 1
        self.latest_snapshot = snap
        self.latest = _snapshot_to_json(snap.to_dict())
        return self.latest


def create_app(
    feed_factory: Callable[[str], Feed],
    instruments: tuple[str, ...] = DEFAULT_INSTRUMENTS,
    loop_interval: float = 1.0,
    autostart_loop: bool = True,
) -> FastAPI:
    """Build the SENTINEL FastAPI service.

    `feed_factory(instrument_name) -> Feed` is called once per instrument at
    startup (production wires a `LiveMT5Feed`; tests inject a shared
    `FakeFeed`). `autostart_loop=False` disables the periodic background
    compute loop (useful for HTTP-only tests that don't want a ticking
    background task).
    """
    runners: dict[str, InstrumentRunner] = {}
    for name in instruments:
        cfg = load_instrument(name)
        runners[name] = InstrumentRunner(name, cfg, feed_factory(name))
        runners[name].compute()  # seed seq=0 so GET /snapshot works pre-loop

    broadcaster = Broadcaster()

    async def _compute_and_broadcast_once(name: str) -> dict:
        runner = runners[name]
        snap = runner.compute()
        await broadcaster.broadcast(name, snap)
        return snap

    async def _background_loop() -> None:
        while True:
            for name in runners:
                await _compute_and_broadcast_once(name)
            await asyncio.sleep(loop_interval)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = asyncio.create_task(_background_loop()) if autostart_loop else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()

    app = FastAPI(title="SENTINEL", lifespan=lifespan)
    app.state.runners = runners
    app.state.broadcaster = broadcaster
    app.state.compute_and_broadcast_once = _compute_and_broadcast_once
    # Optional injected assistant client (tests only) — None uses the default
    # `sentinel.ai_chat.SentinelAI()`, which mock-answers offline when no
    # ANTHROPIC_API_KEY is set. See `.chat.answer_chat`.
    app.state.chat_client = None

    def _resolve(instrument: str | None) -> InstrumentRunner:
        name = instrument or next(iter(runners))
        runner = runners.get(name)
        if runner is None:
            raise HTTPException(status_code=404, detail=f"unknown instrument: {name}")
        return runner

    @app.get("/snapshot")
    def get_snapshot(instrument: str | None = None) -> dict:
        runner = _resolve(instrument)
        if runner.latest is None:
            raise HTTPException(status_code=503, detail="snapshot not ready")
        return runner.latest

    @app.get("/config")
    def get_config(instrument: str | None = None) -> dict[str, Any]:
        runner = _resolve(instrument)
        return {
            "instrument": runner.name,
            "config_hash": config_hash(runner.cfg),
            "config": asdict(runner.cfg),
            "instruments": list(runners.keys()),
        }

    @app.get("/levers")
    def get_levers(instrument: str | None = None) -> dict[str, Any]:
        runner = _resolve(instrument)
        priors = priors_for(runner.cfg)
        groups = []
        for group in LEVER_GROUPS:
            params = []
            for p in group.params:
                params.append({
                    "name": p.name,
                    "lo": p.low,
                    "hi": p.high,
                    "is_int": p.is_int,
                    "production_value": priors[group.name][p.name],
                })
            groups.append({"name": group.name, "params": params})
        return {"instrument": runner.name, "groups": groups}

    @app.get("/models")
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

    @app.post("/chat", response_model=ChatResponse)
    def post_chat(payload: ChatRequest) -> ChatResponse:
        runner = _resolve(payload.instrument)
        if runner.latest_snapshot is None:
            raise HTTPException(status_code=503, detail="snapshot not ready")
        positions_fn = getattr(runner.feed, "positions", None)
        positions = positions_fn() if positions_fn is not None else []
        reply = answer_chat(
            payload.question,
            runner.latest_snapshot,
            runner.cfg,
            positions,
            client=app.state.chat_client,
        )
        return ChatResponse(content=reply.content, error=reply.error)

    @app.websocket("/stream")
    async def stream_ws(websocket: WebSocket, instrument: str | None = None) -> None:
        name = instrument or next(iter(runners))
        if name not in runners:
            await websocket.close(code=4404)
            return
        await broadcaster.connect(websocket, name)
        try:
            runner = runners[name]
            if runner.latest is not None:
                await websocket.send_json(runner.latest)
            while True:
                # Keepalive: client need not send anything meaningful; this
                # just parks the coroutine until disconnect. Broadcasts are
                # pushed independently by the background loop via `send_json`
                # inside Broadcaster.broadcast.
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            broadcaster.disconnect(websocket, name)

    def _gated(capability: str) -> JSONResponse:
        """Every gated route (spec §6) — replay/variant-registry/study/fleet/
        calendar orchestration is future work (P2/P4/P6); this contract lets
        the frontend's gating probes render a labeled placeholder instead of
        a 404/blocked UI (spec §10 acceptance gate #6)."""
        return JSONResponse(
            status_code=501,
            content={"error": "not_implemented", "capability": capability},
        )

    @app.get("/variants")
    def get_variants() -> JSONResponse:
        return _gated("variant_registry")

    @app.get("/variant/diff")
    def get_variant_diff(a: str | None = None, b: str | None = None) -> JSONResponse:
        return _gated("variant_registry")

    @app.get("/study/latest")
    def get_study_latest(instrument: str | None = None) -> JSONResponse:
        return _gated("study")

    @app.get("/study/{study_id}")
    def get_study(study_id: str) -> JSONResponse:
        return _gated("study")

    @app.get("/calendar")
    def get_calendar(within: str | None = None) -> JSONResponse:
        return _gated("calendar")

    @app.post("/replay/control")
    def post_replay_control(payload: dict) -> JSONResponse:
        return _gated("replay")

    @app.post("/variant")
    def post_variant(payload: dict) -> JSONResponse:
        return _gated("variant_registry")

    @app.post("/variant/branch")
    def post_variant_branch(payload: dict) -> JSONResponse:
        return _gated("variant_registry")

    @app.post("/study")
    def post_study(payload: dict) -> JSONResponse:
        return _gated("study")

    @app.post("/fleet")
    def post_fleet(payload: dict) -> JSONResponse:
        return _gated("fleet")

    @app.websocket("/replay")
    async def replay_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"error": "not_implemented", "capability": "replay"})
        await websocket.close()

    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    return app
