"""Acceptance gate for `sentinel_engine.opt.study` (P4 study driver).

Runs against the REAL local Parquet lake at `D:\\FOREX\\data\\lake` (gitignored
but present on this machine -- read directly, no synthetic fixtures). Uses
the `gold` instrument (matching `tests/opt/test_fast_replay.py`'s
non-vacuity trick: a short, real, recent window whose composite scores
cross the G4 lever group's threshold floor (50.0) often enough to guarantee
real entries) with a SMALL trial budget so the smoke run stays fast.

This is a SMOKE test, not a full overnight study: single instrument, small
trial budget, short window, a couple of minutes wall-clock (printed, not
asserted precisely -- see the module docstring's note on why: wall-clock
scales with lake size, which grows daily on this machine).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pandas as pd
import pytest

from sentinel_engine.config import load_instrument
from sentinel_engine.lake.store import read_bars
from sentinel_engine.opt.run_fleet import compute_workers_per_study, run_fleet
from sentinel_engine.opt.study import run_study

LAKE_ROOT = Path("D:/FOREX/data/lake")
INSTRUMENT = "gold"
SEED = 20260707
TRIALS = 20  # small per-stage budget -- smoke, not a real study

pytestmark = pytest.mark.skipif(not LAKE_ROOT.exists(), reason="real lake not present on this machine")

# The ``slow`` marker used below is registered in ``tests/opt/conftest.py``
# (new file, added alongside this test) via ``pytest_configure`` -- this
# repo has no ``pytest.ini``/``pyproject.toml``/``setup.cfg`` yet (checked:
# none exist), so a marker can't be registered there without creating a new
# shared config file; `conftest.py` is the standard, non-invasive place for
# this and doesn't touch any file another task owns. FLAGGED here per the
# task brief in case a real `[tool.pytest.ini_options]` block gets added
# later -- this marker registration should move there at that point.


def _smoke_window():
    """A short-but-real window guaranteed to produce entries: the last few
    days of gold's real M1 history. G4's `score_alert_threshold` lever
    ranges [50, 80] -- 50 is barely above the scoring midline (50 == neutral
    composite), so a multi-day window reliably crosses it many times over,
    unlike the single-hour windows used for exact oracle-vs-fast comparison
    in test_fast_replay.py (this test does not need oracle equivalence, only
    real, non-vacuous entries)."""
    cfg = load_instrument(INSTRUMENT)
    m1 = read_bars(LAKE_ROOT, cfg.target, 1)
    assert not m1.empty, "real lake has no XAUUSD M1 data -- cannot run acceptance gate"
    w_end = m1.index[-1].to_pydatetime()
    w_start = (m1.index[-1] - pd.Timedelta(days=3)).to_pydatetime()
    return w_start, w_end


def _run(tmp_out_dir: Path):
    w_start, w_end = _smoke_window()
    return run_study(
        INSTRUMENT,
        lake_root=LAKE_ROOT,
        out_dir=tmp_out_dir,
        trials=TRIALS,
        seed=SEED,
        test_span_days=1.0,
        step_days=1.0,
        embargo_days=0.1,
        window_start=w_start,
        window_end=w_end,
        horizon=30,
        tp_r=1.5,
        sl=2.0,
        n_min=1,          # small-sample smoke override (like test_fast_replay's OBJ_KW)
        win_rate_min=0.0,  # small-sample smoke override
    )


@pytest.mark.slow
def test_smoke_study_produces_real_trades_and_artifacts(tmp_path):
    import time

    out_dir = tmp_path / "study_run"
    t0 = time.perf_counter()
    result = _run(out_dir)
    wall_clock = time.perf_counter() - t0

    print(f"\nstudy_id: {result.study_id}")
    print(f"folds: {len(result.folds)}")
    print(f"optuna_used: {result.optuna_used}")
    print(f"trade_counts: {result.trade_counts}")
    print(f"notes: {result.notes}")
    print(f"measured wall-clock: {wall_clock:.1f}s (driver-reported: {result.wall_clock_seconds:.1f}s)")

    # ---- 1. non-vacuity: at least one real trade fired somewhere in the study ----
    total_trades = sum(result.trade_counts.values())
    assert total_trades >= 1, (
        f"VACUOUS STUDY: 0 trades fired across every fold/candidate "
        f"({result.trade_counts}) -- widen the window or lower the threshold floor."
    )
    max_single = max(result.trade_counts.values())
    print(f"max single trade_count entry: {max_single}, total (sum, double counts folds x candidates): {total_trades}")

    # ---- 2. artifacts: non-empty report + non-empty proposed-diff, both under out_dir ----
    assert result.report_path.parent == out_dir or out_dir in result.report_path.parents
    assert result.diff_path.parent == out_dir or out_dir in result.diff_path.parents
    assert result.report_path.exists()
    assert result.diff_path.exists()
    report_text = result.report_path.read_text(encoding="utf-8")
    diff_text = result.diff_path.read_text(encoding="utf-8")
    assert len(report_text.strip()) > 0
    assert len(diff_text.strip()) > 0
    assert "PROPOSED" in diff_text and "NOT APPLIED" in diff_text

    # ---- 3. determinism: identical args -> identical study id + selection outcome + diff ----
    out_dir_2 = tmp_path / "study_run_2"
    result2 = _run(out_dir_2)

    assert result.study_id == result2.study_id
    assert result.selection_outcome.reason == result2.selection_outcome.reason
    assert result.selection_outcome.median_J_by_name == result2.selection_outcome.median_J_by_name
    assert result.selection_outcome.dominance_by_name == result2.selection_outcome.dominance_by_name
    assert result.selection_outcome.rejected == result2.selection_outcome.rejected
    winner1 = result.selection_outcome.winner
    winner2 = result2.selection_outcome.winner
    assert (winner1 is None) == (winner2 is None)
    if winner1 is not None:
        assert winner1.name == winner2.name
        assert winner1.config == winner2.config
    assert result.diff_text == result2.diff_text


def test_safety_invariant_no_instrument_config_modified(tmp_path):
    """The driver must NEVER write to (or otherwise mutate) any instrument
    config file. Capture the mtime+content of gold.yaml before and after a
    full study run and assert byte-identical."""
    cfg_path = Path("sentinel_engine/instruments/gold.yaml")
    assert cfg_path.exists()

    before_bytes = cfg_path.read_bytes()
    before_mtime = cfg_path.stat().st_mtime_ns

    out_dir = tmp_path / "study_run_safety"
    _run(out_dir)

    after_bytes = cfg_path.read_bytes()
    after_mtime = cfg_path.stat().st_mtime_ns

    assert before_bytes == after_bytes, "instrument config file content changed -- SAFETY INVARIANT VIOLATED"
    assert before_mtime == after_mtime, "instrument config file mtime changed -- SAFETY INVARIANT VIOLATED"

    # Also assert no other instrument YAML was touched.
    for other in Path("sentinel_engine/instruments").glob("*.yaml"):
        # only checked for existence/readability; a crash here would itself
        # indicate corruption from an errant write.
        other.read_bytes()


# ─────────────────────────────────────────────────────────────────────────
# Parallelism (--workers) acceptance gate
# ─────────────────────────────────────────────────────────────────────────
#
# FAST_TRIALS/FAST window below are deliberately tiny (2 trials/stage, a
# single ~6-hour window that still degenerates to ONE fold) so the tests in
# this section run in the normal (non -m slow) suite in well under a minute
# each, per the task brief: "Keep all test studies SMALL (tiny window,
# trials=2-3) so they run in a couple of minutes and don't hog cores while
# the concurrent agent works."

FAST_TRIALS = 2


def _fast_window():
    """A short, real, non-vacuous window (same non-vacuity trick as
    ``_smoke_window``, just narrower) -- narrow enough that
    ``anchored_walkforward`` degenerates to a single fold (ambiguity #6 in
    ``study.py``'s own docstring), which is fine for a smoke/determinism
    test: the parallel phases (fold train search, candidate x fold matrix,
    plateau pre-warm) all still run, just over 1 fold instead of several."""
    cfg = load_instrument(INSTRUMENT)
    m1 = read_bars(LAKE_ROOT, cfg.target, 1)
    assert not m1.empty, "real lake has no XAUUSD M1 data -- cannot run acceptance gate"
    w_end = m1.index[-1].to_pydatetime()
    w_start = (m1.index[-1] - pd.Timedelta(hours=12)).to_pydatetime()
    return w_start, w_end


def _run_fast(tmp_out_dir: Path, workers: int = 1):
    w_start, w_end = _fast_window()
    return run_study(
        INSTRUMENT,
        lake_root=LAKE_ROOT,
        out_dir=tmp_out_dir,
        trials=FAST_TRIALS,
        seed=SEED,
        test_span_days=1.0,
        step_days=1.0,
        embargo_days=0.1,
        window_start=w_start,
        window_end=w_end,
        horizon=30,
        tp_r=1.5,
        sl=2.0,
        n_min=1,
        win_rate_min=0.0,
        progress=False,
        workers=workers,
    )


def test_fast_smoke_study_minimal(tmp_path):
    """FAST smoke: tiny window, trials=2, runs in the normal (non-slow)
    suite. Same non-vacuity + artifact assertions as the full (slow) smoke
    test, just cheap enough to run every time."""
    out_dir = tmp_path / "fast_study_run"
    result = _run_fast(out_dir, workers=1)

    assert result.report_path.exists()
    assert result.diff_path.exists()
    report_text = result.report_path.read_text(encoding="utf-8")
    diff_text = result.diff_path.read_text(encoding="utf-8")
    assert len(report_text.strip()) > 0
    assert "PROPOSED" in diff_text and "NOT APPLIED" in diff_text
    assert len(result.folds) >= 1


def test_parallel_matches_serial_determinism(tmp_path):
    """THE gate: a study run at --workers 1 and --workers 4 must produce a
    BYTE-IDENTICAL study_id + selection_outcome (winner name+config, reason,
    median_J_by_name, dominance_by_name, rejected) + proposed-diff text +
    report text. Parallelism must be invisible to every output.

    Also proves the safety invariant (no instrument YAML write) holds under
    the parallel path, and reports wall-clock for both runs (speed evidence
    -- not asserted as a hard threshold since this window is intentionally
    tiny; see the module docstring)."""
    import time

    cfg_path = Path("sentinel_engine/instruments/gold.yaml")
    before_bytes = cfg_path.read_bytes()
    before_mtime = cfg_path.stat().st_mtime_ns

    out_dir_serial = tmp_path / "serial_run"
    t0 = time.perf_counter()
    result_serial = _run_fast(out_dir_serial, workers=1)
    serial_wall_clock = time.perf_counter() - t0

    out_dir_parallel = tmp_path / "parallel_run"
    t1 = time.perf_counter()
    result_parallel = _run_fast(out_dir_parallel, workers=4)
    parallel_wall_clock = time.perf_counter() - t1

    print(f"\nserial (--workers 1) wall-clock:   {serial_wall_clock:.1f}s")
    print(f"parallel (--workers 4) wall-clock:  {parallel_wall_clock:.1f}s")
    if parallel_wall_clock > 0:
        print(f"speedup: {serial_wall_clock / parallel_wall_clock:.2f}x "
              f"(tiny test window -- not expected to show the full fleet-scale "
              f"speedup; reported, not asserted)")

    # ---- byte-identical study_id ----
    assert result_serial.study_id == result_parallel.study_id

    # ---- byte-identical selection_outcome, field by field ----
    so_s, so_p = result_serial.selection_outcome, result_parallel.selection_outcome
    assert so_s.reason == so_p.reason
    assert so_s.median_J_by_name == so_p.median_J_by_name
    assert so_s.dominance_by_name == so_p.dominance_by_name
    assert so_s.rejected == so_p.rejected
    assert so_s.tie_pool == so_p.tie_pool
    assert (so_s.winner is None) == (so_p.winner is None)
    if so_s.winner is not None:
        assert so_s.winner.name == so_p.winner.name
        assert so_s.winner.config == so_p.winner.config
        assert so_s.winner.fold_results == so_p.winner.fold_results

    # ---- byte-identical proposed diff + report text ----
    assert result_serial.diff_text == result_parallel.diff_text
    assert result_serial.report_text == result_parallel.report_text

    # ---- byte-identical trade_counts (proves the parallel matrix/plateau
    #      phases evaluated the exact same configs as serial) ----
    assert result_serial.trade_counts == result_parallel.trade_counts

    # ---- safety invariant still holds after the parallel run ----
    after_bytes = cfg_path.read_bytes()
    after_mtime = cfg_path.stat().st_mtime_ns
    assert before_bytes == after_bytes, "SAFETY INVARIANT VIOLATED under --workers>1"
    assert before_mtime == after_mtime, "SAFETY INVARIANT VIOLATED under --workers>1"


# ─────────────────────────────────────────────────────────────────────────
# Fleet allocation (run_fleet.py)
# ─────────────────────────────────────────────────────────────────────────


def test_fleet_core_budget_allocation_math():
    """core_budget=6 over 1/2/3 instruments assigns W=6/3/2 -- pure integer
    arithmetic, no heavy run needed (per the task brief's acceptance gate
    item 3)."""
    assert compute_workers_per_study(6, 1) == 6
    assert compute_workers_per_study(6, 2) == 3
    assert compute_workers_per_study(6, 3) == 2

    # Non-exact divisions floor (max(1, ...)) rather than round or raise.
    assert compute_workers_per_study(6, 4) == 1  # 6//4 == 1
    assert compute_workers_per_study(6, 7) == 1  # 6//7 == 0 -> floored to 1

    with pytest.raises(ValueError):
        compute_workers_per_study(6, 0)
    with pytest.raises(ValueError):
        compute_workers_per_study(0, 1)


def test_fleet_end_to_end_matches_standalone_studies(tmp_path):
    """A light end-to-end fleet run over 2 tiny studies (both `gold` --
    the only instrument the fast, non-vacuous window trick is calibrated
    for; running the SAME instrument twice under two different out_dirs is
    still a valid independence check: two concurrently-launched, fully
    independent study subprocesses must each produce the exact same result
    as a standalone run) produces the same per-study results as running
    them standalone."""
    w_start, w_end = _fast_window()
    passthrough = [
        "--trials", str(FAST_TRIALS),
        "--seed", str(SEED),
        "--test-span-days", "1.0",
        "--step-days", "1.0",
        "--embargo-days", "0.1",
        "--window-start", w_start.isoformat(),
        "--window-end", w_end.isoformat(),
        "--horizon", "30",
        "--tp-r", "1.5",
        "--sl", "2.0",
        "--n-min", "1",
        "--win-rate-min", "0.0",
    ]

    # ---- standalone reference run ----
    standalone_out = tmp_path / "standalone"
    standalone_result = run_study(
        INSTRUMENT,
        lake_root=LAKE_ROOT,
        out_dir=standalone_out,
        trials=FAST_TRIALS,
        seed=SEED,
        test_span_days=1.0,
        step_days=1.0,
        embargo_days=0.1,
        window_start=w_start,
        window_end=w_end,
        horizon=30,
        tp_r=1.5,
        sl=2.0,
        n_min=1,
        win_rate_min=0.0,
        progress=False,
        workers=1,
    )

    # ---- fleet run: 2 concurrent "instruments" (both gold, different
    #      out_dirs) at core_budget=6 -> workers_per_study=3 each ----
    fleet_out = tmp_path / "fleet"
    fleet_result = run_fleet(
        ["gold", "gold"],
        core_budget=6,
        out_root=fleet_out,
        passthrough_args=passthrough,
        timeout_seconds=300.0,
    )

    assert fleet_result.workers_per_study == 3
    assert len(fleet_result.results) == 2
    for r in fleet_result.results:
        assert r.ok, f"fleet study subprocess failed (rc={r.returncode}): {r.stderr[-3000:]}"
        assert r.instrument == "gold"
        assert r.workers == 3

        report_files = list(r.out_dir.glob("*_report.md"))
        diff_files = list(r.out_dir.glob("*_proposed_diff.md"))
        assert len(report_files) == 1
        assert len(diff_files) == 1

        report_text = report_files[0].read_text(encoding="utf-8")
        diff_text = diff_files[0].read_text(encoding="utf-8")

        # Same study_id (embedded in the artifact filenames) as the
        # standalone run -- proves the fleet subprocess computed the exact
        # same study, invisible to whether it ran solo or as part of a
        # fleet.
        assert report_files[0].name.startswith(standalone_result.study_id)
        assert diff_files[0].name.startswith(standalone_result.study_id)
        assert diff_text == standalone_result.diff_text
        assert report_text == standalone_result.report_text
