"""sentinel_engine.live.deals_watcher — DealsWatcher (B1a-1 + B1a-2, NUCLEO).

Polls MT5 deal history into the `deals_raw` table (registry2.py DDL),
guarded by an attach-check so it NEVER calls `mt5.initialize()` (or any
MT5 function) unless the MT5 terminal process is actually running.

B1a-1 scope: attach guard + poll + idempotent upsert by `ticket`.

B1a-2 scope (this revision):
  - Attribution: each deal's `magic` is looked up in `magic_allocation`
    (`ResearchRegistry.lookup_magic`) to determine `origin` + the
    `strategy_id`/`variant_id` it belongs to (see `_attribute_magic`):
      * magic assigned in `magic_allocation` -> origin="strategy",
        strategy_id/variant_id from that row.
      * 900000 <= magic <= 900999 (and NOT already allocated) -> origin="ia".
      * anything else -> origin="human".
    `origin`/`strategy_id`/`variant_id` are persisted on `deals_raw`
    (columns added additively by `registry2._migrate_additive`).
  - `last_sync` is now persisted via `ResearchRegistry.get_meta`/`set_meta`
    (key `"deals_watcher.last_sync"`) instead of held only in memory: the
    constructor loads it at startup (0.0 if never set, e.g. an empty
    registry) so a process restart resumes from where it left off; after
    each successful (non-skipped) poll it's updated to `now` (the poll
    time), NOT the max deal `time` seen -- this stays correct even when
    `deals_seen == 0` (nothing to derive a max from) and is simpler/safer
    than trusting broker-clock timestamps for the resume point.

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
    "origin", "strategy_id", "variant_id",
)

_LAST_SYNC_META_KEY = "deals_watcher.last_sync"
_IA_MAGIC_LO = 900000
_IA_MAGIC_HI = 900999


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


def _attribute_magic(registry: ResearchRegistry, magic: Any) -> dict[str, Any]:
    """`magic` -> `{origin, strategy_id, variant_id}` per B1a-2 spec:
    1. If `magic` has a `magic_allocation` row -> origin="strategy" with
       that row's strategy_id/variant_id.
    2. Elif 900000 <= magic <= 900999 -> origin="ia" (strategy_id/variant_id
       stay None -- no strategy/variant owns an IA-origin deal by def.).
    3. Else -> origin="human"."""
    if magic is not None:
        allocation = registry.lookup_magic(magic)
        if allocation is not None:
            return {
                "origin": "strategy",
                "strategy_id": allocation.get("strategy_id"),
                "variant_id": allocation.get("variant_id"),
            }
        if isinstance(magic, int) and _IA_MAGIC_LO <= magic <= _IA_MAGIC_HI:
            return {"origin": "ia", "strategy_id": None, "variant_id": None}
    return {"origin": "human", "strategy_id": None, "variant_id": None}


def _map_deal(registry: ResearchRegistry, deal: dict[str, Any]) -> dict[str, Any]:
    """Deal dict -> `deals_raw` row shape, incl. B1a-2 magic-attribution
    (`origin`/`strategy_id`/`variant_id`)."""
    row = {col: deal.get(col) for col in _DEAL_COLUMNS}
    row.update(_attribute_magic(registry, deal.get("magic")))
    return row


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
        # B1a-2: resume from the persisted last_sync (0.0 if never set --
        # e.g. brand-new registry) instead of always restarting at 0.0.
        persisted = registry.get_meta(_LAST_SYNC_META_KEY)
        self._last_sync = float(persisted) if persisted is not None else 0.0

    @property
    def last_sync(self) -> float:
        return self._last_sync

    def poll_once(self) -> WatchReport:
        if not self.attach_checker():
            logger.info("DealsWatcher.poll_once: terminal64.exe not found -- skipping cycle")
            return WatchReport(attached=False, deals_seen=0, upserted=0, skipped=True)

        now = time.time()
        from_ts = self._last_sync - 3600
        deals = self.mt5_client.history_deals_get(from_ts, now)

        upserted = self._upsert_deals(deals)

        # Persist last_sync = now (poll time), not max(deal.time) -- stays
        # correct even when deals_seen == 0, and avoids trusting the
        # broker-clock `time` field as the resume point.
        self._last_sync = now
        self.registry.set_meta(_LAST_SYNC_META_KEY, str(now))

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
                row = _map_deal(self.registry, deal)
                conn.execute(
                    f"INSERT OR REPLACE INTO deals_raw({cols}) VALUES ({placeholders})",
                    tuple(row[c] for c in _DEAL_COLUMNS),
                )
            conn.commit()
            return len(deals)
        finally:
            conn.close()
