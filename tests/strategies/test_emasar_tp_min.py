"""tests/strategies/test_emasar_tp_min.py -- W6 Family-A (honest program):
pins the additive fixed-pip take-profit lever on
`sentinel_engine.strategies.emasar_variant.simular_variant`.

  New kwarg `tp_min_pips: float | None = None` (default None = OFF; <=0 also
  OFF). When set to a positive value, at each ficha's fill a FIXED take-profit
  target is armed at `entry + tp_min_pips*pip` (long) / `entry - tp_min_pips*pip`
  (short), for ALL fichas F1/F2/F3 (distinct from the R-multiple f1_tp_r/f2_tp_r
  which are F1/F2 only). Armed at entry, fixed once armed (does not move).
  Ordinary trailing continues on top; whichever level a bar touches first exits
  the ficha, tagged EXIT_TP.

  CONSERVATIVE same-bar fill: if a single bar would touch BOTH the fixed TP and
  the initial/trailing SL, the SL takes precedence (exit at SL, not TP) --
  mirrors the existing V-05 f1_tp_r/f2_tp_r same-bar convention exactly.

Additive and OFF by default: the `tp_min_pips=None` (and <=0) default must be
byte-identical to pre-change behavior. Pinned here.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from sentinel_engine.strategies.emasar_ref import pip_size
from sentinel_engine.strategies.emasar_variant import simular_variant

# Same champion-baseline params + fixture shape used by the sibling lever tests.
V09_PARAMS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
    init_sl_range_k=1.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)

# Wide trails + wide initial stop so fichas HOLD for many bars -- this is what
# lets a small tp_min_pips target bite (with tight trails the trail exits first
# and the fixed TP could never fire).
LONGHOLD_PARAMS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=2000.0, f2_trail_pips=2000.0, f3_trail_pips=2000.0,
    init_sl_range_k=5.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)

PIP = pip_size("XAUUSD", 0.0)


def _synthetic_bars(n: int = 300, seed: int = 120) -> list[dict]:
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


def _first_baseline_signal(bars: list[dict], params: dict):
    """(idx, lado, entry_price) of the first entry in a baseline run."""
    base = simular_variant(bars, symbol="XAUUSD", **params)
    ents = _entries(base)
    assert ents, "fixture must produce at least one baseline entry"
    e = ents[0]
    return e["idx"], (+1 if e["motivo"] == "ENTRY_L" else -1), e["precio"]


def _find_first_signal(want_lado: int, params: dict,
                       seeds=(120, 7, 1, 2, 3, 4, 5, 42, 99, 13, 77)):
    """Return (bars, idx, entry_price) for the first fixture whose first
    baseline signal is on side `want_lado` and has a following bar i+1."""
    for seed in seeds:
        b = _synthetic_bars(400, seed=seed)
        ii, lado, px = _first_baseline_signal(b, params)
        if lado == want_lado and ii + 1 < len(b):
            return b, ii, px
    pytest.skip(f"no lado={want_lado} first-signal fixture among tried seeds")


# ---------------------------------------------------------------------------
# (1) byte-identity: tp_min_pips=None (default) AND tp_min_pips<=0 are
#     byte-identical no-ops vs. NOT passing the kwarg at all.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed,n", [(120, 300), (7, 400)])
def test_tp_min_default_none_is_byte_identical_noop(seed, n):
    bars = _synthetic_bars(n, seed=seed)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", tp_min_pips=None, **V09_PARAMS)
    assert with_default == baseline


@pytest.mark.parametrize("val", [0.0, -5.0])
def test_tp_min_nonpositive_is_byte_identical_noop(val):
    bars = _synthetic_bars(300, seed=120)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    disabled = simular_variant(
        bars, symbol="XAUUSD", tp_min_pips=val, **V09_PARAMS)
    assert disabled == baseline


# ---------------------------------------------------------------------------
# (2) behavior: a fixed tp_min_pips target is reached before any trail/SL ->
#     the ficha exits at EXACTLY entry +/- tp_min_pips*pip, tagged EXIT_TP,
#     for ALL fichas F1/F2/F3. Non-vacuous vs the no-op run.
# ---------------------------------------------------------------------------

def test_tp_min_exits_all_fichas_at_fixed_level_long():
    # A LONG entry, then the very next bar spikes up through a small fixed TP
    # but not far enough for anything else -- and never dips to the (wide) SL.
    bars, i, entry_px = _find_first_signal(+1, LONGHOLD_PARAMS)

    tp_pips = 20.0
    tp_level = entry_px + tp_pips * PIP
    b1 = dict(bars[i + 1])
    # Reach the TP on bar i+1 (high >= tp_level) without hitting the wide SL.
    b1["high"] = max(b1["high"], tp_level + 1.0)
    b1["low"] = max(b1["low"], entry_px - 1.0)  # nowhere near the wide SL
    forced = bars[: i + 1] + [b1] + bars[i + 2:]

    baseline = simular_variant(forced, symbol="XAUUSD", **LONGHOLD_PARAMS)
    events = simular_variant(
        forced, symbol="XAUUSD", tp_min_pips=tp_pips, **LONGHOLD_PARAMS)

    # Non-vacuous.
    assert events != baseline

    tp_exits = [ev for ev in events if ev["motivo"] == "EXIT_TP" and ev["idx"] == i + 1]
    tags = {ev["ficha"] for ev in tp_exits}
    assert tags == {"F1", "F2", "F3"}, (
        f"all three fichas should TP at the fixed level, got {tags}")
    for ev in tp_exits:
        assert ev["precio"] == pytest.approx(tp_level), (
            f"{ev['ficha']} TP price {ev['precio']!r} != {tp_level!r}")


# ---------------------------------------------------------------------------
# (3) same-bar TP+SL collision -> SL takes precedence (exit at SL, not TP).
# ---------------------------------------------------------------------------

def test_tp_min_sl_precedence_on_same_bar_touch():
    bars, i, entry_px = _find_first_signal(+1, LONGHOLD_PARAMS)

    # Recover the initial SL the engine sets (long: low[i] - k*range[i]).
    rng = bars[i]["high"] - bars[i]["low"]
    sl_level = bars[i]["low"] - LONGHOLD_PARAMS["init_sl_range_k"] * rng

    tp_pips = 20.0
    tp_level = entry_px + tp_pips * PIP
    # Bar i+1 touches BOTH the TP (high >= tp_level) and the initial SL
    # (low <= sl_level) in the same bar -> SL must win.
    b1 = dict(bars[i + 1])
    b1["high"] = max(b1["high"], tp_level + 1.0)
    b1["low"] = min(b1["low"], sl_level - 1.0)
    forced = bars[: i + 1] + [b1] + bars[i + 2:]

    events = simular_variant(
        forced, symbol="XAUUSD", tp_min_pips=tp_pips, **LONGHOLD_PARAMS)
    exits_i1 = [ev for ev in events if ev["idx"] == i + 1 and ev["ficha"] is not None]
    assert exits_i1, "expected exits on the collision bar"
    for ev in exits_i1:
        assert ev["motivo"] != "EXIT_TP", (
            f"{ev['ficha']} exited via TP on a same-bar SL collision (SL must win)")
        assert ev["motivo"] == "EXIT_INITSL", (
            f"{ev['ficha']} expected EXIT_INITSL on collision, got {ev['motivo']}")
        assert ev["precio"] == pytest.approx(sl_level)


# ---------------------------------------------------------------------------
# (4) short-side symmetry.
# ---------------------------------------------------------------------------

def test_tp_min_exits_all_fichas_at_fixed_level_short():
    # Find a fixture/seed whose first long-hold signal is a SHORT.
    bars, i, entry_px = _find_first_signal(-1, LONGHOLD_PARAMS)

    tp_pips = 20.0
    tp_level = entry_px - tp_pips * PIP
    b1 = dict(bars[i + 1])
    b1["low"] = min(b1["low"], tp_level - 1.0)   # reach the short TP
    b1["high"] = min(b1["high"], entry_px + 1.0)  # nowhere near the wide SL
    forced = bars[: i + 1] + [b1] + bars[i + 2:]

    baseline = simular_variant(forced, symbol="XAUUSD", **LONGHOLD_PARAMS)
    events = simular_variant(
        forced, symbol="XAUUSD", tp_min_pips=tp_pips, **LONGHOLD_PARAMS)
    assert events != baseline

    tp_exits = [ev for ev in events if ev["motivo"] == "EXIT_TP" and ev["idx"] == i + 1]
    tags = {ev["ficha"] for ev in tp_exits}
    assert tags == {"F1", "F2", "F3"}, (
        f"all three fichas should TP at the fixed short level, got {tags}")
    for ev in tp_exits:
        assert ev["precio"] == pytest.approx(tp_level)


# ---------------------------------------------------------------------------
# (5) the fixed TP is DISTINCT from and composes with the R-multiple f1_tp_r/
#     f2_tp_r: F3 (which never R-TPs) still gets a fixed TP.
# ---------------------------------------------------------------------------

def test_tp_min_applies_to_f3_unlike_r_multiple():
    bars, i, entry_px = _find_first_signal(+1, LONGHOLD_PARAMS)

    tp_pips = 20.0
    tp_level = entry_px + tp_pips * PIP
    b1 = dict(bars[i + 1])
    b1["high"] = max(b1["high"], tp_level + 1.0)
    b1["low"] = max(b1["low"], entry_px - 1.0)
    forced = bars[: i + 1] + [b1] + bars[i + 2:]

    events = simular_variant(
        forced, symbol="XAUUSD", tp_min_pips=tp_pips, **LONGHOLD_PARAMS)
    f3_tp = [ev for ev in events if ev["motivo"] == "EXIT_TP"
             and ev["ficha"] == "F3" and ev["idx"] == i + 1]
    assert f3_tp, "F3 must exit at the fixed tp_min_pips level (R-multiple never TPs F3)"
    assert f3_tp[0]["precio"] == pytest.approx(tp_level)
