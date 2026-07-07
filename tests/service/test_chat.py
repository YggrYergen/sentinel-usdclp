"""
P5 Task 5.1/5.2 — POST /chat builds its context SOLELY from
`render_ai_context(snapshot, cfg)` + MT5 positions (never literals), and the
endpoint answers grounded questions offline (no network, no API key).
"""
from __future__ import annotations

import dataclasses

from fastapi.testclient import TestClient

from sentinel_engine.config import load_instrument
from sentinel_engine.engine import Engine
from sentinel_engine.service.chat import ChatReply, answer_chat, build_chat_context
from tests.golden.capture_engine import ENGINE_WARMUP_TICKS
from tests.golden.fake_feed import FakeFeed


def _engine_snapshot(cfg):
    engine = Engine(cfg, FakeFeed())
    for _ in range(ENGINE_WARMUP_TICKS):
        engine._macro.update_tick(engine.feed)
    return engine.step()


# ── 5.1: context built solely from render_ai_context(snapshot, cfg) + positions ──

def test_chat_context_reflects_config_tf_weights_not_literal():
    cfg = load_instrument("usdclp")
    snap = _engine_snapshot(cfg)

    ctx = build_chat_context(snap, cfg, positions=[])

    tf = cfg.technical.tf_weights
    assert (
        f"M1={tf['M1']*100:.0f}%, M2={tf['M2']*100:.0f}%, "
        f"M5={tf['M5']*100:.0f}%, M15={tf['M15']*100:.0f}%"
    ) in ctx

    # Monkeypatch (via a config copy) — the rendered text must follow, proving
    # the numbers are sourced from config, not hardcoded in the chat layer.
    new_tech = dataclasses.replace(
        cfg.technical, tf_weights={"M1": 0.5, "M2": 0.3, "M5": 0.15, "M15": 0.05}
    )
    cfg2 = dataclasses.replace(cfg, technical=new_tech)
    ctx2 = build_chat_context(snap, cfg2, positions=[])

    assert "M1=50%, M2=30%, M5=15%, M15=5%" in ctx2
    assert "M1=35%, M2=35%, M5=20%, M15=10%" not in ctx2


def test_chat_context_reflects_config_composite_weights_not_literal():
    cfg = load_instrument("usdclp")
    snap = _engine_snapshot(cfg)

    w_tech = cfg.composite.weights["technical"]
    w_corr = cfg.composite.weights["correlation"]
    ctx = build_chat_context(snap, cfg, positions=[])
    assert f"Tech×{w_tech:.2f} + Corr×{w_corr:.2f}" in ctx
    assert f"[peso: {w_tech*100:.0f}%]" in ctx
    assert f"[peso: {w_corr*100:.0f}%]" in ctx

    # Mutate the config-derived composite weight carried on the snapshot —
    # same anti-literal contract `render_ai_context` itself proves.
    comps = dict(snap.components)
    comps["technical"] = {**comps["technical"], "weight": 0.6}
    comps["correlation"] = {**comps["correlation"], "weight": 0.4}
    snap2 = dataclasses.replace(snap, components=comps)

    ctx2 = build_chat_context(snap2, cfg, positions=[])
    assert "Tech×0.60 + Corr×0.40" in ctx2
    assert "[peso: 60%]" in ctx2
    assert "[peso: 40%]" in ctx2


def test_chat_context_includes_positions_when_present():
    cfg = load_instrument("usdclp")
    snap = _engine_snapshot(cfg)
    positions = [
        {"symbol": "USDCLP", "type": 0, "volume": 0.1, "price_open": 950.5, "profit": 12.3}
    ]

    ctx = build_chat_context(snap, cfg, positions)

    assert "POSICIONES ABIERTAS" in ctx
    assert "USDCLP" in ctx
    assert "12.3" in ctx


def test_chat_context_no_positions_is_explicit():
    cfg = load_instrument("usdclp")
    snap = _engine_snapshot(cfg)

    ctx = build_chat_context(snap, cfg, [])

    assert "Sin posiciones abiertas." in ctx


# ── answer_chat: grounded answer via injected stub client (no network) ──

def test_answer_chat_uses_stub_client_and_context_as_system_prompt():
    cfg = load_instrument("usdclp")
    snap = _engine_snapshot(cfg)

    captured = {}

    class StubClient:
        def chat(self, user_message, model_key, system_prompt, conversation, **kwargs):
            captured["system_prompt"] = system_prompt
            captured["user_message"] = user_message
            return {"content": "Score visible en el contexto.", "error": None}

    reply = answer_chat("cual es el score?", snap, cfg, [], client=StubClient())

    assert isinstance(reply, ChatReply)
    assert reply.error is None
    assert "Score visible" in reply.content
    assert captured["user_message"] == "cual es el score?"
    assert "SCORE COMPUESTO" in captured["system_prompt"]


# ── 5.2: POST /chat endpoint, offline (stub client + mock fallback) ──

def test_post_chat_endpoint_uses_injected_stub_client(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)

    captured = {}

    class StubClient:
        def chat(self, user_message, model_key, system_prompt, conversation, **kwargs):
            captured["system_prompt"] = system_prompt
            captured["user_message"] = user_message
            return {"content": "Respuesta grounded del asistente.", "error": None}

    app.state.chat_client = StubClient()

    with TestClient(app) as client:
        resp = client.post("/chat", json={"question": "cual es el score?"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is None
        assert "Respuesta grounded" in body["content"]

    assert captured["user_message"] == "cual es el score?"
    assert "SCORE COMPUESTO" in captured["system_prompt"]


def test_post_chat_endpoint_selects_instrument(app_factory):
    app = app_factory(instruments=("usdclp", "gold"), autostart_loop=False)

    captured = {}

    class StubClient:
        def chat(self, user_message, model_key, system_prompt, conversation, **kwargs):
            captured.setdefault("prompts", []).append(system_prompt)
            return {"content": "ok", "error": None}

    app.state.chat_client = StubClient()

    with TestClient(app) as client:
        resp = client.post(
            "/chat", json={"question": "que pasa con usdclp?", "instrument": "usdclp"}
        )
        assert resp.status_code == 200
        resp2 = client.post(
            "/chat", json={"question": "que pasa con gold?", "instrument": "gold"}
        )
        assert resp2.status_code == 200

    # Different instruments carry different snapshots/config -> different
    # rendered context (proves /chat actually resolved per-instrument state,
    # not a single cached context).
    usdclp_prompt, gold_prompt = captured["prompts"]
    assert usdclp_prompt != gold_prompt


def test_post_chat_endpoint_unknown_instrument_404(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)

    with TestClient(app) as client:
        resp = client.post(
            "/chat", json={"question": "hola", "instrument": "does-not-exist"}
        )
        assert resp.status_code == 404


def test_post_chat_endpoint_mock_mode_without_api_key_or_network(app_factory, monkeypatch):
    """No stub injected, no ANTHROPIC_API_KEY: falls back to ai_chat's
    deterministic `_mock_response` — proves /chat answers offline."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("sentinel.ai_chat.time.sleep", lambda s: None)

    app = app_factory(instruments=("usdclp",), autostart_loop=False)

    with TestClient(app) as client:
        resp = client.post("/chat", json={"question": "resume el mercado"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is None
        assert "Modo Demo" in body["content"]
        assert "resume el mercado" in body["content"]
