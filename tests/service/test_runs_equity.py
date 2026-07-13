"""tests/service/test_runs_equity.py — TDD for `GET /api/runs/{id}/equity`
(task B8).

Fallback source (no equity artifact on disk): cumulative pnl over the
run's trades, ordered by `ts_out` — reuses the same `registry` mechanism
`/api/runs/{id}/trades` already exposes (`ResearchRegistry.insert_run` +
`.insert_trades`, no `equity_path` set). Shape: `{"points":[{"t":epoch_s,
"v":equity_value}]}`.

An artifact-backed test is included too: `equity_path` pointed at a small
JSON file already shaped `{"points":[...]}`, verifying the endpoint serves
it verbatim instead of recomputing from trades.

Follows the `ResearchRegistry(tmp_path / "research.db")` + `create_app(...,
registry=registry)` + `TestClient` pattern from `test_manage_api.py`.
"""
from __future__ import annotations

import json

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


def _trade(trade_id: str, ts_in: str, ts_out: str, pnl: float) -> dict:
    return {
        "trade_id": trade_id, "ts_in": ts_in, "ts_out": ts_out,
        "px_in": 1.0, "px_out": 1.0, "side": "LONG", "volume": 1.0, "pnl": pnl,
    }


def _seed_run_with_trades(registry, run_id: str, trades: list[dict], equity_path=None) -> None:
    registry.insert_run({
        "run_id": run_id,
        "variant_id": None,
        "params_hash": None,
        "engine": "sentinel-sim",
        "fidelity": "research",
        "status": "done",
        "equity_path": str(equity_path) if equity_path else None,
    })
    registry.insert_trades(run_id, trades)


def test_equity_fallback_cumulative_pnl_from_trades(client, registry):
    run_id = "run-equity-1"
    # Deliberately inserted out of ts_out order to assert the endpoint
    # sorts by ts_out (exit time), not insertion/ts_in order.
    _seed_run_with_trades(registry, run_id, [
        _trade("t2", "2026-01-01T00:00:00Z", "2026-01-01T02:00:00Z", -20.0),
        _trade("t1", "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", 100.0),
        _trade("t3", "2026-01-01T00:00:00Z", "2026-01-01T03:00:00Z", 50.0),
    ])

    resp = client.get(f"/api/runs/{run_id}/equity")
    assert resp.status_code == 200
    body = resp.json()

    t1 = int(pd_ts("2026-01-01T01:00:00Z"))
    t2 = int(pd_ts("2026-01-01T02:00:00Z"))
    t3 = int(pd_ts("2026-01-01T03:00:00Z"))

    assert body == {
        "points": [
            {"t": t1, "v": 100.0},
            {"t": t2, "v": 80.0},
            {"t": t3, "v": 130.0},
        ]
    }


def test_equity_unknown_run_404(client):
    resp = client.get("/api/runs/does-not-exist/equity")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body


def test_equity_prefers_artifact_over_trades(client, registry, tmp_path):
    run_id = "run-equity-artifact"
    equity_file = tmp_path / "equity.json"
    artifact_payload = {"points": [{"t": 1000, "v": 5.0}, {"t": 2000, "v": 7.5}]}
    equity_file.write_text(json.dumps(artifact_payload), encoding="utf-8")

    _seed_run_with_trades(
        registry, run_id,
        [_trade("t1", "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", 999.0)],
        equity_path=equity_file,
    )

    resp = client.get(f"/api/runs/{run_id}/equity")
    assert resp.status_code == 200
    assert resp.json() == artifact_payload


def pd_ts(s: str) -> int:
    import pandas as pd
    return pd.Timestamp(s, tz="UTC").value // 1_000_000_000
