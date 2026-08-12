"""Tests de `scripts/research/cost_overlay.py` -- T0.6 mod #10, Paso 2a,
Artefacto 3.

Por que existe. D-21 es vinculante: los backtests sobre AVA usan precios de
AVA con un modelo de costes calibrado sobre Capitaria; el spread nativo de
AVA no se usa para veredictos. El riesgo concreto que estos tests existen
para bloquear: que alguien invierta el sentido del overlay (que ESTRECHE en
vez de ENSANCHAR) -- ese error haria que AVA saliera aun mejor, exactamente
el fallo que D-21 existe para impedir.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pytest

from scripts.research.cost_overlay import (
    AVA_HOLDOUT_FIN,
    AVA_HOLDOUT_INI,
    CAPITARIA_HOLDOUT_FIN,
    CAPITARIA_HOLDOUT_INI,
    aplicar_overlay,
    assert_fuera_holdout_ava,
    assert_fuera_holdout_capitaria,
    cargar_calibracion,
    overlay_arrays,
    spread_calibrado,
)


def _calib_tipica() -> dict:
    """Calibracion sintetica tipica de Capitaria (~0.50-0.60), con los tres
    modos definidos para las 8 horas de la ventana NY."""
    por_hora = {}
    for h in (18, 19, 20, 21, 22, 23, 0, 1):
        por_hora[str(h)] = {"mediana": 0.55, "media": 0.56, "p75": 0.60, "n": 1000}
    return {"por_hora": por_hora}


def _dt_ny(hour: int) -> datetime:
    return datetime(2026, 6, 15, hour, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------- 1. mid
def test_mid_se_conserva_y_anchura_pasa_a_ser_la_calibrada():
    calib = _calib_tipica()
    casos = [
        (2500.10, 2500.44),  # spread nativo AVA ~0.34
        (1800.00, 1800.45),  # spread nativo AVA ~0.45
        (5000.00, 5000.40),
    ]
    for bid, ask in casos:
        mid_original = (bid + ask) / 2.0
        bid2, ask2 = aplicar_overlay(bid, ask, _dt_ny(20), calib, modo="mediana")
        mid_nuevo = (bid2 + ask2) / 2.0
        assert mid_nuevo == pytest.approx(mid_original, abs=1e-9)
        assert (ask2 - bid2) == pytest.approx(0.55, abs=1e-9)  # anchura calibrada, no la nativa


# ------------------------------------------------------------- 2. SIEMPRE ENSANCHA
@pytest.mark.parametrize("bid,ask", [
    (2500.10, 2500.44),  # spread 0.34
    (1800.00, 1800.45),  # spread 0.45
    (3200.00, 3200.40),  # spread 0.40
])
def test_overlay_ensancha_nunca_estrecha(bid, ask):
    """El test que se pone rojo si alguien invierte el sentido del overlay.
    Con un tick AVA tipico (spread 0.34-0.45) y una calibracion tipica de
    Capitaria (~0.50-0.60), la anchura resultante DEBE ser mayor que la
    nativa. Si alguien reescribe aplicar_overlay para tomar min(s_ava,
    s_calibrado) o para promediar en vez de sustituir, este test falla."""
    calib = _calib_tipica()
    spread_nativo = ask - bid
    bid2, ask2 = aplicar_overlay(bid, ask, _dt_ny(20), calib, modo="mediana")
    spread_resultante = ask2 - bid2
    assert spread_resultante > spread_nativo


def test_overlay_ensancha_en_los_tres_modos():
    calib = _calib_tipica()
    bid, ask = 2500.10, 2500.44  # spread nativo 0.34
    for modo in ("mediana", "media", "p75"):
        bid2, ask2 = aplicar_overlay(bid, ask, _dt_ny(20), calib, modo=modo)
        assert (ask2 - bid2) > (ask - bid)


# ------------------------------------------------------- 3. calibracion ausente
def test_cargar_calibracion_falla_duro_si_no_existe(tmp_path):
    with pytest.raises(FileNotFoundError):
        cargar_calibracion(tmp_path / "no_existe.json")


def test_cargar_calibracion_falla_duro_si_falta_por_hora(tmp_path):
    p = tmp_path / "calib.json"
    p.write_text(json.dumps({"algo": 1}), encoding="utf-8")
    with pytest.raises(KeyError):
        cargar_calibracion(p)


def test_cargar_calibracion_falla_duro_si_falta_una_hora(tmp_path):
    calib = _calib_tipica()
    del calib["por_hora"]["23"]  # falta una de las 8 horas
    p = tmp_path / "calib.json"
    p.write_text(json.dumps(calib), encoding="utf-8")
    with pytest.raises(KeyError):
        cargar_calibracion(p)


def test_cargar_calibracion_falla_duro_si_falta_un_modo(tmp_path):
    calib = _calib_tipica()
    del calib["por_hora"]["18"]["p75"]
    p = tmp_path / "calib.json"
    p.write_text(json.dumps(calib), encoding="utf-8")
    with pytest.raises(KeyError):
        cargar_calibracion(p)


def test_cargar_calibracion_ok_devuelve_dict(tmp_path):
    calib = _calib_tipica()
    p = tmp_path / "calib.json"
    p.write_text(json.dumps(calib), encoding="utf-8")
    cargado = cargar_calibracion(p)
    assert cargado["por_hora"]["18"]["mediana"] == 0.55


def test_spread_calibrado_sin_default_silencioso_hora_fuera_ventana():
    calib = _calib_tipica()
    with pytest.raises(KeyError):
        spread_calibrado(_dt_ny(10), calib, modo="mediana")  # 10h no esta en la ventana NY


def test_spread_calibrado_modo_invalido_es_error_duro():
    calib = _calib_tipica()
    with pytest.raises(ValueError):
        spread_calibrado(_dt_ny(20), calib, modo="promedio_inventado")


# --------------------------------------------------------------- 4. tres modos
def test_los_tres_modos_devuelven_valores_distintos_y_p75_es_el_mayor():
    calib = _calib_tipica()
    dt = _dt_ny(20)
    s_mediana = spread_calibrado(dt, calib, "mediana")
    s_media = spread_calibrado(dt, calib, "media")
    s_p75 = spread_calibrado(dt, calib, "p75")
    assert len({s_mediana, s_media, s_p75}) == 3
    assert s_p75 >= s_mediana
    assert s_p75 >= s_media


def test_modo_por_defecto_es_mediana():
    calib = _calib_tipica()
    dt = _dt_ny(20)
    bid, ask = 2500.10, 2500.44
    con_default = aplicar_overlay(bid, ask, dt, calib)
    con_mediana_explicita = aplicar_overlay(bid, ask, dt, calib, modo="mediana")
    assert con_default == con_mediana_explicita


# --------------------------------------------------------- 5. overlay_arrays
def test_overlay_arrays_coincide_con_aplicar_overlay_elemento_a_elemento():
    calib = _calib_tipica()
    rng = np.random.default_rng(0)
    n = 200
    horas = rng.choice([18, 19, 20, 21, 22, 23, 0, 1], size=n)
    bids = 2400 + rng.random(n) * 500
    spreads_nativos = 0.30 + rng.random(n) * 0.20  # 0.30 .. 0.50
    asks = bids + spreads_nativos
    dts = [datetime(2026, 6, 15, int(h), 0, 0) for h in horas]

    for modo in ("mediana", "media", "p75"):
        bids2_vec, asks2_vec = overlay_arrays(bids, asks, dts, calib, modo=modo)
        for i in range(n):
            bid2_esc, ask2_esc = aplicar_overlay(bids[i], asks[i], dts[i], calib, modo=modo)
            assert bids2_vec[i] == pytest.approx(bid2_esc, abs=1e-9)
            assert asks2_vec[i] == pytest.approx(ask2_esc, abs=1e-9)


def test_overlay_arrays_falla_duro_si_alguna_hora_fuera_de_ventana():
    calib = _calib_tipica()
    bids = np.array([2500.0, 2500.0])
    asks = np.array([2500.34, 2500.34])
    dts = [datetime(2026, 6, 15, 20, 0, 0), datetime(2026, 6, 15, 10, 0, 0)]  # 10h fuera
    with pytest.raises(KeyError):
        overlay_arrays(bids, asks, dts, calib, modo="mediana")


# ------------------------------------------------------------ 6. guardas holdout
def test_guarda_holdout_capitaria_aborta_si_toca_el_sello():
    with pytest.raises(SystemExit):
        assert_fuera_holdout_capitaria(CAPITARIA_HOLDOUT_INI, CAPITARIA_HOLDOUT_FIN)


def test_guarda_holdout_capitaria_aborta_con_solape_parcial():
    with pytest.raises(SystemExit):
        assert_fuera_holdout_capitaria(CAPITARIA_HOLDOUT_INI - 10_000, CAPITARIA_HOLDOUT_INI + 10)


def test_guarda_holdout_capitaria_no_aborta_fuera_del_sello():
    assert_fuera_holdout_capitaria(CAPITARIA_HOLDOUT_INI - 1_000_000, CAPITARIA_HOLDOUT_INI)
    assert_fuera_holdout_capitaria(CAPITARIA_HOLDOUT_FIN, CAPITARIA_HOLDOUT_FIN + 1_000_000)


def test_guarda_holdout_ava_aborta_si_toca_el_sello():
    with pytest.raises(SystemExit):
        assert_fuera_holdout_ava(AVA_HOLDOUT_INI, AVA_HOLDOUT_FIN)


def test_guarda_holdout_ava_aborta_con_solape_parcial():
    with pytest.raises(SystemExit):
        assert_fuera_holdout_ava(AVA_HOLDOUT_INI - 10_000, AVA_HOLDOUT_INI + 10)


def test_guarda_holdout_ava_no_aborta_fuera_del_sello():
    assert_fuera_holdout_ava(AVA_HOLDOUT_INI - 1_000_000, AVA_HOLDOUT_INI)
    assert_fuera_holdout_ava(AVA_HOLDOUT_FIN, AVA_HOLDOUT_FIN + 1_000_000)


def test_holdouts_son_las_fechas_exactas_de_d31():
    assert datetime.utcfromtimestamp(CAPITARIA_HOLDOUT_INI).strftime("%Y-%m-%d") == "2026-05-12"
    assert datetime.utcfromtimestamp(CAPITARIA_HOLDOUT_FIN).strftime("%Y-%m-%d") == "2026-07-27"
    assert datetime.utcfromtimestamp(AVA_HOLDOUT_INI).strftime("%Y-%m-%d") == "2023-01-01"
    assert datetime.utcfromtimestamp(AVA_HOLDOUT_FIN).strftime("%Y-%m-%d") == "2024-01-01"
