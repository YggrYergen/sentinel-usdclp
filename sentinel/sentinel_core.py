"""
SENTINEL v4.0 — Cerebro del Sistema
Combina Technical (50%) + Macro EWMA (50%) en score compuesto.
La correlación vieja se mantiene solo para detección de divergencias y tabla UI.
"""
import logging
from datetime import datetime
from sentinel.config import WEIGHTS, SCORE_ALERT_THRESHOLD, SCORE_STRONG_THRESHOLD, SYMBOLS

logger = logging.getLogger("sentinel.core")

class SentinelCore:
    def __init__(self, data_feed):
        self.feed = data_feed
        self.alerts = []
        # v4.0: MacroScorer with EWMA-confidence-weighted voting
        from sentinel.macro_scorer import MacroScorer
        self.macro_scorer = MacroScorer()

    def calculate_composite(self) -> dict:
        """Calcula el score compuesto SENTINEL (Técnico 50% + Macro EWMA 50%)."""
        from sentinel.technical_scorer import calculate_multi_tf_score
        from sentinel.correlation_engine import calculate_target_correlations, detect_divergence
        from sentinel.levels_engine import calculate_levels

        target = SYMBOLS["target"]
        
        # 1. Score técnico multi-TF (50%)
        tech = calculate_multi_tf_score(self.feed, target)
        tech_score = tech["composite_score"]
        tech_dir = tech["h4_direction"]

        # 2. Score macro EWMA (50%) — reemplaza correlación vieja en el compuesto
        self.macro_scorer.update_tick(self.feed)
        macro = self.macro_scorer.calculate_score(self.feed)
        macro_score = macro["score"]
        macro_dir = macro["direction"]

        # 3. Correlación vieja — solo para divergencias y tabla UI (NO entra al score)
        all_data = self.feed.get_all_data(timeframe_minutes=60, bars=200)
        corr = calculate_target_correlations(all_data)
        corr_score_legacy = corr["score"]
        corr_dir_legacy = corr["direction"]
        divergences = detect_divergence(all_data)

        # 4. Niveles price-action
        levels = calculate_levels(self.feed, target)

        # Score compuesto ponderado (técnico + macro EWMA)
        composite = (
            tech_score * WEIGHTS.technical +
            macro_score * WEIGHTS.correlation   # .correlation = 0.50 (mundo)
        )
        composite = round(min(100, max(0, composite)), 1)

        # Dirección consensuada (técnico + macro)
        dir_votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        for d, w in [(tech_dir, 2), (macro_dir, 3)]:
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
                # "correlation" key kept for backward compat — dashboard reads it
                # Now powered by MacroScorer EWMA instead of old binary voting
                "correlation": {"score": macro_score, "weight": WEIGHTS.correlation, "direction": macro_dir, "details": corr},
                # Legacy correlation available separately for table UI
                "_correlation_legacy": {"score": corr_score_legacy, "direction": corr_dir_legacy, "details": corr},
                "_macro": macro,  # Full macro result with per-asset votes
            },
            "levels": levels,
            "divergences": divergences,
            "alerts": self.alerts,
            "meta": {
                "timestamp": datetime.now().isoformat(),
            }
        }

