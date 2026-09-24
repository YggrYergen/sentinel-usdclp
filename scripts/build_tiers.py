"""scripts/build_tiers.py — CLI entrypoint: build lake TF tiers (M1..D) for one
or more symbols, writing `data/lake/<SYMBOL>/<TF>/<YYYY-MM>.parquet` and
updating `data/lake/manifest.json` (Wave A, lane C).

Usage (PowerShell or bash):
    python scripts/build_tiers.py --symbol EURUSD
    python scripts/build_tiers.py --symbol EURUSD --symbol XAUUSD --lake-root data/lake
"""
from __future__ import annotations

import argparse
from pathlib import Path

from sentinel_engine.lake.tiers import build_tiers

DEFAULT_LAKE = Path("data/lake")


def _main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol", action="append", required=True,
                     help="Symbol to build tiers for (repeatable).")
    ap.add_argument("--lake-root", type=Path, default=DEFAULT_LAKE,
                     help=f"Lake root directory (default: {DEFAULT_LAKE}).")
    args = ap.parse_args()

    for symbol in args.symbol:
        report = build_tiers(symbol, args.lake_root)
        for tf_name, entry in sorted(report.tiers.items()):
            print(f"{symbol} {tf_name}: rows={entry['rows']} "
                  f"first={entry['first']} last={entry['last']} "
                  f"sha={entry['content_sha'][:12]}")


if __name__ == "__main__":
    _main()
