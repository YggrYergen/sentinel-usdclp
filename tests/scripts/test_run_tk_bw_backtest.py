"""tests/scripts/test_run_tk_bw_backtest.py -- focused integration tests for
`scripts/research/run_tk_bw_backtest.py` (Task 2,
docs/superpowers/plans/2026-07-21-tk-bw-backtest.md).

Builds a tiny synthetic XAUUSD lake (M1/M2/M5/M15 parquet, tz-aware UTC,
written via the SAME `sentinel_engine.lake.store.write_bars` the real
ingesters use) in `tmp_path`, plus a temp `research.db`. NEVER touches the
real lake or `data/research.db`.

Covers (per the plan's Task 2 "Tests"):
- end-to-end run (dry-run) over the synthetic lake, no error, prints coverage.
- `--dry-run` (default) writes NOTHING to the registry.
- `--write` registers strategy/variant/run/trades; `query_runs` /
  `get_trades_for_run` return them.
- `run.engine`/`run.fidelity` satisfy the registry's CHECK constraints.
- `EmasarPolicy(params_delta)` does not raise.
- trades carry ISO-8601 UTC ts strings + `signal_id` + `ficha`.
- determinism: two `--write` runs (fresh dbs) produce the same trade list.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts.research import run_tk_bw_backtest as runner
from sentinel_engine.lake.store import write_bars
from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.strategies.emasar import EmasarPolicy

SYMBOL = "XAUUSD"
DESDE = pd.Timestamp("2026-07-20T00:00:00Z")


def _is_iso_utc(s: str) -> bool:
    """True if `s` is an unambiguous ISO-8601 UTC string -- either `...Z` or
    carrying an explicit `+00:00` offset (both forms round-trip through
    `pd.Timestamp` and are accepted as-is by the registry's own
    `_normalize_ts_iso_utc`, which never mangles a string that already
    carries an explicit offset)."""
    return isinstance(s, str) and (s.endswith("Z") or s.endswith("+00:00"))


def _m1_series(start: pd.Timestamp, n_minutes: int) -> pd.DataFrame:
    """Deterministic M1 OHLCV series: repeating "mild decline then sharp
    spike-up" cycles (same shape as tests/strategies/test_tk_bw.py's verified
    natural-LONG-entry fixture: a lagging EMA8 + a reset-at-the-flip
    SAR(0.3,30) below it + a breakout pullback candle), replayed on a loop so
    the TK-BW engine gets many chances to fire a LONG entry once resampled to
    native TFs across M15/M5/M2. Fully deterministic (no RNG)."""
    idx = pd.date_range(start, periods=n_minutes, freq="1min", tz="UTC")
    cycle_len = 90  # minutes: ~80 declining + ~10 spike-up, per cycle
    decline_len = 80
    price = 2000.0
    rows = []
    for i in range(n_minutes):
        phase = i % cycle_len
        o = price
        if phase < decline_len:
            c = price - 0.06
        else:
            c = price + 1.2  # sharp spike-up leg, resets SAR near the flip
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
    """Write a synthetic XAUUSD lake (M1/M2/M5/M15) under tmp_path: warmup
    from 2 days before DESDE through ~6 hours after DESDE (M1-granular)."""
    lake_root = tmp_path / "lake"
    start = DESDE - pd.Timedelta(days=3)  # extra headroom over WARMUP_LOOKBACK
    n_minutes = 3 * 24 * 60 + 6 * 60  # 3 warmup days + 6h of "today" window
    m1 = _m1_series(start, n_minutes)
    write_bars(lake_root, SYMBOL, 1, m1)
    for tf in (2, 5, 15):
        write_bars(lake_root, SYMBOL, tf, _resample(m1, tf))
    return lake_root


@pytest.fixture()
def hasta_arg() -> str:
    return (DESDE + pd.Timedelta(hours=6)).isoformat()


# ---------------------------------------------------------------------------
# smoke / dry-run
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
    for tf in runner.TFS:
        assert f"[{tf}]" in out
    assert "[dry-run] nothing written" in out
    # dry-run must not even create the db file.
    assert not db_path.exists()


def test_dry_run_writes_nothing_even_with_db_path_present(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    # Pre-create an empty registry so we can prove row counts stay at zero.
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
# --write: registration
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
    assert any(s["name"] == "tk_bw" and s["familia"] == "TK" for s in strategies)

    runs = reg.query_runs()
    assert runs["total"] == 3  # M15, M5, M2
    seen_tfs = set()
    for row in runs["rows"]:
        assert row["variant_id"].startswith("TK_XAUUSD_BW_")
        seen_tfs.add(row["variant_id"].removeprefix("TK_XAUUSD_BW_"))
        assert row["engine"] == "sentinel-sim"
        assert row["fidelity"] == "research"
    assert seen_tfs == set(runner.TFS)


def test_familia_not_supertrend(synthetic_lake, hasta_arg, tmp_path):
    """familia MUST NOT be 'supertrend' so the UI overlay draws EMA/SAR/ST/AO/AC/MOM."""
    db_path = tmp_path / "research.db"
    runner.main([
        "--lake-root", str(synthetic_lake), "--db", str(db_path),
        "--hasta", hasta_arg, "--write",
    ])
    reg = ResearchRegistry(db_path)
    strategies = [s for s in reg.query_strategies() if s["name"] == "tk_bw"]
    assert len(strategies) == 1
    assert strategies[0]["familia"] != "supertrend"


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
        assert run["metrics_json"] is not None
        parsed = json.loads(run["metrics_json"])
        assert parsed["engine_tag"] == "tk_bw"


def test_emasar_policy_accepts_params_delta():
    params_delta = runner.build_params_delta()
    policy = EmasarPolicy(params_delta)  # must not raise
    assert policy.params["ema_fast"] == 5
    assert policy.params["ema_slow"] == 8
    assert policy.params["sar_step"] == 0.3
    assert policy.params["sar_max"] == 30.0
    assert policy.params["st_atr_period"] == 14
    assert policy.params["st_mult"] == 3.0
    assert policy.params["mom_period"] == 14


def _synthetic_tk_bw_trades(ts_in: int) -> list[dict]:
    """Hand-built trades in the EXACT shape `tk_bw_run` emits (see
    sentinel_engine/strategies/tk_bw.py `_trade_dict`): one signal (3 fichas,
    same ts_in+side) plus a second, later, unrelated signal -- used to test
    `register_tf`'s persistence/shape logic directly, independent of whether
    the TK-BW engine's 5-condition entry naturally fires on any given
    synthetic-lake fixture (empirically validated instead on real data, per
    the plan)."""
    return [
        {"ts_in": ts_in, "ts_out": ts_in + 900, "px_in": 2000.60, "px_out": 2001.20,
         "side": "LONG", "ficha": "F1", "volume": 0.01, "sl": 1999.50,
         "exit_reason": "TP1", "pnl": 0.60, "mae": -0.10, "mfe": 0.65},
        {"ts_in": ts_in, "ts_out": ts_in + 1800, "px_in": 2000.60, "px_out": 2002.00,
         "side": "LONG", "ficha": "F2", "volume": 0.01, "sl": 1999.50,
         "exit_reason": "TP2", "pnl": 1.40, "mae": -0.10, "mfe": 1.45},
        {"ts_in": ts_in, "ts_out": ts_in + 2700, "px_in": 2000.60, "px_out": 1999.50,
         "side": "LONG", "ficha": "F3", "volume": 0.01, "sl": 1999.50,
         "exit_reason": "SL_INIT", "pnl": -1.10, "mae": -1.10, "mfe": 1.90},
        {"ts_in": ts_in + 5400, "ts_out": ts_in + 6300, "px_in": 2003.00, "px_out": 2003.60 + 0.60,
         "side": "SHORT", "ficha": "F1", "volume": 0.01, "sl": 2004.20,
         "exit_reason": "TP1", "pnl": -0.60, "mae": -0.65, "mfe": 0.10},
    ]


def test_register_tf_trade_shape_iso_ts_signal_id_ficha(tmp_path):
    """Direct unit test of `register_tf` (bypasses the engine/lake): builds
    trades in the exact `tk_bw_run` shape and verifies the registered rows
    carry ISO-8601 UTC ts strings, a `signal_id` shared by the 3 fichas of
    the same entry, correct `ficha`/`side`/`exit_reason_source`/`volume`."""
    db_path = tmp_path / "research.db"
    reg = ResearchRegistry(db_path)
    ts_in = int(pd.Timestamp("2026-07-20T10:00:00Z").timestamp())

    result = runner.TfResult("M15")
    result.desde = DESDE
    result.hasta = DESDE + pd.Timedelta(hours=6)
    result.coverage_first = DESDE - pd.Timedelta(days=1)
    result.coverage_last = result.hasta
    result.trades = _synthetic_tk_bw_trades(ts_in)
    result.metrics = runner.compute_metrics(result.trades)

    run_id = runner.register_tf(reg, result, runner.build_params_delta(), tmp_path / "lake")
    trades = reg.get_trades_for_run(run_id)
    assert len(trades) == 4

    for t in trades:
        assert _is_iso_utc(t["ts_in"])
        assert _is_iso_utc(t["ts_out"])
        pd.Timestamp(t["ts_in"])  # round-trips without error
        pd.Timestamp(t["ts_out"])
        assert t["side"] in ("LONG", "SHORT")
        assert t["ficha"] in ("F1", "F2", "F3")
        assert t["signal_id"]
        assert t["exit_reason_source"] == "sentinel-sim"
        assert t["volume"] == 0.01

    # the 3 fichas of the LONG entry (same ts_in+side) share one signal_id;
    # the later unrelated SHORT entry gets a DIFFERENT signal_id.
    long_sig_ids = {t["signal_id"] for t in trades if t["side"] == "LONG"}
    short_sig_ids = {t["signal_id"] for t in trades if t["side"] == "SHORT"}
    assert len(long_sig_ids) == 1
    assert len(short_sig_ids) == 1
    assert long_sig_ids != short_sig_ids


def test_trades_have_iso_ts_signal_id_and_ficha(synthetic_lake, hasta_arg, tmp_path):
    """End-to-end over the synthetic lake: whatever trades (>=0, per the
    plan) the engine naturally produces must still carry the right shape.
    Entry correctness itself is validated empirically on real data via the
    runner + Trade View (plan Task 2), not hunted for here."""
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
# module invocation convention: `python -m scripts.research.run_tk_bw_backtest`
# ---------------------------------------------------------------------------
def test_module_invocable_as_dash_m(synthetic_lake, hasta_arg, tmp_path):
    db_path = tmp_path / "research.db"
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.research.run_tk_bw_backtest",
         "--lake-root", str(synthetic_lake), "--db", str(db_path), "--hasta", hasta_arg],
        cwd=str(runner._REPO_ROOT),
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "[dry-run] nothing written" in proc.stdout
