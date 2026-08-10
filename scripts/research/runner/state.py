"""scripts.research.runner.state -- per-experiment resumption state.

A JSON file next to salidas.resultados, named _runner_state.json, that
records which run_key values already completed. Persists immediately on
every mark_complete so a cut session does not lose progress.
"""
from __future__ import annotations

import json
from pathlib import Path

STATE_FILENAME = "_runner_state.json"


def state_path_for(resultados_dir: Path) -> Path:
    return Path(resultados_dir) / STATE_FILENAME


class RunnerState:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {"completed": {}}

    def is_complete(self, run_key: str) -> bool:
        return run_key in self._data.get("completed", {})

    def mark_complete(self, run_key: str, metrics: dict) -> None:
        self._data.setdefault("completed", {})[run_key] = metrics
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, sort_keys=True, indent=2)
        tmp_path.replace(self.path)
