"""sentinel_engine.live.deals_watcher — DealsWatcher (B1a-1, NUCLEO).

Polls MT5 deal history into the `deals_raw` table (registry2.py DDL),
guarded by an attach-check so it NEVER calls `mt5.initialize()` (or any
MT5 function) unless the MT5 terminal process is actually running.

Scope (B1a-1 only): attach guard + poll + idempotent upsert by `ticket`.
Attribution (magic -> strategy/ia/human via `magic_allocation`) and
persisting `last_sync` are B1a-2 -- NOT implemented here. `magic` is
stored raw/pass-through.

Windows-safe: no new deps (no psutil) -- the attach guard shells out to
`tasklist` via `os.popen`, same as any other subprocess call, and the
checker is injectable so tests never depend on a real MT5 install.

Real accounts are READ-ONLY: this module only ever calls
`history_deals_get`-shaped read methods on the injected `mt5_client` --
never `order_send` or any trading function.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

from sentinel_engine.research.registry2 import ResearchRegistry

logger = logging.getLogger(__name__)

_DEAL_COLUMNS = (
    "ticket", "position_id", "symbol", "side", "volume",
    "price", "profit", "magic", "time", "entry_type",
)


@dataclass
class WatchReport:
    attached: bool
    deals_seen: int = 0
    upserted: int = 0
    skipped: bool = False


def _terminal_running() -> bool:
    """Default attach-guard checker: True iff `terminal64.exe` shows up in
    `tasklist`'s output for that image name. Shells out via `os.popen`
    (no new deps -- explicitly NOT psutil per task constraints)."""
    output = os.popen('tasklist /FI "IMAGENAME eq terminal64.exe"').read()
    return any("terminal64.exe" in line for line in output.splitlines())


def _map_deal(deal: dict[str, Any]) -> dict[str, Any]:
    """Deal dict -> `deals_raw` row shape. `magic` is passed through raw
    (no attribution/lookup here -- that's B1a-2)."""
    return {col: deal.get(col) for col in _DEAL_COLUMNS}


class DealsWatcher:
    """Polls `mt5_client.history_deals_get` and upserts rows into
    `deals_raw`, guarded so MT5 is never touched unless the terminal
    process is confirmed running."""

    def __init__(
        self,
        registry: ResearchRegistry,
        mt5_client: Any,
        poll_s: int = 5,
        attach_checker: Callable[[], bool] = _terminal_running,
    ):
        self.registry = registry
        self.mt5_client = mt5_client
        self.poll_s = poll_s
        self.attach_checker = attach_checker
        self._last_sync = 0.0

    def poll_once(self) -> WatchReport:
        if not self.attach_checker():
            logger.info("DealsWatcher.poll_once: terminal64.exe not found -- skipping cycle")
            return WatchReport(attached=False, deals_seen=0, upserted=0, skipped=True)

        now = time.time()
        from_ts = self._last_sync - 3600
        deals = self.mt5_client.history_deals_get(from_ts, now)
        self._last_sync = now

        upserted = self._upsert_deals(deals)
        return WatchReport(
            attached=True, deals_seen=len(deals), upserted=upserted, skipped=False
        )

    def _upsert_deals(self, deals: list[dict[str, Any]]) -> int:
        if not deals:
            return 0
        cols = ", ".join(_DEAL_COLUMNS)
        placeholders = ", ".join("?" for _ in _DEAL_COLUMNS)
        conn = self.registry._connect()
        try:
            for deal in deals:
                row = _map_deal(deal)
                conn.execute(
                    f"INSERT OR REPLACE INTO deals_raw({cols}) VALUES ({placeholders})",
                    tuple(row[c] for c in _DEAL_COLUMNS),
                )
            conn.commit()
            return len(deals)
        finally:
            conn.close()
