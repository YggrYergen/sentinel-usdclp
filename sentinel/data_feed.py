"""
SENTINEL v3.2 — Fuente de Datos Unificada (MT5 + Yahoo Finance fallback)
Usa MetaTrader 5 como fuente primaria (tiempo real) con Yahoo Finance de respaldo.

⚠️ SEGURIDAD: Este módulo es SOLO LECTURA. NO ejecuta trades.
Solo usa: mt5.symbol_info_tick(), mt5.copy_rates_from_pos(), mt5.symbol_select()
"""
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time
import logging

logger = logging.getLogger("sentinel.data")

# Flag to log yfinance import error only once (prevents log flooding)
_yfinance_warning_logged = False

# ══════════════════════════════════════════════════════════════
# Mapeo de timeframes: minutos → constantes MT5
# ══════════════════════════════════════════════════════════════
MT5_TIMEFRAMES = {}  # Se llena dinámicamente cuando MT5 está disponible

# Yahoo Finance fallback mappings
YAHOO_TICKERS = {
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
YF_INTERVALS = {1: "1m", 5: "5m", 15: "15m", 30: "30m", 60: "60m", 240: "1d", 1440: "1d"}
YF_PERIODS = {"1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d", "60m": "60d", "1d": "1y"}


class DataFeed:
    """
    Fuente de datos unificada.
    Intenta MT5 primero (datos en tiempo real).
    Si MT5 no está disponible, usa Yahoo Finance (con delay ~15 min).
    
    ⚠️ SOLO LECTURA — NO ejecuta trades bajo ninguna circunstancia.
    """

    def __init__(self, mode: str = "auto"):
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl_mt5 = 5       # 5 segundos de cache para MT5 (real-time)
        self._cache_ttl_yf = 30       # 30 segundos para Yahoo (rate limited)
        self.mt5_connected = False
        self.mode = "yfinance"  # Default, se cambia si MT5 conecta
        self._mt5 = None
        
        if mode in ("auto", "mt5"):
            self._try_connect_mt5()
        
        if not self.mt5_connected:
            logger.info("📡 Modo Yahoo Finance — datos con delay ~15 min")

    def _try_connect_mt5(self):
        """Intenta conectar a MT5. Solo lectura."""
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
            
            if not mt5.initialize():
                err = mt5.last_error()
                logger.warning(f"MT5 initialize falló: {err}")
                return
            
            acc = mt5.account_info()
            ti = mt5.terminal_info()
            
            if acc and ti:
                self.mt5_connected = True
                self.mode = "mt5"
                
                # Mapear timeframes
                global MT5_TIMEFRAMES
                MT5_TIMEFRAMES = {
                    1:    mt5.TIMEFRAME_M1,
                    2:    mt5.TIMEFRAME_M2,
                    5:    mt5.TIMEFRAME_M5,
                    15:   mt5.TIMEFRAME_M15,
                    30:   mt5.TIMEFRAME_M30,
                    60:   mt5.TIMEFRAME_H1,
                    240:  mt5.TIMEFRAME_H4,
                    1440: mt5.TIMEFRAME_D1,
                }
                
                logger.info(f"✅ MT5 CONECTADO — Login: {acc.login} | Server: {acc.server}")
                logger.info(f"   Build: {ti.build} | Trade allowed: {ti.trade_allowed}")
                logger.info(f"   ⚠️ MODO SOLO LECTURA — no se ejecutan trades")
                
                # Habilitar símbolos necesarios
                self._enable_symbols()
            else:
                logger.warning("MT5 inicializado pero sin info de cuenta")
                
        except ImportError:
            logger.info("MetaTrader5 no instalado — usando Yahoo Finance")
        except Exception as e:
            logger.error(f"Error conectando MT5: {e}")

    def _enable_symbols(self):
        """Habilita todos los símbolos de SENTINEL en Market Watch de MT5."""
        from sentinel.config import SYMBOLS
        mt5 = self._mt5
        for key, symbol in SYMBOLS.items():
            info = mt5.symbol_info(symbol)
            if info and not info.visible:
                mt5.symbol_select(symbol, True)
                logger.info(f"   Habilitado: {symbol}")

    # ══════════════════════════════════════════════════════════
    # API PÚBLICA — get_data, get_current_price, etc.
    # ══════════════════════════════════════════════════════════

    def get_data(self, symbol: str, timeframe_minutes: int = 15,
                  bars: int = 200) -> pd.DataFrame:
        """Obtiene datos OHLCV. MT5 primero, Yahoo Finance fallback."""
        cache_key = f"{symbol}_{timeframe_minutes}_{bars}"
        now = time.time()
        ttl = self._cache_ttl_mt5 if self.mt5_connected else self._cache_ttl_yf

        if cache_key in self._cache:
            if now - self._cache_time[cache_key] < ttl:
                return self._cache[cache_key]

        df = pd.DataFrame()
        
        if self.mt5_connected:
            df = self._get_data_mt5(symbol, timeframe_minutes, bars)
        
        if df.empty:
            df = self._get_data_yfinance(symbol, timeframe_minutes, bars)

        if not df.empty:
            self._cache[cache_key] = df
            self._cache_time[cache_key] = now

        return df

    def get_current_price(self, symbol: str) -> dict:
        """Obtiene precio actual con bid/ask reales de MT5."""
        if self.mt5_connected:
            mt5 = self._mt5
            tick = mt5.symbol_info_tick(symbol)
            if tick and tick.bid > 0:
                return {
                    "bid": tick.bid,
                    "ask": tick.ask,
                    "spread": round(tick.ask - tick.bid, 5),
                    "time": datetime.fromtimestamp(tick.time, tz=timezone.utc),
                    "source": "mt5",
                }
        
        # Fallback: usar última vela
        df = self.get_data(symbol, 5, 10)
        if not df.empty:
            last = df['close'].iloc[-1]
            spread = last * 0.001
            return {
                "bid": last,
                "ask": last + spread,
                "spread": spread,
                "time": datetime.now(),
                "source": "yfinance",
            }
        return {"bid": 0, "ask": 0, "spread": 0, "time": None, "source": "none"}

    def get_symbol_info(self, symbol: str) -> dict:
        """Información del símbolo (point, digits, etc.)."""
        if self.mt5_connected:
            mt5 = self._mt5
            info = mt5.symbol_info(symbol)
            if info:
                return {
                    "name": info.name,
                    "point": info.point,
                    "digits": info.digits,
                    "spread": info.spread,
                    "trade_mode": info.trade_mode,
                }
        return {"name": symbol, "point": 0.01, "digits": 2}

    def get_all_data(self, timeframe_minutes: int = 15,
                      bars: int = 200) -> dict:
        """Obtiene datos de TODOS los instrumentos monitoreados."""
        from sentinel.config import SYMBOLS
        all_data = {}
        for key, symbol in SYMBOLS.items():
            df = self.get_data(symbol, timeframe_minutes, bars)
            if not df.empty:
                all_data[key] = df
        return all_data

    def get_status(self) -> dict:
        """Estado actual del feed."""
        status = {
            "mode": self.mode,
            "mt5_connected": self.mt5_connected,
            "cache_size": len(self._cache),
        }
        if self.mt5_connected:
            mt5 = self._mt5
            acc = mt5.account_info()
            ti = mt5.terminal_info()
            if acc:
                status["login"] = acc.login
                status["server"] = acc.server
                status["balance"] = acc.balance
            if ti:
                status["build"] = ti.build
                status["connected"] = ti.connected
        return status

    def shutdown(self):
        """Desconecta MT5 limpiamente."""
        if self.mt5_connected and self._mt5:
            self._mt5.shutdown()
            logger.info("MT5 desconectado")

    # ══════════════════════════════════════════════════════════
    # MÉTODOS PRIVADOS — Fuentes de datos
    # ══════════════════════════════════════════════════════════

    def _get_data_mt5(self, symbol: str, timeframe_minutes: int,
                       bars: int) -> pd.DataFrame:
        """Obtiene datos OHLCV desde MT5. SOLO LECTURA."""
        mt5 = self._mt5
        tf = MT5_TIMEFRAMES.get(timeframe_minutes)
        if tf is None:
            return pd.DataFrame()

        try:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
            if rates is None or len(rates) == 0:
                return pd.DataFrame()

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            df.rename(columns={
                'open': 'open', 'high': 'high', 'low': 'low',
                'close': 'close', 'tick_volume': 'volume'
            }, inplace=True)
            
            # Asegurar que tenemos las columnas esperadas
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col not in df.columns:
                    if col == 'volume' and 'real_volume' in df.columns:
                        df['volume'] = df['real_volume']
                    else:
                        df[col] = 0
            
            df = df[['open', 'high', 'low', 'close', 'volume']]
            return df

        except Exception as e:
            logger.error(f"Error MT5 get_data {symbol}: {e}")
            return pd.DataFrame()

    def _get_data_yfinance(self, symbol: str, timeframe_minutes: int,
                            bars: int) -> pd.DataFrame:
        """Obtiene datos OHLCV desde Yahoo Finance (fallback)."""
        global _yfinance_warning_logged
        try:
            import yfinance as yf
        except ImportError:
            if not _yfinance_warning_logged:
                logger.warning("yfinance no instalado — pip install yfinance para habilitar fallback")
                _yfinance_warning_logged = True
            return pd.DataFrame()

        ticker = YAHOO_TICKERS.get(symbol, symbol)
        interval = YF_INTERVALS.get(timeframe_minutes, "15m")
        period = YF_PERIODS.get(interval, "60d")

        try:
            data = yf.Ticker(ticker).history(period=period, interval=interval)
            if data.empty:
                return pd.DataFrame()

            df = data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            df.columns = ['open', 'high', 'low', 'close', 'volume']
            df = df.tail(bars)
            return df

        except Exception as e:
            logger.error(f"Error yfinance {symbol} ({ticker}): {e}")
            return pd.DataFrame()
