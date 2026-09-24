"""
SENTINEL v4.0 — Cerebro del Sistema (thin delegator).

Combina Technical (50%) + Macro EWMA (50%) en score compuesto.
La correlación vieja se mantiene solo para detección de divergencias y tabla UI.

The scoring math now lives ONLY in `sentinel_engine.engine.Engine`.
`calculate_composite()` delegates to `Engine.step()` and reshapes the frozen
`Snapshot` back into the exact legacy dict the dashboards consume (same keys /
values as before, plus the wall-clock `meta.timestamp`). The engine's macro
tracker is the SAME stateful object as `self.macro_scorer`, so external warmup
ticks driven on `core.macro_scorer` feed the tracker `Engine.step()` reads.

Reverting the P1 live-cutover commit restores this file's original standalone
implementation.
"""
import logging
from datetime import datetime

logger = logging.getLogger("sentinel.core")

class SentinelCore:
    def __init__(self, data_feed):
        self.feed = data_feed
        self.alerts = []
        # v4.0: MacroScorer with EWMA-confidence-weighted voting. Kept as the
        # legacy-facing handle (dashboards read/mutate core.macro_scorer).
        from sentinel.macro_scorer import MacroScorer
        self.macro_scorer = MacroScorer()
        # Headless engine is the sole scoring implementation. Share the ONE
        # stateful EWMA tracker between the legacy handle and the engine so
        # warmup ticks on core.macro_scorer and the engine's internal tick
        # advance the same tracker (both are USDCLP-configured, so config_hash
        # is unaffected by the swap).
        from sentinel_engine.config import load_instrument
        from sentinel_engine.engine import Engine
        self._engine = Engine(load_instrument("usdclp"), data_feed)
        self._engine._macro = self.macro_scorer

    def calculate_composite(self) -> dict:
        """Calcula el score compuesto SENTINEL (Técnico 50% + Macro EWMA 50%).

        Delegates to `Engine.step()` and reshapes the Snapshot into the legacy
        dict the dashboards consume."""
        snap = self._engine.step()
        d = snap.to_dict()
        self.alerts = d["alerts"]
        return {
            "composite_score": d["composite_score"],
            "direction": d["direction"],
            "signal": d["signal"],
            "blocked": d["blocked"],
            "block_reason": d["block_reason"],
            "components": d["components"],
            "levels": d["levels"],
            "divergences": d["divergences"],
            "alerts": d["alerts"],
            "meta": {
                "timestamp": datetime.now().isoformat(),
            }
        }

