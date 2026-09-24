"""Tests for scripts/analysis/monday_audit/b1_robustness.py -- the three
robustness checks that decide whether the B1 wait-curve's +32.67% at N3
(commit c402976, docs/superpowers/research/2026-07-27-b1-wait-curve.md) is a
real selection effect or a handful of large trades landing on one side of
the gate.

M1 = sign consistency month-by-month.
M2 = sensitivity to removing the K largest |net| trades (global and
     per-strategy).
M3 = distribution profile of blocked vs. kept trades ("selects or shuffles").

All three reuse `is_blocked`/`bars_since_reopen` from b1_wait_curve.py so the
definition of "blocked" is identical to Task 16's -- never redefined here.
This module is report-only: no test in this file asserts a verdict on which
N to deploy."""
from __future__ import annotations

import datetime as dt

import pytest

from scripts.analysis.monday_audit.b1_robustness import (
    blocked_vs_kept, percentile, sign_consistency, topk_sensitivity,
    trim_top_k_by_group, trim_top_k_global)
from scripts.analysis.monday_audit.b1_wait_curve import bars_since_reopen, is_blocked
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


REOPEN = dt.datetime(2026, 1, 5, 18, 0)


# --------------------------- M1: sign_consistency ---------------------------
def test_sign_consistency_groups_by_month_field_not_derived_from_t_in():
    """month is an opaque label on the Position -- grouping must use it
    verbatim, not re-derive a month from t_in (which could disagree)."""
    reopens = [REOPEN]
    rows = [
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=30), 100.0, ficha="A",
             month="WEIRD-LABEL"),
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=45), 50.0, ficha="B",
             month="WEIRD-LABEL"),
    ]
    out = sign_consistency(rows, reopens, rungs=[2])
    months = [m["month"] for m in out["COMBINED"]["N2"]["months"]]
    assert months == ["WEIRD-LABEL"]
    assert out["COMBINED"]["N2"]["n_months_total"] == 1


def test_sign_consistency_counts_signs_correctly():
    reopens = [REOPEN]
    rows = [
        # Jan: N2 (30-min wait) blocks the +15 entry (-50), net improves -> positive month
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=15), -50.0, ficha="J1", month="2026-01"),
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=30), 10.0, ficha="J2", month="2026-01"),
        # Feb: N2 blocks the +15 entry (+50, a WIN) -> net worsens -> negative month
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=15), 50.0, ficha="F1", month="2026-02"),
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=30), 10.0, ficha="F2", month="2026-02"),
        # Mar: nothing lands inside the wait window -> delta exactly zero
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=30), 10.0, ficha="M1", month="2026-03"),
    ]
    out = sign_consistency(rows, reopens, rungs=[2])
    n2 = out["COMBINED"]["N2"]
    assert n2["n_months_positive"] == 1
    assert n2["n_months_negative"] == 1
    assert n2["n_months_zero"] == 1
    assert n2["n_months_total"] == 3


def test_sign_consistency_delta_matches_is_blocked_definition():
    """Cross-check: the per-month delta reported here must equal
    -sum(net of positions where is_blocked(bars_since_reopen(t_in, reopens), n)),
    i.e. exactly what Task 16's is_blocked would flag -- never a re-derived
    definition."""
    reopens = [REOPEN]
    rows = [
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=15), -30.0, ficha="A", month="2026-01"),
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=45), 20.0, ficha="B", month="2026-01"),
    ]
    out = sign_consistency(rows, reopens, rungs=[2])
    month_row = out["COMBINED"]["N2"]["months"][0]
    blocked_net = sum(
        p.net_067lot_clp for p in rows
        if is_blocked(bars_since_reopen(p.t_in, reopens), 2))
    assert month_row["delta_clp"] == pytest.approx(-blocked_net)
    assert month_row["n_blocked"] == 1


# --------------------------- M2: top-K trim ---------------------------
def test_trim_top_k_global_removes_exactly_k():
    rows = [_pos("S6-K2P0", REOPEN, v, ficha=f"F{i}") for i, v in
            enumerate([10.0, -200.0, 30.0, -5.0, 90.0])]
    remaining, removed = trim_top_k_global(rows, 2)
    assert len(removed) == 2
    assert len(remaining) == 3
    assert len(remaining) + len(removed) == len(rows)


def test_trim_top_k_global_removes_the_largest_abs_net():
    rows = [_pos("S6-K2P0", REOPEN, v, ficha=f"F{i}") for i, v in
            enumerate([10.0, -200.0, 30.0, -5.0, 90.0])]
    _, removed = trim_top_k_global(rows, 2)
    removed_nets = sorted(p.net_067lot_clp for p in removed)
    assert removed_nets == [-200.0, 90.0]


def test_trim_top_k_by_group_removes_k_per_strategy_independently():
    rows = [
        _pos("S6-K2P0", REOPEN, 500.0, ficha="A"),
        _pos("S6-K2P0", REOPEN, 1.0, ficha="B"),
        _pos("S7-TPNONE", REOPEN, -400.0, ficha="C"),
        _pos("S7-TPNONE", REOPEN, 2.0, ficha="D"),
    ]
    remaining, removed = trim_top_k_by_group(rows, 1)
    assert len(removed) == 2  # 1 per strategy, 2 strategies present
    removed_fichas = {p.ficha for p in removed}
    assert removed_fichas == {"A", "C"}
    remaining_fichas = {p.ficha for p in remaining}
    assert remaining_fichas == {"B", "D"}


