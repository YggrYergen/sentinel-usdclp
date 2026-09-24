"""
Tests for sentinel_engine.feed (P1 Task 1.3).

Verifies:
  - FakeFeed structurally satisfies the data-access part of the Feed
    Protocol (duck-typing — Protocol needs no inheritance).
  - LiveMT5Feed exposes all five Feed methods.
  - LiveMT5Feed delegates data calls straight through to the wrapped
    feed, and its positions()/now() are read-only / safe with a dummy
    wrapped object (no real MT5 involved).
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pandas as pd
import pytest

from sentinel_engine.feed import Feed, LiveMT5Feed
from tests.golden.fake_feed import FakeFeed


DATA_METHODS = ("get_data", "get_current_price", "get_all_data")
ALL_METHODS = DATA_METHODS + ("positions", "now")


def test_fakefeed_satisfies_data_protocol_methods():
    ff = FakeFeed()
    for name in DATA_METHODS:
        assert hasattr(ff, name), f"FakeFeed missing {name}"
        assert callable(getattr(ff, name))


def test_fakefeed_isinstance_protocol():
    # typing.Protocol with no @runtime_checkable would raise on isinstance();
    # this test only checks the methods exist (duck typing), matching the
    # spec's "structurally satisfies" wording.
    ff = FakeFeed()
    sig_get_data = inspect.signature(ff.get_data)
    assert list(sig_get_data.parameters)[:3] == ["symbol", "timeframe_minutes", "bars"]


def test_livemt5feed_has_all_five_methods():
    for name in ALL_METHODS:
        assert hasattr(LiveMT5Feed, name), f"LiveMT5Feed missing {name}"


class _DummyWrappedFeed:
    """Stand-in for sentinel.data_feed.DataFeed — no MT5, no network."""

    def __init__(self):
        self.calls = []
        self.mt5_connected = False
        self._mt5 = None

    def get_data(self, symbol, timeframe_minutes=15, bars=200):
        self.calls.append(("get_data", symbol, timeframe_minutes, bars))
        return pd.DataFrame({"close": [1.0, 2.0, 3.0]})

    def get_current_price(self, symbol):
        self.calls.append(("get_current_price", symbol))
        return {"bid": 1.0, "ask": 1.1}

    def get_all_data(self, timeframe_minutes=15, bars=200):
        self.calls.append(("get_all_data", timeframe_minutes, bars))
        return {"target": pd.DataFrame({"close": [1.0]})}


def test_livemt5feed_delegates_get_data():
    wrapped = _DummyWrappedFeed()
    feed = LiveMT5Feed(wrapped)
    df = feed.get_data("USDCLP", timeframe_minutes=1, bars=10)
    assert list(df["close"]) == [1.0, 2.0, 3.0]
    assert wrapped.calls == [("get_data", "USDCLP", 1, 10)]


def test_livemt5feed_delegates_get_current_price():
    wrapped = _DummyWrappedFeed()
    feed = LiveMT5Feed(wrapped)
    price = feed.get_current_price("USDCLP")
    assert price == {"bid": 1.0, "ask": 1.1}
    assert wrapped.calls == [("get_current_price", "USDCLP")]


def test_livemt5feed_delegates_get_all_data():
    wrapped = _DummyWrappedFeed()
    feed = LiveMT5Feed(wrapped)
    result = feed.get_all_data(timeframe_minutes=5, bars=50)
    assert "target" in result
    assert wrapped.calls == [("get_all_data", 5, 50)]


def test_livemt5feed_now_returns_utc_datetime():
    feed = LiveMT5Feed(_DummyWrappedFeed())
    ts = feed.now()
    assert isinstance(ts, datetime)
    assert ts.tzinfo is not None
    assert ts.tzinfo == timezone.utc or ts.utcoffset().total_seconds() == 0


def test_livemt5feed_positions_returns_empty_list_when_not_connected():
    feed = LiveMT5Feed(_DummyWrappedFeed())
    assert feed.positions() == []


def test_livemt5feed_positions_never_places_orders():
    """Sanity check: LiveMT5Feed never exposes order-placement methods."""
    for forbidden in ("order_send", "order_check", "close_position", "place_order"):
        assert not hasattr(LiveMT5Feed, forbidden)
