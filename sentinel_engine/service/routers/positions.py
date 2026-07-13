"""sentinel_engine.service.routers.positions — GET /api/positions (B3-api).

Reads `deals_raw` rows from the registry (`research/registry2.py`),
optionally filtered by `origin`/`symbol`, and groups them into
`PositionGroup`s via `sentinel_engine.live.grouping.group_positions`
(reused verbatim, not reimplemented). `pct` is always null for now
(leverage/contract_size inputs aren't captured yet — B1c). `mae`/`mfe`
come back null with `needs_excursions=True` straight from the grouping
module; passed through as-is.

`_build_router(registry)` follows the same lazy-registry pattern as
`routers/strategies.py`; `app.py` calls it once at `create_app()` time.

Known hazard (review, in progress by another agent): `grouping._build_positions`
raises `StopIteration` via `next(...)` when a `position_id` has deals but no
IN deal. Defended here by pre-filtering `deals_raw` rows to only
`position_id`s that have at least one `entry_type='IN'` deal before calling
`group_positions`, so a stray OUT-only position_id can't crash the endpoint.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter

from ...live.grouping import group_positions

router = APIRouter()


def _pos_to_dict(pos: Any) -> dict[str, Any]:
    return {
        "position_id": pos.position_id,
        "ts_in": pos.entry_time,
        "ts_out": pos.exit_time,
        "px_in": pos.entry_price,
        "px_out": pos.exit_price,
        "volume": pos.entry_volume,
        "pnl": pos.pnl,
        "pct": None,
        "mae": pos.mae,
        "mfe": pos.mfe,
        "needs_excursions": pos.needs_excursions,
        "fills": [
            {
                "ticket": f.get("ticket"),
                "price": f.get("price"),
                "volume": f.get("volume"),
                "profit": f.get("profit"),
                "time": f.get("time"),
            }
            for f in pos.fills
        ],
    }


def _group_to_dict(group: Any) -> dict[str, Any]:
    return {
        "group_id": group.group_id,
        "symbol": group.symbol,
        "side": group.side,
        "magic": group.magic,
        "first_in": group.first_in,
        "last_out": group.last_out,
        "net": group.net,
        "lots": group.lots,
        "children": [_pos_to_dict(p) for p in group.children],
    }


def build_router(registry) -> APIRouter:
    r = APIRouter()

    @r.get("/api/positions")
    def get_positions(origin: str | None = None, symbol: str | None = None, limit: int = 200) -> dict[str, Any]:
        conn = registry._connect()  # noqa: SLF001 - same pattern as registry2's own query methods
        conn.row_factory = sqlite3.Row
        try:
            clauses = []
            params: list[Any] = []
            if origin:
                clauses.append("origin = ?")
                params.append(origin)
            if symbol:
                clauses.append("symbol = ?")
                params.append(symbol)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(f"SELECT * FROM deals_raw {where}", params).fetchall()
        finally:
            conn.close()

        deals = [dict(row) for row in rows]

        # Defend against StopIteration in grouping._build_positions: drop
        # any position_id that has no IN deal before grouping.
        ids_with_in = {d["position_id"] for d in deals if d.get("entry_type") == "IN"}
        deals = [d for d in deals if d["position_id"] in ids_with_in]

        groups = group_positions(deals)
        groups.sort(key=lambda g: g.first_in, reverse=True)
        groups = groups[:limit]

        return {"groups": [_group_to_dict(g) for g in groups]}

    return r
