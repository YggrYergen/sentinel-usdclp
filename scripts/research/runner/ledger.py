"""scripts.research.runner.ledger -- append-only writer for a LEDGER.jsonl.

Validates the 13 required fields from research/LEDGER.schema.md BEFORE
writing; if any is missing, nothing is written. Always opens in append
mode -- never read-modify-rewrite, never edits or deletes an existing line.
Explicit utf-8 encoding.
"""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_FIELDS = (
    "run_id",
    "timestamp",
    "etapa",
    "area",
    "experimento",
    "hipotesis_ref",
    "substrate_id",
    "engine_sha",
    "git_sha",
    "config_hash",
    "generador",
    "artefactos",
    "estado",
)


class LedgerError(Exception):
    """Raised when a ledger row fails validation (missing required field)."""


def append_row(ledger_path: Path, row: dict) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in row]
    if missing:
        raise LedgerError(f"ledger row missing required field(s): {', '.join(missing)}")

    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, sort_keys=True, ensure_ascii=False)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
