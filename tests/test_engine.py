"""
Equivalence test for sentinel_engine.engine.Engine vs the current
(pre-refactor) scoring paths (P1 Task 1.6a).

usdclp: OLD = sentinel.sentinel_core.SentinelCore.calculate_composite()
(drives macro_scorer.update_tick 34x externally + calculate_composite's own
internal 1x = 35 total ticks before scoring, matching
tests/golden/capture_golden.py's WARMUP_CYCLES=35 convention). NEW =
sentinel_engine.engine.Engine(load_instrument("usdclp"), feed).step(), driven
with the SAME 34 external ticks on engine._macro before calling step() (which
itself does the same +1 internal tick, reaching the same 35-tick tracker
state). Full calculate_composite-shaped subset is compared for EXACT
equality: composite_score, direction, signal, blocked, block_reason,
components (all four sub-keys), levels, divergences, alerts.

gold, nasdaq: these do not go through SentinelCore (hardwired to USDCLP) —
their OLD path is tests/golden/capture_golden.py's capture_golden(), which
drives 35 EXTERNAL update cycles then scores with NO extra internal tick.
To reach the SAME 35-tick tracker state via the engine (whose step() always
does its own +1 internal tick), the engine side drives only 34 external
ticks before calling step(). {technical, levels} are compared for exact
equality; macro is compared on the fields capture_golden's reduced
`instrument_panel._calc_macro` shape actually exposes (see
tests/test_macro_engine.py, task 1.4, for why the engine's macro shape is
intentionally richer for gold/nasdaq).

Two independent FakeFeed instances are used per comparison (OLD vs NEW) —
FakeFeed.get_current_price advances a per-symbol pointer on every call, so
sharing one feed between two scorers would desynchronize them.
"""
from __future__ import annotations

import pytest

from sentinel_engine.config import load_instrument
from sentinel_engine.engine import Engine
from tests.golden.capture_golden import capture_golden
from tests.golden.fake_feed import FakeFeed

# External update_tick calls driven on the engine's macro tracker BEFORE
# calling step() (step() itself does exactly 1 more internal update_tick,
# reaching the same 35-total-ticks-before-score state as both OLD paths).
ENGINE_WARMUP_TICKS = 34


def _old_usdclp() -> dict:
    from sentinel.sentinel_core import SentinelCore

    feed = FakeFeed()
    core = SentinelCore(feed)
    for _ in range(34):
        core.macro_scorer.update_tick(feed)
    result = core.calculate_composite()
    result.pop("meta", None)
    return result


def _new_usdclp() -> dict:
    feed = FakeFeed()
    cfg = load_instrument("usdclp")
    engine = Engine(cfg, feed)
    for _ in range(ENGINE_WARMUP_TICKS):
        engine._macro.update_tick(feed)
    snap = engine.step()
    return snap.to_dict()


def test_usdclp_engine_matches_calculate_composite():
    old = _old_usdclp()
    new = _new_usdclp()

    assert new["composite_score"] == old["composite_score"]
    assert new["direction"] == old["direction"]
    assert new["signal"] == old["signal"]
    assert new["blocked"] == old["blocked"]
    assert new["block_reason"] == old["block_reason"]
    assert new["levels"] == old["levels"]
    assert new["divergences"] == old["divergences"]
    assert new["alerts"] == old["alerts"]

    old_comp = old["components"]
    new_comp = new["components"]
    assert new_comp["technical"] == old_comp["technical"]
    assert new_comp["correlation"] == old_comp["correlation"]
    assert new_comp["_correlation_legacy"] == old_comp["_correlation_legacy"]
    assert new_comp["_macro"] == old_comp["_macro"]


def _assert_macro_subset(old_macro: dict, new_macro: dict, name: str) -> None:
    """`capture_golden`'s gold/nasdaq macro shape is the REDUCED
    `instrument_panel._calc_macro` shape (no direction_score/consensus_score
    top-level fields; votes lack ewma_corr/concordance/effective_weight).
    `sentinel_engine.macro.MacroScorer` intentionally always returns the
    RICH shape (already proven equivalent for the fields both share in
    tests/test_macro_engine.py, task 1.4). So compare every field OLD
    actually has for exact equality, rather than full dict equality."""
    for key in ("score", "direction", "consensus_raw", "confidence_avg",
                "total_assets_tracked", "assets_warmed_up"):
        assert new_macro[key] == old_macro[key], (name, key, old_macro[key], new_macro[key])

    assert set(new_macro["votes"].keys()) == set(old_macro["votes"].keys())
    for asset_key, old_vote in old_macro["votes"].items():
        new_vote = new_macro["votes"][asset_key]
        for vkey in ("return_bps", "raw_vote", "confidence", "weighted_vote", "warmup"):
            assert new_vote[vkey] == old_vote[vkey], (name, asset_key, vkey)


@pytest.mark.parametrize("name", ["gold", "nasdaq"])
def test_panel_engine_matches_capture_golden(name):
    old = capture_golden(name, FakeFeed())

    feed = FakeFeed()
    cfg = load_instrument(name)
    engine = Engine(cfg, feed)
    for _ in range(ENGINE_WARMUP_TICKS):
        engine._macro.update_tick(feed)
    snap = engine.step()

    assert snap.technical == old["technical"]
    _assert_macro_subset(old["macro"], snap.macro, name)
    assert snap.levels == old["levels"]
