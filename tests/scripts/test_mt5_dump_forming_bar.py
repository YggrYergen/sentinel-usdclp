"""Offline, pure tests for scripts.mt5_dump_history.drop_forming_bar.

No MT5 connection required or made -- MT5 import lives inside main(), so
importing this module (and scripts.mt5_dump_history) never touches the
terminal.
"""
from __future__ import annotations

import pandas as pd

from scripts.mt5_dump_history import drop_forming_bar

TF_MIN = 2  # M2 bars, matches the production defect (t=1783990080, tf=2)


def _make_df(times_epoch: list[int]) -> pd.DataFrame:
    idx = pd.to_datetime(times_epoch, unit="s", utc=True)
    return pd.DataFrame(
        {
            "open": [1.0] * len(times_epoch),
            "high": [1.0] * len(times_epoch),
            "low": [1.0] * len(times_epoch),
            "close": [1.0] * len(times_epoch),
            "volume": [1] * len(times_epoch),
        },
        index=pd.DatetimeIndex(idx, name="time"),
    )


def test_forming_bar_is_dropped():
    # last bar open at t=1783990080 (tf=2min -> closes at +120s = 1783990200)
    # now is strictly before close -> still forming -> must be dropped
    t_last = 1783990080
    now_epoch = t_last + 120 - 1  # 1 second before close
    df = _make_df([1783989960, t_last])
    out = drop_forming_bar(df, TF_MIN, now_epoch)
    assert len(out) == 1
    assert int(out.index[-1].timestamp()) == 1783989960


def test_bar_closed_exactly_at_boundary_is_kept():
    t_last = 1783990080
    now_epoch = t_last + 120  # exactly at close boundary
    df = _make_df([1783989960, t_last])
    out = drop_forming_bar(df, TF_MIN, now_epoch)
    assert len(out) == 2
    assert int(out.index[-1].timestamp()) == t_last


def test_all_closed_series_unchanged():
    t_last = 1783990080
    now_epoch = t_last + 121  # well past close
    df = _make_df([1783989720, 1783989840, 1783989960, t_last])
    out = drop_forming_bar(df, TF_MIN, now_epoch)
    assert len(out) == len(df)
    pd.testing.assert_frame_equal(out, df)


def test_empty_series_no_crash_unchanged():
    df = _make_df([])
    out = drop_forming_bar(df, TF_MIN, 1783990200)
    assert out.empty
    pd.testing.assert_frame_equal(out, df)
