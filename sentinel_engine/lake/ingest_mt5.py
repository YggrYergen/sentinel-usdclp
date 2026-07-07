"""
sentinel_engine.lake.ingest_mt5 — MT5 OHLC CSV export -> Parquet lake (P2, Task 2.5).

Input format: the SAME CSV shape as the real MT5 exports already committed
under `tests/golden/fixtures/csv/<symbol>/<timeframe_minutes>.csv`:

    time,open,high,low,close,volume
    2026-01-01 00:00:00+00:00,2400.0,2407.6,2396.7,2404.3,926
    ...

(header `time` as the first column, ISO-8601 timestamps, tz-offset included).
This ingester is validated directly against those real MT5 fixtures — see
`tests/lake/test_ingest_mt5.py`.

READ-ONLY: this module only reads CSV files from disk; it never talks to a
live MT5 terminal and never places/modifies orders.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sentinel_engine.lake.manifest import write_manifest
from sentinel_engine.lake.store import BAR_COLUMNS, write_bars


class Mt5CsvFormatError(ValueError):
    """Raised when an input CSV does not match the expected MT5 export shape."""


def read_mt5_csv(csv_path: Path) -> pd.DataFrame:
    """Parse an MT5 OHLC CSV export into a lake-ready frame (DatetimeIndex
    named 'time', tz-aware UTC, columns open/high/low/close/volume)."""
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, encoding="utf-8")
    if df.columns[0] != "time":
        raise Mt5CsvFormatError(
            f"{csv_path}: expected first column 'time', got {df.columns[0]!r}"
        )
    missing = [c for c in BAR_COLUMNS if c not in df.columns]
    if missing:
        raise Mt5CsvFormatError(f"{csv_path}: missing columns {missing}")

    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    return df[BAR_COLUMNS]


def ingest_mt5_csv(csv_path: Path, symbol: str, timeframe_minutes: int,
                    lake_root: Path, update_manifest: bool = True) -> Path:
    """Read an MT5 OHLC CSV export and write it into the Parquet lake at
    `lake_root`, keyed by (symbol, timeframe_minutes). Rebuilds manifest.json
    afterwards unless `update_manifest=False` (useful for batch ingestion)."""
    df = read_mt5_csv(csv_path)
    path = write_bars(lake_root, symbol, timeframe_minutes, df)
    if update_manifest:
        write_manifest(lake_root)
    return path
