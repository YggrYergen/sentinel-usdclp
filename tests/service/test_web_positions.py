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
    # B4/B5 landed: the "future feature" placeholder copy is gone; the
    # surviving honest empty states are IA (paper engine pending, Wave D)
    # and the forward-sessions list.
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "Disponible al activar live/IA (B4/B5)" not in text
    assert "Sin posiciones IA aún" in text
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


# ---- B3b: expanded detail panel + replay -----------------------------------

def test_positions_js_humano_panel_uses_hist_adapter_and_chart_create():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.adapters" in text
    assert "HistAdapter" in text
    assert "window.SENTINEL.chart" in text
    assert "chart.create" in text


def test_positions_js_humano_panel_windows_30_bars_around_entry_exit():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "30" in text
    assert "ensureWindow" in text


def test_positions_js_humano_panel_sets_signals_with_entry_exit():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "setSignals" in text


def test_positions_js_humano_panel_has_replay_button_using_replay_adapter():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "ReplayAdapter" in text
    assert "fromT" in text
    assert "toT" in text
    assert "pauseAfterBars" in text


def test_positions_js_humano_panel_replay_window_is_4x_tf_padded():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "4 * tfSec" in text or "4 * tf_s" in text or "tfSec * 4" in text


def test_positions_js_humano_panel_has_analizar_button_disabled_with_tooltip():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "Analizar" in text
    assert "Análisis IA" in text or "Analisis IA" in text
    assert "próximamente" in text or "proximamente" in text
    assert "disabled" in text


def test_positions_js_humano_panel_closes_on_escape_with_listener_teardown():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert '"keydown"' in text
    assert "Escape" in text
    assert "removeEventListener" in text


def test_positions_js_humano_panel_degrades_clean_without_adapters_or_chart():
    """Guard pattern: if window.SENTINEL.adapters / window.SENTINEL.chart are
    missing, the panel must not crash — checked before use (repo pattern,
    same as chart.js's `window.SENTINEL.adapters &&` guard)."""
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.adapters &&" in text or "window.SENTINEL.adapters&&" in text
    assert "window.SENTINEL.chart &&" in text or "window.SENTINEL.chart&&" in text


# ---- B4: ESTRATEGIA two-floor + labels -----------------------------------

def test_positions_js_fetches_strategy_scorecard():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "/api/strategies/" in text
    assert "/scorecard" in text


def test_positions_js_has_two_floor_markup():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "estrategia-floor-real" in text
    assert "estrategia-floor-teorico" in text


def test_positions_js_teorico_null_shows_sin_baseline():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "sin baseline" in text


def test_positions_js_sessions_header_renamed():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "Sesiones forward" in text


def test_positions_js_tf_badge_present():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "estrategia-tf-badge" in text


def test_positions_js_estado_buttons_still_present():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "manage-estado-btn" in text
    assert '"activa"' in text
    assert '"pausada"' in text
    assert '"graduada"' in text


# ---- B5: IA subtab (empty-state + aggregated card + reused HUMANO list) --

def test_positions_js_ia_tab_fetches_origin_ia():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "origin=ia" in text or 'fetchPositions("ia"' in text or "fetchPositions('ia'" in text


def test_positions_js_ia_tab_has_aggregate_card_markup():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "positions-ia-aggregate" in text


def test_positions_js_ia_tab_empty_state_exact_text():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert "Sin posiciones IA aún — se activa con el motor paper (Wave D)" in text


# ---- REV-5 Fix 2: multi-lote group cards aggregate honestly ---------------
# px_in/px_out of a multi-child group = VWAP over its children; pct/mae/mfe
# have no defined group aggregation yet -> "--".

def _extract_vwap_fn(text: str) -> str:
    start = text.index("function vwapOf")
    end = text.index("\n  }", start) + len("\n  }")
    return text[start:end]


def test_positions_js_group_card_vwap_hand_computed_3_lote():
    """Execute the actual vwapOf implementation (via node) against a 3-lot
    fixture with distinct prices/volumes and compare to hand-computed VWAPs.
    px_out of one child is null (still open) and must be ignored."""
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        import pytest
        pytest.skip("node not available")

    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    vwap_src = _extract_vwap_fn(text)
    fixture = [
        {"px_in": 100.0, "px_out": 110.0, "volume": 1},
        {"px_in": 102.0, "px_out": None, "volume": 2},
        {"px_in": 105.0, "px_out": 112.0, "volume": 3},
    ]
    script = (
        vwap_src
        + f"\nconst children = {json.dumps(fixture)};"
        + "\nconsole.log(JSON.stringify({"
        + 'vin: vwapOf(children, "px_in"), vout: vwapOf(children, "px_out")'
        + "}));"
    )
    out = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True
    ).stdout.strip()
    result = json.loads(out)
    # hand-computed: (100*1 + 102*2 + 105*3) / (1+2+3) = 619/6
    assert abs(result["vin"] - 619.0 / 6.0) < 1e-9
    # hand-computed (null px_out ignored): (110*1 + 112*3) / (1+3) = 446/4
    assert abs(result["vout"] - 446.0 / 4.0) < 1e-9


def test_positions_js_group_card_multi_uses_vwap_and_dashes_pct_mae_mfe():
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    card_src = text.split("function renderHumanoGroupCard")[1]
    # group px_in/px_out come from vwapOf over children, not children[0]
    assert 'vwapOf(children, "px_in")' in card_src
    assert 'vwapOf(children, "px_out")' in card_src
    # pct/mae/mfe of a multi-lote group are "--" (aggregate undefined);
    # single-child groups keep the child's values.
    assert 'isMulti ? "--" : fmtOrDash(fmt, child.pct, "pct")' in card_src
    assert 'isMulti ? "--" : fmtOrDash(fmt, child.mae)' in card_src
    assert 'isMulti ? "--" : fmtOrDash(fmt, child.mfe)' in card_src


def test_positions_js_ia_tab_reuses_humano_list_builder():
    """B5 must not copy-paste a second list builder; renderHumanoTab (or its
    item/card builders) is parametrized by origin and reused for IA."""
    text = (WEB_DIR / "sections" / "positions.js").read_text(encoding="utf-8")
    assert text.count("function renderHumanoGroupCard") == 1
    assert text.count("function renderHumanoChildRow") == 1
    assert text.count("function buildHumanoFlatItems") == 1
    # renderHumanoTab must accept/forward an origin param instead of a
    # second copy-pasted "renderIaTab" list builder existing independently.
    assert "function renderHumanoTab(host, origin" in text or "function renderHumanoTab(host," in text
    assert "renderHumanoTab(" in text.split("function renderHumanoTab")[-1] or text.count("renderHumanoTab(") >= 2
