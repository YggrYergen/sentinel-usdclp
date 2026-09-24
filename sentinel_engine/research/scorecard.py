"""sentinel_engine.research.scorecard — CT-3 scorecard builder (Wave B, B2).

Builds the `GET /api/strategies/{id}/scorecard` payload (CT-3, frozen
contract): a `real` block computed from live `deals_raw` rows
(origin='strategy', matched to this strategy_id via the magic-allocation
attribution already persisted by `DealsWatcher` -- see
`sentinel_engine.live.deals_watcher`) plus forward `trade`/`forward_session`
rows, and a `teorico` block computed SOLELY from the strategy's
`baseline_ref` run (never a best-run search) -- `teorico` is `None` when
`baseline_ref` is unset.

An in-process 60s cache (keyed by strategy_id) avoids recomputing on every
poll; `_CACHE_TTL_S` and `_now_fn` (injectable for tests) control it.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from . import metrics

_CACHE_TTL_S = 60.0
_DEFAULT_BASE_NOTIONAL = 10_000.0

# in-process cache: strategy_id -> (built_at_epoch_s, payload)
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _now() -> float:
    return time.time()


def clear_cache() -> None:
    """Test helper: drop all cached scorecards."""
    _cache.clear()


def _metrics_block(
    trades: list[dict[str, Any]],
    window: dict[str, Any],
    source: dict[str, Any],
    base_notional: float = _DEFAULT_BASE_NOTIONAL,
) -> dict[str, Any]:
    """Trade rows (dicts with pnl/ts_in/sl/px_in/volume) -> one metrics
    block matching CT-3's `real`/`teorico` shape."""
    wins = [t.get("pnl") or 0.0 for t in trades if (t.get("pnl") or 0.0) > 0]
    losses = [t.get("pnl") or 0.0 for t in trades if (t.get("pnl") or 0.0) < 0]
    exp_r, exp_flag = metrics.expectancy_r(trades)
    ordered = sorted(trades, key=lambda t: str(t.get("ts_in") or ""))
    return {
        "trades": len(trades),
        "net": sum(t.get("pnl") or 0.0 for t in trades) if trades else None,
        "pf": metrics.pf(wins, losses),
        "wr": metrics.wr(wins, losses),
        "payoff": metrics.payoff(wins, losses),
        "expectancy_r": exp_r,
        "expectancy_r_flag": exp_flag,
        "net_per_day": metrics.net_per_day(trades),
        "trades_per_day": metrics.trades_per_day(trades),
        "maxdd_pct": metrics.maxdd_pct(ordered, base_notional),
        "sharpe_d": metrics.sharpe_d(trades),
        "window": window,
        "source": source,
    }


def _deal_to_trade(deal: dict[str, Any]) -> dict[str, Any]:
    """`deals_raw` row -> the minimal trade-shaped dict the metrics
    functions expect. `deals_raw` has no `sl`/`px_in` columns (only the
    `trade` table does) -- `expectancy_r` degrades to the currency-unit
    fallback (flag `no_sl_fallback_ccy`) for deals-sourced `real` blocks,
    which is the correct/expected behavior per the expectancy_r contract."""
    ts = deal.get("time")
    ts_in = None
    if ts is not None:
        from datetime import datetime, timezone

        ts_in = datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "pnl": deal.get("profit"),
        "ts_in": ts_in,
        "sl": None,
        "px_in": deal.get("price"),
        "volume": deal.get("volume"),
    }


