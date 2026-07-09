"""M2.6 — variable-speed forward-walk playback (lib/chart.js engine +
CHARTS/REVIEW UI bars) + folded-in REVIEW TF-switcher fix. Static-serve +
source assertions only (pattern from test_frontend.py / test_web_charts.py
/ test_web_review.py); NO browser automation."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_lib_chart_charts_review_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        for path in ("/lib/chart.js", "/sections/charts.js", "/sections/review.js"):
            resp = client.get(path)
            assert resp.status_code == 200, path


def test_chart_js_exposes_playback_controls():
    text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    assert "startPlayback" in text
    assert "pausePlayback" in text
    assert "seekPlayback" in text
    assert "stopPlayback" in text


def test_chart_js_playback_speeds_and_single_timer():
    text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    for speed in ("1", "5", "20", "60", "MAX"):
        assert speed in text
    # one timer, cleared on pause/stop/teardown
    assert "setInterval" in text
    assert "clearInterval" in text


def test_chart_js_playback_mutually_exclusive_with_ticks():
    text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    assert "function enableTicks" in text
    assert "function startPlayback" in text
    # enableTicks stops playback; startPlayback disables ticks.
    enable_idx = text.index("function enableTicks")
    enable_body = text[enable_idx:enable_idx + 400]
    assert "stopPlayback" in enable_body
    start_idx = text.index("function startPlayback")
    start_body = text[start_idx:start_idx + 400]
    assert "disableTicks" in start_body


def test_chart_js_markers_gated_by_playback_cursor():
    text = (WEB_DIR / "lib" / "chart.js").read_text(encoding="utf-8")
    assert "playbackCursor" in text
    # entry gated by ts_in <= cursor, exit/connector gated by ts_out <= cursor
    assert "buildMarkers" in text
    assert "redrawConnectors" in text


def test_charts_js_references_playback_controls_and_speeds(app_factory):
    text = (WEB_DIR / "sections" / "charts.js").read_text(encoding="utf-8")
    assert "startPlayback" in text
    assert "pausePlayback" in text
    for speed in ("1", "5", "20", "60", "MAX"):
        assert speed in text
    assert "playback-bar" in text or "playback-play-btn" in text


def test_review_js_references_playback_controls_and_speeds():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "startPlayback" in text
    assert "pausePlayback" in text
    assert "seekPlayback" in text
    for speed in ("1", "5", "20", "60", "MAX"):
        assert speed in text
    assert "playback-bar" in text or "playback-play-btn" in text


def test_review_js_references_tf_buttons_and_set_tf():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "review-tf-btn" in text
    assert "setTF" in text
    for tf in ("M1", "M2", "M5", "M10", "M15"):
        assert tf in text


def test_review_js_tf_switch_reanchors_selected_trade():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    # setTF(tf) then re-selectTrade(currentTrade) so the anchor trade stays
    # centered across TFs (spec §D.4/§D.7-REVIEW).
    assert "renderTfButtons" in text
    assert "selectTrade" in text
    assert "anchorTrade" in text


def test_escape_stops_playback_in_charts_and_review():
    charts_text = (WEB_DIR / "sections" / "charts.js").read_text(encoding="utf-8")
    review_text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    for text in (charts_text, review_text):
        assert "Escape" in text
        assert "stopPlayback" in text


def test_playback_css_present():
    text = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    assert ".playback-bar" in text
    assert ".playback-play-btn" in text
    assert ".playback-speed-select" in text
    assert ".playback-scrub" in text
    assert ".review-tf-btn" in text


def test_no_cdn_in_playback_assets():
    for rel in ("lib/chart.js", "sections/charts.js", "sections/review.js"):
        text = (WEB_DIR / rel).read_text(encoding="utf-8")
        assert "cdn.jsdelivr" not in text.lower()
        assert "cdnjs." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text.lower()
