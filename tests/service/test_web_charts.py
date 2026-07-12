"""M1.3 — shared chart module (lib/chart.js) + CHARTS section. Static-serve
assertions only (pattern from test_frontend.py); NO browser automation."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_vendor_lightweight_charts_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/vendor/lightweight-charts/lightweight-charts.standalone.production.js")
        assert resp.status_code == 200


def test_vendor_license_present():
    license_path = WEB_DIR / "vendor" / "lightweight-charts" / "LICENSE"
    assert license_path.exists()
    text = license_path.read_text(encoding="utf-8")
    assert "Apache License" in text


def test_lib_chart_and_section_charts_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        for path in ("/lib/chart.js", "/sections/charts.js"):
            resp = client.get(path)
            assert resp.status_code == 200, path


def test_index_references_vendor_and_lib_chart():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert 'src="/vendor/lightweight-charts/lightweight-charts.standalone.production.js"' in html
    # tolerate a cache-busting ?v=... query on the src
    assert 'src="/lib/chart.js"' in html or 'src="/lib/chart.js?v=' in html


def test_chart_js_exposes_sentinel_chart_create():
    text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.chart" in text
    assert "create" in text
    assert "setWindow" in text
    assert "setTF" in text
    assert "addTradeMarkers" in text
    assert "selectTrade" in text
    assert "enableTicks" in text
    assert "addOverlay" in text
    assert "destroy" in text


def test_charts_js_references_api_bars_and_tf_list():
    text = (WEB_DIR / "sections" / "charts.js").read_text(encoding="utf-8")
    assert "/api/bars" in text
    for tf in ("M1", "M2", "M5", "M10", "M15"):
        assert tf in text


def test_charts_js_references_ws_ticks_channel():
    text = (WEB_DIR / "sections" / "charts.js").read_text(encoding="utf-8")
    chart_text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    assert "ws/ticks" in chart_text or "ticks:" in chart_text
    assert "enableTicks" in text or "chartInst" in text


def test_no_cdn_in_new_assets():
    for rel in (
        "index.html",
        "lib/chart.js",
        "sections/charts.js",
    ):
        text = (WEB_DIR / rel).read_text(encoding="utf-8")
        assert "cdn.jsdelivr" not in text.lower()
        assert "cdnjs." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text.lower()


def test_charts_section_registers_sentinel_namespace():
    text = (WEB_DIR / "sections" / "charts.js").read_text(encoding="utf-8")
    assert "window.SENTINEL" in text
    assert "sections.charts" in text
    assert "render" in text
    assert "teardown" in text
