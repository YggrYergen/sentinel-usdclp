"""
SENTINEL v3 — Cerebro del Sistema
Combina Technical + Correlation + Risk + DOM en score compuesto.
"""
import logging
from datetime import datetime
from sentinel.config import WEIGHTS, SCORE_ALERT_THRESHOLD, SCORE_STRONG_THRESHOLD, SYMBOLS, RISK

logger = logging.getLogger("sentinel.core")

class SentinelCore:
    def __init__(self, data_feed):
        self.feed = data_feed
        self.dom_score = 50  # Input manual (default neutral)
        self.dom_direction = "NEUTRAL"
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.consecutive_losses = 0
        self.paused = False
        self.pause_until = None
        self.alerts = []

    def set_dom_input(self, score: int, direction: str):
        """Input manual del DOM bancario (desde el Zoom)."""
        self.dom_score = max(0, min(100, score))
        self.dom_direction = direction.upper()

    def calculate_composite(self) -> dict:
        """Calcula el score compuesto SENTINEL."""
        from sentinel.technical_scorer import calculate_multi_tf_score
        from sentinel.correlation_engine import calculate_target_correlations, detect_divergence

        target = SYMBOLS["target"]
        
        # 1. Score técnico multi-TF (30%)
        tech = calculate_multi_tf_score(self.feed, target)
        tech_score = tech["composite_score"]
        tech_dir = tech["h4_direction"]

        # 2. Score de correlación (45%)
        all_data = self.feed.get_all_data(timeframe_minutes=60, bars=200)
        corr = calculate_target_correlations(all_data)
        corr_score = corr["score"]
        corr_dir = corr["direction"]
        divergences = detect_divergence(all_data)

        # 3. Score de riesgo/contexto (20%)
        risk_score = self._calculate_risk_score()

        # 4. DOM manual (5%)
        dom_score = self.dom_score

        # Score compuesto ponderado
        composite = (
            tech_score * WEIGHTS.technical +
            corr_score * WEIGHTS.correlation +
            risk_score * WEIGHTS.risk +
            dom_score * WEIGHTS.dom
        )
        composite = round(min(100, max(0, composite)), 1)

        # Dirección consensuada
        dir_votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        for d, w in [(tech_dir, 3), (corr_dir, 4), (self.dom_direction, 1)]:
            if d in dir_votes:
                dir_votes[d] += w
        direction = max(dir_votes, key=dir_votes.get)

        # Semáforo
        if composite >= SCORE_STRONG_THRESHOLD:
            signal = "🟢 FUERTE"
        elif composite >= SCORE_ALERT_THRESHOLD:
            signal = "🟡 ALERTA"
        else:
            signal = "🔴 ESPERAR"

        # Alertas
        self.alerts = []
        if composite >= SCORE_ALERT_THRESHOLD:
            self.alerts.append(f"📊 Score {composite} — {direction}")
        for div in divergences[:3]:
            self.alerts.append(div["description"])
        for alert in corr.get("alerts", []):
            self.alerts.append(alert)
        if self.paused:
            self.alerts.insert(0, "⏸️ SISTEMA EN PAUSA — circuit breaker activo")

        # Kill switches
        blocked = False
        block_reason = ""
        if self.paused:
            blocked = True
            block_reason = "Circuit breaker activo"
        elif self.trades_today >= RISK.max_trades_per_day:
            blocked = True
            block_reason = f"Máximo {RISK.max_trades_per_day} trades alcanzado"
        elif abs(self.daily_pnl) >= RISK.capital_clp * RISK.max_daily_loss_pct:
            blocked = True
            block_reason = f"Pérdida diaria máxima ({RISK.max_daily_loss_pct*100}%) alcanzada"

        return {
            "composite_score": composite,
            "direction": direction,
            "signal": signal,
            "blocked": blocked,
            "block_reason": block_reason,
            "components": {
                "technical": {"score": tech_score, "weight": WEIGHTS.technical, "direction": tech_dir, "details": tech},
                "correlation": {"score": corr_score, "weight": WEIGHTS.correlation, "direction": corr_dir, "details": corr},
                "risk": {"score": risk_score, "weight": WEIGHTS.risk},
                "dom": {"score": dom_score, "weight": WEIGHTS.dom, "direction": self.dom_direction},
            },
            "divergences": divergences,
            "alerts": self.alerts,
            "meta": {
                "trades_today": self.trades_today,
                "daily_pnl": self.daily_pnl,
                "consecutive_losses": self.consecutive_losses,
                "timestamp": datetime.now().isoformat(),
            }
        }

    def _calculate_risk_score(self) -> float:
        """Score de contexto de riesgo (0-100). Alto = favorable para operar."""
        score = 70  # Base
        now = datetime.now()
        from sentinel.config import MARKET_OPEN, MARKET_CLOSE
        current_time = now.time()
        # Dentro de horario operativo
        if MARKET_OPEN <= current_time <= MARKET_CLOSE:
            score += 15
        else:
            score -= 30
        # Penalizar si hay pérdidas acumuladas
        loss_pct = abs(self.daily_pnl) / RISK.capital_clp if self.daily_pnl < 0 else 0
        score -= loss_pct * 200
        # Penalizar pérdidas consecutivas
        score -= self.consecutive_losses * 10
        return round(min(100, max(0, score)), 1)

    def register_trade_result(self, pnl_clp: float):
        """Registra el resultado de un trade."""
        self.daily_pnl += pnl_clp
        self.trades_today += 1
        if pnl_clp < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= RISK.consecutive_losses_pause:
                self.paused = True
                logger.warning(f"⏸️ CIRCUIT BREAKER: {self.consecutive_losses} pérdidas seguidas")
        else:
            self.consecutive_losses = 0

    def reset_daily(self):
        """Reset al inicio de cada día."""
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.consecutive_losses = 0
        self.paused = False
        self.alerts = []
