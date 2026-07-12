"""tests/service/test_web_chat.py — Wave A / Task A9 (CT-6 frontend).

Serve-and-assert (substring) tests over the served chat section JS
(`web/chat.js`, served at `/chat.js` per index.html's `<script src="/chat.js">`
— there is no `web/sections/chat.js`; `chat.js` at the web root IS the chat
section's script, wired via the `sentinel:section` event / DOMContentLoaded
like the other section modules). Mirrors `tests/service/test_web_layout.py`'s
pattern: TestClient serves the static file, assert substrings — no browser.

Covers task A9: model dropdown (GET /api/llm/models) + gated-model unlock
flow (POST /api/llm/unlock, 403 gated_model_locked handling, shake-on-fail)
+ usage meter (GET /api/llm/usage).
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def _served_chat_js(app_factory) -> str:
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        resp = client.get("/chat.js")
        assert resp.status_code == 200
        return resp.text


def test_chat_js_served(app_factory):
    text = _served_chat_js(app_factory)
    assert "SENTINEL" in text


def test_chat_js_references_llm_endpoints(app_factory):
    text = _served_chat_js(app_factory)
    assert "/api/llm/models" in text
    assert "/api/llm/unlock" in text
    assert "/api/llm/usage" in text


def test_chat_js_dropdown_populated_from_models_and_marks_default():
    text = (WEB_DIR / "chat.js").read_text(encoding="utf-8")
    # dropdown population logic: iterate models catalog, build <option>s
    assert "llmModelsCatalog" in text or "llmModels" in text
    assert "createElement(\"option\")" in text
    assert "m.default" in text or "model.default" in text
    assert ".selected = true" in text


def test_chat_js_gated_unlock_flow_and_shake_on_failure():
    text = (WEB_DIR / "chat.js").read_text(encoding="utf-8")
    # gated selection -> inline passcode prompt
    assert "gated" in text
    assert "unlock" in text.lower()
    # 403 gated_model_locked handling (both from direct gated-select AND from
    # a /chat 403 response)
    assert "gated_model_locked" in text
    assert "403" in text
    # shake animation class applied on wrong-passcode ({ok:false})
    assert "shake" in text.lower()


def test_chat_js_usage_meter_renders_tokens_and_cost():
    text = (WEB_DIR / "chat.js").read_text(encoding="utf-8")
    assert "session_tokens_in" in text
    assert "session_tokens_out" in text
    assert "est_usd" in text


def test_chat_js_never_hardcodes_passcode(app_factory):
    text = _served_chat_js(app_factory)
    # the only server-known default passcode (see routers/chat.py) must never
    # leak into the client JS.
    assert "abc123" not in text


def test_chat_js_fetch_uses_same_origin_credentials():
    text = (WEB_DIR / "chat.js").read_text(encoding="utf-8")
    assert "credentials" in text
    assert "same-origin" in text


def test_no_cdn_in_chat_js():
    text = (WEB_DIR / "chat.js").read_text(encoding="utf-8")
    assert "cdn.jsdelivr" not in text.lower()
    assert "cdnjs." not in text.lower()
    assert "unpkg.com" not in text
    assert "jsdelivr" not in text.lower()


def test_style_css_has_shake_keyframes_for_unlock_error():
    import re

    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    assert "@keyframes" in stripped and "shake" in stripped.lower()
