"""GET /models — model/effort catalog for the Chat header controls
(UI rework spec §4.1)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_models_endpoint_returns_catalog(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/models")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["models"], list) and len(body["models"]) >= 1
        assert all({"key", "label"} <= set(m.keys()) for m in body["models"])
        assert isinstance(body["effort_levels"], list)
        assert isinstance(body["web_search_available"], bool)
        assert isinstance(body["thinking_available"], bool)
