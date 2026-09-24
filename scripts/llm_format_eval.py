"""scripts/llm_format_eval.py — mini-eval runner (Task C6, CT-5 lane).

Empirically validates/refutes the format recommendations of
`docs/superpowers/specs/2026-07-12-llm-timeseries-context-research.md` §6
("Mini-Eval Design") on this codebase's own dossier data, per that section's
design: 8 fixed questions (4 position-dossier + 4 strategy-review) x 4
competing serialization formats x 2 target models (`sonnet`=`claude-sonnet-5`,
`haiku`=`claude-haiku-4-5-20251001`) = 64 (question, format, model) prompt
specs.

**Formats built from the C3 dossier builders** (`sentinel_engine.ai.dossier`
`build_position_dossier`/`build_strategy_dossier`, imported here read-only,
NOT modified):
  1. `markdown_table` — the C3 builders' literal §3/§4 output, unmodified.
  2. `csv`             — same underlying sections, Markdown `|` bar/run
                          tables swapped for bare CSV (§6 arm 2).
  3. `json_array`       — same underlying bar/run rows re-serialized as a
                          JSON array-of-objects (§6 arm 3, "the team's
                          original assumption's loser arm").
  4. `stats_only`       — bar-table/flagged-excerpt `<document>` blocks
                          dropped entirely, trade_record/aggregate_stats/
                          strategy_record/runs-table sections kept (§6 arm 4).

**Dry-run (default whenever `ANTHROPIC_API_KEY` is absent, per task brief)**:
builds all 64 prompt specs and prints them — zero network calls. The real
run (writes
`docs/superpowers/specs/2026-07-12-format-eval-results.md`) is triggered by
a human/ORC, never by this module's tests, which exercise only the
dry-run/report-writing paths and never call `_call_model`.

Cost guard: hard cap of `MAX_CALLS = 8 * 4 * 2 = 64` single-shot calls (the
mini-eval's own repeat-x3-per-cell design from §6 is a documented follow-up,
out of scope for this minimal runner — see task report DESVIACIONES). Any
attempted real run whose estimated call count exceeds the cap aborts via
`CostGuardError` before any request is issued.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Matrix constants
# ---------------------------------------------------------------------------

MODELS = ["sonnet", "haiku"]
MODEL_IDS = {
    "sonnet": "claude-sonnet-5",
    "haiku": "claude-haiku-4-5-20251001",
}

FORMATS = ["markdown_table", "csv", "json_array", "stats_only"]

# 8 questions per research doc §6 -- 4 position-dossier + 4 strategy-review,
# each with an objectively-derivable ground truth from the underlying fixture
# data (ground-truth values are for the real-run scorer, out of scope here --
# see task report).
QUESTIONS = [
    {
        "id": "Q1_mae_pct_sl",
        "kind": "position",
        "text": "What was the MAE as a percentage of the stop-loss distance?",
    },
    {
        "id": "Q2_highest_high_bar",
        "kind": "position",
        "text": "Which bar (relative to entry) had the highest high in the M1 window shown?",
    },
    {
        "id": "Q3_ema_cross_at_entry",
        "kind": "position",
        "text": "Was EMA8 above or below EMA20 at the moment of entry?",
    },
    {
        "id": "Q4_bars_to_mfe",
        "kind": "position",
        "text": (
            "How many M1 bars elapsed between entry and the bar where price "
            "first reached its most favorable excursion (MFE)?"
        ),
    },
    {
        "id": "Q5_profit_factor",
        "kind": "strategy",
        "text": "What is the strategy's profit factor?",
    },
    {
        "id": "Q6_exit_reason_counts",
        "kind": "strategy",
        "text": "How many trades were closed via sl_hit vs tp_hit?",
    },
    {
        "id": "Q7_worst_mae_trade",
        "kind": "strategy",
        "text": (
            "Which trade_id had the worst MAE-to-SL ratio, and what were its "
            "entry/exit prices?"
        ),
    },
    {
        "id": "Q8_propose_parameter_change",
        "kind": "strategy",
        "text": (
            "Propose one concrete parameter change (e.g. wider SL) and "
            "justify it using at least two specific trades from the data."
        ),
    },
]

QUESTION_IDS = {q["id"] for q in QUESTIONS}

MAX_CALLS = len(QUESTIONS) * len(FORMATS) * len(MODELS)  # 8 * 4 * 2 = 64

DEFAULT_REPORT_PATH = (
    Path("docs/superpowers/specs/2026-07-12-format-eval-results.md")
)


class CostGuardError(RuntimeError):
    """Raised when an estimated call count would exceed the hard cap."""


def check_cost_guard(n_calls: int, cap: int = MAX_CALLS) -> None:
    if n_calls > cap:
        raise CostGuardError(
            f"estimated {n_calls} calls exceeds hard cap {cap} -- aborting "
            "before any request is issued"
        )


# ---------------------------------------------------------------------------
# Fixture dossier data (self-contained, deterministic -- no DB/lake access
# needed for building prompt specs; the C3 builders' DB/lake-backed API is
# still imported and available for a real run to swap in live trade_ids, but
# tests and dry-run use this fixed synthetic dossier so this file has zero
# I/O and zero network in its default/test path).
# ---------------------------------------------------------------------------

_POSITION_XML = """<documents>

  <document index="1">
    <source>trade_record:T00001</source>
    <document_content>
    {
      "trade_id": "T00001",
      "instrument": "XAUUSD",
      "side": "LONG",
      "ts_in": "2026-07-10T13:22:00Z",
      "ts_out": "2026-07-10T13:41:00Z",
      "px_in": 2415.30,
      "px_out": 2418.75,
      "sl": 2413.80,
      "tp": 2420.00,
      "volume": 0.50,
      "exit_reason": "tp_hit",
      "pnl_usd": 172.50,
      "mae_pips": -4.2,
      "mfe_pips": 34.5,
      "hold_time_min": 19
    }
    </document_content>
  </document>

  <document index="2">
    <source>derived_stats:T00001</source>
    <document_content>
    MAE as % of SL distance: 28.0%
    MFE as % of TP distance: 92.6%
    R-multiple realized: 1.84R
    </document_content>
  </document>

  <document index="3">
    <source>bars:M1:T00001:bars_before_entry=20:bars_after_exit=20</source>
    <document_content>
    | idx | time  | open    | high    | low     | close   | ema8    | ema20   | sar     |
    |----:|-------|--------:|--------:|--------:|--------:|--------:|--------:|--------:|
    | -2  | 13:20 | 2414.90 | 2415.05 | 2414.80 | 2414.95 | 2414.60 | 2413.70 | 2413.10 |
    | -1  | 13:21 | 2415.00 | 2415.15 | 2414.95 | 2415.10 | 2414.75 | 2413.80 | 2413.20 |
    | 0   | 13:22 | 2415.10 | 2415.35 | 2415.05 | 2415.30 | 2415.00 | 2413.90 | 2413.20 | <<< ENTRY BAR
    | +1  | 13:23 | 2415.30 | 2415.50 | 2415.20 | 2415.45 | 2415.10 | 2414.00 | 2413.30 |
    | +2  | 13:24 | 2416.80 | 2419.10 | 2416.70 | 2418.90 | 2416.50 | 2414.80 | 2413.70 |
    | +3  | 13:25 | 2418.60 | 2418.80 | 2418.50 | 2418.75 | 2417.90 | 2415.20 | 2414.50 | <<< EXIT BAR
    </document_content>
  </document>

