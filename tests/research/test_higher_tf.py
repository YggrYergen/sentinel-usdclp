r"""tests/research/test_higher_tf.py -- WP-3 (feed H1/H4 sobre M15).

Cubre el contrato antitrampa obligatorio del spec Section 1 -- verificado
cortando la serie en `t`, recalculando sobre el prefijo, y exigiendo igualdad
con el valor que el motor entrega en `t` sobre la serie completa -- mas el
test explicito de que la barra superior en curso nunca es visible.

Ver: research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md (WP-3)
     research/fases/F0-preparacion/02-specs/WP-345-progreso.md
"""
from __future__ import annotations

import numpy as np

from scripts.analysis.realtick_bt.higher_tf import (
    HigherSeries,
    aggregate_closed_with_visibility,
    build_higher_series,
)

M15_SEC = 900
H1_SEC = 3600
H4_SEC = 14400

# Multiple of H4_SEC -> every bucket boundary below is clean, no misalignment
# noise from the base offset itself.
T0 = 20 * H4_SEC


def _m15_bars(n: int, *, t0: float = T0, drift: float = 0.05) -> list[dict]:
    """Deterministic synthetic M15 bars, mildly trending so SuperTrend/EMA/
    momentum are non-degenerate. `t` = bar OPEN time (matches backtest.py's
    `load_bars()` convention)."""
    bars = []
    price = 2000.0
    for i in range(n):
        price += drift
        o = price - drift
        c = price
        h = max(o, c) + 0.2
        lo = min(o, c) - 0.2
        bars.append({"t": t0 + M15_SEC * i, "open": o, "high": h, "low": lo,
                     "close": c, "volume": 1})
    return bars


# --------------------------------------------------------------------- aggregation
def test_h1_aggregation_matches_manual_ohlc_over_first_bucket():
    bars = _m15_bars(32)  # 8 H1 buckets exactly (4 M15 bars each)
    closed, _ = aggregate_closed_with_visibility(bars, H1_SEC)
    assert len(closed) == 8
    first_4 = bars[0:4]
    b0 = closed[0]
    assert b0["t"] == T0
    assert b0["t_close"] == T0 + H1_SEC
    assert b0["open"] == first_4[0]["open"]
    assert b0["close"] == first_4[-1]["close"]
    assert b0["high"] == max(b["high"] for b in first_4)
    assert b0["low"] == min(b["low"] for b in first_4)
    assert b0["n_m15"] == 4


def test_h4_aggregation_produces_two_buckets_of_sixteen_bars():
    bars = _m15_bars(32)  # exactly 2 H4 buckets (16 M15 bars each)
    closed, _ = aggregate_closed_with_visibility(bars, H4_SEC)
    assert len(closed) == 2
    assert closed[0]["n_m15"] == 16
    assert closed[1]["n_m15"] == 16
    assert closed[0]["t"] == T0
    assert closed[1]["t"] == T0 + H4_SEC


# --------------------------------------------------------------------- in-progress bar never visible
def test_in_progress_h1_bucket_is_never_visible():
    bars = _m15_bars(32)
    _, visible_count = aggregate_closed_with_visibility(bars, H1_SEC)
    # first H1 bucket = bars[0..3] (4 M15 bars). While it is still forming
    # (bars 0,1,2 seen -- 3 of 4), it must NOT be visible.
    assert visible_count[0] == 0
    assert visible_count[1] == 0
    assert visible_count[2] == 0
    # bar 3 is the LAST M15 bar of that bucket: its OWN close (t+900) equals
    # the bucket's close boundary -- provably closed using only that bar's
    # own data, no look-ahead into bar 4.
    assert visible_count[3] == 1
    # second bucket (bars 4..7) mirrors the same pattern.
    assert visible_count[4] == 1
    assert visible_count[5] == 1
    assert visible_count[6] == 1
    assert visible_count[7] == 2


def test_in_progress_h4_bucket_is_never_visible_even_after_most_of_its_bars():
    bars = _m15_bars(20)  # first H4 bucket = 16 M15 bars, plus 4 into the next
    _, visible_count = aggregate_closed_with_visibility(bars, H4_SEC)
    # 15 of 16 M15 bars of the first H4 bucket have arrived -- still 0 closed.
    assert visible_count[14] == 0
    # the 16th (last) M15 bar closes the bucket exactly on its own close.
    assert visible_count[15] == 1
    assert visible_count[19] == 1  # second bucket still forming (4/16 bars)


