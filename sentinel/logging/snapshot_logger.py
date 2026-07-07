"""
SnapshotLogger — native, append-batched Parquet logger for SENTINEL scoring
snapshots.

Writes every computed composite-scoring snapshot (the dict returned by
``SentinelCore.calculate_composite()``) to dated Parquet files under
``<out_dir>/snapshots/<symbol>/<YYYY-MM-DD>.parquet`` so P2.8's historical
replayer can later be proven to reproduce the live snapshot at a given
time. Read-only: this module never places orders, it only records
already-computed scoring output.

Design notes
------------
- Mirrors ``sentinel.logging.tick_logger.TickLogger``'s batching/append
  strategy independently (kept un-shared so 0.6's tests/behavior are not
  put at risk): snapshots are buffered in memory and flushed in batches
  (every ``batch_size`` snapshots, and/or explicitly via
  ``flush()``/``close()``). Parquet has no true in-place append, so each
  flush groups buffered rows by (symbol, date-of-record-ts), reads the
  existing dated file if present, concatenates, and rewrites it. This is
  correct across many flushes within one run, across process restarts
  (a new SnapshotLogger reopening the same symbol+day file appends to,
  not clobbers, prior rows), and across a run that spans a date boundary.
- ``seq`` is a monotonically increasing integer assigned by the LOGGER
  per (symbol, day), starting at 0. On each flush, the starting seq for a
  given (symbol, day) group is computed as ``existing_max_seq + 1`` when
  the dated file already exists (whether from an earlier flush in this
  same run or from a prior process), else 0 — so restarts resume the
  counter instead of clobbering or restarting it.
- ``config_hash`` is provided by the caller at construction time (e.g.
  P1's InstrumentConfig hash) and merely persisted here as a string
  column; this module does not compute it.
- The row schema stores the key top-level scalars used for quick
  querying (``composite_score``, ``direction``, ``signal``) PLUS a
  ``snapshot_json`` column holding the COMPLETE snapshot dict serialized
  as canonical JSON (sorted keys, utf-8, ensure_ascii=False) so no scored
  field — including deeply nested ones like
  ``components.technical.details.tf_scores.*`` — is ever lost, and P2.8
  can reconstruct-and-compare the exact snapshot via
  ``json.loads(row.snapshot_json)``.
- The logger's own ``ts`` column is the record (log) time — i.e. when
  this row was logged, not necessarily anything inside the snapshot
  itself. Any wall-clock field the snapshot carries internally (e.g. a
  ``meta.timestamp`` from ``datetime.now()``) is preserved verbatim
  inside ``snapshot_json`` for full fidelity; it is NOT parsed into or
  conflated with the logger's own ``ts`` column, so P2.8's replay
  comparison is free to compare snapshot-internal fields on their own
  terms without the logger's record time polluting them.
- All paths use pathlib.Path (Windows 10/11 safe), parent directories are
  created with mkdir(parents=True, exist_ok=True).
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

COLUMNS = [
    "ts", "symbol", "seq", "config_hash",
    "composite_score", "direction", "signal", "snapshot_json",
]


def to_canonical_json(snapshot: dict) -> str:
    """Canonical JSON for a scoring snapshot: sorted keys, ensure_ascii=False.

    Kept local to this module (not imported from test code) per the task
    contract. Unlike the golden-master harness's cleaner, this does NOT
    round floats — the goal here is byte-for-byte fidelity so
    ``json.loads(snapshot_json) == original_dict`` for P2.8's replay
    comparison, not cross-run float-noise suppression.
    """
    return json.dumps(snapshot, sort_keys=True, ensure_ascii=False, default=str)


class SnapshotLogger:
    """Append-batched Parquet snapshot logger.

    Usage:
        logger = SnapshotLogger(out_dir, config_hash, symbol="USDCLP")
        logger.log(calculate_composite_result)
        ...
        logger.close()

    Or as a context manager:
        with SnapshotLogger(out_dir, config_hash, symbol="USDCLP") as logger:
            logger.log(result)
    """

    def __init__(
        self,
        out_dir: Union[str, Path],
        config_hash: str,
        symbol: Optional[str] = None,
        batch_size: int = 100,
    ):
        self.out_dir = Path(out_dir)
        self.config_hash = config_hash
        self.symbol = symbol
        self.batch_size = batch_size
        self._buffer: list[dict] = []

    def log(self, snapshot: dict) -> None:
        """Record one scored snapshot. May trigger a flush at batch_size."""
        row_symbol = snapshot.get("symbol") or self.symbol
        if not row_symbol:
            raise ValueError(
                "SnapshotLogger.log: no symbol — pass symbol= to the "
                "constructor or include 'symbol' in the snapshot dict"
            )
        record_ts = datetime.now(timezone.utc)
        self._buffer.append(
            {
                "ts": record_ts,
                "symbol": row_symbol,
                "config_hash": self.config_hash,
                "composite_score": snapshot.get("composite_score"),
                "direction": snapshot.get("direction"),
                "signal": snapshot.get("signal"),
                "snapshot_json": to_canonical_json(snapshot),
            }
        )
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """Write all buffered snapshots to their dated Parquet files, then clear the buffer."""
        if not self._buffer:
            return

        by_group: dict[tuple[str, date], list[dict]] = defaultdict(list)
        for row in self._buffer:
            by_group[(row["symbol"], row["ts"].date())].append(row)

        for (symbol, day), rows in by_group.items():
            self._write_rows(symbol, day, rows)

        self._buffer.clear()

    def close(self) -> None:
        """Flush any remaining buffered snapshots. Safe to call multiple times."""
        self.flush()

    def __enter__(self) -> "SnapshotLogger":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -- internal helpers -------------------------------------------------

    def _path_for(self, symbol: str, day: date) -> Path:
        return self.out_dir / "snapshots" / symbol / f"{day.isoformat()}.parquet"

    def _write_rows(self, symbol: str, day: date, rows: list[dict]) -> None:
        path = self._path_for(symbol, day)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing_df = pd.read_parquet(path)
            next_seq = int(existing_df["seq"].max()) + 1 if len(existing_df) else 0
        else:
            existing_df = None
            next_seq = 0

        for i, row in enumerate(rows):
            row["seq"] = next_seq + i

        new_df = pd.DataFrame(rows, columns=COLUMNS)

        if existing_df is not None:
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        combined_df.to_parquet(path, index=False)
