"""
SENTINEL v3 — Motor de Correlaciones Cross-Asset
Calcula correlaciones rolling entre USDCLP y los 8 instrumentos monitoreados.
Detecta divergencias y quiebres de correlación.
"""

import pandas as pd
import numpy as np
import logging
from sentinel.config import (
    EXPECTED_CORRELATIONS, CORRELATION_WINDOW, 
    CORRELATION_BREAK_THRESHOLD, DIVERGENCE_THRESHOLD
)

logger = logging.getLogger("sentinel.correlation")


def calculate_correlation_matrix(all_data: dict, window: int = None) -> pd.DataFrame:
    """
    Calcula la matriz de correlación rolling entre todos los instrumentos.
    
    Args:
        all_data: Dict[str, DataFrame] con datos OHLCV por instrumento
        window: Ventana para rolling correlation (default: config)
    
    Returns:
        DataFrame con correlaciones actuales
    """
    if window is None:
        window = CORRELATION_WINDOW
    
    # Extraer retornos logarítmicos del close de cada instrumento
    # NOTA: Yahoo Finance devuelve timestamps diferentes por ticker,
    # por lo que necesitamos normalizar los índices antes de alinear.
    closes = {}
    for key, df in all_data.items():
        if not df.empty and 'close' in df.columns:
            s = df['close'].copy()
            # Normalizar: si tiene timezone, convertir a UTC y quitar tz
            if hasattr(s.index, 'tz') and s.index.tz is not None:
                s.index = s.index.tz_convert('UTC').tz_localize(None)
            # Redondear timestamps a la hora más cercana para alinear
            s.index = s.index.round('h')
            # Eliminar duplicados por redondeo (quedarse con el último)
            s = s[~s.index.duplicated(keep='last')]
            closes[key] = s
    
    if len(closes) < 2:
        return pd.DataFrame()
    
    # Crear DataFrame alineado por inner join en timestamps normalizados
    closes_df = pd.DataFrame(closes)
    closes_df = closes_df.dropna()
    
    if len(closes_df) < 5:
        return pd.DataFrame()
    
    # Calcular retornos logarítmicos sobre los datos ya alineados
    returns_df = np.log(closes_df / closes_df.shift(1)).dropna()
    
    if len(returns_df) < window:
        # Si no hay suficientes datos, usar toda la ventana disponible
        return returns_df.corr()
    
    # Correlación de los últimos N periodos
    recent = returns_df.tail(window)
    corr_matrix = recent.corr()
    
    return corr_matrix


def calculate_target_correlations(all_data: dict, 
                                    target_key: str = "target") -> dict:
    """
    Calcula correlación de cada instrumento vs USDCLP (target).
    
    Returns:
        Dict con:
        - correlations: dict de correlaciones actuales
        - divergences: dict de divergencias vs esperado
        - breaks: lista de instrumentos con correlación rota
        - score: score de correlación 0-100
    """
    corr_matrix = calculate_correlation_matrix(all_data)
    
    if corr_matrix.empty or target_key not in corr_matrix.columns:
        return {
            "correlations": {},
            "divergences": {},
            "breaks": [],
            "score": 50,  # Neutral si no hay datos
            "direction": "NEUTRAL",
            "alerts": [],
        }
    
    target_corr = corr_matrix[target_key]
    
    correlations = {}
    divergences = {}
    breaks = []
    alerts = []
    
    for key in EXPECTED_CORRELATIONS:
        if key in target_corr.index and key != target_key:
            actual = target_corr[key]
            expected = EXPECTED_CORRELATIONS[key]
            
            correlations[key] = round(actual, 3)
            
            # Calcular divergencia vs esperado
            div = actual - expected
            divergences[key] = round(div, 3)
            
            # Detectar quiebre de correlación
            if abs(actual) < CORRELATION_BREAK_THRESHOLD and abs(expected) > 0.4:
                breaks.append(key)
                alerts.append(f"⚠️ QUIEBRE: {key} correlación actual={actual:.2f} vs esperada={expected:.2f}")
    
    # Calcular score de correlación (0-100)
    score = _calculate_correlation_score(all_data, correlations)
    direction = _determine_correlation_direction(all_data, correlations)
    
    return {
        "correlations": correlations,
        "divergences": divergences,
        "breaks": breaks,
        "score": score,
        "direction": direction,
        "alerts": alerts,
    }


