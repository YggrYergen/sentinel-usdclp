"""
SENTINEL v3 — Gestión de Riesgo y Position Sizing
"""
from sentinel.config import RISK

def calculate_position_size(capital_clp: float, atr: float, exchange_rate: float,
                             pip_value: float = None, contract_size: float = 100000) -> dict:
    """Calcula tamaño de posición basado en ATR y % de riesgo."""
    risk_amount = capital_clp * RISK.risk_per_trade_pct
    sl_distance = atr * RISK.atr_sl_multiplier
    tp_distance = atr * RISK.atr_tp_multiplier
    if sl_distance == 0 or exchange_rate == 0:
        return {"error": "ATR o exchange rate es 0"}
    if pip_value is None:
        pip_value = (0.01 / exchange_rate) * contract_size
    lots = risk_amount / (sl_distance * pip_value * contract_size) if pip_value * contract_size > 0 else 0
    lots = round(lots, 2)
    rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
    return {
        "capital": capital_clp, "risk_pct": RISK.risk_per_trade_pct * 100,
        "risk_amount_clp": round(risk_amount, 0),
        "atr": round(atr, 4), "sl_distance": round(sl_distance, 4),
        "tp_distance": round(tp_distance, 4),
        "lots": lots, "rr_ratio": round(rr_ratio, 2),
        "sl_multiplier": RISK.atr_sl_multiplier,
        "tp_multiplier": RISK.atr_tp_multiplier,
    }

def check_daily_limits(daily_pnl: float, trades_today: int, consecutive_losses: int) -> dict:
    """Verifica límites diarios de riesgo."""
    max_loss = RISK.capital_clp * RISK.max_daily_loss_pct
    return {
        "can_trade": (abs(daily_pnl) < max_loss if daily_pnl < 0 else True) and
                     trades_today < RISK.max_trades_per_day and
                     consecutive_losses < RISK.consecutive_losses_pause,
        "daily_pnl": daily_pnl, "max_daily_loss": max_loss,
        "loss_pct_used": round(abs(min(0, daily_pnl)) / max_loss * 100, 1),
        "trades_used": trades_today, "max_trades": RISK.max_trades_per_day,
        "consecutive_losses": consecutive_losses,
        "max_consecutive": RISK.consecutive_losses_pause,
    }
