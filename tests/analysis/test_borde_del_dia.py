"""tests/analysis/test_borde_del_dia.py -- T0.7-M-B1, brief borde del dia.

Spec: research/fases/F0-preparacion/02-specs/T0.7-M-B1-brief-borde-del-dia.md

Solo prueba las funciones puras de
scripts/analysis/realtick_bt/faulty/borde_del_dia.py sobre fixtures
sinteticas en memoria. No lee ningun parquet/csv real ni pega I/O (eso lo
hace main(), que se corre una sola vez fuera de pytest).

R1-bis / paralelismo: este fichero NO importa ciclos.py, estado_por_barra.py,
llamador.py, comparador.py ni config_faulty.py.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scripts.analysis.realtick_bt.faulty import borde_del_dia as M


# --------------------------------------------------- identificar_cluster_borde_dia
def _df_cola(rows):
    """rows: list of dicts con al menos position_id, signo, delta_t_open_s."""
    return pd.DataFrame(rows)


def test_identificar_cluster_incluye_principal_y_fin_de_semana():
    rows = [
        {"position_id": 1, "signo": "REPLICA_TEMPRANO", "delta_t_open_s": -179395.71},  # max abs -> fin_de_semana
        {"position_id": 2, "signo": "REPLICA_TEMPRANO", "delta_t_open_s": -6369.73},    # principal
        {"position_id": 3, "signo": "REPLICA_TEMPRANO", "delta_t_open_s": -6286.40},    # principal (borde inferior 6000-6500)
        {"position_id": 4, "signo": "REPLICA_TARDE", "delta_t_open_s": 66564.0},        # ni uno ni otro
        {"position_id": 5, "signo": "REPLICA_TEMPRANO", "delta_t_open_s": -60.77},      # fuera de rango (61 s)
    ]
    df = _df_cola(rows)
    out = M.identificar_cluster_borde_dia(df)
    assert set(out["position_id"]) == {1, 2, 3}
    grupo_por_id = dict(zip(out["position_id"], out["grupo"]))
    assert grupo_por_id[1] == "fin_de_semana"
    assert grupo_por_id[2] == "principal"
    assert grupo_por_id[3] == "principal"


def test_identificar_cluster_fila_0_es_siempre_fin_de_semana_por_construccion():
    """censo_cola_t_open.csv viene pre-ordenado por -abs(delta): la fila 0
    ES la divergencia maxima por construccion, sin tener que recalcular el
    maximo."""
    rows = [
        {"position_id": 99, "signo": "REPLICA_TEMPRANO", "delta_t_open_s": -179395.71},
        {"position_id": 2, "signo": "REPLICA_TEMPRANO", "delta_t_open_s": -6369.73},
    ]
    df = _df_cola(rows)
    out = M.identificar_cluster_borde_dia(df)
    fila_fds = out[out["grupo"] == "fin_de_semana"]
    assert list(fila_fds["position_id"]) == [99]


# --------------------------------------------------------------- segundo_set_mask
def test_segundo_set_mask_bordes():
    T = 1000
    t_arr = np.array([T - 0.001, T + 0.0, T + 0.999, T + 1.0])
    mask = M.segundo_set_mask(t_arr, T)
    assert list(mask) == [False, True, True, False]


# ------------------------------------------------------------------ tick_vigente
def test_tick_vigente_ultimo_anterior_o_igual():
    T = 1000
    t_arr = np.array([990.0, 999.0, 1005.0])
    q_arr = np.array([10.0, 20.0, 30.0])
    q, idx = M.tick_vigente(t_arr, q_arr, T)
    assert idx == 1
    assert q == 20.0


def test_tick_vigente_none_si_no_hay_tick_anterior():
    T = 1000
    t_arr = np.array([1001.0, 1002.0])
    q_arr = np.array([10.0, 20.0])
    q, idx = M.tick_vigente(t_arr, q_arr, T)
    assert q is None and idx is None


# -------------------------------------------------------------- primer_tick_desde
def test_primer_tick_desde_replica_first_at_t_sec():
    """Replica EXACTA de la semantica de Ticks.first_at en backtest.py:130-139
    -- primer tick con t >= T, NO el ultimo <= T (eso es tick_vigente)."""
    T = 1000
    t_arr = np.array([990.0, 999.0, 1005.0, 1010.0])
    bid_arr = np.array([1.0, 2.0, 3.0, 4.0])
    ask_arr = np.array([1.5, 2.5, 3.5, 4.5])
    r = M.primer_tick_desde(t_arr, bid_arr, ask_arr, T)
    assert r is not None
    t_tick, bid, ask = r
    assert t_tick == 1005.0
    assert bid == 3.0 and ask == 3.5


def test_primer_tick_desde_none_si_no_hay_tick_futuro():
    T = 1000
    t_arr = np.array([990.0, 999.0])
    bid_arr = np.array([1.0, 2.0])
    ask_arr = np.array([1.5, 2.5])
    assert M.primer_tick_desde(t_arr, bid_arr, ask_arr, T) is None


def test_primer_tick_desde_tick_exacto_en_T_cuenta():
    T = 1000
    t_arr = np.array([990.0, 1000.0, 1010.0])
    bid_arr = np.array([1.0, 2.0, 3.0])
    ask_arr = np.array([1.5, 2.5, 3.5])
    r = M.primer_tick_desde(t_arr, bid_arr, ask_arr, T)
    assert r[0] == 1000.0


# --------------------------------------------------------- analizar_spread_apertura
def test_analizar_spread_apertura_detecta_delay_al_futuro():
    """Caso disenado como el cluster real: segundo T vacio (hueco de
    mantenimiento), tick vigente ANTES del hueco (spread 0.60), y el primer
    tick DESPUES del hueco tiene spread 0.50 (pasa el gate) pero llega con
    retraso -- ese retraso es el dato clave de la pregunta 1."""
    T = 1000
    t_arr = np.array([500.0, 501.0, 4600.0, 4601.0])  # hueco entre 501 y 4600
    bid_arr = np.array([100.00, 100.00, 200.00, 200.00])
    ask_arr = np.array([100.60, 100.60, 200.50, 200.50])  # spread 0.60 antes, 0.50 despues
    r = M.analizar_spread_apertura(t_arr, bid_arr, ask_arr, T, umbral=0.50)
    assert r["n_ticks_segundo"] == 0
    assert r["spread_vigente"] == pytest.approx(0.60)
    assert r["spread_vigente_supera_umbral"] is True
    assert r["spread_primer_tick_futuro"] == pytest.approx(0.50)
    assert r["spread_primer_tick_futuro_supera_umbral"] is False
    assert r["delay_primer_tick_futuro_s"] == pytest.approx(3600.0)


def test_analizar_spread_apertura_con_ticks_en_el_segundo():
    T = 1000
    t_arr = np.array([1000.1, 1000.5, 1000.9])
    bid_arr = np.array([10.0, 10.0, 10.0])
    ask_arr = np.array([10.5, 10.6, 10.7])
    r = M.analizar_spread_apertura(t_arr, bid_arr, ask_arr, T, umbral=0.50)
    assert r["n_ticks_segundo"] == 3
    assert r["spread_min_segundo"] == pytest.approx(0.5)
    assert r["spread_max_segundo"] == pytest.approx(0.7)
    assert r["spread_mediana_segundo"] == pytest.approx(0.6)


# ------------------------------------------------------------- identificar_barra
def test_identificar_barra_decision_encuentra_la_ultima_cerrada():
    """Misma formula que ciclos.py::correr_ciclos paso 1: la ultima barra
    CERRADA como de T (bar_close <= T), no la que esta abierta en T. Con
    bar_times=[0,900,1800,2700] (cierres 900,1800,2700,3600) y T=2000, la
    barra 1800-2700 AUN no cerro (cierra a 2700 > 2000): la vigente es la
    900-1800 (idx=1)."""
    bar_times = np.array([0.0, 900.0, 1800.0, 2700.0])
    T = 2000.0
    r = M.identificar_barra_decision(bar_times, T, bar_sec=900)
    assert r["bar_idx"] == 1
    assert r["bar_open_epoch"] == 900.0
    assert r["bar_close_epoch"] == 1800.0


def test_identificar_barra_decision_contigua_true():
    bar_times = np.array([0.0, 900.0, 1800.0])
    r = M.identificar_barra_decision(bar_times, 950.0, bar_sec=900)
    assert r["bar_idx"] == 0
    assert r["siguiente_bar_contigua"] is True
    assert r["gap_siguiente_bar_s"] == pytest.approx(0.0)


def test_identificar_barra_decision_detecta_hueco_de_rollover():
    """Barra 0-900 (cierra 900), pero la SIGUIENTE barra del parquet
    empieza en 3600 en vez de 900: hueco de 2700 s -- el patron exacto del
    rollover 17:00-17:45 en XAUUSD_M15.parquet."""
    bar_times = np.array([0.0, 3600.0])
    r = M.identificar_barra_decision(bar_times, 950.0, bar_sec=900)
    assert r["bar_idx"] == 0
    assert r["siguiente_bar_contigua"] is False
    assert r["gap_siguiente_bar_s"] == pytest.approx(2700.0)


def test_identificar_barra_decision_none_si_T_antes_de_toda_barra():
    bar_times = np.array([1000.0, 1900.0])
    r = M.identificar_barra_decision(bar_times, 500.0, bar_sec=900)
    assert r["bar_idx"] is None


def test_identificar_barra_decision_ultima_barra_contigua_no_evaluable():
    bar_times = np.array([0.0, 900.0])
    r = M.identificar_barra_decision(bar_times, 1800.0, bar_sec=900)  # >= cierre de la ultima barra
    assert r["bar_idx"] == 1
    assert r["siguiente_bar_contigua"] is None  # no hay barra siguiente: no evaluable
    assert r["gap_siguiente_bar_s"] is None


# --------------------------------------------------------------- evento_en_instante
def test_evento_en_instante_encuentra_el_mas_cercano_dentro_de_tol():
    df = pd.DataFrame([
        {"strategy_id": "A", "t": 100.0, "tipo": "NOOP", "detalle": "{}"},
        {"strategy_id": "A", "t": 100.4, "tipo": "SL_CLAMPED", "detalle": "{}"},
        {"strategy_id": "B", "t": 100.0, "tipo": "OPEN", "detalle": "{}"},
    ])
    r = M.evento_en_instante(df, "A", 100.5, tol=1.0)
    assert r is not None
    assert r["tipo"] == "SL_CLAMPED"
    assert r["dist_s"] == pytest.approx(0.1)


def test_evento_en_instante_none_si_nada_dentro_de_tol():
    df = pd.DataFrame([
        {"strategy_id": "A", "t": 100.0, "tipo": "NOOP", "detalle": "{}"},
    ])
    r = M.evento_en_instante(df, "A", 500.0, tol=1.0)
    assert r is None


def test_evento_en_instante_filtra_por_estrategia():
    df = pd.DataFrame([
        {"strategy_id": "B", "t": 100.0, "tipo": "OPEN", "detalle": "{}"},
    ])
    r = M.evento_en_instante(df, "A", 100.0, tol=1.0)
    assert r is None


# --------------------------------------------------- extraer_desired_sl_en_intervalo
def test_extraer_desired_sl_en_intervalo_parsea_json_y_filtra():
    df = pd.DataFrame([
        {"strategy_id": "A", "t": 100.0, "tipo": "OPEN_SKIPPED_SL_CROSSED",
         "detalle": json.dumps({"ficha": "F1", "desired_sl": 4032.0})},
        {"strategy_id": "A", "t": 101.0, "tipo": "OPEN_SKIPPED_SL_CROSSED",
         "detalle": json.dumps({"ficha": "F1", "desired_sl": 4033.5})},
        {"strategy_id": "A", "t": 102.0, "tipo": "NOOP", "detalle": "{}"},
        {"strategy_id": "B", "t": 100.5, "tipo": "OPEN_SKIPPED_SL_CROSSED",
         "detalle": json.dumps({"ficha": "F1", "desired_sl": 9999.0})},
    ])
    vals = M.extraer_desired_sl_en_intervalo(df, "A", 100.0, 102.0)
    assert vals == [4032.0, 4033.5]


def test_extraer_desired_sl_en_intervalo_vacio_si_ninguno():
    df = pd.DataFrame([
        {"strategy_id": "A", "t": 100.0, "tipo": "NOOP", "detalle": "{}"},
    ])
    vals = M.extraer_desired_sl_en_intervalo(df, "A", 100.0, 200.0)
    assert vals == []


# ---------------------------------------------------------- contar_ticks_por_minuto
def test_contar_ticks_por_minuto_cuenta_por_bin_de_60s():
    t0 = 1000.0
    t1 = 1000.0 + 3 * 60.0  # 3 minutos
    t_arr = np.array([1000.5, 1000.9, 1061.0, 1150.0, 1200.0, 5000.0])  # 1200 y 5000 fuera de [t0,t1)
    minutos, conteos = M.contar_ticks_por_minuto(t_arr, t0, t1)
    assert len(minutos) == 3
    assert list(conteos) == [2, 1, 1]


def test_contar_ticks_por_minuto_bin_vacio_es_cero_no_ausente():
    t0 = 0.0
    t1 = 120.0
    t_arr = np.array([5.0])  # solo en el primer minuto; el segundo debe salir 0
    minutos, conteos = M.contar_ticks_por_minuto(t_arr, t0, t1)
    assert list(conteos) == [1, 0]


# ------------------------------------------------------------------ pandas NaN gotcha
def test_extraer_desired_sl_ignora_detalle_no_parseable_sin_reventar():
    df = pd.DataFrame([
        {"strategy_id": "A", "t": 100.0, "tipo": "OPEN_SKIPPED_SL_CROSSED", "detalle": None},
    ])
    # pandas puede traer NaN en vez de None en la columna detalle; no debe
    # reventar, y no debe colarse como valor evaluable.
    vals = M.extraer_desired_sl_en_intervalo(df, "A", 100.0, 100.0)
    assert vals == []


# -------------------------------------------------------- citas de codigo (file:line)
def test_cita_gate_spread_replica_ciclos_py_literal():
    """El umbral literal del gate de spread de la replica, citado con
    file:line exacto (pregunta 2)."""
    cita = M.CITA_GATE_SPREAD_REPLICA
    assert cita["file"] == "scripts/analysis/realtick_bt/faulty/ciclos.py"
    assert cita["linea_default"] == 127
    assert "max_spread_open: float = 0.50" in cita["texto_linea_default"]
    assert cita["linea_condicion"] == "225-226"
    assert "spread > max_spread_open + 1e-6" in cita["texto_condicion"]


def test_cita_gate_spread_replica_verificada_contra_el_fichero_real():
    """No basta con que la cita este bien escrita en el modulo: se verifica
    leyendo ciclos.py de verdad, en las lineas citadas."""
    ruta = M._REPO_ROOT / "scripts/analysis/realtick_bt/faulty/ciclos.py"
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert "max_spread_open: float = 0.50" in lineas[126]  # linea 127, indice 126
    assert "spread > max_spread_open + 1e-6" in lineas[225]  # linea 226, indice 225


def test_cita_gate_spread_harness_vivo_backtest_py_literal():
    cita = M.CITA_GATE_SPREAD_HARNESS
    assert cita["file"] == "scripts/analysis/realtick_bt/backtest.py"
    assert cita["lineas"] == "349-359"
    assert "abs(sp - 0.5) <= 0.05" in cita["texto"]


def test_cita_gate_spread_harness_verificada_contra_el_fichero_real():
    # T0.7-M-E (backtest.py:130-149, commit ver progreso.md) inserto 18
    # lineas antes de resolve() al acotar Ticks.first_at con tolerance_s;
    # la linea citada se desplazo de 358 a 376 (indice 357 -> 375).
    ruta = M._REPO_ROOT / "scripts/analysis/realtick_bt/backtest.py"
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert "abs(sp - 0.5) <= 0.05" in lineas[375]  # linea 376, indice 375


def test_cita_no_modelado_borde_dia_llamador_py():
    """Pregunta 3: la replica NO modela el corte de mantenimiento ni el fin
    de semana -- cita literal de llamador.py."""
    cita = M.CITA_NO_MODELADO_BORDE_DIA
    assert cita["file"] == "scripts/analysis/realtick_bt/faulty/llamador.py"
    assert cita["lineas"] == "474-478"
    assert "NO reciben" in cita["texto"] or "NO recib" in cita["texto"]


def test_cita_no_modelado_verificada_contra_el_fichero_real():
    ruta = M._REPO_ROOT / "scripts/analysis/realtick_bt/faulty/llamador.py"
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    bloque = "\n".join(lineas[473:478])  # lineas 474-478, indices 473-477
    assert "fin de semana" in bloque
    assert "NO recib" in bloque


def test_cita_t_open_usa_instante_de_ciclo_no_tick_encontrado():
    """El hallazgo mecanico central: ciclos.py guarda t_open=t (el instante
    del bucle), no el timestamp del tick que primer_at() encontro -- eso es
    lo que hace que la apertura quede fechada a las 16:59 aunque el tick
    real usado sea ~1h despues."""
    cita = M.CITA_T_OPEN_ES_INSTANTE_DE_CICLO
    assert cita["file"] == "scripts/analysis/realtick_bt/faulty/ciclos.py"
    assert cita["linea_first_at"] == 180
    assert cita["linea_t_open"] == 254


def test_cita_t_open_verificada_contra_el_fichero_real():
    ruta = M._REPO_ROOT / "scripts/analysis/realtick_bt/faulty/ciclos.py"
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert "ticks.first_at(t)" in lineas[179]        # linea 180
    assert '"t_open": t,' in lineas[253]              # linea 254
