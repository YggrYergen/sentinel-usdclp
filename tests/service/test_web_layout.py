"""M1.1 — navbar extension (charts/review/runs/positions) + section loader
+ cyberpunk tokens. Extends the existing 3-band layout (D.1); must not
regress the ORIGINAL 5 nav items/sections or #left-column (D.9 gate)."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

NEW_SECTIONS = ("charts", "review", "runs", "positions")
ORIGINAL_SECTIONS = ("chat", "lab", "regime", "news", "study")


def test_index_served():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert "<html" in html.lower()


def test_new_nav_buttons_present():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    for section in NEW_SECTIONS:
        assert f'data-section="{section}"' in html, f"missing nav-btn for {section}"
        assert 'class="nav-btn"' in html


def test_new_sections_present():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    for section in NEW_SECTIONS:
        assert f'id="section-{section}"' in html, f"missing section-{section}"


def test_original_sections_still_present():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    for section in ORIGINAL_SECTIONS:
        assert f'id="section-{section}"' in html
        assert f'data-section="{section}"' in html


def test_left_column_untouched():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="left-column"' in html
    for instrument in ("usdclp", "nasdaq", "gold"):
        assert f'id="panel-{instrument}"' in html
        assert 'class="v2-mount"' in html


def test_lib_and_section_scripts_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        for path in (
            "/lib/badge.js",
            "/lib/toast.js",
            "/lib/fmt.js",
            "/sections/charts.js",
            "/sections/review.js",
            "/sections/runs.js",
            "/sections/positions.js",
        ):
            resp = client.get(path)
            assert resp.status_code == 200, path


def test_style_css_design_tokens_not_swallowed_by_comment():
    """Regression: a stray `*/` inside a comment (e.g. a glob like `--fx-*/`)
    closes the CSS comment early, turning the whole `:root { --bg-2: ...; }`
    design-token block into an invalid rule the browser silently drops — which
    strips ALL styling from the right-pane sections. Guard by (a) balanced
    comment delimiters and (b) the key tokens surviving comment-stripping as
    real declarations."""
    import re

    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    assert css.count("/*") == css.count("*/"), "unbalanced CSS comment delimiters (a stray '*/' in a comment?)"

    # strip comments the way a CSS parser does (non-greedy, first '*/' wins)
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    for token in ("--bg-2:", "--border:", "--accent-celeste:", "--sp-3:", "--text-0:", "--font-mono:"):
        assert token in stripped, f"design token {token!r} missing from real CSS (swallowed by a comment?)"


def test_review_section_height_capped():
    """Regression (NB1): the REVIEW section mounts `.review-section` (a grid with
    `height:100%`) into `#section-review`. If `#section-review` itself has no
    definite height, that `height:100%` resolves against an auto-height parent and
    collapses — the chart+control-bar column then grows with the trade list and the
    posnav/playback bar gets pushed far below the viewport (measured posnav top
    ~1995px in a 900px window). Guard that the section is height-capped so the
    percentage-height chain resolves."""
    import re

    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    m = re.search(r"#section-review\s*\{([^}]*)\}", stripped)
    assert m, "no #section-review rule — REVIEW section is not height-capped (NB1)"
    body = m.group(1)
    assert "height" in body and "100%" in body, (
        "#section-review must cap height (e.g. height:100%) so .review-section's "
        "height:100% resolves (NB1)"
    )


def test_no_cdn_in_new_assets():
    for rel in (
        "index.html",
        "app.js",
        "style.css",
        "lib/badge.js",
        "lib/toast.js",
        "lib/fmt.js",
        "sections/charts.js",
        "sections/review.js",
        "sections/runs.js",
        "sections/positions.js",
    ):
        text = (WEB_DIR / rel).read_text(encoding="utf-8")
        assert "cdn.jsdelivr" not in text.lower()
        assert "cdnjs." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text.lower()


def test_section_scripts_register_sentinel_namespace():
    for name in NEW_SECTIONS:
        text = (WEB_DIR / "sections" / f"{name}.js").read_text(encoding="utf-8")
        assert "window.SENTINEL" in text
        assert f'sections.{name} = {{ render, teardown }}' in text or "render" in text
        assert "teardown" in text


def test_appjs_calls_render_and_teardown_on_section_toggle():
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.sections" in app_js
    assert ".render(" in app_js
    assert ".teardown(" in app_js


def test_app_js_persists_and_restores_section():
    """Task 1.1 (Wave-3 Stage 1): the active navbar section must survive a
    refresh (F5). app.js persists the clicked section to localStorage and
    exposes a restoreSection() helper that replays the click on boot."""
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert 'localStorage.setItem("sentinel.ui.section"' in app_js
    assert 'localStorage.getItem("sentinel.ui.section"' in app_js
    assert "restoreSection" in app_js


def test_tokens_present_in_style_css():
    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    for token in (
        "--bg-0:#0a0e14", "--accent-celeste:#00bfff", "--accent-green:#26a69a",
        "--accent-red:#ef5350", "--accent-amber:#ffb020", "--long:#26a69a",
        "--short:#ef5350",
    ):
        assert token in css, f"missing token {token}"
