"""scripts/report/gen_variant_batch4.py -- Batch 4 of the EMASAR variant
research program: V-06b (finish the ac_modulate_factor sweep, zero-code),
V-08 (AC "rojo->verde" transition entry gate, engine extension), V-11
(session/hour entry filter, diagnostic + engine extension), V-12 (intrabar
entry + reinforced confirmation, engine extension).

V-08/V-11/V-12 add `g5_mode`, `blocked_hours`, `entry_timing` to
`sentinel_engine.strategies.emasar_variant.simular_variant` (see that
module's docstring). All three default to the pre-batch-4 behavior EXACTLY
(`g5_mode='ref'`, `blocked_hours=None`, `entry_timing=0`) -- pinned by
`tests/strategies/test_emasar_variant.py` (31/31 pass, extended from batch
3's 19 with 12 new tests).

Reuses (does NOT modify) `scripts/report/gen_variant_batch1.py`'s
load/fill/persistence conventions (BID lake bars, spread 0.5 applied at
fill, ResearchRegistry idempotent delete-before-insert per run_id). See that
module's docstring + `docs/superpowers/research/
2026-07-13-emasar-variants-batch{1,2,3}.md` for baselines and conventions.

WINDOW: 2026-06-08 -> 2026-07-07 (bars from the lake; warmup starts
2026-06-01). TFs: M1, M2, M5, M15.

PROGRAM "CHAMPION CONFIG" (V-01b k stacked with V-06 ac_modulate
factor=0.5, batch 3's best-net lever on EVERY TF): per-TF
`init_sl_range_k` = M1 6.0 / M2 3.0 / M5 6.0 / M15 2.5, `ac_modulate=True`,
`ac_modulate_factor=0.5`. Champion nets (from batch 3): M1 -25,230.6 ·
M2 25,773.9 · M5 43,799.7 · M15 40,514.7.

Each of V-08/V-11/V-12 is run in BOTH legs per the task spec:
  (a) "base" -- V-09 control params (init_sl_range_k=1.0, flat 100/100/100
      trail, no ac_modulate).
  (b) "stacked" -- the CHAMPION config (per-TF k, ac_modulate=True,
      factor=0.5) plus this variant's own new lever on top.

Only the overall-best combo PER VARIANT PER TF (across base+stacked,
whichever scored higher net) is ingested into data/research.db, as
sim-report-emasar-v06b-<tf> / v08 / v11 / v12.

Run this script directly: `python scripts/report/gen_variant_batch4.py`.
Idempotent: re-running replaces the same run_ids (delete-before-insert).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

# Reuse batch1's loader/filler/metrics/ingest machinery directly (same
# importlib pattern batch2/batch3 used).
import importlib.util as _ilu  # noqa: E402

_b1_spec = _ilu.spec_from_file_location(
    "gen_variant_batch1", ROOT / "scripts" / "report" / "gen_variant_batch1.py"
)
_b1 = _ilu.module_from_spec(_b1_spec)
_b1_spec.loader.exec_module(_b1)  # type: ignore[union-attr]

DB_PATH = ROOT / "data" / "research.db"
TFS = _b1.TFS
V09_PARAMS = _b1.V09_PARAMS
run_variant = _b1.run_variant
compute_metrics = _b1.compute_metrics
ingest_run = _b1.ingest_run

# ---------------------------------------------------------------------------
# Champion config (V-01b k stacked with V-06 factor=0.5), per TF.
# ---------------------------------------------------------------------------
V01B_BEST_K = {"M1": 6.0, "M2": 3.0, "M5": 6.0, "M15": 2.5}


def champion_kwargs(tf: str) -> dict[str, Any]:
    return {
        **V09_PARAMS,
        "init_sl_range_k": V01B_BEST_K[tf],
        "ac_modulate": True,
        "ac_modulate_factor": 0.5,
    }


CHAMPION_NET = {"M1": -25230.6, "M2": 25773.9, "M5": 43799.7, "M15": 40514.7}

# ---------------------------------------------------------------------------
# V-06b: ac_modulate_factor sweep, on the champion config, all 4 TFs.
# ---------------------------------------------------------------------------
V06B_FACTOR_GRID = (0.25, 0.35, 0.45)

# ---------------------------------------------------------------------------
# V-09 control params (exact spec, "control leg" for V-08/V-11/V-12).
# ---------------------------------------------------------------------------
V09_CONTROL = dict(V09_PARAMS)


def _run_sweep_leg(
    tf: str,
    base_kwargs: dict[str, Any],
    grid: list[Any],
    kwargs_fn,
    label: str,
    leg: str,
) -> tuple[list[dict[str, Any]], Any, float, dict[str, Any], list[dict[str, Any]]]:
    """Runs one leg (base or stacked) of a sweep grid for one TF. Returns
    (sweep_metrics_rows, best_grid_value, best_net, best_kwargs, best_trades)."""
    sweep_metrics: list[dict[str, Any]] = []
    best_net = None
    best_val = None
    best_kwargs = None
    best_trades = None
    for val in grid:
        kwargs = kwargs_fn(base_kwargs, val)
        trades = run_variant(tf, kwargs)
        m = compute_metrics(trades)
        sweep_metrics.append({"leg": leg, "val": val, **m})
        print(f"[{label}] {tf} leg={leg} val={val}: trades={m['trades']} net={m['net']} "
              f"pf={m['pf']} wr={m['wr']} maxdd={m['maxdd']}")
        if best_net is None or m["net"] > best_net:
            best_net = m["net"]
            best_val = val
            best_kwargs = kwargs
            best_trades = trades
    return sweep_metrics, best_val, best_net, best_kwargs, best_trades


def _run_variant_both_legs(
    tf: str,
    grid: list[Any],
    kwargs_fn,
    label: str,
) -> dict[str, Any]:
    """Runs both the 'base' (V-09 control) and 'stacked' (CHAMPION config)
    legs of a sweep grid, returns combined results plus the single
    overall-best combo (by net) across both legs."""
    base_kwargs = dict(V09_CONTROL)
    stacked_kwargs = champion_kwargs(tf)

    base_sweep, base_best_val, base_best_net, base_best_kwargs, base_best_trades = _run_sweep_leg(
        tf, base_kwargs, grid, kwargs_fn, label, "base",
    )
    stacked_sweep, stacked_best_val, stacked_best_net, stacked_best_kwargs, stacked_best_trades = _run_sweep_leg(
        tf, stacked_kwargs, grid, kwargs_fn, label, "stacked",
    )

    if stacked_best_net > base_best_net:
        overall_leg = "stacked"
        overall_val = stacked_best_val
        overall_net = stacked_best_net
        overall_kwargs = stacked_best_kwargs
        overall_trades = stacked_best_trades
    else:
        overall_leg = "base"
        overall_val = base_best_val
        overall_net = base_best_net
        overall_kwargs = base_best_kwargs
        overall_trades = base_best_trades

    return {
        "base_sweep": base_sweep, "base_best_val": base_best_val, "base_best_net": base_best_net,
        "stacked_sweep": stacked_sweep, "stacked_best_val": stacked_best_val, "stacked_best_net": stacked_best_net,
        "stacking_helps": stacked_best_net > base_best_net,
        "overall_leg": overall_leg, "overall_val": overall_val, "overall_net": overall_net,
        "overall_kwargs": overall_kwargs, "overall_trades": overall_trades,
    }


# ---------------------------------------------------------------------------
# V-11 step (a): hour-of-day PnL diagnostic from the CHAMPION-config
# simulated trades, per TF. Uses ts_in_epoch (signal-bar timestamp) already
# carried by run_variant's trade rows -> UTC hour (lake timezone as-is).
# ---------------------------------------------------------------------------

def v11_hour_diagnostic(tf: str) -> dict[int, dict[str, Any]]:
    trades = run_variant(tf, champion_kwargs(tf))
    trades_in = [t for t in trades if t["entry_in_window"]]
    by_hour: dict[int, dict[str, Any]] = {h: {"net": 0.0, "n": 0} for h in range(24)}
    for t in trades_in:
        hr = datetime.fromtimestamp(t["ts_in_epoch"], tz=timezone.utc).hour
        pnl = _b1._pnl(t["side"], t["px_in"], t["px_out"])
        by_hour[hr]["net"] += pnl
        by_hour[hr]["n"] += 1
    for h in by_hour:
        by_hour[h]["net"] = round(by_hour[h]["net"], 2)
    return by_hour


def bottom_tercile_hours(by_hour: dict[int, dict[str, Any]]) -> frozenset[int]:
    """Bottom tercile (8 of 24 hours) by net, restricted to negative-net
    hours forming that bottom tercile (per task spec: 'negative-net hours
    forming the bottom tercile'). If fewer than 8 hours are negative, only
    the negative ones are blocked (never blocks a positive-net hour just to
    fill the tercile quota)."""
    ranked = sorted(by_hour.items(), key=lambda kv: kv[1]["net"])
    tercile_n = 8
    candidates = ranked[:tercile_n]
    blocked = frozenset(h for h, v in candidates if v["net"] < 0.0)
    return blocked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None,
                         help="optional path to dump the full raw results as JSON")
    args = parser.parse_args()

    registry = ResearchRegistry(DB_PATH)
    all_results: dict[str, Any] = {"v06b": {}, "v08": {}, "v11": {}, "v12": {}}

    # ===== V-06b: finish the ac_modulate_factor sweep on the champion config =====
    v06b_results: dict[str, Any] = {}
    for tf in TFS:
        base_kwargs = champion_kwargs(tf)
        sweep_metrics: list[dict[str, Any]] = []
        best_net = None
        best_factor = None
        best_kwargs = None
        best_trades = None
        for factor in V06B_FACTOR_GRID:
            kwargs = {**base_kwargs, "ac_modulate_factor": factor}
            trades = run_variant(tf, kwargs)
            m = compute_metrics(trades)
            sweep_metrics.append({"factor": factor, **m})
            print(f"[V-06b] {tf} factor={factor}: trades={m['trades']} net={m['net']} "
                  f"pf={m['pf']} wr={m['wr']} maxdd={m['maxdd']}")
            if best_net is None or m["net"] > best_net:
                best_net = m["net"]
                best_factor = factor
                best_kwargs = kwargs
                best_trades = trades

        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v06b-{tf.lower()}",
            variant_id=f"EMS_XAU_V06b_{tf}_c1_f{str(best_factor).replace('.', 'p')}_champion",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**best_kwargs,
                                  "variant": f"V-06b ac_modulate_factor sweep on champion, chosen factor={best_factor}"},
            trades_all=best_trades,
            display_name=f"EMASAR V-06b ac_modulate_factor sweep, best factor={best_factor} (champion) {tf}",
        )
        v06b_results[tf] = {"sweep": sweep_metrics, "best_factor": best_factor,
                             "champion_net": CHAMPION_NET[tf], "ingested": r}
        print(f"[V-06b] {tf}: BEST factor={best_factor} net={r['net']} "
              f"(champion factor=0.5 net={CHAMPION_NET[tf]}) ingested={r['run_id']}")
    all_results["v06b"] = v06b_results

    # ===== V-08: AC "rojo->verde" transition entry gate =====
    def v08_kwargs_fn(base: dict[str, Any], val: str) -> dict[str, Any]:
        return {**base, "g5_mode": val}

    v08_results: dict[str, Any] = {}
    for tf in TFS:
        res = _run_variant_both_legs(tf, ["ac4_transition"], v08_kwargs_fn, "V-08")
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v08-{tf.lower()}",
            variant_id=f"EMS_XAU_V08_{tf}_c1_ac4transition_{res['overall_leg']}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**res["overall_kwargs"],
                                  "variant": f"V-08 AC rojo->verde transition gate, leg={res['overall_leg']}"},
            trades_all=res["overall_trades"],
            display_name=f"EMASAR V-08 AC transition gate ({res['overall_leg']}) {tf}",
        )
        v08_results[tf] = {**res, "ingested": r}
        print(f"[V-08] {tf}: BEST leg={res['overall_leg']} net={r['net']} "
              f"(base_net={res['base_best_net']}, stacked_net={res['stacked_best_net']}, "
              f"champion_net={CHAMPION_NET[tf]}) ingested={r['run_id']}")
    all_results["v08"] = v08_results

    # ===== V-11: session/hour entry filter =====
    # Step (a): diagnostic, hour-of-day net PnL profile per TF, from the
    # CHAMPION-config trades.
    v11_diag: dict[str, Any] = {}
    v11_blocked: dict[str, frozenset[int]] = {}
    for tf in TFS:
        by_hour = v11_hour_diagnostic(tf)
        blocked = bottom_tercile_hours(by_hour)
        v11_diag[tf] = by_hour
        v11_blocked[tf] = blocked
        print(f"[V-11 diag] {tf}: blocked_hours(bottom tercile, net<0)={sorted(blocked)}")
        for h in range(24):
            print(f"  [V-11 diag] {tf} hour={h:02d}: net={by_hour[h]['net']} n={by_hour[h]['n']}")

    # Step (b): block per TF's bottom-tercile hours, both legs.
    def v11_kwargs_fn(base: dict[str, Any], val: frozenset[int]) -> dict[str, Any]:
        return {**base, "blocked_hours": val}

    v11_results: dict[str, Any] = {}
    for tf in TFS:
        res = _run_variant_both_legs(tf, [v11_blocked[tf]], v11_kwargs_fn, "V-11")
        tag = "h" + "-".join(str(h) for h in sorted(v11_blocked[tf])) if v11_blocked[tf] else "none"
        # blocked_hours is a frozenset -> not JSON serializable; params_delta
        # (persisted as JSON in the registry) needs a sorted list instead.
        # The actual sim run above already used the frozenset correctly.
        json_safe_kwargs = {**res["overall_kwargs"],
                             "blocked_hours": sorted(res["overall_kwargs"].get("blocked_hours") or [])}
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v11-{tf.lower()}",
            variant_id=f"EMS_XAU_V11_{tf}_c1_{tag}_{res['overall_leg']}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**json_safe_kwargs,
                                  "variant": f"V-11 hour filter, blocked_hours={sorted(v11_blocked[tf])}, "
                                             f"leg={res['overall_leg']} (in-sample, overfit risk)"},
            trades_all=res["overall_trades"],
            display_name=f"EMASAR V-11 hour filter ({res['overall_leg']}) {tf}",
        )
        v11_results[tf] = {**res, "blocked_hours": sorted(v11_blocked[tf]), "ingested": r}
        print(f"[V-11] {tf}: blocked={sorted(v11_blocked[tf])} BEST leg={res['overall_leg']} net={r['net']} "
              f"(base_net={res['base_best_net']}, stacked_net={res['stacked_best_net']}, "
              f"champion_net={CHAMPION_NET[tf]}) ingested={r['run_id']}")
    all_results["v11"] = {"diag": v11_diag, "blocked_hours": {tf: sorted(v11_blocked[tf]) for tf in TFS},
                           "per_tf": v11_results}

    # ===== V-12: intrabar entry + reinforced confirmation =====
    def v12_kwargs_fn(base: dict[str, Any], val: int) -> dict[str, Any]:
        return {**base, "entry_timing": 1, "confirm_count": val}

    v12_results: dict[str, Any] = {}
    for tf in TFS:
        res = _run_variant_both_legs(tf, [2, 3], v12_kwargs_fn, "V-12")
        tag = f"cc{res['overall_val']}"
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v12-{tf.lower()}",
            variant_id=f"EMS_XAU_V12_{tf}_timing1_{tag}_{res['overall_leg']}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**res["overall_kwargs"],
                                  "variant": f"V-12 intrabar entry_timing=1, confirm_count={res['overall_val']}, "
                                             f"leg={res['overall_leg']}"},
            trades_all=res["overall_trades"],
            display_name=f"EMASAR V-12 intrabar entry, confirm_count={res['overall_val']} ({res['overall_leg']}) {tf}",
        )
        v12_results[tf] = {**res, "ingested": r}
        print(f"[V-12] {tf}: BEST confirm_count={res['overall_val']} leg={res['overall_leg']} net={r['net']} "
              f"(base_net={res['base_best_net']}, stacked_net={res['stacked_best_net']}, "
              f"champion_net={CHAMPION_NET[tf]}) ingested={r['run_id']}")
    all_results["v12"] = v12_results

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        with args.report_json.open("w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nRaw results JSON written to {args.report_json}")

    print("\n==== DONE ====")


if __name__ == "__main__":
    main()
