"""tests/service/test_web_trade_grouping.py — TDD for Wave-2b (V1 signal
grouping UX), plan docs/superpowers/plans/2026-07-10-trade-view-wave2.md
reqs 1/2/3/5/7. Static-serve + source assertions only (pattern from
test_web_charts.py / test_web_review_overlays.py) -- no browser automation;
the purely-visual result is verified in-browser separately.

Core mental model under test: a SIGNAL = one entry (shared ts_in/px_in/side)
+ THREE ficha exits (F1/F2/F3, each its own ts_out/px_out/pnl/exit_reason).
Grouping must be derived from `signal_id`/`ficha` -- no hardcoded run/signal
ids anywhere in the source (req 8)."""
from __future__ import annotations

from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def _chart_js() -> str:
    return (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")


def _review_js() -> str:
    return (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")


# ---- req 8: generic, no hardcoded ids ----

def test_no_hardcoded_run_or_signal_ids_in_chart_or_review_js():
    for text in (_chart_js(), _review_js()):
        assert "mt5import-abc1043ef513" not in text
        assert "sig-20260111_200000" not in text


# ---- req 1: one entry marker + three exit markers per signal (dedupe) ----

def test_chart_js_build_markers_groups_by_signal_id():
    text = _chart_js()
    start = text.index("function buildMarkers")
    end = text.index("\n    function epochOf", start)
    body = text[start:end]
    assert "signal_id" in body


def test_chart_js_has_signal_grouping_helper():
    """A dedicated grouping helper (groupBySignal or similar) must exist so
    buildMarkers/redrawConnectors/selectTrade all derive from ONE shared
    signal model instead of re-deriving ad hoc groupings each of them."""
    text = _chart_js()
    assert "groupBySignal" in text or "signalsById" in text or "buildSignals" in text


# ---- req 2/3: connectors -- dim per-ficha segments, bright selected SIGNAL (3 fichas) ----

def test_chart_js_draw_selected_connector_handles_three_fichas():
    text = _chart_js()
    # drawSelectedConnector (or its replacement) must reference ficha data
    # for more than a single trade -- look for iteration over a fichas list
    # / signal group, not a single 2-point setData call.
    assert "fichas" in text or "signal.trades" in text or "group.trades" in text


def test_chart_js_connectors_are_per_ficha_series_not_one_whitespace_series():
    """Wave-2b rendering-regression fix (2026-07-10): the OLD design merged
    every connector into ONE ascending-time line series using whitespace
    breaks. Because a signal's 3 fichas share the SAME entry time, repeated
    entries got clamped to `last+1` (a fake off-bar time) -> a wavy zigzag
    line. The fix draws ONE 2-point series PER FICHA instead, so redraw
    iterates the signal grouping and calls a per-ficha connector drawer for
    each ficha (not a single shared whitespace-broken dataset builder)."""
    text = _chart_js()
    assert "buildAllConnectorData" not in text
    assert "drawSelectedConnector" not in text
    start = text.index("function redrawConnectors")
    end = text.index("\n    function addTradeMarkers", start)
    body = text[start:end]
    assert ("forEach" in body) or ("for (" in body) or ("map(" in body)
    # per-ficha connector series must be added to an array of series handles
    # (so clearConnectors can remove them all), not two singleton series refs.
    assert "connectorSeriesList" in text


def test_chart_js_connector_series_guarded_for_huge_runs():
    """GUARD: drawing a dim connector series per ficha for every non-selected
    signal is fine for V1's small imports (~69 trades / ~23 signals) but
    must be skipped above some trade-count threshold to protect huge runs
    from a series-per-ficha explosion (each lightweight-charts series has a
    real DOM/canvas cost)."""
    text = _chart_js()
    start = text.index("function redrawConnectors")
    end = text.index("\n    function addTradeMarkers", start)
    body = text[start:end]
    assert "allTrades.length" in body
    assert "300" in body


# ---- Wave-2b rendering regression fix (2026-07-10): bar-time snapping ----
# Root cause: trade event times (exits often at :40s) don't align to TF bar
# boundaries (M1 bars at :00s). lightweight-charts merges every series' time
# points into ONE shared time scale, so an off-bar time on ANY series injects
# a phantom column between real candles -> visible gaps. Fix: snap every
# trade-derived time to the TF's bar boundary before it reaches a series.

def test_chart_js_has_bar_time_snapping_helpers():
    text = _chart_js()
    assert "function secPerBar" in text
    assert "function barTimeOf" in text


def test_chart_js_build_markers_snaps_entry_and_exit_times():
    # 2026-07-13: snapping now flows through resolveBarTime, which wraps
    # barTimeOf AND resolves against the COMMITTED bar set in windowMode
    # (returns null for off-window times instead of injecting a phantom
    # column into the shared time scale).
    text = _chart_js()
    start = text.index("function buildMarkers")
    end = text.index("\n    function epochOf", start)
    body = text[start:end]
    assert "resolveBarTime(group.ts_in)" in body
    assert "resolveBarTime(trade.ts_out)" in body


def test_chart_js_find_signal_at_bar_time_uses_bar_time_of():
    # 2026-07-13: hover matching uses the SAME resolved bar times the
    # markers are drawn at (resolveBarTime), gated on signalFullyInWindow so
    # an undrawn off-window neighbor can never win the hover match.
    text = _chart_js()
    start = text.index("function findSignalAtBarTime")
    end = text.index("\n    function signalTooltipHtml", start)
    body = text[start:end]
    assert "resolveBarTime(group.ts_in)" in body
    assert "resolveBarTime(t.ts_out)" in body
    assert "signalFullyInWindow(group)" in body


def test_chart_js_connector_drawer_snaps_times_to_bar():
    """The per-ficha connector drawer must snap both endpoints to COMMITTED
    bars (resolveBarTime; null endpoint -> no series, never a clamped
    phantom time), and if entry/exit collapse onto the same bar it must bump
    forward to the NEXT COMMITTED bar (nextBarTime) -- not a synthetic +1s
    nor a blind +secPerBar() that could land inside a closed-market gap."""
    text = _chart_js()
    start = text.index("function drawFichaConnector")
    end = text.index("\n    function hexToRgba", start)
    body = text[start:end]
    assert "resolveBarTime(tIn)" in body
    assert "resolveBarTime(tOut)" in body
    assert "nextBarTime(tInBar)" in body


def test_chart_js_resolve_bar_time_helpers_present():
    """2026-07-13 root-cause fix: the windowMode time-scale hygiene helpers
    must exist -- barTimes set committed in applyBars, resolveBarTime /
    nextBarTime / signalFullyInWindow gating, and overlay-point clipping so
    NO series ever hands the shared time scale a non-candle time (phantom
    columns rendered as candle gaps and shifted the anchor zoom's logical
    indices -> selected trade off-center/off-screen)."""
    text = _chart_js()
    assert "let barTimes = new Set()" in text
    assert "function resolveBarTime(" in text
    assert "function nextBarTime(" in text
    assert "function signalFullyInWindow(" in text
    assert "function clipOverlayPoints(" in text
    # every series setter passes its points through the clip
    assert text.count("clipOverlayPoints(points)") >= 4


# ---- req 3: selection tracks a whole signal, not a single trade ----

def test_chart_js_tracks_selected_signal_id():
    text = _chart_js()
    assert "selectedSignalId" in text


def test_chart_js_build_markers_dims_non_selected_signals():
    """Wave-2b regression fix: non-selected signals must visibly dim (not
    just the selected one brighten) so the highlight is actually visible.
    buildMarkers must fade non-selected markers via hexToRgba and only use
    full color for the selected signal (or for everyone when nothing is
    selected)."""
    text = _chart_js()
    start = text.index("function buildMarkers")
    end = text.index("\n    function epochOf", start)
    body = text[start:end]
    # FIX 3 (non-selected 50% MORE transparent): dim marker alpha halved
    # 0.30 -> 0.15. Still fades non-selected markers, just more.
    assert "hexToRgba(colorHex, 0.15)" in body or "hexToRgba(colorHex,0.15)" in body


# ---- req 5: hover popup shows per-ficha mini-table ----

def test_chart_js_crosshair_handler_reports_ficha_details():
    """The crosshair handler delegates to a signal-tooltip builder (rather
    than inlining everything) -- check that whichever function renders the
    hover tooltip references ficha/exit_reason/pnl, and that the crosshair
    handler itself calls into signal detection."""
    text = _chart_js()
    start = text.index("subscribeCrosshairMove")
    end = text.index("\n    });", start)
    handler_body = text[start:end]
    assert "findSignalAtBarTime" in handler_body or "signalTooltipHtml" in handler_body
    assert "ficha" in text
    assert "exit_reason" in text
    assert ".pnl" in text


def test_chart_js_has_duration_humanizer():
    text = _chart_js()
    assert "humanizeDuration" in text or "formatDuration" in text


# ---- req 7: trade list groups the 3 fichas under each signal ----

def test_review_js_trade_rows_grouped_by_signal():
    text = _review_js()
    assert "signal_id" in text
    assert "groupBySignal" in text or "buildSignalRows" in text or "signalRows" in text


def test_review_js_ficha_row_rendering_present():
    text = _review_js()
    assert "ficha" in text


def test_review_js_selects_whole_signal_on_row_click_or_jk():
    """selectTradeAt / moveSelection must operate over SIGNALS, not raw
    trade rows, so j/k steps through the 23 signals in order (not the 69
    ficha rows)."""
    text = _review_js()
    assert "currentSignals" in text or "signals[" in text or "signalList" in text


# ---- Wave-3 Stage 2 (2026-07-10): TF-switch fidelity + selection glow +
# pointer tooltip. Source-assertion style per test_web_trade_grouping.py. ----

# ---- Task 2.1: setTF must re-anchor to the selected trade and rebuild
# markers/connectors for the new tf (not just reload the tail window). ----

def test_settf_reanchors_to_selected_trade():
    text = _chart_js()
    start = text.index("async function setTF")
    end = text.index("\n    // ---- live ticks", start)
    body = text[start:end]
    assert "selectedTradeId" in body
    assert "selectTrade" in body
    assert "buildMarkers" in body or "loadInitial" in body


# ---- Task 2.2: selected signal glow (bright markers/connectors) is
# unmistakable even when it's the only position on screen. ----

def test_selected_markers_use_glow():
    text = _chart_js()
    start = text.index("function buildMarkers")
    end = text.index("\n    function epochOf", start)
    body = text[start:end]
    assert "isSelected ? 2 : 1" in body
    assert "isSelected ? 1.6 : 1" in body
    # FIX 3: dim marker alpha halved 0.30 -> 0.15 (selected stays full color).
    assert "hexToRgba(colorHex, 0.15)" in body or "hexToRgba(colorHex,0.15)" in body

    start2 = text.index("function drawFichaConnector")
    end2 = text.index("\n    function hexToRgba", start2)
    conn_body = text[start2:end2]
    assert "bright ? 3" in conn_body or "bright ? hexToRgba(colorHex, 0.95)" in conn_body
    # FIX 3: dim connector alpha halved 0.22 -> 0.11.
    assert "0.11" in conn_body

    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    assert ".review-row-selected" in css


# ---- Task 2.3: hover/click tooltip must show the entry + all 3 ficha
# exits (time, price, exit_reason, signed net) + the position total. ----

def test_signal_tooltip_has_times_and_net():
    text = _chart_js()
    start = text.index("function signalTooltipHtml")
    end = text.index("\n    function escapeHtmlLite", start)
    body = text[start:end]
    assert "fmt.ts(tsIn)" in body
    assert "fmt.ts(" in body  # entry ts
    assert "exit_reason" in body
    assert "fmt.signed(pnl)" in body
    assert "chart-tooltip-signal-total" in body
    assert "fmt.signed(total)" in body
    # per-ficha EXIT timestamp must be shown (not just duration) -- t.ts_out
    assert "t.ts_out" in body
