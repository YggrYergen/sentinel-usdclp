"""tests/service/test_web_review_overlays.py — TDD for the REVIEW Trade View
EMA/SAR indicator overlays (spec
docs/superpowers/specs/2026-07-09-trade-view-indicator-overlays-design.md).

Static-serve + source assertions only (pattern from test_web_charts.py /
test_web_layout.py) — no browser automation here (that's covered by the
Playwright browser-verify step of this task, run separately)."""
from __future__ import annotations

from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_chart_js_exposes_add_sar_dots():
    text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    assert "addSarDots" in text
    # returned in the public API object alongside addOverlay/removeOverlay
    assert "addSarDots," in text or "addSarDots:" in text


def test_review_js_fetches_indicators_endpoint():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "/indicators" in text


def test_review_js_has_overlay_chip_group_reusing_charts_css_classes():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "charts-overlay-chip" in text
    assert "charts-overlay-chips" in text


def test_review_js_default_tf_not_hardcoded_m1():
    """Regression: `appState.tf || "M1"` forces M1 even for an M2-native
    run, producing the empty state "Sin barras para XAUUSD M1". The default
    tf must come from the run's own record (native tf), so a literal
    `appState.tf || "M1"` must no longer appear."""
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert 'appState.tf || "M1"' not in text


def test_review_js_calls_add_sar_dots_for_sar_indicator():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "addSarDots" in text


def test_chart_js_set_overlay_series_emits_whitespace_points_for_null_values():
    """Defect A: EMA/SuperTrend warmup values are `null` for the leading N
    bars. lightweight-charts line series reject `{time, value: null}` --
    `setData` throws and the whole overlay silently never renders. The fix
    must map null/undefined to a WHITESPACE point (`{time}`, no `value` key)
    so the regex here would fail against the old `value: val` mapping (which
    always includes the key, even when val is null)."""
    text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    # locate the setOverlaySeries function body specifically (not
    # setSarDotsSeries, which already filters nulls and is left untouched).
    start = text.index("function setOverlaySeries")
    end = text.index("function addOverlay", start)
    body = text[start:end]
    assert "val === null" in body or "val == null" in body
    # the null/undefined branch must produce a bare {time} point (no
    # `value` key at all) -- not `{time, value: null}`, which is invalid
    # whitespace data and throws in setData().
    assert "{ time: tsSec(ts) }" in body


def test_chart_js_exposes_window_from_to_getters():
    """Frontend half of defect B: review.js needs the chart's CURRENT
    candle window (winFrom/winTo) to pass to /indicators?from&to so the
    overlay range stays a subset of the candle range. Exposed as getters
    on the object chart.js returns from create()."""
    text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    assert "get windowFrom()" in text
    assert "get windowTo()" in text


def test_review_js_supertrend_chip_color_mapped():
    """Requirement 6: once defect A is fixed, SuperTrend's line will
    actually render -- renderOverlayChips already lists every indicator
    generically, but OVERLAY_COLORS should map 'supertrend' too so its chip
    isn't left on the default fallback color indistinguishable from ema."""
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "supertrend" in text


def test_chart_js_select_trade_returns_set_window_promise():
    """Defect B (frontend half): selectTrade internally calls the async
    setWindow (which fetches new bars and moves winFrom/winTo) but did not
    return that promise -- callers awaiting `selectTrade(...)` resolved
    before the window actually updated, so a `refreshIndicators()` right
    after would fetch overlays for the STALE window. selectTrade must
    `return setWindow(from, to)` so callers can await window-settle."""
    text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    start = text.index("function selectTrade(trade)")
    end = text.index("\n    }", start)
    body = text[start:end]
    assert "return setWindow(" in body


def test_review_js_refresh_indicators_passes_chart_window():
    """Defect B (frontend half): fetchIndicators/refreshIndicators must
    pass the chart's CURRENT window (chartInst.windowFrom/windowTo) as
    from/to query params so /indicators is bounded to the same range as
    the loaded candles (never wider) -- the whole point of the backend
    from/to support added for defect B."""
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "windowFrom" in text
    assert "windowTo" in text


def test_review_js_refreshes_indicators_after_select_trade_resolves():
    """refreshIndicators() must run AFTER selectTrade's returned promise
    resolves (window settled), not fire-and-forget alongside it -- both
    the initial selectTradeAt(0) path and the TF-switch path must await
    selectTrade before calling refreshIndicators so overlays always match
    the trade's settled window."""
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "refreshIndicators" in text
    patterns = [
        "await chartInst.selectTrade",
        "chartInst.selectTrade(trade).then",
        "chartInst.selectTrade(anchorTrade).then",
        "Promise.resolve(chartInst.selectTrade(trade)).then(refreshIndicators)",
        "Promise.resolve(settled).then(refreshIndicators)",
    ]
    assert any(p in text for p in patterns)
