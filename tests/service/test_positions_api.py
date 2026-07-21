"""tests/service/test_positions_api.py — TDD for B3-api `GET /api/positions`.

Uses a throwaway `ResearchRegistry` (tmp_path db) injected into
`create_app`, same pattern as tests/service/test_scorecard.py. Deals are
inserted directly into `deals_raw` (synthetic fixture rows shaped like
`sentinel_engine.live.deals_watcher._DEAL_COLUMNS`) so the endpoint's own
query + `sentinel_engine.live.grouping.group_positions` reuse can be
exercised end to end.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.app import create_app
from tests.golden.fake_feed import FakeFeed

_DEAL_COLUMNS = (
    "ticket", "position_id", "symbol", "side", "volume",
    "price", "profit", "magic", "time", "entry_type",
    "origin", "strategy_id", "variant_id",
    "leverage", "contract_size",
)


@pytest.fixture
def registry(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


def _insert_deals(registry, deals: list[dict]) -> None:
    conn = sqlite3.connect(str(registry.db_path))
    try:
        cols = ", ".join(_DEAL_COLUMNS)
        placeholders = ", ".join("?" for _ in _DEAL_COLUMNS)
        for d in deals:
            conn.execute(
                f"INSERT INTO deals_raw({cols}) VALUES ({placeholders})",
                tuple(d.get(c) for c in _DEAL_COLUMNS),
            )
        conn.commit()
    finally:
        conn.close()


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


def _deal(ticket, position_id, symbol, side, volume, price, profit, magic, time, entry_type, origin, strategy_id=None, variant_id=None, leverage=None, contract_size=None):
    return {
        "ticket": ticket, "position_id": position_id, "symbol": symbol, "side": side,
        "volume": volume, "price": price, "profit": profit, "magic": magic, "time": time,
        "entry_type": entry_type, "origin": origin, "strategy_id": strategy_id, "variant_id": variant_id,
        "leverage": leverage, "contract_size": contract_size,
    }


def test_positions_empty(client):
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    assert resp.json() == {"groups": []}


def test_positions_shape_single_position(client, registry):
    _insert_deals(registry, [
        _deal(1, 100, "EURUSD", "buy", 1.0, 1.1000, 0.0, 111, 1000, "IN", "human"),
        _deal(2, 100, "EURUSD", "buy", 1.0, 1.1050, 50.0, 111, 1100, "OUT", "human"),
    ])
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["groups"]) == 1
    group = body["groups"][0]
    assert set(group.keys()) == {
        "group_id", "symbol", "side", "magic", "strategy_id", "first_in", "last_out",
        "is_open", "net", "lots", "children",
    }
    assert group["symbol"] == "EURUSD"
    assert group["side"] == "buy"
    assert group["magic"] == 111
    assert group["first_in"] == 1000
    assert group["last_out"] == 1100
    assert group["net"] == 50.0
    assert group["lots"] == 1.0
    assert len(group["children"]) == 1
    child = group["children"][0]
    assert set(child.keys()) == {
        "position_id", "ts_in", "ts_out", "px_in", "px_out", "volume", "pnl",
        "pct", "mae", "mfe", "needs_excursions", "is_open",
        "spread_open", "spread_open_min", "spread_close", "fills",
    }
    assert child["position_id"] == 100
    assert child["ts_in"] == 1000
    assert child["ts_out"] == 1100
    assert child["px_in"] == 1.1000
    assert child["px_out"] == 1.1050
    assert child["volume"] == 1.0
    assert child["pnl"] == 50.0
    assert child["pct"] is None
    assert child["mae"] is None
    assert child["mfe"] is None
    assert child["needs_excursions"] is True
    assert len(child["fills"]) == 1
    fill = child["fills"][0]
    assert set(fill.keys()) == {"ticket", "price", "volume", "profit", "time"}
    assert fill["ticket"] == 2
    assert fill["price"] == 1.1050
    assert fill["volume"] == 1.0
    assert fill["profit"] == 50.0
    assert fill["time"] == 1100


def test_positions_filter_by_origin(client, registry):
    _insert_deals(registry, [
        _deal(1, 100, "EURUSD", "buy", 1.0, 1.1, 0.0, 111, 1000, "IN", "human"),
        _deal(2, 100, "EURUSD", "buy", 1.0, 1.11, 10.0, 111, 1100, "OUT", "human"),
        _deal(3, 200, "EURUSD", "buy", 1.0, 1.1, 0.0, 900001, 2000, "IN", "ia"),
        _deal(4, 200, "EURUSD", "buy", 1.0, 1.12, 20.0, 900001, 2100, "OUT", "ia"),
    ])
    resp = client.get("/api/positions", params={"origin": "ia"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["groups"]) == 1
    assert body["groups"][0]["children"][0]["position_id"] == 200


def test_positions_filter_by_symbol(client, registry):
    _insert_deals(registry, [
        _deal(1, 100, "EURUSD", "buy", 1.0, 1.1, 0.0, 111, 1000, "IN", "human"),
        _deal(2, 100, "EURUSD", "buy", 1.0, 1.11, 10.0, 111, 1100, "OUT", "human"),
        _deal(3, 200, "GBPUSD", "buy", 1.0, 1.3, 0.0, 112, 2000, "IN", "human"),
        _deal(4, 200, "GBPUSD", "buy", 1.0, 1.31, 10.0, 112, 2100, "OUT", "human"),
    ])
    resp = client.get("/api/positions", params={"symbol": "GBPUSD"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["groups"]) == 1
    assert body["groups"][0]["symbol"] == "GBPUSD"


def test_positions_limit_applies_to_groups(client, registry):
    deals = []
    for i in range(5):
        pid = 100 + i
        t_in = 1000 + i * 1000
        t_out = t_in + 100
        magic = 200 + i
        deals.append(_deal(pid * 10 + 1, pid, "EURUSD", "buy", 1.0, 1.1, 0.0, magic, t_in, "IN", "human"))
        deals.append(_deal(pid * 10 + 2, pid, "EURUSD", "buy", 1.0, 1.11, 10.0, magic, t_out, "OUT", "human"))
    _insert_deals(registry, deals)
    resp = client.get("/api/positions", params={"limit": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["groups"]) == 2


def test_positions_ordered_by_first_in_desc(client, registry):
    _insert_deals(registry, [
        _deal(1, 100, "EURUSD", "buy", 1.0, 1.1, 0.0, 111, 1000, "IN", "human"),
        _deal(2, 100, "EURUSD", "buy", 1.0, 1.11, 10.0, 111, 1100, "OUT", "human"),
        _deal(3, 200, "EURUSD", "buy", 1.0, 1.1, 0.0, 222, 5000, "IN", "human"),
        _deal(4, 200, "EURUSD", "buy", 1.0, 1.12, 20.0, 222, 5100, "OUT", "human"),
    ])
    resp = client.get("/api/positions")
    body = resp.json()
    first_ins = [g["first_in"] for g in body["groups"]]
    assert first_ins == sorted(first_ins, reverse=True)
    assert first_ins[0] == 5000


def test_positions_multi_lot_group_has_multiple_children(client, registry):
    # Same symbol/side/magic, entries within 90s -> one group, two children.
    _insert_deals(registry, [
        _deal(1, 100, "EURUSD", "buy", 1.0, 1.1, 0.0, 111, 1000, "IN", "strategy", "strat_a", "var_a"),
        _deal(2, 100, "EURUSD", "buy", 1.0, 1.11, 10.0, 111, 1100, "OUT", "strategy", "strat_a", "var_a"),
        _deal(3, 101, "EURUSD", "buy", 1.0, 1.101, 0.0, 111, 1030, "IN", "strategy", "strat_a", "var_a"),
        _deal(4, 101, "EURUSD", "buy", 1.0, 1.115, 14.0, 111, 1130, "OUT", "strategy", "strat_a", "var_a"),
    ])
    resp = client.get("/api/positions", params={"origin": "strategy"})
    body = resp.json()
    assert len(body["groups"]) == 1
    group = body["groups"][0]
    assert len(group["children"]) == 2
    assert group["lots"] == 2.0
    assert group["net"] == 24.0


def test_positions_skips_position_without_in_deal(client, registry):
    # A stray OUT-only position_id must not crash the endpoint (known
    # grouping._build_positions StopIteration hazard, defended in the
    # router by pre-filtering).
    _insert_deals(registry, [
        _deal(1, 100, "EURUSD", "buy", 1.0, 1.1, 0.0, 111, 1000, "IN", "human"),
        _deal(2, 100, "EURUSD", "buy", 1.0, 1.11, 10.0, 111, 1100, "OUT", "human"),
        _deal(3, 999, "EURUSD", "buy", 1.0, 1.12, 5.0, 111, 1200, "OUT", "human"),
    ])
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["groups"]) == 1
    assert body["groups"][0]["children"][0]["position_id"] == 100


def test_positions_pct_computed_when_margin_inputs_present(client, registry):
    # margin = volume * contract_size * px_in / leverage
    #        = 1.0 * 100000 * 1.1 / 100 = 1100.0
    # pct = profit / margin = 50.0 / 1100.0
    _insert_deals(registry, [
        _deal(1, 100, "EURUSD", "buy", 1.0, 1.1000, 0.0, 111, 1000, "IN", "human",
              leverage=100, contract_size=100000.0),
        _deal(2, 100, "EURUSD", "buy", 1.0, 1.1050, 50.0, 111, 1100, "OUT", "human",
              leverage=100, contract_size=100000.0),
    ])
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    child = resp.json()["groups"][0]["children"][0]
    assert child["pct"] == pytest.approx(50.0 / 1100.0)


def test_positions_pct_null_when_margin_inputs_missing(client, registry):
    # No leverage/contract_size captured -> pct stays null (current behavior).
    _insert_deals(registry, [
        _deal(1, 100, "EURUSD", "buy", 1.0, 1.1000, 0.0, 111, 1000, "IN", "human"),
        _deal(2, 100, "EURUSD", "buy", 1.0, 1.1050, 50.0, 111, 1100, "OUT", "human"),
    ])
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    child = resp.json()["groups"][0]["children"][0]
    assert child["pct"] is None


def test_positions_filter_by_strategy_id(client, registry):
    _insert_deals(registry, [
        _deal(1, 100, "XAUUSD", "buy", 0.1, 4000.0, 0.0, 800001, 1000, "IN", "strategy", "strat_a", "var_a"),
        _deal(2, 100, "XAUUSD", "buy", 0.1, 4005.0, 5.0, 800001, 1100, "OUT", "strategy", "strat_a", "var_a"),
        _deal(3, 200, "XAUUSD", "buy", 0.1, 4000.0, 0.0, 800002, 2000, "IN", "strategy", "strat_b", "var_b"),
        _deal(4, 200, "XAUUSD", "buy", 0.1, 4010.0, 10.0, 800002, 2100, "OUT", "strategy", "strat_b", "var_b"),
    ])
    resp = client.get("/api/positions", params={"origin": "strategy", "strategy_id": "strat_b"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["groups"]) == 1
    group = body["groups"][0]
    assert group["strategy_id"] == "strat_b"
    assert group["children"][0]["position_id"] == 200


def test_positions_is_open_when_no_out_deal(client, registry):
    # An OPEN with no matching OUT deal -> still open.
    _insert_deals(registry, [
        _deal(1, 100, "XAUUSD", "buy", 0.1, 4000.0, 0.0, 800001, 1000, "IN", "strategy", "strat_a"),
    ])
    resp = client.get("/api/positions", params={"origin": "strategy"})
    body = resp.json()
    group = body["groups"][0]
    assert group["is_open"] is True
    assert group["children"][0]["is_open"] is True
    assert group["children"][0]["ts_out"] is None


def test_positions_join_spread_when_recorded(client, registry):
    _insert_deals(registry, [
        _deal(1, 100, "XAUUSD", "buy", 0.1, 4000.0, 0.0, 800001, 1000, "IN", "strategy", "strat_a"),
        _deal(2, 100, "XAUUSD", "buy", 0.1, 4005.0, 5.0, 800001, 1100, "OUT", "strategy", "strat_a"),
    ])
    registry.record_position_spread(
        100, ticket_open=100, spread_open=0.50, spread_open_min=0.50, spread_open_ts=1000,
        spread_close=0.62, spread_close_ts=1100,
    )
    resp = client.get("/api/positions", params={"origin": "strategy"})
    child = resp.json()["groups"][0]["children"][0]
    assert child["spread_open"] == 0.50
    assert child["spread_open_min"] == 0.50
    assert child["spread_close"] == 0.62


def test_positions_spread_null_when_not_recorded(client, registry):
    _insert_deals(registry, [
        _deal(1, 100, "XAUUSD", "buy", 0.1, 4000.0, 0.0, 800001, 1000, "IN", "strategy", "strat_a"),
        _deal(2, 100, "XAUUSD", "buy", 0.1, 4005.0, 5.0, 800001, 1100, "OUT", "strategy", "strat_a"),
    ])
    resp = client.get("/api/positions", params={"origin": "strategy"})
    child = resp.json()["groups"][0]["children"][0]
    assert child["spread_open"] is None
    assert child["spread_open_min"] is None
    assert child["spread_close"] is None


def test_positions_pct_null_when_leverage_zero(client, registry):
    _insert_deals(registry, [
        _deal(1, 100, "EURUSD", "buy", 1.0, 1.1000, 0.0, 111, 1000, "IN", "human",
              leverage=0, contract_size=100000.0),
        _deal(2, 100, "EURUSD", "buy", 1.0, 1.1050, 50.0, 111, 1100, "OUT", "human",
              leverage=0, contract_size=100000.0),
    ])
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    child = resp.json()["groups"][0]["children"][0]
    assert child["pct"] is None
