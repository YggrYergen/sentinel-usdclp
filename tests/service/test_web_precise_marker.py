"""A5b -- precise intrabar marker + connector re-anchor (web/lib/chart.js).

Markers/connectors previously snapped to the bucket's bar time (barTimeOf),
losing the exact intrabar signal timestamp. This task re-anchors the drawn
x-position to a FRACTIONAL offset within the bar:
    x = barX + barWidth * ((signal_t - bucket_t) / tf_seconds), clamped [0,1]
and shows the exact HH:MM:SS in the tooltip.

Pattern follows test_web_adapters.py / test_web_chartdata.py: static-serve +
source-substring assertions, PLUS real logic execution via Node for the
load-bearing fractional-x arithmetic (chart.js is a classic script with no
imports, run standalone under a `window`+`document` shim mirroring the other
suites' `requires_node` harness).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
NODE = shutil.which("node")


def _chart_js() -> str:
    return (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")


def _run_node(js_body: str):
    """Loads chart.js in a minimal `window`+`document` shim (no real DOM/
    lightweight-charts needed for the pure fractional-x helper), then runs
    `js_body`, printing one JSON value via `console.log(JSON.stringify(...))`
    as its last statement, captured and decoded here.

    Uses a temp .js FILE (not `node -e "<inline>"`) because chart.js is large
    enough that the inlined harness overflows Windows' CreateProcess command
    -line length limit (WinError 206) -- test_web_adapters.py's smaller
    adapters.js+chartData.js combo fits inline, chart.js alone does not."""
    harness = f"""
"use strict";
const window = {{}};
{_chart_js()}
{js_body}
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", delete=False, encoding="utf-8"
    ) as f:
        f.write(harness)
        tmp_path = f.name
    try:
        proc = subprocess.run(
            [NODE, tmp_path],
            capture_output=True, text=True, timeout=30,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise AssertionError(f"node exec failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return proc.stdout.strip()


requires_node = pytest.mark.skipif(NODE is None, reason="node not available in this environment")


# ---- static serve ----

def test_lib_chart_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/lib/chart.js")
        assert resp.status_code == 200


# ---- interface / substring assertions ----

def test_chart_js_exposes_fractional_x_helper():
    text = _chart_js()
    assert "fractionalX" in text


def test_chart_js_exposes_precise_time_label_helper():
    text = _chart_js()
    assert "preciseTimeLabel" in text


def test_chart_js_preserves_hover_halo_and_connector_functions():
    """Regression guard: A5b's re-anchor edit must not touch hover-halo /
    connector-hit-test semantics or the loadSeq race guard."""
    text = _chart_js()
    assert "let hoveredSignalId" in text
    assert "function findSignalNearConnector(" in text
    assert "function setHoveredSignal(" in text
    assert "let loadSeq = 0;" in text


# ---- real logic execution (pure fractional-x arithmetic) ----

@requires_node
def test_node_fractional_x_midbar():
    # tf=60s (M1), bucket_t=0, signal_t=30 -> exactly mid-bar -> frac 0.5.
    out = _run_node("""
console.log(JSON.stringify(window.SENTINEL.chart.fractionalX(30, 0, 60)));
""")
    assert json.loads(out) == 0.5


@requires_node
def test_node_fractional_x_at_bucket_start_is_zero():
    out = _run_node("""
console.log(JSON.stringify(window.SENTINEL.chart.fractionalX(0, 0, 60)));
""")
    assert json.loads(out) == 0.0


@requires_node
def test_node_fractional_x_clamped_to_zero_and_one():
    # signal_t before bucket_t -> clamp 0; signal_t past the next bucket -> clamp 1.
    out = _run_node("""
const before = window.SENTINEL.chart.fractionalX(-10, 0, 60);
const after = window.SENTINEL.chart.fractionalX(200, 0, 60);
console.log(JSON.stringify({ before, after }));
""")
    data = json.loads(out)
    assert data == {"before": 0.0, "after": 1.0}


@requires_node
def test_node_precise_time_label_formats_hh_mm_ss():
    # 2024-01-01T00:00:45Z == epoch 1704067245.
    out = _run_node("""
console.log(JSON.stringify(window.SENTINEL.chart.preciseTimeLabel(1704067245)));
""")
    label = json.loads(out)
    assert label.endswith("00:00:45") or ":45" in label


# ---- A5b dispatch 2: WIRING (fallback: bar-anchored marker + 1px hairline
# at fractional x via overlay canvas + exact HH:MM:SS in tooltip) ----

def test_chart_js_has_precise_overlay_canvas():
    """The fallback hairline layer must be an overlay CANVAS element created
    by the chart scaffold (pointer-events: none so hover semantics stay
    owned by lightweight-charts' own hit-testing)."""
    text = _chart_js()
    assert "chart-precise-overlay" in text
    assert 'createElement("canvas")' in text
    assert "pointerEvents" in text


def test_chart_js_drawing_code_consumes_fractional_x():
    """The positioning arithmetic x = barLeft + barWidth * fractionalX(...)
    must actually be used by the drawing path, not just exported."""
    text = _chart_js()
    assert "barWidth * fractionalX(" in text
    assert "preciseXOf" in text
    assert "redrawPreciseOverlay" in text


def test_chart_js_hairline_redraw_wired_to_marker_and_range_paths():
    """Hairlines must re-anchor when markers rebuild (hover/selection/
    playback reveal) AND when the visible range pans/zooms."""
    text = _chart_js()
    # called from more than one place (definition + >=2 call sites)
    assert text.count("redrawPreciseOverlay(") >= 3


def test_chart_js_tooltip_uses_precise_time_label():
    """Signal tooltip must include the exact HH:MM:SS via preciseTimeLabel."""
    text = _chart_js()
    assert "preciseTimeLabel(tsIn)" in text
    # per-ficha exit rows also get the exact exit time
    assert "preciseTimeLabel(epochOf(t.ts_out))" in text


@requires_node
def test_node_precise_x_of_intrabar_signal():
    # M1 bar (tf=60s), bucket t=0, bar CENTER x=100px, bar width=8px.
    # Signal at t=30 (mid-bar) -> x = (100 - 4) + 8*0.5 = 100.
    # Signal at t=45 (3/4)     -> x = 96 + 8*0.75 = 102.
    # Signal before bucket     -> clamp 0 -> x = 96 (left edge).
    out = _run_node("""
const px = window.SENTINEL.chart.preciseXOf;
console.log(JSON.stringify({
  mid: px(30, 0, 60, 100, 8),
  q3: px(45, 0, 60, 100, 8),
  clamped: px(-5, 0, 60, 100, 8),
}));
""")
    data = json.loads(out)
    assert data == {"mid": 100, "q3": 102, "clamped": 96}
