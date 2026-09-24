"""Tests for sentinel_engine/opt/report.py (P4.7).

END-TO-END SMOKE on a SMALL SYNTHETIC slice, per the task brief: craft tiny
synthetic price+trade data, run a minimal study through
walkforward -> objective -> registry -> selection -> report, and assert the
report contains the holdout result, per-regime section, and a DSR p-value.

This is a MACHINERY smoke test only -- no real optimization study, no real
price lake, no golden fixtures. All data is synthetic and built in this file.

FLAG: the real study on real broker prices is deferred to the real-data
optimization run (out of scope for this machinery task); this test only
proves the plumbing from walk-forward through to a written report artifact.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sentinel_engine.opt.objective import objective
from sentinel_engine.opt.registry import TrialRegistry, deflated_sharpe_ratio
from sentinel_engine.opt.report import (
    HoldoutResult,
    RegimeMetrics,
    generate_report,
)
from sentinel_engine.opt.selection import (
    CandidateResult,
    FoldResult,
    RegimeResult,
    select_winner,
)
from sentinel_engine.opt.walkforward import anchored_walkforward


# ---------------------------------------------------------------------------
# Synthetic fixtures: tiny price+trade data, hand-crafted and deterministic.
# ---------------------------------------------------------------------------


def _synthetic_timeline(n_days: int = 240) -> list[datetime]:
    start = datetime(2024, 1, 1)
    return [start + timedelta(days=i) for i in range(n_days)]


def _synthetic_trades_R(rng: random.Random, n: int, edge: float) -> list[float]:
    """Deterministic synthetic R-multiple trade series with a fixed edge.

    Not real trades/prices -- a hand-crafted synthetic distribution shaped so
    the "winner" candidate has a real, reproducible edge over "production"
    and clears the objective's gates (n_min, win_rate_min).
    """
    trades = []
    for _ in range(n):
        if rng.random() < 0.5 + edge:
            trades.append(rng.uniform(0.5, 2.0))  # win
        else:
            trades.append(-rng.uniform(0.5, 1.0))  # loss
    return trades


# ---------------------------------------------------------------------------
# The end-to-end smoke test.
# ---------------------------------------------------------------------------


def test_full_study_pipeline_end_to_end_report(tmp_path: Path):
    rng = random.Random(1234)

    timeline = _synthetic_timeline(n_days=240)
    folds = anchored_walkforward(
        timeline,
        test_span=timedelta(days=60),
        step=timedelta(days=60),
        embargo=timedelta(days=1),
    )
    assert len(folds) >= 2, "synthetic timeline must yield >=2 walk-forward folds"

    registry = TrialRegistry(
        db_path=tmp_path / "lab_registry.db",
        parquet_dir=tmp_path / "parquet",
    )
    study_id = "smoke-study-xauusd"
    registry.ensure_study(study_id, seed=1234, notes="synthetic smoke fixture")

    production_config = {"ema_fast": 9.0, "ema_slow": 21.0, "alert_threshold": 0.55}
    candidate_config = {"ema_fast": 8.0, "ema_slow": 21.0, "alert_threshold": 0.60}

    candidate_fold_results = []
    production_fold_results = []
    candidate_returns = []

    for fold in folds:
        cand_trades = _synthetic_trades_R(rng, n=40, edge=0.20)
        prod_trades = _synthetic_trades_R(rng, n=40, edge=0.02)

        cand_result = objective(cand_trades, n_ref=40)
        prod_result = objective(prod_trades, n_ref=40)

        registry.record_trial(
            study_id,
            params=candidate_config,
            metrics={**cand_result.metrics, "fold_index": fold.index},
            arrays={"trades_R": cand_trades},
        )
        registry.record_trial(
            study_id,
            params=production_config,
            metrics={**prod_result.metrics, "fold_index": fold.index},
        )

        candidate_fold_results.append(
            FoldResult(
                fold_index=fold.index,
                candidate_J=cand_result.score,
                production_J=prod_result.score,
            )
        )
        production_fold_results.append(prod_result.score)
        # Use net PnL (R) rather than the (intentionally capped) objective
        # score for the DSR input series -- the score is deliberately
        # ceiling-clipped (PF cap) and degenerates to zero variance on a
        # tiny synthetic fixture, whereas net PnL varies fold to fold, which
        # is what a Sharpe/DSR computation actually needs.
        candidate_returns.append(cand_result.metrics["net_pnl_R"])

    # -- regime slices (synthetic: split each fold's trades into two toy
    # regimes) feeding both the selection guard and the report breakdown --
    regime_results = [
        RegimeResult(regime="TREND", time_share=0.65, candidate_J=1.4, production_J=1.0),
        RegimeResult(regime="RANGE", time_share=0.35, candidate_J=1.1, production_J=0.9),
    ]

    candidate = CandidateResult(
        name="candidate-A",
        config=candidate_config,
        fold_results=candidate_fold_results,
        regime_results=regime_results,
    )

    outcome = select_winner([candidate], production_config)
    assert outcome.winner is not None, "synthetic candidate must beat synthetic production"
    assert outcome.winner.name == "candidate-A"

    # -- single-touch holdout: one more synthetic slice, touched once --
    holdout_trades = _synthetic_trades_R(rng, n=35, edge=0.15)
    holdout_obj = objective(holdout_trades, n_ref=35)
    holdout = HoldoutResult(
        config_name=candidate.name,
        period_start="2024-11-01",
        period_end="2024-12-31",
        metrics=holdout_obj.metrics,
        passed=holdout_obj.gates_passed,
    )

    regime_metrics = [
        RegimeMetrics(
            regime="TREND",
            time_share=0.65,
            metrics={"win_rate": 0.55, "profit_factor_capped": 1.8, "n_trades": 26},
        ),
        RegimeMetrics(
            regime="RANGE",
            time_share=0.35,
            metrics={"win_rate": 0.45, "profit_factor_capped": 1.2, "n_trades": 14},
        ),
    ]

    n_trials = registry.trial_count(study_id)
    dsr_result = deflated_sharpe_ratio(candidate_returns, n_trials)

    out_path = tmp_path / "reports" / f"{study_id}.md"
    report_text = generate_report(
        study_id=study_id,
        registry=registry,
        selection_outcome=outcome,
        production_config=production_config,
        holdout=holdout,
        regime_metrics=regime_metrics,
        dsr=dsr_result,
        out_path=out_path,
        generated_at="2026-07-07T00:00:00Z",
    )

    registry.close()

    # -- artifact was actually written, self-contained, utf-8 --
    assert out_path.exists()
    written_text = out_path.read_text(encoding="utf-8")
    assert written_text == report_text

    # -- required content per the task brief --
    assert "candidate-A" in report_text
    assert "WINNER" in report_text

    # holdout result present, reported win-or-lose (verbatim metrics)
    assert "Single-touch holdout result" in report_text
    assert "2024-11-01" in report_text and "2024-12-31" in report_text
    assert f"{holdout_obj.metrics['net_pnl_R']:.4f}" in report_text

    # per-regime section present with both synthetic regimes
    assert "Per-regime metric breakdown" in report_text
    assert "TREND" in report_text
    assert "RANGE" in report_text

    # honest DSR p-value present
    assert "Deflated Sharpe ratio" in report_text
    assert "Honest p-value" in report_text
    assert f"{dsr_result.p_value:.4f}" in report_text

    # winner-vs-production diff present (ema_fast and alert_threshold changed)
    assert "parameter diff" in report_text
    assert "ema_fast" in report_text
    assert "alert_threshold" in report_text


def test_report_renders_honestly_with_no_winner_and_no_holdout(tmp_path: Path):
    """If no candidate survives selection and no holdout has run yet, the
    report must say so explicitly rather than fabricate or crash."""
    registry = TrialRegistry(
        db_path=tmp_path / "lab_registry.db",
        parquet_dir=tmp_path / "parquet",
    )
    study_id = "smoke-study-empty"
    registry.ensure_study(study_id, seed=7)

    production_config = {"ema_fast": 9.0}
    failing_candidate = CandidateResult(
        name="candidate-fail",
        config={"ema_fast": 8.0},
        fold_results=[
            FoldResult(fold_index=0, candidate_J=0.5, production_J=1.0),
            FoldResult(fold_index=1, candidate_J=0.4, production_J=1.0),
        ],
    )
    outcome = select_winner([failing_candidate], production_config)
    assert outcome.winner is None

    out_path = tmp_path / "reports" / f"{study_id}.md"
    report_text = generate_report(
        study_id=study_id,
        registry=registry,
        selection_outcome=outcome,
        production_config=production_config,
        out_path=out_path,
    )
    registry.close()

    assert "no winner selected" in report_text.lower() or "**none selected**" in report_text
    assert "no holdout has been run yet" in report_text.lower()
    assert "not computed" in report_text.lower()
    assert out_path.exists()
