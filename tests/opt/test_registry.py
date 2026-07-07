"""
Tests for sentinel_engine.opt.registry: SQLite+Parquet trial registry and
the deflated Sharpe ratio.

All fixtures are synthetic and crafted in this file -- no real study, no
real data lake. Machinery-only tests per the Phase-4 task-4.6 brief.
"""
from __future__ import annotations

import math
import sqlite3

import numpy as np
import pytest

from sentinel_engine.opt.registry import (
    DeflatedSharpeResult,
    TrialRegistry,
    deflated_sharpe_ratio,
)


# --------------------------------------------------------------------------
# Round-trip: write N trials, read them back identical.
# --------------------------------------------------------------------------


def _make_registry(tmp_path):
    return TrialRegistry(
        db_path=tmp_path / "lab_registry.db",
        parquet_dir=tmp_path / "parquet",
    )


def test_round_trip_params_and_metrics(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_study("study-a", seed=42, notes="synthetic fixture")

    params = {"ema_fast": 9, "ema_slow": 21, "rsi_period": 14, "label": "nq100_stage1"}
    metrics = {
        "pnl_R": 12.5,
        "profit_factor": 1.8,
        "win_rate": 0.55,
        "maxDD_R": -3.2,
        "sharpe": 0.9,
        "n_trades": 240,
        "is_valid": True,
        "notes": None,
    }

    trial_id = reg.record_trial("study-a", params, metrics)
    got = reg.get_trial("study-a", trial_id)

    assert got.params == params
    assert got.metrics == metrics
    assert got.study_id == "study-a"
    assert got.trial_index == 0
    assert got.arrays == {}
    reg.close()


def test_round_trip_arrays_via_parquet(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_study("study-b")

    equity_curve = [100.0, 101.5, 99.25, 103.0, 97.75, 110.125]
    r_multiples = [0.5, -1.0, 1.25, -0.25]  # deliberately different length

    trial_id = reg.record_trial(
        "study-b",
        params={"tp_atr": 2.0, "sl_atr": 1.0},
        metrics={"pnl_R": 0.5},
        arrays={"equity_curve": equity_curve, "r_multiples": r_multiples},
    )

    got = reg.get_trial("study-b", trial_id)
    assert got.arrays["equity_curve"] == pytest.approx(equity_curve)
    assert got.arrays["r_multiples"] == pytest.approx(r_multiples)

    # Parquet file exists on disk under parquet_dir and is addressable.
    parquet_files = list((tmp_path / "parquet").glob("*.parquet"))
    assert len(parquet_files) == 1
    reg.close()


def test_round_trip_many_trials_all_identical(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_study("study-c", seed=7)

    n = 25
    recorded = []
    for i in range(n):
        params = {"idx": i, "weight": 0.1 * i}
        metrics = {"sharpe": math.sin(i) * 0.1, "n_trades": 50 + i}
        arrays = {"curve": [float(i), float(i) + 0.5, float(i) + 1.0]}
        trial_id = reg.record_trial("study-c", params, metrics, arrays)
        recorded.append((trial_id, params, metrics, arrays))

    all_trials = reg.get_all_trials("study-c")
    assert len(all_trials) == n
    # trial_index assigned in insertion order, 0..n-1
    assert [t.trial_index for t in all_trials] == list(range(n))

    for (trial_id, params, metrics, arrays), record in zip(recorded, all_trials):
        assert record.trial_id == trial_id
        assert record.params == params
        assert record.metrics == metrics
        assert record.arrays["curve"] == pytest.approx(arrays["curve"])

    reg.close()


def test_get_trial_missing_raises_keyerror(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_study("study-d")
    with pytest.raises(KeyError):
        reg.get_trial("study-d", 999)
    reg.close()


# --------------------------------------------------------------------------
# Per-study trial count is persisted and correct.
# --------------------------------------------------------------------------


def test_trial_count_persisted_and_scoped_per_study(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_study("study-x")
    reg.ensure_study("study-y")

    assert reg.trial_count("study-x") == 0
    assert reg.trial_count("study-y") == 0

    for i in range(5):
        reg.record_trial("study-x", {"i": i}, {"sharpe": 0.1})
    for i in range(3):
        reg.record_trial("study-y", {"i": i}, {"sharpe": 0.2})

    assert reg.trial_count("study-x") == 5
    assert reg.trial_count("study-y") == 3
    reg.close()


def test_trial_count_survives_reconnect(tmp_path):
    db_path = tmp_path / "lab_registry.db"
    parquet_dir = tmp_path / "parquet"

    reg1 = TrialRegistry(db_path=db_path, parquet_dir=parquet_dir)
    reg1.ensure_study("study-z")
    for i in range(4):
        reg1.record_trial("study-z", {"i": i}, {"sharpe": 0.1 * i})
    reg1.close()

    reg2 = TrialRegistry(db_path=db_path, parquet_dir=parquet_dir)
    assert reg2.trial_count("study-z") == 4
    trials = reg2.get_all_trials("study-z")
    assert len(trials) == 4
    reg2.close()


def test_sqlite_row_count_matches_registry_count(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_study("study-q")
    for i in range(6):
        reg.record_trial("study-q", {"i": i}, {"sharpe": 0.05 * i})

    conn = sqlite3.connect(str(tmp_path / "lab_registry.db"))
    (raw_count,) = conn.execute(
        "SELECT COUNT(*) FROM trials WHERE study_id = ?", ("study-q",)
    ).fetchone()
    conn.close()

    assert raw_count == reg.trial_count("study-q") == 6
    reg.close()


# --------------------------------------------------------------------------
# Deflated Sharpe ratio.
# --------------------------------------------------------------------------


def _synthetic_winner_returns(seed: int = 0, n: int = 60, mean: float = 0.05, std: float = 0.9):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(n) * std + mean).tolist()


def test_dsr_p_value_in_unit_interval():
    returns = _synthetic_winner_returns()
    result = deflated_sharpe_ratio(returns, n_trials=50, trial_sharpe_std=0.3)
    assert isinstance(result, DeflatedSharpeResult)
    assert 0.0 <= result.dsr <= 1.0
    assert 0.0 <= result.p_value <= 1.0
    assert result.p_value == pytest.approx(1.0 - result.dsr)


def test_dsr_decreases_as_trial_count_rises():
    # Same crafted winner return series; only the trial count searched to
    # find it changes. Deflation must actually bite: more trials tried ->
    # higher bar for luck -> lower deflated Sharpe / higher p-value.
    returns = _synthetic_winner_returns(seed=1, n=80, mean=0.12, std=1.0)

    dsr_few = deflated_sharpe_ratio(returns, n_trials=5, trial_sharpe_std=0.25)
    dsr_some = deflated_sharpe_ratio(returns, n_trials=100, trial_sharpe_std=0.25)
    dsr_many = deflated_sharpe_ratio(returns, n_trials=5000, trial_sharpe_std=0.25)

    assert dsr_few.expected_max_sharpe_null < dsr_some.expected_max_sharpe_null < dsr_many.expected_max_sharpe_null
    assert dsr_few.dsr > dsr_some.dsr > dsr_many.dsr
    assert dsr_few.p_value < dsr_some.p_value < dsr_many.p_value


def test_dsr_requires_at_least_two_trials():
    returns = _synthetic_winner_returns()
    with pytest.raises(ValueError):
        deflated_sharpe_ratio(returns, n_trials=1)


def test_dsr_requires_at_least_two_observations():
    with pytest.raises(ValueError):
        deflated_sharpe_ratio([0.1], n_trials=10)


def test_dsr_rejects_zero_variance_returns():
    with pytest.raises(ValueError):
        deflated_sharpe_ratio([1.0, 1.0, 1.0, 1.0], n_trials=10)


def test_dsr_high_sharpe_beats_low_sharpe_at_equal_trial_count():
    strong = _synthetic_winner_returns(seed=2, n=100, mean=0.3, std=0.8)
    weak = _synthetic_winner_returns(seed=3, n=100, mean=0.01, std=0.8)

    dsr_strong = deflated_sharpe_ratio(strong, n_trials=200, trial_sharpe_std=0.3)
    dsr_weak = deflated_sharpe_ratio(weak, n_trials=200, trial_sharpe_std=0.3)

    assert dsr_strong.dsr > dsr_weak.dsr


def test_dsr_default_trial_sharpe_std_is_conservative_placeholder():
    # When the caller has no empirical spread of trial Sharpes yet, the
    # function should still run (conservative variance=1.0 placeholder)
    # rather than raising.
    returns = _synthetic_winner_returns(seed=4, n=40, mean=0.1, std=0.9)
    result = deflated_sharpe_ratio(returns, n_trials=30)
    assert 0.0 <= result.dsr <= 1.0


# --------------------------------------------------------------------------
# End-to-end: registry-derived trial count feeds DSR deflation.
# --------------------------------------------------------------------------


def test_registry_trial_count_feeds_dsr_end_to_end(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_study("study-e2e", seed=99)

    rng = np.random.default_rng(123)
    trial_sharpes = []
    winner_returns = None
    best_sharpe = -math.inf

    for i in range(40):
        returns = (rng.standard_normal(50) * 1.0 + rng.normal(0.0, 0.05)).tolist()
        sharpe = float(np.mean(returns) / np.std(returns, ddof=1))
        trial_sharpes.append(sharpe)
        reg.record_trial(
            "study-e2e",
            params={"trial": i},
            metrics={"sharpe": sharpe},
            arrays={"returns": returns},
        )
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            winner_returns = returns

    n_trials = reg.trial_count("study-e2e")
    assert n_trials == 40

    trial_sharpe_std = float(np.std(trial_sharpes, ddof=1))
    result = deflated_sharpe_ratio(
        winner_returns, n_trials=n_trials, trial_sharpe_std=trial_sharpe_std
    )
    assert 0.0 <= result.dsr <= 1.0
    assert 0.0 <= result.p_value <= 1.0

    # Re-running DSR as if 10x more trials had been searched for the same
    # winner must deflate further (lower dsr) -- the trial-count penalty
    # composes correctly with data pulled straight out of the registry.
    result_more_trials = deflated_sharpe_ratio(
        winner_returns, n_trials=n_trials * 10, trial_sharpe_std=trial_sharpe_std
    )
    assert result_more_trials.dsr <= result.dsr

    reg.close()
