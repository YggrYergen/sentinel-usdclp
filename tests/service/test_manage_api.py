"""tests/service/test_manage_api.py — TDD for the management endpoints
(M2.4, plan §D.5/§D.6): `POST /api/variants`, `POST /api/strategies/{id}/estado`;
and (M2.5) the backtest-lite job endpoints `POST /api/backtest` +
`GET /api/jobs/{id}`.

Uses a throwaway `ResearchRegistry` (tmp_path db) injected into `create_app`
via an explicit `registry` kwarg — never touches the real
`D:/WebDev/TOKATA` tree or `data/research.db`. The M2.5 tests point
`lake_root` at a small synthetic lake (via a `lake_root` kwarg on
`create_app`), NOT the real `data/lake`, to stay hermetic/fast; the real
XAUUSD-lake determinism/gate check lives in
`tests/sim/test_lite.py::test_emasar_backtest_real_window_is_deterministic`.
"""
from __future__ import annotations

import time

import pandas as pd
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


# ---------------------------------------------------------------------
# POST /api/backtest + GET /api/jobs/{id} (M2.5)
# ---------------------------------------------------------------------

def _mk_synthetic_lake(lake_root) -> None:
    from sentinel_engine.lake.store import write_bars

    n = 400
    start = pd.Timestamp("2026-01-01T00:00:00", tz="UTC")
    idx = pd.date_range(start, periods=n, freq="5min", tz="UTC", name="time")
    # A simple oscillating price path with enough range/volatility to
    # trigger some EMASAR gate combinations over 400 bars.
    import math
    closes = [4000.0 + 20.0 * math.sin(i / 9.0) + (i % 7) * 0.5 for i in range(n)]
    opens = [closes[i - 1] if i > 0 else closes[0] for i in range(n)]
    highs = [max(o, c) + 1.5 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 1.5 for o, c in zip(opens, closes)]
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [100] * n},
        index=idx,
    )
    write_bars(lake_root, "XAUUSD", 5, df)


@pytest.fixture
def registry_with_variant(registry):
    sid = registry.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = registry.upsert_variant(sid, "emasar_XAUUSD_test", {}, "M5", "XAUUSD", "original")
    return registry, sid, vid


@pytest.fixture
def client_with_lake(registry_with_variant, tmp_path):
    registry, sid, vid = registry_with_variant
    lake_root = tmp_path / "lake"
    _mk_synthetic_lake(lake_root)
    shared_feed = FakeFeed()
    app = create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        registry=registry,
        lake_root=lake_root,
    )
    with TestClient(app) as c:
        yield c, registry, vid


def _wait_for_job(client, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        body = resp.json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


def test_post_backtest_runs_and_produces_queryable_run(client_with_lake):
    client, registry, vid = client_with_lake
    resp = client.post("/api/backtest", json={
        "variant_id": vid, "symbol": "XAUUSD", "tf": "M5",
        "desde": "2026-01-01", "hasta": "2026-01-02",
    })
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    assert resp.json()["status"] == "queued"

    job = _wait_for_job(client, job_id)
    assert job["status"] == "done"
    run_id = job["run_id"]
    assert run_id

    runs_resp = client.get("/api/runs", params={"variant_id": vid})
    assert runs_resp.status_code == 200
    body = runs_resp.json()
    assert body["total"] == 1
    assert body["rows"][0]["run_id"] == run_id
    assert body["rows"][0]["engine"] == "sentinel-sim"
    assert body["rows"][0]["fidelity"] == "research"


def test_get_job_unknown_id_404(client_with_lake):
    client, _registry, _vid = client_with_lake
    resp = client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]


def test_post_backtest_unknown_variant_404(client_with_lake):
    client, _registry, _vid = client_with_lake
    resp = client.post("/api/backtest", json={
        "variant_id": "nonexistent", "symbol": "XAUUSD", "tf": "M5",
    })
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "variant_not_found"


def test_backtest_determinism_same_variant_twice(client_with_lake):
    client, registry, vid = client_with_lake
    resp1 = client.post("/api/backtest", json={
        "variant_id": vid, "symbol": "XAUUSD", "tf": "M5",
        "desde": "2026-01-01", "hasta": "2026-01-02",
    })
    job1 = _wait_for_job(client, resp1.json()["job_id"])
    resp2 = client.post("/api/backtest", json={
        "variant_id": vid, "symbol": "XAUUSD", "tf": "M5",
        "desde": "2026-01-01", "hasta": "2026-01-02",
    })
    job2 = _wait_for_job(client, resp2.json()["job_id"])

    trades1 = registry.get_trades_for_run(job1["run_id"])
    trades2 = registry.get_trades_for_run(job2["run_id"])
    assert len(trades1) == len(trades2)
    for t1, t2 in zip(trades1, trades2):
        for key in ("ts_in", "ts_out", "px_in", "px_out", "side", "pnl", "exit_reason"):
            assert t1[key] == t2[key]
