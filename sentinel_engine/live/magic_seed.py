"""sentinel_engine.live.magic_seed -- idempotent `magic_allocation` seeding
(SENTINEL, 2026-07-22). Machine-2's UI/attribution reads `magic_allocation`
(schema: magic PK, strategy_id, variant_id, asignado) to label live deals by
strategy in real time; a config whose magics were never inserted there shows
up unattributed. `ensure_magic_allocations` self-heals that: for each config
in the roster, INSERT-OR-IGNORE a row for magics base+0..base+3 (base itself
plus the F1/F2/F3 ficha offsets), matching the naming convention of the
EXISTING rows already in `data/research.db` (verified by reading them):
  engine tk_*                -> strategy_id "TK::<id>"
  engine supertrend_always_in -> strategy_id "SuperTrend::<id>"
  engine simular_variant (the default/absent-engine key)
                              -> strategy_id "SAR::<id>"
`variant_id` is always `<id>`; `asignado` is left NULL (matches column
nullability -- only `magic`/`strategy_id` are NOT NULL per the schema; the
one hand-seeded example row happens to carry an ISO timestamp there, but
nothing reads it as anything but an optional annotation).

NEVER UPDATE/DELETE an existing row -- `INSERT OR IGNORE`, so a magic
already allocated (by this seeder, a prior run, or by hand) is left
untouched regardless of what it currently says. Read-only from the trading
account's perspective: this only ever touches `data/research.db`'s
`magic_allocation` table, never MT5.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

FICHA_OFFSETS = (0, 1, 2, 3)  # base (F0-ish placeholder) + F1/F2/F3


def _strategy_id(cfg: dict[str, Any]) -> str:
    engine = cfg.get("engine", "simular_variant")
    cid = cfg["id"]
    if engine == "supertrend_always_in":
        return f"SuperTrend::{cid}"
    if engine.startswith("tk_") or engine == "tk":
        return f"TK::{cid}"
    return f"SAR::{cid}"


def ensure_magic_allocations(db_path: str | Path, configs: list[dict[str, Any]]) -> int:
    """INSERT-OR-IGNORE `magic_allocation` rows for magics
    `config["magic"] + offset` (offset in FICHA_OFFSETS) for every config in
    `configs`. Returns the number of rows actually inserted (0 if every
    magic was already allocated). Never UPDATEs or DELETEs an existing row."""
    con = sqlite3.connect(str(db_path))
    try:
        inserted = 0
        for cfg in configs:
            strategy_id = _strategy_id(cfg)
            variant_id = cfg["id"]
            base = cfg["magic"]
            for offset in FICHA_OFFSETS:
                cur = con.execute(
                    "INSERT OR IGNORE INTO magic_allocation "
                    "(magic, strategy_id, variant_id, asignado) VALUES (?, ?, ?, NULL)",
                    (base + offset, strategy_id, variant_id),
                )
                inserted += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        con.commit()
        return inserted
    finally:
        con.close()
