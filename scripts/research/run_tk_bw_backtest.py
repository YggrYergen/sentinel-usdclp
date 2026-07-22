"""scripts/research/run_tk_bw_backtest.py -- data RUNNER for the TK-BW
strategy (Task 2, `docs/superpowers/plans/2026-07-21-tk-bw-backtest.md`).

Loads REAL XAUUSD bars from the lake, drives the pure engine
`sentinel_engine.strategies.tk_bw.tk_bw_run` (Task 1, committed fe7e775) for
each TF in {M15, M5, M2} over "yesterday+today" (2026-07-20 -> last available
bar, or `--hasta`), and registers the 3 backtests as runs in
`data/research.db` so they show up in the Sentinel UI's "runs" list and
Trade View (REVIEW). NO optimization, NO parameter sweeps -- this runs the
trader's exact strategy once per TF and registers it.

This module does NOT modify `tk_bw.py` (the engine) -- it only builds the
`steps` sequence the engine consumes and persists the resulting trades.

steps contract (see tk_bw.py module docstring):
    {"ts": epoch_s, "closed": list[bar asc], "forming": bar|None,
     "price": float, "is_close": bool}
    bar = {"t","open","high","low","close"}  (BID)
Two invariants this builder MUST uphold (engine author, binding):
  1. The just-finalized native candle is appended to `closed` at the
     `is_close` step BEFORE the next step's `closed` is built (off-by-one
     on the "previous"-value slope checks otherwise).
  2. EVERY bar (closed entries AND forming) has `open` within [low, high]
     (the engine's gap-open stop-fill rule keys off `forming["open"]`).

Convención de spread / fills + params EXACTS: see the plan's "Convención de
spread / fills" and "Global Constraints" sections -- spread=0.60,
commission=0, ema_fast=5, ema_slow=8, sar_step=0.3, sar_max=30.0,
mom_period=14, st_period=14, st_mult=3.0, be_trigger=0.60, trail_usd=5.0,
init_sl_offset=0.60, 3 fichas of 0.01 lot, 1 position max. Values are exact,
not tunable via CLI (this is a one-shot registration run, not a sweep).

Usage:
    python -m scripts.research.run_tk_bw_backtest              # dry-run (default)
    python -m scripts.research.run_tk_bw_backtest --write       # persist to data/research.db
    python -m scripts.research.run_tk_bw_backtest --write --hasta 2026-07-21T16:58:00Z
    python -m scripts.research.run_tk_bw_backtest --lake-root D:/other/lake --db D:/other/research.db

Deterministic given the lake: no wall-clock in the simulation logic itself
(`fecha_corrida` on the registered run is wall-clock, per plan).
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Repo root on sys.path -- keeps `python scripts/research/run_tk_bw_backtest.py`
# working in addition to `python -m scripts.research.run_tk_bw_backtest` (same
# bootstrap pattern as scripts/report/mark_validity_2026_07_19.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd  # noqa: E402

from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402
from sentinel_engine.service.bars import load_tf_frame  # noqa: E402
from sentinel_engine.strategies.emasar import _DEFAULT_PARAMS as _EMASAR_DEFAULTS  # noqa: E402
from sentinel_engine.strategies.emasar import EmasarPolicy  # noqa: E402
from sentinel_engine.strategies.tk_bw import tk_bw_run  # noqa: E402

SYMBOL = "XAUUSD"
TFS: tuple[str, ...] = ("M15", "M5", "M2")
NATIVE_TF_MINUTES = {"M15": 15, "M5": 5, "M2": 2}

# ---------------------------------------------------------------------------
# Engine params -- EXACT values from the plan's "Global Constraints" (verbatim,
# not CLI-tunable: this is a one-shot registration run, not a sweep).
# ---------------------------------------------------------------------------
SPREAD = 0.60
COMMISSION = 0.0
EMA_FAST = 5
EMA_SLOW = 8
SAR_STEP = 0.3
SAR_MAX = 30.0
MOM_PERIOD = 14
ST_PERIOD = 14
ST_MULT = 3.0
BE_TRIGGER = 0.60
TRAIL_USD = 5.0
INIT_SL_OFFSET = 0.60
VOLUME = 0.01

DESDE_DEFAULT = pd.Timestamp("2026-07-20T00:00:00Z")
WARMUP_LOOKBACK = pd.Timedelta(days=2)  # >= ~2 days of native history before `desde`

STRATEGY_NAME = "tk_bw"
STRATEGY_FAMILIA = "TK"  # MUST NOT be "supertrend" -- UI overlay draws EMA/SAR/ST/AO/AC/MOM.
STRATEGY_PLATFORM = "python-sim"

DB_PATH_DEFAULT = _REPO_ROOT / "data" / "research.db"
LAKE_ROOT_DEFAULT = _REPO_ROOT / "data" / "lake"


# ---------------------------------------------------------------------------
# steps builder
# ---------------------------------------------------------------------------
def _df_to_bars(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Lake OHLCV frame (tz-aware UTC DatetimeIndex) -> list of
    {"t": epoch_s, "open","high","low","close"} dicts, ascending, with
    `open` clamped into [low, high] (defensive -- lake data should already
    satisfy this, but the engine's gap-open rule depends on it holding for
    every bar including `forming`)."""
    out = []
    for ts, row in df.iterrows():
        epoch_s = int(ts.value // 1_000_000_000)
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        lo, hi = min(l, o, c), max(h, o, c)
        o = min(max(o, lo), hi)
        out.append({"t": epoch_s, "open": o, "high": hi, "low": lo, "close": c})
    return out


def _period_start(epoch_s: int, tf_minutes: int) -> int:
    """Floor `epoch_s` to the start of its native `tf_minutes` period."""
    period_s = tf_minutes * 60
    return (epoch_s // period_s) * period_s


def build_steps(
    native_bars: list[dict[str, Any]],
    m1_bars: list[dict[str, Any]],
    tf_minutes: int,
    desde_epoch: int,
    hasta_epoch: int,
) -> list[dict[str, Any]]:
    """Build the `steps` sequence for `tk_bw_run`, per the plan's "How to
    build steps" section.

    `native_bars`/`m1_bars`: full ascending lists (already loaded, BID,
    open-in-[low,high]). `closed` is seeded with every native bar with
    t < desde_epoch (warmup, unbounded lookback -- caller pre-filters via
    WARMUP_LOOKBACK). Then M1 bars in [desde_epoch, hasta_epoch] are grouped
    into native periods; for each M1 bar the `forming` aggregate is updated
    and a step is emitted. On the M1 bar that finalizes a native period
    (`is_close=True`), the AUTHORITATIVE native parquet candle for that
    period (NOT the M1 aggregate) is appended to `closed` -- but only AFTER
    this step is emitted (so `is_close`'s own step still sees `forming` as
    the just-completed candle, per the engine's step contract: `forming`
    passes to `closed` on the NEXT step)."""
    native_by_period = {b["t"]: b for b in native_bars}

    closed: list[dict[str, Any]] = [b for b in native_bars if b["t"] < desde_epoch]
    closed.sort(key=lambda b: b["t"])

    steps: list[dict[str, Any]] = []
    forming: dict[str, Any] | None = None
    forming_period: int | None = None

    for m1 in m1_bars:
        t = m1["t"]
        if t < desde_epoch or t > hasta_epoch:
            continue
        period = _period_start(t, tf_minutes)

        if forming_period != period:
            # New native period starts: reset the forming aggregate.
            forming = {
                "t": period,
                "open": m1["open"],
                "high": m1["high"],
                "low": m1["low"],
                "close": m1["close"],
            }
            forming_period = period
        else:
            forming["high"] = max(forming["high"], m1["high"])
            forming["low"] = min(forming["low"], m1["low"])
            forming["close"] = m1["close"]
        # Keep open within [low, high] (invariant 2).
        forming["open"] = min(max(forming["open"], forming["low"]), forming["high"])

        period_end = period + tf_minutes * 60
        is_close = (t + 60) >= period_end  # this M1 is the last within its native period

        steps.append({
            "ts": t,
            "closed": list(closed),
            "forming": dict(forming),
            "price": m1["close"],
            "is_close": is_close,
        })

        if is_close:
            # Append the AUTHORITATIVE native parquet candle (not the M1
            # aggregate) so indicators match the UI exactly -- invariant 1:
            # this happens AFTER the is_close step was appended above, so
            # THIS step's `closed` (already captured via list(closed)) does
            # NOT yet include it; the NEXT step's `closed` does.
            native_candle = native_by_period.get(period)
            if native_candle is not None:
                closed.append(native_candle)
            else:
                # Lake gap: no authoritative native candle for this period
                # (shouldn't happen inside coverage, but degrade gracefully
                # rather than silently dropping the period) -- fall back to
                # the M1-built aggregate.
                closed.append(dict(forming))
            forming = None
            forming_period = None

    return steps


# ---------------------------------------------------------------------------
# metrics (pattern from sentinel_engine/sim/lite.py ~171-206)
# ---------------------------------------------------------------------------
def compute_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    net = sum(t["pnl"] for t in trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    wr = (100.0 * len(wins) / len(trades)) if trades else 0.0
    payoff = ((gross_win / len(wins)) / (gross_loss / len(losses))) if wins and losses else 0.0

    by_ts_out = sorted(trades, key=lambda t: t["ts_out"])
    equity = 0.0
    peak = 0.0
    maxdd = 0.0
    for t in by_ts_out:
        equity += t["pnl"]
        peak = max(peak, equity)
        maxdd = max(maxdd, peak - equity)

    return {
        "trades": len(trades),
        "net": net,
        "pf": None if pf == float("inf") else pf,
        "wr": wr,
        "payoff": payoff,
        "maxdd": maxdd,
    }


# ---------------------------------------------------------------------------
# EmasarPolicy-complete params_delta (for the UI indicator overlay)
# ---------------------------------------------------------------------------
def build_params_delta() -> dict[str, Any]:
    """`params_delta` dict, complete against `EmasarPolicy`'s defaults, with
    the TK-BW overrides so `EmasarPolicy(params_delta).params` does not raise
    and `/api/runs/{id}/indicators` reads EMA5/EMA8/SAR(0.3,30)/ST(14,3)
    exactly, per the plan."""
    params = dict(_EMASAR_DEFAULTS)
    params.update({
        "ema_fast": EMA_FAST,
        "ema_slow": EMA_SLOW,
        "sar_step": SAR_STEP,
        "sar_max": SAR_MAX,
        "st_atr_period": ST_PERIOD,
        "st_mult": ST_MULT,
        "mom_period": MOM_PERIOD,
    })
    return params


# ---------------------------------------------------------------------------
# per-TF run
# ---------------------------------------------------------------------------
class TfResult:
    __slots__ = ("tf", "trades", "metrics", "coverage_first", "coverage_last",
                 "desde", "hasta", "run_id", "variant_id", "regime_lookback")

    def __init__(self, tf):
        self.tf = tf
        self.regime_lookback = 1


def run_one_tf(
    tf: str,
    lake_root: Path,
    desde: pd.Timestamp,
    hasta: pd.Timestamp | None,
    regime_lookback: int = 1,
) -> TfResult:
    tf_minutes = NATIVE_TF_MINUTES[tf]

    native_df = load_tf_frame(lake_root, SYMBOL, tf)
    m1_df = load_tf_frame(lake_root, SYMBOL, "M1")

    result = TfResult(tf)
    result.regime_lookback = regime_lookback
    result.desde = desde
    result.coverage_first = native_df.index.min() if not native_df.empty else None
    result.coverage_last = native_df.index.max() if not native_df.empty else None

    if hasta is None:
        hasta = result.coverage_last if result.coverage_last is not None else desde

    result.hasta = hasta

    warmup_start = desde - WARMUP_LOOKBACK
    native_window = native_df[native_df.index >= warmup_start]
    native_window = native_window[native_window.index <= hasta]
    m1_window = m1_df[m1_df.index >= warmup_start]
    m1_window = m1_window[m1_window.index <= hasta]

    native_bars = _df_to_bars(native_window)
    m1_bars = _df_to_bars(m1_window)

    desde_epoch = int(desde.timestamp())
    hasta_epoch = int(hasta.timestamp())

    steps = build_steps(native_bars, m1_bars, tf_minutes, desde_epoch, hasta_epoch)

    trades = tk_bw_run(
        steps,
        spread=SPREAD,
        commission=COMMISSION,
        ema_fast=EMA_FAST,
        ema_slow=EMA_SLOW,
        sar_step=SAR_STEP,
        sar_max=SAR_MAX,
        mom_period=MOM_PERIOD,
        st_period=ST_PERIOD,
        st_mult=ST_MULT,
        be_trigger=BE_TRIGGER,
        trail_usd=TRAIL_USD,
        init_sl_offset=INIT_SL_OFFSET,
        allow_long=True,
        allow_short=True,
        regime_lookback=regime_lookback,
    )
    # Filter trades with ts_in in [desde, hasta] -- discards lookback/warmup
    # entries (the engine itself may have opened positions on warmup data
    # before `desde_epoch`, since `closed` includes the warmup candles).
    trades = [t for t in trades if desde_epoch <= t["ts_in"] <= hasta_epoch]
    trades.sort(key=lambda t: (t["ts_in"], t["ts_out"], t["ficha"]))

    result.trades = trades
    result.metrics = compute_metrics(trades)
    return result


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------
def _iso_utc(epoch_s: int) -> str:
    return pd.Timestamp(epoch_s, unit="s", tz="UTC").isoformat()


def _k_suffix(regime_lookback: int) -> str:
    """`-kN` suffix for K != 1 runs so they never collide with the K=1
    baseline. For K=1 (default) this is empty -- the existing ids/modelo_sim
    stay byte-for-byte unchanged."""
    return f"-k{regime_lookback}" if regime_lookback != 1 else ""


def _run_id(tf: str, desde: pd.Timestamp, hasta: pd.Timestamp, regime_lookback: int = 1) -> str:
    d = desde.strftime("%Y%m%d")
    h = hasta.strftime("%Y%m%d")
    return f"sim-tk_bw-{tf.lower()}-{d}-{h}{_k_suffix(regime_lookback)}"


def register_tf(
    registry: ResearchRegistry,
    result: TfResult,
    params_delta: dict[str, Any],
    lake_root: Path,
) -> str:
    strategy_id = registry.upsert_strategy(
        name=STRATEGY_NAME, familia=STRATEGY_FAMILIA, platform=STRATEGY_PLATFORM,
    )
    k = result.regime_lookback
    k_suffix = _k_suffix(k)
    variant_id = f"TK_XAUUSD_BW_{result.tf}{k_suffix}"
    registry.upsert_variant(
        strategy_id, variant_id, params_delta, result.tf, SYMBOL, "tk_bw",
    )

    run_id = _run_id(result.tf, result.desde, result.hasta, k)

    metrics_json = json.dumps({
        "engine_tag": "tk_bw",
        "regime_lookback": k,
        "spread": SPREAD,
        "commission": COMMISSION,
        "ema_fast": EMA_FAST,
        "ema_slow": EMA_SLOW,
        "sar_step": SAR_STEP,
        "sar_max": SAR_MAX,
        "mom_period": MOM_PERIOD,
        "st_period": ST_PERIOD,
        "st_mult": ST_MULT,
        "be_trigger": BE_TRIGGER,
        "trail_usd": TRAIL_USD,
        "init_sl_offset": INIT_SL_OFFSET,
        "volume_per_ficha": VOLUME,
        "fichas_per_signal": 3,
        "tf": result.tf,
        "coverage": {
            "requested_desde": result.desde.isoformat(),
            "requested_hasta": result.hasta.isoformat(),
            "lake_first_bar": result.coverage_first.isoformat() if result.coverage_first is not None else None,
            "lake_last_bar": result.coverage_last.isoformat() if result.coverage_last is not None else None,
        },
        "assumptions": {
            "short_tp2_symmetry": "assumed symmetric to long TP2 (see plan, FLAG: confirm with trader)",
            "mom_period": MOM_PERIOD,
            "st_period_mult": [ST_PERIOD, ST_MULT],
        },
    }, ensure_ascii=False)

    run_dict = {
        "run_id": run_id,
        "variant_id": variant_id,
        "engine": "sentinel-sim",  # CHECK constraint -- NOT "tk_bw"
        "fidelity": "research",
        "periodo_desde": result.desde.isoformat(),
        "periodo_hasta": result.hasta.isoformat(),
        "modelo_sim": f"tk_bw-v1-intrabar-m1{k_suffix}",
        "status": "done",
        "trades": result.metrics["trades"],
        "net": result.metrics["net"],
        "pf": result.metrics["pf"],
        "wr": result.metrics["wr"],
        "payoff": result.metrics["payoff"],
        "maxdd": result.metrics["maxdd"],
        "sharpe": None,
        "metrics_json": metrics_json,
        "fecha_corrida": datetime.now(timezone.utc).isoformat(),
        "source_file": str(lake_root),
    }
    registry.insert_run(run_dict)

    trade_rows = []
    # Group fichas of the same entry by identical (ts_in, side) -> shared signal_id.
    signal_ids: dict[tuple[int, str], str] = {}
    for t in result.trades:
        key = (t["ts_in"], t["side"])
        if key not in signal_ids:
            signal_ids[key] = f"sig-{uuid.uuid4().hex[:12]}"
        signal_id = signal_ids[key]
        trade_id = f"trtkbw-{uuid.uuid4().hex[:16]}"
        trade_rows.append({
            "trade_id": trade_id,
            "run_id": run_id,
            "origin": "strategy",
            "ts_in": _iso_utc(t["ts_in"]),
            "ts_out": _iso_utc(t["ts_out"]),
            "px_in": t["px_in"],
            "px_out": t["px_out"],
            "side": t["side"],
            "volume": VOLUME,
            "sl": t["sl"],
            "exit_reason": t["exit_reason"],
            "exit_reason_source": "sentinel-sim",
            "pnl": t["pnl"],
            "mae": t["mae"],
            "mfe": t["mfe"],
            "signal_id": signal_id,
            "ficha": t["ficha"],
        })
    registry.insert_trades(run_id, trade_rows)
    result.run_id = run_id
    result.variant_id = variant_id
    return run_id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Run the TK-BW backtest over real XAUUSD lake bars for "
                     "M15/M5/M2 and register the runs in data/research.db.",
    )
    ap.add_argument("--lake-root", default=str(LAKE_ROOT_DEFAULT),
                     help="lake root directory (default: data/lake)")
    ap.add_argument("--db", default=str(DB_PATH_DEFAULT),
                     help="research.db path (default: data/research.db)")
    ap.add_argument("--desde", default=DESDE_DEFAULT.isoformat(),
                     help="window start, ISO-8601 UTC (default: 2026-07-20T00:00:00Z)")
    ap.add_argument("--hasta", default=None,
                     help="window end, ISO-8601 UTC (default: last available bar per TF)")
    ap.add_argument("--write", action="store_true",
                     help="persist to the registry (default: dry-run, computes + prints only)")
    ap.add_argument("--regime-lookback", type=int, default=1,
                     help="K closed candles of regime-slope state read by the engine "
                          "(default: 1 = current behavior). K!=1 writes get a -kN id suffix.")
    ap.add_argument("--sweep-regime", default=None,
                     help="DRY measurement: comma list of K, e.g. '1,2,3,4,5'. For each "
                          "TF x K prints trades/signals/net/pf/wr/maxdd. Never writes "
                          "(overrides --write).")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    lake_root = Path(args.lake_root)
    desde = pd.Timestamp(args.desde)
    if desde.tzinfo is None:
        desde = desde.tz_localize("UTC")
    hasta = None
    if args.hasta:
        hasta = pd.Timestamp(args.hasta)
        if hasta.tzinfo is None:
            hasta = hasta.tz_localize("UTC")

    # --sweep-regime: DRY measurement mode. For each TF x K run in memory and
    # print one row per (TF,K). Never persists (overrides --write).
    if args.sweep_regime:
        ks = [int(x) for x in args.sweep_regime.split(",") if x.strip()]
        if args.write:
            print("[note] --sweep-regime is a measurement and never writes; "
                  "ignoring --write.")
        for tf in TFS:
            for k in ks:
                result = run_one_tf(tf, lake_root, desde, hasta, regime_lookback=k)
                m = result.metrics
                signals = len({(t["ts_in"], t["side"]) for t in result.trades})
                print(
                    f"[{tf}] k={k} trades={m['trades']} signals={signals} "
                    f"net={m['net']:.2f} pf={m['pf']} wr={m['wr']:.1f}% "
                    f"maxdd={m['maxdd']:.2f}"
                )
        return 0

    results: list[TfResult] = []
    for tf in TFS:
        result = run_one_tf(tf, lake_root, desde, hasta, regime_lookback=args.regime_lookback)
        results.append(result)

        stale_warn = ""
        if result.coverage_last is not None and result.hasta is not None:
            gap = result.hasta - result.coverage_last
            if gap > pd.Timedelta(hours=6):
                stale_warn = f"  [WARN lake looks stale: last bar {result.coverage_last.isoformat()}]"

        print(
            f"[{tf}] coverage lake=[{result.coverage_first}, {result.coverage_last}] "
            f"window=[{result.desde.isoformat()}, {result.hasta.isoformat()}] "
            f"trades={result.metrics['trades']} signals={len({(t['ts_in'], t['side']) for t in result.trades})} "
            f"net={result.metrics['net']:.2f} pf={result.metrics['pf']} wr={result.metrics['wr']:.1f}%"
            f"{stale_warn}"
        )

    if not args.write:
        print("[dry-run] nothing written to the registry. Pass --write to persist.")
        return 0

    registry = ResearchRegistry(Path(args.db))
    params_delta = build_params_delta()
    # Fail fast, before writing anything, if params_delta is not
    # EmasarPolicy-compatible (plan requirement).
    EmasarPolicy(params_delta)

    for result in results:
        run_id = register_tf(registry, result, params_delta, lake_root)
        print(f"[{result.tf}] registered run_id={run_id} variant_id={result.variant_id} "
              f"trades={len(result.trades)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
