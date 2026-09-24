"""tests/service/test_api_research.py — TDD for the research data endpoints
(M0.3, plan §D.6): /api/strategies, /api/runs(+filters/order/pagination),
/api/runs/{id}, /api/runs/{id}/trades, /api/forward/sessions,
/api/forward/{id}/trades, POST /api/ingest/tokata.

Uses a throwaway `ResearchRegistry` (tmp_path db) injected into `create_app`
via an explicit `registry` kwarg — never touches the real
`D:/WebDev/TOKATA` tree or `data/research.db`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sentinel_engine.research.registry2 import STRATEGY_PALETTE, ResearchRegistry
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


def _seed_basic(registry) -> dict:
    sid = registry.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = registry.upsert_variant(sid, "EMASAR_M5_v1", {}, "M5", "XAUUSD", "original")
    registry.insert_run({
        "run_id": "RUN1",
        "variant_id": vid,
        "engine": "mt5-tester",
        "fidelity": "screening",
        "instrumento": "XAUUSD",
        "trades": 10,
        "net": 100.5,
        "pf": 1.5,
        "wr": 40.0,
        "payoff": 2.0,
        "maxdd": 50.0,
        "sharpe": 1.1,
        "fecha_corrida": "2026-07-01",
        "report_path": "mt5/reports/x.htm",
    })
    registry.insert_run({
        "run_id": "RUN2",
        "variant_id": vid,
        "engine": "mt5-tester",
        "fidelity": "forward",
        "instrumento": "XAUUSD",
        "trades": 5,
        "net": 20.0,
        "pf": 1.1,
        "wr": 50.0,
        "payoff": 1.0,
        "maxdd": 10.0,
        "sharpe": 0.5,
        "fecha_corrida": "2026-07-05",
    })
    registry.insert_trades("RUN1", [
        {
            "trade_id": "T1", "ts_in": "2026-07-01T00:00:00", "ts_out": "2026-07-01T01:00:00",
            "px_in": 100.0, "px_out": 101.0, "side": "LONG", "volume": 0.1,
            "pnl": 10.0, "exit_reason": "TP", "exit_reason_source": "test",
        },
        {
            "trade_id": "T2", "ts_in": "2026-07-01T02:00:00", "ts_out": "2026-07-01T03:00:00",
            "px_in": 102.0, "px_out": 101.5, "side": "SHORT", "volume": 0.2,
            "pnl": -5.0, "exit_reason": "SL", "exit_reason_source": "test",
        },
    ])
    return {"strategy_id": sid, "variant_id": vid}


def _seed_forward(registry) -> str:
    registry.upsert_forward_session({
        "session_id": "SESS1", "strategy_id": None, "variant_id": None,
        "cuenta": "demo1", "perfil": "W2C-02", "inicio": "2026-07-06T00:00:00",
        "fin": None, "estado": "forward", "source_file": "x.csv",
    })
    registry.insert_trades(None, [
        {
            "trade_id": "FT1", "run_id": None, "origin": "strategy", "session_id": "SESS1",
            "ts_in": "2026-07-06T09:15:00", "ts_out": "2026-07-06T09:35:00",
            "px_in": 4141.1, "px_out": 4149.49, "side": "SHORT", "volume": 0.1,
            "pnl": -77548.77, "exit_reason": "INDETERMINADO", "exit_reason_source": "forward_ledger",
        },
    ])
    return "SESS1"


# ---------------------------------------------------------------------
# /api/strategies
# ---------------------------------------------------------------------

def test_get_strategies_shape_and_display_color(client, registry):
    _seed_basic(registry)
    resp = client.get("/api/strategies")
    assert resp.status_code == 200
    body = resp.json()
    assert "strategies" in body
    row = body["strategies"][0]
    for key in (
        "strategy_id", "name", "familia", "platform", "color_idx", "display_color",
        "n_variants", "n_runs", "sweepable", "graduated",
    ):
        assert key in row
    assert row["display_color"] == STRATEGY_PALETTE[row["color_idx"] % len(STRATEGY_PALETTE)]
    assert row["n_variants"] == 1
    assert row["n_runs"] == 2


def test_get_strategies_empty(client):
    resp = client.get("/api/strategies")
    assert resp.status_code == 200
    assert resp.json() == {"strategies": []}


# ---------------------------------------------------------------------
# /api/runs
# ---------------------------------------------------------------------

def test_get_runs_shape(client, registry):
    _seed_basic(registry)
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    row = body["rows"][0]
    for key in (
        "run_id", "variant_id", "display_name", "color_idx", "familia", "instrumento",
        "engine", "fidelity", "periodo_desde", "periodo_hasta", "modelo_sim", "trades",
        "net", "pf", "wr", "payoff", "maxdd", "sharpe", "fecha_corrida", "report_path",
    ):
        assert key in row


def test_get_runs_filter_by_fidelity(client, registry):
    _seed_basic(registry)
    resp = client.get("/api/runs", params={"fidelity": "forward"})
    body = resp.json()
    assert body["total"] == 1
    assert body["rows"][0]["run_id"] == "RUN2"


def test_get_runs_order_and_pagination(client, registry):
    _seed_basic(registry)
    resp = client.get("/api/runs", params={"order_by": "net", "dir": "desc", "limit": 1, "offset": 0})
    body = resp.json()
    assert body["total"] == 2
    assert body["rows"][0]["run_id"] == "RUN1"

    resp2 = client.get("/api/runs", params={"order_by": "net", "dir": "desc", "limit": 1, "offset": 1})
    assert resp2.json()["rows"][0]["run_id"] == "RUN2"


def test_get_runs_filter_by_strategy_and_variant(client, registry):
    seeds = _seed_basic(registry)
    resp = client.get("/api/runs", params={"strategy_id": seeds["strategy_id"]})
    assert resp.json()["total"] == 2
    resp2 = client.get("/api/runs", params={"variant_id": seeds["variant_id"]})
    assert resp2.json()["total"] == 2
    resp3 = client.get("/api/runs", params={"strategy_id": "nonexistent"})
    assert resp3.json()["total"] == 0


# ---------------------------------------------------------------------
# /api/runs/{id}
# ---------------------------------------------------------------------

def test_get_run_by_id(client, registry):
    _seed_basic(registry)
    resp = client.get("/api/runs/RUN1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "RUN1"
    assert "preregistration" in body
    assert "artifacts" in body
    assert body["artifacts"]["report_path"] == "mt5/reports/x.htm"


def test_get_run_by_id_404_error_format(client, registry):
    _seed_basic(registry)
    resp = client.get("/api/runs/NOPE")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]


# ---------------------------------------------------------------------
# /api/runs/{id}/trades
# ---------------------------------------------------------------------

def test_get_run_trades_shape_and_order(client, registry):
    _seed_basic(registry)
    resp = client.get("/api/runs/RUN1/trades")
    assert resp.status_code == 200
    body = resp.json()
    trades = body["trades"]
    assert len(trades) == 2
    assert trades[0]["trade_id"] == "T1"
    assert trades[1]["trade_id"] == "T2"
    for key in (
        "trade_id", "ts_in", "ts_out", "px_in", "px_out", "side", "volume",
        "sl", "tp", "pnl", "mae", "mfe", "exit_reason", "exit_reason_source",
    ):
        assert key in trades[0]


def test_get_run_trades_for_unknown_run_is_empty_not_error(client, registry):
    _seed_basic(registry)
    resp = client.get("/api/runs/NOPE/trades")
    assert resp.status_code == 200
    assert resp.json() == {"trades": []}


# ---------------------------------------------------------------------
# /api/forward/sessions
# ---------------------------------------------------------------------

def test_get_forward_sessions_shape(client, registry):
    _seed_forward(registry)
    resp = client.get("/api/forward/sessions")
    assert resp.status_code == 200
    body = resp.json()
    row = body["sessions"][0]
    for key in (
        "session_id", "display_name", "color_idx", "cuenta", "perfil",
        "inicio", "fin", "estado", "n_trades", "pnl_total",
    ):
        assert key in row
    assert row["n_trades"] == 1
    assert row["pnl_total"] == pytest.approx(-77548.77)


# ---------------------------------------------------------------------
# /api/forward/{id}/trades
# ---------------------------------------------------------------------

def test_get_forward_session_trades_shape(client, registry):
    _seed_forward(registry)
    resp = client.get("/api/forward/SESS1/trades")
    assert resp.status_code == 200
    body = resp.json()
    trades = body["trades"]
    assert len(trades) == 1
    assert trades[0]["trade_id"] == "FT1"
    assert trades[0]["origin"] == "strategy"


# ---------------------------------------------------------------------
# POST /api/ingest/tokata
# ---------------------------------------------------------------------

def test_post_ingest_tokata_runs_import(client, registry, tmp_path, monkeypatch):
    root = tmp_path / "TOKATA_fake"
    (root / "backtest_results").mkdir(parents=True)
    (root / "mt5" / "reports").mkdir(parents=True)
    fixtures = Path(__file__).parent.parent / "research" / "fixtures"
    import shutil
    shutil.copy(fixtures / "mt5_ledger_sample.csv", root / "backtest_results" / "mt5_ledger.csv")
    shutil.copy(fixtures / "preregistro_sample.csv", root / "backtest_results" / "preregistro.csv")

    resp = client.post("/api/ingest/tokata", json={"tokata_root": str(root)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["files"] >= 2
    assert body["rows_new"] > 0

    # idempotent second call
    resp2 = client.post("/api/ingest/tokata", json={"tokata_root": str(root)})
    assert resp2.json()["rows_new"] == 0


def test_post_ingest_tokata_bad_root_error_format(client):
    resp = client.post("/api/ingest/tokata", json={"tokata_root": "Z:/does/not/exist"})
    assert resp.status_code in (400, 404)
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
