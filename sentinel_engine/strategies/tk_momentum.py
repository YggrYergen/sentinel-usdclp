"""sentinel_engine.strategies.tk_momentum -- TK-Momentum-5-8-short engine
(2026-07-21). A NEW additive live engine for a trader's forward test on XAUUSD.

WHAT IT IS
----------
On M6 CLOSED bars (trader 2026-07-21: switched M10 -> M6 for a faster reaction;
the 5/8/2 periods are UNCHANGED so they now span 30/48/12 min, not 50/80/20):
  * SMA5 vs SMA8 (simple moving averages of closes) gate the ALLOWED side:
      SMA5 < SMA8  -> only SHORTs may open ("regime bajista").
      SMA5 > SMA8  -> only LONGs  may open ("regime alcista").
  * MOM2 = close[i]/close[i-2]*100 (the standard MT5 iMomentum, period 2)
    oscillates around 100. ENTRY IS A STATE, NOT A CROSS (trader 2026-07-21 v2):
    a SINGLE position opens as soon as BOTH conditions hold, coming into the bar
    flat:
      SHORT when SMA5 < SMA8 AND MOM2 < 100 (bajista + momentum below 100);
      LONG  when SMA5 > SMA8 AND MOM2 > 100 (alcista + momentum above 100).
    Strict inequalities: SMA5==SMA8 or MOM2==100 do NOT open. The two states are
    mutually exclusive (a regime is either bajista or alcista, never both).
  * The position holds until EITHER (checked in this order each bar):
      1. a `trail_usd` (default 0.5) trailing stop is touched (server-side SL;
         short: high >= sl; long: low <= sl), OR
      2. MOM2 crosses the 100 line back the other way (momentum reversion),
         closing at that bar's close.
  * Single position, no pyramiding, no re-entry on the SAME bar an exit fired.
    NEVER more than one position open at a time: `pos` is a single slot, so the
    snapshot below emits at most one ficha (F1) -- this is the trader's
    2026-07-21 "solo una posicion" invariant, guarded by construction here and
    asserted again in the executor's tk_momentum reconcile branch.

PARITY-BY-CONSTRUCTION
----------------------
Like `supertrend_always_in_target`, this replays the bar window and emits the
reconciler's `return_state` snapshot -- {"open": {"F1": {...}} | {},
"last_bar_exits": {}, "last_idx": n-1} -- a SINGLE ficha F1. So it reconciles
through the EXACT same ladder reconciler (OPEN / MODIFY-trail / CLOSE-orphan)
with NO reconciler change; the always-present SL satisfies the OPEN SL rule.

No MT5 import, no orders: this decides WHAT the desired state is; the guarded
executor (`scripts/live/run_live_20.py`) turns it into (dry-run/armed) actions.
"""
from __future__ import annotations

from typing import Any

MOM_LINE = 100.0
DEFAULT_TRAIL_USD = 0.5


def sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average. Returns a list the same length as `values`;
    entries before `period-1` (warmup) are None."""
    out: list[float | None] = [None] * len(values)
    if period <= 0:
        return out
    run = 0.0
    for i, v in enumerate(values):
        run += v
        if i >= period:
            run -= values[i - period]
        if i >= period - 1:
            out[i] = run / period
    return out


def momentum(values: list[float], period: int) -> list[float | None]:
    """MT5-style momentum: values[i] / values[i-period] * 100. Entries before
    index `period` (or where the reference is 0) are None."""
    out: list[float | None] = [None] * len(values)
    for i in range(period, len(values)):
        ref = values[i - period]
        out[i] = (values[i] / ref * 100.0) if ref else None
    return out


def tk_momentum_5_8_target(
    bars: list[dict[str, Any]], *,
    trail_usd: float = DEFAULT_TRAIL_USD,
    ma_fast: int = 5, ma_slow: int = 8, mom_period: int = 2,
) -> dict[str, Any]:
    """Replay `bars` (M6 closed bars, sim dict shape {t,open,high,low,close})
    and return the reconciler snapshot for the CURRENT desired position.

    Returns {"open": {"F1": {"side","entry","sl","max_fav"}} | {},
             "last_bar_exits": {}, "last_idx": n-1}.
    """
    n = len(bars)
    flat = {"open": {}, "last_bar_exits": {}, "last_idx": n - 1}
    if n == 0:
        return flat

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]

    ma_f = sma(closes, ma_fast)
    ma_s = sma(closes, ma_slow)
    mom = momentum(closes, mom_period)

    # position state: None, or dict(side, entry, sl, extreme)
    pos: dict[str, Any] | None = None

    for i in range(n):
        maf, mas = ma_f[i], ma_s[i]
        m_now, m_prev = mom[i], (mom[i - 1] if i > 0 else None)
        # need full indicator warmup (both MAs and the current+prior momentum)
        if maf is None or mas is None or m_now is None or m_prev is None:
            continue

        exited_this_bar = False

        # ---- exits (only with an open position), trailing stop FIRST ----
        if pos is not None:
            if pos["side"] == "S":
                if highs[i] >= pos["sl"]:                 # 1) trailing stop hit
                    pos, exited_this_bar = None, True
                elif m_prev <= MOM_LINE and m_now > MOM_LINE:  # 2) mom reversion
                    pos, exited_this_bar = None, True
                else:                                     # trail the SL tighter
                    pos["extreme"] = min(pos["extreme"], lows[i])
                    pos["sl"] = min(pos["sl"], pos["extreme"] + trail_usd)
            else:  # long
                if lows[i] <= pos["sl"]:
                    pos, exited_this_bar = None, True
                elif m_prev >= MOM_LINE and m_now < MOM_LINE:
                    pos, exited_this_bar = None, True
                else:
                    pos["extreme"] = max(pos["extreme"], highs[i])
                    pos["sl"] = max(pos["sl"], pos["extreme"] - trail_usd)

        # ---- entry (STATE, not cross; only if flat coming INTO this bar so an
        #      exit and its re-entry can never happen on the SAME bar) ----
        if pos is None and not exited_this_bar:
            if maf < mas and m_now < MOM_LINE:            # bajista + MOM<100 -> SHORT
                entry = closes[i]
                pos = {"side": "S", "entry": entry, "extreme": entry,
                       "sl": entry + trail_usd}
            elif maf > mas and m_now > MOM_LINE:          # alcista + MOM>100 -> LONG
                entry = closes[i]
                pos = {"side": "L", "entry": entry, "extreme": entry,
                       "sl": entry - trail_usd}

    if pos is None:
        return flat
    return {
        "open": {"F1": {"side": pos["side"], "entry": pos["entry"],
                        "sl": pos["sl"], "max_fav": pos["extreme"]}},
        "last_bar_exits": {},
        "last_idx": n - 1,
    }
