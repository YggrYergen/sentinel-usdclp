"""sentinel_engine.live.grouping — Position grouping (Wave B, lane C / B1b).

Consumes `deals_raw`-shaped deal dicts (as produced by
`sentinel_engine.live.deals_watcher._map_deal`: `ticket, position_id, symbol,
side, volume, price, profit, magic, time, entry_type, origin, strategy_id,
variant_id`) and groups them into:

  1. `Position` — all deals sharing a `position_id`. Exactly one IN deal
     (the entry) and >=1 OUT deals (the exit fills). Partial closes are
     multiple OUT deals against the same position_id; the aggregated exit
     price is the volume-weighted average (VWAP) of the OUT fill prices,
     and `pnl` is the sum of the OUT fills' `profit`.

  2. `PositionGroup` — the "3 fichas" multi-lot pattern: positions that
     share `symbol` + `side` + `magic`, with entry times within 90s of
     each other, are grouped together. `group_id = f"{magic}-{first_entry_t}"`
     where `first_entry_t` is the entry time of the first position that
     anchors the group (see `_cluster_positions` below for the exact
     clustering rule). Positions that don't share symbol/side/magic, or
     whose entry time falls outside the 90s window of the running
     cluster, are NOT grouped together (they end up in their own
     singleton `PositionGroup`, so `group_positions` always returns a
     uniform `list[PositionGroup]`).

MAE/MFE (per-position excursions) are NOT computed here -- that's B2's
`mae_mfe` helper (bar-based, doesn't exist yet). Every `Position` produced
by this module has `mae=None, mfe=None, needs_excursions=True` so a later
stage knows to backfill them.

Style note: dataclasses are used here (not dicts), mirroring
`WatchReport` in `sentinel_engine.live.deals_watcher`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Multi-lot ("3 fichas") clustering window: entries within this many
# seconds of the running cluster's anchor entry are grouped together.
_GROUP_WINDOW_S = 90


@dataclass
class Position:
    position_id: Any
    symbol: str
    side: str
    magic: Any
    entry_time: float
    entry_price: float
    entry_volume: float
    fills: list[dict[str, Any]] = field(default_factory=list)
    exit_price: float | None = None
    exit_time: float | None = None
    pnl: float = 0.0
    mae: float | None = None
    mfe: float | None = None
    needs_excursions: bool = True


@dataclass
class PositionGroup:
    group_id: str
    symbol: str
    side: str
    magic: Any
    first_in: float
    last_out: float | None
    net: float
    lots: float
    children: list[Position] = field(default_factory=list)


def _build_positions(deals: list[dict[str, Any]]) -> list[Position]:
    """Group deals by `position_id` into `Position` objects.

    Each position must have exactly one IN deal (its entry). All OUT
    deals against that position_id are its `fills`; the aggregated exit
    price is their VWAP (sum(price * volume) / sum(volume)), `exit_time`
    is the max OUT `time`, and `pnl` is the sum of OUT `profit`.

    A position_id with no IN deal in `deals` (its entry fell outside the
    queried window) is skipped rather than raising -- see `group_positions`.
    """
    by_position: dict[Any, list[dict[str, Any]]] = {}
    for deal in deals:
        by_position.setdefault(deal["position_id"], []).append(deal)

    positions: list[Position] = []
    for position_id, group_deals in by_position.items():
        entry = next((d for d in group_deals if d["entry_type"] == "IN"), None)
        if entry is None:
            # No IN deal in this batch (e.g. the entry fell outside the
            # queried window on a rolling fetch). Skip rather than
            # inventing an entry; caller re-queries a wider window later.
            logger.debug(
                "grouping: skipping position_id=%r with no IN deal "
                "(%d OUT-only deal(s))",
                position_id, len(group_deals),
            )
            continue
        outs = [d for d in group_deals if d["entry_type"] == "OUT"]

        total_volume = sum(d["volume"] for d in outs)
        if total_volume:
            vwap = sum(d["price"] * d["volume"] for d in outs) / total_volume
        else:
            vwap = None
        pnl = sum(d["profit"] for d in outs)
        exit_time = max((d["time"] for d in outs), default=None)

        positions.append(
            Position(
                position_id=position_id,
                symbol=entry["symbol"],
                side=entry["side"],
                magic=entry.get("magic"),
                entry_time=entry["time"],
                entry_price=entry["price"],
                entry_volume=entry["volume"],
                fills=outs,
                exit_price=vwap,
                exit_time=exit_time,
                pnl=pnl,
                mae=None,
                mfe=None,
                needs_excursions=True,
            )
        )

    positions.sort(key=lambda p: p.entry_time)
    return positions


def _cluster_positions(positions: list[Position]) -> list[list[Position]]:
    """Cluster positions sharing symbol+side+magic whose entry times fall
    within `_GROUP_WINDOW_S` of one another.

    Positions are processed in entry-time order per (symbol, side, magic)
    key. A running cluster's anchor is the entry time of the FIRST
    position added to it; any subsequent position within
    `_GROUP_WINDOW_S` seconds of that anchor joins the same cluster,
    otherwise a new cluster starts (anchored at that position instead).
    This matches "entradas dentro de 90s entre si" as a fixed window from
    the first entry, so a same-key position seen well after the group
    (e.g. an unrelated later trade) is NOT swept in.
    """
    by_key: dict[tuple[Any, Any, Any], list[Position]] = {}
    for pos in positions:
        by_key.setdefault((pos.symbol, pos.side, pos.magic), []).append(pos)

    clusters: list[list[Position]] = []
    for key_positions in by_key.values():
        key_positions = sorted(key_positions, key=lambda p: p.entry_time)
        current_cluster: list[Position] = []
        anchor_time: float | None = None
        for pos in key_positions:
            if current_cluster and (pos.entry_time - anchor_time) <= _GROUP_WINDOW_S:
                current_cluster.append(pos)
            else:
                if current_cluster:
                    clusters.append(current_cluster)
                current_cluster = [pos]
                anchor_time = pos.entry_time
        if current_cluster:
            clusters.append(current_cluster)

    return clusters


def _build_group(cluster: list[Position]) -> PositionGroup:
    cluster = sorted(cluster, key=lambda p: p.entry_time)
    first_in = cluster[0].entry_time
    exit_times = [p.exit_time for p in cluster if p.exit_time is not None]
    last_out = max(exit_times) if exit_times else None
    net = sum(p.pnl for p in cluster)
    lots = sum(p.entry_volume for p in cluster)
    magic = cluster[0].magic

    return PositionGroup(
        group_id=f"{magic}-{first_in}",
        symbol=cluster[0].symbol,
        side=cluster[0].side,
        magic=magic,
        first_in=first_in,
        last_out=last_out,
        net=net,
        lots=lots,
        children=cluster,
    )


def group_positions(deals: list[dict[str, Any]]) -> list[PositionGroup]:
    """Deal rows -> Positions (by position_id) -> PositionGroups (by
    symbol+side+magic within a 90s entry window). Positions that don't
    cluster with any other come back as singleton `PositionGroup`s, so
    the return type is always a uniform `list[PositionGroup]`."""
    positions = _build_positions(deals)
    clusters = _cluster_positions(positions)
    groups = [_build_group(cluster) for cluster in clusters]
    groups.sort(key=lambda g: g.first_in)
    return groups
