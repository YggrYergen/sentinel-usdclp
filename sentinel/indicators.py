"""
SENTINEL v3 — Cálculo de Indicadores Técnicos
Calcula EMA, RSI, MACD, Bollinger Bands, ATR para un DataFrame OHLCV.
"""

import pandas as pd
import numpy as np
import ta
from sentinel.config import INDICATORS as IND


def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula todos los indicadores técnicos sobre un DataFrame OHLCV.
    
    Args:
        df: DataFrame con columnas [open, high, low, close, volume]
    
    Returns:
        DataFrame original + columnas de indicadores
    """
    if df.empty or len(df) < 50:
        return df
    
    result = df.copy()
    
    # ── EMAs ──────────────────────────────────────────────
    result['ema_9'] = ta.trend.ema_indicator(result['close'], window=IND.ema_fast)
    result['ema_21'] = ta.trend.ema_indicator(result['close'], window=IND.ema_mid)
    result['ema_50'] = ta.trend.ema_indicator(result['close'], window=IND.ema_slow)
    if len(result) >= IND.ema_trend:
        result['ema_200'] = ta.trend.ema_indicator(result['close'], window=IND.ema_trend)
    else:
        result['ema_200'] = np.nan
    
    # ── RSI ───────────────────────────────────────────────
    result['rsi'] = ta.momentum.rsi(result['close'], window=IND.rsi_period)
    
    # ── MACD ──────────────────────────────────────────────
    macd = ta.trend.MACD(result['close'], 
                          window_slow=IND.macd_slow, 
                          window_fast=IND.macd_fast, 
                          window_sign=IND.macd_signal)
    result['macd'] = macd.macd()
    result['macd_signal'] = macd.macd_signal()
    result['macd_histogram'] = macd.macd_diff()
    
    # ── Bollinger Bands ───────────────────────────────────
    bb = ta.volatility.BollingerBands(result['close'], 
                                       window=IND.bb_period, 
                                       window_dev=IND.bb_std)
    result['bb_upper'] = bb.bollinger_hband()
    result['bb_middle'] = bb.bollinger_mavg()
    result['bb_lower'] = bb.bollinger_lband()
    result['bb_pct'] = bb.bollinger_pband()  # % position within bands
    
    # ── ATR ────────────────────────────────────────────────
    result['atr'] = ta.volatility.average_true_range(
        result['high'], result['low'], result['close'], 
        window=IND.atr_period
    )
    
    # ── Señales derivadas ─────────────────────────────────
    
    # Tendencia EMA: 1 = alcista, -1 = bajista, 0 = neutral
    result['ema_trend_signal'] = 0
    if 'ema_50' in result.columns:
        result.loc[result['close'] > result['ema_50'], 'ema_trend_signal'] = 1
        result.loc[result['close'] < result['ema_50'], 'ema_trend_signal'] = -1
    
    # EMA Cross: 9 cruza sobre/bajo 21
    result['ema_cross'] = 0
    mask_bull = (result['ema_9'] > result['ema_21']) & (result['ema_9'].shift(1) <= result['ema_21'].shift(1))
    mask_bear = (result['ema_9'] < result['ema_21']) & (result['ema_9'].shift(1) >= result['ema_21'].shift(1))
    result.loc[mask_bull, 'ema_cross'] = 1
    result.loc[mask_bear, 'ema_cross'] = -1
    
    # RSI zones
    result['rsi_signal'] = 0.0
    result.loc[result['rsi'] > IND.rsi_overbought, 'rsi_signal'] = -1  # Overbought
    result.loc[result['rsi'] < IND.rsi_oversold, 'rsi_signal'] = 1     # Oversold
    # Momentum zone
    result.loc[(result['rsi'] > 50) & (result['rsi'] <= IND.rsi_overbought), 'rsi_signal'] = 0.5
    result.loc[(result['rsi'] < 50) & (result['rsi'] >= IND.rsi_oversold), 'rsi_signal'] = -0.5
    
    # MACD signal
    result['macd_trade_signal'] = 0
    result.loc[result['macd_histogram'] > 0, 'macd_trade_signal'] = 1
    result.loc[result['macd_histogram'] < 0, 'macd_trade_signal'] = -1
    
    return result


def get_latest_signals(df: pd.DataFrame) -> dict:
    """
    Extrae las señales más recientes del último row del DataFrame con indicadores.
    
    Returns:
        Dict con todos los valores actuales de indicadores y señales.
    """
    if df.empty:
        return {}
    
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    
    signals = {
        "price": last.get('close', 0),
        "ema_9": last.get('ema_9', 0),
        "ema_21": last.get('ema_21', 0),
        "ema_50": last.get('ema_50', 0),
        "ema_200": last.get('ema_200', 0),
        "rsi": last.get('rsi', 50),
        "macd": last.get('macd', 0),
        "macd_signal": last.get('macd_signal', 0),
        "macd_histogram": last.get('macd_histogram', 0),
        "bb_upper": last.get('bb_upper', 0),
        "bb_lower": last.get('bb_lower', 0),
        "bb_pct": last.get('bb_pct', 0.5),
        "atr": last.get('atr', 0),
        "ema_trend_signal": last.get('ema_trend_signal', 0),
        "ema_cross": last.get('ema_cross', 0),
        "rsi_signal": last.get('rsi_signal', 0),
        "macd_trade_signal": last.get('macd_trade_signal', 0),
    }
    
    return signals