</documents>"""

_STRATEGY_XML = """<documents>

  <document index="1">
    <source>aggregate_stats:S1</source>
    <document_content>
    Period: 2026-07-01 to 2026-07-11 | N trades: 40
    Profit factor: 1.62 | Win rate: 47.5% | Expectancy/trade: +$12.40
    Exit reason breakdown:
      tp_hit: 19 (47.5%) | sl_hit: 15 (37.5%) | manual_close: 6 (15.0%)
    </document_content>
  </document>

  <document index="2">
    <source>trade_log:RUN001:n=40</source>
    <document_content>
    | trade_id | side  | px_in   | px_out  | pnl_usd | mae_pct_sl | exit_reason |
    |----------|-------|--------:|--------:|--------:|-----------:|-------------|
    | T00001   | LONG  | 2415.30 | 2418.75 | +172.50 | 28%        | tp_hit      |
    | T00002   | SHORT | 2404.20 | 2405.90 | -42.50  | 112%       | sl_hit      |
    </document_content>
  </document>

  <document index="3">
    <source>flagged_trade:T00002:reason=worst_mae_pct_sl</source>
    <document_content>
    {"trade_id": "T00002", "side": "SHORT", "px_in": 2404.20, "px_out": 2405.90, "mae_pct_sl": 112}
    </document_content>
  </document>

