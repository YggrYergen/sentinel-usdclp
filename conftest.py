"""Root pytest configuration.

Quarantine for pathologically slow tests
----------------------------------------
Measured 2026-07-26: a full-repo run took roughly an hour, which made the suite
unusable as a pre-commit gate — agents and humans alike were left polling a run
that never seemed to finish. Per-file timing found the cost concentrated in three
files under ``tests/opt/``:

===========================================  ==========================================
File                                         Measured cost
===========================================  ==========================================
``tests/opt/test_fast_replay.py``            4 of its 5 tests each exceeded 90 s
``tests/opt/test_study.py``                  ``test_smoke_study...`` exceeded 90 s
``tests/opt/test_evaluator.py``              ~82 s total, 7-20 s per test
===========================================  ==========================================

These are not unit tests. They replay real market data through the optimizer and
score it — backtests wearing a pytest costume. They are genuinely valuable, so
they are NOT deleted: they are marked ``slow`` here and deselected by the
``addopts`` in ``pytest.ini``. Run them explicitly with ``-m slow`` (or
``-m "slow or not slow"`` for everything) whenever you touch the optimizer, and
in any release or CI check.

Marking happens by path rather than by decorating each test, so the quarantine
list stays in one readable place and no test body is edited to achieve it.
"""

from __future__ import annotations

import pytest

# Paths (repo-relative, forward slashes) whose tests are quarantined as `slow`.
SLOW_TEST_PATHS = (
    "tests/opt/test_fast_replay.py",
    "tests/opt/test_study.py",
    "tests/opt/test_evaluator.py",
)


def pytest_collection_modifyitems(config, items):
    """Attach the `slow` marker to every test living in a quarantined file."""
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if any(path.endswith(slow_path) for slow_path in SLOW_TEST_PATHS):
            item.add_marker(pytest.mark.slow)
