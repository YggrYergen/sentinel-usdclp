"""Offline, pure tests for scripts.mt5_dump_history.drop_forming_bar and
_ingest_and_tier.

No MT5 connection required or made -- MT5 import lives inside main(), so
importing this module (and scripts.mt5_dump_history) never touches the
terminal.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import scripts.mt5_dump_history as mdh
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


def test_ingest_and_tier_order_and_dedup(monkeypatch):
    ingest_calls = []
    manifest_calls = []
    tier_calls = []

    def fake_ingest(path, lake_key, tf_min, lake_root, update_manifest):
        ingest_calls.append((path, lake_key, tf_min, lake_root, update_manifest))

    def fake_write_manifest(lake_root, gap_tolerance_factor):
        manifest_calls.append((lake_root, gap_tolerance_factor))

    def fake_build_tiers(symbol, lake_root):
        tier_calls.append((symbol, lake_root))

    monkeypatch.setattr(mdh, "ingest_mt5_csv", fake_ingest)
    monkeypatch.setattr(mdh, "write_manifest", fake_write_manifest)
    monkeypatch.setattr("sentinel_engine.lake.tiers.build_tiers", fake_build_tiers)

    p1 = Path("p1.csv")
    p2 = Path("p2.csv")
    p3 = Path("p3.csv")
    csv_paths = [("XAUUSD", 1, p1), ("XAUUSD", 5, p2), ("EURUSD", 1, p3)]

    mdh._ingest_and_tier(csv_paths)

    assert ingest_calls == [
        (p1, "XAUUSD", 1, mdh.LAKE_ROOT, False),
        (p2, "XAUUSD", 5, mdh.LAKE_ROOT, False),
        (p3, "EURUSD", 1, mdh.LAKE_ROOT, False),
    ]
    assert manifest_calls == [(mdh.LAKE_ROOT, 3.0)]
    assert tier_calls == [("XAUUSD", mdh.LAKE_ROOT), ("EURUSD", mdh.LAKE_ROOT)]


def test_ingest_and_tier_tier_failure_does_not_abort(monkeypatch):
    tier_calls = []

    def fake_ingest(path, lake_key, tf_min, lake_root, update_manifest):
        pass

    def fake_write_manifest(lake_root, gap_tolerance_factor):
        pass

    def fake_build_tiers(symbol, lake_root):
        tier_calls.append(symbol)
        if symbol == "XAUUSD":
            raise RuntimeError("boom")

    monkeypatch.setattr(mdh, "ingest_mt5_csv", fake_ingest)
    monkeypatch.setattr(mdh, "write_manifest", fake_write_manifest)
    monkeypatch.setattr("sentinel_engine.lake.tiers.build_tiers", fake_build_tiers)

    csv_paths = [
        ("XAUUSD", 1, Path("p1.csv")),
        ("EURUSD", 1, Path("p3.csv")),
    ]

    mdh._ingest_and_tier(csv_paths)  # must not raise

    assert tier_calls == ["XAUUSD", "EURUSD"]
