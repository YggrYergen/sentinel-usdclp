"""scripts.research.runner.state -- per-experiment resumption state.

A JSON file next to salidas.resultados, named _runner_state.json, that
records which run_key values already completed. Persists immediately on
every mark_complete so a cut session does not lose progress.

T0.9-B adds a `failed` dict alongside `completed` (overnight/--on-error
continue): a corrida that fails under `--on-error continue` is recorded
here, NOT in `completed`, so `is_complete()` keeps returning False and a
later re-run retries it. A `durations` dict records each corrida's
wall-clock duration in seconds (T0.9-B SS3, progress/ETA), keyed the same
as `completed`/`failed`; it is populated only when the caller passes
`duration_s` -- pre-existing callers that don't pass it get the exact
pre-T0.9-B behaviour.
"""
from __future__ import annotations

import json
from datetime import datetime
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
                data = json.load(f)
        else:
            data = {}
        data.setdefault("completed", {})
        data.setdefault("failed", {})
        data.setdefault("durations", {})
        return data

    def is_complete(self, run_key: str) -> bool:
        return run_key in self._data.get("completed", {})

    def is_failed(self, run_key: str) -> bool:
        return run_key in self._data.get("failed", {})

    def mark_complete(self, run_key: str, metrics: dict, *, duration_s: float | None = None) -> None:
        self._data.setdefault("completed", {})[run_key] = metrics
        # success after a prior failure: promote out of `failed` (retry semantics).
        self._data.setdefault("failed", {}).pop(run_key, None)
        if duration_s is not None:
            self._data.setdefault("durations", {})[run_key] = duration_s
        self._save()

    def mark_failed(self, run_key: str, error: str, *, duration_s: float | None = None) -> None:
        """Record run_key as FAILED (not complete). Increments `attempts` if
        this run_key was already failed from a previous attempt."""
        failed = self._data.setdefault("failed", {})
        attempts_prev = failed.get(run_key, {}).get("attempts", 0)
        failed[run_key] = {
            "error": error,
            "attempts": attempts_prev + 1,
            # local host time -- host clock IS broker server time (UTC-4),
            # never utcnow(), never a zone conversion.
            "last_ts": datetime.now().isoformat(timespec="seconds"),
        }
        if duration_s is not None:
            self._data.setdefault("durations", {})[run_key] = duration_s
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, sort_keys=True, indent=2)
        tmp_path.replace(self.path)
