"""tests/strategies/test_tk_bw_v2.py -- TK-BW v2 "fixes matrix" engine.

Covers the 7 test cases from the plan (Task 1):
  1. PARITY  -- forced/full5/fixed/pattern reproduces tk_bw.tk_bw_run exactly.
  2. sequence entry -- touch arms, breakout triggers intrabar, px_in=price+spread.
  3. sequence timeout -- no breakout within seq_timeout candles => no entry.
  4. sequence regime-loss -- regime dropping disarms => no entry.
  5. atr stops -- SL at 1.5*ATR, BE at 1.0*ATR, trail 2.5*ATR ratchet.
  6. r take-profits -- F1 at +1R / F2 at +2R (TP1R/TP2R), F3 no TP3.
  7. session gate -- entry blocked outside (a,b), open position still managed.

Synthetic deterministic fixtures only (no lake, no network). The natural
LONG-entry fixture is imported from the v1 suite so the parity test runs over
a real multi-ficha run, not two empty lists.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sentinel_engine.strategies.tk_bw import tk_bw_run
from sentinel_engine.strategies.tk_bw_v2 import tk_bw_v2_run

from tests.strategies.test_tk_bw import (
    T0,
    _bar,
    _entry_step,
    _long_entry_closed_bars,
    _open_long_steps,
)


# ==========================================================================
# 1) PARITY: forced/full5/fixed/pattern == tk_bw.tk_bw_run
# ==========================================================================
def _parity_steps():
    """Natural LONG entry + BE + trailing ratchet + a hard drop that stops
    out -- a non-trivial multi-step run producing 3 fichas via SL_TRAIL."""
    steps, closed, forming = _open_long_steps()
    px_in = 98.50 + 0.60
    prices = [px_in + 1.0, px_in + 6.0, px_in + 10.0, px_in + 8.0, px_in + 12.0]
    prev_close = forming["close"]
    for k, p in enumerate(prices):
        f = dict(forming, open=prev_close, high=max(prev_close, p) + 0.05,
                 low=min(prev_close, p) - 0.05, close=p)
        steps.append(_entry_step(closed, f, p, ts=T0 + 41 * 300 + 60 * (k + 1)))
        prev_close = p
    trail_sl_expected = (px_in + 12.0) - 5.0
    stop_close = trail_sl_expected - 0.4
    f_stop = dict(forming, open=prev_close, high=prev_close + 0.05,
                  low=trail_sl_expected - 0.5, close=stop_close)
    steps.append(_entry_step(closed, f_stop, stop_close, ts=T0 + 41 * 300 + 400))
    return steps


def test_parity_forced_full5_fixed_pattern_matches_v1():
    steps = _parity_steps()
    # Same params on BOTH engines: v1 defaults but with regime_lookback=3,
    # c1_tol=3.0 (the plan's parity spec), allow_short=False.
    common = dict(
        spread=0.60, commission=0.0, ema_fast=5, ema_slow=8, sar_step=0.3,
        sar_max=30.0, mom_period=14, st_period=14, st_mult=3.0,
        regime_lookback=3, c1_tol=3.0, be_trigger=0.60, trail_usd=5.0,
        init_sl_offset=0.60, allow_long=True, allow_short=False,
    )
    v1 = tk_bw_run(steps, **common)
    v2 = tk_bw_v2_run(
        steps, entry_mode="forced", regime_mode="full5", stop_mode="fixed",
        tp_mode="pattern", **common,
    )
    assert len(v1) == 3  # non-trivial: the fixture really opens a position
    assert v2 == v1


def test_parity_holds_on_initial_sl_stopout():
    steps, closed, forming = _open_long_steps()
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=T0 + 41 * 300 + 60))
    common = dict(regime_lookback=3, c1_tol=3.0, allow_short=False)
    v1 = tk_bw_run(steps, **common)
    v2 = tk_bw_v2_run(steps, entry_mode="forced", regime_mode="full5",
                      stop_mode="fixed", tp_mode="pattern", **common)
    assert len(v1) == 3
    assert v2 == v1


# ==========================================================================
# sequence-mode fixtures
# ==========================================================================
def _seq_closed_bars():
    """Reuse the verified natural-uptrend closed bars: the last two closed
    bars make full5 regime_long True (SAR<EMA8, all 5 rising). The last
    closed candle (the spike) has low=97.95 <= EMA8 (~98.80) so it also
    satisfies the sequence touch (low<=EMA8) -- arming at that candle."""
    return _long_entry_closed_bars()


def _seq_step(closed, price, *, ts, forming_open=None, is_close=False):
    fo = forming_open if forming_open is not None else price
    forming = _bar(ts, fo, max(fo, price) + 0.05, min(fo, price) - 0.05, price)
    return _entry_step(closed, forming, price, is_close=is_close, ts=ts)


# ==========================================================================
# 2) sequence: touch arms, breakout triggers intrabar, px_in=price+spread
# ==========================================================================
def test_sequence_touch_arms_breakout_triggers_long():
    closed = _seq_closed_bars()
    breakout_level = closed[-1]["high"]  # spike candle high (arming level)
    # First step (new native candle just appeared): price below breakout ->
    # arms but does NOT trigger. Then a step where price breaks above the
    # level -> LONG enters intrabar at px_in = price + spread.
    below = breakout_level - 0.5
    step_arm = _seq_step(closed, below, ts=T0 + 41 * 300)
    trigger_price = breakout_level + 0.30
    step_fire = _seq_step(closed, trigger_price, ts=T0 + 41 * 300 + 60,
                          forming_open=below)
    # A follow-on stop-out so fichas close and we can inspect px_in.
    step_stop = _seq_step(closed, 90.0, ts=T0 + 41 * 300 + 120, forming_open=90.0)
    trades = tk_bw_v2_run(
        [step_arm, step_fire, step_stop],
        entry_mode="sequence", regime_mode="full5", stop_mode="fixed",
        tp_mode="pattern", allow_short=False,
    )
    assert len(trades) == 3
    assert {t["side"] for t in trades} == {"LONG"}
    for t in trades:
        assert round(t["px_in"], 6) == round(trigger_price + 0.60, 6)
    # SL is the pullback_low (spike candle low) - init_sl_offset.
    pullback_low = closed[-1]["low"]
    # first fichas stopped out at SL_INIT (dropped straight to 90)
    assert all(t["exit_reason"] == "SL_INIT" for t in trades)
    assert round(trades[0]["sl"], 6) == round(pullback_low - 0.60, 6)


def test_sequence_no_trigger_without_breakout():
    closed = _seq_closed_bars()
    breakout_level = closed[-1]["high"]
    below = breakout_level - 0.5
    # arms, but price never exceeds the breakout level -> no entry.
    steps = [
        _seq_step(closed, below, ts=T0 + 41 * 300),
        _seq_step(closed, below - 0.1, ts=T0 + 41 * 300 + 60),
    ]
    trades = tk_bw_v2_run(
        steps, entry_mode="sequence", regime_mode="full5",
        stop_mode="fixed", tp_mode="pattern", allow_short=False,
    )
    assert trades == []


# ==========================================================================
# 3) sequence: timeout disarms
# ==========================================================================
def test_sequence_timeout_disarms():
    closed_arm = _seq_closed_bars()
    breakout_level = closed_arm[-1]["high"]
    below = breakout_level - 0.5
    # Arm on the spike candle, then let seq_timeout+1 NEW native candles
    # elapse with no breakout. The arming must expire, so a late breakout
    # does NOT enter. Append neutral candles to `closed` (do NOT re-touch
    # EMA8 to re-arm: keep highs far below EMA8) each step.
    seq_timeout = 2
    steps = [_seq_step(closed_arm, below, ts=T0 + 41 * 300)]
    # advance native candles beyond armed_until without breakout
    closed = list(closed_arm)
    for k in range(seq_timeout + 1):
        # new closed candle high stays below EMA8-touch? we only need NO
        # breakout; append a candle and a step over the grown `closed`.
        nc = _bar(T0 + (41 + k) * 300, 96.0, 96.05, 95.90, 95.95)
        closed = closed + [nc]
        steps.append(_seq_step(closed, below, ts=T0 + (42 + k) * 300))
    # Now a genuine breakout above the ORIGINAL level -- must be ignored
    # because the arm expired.
    steps.append(_seq_step(closed, breakout_level + 1.0,
                           ts=T0 + (46) * 300, forming_open=below))
    trades = tk_bw_v2_run(
        steps, entry_mode="sequence", regime_mode="full5",
        stop_mode="fixed", tp_mode="pattern", allow_short=False,
        seq_timeout=seq_timeout,
    )
    assert trades == []


# ==========================================================================
# 4) sequence: loss of regime disarms
# ==========================================================================
def test_sequence_regime_loss_disarms():
    closed_arm = _seq_closed_bars()
    breakout_level = closed_arm[-1]["high"]
    below = breakout_level - 0.5
    # Arm on the spike, then append a NEW closed candle that BREAKS the
    # uptrend regime (a sharp bearish candle drops EMAs/AO/etc), so
    # regime_long goes False on the next new-candle step -> disarm. Then a
    # breakout must be ignored.
    steps = [_seq_step(closed_arm, below, ts=T0 + 41 * 300)]
    bearish = _bar(T0 + 41 * 300, 101.0, 101.05, 90.0, 90.10)  # big red candle
    closed2 = closed_arm + [bearish]
    # new-native-candle step: regime recomputed on closed2 -> no longer long.
    steps.append(_seq_step(closed2, below, ts=T0 + 42 * 300))
    # breakout attempt over the original level -> ignored (disarmed).
    steps.append(_seq_step(closed2, breakout_level + 1.0,
                           ts=T0 + 42 * 300 + 60, forming_open=below))
    trades = tk_bw_v2_run(
        steps, entry_mode="sequence", regime_mode="full5",
        stop_mode="fixed", tp_mode="pattern", allow_short=False,
    )
    assert trades == []


# ==========================================================================
# 5) atr stops: SL 1.5*ATR, BE 1.0*ATR, trail 2.5*ATR
# ==========================================================================
def _atr_of(closed, period=14):
    from sentinel_engine.strategies.emasar_ref import _atr_wilder
    highs = [b["high"] for b in closed]
    lows = [b["low"] for b in closed]
    closes = [b["close"] for b in closed]
    atr = _atr_wilder(highs, lows, closes, period)
    return atr[-1]


def test_atr_initial_sl_be_and_trail():
    steps, closed, forming = _open_long_steps()
    atr = _atr_of(closed, 14)
    assert atr is not None
    entry_bid = 98.50
    px_in = entry_bid + 0.60
    expected_sl_init = entry_bid - 1.5 * atr
    # Push price up: BE arms at entry_bid... wait, LONG BE arms when
    # price >= px_in + atr_be_mult*ATR -> then SL ratchets to px_in, and
    # trailing uses 2.5*ATR distance. Drive price to a peak then crash.
    peak = px_in + 1.0 * atr + 30.0  # comfortably past BE + trail arming
    f_peak = dict(forming, open=forming["close"], high=peak + 0.05,
                  low=forming["close"] - 0.05, close=peak)
    steps.append(_entry_step(closed, f_peak, peak, ts=T0 + 41 * 300 + 60))
    trail_sl_expected = peak - 2.5 * atr
    stop_close = trail_sl_expected - 0.5
    f_stop = dict(forming, open=peak, high=peak + 0.05,
                  low=trail_sl_expected - 1.0, close=stop_close)
    steps.append(_entry_step(closed, f_stop, stop_close, ts=T0 + 41 * 300 + 120))
    trades = tk_bw_v2_run(
        steps, entry_mode="forced", regime_mode="full5", stop_mode="atr",
        tp_mode="pattern", regime_lookback=3, c1_tol=3.0, allow_short=False,
        atr_sl_mult=1.5, atr_be_mult=1.0, atr_trail_mult=2.5,
    )
    assert len(trades) == 3
    for t in trades:
        assert t["exit_reason"] == "SL_TRAIL"
        assert round(t["sl"], 6) == round(trail_sl_expected, 6)
    # Confirm the FROZEN initial SL was the 1.5*ATR level by re-running with
    # an immediate stop-out (no BE/trail).
    steps2, closed2, forming2 = _open_long_steps()
    drop = expected_sl_init - 0.2
    f_drop = dict(forming2, open=forming2["close"], high=forming2["close"] + 0.05,
                  low=drop - 0.5, close=drop)
    steps2.append(_entry_step(closed2, f_drop, drop, ts=T0 + 41 * 300 + 60))
    trades2 = tk_bw_v2_run(
        steps2, entry_mode="forced", regime_mode="full5", stop_mode="atr",
        tp_mode="pattern", regime_lookback=3, c1_tol=3.0, allow_short=False,
        atr_sl_mult=1.5,
    )
    assert len(trades2) == 3
    for t in trades2:
        assert t["exit_reason"] == "SL_INIT"
        assert round(t["sl"], 6) == round(expected_sl_init, 6)


def test_atr_none_does_not_enter():
    # Only a handful of closed candles -> ATR14 is None -> no entry even if
    # the forced setup would otherwise fire. (Warmup: fewer than 14 bars.)
    closed = _long_entry_closed_bars()[:10]
    forming = _bar(T0 + 100, 98.2, 98.6, 98.1, 98.5)
    step = _entry_step(closed, forming, 98.5, ts=T0 + 100)
    trades = tk_bw_v2_run(
        [step], entry_mode="forced", regime_mode="full5", stop_mode="atr",
        tp_mode="pattern", allow_short=False,
    )
    assert trades == []


# ==========================================================================
# 6) r take-profits: F1 +1R (TP1R), F2 +2R (TP2R), F3 no TP3
# ==========================================================================
def test_r_targets_close_f1_f2_and_f3_has_no_tp3():
    steps, closed, forming = _open_long_steps()
    # entry_bid = 98.50, fixed SL = 97.98 - 0.60 = 97.38 -> R = 1.12.
    entry_bid = 98.50
    sl_bid = 97.98 - 0.60
    R = abs(entry_bid - sl_bid)
    # Step A: price rises to +1R exactly -> F1 closes TP1R (not F2 yet).
    p1 = entry_bid + 1.0 * R
    fA = dict(forming, open=forming["close"], high=p1 + 0.05,
              low=forming["close"] - 0.05, close=p1)
    steps.append(_entry_step(closed, fA, p1, ts=T0 + 41 * 300 + 60))
    # Step B: price rises to +2R -> F2 closes TP2R. F3 stays open (no TP3
    # in r-mode). Then a trailing/SL exit takes F3.
    p2 = entry_bid + 2.0 * R
    fB = dict(forming, open=p1, high=p2 + 0.05, low=p1 - 0.05, close=p2)
    steps.append(_entry_step(closed, fB, p2, ts=T0 + 41 * 300 + 120))
    # Step C: a big drop stops F3 out (trailing already armed).
    fC = dict(forming, open=p2, high=p2 + 0.05, low=80.0, close=80.5)
    steps.append(_entry_step(closed, fC, 80.5, ts=T0 + 41 * 300 + 180))

    trades = tk_bw_v2_run(
        steps, entry_mode="forced", regime_mode="full5", stop_mode="fixed",
        tp_mode="r", regime_lookback=3, c1_tol=3.0, allow_short=False,
        r1_mult=1.0, r2_mult=2.0,
    )
    by_ficha = {t["ficha"]: t for t in trades}
    assert set(by_ficha) == {"F1", "F2", "F3"}
    assert by_ficha["F1"]["exit_reason"] == "TP1R"
    assert by_ficha["F2"]["exit_reason"] == "TP2R"
    # F3 exits via a stop, never TP3.
    assert by_ficha["F3"]["exit_reason"] in {"SL_TRAIL", "SL_BE", "SL_INIT"}
    assert not any(t["exit_reason"] == "TP3" for t in trades)
    # px_out convention for LONG TP = price (bid).
    assert round(by_ficha["F1"]["px_out"], 6) == round(p1, 6)
    assert round(by_ficha["F2"]["px_out"], 6) == round(p2, 6)


# ==========================================================================
# 7) session gate: blocks entry outside (a,b), open position still managed
# ==========================================================================
def _hour_of(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).hour


def test_session_gate_blocks_entry_outside_window():
    steps, closed, forming = _open_long_steps()
    entry_ts = steps[0]["ts"]
    h = _hour_of(entry_ts)
    # A window that EXCLUDES the entry hour -> no entry at all.
    out_window = ((h + 1) % 24, (h + 2) % 24)
    if out_window[0] >= out_window[1]:
        out_window = (h + 1, h + 2)  # keep a<b; entry hour h not in [h+1,h+2)
    trades = tk_bw_v2_run(
        steps, entry_mode="forced", regime_mode="full5", stop_mode="fixed",
        tp_mode="pattern", regime_lookback=3, c1_tol=3.0, allow_short=False,
        session_hours=out_window,
    )
    assert trades == []


def test_session_gate_allows_entry_inside_window():
    steps, closed, forming = _open_long_steps()
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=T0 + 41 * 300 + 60))
    entry_ts = steps[0]["ts"]
    h = _hour_of(entry_ts)
    in_window = (h, (h + 1) if h + 1 <= 24 else 24)
    trades = tk_bw_v2_run(
        steps, entry_mode="forced", regime_mode="full5", stop_mode="fixed",
        tp_mode="pattern", regime_lookback=3, c1_tol=3.0, allow_short=False,
        session_hours=in_window,
    )
    assert len(trades) == 3  # entered inside window and stopped out


def test_session_gate_still_manages_open_position_outside_window():
    # Enter INSIDE the window, then a later step OUTSIDE the window must
    # still manage the stop (the position exits even though entries are
    # gated off there).
    steps, closed, forming = _open_long_steps()
    entry_ts = steps[0]["ts"]
    h = _hour_of(entry_ts)
    # Window covers only the entry hour; the stop step is dated one hour
    # later (outside the window) yet must still stop the position out.
    in_window = (h, h + 1)
    stop_ts = entry_ts + 3600  # next hour -> outside window
    assert _hour_of(stop_ts) not in range(in_window[0], in_window[1])
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=stop_ts))
    trades = tk_bw_v2_run(
        steps, entry_mode="forced", regime_mode="full5", stop_mode="fixed",
        tp_mode="pattern", regime_lookback=3, c1_tol=3.0, allow_short=False,
        session_hours=in_window,
    )
    assert len(trades) == 3
    assert all(t["exit_reason"] == "SL_INIT" for t in trades)


# ==========================================================================
# 8) return_state (additive, default False): live-reconciler snapshot of the
#    still-open position at the end of `steps`, WITHOUT changing the trades
#    list. Byte-identical existing outputs are pinned by re-running the
#    parity tests above with return_state omitted (default) elsewhere; here
#    we pin (a) default-off returns a bare list, (b) return_state=True
#    returns (trades, snapshot) with an OPEN position, (c) flat -> {}.
# ==========================================================================
def test_return_state_default_off_returns_plain_list():
    steps = _parity_steps()
    out = tk_bw_v2_run(steps, entry_mode="forced", regime_mode="full5",
                       stop_mode="fixed", tp_mode="pattern",
                       regime_lookback=3, c1_tol=3.0, allow_short=False)
    assert isinstance(out, list)


def test_return_state_true_reports_open_position_snapshot():
    # A LONG that opens and is stopped INITIAL-SL immediately (still flat at
    # the end) vs one that stays open (BE/trail ratchet, no stop-out) --
    # use the ATR-stop peak fixture from test 5 but stop BEFORE the crash so
    # the position is still open when steps end.
    steps, closed, forming = _open_long_steps()
    atr = _atr_of(closed, 14)
    entry_bid = 98.50
    px_in = entry_bid + 0.60
    peak = px_in + 1.0 * atr + 30.0
    f_peak = dict(forming, open=forming["close"], high=peak + 0.05,
                  low=forming["close"] - 0.05, close=peak)
    steps.append(_entry_step(closed, f_peak, peak, ts=T0 + 41 * 300 + 60))
    trades, snap = tk_bw_v2_run(
        steps, entry_mode="forced", regime_mode="full5", stop_mode="atr",
        tp_mode="pattern", regime_lookback=3, c1_tol=3.0, allow_short=False,
        atr_sl_mult=1.5, atr_be_mult=1.0, atr_trail_mult=2.5,
        return_state=True,
    )
    assert trades == []  # nothing closed yet -- position still open
    assert set(snap) >= {"open", "last_bar_exits", "last_idx"}
    assert set(snap["open"]) == {"F1", "F2", "F3"}
    for tag in ("F1", "F2", "F3"):
        d = snap["open"][tag]
        assert d["side"] == "LONG"
        assert d["sl"] is not None
    assert snap["last_idx"] == len(steps) - 1


def test_return_state_true_flat_reports_empty_open():
    trades, snap = tk_bw_v2_run(
        [], entry_mode="forced", regime_mode="full5", stop_mode="fixed",
        tp_mode="pattern", return_state=True,
    )
    assert trades == []
    assert snap["open"] == {}


def test_return_state_does_not_change_trades_vs_default():
    # The trades component of the return_state=True tuple must be
    # byte-identical to the plain-list output for the same params.
    steps = _parity_steps()
    common = dict(entry_mode="forced", regime_mode="full5", stop_mode="fixed",
                 tp_mode="pattern", regime_lookback=3, c1_tol=3.0,
                 allow_short=False)
    plain = tk_bw_v2_run(steps, **common)
    trades, _snap = tk_bw_v2_run(steps, return_state=True, **common)
    assert trades == plain
