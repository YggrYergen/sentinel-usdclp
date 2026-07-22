"""sentinel_engine.strategies.tk_bw — pure engine for the "TK-BW" strategy.

New, additive strategy engine (EMA8/EMA5 + Parabolic SAR(0.3,30) + Awesome
Oscillator + Momentum + Accelerator + SuperTrend + candle breakouts, with
break-even + $5 trailing and 3 independent fichas per signal). Spec:
docs/superpowers/plans/2026-07-21-tk-bw-backtest.md, "Task 1 — Motor tk_bw.py".

Pure function, no I/O, no MT5. Consumes a caller-built sequence of evaluation
"steps" (intra-native-candle M1 sub-steps) and emits a flat list of trade
dicts, one per ficha close. Indicators are recomputed each step from
`closed` (+ `forming`, if present) native-candle OHLC via the existing
vendored reference implementations in `emasar_ref` / `_supertrend_ref` — no
indicator math is reimplemented here.

Step contract (built by the caller/runner, NOT this module):
    {"ts": int(epoch_s), "closed": list[bar], "forming": bar|None,
     "price": float, "is_close": bool}
    bar = {"t", "open", "high", "low", "close"}  (BID prices)
    - `closed`: native candles already finalized, ascending `t`.
    - `forming`: native candle currently in progress; its `close` == `price`.
      None only before the very first native candle has started.
    - `is_close`: True on the step that finalizes the in-progress native
      candle (the runner must move `forming` into `closed` for the NEXT
      step). F2/F3 (close-only take-profits) are evaluated only on steps
      where `is_close` is True; F1, stop/BE/trailing and entries are
      evaluated on every step.

REGLA DE LECTURA (human-confirmed, see plan — do not re-derive): this is a
pullback-in-uptrend setup, so two DIFFERENT bar sets feed the indicators:
  - Regime/slope conditions (EMA8/EMA5/AO/MOM/AC "creciente/decreciente" and
    the SAR<->EMA8 relation) are computed on CLOSED NATIVE CANDLES ONLY:
    "current" = last closed candle, "previous" = second-to-last closed
    candle. They never see the forming candle (no repaint).
  - Level/trigger conditions (price vs EMA8, forming-candle body/breakout of
    the last opposite closed candle's high/low) use the live price and the
    forming candle. For the `price < EMA8` / `price > EMA8` threshold check,
    the EMA8 value used is the one from the last CLOSED candle (per the
    plan: repainted or closed EMA8 give the same threshold by convexity, so
    the closed-candle value is used directly — no separate repainted series
    is computed).

Spread/fills convention (verbatim from the plan's "Convención de spread /
fills"): lake bars are BID, spread S is constant (default 0.60), commission
0. LONG entries buy at ask (`px_in = price + S`) and exit at bid
(`px_out = exit_bid`); SHORT entries sell at bid (`px_in = price`) and exit
at ask (`px_out = exit_bid + S`). 1 ficha = 0.01 lot = 1oz, so
`pnl_usd = signed price delta` (no extra multiplier). SL/BE/trailing levels
are tracked in BID terms; the common stop is shared by all open fichas of
the current position (they all opened together at the same `px_in`) and
never loosens once it reaches break-even (monotonic ratchet).
"""
from __future__ import annotations

from .emasar_ref import (
    _atr_wilder,
    ac_series,
    ao_series,
    ema_series,
    momentum_series,
    sar_series,
)
from ._supertrend_ref import supertrend as _supertrend_series

_TAGS = ("F1", "F2", "F3")


def _closed_ohlc_lists(closed):
    highs = [b["high"] for b in closed]
    lows = [b["low"] for b in closed]
    closes = [b["close"] for b in closed]
    return highs, lows, closes


def _last_native_extreme(closed, *, bearish):
    """"Ultima vela bajista/alcista anterior" (NATIVA, cerrada): scan `closed`
    backward for the most recent candle whose body matches `bearish`
    (close<open) or bullish (close>open); doji (close==open) never matches.
    Returns (high, low) of that candle, or None if none found (warmup)."""
    for bar in reversed(closed):
        is_bearish = bar["close"] < bar["open"]
        is_bullish = bar["close"] > bar["open"]
        if bearish and is_bearish:
            return bar["high"], bar["low"]
        if (not bearish) and is_bullish:
            return bar["high"], bar["low"]
    return None


