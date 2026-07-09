"""M2.3 — POSICIONES section (web/sections/positions.js). Static-serve +
source assertions only (pattern from test_frontend.py / test_web_review.py);
NO browser automation."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_sections_positions_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/sections/positions.js")
        assert resp.status_code == 200


def test_positions_js_references_forward_sessions_endpoint():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "/api/forward/sessions" in text
    assert "/api/forward/" in text


def test_positions_js_has_three_provenance_tabs():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "HUMANO" in text
    assert "ESTRATEGIA" in text
    assert "IA" in text


def test_positions_js_has_reimport_button_posting_ingest_endpoint():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "/api/ingest/tokata" in text
    assert "POST" in text
    assert "Re-importar TOKATA" in text


def test_positions_js_uses_vtable():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.vtable" in text or "SENTINEL.vtable" in text
    assert "createVTable" in text


def test_positions_js_registers_sentinel_namespace():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "window.SENTINEL" in text
    assert "sections.positions" in text
    assert "render" in text
    assert "teardown" in text


def test_positions_js_has_honest_empty_states():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "Disponible al activar live/IA (B4/B5)" in text
    assert "Sin sesiones forward" in text


def test_positions_js_handoff_to_review_via_appstate():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "appState" in text
    assert "selectedRun" in text
    assert 'data-section="review"' in text


def test_positions_js_uses_badge_helper():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.badge" in text
    assert "strategyBadge(" in text


def test_no_cdn_in_positions_js():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "cdn.jsdelivr" not in text.lower()
    assert "cdnjs." not in text.lower()
    assert "unpkg.com" not in text
    assert "jsdelivr" not in text.lower()
