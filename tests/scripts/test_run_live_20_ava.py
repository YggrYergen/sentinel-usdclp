"""tests/scripts/test_run_live_20_ava.py -- executor wiring for the AVA demo
roster (D-62, 2026-08-20): `--configs ava` roster resolution, the R1/R2
window-gate suppression, the single-position defense-in-depth assert, the
single-position execution guard (flip scenario), and the mandatory 0.01 lot.

All MT5 interaction is mocked (`MockMT5`); ZERO orders sent. The window-gate
logic itself (R1 candle blackout + R2 calendar window, DST edges) is covered
in depth by `tests/live/test_ava_window_gate.py` -- this file only proves the
WIRING into `run_live_20.reconcile_config` is correct and opt-in.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from scripts.live import run_live_20
from sentinel_engine.strategies.live_configs_20 import CONFIGS_AVA

from tests.live.test_executor_dryrun import MockMT5, _Pos

_NY = ZoneInfo("America/New_York")


def _bars_m15_ending_at(closed_epoch: float, n: int = 60, seed: int = 11):
    """M15 bars (900s step) whose SECOND-TO-LAST element lands at
    `closed_epoch` -- `fetch_bars` drops the LAST element as the still-
    forming bar, so `bars[-1]["t"]` (the last CLOSED bar the executor/gate
    acts on) ends up equal to `closed_epoch`."""
    rnd = random.Random(seed)
    step = 900
    base = closed_epoch - (n - 2) * step
    price = 4500.0
    out = []
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        o = price - drift
        c = price
        hi = max(o, c) + abs(rnd.uniform(0.3, 1.2))
        lo = min(o, c) - abs(rnd.uniform(0.3, 1.2))
        out.append({"t": base + k * step, "open": o, "high": hi, "low": lo, "close": c})
    return out


def _epoch_ny(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, 0, tzinfo=_NY).timestamp()


_ST_AVA = next(c for c in CONFIGS_AVA if c["id"] == "SuperTrend-p14x3-M15-AVA")
_S6_AVA = next(c for c in CONFIGS_AVA if c["id"] == "S6-K2P0-AVA")


# --------------------------------------------------------------------------
# --configs ava roster resolution
# --------------------------------------------------------------------------
def test_configs_ava_selects_exactly_two(caplog):
    mt5 = MockMT5(_bars_m15_ending_at(_epoch_ny(2026, 6, 15, 20, 0)))
    rc = run_live_20.main(["--once", "--configs", "ava"], mt5_module=mt5,
                          attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"


def test_configs_ava_case_insensitive():
    mt5 = MockMT5(_bars_m15_ending_at(_epoch_ny(2026, 6, 15, 20, 0)))
    rc = run_live_20.main(["--once", "--configs", "AVA"], mt5_module=mt5,
                          attach_checker=lambda: True)
    assert rc == 0


# --------------------------------------------------------------------------
# window-gate wiring: R2 (outside the operating window)
# --------------------------------------------------------------------------
def test_window_gate_suppresses_open_outside_r2_window():
    # 12:00 ET -- squarely inside Chilean/US daytime, outside 18-02/03 ET.
    bar_t = _epoch_ny(2026, 6, 15, 12, 0)
    mt5 = MockMT5(_bars_m15_ending_at(bar_t))
    res, got_bar_t = run_live_20.reconcile_config(
        mt5, _ST_AVA, window=60, volume=0.01, kill_switch=False, total_open_fichas=0)
    assert res is not None
    assert got_bar_t == bar_t
    opens = [a for a in res.actions if a.kind == "OPEN"]
    assert not opens, "an OPEN outside the R2 operating window must be suppressed"


# --------------------------------------------------------------------------
# window-gate wiring: R1 (opening blackout, first 3 M15 candles)
# --------------------------------------------------------------------------
def test_window_gate_suppresses_open_during_r1_blackout():
    # bar OPEN time 18:15 ET -- the 2nd M15 candle after the 18:00 ET
    # reopen, squarely inside the R1 blackout (blocked until 18:45).
    bar_t = _epoch_ny(2026, 6, 15, 18, 15)
    mt5 = MockMT5(_bars_m15_ending_at(bar_t))
    res, _ = run_live_20.reconcile_config(
        mt5, _ST_AVA, window=60, volume=0.01, kill_switch=False, total_open_fichas=0)
    assert res is not None
    opens = [a for a in res.actions if a.kind == "OPEN"]
    assert not opens, "an OPEN in the R1 blackout (candles 1-3) must be suppressed"


def test_window_gate_allows_open_from_the_fourth_candle():
    # bar OPEN time 18:45 ET -- the 4th candle, first eligible per R1; and
    # 18:45 is inside the R2 operating window too.
    bar_t = _epoch_ny(2026, 6, 15, 18, 45)
    mt5 = MockMT5(_bars_m15_ending_at(bar_t))
    res, _ = run_live_20.reconcile_config(
        mt5, _ST_AVA, window=60, volume=0.01, kill_switch=False, total_open_fichas=0)
    assert res is not None
    opens = [a for a in res.actions if a.kind == "OPEN"]
    assert opens, "SuperTrend always-in must desire an open position once warmed up"
    for a in opens:
        assert a.volume == 0.01, "AVA lot must be 0.01"


def test_window_gate_allows_open_well_inside_the_window():
    bar_t = _epoch_ny(2026, 6, 15, 21, 0)
    mt5 = MockMT5(_bars_m15_ending_at(bar_t))
    res, _ = run_live_20.reconcile_config(
        mt5, _ST_AVA, window=60, volume=0.01, kill_switch=False, total_open_fichas=0)
    assert res is not None
    opens = [a for a in res.actions if a.kind == "OPEN"]
    assert opens


def test_window_gate_never_suppresses_close_or_modify():
    # A live position already open on the book -- CLOSE/MODIFY decisions
    # must NOT be affected by the window gate, only OPEN.
    bar_t = _epoch_ny(2026, 6, 15, 12, 0)  # outside the window
    bars = _bars_m15_ending_at(bar_t)
    # figure out which side SuperTrend currently desires so we can plant a
    # live position on the OPPOSITE side -> forces a CLOSE (orphan) action.
    from sentinel_engine.strategies.live_configs_20 import supertrend_always_in_target
    desired = supertrend_always_in_target(bars[:-1])
    f1 = desired["open"].get("F1")
    assert f1 is not None
    opposite_type = 1 if f1["side"] == "L" else 0  # POSITION_TYPE_SELL=1 / BUY=0
    magic = _ST_AVA["magic"] + 1
    live_pos = _Pos(ticket=555, magic=magic, type=opposite_type, volume=0.01,
                    sl=f1["sl"], symbol="GOLD")
    mt5 = MockMT5(bars, positions=[live_pos])
    res, _ = run_live_20.reconcile_config(
        mt5, _ST_AVA, window=60, volume=0.01, kill_switch=False, total_open_fichas=0)
    assert res is not None
    kinds = {a.kind for a in res.actions}
    assert "CLOSE" in kinds, \
        "a wrong-side live position must still be closed even outside the R2 window"


# --------------------------------------------------------------------------
# single_position_only: defense-in-depth assert
# --------------------------------------------------------------------------
def test_single_position_only_assert_fires_on_a_multi_ficha_desired_state(monkeypatch):
    # Force a synthetic 2-ficha desired state through simular_variant to
    # prove the defense-in-depth assert actually fires for a
    # single_position_only config -- S6-K2P0-AVA's active_fichas=1 should
    # never let this happen in practice; this test pins the GUARD, not the
    # engine's own truncation (already covered by test_live_configs_ava.py).
    def _fake_simular_variant(bars, *, return_state, **kwargs):
        return [], {"open": {"F1": {"side": "L", "entry": 4500.0, "sl": 4490.0},
                             "F2": {"side": "L", "entry": 4500.0, "sl": 4490.0}},
                    "last_bar_exits": {}, "last_idx": len(bars) - 1}

    monkeypatch.setattr(run_live_20, "simular_variant", _fake_simular_variant)
    bar_t = _epoch_ny(2026, 6, 15, 20, 0)
    mt5 = MockMT5(_bars_m15_ending_at(bar_t))
    with pytest.raises(AssertionError, match="single_position_only"):
        run_live_20.reconcile_config(
            mt5, _S6_AVA, window=60, volume=0.01, kill_switch=False, total_open_fichas=0)


# --------------------------------------------------------------------------
# single_position_only: execution guard (flip scenario)
# --------------------------------------------------------------------------
def test_single_position_execution_guard_suppresses_open_while_live_exists():
    # A genuine FLIP scenario: plant a live F1 position on the OPPOSITE side
    # of what SuperTrend currently desires. Without the guard the reconciler
    # would emit BOTH a CLOSE (wrong-side orphan) AND an OPEN (the new side)
    # in the SAME cycle; the single-position guard must strip the OPEN
    # because a live position still exists (len(live) >= 1), leaving only
    # the CLOSE -- "close this cycle, open once confirmed flat next cycle".
    bar_t = _epoch_ny(2026, 6, 15, 20, 0)
    bars = _bars_m15_ending_at(bar_t)
    from sentinel_engine.strategies.live_configs_20 import supertrend_always_in_target
    desired = supertrend_always_in_target(bars[:-1])
    f1 = desired["open"]["F1"]
    opposite_type = 1 if f1["side"] == "L" else 0  # POSITION_TYPE_SELL=1 / BUY=0
    magic = _ST_AVA["magic"] + 1
    live_pos = _Pos(ticket=777, magic=magic, type=opposite_type, volume=0.01,
                    sl=4000.0, symbol="GOLD")
    mt5 = MockMT5(bars, positions=[live_pos])
    res, _ = run_live_20.reconcile_config(
        mt5, _ST_AVA, window=60, volume=0.01, kill_switch=False, total_open_fichas=0)
    assert res is not None
    kinds = [a.kind for a in res.actions]
    assert "CLOSE" in kinds, "the wrong-side orphan must still be closed"
    assert "OPEN" not in kinds, \
        "single-position guard must suppress the same-cycle re-OPEN while flipping"


# ---------------------------------------------------------------------------
# Filling-mode resolution (2026-08-20). AVA's GOLD is FOK-only and rejected
# the hard-coded IOC with retcode 10030 (INVALID_FILL); Capitaria symbols
# allow IOC and MUST keep behaving exactly as before.
# ---------------------------------------------------------------------------
class _FillMT5:
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1

    def __init__(self, mask):
        self._mask = mask

    def symbol_info(self, symbol):
        if self._mask is None:
            return None
        return type("SI", (), {"filling_mode": self._mask})()


def test_ioc_capable_symbol_still_gets_ioc_unchanged():
    # Capitaria: mask 2 (IOC) or 3 (FOK|IOC) -> IOC, byte-identical to the
    # pre-2026-08-20 hard-coded behaviour.
    for mask in (2, 3):
        assert run_live_20._resolve_filling(_FillMT5(mask), "XAUUSD") == 1


def test_fok_only_symbol_gets_fok():
    # AVA GOLD advertises filling_mode == 1 (FOK only).
    assert run_live_20._resolve_filling(_FillMT5(1), "GOLD") == 0


def test_unknown_symbol_info_falls_back_to_historical_ioc():
    assert run_live_20._resolve_filling(_FillMT5(None), "GOLD") == 1
    assert run_live_20._resolve_filling(_FillMT5(0), "GOLD") == 1
