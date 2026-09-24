"""
SENTINEL v3.1 — Motor de Niveles Price-Action
Calcula Pivot Points (Camarilla) + Swing Levels + posición relativa.
Fuentes: babypips.com (Camarilla formulas), scipy.signal (swing detection)
"""

import pandas as pd
import numpy as np
import logging
from scipy.signal import argrelextrema

logger = logging.getLogger("sentinel.levels")


def calculate_levels(data_feed, symbol: str) -> dict:
    """
    Calcula todos los niveles de price-action para el instrumento.
    
    Returns:
        Dict con:
        - pivot: dict con PP, R1-R3, S1-S3 (Camarilla)
        - swings: dict con resistencias y soportes de swing
        - combined: lista ordenada de niveles arriba y abajo del precio
        - current_price: precio actual
        - position: interpretación de posición actual
    """
    # Datos diarios para Camarilla (necesitamos H/L/C de ayer)
    df_daily = data_feed.get_data(symbol, 1440, 10)
    
    # Datos M15 para swing levels (más granularidad)
    df_m15 = data_feed.get_data(symbol, 15, 200)
    
    # Datos M5 para precio actual
    df_m5 = data_feed.get_data(symbol, 5, 50)
    
    current_price = 0
    if not df_m5.empty:
        current_price = float(df_m5['close'].iloc[-1])
    elif not df_m15.empty:
        current_price = float(df_m15['close'].iloc[-1])
    
    if current_price == 0:
        return _empty_levels()
    
    # 1. Camarilla Pivot Points
    pivot = _calculate_camarilla(df_daily)
    
    # 2. Swing Levels
    swings = _detect_swing_levels(df_m15, current_price)
    
    # 3. Combinar y ordenar: 3 arriba, 3 abajo del precio actual
    combined = _combine_levels(pivot, swings, current_price)
    
    # 4. Interpretación de posición
    position = _interpret_position(combined, current_price, pivot)
    
    return {
        "pivot": pivot,
        "swings": swings,
        "combined": combined,
        "current_price": current_price,
        "position": position,
    }


def _calculate_camarilla(df_daily: pd.DataFrame) -> dict:
    """
    Calcula Pivot Points Camarilla basados en el día anterior.
    
    Fórmulas (fuente: babypips.com, litefinance.org):
        Range = H_prev - L_prev
        R1 = C + Range * 1.1/12
        R2 = C + Range * 1.1/6
        R3 = C + Range * 1.1/4
        S1 = C - Range * 1.1/12
        S2 = C - Range * 1.1/6
        S3 = C - Range * 1.1/4
    """
    if df_daily.empty or len(df_daily) < 2:
        return {}
    
    # Día anterior (penúltima fila, ya que la última es hoy en progreso)
    prev = df_daily.iloc[-2]
    H = float(prev['high'])
    L = float(prev['low'])
    C = float(prev['close'])
    
    rng = H - L
    if rng == 0:
        return {}
    
    PP = round((H + L + C) / 3, 2)
    
    return {
        "PP": PP,
        "R1": round(C + rng * 1.1 / 12, 2),
        "R2": round(C + rng * 1.1 / 6, 2),
        "R3": round(C + rng * 1.1 / 4, 2),
        "S1": round(C - rng * 1.1 / 12, 2),
        "S2": round(C - rng * 1.1 / 6, 2),
        "S3": round(C - rng * 1.1 / 4, 2),
        "prev_high": H,
        "prev_low": L,
        "prev_close": C,
        "range": round(rng, 2),
    }


def _detect_swing_levels(df: pd.DataFrame, current_price: float,
                          order: int = 5) -> dict:
    """
    Detecta swing highs/lows usando scipy.signal.argrelextrema.
    
    order=5 significa que un punto es máximo/mínimo local si es el mayor/menor
    en un rango de 5 velas a cada lado (para M15 = 2.5 horas de contexto).
    
    Fuente: scipy.org docs, medium.com algorithmic trading guides
    """
    if df.empty or len(df) < 20:
        return {"resistances": [], "supports": []}
    
    highs = df['high'].values
    lows = df['low'].values
    
    # Detectar máximos y mínimos locales
    high_idx = argrelextrema(highs, np.greater, order=order)[0]
    low_idx = argrelextrema(lows, np.less, order=order)[0]
    
    # Extraer niveles únicos, redondeados
    resistance_levels = sorted(set(round(float(highs[i]), 2) for i in high_idx), reverse=True)
    support_levels = sorted(set(round(float(lows[i]), 2) for i in low_idx))
    
    # Filtrar: solo los que están cerca del precio actual (±5%)
    margin = current_price * 0.05
    resistance_levels = [r for r in resistance_levels if r > current_price and r < current_price + margin]
    support_levels = [s for s in support_levels if s < current_price and s > current_price - margin]
    
    # Tomar los 5 más cercanos de cada lado
    resistances = sorted(resistance_levels)[:5]
    supports = sorted(support_levels, reverse=True)[:5]
    
    return {
        "resistances": resistances,
        "supports": supports,
    }


