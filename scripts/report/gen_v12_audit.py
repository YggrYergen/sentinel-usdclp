"""scripts/report/gen_v12_audit.py -- V-12 look-ahead audit (2026-07-13):
causal re-simulation (TEST 5 of the forensic audit).

Runs the V-12 champion-stack config (per-TF init_sl_range_k, ac_modulate,
factor=0.5, confirm_count=2, sar_step/sar_max=0.3, require_ema_order=False
-- the EXACT params `sim-report-emasar-v12-<tf>` used, read back from
data/research.db's `metrics_json.params`, see
`scripts/report/gen_variant_batch4.py`'s V-12 section) with TWO additive,
test-pinned engine extensions to `entry_timing`:

  (a) entry_timing=2 ("causal next-open"): gates evaluated on the signal
      bar's CLOSE exactly like entry_timing=0, but the fill only executes at
      the NEXT bar's OPEN -- the earliest price a strictly-causal engine
      could act on a close-confirmed signal. Ingested as
      sim-report-emasar-v12a-<tf>.
  (b) entry_timing=3 ("adverse-fill worst-case bound"): same signal bar/side
      as entry_timing=1 (G3 replaced by the intrabar touch test), but filled
      at the WORST price of the signal bar for the side (high for long, low
      for short) -- a pessimistic bound on how bad a same-bar intrabar fill
      could realistically be. Ingested as sim-report-emasar-v12w-<tf>.

Reuses (does NOT modify) gen_variant_batch1.py's load/fill/persistence
conventions via the SAME importlib pattern batch2/3/4 used, and
gen_variant_batch4.py's champion-stack per-TF params (read back from the
already-ingested sim-report-emasar-v12-<tf> rows, so this script cannot
silently drift from what V-12 actually used).

Run this script directly: `python scripts/report/gen_v12_audit.py`.
Idempotent: re-running replaces the same run_ids (delete-before-insert).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

import importlib.util as _ilu  # noqa: E402

_b1_spec = _ilu.spec_from_file_location(
    "gen_variant_batch1", ROOT / "scripts" / "report" / "gen_variant_batch1.py"
)
_b1 = _ilu.module_from_spec(_b1_spec)
_b1_spec.loader.exec_module(_b1)  # type: ignore[union-attr]

DB_PATH = ROOT / "data" / "research.db"
TFS = _b1.TFS
run_variant = _b1.run_variant
compute_metrics = _b1.compute_metrics
ingest_run = _b1.ingest_run


def _v12_params(tf: str) -> dict[str, Any]:
    """Reads back the EXACT params V-12's ingested run used for this TF from
    data/research.db (metrics_json.params), so this audit cannot drift from
    the config actually under audit. Strips the free-text 'variant' field."""
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT metrics_json FROM run WHERE run_id=?",
            (f"sim-report-emasar-v12-{tf.lower()}",),
        )
        row = cur.fetchone()
    finally:
        con.close()
    if row is None:
        raise RuntimeError(f"sim-report-emasar-v12-{tf.lower()} not found in {DB_PATH}; "
                            "run gen_variant_batch4.py first")
    params = dict(json.loads(row[0])["params"])
    params.pop("variant", None)
    return params


def main() -> None:
    registry = ResearchRegistry(str(DB_PATH))
    results: dict[str, Any] = {}

    for tf in TFS:
        v12_params = _v12_params(tf)
        champion_net = None  # informational only; verdict is computed in the report.

        # ---- (a) entry_timing=2: causal next-open ----
        causal_kwargs = {**v12_params, "entry_timing": 2}
        causal_trades = run_variant(tf, causal_kwargs)
        m_causal = compute_metrics(causal_trades)
        r_causal = ingest_run(
            registry, run_id=f"sim-report-emasar-v12a-{tf.lower()}",
            variant_id=f"EMS_XAU_V12a_{tf}_timing2_causal",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**causal_kwargs,
                                  "variant": "V-12a causal next-open re-simulation "
                                             "(look-ahead audit TEST 5a, 2026-07-13)"},
            trades_all=causal_trades,
            display_name=f"EMASAR V-12a causal next-open (audit) {tf}",
        )
        print(f"[V-12a] {tf}: net={r_causal['net']} trades={r_causal['trades']} "
              f"pf={r_causal['pf']} wr={r_causal['wr']}")

        # ---- (b) entry_timing=3: adverse-fill worst-case bound ----
        adverse_kwargs = {**v12_params, "entry_timing": 3}
        adverse_trades = run_variant(tf, adverse_kwargs)
        m_adverse = compute_metrics(adverse_trades)
        r_adverse = ingest_run(
            registry, run_id=f"sim-report-emasar-v12w-{tf.lower()}",
            variant_id=f"EMS_XAU_V12w_{tf}_timing3_adverse",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**adverse_kwargs,
                                  "variant": "V-12w adverse-fill worst-case bound "
                                             "(look-ahead audit TEST 5b, 2026-07-13)"},
            trades_all=adverse_trades,
            display_name=f"EMASAR V-12w adverse-fill worst-case (audit) {tf}",
        )
        print(f"[V-12w] {tf}: net={r_adverse['net']} trades={r_adverse['trades']} "
              f"pf={r_adverse['pf']} wr={r_adverse['wr']}")

        results[tf] = {"causal": r_causal, "adverse": r_adverse}

    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
