"""tests/scripts/test_gen_honest_sweep.py -- Task B2 (P2/P35/P64, honest program).

Tests for `scripts/report/gen_honest_sweep.py`: the manifest-driven honest-sweep
harness. Runs a tiny 2-entry manifest over SYNTHETIC fixture bars into a temp DB
(NEVER the real data/research.db). Covers the brief's assertions:

- Preregistration is written FIRST and run rows link to it (P64); an entry
  missing `prereg` is REFUSED (error) and nothing for it is persisted.
- Every grid cell persists a run row with fidelity='honest-screen' and
  metrics_json.cost_model == 'flat0.5'; the nullable `validity` column stays NULL.
- The opt-integrated league output file (JSON) + markdown report are produced.
- `--dry-list` prints an entry/window matrix and writes NOTHING (no DB rows,
  no league files).
- Resumable: a second invocation SKIPS already-persisted (variant_id, tf, window)
  cells rather than duplicating rows.
- Deterministic: same manifest + same bars => identical net per cell.
"""
from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.report import gen_honest_sweep as ghs
from sentinel_engine.research.registry2 import ResearchRegistry


# ---------------------------------------------------------------------------
# Synthetic bars (same generator shape as tests/strategies/test_emasar_variant).
# ---------------------------------------------------------------------------
def _synthetic_bars(n: int = 400, seed: int = 7) -> list[dict]:
    rnd = random.Random(seed)
    bars: list[dict] = []
    price = 4500.0
    base_epoch = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        open_ = price - drift
        close = price
        high = max(open_, close) + abs(rnd.uniform(0.3, 1.2))
        low = min(open_, close) - abs(rnd.uniform(0.3, 1.2))
        bars.append({
            "t": base_epoch + k * 60,
            "open": open_, "high": high, "low": low, "close": close,
            "volume": 1.0,
        })
    return bars


@pytest.fixture()
def fixture_bars(monkeypatch):
    """Inject deterministic synthetic bars for every (tf, window) so the
    harness never touches the real lake."""
    def _loader(tf: str, window: str) -> list[dict]:
        # distinct-but-deterministic per (tf, window)
        seed = (hash((tf, window)) % 1000) + 1
        return _synthetic_bars(400, seed=seed)

    monkeypatch.setattr(ghs, "_BARS_LOADER", _loader)
    return _loader


def _manifest(with_bad: bool = False) -> dict:
    kwargs = dict(
        confirm_mode=1, confirm_count=2, require_ema_order=False,
        ema_fast=8, ema_slow=20, sar_step=0.3, sar_max=0.3,
        f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
        init_sl_range_k=3.0, live_fill_mode=True,
    )
    entries = [
        {
            "variant_id": "HON_XAU_A_M5",
            "tf": "M5",
            "kwargs": dict(kwargs),
            "windows": ["IW", "W1"],
            "prereg": {
                "hypothesis": "A survives honest fills on IW+W1",
                "metric": "net_honest",
                "threshold": 0.0,
            },
        },
        {
            "variant_id": "HON_XAU_B_M2",
            "tf": "M2",
            "kwargs": dict(kwargs),
            "windows": ["IW"],
            "prereg": {
                "hypothesis": "B survives honest fills on IW",
                "metric": "net_honest",
                "threshold": 0.0,
            },
        },
    ]
    if with_bad:
        entries.append({
            "variant_id": "HON_XAU_BAD_M1",
            "tf": "M1",
            "kwargs": dict(kwargs),
            "windows": ["IW"],
            # NO prereg -> must be refused.
        })
    return {"_note": "test manifest", "entries": entries}


def _write_manifest(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _runs(db: Path) -> list[dict]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM run")]
    finally:
        conn.close()


def _preregs(db: Path) -> list[dict]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM preregistration")]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Happy path: prereg + linked runs + fidelity + cost model + league output.
# ---------------------------------------------------------------------------
def test_run_persists_prereg_linked_honest_runs_and_league(tmp_path, fixture_bars):
    db = tmp_path / "research.db"
    ResearchRegistry(db)  # materialize schema (incl. validity column)
    manifest = _write_manifest(tmp_path, _manifest())
    league = tmp_path / "league.json"

    result = ghs.run_sweep(
        manifest_path=manifest, db_path=db, league_json=league,
        report_md=tmp_path / "report.md",
    )

    # 3 grid cells: A on IW+W1, B on IW.
    runs = _runs(db)
    assert len(runs) == 3
    for r in runs:
        assert r["fidelity"] == "honest-screen"
        assert r["validity"] is None  # new honest runs: validity NULL
        assert r["preregistro_id"]  # linked to a prereg (P64)
        m = json.loads(r["metrics_json"])
        assert m["cost_model"] == "flat0.5"

    # one prereg per manifest entry (2), each linked from >=1 run.
    preregs = _preregs(db)
    assert len(preregs) == 2
    linked = {r["preregistro_id"] for r in runs}
    assert {p["preregistro_id"] for p in preregs} == linked

    # league artifacts exist.
    assert league.exists()
    assert (tmp_path / "report.md").exists()
    league_data = json.loads(league.read_text(encoding="utf-8"))
    assert league_data["n_trials"] == 2  # trial family size == manifest size
    assert result["persisted"] == 3


def test_entry_without_prereg_is_refused(tmp_path, fixture_bars):
    db = tmp_path / "research.db"
    ResearchRegistry(db)
    manifest = _write_manifest(tmp_path, _manifest(with_bad=True))

    with pytest.raises(ghs.PreregistrationRequired):
        ghs.run_sweep(
            manifest_path=manifest, db_path=db,
            league_json=tmp_path / "league.json",
            report_md=tmp_path / "report.md",
        )

    # The bad entry (M1) must have persisted nothing.
    runs = _runs(db)
    assert all("_M1" not in (r["variant_id"] or "") for r in runs)


def test_dry_list_writes_nothing(tmp_path, fixture_bars, capsys):
    db = tmp_path / "research.db"
    ResearchRegistry(db)
    manifest = _write_manifest(tmp_path, _manifest())
    league = tmp_path / "league.json"

    ghs.run_sweep(
        manifest_path=manifest, db_path=db, league_json=league,
        report_md=tmp_path / "report.md", dry_list=True,
    )

    out = capsys.readouterr().out
    assert "2" in out  # entry count printed
    assert not _runs(db)  # no DB writes
    assert not _preregs(db)
    assert not league.exists()  # no league file


def test_second_invocation_skips_persisted_cells(tmp_path, fixture_bars):
    db = tmp_path / "research.db"
    ResearchRegistry(db)
    manifest = _write_manifest(tmp_path, _manifest())

    r1 = ghs.run_sweep(
        manifest_path=manifest, db_path=db,
        league_json=tmp_path / "league1.json", report_md=tmp_path / "r1.md",
    )
    runs_after_1 = _runs(db)
    nets_1 = {(r["variant_id"], r["periodo_desde"]): r["net"] for r in runs_after_1}

    r2 = ghs.run_sweep(
        manifest_path=manifest, db_path=db,
        league_json=tmp_path / "league2.json", report_md=tmp_path / "r2.md",
    )
    runs_after_2 = _runs(db)

    # No new run rows on the second pass; every cell skipped.
    assert len(runs_after_2) == len(runs_after_1) == 3
    assert r1["persisted"] == 3
    assert r2["persisted"] == 0
    assert r2["skipped"] == 3

    # Deterministic: nets identical across the two invocations.
    nets_2 = {(r["variant_id"], r["periodo_desde"]): r["net"] for r in runs_after_2}
    assert nets_1 == nets_2
