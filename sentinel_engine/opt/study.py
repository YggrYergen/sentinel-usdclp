"""P4 study driver (plan tasks 4.3-4.7, P4 exit gate) -- orchestrates the
EXISTING opt modules into a single, deterministic, per-asset study.

This module does not implement any optimization/validation ALGORITHM itself
-- it WIRES together modules that already implement Fable Sec 2.4-2.9:

  - ``sentinel_engine.config.load_instrument`` -- the production
    ``InstrumentConfig`` for the asset (never mutated, never written back).
  - ``sentinel_engine.opt.walkforward.anchored_walkforward`` -- outer
    train/test/embargo fold splitter (Fable Sec 2.6).
  - ``sentinel_engine.opt.levers.LEVER_GROUPS`` / ``priors_for`` /
    ``apply_overrides`` -- the staged coordinate-descent lever groups
    (Fable Sec 2.5), in their fixed stage order G4 -> G2/G3 -> G5 -> G1 ->
    G6 -> G7.
  - ``sentinel_engine.opt.fast_replay.fast_evaluate_config`` /
    ``make_fast_objective_fn`` -- the FAST replay path (the slow
    ``evaluator.evaluate_config`` oracle is never called here; see that
    module's docstring for the bit-exact equivalence proof).
  - ``sentinel_engine.opt.search.staged_search`` -- per-fold coordinate-block
    search (TPE when optuna is available, else the random-search floor;
    ``StagedSearchResult.optuna_used`` reports which ran).
  - ``sentinel_engine.opt.selection.select_winner`` -- the four selection
    guards (>=70% fold dominance, plateau, regime-balance, minimum-change
    tie-break).
  - ``sentinel_engine.opt.registry.TrialRegistry`` /
    ``deflated_sharpe_ratio`` -- every trial persisted; honest DSR for the
    winner.
  - ``sentinel_engine.opt.report.generate_report`` -- the Markdown study
    report artifact.

SAFETY INVARIANT (non-negotiable, asserted by the test suite): this module
NEVER writes to, or imports a writer for, any instrument config file or
``sentinel/config``. It only ever PROPOSES a config diff as a separate
artifact, clearly labeled "PROPOSED -- NOT APPLIED"; nothing here has a code
path that mutates ``sentinel_engine/instruments/*.yaml`` or any other live
config. ``apply_overrides`` (imported transitively via ``fast_replay``)
always returns a NEW ``InstrumentConfig``; the on-disk YAML is only ever
read (``load_instrument``), never written.

Determinism: given the same instrument + seed + window/fold params +
objective params, this module produces a byte-identical study id, selection
outcome, and proposed-diff artifact across runs. No wall-clock value ever
enters params/config/selection-affecting state; the only wall-clock reads
are ``TrialRegistry``'s own ``created`` bookkeeping column (irrelevant to
the outputs asserted for determinism) and the driver's own measured
wall-clock (reported, not part of any output artifact's content).

Windows-safe: pathlib only, explicit ``encoding="utf-8"`` on every file
open/write, no OS-version APIs.

Ambiguity resolutions (this module; spec is intentionally silent on the
exact orchestration mechanics -- see module docstrings of the wired modules
for their own ambiguity logs):

  1. **Candidate construction for `select_winner`.** Each anchored
     walk-forward fold's TRAIN window gets its own ``staged_search`` run
     (a fold-local winner). Fable Sec 2.6's selection guards (fold
     dominance, plateau, minimum-change) all require ONE candidate's J
     across MULTIPLE test folds -- a single fold's own winner evaluated
     only on its own fold cannot satisfy that. Resolution: each fold's
     winning param set becomes one named candidate
     (``fold{i}_winner``), and EVERY candidate is then re-evaluated (fast
     path, cheap) on EVERY fold's TEST window to build the full
     candidate x fold ``FoldResult`` matrix ``select_winner`` needs. This
     is the standard nested walk-forward-selection pattern implied (not
     spelled out) by Sec 2.6.
  2. **Candidate/production config shape.** ``CandidateResult.config`` and
     ``production_config`` are flat ``{lever_name: value}`` dicts covering
     the UNION of every lever in ``LEVER_GROUPS`` (production's current
     value for any lever a given fold's search didn't touch this stage --
     though in practice every stage of every fold touches every lever
     since ``staged_search`` runs the full ``LEVER_GROUPS`` sequence).
     This keeps ``config_distance``/the report's parameter diff
     well-defined across all candidates and production on a shared key set.
  3. **`score_fn` for the plateau guard.** ``select_winner``'s plateau
     check needs a callable ``config -> J`` to re-score perturbed levers.
     Resolution: the FULL study window (``window_start..window_end``),
     evaluated via the fast path -- cheap enough to run ~2x per lever
     per candidate and gives a stable, whole-history score to perturb
     around (rather than re-deriving per-fold plateau checks, which Sec
     2.6 does not specify either way).
  4. **Single-touch holdout.** The MOST RECENT fold's test window is, by
     ``anchored_walkforward``'s own construction, the latest slice of the
     study window -- exactly Fable Sec 2.6's "most recent 2 months,
     touched once" holdout. Rather than re-evaluating the winner a second
     time (which would violate "touched once"), this driver REUSES the
     winner's already-computed test-fold evaluation on that final fold
     (computed once, during candidate-matrix construction) as the
     holdout result -- reported win-or-lose, verbatim.
  5. **Regime results.** No ``RegimeLabeler`` exists yet in this codebase
     (Phase 6/2.9 future work per the plan) -- ``CandidateResult.
     regime_results`` is always ``()``here, so ``select_winner``'s
     regime-balance guard trivially passes for every candidate (per
     ``selection.regime_balance_check``'s own documented "empty sequence
     -> nothing to check" contract). Flagged here, not silently assumed
     correct: a real regime-balance gate needs the regime labeler wired
     in a follow-up task.
  6. **Degenerate few/zero-fold windows.** ``anchored_walkforward`` returns
     an EMPTY list when the window is too short for even one full
     ``step``+``test_span``. Rather than crashing, this driver falls back
     to a single DEGENERATE fold spanning the entire window for both
     "train" and "test" (no real train/test split, no purge) and records
     an honest note in the result (``StudyResult.notes``) and in the
     report body (via the leaderboard/holdout sections, which render
     whatever they are given verbatim) -- an honest small-sample report,
     never a silent pass-through as if real walk-forward validation had
     occurred.
  7. **DSR inputs.** ``winner_returns`` = the winner's per-fold
     ``candidate_J`` values (one point per test fold -- honestly small for
     short-history assets per the plan's USDCLP-vs-gold/nasdaq depth
     note). ``trial_sharpe_std`` is estimated from the ``sharpe_daily_R``
     metric already recorded on every persisted trial (the nearest
     "per-trial Sharpe" figure this pipeline computes) rather than
     inventing a new figure. DSR is computed only when both the trial
     count (>=2) and per-fold return count (>=2) support it; otherwise
     ``report.generate_report`` renders the DSR section as explicitly
     "not computed" (never faked), per its own contract.
  8. **`study_id`.** A sha256-based digest of every argument that can
     affect the study's outputs (instrument, seed, trial budget, window
     bounds, fold params, objective params, production config hash) --
     no wall-clock, no PID, no run-order dependency, so two invocations
     with identical arguments always produce the identical id.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from sentinel_engine.config import InstrumentConfig, config_hash, load_instrument
from sentinel_engine.lake.store import read_bars
from sentinel_engine.opt.fast_replay import FastReplayCache, fast_evaluate_config
from sentinel_engine.opt.levers import LEVER_GROUPS, priors_for
from sentinel_engine.opt.objective import ObjectiveResult
from sentinel_engine.opt.registry import DeflatedSharpeResult, TrialRegistry, deflated_sharpe_ratio
from sentinel_engine.opt.report import HoldoutResult, generate_report
from sentinel_engine.opt.search import StagedSearchResult, staged_search
from sentinel_engine.opt.selection import (
    DEFAULT_PLATEAU_PERTURB_FRAC,
    CandidateResult,
    FoldResult,
    SelectionOutcome,
    select_winner,
)
from sentinel_engine.opt.walkforward import Fold, anchored_walkforward

DEFAULT_LAKE_ROOT = Path("D:/FOREX/data/lake")

#: total CPU-core budget the P4 study layer is allowed to consume, whether
#: running as one study (--workers 6) or split across a fleet of concurrent
#: studies (run_fleet.py: core_budget // n_instruments workers each). Single
#: source of truth for both `study.py`'s own `--workers` default reasoning
#: and `run_fleet.py`'s allocation math.
DEFAULT_CORE_BUDGET = 6


# ─────────────────────── process-pool worker plumbing ──────────────────────
#
# Windows uses `spawn` (no fork): every object passed into a pool worker must
# be picklable, and the worker callables themselves must be top-level (module
# scope), never closures/lambdas/nested defs -- both requirements are met
# below. Each worker process gets exactly ONE clean core: the pool
# `initializer` pins BLAS/OpenMP thread pools to 1 so numpy inside
# `fast_evaluate_config` never oversubscribes beyond the `--workers` budget,
# and creates a worker-process-LOCAL `FastReplayCache` (module-global to the
# worker process only -- garbage-collected when the pool shuts down, never
# shared across processes, so it has zero effect on any study output; see
# `FastReplayCache`'s own docstring for the byte-identical-with-or-without-
# cache guarantee this relies on).

_WORKER_CACHE: Optional[FastReplayCache] = None


def _pool_initializer() -> None:
    """`ProcessPoolExecutor` initializer: pin every BLAS/OpenMP thread pool
    to 1 (so N worker processes == N cores, never N*threads), and create this
    worker's own private `FastReplayCache`."""
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"
    global _WORKER_CACHE
    _WORKER_CACHE = FastReplayCache()


