"""sentinel_engine.service.routers.runs — /api/runs*, /api/forward/* (W0.1a).

Moved verbatim out of `sentinel_engine.service.app` (plan recalibration V2,
W0.1 "split app.py into routers"). `build_router(registry, lake_root)` is
called once from `create_app()`; the returned `APIRouter` is included via
`app.include_router(...)` so every path stays byte-identical to before the
split.

Helpers (`_api_error`, `_parse_flexible_ts`, `_display_color`) are imported
lazily (inside `build_router`, not at module import time) from
`sentinel_engine.service.app` to avoid a circular import — `app.py` imports
this module at its own top-level to register the router.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..bars import BarsError, load_tf_frame
from sentinel_engine.strategies._supertrend_ref import supertrend as _supertrend_series
from sentinel_engine.strategies.emasar import EmasarPolicy, ema_series, sar_series
from sentinel_engine.strategies.emasar_ref import _atr_wilder

router = APIRouter()


def build_router(registry, lake_root) -> APIRouter:
    from ..app import _api_error, _display_color, _parse_flexible_ts

    r = APIRouter()

    @r.get("/api/runs")
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

    @r.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        row = registry.get_run(run_id)
        if row is None:
            return _api_error(404, "run_not_found", f"unknown run_id: {run_id}")
        row["display_color"] = _display_color(row.get("color_idx"))
        return row

    @r.get("/api/runs/{run_id}/trades")
    def get_run_trades(run_id: str) -> dict[str, Any]:
        return {"trades": registry.get_trades_for_run(run_id)}

    @r.get("/api/runs/{run_id}/indicators")
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

    @r.get("/api/forward/sessions")
    def get_forward_sessions() -> dict[str, Any]:
        return {"sessions": registry.query_forward_sessions()}

    @r.get("/api/forward/{session_id}/trades")
    def get_forward_session_trades(session_id: str) -> dict[str, Any]:
        return {"trades": registry.get_trades_for_session(session_id)}

    return r
