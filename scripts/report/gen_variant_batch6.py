"""scripts/report/gen_variant_batch6.py -- Batch 6 (extension) of the EMASAR
variant research program: V-06d, an `ac_modulate_factor` sweep BELOW 0.10,
continuing the V-06c knee sweep {0.10, 0.15, 0.20} (batch 5) downward into
{0.01, 0.03, 0.05, 0.07, 0.09}.

ZERO new engine code: `ac_modulate_factor` already exists on
`sentinel_engine.strategies.emasar_variant.simular_variant`.

CHAMPION stack (fixed for every run, all TFs):
    confirm_mode=1, confirm_count=2, require_ema_order=False, ema_fast=8,
    ema_slow=20, sar_step=0.3, sar_max=0.3, f1_trail_pips=100,
    f2_trail_pips=100, f3_trail_pips=100, ac_modulate=True
per-TF init_sl_range_k: M1=6.0, M2=3.0, M5=6.0, M15=2.5.

Grid: ac_modulate_factor in {0.01, 0.03, 0.05, 0.07, 0.09} x TF in
{M1, M2, M5, M15} = 20 sims. Reference (factor=0.10, batch 5's V-06c
winner): M1 -14,922.0 (PF 0.80) * M2 +30,777.9 (PF 2.00, WR 46.0,
DD 1,854.9) * M5 +45,815.7 (PF 7.34, WR 65.8, DD 209.7) * M15 +41,126.7
(PF 31.66, WR 79.8, DD 150.3).

XAUUSD, window 2026-06-08 -> 2026-07-07, BID bars + 0.5 spread at fill,
legal-range stop. Reuses (does NOT modify) gen_variant_batch1.py's
load/fill/metrics/ingest machinery via the same importlib pattern batches
2-5 used.

Only the BEST-NET factor per TF is ingested into data/research.db, as
sim-report-emasar-v06d-<tf>, idempotent delete-before-insert.

Run directly: `python scripts/report/gen_variant_batch6.py`.
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
# importlib pattern batch2-batch5 used).
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
# Champion config, per TF.
# ---------------------------------------------------------------------------
V01B_BEST_K = {"M1": 6.0, "M2": 3.0, "M5": 6.0, "M15": 2.5}


def champion_kwargs(tf: str) -> dict[str, Any]:
    return {
        **V09_PARAMS,
        "init_sl_range_k": V01B_BEST_K[tf],
        "ac_modulate": True,
    }


# Batch 5's V-06c reference (factor=0.10) nets, for the knee comparison.
REF_FACTOR = 0.10
REF_NET = {"M1": -14922.0, "M2": 30777.9, "M5": 45815.7, "M15": 41126.7}

# ---------------------------------------------------------------------------
# V-06d: ac_modulate_factor sweep BELOW 0.10.
# ---------------------------------------------------------------------------
V06D_FACTOR_GRID = (0.01, 0.03, 0.05, 0.07, 0.09)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None,
                         help="optional path to dump the full raw results as JSON")
    args = parser.parse_args()

    registry = ResearchRegistry(DB_PATH)
    all_results: dict[str, Any] = {}

    for tf in TFS:
        base_kwargs = champion_kwargs(tf)
        sweep_metrics: list[dict[str, Any]] = []
        best_net = None
        best_factor = None
        best_kwargs = None
        best_trades = None
        for factor in V06D_FACTOR_GRID:
            kwargs = {**base_kwargs, "ac_modulate_factor": factor}
            trades = run_variant(tf, kwargs)
            m = compute_metrics(trades)
            sweep_metrics.append({"factor": factor, **m})
            print(f"[V-06d] {tf} factor={factor}: trades={m['trades']} net={m['net']} "
                  f"pf={m['pf']} wr={m['wr']} maxdd={m['maxdd']}")
            if best_net is None or m["net"] > best_net:
                best_net = m["net"]
                best_factor = factor
                best_kwargs = kwargs
                best_trades = trades

        factor_tag = str(best_factor).replace(".", "p")
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v06d-{tf.lower()}",
            variant_id=f"EMS_XAU_V06d_{tf}_c1_f{factor_tag}_champion",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**best_kwargs,
                                  "variant": f"V-06d ac_modulate_factor sub-0.10 sweep on champion, "
                                             f"chosen factor={best_factor}"},
            trades_all=best_trades,
            display_name=f"EMASAR V-06d ac_modulate_factor sub-0.10 sweep, best factor={best_factor} "
                          f"(champion) {tf}",
        )
        all_results[tf] = {"sweep": sweep_metrics, "best_factor": best_factor,
                            "ref_factor": REF_FACTOR, "ref_net": REF_NET[tf], "ingested": r}
        print(f"[V-06d] {tf}: BEST factor={best_factor} net={r['net']} "
              f"(reference factor=0.10 net={REF_NET[tf]}) ingested={r['run_id']}")

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        with args.report_json.open("w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nRaw results JSON written to {args.report_json}")

    print("\n==== DONE ====")


if __name__ == "__main__":
    main()
