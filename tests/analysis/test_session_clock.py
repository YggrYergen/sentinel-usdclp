"""Tests for the shared session-reopen detector (scripts/analysis/monday_audit/
session_clock.py). Pure-logic tests plus one real-data invariant."""
from __future__ import annotations

import datetime as dt

import pytest

from scripts.analysis.monday_audit.session_clock import (
    market_reopens, minutes_since_reopen)


def test_the_first_bar_always_opens_a_session():
    t = dt.datetime(2026, 1, 1, 20, 0)
    assert market_reopens([t]) == [t]


def test_an_empty_stream_has_no_reopens():
    assert market_reopens([]) == []


def test_a_gap_at_the_threshold_counts_as_a_reopen():
    # >= gap_minutes, not >. The daily break is 1:15, comfortably over 60, but
    # the boundary must be pinned so nobody "fixes" it to > later.
    base = dt.datetime(2026, 1, 5, 12, 0)
    times = [base, base + dt.timedelta(minutes=60)]
    assert market_reopens(times, gap_minutes=60) == times


def test_a_gap_below_the_threshold_does_not():
    base = dt.datetime(2026, 1, 5, 12, 0)
    times = [base, base + dt.timedelta(minutes=45)]
    assert market_reopens(times, gap_minutes=60) == [base]


def test_the_input_need_not_be_sorted():
    a = dt.datetime(2026, 1, 5, 12, 0)
    b = dt.datetime(2026, 1, 5, 12, 15)
    c = dt.datetime(2026, 1, 5, 20, 0)
    assert market_reopens([c, a, b]) == [a, c]


def test_minutes_since_reopen_measures_from_the_most_recent_one():
    r = [dt.datetime(2026, 1, 5, 12, 0), dt.datetime(2026, 1, 5, 20, 0)]
    assert minutes_since_reopen(dt.datetime(2026, 1, 5, 20, 45), r) == 45.0
    assert minutes_since_reopen(dt.datetime(2026, 1, 5, 12, 30), r) == 30.0


def test_minutes_since_reopen_is_none_before_the_first_reopen():
    r = [dt.datetime(2026, 1, 5, 12, 0)]
    assert minutes_since_reopen(dt.datetime(2026, 1, 5, 11, 0), r) is None


def test_a_reopen_itself_is_zero_minutes_in():
    r = [dt.datetime(2026, 1, 5, 12, 0)]
    assert minutes_since_reopen(r[0], r) == 0.0


# --------------------------- real-data invariant ---------------------------
def test_the_real_bar_stream_yields_the_measured_session_count():
    """Pins the substrate: 145 reopens, and the weekly ones land on a Sunday.

    If this ever fails, the bar parquet was re-extracted or the clock
    convention moved -- investigate before touching any B1 number."""
    pd = pytest.importorskip("pandas")
    from scripts.analysis.monday_audit.session_clock import (
        BARS_PATH, load_bar_times)
    if not BARS_PATH.exists():
        pytest.skip("bar substrate not present on this machine")
    del pd
    reopens = market_reopens(load_bar_times())
    assert len(reopens) == 145
    # The weekend break is the long one; every reopen after >= 12h is a Sunday.
    bars = sorted(load_bar_times())
    prev = {b: a for a, b in zip(bars, bars[1:])}
    weekly = [r for r in reopens
              if r in prev and (r - prev[r]) >= dt.timedelta(hours=12)]
    assert weekly, "the 7-month substrate must contain weekend breaks"
    assert {r.weekday() for r in weekly} == {6}, "weekly reopens must be Sundays"
