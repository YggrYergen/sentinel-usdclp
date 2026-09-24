"""Componente C de la réplica del motor faulty (tag engine-faulty-tomachine-902
-> b113eb7): la configuración del roster `tomachine` tal como REALMENTE corrió
en la cuenta 902, leída del commit congelado, nunca del working tree.

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md
§2-bis (ADDENDUM 2026-08-13 -- Componente C).

POR QUÉ EXISTE ESTE MÓDULO
---------------------------
El working tree tiene un roster `tomachine` (`CONFIGS_TOMACHINE` en
`sentinel_engine/strategies/live_configs_20.py`) que evolucionó con la
investigación y hoy es DISTINTO del que corrió en producción: 4 configs
(selección 2026-07-22) en vez de 2 (selección 2026-07-27), sin
`active_fichas` en S6-K2P0 (default del motor = 3) en vez de 1, y sin el
override de `volume`/`max_volume` = 0.67. Alimentar la réplica con el roster
del working tree simularía 4 estrategias con 3 fichas cada una -- la
divergencia D3, reintroducida por la puerta de atrás.

Este módulo lee EXCLUSIVAMENTE del vendorizado
`_vendored_live_configs_20_b113eb7.py` (copia byte a byte del blob de git en
`b113eb7`, ver `tests/analysis/test_config_faulty.py::
test_vendored_module_matches_frozen_blob_hash`). Jamás importa de
`sentinel_engine.strategies.live_configs_20` (el módulo vivo del working
tree): un import de esa ruta en este fichero es un fallo de la tarea.

R1-bis: nada aquí modifica el vendorizado ni ningún módulo vivo de
`sentinel_engine/`. El vendorizado se carga y se lee; jamás se edita.
"""
from __future__ import annotations

import copy
import importlib.util
import pathlib
from typing import Any

_VENDORED_PATH = pathlib.Path(__file__).parent / "_vendored_live_configs_20_b113eb7.py"


def _cargar_vendorizado():
    """Carga el módulo vendorizado como fichero standalone (nombre con `_` a
    propósito: es un artefacto congelado, no una API en `sys.modules`)."""
    spec = importlib.util.spec_from_file_location(
        "_vendored_live_configs_20_b113eb7", _VENDORED_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"no se pudo cargar el módulo vendorizado desde {_VENDORED_PATH}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_VENDORED = _cargar_vendorizado()

# Los 2 configs del roster tomachine tal como corrieron en la 902 (selección
# 2026-07-27): ya llevan el override del roster aplicado -- `volume` /
# `max_volume` = 0.67 y `kwargs["active_fichas"] = 1` en S6-K2P0 -- porque
# `_tomachine_copy` en el módulo congelado los aplica sobre copias
# independientes al construir `CONFIGS_TOMACHINE` (ver
# `_vendored_live_configs_20_b113eb7.py`, función `_tomachine_copy` y
# constructor de `CONFIGS_TOMACHINE`).
_CONFIGS_TOMACHINE: list[dict[str, Any]] = _VENDORED.CONFIGS_TOMACHINE


def configs_tomachine() -> list[dict[str, Any]]:
    """Los 2 configs del roster tomachine tal como corrieron en la 902, desde
    `b113eb7`: ids `S6-K2P0` y `SuperTrend-p14x3-M15`, cada uno con `volume` =
    `max_volume` = 0.67 y (solo S6-K2P0) `kwargs["active_fichas"] == 1`.

    Devuelve copias profundas independientes -- el llamador puede mutar el
    resultado sin afectar al roster congelado ni a llamadas futuras."""
    return copy.deepcopy(_CONFIGS_TOMACHINE)


def kwargs_de(config_id: str) -> dict[str, Any]:
    """kwargs EFECTIVAS de `config_id` ('S6-K2P0' o 'SuperTrend-p14x3-M15'),
    con el override del roster tomachine ya aplicado -- no las del roster
    base `_GOLIVE_M15`/`_GOLIVE_SUPERTREND`. Para 'S6-K2P0' eso significa que
    `active_fichas` vale 1.

    Lanza `KeyError` si `config_id` no está en el roster, con un mensaje que
    lista los ids disponibles."""
    por_id = {c["id"]: c for c in _CONFIGS_TOMACHINE}
    if config_id not in por_id:
        disponibles = sorted(por_id)
        raise KeyError(
            f"config_id {config_id!r} no está en el roster tomachine congelado "
            f"(b113eb7); disponibles: {disponibles}"
        )
    return copy.deepcopy(por_id[config_id]["kwargs"])
