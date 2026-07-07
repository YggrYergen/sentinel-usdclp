"""P2 Task 2.1 — Trade schema v1 + validator."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sentinel_engine.trades.schema import TRADE_COLUMNS, TradeSchemaError, validate_trades

GOOD_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "good_trades.csv"


def _load_good() -> pd.DataFrame:
    return pd.read_csv(GOOD_FIXTURE, encoding="utf-8")


def test_accepts_known_good_fixture():
    df = _load_good()
    out = validate_trades(df)
    assert list(out.columns) == TRADE_COLUMNS
    assert len(out) == 3
    assert pd.api.types.is_datetime64_any_dtype(out["open_ts"])
    assert out["open_ts"].dt.tz is not None


def test_rejects_missing_column():
    df = _load_good().drop(columns=["pnl"])
    with pytest.raises(TradeSchemaError):
        validate_trades(df)


def test_rejects_empty_frame():
    df = _load_good().iloc[0:0]
    with pytest.raises(TradeSchemaError):
        validate_trades(df)


def test_rejects_invalid_side():
    df = _load_good().copy()
    df.loc[0, "side"] = "BUY"
    with pytest.raises(TradeSchemaError):
        validate_trades(df)


def test_rejects_close_before_open():
    df = _load_good().copy()
    df.loc[0, "close_ts"] = "2025-01-01T00:00:00+00:00"
    with pytest.raises(TradeSchemaError):
        validate_trades(df)


def test_rejects_non_positive_size():
    df = _load_good().copy()
    df.loc[0, "size"] = 0
    with pytest.raises(TradeSchemaError):
        validate_trades(df)


def test_rejects_unparseable_timestamp():
    df = _load_good().copy()
    df.loc[0, "open_ts"] = "not-a-date"
    with pytest.raises(TradeSchemaError):
        validate_trades(df)


def test_rejects_non_finite_pnl():
    df = _load_good().copy()
    df.loc[0, "pnl"] = float("nan")
    with pytest.raises(TradeSchemaError):
        validate_trades(df)


def test_rejects_empty_account():
    df = _load_good().copy()
    df.loc[0, "account"] = ""
    with pytest.raises(TradeSchemaError):
        validate_trades(df)
