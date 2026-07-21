"""tests/service/test_strategies_chart_spec.py — TDD for Task 1a
`GET /api/strategies/chart-specs` (per-strategy chart spec: native timeframe +
indicator list + structured rules, derived read-only from
`sentinel_engine.strategies.live_configs_20`).

Uses the same throwaway-registry TestClient pattern as
`tests/service/test_positions_api.py` (not edited here).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.app import create_app
from sentinel_engine.strategies.live_configs_20 import (
    CONFIG_TK_MOMENTUM,
    CONFIGS_20,
    CONFIGS_GOLIVE,
    CONFIGS_GOLIVE_DEDUP,
    MAGIC_BY_ID,
    MAGIC_BY_ID_GOLIVE,
)
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


def _get_specs(client) -> dict:
    resp = client.get("/api/strategies/chart-specs")
    assert resp.status_code == 200
    body = resp.json()
    assert "specs" in body
    return body["specs"]


def test_specs_cover_live_golive_tk_ids(client):
    specs = _get_specs(client)
    expected_ids = (
        {c["id"] for c in CONFIGS_20}
        | {c["id"] for c in CONFIGS_GOLIVE}
        | {c["id"] for c in CONFIGS_GOLIVE_DEDUP}
        | {CONFIG_TK_MOMENTUM["id"]}
    )
    assert expected_ids.issubset(set(specs.keys()))


def test_simular_variant_v11_m2_spec(client):
    specs = _get_specs(client)
    spec = specs["V11-M2"]
    src = next(c for c in CONFIGS_20 if c["id"] == "V11-M2")

    assert spec["id"] == "V11-M2"
    assert spec["tf"] == src["tf"]
    assert spec["engine"] == "simular_variant"
    # V11-M2 is DEFINED in both CONFIGS_20 (magic 720200) and CONFIGS_GOLIVE /
    # CONFIGS_GOLIVE_DEDUP (magic 724060, re-magicked verbatim per
    # live_configs_20's own GL-T1 comment). Per the brief, the go-live/dedup
    # definition wins on id collision -> expect the go-live magic here.
    assert spec["magic"] == MAGIC_BY_ID_GOLIVE["V11-M2"]

    types = [ind["type"] for ind in spec["indicators"]]
    assert "EMA" in types
    assert "SAR" in types

    ema_periods = {ind["params"]["period"] for ind in spec["indicators"] if ind["type"] == "EMA"}
    assert ema_periods == {8, 20}

    sar = next(ind for ind in spec["indicators"] if ind["type"] == "SAR")
    # V11-M2 is static SAR (sar_adaptive absent) with step=0.3, max=0.3.
    assert sar["params"]["step"] == pytest.approx(0.3)
    assert sar["params"]["max"] == pytest.approx(0.3)
    assert "adaptive" not in sar["params"] or sar["params"].get("adaptive") is False

    # no direction_filter on V11-M2 -> no SuperTrend direction mask indicator.
    assert "SUPERTREND" not in types

    for ind in spec["indicators"]:
        assert ind["pane"] == "price"

    rules = spec["rules"]
    assert "entry" in rules and rules["entry"]
    assert "exit" in rules and rules["exit"]


def test_supertrend_config_spec(client):
    specs = _get_specs(client)
    spec = specs["SuperTrend-p14x3-M15"]

    assert spec["tf"] == "M15"
    assert spec["engine"] == "supertrend_always_in"
    assert spec["magic"] == MAGIC_BY_ID_GOLIVE["SuperTrend-p14x3-M15"]

    assert len(spec["indicators"]) == 1
    ind = spec["indicators"][0]
    assert ind["type"] == "SUPERTREND"
    assert ind["params"]["atr_period"] == 14
    assert ind["params"]["mult"] == pytest.approx(3.0)
    assert ind["pane"] == "price"

    rules = spec["rules"]
    assert "entry" in rules and rules["entry"]
    assert "exit" in rules and rules["exit"]


def test_tk_momentum_config_spec(client):
    specs = _get_specs(client)
    spec = specs["TK-Momentum-5-8-short"]

    assert spec["tf"] == "M6"
    assert spec["engine"] == "tk_momentum"
    assert spec["magic"] == CONFIG_TK_MOMENTUM["magic"]

    types_params = [(ind["type"], ind["params"], ind["pane"]) for ind in spec["indicators"]]
    sma_periods = sorted(p["period"] for t, p, _ in types_params if t == "SMA")
    assert sma_periods == [5, 8]

    mom = next(ind for ind in spec["indicators"] if ind["type"] == "MOM")
    assert mom["params"]["period"] == 2
    assert mom["pane"] == "sub"

    # SMA entries live on the price pane.
    for t, _p, pane in types_params:
        if t == "SMA":
            assert pane == "price"

    rules = spec["rules"]
    assert "entry" in rules and rules["entry"]
    assert "exit" in rules and rules["exit"]


def test_magic_echoed_matches_config(client):
    # For ids NOT present in a go-live roster, the CONFIGS_20 magic must be
    # echoed verbatim (V11-M2 is the one deliberate exception -- see
    # test_simular_variant_v11_m2_spec).
    specs = _get_specs(client)
    golive_ids = {c["id"] for c in CONFIGS_GOLIVE} | {c["id"] for c in CONFIGS_GOLIVE_DEDUP}
    for cid, magic in MAGIC_BY_ID.items():
        if cid in specs and cid not in golive_ids:
            assert specs[cid]["magic"] == magic

    # go-live ids echo the go-live magic.
    for cid, magic in MAGIC_BY_ID_GOLIVE.items():
        if cid in specs:
            assert specs[cid]["magic"] == magic
