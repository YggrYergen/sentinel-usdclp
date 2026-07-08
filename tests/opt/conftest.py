"""Local pytest config for ``tests/opt`` -- registers the ``slow`` marker.

This repo has no ``pytest.ini``/``pyproject.toml``/``setup.cfg`` (checked at
the time this was added), so there is nowhere else to register a custom
marker without introducing a new shared config file. ``conftest.py`` is the
standard, scoped (this directory only), non-invasive place for it. FLAG: if
a real ``[tool.pytest.ini_options]`` block is added later, this marker
registration should move there instead of living here.
"""
from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "slow: heavy/long-running test, excluded from the default fast run (use -m slow to run only these, or omit -m to run everything including slow)"
    )
