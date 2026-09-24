"""A7 -- goto-date control (web/lib/goto.js): datetime-local input + "Ir"
button wired into CHARTS and REVIEW/TV toolbars. On go: clamp target to CT-1
coverage (fetched once per symbol, cached), then chartInst.setWindow(target
-150*tf, target+150*tf) (chart.js's setWindow already fetches + calls
timeScale().setVisibleRange internally -- see web/lib/chart.js:1087-1104).

Pattern mirrors test_web_adapters.py: static-serve + source-substring
assertions, PLUS real logic execution via Node for the load-bearing
clamp/window-math (no DOM needed for those -- pure functions).
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


def _goto_js() -> str:
    return (WEB_DIR / "lib" / "goto.js").read_text(encoding="utf-8")


def _charts_js() -> str:
    return (WEB_DIR / "sections" / "charts.js").read_text(encoding="utf-8")


def _review_js() -> str:
    return (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")


def _run_node(js_body: str):
    harness = f"""
"use strict";
const window = {{}};
{_goto_js()}
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

def test_lib_goto_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/lib/goto.js")
        assert resp.status_code == 200


def test_no_cdn_in_goto_js():
    text = _goto_js()
    assert "cdn.jsdelivr" not in text.lower()
    assert "cdnjs." not in text.lower()
    assert "unpkg.com" not in text


# ---- interface ----

def test_goto_js_exposes_namespace():
    text = _goto_js()
    assert "window.SENTINEL.goto" in text
    assert "createGotoControl" in text
    assert "clampToCoverage" in text
    assert "windowAround" in text


def test_charts_js_wires_goto_control():
    text = _charts_js()
    assert "window.SENTINEL.goto" in text
    assert "createGotoControl" in text


def test_review_js_wires_goto_control():
    text = _review_js()
    assert "window.SENTINEL.goto" in text
    assert "createGotoControl" in text


# ---- real logic execution ----

@requires_node
def test_node_clamp_within_coverage_is_unclamped():
    out = _run_node("""
const r = window.SENTINEL.goto.clampToCoverage(500, { first: 0, last: 1000 });
console.log(JSON.stringify(r));
""")
    data = json.loads(out)
    assert data == {"epoch": 500, "clamped": False, "reason": None}


@requires_node
def test_node_clamp_before_first_clamps_up():
    out = _run_node("""
const r = window.SENTINEL.goto.clampToCoverage(-100, { first: 0, last: 1000 });
console.log(JSON.stringify(r));
""")
    data = json.loads(out)
    assert data["epoch"] == 0
    assert data["clamped"] is True
    assert data["reason"] == "before-first"


@requires_node
def test_node_clamp_after_last_clamps_down():
    out = _run_node("""
const r = window.SENTINEL.goto.clampToCoverage(9999, { first: 0, last: 1000 });
console.log(JSON.stringify(r));
""")
    data = json.loads(out)
    assert data["epoch"] == 1000
    assert data["clamped"] is True
    assert data["reason"] == "after-last"


@requires_node
def test_node_clamp_missing_tf_coverage_passes_through():
    # CT-1: TF ausente del lake => key ausente -- no coverage to clamp against.
    out = _run_node("""
const r = window.SENTINEL.goto.clampToCoverage(500, undefined);
console.log(JSON.stringify(r));
""")
    data = json.loads(out)
    assert data == {"epoch": 500, "clamped": False, "reason": None}


@requires_node
def test_node_window_around_spans_150_bars_each_side():
    out = _run_node("""
const w = window.SENTINEL.goto.windowAround(10000, "M1"); // 60s/bar
console.log(JSON.stringify(w));
""")
    data = json.loads(out)
    assert data == {"from": 10000 - 150 * 60, "to": 10000 + 150 * 60}


@requires_node
def test_node_window_around_respects_tf_seconds():
    out = _run_node("""
const w = window.SENTINEL.goto.windowAround(100000, "M5"); // 300s/bar
console.log(JSON.stringify(w));
""")
    data = json.loads(out)
    assert data == {"from": 100000 - 150 * 300, "to": 100000 + 150 * 300}


@requires_node
def test_node_datetime_local_round_trip():
    out = _run_node("""
const epoch = window.SENTINEL.goto.datetimeLocalToEpoch("2026-07-12T10:30");
const back = window.SENTINEL.goto.epochToDatetimeLocal(epoch);
console.log(JSON.stringify({ epoch, back }));
""")
    data = json.loads(out)
    assert data["back"] == "2026-07-12T10:30"


@requires_node
def test_node_create_goto_control_appends_input_and_button_and_calls_set_window():
    out = _run_node("""
// minimal DOM shim -- enough for createGotoControl's element creation/append/listen.
class FakeEl {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.classList = { add: () => {}, remove: () => {}, toggle: () => {} };
    this._listeners = {};
    this.attrs = {};
  }
  appendChild(c) { this.children.push(c); return c; }
  addEventListener(evt, fn) { this._listeners[evt] = fn; }
  set className(v) { this.attrs.className = v; }
  set type(v) { this.attrs.type = v; }
  set textContent(v) { this.attrs.textContent = v; }
  set value(v) { this.attrs.value = v; }
  get value() { return this.attrs.value; }
}
global.document = { createElement: (tag) => new FakeEl(tag) };
global.fetch = () => Promise.reject(new Error("no network in test harness"));
const host = new FakeEl("div");
let calledWith = null;
const chartInst = { setWindow: (from, to) => { calledWith = [from, to]; } };
const ctl = window.SENTINEL.goto.createGotoControl(host, {
  getSymbol: () => "XAUUSD",
  getTf: () => "M1",
  getChartInst: () => chartInst,
});
ctl.input.value = "2026-07-12T10:30";
ctl.btn._listeners.click();
// allow the async onGo (fetchCoverage swallow-catch) microtasks to settle.
await new Promise((res) => setTimeout(res, 50));
console.log(JSON.stringify({ hasInput: !!ctl.input, hasBtn: !!ctl.btn, calledWith }));
""")
    data = json.loads(out)
    assert data["hasInput"] is True
    assert data["hasBtn"] is True
    # global fetch is undefined in this bare harness -> fetchCoverage rejects
    # -> coverage=null -> clampToCoverage passes through unclamped -> setWindow
    # still called with the +-150*60s window around the parsed target.
    assert data["calledWith"] is not None
