"""scripts.research.runner.lineage -- lineage tags (protocolo 04, parte 3).

Builds the 10-field tag dict: run_id, area, experimento, config_hash,
substrate_id, engine_sha, git_sha, etapa, generador, timestamp.

git_sha is read live via `git rev-parse --short HEAD`; failure is fail-loud.
timestamp is the host's local time (the host runs in UTC-4, which IS broker
server time) -- never utcnow(), never a zone offset applied.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime


class LineageError(Exception):
    """Raised when a lineage tag cannot be computed (e.g. git unavailable)."""


def git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LineageError(f"git rev-parse --short HEAD failed: {exc}") from exc

    sha = result.stdout.strip()
    if not sha:
        raise LineageError("git rev-parse --short HEAD returned empty output")
    return sha


def config_hash(params: dict) -> str:
    serialized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def build_tags(
    *,
    run_id: str,
    area: str,
    experimento: str,
    params: dict,
    substrate_id: str,
    engine_sha: str,
    etapa: str,
    generador: str,
) -> dict:
    return {
        "run_id": run_id,
        "area": area,
        "experimento": experimento,
        "config_hash": config_hash(params),
        "substrate_id": substrate_id,
        "engine_sha": engine_sha,
        "git_sha": git_sha(),
        "etapa": etapa,
        "generador": generador,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
