"""sentinel_engine.ingest_tokata — read-only TOKATA artifact importers (M0.2).

Every importer in this package reads CSV artifacts produced by the MT5
tester / TOKATA tooling under `D:/WebDev/TOKATA/**` (an ABSOLUTE READ-ONLY
tree — nothing here ever writes/moves/renames inside it) and maps them into
the `sentinel_engine.research.registry2.ResearchRegistry` (SQLite) per
`docs/superpowers/plans/2026-07-09-sentinel-v2-tokata.md` §D.8 (normative).

Common conventions across all importers:
- Windows-safe: `pathlib.Path` everywhere, `encoding="utf-8"` explicit.
- Files are read with `utf-8-sig` (BOM-tolerant) and fall back to
  `latin-1` if that fails to decode.
- CSV separator is `;` (ledger/preregistro/signals) or `,` (forward ledgers,
  matching the real TOKATA files) — each module documents its own.
- Comma-decimals (`"1,53"`) are normalized to dot-decimals before `float()`.
- Idempotency: every importer computes a sha256 of the file bytes and
  consults/updates `registry.checksum_seen` / `registry.mark_checksum`; if
  the checksum is unchanged since the last import, the file is skipped
  entirely (rows_new=0) without touching the database.
- Corrupt/unparseable rows are recorded via `registry.audit(actor, "import_skip",
  detalle)` and never abort the import — `ImportReport.errors` collects a
  human-readable note per skip too.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


def read_text_resilient(path: Path) -> str:
    """Read a TOKATA artifact as text: `utf-8-sig` first (BOM-tolerant),
    falling back to `latin-1` (never raises on decode for these files)."""
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def to_float(value: str | None) -> float | None:
    """Comma-decimal ("1,53") or dot-decimal ("1.53") -> float; blank/None
    -> None. Never raises; returns None if the value cannot be parsed."""
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return None
    v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def to_int(value: str | None) -> int | None:
    f = to_float(value)
    if f is None:
        return None
    return int(f)


@dataclass
class ImportReport:
    """Aggregate result of one or more importer calls (D.8)."""

    files: int = 0
    rows_new: int = 0
    rows_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "ImportReport") -> "ImportReport":
        self.files += other.files
        self.rows_new += other.rows_new
        self.rows_skipped += other.rows_skipped
        self.errors.extend(other.errors)
        return self