class _Regime:
    """Indicator series computed on CLOSED native candles ONLY (no repaint).
    "current" = last closed candle (index -1), "previous" = second-to-last
    closed candle (index -2)."""

    __slots__ = (
        "ema_fast_cur", "ema_fast_prev", "ema_fast_back",
        "ema_slow_cur", "ema_slow_prev", "ema_slow_back",
        "sar_cur", "ao_cur", "ao_prev", "ao_back",
        "ac_cur", "ac_prev", "ac_back",
        "mom_cur", "mom_prev", "mom_back",
        "st_trend_cur", "st_trend_prev",
        "last_close", "last_open",
    )

    def __init__(self, closed, *, ema_fast, ema_slow, sar_step, sar_max,
                 mom_period, st_period, st_mult, regime_lookback=1):
        highs, lows, closes = _closed_ohlc_lists(closed)
        n = len(closes)
        ema_f = ema_series(closes, ema_fast)
        ema_s = ema_series(closes, ema_slow)
        sar_val, _sar_trend = sar_series(highs, lows, sar_step, sar_max)
        ao = ao_series(highs, lows)
        ac = ac_series(highs, lows)
        mom = momentum_series(closes, mom_period)
        atr = _atr_wilder(highs, lows, closes, st_period)
        atr_for_st = [a if a is not None else 0.0 for a in atr]
        st_trend, _st_line = _supertrend_series(highs, lows, closes, atr_for_st, st_mult)

        def _v(series, idx):
            return series[idx] if 0 <= idx < len(series) else None

        # "back" = the K-velas-atras value used for the regime slope STATE:
        # "creciente" <=> cur > series[n-1-K], "decreciente" <=> cur < that.
        # K=1 makes ib == ip, so *_back == *_prev and behavior is unchanged.
        i, ip, ib = n - 1, n - 2, n - 1 - regime_lookback
        self.ema_fast_cur, self.ema_fast_prev = _v(ema_f, i), _v(ema_f, ip)
        self.ema_fast_back = _v(ema_f, ib)
        self.ema_slow_cur, self.ema_slow_prev = _v(ema_s, i), _v(ema_s, ip)
        self.ema_slow_back = _v(ema_s, ib)
        self.sar_cur = _v(sar_val, i)
        self.ao_cur, self.ao_prev = _v(ao, i), _v(ao, ip)
        self.ao_back = _v(ao, ib)
        self.ac_cur, self.ac_prev = _v(ac, i), _v(ac, ip)
        self.ac_back = _v(ac, ib)
        self.mom_cur, self.mom_prev = _v(mom, i), _v(mom, ip)
        self.mom_back = _v(mom, ib)
        self.st_trend_cur, self.st_trend_prev = _v(st_trend, i), _v(st_trend, ip)
        self.last_close = closes[i] if n else None
        self.last_open = closed[i]["open"] if n else None


class _Position:
    """Shared state for the (at most one) open position: side, common SL
    (BID terms), BE-armed flag, entry price/ts, and the 3 fichas (each just
    a still-open flag + per-ficha MAE/MFE accumulators in USD)."""

    __slots__ = (
        "side", "px_in", "ts_in", "sl", "sl_stage", "entry_native_idx",
        "open_fichas", "mae", "mfe",
    )

    def __init__(self, side, px_in, ts_in, sl, entry_native_idx):
        self.side = side  # "LONG" | "SHORT"
        self.px_in = px_in
        self.ts_in = ts_in
        self.sl = sl
        # sl_stage tracks WHY the current `sl` value is what it is, so the
        # eventual stop-out can report the right exit_reason without
        # re-deriving it from price comparisons: "SL_INIT" (initial offset
        # SL, never moved) -> "SL_BE" (ratchet armed at break-even) ->
        # "SL_TRAIL" (price has moved >= trail_usd past BE, ratchet trailing).
        self.sl_stage = "SL_INIT"
        self.entry_native_idx = entry_native_idx
        self.open_fichas = {tag: True for tag in _TAGS}
        self.mae = {tag: 0.0 for tag in _TAGS}
        self.mfe = {tag: 0.0 for tag in _TAGS}


