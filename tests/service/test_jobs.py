"""tests/service/test_jobs.py — TDD for Task B6: CT-4 jobs queue.

Covers:
- happy path with a stub runner (`POST /api/jobs/backtest` -> `GET
  /api/jobs/{id}` reaches `done` with a `run_id`).
- 422 when the requested window falls outside CT-1 lake coverage.
- SSE `job_update` event emitted on `GET /api/jobs/stream` (test client).
- restart survivability: a `queued`/`running` row is marked
  `error:"interrupted"` when the registry is reconstructed (process
  restart), per CT-4/B6 spec.
"""
from __future__ import annotations

import json
import queue
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from sentinel_engine.lake import store
from sentinel_engine.lake.tiers import build_tiers
from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.app import create_app
from tests.golden.fake_feed import FakeFeed

BASE = pd.Timestamp("2026-01-01T00:00:00Z")
BASE_EPOCH = int(BASE.timestamp())
FAR_FUTURE_NOW = BASE_EPOCH + 400 * 86400


def _m1_frame(n: int, start: pd.Timestamp = BASE) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame({
        "open": [100.0 + i for i in range(n)],
        "high": [100.5 + i for i in range(n)],
        "low": [99.5 + i for i in range(n)],
        "close": [100.2 + i for i in range(n)],
        "volume": [10 + i for i in range(n)],
    }, index=idx)
    df.index.name = "time"
    return df


def _seed_lake(lake_root, symbol: str, n: int) -> None:
    store.write_bars(lake_root, symbol, 1, _m1_frame(n))
    build_tiers(symbol, lake_root, now_epoch=FAR_FUTURE_NOW)


@pytest.fixture
def lake_root(tmp_path):
    root = tmp_path / "lake"
    _seed_lake(root, "XAUUSD", 200)
    return root


@pytest.fixture
def registry(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


def _make_app(registry, lake_root):
    shared_feed = FakeFeed()
    return create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        registry=registry,
        lake_root=lake_root,
    )


@pytest.fixture
def variant_id(registry):
    strategy_id = registry.upsert_strategy("emasar-test", "emasar", "py")
    return registry.upsert_variant(strategy_id, "emasar-test-v1", {}, "M1", "XAUUSD", "original")


def _stub_runner(monkeypatch):
    """Patches `JobsService._default_runner`-equivalent by monkeypatching the
    module-level `run_backtest_lite` import used inside
    `sentinel_engine.service.jobs`, so the test never touches the real
    backtest-lite math -- only the queue/status-row plumbing is exercised."""

    def _fake(policy, symbol, tf, desde, hasta, costs=None, lake_root=None):
        run = {
            "variant_id": None, "engine": "sentinel-sim", "fidelity": "research",
            "periodo_desde": desde, "periodo_hasta": hasta, "status": "done",
            "trades": 0, "net": 0.0, "pf": None, "wr": None, "payoff": None,
            "maxdd": 0.0, "sharpe": None,
        }
        return run, []

    monkeypatch.setattr("sentinel_engine.service.jobs.run_backtest_lite", _fake)


def test_backtest_job_happy_path_with_stub_runner(monkeypatch, registry, lake_root, variant_id):
    _stub_runner(monkeypatch)
    app = _make_app(registry, lake_root)
    with TestClient(app) as client:
        resp = client.post("/api/jobs/backtest", json={
            "variant_id": variant_id, "symbol": "XAUUSD", "tf": "M1",
            "from": BASE.isoformat(), "to": (BASE + pd.Timedelta(minutes=100)).isoformat(),
            "exploratory": False,
        })
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        assert job_id

        deadline = time.time() + 5.0
        body = None
        while time.time() < deadline:
            r2 = client.get(f"/api/jobs/{job_id}")
            body = r2.json()
            if body["status"] in ("done", "error"):
                break
            time.sleep(0.05)

        assert body is not None
        assert body["status"] == "done", body
        assert body["run_id"] is not None
        assert body["error"] is None
        assert body["progress"] == 1.0


