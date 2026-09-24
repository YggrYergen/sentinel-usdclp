"""sentinel_engine.ai.tools — read-only tool registry for the AI assistant (C4a).

Pure, deterministic, no LLM and no network. `TOOLS` is the Anthropic
tool-schema list handed to the model; `execute_tool(name, args, ctx)` is the
single dispatch entrypoint the caller uses to actually run one, where
`ctx = {"registry": ResearchRegistry, "lake_root": Path}`.

Reuses existing internals rather than duplicating logic:
  - get_bars       -> sentinel_engine.service.bars_source (CT-2 shape, same
                       LOD ladder as GET /api/bars).
  - get_scorecard  -> sentinel_engine.research.scorecard.build_scorecard
                       (CT-3 shape, same function GET /api/strategies/{id}/scorecard
                       calls -- direct call, never HTTP self-call).
  - get_trade_detail / query_registry -> sentinel_engine.research.registry2
                       schema, read-only parameterized SQL (registry2.py
                       itself is not modified: it exposes no by-trade-id or
                       ad-hoc-filter query helper today).

Every tool function returns a plain string (JSON-encoded on success, a
short human-readable `"error: ..."` string on failure) -- `execute_tool`
never raises to the caller; an unknown tool name or bad args always comes
back as an error string result.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from sentinel_engine.research import scorecard as scorecard_mod
from sentinel_engine.service.bars_source import (
    BarsSourceError,
    choose_served_tf,
    read_window,
)

# CT-2 default decimals (matches sentinel_engine.service.routers.bars
# defaults: no per-instrument precision field exists yet).
_SYMBOL_DECIMALS: dict[str, int] = {"XAUUSD": 2}
_DEFAULT_DECIMALS = 2

# Hard cap on serialized get_bars result size, chars/3.5 heuristic (~ tokens).
_MAX_RESULT_TOKENS = 25_000
_MAX_RESULT_CHARS = int(_MAX_RESULT_TOKENS * 3.5)

# Whitelisted query_registry filter keys -> (table alias, column). Anything
# not in this map is rejected (never interpolated into SQL).
_QUERY_REGISTRY_FILTERS: dict[str, str] = {
    "strategy_id": "v.strategy_id",
    "variant_id": "r.variant_id",
    "engine": "r.engine",
    "fidelity": "r.fidelity",
    "instrumento": "v.instrumento",
}


TOOLS: list[dict] = [
    {
        "name": "get_bars",
        "description": (
            "Read OHLCV bars for a symbol/timeframe over [from, to] "
            "(epoch seconds), CT-2 shape, from the pre-built lake tiers. "
            "Large windows are served at a coarser timeframe (LOD ladder) "
            "and/or truncated to stay under the result size cap."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "tf": {"type": "string", "description": "e.g. M1, M5, M15, H1, D"},
                "from": {"type": "integer", "description": "epoch seconds, inclusive"},
                "to": {"type": "integer", "description": "epoch seconds, inclusive"},
            },
            "required": ["symbol", "tf", "from", "to"],
        },
    },
    {
        "name": "get_trade_detail",
        "description": "Read one trade row by trade_id from the research registry.",
        "input_schema": {
            "type": "object",
            "properties": {"trade_id": {"type": "string"}},
            "required": ["trade_id"],
        },
    },
    {
        "name": "query_registry",
        "description": (
            "Query `run` rows (joined to variant/strategy) with whitelisted "
            "equality filters: strategy_id, variant_id, engine, fidelity, "
            "instrumento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "description": "subset of {strategy_id, variant_id, engine, fidelity, instrumento}",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_scorecard",
        "description": "Read the CT-3 scorecard (real/teorico metrics) for a strategy_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string"},
                "tf": {"type": "string"},
            },
            "required": ["strategy_id"],
        },
    },
]

_TOOL_NAMES = frozenset(t["name"] for t in TOOLS)


def _decimals_for(symbol: str) -> int:
    return _SYMBOL_DECIMALS.get(str(symbol).upper(), _DEFAULT_DECIMALS)


def _tool_get_bars(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    lake_root = ctx["lake_root"]
    symbol = args["symbol"]
    tf = args["tf"]
    from_epoch = int(args["from"])
    to_epoch = int(args["to"])

    max_points = 3000
    try:
        served_tf = choose_served_tf(tf, from_epoch, to_epoch, max_points)
        bars = read_window(symbol, served_tf, from_epoch, to_epoch, lake_root)
    except BarsSourceError as exc:
        return f"error: bad_tf: {exc}"
    except Exception as exc:  # noqa: BLE001 - never raise to caller
        return f"error: get_bars_failed: {exc}"

    clipped = len(bars) > max_points
    if clipped:
        bars = bars[-max_points:]

    dp = _decimals_for(symbol)
    rounded_bars = [
        {
            "t": b["t"],
            "o": round(b["o"], dp),
            "h": round(b["h"], dp),
            "l": round(b["l"], dp),
            "c": round(b["c"], dp),
            "v": b["v"],
        }
        for b in bars
    ]

    payload = {
        "symbol": symbol,
        "tf_requested": tf,
        "served_tf": served_tf,
        "clipped": clipped,
        "bars": rounded_bars,
        "overlays": {},
    }
    serialized = json.dumps(payload, ensure_ascii=False)

    # Hard cap: truncate bars from the front (keep most recent) until under
    # the char budget, noting the truncation, rather than emitting a
    # result that blows the caller's token budget.
    if len(serialized) > _MAX_RESULT_CHARS:
        payload["clipped"] = True
        payload["truncation_note"] = (
            f"result exceeded {_MAX_RESULT_TOKENS} token cap; bars truncated"
        )
        bars_list = payload["bars"]
        while bars_list and len(json.dumps(payload, ensure_ascii=False)) > _MAX_RESULT_CHARS:
            bars_list.pop(0)
        serialized = json.dumps(payload, ensure_ascii=False)

    return serialized


def _tool_get_trade_detail(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    trade_id = args.get("trade_id")
    if not trade_id:
        return "error: missing required arg: trade_id"

    registry = ctx["registry"]
    conn = registry._connect()  # noqa: SLF001 - read-only, same pattern scorecard.py already uses
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM trade WHERE trade_id=?", (str(trade_id),)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return f"error: trade not found: {trade_id}"

    return json.dumps(dict(row), ensure_ascii=False, default=str)


def _tool_query_registry(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    filters = args.get("filters") or {}
    if not isinstance(filters, dict):
        return "error: filters must be an object"

    where: list[str] = []
    params: list[Any] = []
    for key, value in filters.items():
        column = _QUERY_REGISTRY_FILTERS.get(key)
        if column is None:
            return f"error: unknown filter key (not whitelisted): {key}"
        where.append(f"{column} = ?")
        params.append(value)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    registry = ctx["registry"]
    conn = registry._connect()  # noqa: SLF001 - read-only, same pattern scorecard.py already uses
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""SELECT r.run_id, r.variant_id, r.engine, r.fidelity,
                       r.trades, r.net, r.pf, r.wr, r.payoff, r.maxdd, r.sharpe,
                       v.strategy_id AS strategy_id, v.instrumento AS instrumento
                FROM run r
                LEFT JOIN variant v ON r.variant_id = v.variant_id
                {where_clause}
                ORDER BY r.run_id ASC""",
            params,
        ).fetchall()
    finally:
        conn.close()

    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


