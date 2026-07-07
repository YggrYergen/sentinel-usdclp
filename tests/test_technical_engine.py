"""
Equivalence test for sentinel_engine.technical.TechnicalScorer vs the
current (pre-refactor) technical scoring path (P1 Task 1.5).

For each of {usdclp, gold, nasdaq}:
  - OLD path: sentinel.technical_scorer.calculate_multi_tf_score(feed, target)
    against a FRESH FakeFeed.
  - NEW path: sentinel_engine.technical.TechnicalScorer(load_instrument(name))
    .score(feed) against a SEPARATE fresh FakeFeed.

Technical scoring only calls `feed.get_data` (no pointer-advancing
`get_current_price`), so a shared feed would in fact be safe here too —
but independent FakeFeed() instances are used per side for cleanliness
and to mirror the macro-engine equivalence test's convention
(tests/test_macro_engine.py).

Both paths are pure, deterministic functions of the same fixture CSV
data, so the two result dicts must be exactly equal — down to every
nested per-timeframe score/direction/details/signals entry and the
rsi_divergences list.
"""
from __future__ import annotations

import pytest

from sentinel_engine.config import load_instrument
from sentinel_engine.technical import TechnicalScorer
from tests.golden.fake_feed import FakeFeed


def _old_result(target: str) -> dict:
    from sentinel.technical_scorer import calculate_multi_tf_score

    feed = FakeFeed()
    return calculate_multi_tf_score(feed, target)


def _new_result(name: str) -> dict:
    feed = FakeFeed()
    cfg = load_instrument(name)
    ts = TechnicalScorer(cfg)
    return ts.score(feed)


@pytest.mark.parametrize("name", ["usdclp", "gold", "nasdaq"])
def test_technical_scorer_equivalence(name):
    cfg = load_instrument(name)
    old = _old_result(cfg.target)
    new = _new_result(name)

    assert new == old, (name, new, old)
