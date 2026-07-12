"""A5a -- CT-2 adapters (web/lib/adapters.js): HistAdapter maps barSource's
CT-2 bars to lightweight-charts candlestick points, ReplayAdapter reveals
bars+overlays in lockstep off one already-fetched window, setSignals windows
markers to the loaded range, and TF switch re-anchors by bar bucket.
Static-serve + source-substring assertions (pattern from
test_web_chartdata.py) PLUS real logic execution via Node for the load-bearing
mapping/lockstep/windowing arithmetic, mirroring test_web_chartdata.py's
`requires_node` harness (chartData.js + adapters.js are both classic scripts
with no imports, run standalone under a `window` shim).

If Node is unavailable, the exec-based tests are skipped (substring-only
fallback), per the same pattern.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
NODE = shutil.which("node")


def _adapters_js() -> str:
    return (WEB_DIR / "lib" / "adapters.js").read_text(encoding="utf-8")


def _chartdata_js() -> str:
    return (WEB_DIR / "lib" / "chartData.js").read_text(encoding="utf-8")


def _chart_js() -> str:
    return (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")


def _run_node(js_body: str):
    """Loads chartData.js THEN adapters.js in a minimal `window` shim, then
    runs `js_body` (may use top-level await), printing one JSON value via
    `console.log(JSON.stringify(...))` as its last statement, captured and
    decoded here. Raises AssertionError with stdout/stderr on nonzero exit."""
    harness = f"""
"use strict";
const window = {{}};
{_chartdata_js()}
{_adapters_js()}
(async () => {{
{js_body}
}})().catch((e) => {{ console.error(e && e.stack || e); process.exit(1); }});
"""
    proc = subprocess.run(
        [NODE, "--input-type=commonjs", "-e", harness],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(f"node exec failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return proc.stdout.strip()


requires_node = pytest.mark.skipif(NODE is None, reason="node not available in this environment")


# ---- static serve ----

def test_lib_adapters_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/lib/adapters.js")
        assert resp.status_code == 200


def test_no_cdn_in_adapters_js():
    text = _adapters_js()
    assert "cdn.jsdelivr" not in text.lower()
    assert "cdnjs." not in text.lower()
    assert "unpkg.com" not in text
    assert "jsdelivr" not in text.lower()


# ---- interface / substring assertions ----

def test_adapters_js_exposes_hist_and_replay_adapter():
    text = _adapters_js()
    assert "window.SENTINEL" in text
    assert "window.SENTINEL.adapters" in text
    assert "function HistAdapter(" in text
    assert "function ReplayAdapter(" in text


def test_hist_adapter_uses_bar_source_ensure_range():
    text = _adapters_js()
    assert "barSource.ensureRange(" in text


def test_hist_adapter_maps_ct2_to_lightweight_charts_shape():
    text = _adapters_js()
    assert "ct2ToCandle" in text
    assert "time:" in text and "open:" in text and "high:" in text and "low:" in text and "close:" in text


def test_replay_adapter_has_play_pause_seek_and_lockstep_reveal():
    text = _adapters_js()
    for member in ("function ReplayAdapter(", "play", "pause", "seek", "revealTo"):
        assert member in text


def test_set_signals_windows_and_preserves_chart_marker_ownership():
    text = _adapters_js()
    assert "setSignals" in text
    assert "signalTouchesWindow" in text
    assert "chart.addTradeMarkers(" in text
    # A5a must NOT reimplement hover/connector semantics -- those stay owned
    # by lib/chart.js (only mentioned here in prose comments, never assigned
    # or defined as functions in this file).
    assert "let hoveredSignalId" not in text
    assert "function findSignalNearConnector(" not in text


def test_tf_switch_reanchors_by_bar_bucket():
    text = _adapters_js()
    assert "function setTf(" in text
    assert "bucketOf" in text


# ---- chart.js wiring (CHOKE: adapters wiring) ----

def test_chart_js_wires_hist_adapter():
    text = _chart_js()
    assert "window.SENTINEL.adapters" in text
    assert "HistAdapter" in text


def test_chart_js_still_preserves_load_seq_token():
    """Regression guard: A5a wiring must not remove the existing loadSeq race
    protection (Wave-3 fix)."""
    text = _chart_js()
    assert "let loadSeq = 0;" in text
    assert "mySeq !== loadSeq" in text


def test_chart_js_preserves_hover_halo_and_connector_functions():
    """Regression guard: chart.js CHOKE edit must not touch hover-halo /
    connector-hit-test semantics."""
    text = _chart_js()
    assert "let hoveredSignalId" in text
    assert "function findSignalNearConnector(" in text
    assert "function setHoveredSignal(" in text


def test_chart_js_normalizes_ct2_bars_to_tuples():
    """Root-cause fix: /api/bars (CT-2) returns bar OBJECTS {t,o,h,l,c,v};
    chart.js's internal pipeline (barToCandle et al.) destructures tuples
    [t,o,h,l,c,v] by position. Without normalization at the fetch boundary,
    candleSeries.setData() would receive all-undefined points."""
    text = _chart_js()
    assert "ct2BarsToTuples" in text


def test_chart_js_degrades_clean_without_adapters_namespace():
    """If adapters.js isn't included, chart.js must not crash: the
    histAdapter wiring is guarded behind `window.SENTINEL.adapters &&`."""
    text = _chart_js()
    assert "window.SENTINEL.adapters &&" in text or "window.SENTINEL.adapters&&" in text


# ---- real logic execution (mapping / lockstep / windowing / bucket math) ----

@requires_node
def test_node_hist_adapter_maps_single_ct2_object_bar_to_lightweight_charts_point():
    # Exercises HistAdapter's own CT-2-object -> lightweight-charts mapping
    # through barSource.ensureRange with exactly ONE cached bar (a single
    # object, so chartData.js's rebuildMerged() tuple-indexed dedupe -- Task
    # A4, out of A5a's scope, see DESVIACIONES -- never sees a second `t` to
    # collide with). test_ct2_to_candle_pure_mapping below covers the
    # multi-bar object-mapping case directly (bypassing that dependency).
    out = _run_node("""
