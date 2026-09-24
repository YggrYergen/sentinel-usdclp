"""scripts.research.runner.ledger -- append-only writer for a LEDGER.jsonl.

Validates the 13 required fields from research/LEDGER.schema.md BEFORE
writing; if any is missing, nothing is written. Always opens in append
mode -- never read-modify-rewrite, never edits or deletes an existing line.
Explicit utf-8 encoding.

Hardening (T0.4-impl backlog item): append_row assumed the file already
ends in a newline. If it doesn't, opening in "a" mode and writing
`line + "\n"` merges the new row onto the end of the last existing line,
corrupting an append-only artifact. Before writing, if the file exists and
is non-empty, this checks the last byte and prepends "\n" when missing.
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

    prefix = ""
    if ledger_path.exists() and ledger_path.stat().st_size > 0:
        with ledger_path.open("rb") as f:
            f.seek(-1, 2)
            last_byte = f.read(1)
        if last_byte != b"\n":
            prefix = "\n"

    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(prefix + line + "\n")
