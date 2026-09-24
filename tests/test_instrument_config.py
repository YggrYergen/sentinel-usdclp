"""
Tests for sentinel_engine.config (P1 Task 1.1+1.2).

Round-trip proof: the loaded per-instrument YAML config equals the CURRENT
live scoring constants defined across sentinel/config.py, sentinel/macro_scorer.py,
sentinel/technical_scorer.py and sentinel/sentinel_core.py. This test imports
NO code from sentinel_engine into sentinel — it only reads sentinel's live
constants as the source of truth and compares against sentinel_engine's
loaded YAML config.
"""

import math

import pytest

from sentinel_engine.config import load_instrument, config_hash

from sentinel.config import (
    SYMBOLS,
    EXPECTED_CORRELATIONS,
    SYMBOLS_GOLD,
    EXPECTED_CORRELATIONS_GOLD,
    ASSET_WEIGHTS_GOLD,
    SYMBOLS_NASDAQ,
    EXPECTED_CORRELATIONS_NASDAQ,
    ASSET_WEIGHTS_NASDAQ,
    TIMEFRAMES,
    BARS_TO_FETCH,
    WEIGHTS,
    SCORE_ALERT_THRESHOLD,
    SCORE_STRONG_THRESHOLD,
    INDICATORS,
)
from sentinel.macro_scorer import ASSET_WEIGHTS, TANH_SENSITIVITY
from sentinel.technical_scorer import TF_WEIGHTS

INSTRUMENTS = {
    "usdclp": dict(
        symbols=SYMBOLS,
        expected_correlations=EXPECTED_CORRELATIONS,
        asset_weights=ASSET_WEIGHTS,
    ),
    "gold": dict(
        symbols=SYMBOLS_GOLD,
        expected_correlations=EXPECTED_CORRELATIONS_GOLD,
        asset_weights=ASSET_WEIGHTS_GOLD,
    ),
    "nasdaq": dict(
        symbols=SYMBOLS_NASDAQ,
        expected_correlations=EXPECTED_CORRELATIONS_NASDAQ,
        asset_weights=ASSET_WEIGHTS_NASDAQ,
    ),
}

# Global constants (identical across all 3 instruments — verified in the spec)
MACRO_DIRECTION_THRESHOLD = 0.15
MACRO_WARMUP_THRESHOLD = 30
TRACKER_LAMBDA_VAR = 0.85
TRACKER_LAMBDA_COV = 0.97
TRACKER_CONCORDANCE_WINDOW = 60
DIRECTION_VOTE_WEIGHTS = {"technical": 2, "macro": 3}


def _isclose(a, b):
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-12)


def _dicts_close(actual: dict, expected: dict):
    assert set(actual.keys()) == set(expected.keys())
    for k in expected:
        assert _isclose(float(actual[k]), float(expected[k])), (k, actual[k], expected[k])


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_target_and_symbols_roundtrip(name):
    cfg = load_instrument(name)
    source_symbols = INSTRUMENTS[name]["symbols"]

    assert cfg.target == source_symbols["target"]

    expected_symbols = {k: v for k, v in source_symbols.items() if k != "target"}
    assert cfg.symbols == expected_symbols
    # No key lost or added
    assert set(cfg.symbols.keys()) | {"target"} == set(source_symbols.keys())


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_expected_correlations_roundtrip(name):
    cfg = load_instrument(name)
    _dicts_close(cfg.expected_correlations, INSTRUMENTS[name]["expected_correlations"])


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_asset_weights_roundtrip(name):
    cfg = load_instrument(name)
    _dicts_close(cfg.asset_weights, INSTRUMENTS[name]["asset_weights"])


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_macro_globals_roundtrip(name):
    cfg = load_instrument(name)
    assert _isclose(cfg.macro.tanh_sensitivity, TANH_SENSITIVITY)
    assert _isclose(cfg.macro.tracker.lambda_var, TRACKER_LAMBDA_VAR)
    assert _isclose(cfg.macro.tracker.lambda_cov, TRACKER_LAMBDA_COV)
    assert cfg.macro.tracker.concordance_window == TRACKER_CONCORDANCE_WINDOW
    assert cfg.macro.warmup_threshold == MACRO_WARMUP_THRESHOLD
    assert _isclose(cfg.macro.direction_threshold, MACRO_DIRECTION_THRESHOLD)


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_technical_roundtrip(name):
    cfg = load_instrument(name)
    _dicts_close(cfg.technical.tf_weights, TF_WEIGHTS)

    ind = cfg.technical.indicators
    assert ind.ema_fast == INDICATORS.ema_fast
    assert ind.ema_mid == INDICATORS.ema_mid
    assert ind.ema_slow == INDICATORS.ema_slow
    assert ind.ema_trend == INDICATORS.ema_trend
    assert ind.rsi_period == INDICATORS.rsi_period
    assert _isclose(ind.rsi_overbought, INDICATORS.rsi_overbought)
    assert _isclose(ind.rsi_oversold, INDICATORS.rsi_oversold)
    assert ind.macd_fast == INDICATORS.macd_fast
    assert ind.macd_slow == INDICATORS.macd_slow
    assert ind.macd_signal == INDICATORS.macd_signal
    assert ind.bb_period == INDICATORS.bb_period
    assert _isclose(ind.bb_std, INDICATORS.bb_std)
    assert ind.atr_period == INDICATORS.atr_period


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_composite_roundtrip(name):
    cfg = load_instrument(name)
    assert _isclose(cfg.composite.weights["technical"], WEIGHTS.technical)
    assert _isclose(cfg.composite.weights["correlation"], WEIGHTS.correlation)
    assert cfg.composite.direction_vote_weights == DIRECTION_VOTE_WEIGHTS
    assert _isclose(cfg.composite.score_alert_threshold, SCORE_ALERT_THRESHOLD)
    assert _isclose(cfg.composite.score_strong_threshold, SCORE_STRONG_THRESHOLD)


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_data_roundtrip(name):
    cfg = load_instrument(name)
    assert cfg.data.bars_to_fetch == BARS_TO_FETCH
    assert cfg.data.timeframes == TIMEFRAMES


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_config_hash_deterministic(name):
    h1 = config_hash(load_instrument(name))
    h2 = config_hash(load_instrument(name))
    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 12


def test_config_hash_distinct_across_instruments():
    hashes = {name: config_hash(load_instrument(name)) for name in ("usdclp", "gold", "nasdaq")}
    assert len(set(hashes.values())) == 3, hashes
