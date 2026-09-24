"""
FakeFeed — deterministic, CSV-backed stand-in for sentinel.data_feed.DataFeed.

Implements exactly the subset of the DataFeed public API the scoring
paths call:
    get_data(symbol, timeframe_minutes, bars) -> DataFrame
    get_current_price(symbol) -> dict
    get_all_data(timeframe_minutes, bars) -> dict
    get_symbol_info(symbol) -> dict

No network, no MT5, no yfinance. Reads ONLY committed fixture CSVs
(never regenerates data). `get_current_price` derives bid/ask from a
per-symbol pointer that advances deterministically through the M1
close series each time it is called — this lets a fixed number of
`update_tick` / `_update_macro` cycles produce a reproducible non-zero
returns sequence (required to warm up the MacroScorer's EWMA tracker).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

FIXTURES_CSV_ROOT = Path(__file__).resolve().parent / "fixtures" / "csv"

# Fixed spread expressed as a fraction of price — deterministic, no
# randomness, no wall-clock.
SPREAD_PCT = 0.0002


class FakeFeed:
    """Deterministic replacement for DataFeed, backed by committed CSVs."""

    def __init__(self, csv_root: Path = FIXTURES_CSV_ROOT):
        self._csv_root = Path(csv_root)
        self._data: dict[tuple[str, int], pd.DataFrame] = {}
        self._tick_idx: dict[str, int] = {}

    # ── internal loader ──────────────────────────────────────────────
    def _load(self, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
        key = (symbol, timeframe_minutes)
        if key in self._data:
            return self._data[key]
        path = self._csv_root / symbol / f"{timeframe_minutes}.csv"
        if not path.exists():
            df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        else:
            df = pd.read_csv(path, index_col=0, parse_dates=True, encoding="utf-8")
            df.index.name = "time"
        self._data[key] = df
        return df

    # ── public API (mirrors DataFeed) ────────────────────────────────
    def get_data(self, symbol: str, timeframe_minutes: int = 15,
                 bars: int = 200) -> pd.DataFrame:
        df = self._load(symbol, timeframe_minutes)
        if df.empty:
            return df
        return df.tail(bars)

    def get_current_price(self, symbol: str) -> dict:
        """Deterministic tick: each call advances one step through the
        symbol's M1 close series (wrapping if exhausted)."""
        df1 = self._load(symbol, 1)
        if df1.empty:
            return {"bid": 0, "ask": 0, "spread": 0, "time": None, "source": "fake"}

        idx = self._tick_idx.get(symbol, 0)
        n = len(df1)
        i = idx % n
        self._tick_idx[symbol] = idx + 1

        bid = float(df1["close"].iloc[i])
        spread = round(bid * SPREAD_PCT, 6)
        return {
            "bid": bid,
            "ask": bid + spread,
            "spread": spread,
            "time": None,
            "source": "fake",
        }

    def get_symbol_info(self, symbol: str) -> dict:
        return {"name": symbol, "point": 0.01, "digits": 2}

    def get_all_data(self, timeframe_minutes: int = 15,
                      bars: int = 200) -> dict:
        """Matches DataFeed.get_all_data: always keyed off sentinel.config.SYMBOLS
        (the USDCLP/target group) regardless of which instrument is being
        captured — this mirrors production behavior exactly."""
        from sentinel.config import SYMBOLS
        all_data = {}
        for key, symbol in SYMBOLS.items():
            df = self.get_data(symbol, timeframe_minutes, bars)
            if not df.empty:
                all_data[key] = df
        return all_data
