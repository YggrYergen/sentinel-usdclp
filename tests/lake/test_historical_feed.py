"""
P2 Task 2.6 — HistoricalFeed(lake, as_of): the 2-strikes leakage gate.

Builds a small synthetic lake with STRICTLY MONOTONIC INCREASING close
prices (price == minute offset), so any field that leaks a bar with
ts > as_of is trivially detectable: its value would exceed what's possible
from the as_of-bounded window.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from sentinel_engine.feed_historical import HistoricalFeed
from sentinel_engine.lake.store import write_bars

SYMBOL = "TESTSYM"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
N_BARS = 100  # minutes 0..99, close == minute offset (monotonic increasing)


def _build_lake(tmp_path):
    lake_root = tmp_path / "lake"
    idx = pd.DatetimeIndex([START + timedelta(minutes=i) for i in range(N_BARS)], name="time")
    df = pd.DataFrame({
        "open": range(N_BARS),
        "high": [i + 0.5 for i in range(N_BARS)],
        "low": [i - 0.5 for i in range(N_BARS)],
        "close": range(N_BARS),
        "volume": [10] * N_BARS,
    }, index=idx)
    write_bars(lake_root, SYMBOL, 1, df)
    # Also a 15-min timeframe derived from the same span (independent bars,
    # still strictly increasing close) so get_all_data has something to see.
    idx15 = pd.DatetimeIndex([START + timedelta(minutes=15 * i) for i in range(N_BARS // 15)], name="time")
    df15 = pd.DataFrame({
        "open": range(len(idx15)),
        "high": [i + 0.5 for i in range(len(idx15))],
        "low": [i - 0.5 for i in range(len(idx15))],
        "close": range(len(idx15)),
        "volume": [10] * len(idx15),
    }, index=idx15)
    write_bars(lake_root, SYMBOL, 15, df15)
    return lake_root


AS_OF = START + timedelta(minutes=50)  # bar index 50 is the last visible bar


def test_get_data_never_returns_future_bars(tmp_path):
    lake_root = _build_lake(tmp_path)
    feed = HistoricalFeed(lake_root, AS_OF, symbols={"target": SYMBOL})

    df = feed.get_data(SYMBOL, timeframe_minutes=1, bars=1000)
    assert (df.index <= pd.Timestamp(AS_OF)).all()
    assert df.index.max() == pd.Timestamp(AS_OF)
    assert len(df) == 51  # minutes 0..50 inclusive


def test_get_current_price_never_derived_from_future_bar(tmp_path):
    lake_root = _build_lake(tmp_path)
    feed = HistoricalFeed(lake_root, AS_OF, symbols={"target": SYMBOL})

    # Close price is == minute offset; nothing beyond offset 50 may ever
    # appear, no matter how many ticks we advance (wrap-around must stay
    # within the as_of-bounded window).
    for _ in range(200):
        tick = feed.get_current_price(SYMBOL)
        assert tick["bid"] <= 50.0001, f"leaked a future bar: bid={tick['bid']}"


def test_get_all_data_never_returns_future_bars(tmp_path):
    lake_root = _build_lake(tmp_path)
    feed = HistoricalFeed(lake_root, AS_OF, symbols={"target": SYMBOL})

    all_data = feed.get_all_data(timeframe_minutes=1, bars=1000)
    assert "target" in all_data
    assert (all_data["target"].index <= pd.Timestamp(AS_OF)).all()

    all_data_15 = feed.get_all_data(timeframe_minutes=15, bars=1000)
    assert (all_data_15["target"].index <= pd.Timestamp(AS_OF)).all()
    # bar index 3 (t=45min) is the last <=50min 15-min bar; index 4 (t=60min) must be absent
    assert all_data_15["target"]["close"].max() == 3


def test_now_returns_as_of_not_wallclock(tmp_path):
    lake_root = _build_lake(tmp_path)
    feed = HistoricalFeed(lake_root, AS_OF, symbols={"target": SYMBOL})
    assert feed.now() == AS_OF


def test_positions_is_always_empty(tmp_path):
    lake_root = _build_lake(tmp_path)
    feed = HistoricalFeed(lake_root, AS_OF, symbols={"target": SYMBOL})
    assert feed.positions() == []


def test_as_of_exactly_on_a_bar_boundary_includes_that_bar(tmp_path):
    lake_root = _build_lake(tmp_path)
    exact = START + timedelta(minutes=10)
    feed = HistoricalFeed(lake_root, exact, symbols={"target": SYMBOL})
    df = feed.get_data(SYMBOL, timeframe_minutes=1, bars=1000)
    assert df.index.max() == pd.Timestamp(exact)
    assert df["close"].max() == 10


def test_as_of_before_first_bar_returns_empty(tmp_path):
    lake_root = _build_lake(tmp_path)
    too_early = START - timedelta(minutes=1)
    feed = HistoricalFeed(lake_root, too_early, symbols={"target": SYMBOL})
    df = feed.get_data(SYMBOL, timeframe_minutes=1, bars=1000)
    assert df.empty

    tick = feed.get_current_price(SYMBOL)
    assert tick == {"bid": 0, "ask": 0, "spread": 0, "time": None, "source": "historical"}


def test_requires_tz_aware_as_of(tmp_path):
    lake_root = _build_lake(tmp_path)
    with pytest.raises(ValueError):
        HistoricalFeed(lake_root, datetime(2026, 1, 1), symbols={"target": SYMBOL})


def test_two_feeds_different_as_of_never_cross_contaminate(tmp_path):
    """Two HistoricalFeed instances over the SAME lake at different as_of
    must be fully independent — the earlier one must never see what the
    later one can see, even though both cache internally."""
    lake_root = _build_lake(tmp_path)
    early = HistoricalFeed(lake_root, START + timedelta(minutes=10), symbols={"target": SYMBOL})
    late = HistoricalFeed(lake_root, START + timedelta(minutes=90), symbols={"target": SYMBOL})

    # Query late first, then early — order must not matter.
    late_df = late.get_data(SYMBOL, 1, bars=1000)
    early_df = early.get_data(SYMBOL, 1, bars=1000)

    assert early_df["close"].max() == 10
    assert late_df["close"].max() == 90
