"""A6b — windowed rendering (virtualization) for the REVIEW section's long
lists (run selector groups). Static-serve + source assertions only (same
pattern as test_web_review.py / test_web_layout.py); NO browser automation.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def test_lib_vlist_js_served(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/lib/vlist.js")
        assert resp.status_code == 200


def test_vlist_js_exports_create_vlist():
    text = (WEB_DIR / "lib" / "vlist.js").read_text(encoding="utf-8")
    assert "window.SENTINEL" in text
    assert "vlist" in text
    assert "function createVList(" in text
    assert "createVList" in text


def test_vlist_js_windowed_rendering_math():
    """Windowed rendering: total scroll height = items.length * itemHeight,
    with only the viewport +-10 rows materialized (not all N rows)."""
    text = (WEB_DIR / "lib" / "vlist.js").read_text(encoding="utf-8")
    assert "itemHeight" in text
    assert "scrollTop" in text
    assert "OVERSCAN" in text
    assert "10" in text
    assert "items.length" in text


def test_vlist_js_render_and_items_options():
    text = (WEB_DIR / "lib" / "vlist.js").read_text(encoding="utf-8")
    assert "opts.render" in text
    assert "opts.items" in text
    assert "setItems" in text


def test_vlist_js_scroll_listener_present():
    text = (WEB_DIR / "lib" / "vlist.js").read_text(encoding="utf-8")
    assert 'addEventListener("scroll"' in text


def test_vlist_js_selection_preservation_logic():
    """Selection must survive rows leaving/re-entering the viewport across
    re-renders -- keyed by a stable item id (itemKey), not DOM node identity."""
    text = (WEB_DIR / "lib" / "vlist.js").read_text(encoding="utf-8")
    assert "setSelected" in text
    assert "getSelected" in text
    assert "itemKey" in text
    assert "selected" in text


def test_no_cdn_in_vlist_js():
    text = (WEB_DIR / "lib" / "vlist.js").read_text(encoding="utf-8")
    assert "cdn.jsdelivr" not in text.lower()
    assert "cdnjs." not in text.lower()
    assert "unpkg.com" not in text
    assert "jsdelivr" not in text.lower()


def test_review_js_imports_and_uses_vlist():
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.vlist" in text or "SENTINEL.vlist" in text
    assert "createVList" in text


def test_review_js_still_uses_vtable_for_trade_list():
    """Regression guard (test_web_review.py::test_review_js_uses_vtable):
    A6b must not remove the existing vtable-backed trade/signal list."""
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "window.SENTINEL.vtable" in text or "SENTINEL.vtable" in text
    assert "createVTable" in text


def test_review_js_vlist_selection_survives_rerender():
    """The run-selector's active/selected run must be re-applied via
    setSelected() so it survives scrolling a row out of and back into the
    viewport (re-render destroys/recreates the row DOM node)."""
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "setSelected(" in text


def test_review_js_keyboard_and_run_search_still_present():
    """Regression guard: j/k trade nav and the run search input must still
    work after virtualizing the run selector list."""
    text = (WEB_DIR / "sections" / "review.js").read_text(encoding="utf-8")
    assert "keydown" in text
    assert "review-run-search" in text
