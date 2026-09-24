"""Additive Snapshot fields (data_source, stale_seconds, regime) — UI rework
Task 1. Must never change any existing scoring field; tests/golden stays green."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_snapshot_has_additive_fields(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/snapshot")
        assert resp.status_code == 200
        body = resp.json()
        assert "data_source" in body
        assert isinstance(body["data_source"], str)
        assert "stale_seconds" in body
        assert isinstance(body["stale_seconds"], (int, float))
        assert "regime" in body
        assert body["regime"] is None or isinstance(body["regime"], dict)


def test_snapshot_data_source_reflects_feed_type(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/snapshot")
        body = resp.json()
        # FakeFeed (tests.golden.fake_feed.FakeFeed) is not MT5/historical.
        assert body["data_source"] in ("unknown", "fake", "yahoo")
