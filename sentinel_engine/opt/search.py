"""4.4 -- Optuna TPE + staged block-wise search + random-search floor
(Fable Sec. 2.5 / Sec. 2.6 / Sec. 4 items 2 & 9).

Spec (Fable, verbatim intent):
  - "staged, grouped optimization (coordinate-block descent over lever
    groups) rather than one 40-dimensional search" (Sec 2.5) -- each stage
    tunes one lever group while previous stages' winners are frozen, keeping
    effective dimensionality per fit at **3-8 dims**.
  - "Optuna (TPE + pruning) for search" (Sec 1 / Sec 2.5) with priors
    centered on current (production) values.
  - "200 random trials per stage as a sanity floor: if TPE doesn't beat
    random, the lever group has no signal and we say so in the report"
    (Sec 2.5) -- the random-search floor.
  - "Discarded: evolutionary/CMA-ES ... pure random (baseline only)".

This module MUST import and run correctly with optuna **not installed**:
Optuna is an optional accelerant (TPE) layered on top of the random-search
floor, which is the always-available fallback/baseline. When optuna is
absent, ``tpe_search`` raises ``OptunaNotAvailableError`` and
``staged_search(..., use_tpe=True)`` transparently falls back to the floor
for every stage (flagged in the returned ``StageResult.method`` and in
``StagedSearchResult.optuna_used``).

FLAG: optuna needed for TPE -- this environment does not have optuna
installed, so all *_search* calls in this module's test suite exercise the
random-search floor path only. The TPE code path is implemented (guarded
import, ``optuna.samplers.TPESampler`` with a fixed seed + prior-centered
``enqueue_trial``) but is untested here for lack of the dependency.

Design (module-scoped ambiguity resolutions, see bottom of file for the log):
  - A "lever group" for search purposes is a ``LeverGroup``: a name plus a
    list of ``ParamSpec``. The 3-8 dim/fit cap (Sec 2.5/Sec 4 item 2) is
    enforced by construction: ``LeverGroup.__post_init__`` raises
    ``ValueError`` outside ``[MIN_DIMS_PER_STAGE, MAX_DIMS_PER_STAGE]``.
  - ``objective_fn`` is a plain ``Dict[str, float] -> float`` callable (score
    to *maximize*, consistent with ``sentinel_engine.opt.objective.objective``
    where higher is better and gate failures are pinned to
    ``PENALTY_SCORE``). This module is agnostic to how the score is produced
    (real replay, synthetic fixture) -- callers wire a real evaluator
    (walk-forward folds -> trades_R -> ``objective()``) in the real study;
    unit tests here use crafted synthetic ``objective_fn`` per the task spec
    ("Synthetic objective only").
  - Determinism: every stochastic draw is seeded from a single integer
    ``seed`` deterministically derived per stage (``seed + stage_index``),
    never from wall-clock or global RNG state, so two runs with the same
    inputs produce bit-identical ``StagedSearchResult`` (verified by test).
  - "Priors centered on current values" (Sec 2.5) is implemented as an
    optional ``fixed_params``-independent ``priors: Dict[str, float]``
    passed to ``tpe_search`` (seeds Optuna's first trial via
    ``enqueue_trial``) and, for the random floor, as the first trial
    evaluated before the random draws (so a floor run always checks the
    production point at least once, cheaply).
  - No-signal detection ("if TPE doesn't beat random, the lever group has no
    signal"): ``no_signal_flag(tpe_result, floor_result, tol)`` compares two
    ``StageResult``s. With optuna absent, ``staged_search`` cannot itself
    populate a distinct TPE result to compare against; it simply records
    ``method="random_floor"`` for every stage and leaves TPE-vs-floor
    comparison to the caller once optuna is installed.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional, Sequence

try:
    import optuna  # type: ignore
    from optuna.samplers import TPESampler  # type: ignore

    _HAS_OPTUNA = True
except ImportError:  # pragma: no cover - exercised by environments w/o optuna
    optuna = None  # type: ignore
    TPESampler = None  # type: ignore
    _HAS_OPTUNA = False


#: effective-dimensionality-per-fit cap, Fable Sec 2.5 / Sec 4 item 2.
MIN_DIMS_PER_STAGE = 3
MAX_DIMS_PER_STAGE = 8

#: default random-search floor trial budget ("200 random trials per stage",
#: Fable Sec 2.5). Tests use smaller budgets for speed; this is only the
#: module-level default for real studies.
DEFAULT_FLOOR_TRIALS = 200

ObjectiveFn = Callable[[Dict[str, float]], float]


class OptunaNotAvailableError(RuntimeError):
    """Raised by ``tpe_search`` when optuna is not installed.

    Callers wanting graceful degradation should use ``staged_search`` with
    ``use_tpe=True`` (which auto-falls-back to the random floor) rather than
    calling ``tpe_search`` directly, or catch this exception themselves.
    """


@dataclass(frozen=True)
class ParamSpec:
    """One tunable dimension within a lever group.

    Attributes:
        name: parameter key, matched against ``fixed_params``/``priors``.
        low: inclusive lower bound of the search range.
        high: inclusive upper bound of the search range.
        is_int: if True, sample integers (``optuna.suggest_int`` /
            ``random.randint``).
        log: if True, sample log-uniformly (only meaningful for float
            params; ``low`` must be > 0).
    """

    name: str
    low: float
    high: float
    is_int: bool = False
    log: bool = False

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError(f"ParamSpec {self.name!r}: high < low ({self.high} < {self.low})")
        if self.log and self.low <= 0:
            raise ValueError(f"ParamSpec {self.name!r}: log=True requires low > 0")


@dataclass(frozen=True)
class LeverGroup:
    """A coordinate-descent block: one lever group tuned per search stage.

    Enforces the Fable Sec 2.5 / Sec 4 item 2 rule that effective
    dimensionality per fit stays within ``[MIN_DIMS_PER_STAGE,
    MAX_DIMS_PER_STAGE]`` -- construction raises ``ValueError`` outside that
    band, so an out-of-spec group can never silently enter a search.
    """

    name: str
    params: Sequence[ParamSpec]

    def __post_init__(self) -> None:
        n = len(self.params)
        if not (MIN_DIMS_PER_STAGE <= n <= MAX_DIMS_PER_STAGE):
            raise ValueError(
                f"LeverGroup {self.name!r} has {n} dims; must be within "
                f"[{MIN_DIMS_PER_STAGE}, {MAX_DIMS_PER_STAGE}] per Fable "
                f"Sec 2.5 / Sec 4 item 2 (effective dimensionality/fit cap)"
            )
        names = [p.name for p in self.params]
        if len(set(names)) != len(names):
            raise ValueError(f"LeverGroup {self.name!r} has duplicate param names: {names}")


@dataclass(frozen=True)
class TrialResult:
    """One evaluated point in a search stage."""

    params: Dict[str, float]
    score: float


@dataclass(frozen=True)
class StageResult:
    """Outcome of running one lever-group stage."""

    group_name: str
    method: str  # "random_floor" or "tpe"
    seed: int
    best_params: Dict[str, float]
    best_score: float
    trials: List[TrialResult] = field(default_factory=list)


@dataclass(frozen=True)
class StagedSearchResult:
    """Outcome of a full staged block-wise search across all lever groups."""

    stages: List[StageResult]
    best_params: Dict[str, float]
    optuna_used: bool


def _sample_param(rng: random.Random, spec: ParamSpec) -> float:
    """Draw one value for ``spec`` from ``rng`` (deterministic given seed)."""
    if spec.is_int:
        return float(rng.randint(int(spec.low), int(spec.high)))
    if spec.log:
        lo, hi = math.log(spec.low), math.log(spec.high)
        return math.exp(rng.uniform(lo, hi))
    return rng.uniform(spec.low, spec.high)


def _clamp_prior(spec: ParamSpec, value: float) -> float:
    """Clamp a caller-supplied prior value into ``spec``'s valid range."""
    v = min(max(value, spec.low), spec.high)
    return float(round(v)) if spec.is_int else v


