"""tests/analysis/test_fill_vs_cotizacion.py -- Brief H (F0-A6-FILL-0001):
falsacion del fill del broker. Mide si el precio_open/precio_close real de
cada posicion 902 existe como cotizacion en el lago de ticks Capitaria, en
el segundo en que MT5 dice que ocurrio el llenado.

Spec: .superpowers/sdd/2026-08-13-replica-motor-faulty-spec/h-fill-broker-brief.md

Todos los tests aqui usan fixtures sinteticas en memoria -- NUNCA el lago
real de ticks ni verdad_terreno_902.csv (eso lo hace el script de medicion,
que se corre una sola vez, fuera de pytest).

R1-bis / paralelismo: este fichero no importa ciclos.py, llamador.py,
comparador.py ni config_faulty.py (otro agente puede estar leyendolos en
paralelo sobre los mismos ficheros).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.analysis.realtick_bt.faulty import fill_vs_cotizacion as F


# ----------------------------------------------------- (a) conjunto del segundo
def test_segundo_set_incluye_T000_y_T999_excluye_Tmas1_000():
    """S = { ticks con floor(t_msc/1000) == T }: un tick justo en T.000 y
    otro en T.999 deben quedar dentro; uno en (T+1).000 debe quedar fuera."""
    T = 1785178410
    t_arr = np.array([
        T - 0.001,   # fuera: pertenece al segundo anterior
        T + 0.000,   # dentro (borde inferior)
        T + 0.500,
        T + 0.999,   # dentro (borde superior)
        T + 1.000,   # fuera: pertenece al segundo siguiente
    ])
    mask = F.segundo_set_mask(t_arr, T)
    assert list(mask) == [False, True, True, True, False]


def test_segundo_set_vacio_cuando_no_hay_ticks_en_ese_segundo():
    T = 1785178410
    t_arr = np.array([T - 5.0, T + 5.0])
    mask = F.segundo_set_mask(t_arr, T)
    assert mask.sum() == 0


# ------------------------------------------------------------ (b) tick vigente
def test_tick_vigente_toma_ultimo_anterior_cuando_T_no_tiene_ticks():
    """Si el segundo T no tiene ningun tick, el tick vigente es el ultimo
    tick anterior a T aunque sea de otro segundo."""
    T = 1785178410
    t_arr = np.array([T - 100.0, T - 3.2, T + 4.0, T + 10.0])
    q_arr = np.array([10.0, 20.0, 30.0, 40.0])
    q, idx = F.tick_vigente(t_arr, q_arr, T)
    assert idx == 1
    assert q == 20.0


def test_tick_vigente_none_cuando_no_hay_ningun_tick_anterior():
    """Si no hay ningun tick con t <= T, se declara no evaluable: None,
    nunca un valor inventado."""
    T = 1785178410
    t_arr = np.array([T + 1.0, T + 2.0])
    q_arr = np.array([10.0, 20.0])
    q, idx = F.tick_vigente(t_arr, q_arr, T)
    assert q is None
    assert idx is None


def test_tick_vigente_toma_el_tick_exactamente_en_T():
    T = 1785178410
    t_arr = np.array([T - 1.0, T + 0.0, T + 0.5])
    q_arr = np.array([10.0, 20.0, 30.0])
    q, idx = F.tick_vigente(t_arr, q_arr, T)
    assert idx == 1
    assert q == 20.0


# --------------------------------------------------------- (d) lado / convencion
def test_lado_open_buy_es_ask_y_sell_es_bid():
    assert F.lado_para_evento("BUY", "OPEN") == "ask"
    assert F.lado_para_evento("SELL", "OPEN") == "bid"


def test_lado_close_invierte_respecto_a_open():
    """La convencion se invierte en el cierre: BUY cierra al bid,
    SELL cierra al ask."""
    assert F.lado_para_evento("BUY", "CLOSE") == "bid"
    assert F.lado_para_evento("SELL", "CLOSE") == "ask"


def test_lado_opuesto_invierte_bid_ask():
    assert F.lado_opuesto("bid") == "ask"
    assert F.lado_opuesto("ask") == "bid"


# --------------------------------------------------------- comparacion 2 decimales
def test_hit_exacto_compara_a_2_decimales_no_con_igualdad_float_cruda():
    """Caso disenado para fallar con `==` sobre float crudo por error de
    representacion binaria, pero acertar con round(x, 2)."""
    precio_real = 4074.16
    # 4074.16 - 0.0000000000009 no es == 4074.16 en float crudo, pero
    # round(.., 2) de ambos es 4074.16.
    q_arr = np.array([4074.159999999999, 4074.10, 4074.05])
    assert not np.any(q_arr == precio_real)  # confirma que == falla
    assert F.hit_exacto(precio_real, q_arr) is True


def test_hit_exacto_false_cuando_ningun_valor_redondeado_coincide():
    precio_real = 4074.16
    q_arr = np.array([4074.20, 4074.30])
    assert F.hit_exacto(precio_real, q_arr) is False


def test_hit_exacto_segundo_vacio_es_false_no_error():
    precio_real = 4074.16
    q_arr = np.array([])
    assert F.hit_exacto(precio_real, q_arr) is False


# ----------------------------------------------------------------- integracion
def test_medir_evento_calcula_hit_exacto_dentro_rango_y_dist_min():
    """Prueba de integracion minima de medir_evento(): un BUY open con
    precio real que SI esta exactamente en el conjunto del segundo (via
    el lado ask)."""
    T = 1785178410
    t_arr = np.array([T + 0.1, T + 0.5, T + 0.9])
    bid_arr = np.array([4074.00, 4074.02, 4074.04])
    ask_arr = np.array([4074.10, 4074.16, 4074.20])
    r = F.medir_evento(
        t_arr=t_arr, bid_arr=bid_arr, ask_arr=ask_arr,
        side="BUY", evento="OPEN", T=T, P=4074.16,
    )
    assert r["n_ticks_segundo"] == 3
    assert r["hit_exacto_segundo"] is True
    assert r["dentro_rango_segundo"] is True
    assert r["dist_min_segundo"] == pytest.approx(0.0)
    assert r["q_min_segundo"] == pytest.approx(4074.10)
    assert r["q_max_segundo"] == pytest.approx(4074.20)
    # control lado opuesto: el bid del segundo es [4074.00, 4074.04],
    # 4074.16 no esta ahi.
    assert r["hit_exacto_segundo_lado_opuesto"] is False


# ------------------------------------------ None -> NaN de pandas en percentiles
def test_percentiles_no_cuenta_nan_de_pandas_como_evaluable():
    """Al pasar una columna float de un DataFrame por .tolist(), pandas ya
    convirtio los None en NaN (nunca quedan como None). Un filtro que solo
    revisa `v is not None` no detecta el NaN: se cuela en el array de
    percentiles, infecta p50/p90/max (quedan en NaN) e infla n_evaluable.

    Este test habria fallado con ese filtro (ver reproduccion manual: con
    `[v for v in valores if v is not None]` sobre esta misma columna,
    n_evaluable sale 5 en vez de 3, y p50/p90/max salen NaN)."""
    col = pd.Series([0.0, None, 2.0, None, 4.0], dtype=float)
    # confirma la premisa: pandas ya convirtio los None en NaN, no quedan
    # como None -- por eso `is not None` no basta.
    assert col.isna().sum() == 2
    assert all(v is not None for v in col.tolist())

    agg = F._percentiles(col.tolist())

    assert agg["n_evaluable"] == 3
    assert agg["p50"] == pytest.approx(2.0)
    assert agg["p90"] == pytest.approx(3.6)
    assert agg["max"] == pytest.approx(4.0)


def test_agregar_subset_no_cuenta_eventos_sin_ticks_como_dist_min_cero():
    """17 eventos reales tienen n_ticks_segundo == 0 -> dist_min_segundo es
    legitimamente vacio (None, que pandas vuelve NaN). Deben quedar FUERA
    del percentil de dist_min_segundo, nunca convertirse en 0.0 ni en un
    valor evaluable."""
    filas = []
    for i in range(3):
        filas.append({
            "n_ticks_segundo": 5, "dist_min_segundo": 0.0,
            "n_ticks_1": 5, "dist_min_1": 0.0, "hit_exacto_1": True, "dentro_rango_1": True,
            "n_ticks_2": 5, "dist_min_2": 0.0, "hit_exacto_2": True, "dentro_rango_2": True,
            "n_ticks_5": 5, "dist_min_5": 0.0, "hit_exacto_5": True, "dentro_rango_5": True,
            "n_ticks_30": 5, "dist_min_30": 0.0, "hit_exacto_30": True, "dentro_rango_30": True,
            "hit_exacto_segundo": True, "dentro_rango_segundo": True,
            "hit_exacto_segundo_lado_opuesto": False,
            "q_vigente": 4074.10, "hit_exacto_vigente": True,
        })
    # un evento sin ningun tick en su segundo: dist_min_segundo no evaluable
    filas.append({
        "n_ticks_segundo": 0, "dist_min_segundo": None,
        "n_ticks_1": 0, "dist_min_1": None, "hit_exacto_1": False, "dentro_rango_1": False,
        "n_ticks_2": 0, "dist_min_2": None, "hit_exacto_2": False, "dentro_rango_2": False,
        "n_ticks_5": 5, "dist_min_5": 0.02, "hit_exacto_5": False, "dentro_rango_5": True,
        "n_ticks_30": 5, "dist_min_30": 0.02, "hit_exacto_30": False, "dentro_rango_30": True,
        "hit_exacto_segundo": False, "dentro_rango_segundo": False,
        "hit_exacto_segundo_lado_opuesto": False,
        "q_vigente": 4074.10, "hit_exacto_vigente": False,
    })
    df = pd.DataFrame(filas)
    agg = F.agregar_subset(df)

    assert agg["n_eventos"] == 4
    assert agg["n_ticks_segundo_cero"] == 1
    # el percentil de dist_min_segundo solo ve los 3 eventos con ticks,
    # nunca los 4 (el no-evaluable no se cuela como 0.0)
    assert agg["dist_min_segundo"]["n_evaluable"] == 3
    assert agg["dist_min_segundo"]["p50"] == pytest.approx(0.0)
    assert agg["dist_min_segundo"]["max"] == pytest.approx(0.0)


def test_medir_evento_declara_no_evaluable_sin_ticks_en_el_segundo():
    """Si el evento no tiene ticks en su segundo, n_ticks_segundo = 0 y
    hit/dentro_rango/dist_min quedan como no evaluables (None), nunca
    inventados."""
    T = 1785178410
    t_arr = np.array([T - 500.0, T + 500.0])
    bid_arr = np.array([4074.00, 4075.00])
    ask_arr = np.array([4074.10, 4075.10])
    r = F.medir_evento(
        t_arr=t_arr, bid_arr=bid_arr, ask_arr=ask_arr,
        side="BUY", evento="OPEN", T=T, P=4074.16,
    )
    assert r["n_ticks_segundo"] == 0
    assert r["hit_exacto_segundo"] is False
    assert r["dentro_rango_segundo"] is False
    assert r["dist_min_segundo"] is None
    assert r["q_min_segundo"] is None
    assert r["q_max_segundo"] is None
