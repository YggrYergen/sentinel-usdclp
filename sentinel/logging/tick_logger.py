"""
TickLogger — native, append-batched tick logger for SENTINEL.

Writes real market ticks (bid/ask) observed from the live data feed to
dated Parquet files under ``<out_dir>/ticks/<symbol>/<YYYY-MM-DD>.parquet``.
Read-only: this module never places orders, it only records observed ticks
so P2's historical replayer can later be validated against real data.

Design notes
------------
- Ticks are buffered in memory and flushed in batches (every ``batch_size``
  ticks, and/or explicitly via ``flush()``/``close()``) to keep laptop I/O
  low — no per-tick file write.
- Parquet has no true in-place append. On each flush we group the buffered
  ticks by the date of their own ``ts`` (never wall-clock date), and for
  each affected date: read the existing dated file if present, concat with
  the new rows, and rewrite the file. This is correct across:
    * many ticks within a single run (repeated flushes append correctly),
    * process restarts (a new TickLogger instance reopening the same
      symbol+day file appends to, not clobbers, prior rows), and
    * ticks that span a date boundary (each tick's own ts picks its file).
- All paths use pathlib.Path (Windows 10/11 safe), parent directories are
  created with mkdir(parents=True, exist_ok=True).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Union

import pandas as pd

COLUMNS = ["ts", "bid", "ask", "spread"]

TsLike = Union[datetime, int, float]


class TickLogger:
    """Append-batched Parquet tick logger for a single symbol.

    Usage:
        logger = TickLogger("USDCLP", out_dir)
        logger.on_tick(ts, bid, ask)
        ...
        logger.close()

    Or as a context manager:
        with TickLogger("USDCLP", out_dir) as logger:
            logger.on_tick(ts, bid, ask)
    """

    def __init__(self, symbol: str, out_dir: Union[str, Path], batch_size: int = 100):
        self.symbol = symbol
        self.out_dir = Path(out_dir)
        self.batch_size = batch_size
        self._buffer: list[dict] = []

    def on_tick(self, ts: TsLike, bid: float, ask: float) -> None:
        """Record one tick. May trigger a flush once batch_size is reached."""
        ts_dt = self._normalize_ts(ts)
        self._buffer.append(
            {"ts": ts_dt, "bid": bid, "ask": ask, "spread": ask - bid}
        )
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """Write all buffered ticks to their dated Parquet files, then clear the buffer."""
        if not self._buffer:
            return

        by_date: dict[date, list[dict]] = defaultdict(list)
        for row in self._buffer:
            by_date[row["ts"].date()].append(row)

        for tick_date, rows in by_date.items():
            self._write_rows(tick_date, rows)

        self._buffer.clear()

    def close(self) -> None:
        """Flush any remaining buffered ticks. Safe to call multiple times."""
        self.flush()

    def __enter__(self) -> "TickLogger":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -- internal helpers -------------------------------------------------

    @staticmethod
    def _normalize_ts(ts: TsLike) -> datetime:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return ts

    def _path_for(self, tick_date: date) -> Path:
        return self.out_dir / "ticks" / self.symbol / f"{tick_date.isoformat()}.parquet"

    def _write_rows(self, tick_date: date, rows: list[dict]) -> None:
        path = self._path_for(tick_date)
        path.parent.mkdir(parents=True, exist_ok=True)

        new_df = pd.DataFrame(rows, columns=COLUMNS)

        if path.exists():
            existing_df = pd.read_parquet(path)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        combined_df.to_parquet(path, index=False)
