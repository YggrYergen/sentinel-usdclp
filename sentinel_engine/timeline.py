"""
sentinel_engine.timeline — TimelineAligner(feeds).events(): aligned
point-in-time cursors across symbols/timeframes with different bar cadences
(P2, Task 2.7).

Consumes named time series (typically a `DatetimeIndex` per (symbol, tf)
pulled from the lake) and yields, in ascending order, one event per DISTINCT
timestamp present in ANY of the series, annotated with which named series
were updated ("closed a bar") at that exact instant. This is the point-in-
time cursor sequence a replayer drives `HistoricalFeed(lake, as_of=event.ts)`
with — every symbol/TF advances on its own cadence, but the walk-forward
sees one unified, strictly-increasing timeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping

import pandas as pd


@dataclass(frozen=True)
class TimelineEvent:
    ts: datetime
    updated: tuple[str, ...] = field(default_factory=tuple)


class TimelineAligner:
    """Aligns multiple named timestamp series into one merged, ascending
    point-in-time cursor sequence.

    `feeds` maps a series name (e.g. "XAUUSD@15") to EITHER a
    `pandas.DatetimeIndex`/list of timestamps, or a `pandas.DataFrame` whose
    index is the timestamp series (only the index is used — no leakage risk
    since nothing is read from the data itself).
    """

    def __init__(self, feeds: Mapping[str, Iterable | pd.DataFrame]):
        self._series: dict[str, pd.DatetimeIndex] = {}
        for name, source in feeds.items():
            if isinstance(source, pd.DataFrame):
                idx = pd.DatetimeIndex(source.index)
            else:
                idx = pd.DatetimeIndex(source)
            self._series[name] = idx.sort_values()

    def events(self) -> list[TimelineEvent]:
        """Return the merged, ascending list of `TimelineEvent`s. Each
        distinct timestamp across all series appears exactly once, tagged
        with every series name that has a bar at that exact timestamp."""
        if not self._series:
            return []

        rows: list[tuple[pd.Timestamp, str]] = []
        for name, idx in self._series.items():
            for ts in idx:
                rows.append((ts, name))

        if not rows:
            return []

        rows.sort(key=lambda r: r[0])

        events: list[TimelineEvent] = []
        cur_ts = rows[0][0]
        cur_names: list[str] = []
        for ts, name in rows:
            if ts != cur_ts:
                events.append(TimelineEvent(ts=cur_ts.to_pydatetime(), updated=tuple(cur_names)))
                cur_ts = ts
                cur_names = []
            cur_names.append(name)
        events.append(TimelineEvent(ts=cur_ts.to_pydatetime(), updated=tuple(cur_names)))
        return events
