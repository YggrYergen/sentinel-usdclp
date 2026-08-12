"""Tests de `scripts/research/ventana_calendario.py` -- D-36, Paso 2b.

Por que existe. D-36 revoca el borde conservador fijo `18:00->02:00` ET de
`ny_window.py` y ordena modelar la ventana operativa como CALENDARIO DE
PERIODOS medido: el cierre cambia de `02:00` a `03:00` ET el 2026-04-06 (D-34,
D-36). Este fichero prueba el modulo que resuelve esa regla fechada, sin
tocar `ny_window.py` (que sigue vigente para `cost_overlay.py`).

La propiedad que define esta tarea: la hora `02:00` ET esta FUERA de la
ventana en un instante del 2026-04-04 y DENTRO en un instante del 2026-04-07
(el cierre paso de `02:00` a `03:00` en ese cruce). Ver
`test_cierre_cambia_02_a_03_entre_04_04_y_04_07`.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from scripts.research.cost_overlay import assert_fuera_holdout_capitaria
from scripts.research.ventana_calendario import (
    cargar_calendario,
    es_extrapolado,
    filter_bars,
    in_ventana,
    ventana_para,
)

CALENDARIO_PATH = (
    r"D:\FOREX\research\fases\F0-preparacion\04-resultados"
    r"\T0.13-ventana-ny\calendario-ventana.json"
)


@pytest.fixture(scope="module")
def calendario():
    return cargar_calendario(CALENDARIO_PATH)


# --------------------------------------------------------------------- carga
def test_cargar_calendario_real():
    cal = cargar_calendario(CALENDARIO_PATH)
    assert "periodos" in cal
    assert "rango_medido" in cal
    assert len(cal["periodos"]) > 0


def test_cargar_calendario_fichero_ausente_es_error_duro(tmp_path):
    with pytest.raises(FileNotFoundError):
        cargar_calendario(tmp_path / "no-existe.json")


@pytest.mark.parametrize("clave_a_borrar", ["periodos", "rango_medido"])
def test_cargar_calendario_incompleto_es_error_duro(tmp_path, calendario, clave_a_borrar):
    incompleto = dict(calendario)
    del incompleto[clave_a_borrar]
    p = tmp_path / "incompleto.json"
    p.write_text(json.dumps(incompleto), encoding="utf-8")
    with pytest.raises(KeyError):
        cargar_calendario(p)


def test_cargar_calendario_periodo_sin_clave_requerida_es_error_duro(tmp_path, calendario):
    roto = json.loads(json.dumps(calendario))  # copia profunda
    del roto["periodos"][0]["cierre_ny"]
    p = tmp_path / "periodo-roto.json"
    p.write_text(json.dumps(roto), encoding="utf-8")
    with pytest.raises(KeyError):
        cargar_calendario(p)


def test_cargar_calendario_lista_periodos_vacia_es_error_duro(tmp_path, calendario):
    vacio = dict(calendario)
    vacio["periodos"] = []
    p = tmp_path / "sin-periodos.json"
    p.write_text(json.dumps(vacio), encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_calendario(p)


# --------------------------------------------------------------------- disyuncion
def test_in_ventana_no_es_un_rango(calendario):
    """Si alguien reescribe `in_ventana` como un rango `apertura <= hora <
    cierre`, este test se pone rojo: con apertura=18 y cierre in {2,3}, el
    rango naive es SIEMPRE FALSO (18 no es < 2 ni < 3) y devolveria el
    conjunto vacio para TODAS las horas, sin lanzar ningun error."""
    dentro_conocido = datetime(2026, 6, 15, 20, 0, 0)  # 20:00 ET, dentro por construccion
    assert in_ventana(dentro_conocido, calendario) is True

    apertura, cierre = ventana_para(dentro_conocido, calendario)
    assert apertura > cierre  # la ventana cruza medianoche: el rango naive fallaria
    for h in range(24):
        rango_naive = apertura <= h < cierre
        assert rango_naive is False  # documenta por que el rango esta mal


def test_in_ventana_disyuncion_18_dentro_10_fuera(calendario):
    dt_18 = datetime(2026, 6, 15, 18, 0, 0)
    dt_10 = datetime(2026, 6, 15, 10, 0, 0)
    assert in_ventana(dt_18, calendario) is True
    assert in_ventana(dt_10, calendario) is False


# ------------------------------------------------- la propiedad de esta tarea
def test_cierre_cambia_02_a_03_entre_04_04_y_04_07(calendario):
    """02:00 ET esta FUERA de la ventana el 2026-04-04 (cierre aun 02:00) y
    DENTRO el 2026-04-07 (cierre ya 03:00, tras el cruce del 2026-04-06)."""
    antes = datetime(2026, 4, 4, 2, 0, 0)
    despues = datetime(2026, 4, 7, 2, 0, 0)

    assert in_ventana(antes, calendario) is False
    assert in_ventana(despues, calendario) is True

    _, cierre_antes = ventana_para(antes, calendario)
    _, cierre_despues = ventana_para(despues, calendario)
    assert cierre_antes == 2
    assert cierre_despues == 3


# --------------------------------------------------------------------- apertura
def test_apertura_18_en_todos_los_periodos(calendario):
    """La apertura (18:00 ET, ancla de mercado) es el borde solido: D-34/D-36
    la establecen constante en todo el periodo medido. Se verifica en un
    instante de cada periodo del calendario."""
    for periodo in calendario["periodos"]:
        d = date.fromisoformat(periodo["desde"])
        dt = datetime(d.year, d.month, d.day, 20, 0, 0)  # 20:00 ET, dentro de cualquier ventana
        apertura, _ = ventana_para(dt, calendario)
        assert apertura == 18, f"periodo {periodo['desde']}: apertura {apertura} != 18"


# ------------------------------------------------------------------- extrapolacion
def test_es_extrapolado_2022_true_2026_dentro_rango_false(calendario):
    fecha_2022 = datetime(2022, 6, 15, 20, 0, 0)
    fecha_2026_medida = datetime(2026, 6, 15, 20, 0, 0)
    assert es_extrapolado(fecha_2022, calendario) is True
    assert es_extrapolado(fecha_2026_medida, calendario) is False


def test_extrapolacion_conserva_apertura_18_y_aplica_dst_estacional(calendario):
    """Para 2023 (fuera del rango medido), la apertura sigue siendo 18:00 y
    el cierre reproduce el mismo ciclo estacional que 2026: 02:00 antes del
    6 de abril, 03:00 desde el 6 de abril (D-36: 'se aplica el cierre del
    periodo medido mas cercano en el calendario, respetando el DST vigente
    en esa fecha')."""
    antes_2023 = datetime(2023, 3, 1, 20, 0, 0)
    despues_2023 = datetime(2023, 4, 20, 20, 0, 0)

    assert es_extrapolado(antes_2023, calendario) is True
    assert es_extrapolado(despues_2023, calendario) is True

    apertura_antes, cierre_antes = ventana_para(antes_2023, calendario)
    apertura_despues, cierre_despues = ventana_para(despues_2023, calendario)
    assert apertura_antes == 18
    assert apertura_despues == 18
    assert cierre_antes == 2
    assert cierre_despues == 3


# --------------------------------------------------------------------- filter_bars
def test_filter_bars_no_muta_entrada(calendario):
    import calendar as calmod

    naive_dentro = datetime(2026, 6, 15, 20, 0, 0)
    naive_fuera = datetime(2026, 6, 15, 10, 0, 0)
    bars = [
        {"t": float(calmod.timegm(naive_dentro.timetuple())), "o": 1},
        {"t": float(calmod.timegm(naive_fuera.timetuple())), "o": 2},
    ]
    bars_copia = [dict(b) for b in bars]

    resultado = filter_bars(bars, "capitaria", calendario)

    assert bars == bars_copia  # entrada intacta
    assert len(resultado) == 1
    assert resultado[0]["o"] == 1


def test_filter_bars_devuelve_lista_nueva(calendario):
    bars: list[dict] = []
    resultado = filter_bars(bars, "capitaria", calendario)
    assert resultado is not bars


# --------------------------------------------------------------------- HOLDOUT
def test_guarda_holdout_capitaria_aborta():
    """Guarda dura reutilizada de `cost_overlay.py` (charter SS A.14 + D-31
    acto 1): cualquier rango que toque el holdout sellado de Capitaria debe
    abortar. Esta medicion (`medir_calendario_ventana.py`) invoca esta misma
    guarda ANTES de leer disco -- se prueba aqui la guarda en si."""
    with pytest.raises(SystemExit):
        assert_fuera_holdout_capitaria(
            float(__import__("calendar").timegm(datetime(2026, 6, 1).timetuple())),
            float(__import__("calendar").timegm(datetime(2026, 6, 2).timetuple())),
        )
