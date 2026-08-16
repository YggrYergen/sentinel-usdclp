"""scripts.research.runner.runner -- orchestrator + CLI (protocolo 06).

Flow: validate manifest -> for each incomplete corrida -> run the task-type
-> write artifacts under salidas.resultados/<run_key>/ -> mark complete in
state -> append one LEDGER row if salidas.ledger == "append". On completion,
write a single consolidated record to salidas.resultados/_resumen.json --
the only thing the LLM reads afterwards. After every corrida (ok or
fallido), _progreso.json / _progreso.txt are rewritten atomically (T0.9-B
SS3) and one stdout line is printed.

Failure isolation (T0.9-B SS1) -- CLI flag --on-error:
  - "abort" (DEFAULT): exactly the pre-T0.9-B behaviour. The first failing
    corrida aborts the whole run: RunnerAbort is raised, exit code 1.
  - "continue": a failing corrida is recorded in _resumen.json as
    "fallido" (with traceback), recorded in state as FAILED (not
    complete, so a later re-run retries it), and the run keeps going.
    At the end, if anything failed, the process exits non-zero and the
    failed run_keys are printed to stderr.

Parallelism (T0.9-B SS2) -- CLI flag --workers N: default 1 is byte-
identical to pre-T0.9-B behaviour. N>1 runs corridas concurrently with a
concurrent.futures.ProcessPoolExecutor. state.mark_complete / failure
recording / the _resumen.json write / the LEDGER append all happen in the
PARENT process only, as each future completes, one at a time, in
future-completion order -- worker processes only execute the task
function and return metrics. Task-types registered with
parallelizable=False (MT5-backed: tasks_ticks.py, tasks_ticks_csv.py)
force --workers down to 1 whenever a pending corrida uses one, and the
runner prints why.

CLI:
    python -m scripts.research.runner.runner <ruta-al-manifiesto>
        [--on-error abort|continue] [--workers N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from scripts.research.runner import lineage, progreso, tasks
from scripts.research.runner import tasks_ticks  # noqa: F401 -- side effect: registers ticks_mt5
from scripts.research.runner import tasks_ticks_csv  # noqa: F401 -- side effect: registers ticks_csv_mt5
from scripts.research.runner.ledger import append_row
from scripts.research.runner.manifest import load_manifest
from scripts.research.runner.state import RunnerState, state_path_for

DEFAULT_LEDGER_PATH = Path("research/LEDGER.jsonl")
DEFAULT_GENERADOR = "runner:runner.py"


class RunnerAbort(Exception):
    """Raised when a corrida's task-type raises under --on-error abort
    (the default); the whole run aborts."""


class RunnerParallelExecutionError(Exception):
    """Raised when a corrida cannot be executed under --workers > 1 -- most
    likely because ProcessPoolExecutor could not pickle the task callable
    or its arguments. Names the run_key and tipo; never falls back to
    sequential execution silently."""


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


def _params_for(corrida: dict) -> dict:
    return {k: v for k, v in corrida.items() if k not in ("run_key", "tipo")}


def _run_task(task_fn, params: dict, out_dir: Path) -> dict:
    """Executes one task-type call. Runs either in-process (--workers 1) or
    inside a worker process (--workers > 1); NEVER raises -- always returns
    a dict, so the parent process is the only place that ever touches
    state/ledger/summary. Return shape:
        {"ok": True, "metrics": ..., "duration_s": ...}
        {"ok": False, "error": str, "traceback": str, "duration_s": ...}
    """
    t0 = time.monotonic()
    try:
        metrics = task_fn(params, out_dir)
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "duration_s": time.monotonic() - t0,
        }
    return {"ok": True, "metrics": metrics, "duration_s": time.monotonic() - t0}


def run_manifest(
    manifest_path: Path,
    *,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    generador: str = DEFAULT_GENERADOR,
    on_error: str = "abort",
    workers: int = 1,
) -> dict:
    if on_error not in ("abort", "continue"):
        raise ValueError(f"on_error debe ser 'abort' o 'continue', recibido: {on_error!r}")
    if workers < 1:
        raise ValueError(f"workers debe ser >= 1, recibido: {workers}")

    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)

    resultados_dir = Path(manifest["salidas"]["resultados"])
    ledger_mode = manifest["salidas"]["ledger"]

    state = RunnerState(state_path_for(resultados_dir))
    summary_entries = _load_summary_entries(resultados_dir)
    registry = tasks.get_registry()

    corridas = manifest["corridas"]
    total = len(corridas)
    pendientes = [c for c in corridas if not state.is_complete(c["run_key"])]

    effective_workers = workers
    if workers > 1:
        non_parallel = tasks.get_non_parallelizable_types()
        blocking = sorted({c["tipo"] for c in pendientes if c["tipo"] in non_parallel})
        if blocking:
            print(
                f"--workers forzado de {workers} a 1: el manifiesto incluye tipo(s) no "
                f"paralelizable(s) {', '.join(blocking)} -- MT5 es attach-only (charter "
                "SS A.12) y una segunda conexion es un riesgo real-money-adjacent",
                file=sys.stderr,
            )
            effective_workers = 1

    iniciado_en = datetime.now().isoformat(timespec="seconds")
    historial: list[dict] = []

    def _current_counts() -> tuple[int, int]:
        completadas = sum(1 for c in corridas if state.is_complete(c["run_key"]))
        fallidas = sum(1 for c in corridas if state.is_failed(c["run_key"]))
        return completadas, fallidas

    def _record_result(corrida: dict, result: dict, *, run_key_actual: str | None) -> None:
        run_key = corrida["run_key"]
        tipo = corrida["tipo"]
        params = _params_for(corrida)
        out_dir = resultados_dir / run_key
        duration_s = result["duration_s"]

        if result["ok"]:
            metrics = result["metrics"]
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

            state.mark_complete(run_key, metrics, duration_s=duration_s)
            summary_entries[run_key] = {
                "run_key": run_key,
                "estado": "ok",
                "metricas": metrics,
                "artefactos": str(out_dir),
                "duration_s": duration_s,
            }
            _write_summary(resultados_dir, summary_entries)
            estado_txt = "ok"
        else:
            error = result["error"]
            if on_error == "abort":
                # exactly the pre-T0.9-B behaviour: no traceback field, not
                # recorded in state, raise immediately.
                summary_entries[run_key] = {
                    "run_key": run_key,
                    "estado": "abortado",
                    "metricas": None,
                    "artefactos": str(out_dir),
                    "error": error,
                    "duration_s": duration_s,
                }
                _write_summary(resultados_dir, summary_entries)
                raise RunnerAbort(f"corrida {run_key} (tipo={tipo}) aborted: {error}")

            traceback_txt = result["traceback"]
            summary_entries[run_key] = {
                "run_key": run_key,
                "estado": "fallido",
                "metricas": None,
                "artefactos": str(out_dir),
                "error": error,
                "traceback": traceback_txt,
                "duration_s": duration_s,
            }
            state.mark_failed(run_key, error, duration_s=duration_s)
            _write_summary(resultados_dir, summary_entries)
            estado_txt = "fallido"

        historial.append({"run_key": run_key, "estado": estado_txt, "duration_s": duration_s})
        completadas, fallidas = _current_counts()
        failed_run_keys_now = sorted(c["run_key"] for c in corridas if state.is_failed(c["run_key"]))
        progreso.write_progress(
            resultados_dir,
            total=total,
            completadas=completadas,
            fallidas=fallidas,
            run_key_actual=run_key_actual,
            iniciado_en=iniciado_en,
            historial=historial,
            failed_run_keys=failed_run_keys_now,
        )
        hechas = completadas + fallidas
        print(f"[{hechas}/{total}] {run_key} {estado_txt} {duration_s:.3f}", flush=True)

    if effective_workers <= 1:
        for corrida in pendientes:
            task_fn = registry[corrida["tipo"]]
            params = _params_for(corrida)
            out_dir = resultados_dir / corrida["run_key"]
            result = _run_task(task_fn, params, out_dir)
            _record_result(corrida, result, run_key_actual=corrida["run_key"])
    else:
        with ProcessPoolExecutor(max_workers=effective_workers) as executor:
            future_to_corrida = {}
            for corrida in pendientes:
                task_fn = registry[corrida["tipo"]]
                params = _params_for(corrida)
                out_dir = resultados_dir / corrida["run_key"]
                future = executor.submit(_run_task, task_fn, params, out_dir)
                future_to_corrida[future] = corrida

            aborted_exc: RunnerAbort | None = None
            for future in as_completed(future_to_corrida):
                corrida = future_to_corrida[future]
                try:
                    result = future.result()
                except Exception as exc:
                    raise RunnerParallelExecutionError(
                        f"corrida {corrida['run_key']} (tipo={corrida['tipo']}) fallo al "
                        "ejecutarse en el process pool -- probable fallo de pickling del "
                        f"callable o de sus argumentos, o el worker murio: {exc}"
                    ) from exc

                try:
                    _record_result(corrida, result, run_key_actual=corrida["run_key"])
                except RunnerAbort as exc:
                    aborted_exc = exc
                    for pending_future in future_to_corrida:
                        pending_future.cancel()
                    break

            if aborted_exc is not None:
                raise aborted_exc

    completadas, fallidas = _current_counts()
    failed_run_keys = sorted(c["run_key"] for c in corridas if state.is_failed(c["run_key"]))
    progreso.write_progress(
        resultados_dir,
        total=total,
        completadas=completadas,
        fallidas=fallidas,
        run_key_actual=None,
        iniciado_en=iniciado_en,
        historial=historial,
        failed_run_keys=failed_run_keys,
    )

    return {
        "resultados_dir": str(resultados_dir),
        "summary_path": str(resultados_dir / "_resumen.json"),
        "failed_run_keys": failed_run_keys,
    }


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
    parser.add_argument(
        "--on-error",
        choices=["abort", "continue"],
        default="abort",
        help=(
            "abort (default): la primera corrida que falla aborta todo el run. "
            "continue: se registra como fallida (estado, ledger de estado, no completada) "
            "y el run sigue; el proceso termina con exit code != 0 si algo fallo."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="numero de procesos concurrentes (default 1 = secuencial, comportamiento identico a antes).",
    )
    args = parser.parse_args(argv)

    try:
        result = run_manifest(
            args.manifest,
            ledger_path=args.ledger_path,
            generador=args.generador,
            on_error=args.on_error,
            workers=args.workers,
        )
    except RunnerAbort as exc:
        print(f"ABORTADO: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result))

    failed_run_keys = result.get("failed_run_keys") or []
    if failed_run_keys:
        print(
            f"CORRIDAS FALLIDAS ({len(failed_run_keys)}): {', '.join(failed_run_keys)}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
