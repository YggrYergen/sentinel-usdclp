"""
sentinel_engine.feed — the data-access contract scoring engines consume (P1, Task 1.3).

`Feed` is a structural (typing.Protocol) contract describing exactly the
subset of `sentinel.data_feed.DataFeed`'s public API that the scoring
paths (`sentinel_engine.macro.MacroScorer`, and later the technical
scorer) actually call. `tests/golden/fake_feed.py`'s `FakeFeed` already
satisfies the data-access part of this contract structurally (Protocol
is duck-typed — no inheritance required).

`LiveMT5Feed` is a THIN, READ-ONLY adapter around a `sentinel.data_feed.DataFeed`
instance. It delegates every data call straight through and NEVER places
or modifies orders — `positions()` only reads open MT5 positions (if the
wrapped feed is MT5-connected), mapped to plain dicts.
"""
from __future__ import annotations

import typing
from datetime import datetime, timezone

import pandas as pd


class Feed(typing.Protocol):
    """Structural contract for anything the scoring engines can read from.

    Any object exposing these five methods with matching signatures
    satisfies this Protocol — including `tests/golden/fake_feed.FakeFeed`,
    without it needing to import or inherit from this module.
    """

    def get_data(self, symbol: str, timeframe_minutes: int = 15,
                 bars: int = 200) -> pd.DataFrame:
        ...

    def get_current_price(self, symbol: str) -> dict:
        ...

    def get_all_data(self, timeframe_minutes: int = 15,
                      bars: int = 200) -> dict:
        ...

    def positions(self) -> list:
        ...

    def now(self) -> datetime:
        ...


class LiveMT5Feed:
    """Read-only adapter wrapping a `sentinel.data_feed.DataFeed` instance
    so it satisfies the `Feed` protocol.

    ⚠️ SOLO LECTURA — never places, modifies, or cancels orders. `positions()`
    only reads open MT5 positions via `positions_get()` when the wrapped
    feed is MT5-connected; otherwise it returns `[]`.
    """

    def __init__(self, data_feed):
        self._feed = data_feed

    # ── data delegation (straight passthrough) ──────────────────────
    def get_data(self, symbol: str, timeframe_minutes: int = 15,
                 bars: int = 200) -> pd.DataFrame:
        return self._feed.get_data(symbol, timeframe_minutes, bars)

    def get_current_price(self, symbol: str) -> dict:
        return self._feed.get_current_price(symbol)

    def get_all_data(self, timeframe_minutes: int = 15,
                      bars: int = 200) -> dict:
        return self._feed.get_all_data(timeframe_minutes, bars)

    # ── later-phase methods ──────────────────────────────────────────
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def positions(self) -> list:
        """Read-only view of open MT5 positions, mapped to plain dicts.
        Returns [] if the wrapped feed isn't MT5-connected or the
        positions API isn't available — never raises, never trades."""
        mt5 = getattr(self._feed, "_mt5", None)
        connected = getattr(self._feed, "mt5_connected", False)
        if not connected or mt5 is None:
            return []
        try:
            raw = mt5.positions_get()
        except Exception:
            return []
        if not raw:
            return []
        result = []
        for p in raw:
            if hasattr(p, "_asdict"):
                result.append(dict(p._asdict()))
            else:
                result.append(dict(p))
        return result
