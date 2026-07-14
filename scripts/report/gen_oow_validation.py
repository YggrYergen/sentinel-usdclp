"""scripts/report/gen_oow_validation.py -- Out-of-window (OOW) validation of
the EMASAR variant research program's 14 winning candidate configs, on THREE
contrast windows outside the in-sample window (IW = 2026-06-08 -> 2026-07-07):

    W1 = 2026-05-04 -> 2026-06-05  (month immediately prior to IW)
    W2 = 2026-03-02 -> 2026-04-03
    W3 = 2025-10-01 -> 2025-11-01

Same lake, same methodology as every prior batch: BID lake bars, spread 0.5
applied at fill, same metrics (net/PF/WR/maxDD/n/%motivo/trades-per-day).
Reuses (does NOT modify) `gen_variant_batch1.py`'s load/fill/metrics/ingest
machinery (loader is re-parameterized per window via `_load_bars_window`,
same function shape/semantics as `_bars_for`, just with window-specific
warmup/window bounds) and `gen_variant_batch5.py`'s direction-mask
computation (SuperTrend(14,3.0) on M15, previous-closed-bar, no look-ahead)
for configs C12/C13.

ZERO new engine code: every parameter used already exists on
`sentinel_engine.strategies.emasar_variant.simular_variant`.

14 CANDIDATE CONFIGS x 3 windows = 42 sims, + 9 control (V-09-style, but
ac_modulate=False, init_sl_range_k=1.0) runs (3 TFs x 3 windows) = 51 sims
total.

Ingested into data/research.db, run_ids:
    sim-report-emasar-oow{1,2,3}-<config-tag>          (candidates)
    sim-report-emasar-oow{1,2,3}-ctrl-<tf>             (controls)
where oow1=W1, oow2=W2, oow3=W3.

Run this script directly: `python scripts/report/gen_oow_validation.py`.
Idempotent: re-running replaces the same run_ids (delete-before-insert).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.strategies.emasar_ref import _atr_wilder  # noqa: E402
from sentinel_engine.strategies._supertrend_ref import supertrend as _supertrend  # noqa: E402
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

# Reuse batch1's loader/filler/metrics/ingest machinery directly (same
# importlib pattern batch2-batch7 used).
import importlib.util as _ilu  # noqa: E402

_b1_spec = _ilu.spec_from_file_location(
    "gen_variant_batch1", ROOT / "scripts" / "report" / "gen_variant_batch1.py"
)
_b1 = _ilu.module_from_spec(_b1_spec)
_b1_spec.loader.exec_module(_b1)  # type: ignore[union-attr]

DB_PATH = ROOT / "data" / "research.db"
SYMBOL = _b1.SYMBOL
LOT = _b1.LOT
CONTRACT_SIZE = _b1.CONTRACT_SIZE
LAKE_ROOT = _b1.LAKE_ROOT
V09_PARAMS = _b1.V09_PARAMS
run_variant_generic = _b1.simular_variant  # unused directly; kept for clarity
ingest_run = _b1.ingest_run
compute_metrics_generic = _b1.compute_metrics

# ---------------------------------------------------------------------------
# Windows.
# ---------------------------------------------------------------------------
# (tag, warmup_start, window_start, window_end_excl, lake_months)
WINDOWS: dict[str, dict[str, Any]] = {
    "W1": dict(
        run_tag="oow1",
        warmup_start=datetime(2026, 4, 27, 0, 0, 0, tzinfo=timezone.utc),
        window_start=datetime(2026, 5, 4, 0, 0, 0, tzinfo=timezone.utc),
        window_end_excl=datetime(2026, 6, 6, 0, 0, 0, tzinfo=timezone.utc),  # thru 06-05
        periodo_desde="2026-05-04", periodo_hasta="2026-06-05",
        lake_months=("2026-04", "2026-05", "2026-06"),
    ),
    "W2": dict(
        run_tag="oow2",
        warmup_start=datetime(2026, 2, 23, 0, 0, 0, tzinfo=timezone.utc),
        window_start=datetime(2026, 3, 2, 0, 0, 0, tzinfo=timezone.utc),
        window_end_excl=datetime(2026, 4, 4, 0, 0, 0, tzinfo=timezone.utc),  # thru 04-03
        periodo_desde="2026-03-02", periodo_hasta="2026-04-03",
        lake_months=("2026-02", "2026-03", "2026-04"),
    ),
    "W3": dict(
        run_tag="oow3",
        warmup_start=datetime(2025, 9, 24, 0, 0, 0, tzinfo=timezone.utc),
        window_start=datetime(2025, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
        window_end_excl=datetime(2025, 11, 2, 0, 0, 0, tzinfo=timezone.utc),  # thru 11-01
        periodo_desde="2025-10-01", periodo_hasta="2025-11-01",
        lake_months=("2025-09", "2025-10", "2025-11"),
    ),
}

TFS = ["M2", "M5", "M15"]

# ---------------------------------------------------------------------------
# Per-window bar loading -- same function shape/semantics as batch1's
# `_load_bars`/`_bars_for`, generalized over the window dict above.
# ---------------------------------------------------------------------------
_BARS_CACHE: dict[tuple[str, str], list[dict[str, Any]]] = {}


def _load_bars_window(tf: str, win: dict[str, Any]) -> list[dict[str, Any]]:
    warm_epoch = int(win["warmup_start"].timestamp())
    end_epoch = int(win["window_end_excl"].timestamp())
    bars: list[dict[str, Any]] = []
    for month in win["lake_months"]:
        path = LAKE_ROOT / SYMBOL / tf / f"{month}.parquet"
        if not path.exists():
            continue
        table = pq.read_table(path)
        cols = {name: table.column(name).to_pylist() for name in table.schema.names}
        for i in range(len(cols["t"])):
            t = cols["t"][i]
            if t < warm_epoch or t >= end_epoch:
                continue
            bars.append({
                "t": t,
                "open": cols["o"][i], "high": cols["h"][i],
                "low": cols["l"][i], "close": cols["c"][i],
                "volume": cols["v"][i],
            })
    bars.sort(key=lambda b: b["t"])
    return bars


def _bars_for(tf: str, win_key: str) -> list[dict[str, Any]]:
    cache_key = (tf, win_key)
    if cache_key not in _BARS_CACHE:
        _BARS_CACHE[cache_key] = _load_bars_window(tf, WINDOWS[win_key])
    return _BARS_CACHE[cache_key]


# ---------------------------------------------------------------------------
# Per-window run_variant / compute_metrics -- identical logic to batch1's,
# just parameterized on the window's own bounds instead of the fixed IW
# module-level constants (batch1's functions close over its own IW globals,
# so we cannot reuse them directly for other windows -- everything else,
# incl. spread-at-fill helpers `_entry_fill`/`_exit_fill`/`_pnl`, IS reused
# verbatim from batch1 via the imported module `_b1`).
# ---------------------------------------------------------------------------

def run_variant_window(tf: str, win_key: str, variant_kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    win = WINDOWS[win_key]
    bars = _bars_for(tf, win_key)
    eventos = simular_variant(bars, symbol=SYMBOL, **variant_kwargs)

    window_start_epoch = int(win["window_start"].timestamp())
    window_end_epoch = int(win["window_end_excl"].timestamp())

    def _in_window(epoch: int) -> bool:
        return window_start_epoch <= epoch < window_end_epoch

    trades: list[dict[str, Any]] = []
    open_positions: dict[str, dict[str, Any]] = {}
    signal_seq = 0
    last_signal_id: str | None = None

    for ev in eventos:
        motivo = ev["motivo"]
        idx = ev["idx"]
        bar = bars[idx]
        side_l = ev["lado"]
        side_ui = "LONG" if side_l == "L" else "SHORT"

        if motivo in ("ENTRY_L", "ENTRY_S"):
            signal_seq += 1
            signal_id = f"sig-{bar['t']}-{signal_seq}"
            open_positions[signal_id] = {
                "signal_id": signal_id, "t": bar["t"], "side": side_l,
                "side_ui": side_ui, "precio": ev["precio"],
                "fichas_remaining": {"F1", "F2", "F3"},
            }
            last_signal_id = signal_id
        elif motivo.startswith("EXIT"):
            ficha = ev.get("ficha") or "F1"
            pos = open_positions.get(last_signal_id)
            if pos is None or ficha not in pos["fichas_remaining"]:
                pos = None
                for sid, p in open_positions.items():
                    if ficha in p["fichas_remaining"]:
                        pos = p
                        last_signal_id = sid
                        break
                if pos is None:
                    continue

            entry_side_l = pos["side"]
            entry_px = _b1._entry_fill(entry_side_l, pos["precio"])
            exit_px = _b1._exit_fill(entry_side_l, ev["precio"])

            trades.append({
                "signal_id": pos["signal_id"],
                "ficha": ficha,
                "side": pos["side_ui"],
                "ts_in_epoch": pos["t"],
                "ts_out_epoch": bar["t"],
                "px_in": round(entry_px, 2),
                "px_out": round(exit_px, 2),
                "exit_reason": motivo,
                "entry_in_window": _in_window(pos["t"]),
            })

            pos["fichas_remaining"].discard(ficha)
            if not pos["fichas_remaining"]:
                open_positions.pop(pos["signal_id"], None)

    return trades


def compute_metrics_window(trades_all: list[dict[str, Any]], win_key: str) -> dict[str, Any]:
    win = WINDOWS[win_key]
    trades_in = [t for t in trades_all if t["entry_in_window"]]
    n = len(trades_in)
    if n == 0:
        return {
            "trades": 0, "net": 0.0, "pf": None, "wr": None, "payoff": None,
            "maxdd": 0.0, "pct_initsl": None, "pct_trail": None,
            "trades_per_day": 0.0, "long_pnl": 0.0, "short_pnl": 0.0,
            "long_n": 0, "short_n": 0,
        }

    pnls = [(_b1._pnl(t["side"], t["px_in"], t["px_out"]), t) for t in trades_in]
    net = round(sum(p for p, _ in pnls), 2)
    wins = [p for p, _ in pnls if p > 0]
    losses = [p for p, _ in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    pf = round(gross_win / gross_loss, 4) if gross_loss > 0 else (None if gross_win == 0 else float("inf"))
    wr = round(100.0 * len(wins) / n, 2) if n else None
    avg_win = (gross_win / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    payoff = round(avg_win / avg_loss, 4) if avg_loss > 0 else None

    ordered = sorted(trades_in, key=lambda t: t["ts_out_epoch"])
    cum = 0.0
    peak = 0.0
    maxdd = 0.0
    for t in ordered:
        cum += _b1._pnl(t["side"], t["px_in"], t["px_out"])
        peak = max(peak, cum)
        maxdd = max(maxdd, peak - cum)
    maxdd = round(maxdd, 2)

    n_initsl = sum(1 for t in trades_in if t["exit_reason"] == "EXIT_INITSL")
    n_trail = sum(1 for t in trades_in if t["exit_reason"] == "EXIT_TRAIL")
    pct_initsl = round(100.0 * n_initsl / n, 2)
    pct_trail = round(100.0 * n_trail / n, 2)

    span_days = (win["window_end_excl"] - win["window_start"]).total_seconds() / 86400.0
    trades_per_day = round(n / span_days, 3)

    long_pnl = round(sum(p for p, t in pnls if t["side"] == "LONG"), 2)
    short_pnl = round(sum(p for p, t in pnls if t["side"] == "SHORT"), 2)
    long_n = sum(1 for _, t in pnls if t["side"] == "LONG")
    short_n = sum(1 for _, t in pnls if t["side"] == "SHORT")

    return {
        "trades": n, "net": net, "pf": pf, "wr": wr, "payoff": payoff,
        "maxdd": maxdd, "pct_initsl": pct_initsl, "pct_trail": pct_trail,
        "trades_per_day": trades_per_day,
        "long_pnl": long_pnl, "short_pnl": short_pnl,
        "long_n": long_n, "short_n": short_n,
    }


def ingest_run_window(
    registry: ResearchRegistry,
    *,
    run_id: str,
    variant_id: str,
    strategy_name: str,
    familia: str,
    tf: str,
    win_key: str,
    params_delta: dict[str, Any],
    trades_all: list[dict[str, Any]],
    display_name: str,
) -> dict[str, Any]:
    """Mirrors `gen_variant_batch1.ingest_run` exactly, but window-parameterized
    (periodo_desde/hasta, warmup/feed bounds, trades_per_day denominator)."""
    win = WINDOWS[win_key]
    strategy_id = registry.upsert_strategy(name=strategy_name, familia=familia, platform="python-sim")
    registry.upsert_variant(
        strategy_id=strategy_id, variant_id=variant_id,
        params_delta=params_delta, tf=tf, instrumento=SYMBOL,
        modo_salida=tf.lower(),
    )

    trades_in_window = [t for t in trades_all if t["entry_in_window"]]
    m = compute_metrics_window(trades_all, win_key)

    run_row = {
        "run_id": run_id,
        "variant_id": variant_id,
        "params_hash": None,
        "engine": "sentinel-sim",
        "fidelity": "screening",
        "periodo_desde": win["periodo_desde"],
        "periodo_hasta": win["periodo_hasta"],
        "modelo_sim": "sim-report",
        "status": "OK",
        "trades": m["trades"],
        "net": m["net"],
        "pf": m["pf"] if m["pf"] not in (None, float("inf")) else None,
        "wr": m["wr"],
        "payoff": m["payoff"],
        "maxdd": m["maxdd"],
        "sharpe": None,
        "metrics_json": json.dumps({
            "display_name": display_name,
            "spread_model": "capitaria_0.5_at_fill",
            "warmup_from": win["warmup_start"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "feed_to_excl": win["window_end_excl"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_events_all_dates": len(trades_all),
            "events_in_window": m["trades"],
            "pct_exit_initsl": m["pct_initsl"],
            "pct_exit_trail": m["pct_trail"],
            "trades_per_day": m["trades_per_day"],
            "long_pnl": m["long_pnl"], "short_pnl": m["short_pnl"],
            "long_n": m["long_n"], "short_n": m["short_n"],
            "window_key": win_key,
            "params": params_delta,
        }, ensure_ascii=False),
        "preregistro_id": None,
        "report_path": None,
        "trades_path": None,
        "equity_path": None,
        "signal_history_path": None,
        "fecha_corrida": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "seed": None,
        "config_hash": None,
        "source_file": "scripts/report/gen_oow_validation.py",
        "source_row": None,
        "fidelity_ref": None,
    }

    conn = registry._connect()  # noqa: SLF001 -- idempotent delete-before-insert, same DB the public API writes to
    try:
        conn.execute("DELETE FROM trade WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM run WHERE run_id=?", (run_id,))
        conn.commit()
    finally:
        conn.close()

    registry.insert_run(run_row)

    trade_rows = []
    for t in trades_in_window:
        pnl = _b1._pnl(t["side"], t["px_in"], t["px_out"])
        trade_rows.append({
            "trade_id": f"{run_id}-{t['signal_id']}-{t['ficha']}",
            "run_id": run_id,
            "origin": "strategy",
            "origin_id": variant_id,
            "session_id": None,
            "ts_in": _b1._ts_str(t["ts_in_epoch"]),
            "ts_out": _b1._ts_str(t["ts_out_epoch"]),
            "px_in": t["px_in"],
            "px_out": t["px_out"],
            "side": t["side"],
            "volume": LOT,
            "sl": None,
            "tp": None,
            "exit_reason": t["exit_reason"],
            "exit_reason_source": "sim_report",
            "pnl": pnl,
            "mae": None,
            "mfe": None,
            "snapshot_ref": None,
            "decision_trace_ref": None,
            "signal_id": t["signal_id"],
            "ficha": t["ficha"],
        })
    registry.insert_trades(run_id, trade_rows)

    registry.audit(
        "scripts.report.gen_oow_validation", "sim_report_ingested",
        {"run_id": run_id, "variant_id": variant_id, "trades": m["trades"], "net": m["net"]},
    )

    return {"run_id": run_id, "variant_id": variant_id, "tf": tf, **m}


# ---------------------------------------------------------------------------
# Direction mask (V-10 lever, for C12/C13) -- copied verbatim from
# gen_variant_batch5.py, generalized over window via `_bars_for(tf, win_key)`.
# ---------------------------------------------------------------------------

def _resample_to_m15(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[int, dict[str, Any]] = {}
    for b in bars:
        bucket_t = (b["t"] // 900) * 900
        agg = buckets.get(bucket_t)
        if agg is None:
            buckets[bucket_t] = {
                "t": bucket_t, "open": b["open"], "high": b["high"],
                "low": b["low"], "close": b["close"],
            }
        else:
            agg["high"] = max(agg["high"], b["high"])
            agg["low"] = min(agg["low"], b["low"])
            agg["close"] = b["close"]
    return [buckets[t] for t in sorted(buckets)]


def _bisect_bucket_index(bucket_starts: list[int], target_t: int) -> int:
    lo, hi = 0, len(bucket_starts) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if bucket_starts[mid] == target_t:
            return mid
        if bucket_starts[mid] < target_t:
            lo = mid + 1
        else:
            hi = mid - 1
    raise ValueError(f"bucket_t={target_t} not found in M15 bucket list (resample bug)")


def compute_direction_mask(bars: list[dict[str, Any]], *, atr_period: int = 14,
                            st_mult: float = 3.0) -> list[int]:
    m15 = _resample_to_m15(bars)
    m15_highs = [b["high"] for b in m15]
    m15_lows = [b["low"] for b in m15]
    m15_closes = [b["close"] for b in m15]
    atr = _atr_wilder(m15_highs, m15_lows, m15_closes, atr_period)
    trend, _line = _supertrend(m15_highs, m15_lows, m15_closes,
                                [a if a is not None else 0.0 for a in atr], st_mult)
    st_valid = [atr[i] is not None for i in range(len(m15))]

    m15_bucket_start = [b["t"] for b in m15]
    mask: list[int] = [0] * len(bars)
    for i, b in enumerate(bars):
        own_bucket_t = (b["t"] // 900) * 900
        k = _bisect_bucket_index(m15_bucket_start, own_bucket_t)
        prev_k = k - 1
        if prev_k < 0 or not st_valid[prev_k] or trend[prev_k] is None:
            mask[i] = 0
        else:
            mask[i] = trend[prev_k]
    return mask


_MASK_CACHE: dict[tuple[str, str], list[int]] = {}


def _mask_for(tf: str, win_key: str) -> list[int]:
    key = (tf, win_key)
    if key not in _MASK_CACHE:
        _MASK_CACHE[key] = compute_direction_mask(_bars_for(tf, win_key))
    return _MASK_CACHE[key]


# ---------------------------------------------------------------------------
# Common skeleton (per task spec).
# ---------------------------------------------------------------------------
SKELETON: dict[str, Any] = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    ema_fast=8, ema_slow=20, sar_step=0.3, sar_max=0.3,
    f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
    ac_modulate=True,
)
INIT_SL_RANGE_K = {"M2": 3.0, "M5": 6.0, "M15": 2.5}


def skeleton_kwargs(tf: str) -> dict[str, Any]:
    return {**SKELETON, "init_sl_range_k": INIT_SL_RANGE_K[tf]}


# ---------------------------------------------------------------------------
# 14 candidate configs.
# ---------------------------------------------------------------------------
SS_LEVER = dict(sar_adaptive=True, sar_fast=(0.3, 0.3), sar_slow=(0.005, 0.05),
                 vol_regime_window=200)

CONFIGS: dict[str, dict[str, Any]] = {
    "ss-m2": dict(tf="M2", extra=dict(
        ac_modulate_factor=0.01, reentry_enable=True, reentry_max=2, **SS_LEVER)),
    "ss-m5": dict(tf="M5", extra=dict(
        ac_modulate_factor=0.01, reentry_enable=True, reentry_max=2, **SS_LEVER)),
    "ss-m15": dict(tf="M15", extra=dict(
        ac_modulate_factor=0.01, reentry_enable=True, reentry_max=2)),
    "v13-m5": dict(tf="M5", extra=dict(
        ac_modulate_factor=0.25, reentry_enable=True, reentry_max=2)),
    "v13-m15": dict(tf="M15", extra=dict(
        ac_modulate_factor=0.25, reentry_enable=True, reentry_max=2)),
    "v15-m2": dict(tf="M2", extra=dict(
        ac_modulate_factor=0.25, **SS_LEVER)),
    "v15-m15": dict(tf="M15", extra=dict(
        ac_modulate_factor=0.25, **SS_LEVER)),
    "v06c-m5": dict(tf="M5", extra=dict(ac_modulate_factor=0.10)),
    "v06c-m15": dict(tf="M15", extra=dict(ac_modulate_factor=0.10)),
    "v06d-m5": dict(tf="M5", extra=dict(ac_modulate_factor=0.01)),
    "v06d-m15": dict(tf="M15", extra=dict(ac_modulate_factor=0.01)),
    "v10-m15": dict(tf="M15", extra=dict(ac_modulate_factor=0.25), direction_mask=True),
    "v10-m5": dict(tf="M5", extra=dict(ac_modulate_factor=0.25), direction_mask=True),
    "v06b-m15": dict(tf="M15", extra=dict(ac_modulate_factor=0.25)),
}

IW_NET = {
    "ss-m2": 40263.6, "ss-m5": 48849.9, "ss-m15": 43459.8,
    "v13-m5": 46264.8, "v13-m15": 43027.8,
    "v15-m2": 31181.4, "v15-m15": 36639.9,
    "v06c-m5": 45815.7, "v06c-m15": 41126.7,
    "v06d-m5": 46269.3, "v06d-m15": 41264.4,
    "v10-m15": 22688.7, "v10-m5": 24273.9,
    "v06b-m15": 40897.2,
}

# For v10-m15, direction_mask is computed on M15 directly; for v10-m5, the
# task spec says "M15-resampled" -- i.e. the mask is computed from M15-
# resampled bars but the strategy still runs on M5 bars zipped 1:1 by their
# own M15 bucket (same `compute_direction_mask` function handles both: it
# resamples whatever TF's bars are passed to M15 internally and maps back).


def config_kwargs(cfg_id: str, win_key: str) -> dict[str, Any]:
    cfg = CONFIGS[cfg_id]
    tf = cfg["tf"]
    kwargs = {**skeleton_kwargs(tf), **cfg["extra"]}
    if cfg.get("direction_mask"):
        kwargs["direction_mask"] = _mask_for(tf, win_key)
    return kwargs


# ---------------------------------------------------------------------------
# Control (V-09-style) params: skeleton but ac_modulate=False,
# init_sl_range_k=1.0.
# ---------------------------------------------------------------------------

def control_kwargs(tf: str) -> dict[str, Any]:
    return {**SKELETON, "ac_modulate": False, "init_sl_range_k": 1.0}


# ---------------------------------------------------------------------------
# Window characterization (M5 bars): open->close change, high-low range,
# mean ATR(14), TREND/RANGE label.
# ---------------------------------------------------------------------------

def characterize_window(win_key: str) -> dict[str, Any]:
    bars = _bars_for("M5", win_key)
    win = WINDOWS[win_key]
    ws = int(win["window_start"].timestamp())
    we = int(win["window_end_excl"].timestamp())
    in_win = [b for b in bars if ws <= b["t"] < we]
    if not in_win:
        return {"window": win_key, "error": "no bars in window"}
    open_px = in_win[0]["open"]
    close_px = in_win[-1]["close"]
    change = round(close_px - open_px, 2)
    pct_change = round(100.0 * change / open_px, 4)
    hi = max(b["high"] for b in in_win)
    lo = min(b["low"] for b in in_win)
    hl_range = round(hi - lo, 2)

    highs = [b["high"] for b in in_win]
    lows = [b["low"] for b in in_win]
    closes = [b["close"] for b in in_win]
    atr = _atr_wilder(highs, lows, closes, 14)
    atr_vals = [a for a in atr if a is not None]
    mean_atr = round(sum(atr_vals) / len(atr_vals), 4) if atr_vals else None

    regime = "TREND" if abs(change) > 0.5 * hl_range else "RANGE"

    return {
        "window": win_key, "open": open_px, "close": close_px,
        "change": change, "pct_change": pct_change,
        "hl_range": hl_range, "mean_atr14": mean_atr, "regime": regime,
        "n_bars": len(in_win),
    }


# IW characterization uses batch1's own loader/bounds.
def characterize_iw() -> dict[str, Any]:
    bars = _b1._bars_for("M5")
    ws = int(_b1.WINDOW_START.timestamp())
    we = int(_b1.WINDOW_END_EXCL.timestamp())
    in_win = [b for b in bars if ws <= b["t"] < we]
    if not in_win:
        return {"window": "IW", "error": "no bars in window"}
    open_px = in_win[0]["open"]
    close_px = in_win[-1]["close"]
    change = round(close_px - open_px, 2)
    pct_change = round(100.0 * change / open_px, 4)
    hi = max(b["high"] for b in in_win)
    lo = min(b["low"] for b in in_win)
    hl_range = round(hi - lo, 2)
    highs = [b["high"] for b in in_win]
    lows = [b["low"] for b in in_win]
    closes = [b["close"] for b in in_win]
    atr = _atr_wilder(highs, lows, closes, 14)
    atr_vals = [a for a in atr if a is not None]
    mean_atr = round(sum(atr_vals) / len(atr_vals), 4) if atr_vals else None
    regime = "TREND" if abs(change) > 0.5 * hl_range else "RANGE"
    return {
        "window": "IW", "open": open_px, "close": close_px,
        "change": change, "pct_change": pct_change,
        "hl_range": hl_range, "mean_atr14": mean_atr, "regime": regime,
        "n_bars": len(in_win),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None,
                         help="optional path to dump the full raw results as JSON")
    args = parser.parse_args()

    registry = ResearchRegistry(DB_PATH)
    all_results: dict[str, Any] = {"characterization": {}, "candidates": {}, "controls": {}}

    # ===== Window characterization =====
    print("\n==== WINDOW CHARACTERIZATION (M5 bars) ====")
    char_iw = characterize_iw()
    all_results["characterization"]["IW"] = char_iw
    print(f"[CHAR] IW: {char_iw}")
    for win_key in ("W1", "W2", "W3"):
        c = characterize_window(win_key)
        all_results["characterization"][win_key] = c
        print(f"[CHAR] {win_key}: {c}")

    # ===== 14 candidate configs x 3 windows = 42 sims =====
    print("\n==== CANDIDATE CONFIGS (42 sims) ====")
    for cfg_id, cfg in CONFIGS.items():
        tf = cfg["tf"]
        all_results["candidates"][cfg_id] = {"tf": tf, "iw_net": IW_NET[cfg_id], "windows": {}}
        for win_key in ("W1", "W2", "W3"):
            win = WINDOWS[win_key]
            kwargs = config_kwargs(cfg_id, win_key)
            trades = run_variant_window(tf, win_key, kwargs)
            m = compute_metrics_window(trades, win_key)

            json_safe_kwargs = {k: (list(v) if isinstance(v, tuple) else v)
                                 for k, v in kwargs.items() if k != "direction_mask"}
            if cfg.get("direction_mask"):
                json_safe_kwargs["direction_mask"] = "supertrend_m15_atr14_mult3.0_prev_closed_bar"

            run_id = f"sim-report-emasar-{win['run_tag']}-{cfg_id}"
            r = ingest_run_window(
                registry, run_id=run_id,
                variant_id=f"EMS_XAU_OOW_{cfg_id.upper().replace('-', '_')}_{tf}_{win_key}",
                strategy_name="EMASAR", familia="emasar",
                tf=tf, win_key=win_key,
                params_delta={**json_safe_kwargs, "variant": f"OOW validation: {cfg_id} on {win_key}"},
                trades_all=trades,
                display_name=f"EMASAR OOW {cfg_id} {tf} {win_key}",
            )
            all_results["candidates"][cfg_id]["windows"][win_key] = r
            print(f"[OOW {win_key}] {cfg_id} ({tf}): trades={r['trades']} net={r['net']} "
                  f"pf={r['pf']} wr={r['wr']} maxdd={r['maxdd']} ingested={r['run_id']}")

    # ===== Controls: 3 TFs x 3 windows = 9 sims =====
    print("\n==== CONTROL RUNS (9 sims) ====")
    for tf in TFS:
        all_results["controls"][tf] = {}
        for win_key in ("W1", "W2", "W3"):
            win = WINDOWS[win_key]
            kwargs = control_kwargs(tf)
            trades = run_variant_window(tf, win_key, kwargs)
            m = compute_metrics_window(trades, win_key)

            run_id = f"sim-report-emasar-{win['run_tag']}-ctrl-{tf.lower()}"
            r = ingest_run_window(
                registry, run_id=run_id,
                variant_id=f"EMS_XAU_OOW_CTRL_{tf}_{win_key}",
                strategy_name="EMASAR", familia="emasar",
                tf=tf, win_key=win_key,
                params_delta={**kwargs, "variant": f"OOW control (V-09 style) {tf} on {win_key}"},
                trades_all=trades,
                display_name=f"EMASAR OOW control {tf} {win_key}",
            )
            all_results["controls"][tf][win_key] = r
            print(f"[OOW CTRL {win_key}] {tf}: trades={r['trades']} net={r['net']} "
                  f"pf={r['pf']} wr={r['wr']} maxdd={r['maxdd']} ingested={r['run_id']}")

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        with args.report_json.open("w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nRaw results JSON written to {args.report_json}")

    print("\n==== DONE ====")


if __name__ == "__main__":
    main()
