"""tests/research/test_runner_scaffold.py -- TDD for scripts.research.runner (T0.9-min).

Five required tests per research/protocolos/06-runners.md and
research/fases/F0-preparacion/02-specs/T0.9min-brief-runner-scaffold.md:
1. idempotencia
2. reanudacion
3. fail-loud de manifiesto
4. fail-loud de corrida
5. lineage completo (13 campos obligatorios de LEDGER.schema.md)

The ledger these tests write to always lives under tmp_path -- never
research/LEDGER.jsonl, which is the controller's real append-only file.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.research.runner import runner, tasks
from scripts.research.runner.manifest import ManifestError
from scripts.research.runner.state import RunnerState, state_path_for


def _write_manifest(dir_path: Path, resultados_dir: Path, *, corridas=None) -> Path:
    if corridas is None:
        corridas = [
            {"run_key": "r1", "tipo": "echo", "msg": "hello"},
            {"run_key": "r2", "tipo": "echo", "msg": "world"},
        ]
    manifest = {
        "experimento": "T0.9min-test",
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
    manifest_path = dir_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return manifest_path


def _read_ledger_lines(ledger_path: Path) -> list[dict]:
    if not ledger_path.exists():
        return []
    with ledger_path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_idempotencia_no_duplica_ledger_ni_reejecuta(tmp_path):
    resultados_dir = tmp_path / "04-resultados"
    manifest_path = _write_manifest(tmp_path, resultados_dir)
    ledger_path = tmp_path / "LEDGER.jsonl"

    runner.run_manifest(manifest_path, ledger_path=ledger_path)
    rows_first = _read_ledger_lines(ledger_path)
    assert len(rows_first) == 2

    runner.run_manifest(manifest_path, ledger_path=ledger_path)
    rows_second = _read_ledger_lines(ledger_path)

    assert len(rows_second) == 2
    assert rows_second == rows_first


def test_reanudacion_solo_ejecuta_corridas_pendientes(tmp_path):
    resultados_dir = tmp_path / "04-resultados"
    manifest_path = _write_manifest(tmp_path, resultados_dir)
    ledger_path = tmp_path / "LEDGER.jsonl"

    state = RunnerState(state_path_for(resultados_dir))
    state.mark_complete("r1", {"bytes": 0})

    runner.run_manifest(manifest_path, ledger_path=ledger_path)

    rows = _read_ledger_lines(ledger_path)
    run_ids = {row["run_id"] for row in rows}
    assert run_ids == {"r2"}
    assert not (resultados_dir / "r1" / "params.json").exists()
    assert (resultados_dir / "r2" / "params.json").exists()


def test_fail_loud_manifiesto_campo_faltante_no_escribe_ledger(tmp_path):
    resultados_dir = tmp_path / "04-resultados"
    manifest = {
        "experimento": "T0.9min-test",
        "area": "INFRA",
        "etapa": "F0",
        # "hipotesis" deliberately omitted
        "substrate_id": "n/a",
        "engine_sha": "test-sha",
        "salidas": {"resultados": str(resultados_dir), "ledger": "append"},
        "corridas": [{"run_key": "r1", "tipo": "echo"}],
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    ledger_path = tmp_path / "LEDGER.jsonl"

    with pytest.raises(ManifestError, match="hipotesis"):
        runner.run_manifest(manifest_path, ledger_path=ledger_path)

    assert not ledger_path.exists()


def test_fail_loud_corrida_aborta_y_no_ejecuta_posteriores(tmp_path):
    def boom(params, out_dir):
        raise RuntimeError("boom-task-failure")

    tasks.register("boom-test-task", boom)

    resultados_dir = tmp_path / "04-resultados"
    corridas = [
        {"run_key": "r1", "tipo": "boom-test-task"},
        {"run_key": "r2", "tipo": "echo", "msg": "never runs"},
    ]
    manifest_path = _write_manifest(tmp_path, resultados_dir, corridas=corridas)
    ledger_path = tmp_path / "LEDGER.jsonl"

    with pytest.raises(runner.RunnerAbort):
        runner.run_manifest(manifest_path, ledger_path=ledger_path)

    assert not (resultados_dir / "r2").exists()
    assert _read_ledger_lines(ledger_path) == []


def test_lineage_completo_13_campos(tmp_path):
    resultados_dir = tmp_path / "04-resultados"
    manifest_path = _write_manifest(
        tmp_path,
        resultados_dir,
        corridas=[{"run_key": "r1", "tipo": "echo", "msg": "hi"}],
    )
    ledger_path = tmp_path / "LEDGER.jsonl"

    runner.run_manifest(manifest_path, ledger_path=ledger_path)

    rows = _read_ledger_lines(ledger_path)
    assert len(rows) == 1
    row = rows[0]

    required_fields = {
        "run_id", "timestamp", "etapa", "area", "experimento", "hipotesis_ref",
        "substrate_id", "engine_sha", "git_sha", "config_hash", "generador",
        "artefactos", "estado",
    }
    assert required_fields.issubset(row.keys())

    expected_sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert row["git_sha"] == expected_sha

    # timestamp is local host time (UTC-4, broker server time) -- no zone conversion
    assert "+00:00" not in row["timestamp"]
    assert "Z" not in row["timestamp"]
