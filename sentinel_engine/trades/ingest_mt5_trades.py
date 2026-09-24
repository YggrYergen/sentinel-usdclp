"""
sentinel_engine.trades.ingest_mt5_trades — MT5 deals-history export -> schema v1 (P2, Task 2.3).

NEEDS REAL-SAMPLE VALIDATION (MT5): the `.htm` reports under `MT5_Tester/`
are MT5 Strategy-Tester backtest reports, not a clean per-account trade
export, so they are not usable as a real sample here. This adapter targets
MT5's documented "Deals" history CSV export (Terminal → History tab → Export
to CSV), which lists one row PER DEAL (an "in" deal opens a position, an
"out" deal closes it) rather than one row per round-trip trade:

    Time,Deal,Symbol,Type,Direction,Volume,Price,Order,Commission,Fee,Swap,Profit,Comment,Position

  - `Direction` is "in" or "out"; `Type` is "buy" or "sell" (of the deal,
    not necessarily the position — an "out" deal on a long position is a
    sell)
  - `Position` is the position ticket shared by the in/out deal pair — used
    here to pair them into one round-trip trade
  - `Profit`/`Commission`/`Fee`/`Swap` are all populated on the OUT deal
    (zero on the IN deal), matching real MT5 export behavior

This module pairs deals by `Position`, keeping only positions with exactly
one "in" and one "out" deal (partial closes / multi-fill positions are out
of scope for v1 — rows with any other deal count per position are dropped
and reported via the returned `dropped_positions` count for caller logging).

The test in `tests/trades/test_ingest_mt5_trades.py` runs this adapter
against a FORMAT-ACCURATE synthetic fixture
(`tests/trades/fixtures/mt5_trades_sample.csv`). Flagged for validation
against a real downloaded export before being trusted on live data.

r_multiple: MT5 deal exports do not carry SL/TP on the deal rows themselves,
so r_multiple is computed the same way as the XTB adapter would if no SL
were available: NOT derivable from this export alone -> set to 0.0
(documented approximation; a future task could join against the SL/TP
recorded on the opening ORDER, not the deal, if that data becomes
available).
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pandas as pd

from sentinel_engine.trades.schema import validate_trades

_TYPE_TO_SIDE = {"buy": "LONG", "sell": "SHORT"}

REQUIRED_COLUMNS = [
    "Time", "Deal", "Symbol", "Type", "Direction", "Volume", "Price",
    "Order", "Commission", "Fee", "Swap", "Profit", "Position",
]


class Mt5CsvFormatError(ValueError):
    """Raised when an input CSV does not match the expected MT5 deals-export shape."""


class Mt5TradesResult(NamedTuple):
    trades: pd.DataFrame
    dropped_positions: int


def read_mt5_trades_csv(csv_path: Path, account: str) -> Mt5TradesResult:
    """Parse an MT5 deals-history CSV export, pair in/out deals by
    `Position`, and return schema-v1-validated round-trip trades tagged with
    `account`. Positions that don't have exactly one in-deal + one out-deal
    are dropped (count reported in `dropped_positions`)."""
    csv_path = Path(csv_path)
    raw = pd.read_csv(csv_path, encoding="utf-8")

    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise Mt5CsvFormatError(f"{csv_path}: missing columns {missing}")

    bad_dir = set(raw["Direction"].str.lower().unique()) - {"in", "out"}
    if bad_dir:
        raise Mt5CsvFormatError(f"{csv_path}: unknown Direction values {sorted(bad_dir)}")

    raw = raw.copy()
    raw["Direction"] = raw["Direction"].str.lower()
    raw["Type"] = raw["Type"].str.lower()

    bad_types = set(raw["Type"].unique()) - set(_TYPE_TO_SIDE)
    if bad_types:
        raise Mt5CsvFormatError(f"{csv_path}: unknown Type values {sorted(bad_types)}")

    rows = []
    dropped = 0
    for position, group in raw.groupby("Position"):
        ins = group[group["Direction"] == "in"]
        outs = group[group["Direction"] == "out"]
        if len(ins) != 1 or len(outs) != 1:
            dropped += 1
            continue
        in_row = ins.iloc[0]
        out_row = outs.iloc[0]
        # Side of the POSITION is the side of the opening ("in") deal.
        side = _TYPE_TO_SIDE[in_row["Type"]]
        pnl = float(out_row["Profit"]) + float(out_row["Commission"]) + float(out_row["Fee"]) + float(out_row["Swap"])
        rows.append({
            "account": account,
            "symbol": in_row["Symbol"],
            "side": side,
            "open_ts": in_row["Time"],
            "close_ts": out_row["Time"],
            "open_px": float(in_row["Price"]),
            "close_px": float(out_row["Price"]),
            "size": float(in_row["Volume"]),
            "pnl": pnl,
            "r_multiple": 0.0,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        raise Mt5CsvFormatError(f"{csv_path}: no complete in/out position pairs found")

    validated = validate_trades(out)
    return Mt5TradesResult(trades=validated, dropped_positions=dropped)
