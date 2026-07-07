"""P2 Task 2.7 — TimelineAligner: aligned point-in-time cursors across
symbols/timeframes with different bar cadences."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from sentinel_engine.timeline import TimelineAligner

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_alignment_across_two_different_cadences():
    # A: 5-min bars over 20 minutes -> 5 bars (0,5,10,15,20)
    a_idx = [START + timedelta(minutes=5 * i) for i in range(5)]
    # B: 15-min bars over 20 minutes -> 2 bars (0,15) -- won't have a bar at 20
    b_idx = [START + timedelta(minutes=15 * i) for i in range(2)]

    aligner = TimelineAligner({"A@5": a_idx, "B@15": b_idx})
    events = aligner.events()

    ts_list = [e.ts for e in events]
    assert ts_list == sorted(ts_list)
    # distinct timestamps: 0,5,10,15,20 -> 5 events
    assert len(events) == 5

    by_ts = {e.ts: e.updated for e in events}
    assert by_ts[START] == ("A@5", "B@15")  # both start together
    assert by_ts[START + timedelta(minutes=5)] == ("A@5",)
    assert by_ts[START + timedelta(minutes=10)] == ("A@5",)
    assert by_ts[START + timedelta(minutes=15)] == ("A@5", "B@15")
    assert by_ts[START + timedelta(minutes=20)] == ("A@5",)


def test_accepts_dataframe_index_directly():
    idx = pd.DatetimeIndex([START, START + timedelta(minutes=1)])
    df = pd.DataFrame({"close": [1.0, 2.0]}, index=idx)
    aligner = TimelineAligner({"X": df})
    events = aligner.events()
    assert len(events) == 2
    assert events[0].updated == ("X",)


def test_empty_feeds_yields_no_events():
    assert TimelineAligner({}).events() == []


def test_unsorted_input_series_is_sorted():
    unsorted = [START + timedelta(minutes=10), START, START + timedelta(minutes=5)]
    aligner = TimelineAligner({"A": unsorted})
    events = aligner.events()
    assert [e.ts for e in events] == [START, START + timedelta(minutes=5), START + timedelta(minutes=10)]
