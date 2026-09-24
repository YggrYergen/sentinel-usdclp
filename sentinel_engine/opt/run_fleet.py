"""P4 fleet orchestrator -- run several independent per-instrument studies
concurrently under a FIXED total CPU-core budget (companion to
``sentinel_engine.opt.study``'s ``--workers`` flag).

Motivation: ``study.py --workers W`` parallelizes ONE study's independent
eval phases across ``W`` worker processes. This module is the other half of
the core-budget model: instead of (or in addition to) making one study go
faster, run K independent studies AT ONCE, each capped so the fleet never
exceeds a single fixed core budget (default 6, ``study.DEFAULT_CORE_BUDGET``):

    K (concurrent studies)   workers each   total cores
    1                        6              6
    2                        3              6
    3                        2              6

``W = max(1, core_budget // len(instruments))`` -- computed ONCE up front
(pure integer arithmetic, no wall-clock, no process introspection), then
every study subprocess is launched with ``--workers W``.

Studies are FULLY INDEPENDENT: each instrument's study is its own OS
subprocess (``python -m sentinel_engine.opt.study ...``), with its own
``out_dir``, its own ``TrialRegistry`` (own SQLite file), and its own
in-process ``FastReplayCache`` -- there is no cross-talk between concurrently
running studies, and running instrument X standalone vs as part of a fleet
produces byte-identical outputs for X (same argument: ``run_study``'s
``--workers`` determinism contract already guarantees parallelism is
invisible to outputs; running two INDEPENDENT such invocations side by side
changes nothing about either one's inputs).

Subprocesses (not ``multiprocessing``) are used at the fleet level
deliberately: each study is a substantial, long-running, independently
logged unit of work with its own CLI contract (``study.py``'s own
``argparse`` parser) -- reusing that CLI via ``subprocess`` avoids
duplicating any of ``run_study``'s argument handling here, and keeps each
study's stdout/stderr and ``study.log`` cleanly separated per-instrument
directory rather than interleaved in one process's output.

Windows-safe: pathlib only, explicit ``encoding="utf-8"``, ``__main__``
guard (this module spawns subprocesses via ``subprocess.Popen``, not
``multiprocessing``, so Windows' spawn-start-method picklability
constraints do not apply here -- but the guard is still required so this
module can be safely imported by tests/other tooling without re-launching
a fleet).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from sentinel_engine.opt.study import DEFAULT_CORE_BUDGET, DEFAULT_LAKE_ROOT


def compute_workers_per_study(core_budget: int, n_instruments: int) -> int:
    """``W = max(1, core_budget // n_instruments)`` -- the fleet's core-
    budget allocation math (pure integer arithmetic; unit-tested directly,
    no subprocess needed).

    Raises:
        ValueError: if ``n_instruments <= 0`` (nothing to allocate for) or
            ``core_budget <= 0`` (not a valid budget).
    """
    if n_instruments <= 0:
        raise ValueError("compute_workers_per_study: n_instruments must be > 0")
    if core_budget <= 0:
        raise ValueError("compute_workers_per_study: core_budget must be > 0")
    return max(1, core_budget // n_instruments)


@dataclass(frozen=True)
class StudySubprocessResult:
    """One instrument's completed study subprocess."""

    instrument: str
    out_dir: Path
    workers: int
    returncode: int
    wall_clock_seconds: float
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class FleetResult:
    """Full result of one ``run_fleet`` invocation."""

    core_budget: int
    instruments: List[str]
    workers_per_study: int
    results: List[StudySubprocessResult]
    wall_clock_seconds: float

    @property
    def all_ok(self) -> bool:
        return all(r.ok for r in self.results)


def _build_study_argv(
    instrument: str,
    out_dir: Path,
    workers: int,
    passthrough: Sequence[str],
) -> List[str]:
    """Full ``python -m sentinel_engine.opt.study`` argv for one instrument's
    study subprocess. ``passthrough`` is every fleet-CLI arg this module
    doesn't itself consume (trials/seed/window/etc.) -- forwarded verbatim
    so a fleet run and a standalone ``study.py`` run of the same instrument
    with the same args are byte-identical modulo ``--workers``/``--out-dir``.
    """
    return [
        sys.executable,
        "-m",
        "sentinel_engine.opt.study",
        "--instrument",
        instrument,
        "--out-dir",
        str(out_dir),
        "--workers",
        str(workers),
        *passthrough,
    ]


def run_fleet(
    instruments: Sequence[str],
    *,
    core_budget: int = DEFAULT_CORE_BUDGET,
    out_root: Path,
    passthrough_args: Optional[Sequence[str]] = None,
    timeout_seconds: Optional[float] = None,
) -> FleetResult:
    """Launch one independent ``study.py`` subprocess per instrument in
    ``instruments``, each capped at ``workers_per_study =
    compute_workers_per_study(core_budget, len(instruments))``, running
    CONCURRENTLY (K subprocesses launched together, then all awaited) --
    never more than ``core_budget`` cores in aggregate.

    Each instrument gets its own subdirectory under ``out_root``
    (``out_root/<instrument>/``) so registries/reports/logs never collide.

    Returns:
        FleetResult with one ``StudySubprocessResult`` per instrument, in
        the SAME order as ``instruments`` (not launch/completion order).

    Raises:
        ValueError: if ``instruments`` is empty.
    """
    if not instruments:
        raise ValueError("run_fleet: instruments must be non-empty")

    workers_per_study = compute_workers_per_study(core_budget, len(instruments))
    passthrough = list(passthrough_args or [])
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()

    procs: Dict[str, "subprocess.Popen[str]"] = {}
    out_dirs: Dict[str, Path] = {}
    proc_t0: Dict[str, float] = {}

    for instrument in instruments:
        out_dir = out_root / instrument
        out_dir.mkdir(parents=True, exist_ok=True)
        out_dirs[instrument] = out_dir
        argv = _build_study_argv(instrument, out_dir, workers_per_study, passthrough)
        proc_t0[instrument] = time.perf_counter()
        procs[instrument] = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    results: List[StudySubprocessResult] = []
    for instrument in instruments:
        proc = procs[instrument]
        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        wall_clock = time.perf_counter() - proc_t0[instrument]
        results.append(
            StudySubprocessResult(
                instrument=instrument,
                out_dir=out_dirs[instrument],
                workers=workers_per_study,
                returncode=int(proc.returncode) if proc.returncode is not None else -1,
                wall_clock_seconds=wall_clock,
                stdout=stdout,
                stderr=stderr,
            )
        )

    fleet_wall_clock = time.perf_counter() - t0

    return FleetResult(
        core_budget=core_budget,
        instruments=list(instruments),
        workers_per_study=workers_per_study,
        results=results,
        wall_clock_seconds=fleet_wall_clock,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "SENTINEL P4 fleet orchestrator -- runs several independent "
            "per-instrument studies concurrently under a fixed total "
            "CPU-core budget, splitting the budget evenly across "
            "instruments (study.py's own --workers flag parallelizes ONE "
            "study instead)."
        )
    )
    parser.add_argument(
        "--instruments", required=True,
        help="comma-separated instrument list, e.g. gold,nasdaq,usdclp",
    )
    parser.add_argument("--core-budget", type=int, default=DEFAULT_CORE_BUDGET)
    parser.add_argument("--out-root", type=str, required=True)
    parser.add_argument(
        "--lake-root", type=str, default=str(DEFAULT_LAKE_ROOT),
        help="forwarded to every study subprocess as --lake-root",
    )
    parser.add_argument(
        "--timeout-seconds", type=float, default=None,
        help="per-study subprocess timeout (kills+collects on expiry); default: no timeout",
    )
    # Every other study.py flag is accepted here as free-form passthrough
    # (parsed by argparse.parse_known_args below) rather than re-declared,
    # so this module never drifts from study.py's own CLI contract.
    return parser


def main(argv: Optional[Sequence[str]] = None) -> FleetResult:
    parser = _build_arg_parser()
    args, extra = parser.parse_known_args(argv)

    instruments = [s.strip() for s in args.instruments.split(",") if s.strip()]
    passthrough = ["--lake-root", args.lake_root, *extra]

    result = run_fleet(
        instruments,
        core_budget=args.core_budget,
        out_root=Path(args.out_root),
        passthrough_args=passthrough,
        timeout_seconds=args.timeout_seconds,
    )

    print(f"fleet: {len(result.instruments)} instrument(s), core_budget={result.core_budget}, "
          f"workers_per_study={result.workers_per_study}")
    for r in result.results:
        status = "OK" if r.ok else f"FAILED (rc={r.returncode})"
        print(f"  {r.instrument}: {status}, wall_clock={r.wall_clock_seconds:.1f}s, out_dir={r.out_dir}")
        if not r.ok:
            print(f"    stderr (tail): {r.stderr[-2000:]}")
    print(f"fleet wall_clock_seconds: {result.wall_clock_seconds:.2f}")

    if not result.all_ok:
        sys.exit(1)
    return result


if __name__ == "__main__":
    main()
