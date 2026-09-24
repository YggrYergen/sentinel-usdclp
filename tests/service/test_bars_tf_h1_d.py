"""tests/service/test_bars_tf_h1_d.py — TDD for Task ORC5-F1.

Root cause: `sentinel_engine/service/bars.py::NATIVE_TF_MINUTES` didn't
include H1/D even though the lake stores native `60.parquet` / `1440.parquet`
files (same pattern as 1/5/15), so `load_tf_frame(..., "H1")` and `"D"`
raised `BarsError: unknown tf` and `POST /api/jobs/backtest` failed for the
tf values the launcher UI already offers.

Uses a temp Parquet lake (`sentinel_engine.lake.store.write_bars`) — never
touches the real `data/lake`.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sentinel_engine.lake.store import write_bars
from sentinel_engine.service.bars import BarsError, load_tf_frame


def _m1_frame(n: int, start="2026-01-01T00:00:00Z", freq="1min") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    df = pd.DataFrame({
        "open": [100.0 + i for i in range(n)],
        "high": [100.5 + i for i in range(n)],
        "low": [99.5 + i for i in range(n)],
        "close": [100.2 + i for i in range(n)],
        "volume": [10.0 + i for i in range(n)],
    }, index=idx)
    df.index.name = "time"
    return df


@pytest.fixture
def lake_root(tmp_path):
    root = tmp_path / "lake"
    write_bars(root, "XAUUSD", 60, _m1_frame(5, freq="1h"))
    write_bars(root, "XAUUSD", 1440, _m1_frame(3, freq="1D"))
    return root


def test_load_tf_frame_h1_native(lake_root):
    frame = load_tf_frame(lake_root, "XAUUSD", "H1")
    assert not frame.empty
    assert len(frame) == 5


def test_load_tf_frame_d_native(lake_root):
    frame = load_tf_frame(lake_root, "XAUUSD", "D")
    assert not frame.empty
    assert len(frame) == 3


def test_load_tf_frame_unknown_tf_still_raises(lake_root):
    with pytest.raises(BarsError):
        load_tf_frame(lake_root, "XAUUSD", "H4")
