"""tests/ai/test_dossier_position.py — TDD for Task C3a: position dossier
builder (CT-7, `sentinel_engine/ai/dossier.py`).

CT-7 (frozen contract): `build_position_dossier(trade_id, tfs=["M5"]) ->
{"xml": str, "token_estimate": int, "sections": dict[str,int]}`. Format is
the LITERAL §3 template of
`docs/superpowers/specs/2026-07-12-llm-timeseries-context-research.md`:
markdown tables, fixed dp, `<document><source>...<document_content>`
wrappers, stats server-computed, question NOT included (caller appends it
last). Budget: position dossier <= 8K tokens; oversized bar tables must be
trimmed (oldest rows dropped) with the trim recorded in `sections`.

This test seeds a tiny, deterministic fixture registry DB (sqlite, same DDL
as `ResearchRegistry`) + a tiny fixture lake (parquet via
`sentinel_engine.lake.store.write_bars`) under `tmp_path`, golden-compares
the resulting XML against a committed fixture file
(`tests/ai/fixtures/dossier_position_golden.xml`) by BOTH sha256 hash and
full string diff, and separately covers the token-estimate formula, budget
trim, and unknown-trade_id error handling.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from sentinel_engine.ai.dossier import DossierError, build_position_dossier
from sentinel_engine.lake import store
from sentinel_engine.research.registry2 import ResearchRegistry

FIXTURES = Path(__file__).parent / "fixtures"

# Fixed, deterministic timestamps -- no wall-clock (per repo-wide
# reproducibility discipline, see ai_context.py docstring).
TS_IN = pd.Timestamp("2026-07-10T13:22:00Z")
TS_OUT = pd.Timestamp("2026-07-10T13:41:00Z")


def _seed_registry(db_path: Path) -> ResearchRegistry:
    reg = ResearchRegistry(db_path)
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "sl_tp")
    run_id = reg.insert_run({
        "run_id": "RUN001",
        "variant_id": vid,
        "engine": "sentinel-sim",
        "fidelity": "research",
        "periodo_desde": "2026-07-01",
        "periodo_hasta": "2026-07-11",
    })
    reg.insert_trades(run_id, [{
        "trade_id": "T00001",
        "run_id": run_id,
        "origin": "strategy",
        "ts_in": TS_IN.isoformat(),
        "ts_out": TS_OUT.isoformat(),
        "px_in": 2415.30,
        "px_out": 2418.75,
        "side": "LONG",
        "volume": 0.50,
        "sl": 2413.80,
        "tp": 2420.00,
        "exit_reason": "tp_hit",
        "exit_reason_source": "broker",
        "pnl": 172.50,
        "mae": -4.2,
        "mfe": 34.5,
    }])
    return reg


def _m5_frame(n: int, start: pd.Timestamp) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="5min", tz="UTC")
    base = 2410.0
    df = pd.DataFrame({
        "open": [base + i * 0.10 for i in range(n)],
        "high": [base + i * 0.10 + 0.30 for i in range(n)],
        "low": [base + i * 0.10 - 0.20 for i in range(n)],
        "close": [base + i * 0.10 + 0.05 for i in range(n)],
        "volume": [100.0 + i for i in range(n)],
    }, index=idx)
    df.index.name = "time"
    return df


def _seed_lake(lake_root: Path, symbol: str, n: int, start: pd.Timestamp) -> None:
    store.write_bars(lake_root, symbol, 5, _m5_frame(n, start))


@pytest.fixture
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "research.db"
    lake_root = tmp_path / "lake"
    reg = _seed_registry(db_path)
    # Deep history BEFORE the display window so the 200-bar indicator warmup
    # (same pattern as the /api/bars overlays endpoint) has real data:
    # 250 bars before entry + entry/exit + a tail after. ema8/ema20/sar must
    # then be non-NaN on every served row (asserted in the golden fixture).
    start = TS_IN - pd.Timedelta(minutes=5 * 250)
    _seed_lake(lake_root, "XAUUSD", 300, start)
    return {"db_path": db_path, "lake_root": lake_root, "reg": reg}


def test_golden_snapshot_matches_committed_fixture(env):
    result = build_position_dossier(
        "T00001", tfs=["M5"], db_path=env["db_path"], lake_root=env["lake_root"],
    )
    golden_path = FIXTURES / "dossier_position_golden.xml"
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


def test_token_estimate_formula(env):
    import math

    result = build_position_dossier(
        "T00001", tfs=["M5"], db_path=env["db_path"], lake_root=env["lake_root"],
    )
    expected = math.ceil(len(result["xml"]) / 3.5)
    assert result["token_estimate"] == expected


def test_sections_reports_char_counts(env):
    result = build_position_dossier(
        "T00001", tfs=["M5"], db_path=env["db_path"], lake_root=env["lake_root"],
    )
    assert isinstance(result["sections"], dict)
    assert "trade_record" in result["sections"]
    assert "derived_stats" in result["sections"]
    assert "bars:M5" in result["sections"]


def test_budget_trim_kicks_in_on_oversized_fixture(tmp_path, monkeypatch):
    import sentinel_engine.ai.dossier as dossier_mod

    # Widen the bars-before/after window far beyond normal so the rendered
    # table alone blows the 8K-token budget -- forces the trim path.
    monkeypatch.setattr(dossier_mod, "BARS_BEFORE_ENTRY", 5000)
    monkeypatch.setattr(dossier_mod, "BARS_AFTER_EXIT", 2000)

    db_path = tmp_path / "research.db"
    lake_root = tmp_path / "lake"
    _seed_registry(db_path)
    start = TS_IN - pd.Timedelta(minutes=5 * 5000)
    _seed_lake(lake_root, "XAUUSD", 8000, start)

    result = build_position_dossier(
        "T00001", tfs=["M5"], db_path=db_path, lake_root=lake_root,
    )
    assert result["token_estimate"] <= 8000
    assert result["sections"].get("trim_applied") is True
    assert "bars:M5" in result["sections"]


def test_unknown_trade_id_raises_clean_error(env):
    with pytest.raises(DossierError):
        build_position_dossier(
            "DOES_NOT_EXIST", tfs=["M5"],
            db_path=env["db_path"], lake_root=env["lake_root"],
        )
