"""
sentinel_engine.trades.schema — Trade schema v1 + validator (P2, Task 2.1).

Schema v1 columns (per the revamp plan §Phase 2 interface contract):
    account, symbol, side, open_ts, close_ts, open_px, close_px, size, pnl, r_multiple

Column semantics:
    account     str   — broker account identifier (never empty)
    symbol      str   — instrument symbol (never empty)
    side        str   — "LONG" or "SHORT"
    open_ts     tz-aware datetime — trade open time
    close_ts    tz-aware datetime — trade close time, >= open_ts
    open_px     float — open price, > 0
    close_px    float — close price, > 0
    size        float — position size, > 0
    pnl         float — realized profit/loss (may be any sign), finite
    r_multiple  float — pnl expressed in R units, finite
"""
from __future__ import annotations

import math

import pandas as pd

TRADE_COLUMNS = [
    "account", "symbol", "side", "open_ts", "close_ts",
    "open_px", "close_px", "size", "pnl", "r_multiple",
]

VALID_SIDES = {"LONG", "SHORT"}


class TradeSchemaError(ValueError):
    """Raised when a trades frame fails schema-v1 validation."""


def validate_trades(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a trades frame against schema v1. Raises `TradeSchemaError`
    with a descriptive message on the FIRST violation found; returns a
    normalized copy (columns ordered per `TRADE_COLUMNS`, timestamps coerced
    to tz-aware UTC datetimes, numeric columns coerced to float) on success.

    Never mutates the input frame.
    """
    missing = [c for c in TRADE_COLUMNS if c not in df.columns]
    if missing:
        raise TradeSchemaError(f"trades frame missing columns: {missing}")

    if len(df) == 0:
        raise TradeSchemaError("trades frame has no rows")

    out = df[TRADE_COLUMNS].copy()

    for col in ("account", "symbol", "side"):
        if out[col].isna().any() or (out[col].astype(str).str.strip() == "").any():
            raise TradeSchemaError(f"column {col!r} has empty/NaN values")

    bad_sides = set(out["side"].unique()) - VALID_SIDES
    if bad_sides:
        raise TradeSchemaError(f"column 'side' has invalid values: {sorted(bad_sides)}")

    for col in ("open_ts", "close_ts"):
        try:
            parsed = pd.to_datetime(out[col], utc=True, errors="raise", format="mixed")
        except (ValueError, TypeError) as exc:
            raise TradeSchemaError(f"column {col!r} has unparseable timestamps") from exc
        if parsed.isna().any():
            raise TradeSchemaError(f"column {col!r} has unparseable timestamps")
        out[col] = parsed

    if (out["close_ts"] < out["open_ts"]).any():
        raise TradeSchemaError("close_ts must be >= open_ts for every row")

    for col in ("open_px", "close_px", "size"):
        try:
            numeric = out[col].astype(float)
        except (ValueError, TypeError) as exc:
            raise TradeSchemaError(f"column {col!r} is not numeric") from exc
        if numeric.isna().any() or not numeric.apply(math.isfinite).all():
            raise TradeSchemaError(f"column {col!r} has NaN/non-finite values")
        if (numeric <= 0).any():
            raise TradeSchemaError(f"column {col!r} must be strictly positive")
        out[col] = numeric

    for col in ("pnl", "r_multiple"):
        try:
            numeric = out[col].astype(float)
        except (ValueError, TypeError) as exc:
            raise TradeSchemaError(f"column {col!r} is not numeric") from exc
        if numeric.isna().any() or not numeric.apply(math.isfinite).all():
            raise TradeSchemaError(f"column {col!r} has NaN/non-finite values")
        out[col] = numeric

    return out.reset_index(drop=True)
