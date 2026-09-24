"""tests/live/test_ava_window_gate.py -- R1 (blackout de apertura) + R2
(ventana operativa) para el despliegue AVA (D-62, 2026-08-20).

Cubre, como exige el encargo:
  * el borde de la 4a vela (18:45 ET) en AMBOS lados del cambio de horario de
    EEUU (DST) -- el epoch UTC que corresponde a "18:45 hora de Nueva York"
    se DESPLAZA una hora entre invierno (EST, UTC-5) y verano (EDT, UTC-4);
    el gate debe seguir el reloj de pared de Nueva York, no un offset fijo.
  * el rechazo dentro de la ventana operativa prohibida (R2).
  * que R1 deriva su ancla del calendario (no de un "18" hardcodeado aparte).
  * que el fichero de calendario real de produccion carga sin error.

Los epochs de los tests DST se calcularon independientemente con
`zoneinfo.ZoneInfo("America/New_York")` (ver el informe del implementador
para la sesion que los genero) -- no se re-derivan aqui con la misma
maquinaria que el modulo bajo prueba usa, para que el test sea una
verificacion genuina y no una tautologia.
"""
from __future__ import annotations

import json

import pytest

from sentinel_engine.live import ava_window_gate as awg


# ---------------------------------------------------------------- fixtures
@pytest.fixture()
def calendario_simple():
    """Calendario sintetico: un unico periodo 2020-2030, apertura 18:00 ET,
    cierre 02:00 ET -- evita depender de la extrapolacion/multiples periodos
    del calendario real de produccion para los tests que solo necesitan un
    borde estable."""
    return {
        "periodos": [{
            "desde": "2020-01-01", "hasta": "2030-12-31",
            "apertura_ny": "18:00", "cierre_ny": "02:00",
            "n_semanas": 1, "n_semanas_baja_cobertura": 0,
        }],
        "rango_medido": {"desde": "2020-01-01", "hasta": "2030-12-31"},
    }


@pytest.fixture()
def calendario_ancla_20h():
    """Mismo calendario pero con apertura 20:00 ET -- usado para probar que
    R1 sigue el ancla del calendario, nunca un '18' hardcodeado aparte."""
    return {
        "periodos": [{
            "desde": "2020-01-01", "hasta": "2030-12-31",
            "apertura_ny": "20:00", "cierre_ny": "04:00",
            "n_semanas": 1, "n_semanas_baja_cobertura": 0,
        }],
        "rango_medido": {"desde": "2020-01-01", "hasta": "2030-12-31"},
    }


# ---------------------------------------------------------- R1 en aislado
def test_r1_ok_blocks_first_three_m15_candles():
    # velas 1-3 (apertura 18:00,18:15,18:30) -- bloqueadas.
    from datetime import datetime
    for minute in (0, 15, 30, 44):
        dt = datetime(2026, 6, 15, 18, minute, 0)
        assert awg.r1_ok(dt, apertura_hora=18) is False, f"minute={minute} debe bloquear"


def test_r1_ok_allows_from_fourth_candle():
    from datetime import datetime
    for minute in (45, 50, 59):
        dt = datetime(2026, 6, 15, 18, minute, 0)
        assert awg.r1_ok(dt, apertura_hora=18) is True, f"minute={minute} debe permitir"
    # horas posteriores a la de apertura: siempre permitido por R1 (R2 decide
    # si esa hora esta dentro de la ventana operativa, R1 no vuelve a bloquear).
    assert awg.r1_ok(datetime(2026, 6, 15, 19, 0, 0), apertura_hora=18) is True
    assert awg.r1_ok(datetime(2026, 6, 16, 1, 30, 0), apertura_hora=18) is True


def test_r1_ok_only_bites_at_the_anchor_hour():
    # una hora distinta a la de apertura nunca es bloqueada por R1, aunque
    # el minuto sea < 45 (R1 es solo el blackout de LA apertura).
    from datetime import datetime
    dt = datetime(2026, 6, 15, 2, 10, 0)
    assert awg.r1_ok(dt, apertura_hora=18) is True


