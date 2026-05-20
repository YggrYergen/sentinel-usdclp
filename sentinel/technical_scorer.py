"""
SENTINEL v3 — Score Técnico Multi-Indicador
Combina indicadores técnicos en un score 0-100.
"""
import pandas as pd
import numpy as np
from sentinel.indicators import calculate_all, get_latest_signals
from sentinel.config import INDICATORS as IND

def calculate_technical_score(df: pd.DataFrame, normalize_macd: bool = False) -> dict:
    if df.empty or len(df) < 50:
        return {"score": 50, "direction": "NEUTRAL", "details": {}, "signals": {}}
    df_ind = calculate_all(df)
    signals = get_latest_signals(df_ind)
    if not signals:
        return {"score": 50, "direction": "NEUTRAL", "details": {}, "signals": {}}
    details = {}
    details["ema"] = _score_ema(signals)
    details["rsi"] = _score_rsi(signals)
    # M1/M2: normalize MACD histogram by ATR to avoid saturation on high-price instruments
    atr = signals.get("atr", None) if normalize_macd else None
    details["macd"] = _score_macd(signals, atr=atr)
    details["bb"] = _score_bb(signals)
    details["pa"] = _score_pa(df_ind)
    w = {"ema": 0.30, "rsi": 0.20, "macd": 0.25, "bb": 0.15, "pa": 0.10}
    composite = sum(details[k]["score"] * w[k] for k in w)
    composite = round(min(100, max(0, composite)), 1)
    votes = sum(details[k]["vote"] for k in details)
    direction = "LONG" if votes > 1 else ("SHORT" if votes < -1 else "NEUTRAL")
    return {"score": composite, "direction": direction, "details": details, "signals": signals}

def calculate_multi_tf_score(data_feed, symbol: str) -> dict:
    from sentinel.config import TIMEFRAMES, BARS_TO_FETCH
    tf_scores = {}
    tf_w = {"M15": 0.10, "M5": 0.20, "M2": 0.35, "M1": 0.35}
    for tf_name, tf_min in TIMEFRAMES.items():
        df = data_feed.get_data(symbol, tf_min, BARS_TO_FETCH)
        # ATR-normalize MACD for ALL TFs — raw histogram saturates on high-price
        # instruments like USDCLP (e.g. h=1.5 → 60+1500=clamp→100 = always maxed)
        tf_scores[tf_name] = calculate_technical_score(df, normalize_macd=True)
    wscore = sum(tf_scores.get(t, {}).get("score", 50) * tw for t, tw in tf_w.items())
    anchor_dir = tf_scores.get("M15", {}).get("direction", "NEUTRAL")
    dirs = [tf_scores[t]["direction"] for t in tf_scores]
    confluence = max(sum(1 for d in dirs if d == "LONG"), sum(1 for d in dirs if d == "SHORT"))
    
    # Detectar divergencias RSI entre timeframes
    rsi_divs = detect_rsi_divergences(tf_scores)
    
    return {
        "composite_score": round(wscore, 1),
        "h4_direction": anchor_dir,  # Mantener key por compatibilidad
        "confluence": confluence,
        "total_timeframes": len(tf_scores),
        "tf_scores": tf_scores,
        "rsi_divergences": rsi_divs,
    }


def detect_rsi_divergences(tf_scores: dict) -> list:
    """
    Detecta divergencias de RSI entre timeframes.
    
    Ejemplo: Si RSI en M1=75 (sobrecompra) pero RSI en M15=45 (neutral),
    hay una divergencia temporal que sugiere que el movimiento de corto
    plazo puede revertir hacia la tendencia del timeframe mayor.
    
    Magnitud: Diferencia absoluta entre los RSI. >20 = fuerte, >10 = moderada.
    """
    divergences = []
    
    # Extraer RSI de cada timeframe
    rsi_values = {}
    for tf_name, tf_data in tf_scores.items():
        signals = tf_data.get("signals", {})
        rsi = signals.get("rsi", None)
        if rsi is not None and rsi > 0:
            rsi_values[tf_name] = round(rsi, 1)
    
    if len(rsi_values) < 2:
        return divergences
    
    # Ordenar timeframes de menor a mayor
    tf_order = ["M1", "M2", "M5", "M15"]
    ordered = [(tf, rsi_values[tf]) for tf in tf_order if tf in rsi_values]
    
    # Comparar cada par adyacente de timeframes
    for i in range(len(ordered) - 1):
        tf_fast, rsi_fast = ordered[i]
        tf_slow, rsi_slow = ordered[i + 1]
        
        diff = rsi_fast - rsi_slow
        abs_diff = abs(diff)
        
        if abs_diff < 10:
            continue  # Divergencia insignificante
        
        # Clasificar magnitud
        if abs_diff >= 25:
            magnitude = "🔴 FUERTE"
            mag_score = 3
        elif abs_diff >= 15:
            magnitude = "🟡 MODERADA"
            mag_score = 2
        else:
            magnitude = "🟢 LEVE"
            mag_score = 1
        
        # Interpretar la divergencia
        if rsi_fast > 70 and rsi_slow < 50:
            interpretation = f"{tf_fast} en SOBRECOMPRA pero {tf_slow} neutral → probable retroceso"
        elif rsi_fast < 30 and rsi_slow > 50:
            interpretation = f"{tf_fast} en SOBREVENTA pero {tf_slow} neutral → probable rebote"
        elif diff > 0:
            interpretation = f"{tf_fast} más alcista que {tf_slow} → momentum acelerando"
        else:
            interpretation = f"{tf_fast} más bajista que {tf_slow} → momentum desacelerando"
        
        divergences.append({
            "tf_fast": tf_fast,
            "tf_slow": tf_slow,
            "rsi_fast": rsi_fast,
            "rsi_slow": rsi_slow,
            "diff": round(diff, 1),
            "magnitude": magnitude,
            "mag_score": mag_score,
            "interpretation": interpretation,
            "description": (
                f"RSI {tf_fast}={rsi_fast:.0f} vs {tf_slow}={rsi_slow:.0f} "
                f"(Δ{diff:+.0f}) — {magnitude} — {interpretation}"
            )
        })
    
    # Ordenar por magnitud (más significativas primero)
    divergences.sort(key=lambda x: x["mag_score"], reverse=True)
    return divergences


