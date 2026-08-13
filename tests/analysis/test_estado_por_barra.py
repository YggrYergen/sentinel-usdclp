"""tests/analysis/test_estado_por_barra.py -- Componente A de la réplica del
motor faulty (tag engine-faulty-tomachine-902 -> b113eb7).

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md
§2 (Componente A). `estado_por_barra` / `estado_por_barra_supertrend` calculan,
para cada índice `i` de una lista de velas M15 cerradas, el estado deseado del
motor real (`simular_variant(..., return_state=True)` / `supertrend_always_in_target`)
evaluado sobre la ventana rodante `bars[max(0, i+1-window):i+1]` -- exactamente
lo que el ejecutor vivo vería si consultara al motor tras cerrar esa vela.

El test de aceptación de la Fase 1 (Comp. A) es DELIBERADAMENTE tautológico:
compara el elemento `i` contra una llamada directa al motor real con la MISMA
ventana. Es tautológico por construcción y por eso mismo debe estar escrito
(fija el contrato consumido por la Fase 2, que sí reimplementará la lógica).

R1-bis: nada aquí modifica `emasar_variant.py` / `live_configs_20.py` / ningún
módulo vivo de `sentinel_engine/`. Se importan y se llaman.
"""
from __future__ import annotations

from scripts.analysis.realtick_bt.backtest import load_bars, _GL
from sentinel_engine.strategies.emasar_variant import simular_variant
from sentinel_engine.strategies.live_configs_20 import supertrend_always_in_target

from scripts.analysis.realtick_bt.faulty.estado_por_barra import (
    estado_por_barra,
    estado_por_barra_supertrend,
)

# S6-K2P0 kwargs, byte-idénticas entre el working tree y el commit congelado
# b113eb7 (verificado por el controlador, 0 diferencias en 21 claves). Se
# reutiliza el mismo patrón de import que scripts/analysis/realtick_bt/backtest.py:70.
_S6_KWARGS = _GL["S6-K2P0"]

# Slice fijo del lago real de Capitaria (data/lake_ticks/XAUUSD/_bars_M15.parquet
# vía load_bars()), cacheado a nivel de módulo para no releer el parquet en cada test.
_ALL_BARS = load_bars()


def _slice_real(a: int, b: int) -> list[dict]:
    assert b <= len(_ALL_BARS), "el lago tiene menos velas de las pedidas por el test"
    return _ALL_BARS[a:b]


# --------------------------------------------------------------------- vacío
def test_bars_vacio_devuelve_lista_vacia_sin_excepcion():
    assert estado_por_barra([], _S6_KWARGS) == []


def test_bars_vacio_devuelve_lista_vacia_sin_excepcion_supertrend():
    assert estado_por_barra_supertrend([]) == []


# ------------------------------------------------------- tautológico, S6 ---
def test_tautologico_ventana_grande_i_menor_que_window():
    """window=10000 (default) sobre 220 velas reales: para TODO i, i < window,
    así que el corte siempre empieza en 0 (`bars[0:i+1]`) -- el caso borde
    "i < window" del spec queda cubierto por construcción en este mismo test.
    """
    bars = _slice_real(2000, 2220)
    resultado = estado_por_barra(bars, _S6_KWARGS)
    assert len(resultado) == len(bars)
    for i in range(len(bars)):
        esperado = simular_variant(bars[max(0, i + 1 - 10_000):i + 1],
                                    return_state=True, **_S6_KWARGS)[1]
        assert resultado[i] == esperado, f"i={i}"


def test_tautologico_ventana_pequena_trunca_el_corte():
    """window=10 sobre 60 velas reales: para i>=10 el corte YA NO empieza en 0
    (bars[i-9:i+1]) -- ejercita la ventana rodante propiamente dicha, no sólo
    el caso borde inicial.
    """
    bars = _slice_real(2000, 2060)
    window = 10
    resultado = estado_por_barra(bars, _S6_KWARGS, window=window)
    assert len(resultado) == len(bars)
    for i in range(len(bars)):
        corte = bars[max(0, i + 1 - window):i + 1]
        esperado = simular_variant(corte, return_state=True, **_S6_KWARGS)[1]
        assert resultado[i] == esperado, f"i={i}"
        if i >= window:
            assert len(corte) == window


def test_idx_desde_idx_hasta_acota_el_calculo():
    """Fuera de [idx_desde, idx_hasta] el elemento es None (no calculado);
    dentro, coincide con la llamada directa al motor sobre la misma ventana.
    """
    bars = _slice_real(2000, 2050)
    window = 10_000
    resultado = estado_por_barra(bars, _S6_KWARGS, window=window,
                                  idx_desde=10, idx_hasta=20)
    assert len(resultado) == len(bars)
    for i in range(len(bars)):
        if i < 10 or i > 20:
            assert resultado[i] is None, f"i={i} debería ser None"
        else:
            esperado = simular_variant(bars[max(0, i + 1 - window):i + 1],
                                        return_state=True, **_S6_KWARGS)[1]
            assert resultado[i] == esperado, f"i={i}"


# ------------------------------------------------- tautológico, SuperTrend -
def test_tautologico_supertrend_ventana_grande_i_menor_que_window():
    bars = _slice_real(2000, 2220)
    resultado = estado_por_barra_supertrend(bars)
    assert len(resultado) == len(bars)
    for i in range(len(bars)):
        esperado = supertrend_always_in_target(bars[max(0, i + 1 - 10_000):i + 1])
        assert resultado[i] == esperado, f"i={i}"


def test_tautologico_supertrend_ventana_pequena_trunca_el_corte():
    bars = _slice_real(2000, 2060)
    window = 10
    resultado = estado_por_barra_supertrend(bars, window=window)
    assert len(resultado) == len(bars)
    for i in range(len(bars)):
        corte = bars[max(0, i + 1 - window):i + 1]
        esperado = supertrend_always_in_target(corte)
        assert resultado[i] == esperado, f"i={i}"
        if i >= window:
            assert len(corte) == window


def test_idx_desde_idx_hasta_acota_el_calculo_supertrend():
    bars = _slice_real(2000, 2050)
    window = 10_000
    resultado = estado_por_barra_supertrend(bars, window=window,
                                             idx_desde=10, idx_hasta=20)
    assert len(resultado) == len(bars)
    for i in range(len(bars)):
        if i < 10 or i > 20:
            assert resultado[i] is None, f"i={i} debería ser None"
        else:
            esperado = supertrend_always_in_target(
                bars[max(0, i + 1 - window):i + 1])
            assert resultado[i] == esperado, f"i={i}"


# ------------------------------------------------------------------- pureza
def test_estado_por_barra_es_pura_no_reordena_ni_muta_bars():
    bars = _slice_real(2000, 2060)
    original = [dict(b) for b in bars]
    estado_por_barra(bars, _S6_KWARGS, window=10)
    assert bars == original


def test_estado_por_barra_supertrend_es_pura_no_reordena_ni_muta_bars():
    bars = _slice_real(2000, 2060)
    original = [dict(b) for b in bars]
    estado_por_barra_supertrend(bars, window=10)
    assert bars == original
