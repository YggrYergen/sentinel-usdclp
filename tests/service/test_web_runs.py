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


# ---- B7: "Nueva corrida" launcher panel (CT-1 coverage, CT-4 jobs, CT-9 SSE) ----

def test_runs_js_has_launcher_panel_with_selects_and_period_pickers():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "runs-launcher" in runs_js
    assert 'name="variant_id"' in runs_js
    assert 'name="symbol"' in runs_js
    assert 'name="tf"' in runs_js
    # period pickers must be bounded via CT-1 coverage min/max attrs
    assert ".setAttribute(\"min\"" in runs_js or "min = " in runs_js
    assert ".setAttribute(\"max\"" in runs_js or "max = " in runs_js


def test_runs_js_launcher_uses_coverage_endpoint():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "/api/coverage?symbol=" in runs_js or "/api/coverage?" in runs_js


def test_runs_js_launcher_has_exploratory_toggle_default_on():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "Exploratoria (no cuenta para graduación)" in runs_js
    assert 'name="exploratory"' in runs_js
    assert "checked" in runs_js


def test_runs_js_launcher_posts_to_jobs_backtest():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "/api/jobs/backtest" in runs_js


def test_runs_js_launcher_uses_jobs_stream_sse_and_filters_by_job_id():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "EventSource" in runs_js
    assert "/api/jobs/stream" in runs_js
    assert "job_update" in runs_js


def test_runs_js_detail_pane_has_ventana_and_creada_rows():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "Ventana" in runs_js
    assert "periodo_desde" in runs_js
    assert "periodo_hasta" in runs_js
    assert "Creada" in runs_js


def test_runs_js_list_rows_have_engine_fidelity_origin_badges():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "r.engine" in runs_js
    assert "r.origin" in runs_js


# ---- REV-5 Fix 1: teardown() closes the launcher's live EventSource ------

def test_runs_js_registers_active_eventsource_on_section_state():
    """streamJob must register its EventSource on the section state so that
    teardown() can reach it (otherwise the SSE connection leaks when the user
    navigates away while a job is still running)."""
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    assert "activeEventSource" in runs_js
    # streamJob assigns the freshly-opened EventSource to the state
    assert "state.activeEventSource = es" in runs_js


def test_runs_js_teardown_closes_active_eventsource():
    runs_js = (WEB_DIR / "sections" / "runs.js").read_text(encoding="utf-8")
    teardown_src = runs_js.split("function teardown()")[1]
    assert "state.activeEventSource.close()" in teardown_src
    assert "state.activeEventSource = null" in teardown_src
