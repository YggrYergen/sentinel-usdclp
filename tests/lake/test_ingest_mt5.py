"""
P2 Task 2.5 — MT5 price ingester -> lake, tested against the REAL MT5 OHLC
CSV exports already committed at tests/golden/fixtures/csv/** (never
modified/regenerated here — read-only source)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sentinel_engine.lake.ingest_mt5 import Mt5CsvFormatError, ingest_mt5_csv, read_mt5_csv
from sentinel_engine.lake.manifest import load_manifest
from sentinel_engine.lake.store import read_bars

REAL_XAUUSD_15 = Path(__file__).resolve().parents[1] / "golden" / "fixtures" / "csv" / "XAUUSD" / "15.csv"
REAL_NQ100_5 = Path(__file__).resolve().parents[1] / "golden" / "fixtures" / "csv" / "NQ100" / "5.csv"


def test_read_mt5_csv_parses_real_fixture():
    df = read_mt5_csv(REAL_XAUUSD_15)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tz is not None
    assert df.index.is_monotonic_increasing
    assert len(df) > 0


def test_read_mt5_csv_rejects_bad_header(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("date,open,high,low,close,volume\n2026-01-01,1,2,3,4,5\n", encoding="utf-8")
    with pytest.raises(Mt5CsvFormatError):
        read_mt5_csv(bad)


def test_ingest_mt5_csv_round_trips_real_fixture(tmp_path):
    lake_root = tmp_path / "lake"
    original = read_mt5_csv(REAL_XAUUSD_15)

    ingest_mt5_csv(REAL_XAUUSD_15, "XAUUSD", 15, lake_root)

    stored = read_bars(lake_root, "XAUUSD", 15)
    pd.testing.assert_frame_equal(stored, original, check_freq=False)


def test_ingest_mt5_csv_updates_manifest(tmp_path):
    lake_root = tmp_path / "lake"
    ingest_mt5_csv(REAL_XAUUSD_15, "XAUUSD", 15, lake_root)
    ingest_mt5_csv(REAL_NQ100_5, "NQ100", 5, lake_root)

    manifest = load_manifest(lake_root)
    assert set(manifest.keys()) == {"XAUUSD", "NQ100"}
    assert manifest["XAUUSD"]["15"]["bar_count"] > 0
    assert manifest["XAUUSD"]["15"]["start"] is not None
    assert manifest["XAUUSD"]["15"]["end"] is not None
