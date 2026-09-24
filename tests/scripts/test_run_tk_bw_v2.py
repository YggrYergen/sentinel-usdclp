"""tests/scripts/test_run_tk_bw_v2.py -- focused integration tests for
`scripts/research/run_tk_bw_v2_backtest.py` (Task 2,
docs/superpowers/plans/2026-07-21-tk-bw-regime-state.md "fixes matrix" plan).

Builds a tiny synthetic XAUUSD lake (M1/M5 parquet, tz-aware UTC, written via
the SAME `sentinel_engine.lake.store.write_bars` the real ingesters use) in
`tmp_path`, plus a temp `research.db`. NEVER touches the real lake or
`data/research.db`.

Covers (per the brief's Task 2 test list):
1. CONFIGS: exactly 5 keys with the values of the table (assert dict).
2. run_id/variant_id carry the correct per-config suffix.
3. dry-run (no --write) does not touch the DB.
4. --write registers 5 runs + trades and params_delta passes EmasarPolicy.
5. build_steps/compute_metrics/_df_to_bars/_iso_utc/DESDE_DEFAULT/
   WARMUP_LOOKBACK are the SAME objects as the v1 runner's (import, not
   reimplementation) -- asserted by identity (`is`).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts.research import run_tk_bw_backtest as runner_v1
from scripts.research import run_tk_bw_v2_backtest as runner
from sentinel_engine.lake.store import write_bars
from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.strategies.emasar import EmasarPolicy

SYMBOL = "XAUUSD"
DESDE = pd.Timestamp("2026-07-20T00:00:00Z")

EXPECTED_KEYS = {"fix1seq", "fix2atr", "fix3r", "fix4reg", "fixall"}


def _is_iso_utc(s: str) -> bool:
    return isinstance(s, str) and (s.endswith("Z") or s.endswith("+00:00"))


def _m1_series(start: pd.Timestamp, n_minutes: int) -> pd.DataFrame:
    """Same deterministic fixture shape as tests/scripts/test_run_tk_bw_backtest.py:
    repeating "mild decline then sharp spike-up" cycles, so at least SOME of
    the 5 configs (sequence-armed breakout in particular) get a fair chance
    to fire an entry once resampled to M5."""
    idx = pd.date_range(start, periods=n_minutes, freq="1min", tz="UTC")
    cycle_len = 90
    decline_len = 80
    price = 2000.0
    rows = []
    for i in range(n_minutes):
        phase = i % cycle_len
        o = price
        if phase < decline_len:
            c = price - 0.06
        else:
            c = price + 1.2
        hi = max(o, c) + 0.05
        lo = min(o, c) - 0.05
        rows.append((o, hi, lo, c, 1.0))
        price = c
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx)
    df.index.name = "time"
    return df


def _resample(m1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    rule = f"{minutes}min"
    agg = m1.resample(rule, label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    })
    return agg.dropna(subset=["open", "high", "low", "close"])


@pytest.fixture()
def synthetic_lake(tmp_path: Path) -> Path:
    """M1 + M5 only (v2 runner is M5-only, per the brief)."""
    lake_root = tmp_path / "lake"
    start = DESDE - pd.Timedelta(days=3)
    n_minutes = 3 * 24 * 60 + 6 * 60
    m1 = _m1_series(start, n_minutes)
    write_bars(lake_root, SYMBOL, 1, m1)
    write_bars(lake_root, SYMBOL, 5, _resample(m1, 5))
    return lake_root


@pytest.fixture()
def hasta_arg() -> str:
    return (DESDE + pd.Timedelta(hours=6)).isoformat()


# ---------------------------------------------------------------------------
# 1. CONFIGS -- exact 5-key dict per the brief's table
# ---------------------------------------------------------------------------
def test_configs_has_exactly_5_keys():
    assert set(runner.CONFIGS.keys()) == EXPECTED_KEYS


def test_configs_fix1seq():
    c = runner.CONFIGS["fix1seq"]
    assert c["entry_mode"] == "sequence"
    assert c["regime_mode"] == "full5"
    assert c.get("session_hours") is None
    assert c["stop_mode"] == "fixed"
    assert c["tp_mode"] == "pattern"
    assert c["seq_timeout"] == 6


def test_configs_fix2atr():
    c = runner.CONFIGS["fix2atr"]
    assert c["entry_mode"] == "forced"
    assert c["c1_tol"] == 3.0
    assert c["regime_mode"] == "full5"
    assert c.get("session_hours") is None
    assert c["stop_mode"] == "atr"
    assert c["tp_mode"] == "pattern"
    assert c["atr_sl_mult"] == 1.5
    assert c["atr_be_mult"] == 1.0
    assert c["atr_trail_mult"] == 2.5


def test_configs_fix3r():
    c = runner.CONFIGS["fix3r"]
    assert c["entry_mode"] == "forced"
    assert c["c1_tol"] == 3.0
    assert c["regime_mode"] == "full5"
    assert c.get("session_hours") is None
    assert c["stop_mode"] == "fixed"
    assert c["tp_mode"] == "r"
    assert c["r1_mult"] == 1.0
    assert c["r2_mult"] == 2.0


def test_configs_fix4reg():
    c = runner.CONFIGS["fix4reg"]
    assert c["entry_mode"] == "forced"
    assert c["c1_tol"] == 3.0
    assert c["regime_mode"] == "simple"
    assert c["session_hours"] == (7, 17)
    assert c["stop_mode"] == "fixed"
    assert c["tp_mode"] == "pattern"
    assert c["regime_lookback"] == 3


def test_configs_fixall():
    c = runner.CONFIGS["fixall"]
    assert c["entry_mode"] == "sequence"
    assert c["regime_mode"] == "simple"
    assert c["session_hours"] == (7, 17)
    assert c["stop_mode"] == "atr"
    assert c["tp_mode"] == "r"
    assert c["seq_timeout"] == 6
    assert c["atr_sl_mult"] == 1.5
    assert c["atr_be_mult"] == 1.0
    assert c["atr_trail_mult"] == 2.5
    assert c["r1_mult"] == 1.0
    assert c["r2_mult"] == 2.0


def test_configs_common_defaults():
    """Common params (spread, ema, sar, mom, st, regime_lookback default,
    fixed stop defaults, volume, fichas) baked in via module constants, not
    per-config -- but sanity-check the shared engine constants here."""
    assert runner.SPREAD == 0.60
    assert runner.COMMISSION == 0.0
    assert runner.EMA_FAST == 5
    assert runner.EMA_SLOW == 8
    assert runner.SAR_STEP == 0.3
    assert runner.SAR_MAX == 30.0
    assert runner.MOM_PERIOD == 14
    assert runner.ST_PERIOD == 14
    assert runner.ST_MULT == 3.0
    assert runner.REGIME_LOOKBACK_DEFAULT == 3
    assert runner.INIT_SL_OFFSET == 0.60
    assert runner.BE_TRIGGER == 0.60
    assert runner.TRAIL_USD == 5.0
    assert runner.VOLUME == 0.01


# ---------------------------------------------------------------------------
# 2. run_id / variant_id suffixes
# ---------------------------------------------------------------------------
def test_run_id_and_variant_id_suffix_per_config():
    hasta = DESDE + pd.Timedelta(hours=6)
    for key in EXPECTED_KEYS:
        run_id = runner._run_id(DESDE, hasta, key)
        variant_id = runner._variant_id(key)
        assert run_id == f"sim-tk_bw2-m5-{DESDE.strftime('%Y%m%d')}-{hasta.strftime('%Y%m%d')}-{key}"
        assert variant_id == f"TK_XAUUSD_BW2_M5-{key}"


# ---------------------------------------------------------------------------
# 3. dry-run does not touch the DB
# ---------------------------------------------------------------------------
def test_dry_run_end_to_end_no_error(synthetic_lake, hasta_arg, tmp_path, capsys):
    db_path = tmp_path / "research.db"
    rc = runner.main([
        "--lake-root", str(synthetic_lake),
        "--db", str(db_path),
        "--hasta", hasta_arg,
    ])
    assert rc == 0
    out = capsys.readouterr().out
    for key in EXPECTED_KEYS:
        assert key in out
    assert "[dry-run] nothing written" in out
    assert not db_path.exists()


def test_dry_run_writes_nothing_even_with_db_path_present(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    reg = ResearchRegistry(db_path)
    before = reg.query_runs()["total"]
    runner.main([
        "--lake-root", str(synthetic_lake),
        "--db", str(db_path),
        "--hasta", hasta_arg,
    ])
    after = ResearchRegistry(db_path).query_runs()["total"]
    assert after == before == 0


# ---------------------------------------------------------------------------
# 4. --write registers 5 runs + trades, params_delta passes EmasarPolicy
# ---------------------------------------------------------------------------
def test_write_registers_strategy_variant_run_trades(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    rc = runner.main([
        "--lake-root", str(synthetic_lake),
        "--db", str(db_path),
        "--hasta", hasta_arg,
        "--write",
    ])
    assert rc == 0
    assert db_path.exists()

    reg = ResearchRegistry(db_path)
    strategies = reg.query_strategies()
    assert any(s["name"] == "tk_bw_v2" and s["familia"] == "TK" for s in strategies)

    runs = reg.query_runs()
    assert runs["total"] == 5
    seen_keys = set()
    for row in runs["rows"]:
        assert row["variant_id"].startswith("TK_XAUUSD_BW2_M5-")
        key = row["variant_id"].removeprefix("TK_XAUUSD_BW2_M5-")
        seen_keys.add(key)
        assert row["engine"] == "sentinel-sim"
        assert row["fidelity"] == "research"
        run = reg.get_run(row["run_id"])
        assert run["modelo_sim"] == f"tk_bw_v2-intrabar-m1-{key}"
    assert seen_keys == EXPECTED_KEYS


def test_familia_is_tk(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    runner.main([
        "--lake-root", str(synthetic_lake), "--db", str(db_path),
        "--hasta", hasta_arg, "--write",
    ])
    reg = ResearchRegistry(db_path)
    strategies = [s for s in reg.query_strategies() if s["name"] == "tk_bw_v2"]
    assert len(strategies) == 1
    assert strategies[0]["familia"] == "TK"


def test_engine_fidelity_satisfy_check_constraint(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    runner.main([
        "--lake-root", str(synthetic_lake), "--db", str(db_path),
        "--hasta", hasta_arg, "--write",
    ])
    reg = ResearchRegistry(db_path)
    for row in reg.query_runs()["rows"]:
        run = reg.get_run(row["run_id"])
        assert run["engine"] in (
            "sentinel-replay", "sentinel-sim", "mt5-tester", "nt8-manual", "mt5-import",
        )
        assert run["fidelity"] in (
            "research", "screening", "real-tick", "forward", "live-demo", "mt5-htm",
        )
        parsed = json.loads(run["metrics_json"])
        assert parsed["fix_matrix"] == "2026-07-22"
        assert parsed["engine_tag"] == "tk_bw_v2"
        assert "config" in parsed
        assert "coverage" in parsed


def test_emasar_policy_accepts_params_delta():
    params_delta = runner.build_params_delta()
    policy = EmasarPolicy(params_delta)  # must not raise
    assert policy.params["ema_fast"] == 5
    assert policy.params["ema_slow"] == 8


def test_write_params_delta_valid_before_write(synthetic_lake, hasta_arg, tmp_path):
    """`EmasarPolicy(params_delta)` must be validated (and not raise) as part
    of --write, before any row is persisted."""
    db_path = tmp_path / "research.db"
    rc = runner.main([
        "--lake-root", str(synthetic_lake), "--db", str(db_path),
        "--hasta", hasta_arg, "--write",
    ])
    assert rc == 0


def test_trades_have_iso_ts_signal_id_and_ficha(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    runner.main([
        "--lake-root", str(synthetic_lake), "--db", str(db_path),
        "--hasta", hasta_arg, "--write",
    ])
    reg = ResearchRegistry(db_path)
    for row in reg.query_runs()["rows"]:
        trades = reg.get_trades_for_run(row["run_id"])
        for t in trades:
            assert _is_iso_utc(t["ts_in"])
            assert _is_iso_utc(t["ts_out"])
            pd.Timestamp(t["ts_in"])
            pd.Timestamp(t["ts_out"])
            assert t["side"] in ("LONG", "SHORT")
            assert t["ficha"] in ("F1", "F2", "F3")
            assert t["signal_id"]
            assert t["exit_reason_source"] == "sentinel-sim"
            assert t["volume"] == 0.01


def test_trades_same_entry_share_signal_id(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    runner.main([
        "--lake-root", str(synthetic_lake), "--db", str(db_path),
        "--hasta", hasta_arg, "--write",
    ])
    reg = ResearchRegistry(db_path)
    for row in reg.query_runs()["rows"]:
        trades = reg.get_trades_for_run(row["run_id"])
        groups: dict[tuple[str, str], set[str]] = {}
        for t in trades:
            key = (t["ts_in"], t["side"])
            groups.setdefault(key, set()).add(t["signal_id"])
        for key, sig_ids in groups.items():
            assert len(sig_ids) == 1, f"fichas of the same entry {key} must share signal_id"


def test_trades_filtered_and_sorted(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    desde_epoch = int(DESDE.timestamp())
    hasta_epoch = int((DESDE + pd.Timedelta(hours=6)).timestamp())
    runner.main([
        "--lake-root", str(synthetic_lake), "--db", str(db_path),
        "--hasta", hasta_arg, "--write",
    ])
    reg = ResearchRegistry(db_path)
    for row in reg.query_runs()["rows"]:
        trades = reg.get_trades_for_run(row["run_id"])
        ts_ins = [int(pd.Timestamp(t["ts_in"]).timestamp()) for t in trades]
        for ts_in in ts_ins:
            assert desde_epoch <= ts_in <= hasta_epoch
        assert ts_ins == sorted(ts_ins)


# ---------------------------------------------------------------------------
# 5. reused (not reimplemented) objects from the v1 runner -- identity check
# ---------------------------------------------------------------------------
def test_reuses_v1_helpers_by_identity():
    assert runner.build_steps is runner_v1.build_steps
    assert runner.compute_metrics is runner_v1.compute_metrics
    assert runner._df_to_bars is runner_v1._df_to_bars
    assert runner.build_params_delta is runner_v1.build_params_delta
    assert runner._iso_utc is runner_v1._iso_utc
    assert runner.DESDE_DEFAULT is runner_v1.DESDE_DEFAULT
    assert runner.WARMUP_LOOKBACK is runner_v1.WARMUP_LOOKBACK


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------
def test_determinism_same_lake_same_trades(synthetic_lake, hasta_arg, tmp_path):
    db1 = tmp_path / "r1.db"
    db2 = tmp_path / "r2.db"
    runner.main(["--lake-root", str(synthetic_lake), "--db", str(db1), "--hasta", hasta_arg, "--write"])
    runner.main(["--lake-root", str(synthetic_lake), "--db", str(db2), "--hasta", hasta_arg, "--write"])

    reg1 = ResearchRegistry(db1)
    reg2 = ResearchRegistry(db2)

    def _trade_signature(reg):
        sig = []
        for row in sorted(reg.query_runs()["rows"], key=lambda r: r["variant_id"]):
            trades = reg.get_trades_for_run(row["run_id"])
            for t in trades:
                sig.append((t["ts_in"], t["ts_out"], t["px_in"], t["px_out"],
                             t["side"], t["ficha"], t["pnl"], t["exit_reason"]))
        return sig

    assert _trade_signature(reg1) == _trade_signature(reg2)


# ---------------------------------------------------------------------------
# module invocation convention
# ---------------------------------------------------------------------------
def test_module_invocable_as_dash_m(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.research.run_tk_bw_v2_backtest",
         "--lake-root", str(synthetic_lake), "--db", str(db_path), "--hasta", hasta_arg],
        cwd=str(runner._REPO_ROOT),
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "[dry-run] nothing written" in proc.stdout


# ---------------------------------------------------------------------------
# --configs CLI filter
# ---------------------------------------------------------------------------
def test_configs_cli_filter_subset(synthetic_lake, hasta_arg, tmp_path, capsys):
    db_path = tmp_path / "research.db"
    rc = runner.main([
        "--lake-root", str(synthetic_lake), "--db", str(db_path),
        "--hasta", hasta_arg, "--configs", "fix1seq,fix3r",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "fix1seq" in out
    assert "fix3r" in out
    assert "fix2atr" not in out
    assert "fix4reg" not in out
    assert "fixall" not in out


def test_configs_cli_filter_write_subset(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    rc = runner.main([
        "--lake-root", str(synthetic_lake), "--db", str(db_path),
        "--hasta", hasta_arg, "--write", "--configs", "fix2atr",
    ])
    assert rc == 0
    reg = ResearchRegistry(db_path)
    runs = reg.query_runs()
    assert runs["total"] == 1
    assert runs["rows"][0]["variant_id"] == "TK_XAUUSD_BW2_M5-fix2atr"
