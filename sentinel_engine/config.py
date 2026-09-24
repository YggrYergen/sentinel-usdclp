"""
sentinel_engine.config — per-instrument configuration loader (P1, Task 1.1+1.2).

Loads a frozen, value-comparable `InstrumentConfig` from
`sentinel_engine/instruments/<name>.yaml` and exposes a deterministic
content hash (`config_hash`) suitable for tagging backtests/snapshots
with the exact scoring parameters that produced them.

This module does NOT modify or import any live scoring behavior — it is
a pure, additive read-only config layer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict

import yaml

_INSTRUMENTS_DIR = Path(__file__).parent / "instruments"


@dataclass(frozen=True)
class TrackerConfig:
    lambda_var: float
    lambda_cov: float
    concordance_window: int


@dataclass(frozen=True)
class MacroConfig:
    tanh_sensitivity: float
    tracker: TrackerConfig
    warmup_threshold: int
    direction_threshold: float


@dataclass(frozen=True)
class IndicatorConfig:
    ema_fast: int
    ema_mid: int
    ema_slow: int
    ema_trend: int
    rsi_period: int
    rsi_overbought: float
    rsi_oversold: float
    macd_fast: int
    macd_slow: int
    macd_signal: int
    bb_period: int
    bb_std: float
    atr_period: int


@dataclass(frozen=True)
class TechnicalConfig:
    tf_weights: Dict[str, float] = field(default_factory=dict)
    indicators: IndicatorConfig = None


@dataclass(frozen=True)
class CompositeConfig:
    weights: Dict[str, float] = field(default_factory=dict)
    direction_vote_weights: Dict[str, int] = field(default_factory=dict)
    score_alert_threshold: float = 0
    score_strong_threshold: float = 0


@dataclass(frozen=True)
class DataConfig:
    bars_to_fetch: int
    timeframes: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class InstrumentConfig:
    instrument: str
    target: str
    symbols: Dict[str, str]
    expected_correlations: Dict[str, float]
    asset_weights: Dict[str, float]
    macro: MacroConfig
    technical: TechnicalConfig
    composite: CompositeConfig
    data: DataConfig


def _freeze_dict(d: dict) -> Dict:
    """Return a plain dict copy (kept mutable-free by construction — never
    mutated after load). Dataclasses above are frozen; the nested dict
    *values* (symbols, expected_correlations, asset_weights, tf_weights,
    timeframes, weights, direction_vote_weights) are compared by value via
    normal dict `==`, which is order-independent."""
    return dict(d)


def load_instrument(name: str) -> InstrumentConfig:
    """Load `sentinel_engine/instruments/<name>.yaml` into an InstrumentConfig.

    `name` should be one of: "usdclp", "gold", "nasdaq" (no extension).
    """
    path = _INSTRUMENTS_DIR / f"{name}.yaml"
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    macro_raw = raw["macro"]
    tracker_raw = macro_raw["tracker"]
    macro = MacroConfig(
        tanh_sensitivity=float(macro_raw["tanh_sensitivity"]),
        tracker=TrackerConfig(
            lambda_var=float(tracker_raw["lambda_var"]),
            lambda_cov=float(tracker_raw["lambda_cov"]),
            concordance_window=int(tracker_raw["concordance_window"]),
        ),
        warmup_threshold=int(macro_raw["warmup_threshold"]),
        direction_threshold=float(macro_raw["direction_threshold"]),
    )

    tech_raw = raw["technical"]
    ind_raw = tech_raw["indicators"]
    technical = TechnicalConfig(
        tf_weights=_freeze_dict({k: float(v) for k, v in tech_raw["tf_weights"].items()}),
        indicators=IndicatorConfig(
            ema_fast=int(ind_raw["ema_fast"]),
            ema_mid=int(ind_raw["ema_mid"]),
            ema_slow=int(ind_raw["ema_slow"]),
            ema_trend=int(ind_raw["ema_trend"]),
            rsi_period=int(ind_raw["rsi_period"]),
            rsi_overbought=float(ind_raw["rsi_overbought"]),
            rsi_oversold=float(ind_raw["rsi_oversold"]),
            macd_fast=int(ind_raw["macd_fast"]),
            macd_slow=int(ind_raw["macd_slow"]),
            macd_signal=int(ind_raw["macd_signal"]),
            bb_period=int(ind_raw["bb_period"]),
            bb_std=float(ind_raw["bb_std"]),
            atr_period=int(ind_raw["atr_period"]),
        ),
    )

    comp_raw = raw["composite"]
    composite = CompositeConfig(
        weights=_freeze_dict({k: float(v) for k, v in comp_raw["weights"].items()}),
        direction_vote_weights=_freeze_dict(
            {k: int(v) for k, v in comp_raw["direction_vote_weights"].items()}
        ),
        score_alert_threshold=float(comp_raw["score_alert_threshold"]),
        score_strong_threshold=float(comp_raw["score_strong_threshold"]),
    )

    data_raw = raw["data"]
    data = DataConfig(
        bars_to_fetch=int(data_raw["bars_to_fetch"]),
        timeframes=_freeze_dict({k: int(v) for k, v in data_raw["timeframes"].items()}),
    )

    return InstrumentConfig(
        instrument=str(raw["instrument"]),
        target=str(raw["target"]),
        symbols=_freeze_dict({k: str(v) for k, v in raw["symbols"].items()}),
        expected_correlations=_freeze_dict(
            {k: float(v) for k, v in raw["expected_correlations"].items()}
        ),
        asset_weights=_freeze_dict({k: float(v) for k, v in raw["asset_weights"].items()}),
        macro=macro,
        technical=technical,
        composite=composite,
        data=data,
    )


def config_hash(cfg: InstrumentConfig) -> str:
    """Deterministic, platform-stable content hash of an InstrumentConfig.

    Builds a canonical dict of ALL config fields (via `dataclasses.asdict`,
    which recurses through nested frozen dataclasses into plain dicts),
    serializes with `json.dumps(sort_keys=True, ...)` for order-independence,
    and returns the first 12 hex chars of the sha256 digest.
    """
    canonical = asdict(cfg)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:12]
