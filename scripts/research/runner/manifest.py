"""scripts.research.runner.manifest -- load and validate a runner manifest (YAML).

Spec: research/protocolos/06-runners.md and
research/fases/F0-preparacion/02-specs/T0.9min-brief-runner-scaffold.md.

Fail-loud: a missing required field, a duplicate run_key, an empty corridas
list, or an unregistered tipo each raise ManifestError naming the exact
field. Never filled in with a default.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from scripts.research.runner import tasks

REQUIRED_ROOT_FIELDS = (
    "experimento",
    "area",
    "etapa",
    "hipotesis",
    "substrate_id",
    "engine_sha",
)


class ManifestError(Exception):
    """Raised when a manifest fails validation."""


def load_manifest(path: Path) -> dict:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ManifestError(f"manifest {path} is not a mapping")

    for field in REQUIRED_ROOT_FIELDS:
        if field not in data:
            raise ManifestError(f"manifest {path} is missing required field: {field}")

    salidas = data.get("salidas")
    if not isinstance(salidas, dict) or "resultados" not in salidas:
        raise ManifestError(f"manifest {path} is missing required field: salidas.resultados")
    if "ledger" not in salidas:
        raise ManifestError(f"manifest {path} is missing required field: salidas.ledger")

    corridas = data.get("corridas")
    if not isinstance(corridas, list) or len(corridas) == 0:
        raise ManifestError(
            f"manifest {path} is missing required field: corridas (must be a non-empty list)"
        )

    registry = tasks.get_registry()
    seen_run_keys: set[str] = set()
    for i, corrida in enumerate(corridas):
        if not isinstance(corrida, dict):
            raise ManifestError(f"manifest {path} corridas[{i}] is not a mapping")

        run_key = corrida.get("run_key")
        if not run_key:
            raise ManifestError(f"manifest {path} corridas[{i}] is missing required field: run_key")
        if run_key in seen_run_keys:
            raise ManifestError(f"manifest {path} has duplicate run_key: {run_key}")
        seen_run_keys.add(run_key)

        tipo = corrida.get("tipo")
        if not tipo:
            raise ManifestError(
                f"manifest {path} corridas[{i}] (run_key={run_key}) is missing required field: tipo"
            )
        if tipo not in registry:
            raise ManifestError(
                f"manifest {path} corridas[{i}] (run_key={run_key}) has unregistered tipo: {tipo}"
            )

    return data
