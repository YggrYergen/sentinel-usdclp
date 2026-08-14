"""tests/analysis/test_censo_cola_t_open.py -- BRIEF I (censo de la cola del
p90 de |delta t_open|), T0.7 / A6 Pata A / P-CAP, Fase 0.

Spec: .superpowers/sdd/2026-08-13-replica-motor-faulty-spec/i-cola-p90-brief.md

Sólo prueba las funciones puras de censo/clasificación de
scripts/analysis/realtick_bt/faulty/censo_cola_t_open.py, sobre fixtures
sintéticas en memoria. No lee ningún CSV real ni pega I/O.

R1-bis: nada aquí modifica ciclos.py, estado_por_barra.py, llamador.py,
comparador.py, config_faulty.py ni sentinel_engine/**.
"""
from __future__ import annotations

import pandas as pd
import pytest

from scripts.analysis.realtick_bt.faulty import censo_cola_t_open as M


def _df_replica(rows):
    return pd.DataFrame(rows, columns=["strategy_id", "t", "tipo", "detalle"])


def _df_ejecutor(rows):
    return pd.DataFrame(rows, columns=["epoch", "event"])


# --------------------------------------------------------------- signo_delta
def test_signo_delta_positivo_es_replica_tarde():
    assert M.signo_delta(61.0) == "REPLICA_TARDE"


def test_signo_delta_negativo_es_replica_temprano():
    assert M.signo_delta(-61.0) == "REPLICA_TEMPRANO"


def test_signo_delta_cero_es_replica_tarde_por_convencion():
    # 0.0 no tiene signo real; se fija la convención >=0 => TARDE.
    assert M.signo_delta(0.0) == "REPLICA_TARDE"


# ----------------------------------------- censar_intervalo_replica: bordes
def test_censar_intervalo_replica_bordes_inclusivos():
    df = _df_replica([
        ("A", 100.0, "NOOP", "{}"),
        ("A", 200.0, "OPEN", "{}"),    # lo == 200, inclusive
        ("A", 300.0, "CLOSE", "{}"),   # hi == 300, inclusive
        ("A", 301.0, "MODIFY", "{}"),  # fuera del intervalo
    ])
    res = M.censar_intervalo_replica(df, "A", 200.0, 300.0)
    assert res["n_eventos_intervalo"] == 2
    assert res["eventos_OPEN"] == 1
    assert res["eventos_CLOSE"] == 1
    assert res["eventos_MODIFY"] == 0
    assert res["eventos_NOOP"] == 0


def test_censar_intervalo_replica_excluye_otra_estrategia():
    df = _df_replica([
        ("A", 200.0, "OPEN", "{}"),
        ("B", 250.0, "CLOSE", "{}"),  # otra estrategia dentro del intervalo: NO cuenta
    ])
    res = M.censar_intervalo_replica(df, "A", 200.0, 300.0)
    assert res["n_eventos_intervalo"] == 1
    assert res["eventos_CLOSE"] == 0
    assert res["eventos_OPEN"] == 1


def test_censar_intervalo_replica_todos_los_9_tipos_presentes():
    df = _df_replica([("A", 200.0, "OPEN", "{}")])
    res = M.censar_intervalo_replica(df, "A", 200.0, 200.0)
    for tipo in M.TIPOS_REPLICA:
        assert f"eventos_{tipo}" in res


# -------------------------------------------------- tipo_dominante_intervalo
def test_tipo_dominante_excluye_noop():
    df = _df_replica([
        ("A", 100.0, "NOOP", "{}"),
        ("A", 101.0, "NOOP", "{}"),
        ("A", 102.0, "SPREAD_GATE_SKIP", "{}"),
    ])
    res = M.censar_intervalo_replica(df, "A", 100.0, 102.0)
    assert res["tipo_dominante_intervalo"] == "SPREAD_GATE_SKIP"


def test_tipo_dominante_solo_noop():
    df = _df_replica([
        ("A", 100.0, "NOOP", "{}"),
        ("A", 101.0, "NOOP", "{}"),
    ])
    res = M.censar_intervalo_replica(df, "A", 100.0, 101.0)
    assert res["tipo_dominante_intervalo"] == "SOLO_NOOP"


def test_caso_sin_eventos():
    df = _df_replica([("A", 100.0, "NOOP", "{}")])
    res = M.censar_intervalo_replica(df, "A", 200.0, 300.0)  # intervalo vacío para A
    assert res["n_eventos_intervalo"] == 0
    assert res["tipo_dominante_intervalo"] == "SIN_EVENTOS"
    assert res["primer_evento_no_noop"] == ""
    assert res["t_primer_evento_no_noop"] == ""


def test_primer_evento_no_noop_y_su_epoch():
    df = _df_replica([
        ("A", 100.0, "NOOP", "{}"),
        ("A", 105.0, "SPREAD_GATE_SKIP", "{}"),
        ("A", 110.0, "OPEN", "{}"),
    ])
    res = M.censar_intervalo_replica(df, "A", 100.0, 110.0)
    assert res["primer_evento_no_noop"] == "SPREAD_GATE_SKIP"
    assert res["t_primer_evento_no_noop"] == 105.0


# ----------------------------------------------------- censar_intervalo_ejecutor
def test_censar_intervalo_ejecutor_bordes_inclusivos_y_conteo_por_event():
    df = _df_ejecutor([
        (100, "SENT OPEN"),
        (150, "SENT OPEN"),
        (200, "SL_CLAMPED"),
        (201, "SENT MODIFY"),
    ])
    res = M.censar_intervalo_ejecutor(df, 100, 200)
    assert res["n_eventos_ejecutor_intervalo"] == 3
    assert res["ejecutor_eventos_conteo"]["SENT OPEN"] == 2
    assert res["ejecutor_eventos_conteo"]["SL_CLAMPED"] == 1
    assert "SENT MODIFY" not in res["ejecutor_eventos_conteo"]


# --------------------------------------------------------- epoch_a_servidor_str
def test_epoch_a_servidor_str_valor_conocido():
    # verificado contra verdad_terreno_902.csv fila 1: epoch 1785178410 ->
    # t_open_servidor "2026-07-27 18:53:30"
    assert M.epoch_a_servidor_str(1785178410) == "2026-07-27 18:53:30"


def test_epoch_a_servidor_str_vacio_si_none():
    assert M.epoch_a_servidor_str(None) == ""


# ------------------------------------------------------- epoch_en_blocked_window
def test_epoch_en_blocked_window_dentro():
    # 2026-07-27 18:20:00 -> dentro de 18:00-18:45
    import datetime
    epoch = int(datetime.datetime(2026, 7, 27, 18, 20, 0, tzinfo=datetime.timezone.utc).timestamp())
    assert M.epoch_en_blocked_window(epoch, "18:00", "18:45") is True


def test_epoch_en_blocked_window_fuera():
    import datetime
    epoch = int(datetime.datetime(2026, 7, 27, 19, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    assert M.epoch_en_blocked_window(epoch, "18:00", "18:45") is False


def test_epoch_en_blocked_window_none_si_epoch_ausente():
    assert M.epoch_en_blocked_window(None, "18:00", "18:45") is None
