"""tests/research/test_registry2.py — TDD for ResearchRegistry (M0.1).

Covers: DDL creation (WAL on, all tables present), roundtrip per table,
deterministic/validated `allocate_magic`, `query_runs` filters/order/
pagination, and UNIQUE constraint enforcement.
"""
from __future__ import annotations

import sqlite3

import pytest

from sentinel_engine.research.registry2 import ResearchRegistry


@pytest.fixture
def reg(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


def test_creates_db_with_wal_and_all_tables(tmp_path):
    db_path = tmp_path / "research.db"
    ResearchRegistry(db_path)
    assert db_path.exists()
    conn = sqlite3.connect(str(db_path))
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {
            "strategy", "variant", "param_set", "run", "trade",
            "preregistration", "forward_session", "magic_allocation",
            "audit_log", "import_checksum",
        }
        assert expected.issubset(tables)
    finally:
        conn.close()


def test_db_path_is_injectable(tmp_path):
    custom = tmp_path / "sub" / "custom.db"
    custom.parent.mkdir(parents=True, exist_ok=True)
    reg = ResearchRegistry(custom)
    assert custom.exists()
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    assert sid


def test_upsert_strategy_assigns_seq_and_color_idx(reg):
    sid1 = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    sid2 = reg.upsert_strategy("Sapitos", "sapitos", "mt5")
    strategies = reg.query_strategies()
    by_id = {s["strategy_id"]: s for s in strategies}
    assert by_id[sid1]["color_idx"] == 0
    assert by_id[sid2]["color_idx"] == 1
    assert by_id[sid1]["display_color"] == "#00bfff"
    assert by_id[sid2]["display_color"] == "#26a69a"


def test_upsert_strategy_idempotent_same_name_familia(reg):
    sid1 = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    sid2 = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    assert sid1 == sid2
    assert len(reg.query_strategies()) == 1


def test_upsert_variant_roundtrip(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(
        strategy_id=sid,
        variant_id="EMS_XAU_M5_c2",
        params_delta={"sar": 3},
        tf="M5",
        instrumento="XAUUSD",
        modo_salida="original",
    )
    assert vid == "EMS_XAU_M5_c2"
    strategies = reg.query_strategies()
    assert strategies[0]["n_variants"] == 1


def test_upsert_variant_unique_strategy_seq(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "original")
    reg.upsert_variant(sid, "V2", {}, "M5", "XAUUSD", "original")
    # variant_seq must increment per strategy
    conn = reg._connect()
    try:
        seqs = [
            row[0]
            for row in conn.execute(
                "SELECT variant_seq FROM variant WHERE strategy_id=? ORDER BY variant_seq",
                (sid,),
            ).fetchall()
        ]
    finally:
        conn.close()
    assert seqs == [0, 1]


def test_upsert_param_set_roundtrip(reg):
    reg.upsert_param_set("hash1", '{"a": 1}')
    conn = reg._connect()
    try:
        row = conn.execute(
            "SELECT params_json FROM param_set WHERE params_hash=?", ("hash1",)
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == '{"a": 1}'


def test_insert_run_and_query_runs_roundtrip(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "original")
    reg.upsert_param_set("h1", "{}")
    run_id = reg.insert_run({
        "run_id": "R1",
        "variant_id": vid,
        "params_hash": "h1",
        "engine": "mt5-tester",
        "fidelity": "research",
        "instrumento": "XAUUSD",
        "trades": 10,
        "net": 100.0,
        "pf": 1.5,
        "wr": 60.0,
        "payoff": 1.2,
        "maxdd": 50.0,
        "sharpe": 1.1,
        "fecha_corrida": "2026-07-01",
    })
    assert run_id == "R1"
    result = reg.query_runs()
    assert result["total"] == 1
    assert result["rows"][0]["run_id"] == "R1"
    assert result["rows"][0]["familia"] == "emasar"


def test_insert_trades_roundtrip(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "original")
    reg.insert_run({"run_id": "R1", "variant_id": vid, "engine": "mt5-tester", "fidelity": "research"})
    reg.insert_trades("R1", [
        {
            "trade_id": "T1", "ts_in": "2026-07-01T00:00:00", "px_in": 100.0,
            "side": "LONG",
        },
        {
            "trade_id": "T2", "ts_in": "2026-07-01T01:00:00", "px_in": 101.0,
            "side": "SHORT",
        },
    ])
    conn = reg._connect()
    try:
        rows = conn.execute("SELECT trade_id FROM trade WHERE run_id=? ORDER BY ts_in", ("R1",)).fetchall()
    finally:
        conn.close()
    assert [r[0] for r in rows] == ["T1", "T2"]


def test_insert_preregistration_roundtrip(reg):
    reg.insert_preregistration({
        "preregistro_id": "P1",
        "variant_id": "V1",
        "hipotesis": "test",
        "raw_json": "{}",
    })
    conn = reg._connect()
    try:
        row = conn.execute(
            "SELECT hipotesis FROM preregistration WHERE preregistro_id=?", ("P1",)
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "test"


def test_upsert_forward_session_roundtrip(reg):
    reg.upsert_forward_session({
        "session_id": "S1",
        "strategy_id": "SID1",
        "cuenta": "demo1",
        "estado": "activa",
    })
    conn = reg._connect()
    try:
        row = conn.execute(
            "SELECT estado FROM forward_session WHERE session_id=?", ("S1",)
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "activa"
    # idempotent upsert
    reg.upsert_forward_session({"session_id": "S1", "estado": "cerrada"})
    conn = reg._connect()
    try:
        rows = conn.execute("SELECT estado FROM forward_session WHERE session_id=?", ("S1",)).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "cerrada"


def test_allocate_magic_deterministic_formula(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "original")
    strategies = reg.query_strategies()
    seq = next(s for s in strategies if s["strategy_id"] == sid)
    # first strategy_seq should be 0, first variant_seq 0
    magic = reg.allocate_magic(sid, vid)
    assert magic == 100000 + 0 * 1000 + 0


def test_allocate_magic_validates_ranges(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "original")
    # Force out-of-range strategy_seq/variant_seq via direct DB manipulation
    conn = reg._connect()
    try:
        conn.execute("UPDATE strategy SET strategy_seq=900 WHERE strategy_id=?", (sid,))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ValueError):
        reg.allocate_magic(sid, vid)


def test_query_runs_filters_order_pagination(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "original")
    for i in range(5):
        reg.insert_run({
            "run_id": f"R{i}",
            "variant_id": vid,
            "engine": "mt5-tester",
            "fidelity": "research",
            "instrumento": "XAUUSD",
            "net": float(i),
            "fecha_corrida": f"2026-07-0{i+1}",
        })
    result = reg.query_runs(order_by="net", dir="desc", limit=2, offset=0)
    assert result["total"] == 5
    assert [r["run_id"] for r in result["rows"]] == ["R4", "R3"]

    result2 = reg.query_runs(order_by="net", dir="desc", limit=2, offset=2)
    assert [r["run_id"] for r in result2["rows"]] == ["R2", "R1"]

    filtered = reg.query_runs(strategy_id=sid)
    assert filtered["total"] == 5

    filtered_none = reg.query_runs(strategy_id="nonexistent")
    assert filtered_none["total"] == 0


def test_run_unique_pk(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "original")
    reg.insert_run({"run_id": "R1", "variant_id": vid, "engine": "mt5-tester", "fidelity": "research"})
    with pytest.raises(sqlite3.IntegrityError):
        conn = reg._connect()
        try:
            conn.execute(
                "INSERT INTO run(run_id, engine, fidelity) VALUES (?, ?, ?)",
                ("R1", "mt5-tester", "research"),
            )
            conn.commit()
        finally:
            conn.close()


def test_checksum_seen_roundtrip(reg):
    assert reg.checksum_seen("path/a.csv", "sha1") is False
    reg.audit("importer", "mark_seen", {})
    conn = reg._connect()
    try:
        conn.execute(
            "INSERT INTO import_checksum(path, sha256, imported_at) VALUES (?, ?, ?)",
            ("path/a.csv", "sha1", "2026-07-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()
    assert reg.checksum_seen("path/a.csv", "sha1") is True
    assert reg.checksum_seen("path/a.csv", "sha-different") is False


def test_audit_writes_row(reg):
    reg.audit("importer", "import_skip", {"reason": "bad row"})
    conn = reg._connect()
    try:
        row = conn.execute("SELECT actor, accion FROM audit_log").fetchone()
    finally:
        conn.close()
    assert row == ("importer", "import_skip")
