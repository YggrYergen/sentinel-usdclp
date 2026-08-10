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


def register(name: str, fn: TaskFn) -> None:
    """Register (or overwrite) a task-type under ``name``."""
    _REGISTRY[name] = fn


def get_registry() -> dict[str, TaskFn]:
    """Return a snapshot (shallow copy) of the current task-type registry."""
    return dict(_REGISTRY)


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
