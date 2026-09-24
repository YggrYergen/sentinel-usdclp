"""W0.2 — auto-versioned asset token (`__ASSET_V__`) replaces hand-bumped
`?v=...` query strings in web/index.html.

`compute_asset_version(web_dir)` hashes the max mtime across web/**/*.js and
web/**/*.css; `GET /` substitutes the literal token for that version in
memory (index.html on disk keeps the literal token).
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from sentinel_engine.service.routers import system as system_router

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_index_html_has_no_literal_token_and_versions_match(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.text
        assert "__ASSET_V__" not in body

        versions = set(re.findall(r'(?:app\.js|style\.css)\?v=([0-9a-f]+)', body))
        assert len(versions) == 1, f"expected one shared version, got {versions}"


def test_index_html_on_disk_keeps_literal_token():
    text = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert "__ASSET_V__" in text
    assert "app.js?v=__ASSET_V__" in text


def test_compute_asset_version_changes_when_mtime_changes(monkeypatch, tmp_path):
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "app.js").write_text("console.log(1);", encoding="utf-8")
    (web_dir / "style.css").write_text("body{}", encoding="utf-8")

    v1 = system_router.compute_asset_version(web_dir)

    # Simulate a newer file being touched by bumping its mtime forward.
    js_path = web_dir / "app.js"
    newer = js_path.stat().st_mtime + 1000
    import os

    os.utime(js_path, (newer, newer))

    v2 = system_router.compute_asset_version(web_dir)

    assert v1 != v2
    assert re.match(r"^[0-9a-f]{10}$", v1)
    assert re.match(r"^[0-9a-f]{10}$", v2)
