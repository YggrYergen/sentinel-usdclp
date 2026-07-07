"""tests/service/conftest.py — fixtures for the FastAPI service tests.

Uses `tests.golden.fake_feed.FakeFeed` (deterministic, CSV-backed, no
network/MT5) as the injected `Feed` — the same fixture the frozen-core
golden/parity suite drives, per Route P3's contract ("service must be
feed-injectable so tests use FakeFeed").
"""
from __future__ import annotations

import pytest

from sentinel_engine.service.app import create_app
from tests.golden.fake_feed import FakeFeed


@pytest.fixture
def app_factory():
    def _make(instruments=("usdclp",), loop_interval: float = 0.02, autostart_loop: bool = True):
        shared_feed = FakeFeed()
        return create_app(
            feed_factory=lambda name: shared_feed,
            instruments=instruments,
            loop_interval=loop_interval,
            autostart_loop=autostart_loop,
        )

    return _make
