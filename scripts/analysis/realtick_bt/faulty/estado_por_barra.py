"""Componente A de la réplica del motor faulty (tag engine-faulty-tomachine-902
-> b113eb7).

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md
§2 (Componente A). §1 explica por qué esto es correcto y no una aproximación:
el ejecutor vivo re-simula desde cero cada ~15 s sobre las últimas `window`
velas M15 CERRADAS (`include_forming=False`), así que el estado deseado del
sim es constante entre cierres de vela -- se calcula una vez por vela y los
ciclos de 15 s se iteran encima (Componente B, fichero aparte).

Este módulo NO reimplementa esa lógica: llama al motor real
(`simular_variant` / `supertrend_always_in_target`) una vez por índice, con
prefijos crecientes acotados por la MISMA ventana rodante que usa el vivo
(`bars[max(0, i+1-window):i+1]`). Es deliberadamente O(n^2) -- la fidelidad
al motor real es el objetivo de este componente, no la velocidad; la versión
rápida (Fase 2, spec aparte) se validará CONTRA esta.

R1-bis: `emasar_variant.py` y `live_configs_20.py` se importan y se llaman;
jamás se editan.

FORMA REAL DEL ESTADO (verificada leyendo el código, no asumida de la prosa
del spec -- ver emasar_variant.py:1441-1479 y live_configs_20.py:306-338):
ambas fuentes devuelven
    {"open": {ficha: {"side": "L"|"S", "entry": float, "sl": float,
                       "max_fav": float | None}},
     "last_bar_exits": {...},
     "last_idx": int}
o, cuando no hay ficha deseada, `"open": {}`. `estado_por_barra` NO
reinterpreta ni aplana esa forma: cada elemento de la lista devuelta es
exactamente ese dict, tal como lo emite el motor real, para que el test de
aceptación (tautológico por diseño) fije el contrato consumido por la Fase 2.
"""
from __future__ import annotations

from typing import Any

from sentinel_engine.strategies.emasar_variant import simular_variant
from sentinel_engine.strategies.live_configs_20 import supertrend_always_in_target


def _rango(n: int, idx_desde: int | None, idx_hasta: int | None) -> range:
    lo = 0 if idx_desde is None else idx_desde
    hi = (n - 1) if idx_hasta is None else idx_hasta
    return range(lo, hi + 1)


def estado_por_barra(
    bars: list[dict[str, Any]],
    kwargs: dict[str, Any],
    window: int = 10_000,
    idx_desde: int | None = None,
    idx_hasta: int | None = None,
) -> list[dict | None]:
    """Estado deseado del sim (S6/S7, vía `simular_variant`) DESPUÉS de cerrar
    cada barra i.

    Devuelve una lista de la misma longitud que `bars`. El elemento `i` es el
    segundo valor de retorno de
    `simular_variant(bars[max(0, i+1-window):i+1], return_state=True, **kwargs)`.
    Fuera de `[idx_desde, idx_hasta]` el elemento es `None` (no calculado).
    `bars` vacío -> `[]`, sin excepción. Pura: mismas entradas, misma salida;
    sin caché en disco, sin globals.
    """
    n = len(bars)
    resultado: list[dict | None] = [None] * n
    if n == 0:
        return resultado
    for i in _rango(n, idx_desde, idx_hasta):
        corte = bars[max(0, i + 1 - window):i + 1]
        _, deseado = simular_variant(corte, return_state=True, **kwargs)
        resultado[i] = deseado
    return resultado


def estado_por_barra_supertrend(
    bars: list[dict[str, Any]],
    window: int = 10_000,
    idx_desde: int | None = None,
    idx_hasta: int | None = None,
) -> list[dict | None]:
    """Mismo contrato de retorno que `estado_por_barra`, para SuperTrend.

    SuperTrend no corre por `simular_variant`: es `supertrend_always_in_target`
    (mono-ficha, devuelve el target directamente). El elemento `i` es
    `supertrend_always_in_target(bars[max(0, i+1-window):i+1])`.
    """
    n = len(bars)
    resultado: list[dict | None] = [None] * n
    if n == 0:
        return resultado
    for i in _rango(n, idx_desde, idx_hasta):
        corte = bars[max(0, i + 1 - window):i + 1]
        resultado[i] = supertrend_always_in_target(corte)
    return resultado
