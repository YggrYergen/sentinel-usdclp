"""
Equivalence test for sentinel_engine.macro.MacroScorer vs the current
(pre-refactor) macro scoring paths (P1 Task 1.4).

For each of {usdclp, gold, nasdaq}:
  - OLD path: drives the existing scorer (sentinel.macro_scorer.MacroScorer
    for usdclp; sentinel.instrument_panel._update_macro/_calc_macro for
    gold/nasdaq) against a FRESH FakeFeed, with a FIXED 35 update cycles
    before reading the score (matches tests/golden/capture_golden.py's
    WARMUP_CYCLES=35 total-ticks-before-score convention).
  - NEW path: drives sentinel_engine.macro.MacroScorer(load_instrument(name))
    against a SEPARATE fresh FakeFeed, with the SAME 35 update cycles
    before calling .score(feed).

Both feeds must be independent FakeFeed() instances per scorer run —
FakeFeed.get_current_price advances a per-symbol pointer on every call,
so sharing one feed between two scorers would desynchronize them.

All common numeric fields are asserted for EXACT equality (`==`), since
the math (tanh, rounding, EWMA update order) is byte-identical and fully
deterministic given the same tick sequence and asset iteration order.
"""
from __future__ import annotations

import math

import pytest

from sentinel_engine.config import load_instrument
from sentinel_engine.macro import MacroScorer as NewMacroScorer
from tests.golden.fake_feed import FakeFeed

WARMUP_CYCLES = 35  # total update cycles driven before reading a score


def _isclose(a, b):
    # Exact equality is expected everywhere (deterministic, identically
    # rounded floats on both paths). math.isclose kept only as documented
    # fallback per task spec; not currently needed since all assertions
    # below use plain `==`.
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-9)


def _old_usdclp_result() -> dict:
    from sentinel.macro_scorer import MacroScorer as OldMacroScorer

    feed = FakeFeed()
    ms = OldMacroScorer()
    for _ in range(WARMUP_CYCLES):
        ms.update_tick(feed)
    return ms.calculate_score(feed)


def _old_panel_result(symbols_cfg, asset_weights, expected_corrs) -> dict:
    from sentinel.macro_scorer import MacroScorer as OldMacroScorer
    from sentinel.instrument_panel import _update_macro, _calc_macro

    feed = FakeFeed()
    ms = OldMacroScorer()
    for _ in range(WARMUP_CYCLES):
        _update_macro(ms, feed, symbols_cfg, asset_weights, expected_corrs)
    return _calc_macro(ms, feed, symbols_cfg, expected_corrs, asset_weights)


def _new_result(name: str) -> dict:
    feed = FakeFeed()
    cfg = load_instrument(name)
    ms = NewMacroScorer(cfg)
    for _ in range(WARMUP_CYCLES):
        ms.update_tick(feed)
    return ms.score(feed)


def _old_result(name: str) -> dict:
    if name == "usdclp":
        return _old_usdclp_result()
    from sentinel.config import (
        SYMBOLS_GOLD, ASSET_WEIGHTS_GOLD, EXPECTED_CORRELATIONS_GOLD,
        SYMBOLS_NASDAQ, ASSET_WEIGHTS_NASDAQ, EXPECTED_CORRELATIONS_NASDAQ,
    )
    if name == "gold":
        return _old_panel_result(SYMBOLS_GOLD, ASSET_WEIGHTS_GOLD, EXPECTED_CORRELATIONS_GOLD)
    if name == "nasdaq":
        return _old_panel_result(SYMBOLS_NASDAQ, ASSET_WEIGHTS_NASDAQ, EXPECTED_CORRELATIONS_NASDAQ)
    raise ValueError(name)


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_macro_scorer_equivalence(name):
    old = _old_result(name)
    new = _new_result(name)

    # Top-level fields common to both the rich (usdclp) and reduced
    # (gold/nasdaq) old shapes.
    assert new["score"] == old["score"]
    assert new["direction"] == old["direction"]
    assert new["consensus_raw"] == old["consensus_raw"]

    assert set(old["votes"].keys()).issubset(set(new["votes"].keys()))
    assert set(old["votes"].keys()) == set(new["votes"].keys())

    for asset_key, old_vote in old["votes"].items():
        new_vote = new["votes"][asset_key]
        assert new_vote["return_bps"] == old_vote["return_bps"], (name, asset_key, "return_bps")
        assert new_vote["raw_vote"] == old_vote["raw_vote"], (name, asset_key, "raw_vote")
        assert new_vote["confidence"] == old_vote["confidence"], (name, asset_key, "confidence")
        assert new_vote["weighted_vote"] == old_vote["weighted_vote"], (name, asset_key, "weighted_vote")
        assert new_vote["warmup"] == old_vote["warmup"], (name, asset_key, "warmup")

        # New scorer's rich shape must carry the extra fields even when
        # the old reduced (gold/nasdaq) path doesn't expose them.
        assert "ewma_corr" in new_vote
        assert "concordance" in new_vote
        assert "effective_weight" in new_vote

    # usdclp's old path exposes the full rich shape too — check those
    # extra top-level fields for exact equality as well.
    if name == "usdclp":
        assert new["direction_score"] == old["direction_score"]
        assert new["consensus_score"] == old["consensus_score"]
        assert new["confidence_avg"] == old["confidence_avg"]
        assert new["total_assets_tracked"] == old["total_assets_tracked"]
        assert new["assets_warmed_up"] == old["assets_warmed_up"]
