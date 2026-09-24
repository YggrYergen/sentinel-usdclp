"""Tests de `scripts/research/ny_window.py` -- T0.13 llevado a codigo.

Por que existe. T0.13 (cerrado) midio que el "gate de spread 0.5" del sistema
vivo de Capitaria es en realidad un reloj: el estado de spread estrecho esta
al 99-100% dentro de la ventana 18:00->02:00 hora de Nueva York (apertura de
la sesion electronica del oro en CME Globex) y al 0-5% fuera. El backtest
largo corre sobre AVA, cuyo spread no codifica ese estado (research/NEGATIVOS.md),
asi que la ventana debe reconstruirse como regla de reloj explicita.

Punto de maximo riesgo (ver docstring de ny_window.py): backtest.py decodifica
epochs con `datetime.utcfromtimestamp()`, que para Capitaria devuelve la HORA
DE PARED DEL SERVIDOR CHILENO, no UTC (backtest.py:15-26). Adjuntarle
`timezone.utc` en vez de `America/Santiago` produce un error silencioso de
3-4 horas. El test `test_capitaria_naive_no_es_utc_diverge_3_4h` existe
especificamente para detectar esa implementacion ingenua.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timezone

import pytest

from scripts.research.ny_window import (
    BROKER_TZ,
    filter_bars_ny,
    in_ny_window,
    server_epoch_to_ny,
)


# --------------------------------------------------------------------- BROKER_TZ
def test_broker_tz_mapea_capitaria_y_ava():
    from zoneinfo import ZoneInfo

    assert BROKER_TZ["capitaria"] == ZoneInfo("America/Santiago")
    assert BROKER_TZ["ava"] == timezone.utc


def test_broker_desconocido_es_error_duro():
    with pytest.raises((KeyError, ValueError)):
        server_epoch_to_ny(1700000000.0, "broker_inventado")


# --------------------------------------------------------------------- disyuncion
@pytest.mark.parametrize("hour,expected", [
    (18, True), (23, True), (1, True),   # 01:59 -> hora entera 1
    (2, False), (10, False), (17, False),
])
def test_in_ny_window_disyuncion_por_hora(hour, expected):
    dt = datetime(2026, 6, 15, hour, 0, 0, tzinfo=timezone.utc)  # tz irrelevante, solo .hour importa
    assert in_ny_window(dt) is expected


def test_in_ny_window_1_59_dentro_2_00_fuera():
    dentro = datetime(2026, 6, 15, 1, 59, 0)
    fuera = datetime(2026, 6, 15, 2, 0, 0)
    assert in_ny_window(dentro) is True
    assert in_ny_window(fuera) is False


def test_in_ny_window_no_es_un_rango_18_a_2():
    """Si alguien reescribe la condicion como `18 <= hora < 2`, este test se pone
    rojo: ese rango es SIEMPRE FALSO (18 no es < 2), devolviendo el conjunto vacio
    sin lanzar ningun error -- el modo de fallo mas peligroso de esta tarea."""
    alguna_hora_dentro = datetime(2026, 6, 15, 20, 0, 0)
    assert in_ny_window(alguna_hora_dentro) is True
    # Prueba directa de la trampa: el rango naive daria False para TODAS las horas.
    for h in range(24):
        rango_naive = 18 <= h < 2
        assert rango_naive is False  # documenta por que el rango esta mal


# ------------------------------------------------------- el punto de maximo riesgo
def test_capitaria_naive_no_es_utc_diverge_3_4h():
    """Epoch tal que server-wall-clock == 2026-06-15 20:00:00 (Chile invierno,
    UTC-4, lejos de cualquier transicion DST). Tratado como America/Santiago
    (correcto) cae DENTRO de la ventana NY; tratado como si fuese UTC (naive
    incorrecto: `naive.replace(tzinfo=timezone.utc)`) cae FUERA. Si la
    implementacion trata el naive como UTC, este test falla."""
    naive = datetime(2026, 6, 15, 20, 0, 0)
    epoch = float(calendar.timegm(naive.timetuple()))

    correcto = server_epoch_to_ny(epoch, "capitaria")
    assert correcto.hour == 20
    assert in_ny_window(correcto) is True

    incorrecto_como_utc = naive.replace(tzinfo=timezone.utc).astimezone(
        correcto.tzinfo if correcto.tzinfo else timezone.utc
    )
    # La implementacion ingenua (tratar el naive como UTC) da una hora NY distinta.
    assert incorrecto_como_utc.hour != correcto.hour
    assert incorrecto_como_utc.hour == 16
    assert in_ny_window(incorrecto_como_utc) is False


def test_capitaria_naive_replace_utc_seria_incorrecto_por_construccion():
    """Version explicita de la trampa: si `server_epoch_to_ny` usara
    `naive.replace(tzinfo=timezone.utc).astimezone(NY)` en vez de adjuntar
    America/Santiago primero, el resultado seria distinto del correcto."""
    from zoneinfo import ZoneInfo

    naive = datetime(2026, 6, 15, 20, 0, 0)
    epoch = float(calendar.timegm(naive.timetuple()))

    correcto = server_epoch_to_ny(epoch, "capitaria")
    ingenuo = naive.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/New_York"))
    assert correcto.replace(tzinfo=None) != ingenuo.replace(tzinfo=None)


# --------------------------------------------------------------------- AVA es UTC
def test_ava_naive_es_utc_directo():
    """Para AVA el naive de utcfromtimestamp() YA es UTC (reloj fijo, sin DST).
    La conversion a NY resta 4h (EDT) o 5h (EST) segun el DST de EEUU."""
    naive_invierno_us = datetime(2026, 1, 15, 22, 0, 0)  # EST, UTC-5
    epoch = float(calendar.timegm(naive_invierno_us.timetuple()))
    ny = server_epoch_to_ny(epoch, "ava")
    assert ny.hour == 17  # 22 UTC - 5 = 17 NY -> fuera de la ventana
    assert in_ny_window(ny) is False

    naive_verano_us = datetime(2026, 6, 15, 22, 0, 0)  # EDT, UTC-4
    epoch2 = float(calendar.timegm(naive_verano_us.timetuple()))
    ny2 = server_epoch_to_ny(epoch2, "ava")
    assert ny2.hour == 18  # 22 UTC - 4 = 18 NY -> dentro de la ventana
    assert in_ny_window(ny2) is True


# ------------------------------------------------------------------- cruces DST
def test_dst_eeuu_2026_03_08_ava():
    """DST de EEUU empieza 2026-03-08 02:00 hora local (salta a las 03:00). El
    mismo reloj de servidor AVA (UTC fijo), 22:00, cae fuera de la ventana el
    sabado anterior (EST, NY=17:00) y dentro el lunes posterior (EDT, NY=18:00)."""
    antes = datetime(2026, 3, 7, 22, 0, 0)  # sabado, antes del salto
    despues = datetime(2026, 3, 9, 22, 0, 0)  # lunes, despues del salto

    ny_antes = server_epoch_to_ny(float(calendar.timegm(antes.timetuple())), "ava")
    ny_despues = server_epoch_to_ny(float(calendar.timegm(despues.timetuple())), "ava")

    assert ny_antes.hour == 17
    assert in_ny_window(ny_antes) is False

    assert ny_despues.hour == 18
    assert in_ny_window(ny_despues) is True


def test_dst_chile_2026_04_05_capitaria():
    """DST de Chile termina el 2026-04-05 (vuelve a hora estandar UTC-4). El
    mismo reloj de servidor Capitaria, 18:00, cae fuera de la ventana NY el
    2026-04-04 (Santiago aun en UTC-3 -> NY 17:00) y dentro el 2026-04-06
    (Santiago ya en UTC-4 -> NY 18:00)."""
    antes = datetime(2026, 4, 4, 18, 0, 0)
    despues = datetime(2026, 4, 6, 18, 0, 0)

    ny_antes = server_epoch_to_ny(float(calendar.timegm(antes.timetuple())), "capitaria")
    ny_despues = server_epoch_to_ny(float(calendar.timegm(despues.timetuple())), "capitaria")

    assert ny_antes.hour == 17
    assert in_ny_window(ny_antes) is False

    assert ny_despues.hour == 18
    assert in_ny_window(ny_despues) is True


# --------------------------------------------------------------------- filter_bars_ny
def test_filter_bars_ny_no_muta_entrada():
    naive_dentro = datetime(2026, 6, 15, 20, 0, 0)
    naive_fuera = datetime(2026, 6, 15, 10, 0, 0)
    bars = [
        {"t": float(calendar.timegm(naive_dentro.timetuple())), "o": 1},
        {"t": float(calendar.timegm(naive_fuera.timetuple())), "o": 2},
    ]
    bars_copia = [dict(b) for b in bars]

    resultado = filter_bars_ny(bars, "capitaria")

    assert bars == bars_copia  # entrada intacta
    assert len(resultado) == 1
    assert resultado[0]["o"] == 1


def test_filter_bars_ny_devuelve_lista_nueva():
    bars: list[dict] = []
    resultado = filter_bars_ny(bars, "capitaria")
    assert resultado is not bars
