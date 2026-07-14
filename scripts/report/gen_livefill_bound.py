"""scripts/report/gen_livefill_bound.py -- live-fill realistic-fills bound
for the EMASAR variant research program (2026-07-13).

MOTIVE: `simular_variant`'s CLASSIC exit logic raises a ficha's trailing SL
using that SAME bar's own high (and, when `ac_modulate=True`, that bar's own
AC value) and can book a same-bar exit at the RAISED level -- optimistic
intra-bar ordering that a real broker/live executor cannot replicate (the
live executor's server-side SL is only updated at bar CLOSE, so a raise
computed from bar i's own high can only become the resting order from bar
i+1 onward). `sentinel_engine.strategies.emasar_variant.simular_variant`'s
new additive `live_fill_mode=True` kwarg (default False = classic, unchanged)
mirrors the live executor's semantics EXACTLY (see that function's own
docstring): intrabar stop checks for bar i use the SL level as of the END of
bar i-1; the raise computed at bar i's close only becomes active from i+1;
and a SAME-BAR FALLBACK closes at bar i's own CLOSE (tagged
`same_bar_fallback": True` on the event) when the raised level would already
be violated by that close, but the prior-bar level was never touched.

This script re-simulates the 13 roster configs below in BOTH modes
(`live_fill_mode=False` / classic, and `=True` / live-fill) on all 4 research
windows (IW/W1/W2/W3), and reports the net/PF/WR/maxDD/n deltas plus
same-bar-fallback event counts -- quantifying how much of the backtested edge
survives realistic (non-look-ahead) fills, BEFORE go-live.

ZERO new strategy-selection code: every parameter here already exists on
`simular_variant` (including the new `live_fill_mode` kwarg). Reuses (does
NOT modify) `gen_variant_batch1.py`'s spread-at-fill/metrics/ingest
machinery and `gen_oow_validation.py`'s window definitions, via the same
importlib pattern every batch script in this program has used.

WINDOWS:
    IW = 2026-06-08 -> 2026-07-07  (the program's in-sample window)
    W1 = 2026-05-04 -> 2026-06-05
    W2 = 2026-03-02 -> 2026-04-03
    W3 = 2025-10-01 -> 2025-11-01
M2's lake tier only starts 2025-12-10, so M2 configs SKIP W3 (0 bars, no
sim run attempted -- recorded as "no_data" in the results, not a 0-trade run).

CONFIGS (13; champion skeleton confirm_mode=1, confirm_count=2,
require_ema_order=False, ema 8/20, sar 0.3/0.3, flat ladder 100/100/100,
ac_modulate=True; per-TF init_sl_range_k M1=6.0/M2=3.0/M5=6.0/M15=2.5):
    1. SS-M2   (f=0.01, reentry rmax2, sar_adaptive)
    2. SS-M5   (f=0.01, reentry rmax2, sar_adaptive)
    3. SS-M15  (f=0.01, reentry rmax2, NO sar_adaptive)
    4. SS-M1   (f=0.01, reentry rmax2, sar_adaptive)
    5. V06D-M2 (f=0.01)
    6. V06D-M5 (f=0.01)
    7. V06D-M15 (f=0.01)
    8. V13-M5  (f=0.25, reentry rmax2)
    9. V13-M15 (f=0.25, reentry rmax2)
    10. V15-M2 (f=0.25, sar_adaptive)
    11. V06C-M5  (f=0.10)
    12. V06C-M15 (f=0.10)
    13. V06B-M15 (f=0.25)

XAUUSD, BID lake bars + 0.5 spread applied at fill (Capitaria/MT5 model),
same protocol as every prior batch in this program.

Ingestion (idempotent, delete-before-insert): ONLY the live-fill versions of
the 4 headline configs (SS-M2, SS-M5, SS-M15, V06D-M5) on the IW window, as
run_ids `sim-report-emasar-lf-ss-m2`, `sim-report-emasar-lf-ss-m5`,
`sim-report-emasar-lf-ss-m15`, `sim-report-emasar-lf-v06d-m5`, so traders can
inspect the realistic-fill fills in Trade View.

Run this script directly: `python scripts/report/gen_livefill_bound.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

# Reuse batch1's loader/filler/metrics/ingest machinery + oow_validation's
# window definitions directly (same importlib pattern every batch used).
import importlib.util as _ilu  # noqa: E402

_b1_spec = _ilu.spec_from_file_location(
    "gen_variant_batch1", ROOT / "scripts" / "report" / "gen_variant_batch1.py"
)
_b1 = _ilu.module_from_spec(_b1_spec)
_b1_spec.loader.exec_module(_b1)  # type: ignore[union-attr]

_oow_spec = _ilu.spec_from_file_location(
    "gen_oow_validation", ROOT / "scripts" / "report" / "gen_oow_validation.py"
)
_oow = _ilu.module_from_spec(_oow_spec)
_oow_spec.loader.exec_module(_oow)  # type: ignore[union-attr]

DB_PATH = ROOT / "data" / "research.db"
SYMBOL = _b1.SYMBOL

# ---------------------------------------------------------------------------
# Windows: IW (batch1's own fixed globals) + W1/W2/W3 (oow_validation's).
# ---------------------------------------------------------------------------
WINDOW_KEYS = ("IW", "W1", "W2", "W3")


def _bars_for_window(tf: str, win_key: str) -> list[dict[str, Any]]:
    if win_key == "IW":
        return _b1._bars_for(tf)
    return _oow._bars_for(tf, win_key)


def _run_variant_window(tf: str, win_key: str, kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    """Runs `simular_variant` + spread-at-fill pairing on `tf`/`win_key`'s
    bars -- IW uses batch1's own `run_variant` (closes over IW's fixed
    module-level window bounds), W1/W2/W3 use oow_validation's
    `run_variant_window` (window-parameterized). Both share identical
    pairing/spread logic (oow_validation's is a verbatim port of batch1's)."""
    if win_key == "IW":
        return _b1.run_variant(tf, kwargs)
    return _oow.run_variant_window(tf, win_key, kwargs)


def _compute_metrics_window(trades: list[dict[str, Any]], win_key: str) -> dict[str, Any]:
    if win_key == "IW":
        return _b1.compute_metrics(trades)
    return _oow.compute_metrics_window(trades, win_key)


def _periodo(win_key: str) -> tuple[str, str]:
    if win_key == "IW":
        return "2026-06-08", "2026-07-07"
    win = _oow.WINDOWS[win_key]
    return win["periodo_desde"], win["periodo_hasta"]


def _has_data(tf: str, win_key: str) -> bool:
    """M2's lake tier only starts 2025-12-10 -> W3 (Oct 2025) has zero M2
    bars. Detected mechanically (empty bar list for the window), not
    hardcoded, so it generalizes if the lake tier changes."""
    bars = _bars_for_window(tf, win_key)
    if not bars:
        return False
    if win_key == "IW":
        ws, we = int(_b1.WINDOW_START.timestamp()), int(_b1.WINDOW_END_EXCL.timestamp())
    else:
        win = _oow.WINDOWS[win_key]
        ws, we = int(win["window_start"].timestamp()), int(win["window_end_excl"].timestamp())
    return any(ws <= b["t"] < we for b in bars)


# ---------------------------------------------------------------------------
# Champion skeleton + 13 roster configs (per task spec, mirrors
# gen_oow_validation.py's CONFIGS dict for the ones that overlap).
# ---------------------------------------------------------------------------
SKELETON: dict[str, Any] = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    ema_fast=8, ema_slow=20, sar_step=0.3, sar_max=0.3,
    f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
    ac_modulate=True,
)
INIT_SL_RANGE_K = {"M1": 6.0, "M2": 3.0, "M5": 6.0, "M15": 2.5}


def skeleton_kwargs(tf: str) -> dict[str, Any]:
    return {**SKELETON, "init_sl_range_k": INIT_SL_RANGE_K[tf]}


SAR_ADAPTIVE_LEVER = dict(sar_adaptive=True, sar_fast=(0.3, 0.3), sar_slow=(0.005, 0.05),
                           vol_regime_window=200)
REENTRY_LEVER = dict(reentry_enable=True, reentry_max=2)

CONFIGS: dict[str, dict[str, Any]] = {
    "ss-m2": dict(tf="M2", extra=dict(ac_modulate_factor=0.01, **REENTRY_LEVER, **SAR_ADAPTIVE_LEVER)),
    "ss-m5": dict(tf="M5", extra=dict(ac_modulate_factor=0.01, **REENTRY_LEVER, **SAR_ADAPTIVE_LEVER)),
    "ss-m15": dict(tf="M15", extra=dict(ac_modulate_factor=0.01, **REENTRY_LEVER)),
    "ss-m1": dict(tf="M1", extra=dict(ac_modulate_factor=0.01, **REENTRY_LEVER, **SAR_ADAPTIVE_LEVER)),
    "v06d-m2": dict(tf="M2", extra=dict(ac_modulate_factor=0.01)),
    "v06d-m5": dict(tf="M5", extra=dict(ac_modulate_factor=0.01)),
    "v06d-m15": dict(tf="M15", extra=dict(ac_modulate_factor=0.01)),
    "v13-m5": dict(tf="M5", extra=dict(ac_modulate_factor=0.25, **REENTRY_LEVER)),
    "v13-m15": dict(tf="M15", extra=dict(ac_modulate_factor=0.25, **REENTRY_LEVER)),
    "v15-m2": dict(tf="M2", extra=dict(ac_modulate_factor=0.25, **SAR_ADAPTIVE_LEVER)),
    "v06c-m5": dict(tf="M5", extra=dict(ac_modulate_factor=0.10)),
    "v06c-m15": dict(tf="M15", extra=dict(ac_modulate_factor=0.10)),
    "v06b-m15": dict(tf="M15", extra=dict(ac_modulate_factor=0.25)),
}

# TF-family groupings for the decisive f=0.01-vs-0.10-vs-0.25 comparison.
FAMILY_BY_TF: dict[str, dict[str, str]] = {
    "M5": {"0.01": "v06d-m5", "0.10": "v06c-m5", "0.25": "v06b-m15"},  # v06b is M15-only; see note below
    "M15": {"0.01": "v06d-m15", "0.10": "v06c-m15", "0.25": "v06b-m15"},
}
# NOTE: V06B only exists at M15 in the roster (there's no v06b-m5 config in
# this task's list) -- the M5 family comparison below is therefore 0.01 vs
# 0.10 only (v06d-m5 vs v06c-m5); the M15 family is the full 0.01/0.10/0.25.


def config_kwargs(cfg_id: str) -> dict[str, Any]:
    cfg = CONFIGS[cfg_id]
    tf = cfg["tf"]
    return {**skeleton_kwargs(tf), **cfg["extra"]}


def config_tf(cfg_id: str) -> str:
    return CONFIGS[cfg_id]["tf"]


# ---------------------------------------------------------------------------
# Live-fill ingestion (mirrors gen_oow_validation.ingest_run_window /
# gen_variant_batch1.ingest_run exactly, generalized over IW/W1/W2/W3).
# ---------------------------------------------------------------------------

def ingest_run_any_window(
    registry: ResearchRegistry, *, run_id: str, variant_id: str, tf: str, win_key: str,
    params_delta: dict[str, Any], trades_all: list[dict[str, Any]], display_name: str,
) -> dict[str, Any]:
    import datetime as _dt

    periodo_desde, periodo_hasta = _periodo(win_key)
    strategy_id = registry.upsert_strategy(name="EMASAR", familia="emasar", platform="python-sim")
    registry.upsert_variant(
        strategy_id=strategy_id, variant_id=variant_id, params_delta=params_delta,
        tf=tf, instrumento=SYMBOL, modo_salida=tf.lower(),
    )

    trades_in_window = [t for t in trades_all if t["entry_in_window"]]
    m = _compute_metrics_window(trades_all, win_key)

    run_row = {
        "run_id": run_id, "variant_id": variant_id, "params_hash": None,
        "engine": "sentinel-sim", "fidelity": "screening",
        "periodo_desde": periodo_desde, "periodo_hasta": periodo_hasta,
        "modelo_sim": "sim-report", "status": "OK",
        "trades": m["trades"], "net": m["net"],
        "pf": m["pf"] if m["pf"] not in (None, float("inf")) else None,
        "wr": m["wr"], "payoff": m["payoff"], "maxdd": m["maxdd"], "sharpe": None,
        "metrics_json": json.dumps({
            "display_name": display_name, "spread_model": "capitaria_0.5_at_fill",
            "window_key": win_key, "live_fill_mode": True,
            "total_events_all_dates": len(trades_all), "events_in_window": m["trades"],
            "pct_exit_initsl": m["pct_initsl"], "pct_exit_trail": m["pct_trail"],
            "trades_per_day": m["trades_per_day"],
            "long_pnl": m["long_pnl"], "short_pnl": m["short_pnl"],
            "long_n": m["long_n"], "short_n": m["short_n"],
            "params": params_delta,
        }, ensure_ascii=False),
        "preregistro_id": None, "report_path": None, "trades_path": None,
        "equity_path": None, "signal_history_path": None,
        "fecha_corrida": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"),
        "seed": None, "config_hash": None,
        "source_file": "scripts/report/gen_livefill_bound.py",
        "source_row": None, "fidelity_ref": None,
    }

    conn = registry._connect()  # noqa: SLF001 -- idempotent delete-before-insert
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
            "trade_id": f"{run_id}-{t['signal_id']}-{t['ficha']}", "run_id": run_id,
            "origin": "strategy", "origin_id": variant_id, "session_id": None,
            "ts_in": _b1._ts_str(t["ts_in_epoch"]), "ts_out": _b1._ts_str(t["ts_out_epoch"]),
            "px_in": t["px_in"], "px_out": t["px_out"], "side": t["side"], "volume": _b1.LOT,
            "sl": None, "tp": None, "exit_reason": t["exit_reason"],
            "exit_reason_source": "sim_report", "pnl": pnl, "mae": None, "mfe": None,
            "snapshot_ref": None, "decision_trace_ref": None,
            "signal_id": t["signal_id"], "ficha": t["ficha"],
        })
    registry.insert_trades(run_id, trade_rows)

    registry.audit(
        "scripts.report.gen_livefill_bound", "sim_report_ingested",
        {"run_id": run_id, "variant_id": variant_id, "trades": m["trades"], "net": m["net"]},
    )
    return {"run_id": run_id, "variant_id": variant_id, "tf": tf, **m}


# The 4 headline configs to ingest (IW window, live-fill only).
HEADLINE_INGEST = {
    "ss-m2": "sim-report-emasar-lf-ss-m2",
    "ss-m5": "sim-report-emasar-lf-ss-m5",
    "ss-m15": "sim-report-emasar-lf-ss-m15",
    "v06d-m5": "sim-report-emasar-lf-v06d-m5",
}


def _same_bar_fallback_stats(bars: list[dict[str, Any]], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Runs simular_variant directly (not through the trade-pairing wrapper)
    to count same_bar_fallback-tagged EXIT_TRAIL events -- these are dropped
    by the trade-pairing layer (it only reads motivo/precio/ficha/lado), so
    they must be counted from the raw event stream."""
    events = simular_variant(bars, symbol=SYMBOL, live_fill_mode=True, **kwargs)
    n_exit_trail = sum(1 for e in events if e["motivo"] == "EXIT_TRAIL")
    n_fallback = sum(1 for e in events if e["motivo"] == "EXIT_TRAIL" and e.get("same_bar_fallback"))
    return {"n_exit_trail": n_exit_trail, "n_same_bar_fallback": n_fallback}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None,
                         help="optional path to dump the full raw results as JSON")
    args = parser.parse_args()

    registry = ResearchRegistry(DB_PATH)
    all_results: dict[str, Any] = {}

    for cfg_id in CONFIGS:
        tf = config_tf(cfg_id)
        kwargs = config_kwargs(cfg_id)
        cfg_results: dict[str, Any] = {"tf": tf, "windows": {}}

        for win_key in WINDOW_KEYS:
            if not _has_data(tf, win_key):
                cfg_results["windows"][win_key] = {"skipped": "no_data"}
                print(f"[LF] {cfg_id} ({tf}) {win_key}: SKIPPED (no lake data for this TF/window)")
                continue

            trades_classic = _run_variant_window(tf, win_key, {**kwargs, "live_fill_mode": False})
            m_classic = _compute_metrics_window(trades_classic, win_key)

            trades_live = _run_variant_window(tf, win_key, {**kwargs, "live_fill_mode": True})
            m_live = _compute_metrics_window(trades_live, win_key)

            bars = _bars_for_window(tf, win_key)
            fb_stats = _same_bar_fallback_stats(bars, kwargs)

            delta_net = round(m_live["net"] - m_classic["net"], 2)
            pct_net = (round(100.0 * delta_net / abs(m_classic["net"]), 2)
                       if m_classic["net"] not in (0, 0.0) else None)
            delta_pf = (round(m_live["pf"] - m_classic["pf"], 4)
                        if m_live["pf"] is not None and m_classic["pf"] is not None
                        and m_classic["pf"] != float("inf") and m_live["pf"] != float("inf") else None)
            delta_dd = round(m_live["maxdd"] - m_classic["maxdd"], 2)
            pct_fallback = (round(100.0 * fb_stats["n_same_bar_fallback"] / fb_stats["n_exit_trail"], 2)
                            if fb_stats["n_exit_trail"] else None)

            cell = {
                "classic": m_classic, "live": m_live,
                "delta_net": delta_net, "pct_net": pct_net,
                "delta_pf": delta_pf, "delta_dd": delta_dd,
                "same_bar_fallback": fb_stats, "pct_fallback_of_trail_exits": pct_fallback,
            }
            cfg_results["windows"][win_key] = cell
            print(f"[LF] {cfg_id} ({tf}) {win_key}: classic_net={m_classic['net']} "
                  f"live_net={m_live['net']} delta={delta_net} ({pct_net}%) "
                  f"fallback={fb_stats['n_same_bar_fallback']}/{fb_stats['n_exit_trail']} "
                  f"({pct_fallback}%)")

            # Ingest live-fill IW runs for the 4 headline configs.
            if win_key == "IW" and cfg_id in HEADLINE_INGEST:
                run_id = HEADLINE_INGEST[cfg_id]
                json_safe_kwargs = {k: (list(v) if isinstance(v, tuple) else v)
                                     for k, v in kwargs.items()}
                r = ingest_run_any_window(
                    registry, run_id=run_id,
                    variant_id=f"EMS_XAU_LF_{cfg_id.upper().replace('-', '_')}_{tf}_IW",
                    tf=tf, win_key="IW",
                    params_delta={**json_safe_kwargs, "live_fill_mode": True,
                                  "variant": f"Live-fill bound: {cfg_id} on IW"},
                    trades_all=trades_live,
                    display_name=f"EMASAR live-fill {cfg_id} {tf} IW",
                )
                cell["ingested"] = r
                print(f"[LF INGEST] {cfg_id}: ingested={r['run_id']} net={r['net']}")

        all_results[cfg_id] = cfg_results

    # ===== Decisive per-TF verdict: does f=0.01 still beat 0.10/0.25 within
    # the same family, under live_fill_mode, on IW? =====
    print("\n==== VERDICT: f=0.01 vs 0.10 vs 0.25 (live_fill_mode, IW) ====")
    verdicts: dict[str, Any] = {}
    for tf, family in FAMILY_BY_TF.items():
        nets = {}
        for factor_tag, cfg_id in family.items():
            cell = all_results[cfg_id]["windows"].get("IW", {})
            if "live" in cell:
                nets[factor_tag] = cell["live"]["net"]
        if not nets:
            continue
        best_factor = max(nets, key=lambda k: nets[k])
        if best_factor == "0.01":
            verdict = "0.01 HOLDS"
        elif best_factor == "0.10":
            verdict = "0.01 DEFLATES to 0.10"
        elif best_factor == "0.25":
            verdict = "0.01 DEFLATES to 0.25"
        else:
            verdict = "family flat"
        # "family flat" override: nets within 1% of each other.
        vals = list(nets.values())
        if vals and (max(vals) - min(vals)) / max(abs(max(vals)), 1e-9) < 0.01:
            verdict = "family flat"
        verdicts[tf] = {"nets_live_iw": nets, "best_factor": best_factor, "verdict": verdict}
        print(f"[VERDICT] {tf}: nets(live,IW)={nets} -> {verdict}")

    all_results["_verdicts"] = verdicts

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        with args.report_json.open("w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nRaw results JSON written to {args.report_json}")

    print("\n==== DONE ====")


if __name__ == "__main__":
    main()
