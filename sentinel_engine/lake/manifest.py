"""
sentinel_engine.lake.manifest — coverage manifest (ranges + gap detection) for a lake root.

A manifest is a plain JSON-serializable dict:
    {
      "<symbol>": {
        "<timeframe_minutes>": {
          "start": "2026-01-01T00:00:00+00:00",
          "end":   "2026-01-05T00:00:00+00:00",
          "bar_count": 480,
          "gaps": [
            {"after": "...", "before": "...", "missing_bars": 3}
          ]
        }
      }
    }

Gap detection: for a timeframe of N minutes, consecutive bars are expected
`N` minutes apart. Any consecutive pair further apart than
`gap_tolerance_factor * N` minutes is reported as a gap, with the number of
whole bars that would have fit in between (best-effort integer estimate —
this deliberately does NOT try to model weekends/holidays; callers ingesting
FX data with normal market closures should widen `gap_tolerance_factor`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from sentinel_engine.lake.store import list_lake_entries, read_bars

MANIFEST_FILENAME = "manifest.json"

DEFAULT_GAP_TOLERANCE_FACTOR = 1.5


def _detect_gaps(index: pd.DatetimeIndex, timeframe_minutes: int,
                  gap_tolerance_factor: float) -> list[dict[str, Any]]:
    if len(index) < 2:
        return []
    expected = pd.Timedelta(minutes=timeframe_minutes)
    threshold = expected * gap_tolerance_factor
    gaps: list[dict[str, Any]] = []
    deltas = index.to_series().diff()
    for i in range(1, len(index)):
        delta = deltas.iloc[i]
        if delta > threshold:
            missing_bars = int(delta / expected) - 1
            gaps.append({
                "after": index[i - 1].isoformat(),
                "before": index[i].isoformat(),
                "missing_bars": missing_bars,
            })
    return gaps


def build_manifest(lake_root: Path,
                    gap_tolerance_factor: float = DEFAULT_GAP_TOLERANCE_FACTOR) -> dict:
    """Scan every (symbol, timeframe) parquet under `lake_root` and build a
    fresh coverage manifest. Does not read/merge any existing manifest.json —
    always a full rescan (cheap: it's just parquet index metadata + a diff)."""
    lake_root = Path(lake_root)
    manifest: dict[str, dict[str, Any]] = {}
    for symbol, tf in list_lake_entries(lake_root):
        df = read_bars(lake_root, symbol, tf)
        entry = manifest.setdefault(symbol, {})
        if df.empty:
            entry[str(tf)] = {"start": None, "end": None, "bar_count": 0, "gaps": []}
            continue
        entry[str(tf)] = {
            "start": df.index[0].isoformat(),
            "end": df.index[-1].isoformat(),
            "bar_count": int(len(df)),
            "gaps": _detect_gaps(df.index, tf, gap_tolerance_factor),
        }
    return manifest


def write_manifest(lake_root: Path,
                    gap_tolerance_factor: float = DEFAULT_GAP_TOLERANCE_FACTOR) -> Path:
    """Build and persist the manifest to `<lake_root>/manifest.json`. Returns the path."""
    lake_root = Path(lake_root)
    manifest = build_manifest(lake_root, gap_tolerance_factor)
    path = lake_root / MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    return path


def load_manifest(lake_root: Path) -> dict:
    """Load a previously-written manifest.json. Raises FileNotFoundError if absent."""
    path = Path(lake_root) / MANIFEST_FILENAME
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
