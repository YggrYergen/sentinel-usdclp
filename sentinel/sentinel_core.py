"""
SENTINEL v3.1 — Cerebro del Sistema
Combina Technical + Correlation en score compuesto.
"""
import logging
from datetime import datetime
from sentinel.config import WEIGHTS, SCORE_ALERT_THRESHOLD, SCORE_STRONG_THRESHOLD, SYMBOLS

logger = logging.getLogger("sentinel.core")

class SentinelCore:
    def __init__(self, data_feed):
        self.feed = data_feed
        self.alerts = []

    def calculate_composite(self) -> dict:
        """Calcula el score compuesto SENTINEL (Técnico 75% + Correlación 25%)."""
        from sentinel.technical_scorer import calculate_multi_tf_score
        from sentinel.correlation_engine import calculate_target_correlations, detect_divergence
        from sentinel.levels_engine import calculate_levels

        target = SYMBOLS["target"]
        
        # 1. Score técnico multi-TF (75%)
        tech = calculate_multi_tf_score(self.feed, target)
        tech_score = tech["composite_score"]
        tech_dir = tech["h4_direction"]

        # 2. Score de correlación (25%)
        all_data = self.feed.get_all_data(timeframe_minutes=60, bars=200)
        corr = calculate_target_correlations(all_data)
        corr_score = corr["score"]
        corr_dir = corr["direction"]
        divergences = detect_divergence(all_data)

        # 3. Niveles price-action
        levels = calculate_levels(self.feed, target)

        # Score compuesto ponderado (solo técnico + correlación)
        composite = (
            tech_score * WEIGHTS.technical +
            corr_score * WEIGHTS.correlation
        )
        composite = round(min(100, max(0, composite)), 1)

        # Dirección consensuada
        dir_votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        for d, w in [(tech_dir, 2), (corr_dir, 3)]:
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

        return {
            "composite_score": composite,
            "direction": direction,
            "signal": signal,
            "blocked": False,
            "block_reason": "",
            "components": {
                "technical": {"score": tech_score, "weight": WEIGHTS.technical, "direction": tech_dir, "details": tech},
                "correlation": {"score": corr_score, "weight": WEIGHTS.correlation, "direction": corr_dir, "details": corr},
            },
            "levels": levels,
            "divergences": divergences,
            "alerts": self.alerts,
            "meta": {
                "timestamp": datetime.now().isoformat(),
            }
        }

