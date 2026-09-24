"""Adversarial tests for sentinel_engine.opt.search (Task 4.4).

All objectives here are crafted synthetic convex functions over plain param
dicts -- no real replay, no price lake, no golden fixtures, no live config.
optuna is NOT installed in this environment, so every test exercises the
random-search-floor path (the module's optuna-guarded TPE path is exercised
only indirectly via ``staged_search(..., use_tpe=True)``'s fallback).
"""

from __future__ import annotations

import math

import pytest

from sentinel_engine.opt.search import (
    LeverGroup,
    ParamSpec,
    StageResult,
    _HAS_OPTUNA,
    no_signal_flag,
    random_search_floor,
    staged_search,
    tpe_search,
    OptunaNotAvailableError,
)


# ---------------------------------------------------------------------------
# helpers: crafted synthetic convex objectives
# ---------------------------------------------------------------------------


def _neg_quadratic_bowl(target: dict) -> callable:
    """Returns an objective_fn(params) -> float with a single known maximum
    at ``target`` (a downward paraboloid: 0 at the optimum, negative
    elsewhere). Convex (concave for maximization), unimodal, noise-free.
    """

    def _fn(params: dict) -> float:
        # params.get(k, v): a dimension not yet present (earlier stage of a
        # staged search hasn't tuned it yet) contributes zero penalty rather
        # than crashing -- models "at its as-yet-untuned optimum".
        return -sum((params.get(k, v) - v) ** 2 for k, v in target.items())

    return _fn


# ---------------------------------------------------------------------------
# 1. Dimensionality cap: LeverGroup enforces 3-8 dims/fit (Fable Sec 2.5 /
#    Sec 4 item 2) at construction time.
# ---------------------------------------------------------------------------


def test_lever_group_rejects_too_few_dims():
    with pytest.raises(ValueError):
        LeverGroup(name="tiny", params=[ParamSpec("a", 0, 1), ParamSpec("b", 0, 1)])


def test_lever_group_rejects_too_many_dims():
    params = [ParamSpec(f"p{i}", 0, 1) for i in range(9)]
    with pytest.raises(ValueError):
        LeverGroup(name="huge", params=params)


def test_lever_group_accepts_boundary_dims_3_and_8():
    g3 = LeverGroup(name="g3", params=[ParamSpec(f"p{i}", 0, 1) for i in range(3)])
    g8 = LeverGroup(name="g8", params=[ParamSpec(f"p{i}", 0, 1) for i in range(8)])
    assert len(g3.params) == 3
    assert len(g8.params) == 8


def test_lever_group_rejects_duplicate_param_names():
    with pytest.raises(ValueError):
        LeverGroup(
            name="dupe",
            params=[ParamSpec("a", 0, 1), ParamSpec("a", 0, 1), ParamSpec("b", 0, 1)],
        )


def test_staged_search_every_stage_within_dim_cap():
    # Constructing a StagedSearchResult only ever happens through
    # LeverGroup, so if construction succeeds every stage is in-band by
    # construction; assert that invariant explicitly here too.
    groups = [
        LeverGroup(name="G_a", params=[ParamSpec(f"a{i}", -1, 1) for i in range(3)]),
        LeverGroup(name="G_b", params=[ParamSpec(f"b{i}", -1, 1) for i in range(5)]),
        LeverGroup(name="G_c", params=[ParamSpec(f"c{i}", -1, 1) for i in range(8)]),
    ]
    for g in groups:
        assert 3 <= len(g.params) <= 8

    objective_fn = _neg_quadratic_bowl(
        {**{f"a{i}": 0.0 for i in range(3)}, **{f"b{i}": 0.0 for i in range(5)}, **{f"c{i}": 0.0 for i in range(8)}}
    )
    result = staged_search(groups, objective_fn, n_trials_per_stage=20, seed=42)
    assert len(result.stages) == 3
    for stage in result.stages:
        group = next(g for g in groups if g.name == stage.group_name)
        assert 3 <= len(group.params) <= 8


# ---------------------------------------------------------------------------
# 2. Reproducibility: fixed seed -> identical results across two runs
#    (random-search-floor path, since optuna is absent).
# ---------------------------------------------------------------------------


