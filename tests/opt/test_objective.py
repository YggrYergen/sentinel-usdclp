"""Tests for sentinel_engine/opt/objective.py (P4.2).

All fixtures are synthetic, hand-crafted trade-R-multiple lists -- no real
data, no golden fixtures, no live config. Machinery-only unit tests per the
Phase-4 task brief.
"""

from __future__ import annotations

import math

import pytest

from sentinel_engine.opt.objective import (
    DEFAULT_N_MIN,
    DEFAULT_PF_CAP,
    DEFAULT_WIN_RATE_MIN,
    PENALTY_SCORE,
    objective,
)


def _healthy_trades(n=60):
    """60 trades, ~55% win rate, moderate wins/losses -> should pass gates."""
    trades = []
    for i in range(n):
        if i % 20 < 11:  # 11/20 = 55% wins
            trades.append(1.2)
        else:
            trades.append(-1.0)
    return trades


class TestHealthyTradeSet:
    def test_healthy_set_passes_gates_and_scores_well(self):
        trades = _healthy_trades()
        result = objective(trades, n_ref=60)

        assert result.gates_passed is True
        assert result.violations == []
        assert result.score > 0.0
        assert result.metrics["n_trades"] == 60
        assert result.metrics["win_rate"] == pytest.approx(0.55)
        assert result.metrics["net_pnl_R"] > 0

    def test_full_metric_set_is_reported(self):
        trades = _healthy_trades()
        result = objective(trades, n_ref=60, daily_returns_R=[0.5, -0.2, 0.8, 0.1])

        for key in (
            "net_pnl_R",
            "win_rate",
            "maxDD_R",
            "avg_R",
            "profit_factor",
            "profit_factor_capped",
            "sharpe_daily_R",
            "n_trades",
        ):
            assert key in result.metrics

        # daily Sharpe supplied explicitly -> not the trade-level fallback
        assert result.metrics["sharpe_is_trade_level"] is False


class TestFlukeChasing:
    """Degeneracy (a): a few lucky high-R trades with too-few trades must
    NOT score well -- either the min-trades gate rejects them outright, or
    (if they clear n_min) the PF cap prevents chasing a handful of huge
    winners into an inflated score.
    """

    def test_few_lucky_trades_below_n_min_are_gated(self):
        # 5 trades, all huge wins -- a classic fluke: uncapped PF would be
        # "infinite" (no losses) and tiny-n would still look amazing without
        # gating.
        trades = [10.0, 12.0, 8.0, 15.0, 9.0]
        result = objective(trades, n_ref=60)

        assert len(trades) < DEFAULT_N_MIN
        assert result.gates_passed is False
        assert result.score == PENALTY_SCORE
        assert any("n_trades" in v for v in result.violations)

    @staticmethod
    def _fluke_trades(n=DEFAULT_N_MIN):
        # 3 massive lucky wins + enough small wins to clear the win-rate
        # gate, plus losses -- isolates the PF-cap degeneracy from the
        # win-rate gate (a *different* guard, tested separately below).
        huge_wins = [50.0, 60.0, 40.0]
        n_losses = (n - 3) // 2
        n_small_wins = n - 3 - n_losses
        small_wins = [0.1] * n_small_wins
        losses = [-1.0] * n_losses
        return huge_wins + small_wins + losses

    def test_pf_cap_prevents_uncapped_fluke_from_dominating(self):
        # Even granting enough trades to clear n_min and win-rate, a
        # handful of massive wins would produce an enormous *raw* PF; the
        # capped score must not reflect that raw magnitude.
        n = DEFAULT_N_MIN
        trades = self._fluke_trades(n)
        result = objective(trades, n_ref=n)

        assert result.gates_passed is True
        assert result.metrics["profit_factor"] > DEFAULT_PF_CAP * 3  # raw PF is huge
        assert result.metrics["profit_factor_capped"] == DEFAULT_PF_CAP
        # capped score bounded by pf_cap * sqrt(ratio); ratio here is 1.0
        assert result.score == pytest.approx(DEFAULT_PF_CAP)

    def test_fluke_score_is_far_below_healthy_recurring_edge(self):
        # A "fluke" that does clear n_min (capped) still should not out-rank
        # a healthy, recurring, higher-frequency edge relative to a larger
        # n_ref (frequency matters -- sqrt(n) term).
        n = DEFAULT_N_MIN
        fluke = self._fluke_trades(n)
        fluke_result = objective(fluke, n_ref=200)  # reference policy fires far more often

        healthy = _healthy_trades(n=200)
        healthy_result = objective(healthy, n_ref=200)

        assert fluke_result.gates_passed is True
        assert healthy_result.gates_passed is True
        # fluke's frequency ratio term is starved (n/n_ref = 60/200)
        assert fluke_result.score < healthy_result.score


