"""Tests for sentinel_engine.opt.evaluator (P4 wiring layer).

Builds a hermetic tmp Parquet lake (ingested from the REAL, short MT5
fixtures under tests/golden/fixtures/csv/) and drives evaluate_config /
make_objective_fn against it. This proves WIRING (Engine <-> feed <->
labels <-> objective), NOT a passing optimization study -- the fixtures are
only ~250 M1 bars, far too short for `gates_passed=True`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from sentinel_engine.config import load_instrument
from sentinel_engine.lake.ingest_mt5 import ingest_mt5_csv
from sentinel_engine.opt.evaluator import (
    _ReplayFeed,
    _replay_entries,
    _target_m1_frame,
    evaluate_config,
    make_objective_fn,
)

FIXTURES_CSV_ROOT = Path(__file__).resolve().parents[2] / "tests" / "golden" / "fixtures" / "csv"

# gold's target + full macro basket (see sentinel_engine/instruments/gold.yaml)
_TARGET = "XAUUSD"
_TARGET_TIMEFRAMES = [1, 2, 5, 15, 1440]
_MACRO_SYMBOLS = ["USDX_Jun26", "XAGUSD", "VIX_Jun26", "EURUSD", "SP", "USDJPY", "Cobre_Jul26"]

WINDOW_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 1, 1, 4, 9, 0, tzinfo=timezone.utc)

HORIZON = 5
TP_R = 1.5
SL = 5.0


@pytest.fixture()
def lake_root(tmp_path) -> Path:
    root = tmp_path / "lake"
    for tf in _TARGET_TIMEFRAMES:
        csv_path = FIXTURES_CSV_ROOT / _TARGET / f"{tf}.csv"
        ingest_mt5_csv(csv_path, _TARGET, tf, root, update_manifest=False)
    for symbol in _MACRO_SYMBOLS:
        csv_path = FIXTURES_CSV_ROOT / symbol / "1.csv"
        ingest_mt5_csv(csv_path, symbol, 1, root, update_manifest=False)
    return root


@pytest.fixture()
def gold_cfg():
    return load_instrument("gold")


def _evaluate(cfg, lake_root, params=None, **overrides):
    kwargs = dict(horizon=HORIZON, tp_r=TP_R, sl=SL)
    kwargs.update(overrides)
    return evaluate_config(
        cfg,
        params or {},
        lake_root,
        WINDOW_START,
        WINDOW_END,
        cfg.symbols,
        **kwargs,
    )


# ── core wiring ──────────────────────────────────────────────────────────

def test_evaluate_config_returns_objective_result_with_score_and_metrics(gold_cfg, lake_root):
    result = _evaluate(gold_cfg, lake_root)
    assert isinstance(result.score, float)
    assert isinstance(result.metrics, dict)
    assert "n_trades" in result.metrics
    assert "net_pnl_R" in result.metrics
    assert "n_ref" in result.metrics
    assert result.metrics["n_ref"] >= 0


def test_make_objective_fn_returns_plain_callable(gold_cfg, lake_root):
    fn = make_objective_fn(
        gold_cfg, lake_root, (WINDOW_START, WINDOW_END), gold_cfg.symbols,
        horizon=HORIZON, tp_r=TP_R, sl=SL,
    )
    score = fn({})
    assert isinstance(score, float)


# ── determinism ──────────────────────────────────────────────────────────

def test_determinism_identical_calls_yield_identical_score_and_metrics(gold_cfg, lake_root):
    r1 = _evaluate(gold_cfg, lake_root)
    r2 = _evaluate(gold_cfg, lake_root)
    assert r1.score == r2.score
    assert r1.metrics == r2.metrics


def test_determinism_identical_calls_yield_identical_trades_R(gold_cfg, lake_root):
    m1 = _target_m1_frame(lake_root, gold_cfg.target, pd.Timestamp(WINDOW_END))
    price_index = {ts: i for i, ts in enumerate(m1.index)}

    entries1 = _replay_entries(
        gold_cfg, lake_root, gold_cfg.symbols,
        pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), price_index,
    )
    entries2 = _replay_entries(
        gold_cfg, lake_root, gold_cfg.symbols,
        pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), price_index,
    )
    assert entries1 == entries2


# ── monotonic sanity ─────────────────────────────────────────────────────

def test_higher_alert_threshold_yields_fewer_or_equal_trades(gold_cfg, lake_root):
    baseline = _evaluate(gold_cfg, lake_root)
    strict = _evaluate(gold_cfg, lake_root, params={"composite.score_alert_threshold": 99.0})
    assert strict.metrics["n_trades"] <= baseline.metrics["n_trades"]


# ── leakage ──────────────────────────────────────────────────────────────

def test_no_entry_timestamp_exceeds_window_end(gold_cfg, lake_root):
    m1 = _target_m1_frame(lake_root, gold_cfg.target, pd.Timestamp(WINDOW_END))
    price_index = {ts: i for i, ts in enumerate(m1.index)}
    entries = _replay_entries(
        gold_cfg, lake_root, gold_cfg.symbols,
        pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), price_index,
    )
    assert len(entries) >= 0  # sanity: doesn't crash even if 0 entries fire
    for entry in entries:
        assert entry.ts <= pd.Timestamp(WINDOW_END)


def test_replay_feed_never_returns_rows_past_as_of(lake_root):
    as_of = datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone.utc)
    feed = _ReplayFeed(lake_root, {"target": _TARGET}, as_of=as_of)

    df = feed.get_data(_TARGET, timeframe_minutes=1, bars=500)
    assert not df.empty
    assert (df.index <= pd.Timestamp(as_of)).all()

    all_data = feed.get_all_data(timeframe_minutes=1, bars=500)
    for df in all_data.values():
        assert (df.index <= pd.Timestamp(as_of)).all()

    # advance forward and re-check the gate holds at the new as_of too
    later = datetime(2026, 1, 1, 3, 30, 0, tzinfo=timezone.utc)
    feed.advance(later)
    df2 = feed.get_data(_TARGET, timeframe_minutes=1, bars=500)
    assert (df2.index <= pd.Timestamp(later)).all()
    assert (df2.index > pd.Timestamp(as_of)).any()  # actually advanced


def test_replay_feed_advance_requires_tz_aware():
    feed = _ReplayFeed(Path("."), {}, as_of=datetime(2026, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError):
        feed.advance(datetime(2026, 1, 1))  # naive -- must raise


def test_evaluate_config_requires_tz_aware_window(gold_cfg, lake_root):
    with pytest.raises(ValueError):
        evaluate_config(
            gold_cfg, {}, lake_root,
            datetime(2026, 1, 1), datetime(2026, 1, 1, 4, 9),  # naive
            gold_cfg.symbols, horizon=HORIZON, tp_r=TP_R, sl=SL,
        )
