"""
Tests for sentinel.logging.snapshot_logger.SnapshotLogger

Covers:
- basic write + schema/round-trip of the full nested snapshot via snapshot_json
- seq is monotonic 0..K-1 and config_hash/symbol are stamped correctly
- batching does not lose data (K not a multiple of batch size)
- restart/reopen appends and resumes seq (no clobber)
All I/O happens under pytest's tmp_path — never the repo's real logs/.
"""
import json

import pandas as pd
import pytest

from sentinel.logging.snapshot_logger import SnapshotLogger

CONFIG_HASH = "test-cfg-abc123"


def _make_snapshot(i: int) -> dict:
    """A small nested dict resembling calculate_composite() output."""
    return {
        "composite_score": 55.5 + i,
        "direction": "LONG" if i % 2 == 0 else "SHORT",
        "signal": "🟡 ALERTA",
        "blocked": False,
        "block_reason": "",
        "components": {
            "technical": {
                "score": 60.0 + i,
                "weight": 0.5,
                "direction": "LONG",
                "details": {"tf_scores": {"h1": 50 + i, "h4": 60 + i}},
            },
            "correlation": {"score": 51.0, "weight": 0.5, "direction": "SHORT"},
            "_macro": {"score": 51.0, "direction": "SHORT", "votes": {"dxy": "SHORT"}},
        },
        "levels": {"current_price": 950.1 + i, "combined": {"support": 940.0}},
        "divergences": [],
        "alerts": [f"alert-{i}"],
        "meta": {"timestamp": "2026-07-07T10:00:00"},
    }


def test_logs_k_snapshots_to_dated_parquet_with_correct_schema(tmp_path):
    logger = SnapshotLogger(tmp_path, CONFIG_HASH, symbol="USDCLP", batch_size=10)
    k = 5
    for i in range(k):
        logger.log(_make_snapshot(i))
    logger.close()

    expected_dir = tmp_path / "snapshots" / "USDCLP"
    files = list(expected_dir.glob("*.parquet"))
    assert len(files) == 1
    path = files[0]

    df = pd.read_parquet(path)
    assert len(df) == k
    for col in ["ts", "symbol", "seq", "config_hash", "composite_score",
                "direction", "signal", "snapshot_json"]:
        assert col in df.columns

    assert list(df["seq"]) == list(range(k))
    assert (df["symbol"] == "USDCLP").all()
    assert (df["config_hash"] == CONFIG_HASH).all()


def test_snapshot_json_round_trips_to_original_nested_dict(tmp_path):
    logger = SnapshotLogger(tmp_path, CONFIG_HASH, symbol="USDCLP", batch_size=10)
    snap = _make_snapshot(3)
    logger.log(snap)
    logger.close()

    path = list((tmp_path / "snapshots" / "USDCLP").glob("*.parquet"))[0]
    df = pd.read_parquet(path)
    round_tripped = json.loads(df.iloc[0]["snapshot_json"])
    assert round_tripped == snap
    assert df.iloc[0]["composite_score"] == pytest.approx(snap["composite_score"])
    assert df.iloc[0]["direction"] == snap["direction"]
    assert df.iloc[0]["signal"] == snap["signal"]


def test_batch_remainder_flushes_all_rows_when_k_not_multiple_of_batch_size(tmp_path):
    logger = SnapshotLogger(tmp_path, CONFIG_HASH, symbol="USDCLP", batch_size=4)
    k = 10  # not a multiple of 4
    for i in range(k):
        logger.log(_make_snapshot(i))
    logger.close()

    path = list((tmp_path / "snapshots" / "USDCLP").glob("*.parquet"))[0]
    df = pd.read_parquet(path)
    assert len(df) == k
    assert list(df["seq"]) == list(range(k))


def test_restart_reopen_resumes_seq_without_clobbering_prior_rows(tmp_path):
    logger1 = SnapshotLogger(tmp_path, CONFIG_HASH, symbol="USDCLP", batch_size=3)
    for i in range(3):
        logger1.log(_make_snapshot(i))
    logger1.close()

    # simulate process restart: brand new logger instance, same symbol/day
    logger2 = SnapshotLogger(tmp_path, CONFIG_HASH, symbol="USDCLP", batch_size=3)
    for i in range(4):
        logger2.log(_make_snapshot(100 + i))
    logger2.close()

    path = list((tmp_path / "snapshots" / "USDCLP").glob("*.parquet"))[0]
    df = pd.read_parquet(path)
    assert len(df) == 3 + 4
    assert list(df["seq"]) == list(range(7))


def test_context_manager_flushes_on_exit(tmp_path):
    with SnapshotLogger(tmp_path, CONFIG_HASH, symbol="USDCLP", batch_size=1000) as logger:
        for i in range(3):
            logger.log(_make_snapshot(i))

    path = list((tmp_path / "snapshots" / "USDCLP").glob("*.parquet"))[0]
    df = pd.read_parquet(path)
    assert len(df) == 3


def test_symbol_can_come_from_snapshot_dict_instead_of_constructor(tmp_path):
    logger = SnapshotLogger(tmp_path, CONFIG_HASH, batch_size=10)
    snap = _make_snapshot(0)
    snap["symbol"] = "XAUUSD"
    logger.log(snap)
    logger.close()

    path = list((tmp_path / "snapshots" / "XAUUSD").glob("*.parquet"))[0]
    df = pd.read_parquet(path)
    assert df.iloc[0]["symbol"] == "XAUUSD"