</documents>"""

# NOTE: these two fixtures are hand-written in the SAME shape the real C3
# builders (`build_position_dossier`/`build_strategy_dossier`, imported
# below) produce -- they stand in for a real DB/lake-backed call so that
# building the 64 prompt specs is zero-I/O and deterministic. A real run can
# call the C3 builders directly for a live trade_id/strategy_id; that wiring
# is intentionally left to the caller of `build_prompt_specs(...)` via the
# `position_xml`/`strategy_xml` overrides.

# Imported for availability/typing only -- confirms the C3 contract this
# runner is built against without requiring a DB/lake at import time.
from sentinel_engine.ai.dossier import (  # noqa: E402  (import after fixtures, for readability)
    build_position_dossier,  # noqa: F401
    build_strategy_dossier,  # noqa: F401
)


# ---------------------------------------------------------------------------
# Format transforms (all operate on the markdown-table dossier XML the C3
# builders produce, per §6's arm definitions -- "structurally identical,
# swap the table syntax").
# ---------------------------------------------------------------------------

_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")


def _markdown_table_to_csv(block: str) -> str:
    """Convert a `| a | b |` Markdown table (with a `|---|---|` separator
    row) embedded in `block` into bare CSV lines, leaving non-table lines
    untouched."""
    out_lines = []
    for line in block.splitlines():
        m = _TABLE_ROW_RE.match(line)
        if not m:
            out_lines.append(line)
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue  # drop the markdown separator row entirely
        out_lines.append(",".join(cells))
    return "\n".join(out_lines)


def _markdown_table_to_json_array(block: str) -> str:
    """Convert each `| a | b |` Markdown table found in `block` into a JSON
    array-of-objects using the table's own header row as keys; non-table
    lines are left untouched."""
    lines = block.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _TABLE_ROW_RE.match(line)
        if not m:
            out.append(line)
            i += 1
            continue
        header_cells = [c.strip() for c in m.group(1).split("|")]
        # Expect a separator row right after the header.
        if i + 1 < len(lines) and _TABLE_ROW_RE.match(lines[i + 1]):
            sep_cells = [c.strip() for c in _TABLE_ROW_RE.match(lines[i + 1]).group(1).split("|")]
        else:
            sep_cells = []
        is_separator_next = sep_cells and all(re.fullmatch(r":?-+:?", c) for c in sep_cells if c)
        if not is_separator_next:
            out.append(line)
            i += 1
            continue
        j = i + 2
        rows = []
        while j < len(lines):
            rm = _TABLE_ROW_RE.match(lines[j])
            if not rm:
                break
            row_cells = [c.strip() for c in rm.group(1).split("|")]
            obj = {}
            for k, key in enumerate(header_cells):
                key = key.strip()
                if not key:
                    continue
                val = row_cells[k].strip() if k < len(row_cells) else ""
                # Strip trailing anchor markers (e.g. "<<< ENTRY BAR") from
                # the last populated cell so JSON stays parseable-shaped.
                val = re.sub(r"\s*<<<.*$", "", val).strip()
                obj[key] = val
            rows.append(obj)
            j += 1
        out.append(json.dumps(rows, indent=2))
        i = j
    return "\n".join(out)


def _strip_bar_and_flagged_documents(xml: str) -> str:
    """Drop `<document>` blocks whose `<source>` starts with `bars:` or
    `flagged_trade:` -- the stats-only arm (§6 arm 4): keep aggregate
    stats/trade_record/strategy_record/trade_log, drop raw excerpts."""
    doc_re = re.compile(
        r'  <document index="\d+">\s*\n\s*<source>([^<]*)</source>.*?</document>',
        re.DOTALL,
    )

    def _keep(m: "re.Match[str]") -> str:
        source = m.group(1)
        if source.startswith("bars:") or source.startswith("flagged_trade:"):
            return ""
        return m.group(0)

    stripped = doc_re.sub(_keep, xml)
    # Collapse resulting blank-line runs for readability (cosmetic only).
    return re.sub(r"\n{3,}", "\n\n", stripped)


def render_format(xml: str, fmt: str) -> str:
    """Apply the §6 arm transform for `fmt` to a markdown-table dossier
    `xml` (the C3 builders' native output). `fmt` in `FORMATS`."""
    if fmt == "markdown_table":
        return xml
    if fmt == "csv":
        return _markdown_table_to_csv(xml)
    if fmt == "json_array":
        return _markdown_table_to_json_array(xml)
    if fmt == "stats_only":
        return _strip_bar_and_flagged_documents(xml)
    raise ValueError(f"unknown format: {fmt!r}")


# ---------------------------------------------------------------------------
# Prompt-spec construction (dry-run and real-run share this)
# ---------------------------------------------------------------------------

_INSTRUCTIONS = (
    "<instructions>\n"
    "Before answering, quote the specific bars, indicator values, or trade "
    "fields your conclusion depends on. Then answer the question below, "
    "grounded in those quotes.\n"
    "</instructions>"
)


def build_prompt_specs(
    position_xml: str = _POSITION_XML,
    strategy_xml: str = _STRATEGY_XML,
) -> list[dict[str, Any]]:
    """Build all `len(QUESTIONS) * len(FORMATS) * len(MODELS)` prompt specs.

    Each spec: `{"question_id", "format", "model", "prompt"}`. `prompt`
    places the (format-transformed) dossier data first, then
    `<instructions>` (quote-grounding, RQ6), then the literal `<question>`
    last -- per RQ6's "data before instructions/query" ordering.
    """
    specs: list[dict[str, Any]] = []
    for q in QUESTIONS:
        base_xml = position_xml if q["kind"] == "position" else strategy_xml
        for fmt in FORMATS:
            data_block = render_format(base_xml, fmt)
            for model in MODELS:
                prompt = (
                    f"{data_block}\n\n"
                    f"{_INSTRUCTIONS}\n\n"
                    f"<question>\n{q['text']}\n</question>"
                )
                specs.append({
                    "question_id": q["id"],
                    "format": fmt,
                    "model": model,
                    "model_id": MODEL_IDS[model],
                    "prompt": prompt,
                })
    return specs


# ---------------------------------------------------------------------------
# Dry-run / real-run entry points
# ---------------------------------------------------------------------------

def resolve_dry_run(explicit: bool | None) -> bool:
    """Dry-run is forced True whenever `ANTHROPIC_API_KEY` is absent,
    regardless of what the caller passed -- the safety net the task brief
    requires ("--dry-run prints prompts w/o API calls (default when
    ANTHROPIC_API_KEY absent)"). If a key IS present, honor the caller's
    explicit choice, defaulting to False (real run) only when explicitly
    requested."""
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        return True
    if explicit is None:
        return False
    return explicit


def _call_model(spec: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
    """Real API call -- NEVER exercised by tests (network). Imports the
    Anthropic SDK lazily so importing this module never requires it."""
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=spec["model_id"],
        max_tokens=1024,
        messages=[{"role": "user", "content": spec["prompt"]}],
    )
    text = "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )
    return {**spec, "response": text}


def run(dry_run: bool | None = None) -> list[dict[str, Any]]:
    """Build the 64 prompt specs; in dry-run, print them and return without
    calling the API. Real runs (dry_run=False, key present) are gated by
    `check_cost_guard` before any request is issued."""
    resolved = resolve_dry_run(dry_run)
    specs = build_prompt_specs()

    if resolved:
        print(f"DRY RUN -- {len(specs)} prompt specs built, no API calls made")
        for spec in specs:
            print(f"--- question_id={spec['question_id']} format={spec['format']} model={spec['model']} ---")
            print(spec["prompt"])
            print()
        return specs

    check_cost_guard(len(specs), cap=MAX_CALLS)  # pragma: no cover
    return [_call_model(spec) for spec in specs]  # pragma: no cover


# ---------------------------------------------------------------------------
# Report writer (pure, no network -- renders canned/real results to markdown)
# ---------------------------------------------------------------------------

def render_report(results: list[dict[str, Any]]) -> str:
    """Render `results` (list of `{"question_id","format","model","score",
    "tokens", ...}` dicts) into the §6-mandated per-question breakdown +
    per-format aggregate markdown report. Pure function -- no I/O."""
    lines = ["# LLM Format Mini-Eval Results", ""]
    lines.append(
        "Per research doc §6 — 8 questions x 4 formats x 2 models. "
        "Per-question breakdown is the primary deliverable (not just the "
        "aggregate), since the research explicitly found conflicting "
        "evidence on CSV specifically."
    )
    lines.append("")

    # Per-format aggregate score.
    lines.append("## Aggregate score by format")
    lines.append("")
    lines.append("| format | mean score | n |")
    lines.append("|---|---:|---:|")
    for fmt in FORMATS:
        rows = [r for r in results if r["format"] == fmt]
        mean = sum(r["score"] for r in rows) / len(rows) if rows else float("nan")
        lines.append(f"| {fmt} | {mean:.3f} | {len(rows)} |")
    lines.append("")

    # Per-question x format x model breakdown.
    lines.append("## Per-question breakdown")
    lines.append("")
    lines.append("| question_id | format | model | score | tokens |")
    lines.append("|---|---|---|---:|---:|")
    for q in QUESTIONS:
        for r in [x for x in results if x["question_id"] == q["id"]]:
            lines.append(
                f"| {r['question_id']} | {r['format']} | {r['model']} | "
                f"{r['score']:.2f} | {r.get('tokens', 'n/a')} |"
            )
    lines.append("")

    return "\n".join(lines)


def write_report(results: list[dict[str, Any]], out_path: Path = DEFAULT_REPORT_PATH) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(results), encoding="utf-8")
    return out_path


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=None)
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
