"""
sentinel_engine.trades.ingest_xtb — XTB trade-history export -> schema v1 (P2, Task 2.2).

NEEDS REAL-SAMPLE VALIDATION (XTB): no real XTB "Trade history" export exists
in this repo. This adapter targets XTB's documented closed-trades CSV export
column layout (as produced by the XTB / xStation5 web platform's "Export to
CSV" action on the History tab):

    Symbol,Type,Volume,Open time,Open price,Close time,Close price,SL,TP,Commission,Swap,Profit

  - `Type` is "BUY" or "SELL"
  - `Open time` / `Close time`: "YYYY-MM-DD HH:MM:SS"
  - `Profit` is the NET P&L already including commission/swap
  - account id is not present in the export itself (it's a single-account
    report) — supplied by the caller via `account`.

The test in `tests/trades/test_ingest_xtb.py` runs this adapter against a
FORMAT-ACCURATE synthetic fixture (`tests/trades/fixtures/xtb_sample.csv`).
Flagged for validation against a real downloaded sample before being trusted
on live data.

r_multiple: computed as pnl / risk, where risk = abs(open_price - SL) * volume
(the classic "R" unit — distance to stop, in price terms, scaled by size).
Rows with SL == 0 (no stop set) get r_multiple = 0.0 (risk undefined) — this
is a documented approximation, not a broker-reported field.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sentinel_engine.trades.schema import validate_trades

_TYPE_TO_SIDE = {"BUY": "LONG", "SELL": "SHORT"}


class XtbCsvFormatError(ValueError):
    """Raised when an input CSV does not match the expected XTB export shape."""

REQUIRED_COLUMNS = [
    "Symbol", "Type", "Volume", "Open time", "Open price",
    "Close time", "Close price", "SL", "TP", "Profit",
]


def _r_multiple(row: pd.Series) -> float:
    sl = row["SL"]
    if not sl or sl == 0:
        return 0.0
    risk = abs(row["Open price"] - sl) * row["Volume"]
    if risk == 0:
        return 0.0
    return round(row["Profit"] / risk, 4)


def read_xtb_csv(csv_path: Path, account: str) -> pd.DataFrame:
    """Parse an XTB trade-history CSV export into a schema-v1-validated
    DataFrame, tagging every row with `account`."""
    csv_path = Path(csv_path)
    raw = pd.read_csv(csv_path, encoding="utf-8")

    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise XtbCsvFormatError(f"{csv_path}: missing columns {missing}")

    bad_types = set(raw["Type"].unique()) - set(_TYPE_TO_SIDE)
    if bad_types:
        raise XtbCsvFormatError(f"{csv_path}: unknown Type values {sorted(bad_types)}")

    out = pd.DataFrame({
        "account": account,
        "symbol": raw["Symbol"],
        "side": raw["Type"].map(_TYPE_TO_SIDE),
        "open_ts": raw["Open time"],
        "close_ts": raw["Close time"],
        "open_px": raw["Open price"].astype(float),
        "close_px": raw["Close price"].astype(float),
        "size": raw["Volume"].astype(float),
        "pnl": raw["Profit"].astype(float),
    })
    out["r_multiple"] = [
        _r_multiple(pd.Series({
            "SL": raw.loc[i, "SL"],
            "Open price": raw.loc[i, "Open price"],
            "Volume": raw.loc[i, "Volume"],
            "Profit": raw.loc[i, "Profit"],
        }))
        for i in raw.index
    ]

    return validate_trades(out)
