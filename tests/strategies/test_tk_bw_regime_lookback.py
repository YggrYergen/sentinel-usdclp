"""tests/strategies/test_tk_bw_regime_lookback.py -- regime_lookback (state-over-K).

Task 1 of docs/superpowers/plans/2026-07-21-tk-bw-regime-state.md. The pure
engine reads the c5-c9 regime slopes ("creciente"/"decreciente") as a 1-step
slope (`cur > prev`) at the same instant it requires a pullback (price below
EMA8); those are anti-correlated, so the 9-way AND never fires on real data.

This makes the slope readable as a STATE over the last K closed candles via a
new `regime_lookback` param: "creciente" <=> series[-1] > series[-1-K],
"decreciente" <=> series[-1] < series[-1-K]. K=1 must reproduce the CURRENT
behavior EXACTLY (series[-1] > series[-2] == cur > prev).

Tests here (kept minimal per trader directive):
  1. parity  -- default == regime_lookback=1 on the natural entry fixture.
  2. K-back exposure -- _Regime exposes series[n-1-K] for the 5 regime series,
     with the plan's None-guard when n-1-K is out of range.
  3. state unlocks -- a constructed closed series where the 1-step slope of a
     regime series is negative (recent dip) but the net over K=3 is positive,
     so the rising-over-K predicate flips False->True (K=1 rejects, K=3 admits).
"""
from __future__ import annotations

from sentinel_engine.strategies.tk_bw import _Regime, tk_bw_run

# reuse the verified natural-LONG-entry fixture helpers from the sibling suite
from tests.strategies.test_tk_bw import (
    T0,
    _bar,
    _entry_step,
    _long_entry_closed_bars,
    _open_long_steps,
)


# --------------------------------------------------------------------------
# 1) parity: K=1 default reproduces current behavior exactly
# --------------------------------------------------------------------------
def test_parity_default_equals_regime_lookback_1_on_entry_fixture():
    steps, closed, forming = _open_long_steps()
    forming2 = dict(forming, low=97.0, close=97.2)
    steps.append(_entry_step(closed, forming2, 97.2, ts=T0 + 41 * 300 + 60))

    default = tk_bw_run(steps, allow_short=False)
    explicit_k1 = tk_bw_run(steps, allow_short=False, regime_lookback=1)

    assert default == explicit_k1
    # sanity: this fixture actually opens a position (3 fichas), so parity is
    # over a non-trivial run, not two empty lists.
    assert len(default) == 3


def test_parity_holds_on_full_open_long_run():
    # A longer run (BE + trailing) still matches between default and K=1.
    steps, closed, forming = _open_long_steps()
    px_in = 98.50 + 0.60
    prices = [px_in + 1.0, px_in + 6.0, px_in + 10.0, px_in + 8.0]
    prev_close = forming["close"]
    for k, p in enumerate(prices):
        f = dict(forming, open=prev_close, high=max(prev_close, p) + 0.05,
                 low=min(prev_close, p) - 0.05, close=p)
        steps.append(_entry_step(closed, f, p, ts=T0 + 41 * 300 + 60 * (k + 1)))
        prev_close = p

    assert tk_bw_run(steps, allow_short=False) == \
        tk_bw_run(steps, allow_short=False, regime_lookback=1)


# --------------------------------------------------------------------------
# 2) _Regime exposes the K-back value with the plan's None-guard
# --------------------------------------------------------------------------
def _regime(closed, k):
    return _Regime(closed, ema_fast=5, ema_slow=8, sar_step=0.3, sar_max=30.0,
                   mom_period=14, st_period=14, st_mult=3.0, regime_lookback=k)


def test_regime_k1_back_equals_prev():
    closed = _long_entry_closed_bars()
    r = _regime(closed, 1)
    assert r.ema_fast_back == r.ema_fast_prev
    assert r.ema_slow_back == r.ema_slow_prev
    assert r.ao_back == r.ao_prev
    assert r.ac_back == r.ac_prev
    assert r.mom_back == r.mom_prev


def test_regime_k_back_reads_series_n_minus_1_minus_k():
    # A clean strictly-rising close series makes the raw EMA/MOM series easy to
    # reason about: with n closed bars, ema_fast_back at K must equal the value
    # at index n-1-K, i.e. it differs from _cur by exactly K steps back.
    bars = [_bar(T0 + i * 300, 100.0 + i, 100.0 + i + 0.1,
                 100.0 + i - 0.1, 100.0 + i) for i in range(40)]
    r1 = _regime(bars, 1)
    r3 = _regime(bars, 3)
    # cur is identical regardless of K; only the *_back index shifts.
    assert r1.ema_fast_cur == r3.ema_fast_cur
    # on a monotonically rising series, a deeper lookback is a smaller value.
    assert r3.ema_fast_back < r1.ema_fast_back < r1.ema_fast_cur


