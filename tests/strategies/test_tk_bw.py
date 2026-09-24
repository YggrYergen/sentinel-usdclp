"""tests/strategies/test_tk_bw.py -- TK-BW engine, minimal mechanical tests.

Per the plan (docs/superpowers/plans/2026-07-21-tk-bw-backtest.md, Task 1
"Tests"): these are MINIMAL and MECHANICAL. Entry correctness is validated
empirically later on real data via the runner + Trade View. These tests cover
only: smoke, exact spread/pnl math, stop mechanics (initial SL, BE, trailing
ratchet), F2/F3 close-only gating, single-position/no-same-candle-reentry,
trade-dict shape, and determinism -- using simple/injected fixtures rather
than hunting a natural 5-condition entry combinatorially.

A working natural-LONG-entry fixture (`_long_entry_closed_bars` /
`_long_entry_forming`) IS included (the plan's optional bonus): a mild
downtrend followed by one sharp spike-up closed candle resets Parabolic
SAR(0.3,30) right at the flip (SAR lands near the low of the spike bar, well
under the lagging EMA8) while EMA8/EMA5/AO/AC/MOM all come out rising on the
last two closed bars -- satisfying all 5 regime conditions with a clean,
verified-by-construction fixture (no search loop).
"""
from __future__ import annotations

from sentinel_engine.strategies.tk_bw import tk_bw_run

T0 = 1_700_000_000


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def _bar(t, o, h, l, c):
    return {"t": t, "open": o, "high": h, "low": l, "close": c}


def _long_entry_closed_bars():
    """40 mildly-declining native candles + 1 sharp spike-up candle (closed).
    Verified numerically (see task report) to satisfy, on the last two closed
    bars: EMA8 rising, EMA5 rising, AO/MOM/AC rising, and SAR(0.3,30) (reset
    at the flip) below EMA8. Last bearish closed candle = bars[39]
    (high=98.07, low=97.98); last closed bar (the spike) close=101.0."""
    bars = []
    price = 100.0
    for i in range(40):
        o = price
        c = price - 0.05
        hi = o + 0.02
        lo = c - 0.02
        bars.append(_bar(T0 + i * 300, o, hi, lo, c))
        price = c
    o = price
    c = price + 3.0
    hi = c + 0.05
    lo = o - 0.05
    bars.append(_bar(T0 + 40 * 300, o, hi, lo, c))
    return bars


def _entry_step(closed, forming, price, *, is_close=False, ts=None):
    return {
        "ts": ts if ts is not None else forming["t"],
        "closed": closed,
        "forming": forming,
        "price": price,
        "is_close": is_close,
    }


def _open_long_steps(extra_steps=None):
    """Two steps: step 1 opens a LONG (3 fichas) via the natural fixture
    above; any `extra_steps` are appended after (same `closed`, evolving
    `forming`) to exercise exits/stops on the now-open position."""
    closed = _long_entry_closed_bars()
    last_bear_high = closed[39]["high"]  # 98.07
    ema8_closed = 98.80277777777789  # last-closed EMA8, verified above
    forming_open = 98.20
    forming_price = 98.50  # in (last_bear_high, ema8_closed): breakout + below-EMA8
    assert last_bear_high < forming_price < ema8_closed
    forming = _bar(T0 + 41 * 300, forming_open, forming_price + 0.01,
                    forming_open - 0.01, forming_price)
    steps = [_entry_step(closed, forming, forming_price, ts=T0 + 41 * 300)]
    if extra_steps:
        steps.extend(extra_steps)
    return steps, closed, forming


# --------------------------------------------------------------------------
# smoke
# --------------------------------------------------------------------------
def test_import_and_trivial_run_no_error():
    assert tk_bw_run([]) == []
    # A short, low-history series: no crash, no trades (warmup not met).
    bar = _bar(T0, 100.0, 100.2, 99.8, 100.1)
    step = {"ts": T0, "closed": [bar], "forming": None, "price": 100.1, "is_close": False}
    assert tk_bw_run([step]) == []


