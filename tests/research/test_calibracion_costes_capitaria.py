"""Tests de `scripts/research/calibracion_costes_capitaria.py` -- T0.6 mod
#10, extension D-36/D-37 (ventana periodizada).

Por que existe. D-36/D-37 revocan el borde fijo 18:00->02:00 ET (D-34) que
esta calibracion usaba (`in_ny_window`). La ventana operativa ahora es un
CALENDARIO DE PERIODOS fechado (`ventana_calendario.py`), y dos de los cuatro
periodos cierran a las 03:00/03:15 ET en vez de 02:00 -- la hora 2 NY esta
DENTRO de ventana solo en esos periodos, y FUERA en los otros dos. Calibrar
la hora 2 mezclando ambos regimenes contaminaria el numero con ticks de
spread ancho (fuera de ventana) que no corresponden a ninguna condicion real
de operacion.

Este fichero prueba SOLO la logica pura de filtrado (`_ticks_en_ventana`):
que el predicado usado es `ventana_calendario.in_ventana` (fechado), no
`ny_window.in_ny_window` (fijo) -- sin tocar disco ni ticks reales de
Capitaria (eso lo verifica la regeneracion real de `calibracion.json`, fuera
del alcance de un test unitario).
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from scripts.research.calibracion_costes_capitaria import _ticks_en_ventana


def _calendario_02_hasta_0404_03_desde_0405() -> dict:
    """Calendario minimo con la misma propiedad que el artefacto real
    (D-34/D-36/D-37): cierre 02:00 antes del 2026-04-05, cierre 03:00 desde
    esa fecha. Apertura 18:00 en ambos periodos (borde solido, D-34)."""
    return {
        "periodos": [
            {
                "desde": "2026-01-01", "hasta": "2026-04-04",
                "apertura_ny": "18:00", "cierre_ny": "02:00",
                "n_semanas": 1, "n_semanas_baja_cobertura": 0,
            },
            {
                "desde": "2026-04-05", "hasta": "2026-12-31",
                "apertura_ny": "18:00", "cierre_ny": "03:00",
                "n_semanas": 1, "n_semanas_baja_cobertura": 0,
            },
        ],
        "rango_medido": {"desde": "2026-01-01", "hasta": "2026-12-31"},
    }


def _epoch_ava_para_ny(dt_ny_naive: datetime) -> float:
    """Epoch en convencion backtest.py para broker 'ava' (server tz = UTC
    fijo, ver ny_window.BROKER_TZ) tal que server_epoch_to_ny(epoch, 'ava')
    caiga exactamente en `dt_ny_naive` (se interpreta como hora de NY)."""
    from zoneinfo import ZoneInfo
    ny = dt_ny_naive.replace(tzinfo=ZoneInfo("America/New_York"))
    return ny.astimezone(timezone.utc).timestamp()


def test_hora_2_fuera_de_ventana_antes_del_cambio_de_cierre():
    """2026-03-01, hora 2 NY: el periodo vigente (desde 2026-01-01) cierra a
    las 02:00 -- la hora 2 NO esta dentro (hora < cierre exige 2 < 2, falso)."""
    calendario = _calendario_02_hasta_0404_03_desde_0405()
    t = np.array([_epoch_ava_para_ny(datetime(2026, 3, 1, 2, 0, 0))])
    mask, horas = _ticks_en_ventana(t, "ava", calendario)
    assert mask[0] == False  # noqa: E712
    assert horas[0] == 2


def test_hora_2_dentro_de_ventana_despues_del_cambio_de_cierre():
    """2026-04-10, hora 2 NY: el periodo vigente (desde 2026-04-05) cierra a
    las 03:00 -- la hora 2 SI esta dentro (2 < 3)."""
    calendario = _calendario_02_hasta_0404_03_desde_0405()
    t = np.array([_epoch_ava_para_ny(datetime(2026, 4, 10, 2, 0, 0))])
    mask, horas = _ticks_en_ventana(t, "ava", calendario)
    assert mask[0] == True  # noqa: E712
    assert horas[0] == 2


def test_mismo_reloj_hora_2_distinto_veredicto_segun_fecha():
    """La propiedad central de esta tarea: el MISMO valor de hora (2) da
    veredictos opuestos segun la fecha, porque el predicado es fechado
    (ventana_calendario.in_ventana), no un offset fijo (ny_window.in_ny_window,
    que trataria ambos ticks igual)."""
    calendario = _calendario_02_hasta_0404_03_desde_0405()
    t = np.array([
        _epoch_ava_para_ny(datetime(2026, 3, 1, 2, 0, 0)),
        _epoch_ava_para_ny(datetime(2026, 4, 10, 2, 0, 0)),
    ])
    mask, horas = _ticks_en_ventana(t, "ava", calendario)
    assert list(horas) == [2, 2]
    assert list(mask) == [False, True]


def test_hora_20_siempre_dentro_independiente_del_periodo():
    """Control: una hora del nucleo solido de la ventana (20h) esta dentro en
    ambos periodos -- no todo cambia con el calendario, solo el borde 2h."""
    calendario = _calendario_02_hasta_0404_03_desde_0405()
    t = np.array([
        _epoch_ava_para_ny(datetime(2026, 3, 1, 20, 0, 0)),
        _epoch_ava_para_ny(datetime(2026, 4, 10, 20, 0, 0)),
    ])
    mask, horas = _ticks_en_ventana(t, "ava", calendario)
    assert list(horas) == [20, 20]
    assert list(mask) == [True, True]
