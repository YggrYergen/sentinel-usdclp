r"""diag_p03_activacion.py -- diagnostico P-03 (AC-deceleration), REPORT-ONLY.

NO edita ni el motor ni ningun fichero de investigacion ademas de su propia
salida. NO llama a paired_harness.run_paired_arms, a scripts.research.runner,
ni a correr_ola1.py -- todo lo que sigue trabaja directamente sobre las
8.334 barras del sustrato Ola 1 (research/fases/F0-preparacion/.../sustrato.py)
y sobre una unica llamada a `simular_variant` por brazo medido (default y
ac_off), envuelta con un spy en memoria sobre `ac_desacelerando` -- exactamente
la misma tecnica que ya uso el implementador de OLA1-EXEC (ver
OLA1-EXEC-reporte.md SS4), nunca el runner ni el harness pareado completos.

Escribe un unico JSON con los conteos: research/fases/F0-preparacion/
04-resultados/OLA1/P03-S6/diag_activacion.json
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.analysis.realtick_bt import backtest as bt
from scripts.research.ola1 import sustrato
import sentinel_engine.strategies.emasar_variant as ev
from sentinel_engine.strategies.emasar_ref import (
    ac_series as ac_series_ref,
    ac_desacelerando as ac_desacelerando_ref,
    _atr_wilder,
    pip_size,
)

OUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "04-resultados" / "OLA1" / "P03-S6" / "diag_activacion.json"
)

SID = "S6-K2P0"
UMBRAL_PIPS_GRID = [10, 25, 50, 75, 100, 150]
LOOKBACK_GRID = [1, 2, 3]


def main() -> dict:
    bars = sustrato.cargar_barras()
    n_bars = len(bars)
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]

    pip = pip_size("XAUUSD")
    assert pip == 0.01, f"pip_size(XAUUSD) cambio de valor: {pip!r}"

    # ---- Paso 1: serie AC sobre el sustrato completo (Charter SS A.6:
    # sustrato=bars, non-verdict -- esto es estadistica de senal, no veredicto) --
    ac = ac_series_ref(highs, lows)
    n_ac_none = sum(1 for v in ac if v is None)

    # ---- Paso 2: conteo de disparo de ac_desacelerando sobre TODO el sustrato,
    # ambas direcciones, para cada celda de la grilla preregistrada (umbral en
    # pips * 0.01, lookback 1/2/3). Esto es un COTA SUPERIOR (cuenta cada barra
    # como si hubiera una ficha abierta favorable en esa direccion en ese
    # instante) -- no el conteo real intra-simulacion, que depende de que haya
    # fichas abiertas. Declarado como tal.
    grid_counts = {}
    for umbral_pips in UMBRAL_PIPS_GRID:
        umbral = round(umbral_pips * pip, 10)
        for lookback in LOOKBACK_GRID:
            n_long = sum(
                1 for i in range(n_bars)
                if ac_desacelerando_ref(ac, i, +1, lookback=lookback, umbral=umbral)
            )
            n_short = sum(
                1 for i in range(n_bars)
                if ac_desacelerando_ref(ac, i, -1, lookback=lookback, umbral=umbral)
            )
            grid_counts[f"u{umbral_pips}-lb{lookback}"] = {
                "umbral_pips": umbral_pips, "ac_decel_umbral": umbral,
                "lookback": lookback, "n_long": n_long, "n_short": n_short,
                "n_total": n_long + n_short,
                "frac_long": round(n_long / n_bars, 4),
                "frac_short": round(n_short / n_bars, 4),
            }

    # Umbral=0.0 (byte-identical default de ac_desacelerando, no forma parte
    # de la grilla P-03 pero sirve de referencia -- "sin piso de magnitud").
    n_long_u0 = sum(1 for i in range(n_bars)
                    if ac_desacelerando_ref(ac, i, +1, lookback=1, umbral=0.0))
    n_short_u0 = sum(1 for i in range(n_bars)
                      if ac_desacelerando_ref(ac, i, -1, lookback=1, umbral=0.0))

    # ---- Paso 3: ATR14 Wilder sobre el mismo sustrato, misma funcion que
    # consume el motor (_atr_wilder importado de emasar_ref, re-exportado por
    # emasar_variant) -- para medir el piso trail_atr_floor_k del kwarg VIVO
    # de S6-K2P0 (trail_atr_floor_k=2.0, live_configs_20.py:256-257).
    atr14 = _atr_wilder(highs, lows, closes, 14)
    atr_vals = [v for v in atr14 if v is not None]
    n_atr_none = n_bars - len(atr_vals)

    kwargs_live = bt._GL[SID]
    trail_atr_floor_k_live = kwargs_live["trail_atr_floor_k"]
    base_trail = kwargs_live["f1_trail_pips"] * pip  # F1==F2==F3==100 pips live
    assert kwargs_live["f1_trail_pips"] == kwargs_live["f2_trail_pips"] == kwargs_live["f3_trail_pips"]
    ac_modulate_factor_live = kwargs_live["ac_modulate_factor"]
    ac_modulate_live = kwargs_live["ac_modulate"]

    floor_vals = [trail_atr_floor_k_live * v for v in atr_vals]
    n_floor_domina_base = sum(1 for f in floor_vals if f > base_trail)
    n_floor_domina_modulado = sum(
        1 for f in floor_vals if f > base_trail * ac_modulate_factor_live
    )
    floor_sorted = sorted(floor_vals)
    m = len(floor_sorted)

    def _pct(p):
        if m == 0:
            return None
        idx = min(m - 1, int(round(p * (m - 1))))
        return floor_sorted[idx]

    # ---- Paso 4: spy en memoria sobre ac_desacelerando DENTRO de una corrida
    # real de simular_variant (control S6-K2P0 vivo, y ac_off) -- cuenta
    # cuantas veces la condicion se evalua True EN LA SIMULACION REAL (no la
    # cota superior del Paso 2), sin tocar ningun fichero de motor: el
    # monkeypatch vive solo en el proceso de este script y se revierte al
    # terminar. NO se invoca paired_harness ni el runner.
    calls_default = {"n_true": 0, "n_calls": 0}
    calls_ac_off = {"n_true": 0, "n_calls": 0}

    orig = ev.ac_desacelerando

    def _make_spy(counter):
        def _spy(ac_arg, idx, lado, *, lookback=1, umbral=0.0):
            r = orig(ac_arg, idx, lado, lookback=lookback, umbral=umbral)
            counter["n_calls"] += 1
            if r:
                counter["n_true"] += 1
            return r
        return _spy

    kwargs_default = copy.deepcopy(bt._GL[SID])
    ev.ac_desacelerando = _make_spy(calls_default)
    try:
        eventos_default = ev.simular_variant(bars, **kwargs_default)
    finally:
        ev.ac_desacelerando = orig

    kwargs_ac_off = copy.deepcopy(bt._GL[SID])
    kwargs_ac_off["ac_modulate"] = False
    ev.ac_desacelerando = _make_spy(calls_ac_off)
    try:
        eventos_ac_off = ev.simular_variant(bars, **kwargs_ac_off)
    finally:
        ev.ac_desacelerando = orig

    n_eventos_default = len(eventos_default)
    n_eventos_ac_off = len(eventos_ac_off)
    eventos_identicos = eventos_default == eventos_ac_off

    resultado = {
        "estado": "PRE-INTERPRETACION -- charter SS A.4, ningun numero aqui es veredicto",
        "sustrato": {
            "n_bars": n_bars, "n_ac_none": n_ac_none, "n_atr14_none": n_atr_none,
            "pip_size_XAUUSD": pip,
        },
        "paso2_cota_superior_disparo_por_umbral_lookback_TODO_el_sustrato": grid_counts,
        "referencia_umbral_0.0_lookback_1": {
            "n_long": n_long_u0, "n_short": n_short_u0,
            "n_total": n_long_u0 + n_short_u0,
        },
        "paso3_piso_atr_vs_trail": {
            "trail_atr_floor_k_live_S6K2P0": trail_atr_floor_k_live,
            "base_trail_price_units_100pips": base_trail,
            "ac_modulate_live_S6K2P0": ac_modulate_live,
            "ac_modulate_factor_live_S6K2P0": ac_modulate_factor_live,
            "trail_modulado_price_units": round(base_trail * ac_modulate_factor_live, 6),
            "n_bars_atr14_valido": len(atr_vals),
            "n_floor_domina_trail_BASE_sin_modular": n_floor_domina_base,
            "frac_floor_domina_trail_BASE": round(n_floor_domina_base / len(atr_vals), 6) if atr_vals else None,
            "n_floor_domina_trail_MODULADO_por_AC": n_floor_domina_modulado,
            "frac_floor_domina_trail_MODULADO": round(n_floor_domina_modulado / len(atr_vals), 6) if atr_vals else None,
            "floor_2xATR14_p10": _pct(0.10), "floor_2xATR14_p50": _pct(0.50),
            "floor_2xATR14_p90": _pct(0.90), "floor_2xATR14_min": floor_sorted[0] if floor_sorted else None,
            "floor_2xATR14_max": floor_sorted[-1] if floor_sorted else None,
        },
        "paso4_spy_simulacion_real_S6K2P0": {
            "control_default": calls_default,
            "ac_off": calls_ac_off,
            "n_eventos_default": n_eventos_default,
            "n_eventos_ac_off": n_eventos_ac_off,
            "eventos_default_igual_a_ac_off": eventos_identicos,
        },
    }
    return resultado


if __name__ == "__main__":
    r = main()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    print(f"escrito: {OUT_PATH}")
    print(json.dumps(r, ensure_ascii=False, indent=2))
