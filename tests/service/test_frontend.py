"""P3/UI-rework — static frontend is served (vendored assets, no CDN) and
app.js references the SAME fields the golden Snapshot schema exposes."""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
GOLDEN_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "golden" / "fixtures" / "gold.json"

REQUIRED_TOP_LEVEL_FIELDS = {
    "composite_score", "direction", "signal", "technical", "macro", "levels",
    "alerts", "divergences", "symbol", "seq", "config_hash",
}


def test_static_assets_served_no_cdn(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        for path in ("/index.html", "/app.js", "/lab.js", "/chat.js", "/style.css",
                     "/vendor/uplot/uPlot.iife.min.js", "/vendor/uplot/uPlot.min.css"):
            resp = client.get(path)
            assert resp.status_code == 200, path

    for html_path in (WEB_DIR / "index.html",):
        text = html_path.read_text(encoding="utf-8")
        assert "cdn." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text.lower()
        assert 'src="/vendor/uplot/uPlot.iife.min.js"' in text


def test_appjs_references_snapshot_fields_used_by_renderAssetPanel():
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    golden = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    assert REQUIRED_TOP_LEVEL_FIELDS.issubset(golden.keys())
    # renderAssetPanel reads snapshot.components / .levels / .alerts / .divergences
    # / .symbol / .config_hash — not a flat per-field DOM table anymore (v2
    # replica renders via innerHTML), so check the JS source references each
    # top-level field name at least once (snapshot.<field> or snap.<field>).
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        pattern = rf"(snapshot|snap)\.{re.escape(field)}\b"
        assert re.search(pattern, app_js), f"app.js never references snapshot field '{field}'"


def test_appjs_has_reconnecting_ws_client():
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "new WebSocket(" in app_js
    assert "onclose" in app_js


def test_appjs_exposes_render_asset_panel_global():
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.renderAssetPanel = renderAssetPanel" in app_js
    assert "window.SENTINEL.probeEndpoint = probeEndpoint" in app_js


def test_index_has_navbar_and_three_asset_panels():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    for instrument in ("usdclp", "nasdaq", "gold"):
        assert f'id="panel-{instrument}"' in html
    for section in ("chat", "lab", "regime", "news", "study"):
        assert f'id="section-{section}"' in html
        assert f'data-section="{section}"' in html
