"""4.5 -- Winner selection guards (Fable Sec. 2.6 / Sec. 4 item 2).

Machinery only. Operates on plain, synthetic "fold-result" / "regime-result"
data structures built by walk-forward + objective (Tasks 4.2/4.3) -- this
module does not read the price lake, live config, or golden fixtures, and
does not itself run any search. It implements the four selection guards the
spec fixes verbatim (Fable Sec 2.6, plan Phase-4 task 4.5):

    "Selection: median test-fold J; must beat production in >=70% folds;
    minimum-change prior among 1-SE ties; plateau +/-10% (reject if J
    degrades >25%); regime-balance guard for any regime >15% of test time."

Four independent guards, each individually testable, plus a top-level
``select_winner`` that composes them in spec order:

    1. ``dominance_rate`` / ``passes_dominance`` -- candidate must beat the
       current-production config's J in >= 70% of test folds.
    2. ``plateau_check`` -- perturb each lever +/-10%; reject if J degrades
       by more than 25% for ANY single-lever perturbation (cliff-edge
       optima are noise fits, not real signal).
    3. ``regime_balance_check`` -- reject if the candidate is catastrophic
       in any regime that covers > 15% of total test time (guards against
       "bull-only" configs that only work in one regime).
    4. ``select_minimum_change`` -- among configs within 1 standard error of
       the best median-fold J (a "statistical tie"), prefer the one closest
       to the current production config (cheapest change, most trader
       trust, least data-snooping risk).

This module is pure Python/stdlib only (no optuna, no pandas) and consumes
plain dataclasses / dicts so it composes with objective.py's
``ObjectiveResult`` (imported read-only, for its ``score`` field only) but
does not require it -- fold/regime J-values can come from any source.

Ambiguity resolutions (spec silent on exact mechanics, resolved here):

  - "Median test-fold J" (selection score) is computed over each
    candidate's own ``FoldResult.candidate_J`` values -- ``median_J``.
    Ties/ranking use this median, never the mean (spec explicitly: "not
    mean -- robust to one lucky fold").
  - "Beat production in >=70% folds": per-fold win is a strict
    ``candidate_J > production_J`` comparison (a tie on a fold does not
    count as a win -- the spec's "beat" reads as strictly better; ties are
    rare with continuous J and this keeps the guard conservative/hard to
    game). The dominance threshold ``0.70`` is inclusive (>= 0.70 passes).
  - "1 SE of the best": interpreted as the standard error of the BEST
    candidate's own per-fold J distribution, ``stdev(fold_Js, ddof=1) /
    sqrt(n_folds)`` (the conventional "1-SE rule" from cross-validated model
    selection, e.g. Hastie/Tibshirani/Friedman Sec 7.10). A candidate with
    ``median_J >= best_median_J - SE`` is a statistical tie with the best
    and enters the minimum-change pool. Candidates with fewer than 2 folds
    have an undefined SE; SE is treated as 0.0 for them (no slack -- only
    an exact or better median ties).
  - "Minimum-change prior": distance from production is the normalized L2
    distance over shared lever keys, ``sqrt(mean((delta / scale)**2))``,
    where ``scale`` is a per-lever normalizer (caller-supplied
    ``lever_scales``, e.g. each lever's search-range width) so levers with
    different natural units/magnitudes contribute comparably. If no scale
    is supplied for a lever, raw absolute difference is used for that
    lever's term.
  - Plateau perturbation direction: BOTH +10% and -10% are tried per lever
    (the spec says "perturb each lever +/-10%"); the guard fails if EITHER
    direction degrades J by more than 25% relative to the candidate's own
    baseline J (the more conservative reading -- a cliff on either side is
    still a cliff). Degradation is measured as a relative drop,
    ``(baseline_J - perturbed_J) / abs(baseline_J)``; when
    ``baseline_J <= 0`` (no edge to begin with) degradation is undefined and
    the guard conservatively treats it as a fail for that lever (there is
    no plateau to certify around a non-positive baseline).
  - Regime "catastrophic": a regime is catastrophic for the candidate when
    its ``candidate_J`` is <= a caller-supplied floor (default ``0.0`` --
    the config has zero-or-negative edge in that regime, i.e. it is not
    just weaker than production, it is actively losing there). Only
    regimes with ``time_share > 0.15`` are checked (regimes at or under the
    15% threshold are explicitly exempted per "covering >15% of test
    time").
  - ``select_winner`` evaluates guards in a fixed order (dominance ->
    plateau -> regime-balance) against each candidate and drops any
    candidate that fails any guard *before* the minimum-change tie-break
    runs, matching the spec's read of these as hard gates the winner "must"
    satisfy, with minimum-change as the residual tie-break among survivors.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional, Sequence

#: default fold-dominance threshold (Fable Sec 2.6: ">= 70% of folds").
DEFAULT_DOMINANCE_THRESHOLD = 0.70

#: default plateau perturbation fraction (Fable Sec 2.6: "+/-10%").
DEFAULT_PLATEAU_PERTURB_FRAC = 0.10

#: default max allowed relative J degradation under perturbation
#: (Fable Sec 2.6: "reject if J degrades >25%").
DEFAULT_PLATEAU_MAX_DEGRADATION_FRAC = 0.25

#: default minimum test-time share a regime must cover to be checked
#: (Fable Sec 2.6: "any regime covering >15% of test time").
DEFAULT_REGIME_TIME_SHARE_THRESHOLD = 0.15

#: default "catastrophic" J floor for the regime-balance guard.
DEFAULT_CATASTROPHIC_J_FLOOR = 0.0


@dataclass(frozen=True)
class FoldResult:
    """One walk-forward test fold's J for a candidate vs. production.

    Attributes:
        fold_index: 0-based fold number (chronological order).
        candidate_J: the candidate config's objective score (Task 4.2's
            ``ObjectiveResult.score``) on this fold's test slice.
        production_J: the current-production config's objective score on
            the SAME fold's test slice (must be computed on identical data
            for the comparison to be meaningful -- caller's responsibility).
    """

    fold_index: int
    candidate_J: float
    production_J: float


@dataclass(frozen=True)
class RegimeResult:
    """One regime's aggregate J + test-time coverage for a candidate.

    Attributes:
        regime: regime label (e.g. "BULL", "BEAR", "RANGE", "HIGH_VOL").
        time_share: fraction (0..1) of total test time this regime covers.
        candidate_J: the candidate's objective score restricted to this
            regime's test slices.
        production_J: production's objective score restricted to the same
            regime's test slices (optional context, not required by the
            guard itself).
    """

    regime: str
    time_share: float
    candidate_J: float
    production_J: Optional[float] = None


@dataclass(frozen=True)
class PlateauCheckResult:
    """Result of perturbing every lever +/-10% around a candidate."""

    passed: bool
    baseline_J: float
    worst_degradation_frac: float
    failing_levers: List[str] = field(default_factory=list)
    per_lever_J: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class RegimeBalanceResult:
    """Result of the regime-balance guard for a candidate."""

    passed: bool
    checked_regimes: List[str] = field(default_factory=list)
    failing_regimes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CandidateResult:
    """One candidate config bundled with everything the guards need.

    Attributes:
        name: identifier for reporting (e.g. config sha256 or trial id).
        config: lever name -> value mapping for this candidate.
        fold_results: per-fold candidate-vs-production J (Task 4.3 folds).
        regime_results: per-regime candidate J + time-share (Task 4.1/4.3
            regime slices), or empty if unavailable (regime guard then
            trivially passes -- there is nothing to check).
    """

    name: str
    config: Mapping[str, float]
    fold_results: Sequence[FoldResult]
    regime_results: Sequence[RegimeResult] = field(default_factory=tuple)


@dataclass(frozen=True)
class SelectionOutcome:
    """Full result of running ``select_winner`` over a candidate pool."""

    winner: Optional[CandidateResult]
    reason: str
    median_J_by_name: Dict[str, float] = field(default_factory=dict)
    dominance_by_name: Dict[str, float] = field(default_factory=dict)
    rejected: Dict[str, str] = field(default_factory=dict)
    tie_pool: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Guard 1: median test-fold J + >=70% fold dominance over production
# ---------------------------------------------------------------------------


def median_J(fold_results: Sequence[FoldResult]) -> float:
    """Median of ``candidate_J`` across folds (selection score, Fable Sec 2.6).

    Median, never mean, per spec ("not mean -- robust to one lucky fold").
    """
    if not fold_results:
        return 0.0
    values = sorted(fr.candidate_J for fr in fold_results)
    n = len(values)
    mid = n // 2
    if n % 2 == 1:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def dominance_rate(fold_results: Sequence[FoldResult]) -> float:
    """Fraction of folds where ``candidate_J`` strictly beats ``production_J``."""
    if not fold_results:
        return 0.0
    wins = sum(1 for fr in fold_results if fr.candidate_J > fr.production_J)
    return wins / len(fold_results)


def passes_dominance(
    fold_results: Sequence[FoldResult],
    threshold: float = DEFAULT_DOMINANCE_THRESHOLD,
) -> bool:
    """True iff the candidate beats production in >= ``threshold`` of folds."""
    return dominance_rate(fold_results) >= threshold


# ---------------------------------------------------------------------------
# Guard 2: plateau check (+/-10% per lever, reject if J degrades > 25%)
# ---------------------------------------------------------------------------


def plateau_check(
    config: Mapping[str, float],
    score_fn: Callable[[Mapping[str, float]], float],
    *,
    baseline_J: Optional[float] = None,
    levers: Optional[Sequence[str]] = None,
    perturb_frac: float = DEFAULT_PLATEAU_PERTURB_FRAC,
    max_degradation_frac: float = DEFAULT_PLATEAU_MAX_DEGRADATION_FRAC,
) -> PlateauCheckResult:
    """Perturb each lever +/-``perturb_frac`` and check J doesn't cliff.

    Args:
        config: the candidate's lever values (name -> numeric value).
        score_fn: callable mapping a (possibly perturbed) config to its J
            score. Caller-supplied so this module stays data-agnostic --
            it may re-run the objective over cached fold data, a cheap
            surrogate, or the same walk-forward evaluation used for
            selection.
        baseline_J: the candidate's own J at ``config`` with no
            perturbation. If omitted, computed as ``score_fn(config)``.
        levers: which config keys to perturb. Defaults to all keys in
            ``config`` whose value is numeric and nonzero (a zero-valued
            lever has an undefined percentage perturbation and is skipped
            -- flagged nowhere since a literal 0.0 lever is a legitimate
            "off" state, not an error).
        perturb_frac: relative perturbation size (default 0.10 == +/-10%).
        max_degradation_frac: max allowed relative J drop before failing
            (default 0.25 == 25%).

    Returns:
        PlateauCheckResult. ``passed`` is False if ANY lever's +/- probe
        degrades J by more than ``max_degradation_frac``, OR if
        ``baseline_J <= 0`` (no positive edge to certify a plateau around).
    """
    if baseline_J is None:
        baseline_J = score_fn(config)

    if levers is None:
        levers = [
            k
            for k, v in config.items()
            if isinstance(v, (int, float)) and v != 0
        ]

    failing_levers: List[str] = []
    per_lever_J: Dict[str, Dict[str, float]] = {}
    worst_degradation = float("-inf")

    if baseline_J <= 0:
        # No edge at the nominal point -- there is nothing to certify a
        # plateau around. Conservative fail with no per-lever detail.
        return PlateauCheckResult(
            passed=False,
            baseline_J=baseline_J,
            worst_degradation_frac=float("nan"),
            failing_levers=list(levers),
            per_lever_J={},
        )

    for lever in levers:
        base_val = config[lever]
        lever_fail = False
        lever_js: Dict[str, float] = {}
        for sign, tag in ((1.0, "up"), (-1.0, "down")):
            perturbed_val = base_val * (1.0 + sign * perturb_frac)
            perturbed_config = dict(config)
            perturbed_config[lever] = perturbed_val
            perturbed_J = score_fn(perturbed_config)
            lever_js[tag] = perturbed_J

            degradation = (baseline_J - perturbed_J) / abs(baseline_J)
            worst_degradation = max(worst_degradation, degradation)
            if degradation > max_degradation_frac:
                lever_fail = True

        per_lever_J[lever] = lever_js
        if lever_fail:
            failing_levers.append(lever)

    if worst_degradation == float("-inf"):
        worst_degradation = 0.0

    return PlateauCheckResult(
        passed=len(failing_levers) == 0,
        baseline_J=baseline_J,
        worst_degradation_frac=worst_degradation,
        failing_levers=failing_levers,
        per_lever_J=per_lever_J,
    )


# ---------------------------------------------------------------------------
# Guard 3: regime-balance guard
# ---------------------------------------------------------------------------


def regime_balance_check(
    regime_results: Sequence[RegimeResult],
    *,
    time_share_threshold: float = DEFAULT_REGIME_TIME_SHARE_THRESHOLD,
    catastrophic_J_floor: float = DEFAULT_CATASTROPHIC_J_FLOOR,
) -> RegimeBalanceResult:
    """Reject if the candidate is catastrophic in any regime covering
    more than ``time_share_threshold`` of total test time.

    A regime with no ``regime_results`` entries (empty sequence) trivially
    passes -- there is nothing to check (caller/upstream is responsible for
    supplying regime coverage when available).
    """
    checked = [
        rr.regime for rr in regime_results if rr.time_share > time_share_threshold
    ]
    failing = [
        rr.regime
        for rr in regime_results
        if rr.time_share > time_share_threshold
        and rr.candidate_J <= catastrophic_J_floor
    ]
    return RegimeBalanceResult(
        passed=len(failing) == 0,
        checked_regimes=checked,
        failing_regimes=failing,
    )


# ---------------------------------------------------------------------------
# Guard 4: minimum-change prior among 1-SE statistical ties
# ---------------------------------------------------------------------------


def _stderr(values: Sequence[float]) -> float:
    """Sample standard error: stdev(ddof=1) / sqrt(n). 0.0 if n < 2."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    return math.sqrt(var) / math.sqrt(n)


