"""C2 -- NEWS tab UI (web/sections/news.js). Static-serve + source assertions
only (pattern from test_web_positions.py / test_web_runs.py); NO browser
automation."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_sections_news_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/sections/news.js")
        assert resp.status_code == 200


def test_no_cdn_in_news_js():
    text = (WEB_DIR / "sections" / "news.js").read_text(encoding="utf-8")
    assert "cdn.jsdelivr" not in text.lower()
    assert "cdnjs." not in text.lower()
    assert "unpkg.com" not in text
    assert "jsdelivr" not in text.lower()


def test_news_js_registers_sentinel_namespace():
    text = (WEB_DIR / "sections" / "news.js").read_text(encoding="utf-8")
    assert "window.SENTINEL" in text
    assert "sections.news" in text
    assert "render" in text
    assert "teardown" in text


def test_news_js_reuses_vlist():
    text = (WEB_DIR / "sections" / "news.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.vlist" in text or "SENTINEL.vlist" in text
    assert "createVList" in text


def test_news_js_fetches_news_endpoint_with_filter_params():
    text = (WEB_DIR / "sections" / "news.js").read_text(encoding="utf-8")
    assert "/api/news" in text
    assert "symbol" in text
    assert "impact" in text
    assert "kind" in text
    assert "limit" in text


def test_news_js_title_link_is_target_blank_noopener():
    text = (WEB_DIR / "sections" / "news.js").read_text(encoding="utf-8")
    assert 'target="_blank"' in text
    assert 'rel="noopener"' in text


def test_news_js_uses_eventsource_for_stream_with_teardown():
    text = (WEB_DIR / "sections" / "news.js").read_text(encoding="utf-8")
    assert "/api/news/stream" in text
    assert "EventSource" in text
    assert "news_item" in text
    # REV-5 teardown pattern: EventSource is registered on section state and
    # closed in teardown().
    assert ".close()" in text


def test_news_js_has_freshness_label_with_60s_timer_and_teardown():
    text = (WEB_DIR / "sections" / "news.js").read_text(encoding="utf-8")
    assert "hace" in text
    assert "min" in text
    assert "setInterval" in text
    assert "clearInterval" in text


def test_news_js_builds_filter_query_params():
    text = (WEB_DIR / "sections" / "news.js").read_text(encoding="utf-8")
    assert "URLSearchParams" in text or "qs(" in text


def test_news_js_teardown_closes_eventsource_and_clears_timer():
    text = (WEB_DIR / "sections" / "news.js").read_text(encoding="utf-8")
    teardown_src = text.split("function teardown")[1]
    assert "close()" in teardown_src
    assert "clearInterval" in teardown_src
