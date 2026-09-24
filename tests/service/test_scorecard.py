"""tests/service/test_scorecard.py — TDD for CT-3
`GET /api/strategies/{id}/scorecard` (Wave B, B2).

Uses a throwaway `ResearchRegistry` (tmp_path db) injected into
`create_app`, same pattern as tests/service/test_api_research.py.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel_engine.research import scorecard as scorecard_mod
from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.app import create_app
from tests.golden.fake_feed import FakeFeed


@pytest.fixture(autouse=True)
def _clear_scorecard_cache():
    scorecard_mod.clear_cache()
    yield
    scorecard_mod.clear_cache()


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


def _set_baseline_ref(registry, strategy_id: str, run_id: str | None) -> None:
    conn = registry._connect()
    try:
        conn.execute("UPDATE strategy SET baseline_ref=? WHERE strategy_id=?", (run_id, strategy_id))
        conn.commit()
    finally:
        conn.close()


def _seed_strategy_with_deals(registry) -> dict:
    sid = registry.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = registry.upsert_variant(sid, "EMASAR_M5_v1", {}, "M5", "XAUUSD", "original")
    magic = registry.allocate_magic(sid, vid)

    conn = registry._connect()
    try:
        conn.execute(
            "INSERT INTO deals_raw(ticket, position_id, symbol, side, volume, price, profit, "
            "magic, time, entry_type, origin, strategy_id, variant_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, 100, "XAUUSD", "LONG", 0.1, 100.0, 10.0, magic, 1751328000, "OUT", "strategy", sid, vid),
        )
        conn.execute(
            "INSERT INTO deals_raw(ticket, position_id, symbol, side, volume, price, profit, "
            "magic, time, entry_type, origin, strategy_id, variant_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (2, 101, "XAUUSD", "SHORT", 0.2, 102.0, -5.0, magic, 1751414400, "OUT", "strategy", sid, vid),
        )
        conn.commit()
    finally:
        conn.close()
    return {"strategy_id": sid, "variant_id": vid, "magic": magic}


def _seed_baseline_run(registry, strategy_id: str, variant_id: str) -> str:
    registry.insert_run({
        "run_id": "BASE1",
        "variant_id": variant_id,
        "engine": "mt5-tester",
        "fidelity": "research",
        "periodo_desde": "2026-01-01",
        "periodo_hasta": "2026-02-01",
        "trades": 2,
        "net": 15.0,
        "fecha_corrida": "2026-02-01",
    })
    registry.insert_trades("BASE1", [
        {
            "trade_id": "BT1", "ts_in": "2026-01-01T00:00:00Z", "ts_out": "2026-01-01T01:00:00Z",
            "px_in": 100.0, "px_out": 105.0, "sl": 99.0, "side": "LONG", "volume": 1.0,
            "pnl": 20.0, "exit_reason": "TP", "exit_reason_source": "test",
        },
        {
            "trade_id": "BT2", "ts_in": "2026-01-02T00:00:00Z", "ts_out": "2026-01-02T01:00:00Z",
            "px_in": 100.0, "px_out": 95.0, "sl": 102.0, "side": "LONG", "volume": 1.0,
            "pnl": -5.0, "exit_reason": "SL", "exit_reason_source": "test",
        },
    ])
    _set_baseline_ref(registry, strategy_id, "BASE1")
    return "BASE1"


def test_scorecard_shape_ct3(client, registry):
    seeds = _seed_strategy_with_deals(registry)
    resp = client.get(f"/api/strategies/{seeds['strategy_id']}/scorecard")
    assert resp.status_code == 200
    body = resp.json()

    assert body["strategy_id"] == seeds["strategy_id"]
    assert body["tf"] == "M5"
    assert body["metrics_contract"] == "v1"
    assert body["baseline_ref"] is None

    real = body["floors"]["real"]
    for key in (
        "trades", "net", "pf", "wr", "payoff", "expectancy_r", "expectancy_r_flag",
        "net_per_day", "trades_per_day", "maxdd_pct", "sharpe_d", "window", "source",
    ):
        assert key in real
    assert "from" in real["window"] and "to" in real["window"]
    assert "runs" in real["source"] and "sessions" in real["source"]

    assert body["floors"]["teorico"] is None


def test_scorecard_real_from_deals_origin_strategy(client, registry):
    seeds = _seed_strategy_with_deals(registry)
    resp = client.get(f"/api/strategies/{seeds['strategy_id']}/scorecard")
    real = resp.json()["floors"]["real"]
    assert real["trades"] == 2
    assert real["net"] == 5.0  # 10.0 + -5.0
    # deals_raw carries no sl -> expectancy_r must fall back to ccy flag
    assert real["expectancy_r_flag"] == "no_sl_fallback_ccy"


def test_scorecard_real_counts_positions_not_deals(client, registry):
    """2026-07-21: a closed position is ONE realized trade (its IN deal @0 +
    its OUT deal @pnl), NOT two. Counting each deal inflated `trades` (and
    diluted expectancy/sharpe with the zero-pnl IN rows). A still-OPEN position
    (only an IN) is not a realized trade and must be excluded."""
    sid = registry.upsert_strategy("SARX", "sarx", "mt5")
    vid = registry.upsert_variant(sid, "SARX_M5_v1", {}, "M5", "XAUUSD", "original")
    magic = registry.allocate_magic(sid, vid)
    conn = registry._connect()
    try:
        rows = [
            # position 200: IN (profit 0) + OUT (+30) -> ONE winning trade
            (10, 200, "XAUUSD", "LONG", 0.1, 100.0, 0.0, magic, 1751328000, "IN", "strategy", sid, vid),
            (11, 200, "XAUUSD", "SELL", 0.1, 101.0, 30.0, magic, 1751328600, "OUT", "strategy", sid, vid),
            # position 201: IN (profit 0) + OUT (-10) -> ONE losing trade
            (12, 201, "XAUUSD", "LONG", 0.1, 100.0, 0.0, magic, 1751414400, "IN", "strategy", sid, vid),
            (13, 201, "XAUUSD", "SELL", 0.1, 99.0, -10.0, magic, 1751415000, "OUT", "strategy", sid, vid),
            # position 202: OPEN (only IN) -> NOT a realized trade
            (14, 202, "XAUUSD", "LONG", 0.1, 100.0, 0.0, magic, 1751500000, "IN", "strategy", sid, vid),
        ]
        for row in rows:
            conn.execute(
                "INSERT INTO deals_raw(ticket, position_id, symbol, side, volume, price, profit, "
                "magic, time, entry_type, origin, strategy_id, variant_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
        conn.commit()
    finally:
        conn.close()
    real = client.get(f"/api/strategies/{sid}/scorecard").json()["floors"]["real"]
    assert real["trades"] == 2       # two CLOSED positions, not 5 deals
    assert real["net"] == 20.0       # 30 + (-10); the zero-pnl IN rows add nothing
    assert real["wr"] == 0.5         # 1 win / 1 loss


def test_scorecard_teorico_only_from_baseline_ref_run(client, registry):
    seeds = _seed_strategy_with_deals(registry)
    _seed_baseline_run(registry, seeds["strategy_id"], seeds["variant_id"])
    scorecard_mod.clear_cache()

    resp = client.get(f"/api/strategies/{seeds['strategy_id']}/scorecard")
    body = resp.json()
    assert body["baseline_ref"] == "BASE1"

    teorico = body["floors"]["teorico"]
    assert teorico is not None
    assert teorico["trades"] == 2
    assert teorico["net"] == 15.0  # 20.0 + -5.0
    assert teorico["source"]["runs"] == ["BASE1"]
    # baseline trades DO carry sl -> expectancy_r should be computed, not flagged
    assert teorico["expectancy_r_flag"] == "ok"


def test_scorecard_unknown_strategy_404(client):
    resp = client.get("/api/strategies/does-not-exist/scorecard")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "strategy_not_found"


def test_scorecard_cache_60s(client, registry, monkeypatch):
    seeds = _seed_strategy_with_deals(registry)
    resp1 = client.get(f"/api/strategies/{seeds['strategy_id']}/scorecard")
    net1 = resp1.json()["floors"]["real"]["net"]

    # add another deal after first read -- cached response should NOT change
    conn = registry._connect()
    try:
        conn.execute(
            "INSERT INTO deals_raw(ticket, position_id, symbol, side, volume, price, profit, "
            "magic, time, entry_type, origin, strategy_id, variant_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (3, 102, "XAUUSD", "LONG", 0.1, 100.0, 999.0, seeds["magic"], 1751500800, "OUT",
             "strategy", seeds["strategy_id"], seeds["variant_id"]),
        )
        conn.commit()
    finally:
        conn.close()

    resp2 = client.get(f"/api/strategies/{seeds['strategy_id']}/scorecard")
    assert resp2.json()["floors"]["real"]["net"] == net1

    scorecard_mod.clear_cache()
    resp3 = client.get(f"/api/strategies/{seeds['strategy_id']}/scorecard")
    assert resp3.json()["floors"]["real"]["net"] != net1
