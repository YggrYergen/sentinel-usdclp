"""sentinel_engine.ai.loop — manual tool-use loop (Task C4b).

`run_tool_loop(client, model, system, messages, tools, ctx, on_text) ->
final_text`: calls the injected Anthropic-shaped `client.messages.create(...)`
and, while the response's `stop_reason == "tool_use"`, executes every
`tool_use` block via C4a's `sentinel_engine.ai.tools.execute_tool` (imported,
never reimplemented), appends the assistant turn plus a single user turn
carrying ALL of that turn's `tool_result` blocks (parallel-tool-use pattern,
per Anthropic docs: one user message per round, not one per tool), then
re-calls the client. Capped at `MAX_TOOL_ITERATIONS` (8) API calls -- on
hitting the cap without an `end_turn`, a "max iterations" note is appended to
whatever text was last seen and the loop stops (never raises, never spins
forever).

`on_text(chunk)` is called once per text block on EVERY response (initial and
each follow-up) -- this is the streaming hook the SSE endpoint (chat.py)
wires to emit `ai_text` events per CT-9. The client injected here is expected
to return complete `Message`-shaped objects (`.content`, `.stop_reason`), not
a real SSE stream -- tests inject a fake with that exact minimal shape, no
network and no dependency on the real `anthropic` package.
"""
from __future__ import annotations

from typing import Any, Callable

from sentinel_engine.ai.tools import execute_tool

# Hard cap on the number of client.messages.create(...) calls per
# run_tool_loop invocation. Guards against a model stuck perpetually
# requesting tools (or a fake/misbehaving client in tests).
MAX_TOOL_ITERATIONS = 8

_MAX_ITERATIONS_NOTE = "\n\n[max iterations reached: stopped after repeated tool use]"


def run_tool_loop(
    client: Any,
    model: str,
    system: str,
    messages: list[dict],
    tools: list[dict],
    ctx: dict[str, Any],
    on_text: Callable[[str], None],
) -> str:
    """Drive the manual agentic loop against `client.messages.create(...)`.

    `messages` is the initial conversation (caller-owned list; not mutated --
    a local copy is extended internally). Returns the final assistant text
    (concatenation of all text blocks in the last response), or that text
    plus a `_MAX_ITERATIONS_NOTE` suffix if the iteration cap was hit while
    `stop_reason` was still `"tool_use"`.
    """
    convo = list(messages)
    last_text = ""

    for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
        response = client.messages.create(
            model=model,
            system=system,
            messages=convo,
            tools=tools,
            max_tokens=8192,
        )

        text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        if text_parts:
            last_text = "".join(text_parts)
            for part in text_parts:
                on_text(part)

        if response.stop_reason != "tool_use":
            return last_text

        if iteration == MAX_TOOL_ITERATIONS:
            # Cap reached and the model still wants to call tools -- stop
            # here rather than issuing a 9th API call.
            return last_text + _MAX_ITERATIONS_NOTE

        tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]

        # Preserve the assistant turn (including tool_use blocks) verbatim,
        # per the documented manual-loop pattern.
        convo.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in tool_use_blocks:
            result = execute_tool(block.name, block.input, ctx)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )

        # All of this turn's tool_result blocks go in a SINGLE user message
        # (parallel tool use -> one round trip), never split across
        # multiple messages.
        convo.append({"role": "user", "content": tool_results})

    return last_text + _MAX_ITERATIONS_NOTE
