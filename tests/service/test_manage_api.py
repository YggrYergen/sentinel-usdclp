"""tests/service/test_manage_api.py — TDD for the management endpoints
(M2.4, plan §D.5/§D.6): `POST /api/variants`, `POST /api/strategies/{id}/estado`.

Uses a throwaway `ResearchRegistry` (tmp_path db) injected into `create_app`
via an explicit `registry` kwarg — never touches the real
`D:/WebDev/TOKATA` tree or `data/research.db`.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.app import create_app
from tests.golden.fake_feed import FakeFeed


@pytest.fixture
def registry(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


@pytest.fixture
def client(registry):
    shared_feed = FakeFeed()
    app = create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        registry=registry,
    )
    with TestClient(app) as c:
        yield c


def _seed_strategy(registry, **kwargs) -> str:
    return registry.upsert_strategy(
        kwargs.get("name", "EMASAR"),
        kwargs.get("familia", "emasar"),
        kwargs.get("platform", "mt5"),
    )


# ---------------------------------------------------------------------
# POST /api/variants
# ---------------------------------------------------------------------

def test_post_variants_creates_variant(client, registry):
    sid = _seed_strategy(registry)
    resp = client.post("/api/variants", json={
        "strategy_id": sid,
        "variant_suffix": "M5_c2_sar3m3",
        "params_delta": {"sar_step": 3},
        "tf": "M5",
        "instrumento": "XAUUSD",
        "modo_salida": "original",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "variant_id" in body
    assert body["variant_id"] == "emasar_XAUUSD_M5_c2_sar3m3"
    assert registry.variant_exists(body["variant_id"])


def test_post_variants_allocates_magic(client, registry):
    sid = _seed_strategy(registry)
    resp = client.post("/api/variants", json={
        "strategy_id": sid,
        "variant_suffix": "v1",
        "params_delta": {},
        "tf": "M5",
        "instrumento": "XAUUSD",
        "modo_salida": "original",
    })
    assert resp.status_code == 200
    vid = resp.json()["variant_id"]
    conn = registry._connect()
    try:
        row = conn.execute(
            "SELECT magic FROM magic_allocation WHERE variant_id=?", (vid,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == 100000


def test_post_variants_duplicate_returns_409(client, registry):
    sid = _seed_strategy(registry)
    payload = {
        "strategy_id": sid,
        "variant_suffix": "v1",
        "params_delta": {},
        "tf": "M5",
        "instrumento": "XAUUSD",
        "modo_salida": "original",
    }
    resp1 = client.post("/api/variants", json=payload)
    assert resp1.status_code == 200
    resp2 = client.post("/api/variants", json=payload)
    assert resp2.status_code == 409
    body = resp2.json()
    assert body["error"]["code"] == "variant_exists"
    assert "message" in body["error"]


def test_post_variants_unknown_strategy_error_format(client):
    resp = client.post("/api/variants", json={
        "strategy_id": "nonexistent",
        "variant_suffix": "v1",
        "params_delta": {},
        "tf": "M5",
        "instrumento": "XAUUSD",
        "modo_salida": "original",
    })
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]


def test_post_variants_validates_against_param_schema(client, registry):
    sid = _seed_strategy(registry)
    conn = registry._connect()
    try:
        conn.execute(
            "UPDATE strategy SET param_schema_json=? WHERE strategy_id=?",
            ('{"sar_step": {"type": "number"}}', sid),
        )
        conn.commit()
    finally:
        conn.close()
    resp = client.post("/api/variants", json={
        "strategy_id": sid,
        "variant_suffix": "v1",
        "params_delta": {"unknown_param": 5},
        "tf": "M5",
        "instrumento": "XAUUSD",
        "modo_salida": "original",
    })
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_params_delta"


def test_post_variants_audit_logged(client, registry):
    sid = _seed_strategy(registry)
    client.post("/api/variants", json={
        "strategy_id": sid,
        "variant_suffix": "v1",
        "params_delta": {},
        "tf": "M5",
        "instrumento": "XAUUSD",
        "modo_salida": "original",
    })
    conn = registry._connect()
    try:
        rows = conn.execute(
            "SELECT accion FROM audit_log WHERE accion='variant_created'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1


# ---------------------------------------------------------------------
# POST /api/strategies/{id}/estado
# ---------------------------------------------------------------------

def test_post_strategy_estado_sets_flag(client, registry):
    sid = _seed_strategy(registry)
    resp = client.post(f"/api/strategies/{sid}/estado", json={"estado": "graduada"})
    assert resp.status_code == 200
    strat = registry.get_strategy(sid)
    assert strat["estado"] == "graduada"
    assert strat["graduated"] is True


def test_post_strategy_estado_pausada_clears_graduated(client, registry):
    sid = _seed_strategy(registry)
    client.post(f"/api/strategies/{sid}/estado", json={"estado": "graduada"})
    client.post(f"/api/strategies/{sid}/estado", json={"estado": "pausada"})
    strat = registry.get_strategy(sid)
    assert strat["estado"] == "pausada"
    assert strat["graduated"] is False


def test_post_strategy_estado_invalid_value_error_format(client, registry):
    sid = _seed_strategy(registry)
    resp = client.post(f"/api/strategies/{sid}/estado", json={"estado": "bogus"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_estado"


def test_post_strategy_estado_unknown_strategy_404(client):
    resp = client.post("/api/strategies/nonexistent/estado", json={"estado": "activa"})
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]


def test_post_strategy_estado_audit_logged(client, registry):
    sid = _seed_strategy(registry)
    client.post(f"/api/strategies/{sid}/estado", json={"estado": "pausada"})
    conn = registry._connect()
    try:
        rows = conn.execute(
            "SELECT accion FROM audit_log WHERE accion='strategy_estado_changed'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
