"""tests/live/test_grouping.py — TDD for sentinel_engine.live.grouping (B1b).

Covers: simple 1 IN + 1 OUT position, partial-close (multi-OUT VWAP exit
+ summed pnl), the "3 fichas" multi-lot grouping (entries within 90s),
non-grouping when outside the 90s window or when symbol/side/magic
differ, and the MAE/MFE-deferred flag (mae=None, mfe=None,
needs_excursions=True) on every position.

Deal dicts here follow the exact `deals_raw` field shape produced by
`sentinel_engine.live.deals_watcher._map_deal`: ticket, position_id,
symbol, side, volume, price, profit, magic, time, entry_type, origin,
strategy_id, variant_id.
"""
from __future__ import annotations

import pytest

from sentinel_engine.live.grouping import Position, PositionGroup, group_positions


def _deal(**kwargs):
    base = {
        "ticket": None,
        "position_id": None,
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": 0.1,
        "price": 0.0,
        "profit": 0.0,
        "magic": 100123,
        "time": 0,
        "entry_type": "IN",
        "origin": "strategy",
        "strategy_id": 1,
        "variant_id": 1,
    }
    base.update(kwargs)
    return base


def test_simple_in_out_produces_one_position():
    deals = [
        _deal(ticket=1, position_id=5001, entry_type="IN", price=2400.5,
              volume=0.1, time=1000, profit=0.0),
        _deal(ticket=2, position_id=5001, entry_type="OUT", price=2405.0,
              volume=0.1, time=1100, profit=4.5),
    ]

    groups = group_positions(deals)

    assert len(groups) == 1
    group = groups[0]
    assert isinstance(group, PositionGroup)
    assert len(group.children) == 1

    pos = group.children[0]
    assert isinstance(pos, Position)
    assert pos.position_id == 5001
    assert pos.entry_time == 1000
    assert pos.entry_price == 2400.5
    assert pos.entry_volume == 0.1
    assert pos.exit_price == 2405.0
    assert pos.exit_time == 1100
    assert pos.pnl == 4.5
    assert len(pos.fills) == 1


def test_partial_close_aggregates_vwap_exit_and_summed_pnl():
    deals = [
        _deal(ticket=1, position_id=6001, entry_type="IN", price=100.0,
              volume=0.3, time=2000, profit=0.0),
        _deal(ticket=2, position_id=6001, entry_type="OUT", price=101.0,
              volume=0.1, time=2050, profit=1.0),
        _deal(ticket=3, position_id=6001, entry_type="OUT", price=103.0,
              volume=0.2, time=2100, profit=6.0),
    ]

    groups = group_positions(deals)

    assert len(groups) == 1
    pos = groups[0].children[0]
    assert len(pos.fills) == 2

    expected_vwap = (101.0 * 0.1 + 103.0 * 0.2) / (0.1 + 0.2)
    assert pos.exit_price == pytest.approx(expected_vwap)
    assert pos.pnl == 7.0
    assert pos.exit_time == 2100
    assert pos.entry_price == 100.0
    assert pos.entry_volume == 0.3


def test_three_lot_group_within_90s_aggregates_correctly():
    deals = []
    # Position A: entry t=1000, exit t=1050, pnl=1.0, volume=0.1
    deals += [
        _deal(ticket=1, position_id=7001, entry_type="IN", price=100.0,
              volume=0.1, time=1000, magic=555),
        _deal(ticket=2, position_id=7001, entry_type="OUT", price=101.0,
              volume=0.1, time=1050, profit=1.0, magic=555),
    ]
    # Position B: entry t=1040 (40s after A), exit t=1090, pnl=2.0, volume=0.2
    deals += [
        _deal(ticket=3, position_id=7002, entry_type="IN", price=102.0,
              volume=0.2, time=1040, magic=555),
        _deal(ticket=4, position_id=7002, entry_type="OUT", price=103.0,
              volume=0.2, time=1090, profit=2.0, magic=555),
    ]
    # Position C: entry t=1080 (80s after A), exit t=1150, pnl=3.0, volume=0.3
    deals += [
        _deal(ticket=5, position_id=7003, entry_type="IN", price=104.0,
              volume=0.3, time=1080, magic=555),
        _deal(ticket=6, position_id=7003, entry_type="OUT", price=105.0,
              volume=0.3, time=1150, profit=3.0, magic=555),
    ]

    groups = group_positions(deals)

    assert len(groups) == 1
    group = groups[0]
    assert len(group.children) == 3
    assert group.group_id == "555-1000"
    assert group.symbol == "XAUUSD"
    assert group.side == "BUY"
    assert group.magic == 555
    assert group.first_in == 1000
    assert group.last_out == 1150
    assert group.net == pytest.approx(6.0)
    assert group.lots == pytest.approx(0.6)


