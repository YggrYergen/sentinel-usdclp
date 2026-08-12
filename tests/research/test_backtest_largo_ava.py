"""Tests de `scripts/research/backtest_largo_ava.py` -- T0.6, backtest largo
de S6/SuperTrend sobre ~3.5 anos de ticks reales de AVA.

Por que existe. Este driver conduce `scripts/analysis/realtick_bt/backtest.py`
sin tocarlo (R1-bis), insertando el overlay de costes (D-21) y el filtro de
ventana+exclusiones (D-33/D-36/D-37) por fuera del motor. Las piezas mas
riesgosas -- la version vectorizada de la conversion de reloj AVA->NY, la
guarda de "el overlay nunca estrecha" (D-21), el bloqueo duro de lectura del
holdout sellado (D-31 acto 2) incluso via el sondeo de mes-vecino de
`Ticks._candidates`, y el filtro de exclusiones de continuidad (D-33) -- son
funciones puras y rapidas: se testean aqui sin tocar el lago completo de
ticks (246M ticks), que es cosa del driver real, no de esta suite.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta

import numpy as np
import pytest

from scripts.research.backtest_largo_ava import (
    AVA_HOLDOUT_FIN,
    AVA_HOLDOUT_INI,
    AvaTicks,
    _overlay_month,
    cargar_exclusiones,
    cobertura_mensual,
    filter_exclusiones,
    ny_hours_ava,
)
from scripts.research.ny_window import server_epoch_to_ny


# --------------------------------------------------------------- ny_hours_ava
def _calib_tipica(horas) -> dict:
    por_hora = {}
    for h in horas:
        por_hora[str(h)] = {"mediana": 0.55, "media": 0.56, "p75": 0.60, "n": 1000}
    return {"por_hora": por_hora}


HORAS_VENTANA_TEST = (18, 19, 20, 21, 22, 23, 0, 1, 2)


def _epochs_muestra() -> list[float]:
    """Epochs 'server AVA' (= UTC) repartidos por 2022-2026, incluyendo
    fechas cercanas a los dos cruces de DST de Nueva York (principios de
    marzo / principios de noviembre) cada ano, que es donde una conversion
    vectorizada mal hecha divergiria de la escalar testeada."""
    epochs = []
    for year in range(2022, 2027):
        for month, day in [(1, 15), (3, 8), (3, 9), (3, 10), (6, 15),
                            (11, 1), (11, 2), (11, 3), (12, 20)]:
            try:
                base = datetime(year, month, day)
            except ValueError:
                continue
            for hour in (0, 1, 2, 3, 17, 18, 19, 23):
                epochs.append(calendar.timegm((base + timedelta(hours=hour)).timetuple()))
    return epochs


def test_ny_hours_ava_coincide_con_server_epoch_to_ny_escalar():
    epochs = _epochs_muestra()
    esperado = [server_epoch_to_ny(t, "ava").hour for t in epochs]
    obtenido = ny_hours_ava(np.array(epochs, dtype="float64"))
    assert list(obtenido) == esperado


def test_ny_hours_ava_vacio():
    assert len(ny_hours_ava(np.array([]))) == 0


# --------------------------------------------------------------- _overlay_month
def test_overlay_month_ensancha_dentro_de_ventana():
    calib = _calib_tipica(HORAS_VENTANA_TEST)
    # un tick a las 23:00 UTC (= 18:00 NY en invierno EST, UTC-5); se
    # verifica con ny_hours_ava en vez de suponerlo.
    t = np.array([calendar.timegm(datetime(2024, 1, 15, 23, 0, 0).timetuple())], dtype="float64")
    bid = np.array([2000.10])
    ask = np.array([2000.20])  # spread nativo 0.10, mas angosto que 0.55 calibrado
    hora = int(ny_hours_ava(t)[0])
    assert hora in HORAS_VENTANA_TEST, "ajustar el tick de prueba a una hora cubierta por la calibracion"
    _t2, bid2, ask2, n_no_eval = _overlay_month(t, bid, ask, calib, "mediana", HORAS_VENTANA_TEST)
    assert n_no_eval == 0  # nativo mas ANGOSTO que el calibrado: ensancha, es evaluable
    assert ask2[0] - bid2[0] == pytest.approx(0.55)
    mid_orig = (bid[0] + ask[0]) / 2.0
    mid_new = (bid2[0] + ask2[0]) / 2.0
    assert mid_new == pytest.approx(mid_orig)  # D-21: se conserva el mid de AVA


def test_overlay_month_deja_intactos_los_ticks_fuera_de_ventana():
    calib = _calib_tipica(HORAS_VENTANA_TEST)
    # 12:00 UTC no esta en HORAS_VENTANA_TEST bajo ningun periodo del calendario
    t = np.array([calendar.timegm(datetime(2024, 1, 15, 12, 0, 0).timetuple())], dtype="float64")
    bid = np.array([2000.10])
    ask = np.array([2000.20])
    hora = int(ny_hours_ava(t)[0])
    assert hora not in HORAS_VENTANA_TEST
    _t2, bid2, ask2, n_no_eval = _overlay_month(t, bid, ask, calib, "mediana", HORAS_VENTANA_TEST)
    assert n_no_eval == 0  # fuera de ventana no se evalua la regla D-38
    assert bid2[0] == bid[0]
    assert ask2[0] == ask[0]


def test_overlay_month_retira_ticks_nativos_mas_anchos_que_la_calibracion():
    """🔴 D-38 (decision del user, 2026-08-12, interpretando D-21): el overlay
    NUNCA estrecha. Medido en datos reales (AVA 2022-01), ~0,016% de los ticks
    tiene spread nativo anomalo (hasta 3.0, huecos/iliquidez puntual), MAS
    ancho que cualquier valor calibrado (~0.5-0.6). Sustituir ahi la anchura
    ESTRECHARIA. Esos ticks se declaran NO EVALUABLES y se RETIRAN -- ni se
    estrechan ni se conservan crudos."""
    calib = _calib_tipica(HORAS_VENTANA_TEST)
    t_ancho = calendar.timegm(datetime(2024, 1, 15, 23, 0, 0).timetuple())
    t_normal = calendar.timegm(datetime(2024, 1, 15, 23, 0, 1).timetuple())
    t = np.array([t_ancho, t_normal], dtype="float64")
    bid = np.array([2000.00, 2000.10])
    ask = np.array([2001.00, 2000.20])  # nativo 1.00 (> 0.55) y 0.10 (< 0.55)

    t2, bid2, ask2, n_no_eval = _overlay_month(t, bid, ask, calib, "mediana", HORAS_VENTANA_TEST)

    assert n_no_eval == 1                      # el ancho se declara no evaluable
    assert len(t2) == len(bid2) == len(ask2) == 1
    assert t2[0] == pytest.approx(float(t_normal))   # sobrevive el evaluable, no el otro
    assert ask2[0] - bid2[0] == pytest.approx(0.55)


def test_overlay_month_igualdad_exacta_no_se_retira():
    """La regla D-38 es `nativo > calibrado` ESTRICTO: un tick cuyo spread
    nativo coincide exactamente con el calibrado no estrecha, luego es
    evaluable y se conserva."""
    calib = _calib_tipica(HORAS_VENTANA_TEST)
    t = np.array([calendar.timegm(datetime(2024, 1, 15, 23, 0, 0).timetuple())], dtype="float64")
    bid = np.array([2000.000])
    ask = np.array([2000.550])  # nativo == 0.55 == calibrado
    t2, bid2, ask2, n_no_eval = _overlay_month(t, bid, ask, calib, "mediana", HORAS_VENTANA_TEST)
    assert n_no_eval == 0
    assert len(t2) == 1
    assert ask2[0] - bid2[0] == pytest.approx(0.55)


def test_overlay_month_aborta_si_la_anchura_resultante_no_es_la_calibrada():
    """Guarda D-21 real: dispara si `overlay_arrays` (mockeado aqui) no
    produce exactamente la anchura calibrada -- el caso que atraparia una
    inversion del overlay (p.ej. min() en vez de sustitucion)."""
    import scripts.research.backtest_largo_ava as mod

    calib = _calib_tipica(HORAS_VENTANA_TEST)
    t = np.array([calendar.timegm(datetime(2024, 1, 15, 23, 0, 0).timetuple())], dtype="float64")
    bid = np.array([2000.10])
    ask = np.array([2000.20])  # evaluable (nativo 0.10 < 0.55): no lo retira D-38

    def _overlay_roto(bids, asks, dts_ny, calib, modo):
        # simula una inversion: toma el MIN(nativo, calibrado) en vez de sustituir
        bids = np.asarray(bids, dtype=float); asks = np.asarray(asks, dtype=float)
        mid = (bids + asks) / 2.0
        return mid - 0.001, mid + 0.001  # anchura 0.002, distinta de la calibrada

    orig = mod.co.overlay_arrays
    mod.co.overlay_arrays = _overlay_roto
    try:
        with pytest.raises(SystemExit, match="no produjo la anchura calibrada"):
            _overlay_month(t, bid, ask, calib, "mediana", HORAS_VENTANA_TEST)
    finally:
        mod.co.overlay_arrays = orig


def test_overlay_month_array_vacio_no_falla():
    calib = _calib_tipica(HORAS_VENTANA_TEST)
    t2, bid2, ask2, n_no_eval = _overlay_month(np.array([]), np.array([]), np.array([]),
                                               calib, "mediana", HORAS_VENTANA_TEST)
    assert len(t2) == 0 and len(bid2) == 0 and len(ask2) == 0
    assert n_no_eval == 0


# --------------------------------------------------------------------- AvaTicks
def test_avaticks_nunca_lee_meses_de_2023():
    """Holdout sellado (D-31 acto 2). Meses 2023 deben devolver arrays
    vacios SIN abrir ningun parquet -- ni siquiera si el fichero existiera
    fisicamente en TICKDIR_AVA."""
    calib = _calib_tipica(HORAS_VENTANA_TEST)
    ticks = AvaTicks(calib, "mediana", HORAS_VENTANA_TEST)
    for ym in ("202301", "202306", "202312"):
        ta, bid, ask = ticks._load(ym)
        assert len(ta) == 0 and len(bid) == 0 and len(ask) == 0


def test_avaticks_first_at_no_devuelve_nada_del_holdout():
    """`first_at` cerca del borde del holdout no debe devolver un tick cuyo
    t caiga dentro de [AVA_HOLDOUT_INI, AVA_HOLDOUT_FIN)."""
    calib = _calib_tipica(HORAS_VENTANA_TEST)
    ticks = AvaTicks(calib, "mediana", HORAS_VENTANA_TEST)
    r = ticks.first_at(AVA_HOLDOUT_INI)
    if r is not None:
        t, _, _ = r
        assert not (AVA_HOLDOUT_INI <= t < AVA_HOLDOUT_FIN)


# --------------------------------------------------------------------- exclusiones
def test_filter_exclusiones_descarta_barras_en_intervalo():
    bars = [{"t": 100.0}, {"t": 150.0}, {"t": 200.0}, {"t": 300.0}]
    intervalos = [(140.0, 210.0)]
    out = filter_exclusiones(bars, intervalos)
    assert [b["t"] for b in out] == [100.0, 300.0]


def test_filter_exclusiones_no_muta_entrada():
    bars = [{"t": 100.0}, {"t": 150.0}]
    original = [dict(b) for b in bars]
    filter_exclusiones(bars, [(140.0, 210.0)])
    assert bars == original


def test_filter_exclusiones_sin_intervalos_es_identidad():
    bars = [{"t": 100.0}, {"t": 150.0}]
    out = filter_exclusiones(bars, [])
    assert out == bars
    assert out is not bars


def test_cargar_exclusiones_falla_duro_si_falta_fichero(tmp_path):
    with pytest.raises(FileNotFoundError):
        cargar_exclusiones(tmp_path / "no-existe.json")


def test_cargar_exclusiones_falla_duro_si_falta_clave(tmp_path):
    import json
    p = tmp_path / "malo.json"
    p.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(KeyError):
        cargar_exclusiones(p)


# --------------------------------------------------------------------- cobertura
def test_cobertura_mensual_mes_sin_exclusiones_100pct():
    bars_ventana = [{"t": float(i)} for i in range(10)]
    # ym_of usa utcfromtimestamp -- epochs pequenos caen todos en 1970-01
    cobertura = cobertura_mensual(bars_ventana, bars_ventana)
    assert len(cobertura) == 1
    (mes, datos), = cobertura.items()
    assert datos["n_barras_ventana"] == 10
    assert datos["n_barras_tras_exclusiones"] == 10
    assert datos["cobertura_pct"] == 100.0


def test_cobertura_mensual_mes_mutilado_baja_del_100pct():
    bars_ventana = [{"t": float(i)} for i in range(10)]
    bars_final = bars_ventana[:7]
    cobertura = cobertura_mensual(bars_ventana, bars_final)
    (mes, datos), = cobertura.items()
    assert datos["n_barras_ventana"] == 10
    assert datos["n_barras_tras_exclusiones"] == 7
    assert datos["cobertura_pct"] == 70.0
