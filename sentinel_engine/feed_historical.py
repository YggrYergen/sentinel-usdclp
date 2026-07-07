"""
sentinel_engine.feed_historical — HistoricalFeed(lake, as_of): point-in-time
replay over the Parquet lake, implementing the `Feed` protocol (P2, Task 2.6).

THE 2-STRIKES PROVING GROUND: every accessor here filters to `ts <= as_of`
BEFORE any further computation (tail/slicing/tick advancement). No field
returned by any method may ever be derived from a row with `time > as_of` —
see `tests/lake/test_historical_feed.py::test_leakage_*` for the exhaustive
gate. If in doubt, filter first, compute second.

`get_current_price` mirrors `tests/golden/fake_feed.FakeFeed`'s deterministic
tick-advance behavior (see that module's docstring) but constrained to the
`ts <= as_of` window: each call advances one step through the symbol's M1
close series *restricted to bars at-or-before as_of*, wrapping within that
restricted window. This makes `HistoricalFeed(lake, as_of=<last bar's ts>)`
behaviorally IDENTICAL to `FakeFeed` fed from the same underlying data (used
by the Task 2.8 replayer-equivalence test), while never exposing a future
bar for any `as_of` strictly before the last bar.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from sentinel_engine.lake.store import read_bars

SPREAD_PCT = 0.0002


class HistoricalFeed:
    """Point-in-time replay Feed over a Parquet lake. Read-only; never
    mutates the lake and never places orders (satisfies the same read-only
    contract as `sentinel_engine.feed.LiveMT5Feed`)."""

    def __init__(self, lake_root: Path, as_of: datetime, symbols: dict[str, str] | None = None):
        if as_of.tzinfo is None:
            raise ValueError("HistoricalFeed: as_of must be tz-aware")
        self._lake_root = Path(lake_root)
        self._as_of = pd.Timestamp(as_of).tz_convert("UTC")
        self._cache: dict[tuple[str, int], pd.DataFrame] = {}
        self._tick_idx: dict[str, int] = {}
        if symbols is None:
            from sentinel.config import SYMBOLS as _DEFAULT_SYMBOLS
            symbols = _DEFAULT_SYMBOLS
        self._symbols = symbols

    # ── internal: leakage-safe loader ────────────────────────────────
    def _load(self, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
        key = (symbol, timeframe_minutes)
        if key in self._cache:
            return self._cache[key]
        df = read_bars(self._lake_root, symbol, timeframe_minutes)
        if not df.empty:
            # THE leakage gate: filter to ts <= as_of before anything else
            # ever touches this frame.
            df = df[df.index <= self._as_of]
        self._cache[key] = df
        return df

    # ── public API (Feed protocol) ───────────────────────────────────
    def get_data(self, symbol: str, timeframe_minutes: int = 15,
                 bars: int = 200) -> pd.DataFrame:
        df = self._load(symbol, timeframe_minutes)
        if df.empty:
            return df
        return df.tail(bars)

    def get_current_price(self, symbol: str) -> dict:
        df1 = self._load(symbol, 1)
        if df1.empty:
            return {"bid": 0, "ask": 0, "spread": 0, "time": None, "source": "historical"}

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
            "source": "historical",
        }

    def get_all_data(self, timeframe_minutes: int = 15,
                      bars: int = 200) -> dict:
        all_data = {}
        for key, symbol in self._symbols.items():
            df = self.get_data(symbol, timeframe_minutes, bars)
            if not df.empty:
                all_data[key] = df
        return all_data

    def positions(self) -> list:
        """Historical replay never has live open positions — always []."""
        return []

    def now(self) -> datetime:
        return self._as_of.to_pydatetime()

    # ── introspection helper (not part of the Feed protocol) ─────────
    @property
    def as_of(self) -> pd.Timestamp:
        return self._as_of