def _deals_to_position_trades(deal_rows: list[Any]) -> list[dict[str, Any]]:
    """Reconstruct realized POSITIONS from `deals_raw` rows: one trade per
    CLOSED position (a position with an OUT deal), pnl = sum of that position's
    deal profits, anchored at its IN deal. This is correct for MT5 SL/TP closes
    where the realized profit lands on the OUT deal (magic=0) while the IN deal
    is 0 -- counting each DEAL as a trade doubled `trades` and diluted
    expectancy/sharpe with the zero-pnl IN rows. Still-OPEN positions (no OUT)
    are excluded: they have no realized outcome yet."""
    from datetime import datetime, timezone

    by_pos: dict[Any, list[dict[str, Any]]] = {}
    for r in deal_rows:
        d = dict(r)
        by_pos.setdefault(d.get("position_id"), []).append(d)

    trades: list[dict[str, Any]] = []
    for deals in by_pos.values():
        if not any(x.get("entry_type") == "OUT" for x in deals):
            continue  # still open -> not a realized trade
        pnl = sum(x.get("profit") or 0.0 for x in deals)
        ins = [x for x in deals if x.get("entry_type") == "IN"]
        anchor = min((ins or deals), key=lambda x: x.get("time") or 0)
        ts = anchor.get("time")
        ts_in = None
        if ts is not None:
            ts_in = datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        trades.append({"pnl": pnl, "ts_in": ts_in, "sl": None,
                       "px_in": anchor.get("price"), "volume": anchor.get("volume")})
    trades.sort(key=lambda t: t.get("ts_in") or "")
    return trades


def _real_block(registry, strategy_id: str) -> dict[str, Any]:
    """`real` = deals with `origin='strategy'` attributed to this
    strategy_id (from `deals_raw`, populated by `DealsWatcher`), reconstructed
    into realized POSITIONS (one trade per closed position), plus
    forward-session trades (`trade` rows with `session_id` set) belonging
    to this strategy. Both sources are combined into one trade list."""
    conn = registry._connect()
    conn.row_factory = __import__("sqlite3").Row
    try:
        deal_rows = conn.execute(
            "SELECT * FROM deals_raw WHERE origin='strategy' AND strategy_id=? ORDER BY time ASC",
            (strategy_id,),
        ).fetchall()
        trades = _deals_to_position_trades(deal_rows)

        session_rows = conn.execute(
            "SELECT session_id FROM forward_session WHERE strategy_id=?", (strategy_id,)
        ).fetchall()
        session_ids = [r["session_id"] for r in session_rows]
        for sid in session_ids:
            trade_rows = conn.execute(
                "SELECT * FROM trade WHERE session_id=? ORDER BY ts_in ASC", (sid,)
            ).fetchall()
            trades.extend(dict(r) for r in trade_rows)
    finally:
        conn.close()

    ts_ins = [t.get("ts_in") for t in trades if t.get("ts_in")]
    window = {
        "from": min(ts_ins) if ts_ins else None,
        "to": max(ts_ins) if ts_ins else None,
    }
    source = {"runs": [], "sessions": session_ids}
    return _metrics_block(trades, window, source)


def _teorico_block(registry, baseline_ref: str) -> dict[str, Any] | None:
    """`teorico` = metrics of the `baseline_ref` run's trades, SOLELY --
    never a best-run search. Returns None if the run doesn't exist."""
    run = registry.get_run(baseline_ref)
    if run is None:
        return None
    trades = registry.get_trades_for_run(baseline_ref)
    ts_ins = [t.get("ts_in") for t in trades if t.get("ts_in")]
    window = {
        "from": run.get("periodo_desde") or (min(ts_ins) if ts_ins else None),
        "to": run.get("periodo_hasta") or (max(ts_ins) if ts_ins else None),
    }
    source = {"runs": [baseline_ref], "sessions": []}
    return _metrics_block(trades, window, source)


def build_scorecard(registry, strategy_id: str, tf: str = "M5") -> dict[str, Any] | None:
    """Build (or return cached) CT-3 scorecard payload for `strategy_id`.
    Returns None if the strategy doesn't exist (caller emits 404)."""
    now = _now()
    cached = _cache.get(strategy_id)
    if cached is not None and (now - cached[0]) < _CACHE_TTL_S:
        return cached[1]

    strategy = registry.get_strategy(strategy_id)
    if strategy is None:
        return None

    baseline_ref = strategy.get("baseline_ref")
    payload = {
        "strategy_id": strategy_id,
        "tf": tf,
        "metrics_contract": "v1",
        "baseline_ref": baseline_ref,
        "floors": {
            "real": _real_block(registry, strategy_id),
            "teorico": _teorico_block(registry, baseline_ref) if baseline_ref else None,
        },
    }
    _cache[strategy_id] = (now, payload)
    return payload
