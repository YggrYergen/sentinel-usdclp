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

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from ..bars import BarsError, load_tf_frame
from sentinel_engine.strategies._supertrend_ref import supertrend as _supertrend_series
from sentinel_engine.strategies.emasar import (
    EmasarPolicy,
    ac_series,
    ao_series,
    ema_series,
    momentum_series,
    sar_series,
)
from sentinel_engine.strategies.emasar_ref import _atr_wilder

import re

router = APIRouter()


def _sar_from_variant_token(variant_id: str) -> tuple[float, float] | None:
    """MT5-imported runs often carry NO stored param set (params_hash None,
    params_delta {}), so EmasarPolicy falls back to defaults (SAR 0.02/0.2)
    and the chart draws the WRONG SAR steps. The exact steps are encoded in
    the variant_id token `sarNmM` where each group is the decimal fraction:
    sar3m3 -> 0.3/0.3, sar005m05 -> 0.005/0.05, sar01m1 -> 0.01/0.1,
    sar02m2 -> 0.02/0.2 (value = int(digits) / 10**len(digits)). Returns
    (step, max) or None if the token is absent."""
    m = re.search(r"sar([0-9]+)m([0-9]+)", variant_id or "", re.IGNORECASE)
    if not m:
        return None
    step_d, max_d = m.group(1), m.group(2)
    step = int(step_d) / (10 ** len(step_d))
    sar_max = int(max_d) / (10 ** len(max_d))
    return step, sar_max


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

    @r.get("/api/runs/{run_id}/equity")
    def get_run_equity(run_id: str) -> Any:
        """Equity curve for the REVIEW Trade View (task B8):
        `{"points":[{"t":epoch_s,"v":equity_value}]}`. Prefers a
        pre-computed equity artifact (`run.artifacts.equity_path`, same
        mechanism `/api/runs/{id}` already exposes) when present on disk
        as a JSON file already shaped `{"points":[...]}`; otherwise falls
        back to cumulative pnl over the run's trades (same
        `registry.get_trades_for_run` the `/trades` endpoint uses),
        ordered by `ts_out` (a trade's pnl realizes at exit)."""
        run = registry.get_run(run_id)
        if run is None:
            return _api_error(404, "run_not_found", f"unknown run_id: {run_id}")

        equity_path = (run.get("artifacts") or {}).get("equity_path")
        if equity_path:
            path = Path(equity_path)
            if path.is_file():
                try:
                    with path.open("r", encoding="utf-8") as fh:
                        return json.load(fh)
                except (json.JSONDecodeError, OSError):
                    pass  # corrupt/unreadable artifact -> fall back to trades below

        trades = registry.get_trades_for_run(run_id)
        trades_sorted = sorted(trades, key=lambda t: t.get("ts_out") or "")

        points: list[dict[str, Any]] = []
        cum = 0.0
        for t in trades_sorted:
            ts_out = t.get("ts_out")
            if not ts_out:
                continue
            ts = _parse_flexible_ts(ts_out)
            if ts is None:
                continue
            cum += float(t.get("pnl") or 0.0)
            if hasattr(ts, "value"):
                epoch_s = int(ts.value // 1_000_000_000)
            else:
                epoch_s = int(ts.timestamp())
            points.append({"t": epoch_s, "v": cum})

        return {"points": points}

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
        # ---- FIX 5 / D80: EVERY indicator is ALWAYS returned for EVERY run so
        # the whole set is toggleable in the selector on any run. The previous
        # design BRANCHED by strategy family (SuperTrend run got ONLY
        # SuperTrend; EMASAR got only its family) -- the user wants all of
        # EMA8/EMA20/EMA5/SAR/SuperTrend + the AO/AC/Momentum subpanel present
        # on every run. The family only decides which indicators come toggled
        # ON by default (`default_on`): the rest are present but OFF. Exact
        # params per variant are preserved (SAR token fallback, ATR14/mult3 for
        # the standalone SuperTrend run vs ATR10/mult3 for the V1-internal F2
        # SuperTrend, EMA5 pullback for V2).
        strategy_id = str(run.get("strategy_id") or "")
        family = strategy_id.split("::", 1)[0].lower()
        variant_id = str(run.get("variant_id") or "")
        is_supertrend_family = family == "supertrend"
        is_v2 = "_V2_" in variant_id.upper()

        try:
            df = load_tf_frame(lake_root, symbol, resolved_tf)
        except BarsError as exc:
            return _api_error(400, "bad_tf", str(exc))

        # EMA periods: EMASAR runs read them from the policy; a SuperTrend run
        # has no EMASAR params, so fall back to the manifest defaults (8/20/5)
        # so the (toggle-off-by-default) EMA overlays still render sensibly.
        if is_supertrend_family:
            ema_fast_period = 8
            ema_slow_period = 20
            sar_step, sar_max = 0.02, 0.2
        else:
            policy_params = EmasarPolicy(params).params
            ema_fast_period = policy_params["ema_fast"]
            ema_slow_period = policy_params["ema_slow"]
            sar_step = policy_params["sar_step"]
            sar_max = policy_params["sar_max"]
        # Exact SAR steps: prefer stored params; else recover from the
        # variant_id `sarNmM` token (MT5 imports have no stored param set, so
        # EmasarPolicy defaulted to 0.02/0.2 -- wrong for sar3m3 etc.).
        if not params.get("sar_step"):
            token = _sar_from_variant_token(variant_id)
            if token is not None:
                sar_step, sar_max = token
        # EMA5 pullback is always available; on-by-default only for V2.
        ema_pullback_period = 5
        momentum_period = 14
        # SuperTrend params: the standalone SuperTrend run uses ATR14/mult3
        # (its only signal); the V1-internal F2 exit uses ATR10/mult3. Both are
        # drawable on any run -- pick the params matching the run's family.
        if is_supertrend_family:
            st_atr_period = int(params.get("atr_period") or params.get("ST_ATRPeriod")
                                or params.get("st_atr_period") or 14)
            st_mult = float(params.get("mult") or params.get("ST_Mult")
                            or params.get("st_mult") or 3.0)
        else:
            st_atr_period = int(params.get("st_atr_period") or params.get("ST_ATRPeriod") or 10)
            st_mult = float(params.get("st_mult") or params.get("ST_Mult") or 3.0)
        max_period = max(ema_fast_period, ema_slow_period, st_atr_period, 34, 1)

        if not df.empty and ts_from is not None:
            # Warmup lookback: enough PRIOR bars that every indicator is fully
            # seeded by `from` (ample factor over the largest period -- 34 for
            # AO's slow SMA is included above).
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

        if closes:
            st_atr_vals = _atr_wilder(highs, lows, closes, st_atr_period)
            _st_trend, st_line = _supertrend_series(
                highs, lows, closes, [a if a is not None else 0.0 for a in st_atr_vals], st_mult,
            )
            supertrend_vals = [None if st_atr_vals[i] is None else st_line[i]
                               for i in range(len(st_atr_vals))]
        else:
            supertrend_vals = []

        # FIX 5 / D80: compute the FULL indicator set for EVERY run. The
        # `default_on` flag (per family) decides which chips start toggled ON;
        # every indicator is present in the list so the selector can toggle any
        # of them on any run.
        ema_fast_vals = ema_series(closes, ema_fast_period) if closes else []
        ema_slow_vals = ema_series(closes, ema_slow_period) if closes else []
        ema_pullback_vals = ema_series(closes, ema_pullback_period) if closes else []
        sar_vals, _sar_trend = sar_series(highs, lows, sar_step, sar_max) if closes else ([], [])
        # Extra fixed SAR(0.3/0.3) overlay, ALWAYS available IN ADDITION to the
        # run's native SAR (user request 2026-07-13: "agregar el SAR de 0.3/0.3,
        # dejarlo además del que ya está"). Skipped only when the run's native
        # SAR IS already 0.3/0.3 (the sar3m3 V1 run) to avoid a duplicate chip.
        sar33_step, sar33_max = 0.3, 0.3
        include_sar33 = not (abs(sar_step - sar33_step) < 1e-9 and abs(sar_max - sar33_max) < 1e-9)
        sar33_vals, _sar33_trend = (
            sar_series(highs, lows, sar33_step, sar33_max) if (closes and include_sar33) else ([], [])
        )
        ao_vals = ao_series(highs, lows) if closes else []
        ac_vals = ac_series(highs, lows) if closes else []
        mom_vals = momentum_series(closes, momentum_period) if closes else []

        # Default-ON set per family (the run's own strategy indicators):
        #  - EMASAR V1: EMA8, EMA20, SAR, SuperTrend (F2 internal, ATR10/mult3).
        #  - EMASAR V2: EMA8, EMA20, EMA5 (pullback), SAR (NO SuperTrend by
        #    default -- V2 has no F2 exit -- but it stays toggleable).
        #  - SuperTrend run: SuperTrend only (ATR14/mult3).
        if is_supertrend_family:
            default_on = {"supertrend"}
        elif is_v2:
            default_on = {"ema_fast", "ema_slow", "ema_pullback", "sar"}
        else:
            default_on = {"ema_fast", "ema_slow", "sar", "supertrend"}

        indicators: list[dict[str, Any]] = [
            {
                "id": "ema_fast", "kind": "line", "label": f"EMA{ema_fast_period}",
                "period": ema_fast_period, "panel": "price",
                "default_on": "ema_fast" in default_on,
                "points": _points(ema_fast_vals),
            },
            {
                "id": "ema_slow", "kind": "line", "label": f"EMA{ema_slow_period}",
                "period": ema_slow_period, "panel": "price",
                "default_on": "ema_slow" in default_on,
                "points": _points(ema_slow_vals),
            },
            {
                "id": "ema_pullback", "kind": "line", "label": f"EMA{ema_pullback_period}",
                "period": ema_pullback_period, "panel": "price",
                "default_on": "ema_pullback" in default_on,
                "points": _points(ema_pullback_vals),
            },
            {
                "id": "sar", "kind": "dots", "label": f"SAR {sar_step}/{sar_max}",
                "step": sar_step, "max": sar_max, "panel": "price",
                "default_on": "sar" in default_on,
                "points": _points(sar_vals),
            },
            *([{
                "id": "sar_3_3", "kind": "dots", "label": "SAR 0.3/0.3",
                "step": sar33_step, "max": sar33_max, "panel": "price",
                "default_on": False,  # extra overlay, off by default
                "points": _points(sar33_vals),
            }] if include_sar33 else []),
            {
                "id": "supertrend", "kind": "line",
                "label": f"SuperTrend {st_atr_period}/{st_mult}",
                "atr_period": st_atr_period, "mult": st_mult, "panel": "price",
                "default_on": "supertrend" in default_on,
                "points": _points(supertrend_vals),
            },
            {
                "id": "ao", "kind": "histogram", "label": "AO",
                "panel": "oscillator", "default_on": False,
                "points": _points(ao_vals),
            },
            {
                "id": "ac", "kind": "histogram", "label": "AC",
                "panel": "oscillator", "default_on": False,
                "points": _points(ac_vals),
            },
            {
                "id": "momentum", "kind": "line", "label": f"Mom {momentum_period}",
                "period": momentum_period, "panel": "oscillator", "default_on": False,
                "points": _points(mom_vals),
            },
        ]

        return {
            "tf": resolved_tf,
            "indicators": indicators,
        }

    @r.get("/api/forward/sessions")
    def get_forward_sessions() -> dict[str, Any]:
        return {"sessions": registry.query_forward_sessions()}

    @r.get("/api/forward/{session_id}/trades")
    def get_forward_session_trades(session_id: str) -> dict[str, Any]:
        return {"trades": registry.get_trades_for_session(session_id)}

    return r
