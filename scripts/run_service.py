"""
scripts/run_service.py — local launcher for the SENTINEL FastAPI service.

Wires `sentinel_engine.service.app.create_app` to a real `Feed`:
  - Prefers LIVE: wraps `sentinel.data_feed.DataFeed` (which itself tries
    MT5 first) in `sentinel_engine.feed.LiveMT5Feed` when the MT5 terminal
    is reachable and connected.
  - Falls back to HISTORICAL replay over the Parquet lake
    (`sentinel_engine.feed_historical.HistoricalFeed`) at a fixed recent
    `as_of` timestamp when MT5 is not connected — this works even when the
    market is closed or no terminal is running.

READ-ONLY: this script never imports or calls any MT5 order/trade function.
It only ever reads prices/candles/positions via the existing DataFeed /
HistoricalFeed wrappers.

Usage (PowerShell or bash):
    python scripts/run_service.py
    python scripts/run_service.py --host 127.0.0.1 --port 8501
    python scripts/run_service.py --force-historical

Then open http://127.0.0.1:8501 in a browser.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from sentinel_engine.feed import Feed, LiveMT5Feed
from sentinel_engine.feed_historical import HistoricalFeed
from sentinel_engine.service.app import DEFAULT_INSTRUMENTS, create_app

logger = logging.getLogger("sentinel.run_service")

REPO_ROOT = Path(__file__).resolve().parents[1]
LAKE_ROOT = REPO_ROOT / "data" / "lake"

# Fixed recent as_of used for the historical fallback — must be inside the
# lake's covered window (checked at runtime by simply trying; HistoricalFeed
# just returns empty frames if there is no data at/before this timestamp for
# a given symbol, it never raises for an out-of-range as_of by itself).
HISTORICAL_AS_OF = datetime(2026, 7, 7, 18, 0, 0, tzinfo=timezone.utc)


def _try_build_live_feed() -> Feed | None:
    """Return a LiveMT5Feed if the MT5 terminal is reachable and connected,
    else None. Never raises — any failure just means "not live"."""
    try:
        from sentinel.data_feed import DataFeed
    except Exception as exc:  # pragma: no cover - import-time failures only
        logger.warning("Could not import sentinel.data_feed.DataFeed: %s", exc)
        return None

    try:
        df = DataFeed(mode="auto")
    except Exception as exc:
        logger.warning("DataFeed() construction failed: %s", exc)
        return None

    if not getattr(df, "mt5_connected", False):
        logger.info("MT5 not connected (DataFeed fell back to Yahoo/offline).")
        return None

    logger.info("MT5 connected — using LIVE feed.")
    return LiveMT5Feed(df)


def build_feed_factory(force_historical: bool = False):
    """Build one `feed_factory(instrument_name) -> Feed` shared across all
    instruments. Live feed (if available) is a single shared DataFeed
    instance wrapped once; historical feed is one shared HistoricalFeed
    instance (its own `_symbols` default covers USDCLP macro basket, but the
    engine only calls `get_data`/`get_current_price` per-symbol, so a single
    shared instance across instruments is fine — it lazily loads+caches
    whatever symbol/timeframe pair is actually requested)."""
    live_feed: Feed | None = None if force_historical else _try_build_live_feed()

    if live_feed is not None:
        def _factory(_name: str) -> Feed:
            return live_feed
        return _factory, "live"

    logger.info(
        "Falling back to HISTORICAL replay feed over %s (as_of=%s).",
        LAKE_ROOT, HISTORICAL_AS_OF.isoformat(),
    )
    historical_feed = HistoricalFeed(LAKE_ROOT, HISTORICAL_AS_OF)

    def _factory(_name: str) -> Feed:
        return historical_feed

    return _factory, "historical"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SENTINEL local web service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument(
        "--force-historical",
        action="store_true",
        help="Skip the MT5 live-feed attempt and always use HistoricalFeed over data/lake.",
    )
    parser.add_argument(
        "--instruments",
        default=",".join(DEFAULT_INSTRUMENTS),
        help="Comma-separated instrument names (default: usdclp,gold,nasdaq).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    instruments = tuple(s.strip() for s in args.instruments.split(",") if s.strip())
    feed_factory, kind = build_feed_factory(force_historical=args.force_historical)
    logger.info("Feed kind selected: %s", kind)

    # autostart_news_poller is opt-in (default False so tests/offline
    # harnesses never fetch the network) — the real service DOES poll.
    app = create_app(
        feed_factory=feed_factory,
        instruments=instruments,
        autostart_news_poller=True,
    )

    logger.info("Starting SENTINEL service on http://%s:%s (feed=%s)", args.host, args.port, kind)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
