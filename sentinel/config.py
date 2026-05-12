"""
SENTINEL v3 — Configuración Central
Sistema de Trading USD/CLP
"""

from dataclasses import dataclass, field
from typing import Dict, List
import datetime

# ══════════════════════════════════════════════════════════════
# MODO DE DATOS
# ══════════════════════════════════════════════════════════════
# "mt5"  = MetaTrader 5 (Capitaria) — datos en tiempo real
# "api"  = Alpha Vantage / fallback — datos con delay
DATA_MODE = "mt5"  # Cambiar a "api" si MT5 no está disponible

# ══════════════════════════════════════════════════════════════
# INSTRUMENTOS MONITOREADOS
# ══════════════════════════════════════════════════════════════
# IMPORTANTE: Estos nombres deben coincidir EXACTAMENTE con los
# símbolos de Capitaria en MT5. Si no coinciden, cambiarlos aquí.

SYMBOLS = {
    "target":       "USDCLP",       # Par principal
    "dxy":          "USDX",         # Dollar Index
    "copper":       "COPPER",       # Cobre
    "wti":          "WTI",          # Petróleo
    "usdmxn":       "USDMXN",       # Peso mexicano
    "usdbrl":       "USDBRL",       # Real brasileño
    "audusd":       "AUDUSD",       # Dólar australiano
    "usdcnh":       "USDCNH",       # Yuan offshore
    "sp500":        "US500",        # S&P 500
}

# Símbolos para Alpha Vantage (fallback)
SYMBOLS_API = {
    "target":       "USD/CLP",
    "dxy":          "DX-Y.NYB",     # No disponible directamente, usar proxy
    "copper":       "HG=F",
    "wti":          "CL=F",
    "usdmxn":       "USD/MXN",
    "usdbrl":       "USD/BRL",
    "audusd":       "AUD/USD",
    "usdcnh":       "USD/CNH",
    "sp500":        "SPY",
}

# ══════════════════════════════════════════════════════════════
# CORRELACIONES ESPERADAS CON USDCLP
# ══════════════════════════════════════════════════════════════
# +1 = se mueven juntos, -1 = se mueven opuesto
EXPECTED_CORRELATIONS = {
    "dxy":      +0.75,   # DXY sube → USDCLP sube (DIRECTA FUERTE)
    "copper":   -0.70,   # Cobre sube → CLP se fortalece → USDCLP baja (INVERSA FUERTE)
    "wti":      +0.40,   # WTI sube → Chile importador → CLP baja → USDCLP sube (DIRECTA MODERADA)
    "usdmxn":   +0.60,   # Co-movimiento LATAM risk (DIRECTA)
    "usdbrl":   +0.55,   # Co-movimiento LATAM risk (DIRECTA)
    "audusd":   -0.50,   # AUD proxy commodities (INVERSA — AUD sube cuando commodities suben)
    "usdcnh":   +0.45,   # CNH débil → menos demanda China → Cobre baja (DIRECTA)
    "sp500":    -0.30,   # Risk-on → EM se fortalecen → USDCLP baja (INVERSA DÉBIL)
}

# ══════════════════════════════════════════════════════════════
# TIMEFRAMES
# ══════════════════════════════════════════════════════════════
TIMEFRAMES = {
    "M1":   1,       # Ejecución inmediata
    "M5":   5,       # Ejecución
    "M15":  15,      # Táctico / tendencia corta
}
BARS_TO_FETCH = 200  # Velas a descargar por timeframe

# ══════════════════════════════════════════════════════════════
# GESTIÓN DE RIESGO
# ══════════════════════════════════════════════════════════════
@dataclass
class RiskConfig:
    capital_clp: float = 1_500_000       # Capital total en CLP
    risk_per_trade_pct: float = 0.01     # 1% por trade
    max_daily_loss_pct: float = 0.03     # 3% máximo pérdida diaria
    max_trades_per_day: int = 3          # Máximo trades por día
    min_rr_ratio: float = 1.5            # Mínimo Risk:Reward
    atr_sl_multiplier: float = 2.0       # ATR × 2.0 para Stop Loss
    atr_tp_multiplier: float = 3.0       # ATR × 3.0 para Take Profit
    consecutive_losses_pause: int = 2    # Pausar después de N pérdidas seguidas
    pause_duration_minutes: int = 120    # Duración de la pausa (2 horas)

RISK = RiskConfig()

# ══════════════════════════════════════════════════════════════
# PESOS DEL SCORE COMPUESTO
# ══════════════════════════════════════════════════════════════
@dataclass
class ScoreWeights:
    technical: float = 0.30      # 30% — Indicadores técnicos
    correlation: float = 0.45    # 45% — Motor de correlaciones
    risk: float = 0.20           # 20% — Condiciones de riesgo/contexto
    dom: float = 0.05            # 5%  — DOM bancario (input manual)

WEIGHTS = ScoreWeights()

# Umbral para generar alerta
SCORE_ALERT_THRESHOLD = 65    # Score ≥ 65 → alerta
SCORE_STRONG_THRESHOLD = 75   # Score ≥ 75 → señal fuerte

# ══════════════════════════════════════════════════════════════
# INDICADORES TÉCNICOS
# ══════════════════════════════════════════════════════════════
@dataclass
class IndicatorParams:
    ema_fast: int = 9
    ema_mid: int = 21
    ema_slow: int = 50
    ema_trend: int = 200
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14

INDICATORS = IndicatorParams()

# ══════════════════════════════════════════════════════════════
# CORRELACIONES
# ══════════════════════════════════════════════════════════════
CORRELATION_WINDOW = 50          # Periodos para rolling correlation
CORRELATION_BREAK_THRESHOLD = 0.3  # Si correlación cae debajo de esto → alerta
DIVERGENCE_THRESHOLD = 0.02      # 2% de divergencia con lo esperado → señal

# ══════════════════════════════════════════════════════════════
# HORARIO OPERATIVO (Chile CLT = UTC-4)
# ══════════════════════════════════════════════════════════════
MARKET_OPEN = datetime.time(9, 30)    # 09:30 CLT
MARKET_CLOSE = datetime.time(14, 0)   # 14:00 CLT (ventana primaria)
MARKET_HARD_CLOSE = datetime.time(15, 30)  # 15:30 CLT (cierre absoluto)
NEWS_BUFFER_MINUTES = 30              # No operar 30 min antes/después de noticias

# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════
DASHBOARD_REFRESH_SECONDS = 10   # Cada cuántos segundos actualizar
DASHBOARD_LANGUAGE = "es"        # Español

# ══════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
JOURNAL_PATH = os.path.join(DATA_DIR, "trades_journal.csv")