const api = {
  async getBars() {
    return { bars: [{ t: 0, o: 1.1, h: 1.5, l: 1.0, c: 1.3, v: 10 }], served_tf: "M1", tf_requested: "M1" };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let painted = null;
const chart = {
  _candleSeries: { setData: (pts) => { painted = pts; } },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {}, addTradeMarkers: () => {},
};
const hist = window.SENTINEL.adapters.HistAdapter(chart, barSource);
await hist.ensureWindow(0, 60);
console.log(JSON.stringify(painted));
""")
    data = json.loads(out)
    assert data == [{"time": 0, "open": 1.1, "high": 1.5, "low": 1.0, "close": 1.3}]


@requires_node
def test_ct2_to_candle_pure_mapping_multi_bar():
    # Direct unit test of the CT-2 object -> lightweight-charts mapping used
    # by both HistAdapter and ReplayAdapter, independent of barSource/
    # chartData.js's merge path (see DESVIACIONES: chartData.js's
    # rebuildMerged() dedupes by `bar[0]`, which breaks on >1 CT-2 OBJECT bar
    # per merge -- a pre-existing bug in a file outside A5a's scope). This
    # proves the {t,o,h,l,c,v} -> {time,open,high,low,close} mapping is
    # correct for realistic multi-bar CT-2 payloads.
    out = _run_node("""
const bars = [
  { t: 0, o: 1.1, h: 1.5, l: 1.0, c: 1.3, v: 10 },
  { t: 60, o: 1.3, h: 1.6, l: 1.2, c: 1.4, v: 20 },
];
console.log(JSON.stringify(bars.map(window.SENTINEL.adapters.ct2ToCandle)));
""")
    data = json.loads(out)
    assert data == [
        {"time": 0, "open": 1.1, "high": 1.5, "low": 1.0, "close": 1.3},
        {"time": 60, "open": 1.3, "high": 1.6, "low": 1.2, "close": 1.4},
    ]


@requires_node
def test_node_hist_adapter_ensure_window_clips_to_requested_range():
    # tuple-shaped bars (matches test_web_chartdata.py's own convention) --
    # isolates this test to ensureWindow()'s clip-to-[from,to] logic; see
    # DESVIACIONES re: chartData.js rebuildMerged()'s tuple-only dedupe.
    out = _run_node("""
const api = {
  async getBars() {
    return {
      bars: [[0, 1, 1, 1, 1, 0], [60, 2, 2, 2, 2, 0], [120, 3, 3, 3, 3, 0]],
      served_tf: "M1", tf_requested: "M1",
    };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let painted = null;
const chart = {
  _candleSeries: { setData: (pts) => { painted = pts; } },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {}, addTradeMarkers: () => {},
};
const hist = window.SENTINEL.adapters.HistAdapter(chart, barSource);
await hist.ensureWindow(60, 120);
console.log(JSON.stringify(painted.map((p) => p.time)));
""")
    data = json.loads(out)
    assert data == [60, 120]


@requires_node
def test_node_replay_adapter_lockstep_bars_and_overlay_same_index():
    # tuple-shaped bars (matches test_web_chartdata.py's own convention) --
    # isolates this test to ReplayAdapter's lockstep-reveal logic; see
    # DESVIACIONES re: chartData.js rebuildMerged()'s tuple-only dedupe.
    out = _run_node("""
const api = {
  async getBars() {
    return {
      bars: [
        [0, 1, 1, 1, 1, 0],
        [60, 2, 2, 2, 2, 0],
        [120, 3, 3, 3, 3, 0],
      ],
      served_tf: "M1", tf_requested: "M1",
    };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let paintedBars = null;
let paintedOverlay = null;
const chart = {
  _candleSeries: { setData: (pts) => { paintedBars = pts; } },
  tf: "M1",
  addOverlay: (id, pts) => { paintedOverlay = pts; },
  addSarDots: () => {},
  addTradeMarkers: () => {},
};
const replay = window.SENTINEL.adapters.ReplayAdapter(chart, barSource, { fromT: 0, toT: 120, speed: 1 });
await replay.prime();
replay.setOverlays({ ema8: [{ t: 0, v: 1.0 }, { t: 60, v: 1.1 }, { t: 120, v: 1.2 }] });
replay.seek(60); // reveal bars[0..1] i.e. t=0 and t=60
console.log(JSON.stringify({
  barTimes: paintedBars.map((p) => p.time),
  overlayLen: paintedOverlay.length,
  overlayLastT: paintedOverlay[paintedOverlay.length - 1][0],
}));
""")
    data = json.loads(out)
    # bars and overlay revealed to the SAME index (2 points: t=0,60) -- lockstep.
    assert data["barTimes"] == [0, 60]
    assert data["overlayLen"] == 2
    assert data["overlayLastT"] == 60


@requires_node
def test_node_replay_adapter_seek_to_end_reveals_all():
    # tuple-shaped bars -- see note above (chartData.js dedupe scope).
    out = _run_node("""
const api = {
  async getBars() {
    return {
      bars: [
        [0, 1, 1, 1, 1, 0],
        [60, 2, 2, 2, 2, 0],
        [120, 3, 3, 3, 3, 0],
      ],
      served_tf: "M1", tf_requested: "M1",
    };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let paintedBars = null;
const chart = {
  _candleSeries: { setData: (pts) => { paintedBars = pts; } },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {}, addTradeMarkers: () => {},
};
const replay = window.SENTINEL.adapters.ReplayAdapter(chart, barSource, { fromT: 0, toT: 120, speed: 1 });
await replay.prime();
replay.seek(9999);
console.log(JSON.stringify(paintedBars.map((p) => p.time)));
""")
    data = json.loads(out)
    assert data == [0, 60, 120]


@requires_node
def test_node_set_signals_filters_out_of_window_trades():
    out = _run_node("""
const api = {
  async getBars() {
    return {
      bars: [
        { t: 0, o: 1, h: 1, l: 1, c: 1, v: 0 },
        { t: 60, o: 2, h: 2, l: 2, c: 2, v: 0 },
      ],
      served_tf: "M1", tf_requested: "M1",
    };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let markedTrades = null;
const chart = {
  _candleSeries: { setData: () => {} },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {},
  addTradeMarkers: (trades) => { markedTrades = trades; },
};
const hist = window.SENTINEL.adapters.HistAdapter(chart, barSource);
await hist.ensureWindow(0, 60);
hist.setSignals([
  { signal_id: "in-window", side: "LONG", ts_in: 0, px_in: 1.0 },
  { signal_id: "out-of-window", side: "LONG", ts_in: 600, px_in: 1.0 },
]);
console.log(JSON.stringify(markedTrades.map((t) => t.signal_id)));
""")
    data = json.loads(out)
    assert data == ["in-window"]


@requires_node
def test_node_set_signals_refilters_on_window_change():
    out = _run_node("""
const api = {
  async getBars({ from }) {
    if (from < 300) {
      return { bars: [{ t: 0, o: 1, h: 1, l: 1, c: 1, v: 0 }], served_tf: "M1", tf_requested: "M1" };
    }
    return { bars: [{ t: 600, o: 1, h: 1, l: 1, c: 1, v: 0 }], served_tf: "M1", tf_requested: "M1" };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let markedTrades = null;
const chart = {
  _candleSeries: { setData: () => {} },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {},
  addTradeMarkers: (trades) => { markedTrades = trades; },
};
const hist = window.SENTINEL.adapters.HistAdapter(chart, barSource);
await hist.ensureWindow(0, 60);
hist.setSignals([{ signal_id: "sig-a", side: "LONG", ts_in: 0, px_in: 1.0 }]);
const firstWindowMarked = markedTrades.map((t) => t.signal_id);
// move the window far away -- the signal at t=0 should now be filtered out.
await hist.ensureWindow(600, 660);
console.log(JSON.stringify({ firstWindowMarked, secondWindowMarked: markedTrades.map((t) => t.signal_id) }));
""")
    data = json.loads(out)
    assert data["firstWindowMarked"] == ["sig-a"]
    assert data["secondWindowMarked"] == []


@requires_node
def test_node_bucket_of_snaps_to_tf_grid():
    out = _run_node("""
const b1 = window.SENTINEL.adapters.bucketOf(125, 60); // M1 -> bucket 120
const b2 = window.SENTINEL.adapters.bucketOf(125, 300); // M5 -> bucket 0
console.log(JSON.stringify({ b1, b2 }));
""")
    data = json.loads(out)
    assert data == {"b1": 120, "b2": 0}


@requires_node
def test_node_tf_switch_reanchors_ensure_window_around_bucketed_anchor():
    # Asserts on the ADAPTER's own tracked window (windowFrom/windowTo), not
    # the raw chunk-fetch args chartData.js's ensureRange happens to issue
    # internally -- those are chunk-grid-aligned (chartData.js concern, out
    # of A5a's scope), not the adapter's requested [from,to].
    out = _run_node("""
const api = {
  async getBars({ from, to }) {
    return { bars: [[from, 1, 1, 1, 1, 0]], served_tf: "M5", tf_requested: "M5" };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
const chart = {
  _candleSeries: { setData: () => {} },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {}, addTradeMarkers: () => {},
};
const hist = window.SENTINEL.adapters.HistAdapter(chart, barSource);
await hist.ensureWindow(0, 600); // M1 window, span=600
barSource.setTf("M5");
// anchor at t=730 -> M5 bucket = floor(730/300)*300 = 600; span held at 600
// -> new window = [600 - 300, 600 + 300] = [300, 900], midpoint 600.
await hist.setTf("M5", 730);
console.log(JSON.stringify({ from: hist.windowFrom, to: hist.windowTo, mid: (hist.windowFrom + hist.windowTo) / 2 }));
""")
    data = json.loads(out)
    assert data["mid"] == 600
    assert data["from"] == 300
    assert data["to"] == 900
