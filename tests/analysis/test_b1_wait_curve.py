"""Tests for scripts/analysis/monday_audit/b1_wait_curve.py -- the B1
wait-N-M15-bars screening curve.

This is a DISTINCT experiment from the B1 mask verdicts (pre-committed at 50
minutes). Searching for an elbow here is tuning, and the module/report say so
explicitly. N=1 (15 minutes) is excluded from the grid per user instruction;
the grid is N=2..6 M15 bars (30/45/60/75/90 minutes)."""
from __future__ import annotations

import datetime as dt

import pytest

from scripts.analysis.monday_audit.b1_wait_curve import (
    RUNGS, bars_since_reopen, is_blocked, wait_curve)
from scripts.analysis.monday_audit.loader import Position


def _pos(strategy, t_in, net, *, side="LONG", ficha="F1", reason="EXIT_INITSL",
          t_out=None, entry_fill=100.0, exit_fill=101.0, spread=0.5,
          entry_delay_bars=0, month="2026-01"):
    return Position(
        strategy=strategy, side=side, ficha=ficha, reason=reason,
        t_in=t_in, t_out=t_out or (t_in + dt.timedelta(hours=1)),
        entry_fill=entry_fill, exit_fill=exit_fill, spread=spread,
        entry_delay_bars=entry_delay_bars, net_067lot_clp=net, month=month,
    )


# --------------------------- bars_since_reopen ---------------------------
def test_bars_since_reopen_is_exact_for_15min_multiples():
    reopen = dt.datetime(2026, 1, 5, 18, 0)
    reopens = [reopen]
    assert bars_since_reopen(reopen + dt.timedelta(minutes=15), reopens) == 1
    assert bars_since_reopen(reopen + dt.timedelta(minutes=30), reopens) == 2
    assert bars_since_reopen(reopen + dt.timedelta(minutes=90), reopens) == 6


def test_bars_since_reopen_at_the_reopen_itself_is_zero():
    reopen = dt.datetime(2026, 1, 5, 18, 0)
    assert bars_since_reopen(reopen, [reopen]) == 0


def test_bars_since_reopen_none_before_the_first_reopen():
    reopen = dt.datetime(2026, 1, 5, 18, 0)
    before = reopen - dt.timedelta(minutes=15)
    assert bars_since_reopen(before, [reopen]) is None


# --------------------------- is_blocked ---------------------------
def test_is_blocked_when_bars_below_n():
    assert is_blocked(1, 2) is True
    assert is_blocked(0, 2) is True


def test_is_blocked_false_when_bars_at_or_above_n():
    assert is_blocked(2, 2) is False
    assert is_blocked(3, 2) is False


def test_is_blocked_never_blocks_unclassified_positions():
    # bars is None -> nothing to gate against, so never blocked.
    assert is_blocked(None, 6) is False


def test_grid_excludes_n1_and_covers_2_through_6():
    assert RUNGS == [2, 3, 4, 5, 6]


# --------------------------- wait_curve (synthetic) ---------------------------
def test_wait_curve_blocks_the_expected_set_at_each_rung():
    """One reopen at 18:00. Entries at +15,+30,+45,+60,+75,+90 min, one per
    strategy-agnostic slot, net = +100 each so we can read off kept/blocked by
    counting. A 30-min wait (N=2) blocks only +15; a 90-min wait (N=6) blocks
    everything except +90 -- this is the collapsing-grid behaviour described in
    the task brief (a 50 and 60 minute wait are the same experiment)."""
    reopen = dt.datetime(2026, 1, 5, 18, 0)
    reopens = [reopen]
    offsets = [15, 30, 45, 60, 75, 90]
    rows = [
        _pos("S6-K2P0", reopen + dt.timedelta(minutes=m), 100.0, ficha=f"F{m}")
        for m in offsets
    ]

    curve = wait_curve(rows, reopens)

    baseline = curve["baseline"]["COMBINED"]
    assert baseline["n_kept"] == 6
    assert baseline["n_blocked"] == 0
    assert baseline["net_clp"] == 600.0

    n2 = curve["N2"]["COMBINED"]  # 30-min wait: blocks {+15}
    assert n2["n_blocked"] == 1
    assert n2["n_kept"] == 5
    assert n2["net_clp"] == 500.0

    n4 = curve["N4"]["COMBINED"]  # 60-min wait: blocks {+15,+30,+45}
    assert n4["n_blocked"] == 3
    assert n4["n_kept"] == 3
    assert n4["net_clp"] == 300.0

    n6 = curve["N6"]["COMBINED"]  # 90-min wait: blocks {+15,+30,+45,+60,+75}
    assert n6["n_blocked"] == 5
    assert n6["n_kept"] == 1
    assert n6["net_clp"] == 100.0


def test_wait_curve_reports_delta_vs_baseline():
    reopen = dt.datetime(2026, 1, 5, 18, 0)
    reopens = [reopen]
    rows = [
        _pos("S6-K2P0", reopen + dt.timedelta(minutes=15), -50.0, ficha="F15"),
        _pos("S6-K2P0", reopen + dt.timedelta(minutes=30), 200.0, ficha="F30"),
    ]
    curve = wait_curve(rows, reopens)
    base_net = curve["baseline"]["COMBINED"]["net_clp"]
    assert base_net == 150.0
    n2 = curve["N2"]["COMBINED"]  # blocks the -50 entry at +15
    assert n2["net_clp"] == 200.0
    assert n2["delta_clp"] == pytest.approx(50.0)
    assert n2["delta_pct"] == pytest.approx(100.0 * 50.0 / 150.0)


def test_wait_curve_breaks_down_per_strategy():
    reopen = dt.datetime(2026, 1, 5, 18, 0)
    reopens = [reopen]
    rows = [
        _pos("S6-K2P0", reopen + dt.timedelta(minutes=15), 10.0, ficha="A"),
        _pos("S7-TPNONE", reopen + dt.timedelta(minutes=15), 20.0, ficha="B"),
        _pos("SuperTrend-p14x3-M15", reopen + dt.timedelta(minutes=45), 30.0, ficha="C"),
    ]
    curve = wait_curve(rows, reopens)
    assert set(curve["baseline"]) == {
        "S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15", "COMBINED"}
    assert curve["baseline"]["S6-K2P0"]["n_kept"] == 1
    assert curve["baseline"]["S7-TPNONE"]["n_kept"] == 1
    assert curve["baseline"]["SuperTrend-p14x3-M15"]["n_kept"] == 1
    # N3 (45-min wait) blocks minutes<45 -- the two +15 entries, but not the
    # +45 one (45 is not < 45).
    n3 = curve["N3"]
    assert n3["S6-K2P0"]["n_blocked"] == 1
    assert n3["S7-TPNONE"]["n_blocked"] == 1
    assert n3["SuperTrend-p14x3-M15"]["n_blocked"] == 0


def test_wait_curve_win_rate_and_profit_factor_present():
    reopen = dt.datetime(2026, 1, 5, 18, 0)
    reopens = [reopen]
    rows = [
        _pos("S6-K2P0", reopen + dt.timedelta(minutes=30), 100.0, ficha="A"),
        _pos("S6-K2P0", reopen + dt.timedelta(minutes=45), -40.0, ficha="B"),
    ]
    curve = wait_curve(rows, reopens)
    combined = curve["baseline"]["COMBINED"]
    assert combined["win_rate"] == pytest.approx(50.0)
    assert combined["profit_factor"] == pytest.approx(100.0 / 40.0)
