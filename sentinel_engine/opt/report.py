"""4.7 -- Study report generator (Fable Sec. 2.6 / 2.10 / Sec. 4 items 2, 10).

Scope (per the locked task brief): generate a self-contained study report
artifact from data already produced by the other opt modules -- this module
does not run a search, does not touch the price lake or golden fixtures, and
does not itself compute walk-forward folds, labels, or objective scores. It
consumes:

  - a ``selection.SelectionOutcome`` (Task 4.5) -- the leaderboard, the
    winner (if any), and why every rejected candidate was rejected;
  - a ``registry.TrialRegistry`` (Task 4.6, read-only here) -- to look up the
    study's total trial count (for the deflated Sharpe ratio) and, if the
    caller wants it computed here rather than supplied, the winner's per-trial
    return series;
  - a single-touch ``HoldoutResult`` -- the most-recent-slice result touched
    exactly once by the chosen config, reported **win or lose** (Fable Sec
    2.6: "Result goes in the report verbatim, win or lose.");
  - a sequence of ``RegimeMetrics`` -- the winner's per-regime metric
    breakdown (Fable Sec 2.9/2.10: "per-regime heatmap");
  - the production config, to render a "winner vs production" parameter diff.

Output is a self-contained, deterministic Markdown artifact (pathlib + utf-8,
no external template engine, no network, no timestamps that would break
reproducibility beyond a caller-supplied ``generated_at``) written to
``out_path``. Markdown was chosen over HTML: it renders correctly with zero
dependencies (no CSS/JS to vendor), diffs cleanly in git, and satisfies the
task's "HTML or Markdown" contract; a future HTML variant can wrap this same
data model without touching the machinery below.

Ambiguity resolutions (spec silent on exact mechanics, resolved here):
  - The DSR figure the report shows can either be supplied directly (the
    caller already ran ``registry.deflated_sharpe_ratio`` at study level, per
    Fable Sec 2.6: "DSR computed for the winner") or, if the caller only has
    the winner's per-fold/per-day return series, this module will compute it
    itself via ``registry.trial_count(study_id)`` for the honest trial count
    -- either path lands the same "honest p-value" in the report. If neither
    is available (e.g. no winner was selected), the DSR section is rendered
    as explicitly "not computed" rather than omitted silently.
  - "Single-touch 2-month holdout" is represented by ``HoldoutResult``, a
    plain caller-supplied record (this module does not enforce the
    single-touch discipline -- that is the caller's/orchestrator's
    responsibility, per the task's read-only import boundary). The report
    renders whatever ``HoldoutResult`` it is given verbatim, including the
    case where ``holdout is None`` (no holdout has been run yet -- flagged
    explicitly in the report body, never faked).
  - Per-regime breakdown rows are sorted by descending ``time_share`` (the
    regimes covering the most test time lead the table), matching the
    ">15% of test time" framing used by the regime-balance guard.
  - The "winner vs production diff" lists only levers whose value differs
    (by more than a caller-configurable ``diff_tol``, default ``1e-9``,
    to avoid floating-point noise rows) -- an unchanged config renders an
    explicit "no parameter changes" line rather than an empty, ambiguous
    table.
  - If ``selection_outcome.winner is None`` (no candidate survived the
    guards), the report still renders (leaderboard + rejection reasons +
    holdout-if-any) so a "no viable candidate" study still produces an
    honest artifact rather than crashing the pipeline.

Windows-safe: pathlib only, explicit utf-8, no OS-version APIs, no optuna
import (this module never touches Optuna at all).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

from sentinel_engine.opt.registry import (
    DeflatedSharpeResult,
    TrialRegistry,
    deflated_sharpe_ratio,
)
from sentinel_engine.opt.selection import CandidateResult, SelectionOutcome

#: default tolerance for the winner-vs-production parameter diff table --
#: deltas at or below this magnitude are treated as "unchanged" (floating
#: point noise, not a real lever change).
DEFAULT_DIFF_TOL = 1e-9


@dataclass(frozen=True)
class HoldoutResult:
    """The single-touch, most-recent-slice holdout result (Fable Sec 2.6).

    Rendered verbatim in the report -- win or lose. ``passed`` is an
    optional caller-supplied honest verdict (e.g. "did it clear the same
    gates the objective enforces during selection?"); when omitted the
    report shows the metrics without asserting a pass/fail label (the
    numbers speak for themselves).
    """

    config_name: str
    period_start: str
    period_end: str
    metrics: Dict[str, float]
    passed: Optional[bool] = None
    notes: str = ""


@dataclass(frozen=True)
class RegimeMetrics:
    """One regime's metric breakdown for the report's per-regime section.

    Distinct from ``selection.RegimeResult`` (which only carries the J score
    needed by the regime-balance guard): this carries the *full* metric set
    (e.g. an ``objective.ObjectiveResult.metrics`` dict) a human reader wants
    to see per regime, per Fable Sec 2.10's "per-regime heatmap".
    """

    regime: str
    time_share: float
    metrics: Dict[str, float]


def _fmt(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _leaderboard_section(selection_outcome: SelectionOutcome) -> str:
    lines = ["## Leaderboard", ""]
    names = sorted(
        selection_outcome.median_J_by_name,
        key=lambda n: selection_outcome.median_J_by_name[n],
        reverse=True,
    )
    if not names:
        lines.append("_No candidates were evaluated in this study._")
        lines.append("")
        return "\n".join(lines)

    lines.append("| Candidate | Median fold J | Dominance vs production | Status |")
    lines.append("|---|---|---|---|")
    winner_name = selection_outcome.winner.name if selection_outcome.winner else None
    for name in names:
        median_j = selection_outcome.median_J_by_name.get(name, float("nan"))
        dominance = selection_outcome.dominance_by_name.get(name, float("nan"))
        if name == winner_name:
            status = "**WINNER**"
        elif name in selection_outcome.rejected:
            status = f"rejected -- {selection_outcome.rejected[name]}"
        else:
            status = "tie-pool candidate"
        lines.append(f"| {name} | {_fmt(median_j)} | {_fmt(dominance)} | {status} |")
    lines.append("")
    lines.append(f"**Selection outcome:** {selection_outcome.reason}")
    lines.append("")
    return "\n".join(lines)


def _diff_section(
    winner: Optional[CandidateResult],
    production_config: Mapping[str, float],
    diff_tol: float,
) -> str:
    lines = ["## Winner vs. production -- parameter diff", ""]
    if winner is None:
        lines.append("_No winner was selected -- no diff to report._")
        lines.append("")
        return "\n".join(lines)

    all_keys = sorted(set(winner.config.keys()) | set(production_config.keys()))
    rows = []
    for key in all_keys:
        prod_val = production_config.get(key)
        win_val = winner.config.get(key)
        if prod_val is None or win_val is None:
            changed = True
        else:
            try:
                changed = abs(float(win_val) - float(prod_val)) > diff_tol
            except (TypeError, ValueError):
                changed = win_val != prod_val
        if changed:
            rows.append((key, prod_val, win_val))

    if not rows:
        lines.append("_No parameter changes -- winner is identical to production._")
        lines.append("")
        return "\n".join(lines)

    lines.append("| Lever | Production | Winner |")
    lines.append("|---|---|---|")
    for key, prod_val, win_val in rows:
        lines.append(f"| {key} | {_fmt(prod_val)} | {_fmt(win_val)} |")
    lines.append("")
    return "\n".join(lines)


def _holdout_section(holdout: Optional[HoldoutResult]) -> str:
    lines = ["## Single-touch holdout result", ""]
    if holdout is None:
        lines.append(
            "_No holdout has been run yet for this study "
            "(deferred -- reported here honestly, not faked)._"
        )
        lines.append("")
        return "\n".join(lines)

    lines.append(f"Config: `{holdout.config_name}`")
    lines.append(f"Period: {holdout.period_start} -> {holdout.period_end}")
    if holdout.passed is not None:
        verdict = "PASSED" if holdout.passed else "FAILED"
        lines.append(f"Verdict: **{verdict}** (win-or-lose, reported as observed)")
    lines.append("")
    if holdout.metrics:
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        for key in sorted(holdout.metrics):
            lines.append(f"| {key} | {_fmt(holdout.metrics[key])} |")
        lines.append("")
    if holdout.notes:
        lines.append(f"Notes: {holdout.notes}")
        lines.append("")
    return "\n".join(lines)


def _regime_section(regime_metrics: Sequence[RegimeMetrics]) -> str:
    lines = ["## Per-regime metric breakdown", ""]
    if not regime_metrics:
        lines.append("_No per-regime breakdown available for this study._")
        lines.append("")
        return "\n".join(lines)

    ordered = sorted(regime_metrics, key=lambda rm: rm.time_share, reverse=True)
    metric_keys: list[str] = []
    for rm in ordered:
        for key in rm.metrics:
            if key not in metric_keys:
                metric_keys.append(key)

    header = ["Regime", "Time share"] + metric_keys
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for rm in ordered:
        row = [rm.regime, f"{rm.time_share:.2%}"]
        for key in metric_keys:
            row.append(_fmt(rm.metrics[key]) if key in rm.metrics else "--")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return "\n".join(lines)


def _dsr_section(dsr: Optional[DeflatedSharpeResult]) -> str:
    lines = ["## Deflated Sharpe ratio (honest, trial-count-penalized)", ""]
    if dsr is None:
        lines.append(
            "_DSR not computed for this study (no winner return series and no "
            "trial count were available -- reported as not computed, not "
            "omitted)._"
        )
        lines.append("")
        return "\n".join(lines)

    lines.append(f"- Observed Sharpe: {_fmt(dsr.sharpe)}")
    lines.append(f"- Trials searched: {dsr.n_trials}")
    lines.append(
        f"- Expected max Sharpe under the null (skill-less search): "
        f"{_fmt(dsr.expected_max_sharpe_null)}"
    )
    lines.append(f"- Deflated Sharpe ratio (DSR): {_fmt(dsr.dsr)}")
    lines.append(f"- **Honest p-value: {_fmt(dsr.p_value)}**")
    lines.append("")
    return "\n".join(lines)


def generate_report(
    *,
    study_id: str,
    registry: TrialRegistry,
    selection_outcome: SelectionOutcome,
    production_config: Mapping[str, float],
    holdout: Optional[HoldoutResult] = None,
    regime_metrics: Sequence[RegimeMetrics] = (),
    dsr: Optional[DeflatedSharpeResult] = None,
    winner_returns: Optional[Sequence[float]] = None,
    trial_sharpe_std: Optional[float] = None,
    out_path: Path | str,
    diff_tol: float = DEFAULT_DIFF_TOL,
    generated_at: Optional[str] = None,
) -> str:
    """Render and write a self-contained study report Markdown artifact.

    Args:
        study_id: study identifier (also used to look up the trial count in
            ``registry`` for the DSR, per Fable Sec 2.6/2.10).
        registry: the study's ``TrialRegistry`` (read-only -- only
            ``trial_count`` is called; trials themselves are not dumped into
            the report to keep it readable, the leaderboard already
            summarizes them).
        selection_outcome: Task 4.5's ``select_winner`` output.
        production_config: current-production lever values, for the diff.
        holdout: the single-touch holdout result, or ``None`` if not yet run
            (rendered honestly either way).
        regime_metrics: the winner's per-regime metric breakdown.
        dsr: a pre-computed ``DeflatedSharpeResult``. Takes precedence over
            ``winner_returns`` if both are supplied.
        winner_returns: the winner's per-fold/per-day return series, used to
            compute the DSR here (via ``registry.trial_count``) if ``dsr``
            was not supplied directly.
        trial_sharpe_std: passed through to ``deflated_sharpe_ratio`` when
            computing DSR from ``winner_returns``.
        out_path: destination file path for the artifact (parent directories
            created as needed).
        diff_tol: floating-point tolerance for the parameter-diff table.
        generated_at: optional caller-supplied timestamp/label for the
            report header (kept out of the default path for determinism --
            omit it, or pass a fixed string, for byte-identical reruns).

    Returns:
        The full Markdown report text (also written to ``out_path``).
    """
    if dsr is None and winner_returns is not None:
        n_trials = registry.trial_count(study_id)
        if n_trials >= 2 and len(winner_returns) >= 2:
            dsr = deflated_sharpe_ratio(
                winner_returns,
                n_trials,
                trial_sharpe_std=trial_sharpe_std,
            )

    winner = selection_outcome.winner
    n_trials_recorded = registry.trial_count(study_id)

    sections = [
        f"# Study report -- `{study_id}`",
        "",
        f"Trials recorded in registry: {n_trials_recorded}",
    ]
    if generated_at:
        sections.append(f"Generated: {generated_at}")
    sections.append("")
    sections.append(
        f"Winner: `{winner.name}`" if winner is not None else "Winner: **none selected**"
    )
    sections.append("")

    sections.append(_leaderboard_section(selection_outcome))
    sections.append(_diff_section(winner, production_config, diff_tol))
    sections.append(_holdout_section(holdout))
    sections.append(_regime_section(regime_metrics))
    sections.append(_dsr_section(dsr))

    text = "\n".join(sections).rstrip() + "\n"

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    return text
