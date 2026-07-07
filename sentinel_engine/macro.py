"""
sentinel_engine.macro — instrument-parameterized MacroScorer (P1, Task 1.4).

Reproduces the EXACT math of `sentinel.macro_scorer.MacroScorer.update_tick`
+ `calculate_score` (which is byte-identical to `sentinel.instrument_panel`'s
`_update_macro`/`_calc_macro` pure-compute pair — see task 1.3/1.4 briefing),
but sources every constant from an `sentinel_engine.config.InstrumentConfig`
instead of module-level USDCLP-hardwired globals. Reuses
`sentinel.correlation_engine.RealtimeCorrelationTracker` verbatim — the
EWMA/concordance/z-score math is NOT reimplemented here.

This module is purely additive: it does not modify or import from
`sentinel.macro_scorer` or `sentinel.instrument_panel`.
"""
from __future__ import annotations

import logging

import numpy as np

from sentinel.correlation_engine import RealtimeCorrelationTracker
from sentinel_engine.config import InstrumentConfig
from sentinel_engine.feed import Feed

logger = logging.getLogger("sentinel_engine.macro")


class MacroScorer:
    """Macro/World signal scorer parameterized by an `InstrumentConfig`.

    Usage mirrors `sentinel.macro_scorer.MacroScorer`:
        ms = MacroScorer(load_instrument("gold"))
        ms.update_tick(feed)   # once per refresh cycle
        result = ms.score(feed)
    """

    def __init__(self, cfg: InstrumentConfig):
        self.cfg = cfg
        m = cfg.macro
        self.tracker = RealtimeCorrelationTracker(
            lambda_var=m.tracker.lambda_var,
            lambda_cov=m.tracker.lambda_cov,
            concordance_window=m.tracker.concordance_window,
        )
        self._prev_prices: dict = {}

    def update_tick(self, feed: Feed) -> None:
        """Feed one refresh cycle of price data to the EWMA tracker."""
        target_price = feed.get_current_price(self.cfg.target)
        target_bid = target_price.get("bid", 0)
        if target_bid <= 0:
            return

        prev_target = self._prev_prices.get("target", target_bid)
        ret_target = (target_bid - prev_target) / prev_target * 10000  # bps
        self._prev_prices["target"] = target_bid

        for asset_key in self.cfg.asset_weights:
            symbol = self.cfg.symbols.get(asset_key, "")
            if not symbol:
                continue

            try:
                price_info = feed.get_current_price(symbol)
                curr_bid = price_info.get("bid", 0) if price_info else 0
                if curr_bid <= 0:
                    continue

                prev_bid = self._prev_prices.get(asset_key, curr_bid)
                ret_asset = (curr_bid - prev_bid) / prev_bid * 10000  # bps
                self._prev_prices[asset_key] = curr_bid

                exp_sign = np.sign(self.cfg.expected_correlations.get(asset_key, 0))

                self.tracker.update(asset_key, ret_target, ret_asset, exp_sign)

            except Exception as e:
                logger.debug(f"MacroScorer tick update {asset_key}: {e}")

    def score(self, feed: Feed) -> dict:
        """Calculate the macro score (0-100) with EWMA-confidence-weighted
        voting. Returns the SAME rich shape as
        `sentinel.macro_scorer.MacroScorer.calculate_score`."""
        votes = {}
        total_weighted_vote = 0.0
        total_max_weight = 0.0

        for asset_key, base_weight in self.cfg.asset_weights.items():
            symbol = self.cfg.symbols.get(asset_key, "")
            if not symbol:
                continue

            conf_data = self.tracker.get_confidence(asset_key)
            confidence = conf_data.get("confidence", 0.0)
            ewma_corr = conf_data.get("ewma_corr", 0.0)
            concordance = conf_data.get("concordance", 0.5)
            warmup = conf_data.get("warmup", True)

            try:
                m1_data = feed.get_data(symbol, timeframe_minutes=1, bars=10)
                if m1_data is not None and len(m1_data) >= 4:
                    closes = m1_data['close'].values
                    recent_return_bps = (closes[-1] - closes[-4]) / closes[-4] * 10000
                else:
                    recent_return_bps = 0.0
            except Exception:
                recent_return_bps = 0.0

            exp_sign = np.sign(self.cfg.expected_correlations.get(asset_key, 0))

            raw_vote = np.tanh(recent_return_bps / self.cfg.macro.tanh_sensitivity) * exp_sign

            effective_weight = confidence * base_weight
            weighted_vote = raw_vote * effective_weight

            total_weighted_vote += weighted_vote
            total_max_weight += confidence * base_weight

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

        if total_max_weight > 0.01:
            consensus = total_weighted_vote / total_max_weight
        else:
            consensus = 0.0

        direction_score = round(50 + consensus * 50, 1)
        direction_score = max(0, min(100, direction_score))

        consensus_score = round(50 + abs(consensus) * 50, 1)
        consensus_score = max(0, min(100, consensus_score))

        dth = self.cfg.macro.direction_threshold
        if consensus > dth:
            direction = "LONG"
        elif consensus < -dth:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"

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
