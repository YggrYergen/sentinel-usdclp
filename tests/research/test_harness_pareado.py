r"""tests/research/test_harness_pareado.py -- WP-1+2 (harness pareado real-tick
+ parametros hoy hardcodeados). Cubre, un bloque por clase de test:

  B1 - run_supertrend(atr_period, mult) expuestos, defaults byte-identicos.
  B2 - overlay de kwargs por deep-copy sobre _GL[sid], _GL/_GOLIVE_M15 nunca mutados.
  B3 - harness pareado de K brazos + tabla de alineacion de entradas (con un caso
       donde los brazos NO comparten todas las entradas).
  B4 - umbral/lookback de ac_desacelerando, defaults byte-identicos.
  B5 - sl_offset de SuperTrend: coherencia toque/precio, default 0.0 byte-identico.
  B6 - instrumentacion de camino: apagada por defecto, inerte cuando esta encendida.

Bloques se agregan incrementalmente a este fichero segun se completan (TDD:
rojo -> minimo -> verde -> commit por bloque; ver
research/fases/F0-preparacion/02-specs/WP-1-2-progreso.md).

Ver brief: research/fases/F0-preparacion/02-specs/WP-1-2-brief-harness-pareado-y-parametros.md
"""
from __future__ import annotations

import numpy as np

from scripts.analysis.realtick_bt.backtest import run_supertrend

BAR_SEC = 900


class _FakeTicks:
    """Minimal stand-in for backtest.Ticks (same shape as
    tests/analysis/test_realtick_pairing.py's _FakeTicks): .first_at(t) and
    .range(t0, t1) on the epoch-seconds axis."""

    def __init__(self, ticks: list[tuple[float, float, float]]) -> None:
        self._t = np.array([t for t, _, _ in ticks], dtype="float64")
        self._bid = np.array([b for _, b, _ in ticks], dtype="float64")
        self._ask = np.array([a for _, _, a in ticks], dtype="float64")

    def first_at(self, t_sec: float):
        i = int(np.searchsorted(self._t, t_sec, "left"))
        if i < len(self._t):
            return float(self._t[i]), float(self._bid[i]), float(self._ask[i])
        return None

    def range(self, t0: float, t1: float):
        lo = int(np.searchsorted(self._t, t0, "left"))
        hi = int(np.searchsorted(self._t, t1, "left"))
        return self._t[lo:hi], self._bid[lo:hi], self._ask[lo:hi]


def _trend_bars(n: int = 40) -> list[dict]:
    """Synthetic bars with enough range/drift to make SuperTrend(14,3.0) flip
    at least once -- an up-leg then a down-leg, deterministic, no ticks needed
    for the flip path itself (EXIT_STFLIP fires on bar-close trend change)."""
    bars = []
    t0 = 1_700_000_000
    price = 100.0
    for i in range(n):
        # up for the first half, down for the second half; small oscillation
        # so highs/lows are never degenerate (division-by-zero-free ATR).
        drift = 0.8 if i < n // 2 else -0.8
        price += drift
        o = price - drift
        c = price
        h = max(o, c) + 0.3
        l = min(o, c) - 0.3
        bars.append({"t": t0 + BAR_SEC * i, "open": o, "high": h, "low": l,
                     "close": c, "volume": 1})
    return bars


# --------------------------------------------------------------------- B1
def test_run_supertrend_defaults_match_explicit_hardcoded_values():
    bars = _trend_bars()
    ticks = _FakeTicks([])   # no intra-bar touches -> exits are pure EXIT_STFLIP
    default_out = run_supertrend(bars, ticks)
    explicit_out = run_supertrend(bars, ticks, atr_period=14, mult=3.0)
    assert default_out == explicit_out
    assert len(default_out) > 0, "fixture must actually exercise at least one exit"


def test_run_supertrend_different_params_change_result():
    """Sanity: atr_period/mult are not silently ignored."""
    bars = _trend_bars()
    ticks = _FakeTicks([])
    default_out = run_supertrend(bars, ticks)
    wide_out = run_supertrend(bars, ticks, atr_period=14, mult=6.0)
    assert default_out != wide_out
