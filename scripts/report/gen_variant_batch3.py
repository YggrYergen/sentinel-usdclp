"""scripts/report/gen_variant_batch3.py -- Batch 3 of the EMASAR variant
research program: V-05 (staggered take-profit by R multiples), V-06
(AC-modulated trailing), V-07 (runner exit on sustained AC deceleration).
All three are engine extensions added to
`sentinel_engine.strategies.emasar_variant.simular_variant` in this batch
(see that module's docstring). All default to the pre-batch-3 behavior
EXACTLY (`f1_tp_r=0.0`/`f2_tp_r=0.0`, `ac_modulate=False`,
`f3_ac_decel_exit=False`) -- pinned by
`tests/strategies/test_emasar_variant.py` (19/19 pass).

Reuses (does NOT modify) `scripts/report/gen_variant_batch1.py`'s
load/fill/persistence conventions (BID lake bars, spread 0.5 applied at
fill, ResearchRegistry idempotent delete-before-insert per run_id). See that
module's docstring + `docs/superpowers/research/
2026-07-13-emasar-variants-batch1.md` and `...batch2.md` for baselines and
conventions.

WINDOW: 2026-06-08 -> 2026-07-07 (bars from the lake; warmup starts
2026-06-01). TFs: M1, M2, M5, M15.

Each variant is run TWICE per TF:
  (a) "base" -- on top of V-09 control params (init_sl_range_k=1.0, flat
      100/100/100 trail), per the batch-2 learnings that this ladder/k
      combo is the best-behaved base to isolate a new lever's effect.
  (b) "stacked" -- on top of the V-01b winning init_sl_range_k for that TF
      (M1 k=6.0, M2 k=3.0, M5 k=6.0, M15 k=2.5; still flat 100/100/100
      trail, per the task spec) -- tests whether the new lever's gain (if
      any) compounds with the program's best-known single lever so far.

Only the best-net combo PER VARIANT PER TF (across base+stacked, whichever
scored higher) is ingested into data/research.db, as
sim-report-emasar-v05-<tf> / v06 / v07.

Run this script directly: `python scripts/report/gen_variant_batch3.py`.
Idempotent: re-running replaces the same run_ids (delete-before-insert).
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

# Reuse batch1's loader/filler/metrics/ingest machinery directly (same
# importlib pattern batch2 used).
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
# V-01b winning init_sl_range_k per TF (batch 2 result) -- used for the
# "stacked" leg of each of this batch's sweeps.
# ---------------------------------------------------------------------------
V01B_BEST_K = {"M1": 6.0, "M2": 3.0, "M5": 6.0, "M15": 2.5}

# ---------------------------------------------------------------------------
# V-05: staggered take-profit by R multiples. (f1_tp_r, f2_tp_r) grid.
# ---------------------------------------------------------------------------
V05_TP_GRID = ((1.0, 2.0), (1.0, 3.0), (1.5, 3.0), (0.75, 1.5))

# ---------------------------------------------------------------------------
# V-06: AC-modulated trailing. factor grid.
# ---------------------------------------------------------------------------
V06_FACTOR_GRID = (0.5, 0.7)

# ---------------------------------------------------------------------------
# V-07: runner exit on sustained AC deceleration. bars grid.
# ---------------------------------------------------------------------------
V07_BARS_GRID = (2, 3)


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
    """Runs both the 'base' (V-09 params, k=1.0) and 'stacked' (V-01b best k
    for this TF) legs of a sweep grid, returns combined results plus the
    single overall-best combo (by net) across both legs."""
    base_kwargs = dict(V09_PARAMS)
    stacked_kwargs = {**V09_PARAMS, "init_sl_range_k": V01B_BEST_K[tf]}

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None,
                         help="optional path to dump the full raw results as JSON")
    args = parser.parse_args()

    registry = ResearchRegistry(DB_PATH)
    all_results: dict[str, Any] = {"v05": {}, "v06": {}, "v07": {}}

    # ===== V-05: staggered take-profit by R multiples =====
    def v05_kwargs_fn(base: dict[str, Any], val: tuple[float, float]) -> dict[str, Any]:
        f1_tp_r, f2_tp_r = val
        return {**base, "f1_tp_r": f1_tp_r, "f2_tp_r": f2_tp_r}

    v05_results: dict[str, Any] = {}
    for tf in TFS:
        res = _run_variant_both_legs(tf, list(V05_TP_GRID), v05_kwargs_fn, "V-05")
        tag = f"tp{str(res['overall_val'][0]).replace('.', 'p')}_{str(res['overall_val'][1]).replace('.', 'p')}"
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v05-{tf.lower()}",
            variant_id=f"EMS_XAU_V05_{tf}_c1_{tag}_{res['overall_leg']}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**res["overall_kwargs"],
                                  "variant": f"V-05 staggered TP by R, chosen (f1_tp_r,f2_tp_r)={res['overall_val']}, "
                                             f"leg={res['overall_leg']}"},
            trades_all=res["overall_trades"],
            display_name=f"EMASAR V-05 staggered TP, best {res['overall_val']} ({res['overall_leg']}) {tf}",
        )
        v05_results[tf] = {**res, "ingested": r}
        print(f"[V-05] {tf}: BEST val={res['overall_val']} leg={res['overall_leg']} net={r['net']} "
              f"(base_best_net={res['base_best_net']}, stacked_best_net={res['stacked_best_net']}) "
              f"ingested={r['run_id']}")
    all_results["v05"] = v05_results

    # ===== V-06: AC-modulated trailing =====
    def v06_kwargs_fn(base: dict[str, Any], val: float) -> dict[str, Any]:
        return {**base, "ac_modulate": True, "ac_modulate_factor": val}

    v06_results: dict[str, Any] = {}
    for tf in TFS:
        res = _run_variant_both_legs(tf, list(V06_FACTOR_GRID), v06_kwargs_fn, "V-06")
        tag = f"f{str(res['overall_val']).replace('.', 'p')}"
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v06-{tf.lower()}",
            variant_id=f"EMS_XAU_V06_{tf}_c1_{tag}_{res['overall_leg']}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**res["overall_kwargs"],
                                  "variant": f"V-06 AC-modulated trailing, chosen factor={res['overall_val']}, "
                                             f"leg={res['overall_leg']}"},
            trades_all=res["overall_trades"],
            display_name=f"EMASAR V-06 AC-modulated trailing, best factor={res['overall_val']} ({res['overall_leg']}) {tf}",
        )
        v06_results[tf] = {**res, "ingested": r}
        print(f"[V-06] {tf}: BEST factor={res['overall_val']} leg={res['overall_leg']} net={r['net']} "
              f"(base_best_net={res['base_best_net']}, stacked_best_net={res['stacked_best_net']}) "
              f"ingested={r['run_id']}")
    all_results["v06"] = v06_results

    # ===== V-07: runner exit on sustained AC deceleration =====
    def v07_kwargs_fn(base: dict[str, Any], val: int) -> dict[str, Any]:
        return {**base, "f3_ac_decel_exit": True, "f3_ac_decel_bars": val}

    v07_results: dict[str, Any] = {}
    for tf in TFS:
        res = _run_variant_both_legs(tf, list(V07_BARS_GRID), v07_kwargs_fn, "V-07")
        tag = f"bars{res['overall_val']}"
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v07-{tf.lower()}",
            variant_id=f"EMS_XAU_V07_{tf}_c1_{tag}_{res['overall_leg']}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**res["overall_kwargs"],
                                  "variant": f"V-07 runner AC-decel exit, chosen bars={res['overall_val']}, "
                                             f"leg={res['overall_leg']}"},
            trades_all=res["overall_trades"],
            display_name=f"EMASAR V-07 runner AC-decel exit, best bars={res['overall_val']} ({res['overall_leg']}) {tf}",
        )
        v07_results[tf] = {**res, "ingested": r}
        print(f"[V-07] {tf}: BEST bars={res['overall_val']} leg={res['overall_leg']} net={r['net']} "
              f"(base_best_net={res['base_best_net']}, stacked_best_net={res['stacked_best_net']}) "
              f"ingested={r['run_id']}")
    all_results["v07"] = v07_results

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        with args.report_json.open("w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nRaw results JSON written to {args.report_json}")

    print("\n==== DONE ====")


if __name__ == "__main__":
    main()
