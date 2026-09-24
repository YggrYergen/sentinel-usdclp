"""sentinel_engine.research.metrics — pure performance-metric functions (Wave B, B2).

Every function here is PURE (no I/O, no registry access) so it can be
unit-tested against hand-computed fixtures in isolation from
`scorecard.py` (which wires these to registry data for CT-3's
`GET /api/strategies/{id}/scorecard`).

Trades are represented as plain dicts with (at least) the keys used by
each function -- this mirrors the `trade`/`deals_raw` row shapes already
used elsewhere in `sentinel_engine.research.registry2` /
`sentinel_engine.live.grouping`, so callers can pass registry rows
directly without an adapter layer.
"""
from __future__ import annotations

import math
from typing import Any


def pf(wins: list[float], losses: list[float]) -> float | None:
    """Profit factor = sum(wins) / abs(sum(losses)).

    `wins`/`losses` are lists of signed pnl (wins > 0, losses < 0 -- signs
    are not checked, only magnitudes are used: sum(wins) uses the values
    as-is, abs(sum(losses)) takes the absolute value of their sum).
    Returns None if there are no losses (division by zero) or no trades
    at all -- never inflates/guesses a value.
    """
    if not wins and not losses:
        return None
    gross_loss = abs(sum(losses))
    if gross_loss == 0:
        return None
    gross_win = sum(wins)
    return gross_win / gross_loss


def wr(wins: list[float], losses: list[float]) -> float | None:
    """Win rate = count(wins) / (count(wins) + count(losses)), in [0, 1].

    Returns None if there are no trades at all.
    """
    total = len(wins) + len(losses)
    if total == 0:
        return None
    return len(wins) / total


def payoff(wins: list[float], losses: list[float]) -> float | None:
    """Payoff ratio = avg(wins) / abs(avg(losses)).

    Returns None if there are no wins, no losses, or avg(losses) == 0.
    """
    if not wins or not losses:
        return None
    avg_win = sum(wins) / len(wins)
    avg_loss = abs(sum(losses) / len(losses))
    if avg_loss == 0:
        return None
    return avg_win / avg_loss


def expectancy_r(trades: list[dict[str, Any]]) -> tuple[float | None, str]:
    """Expectancy in R-multiples: r = pnl / (risk_per_unit * volume), where
    risk_per_unit = abs(px_in - sl). Returns (mean(r) over all trades, "ok").

    If ANY trade is missing `sl` (None/falsy) or has risk_per_unit == 0 (sl
    == px_in), R can't be computed for that trade (or any trade, per spec:
    "si algun trade no tiene sl -> retorna (valor_ccy, flag)") -- falls back
    to the mean raw pnl (currency units, NOT R) for ALL trades, flagged
    "no_sl_fallback_ccy" so callers know the unit changed.

    Returns (None, "ok") if `trades` is empty.
    """
    if not trades:
        return None, "ok"

    has_missing_sl = False
    r_values: list[float] = []
    for t in trades:
        sl = t.get("sl")
        px_in = t.get("px_in")
        volume = t.get("volume")
        pnl = t.get("pnl") or 0.0
        if sl is None or px_in is None or volume is None:
            has_missing_sl = True
            break
        risk_per_unit = abs(px_in - sl)
        if risk_per_unit == 0:
            has_missing_sl = True
            break
        r_values.append(pnl / (risk_per_unit * volume))

    if has_missing_sl:
        pnls = [t.get("pnl") or 0.0 for t in trades]
        return sum(pnls) / len(pnls), "no_sl_fallback_ccy"

    return sum(r_values) / len(r_values), "ok"


def net_per_day(trades: list[dict[str, Any]]) -> float | None:
    """Net pnl / active days, where active days = count of distinct dates
    (the date portion of `ts_in`, i.e. `ts_in[:10]`) across all trades.

    Returns None if `trades` is empty (no active days to divide by).
    """
    if not trades:
        return None
    net = sum(t.get("pnl") or 0.0 for t in trades)
    days = {str(t.get("ts_in"))[:10] for t in trades if t.get("ts_in")}
    if not days:
        return None
    return net / len(days)


def trades_per_day(trades: list[dict[str, Any]]) -> float | None:
    """Count(trades) / active days (distinct `ts_in[:10]` dates).

    Returns None if `trades` is empty or no trade carries a `ts_in`.
    """
    if not trades:
        return None
    days = {str(t.get("ts_in"))[:10] for t in trades if t.get("ts_in")}
    if not days:
        return None
    return len(trades) / len(days)


def maxdd_pct(trades: list[dict[str, Any]], base_notional: float) -> float | None:
    """Max drawdown %, peak-to-trough over cumulative pnl (in trade order,
    as given -- callers must pass trades already sorted by ts_in), expressed
    as a percentage of `base_notional` (the equity/account-size reference).

    dd_pct at step i = (peak_so_far - cum_pnl_i) / base_notional * 100.
    Returns the MAX such value over all steps (0.0 if pnl never dips below
    a prior peak). Returns None if `trades` is empty or base_notional <= 0.
    """
    if not trades or base_notional is None or base_notional <= 0:
        return None
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cum += t.get("pnl") or 0.0
        if cum > peak:
            peak = cum
        dd = (peak - cum) / base_notional * 100.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def sharpe_d(trades: list[dict[str, Any]]) -> float | None:
    """Daily Sharpe = mean(daily_pnl) / std(daily_pnl) * sqrt(252), where
    daily_pnl is pnl summed per distinct date (`ts_in[:10]`).

    Returns None if there are fewer than 10 distinct active days (per
    spec: "None si <10 dias") or if std(daily_pnl) == 0 (division by zero).
    """
    if not trades:
        return None
    by_day: dict[str, float] = {}
    for t in trades:
        ts_in = t.get("ts_in")
        if not ts_in:
            continue
        day = str(ts_in)[:10]
        by_day[day] = by_day.get(day, 0.0) + (t.get("pnl") or 0.0)

    if len(by_day) < 10:
        return None

    daily = list(by_day.values())
    n = len(daily)
    mean = sum(daily) / n
    variance = sum((x - mean) ** 2 for x in daily) / n
    std = math.sqrt(variance)
    if std == 0:
        return None
    return mean / std * math.sqrt(252)


def mae_mfe(
    bars: list[dict[str, Any]],
    entry_t: Any,
    exit_t: Any,
    side: str,
    entry_px: float,
) -> tuple[float | None, float | None]:
    """MAE (max adverse excursion) / MFE (max favorable excursion) for one
    trade, computed from OHLC `bars` (dicts with `t`/`h`/`l` keys) whose
    timestamp `t` falls in [entry_t, exit_t] (inclusive both ends).

    For LONG: adverse move is price falling below entry (uses bar lows),
    favorable is price rising above entry (uses bar highs).
    MAE = entry_px - min(low over window); MFE = max(high over window) - entry_px.

    For SHORT it's mirrored: MAE = max(high over window) - entry_px,
    MFE = entry_px - min(low over window).

    Both are returned as non-negative currency-unit distances (0.0 if the
    window never moves against/favorably). Returns (None, None) if no bars
    fall inside [entry_t, exit_t].
    """
    window = [b for b in bars if entry_t <= b.get("t") <= exit_t]
    if not window:
        return None, None
    lo = min(b["l"] for b in window)
    hi = max(b["h"] for b in window)
    if side == "LONG":
        mae = max(0.0, entry_px - lo)
        mfe = max(0.0, hi - entry_px)
    else:  # SHORT
        mae = max(0.0, hi - entry_px)
        mfe = max(0.0, entry_px - lo)
    return mae, mfe
