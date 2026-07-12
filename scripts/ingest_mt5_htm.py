"""scripts/ingest_mt5_htm.py — CLI entrypoint: MT5 Strategy-Tester `.htm` ->
certified V1 run in `research.db` (EMASAR V1 MT5-fidelity integration,
design spec docs/superpowers/specs/2026-07-10-emasar-v1-mt5-integration-design.md,
Component 7 / implementation phase 4).

Wires `sentinel_engine.research.ingest_mt5_deals.ingest_mt5_htm` to the
REAL lake (`sentinel_engine.service.bars.load_tf_frame`) and the real
`ResearchRegistry` (default `data/research.db`). READ-ONLY w.r.t. MT5/TOKATA:
only ever reads the `.htm` file and the lake's Parquet bars; never touches
`D:/WebDev/TOKATA/**` or any MT5 terminal.

Usage (PowerShell or bash):
    python scripts/ingest_mt5_htm.py --htm "D:\\WebDev\\TOKATA\\mt5\\reports\\TOKATA_EMS_XAU_V1_M5_c2_sar3m3_m1.htm" --variant-id EMS_XAU_V1_M5_c2_sar3m3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel_engine.research.ingest_mt5_deals import ingest_mt5_htm
from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.bars import load_tf_frame

DEFAULT_DB = Path("data/research.db")
DEFAULT_LAKE = Path("data/lake")


def _make_bars_lookup(lake_root: Path):
    def _lookup(symbol: str, tf: str, _desde, _hasta):
        try:
            return load_tf_frame(lake_root, symbol, tf)
        except Exception:
            import pandas as pd
            return pd.DataFrame()
    return _lookup


def _main() -> None:
    ap = argparse.ArgumentParser(
        description="Ingest an MT5 Strategy-Tester .htm report into a certified V1 run.",
    )
    ap.add_argument("--htm", required=True, help="path to the MT5 Strategy-Tester .htm report")
    ap.add_argument("--variant-id", required=True, help="variant_id to upsert/attach the run to")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="research.db path")
    ap.add_argument("--lake", default=str(DEFAULT_LAKE), help="lake root path")
    ap.add_argument("--run-id", default=None, help="explicit run_id (default: auto-generated)")
    args = ap.parse_args()

    registry = ResearchRegistry(Path(args.db))
    result = ingest_mt5_htm(
        Path(args.htm), registry,
        bars_lookup=_make_bars_lookup(Path(args.lake)),
        variant_id=args.variant_id,
        run_id=args.run_id,
    )
    print(f"run_id={result['run_id']} n_trades={result['n_trades']}")
    print(json.dumps(result["fidelity_report"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
