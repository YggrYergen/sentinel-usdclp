"""tests/ai/test_dossier_strategy.py — TDD for Task C3b: strategy dossier
builder (CT-7, `sentinel_engine/ai/dossier.py::build_strategy_dossier`).

Format is the LITERAL §4 template of
`docs/superpowers/specs/2026-07-12-llm-timeseries-context-research.md`:
stats-first (CT-3 scorecard via `build_scorecard` internals, direct call —
never HTTP), strategy/variants record as compact JSON, compact
one-row-per-run recent-runs markdown table, §4 tools note after
`</documents>`. Budget <= 10K estimated tokens with oldest-runs trim.

Golden-compares against a committed fixture
(`tests/ai/fixtures/dossier_strategy_golden.xml`) by sha256 hash + full
string diff, same style as tests/ai/test_dossier_position.py (C3a).
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from sentinel_engine.ai.dossier import DossierError, build_strategy_dossier
from sentinel_engine.research import scorecard as scorecard_mod
from sentinel_engine.research.registry2 import ResearchRegistry

FIXTURES = Path(__file__).parent / "fixtures"


def _seed(db_path: Path, n_runs: int = 3) -> str:
    reg = ResearchRegistry(db_path)
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "sl_tp")
    for i in range(n_runs):
        run_id = f"RUN{i:03d}"
        reg.insert_run({
            "run_id": run_id,
            "variant_id": vid,
            "engine": "sentinel-sim",
            "fidelity": "research",
            "periodo_desde": "2026-07-01",
            "periodo_hasta": "2026-07-11",
            # Deterministic fecha_corrida (no wall-clock) so newest-first
            # ordering is stable for the golden snapshot.
            "fecha_corrida": f"2026-07-{10 - i:02d}T00:00:00Z",
            "trades": 10 + i,
            "net": 100.0 + i,
            "pf": 1.5 + i * 0.1,
            "wr": 50.0 + i,
            "maxdd": -80.0 - i,
            "sharpe": 1.0 + i * 0.05,
        })
        reg.insert_trades(run_id, [{
            "trade_id": f"T{i:03d}A",
            "run_id": run_id,
            "ts_in": "2026-07-10T13:22:00Z",
            "ts_out": "2026-07-10T13:41:00Z",
            "px_in": 2415.30,
            "px_out": 2418.75,
            "side": "LONG",
            "sl": 2413.80,
            "tp": 2420.00,
            "volume": 0.50,
            "pnl": 172.50,
        }])
    # Point the CT-3 scorecard's `teorico` block at RUN000 (baseline_ref is
    # a migrated column with no registry setter).
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE strategy SET baseline_ref='RUN000' WHERE strategy_id=?", (sid,)
        )
        conn.commit()
    finally:
        conn.close()
    return sid


@pytest.fixture
def env(tmp_path):
    # The scorecard module caches payloads by strategy_id ONLY (not by db
    # path) with a TTL -- clear it so tests never see another test's data.
    scorecard_mod.clear_cache()
    db_path = tmp_path / "research.db"
    sid = _seed(db_path)
    yield {"db_path": db_path, "sid": sid}
    scorecard_mod.clear_cache()


def test_golden_snapshot_matches_committed_fixture(env):
    result = build_strategy_dossier(env["sid"], db_path=env["db_path"])
    golden_path = FIXTURES / "dossier_strategy_golden.xml"
    assert golden_path.exists(), "golden fixture must be committed"
    expected = golden_path.read_text(encoding="utf-8")
    actual = result["xml"]
    actual_hash = hashlib.sha256(actual.encode("utf-8")).hexdigest()
    expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    if actual_hash != expected_hash:
        assert actual == expected, (
            f"XML mismatch (hash {actual_hash} != {expected_hash}):\n"
            f"--- expected ---\n{expected}\n--- actual ---\n{actual}"
        )
    assert actual_hash == expected_hash


def test_token_estimate_and_sections(env):
    import math

    result = build_strategy_dossier(env["sid"], db_path=env["db_path"])
    assert result["token_estimate"] == math.ceil(len(result["xml"]) / 3.5)
    for key in ("aggregate_stats", "strategy_record", "recent_runs"):
        assert key in result["sections"]
    # §4 tools note must ride after </documents>.
    assert "get_trade_bars" in result["xml"]
    assert result["xml"].index("</documents>") < result["xml"].index("get_trade_bars")


def test_budget_trim_kicks_in_on_oversized_fixture(tmp_path, monkeypatch):
    import sentinel_engine.ai.dossier as dossier_mod

    scorecard_mod.clear_cache()
    # Many runs + a tiny budget forces the oldest-runs trim path.
    monkeypatch.setattr(dossier_mod, "BUDGET_TOKENS_STRATEGY", 1200)
    monkeypatch.setattr(dossier_mod, "RECENT_RUNS_LIMIT", 50)
    db_path = tmp_path / "research.db"
    sid = _seed(db_path, n_runs=40)

    result = build_strategy_dossier(sid, db_path=db_path)
    assert result["token_estimate"] <= 1200
    assert result["sections"].get("trim_applied") is True
    assert "recent_runs" in result["sections"]
    scorecard_mod.clear_cache()


def test_unknown_strategy_id_raises_clean_error(env):
    with pytest.raises(DossierError):
        build_strategy_dossier("DOES_NOT_EXIST", db_path=env["db_path"])