def test_entries_outside_90s_window_do_not_group():
    deals = []
    deals += [
        _deal(ticket=1, position_id=8001, entry_type="IN", price=100.0,
              volume=0.1, time=1000, magic=777),
        _deal(ticket=2, position_id=8001, entry_type="OUT", price=101.0,
              volume=0.1, time=1050, profit=1.0, magic=777),
    ]
    # Entry 200s later -- outside the 90s window.
    deals += [
        _deal(ticket=3, position_id=8002, entry_type="IN", price=102.0,
              volume=0.2, time=1200, magic=777),
        _deal(ticket=4, position_id=8002, entry_type="OUT", price=103.0,
              volume=0.2, time=1250, profit=2.0, magic=777),
    ]

    groups = group_positions(deals)

    assert len(groups) == 2
    assert all(len(g.children) == 1 for g in groups)


def test_different_symbol_side_or_magic_do_not_group():
    deals = []
    # Same times, but different symbol/side/magic each pair.
    deals += [
        _deal(ticket=1, position_id=9001, entry_type="IN", price=100.0,
              volume=0.1, time=1000, symbol="XAUUSD", side="BUY", magic=1),
        _deal(ticket=2, position_id=9001, entry_type="OUT", price=101.0,
              volume=0.1, time=1010, profit=1.0, symbol="XAUUSD", side="BUY", magic=1),
    ]
    deals += [
        _deal(ticket=3, position_id=9002, entry_type="IN", price=100.0,
              volume=0.1, time=1005, symbol="EURUSD", side="BUY", magic=1),
        _deal(ticket=4, position_id=9002, entry_type="OUT", price=101.0,
              volume=0.1, time=1015, profit=1.0, symbol="EURUSD", side="BUY", magic=1),
    ]
    deals += [
        _deal(ticket=5, position_id=9003, entry_type="IN", price=100.0,
              volume=0.1, time=1006, symbol="XAUUSD", side="SELL", magic=1),
        _deal(ticket=6, position_id=9003, entry_type="OUT", price=101.0,
              volume=0.1, time=1016, profit=1.0, symbol="XAUUSD", side="SELL", magic=1),
    ]
    deals += [
        _deal(ticket=7, position_id=9004, entry_type="IN", price=100.0,
              volume=0.1, time=1007, symbol="XAUUSD", side="BUY", magic=2),
        _deal(ticket=8, position_id=9004, entry_type="OUT", price=101.0,
              volume=0.1, time=1017, profit=1.0, symbol="XAUUSD", side="BUY", magic=2),
    ]

    groups = group_positions(deals)

    assert len(groups) == 4
    assert all(len(g.children) == 1 for g in groups)


def test_orphan_out_only_position_is_skipped_without_crash():
    """A position_id with only OUT deals (its IN entry fell outside the
    queried window, e.g. a rolling fetch) must not raise StopIteration.
    It's dropped silently; other positions in the same batch are
    unaffected."""
    deals = [
        # Orphan: OUT-only, no IN deal for position_id=4001.
        _deal(ticket=1, position_id=4001, entry_type="OUT", price=101.0,
              volume=0.1, time=1010, profit=1.0),
        # Normal position, should still be grouped correctly.
        _deal(ticket=2, position_id=4002, entry_type="IN", price=100.0,
              volume=0.1, time=2000),
        _deal(ticket=3, position_id=4002, entry_type="OUT", price=102.0,
              volume=0.1, time=2050, profit=2.0),
    ]

    groups = group_positions(deals)

    all_positions = [pos for g in groups for pos in g.children]
    assert len(all_positions) == 1
    assert all_positions[0].position_id == 4002
    assert all_positions[0].pnl == 2.0


def test_mae_mfe_are_none_and_flagged_pending_on_every_position():
    deals = [
        _deal(ticket=1, position_id=1001, entry_type="IN", price=100.0,
              volume=0.1, time=1000),
        _deal(ticket=2, position_id=1001, entry_type="OUT", price=101.0,
              volume=0.1, time=1010, profit=1.0),
        _deal(ticket=3, position_id=1002, entry_type="IN", price=100.0,
              volume=0.1, time=5000),
        _deal(ticket=4, position_id=1002, entry_type="OUT", price=101.0,
              volume=0.1, time=5010, profit=1.0),
    ]

    groups = group_positions(deals)

    all_positions = [pos for g in groups for pos in g.children]
    assert len(all_positions) == 2
    for pos in all_positions:
        assert pos.mae is None
        assert pos.mfe is None
        assert pos.needs_excursions is True
