"""
sentinel_engine.engine — headless, config-parameterized scoring engine (P1, Task 1.6a).

`Engine(cfg, feed).step()` is a config-parameterized generalization of
`sentinel.sentinel_core.SentinelCore.calculate_composite`: it combines
`sentinel_engine.technical.TechnicalScorer` (50%, technical weight from
`cfg.composite.weights["technical"]`) with `sentinel_engine.macro.MacroScorer`
(50%, `cfg.composite.weights["correlation"]`) into a single composite score,
reproducing the EXACT math/rounding/vote/threshold/alert logic of
`calculate_composite` — but sourcing every constant from an
`sentinel_engine.config.InstrumentConfig` instead of USDCLP-hardwired
module-level globals.

Legacy correlation (divergences, `_correlation_legacy`, correlation alerts)
and price-action levels are reused UNMODIFIED from
`sentinel.correlation_engine` / `sentinel.levels_engine` — that math is not
reimplemented here, matching `calculate_composite`'s own behavior exactly
(including its use of `feed.get_all_data(timeframe_minutes=60, bars=200)`,
which is always keyed off the USDCLP/target symbol group regardless of the
instrument being scored — see `tests/golden/fake_feed.py::get_all_data`).

This module is purely additive: it does not modify or import from
`sentinel.sentinel_core`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sentinel.correlation_engine import calculate_target_correlations, detect_divergence
from sentinel.levels_engine import calculate_levels
from sentinel_engine.config import InstrumentConfig, config_hash
from sentinel_engine.feed import Feed
from sentinel_engine.macro import MacroScorer
from sentinel_engine.technical import TechnicalScorer


@dataclass(frozen=True)
class Snapshot:
    """Immutable point-in-time scoring result produced by `Engine.step()`."""

    ts: datetime | None
    symbol: str
    seq: int
    config_hash: str
    composite_score: float
    direction: str
    signal: str
    blocked: bool
    block_reason: str
    components: dict = field(default_factory=dict)
    levels: dict = field(default_factory=dict)
    divergences: list = field(default_factory=list)
    alerts: list = field(default_factory=list)
    technical: dict = field(default_factory=dict)
    macro: dict = field(default_factory=dict)
    ai_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Plain, JSON-safe dict of every field (datetime kept as-is or None —
        callers that need to serialize to JSON should `.isoformat()` it)."""
        return {
            "ts": self.ts,
            "symbol": self.symbol,
            "seq": self.seq,
            "config_hash": self.config_hash,
            "composite_score": self.composite_score,
            "direction": self.direction,
            "signal": self.signal,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "components": self.components,
            "levels": self.levels,
            "divergences": self.divergences,
            "alerts": self.alerts,
            "technical": self.technical,
            "macro": self.macro,
            "ai_context": self.ai_context,
        }


class Engine:
    """Headless, config-parameterized scoring engine.

    Usage:
        eng = Engine(load_instrument("gold"), feed)
        snap = eng.step()

    Holds ONE `MacroScorer(cfg)` instance for its lifetime (stateful EWMA
    tracker — created once, like `SentinelCore` holds `macro_scorer`).
    """

    def __init__(self, cfg: InstrumentConfig, feed: Feed):
        self.cfg = cfg
        self.feed = feed
        self._macro = MacroScorer(cfg)
        self._config_hash = config_hash(cfg)

    def step(self, seq: int = 0) -> Snapshot:
        cfg = self.cfg
        target = cfg.target

        # 1. Score técnico multi-TF (weight: cfg.composite.weights["technical"])
        technical = TechnicalScorer(cfg).score(self.feed)
        tech_score = technical["composite_score"]
        tech_dir = technical["h4_direction"]

        # 2. Score macro EWMA (weight: cfg.composite.weights["correlation"])
        self._macro.update_tick(self.feed)
        macro = self._macro.score(self.feed)
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
            tech_score * cfg.composite.weights["technical"]
            + macro_score * cfg.composite.weights["correlation"]
        )
        composite = round(min(100, max(0, composite)), 1)

        # Dirección consensuada (técnico + macro)
        dvw = cfg.composite.direction_vote_weights
        dir_votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        for d, w in [(tech_dir, dvw["technical"]), (macro_dir, dvw["macro"])]:
            if d in dir_votes:
                dir_votes[d] += w
        direction = max(dir_votes, key=dir_votes.get)

        # Semáforo
        if composite >= cfg.composite.score_strong_threshold:
            signal = "🟢 FUERTE"
        elif composite >= cfg.composite.score_alert_threshold:
            signal = "🟡 ALERTA"
        else:
            signal = "🔴 ESPERAR"

        # Alertas
        alerts: list = []
        if composite >= cfg.composite.score_alert_threshold:
            alerts.append(f"📊 Score {composite} — {direction}")
        for div in divergences[:3]:
            alerts.append(div["description"])
        for alert in corr.get("alerts", []):
            alerts.append(alert)

        components = {
            "technical": {
                "score": tech_score,
                "weight": cfg.composite.weights["technical"],
                "direction": tech_dir,
                "details": technical,
            },
            "correlation": {
                "score": macro_score,
                "weight": cfg.composite.weights["correlation"],
                "direction": macro_dir,
                "details": corr,
            },
            "_correlation_legacy": {
                "score": corr_score_legacy,
                "direction": corr_dir_legacy,
                "details": corr,
            },
            "_macro": macro,
        }

        return Snapshot(
            ts=None,
            symbol=target,
            seq=seq,
            config_hash=self._config_hash,
            composite_score=composite,
            direction=direction,
            signal=signal,
            blocked=False,
            block_reason="",
            components=components,
            levels=levels,
            divergences=divergences,
            alerts=alerts,
            technical=technical,
            macro=macro,
            ai_context="",
        )
