"""scripts.research.runner.runner -- orchestrator + CLI (protocolo 06).

Flow: validate manifest -> for each incomplete corrida -> run the task-type
-> write artifacts under salidas.resultados/<run_key>/ -> mark complete in
state -> append one LEDGER row if salidas.ledger == "append". On completion,
write a single consolidated record to salidas.resultados/_resumen.json --
the only thing the LLM reads afterwards.

Fail-loud: if a corrida raises, the whole run aborts, state stays
consistent for what already completed, and the process exits non-zero.
Executes exactly what the manifest says -- no choosing, no pruning, no
adjusting.

CLI:
    python -m scripts.research.runner.runner <ruta-al-manifiesto>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.research.runner import lineage, tasks
from scripts.research.runner import tasks_ticks  # noqa: F401 -- side effect: registers ticks_mt5
from scripts.research.runner.ledger import append_row
from scripts.research.runner.manifest import load_manifest
from scripts.research.runner.state import RunnerState, state_path_for

DEFAULT_LEDGER_PATH = Path("research/LEDGER.jsonl")
DEFAULT_GENERADOR = "runner:runner.py"


class RunnerAbort(Exception):
    """Raised when a corrida's task-type raises; the whole run aborts."""


def _write_summary(resultados_dir: Path, entries: dict) -> None:
    resultados_dir = Path(resultados_dir)
    resultados_dir.mkdir(parents=True, exist_ok=True)
    summary_path = resultados_dir / "_resumen.json"
    payload = {"corridas": list(entries.values())}
    tmp_path = summary_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True, indent=2, ensure_ascii=False)
    tmp_path.replace(summary_path)


def _load_summary_entries(resultados_dir: Path) -> dict:
    summary_path = Path(resultados_dir) / "_resumen.json"
    if not summary_path.exists():
        return {}
    with summary_path.open("r", encoding="utf-8") as f:
        existing = json.load(f)
    return {entry["run_key"]: entry for entry in existing.get("corridas", [])}


def run_manifest(
    manifest_path: Path,
    *,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    generador: str = DEFAULT_GENERADOR,
) -> dict:
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)

    resultados_dir = Path(manifest["salidas"]["resultados"])
    ledger_mode = manifest["salidas"]["ledger"]

    state = RunnerState(state_path_for(resultados_dir))
    summary_entries = _load_summary_entries(resultados_dir)
    registry = tasks.get_registry()

    for corrida in manifest["corridas"]:
        run_key = corrida["run_key"]
        tipo = corrida["tipo"]

        if state.is_complete(run_key):
            continue

        params = {k: v for k, v in corrida.items() if k not in ("run_key", "tipo")}
        out_dir = resultados_dir / run_key
        task_fn = registry[tipo]

        try:
            metrics = task_fn(params, out_dir)
        except Exception as exc:
            summary_entries[run_key] = {
                "run_key": run_key,
                "estado": "abortado",
                "metricas": None,
                "artefactos": str(out_dir),
                "error": str(exc),
            }
            _write_summary(resultados_dir, summary_entries)
            raise RunnerAbort(f"corrida {run_key} (tipo={tipo}) aborted: {exc}") from exc

        tags = lineage.build_tags(
            run_id=run_key,
            area=manifest["area"],
            experimento=manifest["experimento"],
            params=params,
            substrate_id=manifest["substrate_id"],
            engine_sha=manifest["engine_sha"],
            etapa=manifest["etapa"],
            generador=generador,
        )

        if ledger_mode == "append":
            row = {
                "run_id": tags["run_id"],
                "timestamp": tags["timestamp"],
                "etapa": tags["etapa"],
                "area": tags["area"],
                "experimento": tags["experimento"],
                "hipotesis_ref": manifest["hipotesis"],
                "substrate_id": tags["substrate_id"],
                "engine_sha": tags["engine_sha"],
                "git_sha": tags["git_sha"],
                "config_hash": tags["config_hash"],
                "generador": tags["generador"],
                "artefactos": [str(out_dir)],
                "estado": "ok",
            }
            append_row(Path(ledger_path), row)

        state.mark_complete(run_key, metrics)
        summary_entries[run_key] = {
            "run_key": run_key,
            "estado": "ok",
            "metricas": metrics,
            "artefactos": str(out_dir),
        }
        _write_summary(resultados_dir, summary_entries)

    return {"resultados_dir": str(resultados_dir), "summary_path": str(resultados_dir / "_resumen.json")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta un manifiesto de corridas (research/protocolos/06-runners.md)."
    )
    parser.add_argument("manifest", type=Path, help="ruta al manifiesto YAML")
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=DEFAULT_LEDGER_PATH,
        help="ruta al LEDGER.jsonl (por defecto: research/LEDGER.jsonl)",
    )
    parser.add_argument("--generador", default=DEFAULT_GENERADOR)
    args = parser.parse_args(argv)

    try:
        result = run_manifest(args.manifest, ledger_path=args.ledger_path, generador=args.generador)
    except RunnerAbort as exc:
        print(f"ABORTADO: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