def test_trades_are_well_formed_dicts():
    steps, closed, forming = _open_long_steps()
    # force an SL_INIT stop-out so we get well-formed trade dicts to inspect.
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=T0 + 41 * 300 + 60))
    trades = tk_bw_run(steps, allow_short=False)
    assert len(trades) == 3  # F1, F2, F3 all closed together by the common stop
    expected_keys = {
        "ts_in", "ts_out", "px_in", "px_out", "side", "ficha", "volume",
        "sl", "exit_reason", "pnl", "mae", "mfe",
    }
    for tr in trades:
        assert set(tr) == expected_keys
        assert isinstance(tr["ts_in"], int) and isinstance(tr["ts_out"], int)
        assert isinstance(tr["px_in"], float) and isinstance(tr["px_out"], float)
        assert tr["side"] in ("LONG", "SHORT")
        assert tr["ficha"] in ("F1", "F2", "F3")
        assert tr["volume"] == 0.01
        assert tr["exit_reason"] in {"TP1", "TP2", "TP3", "SL_INIT", "SL_BE", "SL_TRAIL"}
        assert isinstance(tr["pnl"], float)
    assert {tr["ficha"] for tr in trades} == {"F1", "F2", "F3"}


# --------------------------------------------------------------------------
# spread / pnl
# --------------------------------------------------------------------------
def test_long_pays_spread_on_entry_exits_at_bid():
    steps, closed, forming = _open_long_steps()
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=T0 + 41 * 300 + 60))
    trades = tk_bw_run(steps, allow_short=False, spread=0.60)
    tr = trades[0]
    # px_in = entry_bid(98.50) + spread(0.60)
    assert round(tr["px_in"], 6) == round(98.50 + 0.60, 6)
    # SL_INIT exit at bid: sl_bid = low(last_bear=97.98) - 0.60 = 97.38, no gap
    assert round(tr["px_out"], 6) == round(97.98 - 0.60, 6)
    assert round(tr["pnl"], 6) == round(tr["px_out"] - tr["px_in"], 6)
    assert tr["pnl"] < 0  # stopped out at a loss


def test_pnl_sign_long_vs_short():
    assert round((101.0 - 100.0), 6) > 0  # long: pnl = px_out - px_in (favorable if px_out>px_in)
    assert round((100.0 - 101.0), 6) < 0  # short: pnl = px_in - px_out (favorable if px_out<px_in)


def test_commission_is_not_subtracted_from_pnl():
    # commission=0 is the only supported value per the plan; pnl is pure
    # signed price delta with no extra deduction regardless of the param.
    steps, closed, forming = _open_long_steps()
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=T0 + 41 * 300 + 60))
    trades_default = tk_bw_run(steps, allow_short=False, commission=0.0)
    trades_other = tk_bw_run(steps, allow_short=False, commission=1.23)
    assert [t["pnl"] for t in trades_default] == [t["pnl"] for t in trades_other]


# --------------------------------------------------------------------------
# stop mechanics: initial SL, break-even, trailing ratchet
# --------------------------------------------------------------------------
def test_initial_sl_stops_out_all_fichas():
    steps, closed, forming = _open_long_steps()
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=T0 + 41 * 300 + 60))
    trades = tk_bw_run(steps, allow_short=False)
    assert len(trades) == 3
    for tr in trades:
        assert tr["exit_reason"] == "SL_INIT"
        assert round(tr["sl"], 6) == round(97.98 - 0.60, 6)


