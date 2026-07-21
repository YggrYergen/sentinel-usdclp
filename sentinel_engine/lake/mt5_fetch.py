"""sentinel_engine.lake.mt5_fetch -- shared MT5 raw-rates -> OHLCV frame
shaping and forming-bar logic.

Extracted from `scripts/mt5_dump_history.py` so BOTH the one-shot backfill
dumper and the long-lived incremental ingester daemon
(`scripts/live/run_bars_ingester.py`) reuse ONE implementation of the
frame shape + forming-bar guard (avoiding a verbatim-duplication defect).

IMPORTANT: this module MUST stay importable offline -- it NEVER imports
MetaTrader5 at module top. Callers pass in already-fetched raw `rates`
(the structured array / sequence the terminal's `copy_rates_*` returns),
so nothing here connects to a terminal.
"""
from __future__ import annotations

import pandas as pd


def rates_to_frame(rates) -> pd.DataFrame:
    """Shape raw MT5 `copy_rates_*` output into the canonical OHLCV frame.

    Returns a frame with columns ``open/high/low/close/volume`` and a
    tz-aware UTC ``DatetimeIndex`` named ``time`` (bar-open time), sorted
    ascending. ``volume`` comes from ``tick_volume`` as ``int64``. Mirrors
    the shape `mt5_dump_history.fetch_series` produced (its lines 129-135).

    Returns an empty frame if `rates` is None or empty.
    """
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    return pd.DataFrame({
        "open": df["open"],
        "high": df["high"],
        "low": df["low"],
        "close": df["close"],
        "volume": df["tick_volume"].astype("int64"),
    })


def drop_forming_bar(df: pd.DataFrame, tf_minutes: int, now_epoch: int) -> pd.DataFrame:
    """Remove the last row of df IFF its bar-open time has not yet closed as of
    now_epoch, i.e. t + tf_minutes*60 > now_epoch. df must have a tz-aware
    DatetimeIndex named/representing bar-open time (UTC). Returns df unchanged
    if empty or if the last bar is already closed."""
    if df.empty:
        return df
    last_t = df.index[-1]
    t_epoch = int(last_t.timestamp())
    if t_epoch + tf_minutes * 60 > now_epoch:
        return df.iloc[:-1]
    return df