def tk_bw_run(
    steps,
    *,
    spread=0.60,
    commission=0.0,
    ema_fast=5,
    ema_slow=8,
    sar_step=0.3,
    sar_max=30.0,
    mom_period=14,
    st_period=14,
    st_mult=3.0,
    regime_lookback=1,
    c1_tol=0.0,
    be_trigger=0.60,
    trail_usd=5.0,
    init_sl_offset=0.60,
    allow_long=True,
    allow_short=True,
):
    """Run the TK-BW engine over `steps`, return a flat list of trade dicts
    (one per ficha close), in chronological order of `ts_out`.

    Each trade dict: {"ts_in","ts_out","px_in","px_out","side","ficha",
    "volume":0.01,"sl","exit_reason","pnl","mae","mfe"}.
    exit_reason in {"TP1","TP2","TP3","SL_INIT","SL_BE","SL_TRAIL"}.
    """
    trades = []
    pos = None  # _Position | None
    # Index (in `closed`, i.e. count of finalized native candles) of the
    # most recent native candle in which the last ficha of a position was
    # closed -- blocks re-entry until the NEXT native candle (invariant:
    # "no re-entra en el mismo sub-paso/vela en que se cerro la ultima
    # ficha").
    blocked_native_idx = None

    for step in steps:
        closed = step["closed"]
        forming = step.get("forming")
        price = step["price"]
        ts = step["ts"]
        is_close = step.get("is_close", False)
        n_closed = len(closed)

        if n_closed == 0:
            continue

        regime = _Regime(closed, ema_fast=ema_fast, ema_slow=ema_slow,
                          sar_step=sar_step, sar_max=sar_max,
                          mom_period=mom_period, st_period=st_period,
                          st_mult=st_mult, regime_lookback=regime_lookback)

        e_fast_cur, e_fast_prev = regime.ema_fast_cur, regime.ema_fast_prev
        e_slow_cur, e_slow_prev = regime.ema_slow_cur, regime.ema_slow_prev
        # regime slope STATE compares "cur" against the K-velas-atras value;
        # with regime_lookback=1 these *_back == *_prev (behavior unchanged).
        e_fast_back = regime.ema_fast_back
        e_slow_back = regime.ema_slow_back
        sar_cur = regime.sar_cur
        ao_cur, ao_prev = regime.ao_cur, regime.ao_prev
        ac_cur, ac_prev = regime.ac_cur, regime.ac_prev
        mom_cur, mom_prev = regime.mom_cur, regime.mom_prev
        ao_back, ac_back, mom_back = regime.ao_back, regime.ac_back, regime.mom_back
        st_trend_cur, st_trend_prev = regime.st_trend_cur, regime.st_trend_prev

        have_core = None not in (e_fast_cur, e_slow_cur, sar_cur)

        # Level/trigger conditions use LIVE price + forming candle. The
        # EMA8 threshold uses the last-closed-candle value (regime.ema_slow_cur):
        # per the plan, repainted-vs-closed EMA8 give the same `price</>EMA8`
        # threshold by convexity, so no separate repainted series is built.
        forming_bullish = forming is not None and forming["close"] > forming["open"]
        forming_bearish = forming is not None and forming["close"] < forming["open"]

        # Extreme high/low reached so far this step's native candle, for
        # stop-trigger purposes: use the forming candle's accumulated
        # high/low (updated M1-by-M1 by the caller) when available, else
        # fall back to `price` (no OHLC substructure below `price` yet).
        step_high = forming["high"] if forming is not None else price
        step_low = forming["low"] if forming is not None else price

        # ---------- 1) manage the open position's common stop ----------
        if pos is not None:
            hit = (step_low <= pos.sl) if pos.side == "LONG" else (step_high >= pos.sl)

            if hit:
                hit_reason = pos.sl_stage
                sl_bid = pos.sl
                if pos.side == "LONG":
                    px_out = sl_bid
                    if forming is not None and forming["open"] < sl_bid:
                        # gap open below SL: exit at the open instead
                        px_out = forming["open"]
                else:
                    px_out = sl_bid + spread
                    if forming is not None and forming["open"] > sl_bid:
                        px_out = forming["open"] + spread

                for tag in _TAGS:
                    if not pos.open_fichas[tag]:
                        continue
                    pnl = _ficha_pnl(pos.side, pos.px_in, px_out)
                    _update_mae_mfe(pos, tag, pos.side, price, spread)
                    trades.append(_trade_dict(
                        pos.ts_in, ts, pos.px_in, px_out, pos.side, tag,
                        sl_bid, hit_reason, pnl, pos.mae[tag], pos.mfe[tag],
                    ))
                    pos.open_fichas[tag] = False
                blocked_native_idx = n_closed
                pos = None
                continue  # SL-first: no further exits/entries this step

            # BE / trailing ratchet update (based on current price). Monotonic:
            # once armed at BE, `sl` only ever moves further into profit
            # (trail_sl replaces it) and never loosens back below BE.
            if pos.side == "LONG":
                if pos.sl_stage == "SL_INIT" and price >= pos.px_in + be_trigger:
                    pos.sl = pos.px_in
                    pos.sl_stage = "SL_BE"
                if pos.sl_stage in ("SL_BE", "SL_TRAIL"):
                    trail_sl = price - trail_usd
                    if trail_sl > pos.sl:
                        pos.sl = trail_sl
                        pos.sl_stage = "SL_TRAIL"
            else:
                if pos.sl_stage == "SL_INIT" and price <= pos.px_in - be_trigger:
                    pos.sl = pos.px_in - spread
                    pos.sl_stage = "SL_BE"
                if pos.sl_stage in ("SL_BE", "SL_TRAIL"):
                    trail_sl = price + trail_usd
                    if trail_sl < pos.sl:
                        pos.sl = trail_sl
                        pos.sl_stage = "SL_TRAIL"

            # Update running MAE/MFE for still-open fichas.
            for tag in _TAGS:
                if pos.open_fichas[tag]:
                    _update_mae_mfe(pos, tag, pos.side, price, spread)

        # ---------- 2) per-ficha take-profits ----------
        if pos is not None and have_core:
            closed_this_step = []

            # F1 (TP1, intra-candle): every step. Uses live price + forming
            # candle shape, and SAR/EMA8 from the closed-candle regime.
            if pos.open_fichas["F1"]:
                if pos.side == "LONG":
                    prev_bull = _last_native_extreme(closed, bearish=False)
                    tp1 = (
                        forming_bearish
                        and prev_bull is not None
                        and price < prev_bull[1]
                        and sar_cur is not None and sar_cur > e_slow_cur
                    )
                else:
                    prev_bear = _last_native_extreme(closed, bearish=True)
                    tp1 = (
                        forming_bullish
                        and prev_bear is not None
                        and price > prev_bear[0]
                        and sar_cur is not None and sar_cur < e_slow_cur
                    )
                if tp1:
                    closed_this_step.append(("F1", "TP1"))

            # F2 / F3 (TP2/TP3, close-only): evaluated on the closed native
            # candle that just finalized (regime.last_* == that candle,
            # since `closed` already includes it by the time `is_close`
            # fires for this step per the step contract).
            if is_close:
                if pos.open_fichas["F2"]:
                    if pos.side == "LONG":
                        native_bearish = regime.last_close is not None and regime.last_close < regime.last_open
                        tp2 = (
                            native_bearish
                            and regime.last_close < e_slow_cur
                            and sar_cur is not None and sar_cur > e_slow_cur
                        )
                    else:
                        native_bullish = regime.last_close is not None and regime.last_close > regime.last_open
                        tp2 = (
                            native_bullish
                            and regime.last_close > e_slow_cur
                            and sar_cur is not None and sar_cur < e_slow_cur
                        )
                    if tp2:
                        closed_this_step.append(("F2", "TP2"))

                if pos.open_fichas["F3"] and st_trend_cur is not None and st_trend_prev is not None:
                    if pos.side == "LONG" and st_trend_prev == 1 and st_trend_cur == -1:
                        closed_this_step.append(("F3", "TP3"))
                    elif pos.side == "SHORT" and st_trend_prev == -1 and st_trend_cur == 1:
                        closed_this_step.append(("F3", "TP3"))

            for tag, reason in closed_this_step:
                if not pos.open_fichas[tag]:
                    continue
                px_out = price if pos.side == "LONG" else price + spread
                pnl = _ficha_pnl(pos.side, pos.px_in, px_out)
                _update_mae_mfe(pos, tag, pos.side, price, spread)
                trades.append(_trade_dict(
                    pos.ts_in, ts, pos.px_in, px_out, pos.side, tag,
                    pos.sl, reason, pnl, pos.mae[tag], pos.mfe[tag],
                ))
                pos.open_fichas[tag] = False

            if not any(pos.open_fichas.values()):
                blocked_native_idx = n_closed
                pos = None

        # ---------- 3) entry (only while flat) ----------
        if pos is None and have_core and forming is not None:
            if blocked_native_idx is not None and n_closed == blocked_native_idx:
                continue  # no re-entry within the native candle the last ficha closed on

            # c5-c9: regime slope read as a STATE over the last K closed
            # candles: "creciente" <=> cur > value K-back, "decreciente" <=>
            # cur < value K-back (K = regime_lookback). None-back (warmup /
            # out of range) => flag False, same as the prev-based guards.
            ema_fast_rising = e_fast_back is not None and e_fast_cur > e_fast_back
            ema_fast_falling = e_fast_back is not None and e_fast_cur < e_fast_back
            ema_slow_rising = e_slow_back is not None and e_slow_cur > e_slow_back
            ema_slow_falling = e_slow_back is not None and e_slow_cur < e_slow_back
            ao_rising = ao_back is not None and ao_cur is not None and ao_cur > ao_back
            ao_falling = ao_back is not None and ao_cur is not None and ao_cur < ao_back
            ac_rising = ac_back is not None and ac_cur is not None and ac_cur > ac_back
            ac_falling = ac_back is not None and ac_cur is not None and ac_cur < ac_back
            mom_rising = mom_back is not None and mom_cur is not None and mom_cur > mom_back
            mom_falling = mom_back is not None and mom_cur is not None and mom_cur < mom_back

            long_ok = False
            short_ok = False

            if allow_long:
                prev_bear = _last_native_extreme(closed, bearish=True)
                long_ok = (
                    price < e_slow_cur + c1_tol and forming_bullish
                    and sar_cur < e_slow_cur
                    and prev_bear is not None and price > prev_bear[0]
                    and ema_slow_rising and ema_fast_rising
                    and ao_rising and mom_rising and ac_rising
                )

            if not long_ok and allow_short:
                prev_bull = _last_native_extreme(closed, bearish=False)
                short_ok = (
                    price > e_slow_cur - c1_tol and forming_bearish
                    and sar_cur > e_slow_cur
                    and prev_bull is not None and price < prev_bull[1]
                    and ema_slow_falling and ema_fast_falling
                    and ao_falling and mom_falling and ac_falling
                )

            if long_ok:
                prev_bear = _last_native_extreme(closed, bearish=True)
                sl_bid = prev_bear[1] - init_sl_offset
                px_in = price + spread
                pos = _Position("LONG", px_in, ts, sl_bid, n_closed)
            elif short_ok:
                prev_bull = _last_native_extreme(closed, bearish=False)
                sl_bid = prev_bull[0] + init_sl_offset
                px_in = price
                pos = _Position("SHORT", px_in, ts, sl_bid, n_closed)

    return trades


