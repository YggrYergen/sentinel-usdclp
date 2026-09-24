"""
Equivalence tests for the two live-dashboard-only MacroScorer methods that
`sentinel_engine.macro.MacroScorer` previously lacked (P1 Task 1.6c-1):
`calculate_score_at_window` and `calculate_fusion`.

calculate_score_at_window
--------------------------
For usdclp, the OLD `sentinel.macro_scorer.MacroScorer` and NEW
`sentinel_engine.macro.MacroScorer(load_instrument("usdclp"))` are driven
with an IDENTICAL warmup (35 update_tick cycles, matching
tests/golden/capture_golden.py's WARMUP_CYCLES convention) on their own
FRESH FakeFeed instances, then `calculate_score_at_window(feed, lookback_bars)`
is compared for EXACT equality across lookback_bars in {1, 3, 5, 15}.

The OLD MacroScorer is USDCLP-hardwired (module-level ASSET_WEIGHTS /
SYMBOLS / EXPECTED_CORRELATIONS in sentinel.macro_scorer / sentinel.config),
so it cannot produce a gold/nasdaq window score to compare against — there
is no old per-instrument equivalent for window scores. For gold/nasdaq we
therefore only assert the NEW scorer runs and returns the expected shape.

calculate_fusion
-----------------
This method is a PURE function of its 4 scalar arguments (no feed/tracker
access), so it is compared directly across a full grid of tech/macro
score & direction combinations for EXACT dict equality between the OLD and
NEW implementations.
"""
from __future__ import annotations

import pytest

from sentinel_engine.config import load_instrument
from sentinel_engine.macro import MacroScorer as NewMacroScorer
from tests.golden.fake_feed import FakeFeed

WARMUP_CYCLES = 35  # total update cycles driven before reading a score

LOOKBACKS = [1, 3, 5, 15]
INSTRUMENTS = ["usdclp", "gold", "nasdaq"]

DIRECTIONS = ["LONG", "SHORT", "NEUTRAL"]
SCORES = [20, 45, 50, 55, 80]


# ── calculate_score_at_window ──────────────────────────────────────────

def _old_usdclp_scorer_warmed() -> tuple:
    from sentinel.macro_scorer import MacroScorer as OldMacroScorer

    feed = FakeFeed()
    ms = OldMacroScorer()
    for _ in range(WARMUP_CYCLES):
        ms.update_tick(feed)
    return ms, feed


def _new_scorer_warmed(name: str) -> tuple:
    feed = FakeFeed()
    cfg = load_instrument(name)
    ms = NewMacroScorer(cfg)
    for _ in range(WARMUP_CYCLES):
        ms.update_tick(feed)
    return ms, feed


@pytest.mark.parametrize("lookback_bars", LOOKBACKS)
def test_calculate_score_at_window_usdclp_exact_equivalence(lookback_bars):
    old_ms, old_feed = _old_usdclp_scorer_warmed()
    new_ms, new_feed = _new_scorer_warmed("usdclp")

    old_result = old_ms.calculate_score_at_window(old_feed, lookback_bars=lookback_bars)
    new_result = new_ms.calculate_score_at_window(new_feed, lookback_bars=lookback_bars)

    assert new_result["score"] == old_result["score"]
    assert new_result["direction"] == old_result["direction"]
    assert new_result["consensus_raw"] == old_result["consensus_raw"]
    assert new_result["lookback_bars"] == old_result["lookback_bars"]

    assert set(new_result["votes"].keys()) == set(old_result["votes"].keys())
    for asset_key, old_vote in old_result["votes"].items():
        new_vote = new_result["votes"][asset_key]
        assert new_vote["return_bps"] == old_vote["return_bps"], (asset_key, "return_bps")
        assert new_vote["raw_vote"] == old_vote["raw_vote"], (asset_key, "raw_vote")
        assert new_vote["confidence"] == old_vote["confidence"], (asset_key, "confidence")
        assert new_vote["weighted_vote"] == old_vote["weighted_vote"], (asset_key, "weighted_vote")
        assert new_vote["warmup"] == old_vote["warmup"], (asset_key, "warmup")


@pytest.mark.parametrize("name", ["gold", "nasdaq"])
@pytest.mark.parametrize("lookback_bars", LOOKBACKS)
def test_calculate_score_at_window_non_usdclp_shape(name, lookback_bars):
    # No old per-instrument equivalent exists for gold/nasdaq window
    # scores (the old MacroScorer is USDCLP-hardwired) — just assert the
    # new scorer runs cleanly and returns the expected shape/keys.
    new_ms, new_feed = _new_scorer_warmed(name)
    result = new_ms.calculate_score_at_window(new_feed, lookback_bars=lookback_bars)

    assert set(result.keys()) == {"score", "direction", "consensus_raw", "votes", "lookback_bars"}
    assert result["lookback_bars"] == lookback_bars
    assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    assert 0 <= result["score"] <= 100
    assert isinstance(result["votes"], dict)
    assert set(result["votes"].keys()) == set(load_instrument(name).asset_weights.keys())
    for vote in result["votes"].values():
        assert set(vote.keys()) == {"return_bps", "raw_vote", "confidence", "weighted_vote", "warmup"}


# ── calculate_fusion ─────────────────────────────────────────────────

def _fusion_grid():
    for tech_score in SCORES:
        for macro_score in SCORES:
            for tech_dir in DIRECTIONS:
                for macro_dir in DIRECTIONS:
                    yield (tech_score, tech_dir, macro_score, macro_dir)


@pytest.mark.parametrize("tech_score,tech_direction,macro_score,macro_direction", list(_fusion_grid()))
def test_calculate_fusion_exact_equivalence(tech_score, tech_direction, macro_score, macro_direction):
    from sentinel.macro_scorer import MacroScorer as OldMacroScorer

    old_ms = OldMacroScorer()
    new_ms = NewMacroScorer(load_instrument("usdclp"))

    old_result = old_ms.calculate_fusion(tech_score, tech_direction, macro_score, macro_direction)
    new_result = new_ms.calculate_fusion(tech_score, tech_direction, macro_score, macro_direction)

    assert new_result == old_result