def test_random_search_floor_reproducible_with_fixed_seed():
    group = LeverGroup(name="G1", params=[ParamSpec("x", -10, 10), ParamSpec("y", -10, 10), ParamSpec("z", -10, 10)])
    objective_fn = _neg_quadratic_bowl({"x": 3.0, "y": -2.0, "z": 5.0})

    r1 = random_search_floor(group, objective_fn, n_trials=100, seed=7)
    r2 = random_search_floor(group, objective_fn, n_trials=100, seed=7)

    assert r1.best_params == r2.best_params
    assert r1.best_score == r2.best_score
    assert [t.params for t in r1.trials] == [t.params for t in r2.trials]
    assert [t.score for t in r1.trials] == [t.score for t in r2.trials]


def test_staged_search_reproducible_with_fixed_seed():
    groups = [
        LeverGroup(name="Ga", params=[ParamSpec("x", -5, 5), ParamSpec("y", -5, 5), ParamSpec("z", -5, 5)]),
        LeverGroup(name="Gb", params=[ParamSpec("u", -5, 5), ParamSpec("v", -5, 5), ParamSpec("w", -5, 5)]),
    ]
    objective_fn = _neg_quadratic_bowl({"x": 1.0, "y": 1.0, "z": 1.0, "u": -1.0, "v": -1.0, "w": -1.0})

    res1 = staged_search(groups, objective_fn, n_trials_per_stage=30, seed=123)
    res2 = staged_search(groups, objective_fn, n_trials_per_stage=30, seed=123)

    assert res1.best_params == res2.best_params
    for s1, s2 in zip(res1.stages, res2.stages):
        assert s1.best_params == s2.best_params
        assert s1.best_score == s2.best_score
        assert s1.seed == s2.seed


def test_different_seeds_produce_different_trial_sequences():
    group = LeverGroup(name="G1", params=[ParamSpec("x", -10, 10), ParamSpec("y", -10, 10), ParamSpec("z", -10, 10)])
    objective_fn = _neg_quadratic_bowl({"x": 3.0, "y": -2.0, "z": 5.0})

    r1 = random_search_floor(group, objective_fn, n_trials=50, seed=1)
    r2 = random_search_floor(group, objective_fn, n_trials=50, seed=2)

    assert [t.params for t in r1.trials] != [t.params for t in r2.trials]


# ---------------------------------------------------------------------------
# 3. The floor finds the known optimum on a crafted convex synthetic
#    objective.
# ---------------------------------------------------------------------------


def test_random_search_floor_finds_known_optimum_convex():
    target = {"x": 2.0, "y": -4.0, "z": 1.5}
    group = LeverGroup(name="convex", params=[ParamSpec("x", -5, 5), ParamSpec("y", -5, 5), ParamSpec("z", -5, 5)])
    objective_fn = _neg_quadratic_bowl(target)

    result = random_search_floor(group, objective_fn, n_trials=20000, seed=99)

    # exact optimum has score 0.0 (the bowl's peak); a large random floor
    # over a bounded convex bowl should land close to it.
    assert result.best_score <= 0.0  # score is always <= 0 for this bowl
    assert result.best_score > -0.3  # close to the true optimum (0.0)
    for k, v in target.items():
        assert abs(result.best_params[k] - v) < 0.5


def test_random_search_floor_prior_seeds_trial_zero_at_known_optimum():
    target = {"x": 2.0, "y": -4.0, "z": 1.5}
    group = LeverGroup(name="convex", params=[ParamSpec("x", -10, 10), ParamSpec("y", -10, 10), ParamSpec("z", -10, 10)])
    objective_fn = _neg_quadratic_bowl(target)

    result = random_search_floor(group, objective_fn, n_trials=10, seed=1, priors=target)

    assert result.trials[0].params == target
    assert result.trials[0].score == pytest.approx(0.0)
    # with the prior trial exactly at the optimum, it must win (score 0.0
    # is the global maximum of this bowl, ties never beaten by finite draws)
    assert result.best_score == pytest.approx(0.0)
    assert result.best_params == target


def test_staged_search_finds_known_optimum_across_groups():
    target = {"a0": 1.0, "a1": -1.0, "a2": 2.0, "b0": 0.5, "b1": -0.5, "b2": 3.0}
    groups = [
        LeverGroup(name="Ga", params=[ParamSpec("a0", -5, 5), ParamSpec("a1", -5, 5), ParamSpec("a2", -5, 5)]),
        LeverGroup(name="Gb", params=[ParamSpec("b0", -5, 5), ParamSpec("b1", -5, 5), ParamSpec("b2", -5, 5)]),
    ]
    objective_fn = _neg_quadratic_bowl(target)

    result = staged_search(groups, objective_fn, n_trials_per_stage=3000, seed=55)

    for k, v in target.items():
        assert abs(result.best_params[k] - v) < 0.5


