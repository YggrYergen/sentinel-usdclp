"""P3 Task 3.1 — GET /snapshot and GET /config return the live Engine schema."""
from __future__ import annotations

from fastapi.testclient import TestClient

from sentinel_engine.config import config_hash, load_instrument

SNAPSHOT_FIELDS = {
    "ts", "symbol", "seq", "config_hash", "composite_score", "direction",
    "signal", "blocked", "block_reason", "components", "levels",
    "divergences", "alerts", "technical", "macro", "ai_context",
    "data_source", "stale_seconds", "regime",
}


def test_snapshot_endpoint_returns_engine_schema(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/snapshot")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == SNAPSHOT_FIELDS
        assert body["symbol"] == load_instrument("usdclp").target
        assert isinstance(body["composite_score"], (int, float))
        assert body["seq"] == 0  # seeded exactly once at app construction


def test_snapshot_endpoint_selects_instrument(app_factory):
    app = app_factory(instruments=("usdclp", "gold"), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/snapshot", params={"instrument": "gold"})
        assert resp.status_code == 200
        assert resp.json()["symbol"] == load_instrument("gold").target


def test_snapshot_unknown_instrument_404(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/snapshot", params={"instrument": "does-not-exist"})
        assert resp.status_code == 404


def test_config_endpoint_matches_loaded_config(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/config")
        assert resp.status_code == 200
        body = resp.json()
        cfg = load_instrument("usdclp")
        assert body["config_hash"] == config_hash(cfg)
        assert body["config"]["target"] == cfg.target
        assert body["config"]["composite"]["weights"] == cfg.composite.weights
        assert body["instruments"] == ["usdclp"]


def test_config_endpoint_selects_instrument(app_factory):
    app = app_factory(instruments=("usdclp", "nasdaq"), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/config", params={"instrument": "nasdaq"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["instrument"] == "nasdaq"
        assert body["config_hash"] == config_hash(load_instrument("nasdaq"))