def random_search_floor(
    group: LeverGroup,
    objective_fn: ObjectiveFn,
    n_trials: int,
    seed: int,
    fixed_params: Optional[Mapping[str, float]] = None,
    priors: Optional[Mapping[str, float]] = None,
) -> StageResult:
    """The always-available "sanity floor": ``n_trials`` uniform-random draws
    over ``group``'s params (plus one prior-centered trial if ``priors`` are
    given), evaluated via ``objective_fn``. No optuna dependency.

    Deterministic: identical ``(group, n_trials, seed, fixed_params,
    priors)`` always yields bit-identical ``StageResult.trials`` order and
    values, since the only randomness is ``random.Random(seed)``.

    Args:
        group: the lever group (3-8 dims) being tuned this stage.
        objective_fn: scores a full param dict (frozen params from prior
            stages merged with this stage's draw); higher is better.
        n_trials: number of random draws (Fable Sec 2.5 default: 200).
        seed: RNG seed -- reproducibility contract for this module.
        fixed_params: params frozen from earlier stages, merged into every
            trial's param dict (not searched this stage).
        priors: optional current/production values for this group's params;
            if given, evaluated as trial 0 before the random draws.

    Returns:
        ``StageResult`` with every trial (prior trial first if present) and
        the best (max-score) trial as ``best_params``/``best_score``.
    """
    rng = random.Random(seed)
    fixed = dict(fixed_params or {})
    trials: List[TrialResult] = []

    if priors:
        prior_params = dict(fixed)
        for spec in group.params:
            if spec.name in priors:
                prior_params[spec.name] = _clamp_prior(spec, priors[spec.name])
            else:
                prior_params[spec.name] = _sample_param(rng, spec)
        score = objective_fn(prior_params)
        trials.append(TrialResult(params=prior_params, score=score))

    for _ in range(n_trials):
        params = dict(fixed)
        for spec in group.params:
            params[spec.name] = _sample_param(rng, spec)
        score = objective_fn(params)
        trials.append(TrialResult(params=params, score=score))

    best = max(trials, key=lambda t: t.score)
    return StageResult(
        group_name=group.name,
        method="random_floor",
        seed=seed,
        best_params=dict(best.params),
        best_score=best.score,
        trials=trials,
    )


