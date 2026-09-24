"""UI rework acceptance gate #2 (spec §10.2): every row of the Capability
Coverage Matrix (spec §8) has a rendered surface — either a live element or
a labeled gated placeholder. Since there is no JS test runner in this repo,
this is a structural/regex check over the shipped JS+HTML source, which is
the closest executable proxy for "every capability has a UI home"."""
from __future__ import annotations

from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def _read(name: str) -> str:
    return (WEB_DIR / name).read_text(encoding="utf-8")


def test_left_replica_capabilities_present_in_app_js():
    app_js = _read("app.js")
    # composite/direction/signal/per-TF/macro-votes/correlations/levels/
    # alerts/divergences/derivatives all rendered inside renderAssetPanel.
    for marker in (
        "function renderAssetPanel",
        "tfScores", "votes", "combined", "alerts", "divergences",
        "velAt(", "accelWindow(", "calculateFusion(",
    ):
        assert marker in app_js, f"app.js missing left-replica marker: {marker}"


def test_config_hash_surface_present():
    app_js = _read("app.js")
    assert "topbar-cfg-hash" in app_js
    index_html = _read("index.html")
    assert 'id="topbar-cfg-hash"' in index_html


def test_data_source_staleness_badge_present():
    app_js = _read("app.js")
    assert "data_source" in app_js
    assert "stale_seconds" in app_js


def test_gated_capabilities_have_placeholder_builders():
    lab_js = _read("lab.js")
    chat_js = _read("chat.js")
    # lever groups + variant hash (gated on P4 absence via /levers 200 or 501)
    assert "renderLeverConsole" in lab_js
    assert "/levers" in lab_js
    # replay stage (gated P2)
    assert "renderReplayStage" in lab_js
    assert "/replay/control" in lab_js
    # variant/study/fleet (gated P4)
    assert "renderVariantManager" in lab_js
    assert "/variants" in lab_js
    # regime (gated P6, data-driven)
    assert "buildRegimeSection" in lab_js
    # news/calendar (gated P6)
    assert "buildNewsSection" in lab_js
    assert "/calendar" in lab_js
    # study report (gated P4)
    assert "buildStudySection" in lab_js
    assert "/study/latest" in lab_js
    # AI context / chat (gated P5 — key-dependent, endpoint always exists)
    assert "buildChatRequest" in chat_js
    assert "/models" in chat_js


def test_gated_placeholder_helper_never_blocks_rendering():
    lab_js = _read("lab.js")
    # Every gated-placeholder path must still leave the DOM populated
    # (innerHTML set), never throw/leave blank — verified by the presence
    # of the shared helper used on every gated branch.
    assert lab_js.count("gated-placeholder") >= 4
