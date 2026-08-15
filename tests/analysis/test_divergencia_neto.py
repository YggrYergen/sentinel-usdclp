"""tests/analysis/test_divergencia_neto.py -- T0.7-M-0: divergencia de NETO
entre réplica y realidad (el criterio de paso monetario de T0.7, nunca antes
computado).

Spec: research/fases/F0-preparacion/02-specs/T0.7-M-0-brief-divergencia-neto.md

Todos los tests aquí usan fixtures sintéticas en memoria -- NUNCA los CSV
reales de `data/analysis/p_cap/` (eso lo hace el script de medición, que se
corre una sola vez, fuera de pytest, igual que `fill_vs_cotizacion.py`).

R1-bis / paralelismo: este fichero no importa `ciclos.py`, `llamador.py`,
`comparador.py`, `config_faulty.py` ni `estado_por_barra.py` -- otro agente
puede estar leyéndolos en paralelo sobre los mismos ficheros.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from scripts.analysis.realtick_bt.faulty import divergencia_neto as D


# --------------------------------------------------------------- dirección
def test_direccion_real_buy_mas1_sell_menos1():
    assert D.direccion_real("BUY") == 1.0
    assert D.direccion_real("SELL") == -1.0


def test_direccion_real_valor_desconocido_es_nan():
    assert math.isnan(D.direccion_real("XYZ"))


def test_direccion_real_vectorizado():
    out = D.direccion_real(pd.Series(["BUY", "SELL", "BUY"]))
    np.testing.assert_array_equal(np.asarray(out), np.array([1.0, -1.0, 1.0]))


def test_direccion_replica_L_mas1_S_menos1():
    assert D.direccion_replica("L") == 1.0
    assert D.direccion_replica("S") == -1.0


def test_direccion_replica_valor_desconocido_es_nan():
    assert math.isnan(D.direccion_replica("?"))


# --------------------------------------------------------------- bruto_usd
def test_bruto_usd_buy_ganador():
    # BUY: precio sube -> gana. 10 puntos * 0.67 lotes * 100 contrato = 670
    r = D.bruto_usd(precio_open=4000.0, precio_close=4010.0, direccion=1.0,
                     volumen=0.67, contrato=100.0)
    assert r == pytest.approx(670.0)


def test_bruto_usd_sell_ganador():
    # SELL: precio baja -> gana. (4000-3990)*-1*... espera: formula =
    # (close-open)*direccion*vol*contrato = (3990-4000)*(-1)*0.67*100 = 670
    r = D.bruto_usd(precio_open=4000.0, precio_close=3990.0, direccion=-1.0,
                     volumen=0.67, contrato=100.0)
    assert r == pytest.approx(670.0)


def test_bruto_usd_usa_valores_por_defecto_del_brief():
    # volumen=0.67 (vivo) y contrato=100.0 (F0-INFRA-0020) por defecto
    r = D.bruto_usd(precio_open=4000.0, precio_close=4001.0, direccion=1.0)
    assert r == pytest.approx((4001.0 - 4000.0) * 1.0 * 0.67 * 100.0)


def test_bruto_usd_vectorizado():
    po = pd.Series([4000.0, 4000.0])
    pc = pd.Series([4010.0, 3990.0])
    di = pd.Series([1.0, -1.0])
    r = D.bruto_usd(po, pc, di, volumen=0.67, contrato=100.0)
    np.testing.assert_allclose(np.asarray(r), [670.0, 670.0])


# --------------------------------------------------------------- tasa implícita
def test_tasa_implicita_division_simple():
    r = D.tasa_implicita(profit_clp=pd.Series([900.0]), bruto_usd_val=pd.Series([1.0]))
    assert r.iloc[0] == pytest.approx(900.0)


def test_tasa_implicita_bruto_cero_es_nan_no_inf_no_cero():
    r = D.tasa_implicita(profit_clp=pd.Series([900.0, -50.0]),
                          bruto_usd_val=pd.Series([0.0, 2.0]))
    assert math.isnan(r.iloc[0])
    assert not math.isinf(r.iloc[0])
    assert r.iloc[1] == pytest.approx(-25.0)


def test_tasa_implicita_asignable_a_dataframe_con_indice_no_contiguo():
    """Regresión: un DataFrame filtrado (p.ej. real = cmp[cmp.tipo_fila ==
    'REAL']) conserva su índice ORIGINAL, no contiguo. Si tasa_implicita
    devuelve una Series con índice nuevo (0..n-1) y el caller hace
    `df['tasa'] = tasa_implicita(...)`, pandas alinea por ÍNDICE, no por
    posición -- introduce NaN en todas las filas donde el índice no
    coincide, silenciosamente. Este test reproduce exactamente ese
    escenario con un índice no contiguo (simula filas intercaladas de
    REPLICA_SIN_PAREJA) y exige que el resultado sea asignable
    posicionalmente sin perder filas."""
    df = pd.DataFrame(
        {"profit_clp": [900.0, -50.0, 300.0], "bruto": [1.0, 2.0, 3.0]},
        index=[0, 3, 7],  # índice no contiguo, como una vista filtrada real
    )
    resultado = D.tasa_implicita(df["profit_clp"].to_numpy(), df["bruto"].to_numpy())
    # debe poder asignarse posicionalmente (via to_numpy) sin introducir NaN
    df["tasa"] = resultado.to_numpy()
    assert df["tasa"].isna().sum() == 0
    assert df["tasa"].tolist() == pytest.approx([900.0, -25.0, 100.0])


# --------------------------------------------------------------- stats_control
def test_stats_control_calcula_percentiles_y_dispersion():
    tasa = pd.Series([900.0, 910.0, 920.0, 930.0, 940.0])
    r = D.stats_control(tasa)
    assert r["n"] == 5
    assert r["p50"] == pytest.approx(920.0)
    assert r["min"] == pytest.approx(900.0)
    assert r["max"] == pytest.approx(940.0)
    assert r["dispersion_relativa"] == pytest.approx(tasa.std() / tasa.mean())


def test_stats_control_usa_pd_isna_no_is_not_none():
    """Bug conocido (gotcha del brief): pandas convierte None a NaN en
    columnas float y un filtro `v is not None` NO lo detecta. Este test
    reproduce exactamente ese escenario: una Series float con NaN colado
    (no None) debe quedar excluida de n y de los percentiles."""
    col = pd.Series([900.0, None, 920.0, None, 940.0], dtype=float)
    assert col.isna().sum() == 2
    assert all(v is not None for v in col.tolist())  # confirma la trampa

    r = D.stats_control(col)
    assert r["n"] == 3
    assert r["p50"] == pytest.approx(920.0)
    assert r["max"] == pytest.approx(940.0)


def test_stats_control_vacio_no_lanza_y_declara_no_evaluable():
    r = D.stats_control(pd.Series([], dtype=float))
    assert r["n"] == 0
    assert r["p50"] is None
    assert r["dispersion_relativa"] is None


# --------------------------------------------------------------- tasa por día
def test_tasa_por_dia_agrupa_por_fecha():
    df = pd.DataFrame({
        "day": ["2026-07-28", "2026-07-28", "2026-07-29"],
        "tasa": [930.0, 934.0, 928.0],
    })
    r = D.tasa_por_dia(df, "day", "tasa")
    assert r["2026-07-28"] == pytest.approx(932.0)
    assert r["2026-07-29"] == pytest.approx(928.0)


def test_mapear_tasa_dia_dia_ausente_es_nan_no_evaluable():
    tabla = pd.Series({"2026-07-28": 932.0})
    dias = pd.Series(["2026-07-28", "2026-09-01"])
    r = D.mapear_tasa_dia(dias, tabla)
    assert r.iloc[0] == pytest.approx(932.0)
    assert math.isnan(r.iloc[1])


# --------------------------------------------------------------- divergencia
def test_divergencia_formula_signo_y_pct():
    r = D.divergencia(neto_real=100.0, neto_replica=110.0, n_real=10, n_replica=10)
    assert r["diff_abs"] == pytest.approx(10.0)
    assert r["divergencia_pct"] == pytest.approx(10.0)
    assert r["neto_real"] == pytest.approx(100.0)
    assert r["neto_replica"] == pytest.approx(110.0)
    assert r["n_real"] == 10
    assert r["n_replica"] == 10


def test_divergencia_usa_valor_absoluto_del_denominador():
    # neto_real negativo: divergencia_pct sigue usando |neto_real| en el
    # denominador (brief: divide por |neto_real|)
    r = D.divergencia(neto_real=-100.0, neto_replica=-90.0, n_real=5, n_replica=5)
    assert r["diff_abs"] == pytest.approx(10.0)
    assert r["divergencia_pct"] == pytest.approx(10.0)


def test_divergencia_neto_real_cero_no_evaluable():
    r = D.divergencia(neto_real=0.0, neto_replica=50.0, n_real=1, n_replica=1)
    assert r["divergencia_pct"] is None


# --------------------------------------------------------------- descomposición
def test_descomponer_reconstruye_el_total_exacto():
    r = D.descomponer(
        term_replica_sin_pareja=-10.0,
        term_real_sin_pareja=20.0,  # bruto de los reales sin pareja (con signo original)
        term_matched_diff=-5.0,
        diff_total=-25.0,  # -10 + (-20) + (-5) = -35... ver siguiente test para signo correcto
    )
    # term2 aplicado en la fórmula es -term_real_sin_pareja (falta en la réplica)
    assert r["term_replica_sin_pareja"] == pytest.approx(-10.0)
    assert r["term_real_sin_pareja_neg"] == pytest.approx(-20.0)
    assert r["term_matched_diff"] == pytest.approx(-5.0)
    assert r["suma_terminos"] == pytest.approx(-35.0)
    assert r["diff_total"] == pytest.approx(-25.0)
    assert r["residuo"] == pytest.approx(-25.0 - (-35.0))


# ------------------------------------------------------- csv posicion a posicion
def test_csv_poblacion_c_excluye_replica_sin_pareja():
    """Regresión: las filas REPLICA_SIN_PAREJA traen `replica_side` poblado
    (es su propio lado), pero NO son un par real-réplica -- por definición
    no tienen contraparte real. `poblacion_c_matched` debe ser False para
    ellas aunque tengan replica_side no nulo; sólo cuentan las REAL con
    réplica emparejada."""
    cmp = pd.DataFrame({
        "tipo_fila": ["REAL", "REAL", "REPLICA_SIN_PAREJA"],
        "position_id": [1.0, 2.0, np.nan],
        "real_side": ["BUY", "SELL", np.nan],
        "real_precio_open": [4000.0, 4000.0, np.nan],
        "real_precio_close": [4010.0, 3990.0, np.nan],
        "real_profit_clp": [900.0, 900.0, np.nan],
        "real_volume": [0.67, 0.67, np.nan],
        "excluido_criterio": [False, False, np.nan],
        "replica_side": ["L", np.nan, "S"],
        "replica_precio_open": [4000.0, np.nan, 4000.0],
        "replica_precio_close": [4010.0, np.nan, 3990.0],
        "replica_t_close_servidor": ["2026-07-28 10:00:00", np.nan, "2026-07-28 11:00:00"],
    })
    rep = pd.DataFrame({
        "strategy_id": ["X"], "side": ["L"], "precio_open": [4000.0],
        "precio_close": [4010.0], "t_close_servidor": ["2026-07-28 10:00:00"],
    })
    tabla_tasa = pd.Series({"2026-07-28": 930.0})

    df = D.construir_csv_posicion_a_posicion(cmp, rep, tabla_tasa)

    # fila 0: REAL con réplica -> matched (a) y (c)
    assert bool(df.loc[0, "poblacion_c_matched"]) is True
    assert bool(df.loc[0, "poblacion_a_emparejada_evaluable"]) is True
    # fila 1: REAL sin réplica -> no matched
    assert bool(df.loc[1, "poblacion_c_matched"]) is False
    assert bool(df.loc[1, "poblacion_a_emparejada_evaluable"]) is False
    # fila 2: REPLICA_SIN_PAREJA -- tiene replica_side pero NO es un par
    assert bool(df.loc[2, "poblacion_c_matched"]) is False
    assert bool(df.loc[2, "poblacion_a_emparejada_evaluable"]) is False
    assert pd.isna(df.loc[2, "diff_bruto_usd"])


def test_descomponer_residuo_cero_cuando_cuadra():
    r = D.descomponer(
        term_replica_sin_pareja=-3110.14,
        term_real_sin_pareja=-2020.72,
        term_matched_diff=-4527.86,
        diff_total=-5617.28,
    )
    # -3110.14 + 2020.72 + -4527.86 = -5617.28
    assert r["residuo"] == pytest.approx(0.0, abs=1e-6)
