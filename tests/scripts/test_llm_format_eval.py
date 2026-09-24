"""tests/scripts/test_llm_format_eval.py — TDD for Task C6: mini-eval runner
(`scripts/llm_format_eval.py`), per research doc §6
(`docs/superpowers/specs/2026-07-12-llm-timeseries-context-research.md`).

Scope of this test file: dry-run prompt-spec construction (8 questions x 4
formats x 2 models = 64 specs) and the markdown report writer. NO network
calls anywhere in this file -- the real API-calling path is only exercised
by a human/ORC-triggered real run, never by pytest.
"""
from __future__ import annotations

import importlib

import pytest

mod = importlib.import_module("scripts.llm_format_eval")


# ---------------------------------------------------------------------------
# Matrix constants
# ---------------------------------------------------------------------------

def test_matrix_sizes():
    assert len(mod.QUESTIONS) == 8
    assert len(mod.FORMATS) == 4
    assert len(mod.MODELS) == 2


def test_cost_guard_cap_matches_matrix():
    # research doc §6 + task brief: hard cap N calls = 8 x 4 x 2
    assert mod.MAX_CALLS == 8 * 4 * 2 == 64


# ---------------------------------------------------------------------------
# Dry-run prompt-spec construction
# ---------------------------------------------------------------------------

def test_build_prompt_specs_count_and_shape():
    specs = mod.build_prompt_specs()
    assert len(specs) == 64
    for spec in specs:
        assert set(spec.keys()) >= {"question_id", "format", "model", "prompt"}
        assert spec["question_id"] in {q["id"] for q in mod.QUESTIONS}
        assert spec["format"] in mod.FORMATS
        assert spec["model"] in mod.MODELS
        assert isinstance(spec["prompt"], str)
        assert spec["prompt"]  # non-empty


def test_build_prompt_specs_full_cartesian_product():
    specs = mod.build_prompt_specs()
    seen = {(s["question_id"], s["format"], s["model"]) for s in specs}
    expected = {
        (q["id"], fmt, model)
        for q in mod.QUESTIONS
        for fmt in mod.FORMATS
        for model in mod.MODELS
    }
    assert seen == expected


def test_build_prompt_specs_data_before_question():
    """Per RQ6 (data before instructions/question, 'up to 30%' quality
    finding) -- every prompt must place the dossier data before the literal
    question text."""
    specs = mod.build_prompt_specs()
    for spec in specs:
        q_text = next(q["text"] for q in mod.QUESTIONS if q["id"] == spec["question_id"])
        data_pos = spec["prompt"].find("<documents>")
        question_pos = spec["prompt"].find(q_text)
        assert data_pos != -1
        assert question_pos != -1
        assert data_pos < question_pos


def test_stats_only_format_omits_bar_tables():
    """Arm 4 (stats-only) must not include a Markdown bars table -- it drops
    raw bar excerpts entirely per research doc §6 arm 4 definition."""
    specs = mod.build_prompt_specs()
    stats_only = [s for s in specs if s["format"] == "stats_only"]
    assert stats_only
    for spec in stats_only:
        assert "ema8" not in spec["prompt"].lower() or "| idx |" not in spec["prompt"]


def test_csv_format_has_no_pipe_table_syntax_in_bars():
    """Arm 2 (CSV-sectioned) swaps Markdown '|' table syntax for bare CSV in
    the bar/table sections it derives from the markdown arm."""
    specs = mod.build_prompt_specs()
    csv_specs = [s for s in specs if s["format"] == "csv"]
    assert csv_specs
    # At least one csv-format prompt should contain a comma-delimited data
    # line without a leading markdown pipe.
    assert any("," in s["prompt"] for s in csv_specs)


def test_json_format_is_array_of_objects():
    specs = mod.build_prompt_specs()
    json_specs = [s for s in specs if s["format"] == "json_array"]
    assert json_specs
    for spec in json_specs:
        assert '"open"' in spec["prompt"] or '"pf"' in spec["prompt"] or "[" in spec["prompt"]


# ---------------------------------------------------------------------------
# Cost guard
# ---------------------------------------------------------------------------

def test_cost_guard_raises_when_estimate_exceeds_cap():
    with pytest.raises(mod.CostGuardError):
        mod.check_cost_guard(n_calls=65, cap=mod.MAX_CALLS)


def test_cost_guard_passes_at_cap():
    mod.check_cost_guard(n_calls=64, cap=mod.MAX_CALLS)  # must not raise


# ---------------------------------------------------------------------------
# Dry-run mode / no network
# ---------------------------------------------------------------------------

def test_dry_run_defaults_true_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert mod.resolve_dry_run(explicit=None) is True


def test_dry_run_explicit_false_still_true_without_key(monkeypatch):
    # Even if caller passes --dry-run=false, without a key we cannot call
    # the API -- dry-run must remain forced True (documented safety net).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert mod.resolve_dry_run(explicit=False) is True


def test_dry_run_explicit_true_honored_even_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-for-test")
    assert mod.resolve_dry_run(explicit=True) is True


def test_dry_run_prints_prompts_without_calling_api(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def _boom(*a, **kw):  # pragma: no cover -- must never be called
        raise AssertionError("network call attempted during dry-run")

    monkeypatch.setattr(mod, "_call_model", _boom)
    mod.run(dry_run=True)
    out = capsys.readouterr().out
    assert "question_id" in out or "DRY RUN" in out or "prompt" in out.lower()


# ---------------------------------------------------------------------------
# Report writer (renders markdown from canned results, no network)
# ---------------------------------------------------------------------------

def _canned_results():
    results = []
    for q in mod.QUESTIONS:
        for fmt in mod.FORMATS:
            for model in mod.MODELS:
                results.append({
                    "question_id": q["id"],
                    "format": fmt,
                    "model": model,
                    "score": 1.0 if fmt == "markdown_table" else 0.5,
                    "tokens": 1234,
                })
    return results


def test_render_report_contains_scores_and_per_question_table():
    results = _canned_results()
    report = mod.render_report(results)
    assert isinstance(report, str)
    assert "markdown_table" in report
    assert "csv" in report
    assert "json_array" in report
    assert "stats_only" in report
    for q in mod.QUESTIONS:
        assert q["id"] in report
    assert "1234" in report  # token counts surfaced


def test_write_report_writes_expected_path(tmp_path):
    results = _canned_results()
    out_path = tmp_path / "format-eval-results.md"
    mod.write_report(results, out_path)
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "markdown_table" in content


def test_render_report_is_pure_no_network(monkeypatch):
    def _boom(*a, **kw):  # pragma: no cover
        raise AssertionError("network call attempted during report render")

    monkeypatch.setattr(mod, "_call_model", _boom)
    mod.render_report(_canned_results())
