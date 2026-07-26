"""tests/analysis/test_monday_audit.py -- Track-A audit maths on tiny synthetic
fixtures. The real 2 347-row run is a script invocation, not a test."""
from __future__ import annotations

from pathlib import Path

from scripts.analysis.monday_audit.loader import Position, load_positions

_HEADER = ("side,ficha,reason,t_in,t_out,entry_fill,exit_fill,spread,"
           "entry_delay_bars,net_067lot_clp,month\n")


def _fixture(tmp_path: Path) -> Path:
    (tmp_path / "positions_S6-K2P0.csv").write_text(
        _HEADER
        + "LONG,F1,EXIT_INITSL,2026-01-05T20:00:00,2026-01-05T23:47:08,4450.98,4458.94,0.5,0,499454.18,2026-01\n"
        + "SHORT,F2,EXIT_TRAIL,2026-01-06T10:00:00,2026-01-06T12:00:00,4460.00,4455.00,0.6,1,-120000.00,2026-01\n",
        encoding="utf-8")
    (tmp_path / "positions_S7-TPNONE.csv").write_text(
        _HEADER
        + "LONG,F1,EXIT_INITSL,2026-01-05T21:00:00,2026-01-06T01:00:00,4451.00,4449.00,0.5,0,-80000.00,2026-01\n",
        encoding="utf-8")
    (tmp_path / "positions_SuperTrend-p14x3-M15.csv").write_text(_HEADER, encoding="utf-8")
    return tmp_path


def test_loader_merges_all_three_files_and_tags_the_strategy(tmp_path):
    rows = load_positions(_fixture(tmp_path))
    assert len(rows) == 3
    assert {r.strategy for r in rows} == {"S6-K2P0", "S7-TPNONE"}
    assert all(isinstance(r, Position) for r in rows)


def test_loader_sorts_chronologically_by_entry(tmp_path):
    rows = load_positions(_fixture(tmp_path))
    assert [r.t_in.isoformat() for r in rows] == sorted(r.t_in.isoformat() for r in rows)


def test_loader_types_every_field(tmp_path):
    r = load_positions(_fixture(tmp_path))[0]
    assert r.side == "LONG" and r.ficha == "F1" and r.reason == "EXIT_INITSL"
    assert r.spread == 0.5 and r.entry_delay_bars == 0
    assert abs(r.net_067lot_clp - 499454.18) < 1e-6
    assert r.month == "2026-01"
    assert r.t_out > r.t_in


def test_loader_scales_net_to_an_arbitrary_lot(tmp_path):
    r = load_positions(_fixture(tmp_path))[0]
    assert abs(r.net_at_lot(0.1) - 499454.18 * (0.1 / 0.67)) < 1e-6
    assert abs(r.net_at_lot(0.67) - r.net_067lot_clp) < 1e-9


from datetime import datetime

from scripts.analysis.monday_audit.a2_overlap import max_concurrency, pearson


def _iv(a, b):
    return (datetime.fromisoformat(a), datetime.fromisoformat(b))


def test_max_concurrency_counts_overlapping_intervals():
    ivs = [_iv("2026-01-01T00:00", "2026-01-01T03:00"),
           _iv("2026-01-01T01:00", "2026-01-01T02:00"),
           _iv("2026-01-01T01:30", "2026-01-01T04:00")]
    peak, hist = max_concurrency(ivs)
    assert peak == 3
    assert hist[3] >= 1


def test_concurrency_treats_a_touching_pair_as_sequential():
    # exits are processed BEFORE entries at the same timestamp
    ivs = [_iv("2026-01-01T00:00", "2026-01-01T01:00"),
           _iv("2026-01-01T01:00", "2026-01-01T02:00")]
    peak, _hist = max_concurrency(ivs)
    assert peak == 1


def test_max_concurrency_of_nothing_is_zero():
    assert max_concurrency([])[0] == 0


def test_pearson_matches_known_values():
    assert abs(pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) - 1.0) < 1e-9
    assert abs(pearson([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) + 1.0) < 1e-9
    assert pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) == 0.0  # zero variance


from scripts.analysis.monday_audit.a1_maxdd import max_drawdown


def test_max_drawdown_finds_the_deepest_peak_to_trough():
    # equity: 0 -> 100 -> 60 -> 160 -> 10   (deepest drop is 160 -> 10 = 150)
    deltas = [100.0, -40.0, 100.0, -150.0]
    dd = max_drawdown(deltas)
    assert dd.max_dd == 150.0
    assert dd.peak_equity == 160.0
    assert dd.trough_equity == 10.0
    assert dd.peak_index == 2 and dd.trough_index == 3


def test_max_drawdown_of_a_monotonic_curve_is_zero():
    assert max_drawdown([10.0, 20.0, 5.0]).max_dd == 0.0


def test_max_drawdown_of_an_empty_series_is_zero():
    assert max_drawdown([]).max_dd == 0.0


from scripts.analysis.monday_audit.a3_a4_a5_stats import (
    autocorrelation, longest_streak, profit_factor, win_rate)


def test_win_rate_counts_strictly_positive_results():
    assert win_rate([1.0, -1.0, 0.0, 2.0]) == 50.0
    assert win_rate([]) == 0.0


def test_profit_factor_is_gross_win_over_gross_loss():
    assert profit_factor([3.0, -1.0, -0.5]) == 2.0
    assert profit_factor([1.0, 2.0]) == float("inf")   # no losses
    assert profit_factor([]) == 0.0


def test_autocorrelation_of_an_alternating_series_is_negative():
    assert autocorrelation([1.0, -1.0, 1.0, -1.0, 1.0], lag=1) < -0.9


def test_autocorrelation_with_too_few_points_is_zero():
    assert autocorrelation([1.0], lag=1) == 0.0


def test_longest_streak_finds_both_directions():
    assert longest_streak([1.0, 1.0, 1.0, -1.0]) == (3, 1)
    assert longest_streak([-1.0, -1.0, 2.0]) == (1, 2)
    assert longest_streak([]) == (0, 0)
