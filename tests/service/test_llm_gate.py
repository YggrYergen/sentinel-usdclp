"""tests/service/test_llm_gate.py — Wave A / Task A8 (CT-6).

Covers the LLM model catalog + gate (passcode) + usage meter added to
`sentinel_engine/service/routers/chat.py`:

  GET  /api/llm/models  -> CT-6 shape derived from models.yaml
  POST /api/llm/unlock  -> {"ok": bool}, compares against SENTINEL_OPUS_GATE
  GET  /api/llm/usage   -> session token/cost counters

Uses the same `app_factory` + `TestClient` pattern as `tests/service/
test_chat.py`. `TestClient` persists cookies across requests on the same
instance, which is how the session-scoped gate flag and usage counters are
exercised here (see chat.py's cookie-keyed module-level session store).
"""
from __future__ import annotations

import os

from fastapi.testclient import TestClient


class _StubClient:
    """Deterministic stub matching `SentinelAI.chat`'s dict contract, with a
    non-zero usage block so /api/llm/usage has something to accumulate."""

    def __init__(self, content: str = "ok"):
        self.content = content
        self.calls = 0

    def chat(self, user_message, model_key, system_prompt, conversation, **kwargs):
        self.calls += 1
        return {
            "content": self.content,
            "error": None,
            "input_tokens": 100,
            "output_tokens": 50,
            "model": model_key,
        }


def test_get_llm_models_matches_ct6_shape(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)

    with TestClient(app) as client:
        resp = client.get("/api/llm/models")
        assert resp.status_code == 200
        body = resp.json()

    by_id = {m["id"]: m for m in body}
    assert by_id["claude-opus-4-8"]["gated"] is True
    assert by_id["claude-opus-4-8"]["label"] == "Opus 4.8"

    assert by_id["claude-sonnet-5"]["gated"] is False
    assert by_id["claude-sonnet-5"]["default"] is True
    assert by_id["claude-sonnet-5"]["label"] == "Sonnet 5"

    assert by_id["claude-haiku-4-5"]["gated"] is False
    assert by_id["claude-haiku-4-5"]["label"] == "Haiku 4.5"
    # haiku carries no "default" key at all per CT-6 (not merely False/absent-falsy)
    assert "default" not in by_id["claude-haiku-4-5"]


def test_gated_model_locked_then_unlock_flow(app_factory, monkeypatch):
    monkeypatch.setenv("SENTINEL_OPUS_GATE", "letmein")
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    app.state.chat_client = _StubClient()

    with TestClient(app) as client:
        # 1. Gated model, session not unlocked -> 403 gated_model_locked
        resp = client.post(
            "/chat", json={"question": "hola", "model": "claude-opus-4-8"}
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "gated_model_locked"

        # 2. Wrong passcode -> {"ok": false}, still locked
        resp = client.post("/api/llm/unlock", json={"code": "wrong"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": False}

        resp = client.post(
            "/chat", json={"question": "hola de nuevo", "model": "claude-opus-4-8"}
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "gated_model_locked"

        # 3. Correct passcode -> {"ok": true}, session now unlocked
        resp = client.post("/api/llm/unlock", json={"code": "letmein"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        # 4. Gated model now runs (no 403)
        resp = client.post(
            "/chat", json={"question": "ahora si", "model": "claude-opus-4-8"}
        )
        assert resp.status_code == 200
        assert resp.json()["error"] is None


def test_gated_model_locked_uses_default_passcode_when_env_unset(app_factory, monkeypatch):
    monkeypatch.delenv("SENTINEL_OPUS_GATE", raising=False)
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    app.state.chat_client = _StubClient()

    with TestClient(app) as client:
        resp = client.post("/api/llm/unlock", json={"code": "abc123"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        resp = client.post(
            "/chat", json={"question": "hola", "model": "claude-opus-4-8"}
        )
        assert resp.status_code == 200


def test_non_gated_model_never_blocked(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    app.state.chat_client = _StubClient()

    with TestClient(app) as client:
        resp = client.post(
            "/chat", json={"question": "hola", "model": "claude-sonnet-5"}
        )
        assert resp.status_code == 200
        assert resp.json()["error"] is None


def test_usage_accumulates_after_chat_messages(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    app.state.chat_client = _StubClient()

    with TestClient(app) as client:
        # Baseline: no messages sent yet.
        resp = client.get("/api/llm/usage")
        assert resp.status_code == 200
        baseline = resp.json()
        assert baseline["session_tokens_in"] == 0
        assert baseline["session_tokens_out"] == 0
        assert baseline["est_usd"] == 0

        client.post("/chat", json={"question": "uno", "model": "claude-sonnet-5"})
        client.post("/chat", json={"question": "dos", "model": "claude-sonnet-5"})

        resp = client.get("/api/llm/usage")
        assert resp.status_code == 200
        body = resp.json()

    # Stub reports 100 in / 50 out per call; two calls.
    assert body["session_tokens_in"] == 200
    assert body["session_tokens_out"] == 100
    assert body["est_usd"] > 0
