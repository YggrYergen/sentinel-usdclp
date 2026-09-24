"""scripts/report/mark_validity_2026_07_19.py -- Task B1 (P38, honest program).

Idempotent, ADDITIVE-ONLY validity marking of research registry runs.

Usage:
    python -m scripts.report.mark_validity_2026_07_19 [--db PATH] [--dry-run]

Hard policy (user directive): the registry is append-only history. Marking
happens ONLY via the nullable `run.validity` column (added additively by
`ResearchRegistry._migrate_additive`) plus `audit_log` rows. No run row is
ever deleted; no original field is ever mutated; the only UPDATE touches
`validity` and only where it is still NULL (idempotency: a second run marks
nothing new and writes no duplicate audit rows).

Marking rules (approved plan `docs/superpowers/plans/2026-07-19-honest-program-master.md`,
orchestrator resolution 2026-07-19):

1. DUPLICATE_INGEST -- group runs by (variant_id, net, trades); within each
   group of >1 rows the FIRST ingest (lowest rowid = insertion order, per
   orchestrator tie-break resolution 2026-07-19) stays unmarked and every
   later row is marked. NULL-metric singletons never form a marked group
   (grouping uses IS-distinct semantics per group key tuple).
2. LOOKAHEAD_CONFIRMED -- the four EXACT run_ids
   sim-report-emasar-v12-{m1,m2,m5,m15}. Exact `IN` match on purpose: a
   LIKE 'sim-report-emasar-v12-m1%' prefix would also swallow -m15, and the
   v12a/v12w timing variants must NOT be marked.
3. REGIME_UNAUDITED -- every run_id LIKE 'sim-report-emasar-oow2-%' (a
   later task upgrades these after the regime audit).

Rule 4 (INEXECUTABLE_STOP) deferred 2026-07-19: no reliable predicate; see
task-B1R4-report.

Every marking writes an audit_log row via the existing registry API:
actor='honest-program', accion='validity-mark',
detalle={run_id, label, reason}.

`--dry-run` opens the DB READ-ONLY (mode=ro URI): it neither marks rows nor
adds the `validity` column nor triggers any registry-constructor side
effect -- it only prints the would-mark counts per label.

Windows-safe: pathlib + sqlite3 stdlib only.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Repo root on sys.path when run as a loose script (python -m from repo root
# already works; this keeps `python scripts/report/...py` working too).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sentinel_engine.research.registry2 import DEFAULT_DB_PATH, ResearchRegistry  # noqa: E402

ACTOR = "honest-program"
ACCION = "validity-mark"

V12_RUN_IDS: tuple[str, ...] = (
    "sim-report-emasar-v12-m1",
    "sim-report-emasar-v12-m2",
    "sim-report-emasar-v12-m5",
    "sim-report-emasar-v12-m15",
)

LABELS = ("DUPLICATE_INGEST", "LOOKAHEAD_CONFIRMED", "REGIME_UNAUDITED")


def _has_validity_column(conn: sqlite3.Connection) -> bool:
    return "validity" in {r[1] for r in conn.execute("PRAGMA table_info(run)")}


def _current_validity(conn: sqlite3.Connection) -> dict[str, str | None]:
    """run_id -> validity (all NULL when the column doesn't exist yet)."""
    if _has_validity_column(conn):
        return dict(conn.execute("SELECT run_id, validity FROM run"))
    return {rid: None for (rid,) in conn.execute("SELECT run_id FROM run")}


def plan_markings(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """Compute [(run_id, label, reason)] for rows whose validity is still
    NULL. Pure read -- safe on a mode=ro connection. Rules apply in order
    1->2->3; a row already planned (or already marked) is never re-planned,
    so each run_id appears at most once."""
    validity = _current_validity(conn)
    planned: dict[str, tuple[str, str]] = {}

    def plan(run_id: str, label: str, reason: str) -> None:
        if validity.get(run_id) is None and run_id not in planned:
            planned[run_id] = (label, reason)

    # Rule 1 -- duplicate ingests. Group over ALL rows (marked or not) so
    # the keeper is stable across re-runs; keeper = lowest rowid (ingest
    # order). NULL net/trades rows: `IS` comparison would group NULLs
    # together, but the GROUP BY below already treats NULLs as equal --
    # matching the verified real-DB census (39 groups, all n=2).
    groups = conn.execute(
        """SELECT variant_id, net, trades FROM run
           GROUP BY variant_id, net, trades HAVING COUNT(*) > 1"""
    ).fetchall()
    for variant_id, net, trades in groups:
        rows = conn.execute(
            """SELECT rowid, run_id FROM run
               WHERE variant_id IS ? AND net IS ? AND trades IS ?
               ORDER BY rowid ASC""",
            (variant_id, net, trades),
        ).fetchall()
        keeper_run_id = rows[0][1]
        for _rowid, run_id in rows[1:]:
            plan(
                run_id,
                "DUPLICATE_INGEST",
                f"duplicate ingest: same (variant_id={variant_id!r}, "
                f"net={net!r}, trades={trades!r}) as kept run "
                f"{keeper_run_id!r} (kept = lowest rowid / first ingest)",
            )

    # Rule 2 -- v12 look-ahead (exact run_ids only; never LIKE).
    placeholders = ",".join("?" for _ in V12_RUN_IDS)
    for (run_id,) in conn.execute(
        f"SELECT run_id FROM run WHERE run_id IN ({placeholders})", V12_RUN_IDS
    ):
        plan(
            run_id,
            "LOOKAHEAD_CONFIRMED",
            "v12 stacked-timing look-ahead confirmed "
            "(docs/superpowers/research/2026-07-13-v12-lookahead-audit.md)",
        )

    # Rule 3 -- oow2 family pending regime audit.
    for (run_id,) in conn.execute(
        "SELECT run_id FROM run WHERE run_id LIKE 'sim-report-emasar-oow2-%'"
    ):
        plan(
            run_id,
            "REGIME_UNAUDITED",
            "oow2 out-of-window family: regime not audited yet "
            "(honest program P38; a later task upgrades these)",
        )

    return [(rid, lab, reason) for rid, (lab, reason) in planned.items()]


def mark_validity(db_path: Path, dry_run: bool = False) -> dict[str, int]:
    """Apply (or, with dry_run, just count) the validity markings.

    Returns {label: n_marked_this_run}. Idempotent: rows whose validity is
    already set are skipped, so a second invocation returns all zeros and
    appends no audit rows.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"registry DB not found: {db_path}")

    counts = {label: 0 for label in LABELS}

    if dry_run:
        # READ-ONLY connection: no column add, no registry side effects.
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            for _run_id, label, _reason in plan_markings(conn):
                counts[label] += 1
        finally:
            conn.close()
        return counts

    # Real run: the registry constructor performs the additive migration
    # (adds nullable run.validity if absent) -- reuse it rather than
    # duplicating DDL here.
    #
    # B1 review fix (2026-07-19): each marking's validity UPDATE and its
    # audit row are written on ONE connection inside ONE transaction for the
    # whole batch, committed once at the end. A crash at ANY point leaves
    # the DB exactly as before (rollback) -- there can never be a marked run
    # without its audit row (audit rows go through `registry.audit_on`,
    # which does NOT commit; the sole commit below covers both).
    registry = ResearchRegistry(db_path)
    conn = registry._connect()
    try:
        markings = plan_markings(conn)
        for run_id, label, reason in markings:
            # The ONLY UPDATE in this script: touches validity exclusively,
            # and only while it is still NULL (ADDITIVE-ONLY + idempotent).
            cur = conn.execute(
                "UPDATE run SET validity=? WHERE run_id=? AND validity IS NULL",
                (label, run_id),
            )
            if cur.rowcount != 1:  # pragma: no cover - concurrent re-mark
                continue
            registry.audit_on(
                conn, ACTOR, ACCION,
                {"run_id": run_id, "label": label, "reason": reason},
            )
            counts[label] += 1
        conn.commit()  # single atomic commit: all marks + all audits, or none
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Additive-only validity marking of registry runs "
                    "(P38, honest program). See module docstring.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH,
                        help=f"registry DB path (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--dry-run", action="store_true",
                        help="print would-mark counts per label; write NOTHING "
                             "(opens the DB read-only)")
    args = parser.parse_args(argv)

    counts = mark_validity(args.db, dry_run=args.dry_run)
    mode = "DRY-RUN (nothing written)" if args.dry_run else "APPLIED"
    print(f"mark_validity_2026_07_19 -- {mode} -- db={args.db}")
    for label in LABELS:
        print(f"  {label}: {counts[label]}")
    print(f"  TOTAL: {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
