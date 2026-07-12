"""M2.1 — RUNS section (spec D.7-RUNS): filters, virtualized table, drawer,
uPlot compare modal. Pure static-serve + source assertions (TestClient,
no browser) — mirrors tests/service/test_frontend.py's pattern."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_runs_js_and_vtable_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        for path in ("/sections/runs.js", "/lib/vtable.js"):
            resp = client.get(path)
            assert resp.status_code == 200, path


def test_no_cdn_in_runs_assets():
    for rel in ("sections/runs.js", "lib/vtable.js"):
        text = (WEB_DIR / rel).read_text(encoding="utf-8")
        assert "cdn.jsdelivr" not in text.lower()
        assert "cdnjs." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text.lower()


def test_runs_js_references_required_api_endpoint():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "/api/runs" in runs_js
    assert "/api/strategies" in runs_js
    assert "/api/runs/" in runs_js  # single-run fetch for the drawer


def test_runs_js_uses_badge_and_fmt_helpers():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.badge" in runs_js
    assert "window.SENTINEL.fmt" in runs_js
    assert "strategyBadge(" in runs_js
    assert "fidelityBadge(" in runs_js


def test_runs_js_uses_vtable_component():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.vtable" in runs_js
    assert "createVTable(" in runs_js


def test_runs_js_registers_sentinel_section_with_render_and_teardown():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.sections.runs = { render, teardown }" in runs_js


def test_runs_js_sets_selected_run_appstate_for_review_handoff():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "appState.selectedRun" in runs_js
    assert 'data-section="review"' in runs_js


def test_runs_js_has_empty_state_copy():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "Sin corridas para los filtros" in runs_js


def test_vtable_js_exposes_create_vtable_global():
    vtable_js = (WEB_DIR / "lib" / "vtable.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.vtable = { createVTable }" in vtable_js


def test_index_includes_vtable_script_tag():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    # tolerate a cache-busting ?v=... query on the src
    assert '<script src="/lib/vtable.js">' in html or '<script src="/lib/vtable.js?v=' in html
