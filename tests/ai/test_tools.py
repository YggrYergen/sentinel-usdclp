"""tests/ai/test_tools.py — TDD for Task C4a: tool registry (pure, no LLM).

Builds a tmp lake (via sentinel_engine.lake.tiers.build_tiers) and a tmp
ResearchRegistry, then exercises TOOLS/execute_tool against them.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from sentinel_engine.ai.tools import TOOLS, execute_tool
from sentinel_engine.lake import store
from sentinel_engine.lake.tiers import build_tiers
from sentinel_engine.research.registry2 import ResearchRegistry

BASE = pd.Timestamp("2026-01-01T00:00:00Z")
BASE_EPOCH = int(BASE.timestamp())
FAR_FUTURE_NOW = BASE_EPOCH + 400 * 86400


def _m1_frame(n: int) -> pd.DataFrame:
    idx = pd.date_range(BASE, periods=n, freq="1min", tz="UTC")
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
def ctx(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root, "XAUUSD", 30)

    db_path = tmp_path / "research.db"
    registry = ResearchRegistry(db_path=db_path)

    strategy_id = registry.upsert_strategy("EMS_TEST", "emasar", "mt5")
    variant_id = registry.upsert_variant(
        strategy_id, "EMS_TEST_V1_M5_c1", {}, "M5", "XAUUSD", "sl_tp",
    )
    registry.insert_run({
        "run_id": "run-1",
        "variant_id": variant_id,
        "engine": "sentinel-sim",
        "fidelity": "research",
        "trades": 5,
        "net": 100.0,
        "pf": 1.5,
        "wr": 0.6,
        "payoff": 1.2,
        "maxdd": 5.0,
        "sharpe": 1.1,
        "fecha_corrida": "2026-01-01T00:00:00Z",
    })
    registry.insert_trades("run-1", [
        {
            "trade_id": "trade-1",
            "ts_in": "2026-01-01T00:01:00Z",
            "ts_out": "2026-01-01T00:05:00Z",
            "px_in": 100.0,
            "px_out": 101.0,
            "side": "LONG",
            "volume": 1.0,
            "sl": 99.0,
            "tp": 102.0,
            "pnl": 10.0,
        },
    ])

    return {"registry": registry, "lake_root": lake_root}, strategy_id, variant_id


# ---------------------------------------------------------------------
# TOOLS shape
# ---------------------------------------------------------------------

def test_tools_is_list_of_anthropic_tool_schema_dicts():
    assert isinstance(TOOLS, list)
    names = {t["name"] for t in TOOLS}
    assert names == {"get_bars", "get_trade_detail", "query_registry", "get_scorecard"}
    for t in TOOLS:
        assert "description" in t
        assert "input_schema" in t
        assert t["input_schema"]["type"] == "object"


# ---------------------------------------------------------------------
# get_bars
# ---------------------------------------------------------------------

def test_get_bars_happy_path(ctx):
    c, _sid, _vid = ctx
    result = execute_tool(
        "get_bars",
        {"symbol": "XAUUSD", "tf": "M1", "from": BASE_EPOCH, "to": BASE_EPOCH + 29 * 60},
        c,
    )
    payload = json.loads(result)
    assert payload["symbol"] == "XAUUSD"
    assert payload["tf_requested"] == "M1"
    assert payload["served_tf"] == "M1"
    assert "clipped" in payload
    assert len(payload["bars"]) == 30
    assert set(payload["bars"][0].keys()) == {"t", "o", "h", "l", "c", "v"}
    assert payload["overlays"] == {}


def test_get_bars_cap_enforced(ctx):
    c, _sid, _vid = ctx
    # Seed a much larger lake so the raw result would exceed the char cap.
    lake_root = c["lake_root"]
    _seed_lake(lake_root, "BIGSYM", 20000)

    result = execute_tool(
        "get_bars",
        {"symbol": "BIGSYM", "tf": "M1", "from": BASE_EPOCH, "to": BASE_EPOCH + 19999 * 60},
        c,
    )
    assert len(result) <= 25_000 * 3.5
    payload = json.loads(result)
    assert payload["clipped"] is True


def test_get_bars_unknown_tf_error_string(ctx):
    c, _sid, _vid = ctx
    result = execute_tool(
        "get_bars",
        {"symbol": "XAUUSD", "tf": "NOTATF", "from": BASE_EPOCH, "to": BASE_EPOCH + 60},
        c,
    )
    assert result.startswith("error:")


# ---------------------------------------------------------------------
# get_trade_detail
# ---------------------------------------------------------------------

def test_get_trade_detail_happy_path(ctx):
    c, _sid, _vid = ctx
    result = execute_tool("get_trade_detail", {"trade_id": "trade-1"}, c)
    payload = json.loads(result)
    assert payload["trade_id"] == "trade-1"
    assert payload["pnl"] == 10.0


def test_get_trade_detail_not_found(ctx):
    c, _sid, _vid = ctx
    result = execute_tool("get_trade_detail", {"trade_id": "nope"}, c)
    assert result.startswith("error:")


# ---------------------------------------------------------------------
# query_registry
# ---------------------------------------------------------------------

def test_query_registry_happy_path(ctx):
    c, sid, _vid = ctx
    result = execute_tool("query_registry", {"filters": {"strategy_id": sid}}, c)
    rows = json.loads(result)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-1"


def test_query_registry_sql_injection_neutralized(ctx):
    c, _sid, _vid = ctx
    malicious = "x'; DROP TABLE run; --"
    result = execute_tool("query_registry", {"filters": {"strategy_id": malicious}}, c)
    rows = json.loads(result)
    assert rows == []

    # run table must still exist/work after the attempt.
    result2 = execute_tool("query_registry", {"filters": {}}, c)
    rows2 = json.loads(result2)
    assert len(rows2) == 1


def test_query_registry_unknown_filter_key_rejected(ctx):
    c, _sid, _vid = ctx
    result = execute_tool("query_registry", {"filters": {"evil_col": "1"}}, c)
    assert result.startswith("error:")


# ---------------------------------------------------------------------
# get_scorecard
# ---------------------------------------------------------------------

def test_get_scorecard_happy_path(ctx):
    c, sid, _vid = ctx
    result = execute_tool("get_scorecard", {"strategy_id": sid}, c)
    payload = json.loads(result)
    assert payload["strategy_id"] == sid
    assert payload["metrics_contract"] == "v1"
    assert "floors" in payload
    assert "real" in payload["floors"]


def test_get_scorecard_unknown_strategy_error_string(ctx):
    c, _sid, _vid = ctx
    result = execute_tool("get_scorecard", {"strategy_id": "nope::nope"}, c)
    assert result.startswith("error:")


# ---------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------

def test_unknown_tool_name_returns_error_string(ctx):
    c, _sid, _vid = ctx
    result = execute_tool("not_a_real_tool", {}, c)
    assert result.startswith("error:")
