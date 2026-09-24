"""Tests for sentinel_engine/opt/selection.py (P4.5).

All fixtures are synthetic, hand-crafted fold-result / regime-result / config
structures -- no real data, no golden fixtures, no live config, no optuna.
Machinery-only unit tests per the Phase-4 task brief. Each guard is exercised
both on a config crafted to FAIL it and on a healthy baseline that PASSES,
plus the top-level ``select_winner`` orchestrator and the minimum-change
tie-break.
"""

from __future__ import annotations

import math

import pytest

from sentinel_engine.opt.selection import (
    DEFAULT_DOMINANCE_THRESHOLD,
    CandidateResult,
    FoldResult,
    RegimeResult,
    SelectionOutcome,
    config_distance,
    dominance_rate,
    median_J,
    passes_dominance,
    plateau_check,
    regime_balance_check,
    select_minimum_change,
    select_winner,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _folds(candidate_Js, production_Js):
    assert len(candidate_Js) == len(production_Js)
    return [
        FoldResult(fold_index=i, candidate_J=c, production_J=p)
        for i, (c, p) in enumerate(zip(candidate_Js, production_Js))
    ]


def _healthy_folds(n=10):
    """Candidate consistently beats a flat production baseline."""
    return _folds(
        candidate_Js=[1.5 + 0.05 * i for i in range(n)],
        production_Js=[1.0] * n,
    )


# ---------------------------------------------------------------------------
# median_J / dominance_rate primitives
# ---------------------------------------------------------------------------


class TestMedianJ:
    def test_median_of_odd_count(self):
        folds = _folds([1.0, 5.0, 3.0], [0.0, 0.0, 0.0])
        assert median_J(folds) == 3.0

    def test_median_of_even_count_averages_middle_two(self):
        folds = _folds([1.0, 2.0, 3.0, 4.0], [0.0, 0.0, 0.0, 0.0])
        assert median_J(folds) == 2.5

    def test_median_robust_to_one_lucky_fold(self):
        # one huge outlier fold must not dominate the median the way it
        # would dominate a mean.
        folds = _folds([1.0, 1.1, 1.2, 100.0], [0.0, 0.0, 0.0, 0.0])
        med = median_J(folds)
        mean = sum(fr.candidate_J for fr in folds) / len(folds)
        assert med < mean
        assert med == pytest.approx(1.15)

    def test_empty_folds_returns_zero(self):
        assert median_J([]) == 0.0


# ---------------------------------------------------------------------------
# Guard 1: fold dominance (>=70%)
# ---------------------------------------------------------------------------


class TestDominanceGuard:
    def test_healthy_candidate_beats_production_every_fold(self):
        folds = _healthy_folds()
        assert dominance_rate(folds) == 1.0
        assert passes_dominance(folds, DEFAULT_DOMINANCE_THRESHOLD) is True

    def test_candidate_beating_production_in_under_70pct_folds_is_rejected(self):
        # 3 wins out of 10 folds == 30% dominance, well under the 70% bar.
        candidate_Js = [2.0, 2.0, 2.0] + [0.5] * 7
        production_Js = [1.0] * 10
        folds = _folds(candidate_Js, production_Js)

        assert dominance_rate(folds) == pytest.approx(0.30)
        assert passes_dominance(folds, DEFAULT_DOMINANCE_THRESHOLD) is False

    def test_exactly_70pct_passes_inclusive_threshold(self):
        candidate_Js = [2.0] * 7 + [0.5] * 3
        production_Js = [1.0] * 10
        folds = _folds(candidate_Js, production_Js)

        assert dominance_rate(folds) == pytest.approx(0.70)
        assert passes_dominance(folds, DEFAULT_DOMINANCE_THRESHOLD) is True

    def test_tie_on_a_fold_does_not_count_as_a_win(self):
        folds = _folds([1.0, 1.0, 1.0], [1.0, 1.0, 0.0])
        # only the 3rd fold strictly beats production -> 1/3
        assert dominance_rate(folds) == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------
# Guard 2: plateau check
# ---------------------------------------------------------------------------


class TestPlateauGuard:
    def test_cliff_edge_optimum_fails_plateau(self):
        """A config that scores well ONLY at the exact nominal point (any
        perturbation collapses the score) must fail the plateau guard."""
        nominal = {"ema_fast": 9.0, "rsi_period": 14.0}

        def cliff_score_fn(cfg):
            if cfg["ema_fast"] == nominal["ema_fast"] and cfg[
                "rsi_period"
            ] == nominal["rsi_period"]:
                return 10.0
            return 1.0  # 90% degradation off the exact nominal point

        result = plateau_check(nominal, cliff_score_fn)

        assert result.passed is False
        assert set(result.failing_levers) == {"ema_fast", "rsi_period"}
        assert result.worst_degradation_frac > 0.25

    def test_broad_plateau_passes(self):
        """A config whose score is flat/insensitive to +/-10% perturbation
        must pass -- this is the healthy case the guard should not punish."""
        nominal = {"ema_fast": 9.0, "rsi_period": 14.0}

        def flat_score_fn(cfg):
            # tiny, well within-tolerance sensitivity
            drift = abs(cfg["ema_fast"] - nominal["ema_fast"]) * 0.01
            drift += abs(cfg["rsi_period"] - nominal["rsi_period"]) * 0.01
            return 10.0 - drift

        result = plateau_check(nominal, flat_score_fn)

        assert result.passed is True
        assert result.failing_levers == []

    def test_nonpositive_baseline_conservatively_fails(self):
        nominal = {"ema_fast": 9.0}
        result = plateau_check(nominal, lambda cfg: -1.0)
        assert result.passed is False
        assert result.baseline_J == -1.0

    def test_zero_valued_lever_is_skipped_not_crashed(self):
        nominal = {"offset": 0.0, "ema_fast": 9.0}
        result = plateau_check(nominal, lambda cfg: 5.0)
        assert result.passed is True
        assert "offset" not in result.per_lever_J


# ---------------------------------------------------------------------------
# Guard 3: regime-balance
# ---------------------------------------------------------------------------


class TestRegimeBalanceGuard:
    def test_bull_only_config_fails_regime_balance(self):
        """Great in BULL (60% of test time) but catastrophic in BEAR (25%)
        and RANGE (15%) -- BEAR exceeds the 15% coverage threshold and is
        catastrophic, so the guard must reject."""
        regimes = [
            RegimeResult(regime="BULL", time_share=0.60, candidate_J=5.0),
            RegimeResult(regime="BEAR", time_share=0.25, candidate_J=-2.0),
            RegimeResult(regime="RANGE", time_share=0.15, candidate_J=0.5),
        ]
        result = regime_balance_check(regimes)

        assert result.passed is False
        assert "BEAR" in result.failing_regimes
        # RANGE is exactly at (not over) the 15% threshold -> exempt
        assert "RANGE" not in result.checked_regimes

    def test_balanced_config_passes_regime_balance(self):
        regimes = [
            RegimeResult(regime="BULL", time_share=0.40, candidate_J=2.0),
            RegimeResult(regime="BEAR", time_share=0.35, candidate_J=1.2),
            RegimeResult(regime="RANGE", time_share=0.25, candidate_J=0.8),
        ]
        result = regime_balance_check(regimes)

        assert result.passed is True
        assert result.failing_regimes == []

    def test_catastrophic_minor_regime_under_threshold_is_exempt(self):
        regimes = [
            RegimeResult(regime="BULL", time_share=0.90, candidate_J=5.0),
            RegimeResult(regime="EXTREME_VOL", time_share=0.10, candidate_J=-9.0),
        ]
        result = regime_balance_check(regimes)

        assert result.passed is True
        assert result.checked_regimes == ["BULL"]

    def test_no_regime_data_trivially_passes(self):
        result = regime_balance_check([])
        assert result.passed is True
        assert result.checked_regimes == []


# ---------------------------------------------------------------------------
# Guard 4: minimum-change prior among 1-SE ties
# ---------------------------------------------------------------------------


class TestMinimumChangePrior:
    def test_config_distance_zero_for_identical_configs(self):
        cfg = {"a": 1.0, "b": 2.0}
        assert config_distance(cfg, cfg) == 0.0

    def test_config_distance_scales_by_lever_range(self):
        production = {"a": 10.0, "b": 100.0}
        near = {"a": 11.0, "b": 100.0}  # 1-unit delta on 'a'
        far = {"a": 10.0, "b": 130.0}  # 30-unit delta on 'b'
        scales = {"a": 10.0, "b": 100.0}

        d_near = config_distance(near, production, scales)
        d_far = config_distance(far, production, scales)
        assert d_near < d_far

    def test_among_1se_ties_the_minimum_change_config_is_chosen(self):
        production_config = {"ema_fast": 9.0, "rsi_period": 14.0}

        # Both candidates have (nearly) the same median J, comfortably
        # within 1 SE of each other -- a genuine statistical tie -- but
        # candidate B is a much bigger departure from production.
        close_candidate = CandidateResult(
            name="close",
            config={"ema_fast": 9.5, "rsi_period": 14.5},
            fold_results=_folds([2.0, 2.05, 1.95, 2.0], [1.0] * 4),
        )
        far_candidate = CandidateResult(
            name="far",
            config={"ema_fast": 25.0, "rsi_period": 40.0},
            fold_results=_folds([2.0, 2.05, 1.95, 2.0], [1.0] * 4),
        )

        winner = select_minimum_change(
            [close_candidate, far_candidate], production_config
        )
        assert winner.name == "close"

    def test_select_winner_end_to_end_picks_minimum_change_tie(self):
        production_config = {"ema_fast": 9.0, "rsi_period": 14.0}

        close_candidate = CandidateResult(
            name="close",
            config={"ema_fast": 9.5, "rsi_period": 14.5},
            fold_results=_folds([2.0, 2.1, 1.9, 2.0, 2.05], [1.0] * 5),
            regime_results=[
                RegimeResult(regime="BULL", time_share=0.5, candidate_J=2.0),
                RegimeResult(regime="BEAR", time_share=0.5, candidate_J=1.5),
            ],
        )
        far_candidate = CandidateResult(
            name="far",
            config={"ema_fast": 30.0, "rsi_period": 55.0},
            fold_results=_folds([2.0, 2.1, 1.9, 2.0, 2.05], [1.0] * 5),
            regime_results=[
                RegimeResult(regime="BULL", time_share=0.5, candidate_J=2.0),
                RegimeResult(regime="BEAR", time_share=0.5, candidate_J=1.5),
            ],
        )

        outcome = select_winner([close_candidate, far_candidate], production_config)

        assert isinstance(outcome, SelectionOutcome)
        assert outcome.winner is not None
        assert outcome.winner.name == "close"
        assert set(outcome.tie_pool) == {"close", "far"}
        assert outcome.rejected == {}


# ---------------------------------------------------------------------------
# select_winner: guard integration / rejection paths
# ---------------------------------------------------------------------------


class TestSelectWinnerIntegration:
    def test_rejects_low_dominance_candidate_even_with_great_median_J(self):
        production_config = {"ema_fast": 9.0}
        low_dominance = CandidateResult(
            name="lucky_but_inconsistent",
            config={"ema_fast": 9.0},
            fold_results=_folds(
                candidate_Js=[100.0, 0.1, 0.1, 0.1, 0.1],
                production_Js=[1.0] * 5,
            ),
        )
        outcome = select_winner([low_dominance], production_config)

        assert outcome.winner is None
        assert "lucky_but_inconsistent" in outcome.rejected
        assert "fold-dominance" in outcome.rejected["lucky_but_inconsistent"]

    def test_rejects_regime_catastrophic_candidate(self):
        production_config = {"ema_fast": 9.0}
        bull_only = CandidateResult(
            name="bull_only",
            config={"ema_fast": 9.0},
            fold_results=_healthy_folds(),
            regime_results=[
                RegimeResult(regime="BULL", time_share=0.5, candidate_J=5.0),
                RegimeResult(regime="BEAR", time_share=0.5, candidate_J=-3.0),
            ],
        )
        outcome = select_winner([bull_only], production_config)

        assert outcome.winner is None
        assert "regime-balance" in outcome.rejected["bull_only"]

    def test_rejects_cliff_optimum_when_score_fn_supplied(self):
        production_config = {"ema_fast": 9.0}
        nominal = {"ema_fast": 9.0}

        def cliff_score_fn(cfg):
            return 10.0 if cfg["ema_fast"] == nominal["ema_fast"] else 0.5

        cliff_candidate = CandidateResult(
            name="cliff",
            config=nominal,
            fold_results=_healthy_folds(),
        )
        outcome = select_winner(
            [cliff_candidate], production_config, score_fn=cliff_score_fn
        )

        assert outcome.winner is None
        assert "plateau" in outcome.rejected["cliff"]

    def test_no_survivors_yields_none_winner_with_reason(self):
        production_config = {"ema_fast": 9.0}
        bad = CandidateResult(
            name="bad",
            config={"ema_fast": 9.0},
            fold_results=_folds([0.1] * 5, [1.0] * 5),  # always loses
        )
        outcome = select_winner([bad], production_config)
        assert outcome.winner is None
        assert outcome.reason
