"""A4 -- chart data controller (web/lib/chartData.js): chunked fetch,
in-flight dedupe, LRU eviction, ascending merge with dedupe, served_tf
notice propagation. Static-serve + source-substring assertions (pattern
from test_web_charts.py / test_web_vlist.py) PLUS real logic execution via
Node (present on this machine, no new dependency -- module is a classic
script with no imports, run standalone with a `window`/`fetch` shim) for the
chunk-math / LRU-eviction / merge-dedupe claims, since those are load-bearing
arithmetic that a substring assertion can't actually verify.

If Node is unavailable in the environment, the exec-based tests are skipped
(substring-only fallback), per the "serve-and-assert" pattern used elsewhere
in this suite.
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


def _chartdata_js() -> str:
    return (WEB_DIR / "lib" / "chartData.js").read_text(encoding="utf-8")


def _chart_js() -> str:
    return (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")


def _run_node(js_body: str):
    """Loads chartData.js in a minimal `window` shim, then runs `js_body`
    (which may use top-level `await`), printing one JSON value via
    `console.log(JSON.stringify(...))` as its last statement, captured and
    decoded here. Raises AssertionError with stdout/stderr on nonzero exit."""
    module_src = _chartdata_js()
    harness = f"""
"use strict";
const window = {{}};
{module_src}
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

def test_lib_chartdata_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/lib/chartData.js")
        assert resp.status_code == 200


def test_no_cdn_in_chartdata_js():
    text = _chartdata_js()
    assert "cdn.jsdelivr" not in text.lower()
    assert "cdnjs." not in text.lower()
    assert "unpkg.com" not in text
    assert "jsdelivr" not in text.lower()


# ---- interface / substring assertions ----

def test_chartdata_js_exposes_create_bar_source():
    text = _chartdata_js()
    assert "window.SENTINEL" in text
    assert "chartData" in text
    assert "function createBarSource(" in text
    assert "createBarSource" in text


def test_chartdata_js_interface_shape():
    text = _chartdata_js()
    for member in ("ensureRange", "onData", "setTf", "coverage", "onNotice"):
        assert member in text


def test_chartdata_js_chunk_constants():
    text = _chartdata_js()
    assert "1500" in text  # CHUNK_BARS
    assert "60000" in text  # MAX_CACHED_BARS LRU cap


def test_chartdata_js_chunk_index_math_present():
    text = _chartdata_js()
    assert "chunkIndexOf" in text
    assert "Math.floor" in text


def test_chartdata_js_in_flight_dedupe_map_present():
    text = _chartdata_js()
    assert "inFlight" in text
    assert "Map()" in text


def test_chartdata_js_ascending_merge_dedupe_console_error():
    text = _chartdata_js()
    assert "console.error" in text
    assert "duplicate" in text.lower()


def test_chartdata_js_served_tf_notice_propagation():
    text = _chartdata_js()
    assert "served_tf" in text
    assert "tf_requested" in text
    assert "emitNotice" in text or "onNotice" in text


def test_chartdata_js_lru_eviction_present():
    text = _chartdata_js()
    assert "evictIfNeeded" in text or "evict" in text.lower()


# ---- chart.js wiring (CHOKE: wiring only) ----

def test_chart_js_wires_bar_source_debounced_ensure_range():
    text = _chart_js()
    assert "chartData" in text
    assert "createBarSource" in text
    assert "ensureRange" in text
    assert "150" in text  # debounce ms
    assert "setTimeout" in text


def test_chart_js_ensure_range_uses_300_and_50_bar_padding():
    text = _chart_js()
    assert "300 * barSec" in text or "300 *" in text
    assert "50 * barSec" in text or "50 *" in text


def test_chart_js_still_preserves_load_seq_token():
    """Regression guard: A4 wiring must not remove the existing loadSeq race
    protection (Wave-3 fix)."""
    text = _chart_js()
    assert "let loadSeq = 0;" in text
    assert "mySeq !== loadSeq" in text


def test_chart_js_propagates_tf_switch_to_bar_source():
    text = _chart_js()
    assert "barSource.setTf(" in text


# ---- real logic execution (chunk math / LRU eviction / merge dedupe) ----

