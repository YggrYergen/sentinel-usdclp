"""tests/service/test_news_core.py — TDD for C1a news core (CT-5).

Covers: RSS parsing, ForexFactory-calendar-json parsing, dedupe by id
and by near-duplicate title (48h window), and `GET /api/news` shape
(symbol/impact/kind/limit filters), same registry-injection pattern as
tests/service/test_positions_api.py.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.app import create_app
from sentinel_engine.service.news import (
    dedupe_items,
    dedupe_key,
    is_dup_title,
    parse_ff_calendar,
    parse_rss,
    query_items,
    upsert_items,
)
from tests.golden.fake_feed import FakeFeed

_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Test Feed</title>
<item>
  <title>Gold prices surge on Fed uncertainty</title>
  <link>https://example.com/news/gold-surge?utm_source=rss</link>
  <pubDate>Mon, 06 Jul 2026 12:00:00 GMT</pubDate>
</item>
<item>
  <title>Gold prices surge on Fed uncertainty!</title>
  <link>https://example.com/news/gold-surge-2</link>
  <pubDate>Mon, 06 Jul 2026 12:05:00 GMT</pubDate>
</item>
</channel>
</rss>
"""

_FF_CALENDAR_JSON = """
[
  {"title": "Non-Farm Payrolls", "country": "USD", "date": "2026-07-10T12:30:00Z", "impact": "High"},
  {"title": "CPI m/m", "country": "USD", "date": "2026-07-11T12:30:00Z", "impact": "Medium"}
]
"""


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


def test_parse_rss_shapes_items():
    items = parse_rss(_RSS_XML, source="test_feed")
    assert len(items) == 2
    first = items[0]
    assert set(first.keys()) == {"id", "ts", "source", "title", "url", "symbols", "kind", "impact"}
    assert first["source"] == "test_feed"
    assert first["title"] == "Gold prices surge on Fed uncertainty"
    assert first["url"] == "https://example.com/news/gold-surge?utm_source=rss"
    assert first["kind"] == "news"
    assert first["impact"] is None
    assert "XAUUSD" in first["symbols"]
    assert first["ts"] is not None


def test_parse_ff_calendar_shapes_items():
    items = parse_ff_calendar(_FF_CALENDAR_JSON)
    assert len(items) == 2
    first = items[0]
    assert set(first.keys()) == {"id", "ts", "source", "title", "url", "symbols", "kind", "impact"}
    assert first["title"] == "Non-Farm Payrolls"
    assert first["kind"] == "calendar"
    assert first["impact"] == "high"
    assert first["ts"] is not None


def test_dedupe_key_same_for_canonicalized_urls():
    a = {"url": "https://example.com/news/x?utm_source=rss"}
    b = {"url": "https://example.com/news/x"}
    assert dedupe_key(a) == dedupe_key(b)


def test_dedupe_key_differs_for_different_urls():
    a = {"url": "https://example.com/news/x"}
    b = {"url": "https://example.com/news/y"}
    assert dedupe_key(a) != dedupe_key(b)


def test_is_dup_title_within_window():
    a = {"title": "Gold prices surge on Fed uncertainty", "ts": 1000}
    b = {"title": "Gold prices surge on Fed uncertainty!", "ts": 1300}
    assert is_dup_title(a, b) is True


def test_is_dup_title_outside_window():
    a = {"title": "Gold prices surge on Fed uncertainty", "ts": 1000}
    b = {"title": "Gold prices surge on Fed uncertainty!", "ts": 1000 + 48 * 3600 + 1}
    assert is_dup_title(a, b) is False


def test_is_dup_title_different_titles_within_window():
    a = {"title": "Gold prices surge on Fed uncertainty", "ts": 1000}
    b = {"title": "Oil prices plunge on OPEC news", "ts": 1300}
    assert is_dup_title(a, b) is False


def test_dedupe_items_collapses_title_variants_from_rss_fixture():
    items = parse_rss(_RSS_XML, source="test_feed")
    deduped = dedupe_items(items)
    assert len(deduped) == 1


def test_dedupe_items_keeps_distinct_ids():
    items = [
        {"id": "a", "ts": 1000, "title": "Gold up", "url": "https://x/1", "source": "s", "symbols": [], "kind": "news", "impact": None},
        {"id": "b", "ts": 200000, "title": "Oil down", "url": "https://x/2", "source": "s", "symbols": [], "kind": "news", "impact": None},
    ]
    deduped = dedupe_items(items)
    assert len(deduped) == 2


def test_news_endpoint_empty(client):
    resp = client.get("/api/news")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


def test_news_endpoint_shape_and_filters(client, registry):
    items = [
        {
            "id": "id1", "ts": 1000, "source": "rss1", "title": "Gold surges",
            "url": "https://x/1", "symbols": ["XAUUSD"], "kind": "news", "impact": "high",
        },
        {
            "id": "id2", "ts": 2000, "source": "ff_calendar", "title": "CPI release",
            "url": None, "symbols": ["DXY"], "kind": "calendar", "impact": "medium",
        },
    ]
    upsert_items(registry, items)

    resp = client.get("/api/news")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    item = body["items"][0]
    assert set(item.keys()) == {"id", "ts", "source", "title", "url", "symbols", "kind", "impact"}
    # most recent first
    assert body["items"][0]["id"] == "id2"

    resp = client.get("/api/news", params={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "id1"

    resp = client.get("/api/news", params={"impact": "medium"})
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "id2"

    resp = client.get("/api/news", params={"kind": "calendar"})
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "id2"

    resp = client.get("/api/news", params={"limit": 1})
    body = resp.json()
    assert len(body["items"]) == 1


def test_query_items_direct(registry):
    upsert_items(registry, [
        {"id": "id1", "ts": 1000, "source": "s", "title": "Gold surges",
         "url": "https://x/1", "symbols": ["XAUUSD"], "kind": "news", "impact": "high"},
    ])
    results = query_items(registry, symbol="XAUUSD")
    assert len(results) == 1
    assert results[0]["id"] == "id1"
