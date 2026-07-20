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

    # SAME league path both times (realistic restart): the derived trials DB
    # must be rebuilt, keeping the DSR trial family == manifest size.
    league = tmp_path / "league.json"
    r1 = ghs.run_sweep(
        manifest_path=manifest, db_path=db,
        league_json=league, report_md=tmp_path / "r1.md",
    )
    runs_after_1 = _runs(db)
    nets_1 = {(r["variant_id"], r["periodo_desde"]): r["net"] for r in runs_after_1}

    r2 = ghs.run_sweep(
        manifest_path=manifest, db_path=db,
        league_json=league, report_md=tmp_path / "r2.md",
    )
    runs_after_2 = _runs(db)
    league_2 = json.loads(league.read_text(encoding="utf-8"))
    assert league_2["n_trials"] == 2  # trial family not inflated by restart

    # No new run rows on the second pass; every cell skipped.
    assert len(runs_after_2) == len(runs_after_1) == 3
    assert r1["persisted"] == 3
    assert r2["persisted"] == 0
    assert r2["skipped"] == 3

    # Deterministic: nets identical across the two invocations.
    nets_2 = {(r["variant_id"], r["periodo_desde"]): r["net"] for r in runs_after_2}
    assert nets_1 == nets_2


# ---------------------------------------------------------------------------
# B2 review fixes: the honest-fidelity migration must be crash-atomic and must
# refuse to rebuild run/trade if unnamed indexes/triggers would be lost.
# ---------------------------------------------------------------------------
def _seed_run_and_trade(db: Path) -> None:
    reg = ResearchRegistry(db)
    sid = reg.upsert_strategy("EMASAR", "emasar", "py")
    reg.upsert_variant(sid, "VAR_PRE", {}, "M5", "XAUUSD", None)
    reg.insert_run({
        "run_id": "pre-existing-run", "variant_id": "VAR_PRE",
        "engine": "sentinel-sim", "fidelity": "screening",
        "trades": 1, "net": 42.0, "fecha_corrida": "2026-07-01",
    })
    reg.insert_trades("pre-existing-run", [{
        "trade_id": "pre-t1", "run_id": "pre-existing-run",
        "ts_in": "2026.07.01 10:00:00", "px_in": 4500.0, "side": "LONG",
    }])


class _CrashingConn:
    """Proxy that simulates power loss mid-rebuild: executes the migration
    script only up to (not including) the first DROP TABLE, then dies. With a
    transactional script (BEGIN...COMMIT) the close() in the harness's
    `finally` must roll the whole rebuild back."""

    def __init__(self, real: sqlite3.Connection):
        self._real = real

    def execute(self, *a):
        return self._real.execute(*a)

    def commit(self):
        return self._real.commit()

    def close(self):
        return self._real.close()

    def executescript(self, script: str):
        assert "BEGIN" in script  # migration must be transactional
        idx = script.index("DROP TABLE")
        self._real.executescript(script[:idx])
        raise sqlite3.OperationalError("simulated power loss mid-rebuild")


def test_migration_crash_mid_rebuild_rolls_back(tmp_path, monkeypatch):
    db = tmp_path / "research.db"
    _seed_run_and_trade(db)

    def _crash_connect(self):
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON")
        return _CrashingConn(conn)

    reg = ResearchRegistry(db)
    monkeypatch.setattr(ResearchRegistry, "_connect", _crash_connect)
    with pytest.raises(sqlite3.OperationalError):
        ghs._ensure_honest_fidelity(reg)
    monkeypatch.undo()

    # Whole rebuild rolled back: original tables intact, no transients left.
    conn = sqlite3.connect(str(db))
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "run" in names and "trade" in names
        assert "run_pre_honest" not in names
        assert "trade_pre_honest" not in names
        run_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='run'"
        ).fetchone()[0]
        assert "honest-screen" not in run_sql  # migration did NOT half-apply
        assert conn.execute(
            "SELECT net FROM run WHERE run_id='pre-existing-run'"
        ).fetchone()[0] == 42.0
        assert conn.execute(
            "SELECT px_in FROM trade WHERE trade_id='pre-t1'"
        ).fetchone()[0] == 4500.0
    finally:
        conn.close()

    # And a clean retry completes the migration.
    ghs._ensure_honest_fidelity(ResearchRegistry(db))
    conn = sqlite3.connect(str(db))
    try:
        run_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='run'"
        ).fetchone()[0]
        assert "honest-screen" in run_sql
        assert conn.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM trade").fetchone()[0] == 1
    finally:
        conn.close()


def test_migration_refuses_when_extra_index_would_be_lost(tmp_path):
    db = tmp_path / "research.db"
    _seed_run_and_trade(db)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("CREATE INDEX extra_ix_net ON run(net)")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(RuntimeError, match="refus"):
        ghs._ensure_honest_fidelity(ResearchRegistry(db))

    # Nothing rebuilt: index still there, enum not widened, rows intact.
    conn = sqlite3.connect(str(db))
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        assert "extra_ix_net" in names
        run_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='run'"
        ).fetchone()[0]
        assert "honest-screen" not in run_sql
        assert conn.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 1
    finally:
        conn.close()
