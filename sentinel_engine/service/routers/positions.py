"""sentinel_engine.service.routers.positions — GET /api/positions (B3-api).

Reads `deals_raw` rows from the registry (`research/registry2.py`),
optionally filtered by `origin`/`symbol`, and groups them into
`PositionGroup`s via `sentinel_engine.live.grouping.group_positions`
(reused verbatim, not reimplemented). `pct = profit / margin` with
`margin = volume * contract_size * px_in / leverage`, computed from the
leverage/contract_size columns B1c's DealsWatcher captures on each deal's
IN row; when any input is missing (null) or leverage/margin is not
positive, `pct` is null. `mae`/`mfe` come back null with
`needs_excursions=True` straight from the grouping module; passed
through as-is.

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
from pydantic import BaseModel

from ...live.grouping import group_positions

router = APIRouter()


class PositionCommentRequest(BaseModel):
    body: str
    magic: int | None = None


def _compute_pct(pos: Any, margin_inputs: dict[Any, tuple[Any, Any]]) -> float | None:
    """`pct = profit / margin` with `margin = volume * contract_size *
    px_in / leverage` — only when ALL inputs are non-null, leverage > 0
    and margin > 0; otherwise None (previous behavior)."""
    leverage, contract_size = margin_inputs.get(pos.position_id, (None, None))
    volume = pos.entry_volume
    px_in = pos.entry_price
    profit = pos.pnl
    if leverage is None or contract_size is None or volume is None or px_in is None or profit is None:
        return None
    if leverage <= 0:
        return None
    margin = volume * contract_size * px_in / leverage
    if margin <= 0:
        return None
    return profit / margin


def _pos_to_dict(
    pos: Any,
    margin_inputs: dict[Any, tuple[Any, Any]],
    spreads: dict[Any, dict[str, Any]],
) -> dict[str, Any]:
    spread = spreads.get(pos.position_id) or {}
    return {
        "position_id": pos.position_id,
        "ts_in": pos.entry_time,
        "ts_out": pos.exit_time,
        "px_in": pos.entry_price,
        "px_out": pos.exit_price,
        "volume": pos.entry_volume,
        "pnl": pos.pnl,
        "pct": _compute_pct(pos, margin_inputs),
        "mae": pos.mae,
        "mfe": pos.mfe,
        "needs_excursions": pos.needs_excursions,
        # is_open: a position with no exit fill is still open in MT5.
        "is_open": pos.exit_time is None,
        "spread_open": spread.get("spread_open"),
        "spread_open_min": spread.get("spread_open_min"),
        "spread_close": spread.get("spread_close"),
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


def _group_to_dict(
    group: Any,
    margin_inputs: dict[Any, tuple[Any, Any]],
    spreads: dict[Any, dict[str, Any]],
    strategy_by_position: dict[Any, Any],
) -> dict[str, Any]:
    # strategy_id: all children of a group share symbol/side/magic, so they
    # share the same attribution; take it from the first child's IN deal.
    strat_id = None
    for child in group.children:
        strat_id = strategy_by_position.get(child.position_id)
        if strat_id is not None:
            break
    return {
        "group_id": group.group_id,
        "symbol": group.symbol,
        "side": group.side,
        "magic": group.magic,
        "strategy_id": strat_id,
        "first_in": group.first_in,
        "last_out": group.last_out,
        # is_open at the group level: any child still open keeps the group open.
        "is_open": any(c.exit_time is None for c in group.children),
        "net": group.net,
        "lots": group.lots,
        "children": [_pos_to_dict(p, margin_inputs, spreads) for p in group.children],
    }


def build_router(registry) -> APIRouter:
    from ..app import _api_error

    r = APIRouter()

    @r.get("/api/positions")
    def get_positions(
        origin: str | None = None,
        symbol: str | None = None,
        strategy_id: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
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
            if strategy_id:
                clauses.append("strategy_id = ?")
                params.append(strategy_id)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

            if clauses:
                # BUG fix (2026-07-21): an SL/TP close arrives from MT5 with
                # magic=0; if it was persisted before position_id inheritance
                # (or its IN wasn't in the DB yet), its row has origin='human'
                # / strategy_id=NULL. Filtering deals_raw by origin/strategy_id
                # would then DROP that OUT, so the position would group with no
                # exit fill and falsely show as ABIERTA under the strategy. So
                # the filter selects the matching position_ids, and we then
                # fetch ALL deals for those positions -- the orphan OUT included
                # -- so the close is honored. (symbol is a real per-deal
                # attribute shared by every deal of a position, so widening on
                # it is a no-op; origin/strategy_id are the ones that leak.)
                id_rows = conn.execute(
                    f"SELECT DISTINCT position_id FROM deals_raw {where}", params
                ).fetchall()
                position_ids = [r["position_id"] for r in id_rows if r["position_id"] is not None]
                if position_ids:
                    placeholders = ", ".join("?" for _ in position_ids)
                    rows = conn.execute(
                        f"SELECT * FROM deals_raw WHERE position_id IN ({placeholders})",
                        position_ids,
                    ).fetchall()
                else:
                    rows = []
            else:
                rows = conn.execute("SELECT * FROM deals_raw").fetchall()
        finally:
            conn.close()

        deals = [dict(row) for row in rows]

        # Defend against StopIteration in grouping._build_positions: drop
        # any position_id that has no IN deal before grouping.
        ids_with_in = {d["position_id"] for d in deals if d.get("entry_type") == "IN"}
        deals = [d for d in deals if d["position_id"] in ids_with_in]

        # pct inputs (B1c): leverage/contract_size from each position's IN
        # deal row (grouping.Position doesn't carry these columns).
        margin_inputs = {
            d["position_id"]: (d.get("leverage"), d.get("contract_size"))
            for d in deals
            if d.get("entry_type") == "IN"
        }

        # strategy_id per position: from each position's IN deal (grouping
        # doesn't carry attribution columns onto the Position dataclass).
        strategy_by_position = {
            d["position_id"]: d.get("strategy_id")
            for d in deals
            if d.get("entry_type") == "IN"
        }

        groups = group_positions(deals)
        groups.sort(key=lambda g: g.first_in, reverse=True)
        groups = groups[:limit]

        # LEFT JOIN position_spread for the positions actually returned.
        shown_ids = [c.position_id for g in groups for c in g.children]
        spreads = registry.get_position_spreads(shown_ids)

        return {
            "groups": [
                _group_to_dict(g, margin_inputs, spreads, strategy_by_position)
                for g in groups
            ]
        }

    @r.post("/api/positions/{position_id}/comments")
    def post_position_comment(position_id: int, payload: PositionCommentRequest):
        try:
            comment_id = registry.add_position_comment(
                position_id, payload.body, magic=payload.magic
            )
        except ValueError as exc:
            return _api_error(400, "invalid_comment_body", str(exc))
        comments = registry.get_position_comments([position_id])
        added = next(
            (c for c in comments.get(position_id, []) if c["comment_id"] == comment_id),
            None,
        )
        return {
            "comment_id": comment_id,
            "position_id": position_id,
            "body": payload.body,
            "magic": added["magic"] if added else payload.magic,
            "created_at": added["created_at"] if added else None,
        }

    @r.get("/api/positions/{position_id}/comments")
    def get_position_comments_route(position_id: int) -> dict[str, Any]:
        comments = registry.get_position_comments([position_id])
        return {"comments": comments.get(position_id, [])}

    @r.delete("/api/positions/{position_id}/comments/{comment_id}")
    def delete_position_comment_route(position_id: int, comment_id: int) -> dict[str, Any]:
        deleted = registry.delete_position_comment(comment_id)
        return {"deleted": deleted}

    return r