def tpe_search(
    group: LeverGroup,
    objective_fn: ObjectiveFn,
    n_trials: int,
    seed: int,
    fixed_params: Optional[Mapping[str, float]] = None,
    priors: Optional[Mapping[str, float]] = None,
) -> StageResult:
    """Optuna TPE search over ``group``'s params, priors enqueued as the
    first trial (Fable Sec 2.5: "priors centered on current values").

    Raises:
        OptunaNotAvailableError: if optuna is not installed. Callers wanting
            automatic fallback should use ``staged_search(..., use_tpe=True)``
            instead of calling this directly.
    """
    if not _HAS_OPTUNA:
        raise OptunaNotAvailableError(
            "optuna is not installed; use random_search_floor(), or call "
            "staged_search(..., use_tpe=True) for automatic fallback. "
            "FLAG: optuna needed for TPE."
        )

    fixed = dict(fixed_params or {})
    sampler = TPESampler(seed=seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)

    if priors:
        prior_point = {
            spec.name: _clamp_prior(spec, priors[spec.name])
            for spec in group.params
            if spec.name in priors
        }
        if prior_point:
            study.enqueue_trial(prior_point)

    trials: List[TrialResult] = []

    def _optuna_objective(trial: "optuna.Trial") -> float:  # pragma: no cover - needs optuna
        params = dict(fixed)
        for spec in group.params:
            if spec.is_int:
                params[spec.name] = trial.suggest_int(spec.name, int(spec.low), int(spec.high))
            else:
                params[spec.name] = trial.suggest_float(
                    spec.name, spec.low, spec.high, log=spec.log
                )
        score = objective_fn(params)
        trials.append(TrialResult(params=dict(params), score=score))
        return score

    study.optimize(_optuna_objective, n_trials=n_trials)

    best = max(trials, key=lambda t: t.score)
    return StageResult(
        group_name=group.name,
        method="tpe",
        seed=seed,
        best_params=dict(best.params),
        best_score=best.score,
        trials=trials,
    )


