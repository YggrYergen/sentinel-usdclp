"""
P2 Task 2.3 — MT5 trade ingester -> schema v1.

NEEDS REAL-SAMPLE VALIDATION (MT5): tested against a FORMAT-ACCURATE
synthetic MT5 deals-export CSV (the .htm files under MT5_Tester/ are
Strategy-Tester backtest reports, not a clean per-account trade export, so
they aren't a usable real sample here)."""
from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_engine.trades.ingest_mt5_trades import Mt5CsvFormatError, read_mt5_trades_csv

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mt5_trades_sample.csv"


def test_read_mt5_trades_csv_pairs_in_out_deals():
    result = read_mt5_trades_csv(FIXTURE, account="MT5-DEMO-7")
    assert len(result.trades) == 2
    assert (result.trades["account"] == "MT5-DEMO-7").all()


def test_read_mt5_trades_csv_drops_unpaired_position():
    result = read_mt5_trades_csv(FIXTURE, account="acct")
    # Position 1003 only has an "in" deal (still open) -> dropped.
    assert result.dropped_positions == 1
    assert "USDCLP" not in set(result.trades["symbol"])


def test_read_mt5_trades_csv_maps_side_from_opening_deal():
    result = read_mt5_trades_csv(FIXTURE, account="acct")
    xau = result.trades[result.trades["symbol"] == "XAUUSD"].iloc[0]
    assert xau["side"] == "LONG"
    nq = result.trades[result.trades["symbol"] == "NQ100"].iloc[0]
    assert nq["side"] == "SHORT"


def test_read_mt5_trades_csv_pnl_includes_costs():
    result = read_mt5_trades_csv(FIXTURE, account="acct")
    xau = result.trades[result.trades["symbol"] == "XAUUSD"].iloc[0]
    # Profit 11.65 + Commission -0.20 + Fee 0.00 + Swap -0.15 = 11.30
    assert xau["pnl"] == pytest.approx(11.30, abs=1e-6)


def test_read_mt5_trades_csv_rejects_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Time,Deal,Symbol\n2026.01.01 09:00:00,1,XAUUSD\n", encoding="utf-8")
    with pytest.raises(Mt5CsvFormatError):
        read_mt5_trades_csv(bad, account="acct")
