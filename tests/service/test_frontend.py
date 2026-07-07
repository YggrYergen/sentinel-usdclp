"""P3 Task 3.4/3.5 — static frontend is served (vendored assets, no CDN) and
its JS references the SAME fields the golden Snapshot schema exposes (UI
parity vs golden snapshot fields)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
GOLDEN_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "golden" / "fixtures" / "gold.json"

# Top-level Snapshot.to_dict() fields the UI must surface somewhere in app.js
# (as a `snap.<field>` / `snapshot.<field>` reference), per Task 3.5's UI
# parity requirement ("renders the SAME fields the golden snapshot exposes").
REQUIRED_TOP_LEVEL_FIELDS = {
    "composite_score", "direction", "signal", "technical", "macro", "levels",
    "alerts", "divergences", "symbol", "seq", "config_hash",
}


def test_static_assets_served_no_cdn(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        for path in ("/index.html", "/app.js", "/style.css", "/vendor/uplot/uPlot.iife.min.js",
                     "/vendor/uplot/uPlot.min.css"):
            resp = client.get(path)
            assert resp.status_code == 200, path

    for html_path in (WEB_DIR / "index.html",):
        text = html_path.read_text(encoding="utf-8")
        assert "cdn." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text.lower()
        assert 'src="/vendor/uplot/uPlot.iife.min.js"' in text


def test_appjs_references_every_golden_snapshot_field():
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    golden = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))

    assert REQUIRED_TOP_LEVEL_FIELDS.issubset(golden.keys())

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        pattern = rf"\.{re.escape(field)}\b"
        assert re.search(pattern, app_js), f"app.js never references snapshot field '{field}'"


def test_appjs_has_reconnecting_ws_client():
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "new WebSocket(" in app_js
    assert "onclose" in app_js and "scheduleReconnect" in app_js
