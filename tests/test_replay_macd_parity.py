"""
Task 0.4: Defect 2 — replay MACD scoring must match live MACD scoring.

Live path (sentinel/technical_scorer.py:40, `calculate_multi_tf_score`) always
calls `calculate_technical_score(df, normalize_macd=True)` — MACD histogram is
ATR-normalized before being scored.

Replay path (sentinel/backtester.py:141, inside `replay_scoring`) called
`calculate_technical_score(subset)` with NO `normalize_macd` argument, which
defaults to `False` (sentinel/technical_scorer.py:10). That makes replay use
the raw-histogram MACD formula (`_score_macd`, technical_scorer.py:164-175:
`60 + |h|*1000` vs `50 + (h/ATR)*40`) instead of the live formula — so a
backtest replay of the SAME candles as live scoring produces a different
`details.macd.score` (and thus a different composite TF `score`).

This test:
  1. Proves the flag is discriminating on the fixture window used (RED without
     the fix would be vacuous if True/False happened to coincide on this data
     — they do not, see values asserted below).
  2. Proves replay's M1 TF score for a specific, independently-reconstructed
     candle window equals LIVE `calculate_technical_score(window,
     normalize_macd=True)` on that exact window — the parity property the
     defect breaks.

`bars_back=1` pins replay to a single time step (i=200) so the internal
windowing (backtester.py:130-147) can be reconstructed directly from
FakeFeed without duplicating replay's loop: for tf_min=1, replay's
`subset = d[mask].tail(BARS_TO_FETCH)` at i=200 is exactly `m1_data.tail(200)`
because both `d` and `m1_data` are `.tail(...)` slices of the same underlying
CSV-backed series ending at the same last timestamp.
"""
import pytest

from sentinel.backtester import replay_scoring
from sentinel.config import SYMBOLS
from sentinel.technical_scorer import calculate_technical_score
from tests.golden.fake_feed import FakeFeed


def _live_window():
    """Reconstruct the exact M1 candle window replay_scoring(bars_back=1)
    uses internally for its single time step (i=200)."""
    feed = FakeFeed()
    symbol = SYMBOLS["target"]
    m1_data = feed.get_data(symbol, 1, 1 + 200)  # bars_back + 200, per backtester.py:96
    return m1_data.tail(200)  # BARS_TO_FETCH, per backtester.py:138


def test_normalize_macd_flag_is_discriminating_on_fixture():
    """Sanity check: on this fixture window, normalize_macd actually changes
    details.macd.score. If this ever stops discriminating (e.g. fixture
    regenerated with ATR<=0 or a zero histogram), the parity test below
    would pass vacuously — this guards against that."""
    window = _live_window()
    live_true = calculate_technical_score(window, normalize_macd=True)
    live_false = calculate_technical_score(window, normalize_macd=False)

    assert live_true["details"]["macd"]["score"] != live_false["details"]["macd"]["score"]
    assert live_true["score"] != live_false["score"]


def test_replay_m1_score_matches_live_normalize_macd_true():
    """The parity property: replay's M1 TF score for the reconstructed window
    must equal live scoring (normalize_macd=True) on the SAME window — not
    the normalize_macd=False variant.

    Before the fix (backtester.py:141 calling calculate_technical_score(subset)
    with no normalize_macd arg, defaulting to False), replay's m1_score equals
    the normalize_macd=False score (26.0 on this fixture) instead of the live
    normalize_macd=True score (37.5) — this assertion is RED.
    After the fix (normalize_macd=True passed explicitly), it is GREEN.
    """
    window = _live_window()
    live_true = calculate_technical_score(window, normalize_macd=True)

    replay_df = replay_scoring(bars_back=1, feed=FakeFeed())
    assert len(replay_df) == 1

    replay_m1_score = replay_df.iloc[0]["m1_score"]
    assert replay_m1_score == pytest.approx(live_true["score"], abs=1e-9)
