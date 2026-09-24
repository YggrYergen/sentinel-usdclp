"""scripts/dev/e2e_service.py — ORC-5 e2e service launcher (headless browser checklist).

Same wiring as `scripts/run_service.py --force-historical`, EXCEPT the
registry: the real `data/research.db` is COPIED to a temp path and the
service runs on the copy, seeded with a handful of synthetic `deals_raw`
rows so the Positions UI (HUMANO / IA tabs, groups, panel, VWAP) has data
to render. The real registry is never written; backtest jobs launched
during the e2e land in the copy and are discarded with it.

READ-ONLY with respect to real data: lake is only read; data/research.db
is only copied.

Usage:
    python scripts/dev/e2e_service.py [--port 8611]
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(REPO_ROOT))

from scripts.run_service import HISTORICAL_AS_OF, LAKE_ROOT  # noqa: E402
from sentinel_engine.feed_historical import HistoricalFeed  # noqa: E402
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402
from sentinel_engine.service.app import DEFAULT_INSTRUMENTS, create_app  # noqa: E402

logger = logging.getLogger("sentinel.e2e_service")

_DEAL_COLUMNS = (
    "ticket", "position_id", "symbol", "side", "volume", "price", "profit",
    "magic", "time", "entry_type", "origin", "strategy_id", "variant_id",
    "leverage", "contract_size",
)


def _seed_deals(registry: ResearchRegistry) -> None:
    """Synthetic deals shaped like DealsWatcher rows: one open HUMANO
    position, one multi-lot closed HUMANO group (VWAP), one closed IA
    position with margin inputs (pct computed)."""
    as_of = int(HISTORICAL_AS_OF.timestamp())
    h = 3600

    def d(ticket, position_id, side, volume, price, profit, magic, time, entry_type,
          origin, strategy_id=None, variant_id=None, leverage=None, contract_size=None):
        return (ticket, position_id, "XAUUSD", side, volume, price, profit, magic,
                time, entry_type, origin, strategy_id, variant_id, leverage, contract_size)

    deals = [
        # pos 9100: HUMANO, still open (IN only).
        d(91001, 9100, "buy", 0.10, 3305.0, 0.0, 0, as_of - 26 * h, "IN", "human",
          leverage=100, contract_size=100),
        # pos 9200 + 9201: HUMANO multi-lot group (same magic, overlapping) -> group card + VWAP.
        d(92001, 9200, "buy", 0.20, 3300.0, 0.0, 777, as_of - 30 * h, "IN", "human",
          leverage=100, contract_size=100),
        # grouping clusters entries within 90s of each other (same symbol+side+magic)
        d(92002, 9201, "buy", 0.10, 3302.0, 0.0, 777, as_of - 30 * h + 60, "IN", "human",
          leverage=100, contract_size=100),
        d(92003, 9200, "buy", 0.20, 3312.0, 240.0, 777, as_of - 27 * h, "OUT", "human"),
        d(92004, 9201, "buy", 0.10, 3315.0, 130.0, 777, as_of - 26 * h, "OUT", "human"),
        # pos 9300: IA, closed, margin inputs present -> pct computed.
        d(93001, 9300, "sell", 0.50, 3320.0, 0.0, 424242, as_of - 28 * h, "IN", "ia",
          strategy_id="emasar", variant_id="emasar_XAUUSD_M2_orig_sar3m3_repro",
          leverage=100, contract_size=100),
        d(93002, 9300, "sell", 0.50, 3308.0, 600.0, 424242, as_of - 25 * h, "OUT", "ia"),
    ]
    cols = ", ".join(_DEAL_COLUMNS)
    placeholders = ", ".join("?" for _ in _DEAL_COLUMNS)
    conn = sqlite3.connect(registry.db_path)
    try:
        conn.executemany(f"INSERT INTO deals_raw({cols}) VALUES ({placeholders})", deals)
        conn.commit()
    finally:
        conn.close()
    logger.info("Seeded %d synthetic deals into the e2e registry copy.", len(deals))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SENTINEL e2e service (ORC-5).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8611)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    real_db = REPO_ROOT / "data" / "research.db"
    tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-e2e-"))
    e2e_db = tmp_dir / "research_e2e.db"
    shutil.copy2(real_db, e2e_db)
    logger.info("Registry copy: %s -> %s", real_db, e2e_db)

    registry = ResearchRegistry(e2e_db)
    _seed_deals(registry)

    historical_feed = HistoricalFeed(LAKE_ROOT, HISTORICAL_AS_OF)
    app = create_app(
        feed_factory=lambda _name: historical_feed,
        instruments=DEFAULT_INSTRUMENTS,
        registry=registry,
        lake_root=LAKE_ROOT,
    )
    logger.info("Starting e2e service on http://%s:%s (historical, as_of=%s)",
                args.host, args.port, HISTORICAL_AS_OF.isoformat())
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
