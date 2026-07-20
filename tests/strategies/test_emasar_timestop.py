"""tests/strategies/test_emasar_timestop.py -- W2-T1 (honest program):
pins the additive time-stop lever on
`sentinel_engine.strategies.emasar_variant.simular_variant`.

  New kwarg `max_hold_bars: int | None = None` (default None = OFF). When set
  to N > 0, any ficha open for N bars (bar-count since its entry bar) is closed
  at that bar's CLOSE price, motivo "time_stop". Per ficha. Honest under
  `live_fill_mode` (priced at bar close via the existing honest path).

Additive and OFF by default: the `max_hold_bars=None` default must be
byte-identical to pre-change behavior. Pinned here.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from sentinel_engine.strategies.emasar_variant import simular_variant

V09_PARAMS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
    init_sl_range_k=1.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)

# Wide trails + wide initial stop so fichas HOLD for many bars (max hold ~82
# on seed=120), which is what makes a small max_hold_bars cap non-vacuous.
# (V09_PARAMS' tight 100-pip trails exit within 1-2 bars, so a 5-bar cap could
# never bite there.)
LONGHOLD_PARAMS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=2000.0, f2_trail_pips=2000.0, f3_trail_pips=2000.0,
    init_sl_range_k=5.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)


def _synthetic_bars(n: int = 300, seed: int = 120) -> list[dict]:
    """Same deterministic generator shape as test_emasar_livefill_state's fixture."""
    rnd = random.Random(seed)
    bars = []
    price = 4500.0
    base_epoch = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        open_ = price - drift
        close = price
        high = max(open_, close) + abs(rnd.uniform(0.3, 1.2))
        low = min(open_, close) - abs(rnd.uniform(0.3, 1.2))
        bars.append({"open": open_, "high": high, "low": low, "close": close,
                     "t": base_epoch + k * 60})
    return bars


def _entry_exit_pairs(events: list[dict]) -> list[tuple[str, int, int]]:
    """Reconstruct per-ficha (tag, entry_idx, exit_idx) pairs from an event
    stream. Entries (ENTRY_L/ENTRY_S) open F1/F2/F3 at the entry bar; each
    EXIT_* event names the ficha tag that closed and the bar it closed on."""
    pairs = []
    open_entry_idx: dict[str, int] = {}
    for ev in events:
        if ev["motivo"] in ("ENTRY_L", "ENTRY_S"):
            for tag in ("F1", "F2", "F3"):
                open_entry_idx[tag] = ev["idx"]
        elif ev["motivo"].startswith("EXIT") or ev["motivo"] == "time_stop":
            tag = ev["ficha"]
            if tag in open_entry_idx:
                pairs.append((tag, open_entry_idx.pop(tag), ev["idx"]))
    return pairs


# ---------------------------------------------------------------------------
# (1) byte-identity: max_hold_bars=None (default) is a byte-identical no-op
#     vs. NOT passing the kwarg at all.
# ---------------------------------------------------------------------------

def test_max_hold_bars_default_is_byte_identical_noop_synthetic():
    bars = _synthetic_bars(300, seed=120)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", max_hold_bars=None, **V09_PARAMS)
    assert with_default == baseline


def test_max_hold_bars_default_is_byte_identical_noop_seed7():
    bars = _synthetic_bars(400, seed=7)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", max_hold_bars=None, **V09_PARAMS)
    assert with_default == baseline


# ---------------------------------------------------------------------------
# (2) behavior: max_hold_bars=5 caps every ficha's (bar-count) hold at 5 AND
#     changes at least one trade vs. the no-op run (non-vacuous).
# ---------------------------------------------------------------------------

def test_max_hold_bars_caps_hold_and_changes_trades():
    bars = _synthetic_bars(400, seed=120)
    baseline = simular_variant(bars, symbol="XAUUSD", **LONGHOLD_PARAMS)
    capped = simular_variant(
        bars, symbol="XAUUSD", max_hold_bars=5, **LONGHOLD_PARAMS)

    # Non-vacuous: the cap must actually change the event stream.
    assert capped != baseline

    # No ficha's bar-count hold exceeds 5.
    for tag, entry_idx, exit_idx in _entry_exit_pairs(capped):
        assert exit_idx - entry_idx <= 5, (
            f"{tag}: held {exit_idx - entry_idx} bars (entry {entry_idx}, "
            f"exit {exit_idx}), exceeds max_hold_bars=5")

    # At least one exit is a time_stop (proves the lever fired).
    assert any(ev["motivo"] == "time_stop" for ev in capped), (
        "expected at least one time_stop exit at max_hold_bars=5")


# ---------------------------------------------------------------------------
# (3) honesty: time-stop exits are priced at the bar close under
#     live_fill_mode=True.
# ---------------------------------------------------------------------------

def test_time_stop_priced_at_close_under_live_fill():
    bars = _synthetic_bars(400, seed=120)
    events = simular_variant(
        bars, symbol="XAUUSD", max_hold_bars=5, live_fill_mode=True,
        **LONGHOLD_PARAMS)
    time_stops = [ev for ev in events if ev["motivo"] == "time_stop"]
    assert time_stops, "expected at least one time_stop exit under live_fill_mode"
    for ev in time_stops:
        assert ev["precio"] == bars[ev["idx"]]["close"], (
            f"time_stop exit must be priced at bar close: got {ev['precio']!r} "
            f"vs close {bars[ev['idx']]['close']!r} at idx {ev['idx']}")
