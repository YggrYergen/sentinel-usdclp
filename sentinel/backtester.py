"""
SENTINEL v3.4 — Motor de Backtesting
Replay del sistema de scoring sobre datos históricos de mercado.
Compara recomendaciones SENTINEL vs trades reales del operador.

Referencia: https://www.mql5.com/en/docs/python_metatrader5
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import time
import logging

logger = logging.getLogger("sentinel.backtest")

# ══════════════════════════════════════════════════════════
# FUNCIONES DE DATOS HISTÓRICOS
# ══════════════════════════════════════════════════════════

def fetch_historical_trades(days_back: int = 30) -> pd.DataFrame:
    """Obtiene historial de trades reales del operador desde MT5."""
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            logger.warning("MT5 no disponible para historial de trades")
            return pd.DataFrame()
        
        date_to = datetime.now(timezone.utc)
        date_from = date_to - timedelta(days=days_back)
        
        deals = mt5.history_deals_get(date_from, date_to)
        if deals is None or len(deals) == 0:
            logger.info(f"No se encontraron trades en los últimos {days_back} días")
            return pd.DataFrame()
        
        df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        # Filter only USDCLP trades (or target symbol)
        df = df[df['symbol'].str.contains('USDCLP|CLP', case=False, na=False)]
        df['time_dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        logger.info(f"Encontrados {len(df)} deals de USDCLP en {days_back} días")
        return df
        
    except ImportError:
        logger.warning("MetaTrader5 no instalado — sin historial de trades")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        return pd.DataFrame()


def fetch_historical_candles(symbol: str, timeframe_minutes: int, 
                              bars: int = 500) -> pd.DataFrame:
    """Obtiene velas históricas desde MT5."""
    try:
        import MetaTrader5 as mt5
        from sentinel.data_feed import DataFeed
        
        feed = DataFeed()
        df = feed.get_data(symbol, timeframe_minutes, bars)
        return df
        
    except Exception as e:
        logger.error(f"Error obteniendo velas históricas: {e}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════
# MOTOR DE REPLAY
# ══════════════════════════════════════════════════════════

def replay_scoring(bars_back: int = 500, progress_callback=None) -> pd.DataFrame:
    """
    Reproduce el sistema de scoring SENTINEL sobre datos históricos.
    
    Para cada punto en el tiempo (cada vela M1), calcula:
    - Score técnico por TF (M1, M2, M5, M15)
    - Score compuesto
    - Dirección recomendada
    - Señales v1 (Pulso/Corto/Medio)
    
    Returns: DataFrame con columnas:
        timestamp, price, score, direction, tech_score, corr_score,
        m1_score, m2_score, m5_score, m15_score, signal_5s, signal_30s, signal_1m
    """
    from sentinel.data_feed import DataFeed
    from sentinel.config import SYMBOLS, TIMEFRAMES, BARS_TO_FETCH
    from sentinel.technical_scorer import calculate_technical_score
    from sentinel.correlation_engine import CorrelationEngine
    from sentinel.config import WEIGHTS
    
    feed = DataFeed()
    logger.info(f"Iniciando replay de {bars_back} velas M1...")
    
    # Get M1 candles as the base timeline
    m1_data = feed.get_data(SYMBOLS["target"], 1, bars_back + 200)
    if m1_data is None or len(m1_data) < 50:
        logger.error("Datos insuficientes para replay")
        return pd.DataFrame()
    
    # Get data for other timeframes
    tf_data = {}
    for tf_name, tf_min in TIMEFRAMES.items():
        tf_bars = max(300, bars_back // tf_min + 200)
        d = feed.get_data(SYMBOLS["target"], tf_min, tf_bars)
        if d is not None and len(d) > 0:
            tf_data[tf_name] = d
    
    # Get correlation data (less frequent, use most recent)
    corr_engine = CorrelationEngine(feed)
    try:
        corr_result = corr_engine.calculate()
        corr_score = corr_result.get("score", 50)
        corr_dir = corr_result.get("direction", "NEUTRAL")
    except Exception as e:
        logger.warning(f"Correlación no disponible para backtest: {e}")
        corr_score = 50
        corr_dir = "NEUTRAL"
    
    results = []
    total = min(bars_back, len(m1_data) - 200)
    
    tf_w = {"M15": 0.10, "M5": 0.30, "M2": 0.30, "M1": 0.30}
    
    for i in range(200, 200 + total):
        if progress_callback and i % 50 == 0:
            progress_callback((i - 200) / total)
        
        timestamp = m1_data.index[i] if hasattr(m1_data.index[i], 'timestamp') else m1_data.index[i]
        price = float(m1_data['close'].iloc[i])
        
        # Calculate score for each TF at this point in time
        tf_scores = {}
        for tf_name, tf_min in TIMEFRAMES.items():
            if tf_name in tf_data:
                d = tf_data[tf_name]
                # Find the data up to this timestamp
                if hasattr(d.index, 'tz'):
                    mask = d.index <= m1_data.index[i]
                else:
                    mask = d.index <= m1_data.index[i]
                subset = d[mask].tail(BARS_TO_FETCH)
                if len(subset) >= 30:
                    try:
                        tf_scores[tf_name] = calculate_technical_score(subset)
                    except Exception:
                        tf_scores[tf_name] = {"score": 50, "direction": "NEUTRAL"}
                else:
                    tf_scores[tf_name] = {"score": 50, "direction": "NEUTRAL"}
            else:
                tf_scores[tf_name] = {"score": 50, "direction": "NEUTRAL"}
        
        # Calculate weighted technical score
        tech_score = sum(
            tf_scores.get(tf, {}).get("score", 50) * w 
            for tf, w in tf_w.items()
        )
        
        # Determine technical direction by weighted vote
        dir_votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        for tf, w in tf_w.items():
            d = tf_scores.get(tf, {}).get("direction", "NEUTRAL")
            dir_votes[d] += w
        tech_dir = max(dir_votes, key=dir_votes.get)
        
        # Composite score
        composite = tech_score * WEIGHTS.technical + corr_score * WEIGHTS.correlation
        
        # Direction
        if tech_dir != "NEUTRAL":
            direction = tech_dir
        elif corr_dir != "NEUTRAL":
            direction = corr_dir
        else:
            direction = "NEUTRAL"
        
        # Signal v1 blends
        m1s = tf_scores.get("M1", {}).get("score", 50)
        m2s = tf_scores.get("M2", {}).get("score", 50)
        m5s = tf_scores.get("M5", {}).get("score", 50)
        
        sig_5s = m1s
        sig_30s = m1s * 0.6 + m2s * 0.4
        sig_1m = m1s * 0.4 + m2s * 0.3 + m5s * 0.3
        
        results.append({
            "timestamp": timestamp,
            "price": price,
            "score": round(composite, 1),
            "direction": direction,
            "tech_score": round(tech_score, 1),
            "corr_score": round(corr_score, 1),
            "m1_score": round(m1s, 1),
            "m2_score": round(m2s, 1),
            "m5_score": round(m5s, 1),
            "m15_score": round(tf_scores.get("M15", {}).get("score", 50), 1),
            "signal_5s": round(sig_5s, 1),
            "signal_30s": round(sig_30s, 1),
            "signal_1m": round(sig_1m, 1),
            "m1_dir": tf_scores.get("M1", {}).get("direction", "NEUTRAL"),
        })
    
    logger.info(f"Replay completado: {len(results)} puntos calculados")
    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════
# COMPARACIÓN CON TRADES REALES
# ══════════════════════════════════════════════════════════

def compare_with_trades(replay_df: pd.DataFrame, trades_df: pd.DataFrame) -> dict:
    """
    Compara las recomendaciones SENTINEL con los trades reales.
    
    Returns dict con métricas:
    - total_trades: int
    - sentinel_agreed: int (SENTINEL coincidía con la dirección)
    - sentinel_would_filter: int (trades perdedores donde SENTINEL decía esperar)
    - missed_opportunities: int (SENTINEL decía entrar pero trader no operó)
    - accuracy_pct: float
    - filter_rate_pct: float (% de pérdidas evitables)
    - trade_details: list of dicts
    """
    if replay_df.empty or trades_df.empty:
        return {
            "total_trades": 0, "sentinel_agreed": 0,
            "sentinel_would_filter": 0, "accuracy_pct": 0,
            "filter_rate_pct": 0, "trade_details": [],
            "error": "Datos insuficientes"
        }
    
    # Build trade pairs (entry + exit)
    # MT5 deals: type 0=BUY, type 1=SELL, entry 0=IN, entry 1=OUT
    entries = trades_df[trades_df['entry'] == 0].copy()
    exits = trades_df[trades_df['entry'] == 1].copy()
    
    trade_details = []
    agreed = 0
    would_filter = 0
    losing_filtered = 0
    total_losing = 0
    
    for _, entry in entries.iterrows():
        entry_time = entry['time_dt']
        position_id = entry.get('position_id', entry.get('order', 0))
        
        # Find matching exit
        matching_exit = exits[exits.get('position_id', exits.get('order', 0)) == position_id]
        if matching_exit.empty:
            continue
        
        exit_row = matching_exit.iloc[0]
        exit_time = exit_row['time_dt']
        profit = exit_row.get('profit', 0)
        trade_type = "LONG" if entry['type'] == 0 else "SHORT"
        
        # Find SENTINEL score at entry time
        replay_df['timestamp'] = pd.to_datetime(replay_df['timestamp'])
        entry_mask = replay_df['timestamp'] <= entry_time
        if not entry_mask.any():
            continue
        
        sentinel_at_entry = replay_df[entry_mask].iloc[-1]
        sentinel_score = sentinel_at_entry['score']
        sentinel_dir = sentinel_at_entry['direction']
        
        # Analysis
        direction_match = sentinel_dir == trade_type
        sentinel_says_go = sentinel_score >= 65
        is_winner = profit > 0
        
        if direction_match and sentinel_says_go:
            agreed += 1
        
        if not is_winner:
            total_losing += 1
            if not sentinel_says_go or not direction_match:
                would_filter += 1
                losing_filtered += 1
        
        trade_details.append({
            "entry_time": entry_time.strftime("%Y-%m-%d %H:%M"),
            "exit_time": exit_time.strftime("%Y-%m-%d %H:%M"),
            "type": trade_type,
            "profit": round(profit, 2),
            "sentinel_score": sentinel_score,
            "sentinel_dir": sentinel_dir,
            "match": "✅" if direction_match else "❌",
            "sentinel_go": "🟢" if sentinel_says_go else "🔴",
            "result": "✅" if is_winner else "❌",
        })
    
    total = len(trade_details)
    return {
        "total_trades": total,
        "sentinel_agreed": agreed,
        "sentinel_would_filter": would_filter,
        "total_losing": total_losing,
        "accuracy_pct": round(agreed / total * 100, 1) if total > 0 else 0,
        "filter_rate_pct": round(losing_filtered / total_losing * 100, 1) if total_losing > 0 else 0,
        "trade_details": trade_details,
    }
