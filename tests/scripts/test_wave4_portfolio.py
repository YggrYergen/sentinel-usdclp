"""Unit tests for scripts/report/gen_wave4_portfolio.py — the honest Wave 4
portfolio/cross-config study (P48/P49/P50).

Test-first coverage of the load-bearing pure logic:
  (a) F1/F2/F3 dedup collapses identical-pnl same-signal fichas to ONE, but
      keeps divergent-exit fichas separately;
  (b) two opposite-side simultaneously-open positions net in gross exposure;
  (c) a known tiny fixture portfolio nets to the hand-computed combined pnl.

All logic under test is pure (operates on plain Trade tuples), so no DB is
touched here.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "report" / "gen_wave4_portfolio.py"
_spec = importlib.util.spec_from_file_location("gen_wave4_portfolio", _MOD_PATH)
w4 = importlib.util.module_from_spec(_spec)
sys.modules["gen_wave4_portfolio"] = w4  # dataclass needs the module registered
_spec.loader.exec_module(w4)


def T(signal_id, ficha, pnl, side="LONG", ts_in="2026.06.01 09:00:00",
      ts_out="2026.06.01 10:00:00", exit_reason="EXIT_INITSL"):
    return w4.Trade(
        signal_id=signal_id, ficha=ficha, pnl=pnl, side=side,
        ts_in=ts_in, ts_out=ts_out, exit_reason=exit_reason,
    )


# --------------------------------------------------------------------------
# (a) F1/F2/F3 dedup
# --------------------------------------------------------------------------

def test_dedup_collapses_identical_replicas_to_one():
    # Three fichas of the same signal, identical pnl + exit -> replicas.
    rows = [
        T("sig-1", "F1", 130.5),
        T("sig-1", "F2", 130.5),
        T("sig-1", "F3", 130.5),
    ]
    out = w4.dedup_trades(rows)
    assert len(out) == 1
    assert out[0].pnl == 130.5


def test_dedup_keeps_divergent_exit_fichas():
    # Same signal but fichas diverge (different pnl / exit) -> keep each.
    rows = [
        T("sig-9", "F1", 100.0, exit_reason="EXIT_TP"),
        T("sig-9", "F2", -40.0, exit_reason="EXIT_SL"),
        T("sig-9", "F3", 100.0, exit_reason="EXIT_TP"),  # replica of F1
    ]
    out = w4.dedup_trades(rows)
    # F1 & F3 collapse (identical pnl+exit); F2 diverges and is kept.
    assert len(out) == 2
    pnls = sorted(t.pnl for t in out)
    assert pnls == [-40.0, 100.0]


def test_dedup_net_is_one_third_of_summed_replicas():
    rows = [T(f"sig-{i}", f, 10.0) for i in range(5) for f in ("F1", "F2", "F3")]
    summed = sum(t.pnl for t in rows)  # 15 rows * 10
    net = sum(t.pnl for t in w4.dedup_trades(rows))
    assert summed == 150.0
    assert net == 50.0  # 5 unique signals * 10


# --------------------------------------------------------------------------
# (b) opposite-side simultaneous positions net in gross exposure
# --------------------------------------------------------------------------

def test_opposite_simultaneous_positions_net_gross_exposure():
    # cfgA holds LONG 09:00-11:00; cfgB holds SHORT 10:00-12:00.
    # Overlap window 10:00-11:00: gross = 2 units, net = 0 units.
    cfgA = [T("a1", "F1", 0.0, side="LONG",
              ts_in="2026.06.01 09:00:00", ts_out="2026.06.01 11:00:00")]
    cfgB = [T("b1", "F1", 0.0, side="SHORT",
              ts_in="2026.06.01 10:00:00", ts_out="2026.06.01 12:00:00")]
    res = w4.exposure_netting({"A": cfgA, "B": cfgB})
    # There is exactly one overlapping-opposite interval.
    assert res["opposite_overlap_intervals"] >= 1
    # Gross exposure-time strictly exceeds net exposure-time (netting happened).
    assert res["gross_exposure_minutes"] > res["net_exposure_minutes"]
    assert 0.0 <= res["reduction_pct"] <= 100.0
    assert res["reduction_pct"] > 0.0


def test_same_side_positions_do_not_reduce_net():
    # Two LONGs overlapping -> net exposure == gross (no opposite netting).
    cfgA = [T("a1", "F1", 0.0, side="LONG",
              ts_in="2026.06.01 09:00:00", ts_out="2026.06.01 11:00:00")]
    cfgB = [T("b1", "F1", 0.0, side="LONG",
              ts_in="2026.06.01 10:00:00", ts_out="2026.06.01 12:00:00")]
    res = w4.exposure_netting({"A": cfgA, "B": cfgB})
    assert res["opposite_overlap_intervals"] == 0
    assert res["gross_exposure_minutes"] == res["net_exposure_minutes"]
    assert res["reduction_pct"] == 0.0


# --------------------------------------------------------------------------
# (c) known tiny fixture portfolio nets to the hand-computed combined pnl
# --------------------------------------------------------------------------

def test_tiny_fixture_portfolio_combined_pnl():
    # cfgA: sig-1 (3 replica fichas @ +100) + sig-2 (3 replica fichas @ -30).
    #   dedup'd net = 100 + (-30) = 70.
    # cfgB: sig-3 (3 replica fichas @ +50).  dedup'd net = 50.
    # Equal-weight combined portfolio net = 70 + 50 = 120.
    cfgA = (
        [T("sig-1", f, 100.0) for f in ("F1", "F2", "F3")]
        + [T("sig-2", f, -30.0) for f in ("F1", "F2", "F3")]
    )
    cfgB = [T("sig-3", f, 50.0) for f in ("F1", "F2", "F3")]

    net_a = w4.config_net({"A": cfgA})["A"]
    net_b = w4.config_net({"B": cfgB})["B"]
    assert net_a == 70.0
    assert net_b == 50.0

    combined = w4.combined_portfolio_net({"A": cfgA, "B": cfgB})
    assert combined == 120.0


def test_combined_equals_sum_of_config_nets():
    cfgA = [T("s1", f, 12.5) for f in ("F1", "F2", "F3")]
    cfgB = [T("s2", f, -4.0) for f in ("F1", "F2", "F3")]
    nets = w4.config_net({"A": cfgA, "B": cfgB})
    combined = w4.combined_portfolio_net({"A": cfgA, "B": cfgB})
    assert combined == pytest.approx(sum(nets.values()))


# --------------------------------------------------------------------------
# signal-overlap (P50) pure helper
# --------------------------------------------------------------------------

def test_signal_overlap_fraction():
    # A and B share 2 of 3 signal keys -> Jaccard 2/4 = 0.5.
    a = [T("sig-1780277880-1", "F1", 0.0), T("sig-1780278120-2", "F1", 0.0),
         T("sig-9999999999-9", "F1", 0.0)]
    b = [T("sig-1780277880-1", "F1", 0.0), T("sig-1780278120-2", "F1", 0.0),
         T("sig-8888888888-8", "F1", 0.0)]
    frac = w4.signal_overlap_jaccard(a, b)
    assert frac == pytest.approx(2.0 / 4.0)


def test_signal_overlap_uses_timestamp_key_not_seq():
    # Same entry timestamp, different trailing seq -> still counted as shared.
    a = [T("sig-1780277880-1", "F1", 0.0)]
    b = [T("sig-1780277880-7", "F1", 0.0)]
    frac = w4.signal_overlap_jaccard(a, b)
    assert frac == pytest.approx(1.0)
