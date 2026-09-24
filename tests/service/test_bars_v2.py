"""tests/service/test_bars_v2.py — TDD for Task A3a: `/api/bars` v2

(windowed + LOD, CT-2 shape). Builds a real tiered lake (via
`sentinel_engine.lake.tiers.build_tiers`, Wave A / Task A1) in `tmp_path` and
exercises both the pure reader (`sentinel_engine.service.bars_source`) and
the FastAPI route (`GET /api/bars`) against it.

CT-2 (frozen contract):
    {"symbol","tf_requested","served_tf","clipped",
     "bars":[{"t","o","h","l","c","v"}, ...],
     "overlays":{"ema8":[{"t","v"}, ...], ...}}

A3a left `overlays` always `{}`. A3b (this file's overlay tests, below)
populates it server-side per the `overlays` query param (csv of
ema8/ema20/sar/supertrend), with a 200-bar warmup window so indicator math
matches what a client would get computing over the full history.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from sentinel_engine.lake import store
from sentinel_engine.lake.tiers import TF_SECONDS, build_tiers
from sentinel_engine.service.app import create_app
from sentinel_engine.service.bars_source import (
    BarsSourceError,
    choose_served_tf,
    read_window,
)
from sentinel_engine.strategies.emasar import ema_series
from tests.golden.fake_feed import FakeFeed

BASE = pd.Timestamp("2026-01-01T00:00:00Z")
BASE_EPOCH = int(BASE.timestamp())

# Far enough past any bar built below that every tier's buckets, including
# the coarsest (D), are safely "closed" (build_tiers' forming-bar guard).
FAR_FUTURE_NOW = BASE_EPOCH + 400 * 86400


def _m1_frame(n: int, start: pd.Timestamp = BASE, freq: str = "1min") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    df = pd.DataFrame({
        "open": [100.0 + i for i in range(n)],
        "high": [100.5 + i for i in range(n)],
        "low": [99.5 + i for i in range(n)],
        "close": [100.2 + i for i in range(n)],
        "volume": [10 + i for i in range(n)],
    }, index=idx)
    df.index.name = "time"
    return df


def _seed_lake(lake_root, symbol: str, n: int, **frame_kwargs) -> None:
    store.write_bars(lake_root, symbol, 1, _m1_frame(n, **frame_kwargs))
    build_tiers(symbol, lake_root, now_epoch=FAR_FUTURE_NOW)


# ---------------------------------------------------------------------
# read_window (pure pyarrow reader)
# ---------------------------------------------------------------------

def test_read_window_ascending_unique_no_empty_buckets(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root, "XAUUSD", 20)

    bars = read_window("XAUUSD", "M1", BASE_EPOCH, BASE_EPOCH + 19 * 60, lake_root)

    assert len(bars) == 20
    ts = [b["t"] for b in bars]
    assert ts == sorted(ts)
    assert len(set(ts)) == len(ts)
    # all bars strictly within the closed [from,to] window requested
    assert all(BASE_EPOCH <= t <= BASE_EPOCH + 19 * 60 for t in ts)


def test_read_window_only_closed_bars_no_forming_bar_leak(tmp_path):
    lake_root = tmp_path / "lake"
    # Seed 5 M1 bars, but build tiers with now_epoch such that the M5 bucket
    # they'd form is still "forming" (not yet closed) -> tier has 0 rows.
    store.write_bars(lake_root, "XAUUSD", 1, _m1_frame(5))
    now_epoch = BASE_EPOCH + TF_SECONDS["M5"] - 1
    build_tiers("XAUUSD", lake_root, now_epoch=now_epoch)

    bars = read_window("XAUUSD", "M5", BASE_EPOCH, BASE_EPOCH + 3600, lake_root)
    assert bars == []  # the only bucket was still forming -> tier builder omitted it


def test_read_window_unknown_tf_raises(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root, "XAUUSD", 5)
    with pytest.raises(BarsSourceError):
        read_window("XAUUSD", "M99", BASE_EPOCH, BASE_EPOCH + 60, lake_root)


def test_read_window_unknown_symbol_returns_empty(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root, "XAUUSD", 5)
    bars = read_window("NOPE", "M1", BASE_EPOCH, BASE_EPOCH + 60, lake_root)
    assert bars == []


# ---------------------------------------------------------------------
# choose_served_tf (LOD ladder)
# ---------------------------------------------------------------------

def test_choose_served_tf_no_escalation_when_under_max_points():
    served = choose_served_tf("M1", BASE_EPOCH, BASE_EPOCH + 100 * 60, max_points=5000)
    assert served == "M1"


def test_choose_served_tf_escalates_up_the_ladder():
    # 10 days of M1 bars = 14400 estimated M1 points, over max_points=5000
    # -> ladder must step up (M1 -> M2 -> M5 -> ...) until it fits.
    span = 10 * 86400
    served = choose_served_tf("M1", BASE_EPOCH, BASE_EPOCH + span, max_points=5000)
    assert served != "M1"
    seconds = TF_SECONDS[served]
    assert span / seconds <= 5000


def test_choose_served_tf_already_coarsest_stays(tmp_path):
    # Even a huge span at the coarsest tier ("D") cannot escalate further.
    span = 100_000 * 86400
    served = choose_served_tf("D", BASE_EPOCH, BASE_EPOCH + span, max_points=100)
    assert served == "D"


# ---------------------------------------------------------------------
# GET /api/bars — CT-2 shape via the FastAPI route
# ---------------------------------------------------------------------

@pytest.fixture
def lake_root(tmp_path):
    root = tmp_path / "lake"
    _seed_lake(root, "XAUUSD", 120)
    return root


@pytest.fixture
def app_factory(lake_root):
    def _make():
        shared_feed = FakeFeed()
        return create_app(
            feed_factory=lambda name: shared_feed,
            instruments=("usdclp",),
            autostart_loop=False,
            lake_root=lake_root,
        )
    return _make


@pytest.fixture
def client(app_factory):
    app = app_factory()
    with TestClient(app) as c:
        yield c


def test_ct2_shape_and_overlays_empty(client):
    resp = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1",
        "from": BASE_EPOCH, "to": BASE_EPOCH + 119 * 60,
        "max_points": 5000,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"symbol", "tf_requested", "served_tf", "clipped", "bars", "overlays"}
    assert body["symbol"] == "XAUUSD"
    assert body["tf_requested"] == "M1"
    assert body["served_tf"] == "M1"
    assert body["clipped"] is False
    assert body["overlays"] == {}
    assert len(body["bars"]) == 120
    bar0 = body["bars"][0]
    assert set(bar0.keys()) == {"t", "o", "h", "l", "c", "v"}
    assert bar0["t"] == BASE_EPOCH
    assert bar0["o"] == pytest.approx(100.0)


def test_ct2_bars_ascending_unique_via_api(client):
    resp = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1",
        "from": BASE_EPOCH, "to": BASE_EPOCH + 119 * 60,
    })
    body = resp.json()
    ts = [b["t"] for b in body["bars"]]
    assert ts == sorted(ts)
    assert len(set(ts)) == len(ts)


def test_ct2_lod_escalates_served_tf_and_respects_max_points(tmp_path):
    lake_root = tmp_path / "lake"
    # 10 days of M1 bars -> at M1 that's 14400 points, well over max_points.
    _seed_lake(lake_root, "XAUUSD", 10 * 24 * 60)

    shared_feed = FakeFeed()
    app = create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        lake_root=lake_root,
    )
    with TestClient(app) as client:
        resp = client.get("/api/bars", params={
            "symbol": "XAUUSD", "tf": "M1",
            "from": BASE_EPOCH, "to": BASE_EPOCH + 10 * 86400,
            "max_points": 500,
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["tf_requested"] == "M1"
    assert body["served_tf"] != "M1"
    assert len(body["bars"]) <= 500


def test_ct2_accepts_epoch_and_iso_from_to(client):
    resp_epoch = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1",
        "from": BASE_EPOCH, "to": BASE_EPOCH + 59 * 60,
    })
    resp_iso = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1",
        "from": BASE.isoformat(), "to": (BASE + pd.Timedelta(minutes=59)).isoformat(),
    })
    assert resp_epoch.status_code == 200
    assert resp_iso.status_code == 200
    body_epoch = resp_epoch.json()
    body_iso = resp_iso.json()
    assert body_epoch["bars"] == body_iso["bars"]
    assert len(body_epoch["bars"]) == 60


def test_ct2_rounds_to_instrument_decimals(client):
    resp = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1",
        "from": BASE_EPOCH, "to": BASE_EPOCH + 5 * 60,
    })
    body = resp.json()
    for bar in body["bars"]:
        for k in ("o", "h", "l", "c"):
            val = bar[k]
            assert round(val, 2) == val


def test_ct2_payload_size_under_1_5mb_for_5000_bars(tmp_path):
    lake_root = tmp_path / "lake"
    n = 5000
    _seed_lake(lake_root, "XAUUSD", n)

    shared_feed = FakeFeed()
    app = create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        lake_root=lake_root,
    )
    with TestClient(app) as client:
        resp = client.get("/api/bars", params={
            "symbol": "XAUUSD", "tf": "M1",
            "from": BASE_EPOCH, "to": BASE_EPOCH + (n - 1) * 60,
            "max_points": 10000,
        })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["bars"]) == n
    assert len(resp.content) < 1.5 * 1024 * 1024


def test_ct2_bad_tf_returns_error_envelope(client):
    resp = client.get("/api/bars", params={"symbol": "XAUUSD", "tf": "M99"})
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"] and "message" in body["error"]


def test_ct2_unknown_symbol_returns_empty_bars(client):
    resp = client.get("/api/bars", params={
        "symbol": "NOPE", "tf": "M1",
        "from": BASE_EPOCH, "to": BASE_EPOCH + 60,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["bars"] == []
    assert body["clipped"] is False


# ---------------------------------------------------------------------
# overlays (A3b) — server-side computed, warmed-up, clipped to the window
# ---------------------------------------------------------------------

def test_overlays_empty_when_not_requested(client):
    resp = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1",
        "from": BASE_EPOCH, "to": BASE_EPOCH + 119 * 60,
    })
    body = resp.json()
    assert body["overlays"] == {}


def test_overlays_t_is_subset_of_bars_t(client):
    resp = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1",
        "from": BASE_EPOCH + 30 * 60, "to": BASE_EPOCH + 119 * 60,
        "overlays": "ema8,ema20,sar,supertrend",
    })
    assert resp.status_code == 200
    body = resp.json()
    bars_t = {b["t"] for b in body["bars"]}
    assert set(body["overlays"].keys()) == {"ema8", "ema20", "sar", "supertrend"}
    for name, points in body["overlays"].items():
        assert points, f"{name} should have points given warmup + 120 seeded bars"
        pts_t = {p["t"] for p in points}
        assert pts_t <= bars_t
        for p in points:
            assert set(p.keys()) == {"t", "v"}


def test_overlays_warmup_correctness_ema8(tmp_path):
    # Seed 400 M1 bars so a window starting well after bar 200 has a full
    # 200-bar warmup available before `from`.
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root, "XAUUSD", 400)

    shared_feed = FakeFeed()
    app = create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        lake_root=lake_root,
    )
    window_from = BASE_EPOCH + 250 * 60
    window_to = BASE_EPOCH + 399 * 60
    with TestClient(app) as client:
        resp = client.get("/api/bars", params={
            "symbol": "XAUUSD", "tf": "M1",
            "from": window_from, "to": window_to,
            "overlays": "ema8",
        })
    assert resp.status_code == 200
    body = resp.json()
    ema8_points = body["overlays"]["ema8"]
    assert ema8_points

    # Independently reconstruct EMA8 the way the warmup contract promises:
    # read the FULL history from t=0 up to the window end, compute EMA8 over
    # the whole thing, and check the first in-window value the server
    # returned equals the full-history EMA at that same t. This proves the
    # server's 200-bar warmup was deep enough for EMA8 (period 8) to have
    # fully converged by the start of the window, not just "some warmup".
    full_bars = read_window("XAUUSD", "M1", BASE_EPOCH, window_to, lake_root)
    full_closes = [b["c"] for b in full_bars]
    full_ema8 = ema_series(full_closes, 8)
    full_by_t = {b["t"]: v for b, v in zip(full_bars, full_ema8) if v is not None}

    first_point = ema8_points[0]
    assert first_point["t"] in full_by_t
    assert first_point["v"] == pytest.approx(round(full_by_t[first_point["t"]], 2))


def test_overlays_unsupported_name_ignored(client):
    resp = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1",
        "from": BASE_EPOCH, "to": BASE_EPOCH + 119 * 60,
        "overlays": "ema8,bogus",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["overlays"].keys()) == {"ema8"}


# ---------------------------------------------------------------------
# Default window (no from/to): legacy ergonomics — serve the tail
# (charts.js fetchLastBars calls with symbol/tf/max_points only)
# ---------------------------------------------------------------------

def test_rangeless_request_serves_most_recent_window(client):
    resp = client.get("/api/bars", params={"symbol": "XAUUSD", "tf": "M1", "max_points": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["bars"], "rangeless call must serve the coverage tail, not an empty window"
    assert len(body["bars"]) <= 50
    # the returned window must END at the lake's last M1 bar
    assert body["bars"][-1]["t"] == BASE_EPOCH + 119 * 60


def test_rangeless_request_unknown_symbol_still_empty(client):
    resp = client.get("/api/bars", params={"symbol": "NOPE", "tf": "M1"})
    assert resp.status_code == 200
    assert resp.json()["bars"] == []
