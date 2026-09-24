"""
P2 Task 2.2 — XTB trade ingester -> schema v1.

NEEDS REAL-SAMPLE VALIDATION (XTB): tested against a FORMAT-ACCURATE
synthetic fixture (no real XTB export exists in this repo)."""
from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_engine.trades.ingest_xtb import XtbCsvFormatError, read_xtb_csv

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "xtb_sample.csv"


def test_read_xtb_csv_produces_valid_schema_v1():
    out = read_xtb_csv(FIXTURE, account="XTB-DEMO-42")
    assert len(out) == 3
    assert set(out["side"]) == {"LONG", "SHORT"}
    assert (out["account"] == "XTB-DEMO-42").all()


def test_read_xtb_csv_maps_buy_sell_to_long_short():
    out = read_xtb_csv(FIXTURE, account="acct")
    row0 = out.iloc[0]
    assert row0["symbol"] == "XAUUSD"
    assert row0["side"] == "LONG"
    row1 = out.iloc[1]
    assert row1["symbol"] == "NQ100"
    assert row1["side"] == "SHORT"


def test_read_xtb_csv_computes_r_multiple_from_sl_distance():
    out = read_xtb_csv(FIXTURE, account="acct")
    row0 = out.iloc[0]
    # risk = |2400.50 - 2390.00| * 0.10 = 1.05 ; pnl = 11.65
    assert row0["r_multiple"] == pytest.approx(11.65 / 1.05, rel=1e-3)


def test_read_xtb_csv_zero_sl_gives_zero_r_multiple():
    out = read_xtb_csv(FIXTURE, account="acct")
    row2 = out.iloc[2]
    assert row2["symbol"] == "USDCLP"
    assert row2["r_multiple"] == 0.0


def test_read_xtb_csv_rejects_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Symbol,Type,Volume\nXAUUSD,BUY,0.1\n", encoding="utf-8")
    with pytest.raises(XtbCsvFormatError):
        read_xtb_csv(bad, account="acct")


def test_read_xtb_csv_rejects_unknown_type(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "Symbol,Type,Volume,Open time,Open price,Close time,Close price,SL,TP,Commission,Swap,Profit\n"
        "XAUUSD,SHORTX,0.1,2026-01-01 09:00:00,2400.5,2026-01-01 10:00:00,2401.0,0,0,0,0,1.0\n",
        encoding="utf-8",
    )
    with pytest.raises(XtbCsvFormatError):
        read_xtb_csv(bad, account="acct")
