"""tests/sim/test_lite.py — TDD for the backtest-lite engine (M2.5).

Covers: a small synthetic-bars unit test forcing a known
entry->engulfing-exit sequence (fill-next-open, spread applied), and a
determinism check against the real XAUUSD lake window (same input -> same
trades, exercised twice).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sentinel_engine.sim.lite import run_backtest_lite
from sentinel_engine.strategies.emasar import EmasarPolicy, ema_series, sar_series

LAKE_ROOT = Path("data/lake")


class _StubPolicy:
    """Deterministic stub: enters LONG at a fixed bar index, exits on the
    very next bar — used to pin down fill-next-open + spread mechanics
    without depending on the real EMASAR gate logic."""

    def __init__(self, entry_idx: int):
        self.entry_idx = entry_idx
        self._exited = False

    def signal_at(self, bars, i):
        if i == self.entry_idx:
            return "LONG"
        return None

    def should_exit(self, bars, i, side):
        # Exit decided as soon as the position is open (checked at the top
        # of the loop for the bar right after the entry fill), closing on
        # the NEXT bar's open (i+1).
        if self._exited:
            return False
        if i == self.entry_idx + 1:
            self._exited = True
            return True
        return False


def _mk_frame(rows: list[tuple[str, float, float, float, float, float]]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(r[0], tz="UTC") for r in rows], name="time")
    df = pd.DataFrame(
        {
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "volume": [r[5] for r in rows],
        },
        index=idx,
    )
    return df


@pytest.fixture
def synthetic_lake(tmp_path):
    from sentinel_engine.lake.store import write_bars

    rows = [
        ("2026-01-01T00:00:00", 100.0, 101.0, 99.0, 100.5, 10),
        ("2026-01-01T00:05:00", 100.5, 102.0, 100.0, 101.5, 10),  # entry_idx=1 signal
        ("2026-01-01T00:10:00", 102.0, 103.0, 101.5, 102.5, 10),  # fill open=102.0
        ("2026-01-01T00:15:00", 102.5, 104.0, 102.0, 103.5, 10),  # exit decided here
        ("2026-01-01T00:20:00", 103.5, 105.0, 103.0, 104.5, 10),  # exit fill open=103.5
        ("2026-01-01T00:25:00", 104.5, 105.5, 104.0, 105.0, 10),
    ]
    df = _mk_frame(rows)
    lake_root = tmp_path / "lake"
    write_bars(lake_root, "SYN", 5, df)
    return lake_root


def test_fill_next_open_and_spread(synthetic_lake):
    policy = _StubPolicy(entry_idx=1)
    run, trades = run_backtest_lite(
        policy, "SYN", "M5", None, None,
        costs={"spread": 1.0, "commission": 0.0},
        lake_root=synthetic_lake,
    )
    assert len(trades) == 1
    t = trades[0]
    # Entry: signal decided at bar[1] (close), fills at bar[2].open (102.0)
    # + half-spread (0.5) = 102.5.
    assert t["px_in"] == pytest.approx(102.5)
    # Exit: should_exit is checked at bar[2] (the bar right after the fill)
    # and fills at bar[3].open (102.5) - half-spread (0.5) = 102.0.
    assert t["px_out"] == pytest.approx(102.0)
    assert t["side"] == "LONG"
    assert t["pnl"] == pytest.approx(102.0 - 102.5)
    assert run["trades"] == 1
    assert run["engine"] == "sentinel-sim"
    assert run["fidelity"] == "research"


def test_commission_subtracted(synthetic_lake):
    policy = _StubPolicy(entry_idx=1)
    run, trades = run_backtest_lite(
        policy, "SYN", "M5", None, None,
        costs={"spread": 0.0, "commission": 0.25},
        lake_root=synthetic_lake,
    )
    t = trades[0]
    # No spread: entry=bar[2].open=102.0, exit=bar[3].open=102.5, gross
    # pnl=0.5, minus commission.
    assert t["pnl"] == pytest.approx(0.5 - 0.25)


def test_no_signal_produces_no_trades(synthetic_lake):
    class _NeverPolicy:
        def signal_at(self, bars, i):
            return None

        def should_exit(self, bars, i, side):
            return False

    run, trades = run_backtest_lite(_NeverPolicy(), "SYN", "M5", None, None, lake_root=synthetic_lake)
    assert trades == []
    assert run["trades"] == 0
    assert run["net"] == 0.0


# ---------------------------------------------------------------------
# EMASAR indicator sanity (ported logic matches reference shape)
# ---------------------------------------------------------------------

def test_ema_series_seed_and_recursion():
    closes = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = ema_series(closes, 3)
    assert out[0] is None and out[1] is None
    assert out[2] == pytest.approx(2.0)  # SMA(1,2,3)
    assert out[3] is not None
    assert out[4] is not None


def test_sar_series_basic_shape():
    highs = [10, 11, 12, 11, 10, 9, 8, 9, 10]
    lows = [9, 10, 11, 10, 9, 8, 7, 8, 9]
    sar, trend = sar_series(highs, lows, 0.02, 0.2)
    assert len(sar) == len(highs)
    assert all(t in (1, -1) for t in trend)


# ---------------------------------------------------------------------
# Determinism against the real lake (EMASAR policy, XAUUSD)
# ---------------------------------------------------------------------

def _has_real_lake() -> bool:
    return (LAKE_ROOT / "XAUUSD" / "5.parquet").exists()


@pytest.mark.skipif(not _has_real_lake(), reason="requires the real data/lake XAUUSD M5 parquet")
def test_emasar_backtest_real_window_is_deterministic():
    policy1 = EmasarPolicy({})
    run1, trades1 = run_backtest_lite(
        policy1, "XAUUSD", "M5", "2026-06-01", "2026-06-08", lake_root=LAKE_ROOT,
    )
    policy2 = EmasarPolicy({})
    run2, trades2 = run_backtest_lite(
        policy2, "XAUUSD", "M5", "2026-06-01", "2026-06-08", lake_root=LAKE_ROOT,
    )
    assert trades1 == trades2
    assert run1["trades"] == run2["trades"]
    assert run1["net"] == run2["net"]
    assert len(trades1) > 0
