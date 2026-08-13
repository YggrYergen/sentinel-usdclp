"""tests/analysis/test_mapeo_motivos_cierre.py -- lógica de emparejamiento
histórico (verdad de terreno 902) <-> log del ejecutor, reutilizable por el
comparador de P-CAP (T0.7-p-cap, brief
`.superpowers/sdd/2026-08-13-replica-motor-faulty-spec/m2-mapeo-motivos-brief.md`).

Los 5 tests de aceptación del brief (§4), uno por función de test. Datos
sintéticos en memoria -- no toca los CSV reales de `data/analysis/p_cap/`.
"""
from __future__ import annotations

from scripts.analysis.p_cap.mapeo_motivos_cierre import (
    build_contingency_matrix,
    match_closures,
)


def _pos(position_id, reason_name="EXPERT", strategy_id="SAR::S6-K2P0",
         t_close_epoch=1000, ticket_in=None, ticket_out=None):
    return {
        "position_id": str(position_id),
        "reason_name": reason_name,
        "strategy_id": strategy_id,
        "t_close_epoch": str(t_close_epoch),
        "ticket_in": str(ticket_in) if ticket_in is not None else str(position_id),
        "ticket_out": str(ticket_out) if ticket_out is not None else str(position_id) + "1",
    }


def _evt(event="SENT CLOSE", epoch=1000, ticket=None, config="", raw=""):
    return {
        "event": event,
        "epoch": str(epoch),
        "ticket": str(ticket) if ticket is not None else "",
        "magic": "",
        "config": config,
        "raw": raw,
    }


# --------------------------------------------------------------------- test 1
def test_ticket_match_3s_apart():
    """Un cierre y un evento de log del mismo ticket separados 3s emparejan,
    con ancla 'ticket'."""
    pos = _pos(position_id=55216738, t_close_epoch=1785268594)
    evt = _evt(event="FALLBACK_CLOSE_INVALID_SL", epoch=1785268594 + 3,
                ticket=55216738)

    result = match_closures([pos], [evt], tolerance_s=60.0)

    assert len(result.matched) == 1
    m = result.matched[0]
    assert m["position_id"] == "55216738"
    assert m["anchor"] == "ticket"
    assert abs(m["offset_s"] - 3.0) < 1e-9
    assert not result.residual_positions
    assert not result.residual_events


# --------------------------------------------------------------------- test 2
def test_ticket_match_600s_apart_no_empareja_con_tolerancia_60s():
    """Los mismos separados 600s con tolerancia 60s no emparejan; ambos
    aparecen como residuo."""
    pos = _pos(position_id=55216738, t_close_epoch=1785268594)
    evt = _evt(event="FALLBACK_CLOSE_INVALID_SL", epoch=1785268594 + 600,
                ticket=55216738)

    result = match_closures([pos], [evt], tolerance_s=60.0)

    assert result.matched == []
    assert len(result.residual_positions) == 1
    assert result.residual_positions[0]["position_id"] == "55216738"
    assert len(result.residual_events) == 1
    assert result.residual_events[0]["event"] == "FALLBACK_CLOSE_INVALID_SL"


# --------------------------------------------------------------------- test 3
def test_dos_candidatos_gana_el_mas_cercano_y_el_otro_queda_residuo():
    """Dos eventos candidatos para un mismo cierre: gana el más cercano en
    el tiempo, y el otro queda como residuo. El emparejamiento es 1-a-1: el
    evento ganador nunca se reutiliza."""
    pos = _pos(position_id=55216738, t_close_epoch=1785268594)
    evt_lejos = _evt(event="SENT CLOSE", epoch=1785268594 + 40, ticket=55216738)
    evt_cerca = _evt(event="FALLBACK_CLOSE_INVALID_SL", epoch=1785268594 + 2,
                       ticket=55216738)

    result = match_closures([pos], [evt_lejos, evt_cerca], tolerance_s=60.0)

    assert len(result.matched) == 1
    m = result.matched[0]
    assert m["event"] == "FALLBACK_CLOSE_INVALID_SL"
    assert abs(m["offset_s"] - 2.0) < 1e-9

    assert len(result.residual_events) == 1
    assert result.residual_events[0]["event"] == "SENT CLOSE"
    assert not result.residual_positions


# --------------------------------------------------------------------- test 4
def test_magic_cero_empareja_igual_por_ticket():
    """Un cierre con magic=0 (deals de cierre SL/TP en MT5 llegan con
    magic=0) empareja igual por ticket -- blinda la trampa del §2 del
    brief: emparejar por magic perdería precisamente estos cierres."""
    pos = _pos(position_id=55216738, reason_name="SL", t_close_epoch=1785268594)
    evt = _evt(event="SENT CLOSE", epoch=1785268594 + 1, ticket=55216738)
    evt["magic"] = "0"

    result = match_closures([pos], [evt], tolerance_s=60.0)

    assert len(result.matched) == 1
    assert result.matched[0]["anchor"] == "ticket"


# --------------------------------------------------------------------- test 5
def test_matriz_incluye_sin_emparejar_aunque_vacia():
    """La matriz de contingencia incluye la categoría SIN EMPAREJAR en fila
    y columna aunque no haya ningún residuo."""
    pos = _pos(position_id=55216738, reason_name="EXPERT", t_close_epoch=1785268594)
    evt = _evt(event="SENT CLOSE", epoch=1785268594 + 1, ticket=55216738)

    result = match_closures([pos], [evt], tolerance_s=60.0)
    matrix = build_contingency_matrix(result)

    assert "SIN EMPAREJAR" in matrix["rows"]
    assert "SIN EMPAREJAR" in matrix["cols"]
    assert matrix["cells"]["SIN EMPAREJAR"]["SIN EMPAREJAR"] == 0
    assert matrix["cells"]["EXPERT"]["SENT CLOSE"] == 1
    assert matrix["cells"]["EXPERT"]["SIN EMPAREJAR"] == 0
    assert matrix["cells"]["SIN EMPAREJAR"]["SENT CLOSE"] == 0
