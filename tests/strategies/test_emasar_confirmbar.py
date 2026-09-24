"""tests/strategies/test_emasar_confirmbar.py -- W2-T3 (honest program):
pins the additive confirmation-bar entry lever (P54) on
`sentinel_engine.strategies.emasar_variant.simular_variant`.

  New kwarg `confirm_bar: bool = False` (default False = OFF). When True, a
  signal raised at bar `i` does NOT enter at `i`; it is held pending for ONE
  bar and enters at bar `i+1` ONLY if `i+1` confirms the direction beyond the
  signal bar's extreme -- LONG iff `close[i+1] > high[i]`, SHORT iff
  `close[i+1] < low[i]`. If not confirmed at `i+1`, the pending signal is
  dropped (no entry; no carry beyond i+1). The deferred entry is priced at the
  confirmation bar via the EXISTING entry fill path (honest under
  `live_fill_mode`, no new fill route).

Additive and OFF by default: the `confirm_bar=False` default must be
byte-identical to pre-change behavior. Pinned here.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from sentinel_engine.strategies.emasar_variant import simular_variant

# Params that actually produce entries (tight trails so fichas cycle fast and
# many signals fire across the fixture -- makes both byte-identity and the
# confirm-bar behavior meaningful/non-vacuous).
V09_PARAMS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
    init_sl_range_k=1.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)


def _synthetic_bars(n: int = 300, seed: int = 120) -> list[dict]:
    """Same deterministic generator shape as test_emasar_timestop's fixture."""
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


def _entries(events: list[dict]) -> list[dict]:
    return [ev for ev in events if ev["motivo"] in ("ENTRY_L", "ENTRY_S")]


# ---------------------------------------------------------------------------
# (1) byte-identity: confirm_bar=False (default) is a byte-identical no-op
#     vs. NOT passing the kwarg at all.
# ---------------------------------------------------------------------------

def test_confirm_bar_default_is_byte_identical_noop_synthetic():
    bars = _synthetic_bars(300, seed=120)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", confirm_bar=False, **V09_PARAMS)
    assert with_default == baseline


def test_confirm_bar_default_is_byte_identical_noop_seed7():
    bars = _synthetic_bars(400, seed=7)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", confirm_bar=False, **V09_PARAMS)
    assert with_default == baseline


# ---------------------------------------------------------------------------
# (2) behavior: confirm_bar=True defers every entry >=1 bar past its signal,
#     filters at least one signal (differs from the no-op run), and still
#     leaves at least one entry (non-vacuous).
# ---------------------------------------------------------------------------

def test_confirm_bar_true_defers_and_filters_and_is_non_vacuous():
    bars = _synthetic_bars(400, seed=120)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    confirmed = simular_variant(
        bars, symbol="XAUUSD", confirm_bar=True, **V09_PARAMS)

    base_entries = _entries(baseline)
    conf_entries = _entries(confirmed)

    # (a) NO entry occurs on the same bar as its signal. A baseline entry
    #     at bar j is the signal bar; under confirm_bar every entry must be
    #     at a bar that is NOT one of those signal bars (it is deferred to
    #     the following confirmation bar). Concretely: every confirm-bar
    #     entry must confirm beyond the PRIOR bar's extreme, i.e. it is at
    #     least one bar after a signal -- assert the confirmation predicate
    #     holds against bar i-1 for each entry.
    for ev in conf_entries:
        i = ev["idx"]
        assert i >= 1, "a confirm-bar entry cannot be on bar 0 (no prior signal bar)"
        if ev["motivo"] == "ENTRY_L":
            assert bars[i]["close"] > bars[i - 1]["high"], (
                f"long confirm entry at idx {i} must have close > prior high")
        else:
            assert bars[i]["close"] < bars[i - 1]["low"], (
                f"short confirm entry at idx {i} must have close < prior low")

    # (b) at least one signal is filtered: the entry set differs.
    assert conf_entries != base_entries, (
        "confirm_bar=True should differ from the no-op run (filtered signals)")
    assert len(conf_entries) < len(base_entries), (
        "confirm_bar=True should filter out at least one unconfirmed signal")

    # (c) non-vacuous: at least one entry still fires (some signals confirm).
    assert conf_entries, "expected at least one confirmed entry"


# ---------------------------------------------------------------------------
# (3) honesty: the deferred entry is priced at the CONFIRMATION bar's fill
#     (bar close for the default entry_timing=0 path) under live_fill_mode.
# ---------------------------------------------------------------------------

def test_confirm_bar_entry_priced_at_confirmation_bar_under_live_fill():
    bars = _synthetic_bars(400, seed=120)
    events = simular_variant(
        bars, symbol="XAUUSD", confirm_bar=True, live_fill_mode=True,
        **V09_PARAMS)
    entries = _entries(events)
    assert entries, "expected at least one confirmed entry under live_fill_mode"
    for ev in entries:
        i = ev["idx"]
        # Deferred entry uses the EXISTING close-entry fill path (entry_timing
        # default 0): the fill price is the confirmation bar's own close, NOT
        # the signal bar's price.
        assert ev["precio"] == bars[i]["close"], (
            f"confirm-bar entry must be priced at the confirmation bar close: "
            f"got {ev['precio']!r} vs close {bars[i]['close']!r} at idx {i}")
