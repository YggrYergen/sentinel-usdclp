"""tests/lake/test_mt5_fetch.py -- offline tests for the shared MT5
frame-shaping + forming-bar helpers (`sentinel_engine.lake.mt5_fetch`).

Hermetic: no real MetaTrader5, no real lake. Raw "rates" are plain lists of
dicts (the same field shape the real `copy_rates_from*` structured arrays
expose: time/open/high/low/close/tick_volume).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sentinel_engine.lake import mt5_fetch


def _rate(t_epoch: int, o=1.0, h=2.0, lo=0.5, c=1.5, tv=100):
    return (t_epoch, o, h, lo, c, tv)


def _rates_array(rows):
    dtype = [
        ("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
        ("close", "f8"), ("tick_volume", "i8"),
    ]
    return np.array(rows, dtype=dtype)


def test_rates_to_frame_shape_matches_fetch_series():
    rows = [_rate(0), _rate(60), _rate(120)]
    df = mt5_fetch.rates_to_frame(_rates_array(rows))
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "time"
    assert str(df.index.tz) == "UTC"
    assert df["volume"].dtype == np.int64
    assert df.index[0] == pd.Timestamp(0, unit="s", tz="UTC")


def test_rates_to_frame_empty_and_none():
    assert mt5_fetch.rates_to_frame(None).empty
    assert mt5_fetch.rates_to_frame(_rates_array([])).empty


def test_drop_forming_bar_removes_open_bar():
    # tf=1min; last bar opens at t=120, closes at 180. now=150 -> still forming.
    idx = pd.to_datetime([0, 60, 120], unit="s", utc=True)
    df = pd.DataFrame(
        {"open": [1, 1, 1], "high": [1, 1, 1], "low": [1, 1, 1],
         "close": [1, 1, 1], "volume": [1, 1, 1]}, index=idx)
    out = mt5_fetch.drop_forming_bar(df, 1, now_epoch=150)
    assert len(out) == 2
    assert out.index[-1] == pd.Timestamp(60, unit="s", tz="UTC")


def test_drop_forming_bar_keeps_closed_bar():
    idx = pd.to_datetime([0, 60, 120], unit="s", utc=True)
    df = pd.DataFrame(
        {"open": [1, 1, 1], "high": [1, 1, 1], "low": [1, 1, 1],
         "close": [1, 1, 1], "volume": [1, 1, 1]}, index=idx)
    # last bar (t=120) closes at 180; now=200 -> already closed, keep it.
    out = mt5_fetch.drop_forming_bar(df, 1, now_epoch=200)
    assert len(out) == 3


def test_drop_forming_bar_empty():
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    empty.index = pd.DatetimeIndex([], tz="UTC", name="time")
    out = mt5_fetch.drop_forming_bar(empty, 5, now_epoch=1000)
    assert out.empty
