"""GET /levers — serializes sentinel_engine.opt.levers.LEVER_GROUPS +
priors_for(cfg) for the Lab Zone A lever console (UI rework spec §4.2/§6)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_levers_endpoint_returns_all_groups(app_factory):
    app = app_factory(instruments=("gold",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/levers", params={"instrument": "gold"})
        assert resp.status_code == 200
        body = resp.json()
        assert "groups" in body
        names = {g["name"] for g in body["groups"]}
        assert "G1_indicator_params" in names
        assert "G4_composite_thresholds" in names
        for group in body["groups"]:
            for param in group["params"]:
                assert set(param.keys()) >= {"name", "lo", "hi", "is_int", "production_value"}
                assert param["lo"] <= param["hi"]


def test_levers_endpoint_unknown_instrument_404(app_factory):
    app = app_factory(instruments=("gold",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/levers", params={"instrument": "not-a-real-one"})
        assert resp.status_code == 404
