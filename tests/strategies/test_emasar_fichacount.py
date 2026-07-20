"""tests/strategies/test_emasar_fichacount.py -- W2-T5 (honest program):
pins the additive ficha-count lever (P46 escalera) on
`sentinel_engine.strategies.emasar_variant.simular_variant`.

  New kwarg `active_fichas: int = 3` (valid 1, 2 or 3; default 3 = OFF). When
  set to N, every entry site opens ONLY fichas F1..FN (N=1 -> only F1; N=2 ->
  F1+F2; N=3 -> the classic full F1/F2/F3 ladder). The existing exit/trail/BE/
  SL loops iterate over whatever fichas exist, so fewer fichas flow through
  naturally with no other behavior change (same signals, same per-ficha trail
  params for the fichas that do exist). This actually SIMULATES the reduced
  ladder rather than post-hoc dropping rows (shared trail/BE/SL state makes
  dropping non-equivalent). Honest under `live_fill_mode` (no new fill route).

Additive and OFF by default: the `active_fichas=3` default must be byte-
identical to pre-change behavior. Pinned here. Values outside {1,2,3} raise
ValueError.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from sentinel_engine.strategies.emasar_variant import simular_variant

# Params that actually produce entries across the fixture (tight-ish trails so
# fichas cycle and both long/short signals fire -- makes both byte-identity and
# the reduced-ladder behavior meaningful/non-vacuous).
FC_PARAMS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=300.0, f2_trail_pips=230.0, f3_trail_pips=170.0,
    init_sl_range_k=1.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)


def _synthetic_bars(n: int = 300, seed: int = 120) -> list[dict]:
    """Same deterministic generator shape as test_emasar_sar's fixture."""
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


def _ficha_tags(events: list[dict]) -> set[str]:
    """The set of per-ficha tags appearing on EXIT/reverse/time_stop events."""
    return {ev["ficha"] for ev in events
            if ev.get("ficha") is not None}


# ---------------------------------------------------------------------------
# (1) byte-identity: active_fichas=3 (default) is a byte-identical no-op vs.
#     NOT passing the kwarg at all.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed,n", [(120, 300), (7, 400)])
def test_active_fichas_default_is_byte_identical_noop(seed, n):
    bars = _synthetic_bars(n, seed=seed)
    baseline = simular_variant(bars, symbol="XAUUSD", **FC_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", active_fichas=3, **FC_PARAMS)
    assert with_default == baseline


# ---------------------------------------------------------------------------
# (2) behavior: active_fichas=1 opens only F1; =2 opens only F1,F2; and the
#     escalera actually changes results vs. the default (non-vacuous).
# ---------------------------------------------------------------------------

def test_active_fichas_one_opens_only_f1_and_differs():
    bars = _synthetic_bars(400, seed=7)
    baseline = simular_variant(bars, symbol="XAUUSD", **FC_PARAMS)
    events = simular_variant(bars, symbol="XAUUSD", active_fichas=1, **FC_PARAMS)

    entries = _entries(events)
    assert entries, "fixture must produce entries"

    tags = _ficha_tags(events)
    assert tags == {"F1"}, f"active_fichas=1 must only ever touch F1; got {tags}"

    # Non-vacuous: results differ from the full 3-ficha ladder.
    assert events != baseline, "active_fichas=1 should differ from default"


def test_active_fichas_two_opens_only_f1_f2_and_differs():
    bars = _synthetic_bars(400, seed=7)
    baseline = simular_variant(bars, symbol="XAUUSD", **FC_PARAMS)
    events = simular_variant(bars, symbol="XAUUSD", active_fichas=2, **FC_PARAMS)

    entries = _entries(events)
    assert entries, "fixture must produce entries"

    tags = _ficha_tags(events)
    assert tags <= {"F1", "F2"} and "F3" not in tags, (
        f"active_fichas=2 must never touch F3; got {tags}")
    assert "F1" in tags and "F2" in tags, (
        f"active_fichas=2 should exercise both F1 and F2; got {tags}")

    # Non-vacuous: results differ from the full 3-ficha ladder.
    assert events != baseline, "active_fichas=2 should differ from default"


def test_active_fichas_ordering_one_subset_of_two_subset_of_three():
    """1 -> 2 -> 3 is a strictly-growing ficha set (structural sanity)."""
    bars = _synthetic_bars(400, seed=7)
    t1 = _ficha_tags(simular_variant(bars, symbol="XAUUSD", active_fichas=1, **FC_PARAMS))
    t2 = _ficha_tags(simular_variant(bars, symbol="XAUUSD", active_fichas=2, **FC_PARAMS))
    t3 = _ficha_tags(simular_variant(bars, symbol="XAUUSD", active_fichas=3, **FC_PARAMS))
    assert t1 == {"F1"}
    assert t2 == {"F1", "F2"}
    assert t3 == {"F1", "F2", "F3"}


# ---------------------------------------------------------------------------
# (3) validation: active_fichas outside {1,2,3} raises ValueError.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [0, 4, -1, 5])
def test_active_fichas_out_of_range_raises(bad):
    bars = _synthetic_bars(50, seed=1)
    with pytest.raises(ValueError):
        simular_variant(bars, symbol="XAUUSD", active_fichas=bad, **FC_PARAMS)


# ---------------------------------------------------------------------------
# (4) honesty: under live_fill_mode=True the reduced ladder still prices at
#     honest close/level fills (no new route) and only F1 is opened at N=1.
# ---------------------------------------------------------------------------

def test_active_fichas_honest_under_live_fill():
    bars = _synthetic_bars(400, seed=7)
    events = simular_variant(
        bars, symbol="XAUUSD", active_fichas=1, live_fill_mode=True, **FC_PARAMS)
    assert _entries(events), "fixture must produce entries under live_fill"
    tags = _ficha_tags(events)
    assert tags == {"F1"}, f"active_fichas=1 must only touch F1 (live_fill); got {tags}"

    # Every emitted price is a real price on its bar (close, a bar extreme, or
    # a level between low/high) -- no invented route.
    for ev in events:
        i = ev["idx"]
        b = bars[i]
        lo = min(b["low"], b["close"], b["open"])
        hi = max(b["high"], b["close"], b["open"])
        assert lo - 1e-6 <= ev["precio"] <= hi + 1e-6, (
            f"price {ev['precio']!r} at idx {i} outside bar range [{lo},{hi}]")
