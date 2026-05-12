"""
SENTINEL v3 — Fuente de Datos via Yahoo Finance (yfinance)
Datos reales de mercado sin necesidad de MT5.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import time
import logging

logger = logging.getLogger("sentinel.data")

# Mapeo de símbolos internos a tickers de Yahoo Finance
YAHOO_TICKERS = {
    "USDCLP":   "CLP=X",
    "USDX":     "DX-Y.NYB",
    "COPPER":   "HG=F",
    "WTI":      "CL=F",
    "USDMXN":   "MXN=X",
    "USDBRL":   "BRL=X",
    "AUDUSD":   "AUDUSD=X",
    "USDCNH":   "CNH=X",
    "US500":    "^GSPC",
}

# Mapeo de timeframe en minutos a interval de yfinance
YF_INTERVALS = {
    1:    "1m",
    5:    "5m",
    15:   "15m",
    30:   "30m",
    60:   "60m",
    240:  "1d",   # yfinance no soporta 4h; usamos 1d como proxy
    1440: "1d",
}

# Periodo máximo de lookback por intervalo
YF_PERIODS = {
    "1m":  "7d",
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "60d",
    "1d":  "1y",
}


class DataFeed:
    """Fuente de datos unificada via Yahoo Finance."""

    def __init__(self, mode: str = "auto"):
        self.mode = "yfinance"
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 30  # 30 segundos de cache (yfinance tiene rate limits)
        self.mt5_connected = False
        logger.info("📡 Modo Yahoo Finance activado — datos reales de mercado")

    def get_data(self, symbol: str, timeframe_minutes: int = 15,
                  bars: int = 200) -> pd.DataFrame:
        cache_key = f"{symbol}_{timeframe_minutes}_{bars}"
        now = time.time()

        if cache_key in self._cache:
            if now - self._cache_time[cache_key] < self._cache_ttl:
                return self._cache[cache_key]

        ticker = YAHOO_TICKERS.get(symbol, symbol)
        interval = YF_INTERVALS.get(timeframe_minutes, "15m")
        period = YF_PERIODS.get(interval, "60d")

        try:
            data = yf.Ticker(ticker).history(period=period, interval=interval)
            if data.empty:
                logger.warning(f"Sin datos yfinance para {symbol} ({ticker})")
                return pd.DataFrame()

            df = data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            df.columns = ['open', 'high', 'low', 'close', 'volume']
            df = df.tail(bars)

            self._cache[cache_key] = df
            self._cache_time[cache_key] = now
            return df

        except Exception as e:
            logger.error(f"Error yfinance {symbol}: {e}")
            return pd.DataFrame()

    def get_current_price(self, symbol: str) -> dict:
        df = self.get_data(symbol, 5, 10)
        if not df.empty:
            last = df['close'].iloc[-1]
            spread = last * 0.001
            return {
                "bid": last,
                "ask": last + spread,
                "spread": spread,
                "time": datetime.now(),
            }
        return {"bid": 0, "ask": 0, "spread": 0, "time": None}

    def get_symbol_info(self, symbol: str) -> dict:
        return {"name": symbol, "point": 0.01, "digits": 2}

    def get_all_data(self, timeframe_minutes: int = 15,
                      bars: int = 200) -> dict:
        from sentinel.config import SYMBOLS
        all_data = {}
        for key, symbol in SYMBOLS.items():
            df = self.get_data(symbol, timeframe_minutes, bars)
            if not df.empty:
                all_data[key] = df
        return all_data

    def get_status(self) -> dict:
        return {
            "mode": "yfinance",
            "mt5_connected": False,
            "cache_size": len(self._cache),
        }

    def shutdown(self):
        pass
