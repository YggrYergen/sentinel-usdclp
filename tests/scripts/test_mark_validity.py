"""tests/scripts/test_mark_validity.py -- Task B1 (P38, honest program).

Tests for `scripts/report/mark_validity_2026_07_19.py` against a synthetic
mini fixture DB built in tmp_path -- NEVER the real `data/research.db`.

Covers (per the approved brief + orchestrator resolution 2026-07-19):
- Rule 1: duplicate groups by (variant_id, net, trades); the FIRST ingest
  (lowest rowid) stays unmarked, later rows -> DUPLICATE_INGEST.
- Rule 2: the four EXACT run_ids sim-report-emasar-v12-{m1,m2,m5,m15} ->
  LOOKAHEAD_CONFIRMED (exact IN match: v12a/v12w and the m1-vs-m15 LIKE
  prefix trap must NOT be marked).
- Rule 3: run_id LIKE 'sim-report-emasar-oow2-%' -> REGIME_UNAUDITED.
- Rule 4 (INEXECUTABLE_STOP): DEFERRED 2026-07-19 -- intentionally absent.
- Every marking writes an audit_log row (actor='honest-program',
  accion='validity-mark', detalle_json carrying run_id + label + reason).
- ADDITIVE-ONLY: no row deleted, no original column value changed -- ever.
- Idempotency: a second run marks nothing new, writes no new audit rows.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.report import mark_validity_2026_07_19 as mv
from sentinel_engine.research.registry2 import ResearchRegistry

V12_RUN_IDS = (
    "sim-report-emasar-v12-m1",
    "sim-report-emasar-v12-m2",
    "sim-report-emasar-v12-m5",
    "sim-report-emasar-v12-m15",
)


def _mk_run(run_id: str, variant_id: str | None, net: float | None,
            trades: int | None) -> dict:
    return {
        "run_id": run_id,
        "variant_id": variant_id,
        "engine": "sentinel-sim",
        "fidelity": "screening",
        "trades": trades,
        "net": net,
        "pf": 1.5,
        "wr": 0.4,
        "fecha_corrida": "2026-07-05",
        "source_file": "tests/fixture",
    }


@pytest.fixture()
def fixture_db(tmp_path: Path) -> Path:
    """Mini registry DB with synthetic rows covering every marking rule."""
    db = tmp_path / "research_fixture.db"
    reg = ResearchRegistry(db)
    sid = reg.upsert_strategy("emasar", "emasar", "py")
    for vid in ("VAR_DUP", "VAR_SINGLE", "VAR_V12", "VAR_OOW", "VAR_NULL"):
        reg.upsert_variant(sid, vid, {}, "M5", "XAUUSD", None)

    # Rule 1: a duplicate pair -- 'dup-second-by-name' ingested FIRST (lower
    # rowid) so the tie-break is provably rowid order, not run_id order.
    reg.insert_run(_mk_run("dup-z-first-ingest", "VAR_DUP", 100.0, 10))
    reg.insert_run(_mk_run("dup-a-second-ingest", "VAR_DUP", 100.0, 10))
    # Control: same variant, different metrics -> NOT a duplicate.
    reg.insert_run(_mk_run("dup-control-diff-net", "VAR_DUP", 200.0, 10))
    # Control: singleton.
    reg.insert_run(_mk_run("single-1", "VAR_SINGLE", 50.0, 5))
    # Control: NULL net/trades singletons must never form a marked group.
    reg.insert_run(_mk_run("null-metrics-1", "VAR_NULL", None, None))

    # Rule 2: the 4 exact v12 run_ids + a v12a control (must stay NULL).
    for i, rid in enumerate(V12_RUN_IDS):
        reg.insert_run(_mk_run(rid, "VAR_V12", 300.0 + i, 20))
    reg.insert_run(_mk_run("sim-report-emasar-v12a-m1", "VAR_V12", 999.0, 21))

    # Rule 3: two oow2 rows + a non-oow2 control.
    reg.insert_run(_mk_run("sim-report-emasar-oow2-ss-m2", "VAR_OOW", 10.0, 3))
    reg.insert_run(_mk_run("sim-report-emasar-oow2-v13-m5", "VAR_OOW", 11.0, 4))
    reg.insert_run(_mk_run("sim-report-emasar-oow-w1-m5", "VAR_OOW", 12.0, 5))
    return db


def _snapshot_runs_sans_validity(db: Path) -> list[tuple]:
    """Every run row, every column EXCEPT validity, ordered by rowid."""
    conn = sqlite3.connect(str(db))
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(run)")
                if r[1] != "validity"]
        sel = ", ".join(f'"{c}"' for c in cols)
        return conn.execute(
            f"SELECT rowid, {sel} FROM run ORDER BY rowid").fetchall()
    finally:
        conn.close()


def _validity(db: Path) -> dict[str, str | None]:
    conn = sqlite3.connect(str(db))
    try:
        return dict(conn.execute("SELECT run_id, validity FROM run"))
    finally:
        conn.close()


def _audit_rows(db: Path) -> list[tuple[str, str, dict]]:
    conn = sqlite3.connect(str(db))
    try:
        return [
            (actor, accion, json.loads(dj))
            for actor, accion, dj in conn.execute(
                "SELECT actor, accion, detalle_json FROM audit_log "
                "WHERE accion='validity-mark' ORDER BY id")
        ]
    finally:
        conn.close()


def test_registry_migration_adds_nullable_validity_column(tmp_path: Path):
    db = tmp_path / "mig.db"
    ResearchRegistry(db)
    conn = sqlite3.connect(str(db))
    try:
        info = {r[1]: r for r in conn.execute("PRAGMA table_info(run)")}
        assert "validity" in info
        # nullable TEXT, no default -- pre-existing rows stay NULL.
        assert info["validity"][2] == "TEXT"
        assert info["validity"][3] == 0  # notnull flag off
    finally:
        conn.close()


def test_marking_labels_and_controls(fixture_db: Path):
    counts = mv.mark_validity(fixture_db, dry_run=False)
    v = _validity(fixture_db)

    # Rule 1: lowest-rowid ingest kept, second marked -- regardless of
    # run_id alphabetical order.
    assert v["dup-z-first-ingest"] is None
    assert v["dup-a-second-ingest"] == "DUPLICATE_INGEST"
    assert v["dup-control-diff-net"] is None
    assert v["single-1"] is None
    assert v["null-metrics-1"] is None

    # Rule 2: exact IN -- the 4 v12 rows marked, v12a control untouched.
    for rid in V12_RUN_IDS:
        assert v[rid] == "LOOKAHEAD_CONFIRMED"
    assert v["sim-report-emasar-v12a-m1"] is None

    # Rule 3: oow2 prefix marked, oow (w1) control untouched.
    assert v["sim-report-emasar-oow2-ss-m2"] == "REGIME_UNAUDITED"
    assert v["sim-report-emasar-oow2-v13-m5"] == "REGIME_UNAUDITED"
    assert v["sim-report-emasar-oow-w1-m5"] is None

    assert counts == {
        "DUPLICATE_INGEST": 1,
        "LOOKAHEAD_CONFIRMED": 4,
        "REGIME_UNAUDITED": 2,
    }


def test_every_marking_writes_an_audit_row(fixture_db: Path):
    mv.mark_validity(fixture_db, dry_run=False)
    rows = _audit_rows(fixture_db)
    assert len(rows) == 7  # 1 dup + 4 v12 + 2 oow2
    marked = _validity(fixture_db)
    for actor, accion, detalle in rows:
        assert actor == "honest-program"
        assert accion == "validity-mark"
        assert detalle["run_id"] in marked
        assert marked[detalle["run_id"]] == detalle["label"]
        assert detalle["label"] in (
            "DUPLICATE_INGEST", "LOOKAHEAD_CONFIRMED", "REGIME_UNAUDITED")
        assert detalle["reason"]  # non-empty human reason
    audited_ids = {d["run_id"] for _, _, d in rows}
    assert audited_ids == {rid for rid, lab in marked.items() if lab}


def test_additive_only_other_columns_untouched(fixture_db: Path):
    before = _snapshot_runs_sans_validity(fixture_db)
    mv.mark_validity(fixture_db, dry_run=False)
    after = _snapshot_runs_sans_validity(fixture_db)
    assert before == after  # no row deleted, no original field mutated


def test_idempotent_second_run_marks_nothing(fixture_db: Path):
    mv.mark_validity(fixture_db, dry_run=False)
    v1 = _validity(fixture_db)
    audits1 = _audit_rows(fixture_db)

    counts2 = mv.mark_validity(fixture_db, dry_run=False)
    assert counts2 == {
        "DUPLICATE_INGEST": 0,
        "LOOKAHEAD_CONFIRMED": 0,
        "REGIME_UNAUDITED": 0,
    }
    assert _validity(fixture_db) == v1
    assert _audit_rows(fixture_db) == audits1  # no duplicate audit rows


def test_mark_and_audit_are_atomic_under_crash(fixture_db: Path, monkeypatch):
    """B1 review fix: a crash between a validity UPDATE and its audit row
    must leave NEITHER committed (one transaction), and a clean re-run must
    recover everything -- no permanently-marked-but-unaudited row."""
    calls = {"n": 0}
    real_audit_on = ResearchRegistry.audit_on

    def flaky_audit_on(self, conn, actor, accion, detalle=None):
        calls["n"] += 1
        if calls["n"] == 3:  # crash mid-batch, after some marks succeeded
            raise RuntimeError("simulated crash between mark and audit")
        return real_audit_on(self, conn, actor, accion, detalle)

    monkeypatch.setattr(ResearchRegistry, "audit_on", flaky_audit_on)
    with pytest.raises(RuntimeError):
        mv.mark_validity(fixture_db, dry_run=False)

    # Atomicity: NOTHING landed -- not even the marks/audits from before the
    # simulated crash (whole batch is one transaction, rolled back).
    assert all(lab is None for lab in _validity(fixture_db).values())
    assert _audit_rows(fixture_db) == []

    # Recovery: a clean re-run marks and audits everything, 1:1.
    monkeypatch.setattr(ResearchRegistry, "audit_on", real_audit_on)
    counts = mv.mark_validity(fixture_db, dry_run=False)
    assert counts == {
        "DUPLICATE_INGEST": 1,
        "LOOKAHEAD_CONFIRMED": 4,
        "REGIME_UNAUDITED": 2,
    }
    rows = _audit_rows(fixture_db)
    assert len(rows) == 7
    marked = {rid for rid, lab in _validity(fixture_db).items() if lab}
    assert {d["run_id"] for _, _, d in rows} == marked


def test_dry_run_writes_nothing(fixture_db: Path):
    before = _snapshot_runs_sans_validity(fixture_db)
    counts = mv.mark_validity(fixture_db, dry_run=True)
    assert counts == {
        "DUPLICATE_INGEST": 1,
        "LOOKAHEAD_CONFIRMED": 4,
        "REGIME_UNAUDITED": 2,
    }
    assert all(lab is None for lab in _validity(fixture_db).values())
    assert _audit_rows(fixture_db) == []
    assert _snapshot_runs_sans_validity(fixture_db) == before