class TestTradeStarvation:
    """Degeneracy (b): below the statistical trade-count floor -> rejected,
    regardless of how good the few trades looked.
    """

    def test_zero_trades_rejected(self):
        result = objective([], n_ref=60)
        assert result.gates_passed is False
        assert result.score == PENALTY_SCORE
        assert any("n_trades" in v for v in result.violations)

    def test_just_below_floor_rejected(self):
        trades = [1.5] * (DEFAULT_N_MIN - 1)
        result = objective(trades, n_ref=60)
        assert result.gates_passed is False
        assert result.score == PENALTY_SCORE

    def test_exactly_at_floor_not_rejected_on_count_alone(self):
        # boundary check: n_min itself must pass the count gate (>=, not >).
        trades = _healthy_trades(n=DEFAULT_N_MIN)
        result = objective(trades, n_ref=DEFAULT_N_MIN)
        assert not any("n_trades" in v for v in result.violations)
        assert result.gates_passed is True


class TestConstraintGates:
    def test_low_win_rate_rejected(self):
        # 60 trades, only 20% wins -> below default 0.35 floor, even though
        # PnL could still be net positive with big winners.
        trades = ([5.0] * 12) + ([-1.0] * 48)
        assert (12 / 60) < DEFAULT_WIN_RATE_MIN
        result = objective(trades, n_ref=60)

        assert result.gates_passed is False
        assert result.score == PENALTY_SCORE
        assert any("win_rate" in v for v in result.violations)

    def test_excess_drawdown_vs_baseline_rejected(self):
        # Construct a trade sequence whose cumulative-R equity curve dips
        # far below what 1.25x a small baseline maxDD would allow.
        trades = [3.0, -5.0, -5.0, -5.0] + [1.2, -1.0] * 30
        result = objective(trades, n_ref=60, baseline_maxDD_R=2.0)

        assert result.metrics["maxDD_R"] > 1.25 * 2.0
        assert result.gates_passed is False
        assert result.score == PENALTY_SCORE
        assert any("maxDD" in v for v in result.violations)

    def test_maxdd_gate_skipped_when_no_baseline_supplied(self):
        trades = _healthy_trades()
        result = objective(trades, n_ref=60)  # no baseline_maxDD_R
        assert not any("maxDD" in v for v in result.violations)
        assert any("maxDD" in s for s in result.constraints_skipped)

    def test_within_baseline_dd_passes(self):
        trades = _healthy_trades()
        result = objective(trades, n_ref=60, baseline_maxDD_R=100.0)
        assert not any("maxDD" in v for v in result.violations)


class TestTradeCountRatio:
    def test_higher_frequency_at_same_quality_scores_higher(self):
        # Same per-trade quality, more trades relative to n_ref -> higher
        # sqrt(n) reward (Fable: "a scalper's edge must recur").
        low_freq = _healthy_trades(n=DEFAULT_N_MIN)
        high_freq = _healthy_trades(n=DEFAULT_N_MIN * 4)

        low_result = objective(low_freq, n_ref=DEFAULT_N_MIN * 4)
        high_result = objective(high_freq, n_ref=DEFAULT_N_MIN * 4)

        assert high_result.gates_passed is True
        assert low_result.gates_passed is True
        assert high_result.score > low_result.score

    def test_n_ref_zero_does_not_crash_and_yields_zero_ratio(self):
        trades = _healthy_trades()
        result = objective(trades, n_ref=0)
        assert result.metrics["trade_count_ratio"] == 0.0
        # ratio term is zero -> capped score collapses to zero even though
        # gates pass (no reference signal to compare against).
        assert result.gates_passed is True
        assert result.score == pytest.approx(0.0)


class TestDrawdownAndSharpeCalculations:
    def test_max_drawdown_is_peak_to_trough_on_equity_curve(self):
        # equity path: 0 -> 2 -> 1 -> 4 -> 0  => max dd = 4 (from peak 4 to 0)
        trades = [2.0, -1.0, 3.0, -4.0]
        result = objective(trades, n_ref=4)
        assert result.metrics["maxDD_R"] == pytest.approx(4.0)

    def test_trade_level_sharpe_fallback_flagged(self):
        trades = _healthy_trades()
        result = objective(trades, n_ref=60)
        assert result.metrics["sharpe_is_trade_level"] is True
        assert math.isfinite(result.metrics["sharpe_daily_R"])

    def test_all_wins_profit_factor_is_capped_not_infinite(self):
        trades = [1.0] * DEFAULT_N_MIN
        result = objective(trades, n_ref=DEFAULT_N_MIN)
        assert math.isfinite(result.metrics["profit_factor"])
        assert result.metrics["profit_factor_capped"] == DEFAULT_PF_CAP
