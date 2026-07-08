"""Gated endpoints (replay/variant/study/fleet/calendar) — this UI rework
wires the CONTRACT only; the orchestration backends (P2 replay sessions, P4
async study/fleet triggers, P6 calendar) are future work. Every one of these
routes must return 501 with a labeled body so the frontend's gating probes
(spec §6) render a placeholder, never a blocked UI."""
from __future__ import annotations

from fastapi.testclient import TestClient


GATED_GET_ROUTES = [
    "/variants",
    "/variant/diff",
    "/study/abc123",
    "/study/latest",
    "/calendar",
]

GATED_POST_ROUTES = [
    "/replay/control",
    "/variant",
    "/variant/branch",
    "/study",
    "/fleet",
]


def test_gated_get_routes_return_501(app_factory):
    app = app_factory(instruments=("gold",), autostart_loop=False)
    with TestClient(app) as client:
        for route in GATED_GET_ROUTES:
            resp = client.get(route)
            assert resp.status_code == 501, route
            body = resp.json()
            assert body["error"] == "not_implemented"
            assert "capability" in body


def test_gated_post_routes_return_501(app_factory):
    app = app_factory(instruments=("gold",), autostart_loop=False)
    with TestClient(app) as client:
        for route in GATED_POST_ROUTES:
            resp = client.post(route, json={})
            assert resp.status_code == 501, route
            body = resp.json()
            assert body["error"] == "not_implemented"


def test_replay_ws_closes_with_gated_code(app_factory):
    app = app_factory(instruments=("gold",), autostart_loop=False)
    with TestClient(app) as client:
        with client.websocket_connect("/replay") as ws:
            data = ws.receive_json()
            assert data == {"error": "not_implemented", "capability": "replay"}
