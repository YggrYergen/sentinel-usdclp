"""tests/ai/test_loop.py — TDD for Task C4b: manual tool loop
(`sentinel_engine/ai/loop.py`).

`run_tool_loop(client, model, system, messages, tools, ctx, on_text) ->
final_text`: while `stop_reason == "tool_use"`, execute every tool_use block
via C4a's `execute_tool` (imported, never reimplemented), append a
`tool_result` user message, and re-call the (fake, injected) Anthropic
client. Max 8 iterations -- on hitting the cap, append a "max iterations"
note and stop instead of looping forever. `on_text(chunk)` is invoked once
per text block seen on each response (streaming-shaped callback, but the fake
client here returns complete messages -- no real network/SSE involved).

Fake Anthropic client: a plain object exposing `.messages.create(**kwargs) ->
FakeMessage`, scripted with a fixed sequence of responses keyed by call
index. No network, no real `anthropic` package dependency for these tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from sentinel_engine.ai.loop import MAX_TOOL_ITERATIONS, run_tool_loop


# ── Fake Anthropic message/content-block shapes (mirrors the real SDK's
# minimal surface run_tool_loop actually touches: .content, .stop_reason) ──

@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class FakeMessage:
    content: list
    stop_reason: str


@dataclass
class FakeMessagesResource:
    responses: list = field(default_factory=list)
    calls: list = field(default_factory=list)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        idx = len(self.calls) - 1
        if idx < len(self.responses):
            return self.responses[idx]
        # Repeat the last scripted response if the loop calls more times
        # than scripted (keeps a runaway loop from raising instead of
        # exercising the max-iterations cap).
        return self.responses[-1]


@dataclass
class FakeAnthropicClient:
    responses: list

    def __post_init__(self):
        self.messages = FakeMessagesResource(responses=self.responses)


def _noop_ctx():
    return {"registry": None, "lake_root": None}


# ── executes tools, respects tool_use -> end_turn sequence ──

def test_loop_executes_tool_then_returns_final_text(monkeypatch):
    calls = {"n": 0}

    def fake_execute_tool(name, args, ctx):
        calls["n"] += 1
        assert name == "get_scorecard"
        assert args == {"strategy_id": "EMS1"}
        return '{"pf": 1.5}'

    monkeypatch.setattr("sentinel_engine.ai.loop.execute_tool", fake_execute_tool)

    responses = [
        FakeMessage(
            content=[FakeToolUseBlock(id="tu_1", name="get_scorecard", input={"strategy_id": "EMS1"})],
            stop_reason="tool_use",
        ),
        FakeMessage(
            content=[FakeTextBlock(text="PF is 1.5, looks solid.")],
            stop_reason="end_turn",
        ),
    ]
    client = FakeAnthropicClient(responses=responses)

    seen_chunks = []
    final_text = run_tool_loop(
        client=client,
        model="claude-sonnet-5",
        system="You are a trading analyst.",
        messages=[{"role": "user", "content": "how's EMS1 doing?"}],
        tools=[],
        ctx=_noop_ctx(),
        on_text=seen_chunks.append,
    )

    assert calls["n"] == 1
    assert final_text == "PF is 1.5, looks solid."
    assert seen_chunks == ["PF is 1.5, looks solid."]
    # Two API calls: initial + one after the tool_result.
    assert len(client.messages.calls) == 2
    # Second call's messages must include the assistant tool_use turn and a
    # user turn carrying the tool_result (matched by tool_use_id).
    second_call_messages = client.messages.calls[1]["messages"]
    assert second_call_messages[-2]["role"] == "assistant"
    tool_result_msg = second_call_messages[-1]
    assert tool_result_msg["role"] == "user"
    tool_result_block = tool_result_msg["content"][0]
    assert tool_result_block["type"] == "tool_result"
    assert tool_result_block["tool_use_id"] == "tu_1"
    assert tool_result_block["content"] == '{"pf": 1.5}'


def test_loop_streams_text_on_every_response(monkeypatch):
    monkeypatch.setattr("sentinel_engine.ai.loop.execute_tool", lambda *a, **k: "ok")

    responses = [
        FakeMessage(
            content=[
                FakeTextBlock(text="Checking data first..."),
                FakeToolUseBlock(id="tu_1", name="get_bars", input={}),
            ],
            stop_reason="tool_use",
        ),
        FakeMessage(content=[FakeTextBlock(text="Done.")], stop_reason="end_turn"),
    ]
    client = FakeAnthropicClient(responses=responses)
    chunks = []
    final_text = run_tool_loop(
        client=client,
        model="claude-sonnet-5",
        system="sys",
        messages=[{"role": "user", "content": "q"}],
        tools=[],
        ctx=_noop_ctx(),
        on_text=chunks.append,
    )
    assert chunks == ["Checking data first...", "Done."]
    assert final_text == "Done."


def test_loop_with_no_tool_use_returns_immediately(monkeypatch):
    calls_made = {"n": 0}
    monkeypatch.setattr(
        "sentinel_engine.ai.loop.execute_tool",
        lambda *a, **k: calls_made.__setitem__("n", calls_made["n"] + 1) or "unused",
    )

    responses = [FakeMessage(content=[FakeTextBlock(text="Direct answer.")], stop_reason="end_turn")]
    client = FakeAnthropicClient(responses=responses)

    final_text = run_tool_loop(
        client=client,
        model="claude-sonnet-5",
        system="sys",
        messages=[{"role": "user", "content": "q"}],
        tools=[],
        ctx=_noop_ctx(),
        on_text=lambda c: None,
    )
    assert final_text == "Direct answer."
    assert calls_made["n"] == 0
    assert len(client.messages.calls) == 1


# ── max-8-iterations cap ──

def test_loop_stops_at_max_iterations_and_appends_note(monkeypatch):
    monkeypatch.setattr("sentinel_engine.ai.loop.execute_tool", lambda *a, **k: "loop forever result")

    # Always returns tool_use -> the loop must be the thing that stops it,
    # not the fake client running out of scripted responses.
    always_tool_use = FakeMessage(
        content=[FakeToolUseBlock(id="tu_x", name="get_bars", input={})],
        stop_reason="tool_use",
    )
    client = FakeAnthropicClient(responses=[always_tool_use])

    final_text = run_tool_loop(
        client=client,
        model="claude-sonnet-5",
        system="sys",
        messages=[{"role": "user", "content": "q"}],
        tools=[],
        ctx=_noop_ctx(),
        on_text=lambda c: None,
    )

    assert len(client.messages.calls) == MAX_TOOL_ITERATIONS
    assert "max iterations" in final_text.lower()


def test_loop_multiple_tool_use_blocks_in_one_response(monkeypatch):
    seen_names = []

    def fake_execute_tool(name, args, ctx):
        seen_names.append(name)
        return f"result-for-{name}"

    monkeypatch.setattr("sentinel_engine.ai.loop.execute_tool", fake_execute_tool)

    responses = [
        FakeMessage(
            content=[
                FakeToolUseBlock(id="tu_1", name="get_bars", input={}),
                FakeToolUseBlock(id="tu_2", name="get_scorecard", input={}),
            ],
            stop_reason="tool_use",
        ),
        FakeMessage(content=[FakeTextBlock(text="Combined.")], stop_reason="end_turn"),
    ]
    client = FakeAnthropicClient(responses=responses)

    final_text = run_tool_loop(
        client=client,
        model="claude-sonnet-5",
        system="sys",
        messages=[{"role": "user", "content": "q"}],
        tools=[],
        ctx=_noop_ctx(),
        on_text=lambda c: None,
    )

    assert seen_names == ["get_bars", "get_scorecard"]
    assert final_text == "Combined."
    # Both tool_result blocks must land in a SINGLE user message (per docs
    # guidance: parallel tool_use -> one user message with all results).
    second_call_messages = client.messages.calls[1]["messages"]
    tool_result_msg = second_call_messages[-1]
    assert tool_result_msg["role"] == "user"
    assert len(tool_result_msg["content"]) == 2
    ids = {b["tool_use_id"] for b in tool_result_msg["content"]}
    assert ids == {"tu_1", "tu_2"}