def _worker_eval(
    task_id: object,
    cfg: InstrumentConfig,
    params: Dict[str, float],
    lake_root: Path,
    window_start: datetime,
    window_end: datetime,
    symbols: Dict[str, str],
    obj_kw: Dict[str, object],
) -> Tuple[object, ObjectiveResult]:
    """Top-level (picklable, spawn-safe) unit of work submitted to the pool:
    one `fast_evaluate_config` call, tagged with a caller-chosen `task_id` so
    the parent can route the result back to the right fold/candidate/lever
    slot regardless of completion order. Uses this worker process's own
    private cache (created once by `_pool_initializer`, reused across every
    task this worker handles)."""
    result = fast_evaluate_config(
        cfg, params, lake_root, window_start, window_end, symbols,
        cache=_WORKER_CACHE, **obj_kw,
    )
    return task_id, result


def _make_pool(workers: int) -> Optional[ProcessPoolExecutor]:
    """`None` for `workers <= 1` (serial path -- no pool overhead, and the
    exact same code path as before parallelism was added, for the cheapest
    possible determinism argument)."""
    if workers <= 1:
        return None
    return ProcessPoolExecutor(max_workers=workers, initializer=_pool_initializer)


@dataclass(frozen=True)
class StudyResult:
    """Full result of one ``run_study`` invocation."""

    study_id: str
    instrument: str
    folds: List[Fold]
    fold_stage_results: List[StagedSearchResult]
    candidates: List[CandidateResult]
    production_config: Dict[str, float]
    selection_outcome: SelectionOutcome
    dsr: Optional[DeflatedSharpeResult]
    holdout: Optional[HoldoutResult]
    report_text: str
    report_path: Path
    diff_path: Path
    diff_text: str
    trade_counts: Dict[str, int]
    optuna_used: bool
    wall_clock_seconds: float
    notes: List[str] = field(default_factory=list)


