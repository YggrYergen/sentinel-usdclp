"""A11 -- LiveAdapter (web/lib/adapters.js): HistAdapter + subscribe to
`bar_tail` SSE (CT-9, /api/bars/tail). series.update(bar) throttled to rAF,
auto-scroll only when the viewport is at the right edge, disconnect on tab
hide (visibilitychange) to save laptop resources. Degrades to pure
HistAdapter behaviour (no error, console.info log) when the endpoint 503s
`{"live": false}` instead of opening an SSE stream.

Pattern mirrors test_web_adapters.py: static-serve + source-substring
assertions, PLUS real logic execution via Node with a stubbed EventSource /
document (visibilitychange) / requestAnimationFrame, run from a temp file
(node <file>) since inline harnesses here get long enough to trip Windows'
command-line length limit.
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

requires_node = pytest.mark.skipif(NODE is None, reason="node not available in this environment")


def _adapters_js() -> str:
    return (WEB_DIR / "lib" / "adapters.js").read_text(encoding="utf-8")


def _chartdata_js() -> str:
    return (WEB_DIR / "lib" / "chartData.js").read_text(encoding="utf-8")


def _run_node(js_body: str) -> str:
    """Loads chartData.js THEN adapters.js in a minimal window/document/
    EventSource/requestAnimationFrame shim, then runs `js_body` (may use
    top-level await), printing one JSON value via
    console.log(JSON.stringify(...)) as its last statement. Written to a
    temp file and run as `node <file>` -- an inline `-e` harness here would
    exceed Windows' command-line length limit."""
    harness = f"""
"use strict";

// ---- rAF stub: synchronous-ish, queue drained by drainRaf() ----
let _rafQueue = [];
function requestAnimationFrame(cb) {{ _rafQueue.push(cb); return _rafQueue.length; }}
function drainRaf() {{
  const q = _rafQueue;
  _rafQueue = [];
  q.forEach((cb) => cb());
}}

// ---- document stub: visibilitychange + hidden flag ----
const _visListeners = [];
const document = {{
  hidden: false,
  addEventListener(name, cb) {{ if (name === "visibilitychange") _visListeners.push(cb); }},
  removeEventListener(name, cb) {{
    if (name === "visibilitychange") {{
      const i = _visListeners.indexOf(cb);
      if (i >= 0) _visListeners.splice(i, 1);
    }}
  }},
}};
function fireVisibilityChange(hidden) {{
  document.hidden = hidden;
  _visListeners.slice().forEach((cb) => cb());
}}

// ---- EventSource stub ----
let _lastEventSource = null;
class FakeEventSource {{
  constructor(url) {{
    this.url = url;
    this.closed = false;
    this._listeners = {{}};
    _lastEventSource = this;
  }}
  addEventListener(name, cb) {{
    this._listeners[name] = this._listeners[name] || [];
    this._listeners[name].push(cb);
  }}
  close() {{ this.closed = true; }}
  emit(name, data) {{
    (this._listeners[name] || []).forEach((cb) => cb({{ data: JSON.stringify(data) }}));
  }}
}}
const EventSource = FakeEventSource;

const window = {{}};
{_chartdata_js()}
{_adapters_js()}
(async () => {{
{js_body}
}})().catch((e) => {{ console.error(e && e.stack || e); process.exit(1); }});
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(harness)
        path = f.name
    try:
        proc = subprocess.run([NODE, path], capture_output=True, text=True, timeout=30)
    finally:
        Path(path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise AssertionError(f"node exec failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return proc.stdout.strip()


# ---- static serve / no new lib file (LiveAdapter lives in adapters.js) ----

def test_lib_adapters_js_still_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/lib/adapters.js")
        assert resp.status_code == 200


# ---- interface / substring assertions ----

def test_adapters_js_exposes_live_adapter():
    text = _adapters_js()
    assert "function LiveAdapter(" in text
    assert "LiveAdapter" in text.split("window.SENTINEL.adapters = {")[1]


def test_live_adapter_subscribes_bar_tail_sse():
    text = _adapters_js()
    assert "/api/bars/tail" in text
    assert "bar_tail" in text
    assert "EventSource" in text


def test_live_adapter_throttles_updates_to_raf():
    text = _adapters_js()
    assert "requestAnimationFrame" in text


def test_live_adapter_disconnects_on_visibilitychange():
    text = _adapters_js()
    assert "visibilitychange" in text


def test_live_adapter_degrades_on_503_without_throwing():
    text = _adapters_js()
    assert "console.info" in text


# ---- real logic execution ----

@requires_node
def test_node_live_adapter_extends_hist_adapter_api():
    out = _run_node("""
