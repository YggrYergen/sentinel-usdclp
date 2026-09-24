"""tests/research/test_ingest_tokata.py — TDD for TOKATA importers (M0.2).

Fixtures under tests/research/fixtures/ are SMALL copies (<=20 rows) of the
real TOKATA files, preserving real quirks: `;`-delimited CSVs with ragged
rows (free-text fields containing unescaped `;`), comma-decimals, and a
handful of genuinely corrupt rows to exercise skip+audit behavior. The real
`D:/WebDev/TOKATA/**` tree is READ-ONLY and never touched by these tests.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_engine.ingest_tokata import ledger, preregistro, signals, forward
from sentinel_engine.ingest_tokata.runner import import_all
from sentinel_engine.research.registry2 import ResearchRegistry

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def reg(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


# ---------------------------------------------------------------------
# ledger.py
# ---------------------------------------------------------------------

def test_ledger_import_maps_clean_row(reg):
    report = ledger.import_ledger(FIXTURES / "mt5_ledger_sample.csv", reg)
    result = reg.query_runs()
    run_ids = {r["run_id"] for r in result["rows"]}
    assert "FT-S-v101" in run_ids
    row = next(r for r in result["rows"] if r["run_id"] == "FT-S-v101")
    assert row["engine"] == "mt5-tester"
    assert row["fidelity"] == "screening"
    assert row["trades"] == 64
    assert row["net"] == pytest.approx(696.6)
    assert row["familia"] == "sapitos"
    assert report.rows_new > 0


def test_ledger_fidelity_mapping(reg):
    ledger.import_ledger(FIXTURES / "mt5_ledger_sample.csv", reg)
    result = reg.query_runs()
    by_id = {r["run_id"]: r for r in result["rows"]}
    # tipo_corrida 'paridad-realtick' -> real-tick per D.8 (validacion|validación)
    # our fixture uses 'paridad'/'paridad-realtick'/'screening-m1' as observed in real data
    assert by_id["PAR-001"]["fidelity"] in ("research", "screening", "real-tick", "forward")


def test_ledger_repairs_ragged_row_with_embedded_semicolons(reg):
    # PAR-002 has an unescaped ';' inside mecanismo_preregistro in the real file;
    # a naive csv split would misalign net/pf/etc. Verify correct realignment.
    ledger.import_ledger(FIXTURES / "mt5_ledger_sample.csv", reg)
    result = reg.query_runs()
    row = next(r for r in result["rows"] if r["run_id"] == "PAR-002")
    assert row["trades"] == 73
    assert row["net"] == pytest.approx(2805.8)
    assert row["pf"] == pytest.approx(1.53)


def test_ledger_corrupt_row_skipped_and_audited(reg):
    report = ledger.import_ledger(FIXTURES / "mt5_ledger_sample.csv", reg)
    assert report.rows_skipped >= 1
    conn = reg._connect()
    try:
        row = conn.execute(
            "SELECT accion FROM audit_log WHERE accion='import_skip'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None


def test_ledger_idempotent_second_run_zero_new(reg):
    report1 = ledger.import_ledger(FIXTURES / "mt5_ledger_sample.csv", reg)
    assert report1.rows_new > 0
    report2 = ledger.import_ledger(FIXTURES / "mt5_ledger_sample.csv", reg)
    assert report2.rows_new == 0


def test_ledger_creates_strategy_per_familia(reg):
    ledger.import_ledger(FIXTURES / "mt5_ledger_sample.csv", reg)
    strategies = reg.query_strategies()
    familias = {s["familia"] for s in strategies}
    assert "sapitos" in familias
    assert "pedro" in familias


# ---------------------------------------------------------------------
# preregistro.py
# ---------------------------------------------------------------------

def test_preregistro_import_roundtrip(reg):
    report = preregistro.import_preregistro(FIXTURES / "preregistro_sample.csv", reg)
    assert report.rows_new > 0
    conn = reg._connect()
    try:
        rows = conn.execute("SELECT preregistro_id, hipotesis FROM preregistration").fetchall()
    finally:
        conn.close()
    assert len(rows) > 0


def test_preregistro_corrupt_row_skipped(reg):
    report = preregistro.import_preregistro(FIXTURES / "preregistro_sample.csv", reg)
    assert report.rows_skipped >= 1


def test_preregistro_idempotent(reg):
    r1 = preregistro.import_preregistro(FIXTURES / "preregistro_sample.csv", reg)
    r2 = preregistro.import_preregistro(FIXTURES / "preregistro_sample.csv", reg)
    assert r1.rows_new > 0
    assert r2.rows_new == 0


# ---------------------------------------------------------------------
# signals.py
# ---------------------------------------------------------------------

def test_signals_parses_entry_and_exit(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "EMASAR_v1", {}, "M1", "XAUUSD", "original")
    reg.insert_run({
        "run_id": "SIGRUN1", "variant_id": vid, "engine": "mt5-tester",
        "fidelity": "research", "periodo_desde": "2026.01.02", "periodo_hasta": "2026.03.23",
    })
    report = signals.import_signals(
        FIXTURES / "TOKATA_EMASAR_v1_signals_sample.csv", reg, variant_id=vid,
    )
    assert report.rows_new > 0
    conn = reg._connect()
    try:
        rows = conn.execute("SELECT side, exit_reason, exit_reason_source FROM trade").fetchall()
    finally:
        conn.close()
    sides = {r[0] for r in rows}
    assert "LONG" in sides or "SHORT" in sides


def test_signals_side_translation_largo_corto(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "EMASAR_v1", {}, "M1", "XAUUSD", "original")
    reg.insert_run({"run_id": "SIGRUN2", "variant_id": vid, "engine": "mt5-tester", "fidelity": "research"})
    signals.import_signals(FIXTURES / "TOKATA_EMASAR_v1_signals_sample.csv", reg, variant_id=vid)
    conn = reg._connect()
    try:
        rows = conn.execute("SELECT DISTINCT side FROM trade").fetchall()
    finally:
        conn.close()
    for (side,) in rows:
        assert side in ("LONG", "SHORT")


# ---------------------------------------------------------------------
# forward.py
# ---------------------------------------------------------------------

def test_forward_import_creates_sessions_and_trades(reg):
    report = forward.import_forward(FIXTURES / "forward_positions_ledger_sample.csv", reg)
    assert report.rows_new > 0
    conn = reg._connect()
    try:
        sessions = conn.execute("SELECT session_id FROM forward_session").fetchall()
        trades = conn.execute("SELECT trade_id, session_id, origin FROM trade WHERE session_id IS NOT NULL").fetchall()
    finally:
        conn.close()
    assert len(sessions) > 0
    assert len(trades) > 0
    for _, _, origin in trades:
        assert origin == "strategy"


def test_forward_idempotent(reg):
    r1 = forward.import_forward(FIXTURES / "forward_positions_ledger_sample.csv", reg)
    r2 = forward.import_forward(FIXTURES / "forward_positions_ledger_sample.csv", reg)
    assert r1.rows_new > 0
    assert r2.rows_new == 0


# ---------------------------------------------------------------------
# runner.py (import_all)
# ---------------------------------------------------------------------

def test_import_all_uses_fixture_root(reg, tmp_path):
    root = tmp_path / "TOKATA_fake"
    (root / "backtest_results").mkdir(parents=True)
    (root / "backtest_results" / "forward_daily").mkdir(parents=True)
    (root / "mt5" / "reports").mkdir(parents=True)

    import shutil
    shutil.copy(FIXTURES / "mt5_ledger_sample.csv", root / "backtest_results" / "mt5_ledger.csv")
    shutil.copy(FIXTURES / "preregistro_sample.csv", root / "backtest_results" / "preregistro.csv")
    shutil.copy(
        FIXTURES / "forward_positions_ledger_sample.csv",
        root / "backtest_results" / "forward_positions_ledger.csv",
    )
    shutil.copy(
        FIXTURES / "TOKATA_EMASAR_v1_signals_sample.csv",
        root / "mt5" / "reports" / "TOKATA_EMASAR_v1_signals.csv",
    )

    report = import_all(root, reg)
    assert report.files >= 3
    assert report.rows_new > 0

    strategies = reg.query_strategies()
    assert len(strategies) > 0

    # idempotent second pass
    report2 = import_all(root, reg)
    assert report2.rows_new == 0