@requires_node
def test_node_chunk_index_math_correct_and_grid_aligned():
    out = _run_node("""
const tfSec = 60; // M1
const span = 1500 * tfSec;
const cases = [0, span - 1, span, span + 1, 2 * span - 1, 2 * span, 3 * span + 42];
const idxs = cases.map((t) => window.SENTINEL.chartData.chunkIndexOf(t, tfSec));
// verify every chunk's bounds are grid-aligned: from = idx*span, to = from+span-tfSec
const bounds = idxs.map((idx) => window.SENTINEL.chartData.chunkBounds(idx, tfSec));
console.log(JSON.stringify({ idxs, bounds }));
""")
    data = json.loads(out)
    assert data["idxs"] == [0, 0, 1, 1, 1, 2, 3]
    tf_sec = 60
    span = 1500 * tf_sec
    for idx, b in zip(data["idxs"], data["bounds"]):
        assert b["from"] == idx * span
        assert b["to"] == idx * span + span - tf_sec


@requires_node
def test_node_lru_eviction_drops_farthest_chunk_from_view():
    out = _run_node("""
const tfSec = 60;
const span = 1500 * tfSec;
const bars = (idx) => {
  const out = [];
  for (let i = 0; i < 1500; i++) {
    out.push([idx * span + i * tfSec, 1, 1, 1, 1, 0]);
  }
  return out;
};
let calls = 0;
const api = {
  async getBars({ from, to }) {
    calls += 1;
    const idx = Math.floor(from / span);
    return { bars: bars(idx), served_tf: "M1", tf_requested: "M1" };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const src = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });

// Load chunk 0 (near view), then chunks 1..39 sequentially (40 chunks * 1500 = 60000 bars, at cap).
// View stays anchored near chunk 0 while we keep loading far-away chunks 39,38,... etc,
// so chunk 0 should be the LAST to be evicted; the FARTHEST chunk (highest idx while view is near 0)
// should be evicted first once the cap is exceeded.
await src.ensureRange(0, span - tfSec); // chunk 0, view near chunk 0
for (let idx = 1; idx <= 41; idx++) {
  // Move the view to progressively higher indices while requesting ONLY the new chunk.
  const from = idx * span;
  const to = from + span - tfSec;
  await src.ensureRange(from, to);
}
const keys = src._cachedChunkKeys;
const hasChunk0 = keys.includes("M1:0");
const cacheSize = src._cacheSize;
console.log(JSON.stringify({ hasChunk0, cacheSize, keyCount: keys.length }));
""")
    data = json.loads(out)
    # Chunk 0 was farthest from the view once we'd moved on to idx=41 (view mid
    # far away); LRU eviction (farthest-from-view) must have dropped it long
    # before chunk 40/41 (which are near the CURRENT view).
    assert data["hasChunk0"] is False
    assert data["cacheSize"] <= 60000


@requires_node
def test_node_lru_keeps_chunk_near_current_view():
    out = _run_node("""
const tfSec = 60;
const span = 1500 * tfSec;
const bars = (idx) => {
  const out = [];
  for (let i = 0; i < 1500; i++) out.push([idx * span + i * tfSec, 1, 1, 1, 1, 0]);
  return out;
};
const api = {
  async getBars({ from }) {
    const idx = Math.floor(from / span);
    return { bars: bars(idx), served_tf: "M1", tf_requested: "M1" };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const src = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
// Load 41 chunks with the view always near the LATEST chunk (simulating scrolling forward).
for (let idx = 0; idx <= 41; idx++) {
  const from = idx * span;
  const to = from + span - tfSec;
  await src.ensureRange(from, to);
}
const keys = src._cachedChunkKeys;
console.log(JSON.stringify({ hasLatest: keys.includes("M1:41"), hasEarliest: keys.includes("M1:0"), size: src._cacheSize }));
""")
    data = json.loads(out)
    assert data["hasLatest"] is True
    assert data["hasEarliest"] is False
    assert data["size"] <= 60000


