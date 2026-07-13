"""
P5 Task 5.1/5.2 — POST /chat builds its context SOLELY from
`render_ai_context(snapshot, cfg)` + MT5 positions (never literals), and the
endpoint answers grounded questions offline (no network, no API key).

Task C4b (additive, below the P5 tests) covers `POST
/api/ai/analyze_position` — SSE stream (CT-9 events `ai_text`/`ai_done`/
`ai_error`), CT-6 gate enforcement, and unknown-trade_id handling. Uses a
fake Anthropic-shaped client (`.messages.create(**kwargs) -> FakeMessage`)
injected as `app.state.chat_client` — no network, mirrors the fakes in
`tests/ai/test_loop.py`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from sentinel_engine.config import load_instrument
from sentinel_engine.engine import Engine
from sentinel_engine.lake import store
from sentinel_engine.research.registry2 import ResearchRegistry
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


# ── C4b: POST /api/ai/analyze_position (SSE, CT-9) ──

TS_IN = pd.Timestamp("2026-07-10T13:22:00Z")
TS_OUT = pd.Timestamp("2026-07-10T13:41:00Z")


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeMessage:
    content: list
    stop_reason: str


@dataclass
class _FakeMessagesResource:
    responses: list = field(default_factory=list)
    calls: list = field(default_factory=list)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        idx = len(self.calls) - 1
        if idx < len(self.responses):
            return self.responses[idx]
        return self.responses[-1]


@dataclass
class _FakeAnthropicClient:
    responses: list

    def __post_init__(self):
        self.messages = _FakeMessagesResource(responses=self.responses)


def _seed_trade_and_lake(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / "research.db"
    lake_root = tmp_path / "lake"

    reg = ResearchRegistry(db_path)
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "sl_tp")
    run_id = reg.insert_run({
        "run_id": "RUN001",
        "variant_id": vid,
        "engine": "sentinel-sim",
        "fidelity": "research",
        "periodo_desde": "2026-07-01",
        "periodo_hasta": "2026-07-11",
    })
    reg.insert_trades(run_id, [{
        "trade_id": "T00001",
        "run_id": run_id,
        "origin": "strategy",
        "ts_in": TS_IN.isoformat(),
        "ts_out": TS_OUT.isoformat(),
        "px_in": 2415.30,
        "px_out": 2418.75,
        "side": "LONG",
        "volume": 0.50,
        "sl": 2413.80,
        "tp": 2420.00,
        "exit_reason": "tp_hit",
        "exit_reason_source": "broker",
        "pnl": 172.50,
        "mae": -4.2,
        "mfe": 34.5,
    }])

    start = TS_IN - pd.Timedelta(minutes=5 * 250)
    idx = pd.date_range(start, periods=300, freq="5min", tz="UTC")
    base = 2410.0
    df = pd.DataFrame({
        "open": [base + i * 0.10 for i in range(300)],
        "high": [base + i * 0.10 + 0.30 for i in range(300)],
        "low": [base + i * 0.10 - 0.20 for i in range(300)],
        "close": [base + i * 0.10 + 0.05 for i in range(300)],
        "volume": [100.0 + i for i in range(300)],
    }, index=idx)
    df.index.name = "time"
    store.write_bars(lake_root, "XAUUSD", 5, df)

    return db_path, lake_root


def _parse_sse_events(text: str) -> list[tuple[str, str]]:
    """Parse raw SSE body text into a list of (event_name, data_json_str),
    skipping `retry:` lines and heartbeat comments (`: hb`)."""
    events = []
    event_name = None
    for block in text.split("\n\n"):
        block = block.strip("\n")
        if not block or block.startswith(":") or block.startswith("retry:"):
            continue
        event_name = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_name = line[len("event: "):]
            elif line.startswith("data: "):
                data = line[len("data: "):]
        if event_name is not None and data is not None:
            events.append((event_name, data))
    return events


def test_analyze_position_happy_path_sse_sequence(app_factory, tmp_path):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    db_path, lake_root = _seed_trade_and_lake(tmp_path)
    app.state.registry = ResearchRegistry(db_path)
    app.state.lake_root = lake_root

    responses = [
        _FakeMessage(content=[_FakeTextBlock(text="The trade hit TP cleanly.")], stop_reason="end_turn"),
    ]
    app.state.chat_client = _FakeAnthropicClient(responses=responses)

    with TestClient(app) as client:
        with client.stream(
            "POST", "/api/ai/analyze_position", json={"trade_id": "T00001"}
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            body = "".join(resp.iter_text())

    events = _parse_sse_events(body)
    names = [e[0] for e in events]
    assert names == ["ai_text", "ai_done"]
    assert "TP cleanly" in events[0][1]
    assert "TP cleanly" in events[1][1]

    # Model actually received the dossier XML + question, STABLE-FIRST
    # ordering (fixed preamble -> dossier -> question last, per system
    # prompt construction; the question itself lives in `messages`, not
    # appended after the dossier inside `system`).
    call = app.state.chat_client.messages.calls[0]
    assert "<documents>" in call["system"]
    assert call["system"].index("You are SENTINEL") < call["system"].index("<documents>")
    assert "T00001" in call["messages"][0]["content"]


def test_analyze_position_unknown_trade_id_emits_ai_error(app_factory, tmp_path):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    db_path, lake_root = _seed_trade_and_lake(tmp_path)
    app.state.registry = ResearchRegistry(db_path)
    app.state.lake_root = lake_root
    app.state.chat_client = _FakeAnthropicClient(responses=[])

    with TestClient(app) as client:
        with client.stream(
            "POST", "/api/ai/analyze_position", json={"trade_id": "DOES-NOT-EXIST"}
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())

    events = _parse_sse_events(body)
    assert [e[0] for e in events] == ["ai_error"]
    assert "DOES-NOT-EXIST" in events[0][1]


def test_analyze_position_gated_model_without_unlock_returns_403_before_any_call(
    app_factory, tmp_path, monkeypatch
):
    monkeypatch.setenv("SENTINEL_OPUS_GATE", "letmein")
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    db_path, lake_root = _seed_trade_and_lake(tmp_path)
    app.state.registry = ResearchRegistry(db_path)
    app.state.lake_root = lake_root

    fake_client = _FakeAnthropicClient(responses=[])
    app.state.chat_client = fake_client

    with TestClient(app) as client:
        resp = client.post(
            "/api/ai/analyze_position",
            json={"trade_id": "T00001", "model": "claude-opus-4-8"},
        )
        assert resp.status_code == 403
        assert resp.json() == {"error": "gated_model_locked"}

    # No API call was made -- gate checked BEFORE dossier build / API call.
    assert fake_client.messages.calls == []


# ── C7a: POST /api/ai/review_strategy (SSE, CT-9) ──

def _seed_strategy(db_path: Path) -> None:
    reg = ResearchRegistry(db_path)
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "sl_tp")
    run_id = reg.insert_run({
        "run_id": "RUN001",
        "variant_id": vid,
        "engine": "sentinel-sim",
        "fidelity": "research",
        "periodo_desde": "2026-07-01",
        "periodo_hasta": "2026-07-11",
    })
    reg.insert_trades(run_id, [{
        "trade_id": "T00001",
        "run_id": run_id,
        "origin": "strategy",
        "ts_in": TS_IN.isoformat(),
        "ts_out": TS_OUT.isoformat(),
        "px_in": 2415.30,
        "px_out": 2418.75,
        "side": "LONG",
        "volume": 0.50,
        "sl": 2413.80,
        "tp": 2420.00,
        "exit_reason": "tp_hit",
        "exit_reason_source": "broker",
        "pnl": 172.50,
        "mae": -4.2,
        "mfe": 34.5,
    }])


def test_review_strategy_happy_path_sse_sequence(app_factory, tmp_path):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    db_path = tmp_path / "research.db"
    lake_root = tmp_path / "lake"
    _seed_strategy(db_path)
    app.state.registry = ResearchRegistry(db_path)
    app.state.lake_root = lake_root

    responses = [
        _FakeMessage(content=[_FakeTextBlock(text="The strategy is performing well overall.")], stop_reason="end_turn"),
    ]
    app.state.chat_client = _FakeAnthropicClient(responses=responses)

    with TestClient(app) as client:
        with client.stream(
            "POST", "/api/ai/review_strategy", json={"strategy_id": "EMASAR"}
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            body = "".join(resp.iter_text())

    events = _parse_sse_events(body)
    names = [e[0] for e in events]
    assert names == ["ai_text", "ai_done"]
    assert "performing well" in events[0][1]
    assert "performing well" in events[1][1]

    # Model actually received the dossier XML + question, STABLE-FIRST
    # ordering (fixed preamble -> dossier -> question last).
    call = app.state.chat_client.messages.calls[0]
    assert "<documents>" in call["system"]
    assert call["system"].index("You are SENTINEL") < call["system"].index("<documents>")
    assert "EMASAR" in call["messages"][0]["content"]


def test_review_strategy_unknown_strategy_id_emits_ai_error(app_factory, tmp_path):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    db_path = tmp_path / "research.db"
    lake_root = tmp_path / "lake"
    _seed_strategy(db_path)
    app.state.registry = ResearchRegistry(db_path)
    app.state.lake_root = lake_root
    app.state.chat_client = _FakeAnthropicClient(responses=[])

    with TestClient(app) as client:
        with client.stream(
            "POST", "/api/ai/review_strategy", json={"strategy_id": "DOES-NOT-EXIST"}
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())

    events = _parse_sse_events(body)
    assert [e[0] for e in events] == ["ai_error"]
    assert "DOES-NOT-EXIST" in events[0][1]


def test_review_strategy_gated_model_without_unlock_returns_403_before_any_call(
    app_factory, tmp_path, monkeypatch
):
    monkeypatch.setenv("SENTINEL_OPUS_GATE", "letmein")
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    db_path = tmp_path / "research.db"
    lake_root = tmp_path / "lake"
    _seed_strategy(db_path)
    app.state.registry = ResearchRegistry(db_path)
    app.state.lake_root = lake_root

    fake_client = _FakeAnthropicClient(responses=[])
    app.state.chat_client = fake_client

    with TestClient(app) as client:
        resp = client.post(
            "/api/ai/review_strategy",
            json={"strategy_id": "EMASAR", "model": "claude-opus-4-8"},
        )
        assert resp.status_code == 403
        assert resp.json() == {"error": "gated_model_locked"}

    # No API call was made -- gate checked BEFORE dossier build / API call.
    assert fake_client.messages.calls == []
