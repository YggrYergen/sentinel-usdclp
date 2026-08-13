"""tests/analysis/test_comparador_faulty.py -- Componente E de la réplica del
motor faulty: el COMPARADOR de P-CAP (`comparar_p_cap`), que enfrenta la
corrida de la réplica (Componente D) contra la verdad de terreno de la
cuenta 902.

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md
§5-bis (ADDENDUM 2026-08-13 -- Componente E) y §3-quinquies (tabla de
equivalencia final).

R1-bis: nada aquí modifica A/B/C/D, backtest.py ni sentinel_engine/**. Sólo
se leen artefactos ya producidos.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.analysis.realtick_bt.faulty import comparador as C

_REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------- 0. guarda t1 (§3)
def test_verificar_t1_ok_no_revienta():
    C.verificar_t1({"parametros": {"t1": C.T1_ESPERADO}})


def test_verificar_t1_truncado_conocido_revienta():
    with pytest.raises(C.CorridaTruncadaError):
        C.verificar_t1({"parametros": {"t1": C.T1_TRUNCADO_CONOCIDO}})


def test_verificar_t1_otro_valor_revienta():
    with pytest.raises(C.CorridaTruncadaError):
        C.verificar_t1({"parametros": {"t1": 123.0}})


def test_metricas_p_cap_real_trae_el_t1_esperado():
    """§3 del brief: comprobación contra el artefacto real en disco -- si
    esto revienta, la corrida en disco es la truncada y hay que parar."""
    with open(C.METRICAS_P_CAP_JSON, encoding="utf-8") as f:
        metricas = json.load(f)
    C.verificar_t1(metricas)  # no debe reventar


# --------------------------------------------------- 1. tabla de equivalencia
def test_cargar_equivalencia_desde_artefacto_real():
    equivalencia, conteos = C.cargar_equivalencia(C.MAPEO_MOTIVOS_JSON)
    assert equivalencia["SL"] == {"SL"}
    assert equivalencia["CLOSE_RECONCILER"] == {"EXPERT"}
    assert equivalencia["FALLBACK_CLOSE_INVALID_SL"] == {"EXPERT", "SL"}
    # conteos vienen del propio artefacto, no se inventan
    assert conteos[("CLOSE_RECONCILER", "EXPERT")] == 13  # 10 SAME_BAR + 3 SENT CLOSE
    assert conteos[("FALLBACK_CLOSE_INVALID_SL", "EXPERT")] == 8
    assert conteos[("FALLBACK_CLOSE_INVALID_SL", "SL")] == 1
    assert conteos[("SL", "SL")] == 117


def test_fallback_close_invalid_sl_replica_contra_sl_real_empareja():
    """Blinda la regla 4.2 (spec E.2.2, brief §7.1): FALLBACK_CLOSE_INVALID_SL
    de la réplica puede casar LEGÍTIMAMENTE con SL de MT5 -- 1 caso medido,
    carrera entre el cierre a mercado del ejecutor y el stop server-side.
    NO debe marcarse como fallo de razón de cierre."""
    equivalencia, _ = C.cargar_equivalencia(C.MAPEO_MOTIVOS_JSON)
    coincide, no_evaluable = C.evaluar_razon_cierre("FALLBACK_CLOSE_INVALID_SL", "SL", equivalencia)
    assert coincide is True
    assert no_evaluable is False


def test_motivo_ausente_de_la_tabla_produce_no_evaluable_no_forzado():
    """Regla dura 1: un motivo_cierre ausente de la tabla de equivalencia
    produce NO_EVALUABLE, NUNCA el emparejamiento más parecido."""
    equivalencia, _ = C.cargar_equivalencia(C.MAPEO_MOTIVOS_JSON)
    assert "FIN_VENTANA" not in equivalencia  # artefacto del harness, sin evidencia real
    coincide, no_evaluable = C.evaluar_razon_cierre("FIN_VENTANA", "SL", equivalencia)
    assert no_evaluable is True
    assert coincide is None  # nunca se fuerza a True ni a False


def test_evaluar_razon_cierre_motivo_conocido_pero_reason_no_permitido():
    equivalencia, _ = C.cargar_equivalencia(C.MAPEO_MOTIVOS_JSON)
    coincide, no_evaluable = C.evaluar_razon_cierre("SL", "EXPERT", equivalencia)
    assert no_evaluable is False
    assert coincide is False


# ------------------------------------------------------- 2. resultado (win/loss)
def test_resultado_real_por_signo_de_profit():
    assert C.resultado_real(100.0) == "GANADORA"
    assert C.resultado_real(-1.0) == "PERDEDORA"
    assert C.resultado_real(0.0) == "BREAKEVEN"


def test_resultado_replica_long_y_short():
    assert C.resultado_replica("L", 100.0, 101.0) == "GANADORA"
    assert C.resultado_replica("L", 100.0, 99.0) == "PERDEDORA"
    assert C.resultado_replica("S", 100.0, 99.0) == "GANADORA"
    assert C.resultado_replica("S", 100.0, 101.0) == "PERDEDORA"


# --------------------------------------------------- 3. CLIENT_manual excluido
def test_client_manual_real_queda_fuera_del_denominador():
    """Regla dura 4/5 (brief): los cierres CLIENT_manual (11) quedan FUERA
    del denominador del criterio de paso y aparecen en el conteo aparte."""
    verdad = pd.DataFrame([
        {"position_id": 1, "strategy_id": "SAR::S6-K2P0", "side": "SELL",
         "t_open_epoch": 100.0, "t_open_servidor": "x", "precio_open": 4000.0,
         "t_close_epoch": 200.0, "t_close_servidor": "y", "precio_close": 3990.0,
         "reason_name": "CLIENT_manual", "profit": 500.0, "volume": 0.67},
        {"position_id": 2, "strategy_id": "SAR::S6-K2P0", "side": "SELL",
         "t_open_epoch": 300.0, "t_open_servidor": "x", "precio_open": 4010.0,
         "t_close_epoch": 400.0, "t_close_servidor": "y", "precio_close": 4020.0,
         "reason_name": "SL", "profit": -500.0, "volume": 0.67},
    ])
    replica = pd.DataFrame([
        {"strategy_id": "SAR::S6-K2P0", "side": "S", "t_open": 300.0,
         "t_open_servidor": "x", "precio_open": 4010.0, "sl_open_deseado": 4020.0,
         "sl_open_enviado": 4020.0, "clamp_aplicado": False, "t_close": 400.0,
         "t_close_servidor": "y", "precio_close": 4020.0, "motivo_cierre": "SL"},
    ])
    sl_enviado = pd.DataFrame(
        [{"position_id": 1, "sl_status": "NO_LOGUEADO", "sl_clamped_enviado": np.nan},
         {"position_id": 2, "sl_status": "NO_LOGUEADO", "sl_clamped_enviado": np.nan}]
    ).set_index("position_id")
    equivalencia, conteos = C.cargar_equivalencia(C.MAPEO_MOTIVOS_JSON)

    comparacion = C.construir_comparacion(verdad, replica, sl_enviado, equivalencia)
    resumen = C.resumen_agregado(comparacion, conteos_equivalencia=conteos)

    assert resumen["denominadores"]["posiciones"]["valor"] == 1  # sólo la posición 2 (SL)
    assert resumen["excluidos_del_criterio"]["total"] == 1
    assert resumen["excluidos_del_criterio"]["por_categoria"]["CLIENT_manual"] == 1
    assert resumen["excluidos_del_criterio"]["profit_clp_client_manual"] == 500.0

    fila_manual = comparacion[comparacion["position_id"] == 1].iloc[0]
    assert bool(fila_manual["excluido_criterio"]) is True
    fila_sl = comparacion[comparacion["position_id"] == 2].iloc[0]
    assert bool(fila_sl["excluido_criterio"]) is False


# --------------------------------------------------- 4. emparejamiento 1-a-1
def test_emparejamiento_1_a_1_no_reutiliza_la_misma_real():
    """Regla dura 6: dos posiciones de la réplica candidatas a la misma real
    -> una queda como residuo, nunca se consume dos veces la misma real."""
    real_precios = np.array([4000.0])
    rep_precios = np.array([4000.10, 4000.20])  # ambas MUY cerca de la única real
    pares, residuo_real, residuo_rep = C.alinear_posiciones(real_precios, rep_precios, gap_cost=1000.0)

    assert len(pares) == 1
    assert len(residuo_real) == 0
    assert len(residuo_rep) == 1
    # la real (índice 0) sólo aparece una vez, como pareja de la réplica más cercana en precio
    reales_usadas = [i for i, _ in pares]
    assert reales_usadas.count(0) == 1
    # la réplica emparejada es la más cercana en precio (índice 0, delta 0.10)
    assert pares[0][1] == 0
    assert residuo_rep == [1]


def test_alinear_por_estrategia_separa_por_side():
    """Una posición SELL nunca debe emparejarse con una réplica L (BUY),
    aunque el precio esté clavado."""
    real = pd.DataFrame([
        {"side": "SELL", "precio_open": 4000.0, "t_open_epoch": 100.0},
    ])
    replica = pd.DataFrame([
        {"side": "L", "precio_open": 4000.0, "t_open": 100.0},  # mismo precio, lado distinto
    ])
    pares, residuo_real, residuo_rep = C.alinear_por_estrategia(real, replica, gap_cost=1000.0)
    assert pares == []
    assert residuo_real == [0]
    assert residuo_rep == [0]


# ----------------------------------------------- 5. dos denominadores, sin mezclar
def test_reporte_publica_los_dos_denominadores_sin_mezclarlos():
    verdad = pd.DataFrame([
        {"position_id": 1, "strategy_id": "SAR::S6-K2P0", "side": "SELL",
         "t_open_epoch": 100.0, "t_open_servidor": "x", "precio_open": 4000.0,
         "t_close_epoch": 200.0, "t_close_servidor": "y", "precio_close": 3990.0,
         "reason_name": "SL", "profit": 500.0, "volume": 0.67},
    ])
    replica = pd.DataFrame([
        {"strategy_id": "SAR::S6-K2P0", "side": "S", "t_open": 100.0,
         "t_open_servidor": "x", "precio_open": 4000.0, "sl_open_deseado": 3990.0,
         "sl_open_enviado": 3990.0, "clamp_aplicado": False, "t_close": 200.0,
         "t_close_servidor": "y", "precio_close": 3990.0, "motivo_cierre": "SL"},
    ])
    sl_enviado = pd.DataFrame(
        [{"position_id": 1, "sl_status": "NO_LOGUEADO", "sl_clamped_enviado": np.nan}]
    ).set_index("position_id")
    equivalencia, conteos = C.cargar_equivalencia(C.MAPEO_MOTIVOS_JSON)
    comparacion = C.construir_comparacion(verdad, replica, sl_enviado, equivalencia)
    resumen = C.resumen_agregado(comparacion, conteos_equivalencia=conteos)

    d = resumen["denominadores"]
    assert d["posiciones"]["valor"] == 1
    assert d["barras_senal"] == C.DENOMINADOR_BARRAS_SENAL
    assert d["barras_senal"]["S6"] == 49
    assert d["barras_senal"]["ST"] == 42
    assert d["barras_senal"]["total"] == 91
    # no se mezclan: no existe ninguna clave que sume o promedie ambos cortes
    assert "posiciones" in d and "barras_senal" in d
    assert d["posiciones"]["valor"] != d["barras_senal"]["total"]


# ------------------------------------------------------- artefactos reales
def test_metricas_p_cap_json_real_no_es_la_corrida_truncada():
    """Repite el guard sobre el artefacto real en disco (data/analysis/...),
    igual que el brief §3 exige comprobar explícitamente."""
    assert C.METRICAS_P_CAP_JSON.exists()
    with open(C.METRICAS_P_CAP_JSON, encoding="utf-8") as f:
        metricas = json.load(f)
    assert metricas["parametros"]["t1"] == C.T1_ESPERADO


def test_comparar_p_cap_corrida_completa_escribe_los_3_artefactos(tmp_path):
    """Corrida completa contra los artefactos reales en disco (§8 HECHO:
    'Los tres artefactos de §6 existen en sus rutas exactas'). Se escribe a
    tmp_path para no depender del orden de ejecución del test que sí escribe
    a la ruta final."""
    out_csv = tmp_path / "comparacion_p_cap.csv"
    out_json = tmp_path / "p_cap_resultado.json"
    out_md = tmp_path / "p_cap_resultado.md"

    resumen = C.comparar_p_cap(out_csv=out_csv, out_json=out_json, out_md=out_md)

    assert out_csv.exists()
    assert out_json.exists()
    assert out_md.exists()

    comparacion = pd.read_csv(out_csv)
    assert len(comparacion) > 0
    assert set(comparacion["tipo_fila"].unique()) <= {"REAL", "REPLICA_SIN_PAREJA"}
    assert (comparacion["tipo_fila"] == "REAL").sum() == 152

    assert resumen["denominadores"]["posiciones"]["valor"] == 140
    assert resumen["lineage"]["engine_sha"] == "b113eb7"
    assert resumen["lineage"]["experimento"] == "T0.7-P-CAP"
