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

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from sentinel_engine.config import InstrumentConfig, config_hash, load_instrument
from sentinel_engine.engine import Engine, Snapshot
from sentinel_engine.feed import Feed
from sentinel_engine.opt.levers import LEVER_GROUPS, priors_for
from sentinel_engine.research.registry2 import STRATEGY_PALETTE, ResearchRegistry

from .bars import BarsError, bars_payload
from .chat import answer_chat
from .stream import Broadcaster, TickHub

DEFAULT_INSTRUMENTS: tuple[str, ...] = ("usdclp", "gold", "nasdaq")
WEB_DIR = Path(__file__).resolve().parents[2] / "web"
DEFAULT_RESEARCH_DB = Path("data/research.db")
DEFAULT_LAKE_ROOT = Path("data/lake")


def _default_tick_source(symbol: str) -> tuple[float, float] | None:
    """Read-only MT5 tick source for production (`ticks:{SYMBOL}`, plan
    §D.6): `mt5.symbol_info_tick` ONLY — never any order-side function.
    Returns `None` (no push) if MT5 isn't available/initialized or the
    symbol has no tick yet; imported lazily so this module has no hard MT5
    dependency (tests inject a fake `tick_source` instead)."""
    try:
        import MetaTrader5 as mt5  # noqa: N813 - matches package's own casing
    except ImportError:
        return None
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None
    return float(tick.bid), float(tick.ask)


def _display_color(color_idx: int | None) -> str | None:
    if color_idx is None:
        return None
    return STRATEGY_PALETTE[color_idx % len(STRATEGY_PALETTE)]