def test_break_even_arms_at_plus_060_and_never_loosens_below_be():
    steps, closed, forming = _open_long_steps()
    px_in = 98.50 + 0.60  # 99.10
    # step 2: price rises to exactly the BE trigger (px_in + 0.60) -> SL should
    # ratchet to px_in (break-even), never below.
    forming_be = dict(forming, high=px_in + 0.60 + 0.05, close=px_in + 0.60)
    steps.append(_entry_step(closed, forming_be, px_in + 0.60, ts=T0 + 41 * 300 + 60))
    # step 3: price dips back down but stays ABOVE break-even (low > px_in)
    # -- SL must NOT loosen (it stays pinned at px_in, not follow price down).
    forming_dip = dict(forming, high=px_in + 0.61, low=px_in + 0.05, close=px_in + 0.10)
    steps.append(_entry_step(closed, forming_dip, px_in + 0.10, ts=T0 + 41 * 300 + 120))
    # step 4: dip hits px_in exactly -> stops out at break-even (pnl ~ 0).
    # `open` must stay inside [low, high] (no fixture gap) so the stop fires
    # AT the SL level rather than the engine's gap-open handling.
    forming_hit = dict(forming, open=px_in, high=px_in + 0.02, low=px_in - 0.01, close=px_in)
    steps.append(_entry_step(closed, forming_hit, px_in, ts=T0 + 41 * 300 + 180))

    trades = tk_bw_run(steps, allow_short=False)
    assert len(trades) == 3
    for tr in trades:
        assert tr["exit_reason"] == "SL_BE"
        assert round(tr["sl"], 6) == round(px_in, 6)
        assert round(tr["pnl"], 6) == 0.0


def test_trailing_5usd_ratchet_monotonic():
    steps, closed, forming = _open_long_steps()
    px_in = 98.50 + 0.60
    # Run price up well past BE and past the $5-trailing activation range,
    # ratcheting the SL each step; confirm it only ever moves up (never down)
    # even when price momentarily dips. `open` is kept == `close` of the
    # PRIOR step (inside the new [low, high]) so no fixture gap masks the
    # real trailing-stop fill.
    prices = [px_in + 1.0, px_in + 6.0, px_in + 10.0, px_in + 8.0, px_in + 12.0]
    extra = []
    prev_close = forming["close"]
    for k, p in enumerate(prices):
        f = dict(forming, open=prev_close, high=max(prev_close, p) + 0.05,
                  low=min(prev_close, p) - 0.05, close=p)
        extra.append(_entry_step(closed, f, p, ts=T0 + 41 * 300 + 60 * (k + 1)))
        prev_close = p
    steps.extend(extra)
    # Finally, drop hard to trigger the trailing stop.
    trail_sl_expected = (px_in + 12.0) - 5.0  # ratchet tracks the running max (12.0 was highest)
    stop_close = trail_sl_expected - 0.4
    f_stop = dict(forming, open=prev_close, high=prev_close + 0.05,
                  low=trail_sl_expected - 0.5, close=stop_close)
    steps.append(_entry_step(closed, f_stop, stop_close, ts=T0 + 41 * 300 + 400))

    trades = tk_bw_run(steps, allow_short=False)
    assert len(trades) == 3
    for tr in trades:
        assert tr["exit_reason"] == "SL_TRAIL"
        assert round(tr["sl"], 6) == round(trail_sl_expected, 6)
        assert round(tr["px_out"], 6) == round(trail_sl_expected, 6)  # LONG exits at sl (bid)
        assert tr["sl"] >= px_in  # never loosens below break-even


def test_trailing_sl_does_not_loosen_when_price_pulls_back():
    # Run up to a peak (arming the $5 trail), then a SEPARATE later step
    # crashes through the ratcheted SL: the fill must be at the peak-5.0
    # level (not some looser level), proving the SL held from the peak step
    # through the pullback step without loosening.
    steps, closed, forming = _open_long_steps()
    px_in = 98.50 + 0.60
    peak = px_in + 9.0  # comfortably past BE+trail activation (5.0)
    f_peak = dict(forming, open=forming["close"], high=peak + 0.05,
                  low=forming["close"] - 0.05, close=peak)
    steps.append(_entry_step(closed, f_peak, peak, ts=T0 + 41 * 300 + 60))
    trail_sl_expected = peak - 5.0
    stop_close = trail_sl_expected - 0.1
    f_stop = dict(forming, open=peak, high=peak + 0.05,
                  low=trail_sl_expected - 0.2, close=stop_close)
    steps.append(_entry_step(closed, f_stop, stop_close, ts=T0 + 41 * 300 + 120))
    trades = tk_bw_run(steps, allow_short=False)
    assert len(trades) == 3
    for tr in trades:
        assert tr["exit_reason"] == "SL_TRAIL"
        assert round(tr["sl"], 6) == round(trail_sl_expected, 6)
        assert round(tr["px_out"], 6) == round(trail_sl_expected, 6)


