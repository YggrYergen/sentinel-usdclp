"""scripts/research/run_tk_bw_v2_backtest.py -- data RUNNER for the TK-BW v2
"fixes matrix" strategy (Task 2,
docs/superpowers/plans/2026-07-21-tk-bw-regime-state.md / the sibling
"fixes matrix" plan). Loads REAL XAUUSD M5 bars from the lake, drives the
pure engine `sentinel_engine.strategies.tk_bw_v2.tk_bw_v2_run` (Task 1,
committed 02bbc5b) for 5 FIXED configs (derived 1:1 from the TK-BW
diagnostic, NOT a sweep/optimization), and registers them as runs in
`data/research.db` so they show up in the Sentinel UI's "runs" list and
Trade View -- exactly like `run_tk_bw_backtest.py` (v1) already does for
`tk_bw`.

This module reuses (imports, never reimplements) the v1 runner's step
builder / metrics / params_delta / window-constant helpers:
`_df_to_bars`, `build_steps`, `compute_metrics`, `build_params_delta`,
`_iso_utc`, `DESDE_DEFAULT`, `WARMUP_LOOKBACK`. See
`scripts/research/run_tk_bw_backtest.py` for their docstrings.

The 5 configs (CONFIGS dict) are EXACT, not tunable via CLI (this is a
one-shot fixes-matrix registration run, not a sweep):

  fix1seq  -- entry_mode=sequence (armed-breakout), everything else default.
  fix2atr  -- forced entry (c1_tol=3.0) + ATR-based stops (1.5/1.0/2.5xATR14).
  fix3r    -- forced entry (c1_tol=3.0) + R-multiple take-profits (1R/2R).
  fix4reg  -- forced entry (c1_tol=3.0) + simplified regime + session gate
              (07-17h) + K=3 regime_lookback.
  fixall   -- all four fixes combined (sequence + simple regime + session
              gate + ATR stops + R take-profits).

Usage:
    python -m scripts.research.run_tk_bw_v2_backtest              # dry-run (default)
    python -m scripts.research.run_tk_bw_v2_backtest --write       # persist to data/research.db
    python -m scripts.research.run_tk_bw_v2_backtest --write --hasta 2026-07-21T16:58:00Z
    python -m scripts.research.run_tk_bw_v2_backtest --lake-root D:/other/lake --db D:/other/research.db
    python -m scripts.research.run_tk_bw_v2_backtest --configs fix1seq,fix3r

Deterministic given the lake: no wall-clock in the simulation logic itself
(`fecha_corrida` on the registered run is wall-clock, per the v1 pattern).
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Repo root on sys.path -- same bootstrap pattern as run_tk_bw_backtest.py.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd  # noqa: E402

from scripts.research.run_tk_bw_backtest import (  # noqa: E402
    DESDE_DEFAULT,
    WARMUP_LOOKBACK,
    _df_to_bars,
    _iso_utc,
    build_params_delta,
    build_steps,
    compute_metrics,
)
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402
from sentinel_engine.service.bars import load_tf_frame  # noqa: E402
from sentinel_engine.strategies.emasar import EmasarPolicy  # noqa: E402
from sentinel_engine.strategies.tk_bw_v2 import tk_bw_v2_run  # noqa: E402

SYMBOL = "XAUUSD"
TF = "M5"
TF_MINUTES = 5

# ---------------------------------------------------------------------------
# Engine params -- common to ALL 5 configs (EXACT values from the plan's
# "Comunes a todas" list, not CLI-tunable).
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
REGIME_LOOKBACK_DEFAULT = 3
INIT_SL_OFFSET = 0.60
BE_TRIGGER = 0.60
TRAIL_USD = 5.0
VOLUME = 0.01

DESDE_DEFAULT = DESDE_DEFAULT  # re-exported (identity-checked by tests)

STRATEGY_NAME = "tk_bw_v2"
STRATEGY_FAMILIA = "TK"
STRATEGY_PLATFORM = "python-sim"

DB_PATH_DEFAULT = _REPO_ROOT / "data" / "research.db"
LAKE_ROOT_DEFAULT = _REPO_ROOT / "data" / "lake"

_COMMON_PARAMS: dict[str, Any] = {
    "spread": SPREAD,
    "commission": COMMISSION,
    "ema_fast": EMA_FAST,
    "ema_slow": EMA_SLOW,
    "sar_step": SAR_STEP,
    "sar_max": SAR_MAX,
    "mom_period": MOM_PERIOD,
    "st_period": ST_PERIOD,
    "st_mult": ST_MULT,
    "regime_lookback": REGIME_LOOKBACK_DEFAULT,
    "init_sl_offset": INIT_SL_OFFSET,
    "be_trigger": BE_TRIGGER,
    "trail_usd": TRAIL_USD,
    "allow_long": True,
    "allow_short": True,
}

# ---------------------------------------------------------------------------
# The 5 fixes-matrix configs -- EXACT, per the plan's table. Each dict holds
# ONLY the keys that differ from tk_bw_v2_run's defaults / _COMMON_PARAMS;
# `run_one_config` merges `_COMMON_PARAMS` underneath.
# ---------------------------------------------------------------------------
CONFIGS: dict[str, dict[str, Any]] = {
    "fix1seq": {
        "entry_mode": "sequence",
        "regime_mode": "full5",
        "session_hours": None,
        "stop_mode": "fixed",
        "tp_mode": "pattern",
        "seq_timeout": 6,
    },
    "fix2atr": {
        "entry_mode": "forced",
        "c1_tol": 3.0,
        "regime_mode": "full5",
        "session_hours": None,
        "stop_mode": "atr",
        "tp_mode": "pattern",
        "atr_sl_mult": 1.5,
        "atr_be_mult": 1.0,
        "atr_trail_mult": 2.5,
    },
    "fix3r": {
        "entry_mode": "forced",
        "c1_tol": 3.0,
        "regime_mode": "full5",
        "session_hours": None,
        "stop_mode": "fixed",
        "tp_mode": "r",
        "r1_mult": 1.0,
        "r2_mult": 2.0,
    },
    "fix4reg": {
        "entry_mode": "forced",
        "c1_tol": 3.0,
        "regime_mode": "simple",
        "session_hours": (7, 17),
        "stop_mode": "fixed",
        "tp_mode": "pattern",
        "regime_lookback": 3,
    },
    "fixall": {
        "entry_mode": "sequence",
        "regime_mode": "simple",
        "session_hours": (7, 17),
        "stop_mode": "atr",
        "tp_mode": "r",
        "seq_timeout": 6,
        "atr_sl_mult": 1.5,
        "atr_be_mult": 1.0,
        "atr_trail_mult": 2.5,
        "r1_mult": 1.0,
        "r2_mult": 2.0,
    },
}

CONFIG_KEYS: tuple[str, ...] = tuple(CONFIGS.keys())


# ---------------------------------------------------------------------------
# per-config run
# ---------------------------------------------------------------------------
class ConfigResult:
    __slots__ = (
        "key", "trades", "metrics", "coverage_first", "coverage_last",
        "desde", "hasta", "run_id", "variant_id", "params",
    )

    def __init__(self, key: str):
        self.key = key


def run_one_config(
    key: str,
    lake_root: Path,
    desde: pd.Timestamp,
    hasta: pd.Timestamp | None,
) -> ConfigResult:
    native_df = load_tf_frame(lake_root, SYMBOL, TF)
    m1_df = load_tf_frame(lake_root, SYMBOL, "M1")

    result = ConfigResult(key)
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

    steps = build_steps(native_bars, m1_bars, TF_MINUTES, desde_epoch, hasta_epoch)

    params = dict(_COMMON_PARAMS)
    params.update(CONFIGS[key])
    result.params = params

    trades = tk_bw_v2_run(steps, **params)
    trades = [t for t in trades if desde_epoch <= t["ts_in"] <= hasta_epoch]
    trades.sort(key=lambda t: (t["ts_in"], t["ts_out"], t["ficha"]))

    result.trades = trades
    result.metrics = compute_metrics(trades)
    return result


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------
def _run_id(desde: pd.Timestamp, hasta: pd.Timestamp, key: str) -> str:
    d = desde.strftime("%Y%m%d")
    h = hasta.strftime("%Y%m%d")
    return f"sim-tk_bw2-m5-{d}-{h}-{key}"


def _variant_id(key: str) -> str:
    return f"TK_XAUUSD_BW2_M5-{key}"


def register_config(
    registry: ResearchRegistry,
    result: ConfigResult,
    params_delta: dict[str, Any],
    lake_root: Path,
) -> str:
    strategy_id = registry.upsert_strategy(
        name=STRATEGY_NAME, familia=STRATEGY_FAMILIA, platform=STRATEGY_PLATFORM,
    )
    key = result.key
    variant_id = _variant_id(key)
    registry.upsert_variant(
        strategy_id, variant_id, params_delta, TF, SYMBOL, "tk_bw_v2",
    )

    run_id = _run_id(result.desde, result.hasta, key)

    metrics_json = json.dumps({
        "engine_tag": "tk_bw_v2",
        "fix_matrix": "2026-07-22",
        "config_key": key,
        "config": {k: v for k, v in result.params.items()},
        "tf": TF,
        "coverage": {
            "requested_desde": result.desde.isoformat(),
            "requested_hasta": result.hasta.isoformat(),
            "lake_first_bar": result.coverage_first.isoformat() if result.coverage_first is not None else None,
            "lake_last_bar": result.coverage_last.isoformat() if result.coverage_last is not None else None,
        },
    }, ensure_ascii=False)

    run_dict = {
        "run_id": run_id,
        "variant_id": variant_id,
        "engine": "sentinel-sim",  # CHECK constraint -- NOT "tk_bw_v2"
        "fidelity": "research",
        "periodo_desde": result.desde.isoformat(),
        "periodo_hasta": result.hasta.isoformat(),
        "modelo_sim": f"tk_bw_v2-intrabar-m1-{key}",
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
    signal_ids: dict[tuple[int, str], str] = {}
    for t in result.trades:
        sig_key = (t["ts_in"], t["side"])
        if sig_key not in signal_ids:
            signal_ids[sig_key] = f"sig-{uuid.uuid4().hex[:12]}"
        signal_id = signal_ids[sig_key]
        trade_id = f"trtkbw2-{uuid.uuid4().hex[:16]}"
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
        description="Run the TK-BW v2 fixes-matrix backtest (5 fixed configs) "
                     "over real XAUUSD M5 lake bars and register the runs in "
                     "data/research.db.",
    )
    ap.add_argument("--lake-root", default=str(LAKE_ROOT_DEFAULT),
                     help="lake root directory (default: data/lake)")
    ap.add_argument("--db", default=str(DB_PATH_DEFAULT),
                     help="research.db path (default: data/research.db)")
    ap.add_argument("--desde", default=DESDE_DEFAULT.isoformat(),
                     help="window start, ISO-8601 UTC (default: 2026-07-20T00:00:00Z)")
    ap.add_argument("--hasta", default=None,
                     help="window end, ISO-8601 UTC (default: last available M5 bar)")
    ap.add_argument("--write", action="store_true",
                     help="persist to the registry (default: dry-run, computes + prints only)")
    ap.add_argument("--configs", default=None,
                     help="comma list of config keys to run (default: all 5). "
                          "Keys are fixed (fix1seq,fix2atr,fix3r,fix4reg,fixall) -- "
                          "this only SELECTS a subset, it never changes their params.")
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

    if args.configs:
        keys = [k.strip() for k in args.configs.split(",") if k.strip()]
        unknown = [k for k in keys if k not in CONFIGS]
        if unknown:
            print(f"[error] unknown config key(s): {unknown}. Valid: {CONFIG_KEYS}")
            return 2
    else:
        keys = list(CONFIG_KEYS)

    results: list[ConfigResult] = []
    for key in keys:
        result = run_one_config(key, lake_root, desde, hasta)
        results.append(result)

        stale_warn = ""
        if result.coverage_last is not None and result.hasta is not None:
            gap = result.hasta - result.coverage_last
            if gap > pd.Timedelta(hours=6):
                stale_warn = f"  [WARN lake looks stale: last bar {result.coverage_last.isoformat()}]"

        m = result.metrics
        signals = len({(t["ts_in"], t["side"]) for t in result.trades})
        print(
            f"[{key}] coverage lake=[{result.coverage_first}, {result.coverage_last}] "
            f"window=[{result.desde.isoformat()}, {result.hasta.isoformat()}] "
            f"trades={m['trades']} signals={signals} "
            f"net={m['net']:.2f} pf={m['pf']} wr={m['wr']:.1f}% maxdd={m['maxdd']:.2f}"
            f"{stale_warn}"
        )

    if not args.write:
        print("[dry-run] nothing written to the registry. Pass --write to persist.")
        return 0

    registry = ResearchRegistry(Path(args.db))
    params_delta = build_params_delta()
    # Fail fast, before writing anything, if params_delta is not
    # EmasarPolicy-compatible.
    EmasarPolicy(params_delta)

    for result in results:
        run_id = register_config(registry, result, params_delta, lake_root)
        print(f"[{result.key}] registered run_id={run_id} variant_id={result.variant_id} "
              f"trades={len(result.trades)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
