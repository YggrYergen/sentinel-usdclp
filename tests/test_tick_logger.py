"""
Tests for sentinel.logging.tick_logger.TickLogger

Covers:
- basic write + schema/round-trip
- batching does not lose data (N not a multiple of batch size)
- restart/reopen append (no clobber)
- date-boundary rollover into separate dated files
All I/O happens under pytest's tmp_path — never the repo's real logs/.
"""
from datetime import datetime, timezone, timedelta

import pandas as pd
import pytest

from sentinel.logging.tick_logger import TickLogger


def _dt(y, m, d, hh=10, mm=0, ss=0, micro=0):
    return datetime(y, m, d, hh, mm, ss, micro, tzinfo=timezone.utc)


def test_logs_n_ticks_to_dated_parquet_with_correct_schema(tmp_path):
    logger = TickLogger("USDCLP", tmp_path, batch_size=5)
    ts0 = _dt(2026, 7, 7, 10, 0, 0)
    n = 5
    for i in range(n):
        logger.on_tick(ts0 + timedelta(seconds=i), 950.10 + i, 950.20 + i)
    logger.close()

    expected_path = tmp_path / "ticks" / "USDCLP" / "2026-07-07.parquet"
    assert expected_path.exists()

    df = pd.read_parquet(expected_path)
    assert len(df) == n
    assert list(df.columns) == ["ts", "bid", "ask", "spread"]

    for i in range(n):
        row = df.iloc[i]
        assert row["bid"] == pytest.approx(950.10 + i)
        assert row["ask"] == pytest.approx(950.20 + i)
        assert row["spread"] == pytest.approx(row["ask"] - row["bid"])


def test_batching_does_not_lose_data_when_n_not_multiple_of_batch_size(tmp_path):
    logger = TickLogger("USDCLP", tmp_path, batch_size=4)
    ts0 = _dt(2026, 7, 7, 11, 0, 0)
    n = 10  # not a multiple of 4
    for i in range(n):
        logger.on_tick(ts0 + timedelta(seconds=i), 1.0 + i, 1.1 + i)
    logger.flush()
    logger.close()

    path = tmp_path / "ticks" / "USDCLP" / "2026-07-07.parquet"
    df = pd.read_parquet(path)
    assert len(df) == n


def test_restart_reopen_appends_without_clobbering_prior_rows(tmp_path):
    ts0 = _dt(2026, 7, 7, 12, 0, 0)

    logger1 = TickLogger("USDCLP", tmp_path, batch_size=3)
    for i in range(3):
        logger1.on_tick(ts0 + timedelta(seconds=i), 2.0 + i, 2.1 + i)
    logger1.close()

    # simulate process restart: brand new logger instance, same symbol/day
    logger2 = TickLogger("USDCLP", tmp_path, batch_size=3)
    for i in range(4):
        logger2.on_tick(ts0 + timedelta(seconds=100 + i), 3.0 + i, 3.1 + i)
    logger2.close()

    path = tmp_path / "ticks" / "USDCLP" / "2026-07-07.parquet"
    df = pd.read_parquet(path)
    assert len(df) == 3 + 4


def test_date_boundary_rollover_creates_two_dated_files(tmp_path):
    logger = TickLogger("USDCLP", tmp_path, batch_size=100)
    day1 = _dt(2026, 7, 7, 23, 59, 59)
    day2 = _dt(2026, 7, 8, 0, 0, 1)
    logger.on_tick(day1, 950.0, 950.1)
    logger.on_tick(day2, 951.0, 951.1)
    logger.close()

    path1 = tmp_path / "ticks" / "USDCLP" / "2026-07-07.parquet"
    path2 = tmp_path / "ticks" / "USDCLP" / "2026-07-08.parquet"
    assert path1.exists()
    assert path2.exists()

    df1 = pd.read_parquet(path1)
    df2 = pd.read_parquet(path2)
    assert len(df1) == 1
    assert len(df2) == 1


def test_context_manager_flushes_on_exit(tmp_path):
    ts0 = _dt(2026, 7, 7, 13, 0, 0)
    with TickLogger("USDCLP", tmp_path, batch_size=1000) as logger:
        for i in range(3):
            logger.on_tick(ts0 + timedelta(seconds=i), 1.0, 1.1)

    path = tmp_path / "ticks" / "USDCLP" / "2026-07-07.parquet"
    assert path.exists()
    df = pd.read_parquet(path)
    assert len(df) == 3


def test_accepts_epoch_timestamp(tmp_path):
    logger = TickLogger("USDCLP", tmp_path, batch_size=10)
    epoch_ts = _dt(2026, 7, 7, 14, 0, 0).timestamp()
    logger.on_tick(epoch_ts, 1.0, 1.1)
    logger.close()

    path = tmp_path / "ticks" / "USDCLP" / "2026-07-07.parquet"
    assert path.exists()
    df = pd.read_parquet(path)
    assert len(df) == 1