def test_trim_determinism_on_tied_abs_net():
    """Two positions tie on |net|=100. The tie-break is (t_in, strategy,
    ficha) ascending, so the earlier t_in is removed first at K=1."""
    earlier = REOPEN
    later = REOPEN + dt.timedelta(minutes=30)
    rows = [
        _pos("S6-K2P0", later, -100.0, ficha="LATE"),
        _pos("S6-K2P0", earlier, 100.0, ficha="EARLY"),
    ]
    _, removed = trim_top_k_global(rows, 1)
    assert len(removed) == 1
    assert removed[0].ficha == "EARLY"

    # Re-running must reproduce the exact same choice (no set/dict-order
    # nondeterminism sneaking in).
    _, removed_again = trim_top_k_global(rows, 1)
    assert removed_again[0].ficha == "EARLY"


def test_topk_sensitivity_reports_global_and_by_group_for_each_k():
    reopens = [REOPEN]
    rows = [
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=15), -50.0, ficha="A"),
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=30), 200.0, ficha="B"),
        _pos("S7-TPNONE", REOPEN + dt.timedelta(minutes=45), 10.0, ficha="C"),
    ]
    out = topk_sensitivity(rows, reopens, ks=(1,), rungs=[2])
    assert "global" in out and "by_group" in out
    assert "K1" in out["global"] and "K1" in out["by_group"]
    g = out["global"]["K1"]
    assert g["n_removed"] == 1
    assert "COMBINED" in g["curve"]
    assert "N2" in g["curve"]["COMBINED"]
    assert "ranking" in g
    assert {r["rung"] for r in g["ranking"]["COMBINED"]} == {"N2"}


# --------------------------- percentile ---------------------------
def test_percentile_known_vector_linear_interpolation():
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    assert percentile(values, 10) == pytest.approx(19.0)
    assert percentile(values, 25) == pytest.approx(32.5)
    assert percentile(values, 50) == pytest.approx(55.0)
    assert percentile(values, 75) == pytest.approx(77.5)
    assert percentile(values, 90) == pytest.approx(91.0)


def test_percentile_single_value():
    assert percentile([42.0], 25) == 42.0


def test_percentile_empty_is_zero():
    assert percentile([], 50) == 0.0


# --------------------------- M3: blocked vs kept ---------------------------
def test_blocked_vs_kept_uses_is_blocked_definition_exactly():
    reopens = [REOPEN]
    rows = [
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=15), -50.0, ficha="A"),
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=30), 200.0, ficha="B"),
        _pos("S6-K2P0", REOPEN + dt.timedelta(minutes=45), 30.0, ficha="C"),
    ]
    out = blocked_vs_kept(rows, reopens, rungs=[2])
    n2 = out["COMBINED"]["N2"]
    # N2 = 30-min wait blocks bars_since_reopen < 2, i.e. only the +15 entry.
    assert n2["blocked"]["n"] == 1
    assert n2["blocked"]["sum_clp"] == pytest.approx(-50.0)
    assert n2["kept"]["n"] == 2
    assert n2["kept"]["sum_clp"] == pytest.approx(230.0)


def test_blocked_vs_kept_profile_has_required_fields():
    reopens = [REOPEN]
    rows = [_pos("S6-K2P0", REOPEN + dt.timedelta(minutes=15 * i), float(v),
                 ficha=f"F{i}")
            for i, v in enumerate([-50, 200, 30, -10, 5, 70], start=0)]
    out = blocked_vs_kept(rows, reopens, rungs=[2])
    profile = out["COMBINED"]["N2"]["blocked"]
    for field in ("n", "sum_clp", "mean_clp", "median_clp", "p10", "p25",
                  "p75", "p90", "win_rate", "profit_factor", "max_win",
                  "max_loss"):
        assert field in profile


def test_blocked_vs_kept_concentration_top5_sums():
    reopens = [REOPEN]
    # 6 entries at +0min (bars_since_reopen == 0), all blocked by N=2..6 waits.
    nets = [-100.0, -80.0, -60.0, 40.0, 90.0, 120.0]
    rows = [_pos("S6-K2P0", REOPEN + dt.timedelta(minutes=15 * i), v, ficha=f"F{i}")
            for i, v in enumerate(nets)]
    out = blocked_vs_kept(rows, reopens, rungs=[6])
    conc = out["COMBINED"]["N6"]["concentration"]
    # Only the first 6 slots (0..75min) are all < 90min => all 6 blocked at N6
    # (bars 0,1,2,3,4,5 all < 6).
    assert conc["n_available"] == 6
    assert conc["top5_most_negative_sum"] == pytest.approx(sum(sorted(nets)[:5]))
    assert conc["top5_most_positive_sum"] == pytest.approx(
        sum(sorted(nets, reverse=True)[:5]))
