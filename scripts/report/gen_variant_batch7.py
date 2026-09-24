"""scripts/report/gen_variant_batch7.py -- Batch 7 ("SUPER-STACK") of the
EMASAR variant research program: combines the program's winning levers that
have never been combined before, on top of the champion skeleton.

ZERO new engine code: every parameter used here already exists on
`sentinel_engine.strategies.emasar_variant.simular_variant`.

CHAMPION SKELETON (fixed for every run, all TFs):
    confirm_mode=1, confirm_count=2, require_ema_order=False, ema_fast=8,
    ema_slow=20, sar_step=0.3, sar_max=0.3, f1_trail_pips=100,
    f2_trail_pips=100, f3_trail_pips=100, ac_modulate=True
per-TF init_sl_range_k: M1=6.0, M2=3.0, M5=6.0, M15=2.5.

STACK SHAPES (each layered on the skeleton):
    S1 = skeleton + reentry_enable=True, reentry_max=2           (V-13 lever)
    S2 = skeleton + sar_adaptive=True, sar_fast=(0.3,0.3),
         sar_slow=(0.005,0.05), vol_regime_window=200            (V-15 lever)
    S3 = skeleton + BOTH S1 and S2 params together

AC FACTORS: ac_modulate_factor in {0.10, 0.01} (0.01 = V-06d improvement,
0.10 = prior reference).

GRID: 3 stacks x 2 factors x 4 TFs (M1, M2, M5, M15) = 24 sims.

XAUUSD, window 2026-06-08 -> 2026-07-07, BID bars + 0.5 spread at fill.
Reuses (does NOT modify) gen_variant_batch1.py's load/fill/metrics/ingest
machinery via the same importlib pattern batches 2-6 used.

Only the overall BEST-NET stack per TF is ingested into data/research.db,
as sim-report-emasar-ss-<tf>, idempotent delete-before-insert.

Run directly: `python scripts/report/gen_variant_batch7.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

# Reuse batch1's loader/filler/metrics/ingest machinery directly (same
# importlib pattern batch2-batch6 used).
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
# Champion skeleton, per TF.
# ---------------------------------------------------------------------------
V01B_BEST_K = {"M1": 6.0, "M2": 3.0, "M5": 6.0, "M15": 2.5}


def skeleton_kwargs(tf: str) -> dict[str, Any]:
    return {
        **V09_PARAMS,
        "init_sl_range_k": V01B_BEST_K[tf],
        "ac_modulate": True,
    }


# ---------------------------------------------------------------------------
# Stack-shape lever params.
# ---------------------------------------------------------------------------
S1_LEVER: dict[str, Any] = dict(reentry_enable=True, reentry_max=2)
S2_LEVER: dict[str, Any] = dict(
    sar_adaptive=True, sar_fast=(0.3, 0.3), sar_slow=(0.005, 0.05),
    vol_regime_window=200,
)

STACK_SHAPES: dict[str, dict[str, Any]] = {
    "S1": dict(S1_LEVER),
    "S2": dict(S2_LEVER),
    "S3": {**S1_LEVER, **S2_LEVER},
}

AC_FACTOR_GRID = (0.10, 0.01)

# ---------------------------------------------------------------------------
# Baselines to beat (standing program bests per TF) and single-lever /
# no-lever base nets for the interaction analysis (V-06c/d).
# ---------------------------------------------------------------------------
STANDING_BEST = {
    "M1": {"label": "V-06d f=0.01", "net": -12583.8},
    "M2": {"label": "V-06d f=0.01", "net": 31903.8},
    "M5": {"label": "V-06d f=0.01", "net": 46269.3},
    "M15": {"label": "V-13 rmax2 (f=0.25)", "net": 43027.8},
}

# Single-lever reference nets at factor=0.25 (V-13 / V-15), where they exist.
SINGLE_LEVER_F025 = {
    "V13": {"M2": 30174.6, "M5": 46264.8, "M15": 43027.8},
    "V15": {"M2": 31181.4, "M5": 42425.1, "M15": 36639.9},
}

# Base (no-lever, V-06c/d) nets per factor, for additivity analysis.
BASE_NET_BY_FACTOR = {
    0.10: {"M1": -14922.0, "M2": 30777.9, "M5": 45815.7, "M15": 41126.7},
    0.01: {"M1": -12583.8, "M2": 31903.8, "M5": 46269.3, "M15": 41264.4},
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None,
                         help="optional path to dump the full raw results as JSON")
    args = parser.parse_args()

    registry = ResearchRegistry(DB_PATH)
    all_results: dict[str, Any] = {}

    for tf in TFS:
        base_kwargs = skeleton_kwargs(tf)
        tf_grid: list[dict[str, Any]] = []
        best_net = None
        best_cell = None
        best_kwargs = None
        best_trades = None

        for shape_name, lever_kwargs in STACK_SHAPES.items():
            for factor in AC_FACTOR_GRID:
                kwargs = {**base_kwargs, **lever_kwargs, "ac_modulate_factor": factor}
                trades = run_variant(tf, kwargs)
                m = compute_metrics(trades)
                cell = {"shape": shape_name, "factor": factor, **m}
                tf_grid.append(cell)
                print(f"[SS] {tf} {shape_name} factor={factor}: trades={m['trades']} "
                      f"net={m['net']} pf={m['pf']} wr={m['wr']} maxdd={m['maxdd']}")
                if best_net is None or m["net"] > best_net:
                    best_net = m["net"]
                    best_cell = cell
                    best_kwargs = kwargs
                    best_trades = trades

        factor_tag = str(best_cell["factor"]).replace(".", "p")
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-ss-{tf.lower()}",
            variant_id=f"EMS_XAU_SS_{tf}_c1_{best_cell['shape']}_f{factor_tag}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**best_kwargs,
                                  "variant": f"Super-stack {best_cell['shape']} "
                                             f"factor={best_cell['factor']} (best of 6 stack cells)"},
            trades_all=best_trades,
            display_name=f"EMASAR super-stack {best_cell['shape']} factor={best_cell['factor']} {tf}",
        )

        standing = STANDING_BEST[tf]
        beats_standing = r["net"] > standing["net"]
        delta_vs_standing = round(r["net"] - standing["net"], 2)
        pct_vs_standing = (round(100.0 * delta_vs_standing / abs(standing["net"]), 2)
                            if standing["net"] != 0 else None)

        all_results[tf] = {
            "grid": tf_grid,
            "best_shape": best_cell["shape"], "best_factor": best_cell["factor"],
            "ingested": r,
            "standing_best": standing,
            "beats_standing_best": beats_standing,
            "delta_vs_standing": delta_vs_standing,
            "pct_vs_standing": pct_vs_standing,
        }
        print(f"[SS] {tf}: BEST shape={best_cell['shape']} factor={best_cell['factor']} "
              f"net={r['net']} (standing best={standing['label']} net={standing['net']}) "
              f"beats_standing={beats_standing} ingested={r['run_id']}")

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        with args.report_json.open("w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nRaw results JSON written to {args.report_json}")

    print("\n==== DONE ====")


if __name__ == "__main__":
    main()
