r"""tests/research/test_regime.py -- WP-5 (4 series de regimen + gate).

Cubre el contrato antitrampa obligatorio del spec Section 1 para las 4 series
(ADX, Variance Ratio, Efficiency Ratio, Choppiness) -- corte de prefijo,
recalculo, igualdad con el valor de la serie completa en `t` -- y el gate
booleano apagado por defecto.

Ver: research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md (WP-5)
     research/fases/F0-preparacion/02-specs/WP-345-progreso.md
"""
from __future__ import annotations

import math

from scripts.analysis.realtick_bt.regime import (
    RegimeGateConfig,
    RegimeSeries,
    compute_adx,
    compute_choppiness,
    compute_efficiency_ratio,
    compute_regime_series,
    compute_variance_ratio,
    regime_gate,
)

BAR_SEC = 900
T0 = 20 * 14400


def _trending_bars(n: int, *, t0: float = T0, drift: float = 0.6) -> list[dict]:
    bars = []
    price = 2000.0
    for i in range(n):
        price += drift
        o = price - drift
        c = price
        h = max(o, c) + 0.15
        lo = min(o, c) - 0.15
        bars.append({"t": t0 + BAR_SEC * i, "open": o, "high": h, "low": lo, "close": c, "volume": 1})
    return bars


def _choppy_bars(n: int, *, t0: float = T0, amp: float = 3.0) -> list[dict]:
    bars = []
    base = 2000.0
    for i in range(n):
        c = base + amp * (1 if i % 2 == 0 else -1)
        o = base
        h = max(o, c) + 0.5
        lo = min(o, c) - 0.5
        bars.append({"t": t0 + BAR_SEC * i, "open": o, "high": h, "low": lo, "close": c, "volume": 1})
    return bars


# --------------------------------------------------------------------- sanity: trending vs choppy
def test_efficiency_ratio_near_one_for_a_clean_trend():
    bars = _trending_bars(60)
    closes = [b["close"] for b in bars]
    er = compute_efficiency_ratio(closes, period=10)
    assert er[59] is not None
    assert er[59] > 0.9  # near-monotonic drift -> ER close to 1


def test_efficiency_ratio_near_zero_for_pure_chop():
    bars = _choppy_bars(60)
    closes = [b["close"] for b in bars]
    er = compute_efficiency_ratio(closes, period=10)
    assert er[59] is not None
    assert er[59] < 0.2  # net displacement ~0 vs a lot of back-and-forth path


def test_choppiness_higher_for_chop_than_for_trend_same_period():
    trend = _trending_bars(60)
    chop = _choppy_bars(60)
    c_trend = compute_choppiness([b["high"] for b in trend], [b["low"] for b in trend],
                                  [b["close"] for b in trend], period=14)
    c_chop = compute_choppiness([b["high"] for b in chop], [b["low"] for b in chop],
                                 [b["close"] for b in chop], period=14)
    assert c_trend[59] is not None and c_chop[59] is not None
    assert c_chop[59] > c_trend[59]


def test_adx_rises_above_warmup_none_on_a_sustained_trend():
    bars = _trending_bars(80)
    adx = compute_adx([b["high"] for b in bars], [b["low"] for b in bars],
                       [b["close"] for b in bars], period=14)
    assert adx[27] is not None  # 2*period-1 warm-up
    assert adx[79] is not None
    assert adx[79] > 10.0  # a clean one-directional drift should register as directional


def test_variance_ratio_is_none_before_the_trailing_window_is_full():
    bars = _trending_bars(30)
    closes = [b["close"] for b in bars]
    vr = compute_variance_ratio(closes, window=20, q=2)
    assert vr[18] is None
    assert vr[20] is not None


def test_variance_ratio_greater_than_one_for_a_persistent_trend():
    bars = _trending_bars(80, drift=0.6)
    closes = [b["close"] for b in bars]
    vr = compute_variance_ratio(closes, window=40, q=2)
    assert vr[79] is not None
    assert vr[79] > 1.0  # constant-drift returns are positively autocorrelated -> VR(2) > 1


