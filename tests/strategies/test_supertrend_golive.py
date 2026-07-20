"""tests/strategies/test_supertrend_golive.py -- GL-T3: the 7th GO-LIVE
strategy, SuperTrend-p14x3-M15 (always-in).

Unlike the six simular_variant configs, this flavor is ALWAYS-IN: a SINGLE
position that is either LONG or SHORT and FLIPS when price crosses the
SuperTrend(14, 3.0) line on M15. It is NOT the 3-ficha ladder.

These tests pin the ADDITIVE contract that lets it reconcile like any other
magic WITHOUT touching the ladder reconciler:
  * `supertrend_always_in_target(bars)` returns a `return_state`-shaped
    snapshot: {"open": {"F1": {side, entry, sl}}, "last_bar_exits": {},
    "last_idx": ...} -- a SINGLE ficha (F1) on the SuperTrend side, with the
    SuperTrend line as the server-side SL;
  * long when the last closed bar's trend is +1 (price above the line),
    short when -1 (price below);
  * flipping the trend flips the target side (so the reconciler CLOSEs the
    old side and re-OPENs the opposite next cycle -- the always-in flip);
  * the roster now has SEVEN configs, the 7th on fresh magic 724070, and it
    is flagged with engine="supertrend_always_in" (NOT simular_variant).
No MT5, no orders.
"""
from __future__ import annotations

from sentinel_engine.strategies.live_configs_20 import (
    CONFIGS_GOLIVE,
    MAGIC_BY_ID_GOLIVE,
    supertrend_always_in_target,
)


def _trend_bars(n_up: int, n_down: int) -> list[dict]:
    """Bars that ramp UP strongly then ramp DOWN strongly, so SuperTrend is
    clearly long over the first leg and clearly short over the second."""
    bars: list[dict] = []
    t = 1_700_000_000
    price = 2000.0
    for k in range(n_up):
        o = price
        price += 3.0
        c = price
        bars.append({"t": t, "open": o, "high": max(o, c) + 0.5,
                     "low": min(o, c) - 0.5, "close": c})
        t += 900
    for k in range(n_down):
        o = price
        price -= 3.0
        c = price
        bars.append({"t": t, "open": o, "high": max(o, c) + 0.5,
                     "low": min(o, c) - 0.5, "close": c})
        t += 900
    return bars


def test_target_snapshot_shape_is_reconciler_ready():
    bars = _trend_bars(60, 0)
    snap = supertrend_always_in_target(bars)
    assert set(snap) >= {"open", "last_bar_exits", "last_idx"}
    assert snap["last_bar_exits"] == {}, "always-in has no same-bar ladder exits"
    # exactly ONE position slot (single always-in position, not a 3-ficha ladder)
    assert list(snap["open"]) == ["F1"]
    d = snap["open"]["F1"]
    assert set(d) >= {"side", "entry", "sl"}
    assert d["side"] in ("L", "S")


def test_long_when_price_above_line():
    """A clean uptrend leaves the last closed bar long (trend +1)."""
    bars = _trend_bars(60, 0)
    snap = supertrend_always_in_target(bars)
    d = snap["open"]["F1"]
    assert d["side"] == "L"
    # SL (the SuperTrend line) sits BELOW the entry for a long.
    assert d["sl"] < d["entry"]


def test_short_when_price_below_line():
    """A clean downtrend leaves the last closed bar short (trend -1)."""
    bars = _trend_bars(30, 60)
    snap = supertrend_always_in_target(bars)
    d = snap["open"]["F1"]
    assert d["side"] == "S"
    # SL (the SuperTrend line) sits ABOVE the entry for a short.
    assert d["sl"] > d["entry"]


def test_flip_flips_the_target_side():
    """Same feed, one leg longer: the always-in side flips with the trend.
    A pure uptrend => L; extending it with a strong downtrend => S."""
    up = supertrend_always_in_target(_trend_bars(60, 0))
    flipped = supertrend_always_in_target(_trend_bars(60, 60))
    assert up["open"]["F1"]["side"] == "L"
    assert flipped["open"]["F1"]["side"] == "S", "trend flip must flip the side"


def test_empty_bars_is_flat():
    assert supertrend_always_in_target([])["open"] == {}


def test_entry_is_last_closed_bar_close():
    bars = _trend_bars(60, 0)
    snap = supertrend_always_in_target(bars)
    assert snap["open"]["F1"]["entry"] == bars[-1]["close"]
    assert snap["last_idx"] == len(bars) - 1


# ------------------------- roster membership --------------------------------
def test_roster_has_seven_configs_with_supertrend_7th():
    assert len(CONFIGS_GOLIVE) == 7
    st = CONFIGS_GOLIVE[-1]
    assert st["id"] == "SuperTrend-p14x3-M15"
    assert st["tf"] == "M15"
    assert st["engine"] == "supertrend_always_in"
    assert st["magic"] == 724070
    assert MAGIC_BY_ID_GOLIVE["SuperTrend-p14x3-M15"] == 724070


def test_the_six_ladder_configs_stay_simular_variant():
    for c in CONFIGS_GOLIVE[:6]:
        assert c.get("engine", "simular_variant") == "simular_variant", c["id"]


def test_supertrend_magic_band_disjoint_from_the_six():
    st = CONFIGS_GOLIVE[-1]
    st_band = {st["magic"] + o for o in range(4)}
    six_band = {c["magic"] + o for c in CONFIGS_GOLIVE[:6] for o in range(4)}
    assert st_band.isdisjoint(six_band)
    assert all(724000 <= m <= 724099 for m in st_band)