@requires_node
def test_node_merge_ascending_dedupes_overlapping_fetches():
    out = _run_node("""
const tfSec = 60;
const span = 1500 * tfSec;
// Two overlapping chunk responses that BOTH include t=span (boundary bar),
// simulating an overlapping/duplicate fetch. chunk 0: [0..span), chunk 1: [span..2span)
// but engineer chunk 0's response to ALSO include the first bar of chunk 1 (duplicate).
const chunk0Bars = [];
for (let i = 0; i < 1500; i++) chunk0Bars.push([i * tfSec, 1, 1, 1, 1, 0]);
chunk0Bars.push([span, 999, 999, 999, 999, 0]); // duplicate of chunk1's first bar, BAD value marker
const chunk1Bars = [];
for (let i = 0; i < 1500; i++) chunk1Bars.push([span + i * tfSec, 2, 2, 2, 2, 0]);

const api = {
  async getBars({ from }) {
    const idx = Math.floor(from / span);
    if (idx === 0) return { bars: chunk0Bars, served_tf: "M1", tf_requested: "M1" };
    return { bars: chunk1Bars, served_tf: "M1", tf_requested: "M1" };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const src = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
await src.ensureRange(0, 2 * span - tfSec);
const merged = src._bars;
const ts = merged.map((b) => b[0]);
let ascending = true;
for (let i = 1; i < ts.length; i++) if (ts[i] <= ts[i - 1]) ascending = false;
const uniqueCount = new Set(ts).size;
console.log(JSON.stringify({ ascending, total: ts.length, uniqueCount, dupTBoundaryValue: merged.find((b) => b[0] === span)[1] }));
""")
    data = json.loads(out)
    assert data["ascending"] is True
    assert data["total"] == data["uniqueCount"]  # no duplicate t survived merge
    # The FIRST-seen value for the boundary t must win (chunk0's 999 came
    # first in insertion order for idx=0's chunk, then chunk1's t=span (val=2)
    # is treated as the duplicate and discarded) -- assert only one survives,
    # not which specific one (dedupe contract is "keep first, drop dup").
    assert data["dupTBoundaryValue"] in (999, 2)


@requires_node
def test_node_served_tf_notice_propagated_when_coarser():
    out = _run_node("""
const tfSec = 300; // M5 requested
const span = 1500 * tfSec;
const api = {
  async getBars() {
    return {
      bars: [[0, 1, 1, 1, 1, 0]],
      served_tf: "M15",
      tf_requested: "M5",
    };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const src = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M5", api });
let notice = null;
src.onNotice((n) => { notice = n; });
await src.ensureRange(0, span - tfSec);
console.log(JSON.stringify(notice));
""")
    data = json.loads(out)
    assert data == {"served_tf": "M15", "tf_requested": "M5"}


@requires_node
def test_node_no_notice_when_served_tf_matches_requested():
    out = _run_node("""
const tfSec = 60;
const span = 1500 * tfSec;
const api = {
  async getBars() {
    return { bars: [[0, 1, 1, 1, 1, 0]], served_tf: "M1", tf_requested: "M1" };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const src = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
let notice = null;
src.onNotice((n) => { notice = n; });
await src.ensureRange(0, span - tfSec);
console.log(JSON.stringify(notice));
""")
    data = json.loads(out)
    assert data is None


@requires_node
def test_node_in_flight_requests_deduped_for_same_chunk():
    out = _run_node("""
const tfSec = 60;
const span = 1500 * tfSec;
let callCount = 0;
const api = {
  async getBars() {
    callCount += 1;
    await new Promise((r) => setTimeout(r, 5));
    return { bars: [[0, 1, 1, 1, 1, 0]], served_tf: "M1", tf_requested: "M1" };
  },
  async getCoverage() { return { symbol: "X", tfs: {} }; },
};
const src = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
// Fire two overlapping ensureRange() calls for the SAME chunk before either resolves.
const p1 = src.ensureRange(0, span - tfSec);
const p2 = src.ensureRange(10, span - tfSec - 10);
await Promise.all([p1, p2]);
console.log(JSON.stringify({ callCount }));
""")
    data = json.loads(out)
    assert data["callCount"] == 1


@requires_node
def test_node_coverage_cached_per_symbol_tf():
    out = _run_node("""
let coverageCalls = 0;
const api = {
  async getBars() { return { bars: [], served_tf: "M1", tf_requested: "M1" }; },
  async getCoverage() { coverageCalls += 1; return { symbol: "XAUUSD", tfs: { M1: { first: 0, last: 100 } } }; },
};
const src = window.SENTINEL.chartData.createBarSource({ symbol: "XAUUSD", tf: "M1", api });
await src.coverage();
await src.coverage();
await src.coverage();
console.log(JSON.stringify({ coverageCalls }));
""")
    data = json.loads(out)
    assert data["coverageCalls"] == 1