# --------------------------------------------------------------------- anti-look-ahead (spec Section 1)
def test_prefix_cut_recompute_equals_full_series_value_at_t_all_four_series():
    bars = _trending_bars(120)
    full = compute_regime_series(bars, adx_period=14, vr_window=40, vr_q=2, er_period=10, chop_period=14)
    for k in (5, 13, 14, 27, 28, 39, 40, 60, 90, 119):
        prefix = compute_regime_series(bars[: k + 1], adx_period=14, vr_window=40, vr_q=2,
                                        er_period=10, chop_period=14)
        assert prefix.adx[k] == full.adx[k], f"k={k}: ADX diverges under prefix cut -- look-ahead"
        assert prefix.variance_ratio[k] == full.variance_ratio[k], f"k={k}: variance_ratio diverges"
        assert prefix.efficiency_ratio[k] == full.efficiency_ratio[k], f"k={k}: efficiency_ratio diverges"
        assert prefix.choppiness[k] == full.choppiness[k], f"k={k}: choppiness diverges"


def test_prefix_cut_recompute_equals_full_series_value_at_t_choppy_bars():
    bars = _choppy_bars(120)
    full = compute_regime_series(bars)
    for k in (10, 40, 41, 80, 119):
        prefix = compute_regime_series(bars[: k + 1])
        assert prefix.adx[k] == full.adx[k]
        assert prefix.variance_ratio[k] == full.variance_ratio[k]
        assert prefix.efficiency_ratio[k] == full.efficiency_ratio[k]
        assert prefix.choppiness[k] == full.choppiness[k]


def test_the_future_bar_never_changes_a_past_regime_value():
    """Explicit regression for the exact failure mode named in the spec:
    appending MORE bars after t must not change the series value AT t."""
    bars = _trending_bars(50)
    short = compute_regime_series(bars)
    longer_bars = bars + _choppy_bars(50, t0=bars[-1]["t"] + BAR_SEC)  # totally different regime tacked on after
    longer = compute_regime_series(longer_bars)
    for k in (14, 28, 40, 49):
        assert short.adx[k] == longer.adx[k]
        assert short.variance_ratio[k] == longer.variance_ratio[k]
        assert short.efficiency_ratio[k] == longer.efficiency_ratio[k]
        assert short.choppiness[k] == longer.choppiness[k]


# --------------------------------------------------------------------- gate
def test_regime_gate_off_by_default_always_true():
    bars = _trending_bars(50)
    series = compute_regime_series(bars)
    cfg = RegimeGateConfig()  # enabled=False
    for i in range(50):
        assert regime_gate(i, series, cfg) is True


def test_regime_gate_none_indicator_counts_as_fail_not_pass():
    series = RegimeSeries(adx=[None], variance_ratio=[None], efficiency_ratio=[None], choppiness=[None])
    cfg = RegimeGateConfig(enabled=True, adx_min=20.0, k_of_m=1)
    assert regime_gate(0, series, cfg) is False


def test_regime_gate_k_of_m_requires_enough_criteria_to_pass():
    series = RegimeSeries(adx=[30.0], variance_ratio=[1.5], efficiency_ratio=[0.1], choppiness=[80.0])
    # adx>=20 PASS, vr in [1.2,2.0] PASS, er>=0.5 FAIL, chop<=40 FAIL -> 2 of 4
    cfg2 = RegimeGateConfig(enabled=True, adx_min=20.0, vr_low=1.2, vr_high=2.0,
                             er_min=0.5, chop_max=40.0, k_of_m=2)
    assert regime_gate(0, series, cfg2) is True
    cfg3 = RegimeGateConfig(enabled=True, adx_min=20.0, vr_low=1.2, vr_high=2.0,
                             er_min=0.5, chop_max=40.0, k_of_m=3)
    assert regime_gate(0, series, cfg3) is False


def test_regime_gate_only_evaluates_criteria_with_a_threshold_set():
    series = RegimeSeries(adx=[5.0], variance_ratio=[None], efficiency_ratio=[None], choppiness=[None])
    cfg = RegimeGateConfig(enabled=True, adx_min=1.0, k_of_m=1)  # only ADX has a threshold
    assert regime_gate(0, series, cfg) is True
