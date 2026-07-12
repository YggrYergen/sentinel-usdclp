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
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from sentinel_engine.config import InstrumentConfig, config_hash, load_instrument
from sentinel_engine.engine import Engine, Snapshot
from sentinel_engine.feed import Feed
from sentinel_engine.opt.levers import LEVER_GROUPS, priors_for
from sentinel_engine.research.registry2 import STRATEGY_PALETTE, ResearchRegistry
from sentinel_engine.sim.lite import run_backtest_lite
from sentinel_engine.strategies.emasar import EmasarPolicy, ema_series, sar_series


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
from sentinel_engine.strategies._supertrend_ref import supertrend as _supertrend_series
from sentinel_engine.strategies.emasar_ref import _atr_wilder

from .bars import BarsError, bars_payload, load_tf_frame
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
    app.state.jobs = {}
    app.state.backtest_lock = asyncio.Lock()

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
            ts_from = _parse_flexible_ts(from_)
            ts_to = _parse_flexible_ts(to)
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

    @app.get("/api/runs/{run_id}/indicators")
    def get_run_indicators(
        run_id: str,
        tf: str | None = None,
        from_: str | None = Query(default=None, alias="from"),
        to: str | None = None,
    ) -> Any:
        """EMA-fast/EMA-slow/SAR/SuperTrend overlay descriptors for the
        REVIEW Trade View chart (design spec
        2026-07-09-trade-view-indicator-overlays): computed with the RUN's
        exact params (parity — same `emasar.py` functions the strategy
        itself calls), on the bars for `tf` (default: the run's native tf
        from its variant). Returns an extensible list of indicator
        descriptors, not fixed keys, so adding more later is a
        one-endpoint change.

        Defect B fix (Wave-2 plan 2026-07-10, "candle-killer"): optional
        `from`/`to` (ISO-8601, same contract as `/api/bars`) bound the
        returned points to `[from, to]` — WITHOUT this, the endpoint
        returns the entire lake history (100k+ points in production)
        regardless of the loaded candle window; since every
        lightweight-charts series shares ONE time scale, that pushes the
        actual candles off the visible logical range. The invariant this
        enforces: overlay time-range ⊆ candle time-range, never wider.
        Indicators are still COMPUTED on a frame that includes a warmup
        lookback before `from` (`lookback = max(periods) * 4` bars) so the
        in-window values are correctly seeded, not cold-started at `from`
        — only the RETURNED points are trimmed to `[from, to]`. Omitting
        both keeps the pre-existing full-frame behavior (back-compat)."""
        run = registry.get_run(run_id)
        if run is None:
            return _api_error(404, "run_not_found", f"unknown run_id: {run_id}")

        resolved_tf = tf or run.get("tf") or "M1"
        symbol = run.get("instrumento") or "XAUUSD"

        try:
            ts_from = _parse_flexible_ts(from_)
            ts_to = _parse_flexible_ts(to)
        except (ValueError, TypeError) as exc:
            return _api_error(400, "bad_range", f"invalid from/to: {exc}")

        params = registry.get_param_set(run.get("params_hash"))
        if params is None:
            variant = registry.get_variant(run.get("variant_id")) or {}
            params = dict(variant.get("params_delta") or {})
        policy_params = EmasarPolicy(params).params

        try:
            df = load_tf_frame(lake_root, symbol, resolved_tf)
        except BarsError as exc:
            return _api_error(400, "bad_tf", str(exc))

        ema_fast_period = policy_params["ema_fast"]
        ema_slow_period = policy_params["ema_slow"]
        sar_step = policy_params["sar_step"]
        sar_max = policy_params["sar_max"]
        # SuperTrend (design spec 2026-07-10-emasar-v1-mt5-integration,
        # Component 7): V1-only params, absent from V2's EmasarPolicy
        # defaults -- read raw from the run's params dict (falls back to
        # emasar_ref's own defaults: ATRPeriod=10, Mult=3.0, S6).
        st_atr_period = int(params.get("st_atr_period") or params.get("ST_ATRPeriod") or 10)
        st_mult = float(params.get("st_mult") or params.get("ST_Mult") or 3.0)

        if not df.empty and ts_from is not None:
            # Warmup lookback: enough PRIOR bars that every indicator is
            # fully seeded by `from` (ample factor over the largest period
            # among ema_fast/ema_slow/st_atr_period).
            max_period = max(ema_fast_period, ema_slow_period, st_atr_period, 1)
            lookback_bars = max_period * 4
            pos = df.index.searchsorted(ts_from, side="left")
            start_pos = max(0, pos - lookback_bars)
            df = df.iloc[start_pos:]
            if ts_to is not None:
                df = df[df.index <= ts_to]
        elif not df.empty and ts_to is not None:
            df = df[df.index <= ts_to]

        if df.empty:
            times: list[int] = []
            closes: list[float] = []
            highs: list[float] = []
            lows: list[float] = []
        else:
            times = [int(ts.value // 1_000_000_000) for ts in df.index]
            closes = df["close"].tolist()
            highs = df["high"].tolist()
            lows = df["low"].tolist()

        ema_fast_vals = ema_series(closes, ema_fast_period)
        ema_slow_vals = ema_series(closes, ema_slow_period)
        sar_vals, _sar_trend = sar_series(highs, lows, sar_step, sar_max)

        if closes:
            atr_vals = _atr_wilder(highs, lows, closes, st_atr_period)
            _st_trend, st_line = _supertrend_series(
                highs, lows, closes, [a if a is not None else 0.0 for a in atr_vals], st_mult,
            )
            supertrend_vals = [None if atr_vals[i] is None else st_line[i] for i in range(len(atr_vals))]
        else:
            supertrend_vals = []

        from_epoch = int(ts_from.value // 1_000_000_000) if ts_from is not None else None
        to_epoch = int(ts_to.value // 1_000_000_000) if ts_to is not None else None

        def _points(vals: list) -> list:
            pairs = zip(times, vals)
            if from_epoch is not None or to_epoch is not None:
                pairs = (
                    (t, v) for t, v in pairs
                    if (from_epoch is None or t >= from_epoch)
                    and (to_epoch is None or t <= to_epoch)
                )
            return [[t, v] for t, v in pairs]

        return {
            "tf": resolved_tf,
            "indicators": [
                {
                    "id": "ema_fast", "kind": "line", "label": f"EMA{ema_fast_period}",
                    "period": ema_fast_period, "points": _points(ema_fast_vals),
                },
                {
                    "id": "ema_slow", "kind": "line", "label": f"EMA{ema_slow_period}",
                    "period": ema_slow_period, "points": _points(ema_slow_vals),
                },
                {
                    "id": "sar", "kind": "dots", "label": f"SAR {sar_step}/{sar_max}",
                    "step": sar_step, "max": sar_max, "points": _points(sar_vals),
                },
                {
                    "id": "supertrend", "kind": "line",
                    "label": f"SuperTrend {st_atr_period}/{st_mult}",
                    "atr_period": st_atr_period, "mult": st_mult,
                    "points": _points(supertrend_vals),
                },
            ],
        }

    @app.get("/api/forward/sessions")
    def get_forward_sessions() -> dict[str, Any]:
        return {"sessions": registry.query_forward_sessions()}

    @app.get("/api/forward/{session_id}/trades")
    def get_forward_session_trades(session_id: str) -> dict[str, Any]:
        return {"trades": registry.get_trades_for_session(session_id)}

    # ------------------------------------------------------------------
    # Management endpoints (M2.4, plan §D.5/§D.6): create variants, flip
    # strategy estado. Minimal validation only — no full param-schema
    # engine, just a key-set check against `param_schema_json` if present.
    # ------------------------------------------------------------------
    @app.post("/api/variants")
    def post_variant_create(payload: VariantCreateRequest):
        strategy = registry.get_strategy(payload.strategy_id)
        if strategy is None:
            return _api_error(404, "strategy_not_found", f"unknown strategy_id: {payload.strategy_id}")

        schema_json = strategy.get("param_schema_json") or "{}"
        try:
            schema = json.loads(schema_json)
        except (TypeError, ValueError):
            schema = {}
        if schema:
            unknown = [k for k in payload.params_delta if k not in schema]
            if unknown:
                return _api_error(
                    400, "invalid_params_delta",
                    f"params_delta has keys not in param_schema: {unknown}",
                )

        instrumento = payload.instrumento or ""
        variant_id = f"{strategy['familia']}_{instrumento}_{payload.variant_suffix}"
        if registry.variant_exists(variant_id):
            return _api_error(409, "variant_exists", f"variant already exists: {variant_id}")

        registry.insert_variant(
            payload.strategy_id, variant_id, payload.params_delta,
            payload.tf, payload.instrumento, payload.modo_salida,
        )
        try:
            registry.allocate_magic(payload.strategy_id, variant_id)
        except ValueError as exc:
            return _api_error(400, "magic_allocation_failed", str(exc))
        registry.audit("api", "variant_created", {
            "strategy_id": payload.strategy_id, "variant_id": variant_id,
            "params_delta": payload.params_delta,
        })
        return {"variant_id": variant_id}

    _VALID_ESTADOS = {"activa", "pausada", "graduada"}

    @app.post("/api/strategies/{strategy_id}/estado")
    def post_strategy_estado(strategy_id: str, payload: StrategyEstadoRequest):
        if registry.get_strategy(strategy_id) is None:
            return _api_error(404, "strategy_not_found", f"unknown strategy_id: {strategy_id}")
        if payload.estado not in _VALID_ESTADOS:
            return _api_error(
                400, "invalid_estado",
                f"estado must be one of {sorted(_VALID_ESTADOS)}: got {payload.estado!r}",
            )
        registry.set_strategy_estado(strategy_id, payload.estado)
        registry.audit("api", "strategy_estado_changed", {
            "strategy_id": strategy_id, "estado": payload.estado,
        })
        return {"strategy_id": strategy_id, "estado": payload.estado}

    # ------------------------------------------------------------------
    # Backtest-lite job endpoints (M2.5, plan §D.6/§B1 minimal slice)
    # ------------------------------------------------------------------
    def _build_policy(variant: dict[str, Any]):
        """Policy dispatch by `familia` — only EMASAR exists in this lean
        M2.5 slice; other families are rejected with a clear error rather
        than silently defaulting to the wrong strategy."""
        familia = (variant.get("familia") or "").lower()
        if familia != "emasar":
            raise ValueError(f"no backtest-lite policy registered for familia: {familia!r}")
        return EmasarPolicy(variant.get("params_delta") or {})

    def _run_backtest_job(job_id: str, variant_id: str, symbol: str, tf: str,
                           desde: str | None, hasta: str | None) -> None:
        jobs = app.state.jobs
        jobs[job_id]["status"] = "running"
        try:
            variant = registry.get_variant(variant_id)
            if variant is None:
                raise ValueError(f"unknown variant_id: {variant_id}")
            policy = _build_policy(variant)
            run, trades = run_backtest_lite(
                policy, symbol, tf, desde, hasta, lake_root=lake_root,
            )
            run_id = f"sim-{uuid.uuid4().hex[:16]}"
            run["run_id"] = run_id
            run["variant_id"] = variant_id
            for t in trades:
                t["trade_id"] = f"simtr-{uuid.uuid4().hex[:16]}"
            registry.insert_run(run)
            registry.insert_trades(run_id, trades)
            registry.audit("api", "backtest_done", {
                "job_id": job_id, "variant_id": variant_id, "run_id": run_id,
                "trades": len(trades),
            })
            jobs[job_id]["status"] = "done"
            jobs[job_id]["run_id"] = run_id
        except Exception as exc:  # noqa: BLE001 - job errors are reported via GET /api/jobs, never raised
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(exc)
            registry.audit("api", "backtest_failed", {"job_id": job_id, "variant_id": variant_id, "error": str(exc)})

    async def _run_backtest_job_locked(job_id: str, variant_id: str, symbol: str, tf: str,
                                        desde: str | None, hasta: str | None) -> None:
        async with app.state.backtest_lock:
            await asyncio.to_thread(_run_backtest_job, job_id, variant_id, symbol, tf, desde, hasta)

    @app.post("/api/backtest")
    def post_backtest(payload: BacktestRequest, background_tasks: BackgroundTasks):
        if registry.get_variant(payload.variant_id) is None:
            return _api_error(404, "variant_not_found", f"unknown variant_id: {payload.variant_id}")
        job_id = f"job-{uuid.uuid4().hex[:16]}"
        app.state.jobs[job_id] = {"status": "queued", "run_id": None}
        background_tasks.add_task(
            _run_backtest_job_locked, job_id, payload.variant_id, payload.symbol,
            payload.tf, payload.desde, payload.hasta,
        )
        return {"job_id": job_id, "status": "queued"}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        job = app.state.jobs.get(job_id)
        if job is None:
            return _api_error(404, "job_not_found", f"unknown job_id: {job_id}")
        out = {"status": job["status"]}
        if job.get("run_id"):
            out["run_id"] = job["run_id"]
        if job.get("error"):
            out["error"] = job["error"]
        return out

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
        # `no-cache` (revalidate every time), NOT `no-store`: the browser still
        # keeps a copy but must revalidate via ETag/Last-Modified on each load,
        # so StaticFiles returns 304 when unchanged and fresh 200 the moment a
        # file is edited. Without this, StaticFiles sends no Cache-Control and
        # browsers heuristically serve stale app.js/style.css from memory cache
        # on a plain F5 — making edits appear to have "no effect" until a hard
        # reload. This keeps local dev edits always visible.
        class _NoCacheStatic(StaticFiles):
            async def get_response(self, path, scope):
                response = await super().get_response(path, scope)
                response.headers["Cache-Control"] = "no-cache"
                return response

        app.mount("/", _NoCacheStatic(directory=str(WEB_DIR), html=True), name="web")

    return app
