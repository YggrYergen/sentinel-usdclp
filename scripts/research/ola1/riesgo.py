r"""scripts/research/ola1/riesgo.py -- OLA1-EXEC Bloque 1.

R por posicion (E-04 SS2.3): R1_i en CLP por 1.0 lote,

    R1_i = abs(entry_fill_i - SL_inicial_i) * bt.CONTRACT * bt.USDCLP

calculado con los MISMOS helpers que usa el motor para el SL inicial --
`bt._sl_inicial_genuine` para la escalera (S6/S7, el mismo que usa
`run_ladder`), y `bt._atr_wilder` + `bt.supertrend` para SuperTrend (los
mismos que usa `run_supertrend`). Nunca reimplementado desde cero, nunca
rellenado con un default: no computable o <= 0 => None, contado y publicado
por metricas.metricas_de_brazo (nunca aqui -- este modulo solo calcula).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from scripts.analysis.realtick_bt import backtest as bt
from scripts.analysis.realtick_bt.overlay import overlay_kwargs


def _r_ladder(sid: str, arm_overlay: dict[str, Any], posiciones: list[dict[str, Any]],
              bars: list[dict[str, Any]]) -> list[float | None]:
    kwargs = overlay_kwargs(sid, arm_overlay)
    # Mismos defaults que run_ladder (backtest.py:255,262) y que
    # simular_variant, para que un overlay vacio/parcial clasifique igual
    # que llamar al motor con sus propios defaults.
    k_init = kwargs.get("init_sl_range_k", 1.0)
    wait_mae_atr_k = kwargs.get("wait_mae_atr_k", 0.0)
    atr14 = (
        bt._atr_wilder([b["high"] for b in bars], [b["low"] for b in bars],
                        [b["close"] for b in bars], 14)
        if wait_mae_atr_k > 0.0 else None
    )
    bar_times = np.array([b["t"] for b in bars], dtype="float64")
    out: list[float | None] = []
    for pos in posiciones:
        idx = int(np.searchsorted(bar_times, pos["t_in"], "left"))
        assert bars[idx]["t"] == pos["t_in"], (
            f"{sid}: bars[{idx}]['t']={bars[idx]['t']} != pos['t_in']={pos['t_in']} "
            "-- indice de barra de senal desalineado"
        )
        side_l = pos["side_l"]
        sl_inicial = bt._sl_inicial_genuine(
            side_l, idx, bars, k_init, pos["entry_bid"], wait_mae_atr_k, atr14
        )
        r = abs(pos["entry_fill"] - sl_inicial) * bt.CONTRACT * bt.USDCLP
        out.append(r if r > 0 else None)
    return out


def _r_supertrend(arm_overlay: dict[str, Any], posiciones: list[dict[str, Any]],
                   bars: list[dict[str, Any]]) -> list[float | None]:
    atr_period = arm_overlay.get("atr_period", 14)
    mult = arm_overlay.get("mult", 3.0)
    sl_offset = arm_overlay.get("sl_offset", 0.0)
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    atr = bt._atr_wilder(highs, lows, closes, atr_period)
    atrf = [a if a is not None else 0.0 for a in atr]
    _trend, line = bt.supertrend(highs, lows, closes, atrf, mult)
    bar_times = np.array([b["t"] for b in bars], dtype="float64")
    out: list[float | None] = []
    for pos in posiciones:
        idx = int(np.searchsorted(bar_times, pos["t_in"], "left"))
        assert bars[idx]["t"] == pos["t_in"], (
            f"SuperTrend: bars[{idx}]['t']={bars[idx]['t']} != pos['t_in']={pos['t_in']} "
            "-- indice de barra de senal desalineado"
        )
        sl_line = line[idx]
        if sl_line is None:
            out.append(None)
            continue
        sl_inicial = (sl_line - sl_offset) if pos["side_l"] == "L" else (sl_line + sl_offset)
        r = abs(pos["entry_fill"] - sl_inicial) * bt.CONTRACT * bt.USDCLP
        out.append(r if r > 0 else None)
    return out


def r_por_posicion(sid: str, arm_overlay: dict[str, Any], posiciones: list[dict[str, Any]],
                    bars: list[dict[str, Any]]) -> list[float | None]:
    """R1_i en CLP por 1.0 lote, en el mismo orden que `posiciones`. `None`
    si no computable o <= 0 -- nunca un default."""
    if sid == "SuperTrend-p14x3-M15":
        return _r_supertrend(arm_overlay, posiciones, bars)
    return _r_ladder(sid, arm_overlay, posiciones, bars)