def staged_search(
    groups: Sequence[LeverGroup],
    objective_fn: ObjectiveFn,
    n_trials_per_stage: int,
    seed: int,
    priors: Optional[Mapping[str, Mapping[str, float]]] = None,
    use_tpe: bool = False,
) -> StagedSearchResult:
    """Coordinate-block descent over ``groups`` (Fable Sec 2.5: "staged,
    grouped optimization ... rather than one 40-dimensional search").

    Each stage tunes exactly one ``LeverGroup`` (3-8 dims) while every
    previously-decided group's winning params are frozen into
    ``fixed_params`` for subsequent stages ("Each stage re-freezes previous
    winners", Fable Sec 2.5).

    Args:
        groups: ordered lever groups (stage order per Fable Sec 2.5:
            G4 -> G2/G3 -> G5 -> G1 -> G6 -> G7, then a joint polish -- callers
            supply groups pre-ordered; this function does not reorder them).
        objective_fn: shared scorer across all stages/groups.
        n_trials_per_stage: trial budget per stage.
        seed: base RNG seed; stage ``i`` derives its own seed as
            ``seed + i`` so runs are reproducible yet stages don't share
            an RNG stream.
        priors: optional ``{group_name: {param_name: value}}`` map of
            current/production values to center each stage's search on.
        use_tpe: if True, attempt Optuna TPE per stage; transparently falls
            back to the random-search floor for every stage where optuna is
            unavailable (this environment: always, since optuna is not
            installed -- ``StagedSearchResult.optuna_used`` reports which
            path actually ran).

    Returns:
        ``StagedSearchResult`` with every stage's ``StageResult`` and the
        final merged ``best_params`` across all stages.
    """
    fixed: Dict[str, float] = {}
    stages: List[StageResult] = []
    optuna_used = False

    for i, group in enumerate(groups):
        stage_seed = seed + i
        group_priors = dict((priors or {}).get(group.name, {}))

        if use_tpe and _HAS_OPTUNA:
            result = tpe_search(
                group, objective_fn, n_trials_per_stage, stage_seed,
                fixed_params=fixed, priors=group_priors,
            )
            optuna_used = True
        else:
            result = random_search_floor(
                group, objective_fn, n_trials_per_stage, stage_seed,
                fixed_params=fixed, priors=group_priors,
            )

        stages.append(result)
        fixed.update(result.best_params)

    return StagedSearchResult(stages=stages, best_params=fixed, optuna_used=optuna_used)


def no_signal_flag(
    candidate: StageResult,
    floor: StageResult,
    tol: float = 1e-9,
) -> bool:
    """True if ``candidate`` (typically a TPE stage) fails to beat the
    random-search ``floor`` for the same lever group -- per Fable Sec 2.5:
    "if TPE doesn't beat random, the lever group has no signal and we say
    so in the report".

    Args:
        candidate: the stage result being evaluated for signal (e.g. TPE).
        floor: the random-search-floor stage result for the *same* group.
        tol: candidate must exceed floor by more than ``tol`` to count as
            "beating" it (guards against floating-point ties reading as a
            real edge).

    Raises:
        ValueError: if ``candidate`` and ``floor`` are not for the same
            lever group (comparing across groups is meaningless).
    """
    if candidate.group_name != floor.group_name:
        raise ValueError(
            f"no_signal_flag: group mismatch ({candidate.group_name!r} vs "
            f"{floor.group_name!r}) -- compare same-group stages only"
        )
    return not (candidate.best_score > floor.best_score + tol)


# --- Ambiguity log -------------------------------------------------------
# 1. Fable Sec 2.5 does not give an exact type for "lever group" nor pin a
#    concrete data structure for the 3-8 dim/fit cap. Resolved with
#    ``LeverGroup`` as a first-class, self-validating container so the cap
#    is enforced at construction time everywhere in the pipeline, not just
#    inside the search loop.
# 2. "priors centered on current values" (Sec 2.5) doesn't specify the
#    floor's behavior when optuna is absent. Resolved by giving the floor
#    itself an optional prior-centered "trial 0" (evaluated once, before
#    the uniform-random draws) so even the always-available floor path
#    checks the production point -- consistent with the spirit of "priors
#    centered on current values" without requiring optuna.
# 3. The exact trial budget ("200 random trials per stage") is a Fable
#    *default*, not a hard requirement; exposed as ``DEFAULT_FLOOR_TRIALS``
#    but every function takes an explicit ``n_trials``/``n_trials_per_stage``
#    argument so callers (and this module's fast unit tests) can choose a
#    smaller budget without editing the module.
# 4. "if TPE doesn't beat random" (Sec 2.5) is operationalized as
#    ``no_signal_flag``, a same-group StageResult comparator. Since optuna
#    is not installed in this environment, ``staged_search`` cannot itself
#    produce two distinct results (TPE vs floor) to feed it; the comparator
#    is implemented and unit-tested directly (construct two StageResults by
#    hand) so it is ready the moment optuna is added, per the task's FLAG
#    requirement.
