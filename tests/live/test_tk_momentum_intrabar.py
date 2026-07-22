"""tests/live/test_tk_momentum_intrabar.py -- INTRABAR path for TK-Momentum
(2026-07-21 trader request: enter the moment conditions are met live, WITHOUT
waiting for the M6 bar to close).

The executor evaluates the engine on the still-FORMING bar (current price) when
the config carries `intrabar=True`. These tests pin that contract with a mock
MT5: the same bar series yields NO entry from the closed bars alone, but DOES
open once the forming bar is included. No real MT5, no orders sent.
"""
from __future__ import annotations

import copy

from scripts.live import run_live_20
from sentinel_engine.live.reconciler import Action
from sentinel_engine.strategies.live_configs_20 import CONFIG_TK_MOMENTUM
from tests.live.test_executor_dryrun import MockMT5, _Pos

# A long-STATE setup: the up-regime (SMA5>SMA8) + MOM2>100 state materialises
# ONLY on the 10th bar. If that 10th bar is the still-forming one, closed bars
# (first 9) show no state (MOM2 dipped <100 at i=7,8); including the forming bar
# satisfies the LONG state and opens.
_CLOSES = [90, 92, 94, 100, 102, 104, 101, 100, 101, 108]


def _bars():
    t0 = 1_700_000_000
    # M6 bars are 360s apart (trader 2026-07-21: M10 -> M6).
    return [{"t": t0 + 360 * i, "open": c, "high": c + 0.1, "low": c - 0.1,
             "close": c} for i, c in enumerate(_CLOSES)]


def _cfg(intrabar: bool):
    c = copy.deepcopy(CONFIG_TK_MOMENTUM)
    c["kwargs"]["intrabar"] = intrabar
    return c


def test_fetch_bars_include_forming_toggles_last_bar():
    mt5 = MockMT5(_bars())
    closed = run_live_20.fetch_bars(mt5, "XAUUSD", "M6", 3000)
    withforming = run_live_20.fetch_bars(mt5, "XAUUSD", "M6", 3000,
                                         include_forming=True)
    assert len(withforming) == len(closed) + 1
    assert withforming[-1]["close"] == _CLOSES[-1]      # forming bar kept
    assert closed[-1]["close"] == _CLOSES[-2]           # forming bar dropped


def test_closed_driven_does_not_open_until_bar_closes():
    mt5 = MockMT5(_bars())
    res, _ = run_live_20.reconcile_config(
        mt5, _cfg(intrabar=False), window=3000, volume=0.01,
        kill_switch=False, total_open_fichas=0)
    assert [a for a in res.actions if a.kind == "OPEN"] == [], \
        "close-driven: the still-forming bar's signal must NOT open yet"


def test_intrabar_opens_on_the_forming_bar():
    mt5 = MockMT5(_bars())
    res, _ = run_live_20.reconcile_config(
        mt5, _cfg(intrabar=True), window=3000, volume=0.01,
        kill_switch=False, total_open_fichas=0)
    opens = [a for a in res.actions if a.kind == "OPEN"]
    assert len(opens) == 1, "intrabar: the forming-bar state opens immediately"
    o = opens[0]
    assert o.side == "L" and o.magic == 999999999
    assert o.sl == _CLOSES[-1] - 3.0                    # long SL = entry - trail(3.0)


# ---- single-position invariant at the EXECUTION layer (2026-07-21 incident) --
def test_single_position_guard_suppresses_open_while_a_position_is_live():
    # The forming-bar state wants a LONG, but a stale SHORT is still on the book
    # (magic 999999999). The reconciler would emit CLOSE(short)+OPEN(long) in the
    # SAME cycle (optimistic reopen). The guard must SUPPRESS the OPEN while any
    # live position exists -> only the CLOSE goes out; the (re)open waits until
    # the book is confirmed flat next cycle. This caps the book at one position
    # even if a close transiently fails, the root of the accumulation incident.
    stale_short = _Pos(ticket=900, magic=999999999,
                       type=MockMT5.POSITION_TYPE_SELL, volume=0.01, sl=9999.0)
    mt5 = MockMT5(_bars(), positions=[stale_short])
    res, _ = run_live_20.reconcile_config(
        mt5, _cfg(intrabar=True), window=3000, volume=0.01,
        kill_switch=False, total_open_fichas=0)
    kinds = [a.kind for a in res.actions]
    assert "OPEN" not in kinds, "guard must suppress OPEN while a live position exists"
    assert "CLOSE" in kinds, "the stale opposite-side position must still be closed"


def test_close_retries_on_transient_send_failure():
    # order_send returns None on the first close (transient "trade context
    # busy") then DONE. The close MUST be retried (not fire-and-forget), so the
    # position is actually removed instead of silently leaking -> accumulation.
    pos = _Pos(ticket=555, magic=999999999, type=MockMT5.POSITION_TYPE_SELL,
               volume=0.01, sl=9999.0)
    mt5 = MockMT5(_bars(), positions=[pos], order_send_retcodes=[None, 10009])
    a = Action(kind="CLOSE", config_id="TK-Momentum-5-8-short", ficha="F1",
               magic=999999999, ticket=555, side="S", volume=0.01)
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False)
    assert len(mt5.sent) == 2, "a transient None on close must be retried, not dropped"
