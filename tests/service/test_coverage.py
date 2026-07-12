"""tests/service/test_coverage.py — TDD for Task A2: `GET /api/coverage`.

CT-1 (frozen contract):
    {"symbol": "XAUUSD", "tfs": {"M1": {"first": <epoch-s>, "last": <epoch-s>}, ...}}

Reads `<lake_root>/manifest.json` (same nested shape A1's
`sentinel_engine.lake.tiers.build_tiers` writes:
`{symbol: {tf_name: {symbol,tf,first,last,rows,content_sha}}}`). Only
tier-named TF keys (M1/M2/M5/M15/H1/D) are surfaced; legacy manifest entries
keyed by raw minute strings (e.g. "5") must be filtered out. Unknown symbol
-> 404. The manifest is cached in-process and invalidated by file mtime.
"""
from __future__ import annotations

import json
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from sentinel_engine.lake import store
from sentinel_engine.lake.tiers import build_tiers
from sentinel_engine.service.app import create_app
from tests.golden.fake_feed import FakeFeed

BASE = pd.Timestamp("2026-01-01T00:00:00Z")
BASE_EPOCH = int(BASE.timestamp())

# Far enough past any bar built below that every tier's buckets are closed.
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


def _make_app(lake_root):
    shared_feed = FakeFeed()
    return create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        lake_root=lake_root,
    )


@pytest.fixture
def lake_root(tmp_path):
    root = tmp_path / "lake"
    _seed_lake(root, "XAUUSD", 120)
    return root


@pytest.fixture
def client(lake_root):
    app = _make_app(lake_root)
    with TestClient(app) as c:
        yield c


def test_coverage_known_symbol_shape_ct1(client):
    resp = client.get("/api/coverage", params={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"symbol", "tfs"}
    assert body["symbol"] == "XAUUSD"

    # Only tier-named TFs, per tiers.TF_SECONDS (M1/M2/M5/M15/H1/D).
    assert set(body["tfs"].keys()) == {"M1", "M2", "M5", "M15", "H1", "D"}

    for tf_name, tf_cov in body["tfs"].items():
        assert set(tf_cov.keys()) == {"first", "last"}
        assert isinstance(tf_cov["first"], int)
        assert isinstance(tf_cov["last"], int)
        assert tf_cov["first"] <= tf_cov["last"]

    m1 = body["tfs"]["M1"]
    assert m1["first"] == BASE_EPOCH
    assert m1["last"] == BASE_EPOCH + 119 * 60


def test_coverage_unknown_symbol_returns_404(client):
    resp = client.get("/api/coverage", params={"symbol": "NOPE"})
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"] and "message" in body["error"]


def test_coverage_reload_reflects_manifest_change_via_mtime(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root, "XAUUSD", 120)

    app = _make_app(lake_root)
    with TestClient(app) as client:
        resp1 = client.get("/api/coverage", params={"symbol": "XAUUSD"})
        assert resp1.status_code == 200
        first_last_before = resp1.json()["tfs"]["M1"]["last"]

        # Grow the lake and rebuild tiers -> manifest.json mtime changes.
        manifest_path = lake_root / "manifest.json"
        mtime_before = manifest_path.stat().st_mtime

        _seed_lake(lake_root, "XAUUSD", 200)

        # Ensure the mtime actually advances even on coarse-grained
        # filesystem clocks (Windows FAT-ish resolution can be ~2s).
        if manifest_path.stat().st_mtime == mtime_before:
            new_mtime = mtime_before + 5
            import os
            os.utime(manifest_path, (new_mtime, new_mtime))

        resp2 = client.get("/api/coverage", params={"symbol": "XAUUSD"})
        assert resp2.status_code == 200
        first_last_after = resp2.json()["tfs"]["M1"]["last"]

        assert first_last_after != first_last_before
        assert first_last_after == BASE_EPOCH + 199 * 60


def test_coverage_ignores_legacy_minute_keyed_entries(tmp_path):
    lake_root = tmp_path / "lake"
    _seed_lake(lake_root, "XAUUSD", 10)

    manifest_path = lake_root / "manifest.json"
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Inject a legacy per-minute-keyed entry alongside the tf-name-keyed ones.
    manifest["XAUUSD"]["5"] = {
        "symbol": "XAUUSD", "tf": 5, "first": BASE_EPOCH, "last": BASE_EPOCH + 599,
        "rows": 10, "content_sha": "deadbeef",
    }
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, sort_keys=True, indent=2)
    # Force a fresh mtime so the app (which may have already cached the
    # manifest from build_tiers's write) is guaranteed to see this rewrite.
    new_mtime = manifest_path.stat().st_mtime + 5
    import os
    os.utime(manifest_path, (new_mtime, new_mtime))

    app = _make_app(lake_root)
    with TestClient(app) as client:
        resp = client.get("/api/coverage", params={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    body = resp.json()
    assert "5" not in body["tfs"]
    assert set(body["tfs"].keys()) == {"M1", "M2", "M5", "M15", "H1", "D"}
