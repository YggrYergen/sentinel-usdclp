"""
SENTINEL v4.0 — Macro Scorer (thin forwarder).

The macro scoring math now lives ONLY in `sentinel_engine.macro.MacroScorer`.
This module is a backward-compat shim: `sentinel.macro_scorer.MacroScorer` is a
USDCLP-configured subclass of the engine scorer, preserving the EXACT public
API the dashboards use (`MacroScorer()`, `.update_tick`, `.calculate_score`,
`.calculate_score_at_window`, `.calculate_fusion`, `.tracker`, `._prev_prices`).

Reverting the P1 live-cutover commit restores this file's original standalone
implementation.
"""

from sentinel_engine.config import load_instrument
from sentinel_engine.macro import MacroScorer as _EngineMacroScorer

# ── Single-source-of-truth USDCLP macro constants ──────────────────────────
# Kept as literals so `tests/test_instrument_config.py` can independently
# validate `sentinel_engine/instruments/usdclp.yaml` against them. These are
# per-instrument CONFIG data, not scoring math (the math is in
# `sentinel_engine.macro`).
#
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
TANH_SENSITIVITY = 5.0  # 5 bps ≈ half-saturation


class MacroScorer(_EngineMacroScorer):
    """USDCLP-configured forwarder to `sentinel_engine.macro.MacroScorer`.

    Preserves the legacy no-arg constructor and the legacy `calculate_score`
    method name (the engine scorer calls it `score`). Every other method
    (`update_tick`, `calculate_score_at_window`, `calculate_fusion`) and every
    attribute (`tracker`, `_prev_prices`, `cfg`) is inherited unchanged from
    the engine scorer.
    """

    def __init__(self):
        super().__init__(load_instrument("usdclp"))

    def calculate_score(self, data_feed) -> dict:
        """Legacy alias for the engine scorer's `score(feed)`."""
        return self.score(data_feed)
