"""tests/live/test_risk_gates.py -- the challenger sleeve's four OPEN gates.

Pure logic: no MT5, no clock, no filesystem. The champion sleeve never reaches
this module (it has no `risk_gates` key), which the empty-dict test pins down.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sentinel_engine.live.risk_gates import GateInput, evaluate_open_gates

T0 = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


def _gi(**over):
    base = dict(now=T0, spread_ok_since=T0 - timedelta(minutes=90), open_fichas=0,
                desired_sl=3900.0, market_ref=4000.0, news_windows=())
    base.update(over)
    return GateInput(**base)


def test_no_gates_always_allows():
    # THE CHAMPION'S GUARANTEE: an absent/empty risk_gates dict is a no-op.
    for gates in ({}, None):
        d = evaluate_open_gates(gates, _gi(spread_ok_since=None, open_fichas=999,
                                           desired_sl=None, market_ref=None,
                                           news_windows=None))
        assert d.allow is True
        assert d.gate == ""


def test_b1_denies_before_the_wait_elapses():
    d = evaluate_open_gates({"gap_wait_minutes": 50},
                            _gi(spread_ok_since=T0 - timedelta(minutes=49)))
    assert d.allow is False and d.gate == "B1"
    assert "49.0 of 50" in d.reason


def test_b1_allows_once_the_wait_elapsed():
    d = evaluate_open_gates({"gap_wait_minutes": 50},
                            _gi(spread_ok_since=T0 - timedelta(minutes=50)))
    assert d.allow is True


def test_b1_denies_when_the_thin_regime_never_started():
    d = evaluate_open_gates({"gap_wait_minutes": 50}, _gi(spread_ok_since=None))
    assert d.allow is False and d.gate == "B1"


def test_b2_fails_closed_without_a_calendar():
    d = evaluate_open_gates({"news_blackout_minutes": 30}, _gi(news_windows=None))
    assert d.allow is False and d.gate == "B2"
    assert "fail-closed" in d.reason


def test_b2_denies_inside_a_window_and_allows_outside():
    win = ((T0 - timedelta(minutes=5), T0 + timedelta(minutes=25)),)
    assert evaluate_open_gates({"news_blackout_minutes": 30},
                               _gi(news_windows=win)).allow is False
    far = ((T0 + timedelta(hours=3), T0 + timedelta(hours=4)),)
    assert evaluate_open_gates({"news_blackout_minutes": 30},
                               _gi(news_windows=far)).allow is True


def test_b2_boundaries_are_inclusive():
    win = ((T0, T0 + timedelta(minutes=30)),)
    assert evaluate_open_gates({"news_blackout_minutes": 30},
                               _gi(now=T0, news_windows=win)).allow is False
    assert evaluate_open_gates({"news_blackout_minutes": 30},
                               _gi(now=T0 + timedelta(minutes=30),
                                   news_windows=win)).allow is False


def test_b3_denies_at_and_above_the_cap():
    assert evaluate_open_gates({"max_open_fichas": 3}, _gi(open_fichas=2)).allow is True
    d = evaluate_open_gates({"max_open_fichas": 3}, _gi(open_fichas=3))
    assert d.allow is False and d.gate == "B3"


def test_b4_flags_an_illegal_sl_as_a_bug():
    d = evaluate_open_gates({"min_sl_distance": 0.5},
                            _gi(desired_sl=3999.7, market_ref=4000.0))
    assert d.allow is False and d.gate == "B4"
    assert "THIS IS A BUG" in d.reason


def test_b4_allows_a_legal_sl_on_either_side():
    assert evaluate_open_gates({"min_sl_distance": 0.5},
                               _gi(desired_sl=3999.4, market_ref=4000.0)).allow is True
    assert evaluate_open_gates({"min_sl_distance": 0.5},
                               _gi(desired_sl=4000.6, market_ref=4000.0)).allow is True


def test_b4_fails_closed_when_it_cannot_verify():
    d = evaluate_open_gates({"min_sl_distance": 0.5}, _gi(desired_sl=None))
    assert d.allow is False and d.gate == "B4"


def test_gate_order_is_b1_b2_b3_b4():
    # All four would deny; the reported gate must be the FIRST in order, so the
    # audit log always names the outermost reason.
    gates = {"gap_wait_minutes": 50, "news_blackout_minutes": 30,
             "max_open_fichas": 1, "min_sl_distance": 0.5}
    d = evaluate_open_gates(gates, _gi(spread_ok_since=None, news_windows=None,
                                       open_fichas=5, desired_sl=None))
    assert d.gate == "B1"