# --------------------------------------------------------------------- anti-look-ahead (spec Section 1)
def test_prefix_cut_recompute_equals_full_series_value_at_t_h1():
    bars = _m15_bars(60)
    full = build_higher_series(bars, H1_SEC)
    for k in (2, 3, 7, 15, 20, 40, 59):
        prefix = build_higher_series(bars[: k + 1], H1_SEC)
        m = len(prefix.bars)
        assert prefix.bars == full.bars[:m], f"k={k}: closed bars diverge under prefix cut"
        assert prefix.ema[:m] == full.ema[:m], f"k={k}: ema diverges"
        assert prefix.ema_slope[:m] == full.ema_slope[:m], f"k={k}: ema_slope diverges"
        assert prefix.st_dir[:m] == full.st_dir[:m], f"k={k}: st_dir diverges"
        assert prefix.momentum[:m] == full.momentum[:m], f"k={k}: momentum diverges"
        assert int(prefix.visible_count[k]) == int(full.visible_count[k]), (
            f"k={k}: visible_count at the cut point diverges -- look-ahead"
        )
        # the snapshot the engine would see AT t (cut at k, recomputed on the
        # prefix) must equal the snapshot the full series gives at that same
        # M15 index.
        assert prefix.snapshot_at_m15_index(k) == full.snapshot_at_m15_index(k)


def test_prefix_cut_recompute_equals_full_series_value_at_t_h4():
    bars = _m15_bars(80)
    full = build_higher_series(bars, H4_SEC)
    for k in (5, 15, 16, 31, 32, 63, 79):
        prefix = build_higher_series(bars[: k + 1], H4_SEC)
        m = len(prefix.bars)
        assert prefix.bars == full.bars[:m]
        assert prefix.ema[:m] == full.ema[:m]
        assert prefix.st_dir[:m] == full.st_dir[:m]
        assert int(prefix.visible_count[k]) == int(full.visible_count[k])
        assert prefix.snapshot_at_m15_index(k) == full.snapshot_at_m15_index(k)


def test_cutting_mid_bucket_never_leaks_the_forming_bucket():
    """Explicit regression for the exact failure mode named in the spec: a
    4h bar being formed must NOT exist for a decision inside it."""
    bars = _m15_bars(20)
    full = build_higher_series(bars, H4_SEC)
    # cut right before the first H4 bucket closes (bar index 14, 15 of 16 seen)
    prefix = build_higher_series(bars[:15], H4_SEC)
    assert prefix.bars == []  # the in-progress bucket must not appear at all
    assert prefix.snapshot_at_m15_index(14) is None
    assert full.snapshot_at_m15_index(14) is None  # same instant, same answer


# --------------------------------------------------------------------- snapshot / caching shape
def test_snapshot_is_none_before_any_higher_bar_has_closed():
    bars = _m15_bars(3)  # not enough to close even one H1 bucket
    series = build_higher_series(bars, H1_SEC)
    assert series.bars == []
    for i in range(3):
        assert series.snapshot_at_m15_index(i) is None


def test_snapshot_populates_after_first_close_and_momentum_warms_up():
    bars = _m15_bars(80)
    series = build_higher_series(bars, H1_SEC, momentum_lookback=10)
    snap_early = series.snapshot_at_m15_index(3)  # first H1 bucket just closed
    assert snap_early is not None
    assert snap_early["momentum"] is None  # only 1 higher bar closed, lookback=10
    snap_late = series.snapshot_at_m15_index(79)
    assert snap_late is not None
    assert snap_late["momentum"] is not None
    assert snap_late["ema"] is not None
    assert snap_late["ema_slope"] is not None
    assert snap_late["st_dir"] in (+1, -1)


def test_indicator_arrays_are_cached_per_closed_higher_bar_not_per_m15_bar():
    """Structural proxy for 'recomputation must not be linear in history per
    bar': every indicator array has EXACTLY one entry per CLOSED higher bar
    (len(bars)), never one entry per M15 bar (len(bars_m15))."""
    bars = _m15_bars(200)
    series = build_higher_series(bars, H4_SEC)
    m = len(series.bars)
    assert 0 < m < len(bars)
    assert len(series.ema) == m
    assert len(series.ema_slope) == m
    assert len(series.st_dir) == m
    assert len(series.momentum) == m
    assert len(series.visible_count) == len(bars)  # one lookup slot per M15 bar, O(1) each


def test_visible_count_is_monotonic_non_decreasing():
    bars = _m15_bars(200)
    series = build_higher_series(bars, H4_SEC)
    diffs = np.diff(series.visible_count)
    assert (diffs >= 0).all()


def test_returns_a_higherseries_dataclass_instance():
    bars = _m15_bars(20)
    series = build_higher_series(bars, H1_SEC)
    assert isinstance(series, HigherSeries)
    assert series.tf_sec == H1_SEC
