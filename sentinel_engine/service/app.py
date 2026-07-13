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
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse

from sentinel_engine.config import InstrumentConfig, load_instrument
from sentinel_engine.engine import Engine, Snapshot
from sentinel_engine.feed import Feed
from sentinel_engine.research.registry2 import STRATEGY_PALETTE, ResearchRegistry


def _parse_flexible_ts(value: str | None) -> "pd.Timestamp | None":
    """Parse a `from`/`to` query param that may arrive as EITHER epoch
    seconds/ms (a bare integer, e.g. the chart's pan-fetch `to=oldestTs-1`)
    OR an ISO-8601 string (e.g. `setWindow`'s `Date.toISOString()`).

    The chart frontend mixes both conventions; parsing a bare epoch with
    `pd.Timestamp(str, tz="UTC")` mis-reads it as a calendar YEAR and raises
    ``year 1769651099 is out of range`` → HTTP 400 → the candle window never
    loads. Accepting both here (defense-in-depth) makes any caller work.
    Returns None for empty/None so ``if from_`` semantics are preserved.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    if s.lstrip("-").isdigit():  # bare epoch: >=1e12 is milliseconds, else seconds
        n = int(s)
        return pd.Timestamp(n, unit="ms" if abs(n) >= 1_000_000_000_000 else "s", tz="UTC")
    return pd.Timestamp(s, tz="UTC")


from .routers import bars as bars_router
from .routers import chat as chat_router
from .routers import jobs as jobs_router
from .routers import news as news_router
from .routers import positions as positions_router
from .routers import runs as runs_router
from .routers import strategies as strategies_router
from .routers import system as system_router
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


class VariantCreateRequest(BaseModel):
    strategy_id: str
    variant_suffix: str
    params_delta: dict[str, Any] = {}
    tf: str | None = None
    instrumento: str | None = None
    modo_salida: str | None = None


class StrategyEstadoRequest(BaseModel):
    estado: str


class BacktestRequest(BaseModel):
    variant_id: str
    symbol: str
    tf: str = "M5"
    desde: str | None = None
    hasta: str | None = None


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
    jobs: dict = {}
    backtest_lock = asyncio.Lock()

    def _resolve(instrument: str | None) -> InstrumentRunner:
        name = instrument or next(iter(runners))
        runner = runners.get(name)
        if runner is None:
            raise HTTPException(status_code=404, detail=f"unknown instrument: {name}")
        return runner

    app.include_router(bars_router.build_router(lake_root, tick_hub))
    app.include_router(runs_router.build_router(registry, lake_root))
    app.include_router(strategies_router.build_router(registry))
    app.include_router(positions_router.build_router(registry))
    app.include_router(chat_router.build_router(runners, _resolve, app.state))
    app.include_router(jobs_router.build_router(registry, lake_root, jobs, backtest_lock))
    app.include_router(news_router.build_router(registry))
    app.include_router(system_router.build_router(runners, broadcaster))
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
    # POST /api/backtest job bookkeeping (M2.5): a plain dict of
    # job_id -> {"status","run_id"} plus a lock that serializes the actual
    # sim runs — "single-worker sequential queue" per plan §M2.5, backed by
    # FastAPI BackgroundTasks rather than a separate worker process/task.
    app.state.jobs = jobs
    app.state.backtest_lock = backtest_lock

    system_router.mount_static(app, WEB_DIR)

    return app
