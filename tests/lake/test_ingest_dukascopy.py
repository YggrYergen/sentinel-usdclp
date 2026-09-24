"""
P2 Task 2.4 — Dukascopy price ingester -> lake + manifest gap detection.

NEEDS REAL-SAMPLE VALIDATION (Dukascopy): no real Dukascopy export exists in
this repo, so this test runs the adapter against a FORMAT-ACCURATE synthetic
fixture (tests/lake/fixtures/dukascopy_sample.csv) built to the documented
Dukascopy historical-data CSV shape. The fixture deliberately contains a
single gap (bars for 01:00 and 01:15 are missing) to exercise manifest gap
detection.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_engine.lake.ingest_dukascopy import (
    DukascopyCsvFormatError,
    ingest_dukascopy_csv,
    read_dukascopy_csv,
)
from sentinel_engine.lake.manifest import load_manifest
from sentinel_engine.lake.store import read_bars

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dukascopy_sample.csv"


def test_read_dukascopy_csv_parses_synthetic_fixture():
    df = read_dukascopy_csv(FIXTURE)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 7
    assert df.index.tz is not None
    assert df.index.is_monotonic_increasing


def test_read_dukascopy_csv_rejects_bad_header(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("time,open,high,low,close,volume\n2026-01-01,1,2,3,4,5\n", encoding="utf-8")
    with pytest.raises(DukascopyCsvFormatError):
        read_dukascopy_csv(bad)


def test_ingest_dukascopy_csv_round_trips(tmp_path):
    lake_root = tmp_path / "lake"
    original = read_dukascopy_csv(FIXTURE)

    ingest_dukascopy_csv(FIXTURE, "NQ100", 15, lake_root)

    stored = read_bars(lake_root, "NQ100", 15)
    assert len(stored) == len(original)
    assert list(stored.columns) == ["open", "high", "low", "close", "volume"]


def test_ingest_dukascopy_manifest_detects_gap(tmp_path):
    lake_root = tmp_path / "lake"
    ingest_dukascopy_csv(FIXTURE, "NQ100", 15, lake_root)

    manifest = load_manifest(lake_root)
    entry = manifest["NQ100"]["15"]
    assert entry["bar_count"] == 7
    assert len(entry["gaps"]) == 1
    gap = entry["gaps"][0]
    assert gap["missing_bars"] == 2
    assert gap["after"].startswith("2026-01-01T00:45:00")
    assert gap["before"].startswith("2026-01-01T01:30:00")