def _combine_levels(pivot: dict, swings: dict, current_price: float) -> dict:
    """
    Combina Camarilla + Swing levels, ordena y devuelve
    los 3 más cercanos arriba y 3 más cercanos abajo.
    
    Siempre incluye Camarilla R/S independiente de la posición del precio.
    """
    all_levels = []
    
    # Agregar todos los Camarilla (R1-R3, S1-S3) sin filtrar por lado
    for key in ["R1", "R2", "R3", "S1", "S2", "S3"]:
        if key in pivot:
            level = pivot[key]
            all_levels.append({
                "price": level,
                "label": f"{key} (Camarilla)",
                "type": "camarilla",
            })
    
    # Agregar Swing levels
    for r in swings.get("resistances", []):
        if not any(abs(r - lv["price"]) < current_price * 0.001 for lv in all_levels):
            all_levels.append({"price": r, "label": "Swing High", "type": "swing"})
    
    for s in swings.get("supports", []):
        if not any(abs(s - lv["price"]) < current_price * 0.001 for lv in all_levels):
            all_levels.append({"price": s, "label": "Swing Low", "type": "swing"})
    
    # Separar en above/below del precio actual y calcular %
    above = []
    below = []
    for lv in all_levels:
        lv["pct"] = round((lv["price"] - current_price) / current_price * 100, 3)
        if lv["price"] > current_price:
            above.append(lv)
        elif lv["price"] < current_price:
            below.append(lv)
    
    # Agregar PP
    pp_level = pivot.get("PP")
    
    # Ordenar: above por más cercano, below por más cercano
    above.sort(key=lambda x: x["price"])
    below.sort(key=lambda x: x["price"], reverse=True)
    
    # Garantizar mínimo 3 niveles por lado (extrapolar si faltan)
    pivot_range = pivot.get("range", current_price * 0.005)  # fallback 0.5%
    step = pivot_range * 1.1 / 4  # ~Camarilla S3/R3 distance
    
    while len(above) < 3:
        last = above[-1]["price"] if above else current_price
        synth_price = round(last + step, 2)
        above.append({
            "price": synth_price,
            "label": f"Ext. R{len(above)+1}",
            "type": "synthetic",
            "pct": round((synth_price - current_price) / current_price * 100, 3),
        })
    
    while len(below) < 3:
        last = below[-1]["price"] if below else current_price
        synth_price = round(last - step, 2)
        below.append({
            "price": synth_price,
            "label": f"Ext. S{len(below)+1}",
            "type": "synthetic",
            "pct": round((synth_price - current_price) / current_price * 100, 3),
        })
    
    return {
        "above": above[:3],
        "below": below[:3],
        "pp": pp_level,
    }


def _interpret_position(combined: dict, current_price: float, pivot: dict) -> str:
    """Genera interpretación de la posición actual relativa a los niveles."""
    if not pivot:
        return "Sin datos diarios para calcular niveles"
    
    pp = pivot.get("PP", 0)
    r1 = pivot.get("R1", 0)
    s1 = pivot.get("S1", 0)
    prev_high = pivot.get("prev_high", 0)
    prev_low = pivot.get("prev_low", 0)
    
    if current_price > prev_high:
        return f"🚀 Por ENCIMA del máximo de ayer ({prev_high:.2f}) — momentum alcista fuerte"
    elif current_price < prev_low:
        return f"📉 Por DEBAJO del mínimo de ayer ({prev_low:.2f}) — presión bajista fuerte"
    elif current_price > r1:
        return f"📈 Sobre R1 ({r1:.2f}), acercándose a resistencia — buscar confirmación"
    elif current_price < s1:
        return f"📉 Bajo S1 ({s1:.2f}), acercándose a soporte — buscar rebote"
    elif current_price > pp:
        return f"➡️ Sobre Pivot ({pp:.2f}) — sesgo moderadamente alcista"
    elif current_price < pp:
        return f"➡️ Bajo Pivot ({pp:.2f}) — sesgo moderadamente bajista"
    else:
        return f"⚖️ En el Pivot exacto ({pp:.2f}) — esperar definición"


def _empty_levels() -> dict:
    """Retorna estructura vacía cuando no hay datos."""
    return {
        "pivot": {},
        "swings": {"resistances": [], "supports": []},
        "combined": {"above": [], "below": [], "pp": None},
        "current_price": 0,
        "position": "Sin datos disponibles",
    }
