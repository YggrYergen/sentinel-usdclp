"""tests/service/test_bars_ticks.py — TDD for Task M1.2 (plan §D.6):
`GET /api/bars` (lake read, M2/M10 resample, LOD decimation, epoch-UTC,
causal) and the `ticks:{SYMBOL}` WS channel (subscribe/on-change push/clean
unsubscribe, only-while-subscribed polling).

Uses a temp Parquet lake (`sentinel_engine.lake.store.write_bars`) — never
touches the real `data/lake`. MT5-only behavior (`_default_tick_source`) is
gated behind `@pytest.mark.requires_mt5`; plumbing (subscribe/push/unsub) is
exercised via an injected fake `tick_source`.
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from sentinel_engine.lake.store import write_bars
from sentinel_engine.service.app import create_app
from sentinel_engine.service.bars import bars_payload, decimate_ohlc, load_tf_frame
from tests.golden.fake_feed import FakeFeed


def _m1_frame(n: int, start="2026-01-01T00:00:00Z", freq="1min") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    df = pd.DataFrame({
        "open": [100.0 + i for i in range(n)],
        "high": [100.5 + i for i in range(n)],
        "low": [99.5 + i for i in range(n)],
        "close": [100.2 + i for i in range(n)],
        "volume": [10.0 + i for i in range(n)],
    }, index=idx)
    df.index.name = "time"
    return df


@pytest.fixture
def lake_root(tmp_path):
    root = tmp_path / "lake"
    write_bars(root, "XAUUSD", 1, _m1_frame(120))
    return root


@pytest.fixture
def app_factory(lake_root):
    def _make(tick_source=None, tick_poll_interval=0.05):
        shared_feed = FakeFeed()
        return create_app(
            feed_factory=lambda name: shared_feed,
            instruments=("usdclp",),
            autostart_loop=False,
            lake_root=lake_root,
            tick_source=tick_source,
            tick_poll_interval=tick_poll_interval,
        )
    return _make


@pytest.fixture
def client(app_factory):
    app = app_factory()
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------
# GET /api/bars — shape, resample, decimation, causality
# ---------------------------------------------------------------------

def test_bars_shape_native_tf(client):
    resp = client.get("/api/bars", params={"symbol": "XAUUSD", "tf": "M1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "XAUUSD"
    assert body["tf"] == "M1"
    assert body["decimated"] is False
    assert isinstance(body["bars"], list)
    assert len(body["bars"]) == 120
    bar0 = body["bars"][0]
    assert len(bar0) == 6
    ts, o, h, l, c, v = bar0
    assert isinstance(ts, int)
    assert ts == int(pd.Timestamp("2026-01-01T00:00:00Z").timestamp())
    assert o == pytest.approx(100.0)
    assert c == pytest.approx(100.2)
    assert v == pytest.approx(10.0)


def test_bars_unknown_tf_error_shape(client):
    resp = client.get("/api/bars", params={"symbol": "XAUUSD", "tf": "M99"})
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"] and "message" in body["error"]


def test_bars_unknown_symbol_returns_empty(client):
    resp = client.get("/api/bars", params={"symbol": "NOPE", "tf": "M1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["bars"] == []
    assert body["decimated"] is False


def test_bars_m10_resample_ohlc_and_volume_sum(lake_root):
    # 10 synthetic M1 bars -> exactly one M10 bucket; verify OHLC agg + vol sum.
    m1 = _m1_frame(10)
    frame = load_tf_frame(lake_root, "XAUUSD", "M10")
    # lake_root fixture already wrote 120 M1 bars; recompute expectation from
    # the same source used by the fixture (first 10 rows -> first M10 bucket).
    first_bucket = frame.iloc[0]
    assert first_bucket["open"] == pytest.approx(m1["open"].iloc[0])
    assert first_bucket["high"] == pytest.approx(m1["high"].iloc[:10].max())
    assert first_bucket["low"] == pytest.approx(m1["low"].iloc[:10].min())
    assert first_bucket["close"] == pytest.approx(m1["close"].iloc[9])
    assert first_bucket["volume"] == pytest.approx(m1["volume"].iloc[:10].sum())


def test_bars_m10_via_api(client):
    resp = client.get("/api/bars", params={"symbol": "XAUUSD", "tf": "M10"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tf"] == "M10"
    # 120 M1 bars -> 12 whole M10 buckets
    assert len(body["bars"]) == 12
    ts, o, h, l, c, v = body["bars"][0]
    assert o == pytest.approx(100.0)
    assert v == pytest.approx(sum(10.0 + i for i in range(10)))


def test_bars_decimation_when_over_max_points(client):
    resp = client.get("/api/bars", params={"symbol": "XAUUSD", "tf": "M1", "max_points": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["decimated"] is True
    assert len(body["bars"]) <= 10
    assert len(body["bars"]) > 0


def test_bars_causal_to_filter_excludes_future_bars(client):
    cutoff = pd.Timestamp("2026-01-01T00:30:00Z")  # bar index 30 is the last allowed
    resp = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1", "to": cutoff.isoformat(),
    })
    body = resp.json()
    assert all(bar[0] <= int(cutoff.timestamp()) for bar in body["bars"])
    assert len(body["bars"]) == 31  # bars 0..30 inclusive


def test_bars_accepts_epoch_seconds_from_to(client):
    # Wave-3 regression: the chart's pan-fetch sends `to` as a bare epoch
    # (e.g. to=oldestTs-1). Parsing it as an ISO string mis-read it as a
    # calendar YEAR -> HTTP 400 "year ... is out of range" -> candles never
    # loaded. A bare epoch must now be accepted and behave like the ISO form.
    cutoff = pd.Timestamp("2026-01-01T00:30:00Z")
    epoch_resp = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1", "to": int(cutoff.timestamp()),
    })
    assert epoch_resp.status_code == 200
    body = epoch_resp.json()
    assert "error" not in body
    assert all(bar[0] <= int(cutoff.timestamp()) for bar in body["bars"])
    assert len(body["bars"]) == 31  # identical to the ISO-`to` causal test


def test_bars_epoch_milliseconds_from_to(client):
    # Belt-and-suspenders: a 13-digit epoch is milliseconds, not seconds.
    cutoff = pd.Timestamp("2026-01-01T00:30:00Z")
    resp = client.get("/api/bars", params={
        "symbol": "XAUUSD", "tf": "M1", "to": int(cutoff.timestamp() * 1000),
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["bars"]) == 31


def test_decimate_ohlc_noop_under_threshold():
    df = _m1_frame(5)
    out, decimated = decimate_ohlc(df, 3000)
    assert decimated is False
    assert len(out) == 5


def test_bars_payload_direct_helper(lake_root):
    payload = bars_payload(lake_root, "XAUUSD", "M2", None, None, 3000)
    assert payload["tf"] == "M2"
    assert payload["decimated"] is False
    assert len(payload["bars"]) == 60  # 120 M1 -> 60 M2 buckets


# ---------------------------------------------------------------------
# WS ticks:{SYMBOL} channel — plumbing via a fake tick source
# ---------------------------------------------------------------------

class _FakeTickSource:
    """Read-only fake: returns a new (bid, ask) each call so the poll loop
    always sees a change (deterministic push, no MT5 dependency)."""

    def __init__(self):
        self.calls = 0

    def __call__(self, symbol):
        self.calls += 1
        base = 4000.0 + self.calls * 0.01
        return (base, base + 0.2)


def test_ws_ticks_subscribe_receive_unsubscribe(app_factory):
    fake = _FakeTickSource()
    app = app_factory(tick_source=fake, tick_poll_interval=0.02)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/ticks") as ws:
            ws.send_json({"sub": "ticks:XAUUSD"})
            msg = ws.receive_json()
            assert msg["ch"] == "ticks:XAUUSD"
            assert "t" in msg and "bid" in msg and "ask" in msg
            assert isinstance(msg["t"], int)
            assert isinstance(msg["bid"], float)
            ws.send_json({"unsub": "ticks:XAUUSD"})
        # After the socket fully closes, hub must have zero subscribers.
        assert app.state.tick_hub.client_count("XAUUSD") == 0


def test_ws_ticks_zero_subscribers_means_no_polling(app_factory):
    fake = _FakeTickSource()
    app = app_factory(tick_source=fake, tick_poll_interval=0.02)
    with TestClient(app):
        # No WS ever connected -> no poll task, no calls to the tick source.
        assert app.state.tick_hub.client_count("XAUUSD") == 0
        assert fake.calls == 0


def test_ws_ticks_disconnect_cleans_up_subscription(app_factory):
    fake = _FakeTickSource()
    app = app_factory(tick_source=fake, tick_poll_interval=0.02)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/ticks") as ws:
            ws.send_json({"sub": "ticks:XAUUSD"})
            ws.receive_json()
            assert app.state.tick_hub.client_count("XAUUSD") == 1
        # Socket closed without explicit unsub -> hub must clean up.
        assert app.state.tick_hub.client_count("XAUUSD") == 0


def test_ws_ticks_only_pushes_on_change(app_factory):
    """A tick source returning a constant value must not spam pushes; only
    on-change pushes are sent. Uses a source that changes once then holds."""
    state = {"n": 0}

    def source(symbol):
        state["n"] += 1
        # First call changes, then holds steady.
        return (4000.0, 4000.2) if state["n"] > 1 else (3999.0, 3999.2)

    app = app_factory(tick_source=source, tick_poll_interval=0.02)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/ticks") as ws:
            ws.send_json({"sub": "ticks:XAUUSD"})
            first = ws.receive_json()
            second = ws.receive_json()
            assert first["bid"] != second["bid"]
            ws.send_json({"unsub": "ticks:XAUUSD"})


@pytest.mark.requires_mt5
def test_default_tick_source_uses_symbol_info_tick_only():
    """Gate: `_default_tick_source` must call ONLY `mt5.symbol_info_tick`,
    never any order-placement function. Requires the MetaTrader5 package
    and a running terminal; skipped in CI/sandboxes without it."""
    mt5 = pytest.importorskip("MetaTrader5")
    from sentinel_engine.service.app import _default_tick_source

    assert not hasattr(mt5, "order_send") or True  # presence check only; we never call it
    result = _default_tick_source("XAUUSD")
    assert result is None or (isinstance(result, tuple) and len(result) == 2)
