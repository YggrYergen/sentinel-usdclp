"""sentinel_engine.strategies.tk_bw_v2 — pure engine, TK-BW "fixes matrix".

New, additive strategy engine. TK-BW v1 (`tk_bw.py`) never fires as-written
(the forced c1 pullback-below-EMA8 and c4 breakout-above-prev-high conditions
are geometrically incompatible on real data) and loses money when forced.
This module implements a SINGLE parameterized engine that reproduces v1's
exact behavior in its default ("forced") mode, plus five orthogonal fixes
that can be toggled independently or combined: sequence (armed-breakout)
entry, ATR-based stops, R-multiple take-profits, a simplified regime filter,
and a session-hours entry gate. Spec:
docs/superpowers/plans/2026-07-21-tk-bw-backtest.md (v1) and the sibling
"fixes matrix" plan (Task 1 — Motor tk_bw_v2.py).

Pure function, no I/O, no MT5, no wall-clock. Same step contract as
`tk_bw.tk_bw_run` (see that module's docstring for the full step-contract
description): steps built by the caller/runner as
    {"ts": int(epoch_s), "closed": list[bar], "forming": bar|None,
     "price": float, "is_close": bool}
    bar = {"t", "open", "high", "low", "close"}  (BID prices)

Indicators are recomputed each step from `closed` (+ `forming`) via the
existing vendored reference implementations in `emasar_ref` /
`_supertrend_ref` only — no indicator math is reimplemented here.

Spread/fills/pnl/MAE-MFE/trade-dict convention is IDENTICAL to `tk_bw.py`:
spread constant (default 0.60), commission 0 (param kept for signature
parity only, unused). LONG entries buy at ask (`px_in = price + spread`)
and exit at bid; SHORT entries sell at bid (`px_in = price`) and exit at ask
(`px_out = exit_bid + spread`). 1 ficha = 0.01 lot = 1oz, so
`pnl_usd = signed price delta`. 3 independent fichas (F1/F2/F3) share one
common stop, tracked in BID terms, monotonic ratchet (never loosens once
armed at break-even).

PARITY (binding, see tests/strategies/test_tk_bw_v2.py): `tk_bw_v2_run`
called with `entry_mode="forced", regime_mode="full5", stop_mode="fixed",
tp_mode="pattern"` and the same params as `tk_bw.tk_bw_run` must produce the
byte-identical trade list.
"""
from __future__ import annotations

