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
# símbolos de Capitaria en MT5. Verificados el 2026-05-13.

SYMBOLS = {
    "target":       "USDCLP",         # Par principal
    "dxy":          "USDX_Jun26",     # Dollar Index (futuro)
    "copper":       "Cobre_Jul26",    # Cobre (futuro)
    "wti":          "WTI",            # Petróleo
    "usdmxn":       "USDMXN",         # Peso mexicano
    "usdbrl":       "USDBRL",         # Real brasileño
    "audusd":       "AUDUSD",         # Dólar australiano
    "usdcnh":       "USDCNH",         # Yuan offshore
    "sp500":        "SP",             # S&P 500 (CFD)
}

# Símbolos para Yahoo Finance (fallback cuando MT5 no está disponible)
SYMBOLS_YAHOO = {
    "USDCLP":       "CLP=X",
    "USDX_Jun26":   "DX-Y.NYB",
    "Cobre_Jul26":  "HG=F",
    "WTI":          "CL=F",
    "USDMXN":       "MXN=X",
    "USDBRL":       "BRL=X",
    "AUDUSD":       "AUDUSD=X",
    "USDCNH":       "CNH=X",
    "SP":           "^GSPC",
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
# GOLD (XAUUSD) — Instrument config
# ══════════════════════════════════════════════════════════════
SYMBOLS_GOLD = {
    "target":   "XAUUSD",
    "dxy":      "USDX_Jun26",
    "silver":   "XAGUSD",
    "vix":      "VIX_Jun26",
    "wti":      "WTI",
    "eurusd":   "EURUSD",
    "sp500":    "SP",
    "usdjpy":   "USDJPY",
    "copper":   "Cobre_Jul26",
}
EXPECTED_CORRELATIONS_GOLD = {
    "dxy":      -0.70,   # DXY up → Gold down (denominator effect)
    "silver":   +0.85,   # Peer precious metal — strongest correlation
    "vix":      +0.35,   # Fear rising → safety demand → Gold up
    "wti":      +0.35,   # Oil up → inflation hedge → Gold up
    "eurusd":   +0.45,   # EUR up (dollar weak) → Gold up
    "sp500":    -0.15,   # Risk-on → less gold demand (weak, near-zero)
    "usdjpy":   -0.60,   # USD/JPY up → risk-on → Gold down
    "copper":   +0.30,   # Shared macro — weak positive
}
ASSET_WEIGHTS_GOLD = {
    "dxy":      3.0,
    "silver":   2.5,
    "vix":      2.0,
    "wti":      1.5,
    "eurusd":   1.5,
    "sp500":    1.0,
    "usdjpy":   2.0,
    "copper":   1.0,
}

# ══════════════════════════════════════════════════════════════
# NASDAQ 100 (NQ100) — Instrument config
# ══════════════════════════════════════════════════════════════
SYMBOLS_NASDAQ = {
    "target":   "NQ100",
    "sp500":    "SP",
    "vix":      "VIX_Jun26",
    "dxy":      "USDX_Jun26",
    "usdjpy":   "USDJPY",
    "bitcoin":  "BTCUSD",
    "wti":      "WTI",
    "eurusd":   "EURUSD",
    "gold":     "XAUUSD",
}
EXPECTED_CORRELATIONS_NASDAQ = {
    "sp500":    +0.92,   # Mechanical — NASDAQ is subset of broad equities
    "vix":      -0.80,   # VIX up → growth selloff → NASDAQ down
    "dxy":      -0.50,   # Dollar up → tech earnings hurt → NASDAQ down
    "usdjpy":   +0.45,   # Carry trade intact → risk-on → NASDAQ up
    "bitcoin":  +0.55,   # Institutional linkage — shared macro (unstable)
    "wti":      -0.35,   # Oil up → inflation → rates up → NASDAQ down
    "eurusd":   +0.35,   # EUR up → dollar weak → risk-on → NASDAQ up
    "gold":     -0.15,   # Gold up → safety flight → NASDAQ down (weak)
}
ASSET_WEIGHTS_NASDAQ = {
    "sp500":    3.0,
    "vix":      3.0,
    "dxy":      2.5,
    "usdjpy":   2.0,
    "bitcoin":  1.5,
    "wti":      1.5,
    "eurusd":   1.0,
    "gold":     0.5,
}

# ══════════════════════════════════════════════════════════════
# TIMEFRAMES
# ══════════════════════════════════════════════════════════════
TIMEFRAMES = {
    "M1":   1,       # Micro-momentum
    "M2":   2,       # Transición corta
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
    technical: float = 0.50      # 50% — Indicadores técnicos
    correlation: float = 0.50    # 50% — Correlaciones cross-asset (mundo)

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
DASHBOARD_REFRESH_SECONDS = 1.5  # Faster refresh — safe for Capitaria data requests
DASHBOARD_LANGUAGE = "es"        # Español

# ══════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
JOURNAL_PATH = os.path.join(DATA_DIR, "trades_journal.csv")
