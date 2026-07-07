"""
P2 Task 2.8 — Replayer equivalence: Engine over HistoricalFeed(as_of=t) ==
Engine over a deterministic feed built from the SAME underlying data.

No live P0.7 snapshot logs exist in this repo (self-contained per the P2
brief), so this test:
  1. Ingests the SAME real MT5 fixture CSVs `tests/golden/fake_feed.FakeFeed`
     reads (tests/golden/fixtures/csv/**, read-only) into a temp Parquet
     lake, covering every committed symbol/timeframe.
  2. Sets `as_of` to the GLOBAL max timestamp across every ingested file, so
     `HistoricalFeed`'s `ts <= as_of` filter is a no-op on every file
     (nothing gets truncated) — i.e. HistoricalFeed exposes EXACTLY the same
     rows FakeFeed does, from the same underlying data.
  3. Drives `Engine` over both feeds via `tests/golden/capture_engine.capture_engine`
     (unmodified, reused) with the same warmup convention, and asserts the
     resulting canonical-JSON snapshots are byte-identical for all three
     target instruments.

This proves HistoricalFeed(as_of=t) is a faithful point-in-time replayer:
when nothing is actually filtered out, it reproduces the live/deterministic
scoring path exactly.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sentinel_engine.feed_historical import HistoricalFeed
from sentinel_engine.lake.ingest_mt5 import ingest_mt5_csv

from tests.golden.capture_engine import capture_engine
from tests.golden.capture_golden import to_canonical_json
from tests.golden.fake_feed import FIXTURES_CSV_ROOT, FakeFeed

INSTRUMENTS = ["usdclp", "gold", "nasdaq"]


def _build_lake_from_fixtures(tmp_path):
    lake_root = tmp_path / "lake"
    max_ts = None
    for symbol_dir in sorted(p for p in FIXTURES_CSV_ROOT.iterdir() if p.is_dir()):
        for csv_file in sorted(symbol_dir.glob("*.csv")):
            tf = int(csv_file.stem)
            ingest_mt5_csv(csv_file, symbol_dir.name, tf, lake_root, update_manifest=False)
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True, encoding="utf-8")
            local_max = df.index.max()
            if max_ts is None or local_max > max_ts:
                max_ts = local_max
    return lake_root, max_ts


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_historical_feed_reproduces_fakefeed_snapshot(instrument, tmp_path):
    lake_root, max_ts = _build_lake_from_fixtures(tmp_path)
    historical_feed = HistoricalFeed(lake_root, max_ts.to_pydatetime())

    fake_result = capture_engine(instrument, FakeFeed())
    hist_result = capture_engine(instrument, historical_feed)

    assert to_canonical_json(fake_result) == to_canonical_json(hist_result)
