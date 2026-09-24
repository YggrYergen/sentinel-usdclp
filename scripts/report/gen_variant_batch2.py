"""scripts/report/gen_variant_batch2.py -- Batch 2 of the EMASAR variant
research program: V-01b (range_k sweep extension), V-04 (trailing ladder
sweep), V-02 (breakeven-at-R, engine extension), V-03 (range-based trailing
ladder, engine extension).

Reuses (does NOT modify) `scripts/report/gen_variant_batch1.py`'s
load/fill/persistence conventions (copied verbatim: BID lake bars, spread 0.5
applied at fill, ResearchRegistry idempotent delete-before-insert per
run_id). See that module's docstring + `docs/superpowers/research/
2026-07-13-emasar-variants-batch1.md` for the full baseline context.

WINDOW: 2026-06-08 -> 2026-07-07 (bars from the lake; warmup starts
2026-06-01). TFs: M1, M2, M5, M15.

Run this script directly: `python scripts/report/gen_variant_batch2.py`.
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

# Reuse batch1's loader/filler/metrics/ingest machinery directly.
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
# V-01b: extend the range_k sweep past batch 1's k=2.0 ceiling.
# ---------------------------------------------------------------------------
V01B_RANGE_K_GRID = (2.5, 3.0, 4.0, 6.0)

# ---------------------------------------------------------------------------
# V-04: trailing ladder sweep grid (constraint f1<f2<f3).
# ---------------------------------------------------------------------------
V04_F1_GRID = (80.0, 100.0, 120.0)
V04_F2_GRID = (150.0, 170.0, 230.0)
V04_F3_GRID = (230.0, 289.0, 340.0)


def _v04_combos() -> list[tuple[float, float, float]]:
    combos = []
    for f1 in V04_F1_GRID:
        for f2 in V04_F2_GRID:
            for f3 in V04_F3_GRID:
                if f1 < f2 < f3:
                    combos.append((f1, f2, f3))
    return combos


# ---------------------------------------------------------------------------
# V-02: breakeven-at-R sweep.
# ---------------------------------------------------------------------------
V02_BE_AT_R_GRID = (0.5, 1.0, 1.5)
V02_BE_OFFSET_PIPS = 0.5

# ---------------------------------------------------------------------------
# V-03: range-based trailing ladder sweep (f1_k, f2_k, f3_k).
# ---------------------------------------------------------------------------
V03_LADDER_GRID = (
    (2.0, 3.0, 4.0),
    (1.5, 2.5, 3.5),
    (3.0, 4.0, 6.0),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None,
                         help="optional path to dump the full raw results as JSON")
    args = parser.parse_args()

    registry = ResearchRegistry(DB_PATH)
    all_results: dict[str, Any] = {"v01b": {}, "v04": {}, "v02": {}, "v03": {}}

    # ===== V-01b: range_k sweep extension =====
    v01b_results: dict[str, dict[str, Any]] = {}
    for tf in TFS:
        sweep_metrics: list[dict[str, Any]] = []
        best_net = None
        best_k = None
        best_kwargs = None
        best_trades = None
        for k in V01B_RANGE_K_GRID:
            kwargs = {**V09_PARAMS, "init_sl_range_k": k}
            trades = run_variant(tf, kwargs)
            m = compute_metrics(trades)
            sweep_metrics.append({"k": k, **m})
            print(f"[V-01b] {tf} k={k}: trades={m['trades']} net={m['net']} pf={m['pf']} "
                  f"wr={m['wr']} maxdd={m['maxdd']} initsl%={m['pct_initsl']}")
            if best_net is None or m["net"] > best_net:
                best_net = m["net"]
                best_k = k
                best_kwargs = kwargs
                best_trades = trades

        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v01b-{tf.lower()}",
            variant_id=f"EMS_XAU_V01B_{tf}_c1_k{str(best_k).replace('.', 'p')}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**best_kwargs, "variant": f"V-01b range_k sweep ext, chosen k={best_k}"},
            trades_all=best_trades,
            display_name=f"EMASAR V-01b range_k sweep ext, best k={best_k} {tf}",
        )
        v01b_results[tf] = {"sweep": sweep_metrics, "best_k": best_k, "ingested": r}
        print(f"[V-01b] {tf}: BEST k={best_k} net={r['net']} ingested={r['run_id']}")
    all_results["v01b"] = v01b_results

    # ===== V-04: trailing ladder sweep =====
    combos = _v04_combos()
    v04_results: dict[str, dict[str, Any]] = {}
    for tf in TFS:
        sweep_metrics: list[dict[str, Any]] = []
        best_net = None
        best_ladder = None
        best_kwargs = None
        best_trades = None
        for (f1, f2, f3) in combos:
            kwargs = {**V09_PARAMS, "f1_trail_pips": f1, "f2_trail_pips": f2, "f3_trail_pips": f3}
            trades = run_variant(tf, kwargs)
            m = compute_metrics(trades)
            sweep_metrics.append({"f1": f1, "f2": f2, "f3": f3, **m})
            print(f"[V-04] {tf} ladder=({f1},{f2},{f3}): trades={m['trades']} net={m['net']} "
                  f"pf={m['pf']} wr={m['wr']} maxdd={m['maxdd']}")
            if best_net is None or m["net"] > best_net:
                best_net = m["net"]
                best_ladder = (f1, f2, f3)
                best_kwargs = kwargs
                best_trades = trades

        ladder_tag = f"f1_{best_ladder[0]:.0f}_f2_{best_ladder[1]:.0f}_f3_{best_ladder[2]:.0f}"
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v04-{tf.lower()}",
            variant_id=f"EMS_XAU_V04_{tf}_c1_{ladder_tag}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**best_kwargs, "variant": f"V-04 trailing ladder sweep, chosen {best_ladder}"},
            trades_all=best_trades,
            display_name=f"EMASAR V-04 trailing ladder sweep, best {best_ladder} {tf}",
        )
        v04_results[tf] = {"sweep": sweep_metrics, "best_ladder": best_ladder, "ingested": r}
        print(f"[V-04] {tf}: BEST ladder={best_ladder} net={r['net']} ingested={r['run_id']}")
    all_results["v04"] = v04_results

    # ===== V-02: breakeven-at-R sweep =====
    v02_results: dict[str, dict[str, Any]] = {}
    for tf in TFS:
        sweep_metrics: list[dict[str, Any]] = []
        best_net = None
        best_be = None
        best_kwargs = None
        best_trades = None
        for be_at_r in V02_BE_AT_R_GRID:
            kwargs = {**V09_PARAMS, "be_at_r": be_at_r, "be_offset_pips": V02_BE_OFFSET_PIPS}
            trades = run_variant(tf, kwargs)
            m = compute_metrics(trades)
            sweep_metrics.append({"be_at_r": be_at_r, **m})
            print(f"[V-02] {tf} be_at_r={be_at_r}: trades={m['trades']} net={m['net']} "
                  f"pf={m['pf']} wr={m['wr']} maxdd={m['maxdd']}")
            if best_net is None or m["net"] > best_net:
                best_net = m["net"]
                best_be = be_at_r
                best_kwargs = kwargs
                best_trades = trades

        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v02-{tf.lower()}",
            variant_id=f"EMS_XAU_V02_{tf}_c1_be{str(best_be).replace('.', 'p')}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**best_kwargs, "variant": f"V-02 breakeven-at-R, chosen be_at_r={best_be}"},
            trades_all=best_trades,
            display_name=f"EMASAR V-02 breakeven-at-R, best be_at_r={best_be} {tf}",
        )
        v02_results[tf] = {"sweep": sweep_metrics, "best_be_at_r": best_be, "ingested": r}
        print(f"[V-02] {tf}: BEST be_at_r={best_be} net={r['net']} ingested={r['run_id']}")
    all_results["v02"] = v02_results

    # ===== V-03: range-based trailing ladder sweep =====
    v03_results: dict[str, dict[str, Any]] = {}
    for tf in TFS:
        sweep_metrics: list[dict[str, Any]] = []
        best_net = None
        best_ladder = None
        best_kwargs = None
        best_trades = None
        for (k1, k2, k3) in V03_LADDER_GRID:
            kwargs = {
                **V09_PARAMS, "trail_mode_ladder": "range",
                "f1_trail_range_k": k1, "f2_trail_range_k": k2, "f3_trail_range_k": k3,
            }
            trades = run_variant(tf, kwargs)
            m = compute_metrics(trades)
            sweep_metrics.append({"k1": k1, "k2": k2, "k3": k3, **m})
            print(f"[V-03] {tf} ladder_k=({k1},{k2},{k3}): trades={m['trades']} net={m['net']} "
                  f"pf={m['pf']} wr={m['wr']} maxdd={m['maxdd']}")
            if best_net is None or m["net"] > best_net:
                best_net = m["net"]
                best_ladder = (k1, k2, k3)
                best_kwargs = kwargs
                best_trades = trades

        ladder_tag = f"k1_{best_ladder[0]}_k2_{best_ladder[1]}_k3_{best_ladder[2]}".replace(".", "p")
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v03-{tf.lower()}",
            variant_id=f"EMS_XAU_V03_{tf}_c1_{ladder_tag}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**best_kwargs, "variant": f"V-03 range trailing ladder, chosen {best_ladder}"},
            trades_all=best_trades,
            display_name=f"EMASAR V-03 range trailing ladder, best {best_ladder} {tf}",
        )
        v03_results[tf] = {"sweep": sweep_metrics, "best_ladder_k": best_ladder, "ingested": r}
        print(f"[V-03] {tf}: BEST ladder_k={best_ladder} net={r['net']} ingested={r['run_id']}")
    all_results["v03"] = v03_results

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        with args.report_json.open("w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nRaw results JSON written to {args.report_json}")

    print("\n==== DONE ====")


if __name__ == "__main__":
    main()
