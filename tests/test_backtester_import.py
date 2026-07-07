"""
Regression test for Defect 1 (SENTINEL revamp, Task 0.3).

sentinel/backtester.py::replay_scoring had a deferred (function-body-local)
import of a nonexistent class: `from sentinel.correlation_engine import
CorrelationEngine`. Because the import lives inside the function body, a
plain `from sentinel.backtester import replay_scoring` does NOT raise —
the crash only happens once `replay_scoring` is actually CALLED. This test
calls it (with an injected fake feed, headless, no MT5) to genuinely
exercise the broken code path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden.fake_feed import FakeFeed  # noqa: E402

from sentinel.backtester import replay_scoring


def test_replay_scoring_does_not_raise_import_error():
    """replay_scoring must run end-to-end without ImportError, using an
    injected FakeFeed so it never touches MT5."""
    df = replay_scoring(bars_back=50, feed=FakeFeed())

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "corr_score" in df.columns
    # Neutral fallback per intent: legacy correlation is excluded from
    # replay scoring (it was never part of the live composite).
    assert (df["corr_score"] == 50.0).all()