def _tool_get_scorecard(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    strategy_id = args.get("strategy_id")
    if not strategy_id:
        return "error: missing required arg: strategy_id"
    tf = args.get("tf", "M5")

    registry = ctx["registry"]
    try:
        card = scorecard_mod.build_scorecard(registry, strategy_id, tf=tf)
    except Exception as exc:  # noqa: BLE001 - never raise to caller
        return f"error: get_scorecard_failed: {exc}"

    if card is None:
        return f"error: strategy not found: {strategy_id}"

    return json.dumps(card, ensure_ascii=False, default=str)


_DISPATCH = {
    "get_bars": _tool_get_bars,
    "get_trade_detail": _tool_get_trade_detail,
    "query_registry": _tool_query_registry,
    "get_scorecard": _tool_get_scorecard,
}


def execute_tool(name: str, args: dict[str, Any], ctx: dict[str, Any]) -> str:
    """Dispatch one tool call by name. Never raises: unknown tool name or
    any internal failure comes back as an `"error: ..."` string."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"error: unknown tool: {name}"
    try:
        return fn(args or {}, ctx)
    except KeyError as exc:
        return f"error: missing required arg: {exc}"
    except Exception as exc:  # noqa: BLE001 - never raise to caller
        return f"error: {name}_failed: {exc}"
