"""
sentinel_engine.service.chat — POST /chat context builder + endpoint logic
(P5, Tasks 5.1/5.2 — AI assistant re-enable).

`build_chat_context(snapshot, cfg, positions)` builds the assistant's system
prompt SOLELY from `sentinel_engine.ai_context.render_ai_context(snapshot,
cfg)` — the single, config-sourced producer of AI context (P1 Task 1.7) —
plus a read-only MT5 positions block. No literal weights, no ad-hoc scoring
text are added here: every number in the context is either sourced from
`render_ai_context` or is a raw pass-through of a position field. This keeps
prompt drift impossible by construction, per the Phase 5 exit gate.

`answer_chat(...)` wires that context as the system prompt into the existing
`sentinel.ai_chat` client (`SentinelAI`), which itself falls back to a
deterministic mock response when no `ANTHROPIC_API_KEY` is configured — so
callers (including tests) never need network access or a real key. A stub
client can be injected for fully deterministic testing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sentinel_engine.ai_context import render_ai_context


def _format_positions(positions: list) -> str:
    """Plain, read-only rendering of MT5 positions (never used to place or
    modify orders — see `sentinel_engine.feed.LiveMT5Feed.positions`)."""
    if not positions:
        return "Sin posiciones abiertas."
    lines = []
    for p in positions:
        symbol = p.get("symbol", "?")
        volume = p.get("volume", p.get("volume_lots", "?"))
        ptype = p.get("type", "?")
        price_open = p.get("price_open", "?")
        profit = p.get("profit", "?")
        lines.append(
            f"  {symbol}: type={ptype} vol={volume} open={price_open} profit={profit}"
        )
    return "\n".join(lines)


def build_chat_context(snapshot: Any, cfg: Any, positions: list | None) -> str:
    """Build the /chat system prompt SOLELY from `render_ai_context(snapshot,
    cfg)` plus a read-only MT5 positions block.

    `snapshot` must be a `sentinel_engine.engine.Snapshot` (or anything with
    a `.to_dict()` matching its shape) — the same object `Engine.step()`
    produces. `cfg` is the matching `InstrumentConfig`. `positions` is the
    feed's `positions()` list (plain dicts); `None`/`[]` are both rendered
    as "no open positions".
    """
    base = render_ai_context(snapshot, cfg)
    positions_block = (
        "\n=== POSICIONES ABIERTAS (MT5, solo lectura) ===\n"
        f"{_format_positions(positions or [])}\n"
    )
    return base + positions_block


@dataclass
class ChatReply:
    content: str
    error: str | None = None


def answer_chat(
    question: str,
    snapshot: Any,
    cfg: Any,
    positions: list | None,
    client: Any = None,
    conversation: list | None = None,
) -> ChatReply:
    """Answer `question` grounded in the current snapshot + positions.

    `client` defaults to a fresh `sentinel.ai_chat.SentinelAI()` (imported
    lazily to keep this module's import graph light) — which falls back to
    its deterministic `_mock_response` when no `ANTHROPIC_API_KEY` is set.
    Inject a stub `client` (any object exposing `.chat(user_message,
    model_key, system_prompt, conversation, **kwargs) -> dict`) for fully
    deterministic tests.
    """
    context = build_chat_context(snapshot, cfg, positions)
    if client is None:
        from sentinel.ai_chat import SentinelAI

        client = SentinelAI()
    result = client.chat(
        user_message=question,
        model_key="sonnet",
        system_prompt=context,
        conversation=conversation or [],
    )
    return ChatReply(content=result.get("content", ""), error=result.get("error"))