def _api_error(status_code: int, code: str, message: str) -> JSONResponse:
    """Normative error envelope (plan §D.6): `{"error":{"code","message"}}`."""
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


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
    registry: ResearchRegistry | None = None,
    lake_root: Path | None = None,
    tick_source: Callable[[str], tuple[float, float] | None] | None = None,
    tick_poll_interval: float = 0.25,
) -> FastAPI:
    """Build the SENTINEL FastAPI service.

    `feed_factory(instrument_name) -> Feed` is called once per instrument at
    startup (production wires a `LiveMT5Feed`; tests inject a shared
    `FakeFeed`). `autostart_loop=False` disables the periodic background
    compute loop (useful for HTTP-only tests that don't want a ticking
    background task).

    `registry` (M0.3): the `ResearchRegistry` backing `/api/strategies`,
    `/api/runs*`, `/api/forward/*` and `POST /api/ingest/tokata`. Tests
    inject a `tmp_path`-backed registry; production defaults to
    `data/research.db` (created lazily on first use, same DDL as M0.1).

    `lake_root` (M1.2): Parquet lake root backing `GET /api/bars`; defaults
    to `data/lake` (see `sentinel_engine.lake.store`).

    `tick_source` (M1.2): read-only `symbol -> (bid, ask) | None` callable
    backing the `ticks:{SYMBOL}` WS channel; defaults to
    `_default_tick_source` (lazy MT5 import, never any order function).
    Tests inject a fake for plumbing without an MT5 dependency.
    """
    if registry is None:
        registry = ResearchRegistry(DEFAULT_RESEARCH_DB)
    if lake_root is None:
        lake_root = DEFAULT_LAKE_ROOT
    lake_root = Path(lake_root)
    if tick_source is None:
        tick_source = _default_tick_source

    runners: dict[str, InstrumentRunner] = {}
    for name in instruments:
        cfg = load_instrument(name)
        runners[name] = InstrumentRunner(name, cfg, feed_factory(name))
        runners[name].compute()  # seed seq=0 so GET /snapshot works pre-loop

    broadcaster = Broadcaster()
    tick_hub = TickHub(tick_source, poll_interval=tick_poll_interval)

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
            for sym_task in list(tick_hub._tasks.values()):  # noqa: SLF001 - shutdown-only cleanup
                sym_task.cancel()

    app = FastAPI(title="SENTINEL", lifespan=lifespan)
    app.state.runners = runners
    app.state.broadcaster = broadcaster
    app.state.compute_and_broadcast_once = _compute_and_broadcast_once
    # Optional injected assistant client (tests only) — None uses the default
    # `sentinel.ai_chat.SentinelAI()`, which mock-answers offline when no
    # ANTHROPIC_API_KEY is set. See `.chat.answer_chat`.
    app.state.chat_client = None
    app.state.registry = registry
    app.state.lake_root = lake_root
    app.state.tick_hub = tick_hub

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

    # ------------------------------------------------------------------
    # /api/bars + ticks:{SYMBOL} WS channel (M1.2, plan §D.6)
    # ------------------------------------------------------------------
    @app.get("/api/bars")
    def get_bars(
        symbol: str,
        tf: str = "M1",
        from_: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        max_points: int = 3000,
    ) -> Any:
        try:
            ts_from = pd.Timestamp(from_, tz="UTC") if from_ else None
            ts_to = pd.Timestamp(to, tz="UTC") if to else None
        except (ValueError, TypeError) as exc:
            return _api_error(400, "bad_range", f"invalid from/to: {exc}")
        try:
            payload = bars_payload(lake_root, symbol, tf, ts_from, ts_to, max_points)
        except BarsError as exc:
            return _api_error(400, "bad_tf", str(exc))
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the client
            return _api_error(500, "bars_failed", str(exc))
        return payload

    @app.websocket("/ws/ticks")
    async def ticks_ws(websocket: WebSocket) -> None:
        """`ticks:{SYMBOL}` channel (plan §D.6): client sends
        `{"sub":"ticks:XAUUSD"}` / `{"unsub":"ticks:XAUUSD"}`; server pushes
        `{"ch":"ticks:XAUUSD","t":epoch_ms,"bid","ask"}` on-change ~250ms,
        only while this socket (or another) is subscribed to that symbol.
        Subscribing to a second symbol on the same socket is additive."""
        await websocket.accept()
        subscribed: set[str] = set()
        try:
            while True:
                msg = await websocket.receive_json()
                sub = msg.get("sub")
                unsub = msg.get("unsub")
                if isinstance(sub, str) and sub.startswith("ticks:"):
                    symbol = sub[len("ticks:"):]
                    await tick_hub.subscribe(websocket, symbol)
                    subscribed.add(symbol)
                if isinstance(unsub, str) and unsub.startswith("ticks:"):
                    symbol = unsub[len("ticks:"):]
                    await tick_hub.unsubscribe(websocket, symbol)
                    subscribed.discard(symbol)
        except WebSocketDisconnect:
            pass
        finally:
            for symbol in list(subscribed):
                await tick_hub.unsubscribe(websocket, symbol)

    # ------------------------------------------------------------------
    # Research data endpoints (M0.3, plan §D.6)
    # ------------------------------------------------------------------
    @app.get("/api/strategies")
    def get_strategies() -> dict[str, Any]:
        rows = registry.query_strategies()
        for row in rows:
            row["display_color"] = _display_color(row.get("color_idx"))
        return {"strategies": rows}

    @app.get("/api/runs")
    def get_runs(
        strategy_id: str | None = None,
        variant_id: str | None = None,
        instrumento: str | None = None,
        engine: str | None = None,
        fidelity: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        order_by: str = "fecha_corrida",
        dir: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        return registry.query_runs(
            strategy_id=strategy_id,
            variant_id=variant_id,
            instrumento=instrumento,
            engine=engine,
            fidelity=fidelity,
            desde=desde,
            hasta=hasta,
            order_by=order_by,
            dir=dir,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        row = registry.get_run(run_id)
        if row is None:
            return _api_error(404, "run_not_found", f"unknown run_id: {run_id}")
        row["display_color"] = _display_color(row.get("color_idx"))
        return row

    @app.get("/api/runs/{run_id}/trades")
    def get_run_trades(run_id: str) -> dict[str, Any]:
        return {"trades": registry.get_trades_for_run(run_id)}

    @app.get("/api/forward/sessions")
    def get_forward_sessions() -> dict[str, Any]:
        return {"sessions": registry.query_forward_sessions()}

    @app.get("/api/forward/{session_id}/trades")
    def get_forward_session_trades(session_id: str) -> dict[str, Any]:
        return {"trades": registry.get_trades_for_session(session_id)}

    @app.post("/api/ingest/tokata")
    def post_ingest_tokata(payload: dict[str, Any] | None = None):
        from sentinel_engine.ingest_tokata.runner import import_all

        payload = payload or {}
        root_raw = payload.get("tokata_root") or "D:/WebDev/TOKATA"
        root = Path(root_raw)
        if not root.exists() or not root.is_dir():
            return _api_error(404, "tokata_root_not_found", f"tokata_root does not exist: {root}")
        try:
            report = import_all(root, registry)
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the client
            return _api_error(500, "ingest_failed", str(exc))
        return {
            "files": report.files,
            "rows_new": report.rows_new,
            "rows_skipped": report.rows_skipped,
            "errors": report.errors,
        }

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
