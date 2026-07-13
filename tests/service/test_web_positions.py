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


# ---- B3a: HUMANO tab card list (vlist) -----------------------------------

def test_positions_js_humano_fetches_positions_endpoint():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "/api/positions" in text
    assert "origin=human" in text


def test_positions_js_humano_uses_vlist():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.vlist" in text or "SENTINEL.vlist" in text
    assert "createVList" in text


def test_positions_js_humano_renders_group_fields():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "group_id" in text
    assert "position_id" in text
    assert "px_in" in text
    assert "px_out" in text
    assert "mae" in text
    assert "mfe" in text


def test_positions_js_humano_null_fields_render_dashes():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "--" in text
    # pct/mae/mfe formatting must go through a null-safe helper
    assert "fmtOrDash" in text or "orDash" in text or "fmt.num" in text or "fmt.pct" in text


def test_positions_js_humano_group_chevron_expand():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "chevron" in text.lower()
    assert "expand" in text.lower() or "toggle" in text.lower()


def test_positions_js_humano_selection_uses_vlist_selected_class():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "vlist-selected" in text or "setSelected" in text


def test_positions_js_humano_has_onpositionselect_hook():
    """B3b (expanded panel + replay) will consume this hook; B3a leaves it
    as a documented no-op."""
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "onPositionSelect" in text


def test_positions_js_humano_injects_scoped_style():
    """CHOKE: index.html/style.css are off-limits for this task; any new
    CSS must be injected section-scoped via a <style id="positions-humano-css">."""
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "positions-humano-css" in text
