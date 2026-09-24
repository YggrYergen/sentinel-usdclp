"""M2.2 — TRADE REVIEW section (web/sections/review.js). Static-serve +
source assertions only (pattern from test_frontend.py / test_web_charts.py);
NO browser automation."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_sections_review_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/sections/review.js")
        assert resp.status_code == 200


def test_review_js_references_trades_endpoint():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "/api/runs" in text
    assert "/trades" in text


def test_review_js_uses_shared_chart_module():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.chart.create" in text
    assert "chart.create" in text
    assert "selectTrade" in text
    assert "addTradeMarkers" in text


def test_review_js_uses_vtable():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.vtable" in text or "SENTINEL.vtable" in text
    assert "createVTable" in text


def test_review_js_has_jk_keyboard_navigation():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert '"j"' in text or "'j'" in text
    assert '"k"' in text or "'k'" in text
    assert "keydown" in text


def test_review_js_registers_sentinel_namespace():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "window.SENTINEL" in text
    assert "sections.review" in text
    assert "render" in text
    assert "teardown" in text


def test_review_js_honors_preselected_run_from_app_state():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "appState" in text
    assert "selectedRun" in text


def test_review_js_dims_all_trades_and_reads_strategies_badges():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "dim" in text
    assert "/api/strategies" in text
    assert "window.SENTINEL.badge" in text


def test_no_cdn_in_review_js():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "cdn.jsdelivr" not in text.lower()
    assert "cdnjs." not in text.lower()
    assert "unpkg.com" not in text
    assert "jsdelivr" not in text.lower()
