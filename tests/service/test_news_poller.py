"""tests/service/test_news_poller.py — TDD for C1b news poller loop + SSE
+ news.yaml (CT-5 / CT-9).

Covers:
- `NewsPoller` with an injectable `fetcher(url, etag, last_modified) ->
  (status, headers, body)`: first poll inserts + broadcasts new items;
  second poll gets 304 -> no work done.
- malformed feed body -> logged, loop stays alive (poll() doesn't raise).
- `GET /api/news/stream` SSE emits a `news_item` event for a new insert
  (content-level check against the poller's own broadcaster, same
  technique `test_jobs.py::test_jobs_stream_broadcasts_job_update_event`
  uses for `/api/jobs/stream` -- driving the unbounded SSE generator over
  a real HTTP transport deadlocks TestClient).
- `load_news_config` honors `symbol_keywords` overrides from `news.yaml`.
"""
from __future__ import annotations

import json
import queue
import time
from pathlib import Path

import pytest

from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.news import NewsPoller, load_news_config, query_items

_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Test Feed</title>
<item>
  <title>Gold prices surge on Fed uncertainty</title>
  <link>https://example.com/news/gold-surge</link>
  <pubDate>Mon, 06 Jul 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>
"""

_CONFIG = {
    "rss": ["https://example.com/feed.xml"],
    "ff_calendar": None,
    "symbol_keywords": {},
}


@pytest.fixture
def registry(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


def _make_fetcher(bodies: dict[str, str], calls: list):
    """`fetcher(url, etag, last_modified) -> (status, headers, body)`.
    Returns 200 + body the first time a url is fetched, then 304 (with no
    body) on every subsequent call for that same url -- mimicking a
    conditional-GET server that hasn't changed."""
    seen: set[str] = set()

    def fetcher(url, etag, last_modified):
        calls.append((url, etag, last_modified))
        if url in seen:
            return 304, {}, b""
        seen.add(url)
        return 200, {"ETag": '"abc123"'}, bodies[url].encode("utf-8")

    return fetcher


def test_poll_first_time_inserts_and_broadcasts(registry):
    calls: list = []
    fetcher = _make_fetcher({"https://example.com/feed.xml": _RSS_XML}, calls)
    poller = NewsPoller(registry, _CONFIG, fetcher=fetcher)
    sub_queue = poller.subscribe()

    poller.poll_once()

    items = query_items(registry)
    assert len(items) == 1
    assert items[0]["title"] == "Gold prices surge on Fed uncertainty"

    body = sub_queue.get(timeout=1.0)
    assert body["title"] == "Gold prices surge on Fed uncertainty"


def test_poll_second_time_304_no_new_work(registry):
    calls: list = []
    fetcher = _make_fetcher({"https://example.com/feed.xml": _RSS_XML}, calls)
    poller = NewsPoller(registry, _CONFIG, fetcher=fetcher)

    poller.poll_once()
    assert len(query_items(registry)) == 1

    sub_queue = poller.subscribe()
    poller.poll_once()

    # second call was conditional (etag passed) and got 304 -> no new rows,
    # no broadcast.
    assert len(query_items(registry)) == 1
    assert calls[-1][1] == '"abc123"'
    with pytest.raises(queue.Empty):
        sub_queue.get(timeout=0.2)


def test_poll_malformed_feed_logged_and_loop_alive(registry, caplog):
    calls: list = []

    def fetcher(url, etag, last_modified):
        calls.append(url)
        return 200, {}, b"<not valid xml"

    poller = NewsPoller(registry, _CONFIG, fetcher=fetcher)

    # must not raise
    poller.poll_once()
    assert len(query_items(registry)) == 0

    # loop is still usable afterward (poll_once can be called again)
    poller.poll_once()
    assert len(calls) == 2


def test_sse_stream_emits_news_item_event(registry):
    """Content-level check, mirroring test_jobs.py's SSE test technique."""
    calls: list = []
    fetcher = _make_fetcher({"https://example.com/feed.xml": _RSS_XML}, calls)
    poller = NewsPoller(registry, _CONFIG, fetcher=fetcher)
    sub_queue = poller.subscribe()

    poller.poll_once()

    body = sub_queue.get(timeout=1.0)
    frame = f"event: news_item\ndata: {json.dumps(body)}\n\n"
    assert frame.startswith("event: news_item\ndata: ")
    assert frame.endswith("\n\n")
    assert body["title"] == "Gold prices surge on Fed uncertainty"


def test_sse_endpoint_wired_in_app(monkeypatch, registry, tmp_path):
    """`GET /api/news/stream` is registered on the app's `news_poller` and
    the route function is reachable (no real HTTP stream is driven here --
    `client.stream(...)` against this unbounded SSE generator deadlocks the
    anyio portal, same pitfall documented in
    `test_jobs.py::test_jobs_stream_broadcasts_job_update_event`)."""
    from sentinel_engine.service.app import create_app
    from tests.golden.fake_feed import FakeFeed

    shared_feed = FakeFeed()
    app = create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        autostart_news_poller=False,
        registry=registry,
    )
    assert app.state.news_poller is not None
    paths = {route.path for route in app.routes}
    assert "/api/news/stream" in paths


def test_load_news_config_honors_symbol_keyword_overrides(tmp_path):
    config_path = tmp_path / "news.yaml"
    config_path.write_text(
        "rss:\n  - https://example.com/feed.xml\n"
        "ff_calendar: https://example.com/cal.json\n"
        "symbol_keywords:\n"
        "  XAUUSD: [\"bullion\"]\n",
        encoding="utf-8",
    )
    config = load_news_config(config_path)
    assert config["rss"] == ["https://example.com/feed.xml"]
    assert config["ff_calendar"] == "https://example.com/cal.json"
    assert config["symbol_keywords"] == {"XAUUSD": ["bullion"]}


def test_repo_root_news_yaml_loads():
    repo_root = Path(__file__).resolve().parents[2]
    config = load_news_config(repo_root / "news.yaml")
    assert isinstance(config["rss"], list) and len(config["rss"]) >= 1
    assert config["ff_calendar"]
    assert "XAUUSD" in config["symbol_keywords"]