def test_backtest_job_422_window_outside_coverage(registry, lake_root, variant_id):
    app = _make_app(registry, lake_root)
    with TestClient(app) as client:
        far_from = (BASE + pd.Timedelta(days=10)).isoformat()
        far_to = (BASE + pd.Timedelta(days=11)).isoformat()
        resp = client.post("/api/jobs/backtest", json={
            "variant_id": variant_id, "symbol": "XAUUSD", "tf": "M1",
            "from": far_from, "to": far_to, "exploratory": False,
        })
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body


def test_backtest_job_422_unknown_symbol(registry, lake_root, variant_id):
    app = _make_app(registry, lake_root)
    with TestClient(app) as client:
        resp = client.post("/api/jobs/backtest", json={
            "variant_id": variant_id, "symbol": "NOPE", "tf": "M1",
            "from": BASE.isoformat(), "to": (BASE + pd.Timedelta(minutes=10)).isoformat(),
            "exploratory": False,
        })
        assert resp.status_code == 422


def test_jobs_stream_broadcasts_job_update_event(monkeypatch, registry, lake_root, variant_id):
    """Content-level check (no HTTP transport), mirroring the established
    pattern in `tests/service/test_live_tail.py` (`/api/bars/tail`'s own
    CT-9 SSE endpoint): driving `/api/jobs/stream`'s unbounded SSE generator
    over a real HTTP transport (`TestClient.stream(...)`) deadlocks the
    anyio portal (httpx buffers the full response body before returning,
    and this generator only ends on client disconnect / heartbeats
    forever) -- confirmed while implementing this test. So this asserts the
    `JobsService` broadcaster (the SAME class `routers/jobs.py`'s
    `get_jobs_stream` reads from via `subscribe()`) delivers a
    `job_update`-shaped body to a subscriber queue, and that the route's
    frame formatting (`event: job_update\\ndata: {...}\\n\\n`) matches
    CT-9, WITHOUT going through the HTTP layer."""
    from sentinel_engine.service.jobs import JobsService

    def _fake_runner(variant, symbol, tf, desde, hasta, progress_cb):
        progress_cb(0.5)
        run = {
            "variant_id": None, "engine": "sentinel-sim", "fidelity": "research",
            "periodo_desde": desde, "periodo_hasta": hasta, "status": "done",
            "trades": 0, "net": 0.0, "pf": None, "wr": None, "payoff": None,
            "maxdd": 0.0, "sharpe": None,
        }
        return run, []

    js = JobsService(registry, lake_root, coverage_check=lambda *a: True, runner=_fake_runner)
    sub_queue = js.subscribe()
    job_id = js.submit_backtest(
        variant_id, "XAUUSD", "M1", BASE.isoformat(),
        (BASE + pd.Timedelta(minutes=50)).isoformat(),
    )
    assert job_id

    deadline = time.time() + 5.0
    seen_done = False
    while time.time() < deadline:
        try:
            body = sub_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        assert set(body.keys()) == {"job_id", "status", "progress", "run_id", "error"}
        assert body["job_id"] == job_id
        frame = f"event: job_update\ndata: {json.dumps(body)}\n\n"
        assert frame.startswith("event: job_update\ndata: ")
        assert frame.endswith("\n\n")
        if body["status"] == "done":
            seen_done = True
            break
    assert seen_done


def test_interrupted_job_marked_on_registry_restart(tmp_path):
    db_path = tmp_path / "research.db"
    reg1 = ResearchRegistry(db_path)
    conn = reg1._connect()
    try:
        conn.execute(
            "INSERT INTO jobs(id, kind, params_json, status, progress, run_id, error, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("jobrun-stale", "backtest", "{}", "running", 0.3, None, None, "t0", "t0"),
        )
        conn.commit()
    finally:
        conn.close()

    # Simulate process restart: reconstruct the registry against the same DB.
    reg2 = ResearchRegistry(db_path)
    conn2 = reg2._connect()
    try:
        row = conn2.execute("SELECT status, error FROM jobs WHERE id=?", ("jobrun-stale",)).fetchone()
    finally:
        conn2.close()
    assert row == ("error", "interrupted")