def config_distance(
    config_a: Mapping[str, float],
    config_b: Mapping[str, float],
    lever_scales: Optional[Mapping[str, float]] = None,
) -> float:
    """Normalized L2 distance between two configs over their shared keys.

    Each per-lever delta is divided by ``lever_scales[lever]`` (if
    supplied) before squaring, so levers with different natural units
    contribute comparably. Levers present in only one config are ignored
    (undefined delta -- caller should ensure both configs share the same
    lever set for a meaningful minimum-change comparison).
    """
    shared_keys = [k for k in config_a.keys() if k in config_b]
    if not shared_keys:
        return 0.0
    scales = lever_scales or {}
    sq_terms = []
    for k in shared_keys:
        delta = float(config_a[k]) - float(config_b[k])
        scale = scales.get(k)
        if scale:
            delta = delta / scale
        sq_terms.append(delta * delta)
    return math.sqrt(sum(sq_terms) / len(sq_terms))


def select_minimum_change(
    candidates: Sequence[CandidateResult],
    production_config: Mapping[str, float],
    lever_scales: Optional[Mapping[str, float]] = None,
) -> CandidateResult:
    """Among a pool of statistically-tied candidates, pick the one closest
    to ``production_config`` (the "minimum-change prior", Fable Sec 2.6).

    Raises:
        ValueError: if ``candidates`` is empty.
    """
    if not candidates:
        raise ValueError("select_minimum_change requires at least one candidate")
    return min(
        candidates,
        key=lambda c: config_distance(c.config, production_config, lever_scales),
    )


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def select_winner(
    candidates: Sequence[CandidateResult],
    production_config: Mapping[str, float],
    score_fn: Optional[Callable[[Mapping[str, float]], float]] = None,
    *,
    dominance_threshold: float = DEFAULT_DOMINANCE_THRESHOLD,
    plateau_perturb_frac: float = DEFAULT_PLATEAU_PERTURB_FRAC,
    plateau_max_degradation_frac: float = DEFAULT_PLATEAU_MAX_DEGRADATION_FRAC,
    regime_time_share_threshold: float = DEFAULT_REGIME_TIME_SHARE_THRESHOLD,
    regime_catastrophic_J_floor: float = DEFAULT_CATASTROPHIC_J_FLOOR,
    lever_scales: Optional[Mapping[str, float]] = None,
) -> SelectionOutcome:
    """Run all four selection guards and pick the winner, if any.

    Order (per Fable Sec 2.6, plan task 4.5): every candidate must pass
    (1) fold-dominance over production and (3) regime-balance outright;
    (2) plateau is only checked when ``score_fn`` is supplied (it requires
    re-scoring perturbed configs, which needs a live scoring callable --
    without one this guard is skipped and flagged, never silently assumed
    to pass, via ``rejected`` staying empty AND the candidate simply not
    being plateau-screened). Among survivors, the winner is chosen by
    (4) minimum-change among candidates within 1 SE of the best median J.

    Returns:
        SelectionOutcome with ``winner=None`` and a ``reason`` if no
        candidate survives all guards.
    """
    median_J_by_name: Dict[str, float] = {}
    dominance_by_name: Dict[str, float] = {}
    rejected: Dict[str, str] = {}
    survivors: List[CandidateResult] = []

    for cand in candidates:
        median_J_by_name[cand.name] = median_J(cand.fold_results)
        dominance_by_name[cand.name] = dominance_rate(cand.fold_results)

        if not passes_dominance(cand.fold_results, dominance_threshold):
            rejected[cand.name] = (
                f"fold-dominance {dominance_by_name[cand.name]:.2%} < "
                f"{dominance_threshold:.0%}"
            )
            continue

        if score_fn is not None:
            plateau = plateau_check(
                cand.config,
                score_fn,
                levers=list(cand.config.keys()),
                perturb_frac=plateau_perturb_frac,
                max_degradation_frac=plateau_max_degradation_frac,
            )
            if not plateau.passed:
                rejected[cand.name] = (
                    "plateau check failed: cliff-edge lever(s) "
                    f"{plateau.failing_levers}"
                )
                continue

        regime = regime_balance_check(
            cand.regime_results,
            time_share_threshold=regime_time_share_threshold,
            catastrophic_J_floor=regime_catastrophic_J_floor,
        )
        if not regime.passed:
            rejected[cand.name] = (
                "regime-balance check failed: catastrophic in "
                f"{regime.failing_regimes}"
            )
            continue

        survivors.append(cand)

    if not survivors:
        return SelectionOutcome(
            winner=None,
            reason="no candidate survived the selection guards",
            median_J_by_name=median_J_by_name,
            dominance_by_name=dominance_by_name,
            rejected=rejected,
            tie_pool=[],
        )

    best_median = max(median_J_by_name[c.name] for c in survivors)
    best_candidate = max(survivors, key=lambda c: median_J_by_name[c.name])
    best_fold_Js = [fr.candidate_J for fr in best_candidate.fold_results]
    se = _stderr(best_fold_Js)

    tie_pool = [
        c for c in survivors if median_J_by_name[c.name] >= best_median - se
    ]

    winner = select_minimum_change(tie_pool, production_config, lever_scales)

    return SelectionOutcome(
        winner=winner,
        reason="selected via minimum-change prior among 1-SE ties"
        if len(tie_pool) > 1
        else "selected as sole best-median-J survivor",
        median_J_by_name=median_J_by_name,
        dominance_by_name=dominance_by_name,
        rejected=rejected,
        tie_pool=[c.name for c in tie_pool],
    )
