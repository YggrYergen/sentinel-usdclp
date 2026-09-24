"""scripts.research.runner.tasks -- registry of task-type callables.

A task-type is a callable ``(params: dict, out_dir: Path) -> dict`` (metrics).
Registered by name so manifests can reference it via ``tipo:``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

TaskFn = Callable[[dict, Path], dict]

_REGISTRY: dict[str, TaskFn] = {}
_NON_PARALLELIZABLE: set[str] = set()


def register(name: str, fn: TaskFn, *, parallelizable: bool = True) -> None:
    """Register (or overwrite) a task-type under ``name``.

    ``parallelizable=False`` marks a task-type that must never run inside a
    process pool (T0.9-B): MT5-backed task-types are the motivating case --
    MT5 is attach-only (charter SS A.12) and a second connection is a
    real-money-adjacent hazard. The runner forces ``--workers`` down to 1
    for any manifest whose pending corridas include such a type.
    """
    _REGISTRY[name] = fn
    if parallelizable:
        _NON_PARALLELIZABLE.discard(name)
    else:
        _NON_PARALLELIZABLE.add(name)


def get_registry() -> dict[str, TaskFn]:
    """Return a snapshot (shallow copy) of the current task-type registry."""
    return dict(_REGISTRY)


def get_non_parallelizable_types() -> set[str]:
    """Return a snapshot (shallow copy) of task-type names registered with
    ``parallelizable=False``."""
    return set(_NON_PARALLELIZABLE)


def echo(params: dict, out_dir: Path) -> dict:
    """Reference task-type: writes its params to out_dir/params.json.

    Exists for the runner scaffold's own tests. Not product functionality.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    content = json.dumps(params, sort_keys=True, ensure_ascii=False)
    (out_dir / "params.json").write_text(content, encoding="utf-8")
    return {"bytes": len(content.encode("utf-8"))}


register("echo", echo)