def _ficha_pnl(side, px_in, px_out):
    return (px_out - px_in) if side == "LONG" else (px_in - px_out)


def _update_mae_mfe(pos, tag, side, price, spread):
    """Update running MAE/MFE (USD, per ficha) as unrealized P&L extremes
    observed over the held steps, marking-to-market at the SAME bid/ask
    convention used for a real close of this side (LONG closes at bid=price,
    SHORT closes at ask=price+spread) so MAE/MFE are directly comparable to
    the realized `pnl` of an exit at that instant."""
    px_close_now = price if side == "LONG" else price + spread
    unrealized = _ficha_pnl(side, pos.px_in, px_close_now)
    if unrealized < pos.mae[tag]:
        pos.mae[tag] = unrealized
    if unrealized > pos.mfe[tag]:
        pos.mfe[tag] = unrealized


def _trade_dict(ts_in, ts_out, px_in, px_out, side, ficha, sl, exit_reason, pnl, mae, mfe):
    return {
        "ts_in": ts_in,
        "ts_out": ts_out,
        "px_in": px_in,
        "px_out": px_out,
        "side": side,
        "ficha": ficha,
        "volume": 0.01,
        "sl": sl,
        "exit_reason": exit_reason,
        "pnl": pnl,
        "mae": mae,
        "mfe": mfe,
    }
