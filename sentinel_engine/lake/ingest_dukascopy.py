"""
sentinel_engine.lake.ingest_dukascopy — Dukascopy CSV export -> Parquet lake (P2, Task 2.4).

NEEDS REAL-SAMPLE VALIDATION (Dukascopy): no real Dukascopy historical-data
export exists in this repo. This adapter targets the well-documented format
of Dukascopy's free historical-data CSV download (Duka node / "Historical
Data Feed" export):

    Gmt time,Open,High,Low,Close,Volume
    01.01.2026 00:00:00.000,2400.000,2407.618,2396.757,2404.370,926.0

  - header `Gmt time,Open,High,Low,Close,Volume` (capitalized columns)
  - timestamp `DD.MM.YYYY HH:MM:SS.fff` (always GMT/UTC, no offset suffix)
  - decimal point, comma-separated

The test in `tests/lake/test_ingest_dukascopy.py` runs this adapter against
a FORMAT-ACCURATE synthetic fixture built to this spec
(`tests/lake/fixtures/dukascopy_sample.csv`). Flagged for validation against
a real downloaded sample before being trusted on live data.

READ-ONLY: only reads CSV files from disk.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sentinel_engine.lake.manifest import write_manifest
from sentinel_engine.lake.store import BAR_COLUMNS, write_bars

DUKASCOPY_TIME_FORMAT = "%d.%m.%Y %H:%M:%S.%f"
DUKASCOPY_COLUMNS = {
    "Gmt time": "time",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}


class DukascopyCsvFormatError(ValueError):
    """Raised when an input CSV does not match the expected Dukascopy export shape."""


def read_dukascopy_csv(csv_path: Path) -> pd.DataFrame:
    """Parse a Dukascopy historical-data CSV export into a lake-ready frame
    (DatetimeIndex named 'time', tz-aware UTC, columns open/high/low/close/volume)."""
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, encoding="utf-8")

    missing = [c for c in DUKASCOPY_COLUMNS if c not in df.columns]
    if missing:
        raise DukascopyCsvFormatError(f"{csv_path}: missing columns {missing}")

    df = df.rename(columns=DUKASCOPY_COLUMNS)
    try:
        df["time"] = pd.to_datetime(df["time"], format=DUKASCOPY_TIME_FORMAT, utc=True)
    except (ValueError, TypeError) as exc:
        raise DukascopyCsvFormatError(f"{csv_path}: unparseable timestamp column") from exc

    df = df.set_index("time").sort_index()
    return df[BAR_COLUMNS]


def ingest_dukascopy_csv(csv_path: Path, symbol: str, timeframe_minutes: int,
                          lake_root: Path, update_manifest: bool = True) -> Path:
    """Read a Dukascopy CSV export and write it into the Parquet lake at
    `lake_root`, keyed by (symbol, timeframe_minutes). Rebuilds manifest.json
    afterwards unless `update_manifest=False`."""
    df = read_dukascopy_csv(csv_path)
    path = write_bars(lake_root, symbol, timeframe_minutes, df)
    if update_manifest:
        write_manifest(lake_root)
    return path