# ---------------------------------------------------------------------------
# 4. Staged search freezes previous stage winners into subsequent stages.
# ---------------------------------------------------------------------------


def test_staged_search_freezes_prior_winners_into_later_stage_params():
    calls = []

    def objective_fn(params: dict) -> float:
        calls.append(dict(params))
        return -sum(v ** 2 for v in params.values())

    groups = [
        LeverGroup(name="Ga", params=[ParamSpec("a0", -1, 1), ParamSpec("a1", -1, 1), ParamSpec("a2", -1, 1)]),
        LeverGroup(name="Gb", params=[ParamSpec("b0", -1, 1), ParamSpec("b1", -1, 1), ParamSpec("b2", -1, 1)]),
    ]
    staged_search(groups, objective_fn, n_trials_per_stage=5, seed=3)

    stage_b_calls = calls[5:]  # after 5 stage-A trials (no priors supplied)
    for c in stage_b_calls:
        assert set(c.keys()) == {"a0", "a1", "a2", "b0", "b1", "b2"}


# ---------------------------------------------------------------------------
# 5. optuna-absent guard: tpe_search raises cleanly; staged_search falls back.
# ---------------------------------------------------------------------------


def test_tpe_search_raises_cleanly_without_optuna():
    if _HAS_OPTUNA:
        pytest.skip("optuna is installed in this environment; guard path not exercised")
    group = LeverGroup(name="G1", params=[ParamSpec("x", -1, 1), ParamSpec("y", -1, 1), ParamSpec("z", -1, 1)])
    objective_fn = _neg_quadratic_bowl({"x": 0.0, "y": 0.0, "z": 0.0})
    with pytest.raises(OptunaNotAvailableError):
        tpe_search(group, objective_fn, n_trials=5, seed=1)


def test_staged_search_use_tpe_falls_back_to_floor_without_optuna():
    if _HAS_OPTUNA:
        pytest.skip("optuna is installed in this environment; fallback path not exercised")
    groups = [LeverGroup(name="G1", params=[ParamSpec("x", -1, 1), ParamSpec("y", -1, 1), ParamSpec("z", -1, 1)])]
    objective_fn = _neg_quadratic_bowl({"x": 0.0, "y": 0.0, "z": 0.0})

    result = staged_search(groups, objective_fn, n_trials_per_stage=5, seed=1, use_tpe=True)

    assert result.optuna_used is False
    assert result.stages[0].method == "random_floor"


def test_module_imports_and_runs_without_optuna_installed():
    # This test file itself imports sentinel_engine.opt.search successfully
    # in an environment where `import optuna` fails -- the import guard at
    # module scope is what's under test here (a broken guard would have
    # already failed collection of this whole file).
    assert _HAS_OPTUNA is False


# ---------------------------------------------------------------------------
# 6. no_signal_flag: TPE-vs-floor comparator (Fable Sec 2.5 "if TPE doesn't
#    beat random, the lever group has no signal").
# ---------------------------------------------------------------------------


def test_no_signal_flag_true_when_candidate_does_not_beat_floor():
    floor = StageResult(
        group_name="G1", method="random_floor", seed=1,
        best_params={"x": 0.0}, best_score=0.5, trials=[],
    )
    weaker = StageResult(
        group_name="G1", method="tpe", seed=1,
        best_params={"x": 0.1}, best_score=0.4, trials=[],
    )
    tied = StageResult(
        group_name="G1", method="tpe", seed=1,
        best_params={"x": 0.0}, best_score=0.5, trials=[],
    )
    assert no_signal_flag(weaker, floor) is True
    assert no_signal_flag(tied, floor) is True  # tie is not "beating"


def test_no_signal_flag_false_when_candidate_beats_floor():
    floor = StageResult(
        group_name="G1", method="random_floor", seed=1,
        best_params={"x": 0.0}, best_score=0.5, trials=[],
    )
    stronger = StageResult(
        group_name="G1", method="tpe", seed=1,
        best_params={"x": 0.2}, best_score=0.9, trials=[],
    )
    assert no_signal_flag(stronger, floor) is False


def test_no_signal_flag_rejects_cross_group_comparison():
    a = StageResult(group_name="G1", method="tpe", seed=1, best_params={}, best_score=1.0, trials=[])
    b = StageResult(group_name="G2", method="random_floor", seed=1, best_params={}, best_score=0.5, trials=[])
    with pytest.raises(ValueError):
        no_signal_flag(a, b)
