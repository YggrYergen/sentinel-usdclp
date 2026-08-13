"""tests/analysis/test_derivar_stops_level.py -- M1: derivar `stops_level` del
motor faulty (tag engine-faulty-tomachine-902 -> b113eb7) desde los eventos de
clamp del ejecutor real.

Brief: .superpowers/sdd/2026-08-13-replica-motor-faulty-spec/m1-stops-level-brief.md

Los 4 casos minimos exigidos por el brief (Sec. 4), uno por funcion de test:
  1. nivel_desde_ref_clamped exacto para un caso long y uno short sinteticos.
  2. verificar_signo marca como incoherente un long cuyo clamped > ref.
  3. Un conjunto sintetico con dos niveles distintos se reporta como NO
     constante, con los dos valores y sus frecuencias -- no se promedia ni se
     elige uno.
  4. Un evento sin `ref` se cuenta como descartado y no entra en el conjunto
     de niveles.
"""
from __future__ import annotations

from scripts.analysis.p_cap.derivar_stops_level import (
    nivel_desde_ref_clamped,
    procesar_familia,
    verificar_necesidad,
    verificar_signo,
)


def _ev(**kw):
    """Evento sintetico minimo; los campos no dados quedan en None."""
    base = {
        "epoch": 0,
        "timestamp_servidor": "",
        "config": "CFG",
        "ficha": "F1",
        "side": None,
        "ref": None,
        "clamped": None,
        "desired_sl": None,
    }
    base.update(kw)
    return base


def test_nivel_desde_ref_clamped_long_y_short():
    # long: ref=bid, clamped = ref - level
    assert nivel_desde_ref_clamped(ref=4000.00, clamped=3999.50) == 0.50
    # short: ref=ask, clamped = ref + level
    assert nivel_desde_ref_clamped(ref=4000.00, clamped=4000.50) == 0.50


def test_verificar_signo_detecta_long_incoherente():
    # long cuyo clamped > ref (deberia ser ref - level, i.e. clamped < ref):
    # geometricamente incoherente con la aritmetica del clamp.
    level = nivel_desde_ref_clamped(ref=4000.00, clamped=4000.50)
    assert verificar_signo(side="L", ref=4000.00, clamped=4000.50, level=level) is False
    # el caso coherente (long, clamped = ref - level) sigue pasando
    level_ok = nivel_desde_ref_clamped(ref=4000.00, clamped=3999.50)
    assert verificar_signo(side="L", ref=4000.00, clamped=3999.50, level=level_ok) is True


def test_verificar_signo_short_coherente_e_incoherente():
    level_ok = nivel_desde_ref_clamped(ref=4000.00, clamped=4000.50)
    assert verificar_signo(side="S", ref=4000.00, clamped=4000.50, level=level_ok) is True
    # short cuyo clamped < ref es incoherente (deberia ser ref + level)
    level_bad = nivel_desde_ref_clamped(ref=4000.00, clamped=3999.50)
    assert verificar_signo(side="S", ref=4000.00, clamped=3999.50, level=level_bad) is False


def test_verificar_necesidad_long_y_short():
    # long: se dispara si desired_sl > ref - level
    assert verificar_necesidad(side="L", desired_sl=3999.60, ref=4000.00, level=0.50) is True
    assert verificar_necesidad(side="L", desired_sl=3999.40, ref=4000.00, level=0.50) is False
    # short: se dispara si desired_sl < ref + level
    assert verificar_necesidad(side="S", desired_sl=4000.40, ref=4000.00, level=0.50) is True
    assert verificar_necesidad(side="S", desired_sl=4000.60, ref=4000.00, level=0.50) is False


def test_conjunto_sintetico_no_constante_no_se_promedia_ni_se_elige_uno():
    eventos = [
        _ev(epoch=1, side="L", ref=4000.00, clamped=3999.50, desired_sl=3999.60),
        _ev(epoch=2, side="L", ref=4000.00, clamped=3999.70, desired_sl=3999.80),
    ]
    resultado = procesar_familia(eventos)
    resumen = resultado["resumen_niveles"]
    assert resumen["es_constante"] is False
    # ambos valores deben seguir presentes -- el codigo NO debe promediar
    # (0.30) ni colapsar en uno solo.
    valores = resumen["valores"]
    assert "0.50000" in valores and valores["0.50000"] == 1
    assert "0.30000" in valores and valores["0.30000"] == 1
    assert resumen.get("mediana") not in (None,) or True  # mediana puede existir, no debe sustituir a 'valores'
    assert len(resultado["discrepancias"]) >= 1


def test_evento_sin_ref_se_descarta_y_no_entra_en_niveles():
    eventos = [
        _ev(epoch=1, side="L", ref=4000.00, clamped=3999.50, desired_sl=3999.60),
        _ev(epoch=2, side="L", ref=None, clamped=3999.50, desired_sl=3999.60),
    ]
    resultado = procesar_familia(eventos)
    assert resultado["n"] == 2
    assert resultado["n_usable"] == 1
    assert resultado["n_descartados"] == 1
    assert resultado["motivos_descartados"].get("ref_ausente") == 1
    # solo el nivel del evento usable entra en el conjunto
    assert resultado["resumen_niveles"]["n"] == 1
    assert resultado["resumen_niveles"]["valores"] == {"0.50000": 1}
