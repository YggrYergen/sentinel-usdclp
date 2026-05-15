"""
SENTINEL v4.0 — Macro Scorer (EWMA-Confidence-Weighted)

Generates a macro/world score (0-100) by aggregating cross-asset votes
weighted by real-time EWMA correlation confidence.

Each asset's vote is proportional to:
  1. The MAGNITUDE of its price movement (tanh-scaled)
  2. The DIRECTION expected vs USDCLP (direct/inverse correlation)
  3. The CONFIDENCE that the correlation is working RIGHT NOW (EWMA)
  4. The structural IMPORTANCE of the asset (DXY > Cobre > MXN > ...)

This replaces the binary (+1/-1) voting in the legacy correlation score.
"""

import numpy as np
import logging
from sentinel.config import EXPECTED_CORRELATIONS, SYMBOLS
from sentinel.correlation_engine import RealtimeCorrelationTracker

logger = logging.getLogger("sentinel.macro")

# Structural importance weights (how relevant each asset is for USDCLP)
ASSET_WEIGHTS = {
    "dxy":      3.0,    # Dollar Index — primary driver
    "copper":   2.5,    # Copper — Chile's #1 export
    "usdmxn":   1.5,    # MXN — LATAM peer
    "usdbrl":   1.5,    # BRL — LATAM peer
    "wti":      1.0,    # Oil — import cost
    "audusd":   1.0,    # AUD — commodity proxy
    "usdcnh":   1.0,    # CNH — China demand
    "sp500":    0.5,    # S&P — risk sentiment
}

# tanh sensitivity: how much return (in bps) saturates the vote
# Lower = more sensitive (vote reaches ±1 faster)
TANH_SENSITIVITY = 5.0  # 5 bps ≈ half-saturation