# ------------------------------------------------------- R2 (ventana) sola
def test_open_allowed_true_well_inside_window_after_blackout(calendario_simple):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    dt_ny = datetime(2026, 6, 15, 20, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    epoch = dt_ny.timestamp()
    assert awg.open_allowed(epoch, calendario_simple, broker="ava") is True


def test_open_allowed_false_outside_the_operating_window(calendario_simple):
    # 12:00 ET -- horario laboral chileno/de dia, fuera de la ventana 18-02.
    from datetime import datetime
    from zoneinfo import ZoneInfo
    dt_ny = datetime(2026, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    epoch = dt_ny.timestamp()
    assert awg.open_allowed(epoch, calendario_simple, broker="ava") is False


# ---------------------------------------------- DST -- el borde de 18:45 ET
# Epochs calculados independientemente (zoneinfo.ZoneInfo("America/New_York")):
#   invierno (EST, UTC-5): 2026-01-15
#   verano   (EDT, UTC-4): 2026-07-01
_INVIERNO_1844_ET = 1768520640  # 2026-01-15 18:44:00-05:00
_INVIERNO_1845_ET = 1768520700  # 2026-01-15 18:45:00-05:00
_VERANO_1844_ET = 1782945840    # 2026-07-01 18:44:00-04:00
_VERANO_1845_ET = 1782945900    # 2026-07-01 18:45:00-04:00


def test_dst_boundary_winter_1844_blocked_1845_allowed(calendario_simple):
    assert awg.open_allowed(_INVIERNO_1844_ET, calendario_simple, broker="ava") is False
    assert awg.open_allowed(_INVIERNO_1845_ET, calendario_simple, broker="ava") is True


def test_dst_boundary_summer_1844_blocked_1845_allowed(calendario_simple):
    assert awg.open_allowed(_VERANO_1844_ET, calendario_simple, broker="ava") is False
    assert awg.open_allowed(_VERANO_1845_ET, calendario_simple, broker="ava") is True


def test_dst_boundary_epochs_are_one_hour_apart_between_seasons():
    """Confirma la premisa del test: el MISMO instante de pared '18:44 ET'
    cae en epochs UTC distintos en invierno vs verano (offset -5 vs -4) --
    si el gate usara un offset UTC fijo en vez de zoneinfo, uno de los dos
    tests de arriba fallaria."""
    # ambos representan "18:44 hora de pared de NY" en dias de estaciones
    # distintas; la diferencia de fecha (15-ene a 1-jul, ~167 dias) hace que
    # la resta cruda no sea exactamente 1h -- se verifica solo que las horas
    # de reloj UTC de cada uno difieren en el offset esperado.
    import datetime as dt
    invierno_utc = dt.datetime.utcfromtimestamp(_INVIERNO_1844_ET)
    verano_utc = dt.datetime.utcfromtimestamp(_VERANO_1844_ET)
    assert invierno_utc.hour == 23  # 18:44 EST -05:00 -> 23:44 UTC
    assert verano_utc.hour == 22    # 18:44 EDT -04:00 -> 22:44 UTC


# ----------------------------------------------- R1 sigue el ancla del calendario
def test_r1_anchor_follows_calendar_not_hardcoded(calendario_ancla_20h):
    """Con un calendario cuya apertura es 20:00 ET (no 18:00), el blackout
    de R1 debe desplazarse a 20:00-20:44 -- si el codigo tuviera un '18'
    hardcodeado en vez de derivarlo del calendario, este test lo detectaria."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
    bloqueado = datetime(2026, 6, 15, 20, 30, 0, tzinfo=NY).timestamp()
    permitido = datetime(2026, 6, 15, 20, 45, 0, tzinfo=NY).timestamp()
    # a las 18:30 ET (la vieja apertura) ya no hay blackout -- esa hora ahora
    # cae dentro de la ventana operativa sin restriccion de R1 (no es la
    # apertura vigente en este calendario).
    fuera_de_la_vieja_apertura = datetime(2026, 6, 15, 18, 30, 0, tzinfo=NY).timestamp()

    assert awg.open_allowed(bloqueado, calendario_ancla_20h, broker="ava") is False
    assert awg.open_allowed(permitido, calendario_ancla_20h, broker="ava") is True
    # 18:30 ET esta fuera de la ventana 20:00->04:00 de este calendario, asi
    # que R2 la rechaza igual (por ventana, no por R1) -- se prueba aparte
    # con ventana_para para no confundir el motivo.
    from scripts.research import ventana_calendario
    from scripts.research import ny_window
    dt_ny = ny_window.server_epoch_to_ny(fuera_de_la_vieja_apertura, "ava")
    apertura, _ = ventana_calendario.ventana_para(dt_ny, calendario_ancla_20h)
    assert apertura == 20, "el calendario debe reportar la apertura vigente (20), no 18"


# --------------------------------------------------------- carga real / cache
def test_cargar_calendario_ava_loads_real_production_file():
    cal = awg.cargar_calendario_ava()
    assert "periodos" in cal
    assert len(cal["periodos"]) > 0
    assert cal["broker"] == "capitaria", (
        "el calendario D-36/D-37 se midio sobre Capitaria y se transfiere a "
        "AVA por hipotesis declarada (D-36) -- no debe aparecer re-etiquetado "
        "como si se hubiera medido sobre AVA")


def test_cargar_calendario_ava_is_cached():
    a = awg.cargar_calendario_ava()
    b = awg.cargar_calendario_ava()
    assert a is b, "cargar_calendario_ava debe cachear por ruta (lru_cache)"


def test_cargar_calendario_ava_missing_file_is_a_hard_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        awg.cargar_calendario_ava(tmp_path / "no-existe.json")


def test_cargar_calendario_ava_incomplete_file_is_a_hard_error(tmp_path):
    p = tmp_path / "incompleto.json"
    p.write_text(json.dumps({"periodos": []}), encoding="utf-8")
    with pytest.raises((KeyError, ValueError)):
        awg.cargar_calendario_ava(p)


# --------------------------------------------------------- broker desconocido
def test_open_allowed_broker_no_declarado_es_error_duro(calendario_simple):
    with pytest.raises(KeyError):
        awg.open_allowed(1700000000, calendario_simple, broker="capitaria_mal_escrito")