from datetime import datetime, timezone

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
    closed candle (index -2), "back" = K (regime_lookback) closed candles
    before current (index -1-K)."""

    __slots__ = (
        "ema_fast_cur", "ema_fast_prev", "ema_fast_back",
        "ema_slow_cur", "ema_slow_prev", "ema_slow_back",
        "sar_cur", "ao_cur", "ao_prev", "ao_back",
        "ac_cur", "ac_prev", "ac_back",
        "mom_cur", "mom_prev", "mom_back",
        "st_trend_cur", "st_trend_prev",
        "atr_cur",
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
        self.atr_cur = _v(atr, i)
        self.last_close = closes[i] if n else None
        self.last_open = closed[i]["open"] if n else None


class _Position:
    """Shared state for the (at most one) open position: side, common SL
    (BID terms), BE-armed flag, entry price/ts, and the 3 fichas (each just
    a still-open flag + per-ficha MAE/MFE accumulators in USD). `atr_entry`
    is the ATR value frozen at entry (stop_mode="atr" only, else None).
    `r_target` is the frozen R distance (tp_mode="r" only, else None) and
    `entry_bid` is the BID-terms entry price used as the R origin."""

    __slots__ = (
        "side", "px_in", "ts_in", "sl", "sl_stage", "entry_native_idx",
        "open_fichas", "mae", "mfe", "atr_entry", "entry_bid", "r_dist",
    )

    def __init__(self, side, px_in, ts_in, sl, entry_native_idx, *,
                 atr_entry=None, entry_bid=None, r_dist=None):
        self.side = side  # "LONG" | "SHORT"
        self.px_in = px_in
        self.ts_in = ts_in
        self.sl = sl
        # sl_stage tracks WHY the current `sl` value is what it is, so the
        # eventual stop-out can report the right exit_reason without
        # re-deriving it from price comparisons: "SL_INIT" (initial offset
        # SL, never moved) -> "SL_BE" (ratchet armed at break-even) ->
        # "SL_TRAIL" (price has moved >= trigger past BE, ratchet trailing).
        self.sl_stage = "SL_INIT"
        self.entry_native_idx = entry_native_idx
        self.open_fichas = {tag: True for tag in _TAGS}
        self.mae = {tag: 0.0 for tag in _TAGS}
        self.mfe = {tag: 0.0 for tag in _TAGS}
        self.atr_entry = atr_entry
        self.entry_bid = entry_bid
        self.r_dist = r_dist


class _Sequence:
    """Armed-breakout state machine bookkeeping for `entry_mode="sequence"`,
    LONG and SHORT tracked independently. `armed`: bool. `breakout_level`:
    price that, when crossed by live `price`, triggers entry. `pullback`:
    the touch candle's opposite extreme (low for LONG / high for SHORT),
    used as the `fixed` initial-SL reference. `armed_until`: native-candle
    count (n_closed) after which the arming expires if no breakout fired."""

    __slots__ = ("armed", "breakout_level", "pullback", "armed_until")

    def __init__(self):
        self.armed = False
        self.breakout_level = None
        self.pullback = None
        self.armed_until = None


def tk_bw_v2_run(
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
    regime_lookback=3,
    # --- entrada ---
    entry_mode="forced",        # "forced" | "sequence"
    c1_tol=3.0,                 # solo forced
    seq_timeout=6,               # sequence: velas nativas armado antes de desarmar
    # --- regimen ---
    regime_mode="full5",        # "full5" | "simple"
    session_hours=None,         # None | (start_h, end_h) hora del bar-clock, gate SOLO de entrada
    # --- stops ---
    stop_mode="fixed",          # "fixed" | "atr"
    init_sl_offset=0.60, be_trigger=0.60, trail_usd=5.0,    # fixed
    atr_sl_mult=1.5, atr_be_mult=1.0, atr_trail_mult=2.5,   # atr (ATR14 congelado al entrar)
    # --- take profits ---
    tp_mode="pattern",          # "pattern" | "r"
    r1_mult=1.0, r2_mult=2.0,   # r: F1 a 1R, F2 a 2R, F3 solo trailing
    allow_long=True,
    allow_short=True,
    return_state=False,
):
    """Run the TK-BW v2 engine over `steps`, return a flat list of trade
    dicts (one per ficha close), in chronological order of `ts_out`.

    Each trade dict: {"ts_in","ts_out","px_in","px_out","side","ficha",
    "volume":0.01,"sl","exit_reason","pnl","mae","mfe"}.
    exit_reason in {"TP1","TP2","TP3","SL_INIT","SL_BE","SL_TRAIL"} in
    tp_mode="pattern"; in tp_mode="r" the TP reasons are "TP1R"/"TP2R"
    instead (F3 never take-profits in "r" mode -- TP3-SuperTrend does not
    exist there; F3 only exits via SL/BE/trail).

    `return_state` (additive, default False, parity-by-construction for the
    live reconciler): when True, returns `(trades, snapshot)` instead of a
    bare `trades` list -- `trades` is BYTE-IDENTICAL to the default-off
    output. `snapshot` is {"open": {tag: {"side","entry","sl","max_fav"}},
    "last_bar_exits": {}, "last_idx": len(steps)-1}: the still-open fichas
    (LONG/SHORT + current SL) AFTER processing the last step, in the SAME
    shape `simular_variant(return_state=True)` emits, so the SAME ladder
    reconciler applies with no change. `last_bar_exits` is always {} here
    (TK-BW v2's SL-first same-step exit already lands in `trades`; there is
    no separate same-bar-exit-fallback concept for this engine yet). Empty
    `steps` or a flat end-state -> {"open": {}, ...}."""
    trades = []
    pos = None  # _Position | None
    # Index (in `closed`, i.e. count of finalized native candles) of the
    # most recent native candle in which the last ficha of a position was
    # closed -- blocks re-entry until the NEXT native candle (invariant:
    # "no re-entra en el mismo sub-paso/vela en que se cerro la ultima
    # ficha").
    blocked_native_idx = None

    seq_long = _Sequence()
    seq_short = _Sequence()
    prev_n_closed = 0

    for step in steps:
        closed = step["closed"]
        forming = step.get("forming")
        price = step["price"]
        ts = step["ts"]
        is_close = step.get("is_close", False)
        n_closed = len(closed)

        if n_closed == 0:
            continue

        new_native_candle = n_closed > prev_n_closed

        regime = _Regime(closed, ema_fast=ema_fast, ema_slow=ema_slow,
                          sar_step=sar_step, sar_max=sar_max,
                          mom_period=mom_period, st_period=st_period,
                          st_mult=st_mult, regime_lookback=regime_lookback)

        e_fast_cur = regime.ema_fast_cur
        e_slow_cur, e_slow_prev = regime.ema_slow_cur, regime.ema_slow_prev
        e_fast_back = regime.ema_fast_back
        e_slow_back = regime.ema_slow_back
        sar_cur = regime.sar_cur
        ao_cur = regime.ao_cur
        ac_cur = regime.ac_cur
        mom_cur = regime.mom_cur
        ao_back, ac_back, mom_back = regime.ao_back, regime.ac_back, regime.mom_back
        st_trend_cur, st_trend_prev = regime.st_trend_cur, regime.st_trend_prev

        have_core = None not in (e_fast_cur, e_slow_cur, sar_cur)

        # Level/trigger conditions use LIVE price + forming candle. The
        # EMA8 threshold uses the last-closed-candle value (regime.ema_slow_cur).
        forming_bullish = forming is not None and forming["close"] > forming["open"]
        forming_bearish = forming is not None and forming["close"] < forming["open"]

        step_high = forming["high"] if forming is not None else price
        step_low = forming["low"] if forming is not None else price

        # ---------- regime flags (regime_mode) ----------
        if regime_mode == "simple":
            regime_long = (
                st_trend_cur is not None and st_trend_cur == 1
                and e_slow_cur is not None and e_slow_back is not None
                and e_slow_cur > e_slow_back
            )
            regime_short = (
                st_trend_cur is not None and st_trend_cur == -1
                and e_slow_cur is not None and e_slow_back is not None
                and e_slow_cur < e_slow_back
            )
        else:  # "full5"
            ema_fast_rising = e_fast_back is not None and e_fast_cur is not None and e_fast_cur > e_fast_back
            ema_fast_falling = e_fast_back is not None and e_fast_cur is not None and e_fast_cur < e_fast_back
            ema_slow_rising = e_slow_back is not None and e_slow_cur is not None and e_slow_cur > e_slow_back
            ema_slow_falling = e_slow_back is not None and e_slow_cur is not None and e_slow_cur < e_slow_back
            ao_rising = ao_back is not None and ao_cur is not None and ao_cur > ao_back
            ao_falling = ao_back is not None and ao_cur is not None and ao_cur < ao_back
            ac_rising = ac_back is not None and ac_cur is not None and ac_cur > ac_back
            ac_falling = ac_back is not None and ac_cur is not None and ac_cur < ac_back
            mom_rising = mom_back is not None and mom_cur is not None and mom_cur > mom_back
            mom_falling = mom_back is not None and mom_cur is not None and mom_cur < mom_back
            regime_long = (
                sar_cur is not None and e_slow_cur is not None and sar_cur < e_slow_cur
                and ema_slow_rising and ema_fast_rising
                and ao_rising and mom_rising and ac_rising
            )
            regime_short = (
                sar_cur is not None and e_slow_cur is not None and sar_cur > e_slow_cur
                and ema_slow_falling and ema_fast_falling
                and ao_falling and mom_falling and ac_falling
            )

        # ---------- session gate (entries only) ----------
        session_ok = True
        if session_hours is not None:
            start_h, end_h = session_hours
            hour_utc = datetime.fromtimestamp(ts, tz=timezone.utc).hour
            session_ok = start_h <= hour_utc < end_h

        # ---------- sequence: arming bookkeeping (runs regardless of gate) ----------
        if entry_mode == "sequence" and new_native_candle and n_closed >= 1:
            new_candle = closed[-1]
            if allow_long and regime_long and e_slow_cur is not None and new_candle["low"] <= e_slow_cur:
                seq_long.armed = True
                seq_long.breakout_level = new_candle["high"]
                seq_long.pullback = new_candle["low"]
                seq_long.armed_until = n_closed + seq_timeout
            if allow_short and regime_short and e_slow_cur is not None and new_candle["high"] >= e_slow_cur:
                seq_short.armed = True
                seq_short.breakout_level = new_candle["low"]
                seq_short.pullback = new_candle["high"]
                seq_short.armed_until = n_closed + seq_timeout

            # DESARME: timeout or loss of regime.
            if seq_long.armed and (n_closed > seq_long.armed_until or not regime_long):
                seq_long.armed = False
            if seq_short.armed and (n_closed > seq_short.armed_until or not regime_short):
                seq_short.armed = False

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
                prev_n_closed = n_closed
                continue  # SL-first: no further exits/entries this step

            # BE / trailing ratchet update (based on current price). Monotonic:
            # once armed at BE, `sl` only ever moves further into profit
            # (trail_sl replaces it) and never loosens back below BE.
            if stop_mode == "atr":
                be_trig = atr_be_mult * pos.atr_entry
                trail_dist = atr_trail_mult * pos.atr_entry
            else:
                be_trig = be_trigger
                trail_dist = trail_usd

            if pos.side == "LONG":
                if pos.sl_stage == "SL_INIT" and price >= pos.px_in + be_trig:
                    pos.sl = pos.px_in
                    pos.sl_stage = "SL_BE"
                if pos.sl_stage in ("SL_BE", "SL_TRAIL"):
                    trail_sl = price - trail_dist
                    if trail_sl > pos.sl:
                        pos.sl = trail_sl
                        pos.sl_stage = "SL_TRAIL"
            else:
                if pos.sl_stage == "SL_INIT" and price <= pos.px_in - be_trig:
                    pos.sl = pos.px_in - spread
                    pos.sl_stage = "SL_BE"
                if pos.sl_stage in ("SL_BE", "SL_TRAIL"):
                    trail_sl = price + trail_dist
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

            if tp_mode == "r":
                r_dist = pos.r_dist
                if pos.side == "LONG":
                    if pos.open_fichas["F1"] and price >= pos.entry_bid + r1_mult * r_dist:
                        closed_this_step.append(("F1", "TP1R"))
                    if pos.open_fichas["F2"] and price >= pos.entry_bid + r2_mult * r_dist:
                        closed_this_step.append(("F2", "TP2R"))
                else:
                    if pos.open_fichas["F1"] and price <= pos.entry_bid - r1_mult * r_dist:
                        closed_this_step.append(("F1", "TP1R"))
                    if pos.open_fichas["F2"] and price <= pos.entry_bid - r2_mult * r_dist:
                        closed_this_step.append(("F2", "TP2R"))
                # F3: no take-profit in "r" mode (SL/BE/trail only).
            else:  # "pattern"
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
        if pos is None and have_core and forming is not None and session_ok:
            re_entry_blocked = blocked_native_idx is not None and n_closed == blocked_native_idx

            if not re_entry_blocked:
                if entry_mode == "sequence":
                    pos = _try_sequence_entry(
                        seq_long, seq_short, price, closed, n_closed, ts,
                        regime_long=regime_long, regime_short=regime_short,
                        allow_long=allow_long, allow_short=allow_short,
                        spread=spread, stop_mode=stop_mode,
                        init_sl_offset=init_sl_offset, atr_sl_mult=atr_sl_mult,
                        atr_cur=regime.atr_cur, tp_mode=tp_mode,
                    )
                else:  # "forced"
                    pos = _try_forced_entry(
                        price, closed, n_closed, ts, regime,
                        forming_bullish=forming_bullish, forming_bearish=forming_bearish,
                        c1_tol=c1_tol, allow_long=allow_long, allow_short=allow_short,
                        spread=spread, stop_mode=stop_mode,
                        init_sl_offset=init_sl_offset, atr_sl_mult=atr_sl_mult,
                        tp_mode=tp_mode,
                    )

        prev_n_closed = n_closed

    if not return_state:
        return trades

    last_idx = len(steps) - 1
    open_state: dict[str, Any] = {}
    if pos is not None:
        for tag in _TAGS:
            if pos.open_fichas[tag]:
                open_state[tag] = {"side": pos.side, "entry": pos.px_in,
                                    "sl": pos.sl, "max_fav": pos.mfe[tag]}
    return trades, {"open": open_state, "last_bar_exits": {}, "last_idx": last_idx}


def _try_forced_entry(price, closed, n_closed, ts, regime, *,
                       forming_bullish, forming_bearish, c1_tol,
                       allow_long, allow_short, spread, stop_mode,
                       init_sl_offset, atr_sl_mult, tp_mode):
    """v1-identical c1..c9 forced entry logic (regime slope read as
    state-over-K via regime.*_back, same as tk_bw.py's forced path)."""
    e_fast_cur, e_fast_back = regime.ema_fast_cur, regime.ema_fast_back
    e_slow_cur, e_slow_back = regime.ema_slow_cur, regime.ema_slow_back
    sar_cur = regime.sar_cur
    ao_cur, ao_back = regime.ao_cur, regime.ao_back
    ac_cur, ac_back = regime.ac_cur, regime.ac_back
    mom_cur, mom_back = regime.mom_cur, regime.mom_back

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
        px_in = price + spread
        return _open_position("LONG", px_in, price, ts, n_closed,
                               stop_mode=stop_mode, atr_cur=regime.atr_cur,
                               atr_sl_mult=atr_sl_mult, tp_mode=tp_mode,
                               fixed_sl_ref=prev_bear[1], init_sl_offset=init_sl_offset)
    if short_ok:
        prev_bull = _last_native_extreme(closed, bearish=False)
        px_in = price
        return _open_position("SHORT", px_in, price, ts, n_closed,
                               stop_mode=stop_mode, atr_cur=regime.atr_cur,
                               atr_sl_mult=atr_sl_mult, tp_mode=tp_mode,
                               fixed_sl_ref=prev_bull[0], init_sl_offset=init_sl_offset)
    return None


def _try_sequence_entry(seq_long, seq_short, price, closed, n_closed, ts, *,
                         regime_long, regime_short, allow_long, allow_short,
                         spread, stop_mode, init_sl_offset, atr_sl_mult,
                         atr_cur, tp_mode):
    """Armed-breakout trigger: intrabar, requires `armed` AND current-step
    regime AND flat (caller already checked flat/blocked). Entering
    disarms BOTH sides. LONG checked before SHORT (mirrors forced-mode
    LONG-first precedence)."""
    if allow_long and seq_long.armed and regime_long and price > seq_long.breakout_level:
        px_in = price + spread
        pos = _open_position("LONG", px_in, price, ts, n_closed,
                              stop_mode=stop_mode, atr_cur=atr_cur,
                              atr_sl_mult=atr_sl_mult, tp_mode=tp_mode,
                              fixed_sl_ref=None, init_sl_offset=init_sl_offset,
                              sequence_pullback=seq_long.pullback)
        seq_long.armed = False
        seq_short.armed = False
        return pos

    if allow_short and seq_short.armed and regime_short and price < seq_short.breakout_level:
        px_in = price
        pos = _open_position("SHORT", px_in, price, ts, n_closed,
                              stop_mode=stop_mode, atr_cur=atr_cur,
                              atr_sl_mult=atr_sl_mult, tp_mode=tp_mode,
                              fixed_sl_ref=None, init_sl_offset=init_sl_offset,
                              sequence_pullback=seq_short.pullback)
        seq_long.armed = False
        seq_short.armed = False
        return pos

    return None


def _open_position(side, px_in, price, ts, n_closed, *, stop_mode, atr_cur,
                    atr_sl_mult, tp_mode, fixed_sl_ref, init_sl_offset,
                    sequence_pullback=None):
    """Build a `_Position` with the SL initialized per `stop_mode` and, if
    `tp_mode == "r"`, the frozen R distance. `entry_bid` = `price` at the
    entry step (LONG pays spread on top for px_in; SHORT's entry_bid ==
    px_in). ATR entry mode: if ATR is None, do NOT enter (return None)."""
    entry_bid = price

    if stop_mode == "atr":
        if atr_cur is None:
            return None
        sl = (entry_bid - atr_sl_mult * atr_cur) if side == "LONG" else (entry_bid + atr_sl_mult * atr_cur)
        atr_entry = atr_cur
    else:  # "fixed"
        if fixed_sl_ref is not None:
            # forced mode: fixed_sl_ref = prev_bear.low (LONG) / prev_bull.high (SHORT)
            sl = (fixed_sl_ref - init_sl_offset) if side == "LONG" else (fixed_sl_ref + init_sl_offset)
        else:
            # sequence mode: pullback_low (LONG) / pullback_high (SHORT)
            sl = (sequence_pullback - init_sl_offset) if side == "LONG" else (sequence_pullback + init_sl_offset)
        atr_entry = None

    r_dist = None
    if tp_mode == "r":
        r_dist = abs(entry_bid - sl)

    return _Position(side, px_in, ts, sl, n_closed,
                      atr_entry=atr_entry, entry_bid=entry_bid, r_dist=r_dist)


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
