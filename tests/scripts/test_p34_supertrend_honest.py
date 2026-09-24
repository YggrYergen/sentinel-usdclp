"""tests/scripts/test_p34_supertrend_honest.py -- Wave 5, Task P34.

Tests for `scripts/report/gen_p34_supertrend_honest.py`, the honest port of the
standalone SuperTrend always-in p14x3-M15 engine. All tests run on SYNTHETIC
bar fixtures (no lake, no research.db). Covers the brief's required assertions:

(a) the always-in engine produces ALTERNATING LONG/SHORT positions across
    trend flips on an up-then-down synthetic fixture;
(b) flat-0.5 spread is actually SUBTRACTED at fill (net-with-spread < the
    zero-spread counterfactual on a known fixture);
(c) a monotone window with no trend flip yields the documented zero-flip,
    zero-emitted-trade behavior (the single position is left open, not emitted).
"""
from __future__ import annotations

from scripts.report import gen_p34_supertrend_honest as p34


# ---------------------------------------------------------------------------
# Synthetic bar helpers.
# ---------------------------------------------------------------------------
def _bar(t: int, o: float, h: float, l: float, c: float) -> dict:
    return {"t": t, "open": o, "high": h, "low": l, "close": c, "volume": 1.0}


def _ramp(start_price: float, step: float, n: int, t0: int = 0, dt: int = 900) -> list[dict]:
    """n bars marching by `step` per bar (up if step>0, down if step<0)."""
    bars: list[dict] = []
    price = start_price
    for k in range(n):
        o = price
        c = price + step
        h = max(o, c) + 0.5
        l = min(o, c) - 0.5
        bars.append(_bar(t0 + k * dt, o, h, l, c))
        price = c
    return bars


def _up_then_down(n_up: int = 40, n_down: int = 40, step: float = 5.0) -> list[dict]:
    """Strong rise then strong fall -> SuperTrend must flip at least once."""
    up = _ramp(4000.0, step, n_up, t0=0)
    last_c = up[-1]["close"]
    down = _ramp(last_c, -step, n_down, t0=n_up * 900)
    return up + down


# ---------------------------------------------------------------------------
# (a) Alternating LONG/SHORT across flips.
# ---------------------------------------------------------------------------
def test_alternating_sides_across_flips():
    bars = _up_then_down(n_up=50, n_down=50, step=6.0)
    trades, n_flips = p34.supertrend_always_in_trades(bars, p34.ATR_PERIOD, p34.MULT)

    assert n_flips >= 1, "up-then-down fixture must produce at least one flip"
    assert len(trades) >= 1
    # Consecutive emitted trades must alternate side (always-in: close then
    # reopen the OPPOSITE side at the same bar).
    sides = [t["side"] for t in trades]
    for a, b in zip(sides, sides[1:]):
        assert a != b, f"sides must alternate, got {sides}"
    # Each emitted trade exits by a flip.
    assert all(t["exit_reason"] == "EXIT_STFLIP" for t in trades)
    # An exit reconnects to the next entry at the same bar (always-in).
    for prev, nxt in zip(trades, trades[1:]):
        assert prev["ts_out_epoch"] == nxt["ts_in_epoch"]


# ---------------------------------------------------------------------------
# (b) flat-0.5 spread is actually subtracted at fill.
# ---------------------------------------------------------------------------
def test_spread_reduces_net_at_fill():
    bars = _up_then_down(n_up=60, n_down=60, step=5.0)
    trades, _ = p34.supertrend_always_in_trades(bars, p34.ATR_PERIOD, p34.MULT)
    assert trades, "need at least one trade for the spread comparison"

    # Net WITH the module's spread-at-fill (already baked into px_in/px_out).
    net_with = round(sum(p34._pnl(t["side"], t["px_in"], t["px_out"]) for t in trades), 2)

    # Zero-spread counterfactual: recompute fills with SPREAD forced to 0.
    orig = p34.SPREAD
    try:
        p34.SPREAD = 0.0
        trades0, _ = p34.supertrend_always_in_trades(bars, p34.ATR_PERIOD, p34.MULT)
        net_without = round(
            sum(p34._pnl(t["side"], t["px_in"], t["px_out"]) for t in trades0), 2)
    finally:
        p34.SPREAD = orig

    assert net_with < net_without, (
        f"flat-0.5 spread must cost money: with={net_with} vs without={net_without}")


def test_spread_helpers_direction():
    # Long buys at ask (bid + spread) on entry, sells at bid on exit.
    assert p34._entry_fill("L", 100.0) == 100.0 + p34.SPREAD
    assert p34._exit_fill("L", 100.0) == 100.0
    # Short sells at bid on entry, buys back at ask (bid + spread) on exit.
    assert p34._entry_fill("S", 100.0) == 100.0
    assert p34._exit_fill("S", 100.0) == 100.0 + p34.SPREAD


# ---------------------------------------------------------------------------
# (c) No-flip window -> zero flips, no emitted trade (position left open).
# ---------------------------------------------------------------------------
def test_no_flip_window_emits_no_trade():
    # Monotone rise only: trend never flips down, so no exit event fires.
    bars = _ramp(4000.0, 5.0, 120, t0=0)
    trades, n_flips = p34.supertrend_always_in_trades(bars, p34.ATR_PERIOD, p34.MULT)
    assert n_flips == 0, f"monotone rise should not flip, got {n_flips}"
    assert trades == [], "no flip => no exit => no emitted trade (position open)"


# ---------------------------------------------------------------------------
# in-window predicate tags trades correctly.
# ---------------------------------------------------------------------------
def test_in_window_tagging():
    bars = _up_then_down(n_up=50, n_down=50, step=6.0)
    # Window that excludes everything.
    trades_none, _ = p34.supertrend_always_in_trades(
        bars, p34.ATR_PERIOD, p34.MULT, in_window=lambda _e: False)
    assert trades_none, "engine still emits trades; only the tag changes"
    assert all(not t["entry_in_window"] for t in trades_none)

    # Window that includes everything.
    trades_all, _ = p34.supertrend_always_in_trades(
        bars, p34.ATR_PERIOD, p34.MULT, in_window=lambda _e: True)
    assert all(t["entry_in_window"] for t in trades_all)


# ---------------------------------------------------------------------------
# metrics: net only counts in-window trades.
# ---------------------------------------------------------------------------
def test_compute_window_metrics_filters_in_window():
    bars = _up_then_down(n_up=50, n_down=50, step=6.0)
    trades, _ = p34.supertrend_always_in_trades(
        bars, p34.ATR_PERIOD, p34.MULT, in_window=lambda _e: True)
    m_all = p34.compute_window_metrics(trades)
    # Force all out of window -> zero trades counted, zero net.
    for t in trades:
        t["entry_in_window"] = False
    m_none = p34.compute_window_metrics(trades)
    assert m_none["trades"] == 0
    assert m_none["net"] == 0.0
    assert m_all["trades"] >= 1