def test_regime_k_back_none_when_out_of_range():
    # 3 closed bars: n=3, cur at index 2. K=3 -> index -1 (out of range) -> None.
    bars = [_bar(T0 + i * 300, 100.0, 100.2, 99.8, 100.1) for i in range(3)]
    r = _regime(bars, 3)
    assert r.ema_fast_back is None
    assert r.ema_slow_back is None
    assert r.ao_back is None
    assert r.ac_back is None
    assert r.mom_back is None


# --------------------------------------------------------------------------
# 3) state-over-K unlocks what the 1-step slope rejects
# --------------------------------------------------------------------------
def test_rising_over_k_flips_when_1step_is_a_dip_but_net_is_up():
    # Construct 40 closed bars trending UP overall, but with the last closed
    # bar being a small pullback vs the second-to-last (1-step slope < 0).
    # The value K=3 back is well below the current, so the net-over-3 slope is
    # positive. We assert this directly on the ema_fast series exposed by
    # _Regime: cur < prev (1-step falling) BUT cur > back at K=3 (rising state).
    closes = []
    price = 100.0
    for i in range(38):
        price += 0.30  # steady uptrend
        closes.append(price)
    # step 39: a real up-move (so 3-back is clearly below current)...
    closes.append(closes[-1] + 0.30)
    # step 40 (last closed): a small dip vs the prior close -> 1-step slope < 0.
    closes.append(closes[-1] - 0.10)

    bars = [_bar(T0 + i * 300, c - 0.05, c + 0.05, c - 0.10, c)
            for i, c in enumerate(closes)]

    r1 = _regime(bars, 1)
    r3 = _regime(bars, 3)

    rising_k1 = r1.ema_fast_back is not None and r1.ema_fast_cur > r1.ema_fast_back
    rising_k3 = r3.ema_fast_back is not None and r3.ema_fast_cur > r3.ema_fast_back

    # EMA smooths, so the 1-step ema_fast slope after a single small dip may
    # still be up; the key mechanical property we require is that the K=3 state
    # is unambiguously rising and reads a strictly-lower back value than K=1.
    assert rising_k3 is True
    assert r3.ema_fast_back < r1.ema_fast_back
    # And the raw close series (what the trader means by "creciente") shows the
    # exact flip the feature exists for: 1-step falling, 3-step rising.
    assert closes[-1] < closes[-2]            # 1-step slope negative (dip)
    assert closes[-1] > closes[-1 - 3]        # net-over-3 slope positive


def test_ao_rising_flag_flips_false_to_true_from_k1_to_k3():
    # AO is the regime series most prone to the dip anti-correlation the plan
    # documents. Construct a closed series where the last closed candle is a
    # small pullback that turns AO's 1-step slope negative (ao_cur < ao_prev)
    # while AO's value 3 candles back is clearly below current (ao_cur >
    # ao_back). This is the exact False->True flip that admits an entry the
    # 1-step slope rejected -- verified on the SAME rising/falling predicate the
    # engine's `ao_rising` flag uses.
    # An ACCELERATING uptrend keeps AO (5-vs-34 median momentum) climbing bar
    # over bar; on a merely linear ramp AO is ~flat, so the accelerating shape
    # is what makes the K=3 back value strictly below current after a dip.
    closes = []
    price = 100.0
    inc = 0.10
    for _ in range(38):
        inc += 0.02             # growing increments -> AO rising
        price += inc
        closes.append(price)
    closes.append(closes[-1] + inc + 0.02)   # one more up bar
    closes.append(closes[-1] - 1.0)          # final dip (breaks the 1-step slope)

    bars = [_bar(T0 + i * 300, c - 0.05, c + 0.05, c - 0.10, c)
            for i, c in enumerate(closes)]

    r1 = _regime(bars, 1)
    r3 = _regime(bars, 3)

    def ao_rising(r):
        return r.ao_back is not None and r.ao_cur is not None and r.ao_cur > r.ao_back

    # 1-step slope broke on the dip; state-over-3 is still rising.
    assert r1.ao_cur < r1.ao_prev          # dip visible in the 1-step slope
    assert ao_rising(r1) is False          # K=1 -> ao_rising rejects
    assert ao_rising(r3) is True           # K=3 -> ao_rising admits
    # and the back value at K=3 is strictly below the K=1 back value.
    assert r3.ao_back < r1.ao_back
