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


# ---------------------------------------------------------------------
# EMASAR V1 MT5-fidelity integration (design spec 2026-07-10, Component 4):
# additive/nullable trade.signal_id + trade.ficha, and widened run.engine /
# run.fidelity CHECK constraints to admit 'mt5-import' / 'mt5-htm'.
# ---------------------------------------------------------------------

def test_trade_table_has_nullable_signal_id_and_ficha_columns(reg):
    cols = {row[1] for row in reg._connect().execute("PRAGMA table_info(trade)").fetchall()}
    assert "signal_id" in cols
    assert "ficha" in cols


def test_legacy_trade_insert_leaves_signal_id_and_ficha_null(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V-legacy", {}, "M5", "XAUUSD", "original")
    reg.insert_run({"run_id": "R-legacy", "variant_id": vid, "engine": "mt5-tester", "fidelity": "research"})
    reg.insert_trades("R-legacy", [
        {"trade_id": "TL1", "ts_in": "2026-07-01T00:00:00", "px_in": 100.0, "side": "LONG"},
    ])
    trades = reg.get_trades_for_run("R-legacy")
    assert trades[0]["signal_id"] is None
    assert trades[0]["ficha"] is None


def test_trade_insert_can_carry_signal_id_and_ficha(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V-v1", {}, "M5", "XAUUSD", "3ficha")
    reg.insert_run({"run_id": "R-v1", "variant_id": vid, "engine": "mt5-import", "fidelity": "mt5-htm"})
    reg.insert_trades("R-v1", [
        {
            "trade_id": "TV1", "ts_in": "2026-01-11T20:00:00", "px_in": 4511.96,
            "side": "LONG", "signal_id": "sig-0001", "ficha": "F1",
            "exit_reason": "EXIT_ENGULF", "exit_reason_source": "emasar_ref",
        },
    ])
    trades = reg.get_trades_for_run("R-v1")
    assert trades[0]["signal_id"] == "sig-0001"
    assert trades[0]["ficha"] == "F1"
    assert trades[0]["exit_reason"] == "EXIT_ENGULF"
    assert trades[0]["exit_reason_source"] == "emasar_ref"


# ---------------------------------------------------------------------
# Defect D (Wave-2 plan 2026-07-10): `/trades` ts_in/ts_out must come back
# ISO-8601 UTC (`...Z`), never MT5 dotted-string (`2026.01.11 20:00:00`).
# `new Date('2026.01.11 20:00:00')` parses as browser-LOCAL time in JS ->
# markers land offset from the UTC candle axis. Source is UTC already
# (MT5 tester times matched lake bars byte-identically) -- reformat only,
# never shift the clock. get_trades_for_run is the read-path serialization
# point, so it normalizes regardless of how ts_in/ts_out were stored.
# ---------------------------------------------------------------------

def test_get_trades_for_run_normalizes_mt5_dotted_ts_to_iso_utc(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V-mt5dotted", {}, "M5", "XAUUSD", "3ficha")
    reg.insert_run({"run_id": "R-mt5dotted", "variant_id": vid, "engine": "mt5-import", "fidelity": "mt5-htm"})
    reg.insert_trades("R-mt5dotted", [
        {
            "trade_id": "TD1", "ts_in": "2026.01.11 20:00:00", "ts_out": "2026.01.11 20:10:40",
            "px_in": 4511.96, "side": "LONG",
        },
    ])
    trades = reg.get_trades_for_run("R-mt5dotted")
    assert trades[0]["ts_in"] == "2026-01-11T20:00:00Z"
    assert trades[0]["ts_out"] == "2026-01-11T20:10:40Z"


def test_get_trades_for_run_normalizes_already_iso_ts_to_z_suffix(reg):
    """Non-MT5 ingest paths already store bare ISO (no `Z`/offset) -- the
    normalizer must reformat those too (same UTC instant, `Z` appended),
    not just the MT5-dotted format, so /trades emits ONE unambiguous shape
    regardless of ingest origin."""
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V-iso", {}, "M5", "XAUUSD", "original")
    reg.insert_run({"run_id": "R-iso", "variant_id": vid, "engine": "mt5-tester", "fidelity": "research"})
    reg.insert_trades("R-iso", [
        {"trade_id": "TI1", "ts_in": "2026-07-01T00:00:00", "ts_out": "2026-07-01T01:00:00", "px_in": 100.0, "side": "LONG"},
    ])
    trades = reg.get_trades_for_run("R-iso")
    assert trades[0]["ts_in"] == "2026-07-01T00:00:00Z"
    assert trades[0]["ts_out"] == "2026-07-01T01:00:00Z"


def test_get_trades_for_run_leaves_null_ts_out_alone(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V-opentrade", {}, "M5", "XAUUSD", "3ficha")
    reg.insert_run({"run_id": "R-opentrade", "variant_id": vid, "engine": "mt5-import", "fidelity": "mt5-htm"})
    reg.insert_trades("R-opentrade", [
        {"trade_id": "TO1", "ts_in": "2026.01.28 21:35:00", "px_in": 4500.0, "side": "LONG"},
    ])
    trades = reg.get_trades_for_run("R-opentrade")
    assert trades[0]["ts_in"] == "2026-01-28T21:35:00Z"
    assert trades[0]["ts_out"] is None


def test_run_engine_admits_mt5_import(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V-mt5import", {}, "M5", "XAUUSD", "3ficha")
    reg.insert_run({
        "run_id": "R-mt5import", "variant_id": vid,
        "engine": "mt5-import", "fidelity": "mt5-htm",
    })
    result = reg.query_runs()
    row = next(r for r in result["rows"] if r["run_id"] == "R-mt5import")
    assert row["engine"] == "mt5-import"
    assert row["fidelity"] == "mt5-htm"


def test_get_run_self_heals_null_tf_from_variant_id_suffix(reg):
    """Task 1.2 (Wave-3 Stage 1): pre-existing rows ingested before `tf` was
    populated on the variant row must self-heal at serialization time —
    `get_run` falls back to a `_(M\\d+)_` regex on `variant_id` (e.g.
    `EMS_XAU_V1_M5_c2_sar3m3` -> "M5") so `/api/runs/{id}` never returns a
    null `tf` for an mt5-import run, without requiring a re-ingest."""
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "EMS_XAU_V1_M5_c2_sar3m3", {}, None, "XAUUSD", "3ficha")
    reg.insert_run({
        "run_id": "R-null-tf", "variant_id": vid,
        "engine": "mt5-import", "fidelity": "mt5-htm",
    })
    run = reg.get_run("R-null-tf")
    assert run["tf"] == "M5"
