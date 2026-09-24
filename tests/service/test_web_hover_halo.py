"""tests/service/test_web_hover_halo.py — TDD for the Trade View hover-halo
feature: hovering ANY component of a position (entry marker, any exit marker,
OR a connector line) highlights the WHOLE group (entry + all exits + all
connectors) with an electric sky-blue halo, distinct from the existing
click-driven selection glow (selectedSignalId).

Static-serve + source assertions only (pattern from test_web_trade_grouping.py
/ test_web_review_overlays.py) — no browser automation here (that's covered by
the DevTools-protocol browser-verify step of this task, run separately)."""
from __future__ import annotations

from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def _chart_js() -> str:
    return (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")


# ---- hover state is distinct from click selection ----

def test_hovered_signal_id_is_a_separate_concept_from_selected():
    text = _chart_js()
    assert "hoveredSignalId" in text
    assert "selectedSignalId" in text  # still present, unchanged mechanism


def test_hover_halo_color_constant_is_a_single_tunable_knob():
    text = _chart_js()
    assert "HOVER_HALO_COLOR" in text
    # one definition site (easy for the user to tweak the shade/intensity)
    assert text.count("const HOVER_HALO_COLOR") == 1


# ---- connector-span hover detection (not just entry/exit bar endpoints) ----

def test_connector_span_hover_detection_exists():
    text = _chart_js()
    assert "function findSignalNearConnector" in text
    start = text.index("function findSignalNearConnector")
    end = text.index("\n    function visiblePriceRange", start)
    body = text[start:end]
    # must interpolate along the connector and compare against a price
    # tolerance to disambiguate overlapping signals
    assert "interpPrice" in body
    assert "bestDist" in body


def test_crosshair_handler_falls_back_to_connector_hover():
    text = _chart_js()
    start = text.index("subscribeCrosshairMove")
    end = text.index("\n    });", start)
    body = text[start:end]
    assert "findSignalNearConnector" in body
    assert "setHoveredSignal" in body


# ---- hover halo applied to markers ----

def test_build_markers_applies_hover_halo():
    text = _chart_js()
    start = text.index("function buildMarkers")
    end = text.index("\n    function epochOf", start)
    body = text[start:end]
    assert "isHovered" in body
    assert "HOVER_HALO_COLOR" in body


# ---- hover halo applied to connectors (glow underlay + bright core) ----

def test_draw_ficha_connector_supports_hovered_glow_layer():
    text = _chart_js()
    start = text.index("function drawFichaConnector")
    end = text.index("\n    function hexToRgba", start)
    body = text[start:end]
    assert "hovered" in body
    assert "HOVER_HALO_COLOR" in body


def test_redraw_connectors_draws_hovered_signal_last():
    """Hovered signal must be drawn on top of both the dim layer and a
    (possibly different) selected signal, so the halo reads clearly."""
    text = _chart_js()
    start = text.index("function redrawConnectors")
    end = text.index("\n    function addTradeMarkers", start)
    body = text[start:end]
    assert "hoveredSignalId" in body
    assert body.index("if (hoveredSignalId) {") > body.index("if (selectedSignalId")


# ---- rebuild is debounced to actual hover changes, not every mousemove ----

def test_set_hovered_signal_helper_guards_against_redundant_rebuilds():
    text = _chart_js()
    assert "function setHoveredSignal" in text
    start = text.index("function setHoveredSignal")
    end = text.index("\n    }", start)
    body = text[start:end]
    assert "if (signalId === hoveredSignalId) return;" in body