const api = {
  async getBars() { return { bars: [], served_tf: "M1", tf_requested: "M1" }; },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
const chart = {
  _candleSeries: { setData: () => {}, update: () => {} },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {}, addTradeMarkers: () => {},
  timeScale: () => ({ scrollPosition: () => 0 }),
};
const live = window.SENTINEL.adapters.LiveAdapter(chart, barSource, { symbol: "XAUUSD" });
console.log(JSON.stringify({
  hasEnsureWindow: typeof live.ensureWindow === "function",
  hasSetSignals: typeof live.setSignals === "function",
  hasSetTf: typeof live.setTf === "function",
  hasConnect: typeof live.connect === "function",
  hasDisconnect: typeof live.disconnect === "function",
}));
""")
    data = json.loads(out)
    assert data == {
        "hasEnsureWindow": True,
        "hasSetSignals": True,
        "hasSetTf": True,
        "hasConnect": True,
        "hasDisconnect": True,
    }


@requires_node
def test_node_live_adapter_applies_bar_tail_update_at_right_edge():
    out = _run_node("""
const api = {
  async getBars() { return { bars: [{ t: 0, o: 1, h: 1, l: 1, c: 1, v: 0 }], served_tf: "M1", tf_requested: "M1" }; },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let updated = null;
const chart = {
  _candleSeries: { setData: () => {}, update: (pt) => { updated = pt; } },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {}, addTradeMarkers: () => {},
  timeScale: () => ({ scrollPosition: () => 0 }), // 0 == at the right edge
};
const live = window.SENTINEL.adapters.LiveAdapter(chart, barSource, { symbol: "XAUUSD" });
await live.ensureWindow(0, 60);
live.connect();
_lastEventSource.emit("bar_tail", {
  symbol: "XAUUSD", tf: "M1", bar: { t: 60, o: 2, h: 2.5, l: 1.8, c: 2.2, v: 5 }, closed: false,
});
drainRaf();
console.log(JSON.stringify(updated));
""")
    data = json.loads(out)
    assert data == {"time": 60, "open": 2, "high": 2.5, "low": 1.8, "close": 2.2}


@requires_node
def test_node_live_adapter_skips_update_when_panned_left():
    out = _run_node("""
const api = {
  async getBars() { return { bars: [{ t: 0, o: 1, h: 1, l: 1, c: 1, v: 0 }], served_tf: "M1", tf_requested: "M1" }; },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let updated = null;
const chart = {
  _candleSeries: { setData: () => {}, update: (pt) => { updated = pt; } },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {}, addTradeMarkers: () => {},
  timeScale: () => ({ scrollPosition: () => 25 }), // panned away from the right edge
};
const live = window.SENTINEL.adapters.LiveAdapter(chart, barSource, { symbol: "XAUUSD" });
await live.ensureWindow(0, 60);
live.connect();
_lastEventSource.emit("bar_tail", {
  symbol: "XAUUSD", tf: "M1", bar: { t: 60, o: 2, h: 2.5, l: 1.8, c: 2.2, v: 5 }, closed: false,
});
drainRaf();
console.log(JSON.stringify({ updated }));
""")
    data = json.loads(out)
    assert data == {"updated": None}


@requires_node
def test_node_live_adapter_filters_events_to_active_tf():
    out = _run_node("""
const api = {
  async getBars() { return { bars: [{ t: 0, o: 1, h: 1, l: 1, c: 1, v: 0 }], served_tf: "M1", tf_requested: "M1" }; },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let updated = null;
const chart = {
  _candleSeries: { setData: () => {}, update: (pt) => { updated = pt; } },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {}, addTradeMarkers: () => {},
  timeScale: () => ({ scrollPosition: () => 0 }),
};
const live = window.SENTINEL.adapters.LiveAdapter(chart, barSource, { symbol: "XAUUSD" });
await live.ensureWindow(0, 60);
live.connect();
_lastEventSource.emit("bar_tail", {
  symbol: "XAUUSD", tf: "M5", bar: { t: 300, o: 9, h: 9, l: 9, c: 9, v: 1 }, closed: false,
});
drainRaf();
console.log(JSON.stringify({ updated }));
""")
    data = json.loads(out)
    assert data == {"updated": None}


@requires_node
def test_node_live_adapter_disconnects_on_tab_hide():
    out = _run_node("""
const api = {
  async getBars() { return { bars: [], served_tf: "M1", tf_requested: "M1" }; },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const barSource = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
const chart = {
  _candleSeries: { setData: () => {}, update: () => {} },
  tf: "M1",
  addOverlay: () => {}, addSarDots: () => {}, addTradeMarkers: () => {},
  timeScale: () => ({ scrollPosition: () => 0 }),
};
const live = window.SENTINEL.adapters.LiveAdapter(chart, barSource, { symbol: "XAUUSD" });
live.connect();
const es = _lastEventSource;
fireVisibilityChange(true); // tab hidden -> disconnect
console.log(JSON.stringify({ closed: es.closed }));
""")
    data = json.loads(out)
    assert data == {"closed": True}
