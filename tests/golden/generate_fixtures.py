"""
SENTINEL golden-master harness — fixture generator.

Generates DETERMINISTIC synthetic OHLCV CSV fixtures (seeded random walk,
no network/MT5/yfinance) for every (symbol, timeframe) pair the three
target instruments' scoring paths read from a `DataFeed`.

This script is run ONCE (or whenever fixtures need regenerating) to
produce the committed CSVs under tests/golden/fixtures/csv/<symbol>/<tf>.csv.
`capture_golden.py` NEVER regenerates data on the fly — it only reads
these committed files via FakeFeed.

Run:
    python -m tests.golden.generate_fixtures
"""
from __future__ import annotations

import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from sentinel.config import (
    SYMBOLS, SYMBOLS_GOLD, SYMBOLS_NASDAQ,
)

FIXTURES_CSV_ROOT = Path(__file__).resolve().parent / "fixtures" / "csv"

# Fixed reference epoch — never wall-clock derived, so regenerating
# fixtures from scratch is itself reproducible.
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Bars to generate per timeframe (comfortably covers every consumer:
# technical scorer BARS_TO_FETCH=200, correlation CORRELATION_WINDOW
# lookback of 200, levels engine's daily/M15/M5 needs, and the macro
# scorer's tick-advancement loop of ~35 update cycles on M1).
BARS_BY_TF = {
    1: 250,
    2: 200,
    5: 200,
    15: 200,
    60: 200,
    1440: 15,
}

# Plausible starting price per MT5 symbol (only affects readability of
# the fixture; scoring logic only cares about relative movement).
START_PRICE = {
    "USDCLP": 950.0,
    "USDX_Jun26": 104.0,
    "Cobre_Jul26": 4.50,
    "WTI": 68.0,
    "USDMXN": 18.5,
    "USDBRL": 5.6,
    "AUDUSD": 0.65,
    "USDCNH": 7.2,
    "SP": 5500.0,
    "XAUUSD": 2400.0,
    "XAGUSD": 29.0,
    "VIX_Jun26": 15.0,
    "EURUSD": 1.08,
    "USDJPY": 155.0,
    "NQ100": 19000.0,
    "BTCUSD": 65000.0,
}


def _seed_for(symbol: str, tf: int) -> int:
    """Stable seed derived from symbol+timeframe (NOT python hash(), which
    is randomized per-process for strings unless PYTHONHASHSEED is fixed)."""
    return zlib.crc32(f"{symbol}_{tf}".encode("utf-8")) & 0xFFFFFFFF


def generate_ohlcv(symbol: str, tf_minutes: int, n_bars: int) -> pd.DataFrame:
    """Deterministic synthetic OHLCV random walk for (symbol, timeframe)."""
    seed = _seed_for(symbol, tf_minutes)
    rng = np.random.default_rng(seed)
    start_price = START_PRICE.get(symbol, 100.0)

    vol = 0.0015  # per-bar log-return volatility
    log_returns = rng.normal(loc=0.0, scale=vol, size=n_bars)
    closes = start_price * np.exp(np.cumsum(log_returns))

    opens = np.empty(n_bars)
    opens[0] = start_price
    opens[1:] = closes[:-1]

    # Intrabar noise for high/low, always enclosing open/close.
    intrabar = np.abs(rng.normal(loc=0.0006, scale=0.0006, size=n_bars))
    highs = np.maximum(opens, closes) * (1 + intrabar)
    lows = np.minimum(opens, closes) * (1 - intrabar)

    volumes = rng.integers(low=100, high=5000, size=n_bars)

    idx = pd.DatetimeIndex(
        [EPOCH + timedelta(minutes=tf_minutes * i) for i in range(n_bars)]
    )

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        },
        index=idx,
    )
    df.index.name = "time"
    return df


def required_symbol_tfs() -> dict[str, set[int]]:
    """Build the exact (symbol -> set(timeframes)) map every capture path
    needs, derived directly from sentinel.config so it can never drift
    from the real scoring code's data requirements."""
    req: dict[str, set[int]] = {}

    def add(symbol: str, tfs: set[int]):
        req.setdefault(symbol, set()).update(tfs)

    target_tfs = {1, 2, 5, 15, 1440}
    asset_tfs = {1}

    # USDCLP — also needs tf=60 (correlation_engine's get_all_data window)
    # for the target AND every cross-asset (SentinelCore.calculate_composite
    # calls feed.get_all_data(timeframe_minutes=60, bars=200) over ALL
    # SYMBOLS values, target included).
    for key, symbol in SYMBOLS.items():
        tfs = (target_tfs if key == "target" else asset_tfs) | {60}
        add(symbol, tfs)

    # Gold / NASDAQ — instrument_panel path never calls correlation_engine.
    for cfg in (SYMBOLS_GOLD, SYMBOLS_NASDAQ):
        for key, symbol in cfg.items():
            tfs = target_tfs if key == "target" else asset_tfs
            add(symbol, tfs)

    return req


def write_fixtures(root: Path = FIXTURES_CSV_ROOT) -> None:
    req = required_symbol_tfs()
    for symbol, tfs in sorted(req.items()):
        symbol_dir = root / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        for tf in sorted(tfs):
            n_bars = BARS_BY_TF[tf]
            df = generate_ohlcv(symbol, tf, n_bars)
            out_path = symbol_dir / f"{tf}.csv"
            df.to_csv(out_path, encoding="utf-8")


if __name__ == "__main__":
    write_fixtures()
    print(f"Wrote fixtures under {FIXTURES_CSV_ROOT}")
