"""
Tests for sentinel_engine.lake.tiers — Wave A / lane C lake TF tiers builder.

Uses tmp_path for the lake root in every test; never touches the real
data/lake/ tree.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from sentinel_engine.lake import store
from sentinel_engine.lake.tiers import TF_SECONDS, build_tiers

BASE = pd.Timestamp("2026-01-01T00:00:00Z")
BASE_EPOCH = int(BASE.timestamp())

# 13 M1 bars with a 3-bucket (15 minute) gap in the M5 grid:
#   bucket@0   (minutes 0-4)   -> 5 bars
#   [gap: minutes 5-19, buckets @5,@10,@15 empty]
#   bucket@20  (minutes 20-24) -> 5 bars
#   bucket@25  (minutes 25-27) -> 3 bars (partial)
_MINUTES = [0, 1, 2, 3, 4, 20, 21, 22, 23, 24, 25, 26, 27]


def _make_m1_frame() -> pd.DataFrame:
    idx = [BASE + pd.Timedelta(minutes=m) for m in _MINUTES]
    rows = []
    for i, _m in enumerate(_MINUTES):
        o = 100 + i
        rows.append({
            "open": float(o),
            "high": o + 0.5,
            "low": o - 0.5,
            "close": o + 0.2,
            "volume": 10 + i,
        })
    df = pd.DataFrame(rows, index=pd.DatetimeIndex(idx, tz="UTC", name="time"))
    return df


def _seed_lake(lake_root: Path, symbol: str = "EURUSD") -> None:
    store.write_bars(lake_root, symbol, 1, _make_m1_frame())


# now_epoch far enough past the last bar that ALL buckets (including the
# partial trailing one) are safely "closed" for every TF used in these tests.
FAR_FUTURE_NOW = BASE_EPOCH + 10_000 * 60


def test_m5_resample_golden_fixture_exact_rows(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root)

    report = build_tiers("EURUSD", lake_root, now_epoch=FAR_FUTURE_NOW)

    m5_dir = lake_root / "EURUSD" / "M5"
    files = sorted(m5_dir.glob("*.parquet"))
    assert len(files) == 1  # all bars fall in the same UTC month
    df = pd.read_parquet(files[0])
    df = df.sort_values("t").reset_index(drop=True)

    expected = pd.DataFrame([
        {"t": BASE_EPOCH + 0 * 60, "o": 100.0, "h": 104.5, "l": 99.5, "c": 104.2, "v": 60},
        {"t": BASE_EPOCH + 20 * 60, "o": 105.0, "h": 109.5, "l": 104.5, "c": 109.2, "v": 85},
        {"t": BASE_EPOCH + 25 * 60, "o": 110.0, "h": 112.5, "l": 109.5, "c": 112.2, "v": 63},
    ])

    assert list(df.columns) == ["t", "o", "h", "l", "c", "v"]
    pd.testing.assert_frame_equal(df, expected, check_dtype=False)
    # empty buckets (@5, @10, @15) must not appear at all
    assert set(df["t"]) == set(expected["t"])
    assert report.tiers["M5"]["rows"] == 3


def test_forming_bar_is_excluded(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root)

    # now_epoch chosen so the LAST M5 bucket (@25, i.e. BASE_EPOCH + 25*60)
    # is still within its forming window: now - tf_seconds < bucket_start.
    tf_seconds = TF_SECONDS["M5"]
    last_bucket_start = BASE_EPOCH + 25 * 60
    now_epoch = last_bucket_start + tf_seconds - 1  # bucket not yet closed

    build_tiers("EURUSD", lake_root, now_epoch=now_epoch)

    m5_dir = lake_root / "EURUSD" / "M5"
    df = pd.read_parquet(sorted(m5_dir.glob("*.parquet"))[0])

    assert last_bucket_start not in set(df["t"])
    # the two earlier, fully-closed buckets must still be present
    assert BASE_EPOCH + 0 * 60 in set(df["t"])
    assert BASE_EPOCH + 20 * 60 in set(df["t"])
    assert len(df) == 2


def test_build_is_idempotent_same_shas(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root)

    report1 = build_tiers("EURUSD", lake_root, now_epoch=FAR_FUTURE_NOW)
    report2 = build_tiers("EURUSD", lake_root, now_epoch=FAR_FUTURE_NOW)

    for tf_name in TF_SECONDS:
        assert report1.tiers[tf_name]["content_sha"] == report2.tiers[tf_name]["content_sha"]
        assert report1.tiers[tf_name]["content_sha"] != ""


def test_manifest_updated_with_correct_entries(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root)

    build_tiers("EURUSD", lake_root, now_epoch=FAR_FUTURE_NOW)

    manifest_path = lake_root / "manifest.json"
    assert manifest_path.exists()
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert "EURUSD" in manifest
    m5_entry = manifest["EURUSD"]["M5"]
    assert m5_entry["symbol"] == "EURUSD"
    assert m5_entry["tf"] == "M5"
    assert m5_entry["rows"] == 3
    assert m5_entry["first"] == BASE_EPOCH + 0 * 60
    assert m5_entry["last"] == BASE_EPOCH + 25 * 60
    assert isinstance(m5_entry["content_sha"], str) and len(m5_entry["content_sha"]) == 40

    # all supported TFs are represented
    for tf_name in TF_SECONDS:
        assert tf_name in manifest["EURUSD"]
