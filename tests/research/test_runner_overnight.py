"""tests/research/test_runner_overnight.py -- TDD for T0.9-B (overnight grid:
failure isolation, parallelism, progress visibility).

Six required tests per the T0.9-B closed spec:
1. --on-error continue: corrida 2/4 raises -> 3 and 4 still run, exit != 0,
   _resumen.json marks 2 as "fallido" with traceback, state has 3
   completed + 1 failed.
2. Retry semantics: re-running the same manifest re-executes ONLY the
   failed corrida; on success it moves from failed -> completed and the
   exit code becomes 0.
3. --workers 2: 4 corridas all complete, LEDGER has exactly 4 rows, no
   duplicates, _resumen.json has 4 entries.
4. Interruption safety: with a state file marking 2 of 4 complete, only
   the remaining 2 run -- under --workers 2 as well as --workers 1.
5. MT5 guard: a manifest containing a non-parallelizable task type with
   --workers 4 is forced down to 1 worker, and the runner says so. Also
   verifies the REAL registrations (ticks_mt5, ticks_csv_mt5) are marked
   non-parallelizable.
6. Progress files: after a run, _progreso.json and _progreso.txt exist,
   counts are correct, durations are present and positive; the `progress`
   CLI module prints _progreso.txt's content (and a clear message when the
   file does not exist yet).

The ledger these tests write to always lives under tmp_path -- never
research/LEDGER.jsonl. No test is marked `slow`.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import yaml

from scripts.research.runner import progress as progress_cli
from scripts.research.runner import runner, tasks
from scripts.research.runner.state import RunnerState, state_path_for

# ---------------------------------------------------------------------------
# module-level task-types (must be module-level, not closures, so they can be
# pickled by reference and executed inside a ProcessPoolExecutor worker).
# ---------------------------------------------------------------------------


def _tarea_ok(params: dict, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # busy-wait on time.monotonic() rather than time.sleep(): on this
    # Windows host, time.sleep(0.01) has been observed to occasionally
    # return in ~0s (confirmed independently of this test/runner, a
    # platform timer-resolution quirk) -- that would make a duration_s > 0
    # assertion flaky for reasons unrelated to the runner under test.
    t0 = time.monotonic()
    while time.monotonic() - t0 < 0.005:
        pass
    (out_dir / "marker.txt").write_text("ok", encoding="utf-8")
    return {"ok": True}


def _tarea_falla_siempre(params: dict, out_dir: Path) -> dict:
    raise RuntimeError("boom-overnight-siempre")


def _tarea_falla_primera_vez(params: dict, out_dir: Path) -> dict:
    """Fails on its first invocation for a given run_key (tracked via a
    sentinel file on disk inside out_dir, so it works the same whether
    called in-process or in a worker process), succeeds every time after."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sentinel = out_dir / "_intentado.marker"
    if not sentinel.exists():
        sentinel.write_text("1", encoding="utf-8")
        raise RuntimeError("boom-overnight-primera-vez")
    return {"ok": True}


