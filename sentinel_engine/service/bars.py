"""
sentinel_engine.service.bars — `/api/bars` support (plan §D.6, Task M1.2).

Pure helpers, no FastAPI here: reading the lake, resampling M2/M10 from the
native M1 frame, LOD-decimating to `max_points`, and shaping the normative
wire format `{"symbol","tf","decimated":bool,"bars":[[ts_epoch_s,o,h,l,c,v],...]}`.

Timestamps are ALWAYS epoch-seconds UTC ints on the wire. Causality (`ts<=to`)
is enforced by the caller filtering the frame before it reaches
`bars_payload`/`decimate_ohlc` — see `app.py::get_bars`.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sentinel_engine.lake.store import read_bars

# Native timeframes stored directly in the lake (minutes). M2/M10 are
# resampled on read from the M1 frame — see plan §D.6.
NATIVE_TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "D": 1440}
RESAMPLE_TF_MINUTES = {"M2": 2, "M10": 10}
ALL_TF_MINUTES = {**NATIVE_TF_MINUTES, **RESAMPLE_TF_MINUTES}


class BarsError(ValueError):
    """Raised for a bad `/api/bars` request (bad tf, bad range, ...)."""


def _resample_from_m1(m1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """OHLC-aggregate a native M1 frame into `minutes`-wide bars: open=first,
    high=max, low=min, close=last, volume=sum. Empty input -> empty output."""
    if m1.empty:
        return m1
    rule = f"{int(minutes)}min"
    agg = m1.resample(rule, label="left", closed="left").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    return agg.dropna(subset=["open", "high", "low", "close"])


def load_tf_frame(lake_root: Path, symbol: str, tf: str) -> pd.DataFrame:
    """Return the OHLCV frame for `symbol`/`tf`, resampling M2/M10 from the
    native M1 frame when `tf` has no dedicated lake file."""
    if tf in NATIVE_TF_MINUTES:
        return read_bars(lake_root, symbol, NATIVE_TF_MINUTES[tf])
    if tf in RESAMPLE_TF_MINUTES:
        m1 = read_bars(lake_root, symbol, 1)
        return _resample_from_m1(m1, RESAMPLE_TF_MINUTES[tf])
    raise BarsError(f"unknown tf: {tf}")


def _row_to_wire(ts: pd.Timestamp, row) -> list:
    epoch_s = int(ts.value // 1_000_000_000)
    return [epoch_s, float(row["open"]), float(row["high"]), float(row["low"]),
            float(row["close"]), float(row["volume"])]


def decimate_ohlc(df: pd.DataFrame, max_points: int) -> tuple[pd.DataFrame, bool]:
    """If `len(df) > max_points`, LOD-decimate by bucketing into
    `max_points` equal-sized buckets and OHLC-aggregating each bucket
    (open=first, high=max, low=min, close=last, volume=sum). Returns
    `(frame, decimated)`."""
    n = len(df)
    if n <= max_points or max_points <= 0:
        return df, False
    # Assign each row to one of `max_points` buckets, preserving order.
    bucket_size = -(-n // max_points)  # ceil division
    bucket_idx = (pd.RangeIndex(n) // bucket_size)
    grouped = df.groupby(bucket_idx)
    out = grouped.agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    # Bucket timestamp = first row's timestamp in that bucket.
    first_ts = grouped.apply(lambda g: g.index[0])
    out.index = pd.DatetimeIndex(first_ts.values, tz="UTC", name="time")
    return out, True


def bars_payload(
    lake_root: Path,
    symbol: str,
    tf: str,
    ts_from: pd.Timestamp | None,
    ts_to: pd.Timestamp | None,
    max_points: int,
) -> dict:
    """Build the exact `/api/bars` response body (plan §D.6)."""
    if tf not in ALL_TF_MINUTES:
        raise BarsError(f"unknown tf: {tf}")
    df = load_tf_frame(lake_root, symbol, tf)
    if not df.empty:
        if ts_from is not None:
            df = df[df.index >= ts_from]
        if ts_to is not None:
            # Causal: never return a bar timestamped after `to`.
            df = df[df.index <= ts_to]
    df, decimated = decimate_ohlc(df, max_points)
    bars = [_row_to_wire(ts, row) for ts, row in df.iterrows()]
    return {"symbol": symbol, "tf": tf, "decimated": decimated, "bars": bars}