class MacroScorer:
    """
    Macro/World signal scorer for USDCLP.
    
    Uses EWMA-confidence-weighted voting from cross-asset movements
    to generate a directional macro score that updates every 2.5 seconds.
    """
    
    def __init__(self):
        self.tracker = RealtimeCorrelationTracker(
            lambda_var=0.85,    # Fast variance (react to vol spikes)
            lambda_cov=0.97,    # Slow covariance (stable correlation)
            concordance_window=60,  # 60 ticks × 2.5s = 2.5 min window
        )
        self._prev_prices = {}  # Track previous tick prices for returns
        self._warmup_done = False
    
    def update_tick(self, data_feed) -> None:
        """
        Feed one refresh cycle of price data to the EWMA tracker.
        Call this every dashboard refresh (2.5s).
        """
        # Get USDCLP current price
        target_price = data_feed.get_current_price(SYMBOLS["target"])
        target_bid = target_price.get("bid", 0)
        if target_bid <= 0:
            return
        
        # Calculate target return
        prev_target = self._prev_prices.get("target", target_bid)
        ret_target = (target_bid - prev_target) / prev_target * 10000  # bps
        self._prev_prices["target"] = target_bid
        
        # Update each cross-asset
        for asset_key in ASSET_WEIGHTS:
            symbol = SYMBOLS.get(asset_key, "")
            if not symbol:
                continue
            
            try:
                price_info = data_feed.get_current_price(symbol)
                curr_bid = price_info.get("bid", 0) if price_info else 0
                if curr_bid <= 0:
                    continue
                
                prev_bid = self._prev_prices.get(asset_key, curr_bid)
                ret_asset = (curr_bid - prev_bid) / prev_bid * 10000  # bps
                self._prev_prices[asset_key] = curr_bid
                
                # Expected correlation sign
                exp_sign = np.sign(EXPECTED_CORRELATIONS.get(asset_key, 0))
                
                # Feed to EWMA tracker
                self.tracker.update(asset_key, ret_target, ret_asset, exp_sign)
                
            except Exception as e:
                logger.debug(f"MacroScorer tick update {asset_key}: {e}")
    
    def calculate_score(self, data_feed) -> dict:
        """
        Calculate the macro score (0-100) with EWMA-confidence-weighted voting.
        
        Returns:
            score: 0-100 (50=neutral, >50=LONG bias, <50=SHORT bias)
            direction: LONG/SHORT/NEUTRAL
            direction_score: 0-100 directional (>50=LONG, <50=SHORT)
            consensus_score: 0-100 absolute consensus (how much agreement)
            votes: per-asset breakdown
            confidence_avg: average EWMA confidence
        """
        votes = {}
        total_weighted_vote = 0.0
        total_max_weight = 0.0
        
        for asset_key, base_weight in ASSET_WEIGHTS.items():
            symbol = SYMBOLS.get(asset_key, "")
            if not symbol:
                continue
            
            # Get EWMA confidence for this asset
            conf_data = self.tracker.get_confidence(asset_key)
            confidence = conf_data.get("confidence", 0.0)
            ewma_corr = conf_data.get("ewma_corr", 0.0)
            concordance = conf_data.get("concordance", 0.5)
            warmup = conf_data.get("warmup", True)
            
            # Get recent price movement (M1 last 3 bars for reactiveness)
            try:
                m1_data = data_feed.get_data(symbol, timeframe_minutes=1, bars=10)
                if m1_data is not None and len(m1_data) >= 4:
                    closes = m1_data['close'].values
                    # Use last 3 M1 bars (~3 min) for responsive signal
                    recent_return_bps = (closes[-1] - closes[-4]) / closes[-4] * 10000
                else:
                    recent_return_bps = 0.0
            except Exception:
                recent_return_bps = 0.0
            
            # Expected sign: +1 = direct correlation, -1 = inverse
            exp_sign = np.sign(EXPECTED_CORRELATIONS.get(asset_key, 0))
            
            # Directional vote: tanh maps large moves to ±1 proportionally
            # Multiply by exp_sign so positive = "USDCLP should go up"
            raw_vote = np.tanh(recent_return_bps / TANH_SENSITIVITY) * exp_sign
            
            # Weighted vote: confidence × base_weight
            effective_weight = confidence * base_weight
            weighted_vote = raw_vote * effective_weight
            
            total_weighted_vote += weighted_vote
            total_max_weight += confidence * base_weight  # for normalization
            
            votes[asset_key] = {
                "return_bps": round(recent_return_bps, 2),
                "raw_vote": round(raw_vote, 3),
                "confidence": round(confidence, 3),
                "effective_weight": round(effective_weight, 3),
                "weighted_vote": round(weighted_vote, 3),
                "ewma_corr": round(ewma_corr, 4),
                "concordance": round(concordance, 3),
                "warmup": warmup,
            }
        
        # Normalize to -1..+1
        if total_max_weight > 0.01:
            consensus = total_weighted_vote / total_max_weight
        else:
            consensus = 0.0
        
        # Directional score: 0-100 where >50 = LONG, <50 = SHORT
        # consensus of +1 → score 100, consensus of -1 → score 0
        direction_score = round(50 + consensus * 50, 1)
        direction_score = max(0, min(100, direction_score))
        
        # Consensus strength: how much agreement regardless of direction
        # |consensus| of 1 → 100, |consensus| of 0 → 50
        consensus_score = round(50 + abs(consensus) * 50, 1)
        consensus_score = max(0, min(100, consensus_score))
        
        # Direction determination
        if consensus > 0.15:
            direction = "LONG"
        elif consensus < -0.15:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"
        
        # Average confidence across tracked assets
        all_conf = self.tracker.get_all_confidence()
        conf_values = [v["confidence"] for v in all_conf.values() if not v.get("warmup")]
        avg_confidence = sum(conf_values) / len(conf_values) if conf_values else 0.0
        
        return {
            "score": direction_score,
            "direction": direction,
            "direction_score": direction_score,
            "consensus_score": consensus_score,
            "consensus_raw": round(consensus, 4),
            "votes": votes,
            "confidence_avg": round(avg_confidence, 3),
            "total_assets_tracked": len(votes),
            "assets_warmed_up": sum(1 for v in votes.values() if not v["warmup"]),
        }
    
    def calculate_fusion(self, tech_score: float, tech_direction: str,
                          macro_score: float, macro_direction: str) -> dict:
        """
        Calculate the Fusion signal combining Technical + Macro.
        
        The fusion score accounts for alignment:
        - Both same direction → boost
        - Opposite directions → penalize
        """
        # Directional alignment
        aligned = (tech_direction == macro_direction and 
                   tech_direction != "NEUTRAL")
        opposed = (tech_direction != macro_direction and 
                   "NEUTRAL" not in (tech_direction, macro_direction))
        
        if aligned:
            # Both agree → weighted average with boost
            fusion_score = (tech_score + macro_score) / 2
            # Boost: the more both are extreme, the stronger
            boost = min(10, abs(tech_score - 50) * abs(macro_score - 50) / 500)
            if tech_direction == "LONG":
                fusion_score += boost
            else:
                fusion_score -= boost
            confluence_pct = round((tech_score + macro_score) / 2, 1)
        elif opposed:
            # Divergence → pull toward neutral (50)
            fusion_score = 50 + (tech_score - 50) * 0.3 + (macro_score - 50) * 0.3
            confluence_pct = round(100 - abs(tech_score - macro_score), 1)
        else:
            # One is neutral → lean toward the active one
            if tech_direction != "NEUTRAL":
                fusion_score = 50 + (tech_score - 50) * 0.6
            elif macro_direction != "NEUTRAL":
                fusion_score = 50 + (macro_score - 50) * 0.6
            else:
                fusion_score = 50
            confluence_pct = round((tech_score + macro_score) / 2, 1)
        
        fusion_score = round(max(0, min(100, fusion_score)), 1)
        confluence_pct = max(0, min(100, confluence_pct))
        
        # Fusion direction
        if fusion_score >= 60:
            fusion_dir = "LONG"
        elif fusion_score <= 40:
            fusion_dir = "SHORT"
        else:
            fusion_dir = "NEUTRAL"
        
        # Risk mode based on confluence
        if aligned and confluence_pct >= 80:
            risk_mode = "AGGRESSIVE"
            risk_emoji = "🟢"
            sl_mult = 2.0
            tp_mult = 3.5
        elif confluence_pct >= 50:
            risk_mode = "NORMAL"
            risk_emoji = "🟡"
            sl_mult = 2.0
            tp_mult = 3.0
        else:
            risk_mode = "CONSERVATIVE"
            risk_emoji = "🔴"
            sl_mult = 1.5
            tp_mult = 2.0
        
        return {
            "score": fusion_score,
            "direction": fusion_dir,
            "aligned": aligned,
            "opposed": opposed,
            "confluence_pct": confluence_pct,
            "risk_mode": risk_mode,
            "risk_emoji": risk_emoji,
            "sl_multiplier": sl_mult,
            "tp_multiplier": tp_mult,
        }
