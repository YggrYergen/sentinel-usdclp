r"""scripts/analysis/realtick_bt/regime.py -- WP-5: regime computations (4
closed-form series, no external statistical dependency) + a boolean regime
gate, off by default. Sirve a P-09, habilita P-31
(research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md,
WP-5). **Does not touch `backtest.py` at all** -- per spec Section 2 table,
WP-5 "no toca el nucleo": this module is a pure, standalone add-on, consumed
(if at all) by future strategy levers, not wired into the engine here.

Self-contained: no import from `emasar_ref.py`/`emasar_variant.py` (out of
scope -- another agent owns the AC deceleration code) and no dependency
beyond numpy (already a project dependency); no `hmmlearn`/`statsmodels`/
`arch`/similar (those are the explicitly-deferred P-10/P-11/P-12, spec
Section 3).

Anti-look-ahead contract (spec Section 1), by construction: every series
value at bar `i` is computed from a STRICTLY TRAILING window/recursion over
`bars[0..i]` (never `bars[i+1:]`). ADX uses Wilder's classic left-to-right
recursive smoothing (each step depends only on the previous smoothed value
and the current bar); Variance Ratio / Efficiency Ratio / Choppiness use a
fixed trailing window ending at `i` (`bars[i-window+1 .. i]`), never a
centered or whole-series-then-indexed computation. This is verified by
`tests/research/test_regime.py`'s prefix-cut test (cut at `t`, recompute on
the prefix, require equality with the full-series value at `t`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


# --------------------------------------------------------------------------- helpers
def _true_range(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    n = len(highs)
    if n == 0:
        return []
    tr = [highs[0] - lows[0]]
    for i in range(1, n):
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    return tr


def _wilder_smooth(values: list[float], period: int) -> list[float | None]:
    """Wilder's smoothing: seed = simple sum of the first `period` values,
    then `S[i] = S[i-1] - S[i-1]/period + values[i]`. Purely left-to-right."""
    n = len(values)
    out: list[float | None] = [None] * n
    if n < period:
        return out
    s = sum(values[:period])
    out[period - 1] = s
    for i in range(period, n):
        s = s - s / period + values[i]
        out[i] = s
    return out


# --------------------------------------------------------------------------- ADX
def compute_adx(highs: list[float], lows: list[float], closes: list[float],
                 period: int = 14) -> list[float | None]:
    """Average Directional Index, Wilder's original recursive formulation.
    `None` during warm-up (needs `2*period - 1` bars for the first value,
    the classic ADX warm-up: `period` bars to seed the DI smoothing, another
    `period` DX values to seed the ADX smoothing itself)."""
    n = len(highs)
    if n == 0:
        return []
    tr = _true_range(highs, lows, closes)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
    tr_s = _wilder_smooth(tr, period)
    pdm_s = _wilder_smooth(plus_dm, period)
    mdm_s = _wilder_smooth(minus_dm, period)
    dx: list[float | None] = [None] * n
    for i in range(n):
        if tr_s[i] is None or tr_s[i] == 0:
            continue
        plus_di = 100.0 * pdm_s[i] / tr_s[i]
        minus_di = 100.0 * mdm_s[i] / tr_s[i]
        denom = plus_di + minus_di
        dx[i] = 100.0 * abs(plus_di - minus_di) / denom if denom > 0 else 0.0
    # ADX = Wilder-smoothed DX; seed with the simple average of the first
    # `period` AVAILABLE dx values (dx is None until index period-1).
    adx: list[float | None] = [None] * n
    first_dx = period - 1
    seed_end = first_dx + period  # exclusive
    if seed_end > n:
        return adx
    dx_seed = dx[first_dx:seed_end]
    if any(v is None for v in dx_seed):
        return adx
    s = sum(dx_seed) / period
    adx[seed_end - 1] = s
    for i in range(seed_end, n):
        if dx[i] is None:
            continue
        s = (s * (period - 1) + dx[i]) / period
        adx[i] = s
    return adx


# --------------------------------------------------------------------------- Variance Ratio
def compute_variance_ratio(closes: list[float], *, window: int = 40, q: int = 2) -> list[float | None]:
    """Lo-MacKinlay-style variance ratio over a STRICTLY TRAILING window of
    `window` log-returns ending at `i` (uses `bars[i-window..i]`, i.e. needs
    `window+1` closes). VR(q) = Var(q-period overlapping returns)/(q*Var(1-
    period returns)); VR ~= 1 for a random walk, >1 trending, <1 mean-
    reverting. `None` until the trailing window is full."""
    n = len(closes)
    out: list[float | None] = [None] * n
    if window < 2 * q:
        window = 2 * q  # q-period returns need at least 2*q 1-period returns to be meaningful
    for i in range(n):
        lo = i - window
        if lo < 0:
            continue
        seg = closes[lo:i + 1]
        if any(c <= 0 for c in seg):
            continue
        rets = [math.log(seg[j] / seg[j - 1]) for j in range(1, len(seg))]
        m = len(rets)
        if m < window:
            continue
        mean1 = sum(rets) / m
        var1 = sum((r - mean1) ** 2 for r in rets) / m
        if var1 <= 0:
            continue
        qrets = [sum(rets[j:j + q]) for j in range(0, m - q + 1)]
        mq = len(qrets)
        meanq = sum(qrets) / mq
        varq = sum((r - meanq) ** 2 for r in qrets) / mq
        out[i] = varq / (q * var1)
    return out


# --------------------------------------------------------------------------- Efficiency Ratio
def compute_efficiency_ratio(closes: list[float], *, period: int = 10) -> list[float | None]:
    """Kaufman's Efficiency Ratio: net displacement over `period` bars divided
    by the sum of the bar-to-bar absolute moves in that same TRAILING window
    (`bars[i-period..i]`). 1.0 = pure trend, ~0 = pure noise."""
    n = len(closes)
    out: list[float | None] = [None] * n
    for i in range(n):
        lo = i - period
        if lo < 0:
            continue
        net = abs(closes[i] - closes[lo])
        path = sum(abs(closes[j] - closes[j - 1]) for j in range(lo + 1, i + 1))
        out[i] = (net / path) if path > 0 else 0.0
    return out


# --------------------------------------------------------------------------- Choppiness Index
def compute_choppiness(highs: list[float], lows: list[float], closes: list[float],
                        *, period: int = 14) -> list[float | None]:
    """Choppiness Index over a TRAILING window of `period` bars
    (`bars[i-period+1..i]`): 100 * log10(sum(TR)/(max(high)-min(low))) /
    log10(period). Bounded in [0,100]; high = choppy/range-bound, low =
    trending."""
    n = len(highs)
    out: list[float | None] = [None] * n
    if n == 0:
        return out
    tr = _true_range(highs, lows, closes)
    log_period = math.log10(period)
    for i in range(n):
        lo = i - period + 1
        if lo < 0:
            continue
        sum_tr = sum(tr[lo:i + 1])
        rng = max(highs[lo:i + 1]) - min(lows[lo:i + 1])
        if rng <= 0 or sum_tr <= 0:
            continue
        out[i] = 100.0 * math.log10(sum_tr / rng) / log_period
    return out


@dataclass
class RegimeSeries:
    adx: list[float | None]
    variance_ratio: list[float | None]
    efficiency_ratio: list[float | None]
    choppiness: list[float | None]


def compute_regime_series(bars: list[dict[str, Any]], *, adx_period: int = 14,
                           vr_window: int = 40, vr_q: int = 2, er_period: int = 10,
                           chop_period: int = 14) -> RegimeSeries:
    """All 4 series, index-aligned with `bars`. Every entry at index `i` uses
    only `bars[0..i]` (see module docstring)."""
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    return RegimeSeries(
        adx=compute_adx(highs, lows, closes, adx_period),
        variance_ratio=compute_variance_ratio(closes, window=vr_window, q=vr_q),
        efficiency_ratio=compute_efficiency_ratio(closes, period=er_period),
        choppiness=compute_choppiness(highs, lows, closes, period=chop_period),
    )


# --------------------------------------------------------------------------- gate
@dataclass
class RegimeGateConfig:
    """Off by default (`enabled=False`): `regime_gate()` then always returns
    `True` (never filters anything) -- the WP-5 acceptance requirement ("con
    el gate apagado, resultado byte-idéntico al de hoy") holds trivially
    because this module is never called by the engine at all unless a future
    lever (P-31) opts in explicitly."""
    enabled: bool = False
    adx_min: float | None = None
    vr_low: float | None = None
    vr_high: float | None = None
    er_min: float | None = None
    chop_max: float | None = None
    k_of_m: int = 1


def regime_gate(idx: int, series: RegimeSeries, cfg: RegimeGateConfig) -> bool:
    """Boolean "k of m" composite gate over the 4 series at `bars[idx]`. Any
    criterion whose threshold is `None` is not evaluated (not counted in
    `m`). Missing/None indicator values (warm-up) count as a FAIL for that
    criterion, never as a pass."""
    if not cfg.enabled:
        return True
    checks: list[bool] = []
    if cfg.adx_min is not None:
        v = series.adx[idx]
        checks.append(v is not None and v >= cfg.adx_min)
    if cfg.vr_low is not None or cfg.vr_high is not None:
        v = series.variance_ratio[idx]
        ok = v is not None
        if ok and cfg.vr_low is not None:
            ok = v >= cfg.vr_low
        if ok and cfg.vr_high is not None:
            ok = ok and v <= cfg.vr_high
        checks.append(ok)
    if cfg.er_min is not None:
        v = series.efficiency_ratio[idx]
        checks.append(v is not None and v >= cfg.er_min)
    if cfg.chop_max is not None:
        v = series.choppiness[idx]
        checks.append(v is not None and v <= cfg.chop_max)
    if not checks:
        return True
    return sum(checks) >= cfg.k_of_m
