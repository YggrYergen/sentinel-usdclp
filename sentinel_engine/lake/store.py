"""
sentinel_engine.lake.store — low-level Parquet read/write for OHLCV bars.

Storage layout (a "lake root" is just a directory):
    <lake_root>/<symbol>/<timeframe_minutes>.parquet

Every bar frame written/read here has the SAME shape as
`tests/golden/fake_feed.FakeFeed._load`'s in-memory frames: a
`DatetimeIndex` named "time" (tz-aware, UTC) and columns
`open, high, low, close, volume`, sorted ascending, de-duplicated on
the index. This lets `HistoricalFeed` (feed_historical.py) and the
ingesters share one on-disk format.

Uses pyarrow + pandas only (duckdb is NOT installed / NOT used).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BAR_COLUMNS = ["open", "high", "low", "close", "volume"]


def _bar_path(lake_root: Path, symbol: str, timeframe_minutes: int) -> Path:
    return Path(lake_root) / symbol / f"{int(timeframe_minutes)}.parquet"


def write_bars(lake_root: Path, symbol: str, timeframe_minutes: int,
                df: pd.DataFrame) -> Path:
    """Write an OHLCV frame to the lake, merging with any existing data for
    the same (symbol, timeframe) — new rows overwrite existing rows at the
    same timestamp, the result is sorted and de-duplicated on the index.

    `df` must have a DatetimeIndex and the `BAR_COLUMNS` columns (extra
    columns are dropped).
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("write_bars: df must have a DatetimeIndex")
    missing = [c for c in BAR_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"write_bars: df missing columns {missing}")

    out = df[BAR_COLUMNS].copy()
    out.index = out.index.tz_convert("UTC") if out.index.tz is not None else out.index.tz_localize("UTC")
    out.index.name = "time"

    path = _bar_path(lake_root, symbol, timeframe_minutes)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, out])
    else:
        combined = out

    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    combined.to_parquet(path, engine="pyarrow")
    return path


def read_bars(lake_root: Path, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
    """Read the OHLCV frame for (symbol, timeframe) from the lake. Returns
    an empty frame (with the right columns/index name) if no data exists."""
    path = _bar_path(lake_root, symbol, timeframe_minutes)
    if not path.exists():
        empty = pd.DataFrame(columns=BAR_COLUMNS)
        empty.index = pd.DatetimeIndex([], tz="UTC", name="time")
        return empty
    df = pd.read_parquet(path)
    df.index.name = "time"
    return df.sort_index()


def list_lake_entries(lake_root: Path) -> list[tuple[str, int]]:
    """Enumerate every (symbol, timeframe_minutes) pair stored in a lake root."""
    root = Path(lake_root)
    if not root.exists():
        return []
    entries: list[tuple[str, int]] = []
    for symbol_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for pq in sorted(symbol_dir.glob("*.parquet")):
            try:
                tf = int(pq.stem)
            except ValueError:
                continue
            entries.append((symbol_dir.name, tf))
    return entries