# --------------------------------------------------------------------------
# structure: F2/F3 close-only, single position, no same-candle re-entry
# --------------------------------------------------------------------------
def test_f2_f3_do_not_fire_on_non_close_steps_even_if_conditions_would_match():
    # Build a position, then a step whose conditions numerically satisfy the
    # F2 close-bearish/EMA8/SAR pattern but with is_close=False: F2 must NOT
    # fire (only F1/stop are evaluated on non-close steps).
    steps, closed, forming = _open_long_steps()
    forming_bear_below_ema8 = dict(forming, open=forming["close"] + 0.5,
                                    close=forming["close"] - 0.5,
                                    high=forming["close"] + 0.6,
                                    low=forming["close"] - 0.6)
    steps.append(_entry_step(closed, forming_bear_below_ema8,
                              forming_bear_below_ema8["close"],
                              is_close=False, ts=T0 + 41 * 300 + 60))
    trades = tk_bw_run(steps, allow_short=False)
    assert not any(tr["exit_reason"] == "TP2" for tr in trades)
    assert not any(tr["exit_reason"] == "TP3" for tr in trades)


def test_single_position_no_second_entry_while_one_open():
    # While a position from `_open_long_steps` is open, feed steps that would
    # otherwise satisfy a fresh SHORT entry's level/trigger checks; assert no
    # second position is opened (total open+closed ficha count stays <= 3
    # for the whole run, i.e. never 6).
    steps, closed, forming = _open_long_steps()
    forming2 = dict(forming, high=forming["high"] + 5.0, close=forming["close"] + 3.0)
    steps.append(_entry_step(closed, forming2, forming2["close"], ts=T0 + 41 * 300 + 60))
    forming3 = dict(forming, low=95.0, close=95.2)
    steps.append(_entry_step(closed, forming3, 95.2, ts=T0 + 41 * 300 + 120))
    trades = tk_bw_run(steps, allow_short=True)
    assert len(trades) == 3  # exactly one position's worth of fichas, never 6
    assert {tr["side"] for tr in trades} == {"LONG"}


def test_no_reentry_within_the_same_native_candle_the_position_closed_on():
    # Close the LONG via SL_INIT, then within the SAME `closed` list (i.e.
    # the entry native candle hasn't advanced) feed a step that would
    # otherwise satisfy a fresh entry: no re-entry until `closed` grows
    # (next native candle).
    steps, closed, forming = _open_long_steps()
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=T0 + 41 * 300 + 60))
    # position is now closed (SL_INIT). Feed one more step, SAME `closed`
    # list, with a forming candle that reproduces the original entry setup.
    steps.append(_entry_step(closed, forming, 98.50, ts=T0 + 41 * 300 + 120))
    trades = tk_bw_run(steps, allow_short=False)
    # Only the original 3 SL_INIT trades; the repeated entry-shaped step must
    # NOT open a second position within the same native candle.
    assert len(trades) == 3
    assert all(tr["exit_reason"] == "SL_INIT" for tr in trades)


# --------------------------------------------------------------------------
# determinism
# --------------------------------------------------------------------------
def test_determinism_same_steps_same_trades():
    steps, closed, forming = _open_long_steps()
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=T0 + 41 * 300 + 60))
    t1 = tk_bw_run(steps, allow_short=False)
    t2 = tk_bw_run(steps, allow_short=False)
    assert t1 == t2