def _score_ema(s):
    p, e9, e21, e50 = s.get("price",0), s.get("ema_9",0), s.get("ema_21",0), s.get("ema_50",0)
    if p == 0 or e9 == 0:
        return {"score": 50, "vote": 0, "detail": "Sin datos"}
    if e9 > e21 > e50 > 0:
        sc, v = 85, 1
    elif e9 < e21 < e50 and e50 > 0:
        sc, v = 15, -1
    elif sum(1 for e in [e9,e21,e50] if p > e and e > 0) >= 2:
        sc, v = 65, 1
    elif sum(1 for e in [e9,e21,e50] if p < e and e > 0) >= 2:
        sc, v = 35, -1
    else:
        sc, v = 50, 0
    cross = s.get("ema_cross", 0)
    if cross == 1: sc = min(100, sc + 15); v = 1
    elif cross == -1: sc = max(0, sc - 15); v = -1
    return {"score": sc, "vote": v, "detail": f"EMA alineación"}

def _score_rsi(s):
    rsi = s.get("rsi", 50)
    if rsi >= 70: return {"score": 30, "vote": -1, "detail": f"RSI={rsi:.1f} OB"}
    elif rsi <= 30: return {"score": 70, "vote": 1, "detail": f"RSI={rsi:.1f} OS"}
    elif rsi > 50: return {"score": round(55 + (rsi-50)*0.5, 1), "vote": 1, "detail": f"RSI={rsi:.1f}"}
    else: return {"score": round(45 - (50-rsi)*0.5, 1), "vote": -1, "detail": f"RSI={rsi:.1f}"}

def _score_macd(s, atr=None):
    h = s.get("macd_histogram", 0)
    if atr and atr > 0:
        # ATR-normalized: h/ATR gives ~-1 to +1 range, × 40 maps to ±40 around 50
        h_norm = h / atr
        sc = round(min(100, max(0, 50 + h_norm * 40)), 1)
        v = 1 if h > 0 else (-1 if h < 0 else 0)
        return {"score": sc, "vote": v, "detail": f"MACD {'+'if h>0 else ''}{h:.4f} (h/ATR={h_norm:+.2f})"}
    # Original behavior (M5/M15 — untouched)
    if h > 0: return {"score": round(min(100, 60 + abs(h)*1000), 1), "vote": 1, "detail": f"MACD+ {h:.4f}"}
    elif h < 0: return {"score": round(max(0, 40 - abs(h)*1000), 1), "vote": -1, "detail": f"MACD- {h:.4f}"}
    return {"score": 50, "vote": 0, "detail": "MACD neutral"}

def _score_bb(s):
    bp = s.get("bb_pct", 0.5)
    if bp > 0.95: return {"score": 25, "vote": -1, "detail": f"BB alta {bp:.2f}"}
    elif bp < 0.05: return {"score": 75, "vote": 1, "detail": f"BB baja {bp:.2f}"}
    elif bp > 0.7: return {"score": 40, "vote": 0, "detail": f"BB {bp:.2f}"}
    elif bp < 0.3: return {"score": 60, "vote": 0, "detail": f"BB {bp:.2f}"}
    return {"score": 50, "vote": 0, "detail": f"BB centro {bp:.2f}"}

def _score_pa(df):
    if len(df) < 5:
        return {"score": 50, "vote": 0, "detail": "Sin datos"}
    last = df.iloc[-1]
    body = last['close'] - last['open']
    rng = last['high'] - last['low']
    if rng == 0:
        return {"score": 50, "vote": 0, "detail": "Sin rango"}
    bp = abs(body) / rng
    if bp > 0.7:
        if body > 0: return {"score": 70, "vote": 1, "detail": "Vela alcista fuerte"}
        else: return {"score": 30, "vote": -1, "detail": "Vela bajista fuerte"}
    if body > 0: return {"score": 55, "vote": 0, "detail": f"Vela normal {bp:.0%}"}
    return {"score": 45, "vote": 0, "detail": f"Vela normal {bp:.0%}"}
