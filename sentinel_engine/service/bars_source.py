"""sentinel_engine.service.bars_source — CT-2 windowed + LOD bar reader (A3a).

Reads pre-built lake tiers (`sentinel_engine.lake.tiers.build_tiers` output:
`<lake_root>/<SYMBOL>/<TF>/<YYYY-MM>.parquet`, columns `t,o,h,l,c,v`) via
pyarrow predicate pushdown — never loads a whole month into pandas. Also
implements the LOD tier-selection ladder (M1->M2->M5->M15->H1->D): if the
requested timeframe would need to return more than `max_points` bars over
the requested [from, to] window, step up to the next coarser tier until the
estimated bar count fits.

This module is intentionally pandas-free on the read path (pyarrow only),
per the A3a spec ("NADA de pandas whole-file").
"""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pyarrow.compute as pc
import pyarrow.parquet as pq

from sentinel_engine.lake.tiers import TF_SECONDS

# LOD ladder, coarsest-last. Must match sentinel_engine.lake.tiers.TF_SECONDS.
TIER_LADDER: list[str] = ["M1", "M2", "M5", "M15", "H1", "D"]

OUT_COLUMNS = ["t", "o", "h", "l", "c", "v"]


class Bar(TypedDict):
    t: int
    o: float
    h: float
    l: float
    c: float
    v: int


class BarsSourceError(ValueError):
    """Raised for a bad tf name (unknown to the LOD ladder/lake tiers)."""


def tf_seconds(tf: str) -> int:
    try:
        return TF_SECONDS[tf]
    except KeyError as exc:
        raise BarsSourceError(f"unknown tf: {tf}") from exc


def next_coarser_tf(tf: str) -> str | None:
    """Return the next coarser tier on the ladder, or None if `tf` is
    already the coarsest (or not on the ladder)."""
    try:
        idx = TIER_LADDER.index(tf)
    except ValueError:
        return None
    if idx + 1 >= len(TIER_LADDER):
        return None
    return TIER_LADDER[idx + 1]


def choose_served_tf(tf_requested: str, from_: int, to_: int, max_points: int) -> str:
    """Apply the LOD ladder: while the estimated bar count at the current
    tier exceeds `max_points`, step up to the next coarser tier. Returns the
    tier name that should actually be served."""
    tf = tf_requested
    span = max(0, to_ - from_)
    while True:
        seconds = tf_seconds(tf)
        estimate = span / seconds if seconds > 0 else 0
        if estimate <= max_points:
            return tf
        nxt = next_coarser_tf(tf)
        if nxt is None:
            return tf  # already coarsest; nothing more to do
        tf = nxt


def _months_spanning(from_: int, to_: int) -> list[str]:
    """Return the sorted list of "YYYY-MM" month keys that intersect
    [from_, to_] (inclusive), in UTC calendar terms."""
    import datetime as _dt

    start = _dt.datetime.fromtimestamp(from_, tz=_dt.timezone.utc)
    end = _dt.datetime.fromtimestamp(to_, tz=_dt.timezone.utc)

    months: list[str] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def read_window(symbol: str, tf: str, from_: int, to_: int, lake_root: Path) -> list[Bar]:
    """Read closed bars for `symbol`/`tf` in `[from_, to_]` (epoch seconds,
    inclusive) from the pre-built lake tier parquet files, using pyarrow
    predicate pushdown (no whole-file pandas load). Returns a list of dicts,
    strictly ascending by `t`, with `t` unique.
    """
    lake_root = Path(lake_root)
    tf_seconds(tf)  # validate tf is a known tier name; raises BarsSourceError
    tier_dir = lake_root / symbol / tf
    if not tier_dir.is_dir():
        return []

    filters = [("t", ">=", int(from_)), ("t", "<=", int(to_))]

    rows: list[Bar] = []
    for month_key in _months_spanning(int(from_), int(to_)):
        path = tier_dir / f"{month_key}.parquet"
        if not path.exists():
            continue
        table = pq.read_table(path, filters=filters, columns=OUT_COLUMNS)
        if table.num_rows == 0:
            continue
        table = table.sort_by("t")
        cols = {name: table.column(name) for name in OUT_COLUMNS}
        for i in range(table.num_rows):
            rows.append({
                "t": cols["t"][i].as_py(),
                "o": cols["o"][i].as_py(),
                "h": cols["h"][i].as_py(),
                "l": cols["l"][i].as_py(),
                "c": cols["c"][i].as_py(),
                "v": cols["v"][i].as_py(),
            })

    rows.sort(key=lambda b: b["t"])

    # De-duplicate by t (defensive: monthly files are disjoint by
    # construction, but guard against any overlap so `t` stays unique).
    deduped: list[Bar] = []
    seen: set[int] = set()
    for b in rows:
        if b["t"] in seen:
            continue
        seen.add(b["t"])
        deduped.append(b)

    return deduped