def _tarea_mt5_stand_in(params: dict, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return {"ok": True}


tasks.register("overnight-ok", _tarea_ok)
tasks.register("overnight-falla-siempre", _tarea_falla_siempre)
tasks.register("overnight-falla-primera-vez", _tarea_falla_primera_vez)
tasks.register("overnight-mt5-stand-in", _tarea_mt5_stand_in, parallelizable=False)


def _write_manifest(dir_path: Path, resultados_dir: Path, *, corridas, filename="manifest.yaml") -> Path:
    manifest = {
        "experimento": "T0.9-B-test",
        "area": "INFRA",
        "etapa": "F0",
        "hipotesis": "01-hipotesis/does-not-exist.md",
        "substrate_id": "n/a",
        "engine_sha": "test-sha",
        "salidas": {
            "resultados": str(resultados_dir),
            "ledger": "append",
        },
        "corridas": corridas,
    }
    manifest_path = dir_path / filename
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return manifest_path


def _read_ledger_lines(ledger_path: Path) -> list[dict]:
    if not ledger_path.exists():
        return []
    with ledger_path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _read_summary(resultados_dir: Path) -> dict:
    return json.loads((resultados_dir / "_resumen.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. --on-error continue
# ---------------------------------------------------------------------------


def test_on_error_continue_sigue_tras_fallo_y_marca_fallido(tmp_path):
    resultados_dir = tmp_path / "04-resultados"
    corridas = [
        {"run_key": "r1", "tipo": "overnight-ok"},
        {"run_key": "r2", "tipo": "overnight-falla-siempre"},
        {"run_key": "r3", "tipo": "overnight-ok"},
        {"run_key": "r4", "tipo": "overnight-ok"},
    ]
    manifest_path = _write_manifest(tmp_path, resultados_dir, corridas=corridas)
    ledger_path = tmp_path / "LEDGER.jsonl"

    exit_code = runner.main(
        [str(manifest_path), "--ledger-path", str(ledger_path), "--on-error", "continue"]
    )

    assert exit_code != 0

    # r3 and r4 (after the failing r2) still ran.
    assert (resultados_dir / "r1" / "marker.txt").exists()
    assert (resultados_dir / "r3" / "marker.txt").exists()
    assert (resultados_dir / "r4" / "marker.txt").exists()

    summary = _read_summary(resultados_dir)
    by_key = {e["run_key"]: e for e in summary["corridas"]}
    assert by_key["r1"]["estado"] == "ok"
    assert by_key["r3"]["estado"] == "ok"
    assert by_key["r4"]["estado"] == "ok"
    assert by_key["r2"]["estado"] == "fallido"
    assert "boom-overnight-siempre" in by_key["r2"]["error"]
    assert "Traceback" in by_key["r2"]["traceback"]

    ledger_rows = _read_ledger_lines(ledger_path)
    assert {r["run_id"] for r in ledger_rows} == {"r1", "r3", "r4"}

    state = RunnerState(state_path_for(resultados_dir))
    assert state.is_complete("r1")
    assert state.is_complete("r3")
    assert state.is_complete("r4")
    assert state.is_failed("r2")
    assert not state.is_complete("r2")


# ---------------------------------------------------------------------------
# 2. retry semantics
# ---------------------------------------------------------------------------


def test_retry_reejecuta_solo_la_fallida_y_pasa_a_completed(tmp_path):
    resultados_dir = tmp_path / "04-resultados"
    corridas = [
        {"run_key": "r1", "tipo": "overnight-ok"},
        {"run_key": "r2", "tipo": "overnight-falla-primera-vez"},
        {"run_key": "r3", "tipo": "overnight-ok"},
        {"run_key": "r4", "tipo": "overnight-ok"},
    ]
    manifest_path = _write_manifest(tmp_path, resultados_dir, corridas=corridas)
    ledger_path = tmp_path / "LEDGER.jsonl"

    exit_code_1 = runner.main(
        [str(manifest_path), "--ledger-path", str(ledger_path), "--on-error", "continue"]
    )
    assert exit_code_1 != 0
    ledger_rows_1 = _read_ledger_lines(ledger_path)
    assert {r["run_id"] for r in ledger_rows_1} == {"r1", "r3", "r4"}

    state_mid = RunnerState(state_path_for(resultados_dir))
    assert state_mid.is_failed("r2")

    # second invocation: only r2 (the failed one) should re-execute.
    exit_code_2 = runner.main([str(manifest_path), "--ledger-path", str(ledger_path)])
    assert exit_code_2 == 0

    ledger_rows_2 = _read_ledger_lines(ledger_path)
    assert len(ledger_rows_2) == 4
    assert {r["run_id"] for r in ledger_rows_2} == {"r1", "r2", "r3", "r4"}
    # r1/r3/r4 rows were not duplicated/re-appended.
    assert sum(1 for r in ledger_rows_2 if r["run_id"] == "r1") == 1

    state_end = RunnerState(state_path_for(resultados_dir))
    assert state_end.is_complete("r2")
    assert not state_end.is_failed("r2")

    summary = _read_summary(resultados_dir)
    by_key = {e["run_key"]: e for e in summary["corridas"]}
    assert by_key["r2"]["estado"] == "ok"


# ---------------------------------------------------------------------------
# 3. --workers 2
# ---------------------------------------------------------------------------


def test_workers_2_ejecuta_las_4_sin_duplicar(tmp_path):
    resultados_dir = tmp_path / "04-resultados"
    corridas = [{"run_key": f"r{i}", "tipo": "overnight-ok"} for i in range(1, 5)]
    manifest_path = _write_manifest(tmp_path, resultados_dir, corridas=corridas)
    ledger_path = tmp_path / "LEDGER.jsonl"

    exit_code = runner.main(
        [str(manifest_path), "--ledger-path", str(ledger_path), "--workers", "2"]
    )
    assert exit_code == 0

    rows = _read_ledger_lines(ledger_path)
    assert len(rows) == 4
    assert len({r["run_id"] for r in rows}) == 4

    summary = _read_summary(resultados_dir)
    assert len(summary["corridas"]) == 4
    assert {e["estado"] for e in summary["corridas"]} == {"ok"}


# ---------------------------------------------------------------------------
# 4. interruption safety, workers=1 and workers=2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("workers", [1, 2])
def test_interrupcion_solo_corre_pendientes(tmp_path, workers):
    case_dir = tmp_path / f"case-w{workers}"
    case_dir.mkdir()
    resultados_dir = case_dir / "04-resultados"
    corridas = [{"run_key": f"r{i}", "tipo": "overnight-ok"} for i in range(1, 5)]
    manifest_path = _write_manifest(case_dir, resultados_dir, corridas=corridas)
    ledger_path = case_dir / "LEDGER.jsonl"

    state = RunnerState(state_path_for(resultados_dir))
    state.mark_complete("r1", {"ok": True})
    state.mark_complete("r2", {"ok": True})

    exit_code = runner.main(
        [str(manifest_path), "--ledger-path", str(ledger_path), "--workers", str(workers)]
    )
    assert exit_code == 0

    rows = _read_ledger_lines(ledger_path)
    assert {r["run_id"] for r in rows} == {"r3", "r4"}

    # r1/r2 were pre-marked complete without ever running the task -- no
    # marker files for them; r3/r4 actually ran.
    assert not (resultados_dir / "r1" / "marker.txt").exists()
    assert not (resultados_dir / "r2" / "marker.txt").exists()
    assert (resultados_dir / "r3" / "marker.txt").exists()
    assert (resultados_dir / "r4" / "marker.txt").exists()


# ---------------------------------------------------------------------------
# 5. MT5 guard
# ---------------------------------------------------------------------------


def test_mt5_guard_fuerza_workers_a_1_y_lo_informa(tmp_path, capsys):
    # Real registrations (production code, T0.9-B): both MT5-family
    # task-types must be marked non-parallelizable.
    from scripts.research.runner import tasks_ticks, tasks_ticks_csv  # noqa: F401 -- side effect

    non_parallel = tasks.get_non_parallelizable_types()
    assert "ticks_mt5" in non_parallel
    assert "ticks_csv_mt5" in non_parallel

    # Behavioural check uses a safe stand-in (never touches real MT5) that
    # exercises the exact same guard mechanism (parallelizable=False).
    resultados_dir = tmp_path / "04-resultados"
    corridas = [
        {"run_key": "r1", "tipo": "overnight-ok"},
        {"run_key": "r2", "tipo": "overnight-mt5-stand-in"},
        {"run_key": "r3", "tipo": "overnight-ok"},
    ]
    manifest_path = _write_manifest(tmp_path, resultados_dir, corridas=corridas)
    ledger_path = tmp_path / "LEDGER.jsonl"

    exit_code = runner.main(
        [str(manifest_path), "--ledger-path", str(ledger_path), "--workers", "4"]
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "workers" in captured.err.lower()
    assert "overnight-mt5-stand-in" in captured.err

    rows = _read_ledger_lines(ledger_path)
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# 6. progress files
# ---------------------------------------------------------------------------


def test_progreso_json_y_txt_existen_con_conteos_y_duraciones(tmp_path):
    resultados_dir = tmp_path / "04-resultados"
    corridas = [{"run_key": f"r{i}", "tipo": "overnight-ok"} for i in range(1, 4)]
    manifest_path = _write_manifest(tmp_path, resultados_dir, corridas=corridas)
    ledger_path = tmp_path / "LEDGER.jsonl"

    exit_code = runner.main([str(manifest_path), "--ledger-path", str(ledger_path)])
    assert exit_code == 0

    progreso_json_path = resultados_dir / "_progreso.json"
    progreso_txt_path = resultados_dir / "_progreso.txt"
    assert progreso_json_path.exists()
    assert progreso_txt_path.exists()

    data = json.loads(progreso_json_path.read_text(encoding="utf-8"))
    assert data["total"] == 3
    assert data["completadas"] == 3
    assert data["fallidas"] == 0
    assert data["pendientes"] == 0
    assert data["run_key_actual"] is None
    assert data["failed_run_keys"] == []
    assert data["segundos_transcurridos"] >= 0
    assert data["segundos_por_corrida_media"] > 0
    assert "iniciado_en" in data and "actualizado_en" in data
    assert "+00:00" not in data["iniciado_en"] and "Z" not in data["iniciado_en"]

    txt = progreso_txt_path.read_text(encoding="utf-8")
    assert "3/3" in txt
    for i in range(1, 4):
        assert f"r{i}" in txt

    summary = _read_summary(resultados_dir)
    for entry in summary["corridas"]:
        assert entry["duration_s"] > 0

    # progress CLI: prints the same content.
    exit_code_cli = progress_cli.main([str(resultados_dir)])
    assert exit_code_cli == 0
    captured = None
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        progress_cli.main([str(resultados_dir)])
    assert buf.getvalue() == txt

    # missing _progreso.txt -> clear message, not a crash.
    empty_dir = tmp_path / "vacio"
    empty_dir.mkdir()
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        exit_code_missing = progress_cli.main([str(empty_dir)])
    assert exit_code_missing == 0
    assert "no existe" in buf2.getvalue().lower()