def _calculate_correlation_score(all_data: dict, correlations: dict) -> float:
    """
    Calcula un score 0-100 basado en si las correlaciones confirman
    una dirección clara para USDCLP.
    
    Score alto = alta confluencia de señales correlacionadas
    Score bajo = señales contradictorias o correlaciones rotas
    """
    if not correlations or not all_data:
        return 50
    
    votes = []
    weights = {
        "dxy": 3.0,      # DXY es el driver principal
        "copper": 2.5,    # Cobre es crucial para Chile
        "usdmxn": 1.5,    # Peer LATAM
        "usdbrl": 1.5,    # Peer LATAM
        "wti": 1.0,
        "audusd": 1.0,
        "usdcnh": 1.0,
        "sp500": 0.5,
    }
    
    for key in correlations:
        if key not in all_data or all_data[key].empty:
            continue
        
        df = all_data[key]
        if len(df) < 10:
            continue
        
        # Retorno reciente del instrumento (últimas 5 velas)
        recent_return = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) if len(df) >= 5 else 0
        
        # Según la correlación esperada, ¿qué dirección sugiere para USDCLP?
        expected = EXPECTED_CORRELATIONS.get(key, 0)
        if expected > 0:
            # Correlación directa: si sube → USDCLP debería subir
            vote = 1 if recent_return > 0 else -1
        elif expected < 0:
            # Correlación inversa: si sube → USDCLP debería bajar
            vote = -1 if recent_return > 0 else 1
        else:
            vote = 0
        
        weight = weights.get(key, 1.0)
        votes.append(vote * weight)
    
    if not votes:
        return 50
    
    # Normalizar: si todos votan lo mismo → score alto
    total_weight = sum(weights.get(k, 1.0) for k in correlations if k in all_data)
    if total_weight == 0:
        return 50
    
    consensus = sum(votes) / total_weight
    # consensus va de -1 a +1. Convertir a 0-100
    # Alta confluencia (consensus cercano a ±1) → score alto
    score = 50 + (abs(consensus) * 50)
    
    return round(min(100, max(0, score)), 1)


def _determine_correlation_direction(all_data: dict, correlations: dict) -> str:
    """
    Determina la dirección sugerida por las correlaciones.
    LONG = correlaciones sugieren que USDCLP suba
    SHORT = correlaciones sugieren que USDCLP baje
    NEUTRAL = sin consenso claro
    """
    if not correlations or not all_data:
        return "NEUTRAL"
    
    bull_score = 0
    bear_score = 0
    
    for key in correlations:
        if key not in all_data or all_data[key].empty:
            continue
        
        df = all_data[key]
        if len(df) < 5:
            continue
        
        recent_return = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) if len(df) >= 5 else 0
        expected = EXPECTED_CORRELATIONS.get(key, 0)
        
        if expected > 0:
            if recent_return > DIVERGENCE_THRESHOLD:
                bull_score += abs(expected)
            elif recent_return < -DIVERGENCE_THRESHOLD:
                bear_score += abs(expected)
        elif expected < 0:
            if recent_return > DIVERGENCE_THRESHOLD:
                bear_score += abs(expected)
            elif recent_return < -DIVERGENCE_THRESHOLD:
                bull_score += abs(expected)
    
    diff = bull_score - bear_score
    if diff > 0.5:
        return "LONG"
    elif diff < -0.5:
        return "SHORT"
    return "NEUTRAL"


def detect_divergence(all_data: dict, target_key: str = "target") -> list:
    """
    Detecta divergencias cross-asset: cuando USDCLP NO se mueve
    en la dirección esperada según los otros instrumentos.
    
    Esta es la ventaja competitiva principal del sistema.
    
    Returns:
        Lista de divergencias detectadas con descripción.
    """
    divergences = []
    
    if target_key not in all_data or all_data[target_key].empty:
        return divergences
    
    target_df = all_data[target_key]
    if len(target_df) < 10:
        return divergences
    
    target_return = (target_df['close'].iloc[-1] / target_df['close'].iloc[-5] - 1)
    
    for key, expected_corr in EXPECTED_CORRELATIONS.items():
        if key not in all_data or all_data[key].empty:
            continue
        
        df = all_data[key]
        if len(df) < 5:
            continue
        
        other_return = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1)
        
        # Retorno esperado de USDCLP basado en este instrumento
        expected_target_direction = other_return * np.sign(expected_corr)
        
        # ¿Hay divergencia?
        if abs(other_return) > DIVERGENCE_THRESHOLD:
            if np.sign(expected_target_direction) != np.sign(target_return):
                magnitude = abs(other_return)
                direction = "SUBIR" if expected_target_direction > 0 else "BAJAR"
                
                divergences.append({
                    "instrument": key,
                    "instrument_move": f"{other_return*100:.2f}%",
                    "expected_usdclp": direction,
                    "actual_usdclp": f"{target_return*100:.2f}%",
                    "magnitude": magnitude,
                    "description": (
                        f"🔍 DIVERGENCIA: {key.upper()} se movió {other_return*100:+.2f}% "
                        f"→ USDCLP debería {direction} pero fue {target_return*100:+.2f}%"
                    )
                })
    
    # Ordenar por magnitud (más significativas primero)
    divergences.sort(key=lambda x: x['magnitude'], reverse=True)
    
    return divergences