def _parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp; naive inputs are assumed UTC (documented
    leniency -- callers wanting exactness should pass explicit offsets)."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _flatten_production_config(cfg: InstrumentConfig) -> Dict[str, float]:
    """Flat ``{lever_name: current_value}`` over every lever in
    ``LEVER_GROUPS`` (ambiguity #2)."""
    priors = priors_for(cfg)
    flat: Dict[str, float] = {}
    for group in LEVER_GROUPS:
        flat.update(priors[group.name])
    return flat


def _lever_scales() -> Dict[str, float]:
    """Per-lever normalizer (search-range width) for ``config_distance``."""
    return {p.name: float(p.high - p.low) for g in LEVER_GROUPS for p in g.params}


def _compute_study_id(
    *,
    instrument: str,
    cfg_hash_val: str,
    seed: int,
    trials: int,
    test_span_days: float,
    step_days: float,
    embargo_days: float,
    window_start: datetime,
    window_end: datetime,
    horizon: int,
    tp_r: float,
    sl: float,
    n_min: int,
    win_rate_min: float,
) -> str:
    payload = {
        "instrument": instrument,
        "cfg_hash": cfg_hash_val,
        "seed": seed,
        "trials": trials,
        "test_span_days": test_span_days,
        "step_days": step_days,
        "embargo_days": embargo_days,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "horizon": horizon,
        "tp_r": tp_r,
        "sl": sl,
        "n_min": n_min,
        "win_rate_min": win_rate_min,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"{instrument}_{digest}"


def _build_folds(
    window_start: datetime,
    window_end: datetime,
    test_span: timedelta,
    step: timedelta,
    embargo: timedelta,
    notes: List[str],
) -> List[Fold]:
    """Wraps ``anchored_walkforward``; falls back to a single degenerate
    fold (ambiguity #6) rather than crashing on too-short a window."""
    folds = anchored_walkforward([window_start, window_end], test_span, step, embargo)
    if folds:
        return folds
    notes.append(
        "DEGENERATE WALK-FORWARD: the study window was too short for a "
        "single real anchored-walk-forward fold (test_span + step did not "
        "fit). Falling back to ONE degenerate fold spanning the full "
        "window for both train and test -- there is NO real train/test "
        "separation and NO embargo purge in this fold; treat any result "
        "from this study as an honest small-sample smoke result only, "
        "never as a validated selection."
    )
    degenerate = Fold(
        index=0,
        train_start=window_start,
        split=window_end,
        embargo=embargo,
        train_end=window_end,
        test_start=window_start,
        test_end=window_end,
    )
    return [degenerate]


def _make_recording_objective_fn(
    cfg: InstrumentConfig,
    lake_root: Path,
    window: Tuple[datetime, datetime],
    symbols: Dict[str, str],
    registry: TrialRegistry,
    study_id: str,
    fold_index: int,
    metrics_log: List[Dict[str, float]],
    on_trial: Optional[Callable[[float, float, int], None]] = None,
    cache: Optional[FastReplayCache] = None,
    **obj_kw: object,
) -> Callable[[Dict[str, float]], float]:
    """Fast-path objective wrapper that persists EVERY trial to the
    registry (Fable Sec 2.6/2.10: "all trials persisted") and appends the
    full metric set to ``metrics_log`` for in-process trade-count summary
    (avoids a redundant registry round-trip just to prove non-vacuity).

    ``on_trial(elapsed_seconds, score, n_trades)`` is an optional progress
    heartbeat invoked after every evaluation (diagnostic only -- it never
    affects any study output, preserving determinism).

    ``cache`` (optional): a study-scoped `FastReplayCache` passed through
    verbatim to `fast_evaluate_config` -- purely a speed optimization
    (P4 speed layer); `fast_evaluate_config` guarantees byte-identical
    output with `cache` supplied vs `cache=None`, so this never affects
    any study output."""
    import time as _time

    def _fn(params: Dict[str, float]) -> float:
        _t = _time.perf_counter()
        result: ObjectiveResult = fast_evaluate_config(
            cfg, params, lake_root, window[0], window[1], symbols, cache=cache, **obj_kw
        )
        elapsed = _time.perf_counter() - _t
        metrics = dict(result.metrics)
        metrics["fold_index"] = fold_index
        metrics["phase"] = "train_search"
        registry.record_trial(study_id, params, metrics)
        metrics_log.append(metrics)
        if on_trial is not None:
            on_trial(elapsed, result.score, int(metrics.get("n_trades", 0)))
        return result.score

    return _fn


@dataclass(frozen=True)
class _RecordedTrial:
    """One (params, metrics) pair collected by a worker-process fold task,
    to be persisted to the registry by the PARENT process afterwards (the
    registry is single-writer SQLite; worker processes must never touch it
    -- see ``run_study``'s parent-writes-registry comment block)."""

    params: Dict[str, float]
    metrics: Dict[str, float]


def _make_collecting_objective_fn(
    cfg: InstrumentConfig,
    lake_root: Path,
    window: Tuple[datetime, datetime],
    symbols: Dict[str, str],
    fold_index: int,
    recorded: List[_RecordedTrial],
    cache: Optional[FastReplayCache] = None,
    **obj_kw: object,
) -> Callable[[Dict[str, float]], float]:
    """Same evaluation as ``_make_recording_objective_fn`` but COLLECTS every
    trial into ``recorded`` instead of writing to a ``TrialRegistry`` --
    used inside a worker process (parallel fold-search path), where writing
    to the (single-writer, SQLite-backed) registry directly would be unsafe.
    The parent process persists every collected trial afterwards, in
    deterministic (fold-then-trial) order -- see ``_run_fold_search_task``
    and its caller."""

    def _fn(params: Dict[str, float]) -> float:
        result: ObjectiveResult = fast_evaluate_config(
            cfg, params, lake_root, window[0], window[1], symbols, cache=cache, **obj_kw
        )
        metrics = dict(result.metrics)
        metrics["fold_index"] = fold_index
        metrics["phase"] = "train_search"
        recorded.append(_RecordedTrial(params=dict(params), metrics=metrics))
        return result.score

    return _fn


def _run_fold_search_task(
    fold_index: int,
    train_start: datetime,
    train_end: datetime,
    cfg: InstrumentConfig,
    lake_root: Path,
    symbols: Dict[str, str],
    trials: int,
    seed: int,
    priors: Mapping[str, Mapping[str, float]],
    obj_kw: Dict[str, object],
) -> Tuple[int, StagedSearchResult, List[_RecordedTrial]]:
    """Top-level (picklable), one-fold unit of work for the parallel
    per-fold train-search phase (folds are independent -> distribute across
    the pool; TPE/random search WITHIN one fold stays serial, per the task
    brief -- only the across-fold dimension is parallelized here).

    Runs entirely inside a worker process using that worker's own private
    ``FastReplayCache`` (module-global to the worker, set by
    ``_pool_initializer``) -- never touches the registry (workers must not
    write to single-writer SQLite; the parent records every returned trial
    afterwards, in deterministic fold order).
    """
    recorded: List[_RecordedTrial] = []
    obj_fn = _make_collecting_objective_fn(
        cfg, lake_root, (train_start, train_end), symbols, fold_index, recorded,
        cache=_WORKER_CACHE, **obj_kw,
    )
    stage_result = staged_search(
        LEVER_GROUPS, obj_fn, n_trials_per_stage=trials, seed=seed,
        priors=priors, use_tpe=True,
    )
    return fold_index, stage_result, recorded


def _render_proposed_diff(
    winner: Optional[CandidateResult],
    production_config: Mapping[str, float],
    diff_tol: float = 1e-9,
) -> str:
    """A standalone "PROPOSED -- NOT APPLIED" artifact (never auto-applied;
    the safety invariant is enforced by this module having no code path
    that writes any instrument config file at all)."""
    lines = [
        "# PROPOSED CONFIG DIFF -- NOT APPLIED",
        "",
        "This file is a PROPOSAL ONLY. Nothing in this study driver writes "
        "to any instrument config file. A human must review this diff and "
        "manually edit the instrument YAML to adopt it.",
        "",
    ]
    if winner is None:
        lines.append("No winner was selected by this study -- no diff is proposed.")
        lines.append("")
        lines.append("STATUS: PROPOSED -- NOT APPLIED (no-op).")
        return "\n".join(lines) + "\n"

    lines.append(f"Proposed winner candidate: `{winner.name}`")
    lines.append("")
    all_keys = sorted(set(winner.config) | set(production_config))
    rows = []
    for key in all_keys:
        prod_val = production_config.get(key)
        win_val = winner.config.get(key)
        if prod_val is None or win_val is None:
            changed = True
        else:
            changed = abs(float(win_val) - float(prod_val)) > diff_tol
        if changed:
            rows.append((key, prod_val, win_val))

    if not rows:
        lines.append("No parameter changes proposed -- winner is identical to production.")
    else:
        lines.append("| Lever | Production (current) | Proposed |")
        lines.append("|---|---|---|")
        for key, prod_val, win_val in rows:
            lines.append(f"| {key} | {prod_val} | {win_val} |")
    lines.append("")
    lines.append("STATUS: **PROPOSED -- NOT APPLIED**. No file on disk has been modified.")
    return "\n".join(lines) + "\n"


def run_study(
    instrument: str,
    *,
    lake_root: Path = DEFAULT_LAKE_ROOT,
    out_dir: Path,
    trials: int = 30,
    seed: int = 20260707,
    test_span_days: float = 60.0,
    step_days: float = 60.0,
    embargo_days: float = 1.0,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    horizon: int = 30,
    tp_r: float = 1.5,
    sl: float = 2.0,
    n_min: int = 30,
    win_rate_min: float = 0.35,
    progress: bool = True,
    workers: int = 1,
) -> StudyResult:
    """Run one full P4 study for ``instrument`` on the real lake at
    ``lake_root``, writing artifacts to ``out_dir``.

    Never mutates ``lake_root`` or any instrument config file. See the
    module docstring's ambiguity log for how candidates/folds/holdout/DSR
    are constructed from the wired modules.

    ``progress`` (default True): stream a live heartbeat to stderr and to
    ``out_dir/study.log`` (per-fold, per-trial with seconds-per-eval, and
    per-phase). Purely diagnostic -- it touches no study output, so
    determinism is unaffected.

    ``workers`` (default 1 == fully serial, byte-identical to the
    pre-parallelism code path): number of worker PROCESSES used to
    parallelize this study's three INDEPENDENT-eval phases -- (1) per-fold
    train search (folds distributed across the pool; single-fold assets get
    no fold parallelism here, Amdahl), (2) the candidate x fold test matrix,
    and (3) the plateau-guard perturbation pre-warm. TPE/random search
    WITHIN one fold stays serial (coordinate descent has a sequential stage
    dependency). Workers are process-isolated (Windows spawn-safe): each
    gets its own private ``FastReplayCache`` and pinned single-threaded BLAS
    (see ``_pool_initializer``), and NEVER writes to the registry directly
    -- this process (the parent) is the sole registry writer, persisting
    every trial (from every phase, from every worker) in deterministic
    order. DETERMINISM CONTRACT: for any ``workers >= 1``, ``run_study``'s
    ``study_id``, ``selection_outcome``, ``diff_text``, and ``report_text``
    are byte-identical -- parallelism changes only wall-clock, never any
    output artifact (see ``tests/opt/test_study.py``'s
    ``test_parallel_matches_serial_determinism``).
    """
    import sys
    import time

    t0 = time.perf_counter()
    notes: List[str] = []

    lake_root = Path(lake_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log_path = out_dir / "study.log"
    _log_fh = log_path.open("a", encoding="utf-8")

    def _log(msg: str) -> None:
        line = f"[{time.perf_counter() - t0:8.1f}s] {msg}"
        _log_fh.write(line + "\n")
        _log_fh.flush()
        if progress:
            print(line, file=sys.stderr, flush=True)

    cfg = load_instrument(instrument)
    symbols = cfg.symbols

    if window_start is None or window_end is None:
        m1 = read_bars(lake_root, cfg.target, 1)
        if m1.empty:
            raise ValueError(
                f"run_study: no M1 data in the lake for target {cfg.target!r} "
                f"({instrument!r}) at {lake_root} -- cannot determine a study window"
            )
        window_start = window_start or m1.index.min().to_pydatetime()
        window_end = window_end or m1.index.max().to_pydatetime()

    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise ValueError("run_study: window_start/window_end must be tz-aware")

    test_span = timedelta(days=test_span_days)
    step = timedelta(days=step_days)
    embargo = timedelta(days=embargo_days)

    folds = _build_folds(window_start, window_end, test_span, step, embargo, notes)
    if len(folds) == 1 and "DEGENERATE" not in "".join(notes):
        notes.append(
            "Only 1 walk-forward fold available for this window -- honest "
            "small-sample regime (per plan: gold/nasdaq have ~3.5 months of "
            "intraday history vs USDCLP's ~17 months; fewer folds is "
            "expected, not an error). Deflated Sharpe / dominance figures "
            "are reported as-is with this caveat."
        )

    cfg_hash_val = config_hash(cfg)
    study_id = _compute_study_id(
        instrument=instrument,
        cfg_hash_val=cfg_hash_val,
        seed=seed,
        trials=trials,
        test_span_days=test_span_days,
        step_days=step_days,
        embargo_days=embargo_days,
        window_start=window_start,
        window_end=window_end,
        horizon=horizon,
        tp_r=tp_r,
        sl=sl,
        n_min=n_min,
        win_rate_min=win_rate_min,
    )

    obj_kw = dict(horizon=horizon, tp_r=tp_r, sl=sl, n_min=n_min, win_rate_min=win_rate_min)
    priors = priors_for(cfg)
    production_config = _flatten_production_config(cfg)
    lever_scales = _lever_scales()

    # ONE study-scoped fast-replay cache, shared across every fast_evaluate_config
    # call this study makes (train search, candidate x fold test matrix, plateau
    # score_fn). Purely a speed optimization (P4 speed layer) -- fast_evaluate_config
    # guarantees byte-identical output with this cache supplied vs cache=None, so
    # this never affects any study output. Garbage-collected with run_study's own
    # frame; no module-global mutable state, no cross-study/test leakage.
    fast_cache = FastReplayCache()

    registry = TrialRegistry(
        db_path=out_dir / "registry.sqlite", parquet_dir=out_dir / "registry_parquet"
    )
    registry.ensure_study(study_id, seed=seed, notes=f"P4 study instrument={instrument}")

    trade_counts: Dict[str, int] = {}
    optuna_used = False

    n_groups = len(LEVER_GROUPS)
    _log(
        f"study_id={study_id} instrument={instrument} folds={len(folds)} "
        f"groups={n_groups} trials/stage={trials} "
        f"=> ~{len(folds) * n_groups * trials} train evals expected "
        f"(window {window_start.isoformat()}..{window_end.isoformat()})"
    )

    # ---- per-fold TRAIN search -> one candidate config per fold ----
    # Folds are independent (Amdahl: a single-fold asset like gold gets no
    # fold parallelism here -- expected). ``workers<=1`` takes the ORIGINAL
    # serial code path verbatim (unchanged since before parallelism was
    # added) for the cheapest possible determinism argument; ``workers>1``
    # distributes whole per-fold ``staged_search`` runs across a process
    # pool (TPE/random search WITHIN one fold stays serial -- coordinate
    # descent has a sequential stage dependency). Workers never touch the
    # registry; every collected trial is persisted by THIS (parent) process
    # afterwards, in deterministic fold order, keeping SQLite single-writer.
    fold_stage_results_by_index: Dict[int, StagedSearchResult] = {}
    fold_winner_params_by_index: Dict[int, Dict[str, float]] = {}

    if workers <= 1:
        for fold in folds:
            _log(
                f"FOLD {fold.index + 1}/{len(folds)} train search START "
                f"(train {fold.train_start.isoformat()}..{fold.train_end.isoformat()})"
            )
            metrics_log: List[Dict[str, float]] = []
            _counter = {"n": 0, "t": 0.0}

            def _heartbeat(elapsed: float, score: float, n_trades: int, _c=_counter, _fi=fold.index) -> None:
                _c["n"] += 1
                _c["t"] += elapsed
                if _c["n"] % 5 == 0 or elapsed > 15.0:
                    _log(
                        f"  fold{_fi} trial {_c['n']}: {elapsed:5.1f}s/eval "
                        f"(avg {_c['t'] / _c['n']:5.1f}s), score={score:.4f}, n_trades={n_trades}"
                    )

            obj_fn = _make_recording_objective_fn(
                cfg, lake_root, (fold.train_start, fold.train_end), symbols,
                registry, study_id, fold.index, metrics_log, on_trial=_heartbeat,
                cache=fast_cache, **obj_kw,
            )
            stage_result = staged_search(
                LEVER_GROUPS, obj_fn, n_trials_per_stage=trials, seed=seed,
                priors=priors, use_tpe=True,
            )
            optuna_used = optuna_used or stage_result.optuna_used
            fold_stage_results_by_index[fold.index] = stage_result
            _log(
                f"FOLD {fold.index + 1}/{len(folds)} train search DONE "
                f"({_counter['n']} evals, {_counter['t']:.1f}s total, "
                f"avg {_counter['t'] / max(_counter['n'], 1):.1f}s/eval)"
            )

            winner_full = dict(production_config)
            winner_full.update(stage_result.best_params)
            fold_winner_params_by_index[fold.index] = winner_full

            train_n_trades = [m.get("n_trades", 0) for m in metrics_log]
            trade_counts[f"fold{fold.index}_train_search_max_n_trades"] = int(max(train_n_trades, default=0))
    else:
        _log(f"FOLD train search (PARALLEL, {workers} workers) START for {len(folds)} fold(s)")
        pool = _make_pool(workers)
        assert pool is not None
        try:
            futures = {
                pool.submit(
                    _run_fold_search_task,
                    fold.index, fold.train_start, fold.train_end,
                    cfg, lake_root, symbols, trials, seed, priors, obj_kw,
                ): fold.index
                for fold in folds
            }
            fold_task_results: Dict[int, Tuple[StagedSearchResult, List[_RecordedTrial]]] = {}
            for future in futures:
                fold_index, stage_result, recorded = future.result()
                fold_task_results[fold_index] = (stage_result, recorded)
        finally:
            pool.shutdown(wait=True)

        # Parent writes every trial to the registry, and logs, in
        # deterministic FOLD ORDER (not completion order) -- this is what
        # keeps the persisted registry order, and the progress log, a
        # reproducible function of the study's inputs alone.
        for fold in folds:
            stage_result, recorded = fold_task_results[fold.index]
            _log(
                f"FOLD {fold.index + 1}/{len(folds)} train search DONE (parallel worker) "
                f"({len(recorded)} evals)"
            )
            for rec in recorded:
                registry.record_trial(study_id, rec.params, rec.metrics)
            optuna_used = optuna_used or stage_result.optuna_used
            fold_stage_results_by_index[fold.index] = stage_result

            winner_full = dict(production_config)
            winner_full.update(stage_result.best_params)
            fold_winner_params_by_index[fold.index] = winner_full

            train_n_trades = [rec.metrics.get("n_trades", 0) for rec in recorded]
            trade_counts[f"fold{fold.index}_train_search_max_n_trades"] = int(max(train_n_trades, default=0))
        _log("FOLD train search (PARALLEL) DONE for all folds")

    fold_stage_results: List[StagedSearchResult] = [fold_stage_results_by_index[f.index] for f in folds]
    fold_winner_params: List[Tuple[int, Dict[str, float]]] = [
        (f.index, fold_winner_params_by_index[f.index]) for f in folds
    ]

    # ---- evaluate every candidate on EVERY fold's TEST window (ambiguity #1) ----
    # Every (candidate, fold) cell needs BOTH the candidate's eval and
    # production's eval on that fold's test window -- all independent ->
    # distribute across the pool when workers>1. workers<=1 takes the
    # ORIGINAL serial code path verbatim.
    _n_matrix = len(fold_winner_params) * len(folds) * 2
    _log(f"CANDIDATE x FOLD test matrix START ({_n_matrix} test evals expected)")
    candidates: List[CandidateResult] = []
    test_eval_by_candidate_fold: Dict[str, Dict[int, ObjectiveResult]] = {}

    if workers <= 1:
        for cand_fold_idx, cand_params in fold_winner_params:
            cand_name = f"fold{cand_fold_idx}_winner"
            fold_results: List[FoldResult] = []
            test_eval_by_candidate_fold[cand_name] = {}
            for fold in folds:
                cand_eval = fast_evaluate_config(
                    cfg, cand_params, lake_root, fold.test_start, fold.test_end, symbols,
                    cache=fast_cache, **obj_kw
                )
                prod_eval = fast_evaluate_config(
                    cfg, {}, lake_root, fold.test_start, fold.test_end, symbols,
                    cache=fast_cache, **obj_kw
                )
                registry.record_trial(
                    study_id, cand_params,
                    {**cand_eval.metrics, "fold_index": fold.index, "phase": "test", "candidate": cand_name},
                )
                fold_results.append(
                    FoldResult(fold_index=fold.index, candidate_J=cand_eval.score, production_J=prod_eval.score)
                )
                test_eval_by_candidate_fold[cand_name][fold.index] = cand_eval
                trade_counts[f"{cand_name}__test_fold{fold.index}_n_trades"] = int(cand_eval.metrics["n_trades"])

            candidates.append(
                CandidateResult(name=cand_name, config=cand_params, fold_results=fold_results, regime_results=())
            )
    else:
        _log(f"CANDIDATE x FOLD test matrix (PARALLEL, {workers} workers) START")
        # task_id = (cand_name, fold_index, "cand"|"prod") -> deterministic key
        # so results route back regardless of pool completion order.
        matrix_tasks: List[Tuple[Tuple[str, int, str], Dict[str, float], datetime, datetime]] = []
        for cand_fold_idx, cand_params in fold_winner_params:
            cand_name = f"fold{cand_fold_idx}_winner"
            for fold in folds:
                matrix_tasks.append(((cand_name, fold.index, "cand"), cand_params, fold.test_start, fold.test_end))
                matrix_tasks.append(((cand_name, fold.index, "prod"), {}, fold.test_start, fold.test_end))

        pool = _make_pool(workers)
        assert pool is not None
        try:
            futures = [
                pool.submit(
                    _worker_eval, task_id, cfg, params, lake_root,
                    test_start, test_end, symbols, obj_kw,
                )
                for task_id, params, test_start, test_end in matrix_tasks
            ]
            matrix_results: Dict[Tuple[str, int, str], ObjectiveResult] = {}
            for future in futures:
                task_id, result = future.result()
                matrix_results[task_id] = result
        finally:
            pool.shutdown(wait=True)

        # Parent writes to the registry + builds candidates in deterministic
        # (candidate order, then fold order) sequence -- matches the serial
        # path's write order exactly.
        for cand_fold_idx, cand_params in fold_winner_params:
            cand_name = f"fold{cand_fold_idx}_winner"
            fold_results = []
            test_eval_by_candidate_fold[cand_name] = {}
            for fold in folds:
                cand_eval = matrix_results[(cand_name, fold.index, "cand")]
                prod_eval = matrix_results[(cand_name, fold.index, "prod")]
                registry.record_trial(
                    study_id, cand_params,
                    {**cand_eval.metrics, "fold_index": fold.index, "phase": "test", "candidate": cand_name},
                )
                fold_results.append(
                    FoldResult(fold_index=fold.index, candidate_J=cand_eval.score, production_J=prod_eval.score)
                )
                test_eval_by_candidate_fold[cand_name][fold.index] = cand_eval
                trade_counts[f"{cand_name}__test_fold{fold.index}_n_trades"] = int(cand_eval.metrics["n_trades"])

            candidates.append(
                CandidateResult(name=cand_name, config=cand_params, fold_results=fold_results, regime_results=())
            )
        _log("CANDIDATE x FOLD test matrix (PARALLEL) DONE")

    # ---- selection (ambiguity #3: whole-window fast eval as plateau score_fn) ----
    _plat = {"n": 0, "t": 0.0}
    _log(
        "SELECTION START (plateau guard re-scores perturbed levers over the "
        "FULL window via fast eval -- typically the most expensive phase)"
    )

    if workers <= 1:
        def score_fn(params: Mapping[str, float]) -> float:
            _t = time.perf_counter()
            s = fast_evaluate_config(
                cfg, dict(params), lake_root, window_start, window_end, symbols,
                cache=fast_cache, **obj_kw
            ).score
            _plat["n"] += 1
            _plat["t"] += time.perf_counter() - _t
            if _plat["n"] % 5 == 0:
                _log(f"  plateau eval {_plat['n']}: avg {_plat['t'] / _plat['n']:.1f}s/eval")
            return s
    else:
        # ---- parallel plateau PRE-WARM ----
        # `select_winner` -> `plateau_check` calls `score_fn` in a SERIAL loop
        # (selection.py is off-limits -- not modified). Instead: replicate
        # `plateau_check`'s EXACT perturbation enumeration (as called from
        # `select_winner`: `levers=list(cand.config.keys())` -- i.e. EVERY
        # config key, not just nonzero ones -- `base*(1 +/- frac)` per
        # lever) for every candidate (conservative superset -- select_winner
        # only actually plateau-checks dominance-survivors, but pre-warming
        # every candidate costs nothing extra in parallel and guarantees a
        # cache hit regardless of which candidates survive dominance),
        # evaluate the whole perturbation set (baseline + up/down per lever)
        # over the FULL study window in the pool, and hand `select_winner`
        # a lookup `score_fn` with a serial fallback for safety (identical
        # numeric result either way -- same window, same obj_kw -- so the
        # selection outcome is unaffected regardless of whether a given
        # call is a precomputed hit or a fallback miss).
        _log(f"PLATEAU PRE-WARM (PARALLEL, {workers} workers) START")

        def _canonical_key(params: Mapping[str, float]) -> Tuple[Tuple[str, float], ...]:
            """Float-safe canonical key: sorted (name, value) pairs, values
            rounded to a fixed precision so trivially-equal floats produced
            by independent perturbation-enumeration passes always collide
            to the same dict key."""
            return tuple(sorted((k, round(float(v), 12)) for k, v in params.items()))

        prewarm_configs: Dict[Tuple[Tuple[str, float], ...], Dict[str, float]] = {}
        for cand in candidates:
            base_config = dict(cand.config)
            prewarm_configs[_canonical_key(base_config)] = base_config
            levers = list(base_config.keys())
            for lever in levers:
                base_val = base_config[lever]
                if not isinstance(base_val, (int, float)):
                    continue
                for sign in (1.0, -1.0):
                    perturbed = dict(base_config)
                    perturbed[lever] = base_val * (1.0 + sign * DEFAULT_PLATEAU_PERTURB_FRAC)
                    prewarm_configs[_canonical_key(perturbed)] = perturbed

        pool = _make_pool(workers)
        assert pool is not None
        try:
            items = list(prewarm_configs.items())
            futures = [
                pool.submit(
                    _worker_eval, key, cfg, params, lake_root,
                    window_start, window_end, symbols, obj_kw,
                )
                for key, params in items
            ]
            precomputed: Dict[Tuple[Tuple[str, float], ...], float] = {}
            for future in futures:
                key, result = future.result()
                precomputed[key] = result.score
        finally:
            pool.shutdown(wait=True)
        _log(f"PLATEAU PRE-WARM (PARALLEL) DONE ({len(precomputed)} distinct configs evaluated)")

        def score_fn(params: Mapping[str, float]) -> float:
            _t = time.perf_counter()
            key = _canonical_key(params)
            if key in precomputed:
                s = precomputed[key]
            else:
                # Serial fallback -- guarantees correctness even if the
                # perturbation enumeration above ever drifts from
                # selection.py's own (identical window/obj_kw, so the
                # numeric result is unaffected either way).
                s = fast_evaluate_config(
                    cfg, dict(params), lake_root, window_start, window_end, symbols,
                    cache=fast_cache, **obj_kw
                ).score
            _plat["n"] += 1
            _plat["t"] += time.perf_counter() - _t
            if _plat["n"] % 5 == 0:
                _log(f"  plateau eval {_plat['n']}: avg {_plat['t'] / _plat['n']:.1f}s/eval")
            return s

    selection_outcome = select_winner(
        candidates, production_config, score_fn=score_fn, lever_scales=lever_scales,
    )
    _log(
        f"SELECTION DONE ({_plat['n']} plateau evals, {_plat['t']:.1f}s). "
        f"winner={selection_outcome.winner.name if selection_outcome.winner else None}"
    )

    # ---- single-touch holdout: reuse the winner's last-fold test eval (ambiguity #4) ----
    holdout: Optional[HoldoutResult] = None
    if selection_outcome.winner is not None:
        winner_name = selection_outcome.winner.name
        last_fold = folds[-1]
        winner_last_eval = test_eval_by_candidate_fold[winner_name][last_fold.index]
        holdout = HoldoutResult(
            config_name=winner_name,
            period_start=last_fold.test_start.isoformat(),
            period_end=last_fold.test_end.isoformat(),
            metrics=dict(winner_last_eval.metrics),
            passed=winner_last_eval.gates_passed,
            notes=(
                "Holdout = the most recent walk-forward fold's test window, "
                "reused verbatim from the selection-time evaluation (single "
                "touch -- never re-run)."
                + (" DEGENERATE fold (no real train/test split)." if len(folds) == 1 and folds[0].train_start == folds[0].test_start else "")
            ),
        )

    # ---- deflated Sharpe (ambiguity #7) ----
    dsr: Optional[DeflatedSharpeResult] = None
    if selection_outcome.winner is not None:
        winner_returns = [fr.candidate_J for fr in selection_outcome.winner.fold_results]
        n_trials_total = registry.trial_count(study_id)
        if len(winner_returns) >= 2 and n_trials_total >= 2:
            all_trials = registry.get_all_trials(study_id)
            sharpe_series = [
                t.metrics["sharpe_daily_R"] for t in all_trials if "sharpe_daily_R" in t.metrics
            ]
            trial_sharpe_std = float(np.std(sharpe_series, ddof=1)) if len(sharpe_series) >= 2 else None
            dsr = deflated_sharpe_ratio(winner_returns, n_trials_total, trial_sharpe_std=trial_sharpe_std)
        else:
            notes.append(
                "DSR not computed: fewer than 2 test folds and/or fewer than "
                "2 registry trials -- honestly reported as 'not computed' in "
                "the study report rather than faked."
            )

    # ---- report + proposed diff artifacts ----
    report_path = out_dir / f"{study_id}_report.md"
    diff_path = out_dir / f"{study_id}_proposed_diff.md"

    report_text = generate_report(
        study_id=study_id,
        registry=registry,
        selection_outcome=selection_outcome,
        production_config=production_config,
        holdout=holdout,
        regime_metrics=(),
        dsr=dsr,
        out_path=report_path,
    )
    diff_text = _render_proposed_diff(selection_outcome.winner, production_config)
    diff_path.write_text(diff_text, encoding="utf-8")

    registry.close()

    wall_clock = time.perf_counter() - t0
    _log(f"STUDY DONE in {wall_clock:.1f}s. report={report_path.name} diff={diff_path.name}")
    _log_fh.close()

    return StudyResult(
        study_id=study_id,
        instrument=instrument,
        folds=folds,
        fold_stage_results=fold_stage_results,
        candidates=candidates,
        production_config=production_config,
        selection_outcome=selection_outcome,
        dsr=dsr,
        holdout=holdout,
        report_text=report_text,
        report_path=report_path,
        diff_path=diff_path,
        diff_text=diff_text,
        trade_counts=trade_counts,
        optuna_used=optuna_used,
        wall_clock_seconds=wall_clock,
        notes=notes,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "SENTINEL P4 study driver -- runs a full anchored walk-forward "
            "optimization study for one instrument on the real Parquet lake "
            "and emits a Markdown report + a PROPOSED (never auto-applied) "
            "config-diff artifact."
        )
    )
    parser.add_argument("--instrument", required=True, help="e.g. gold, nasdaq, usdclp")
    parser.add_argument("--trials", type=int, default=30, help="n_trials_per_stage")
    parser.add_argument("--seed", type=int, default=20260707)
    parser.add_argument("--lake-root", type=str, default=str(DEFAULT_LAKE_ROOT))
    parser.add_argument("--out-dir", type=str, required=True)
    parser.add_argument("--test-span-days", type=float, default=60.0)
    parser.add_argument("--step-days", type=float, default=60.0)
    parser.add_argument("--embargo-days", type=float, default=1.0)
    parser.add_argument("--window-start", type=str, default=None, help="ISO-8601; default: full lake depth")
    parser.add_argument("--window-end", type=str, default=None, help="ISO-8601; default: full lake depth")
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--tp-r", type=float, default=1.5)
    parser.add_argument("--sl", type=float, default=2.0)
    parser.add_argument("--n-min", type=int, default=30)
    parser.add_argument("--win-rate-min", type=float, default=0.35)
    parser.add_argument(
        "--workers", type=int, default=1,
        help=(
            "number of worker PROCESSES parallelizing this study's independent "
            "eval phases (fold train search, candidate x fold test matrix, "
            "plateau pre-warm); TPE stays serial within a fold. Default 1 == "
            "fully serial (byte-identical outputs to any --workers value, per "
            "the study's determinism contract). Under a fixed 6-core budget: "
            "1 study => --workers 6; run_fleet.py splits the budget across "
            "concurrently-launched studies instead."
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> StudyResult:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    result = run_study(
        args.instrument,
        lake_root=Path(args.lake_root),
        out_dir=Path(args.out_dir),
        trials=args.trials,
        seed=args.seed,
        test_span_days=args.test_span_days,
        step_days=args.step_days,
        embargo_days=args.embargo_days,
        window_start=_parse_ts(args.window_start) if args.window_start else None,
        window_end=_parse_ts(args.window_end) if args.window_end else None,
        horizon=args.horizon,
        tp_r=args.tp_r,
        sl=args.sl,
        n_min=args.n_min,
        win_rate_min=args.win_rate_min,
        workers=args.workers,
    )

    print(f"study_id: {result.study_id}")
    print(f"folds: {len(result.folds)}")
    print(f"optuna_used: {result.optuna_used}")
    winner = result.selection_outcome.winner
    print(f"winner: {winner.name if winner else None}")
    print(f"trade_counts: {result.trade_counts}")
    print(f"wall_clock_seconds: {result.wall_clock_seconds:.2f}")
    print(f"report: {result.report_path}")
    print(f"proposed_diff: {result.diff_path}")
    for note in result.notes:
        print(f"NOTE: {note}")
    return result


if __name__ == "__main__":
    main()
