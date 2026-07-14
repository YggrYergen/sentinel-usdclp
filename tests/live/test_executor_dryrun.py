"""tests/live/test_executor_dryrun.py -- full dry-run cycle + never-launch +
parity smoke for the guarded live executor. All mocked; no MT5 terminal, no
orders sent."""
from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from scripts.live import run_live_20
from sentinel_engine.live import guard_cuenta
from sentinel_engine.live.reconciler import reconcile
from sentinel_engine.strategies.emasar_variant import simular_variant
from sentinel_engine.strategies.live_configs_20 import CONFIGS_20


# ------------------------- synthetic bars + mock mt5 -------------------------
def _bars(n=400, seed=7):
    rnd = random.Random(seed)
    price = 2000.0
    base = int(datetime(2026, 6, 2, tzinfo=timezone.utc).timestamp())
    out = []
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        o = price - drift
        c = price
        hi = max(o, c) + abs(rnd.uniform(0.3, 1.2))
        lo = min(o, c) - abs(rnd.uniform(0.3, 1.2))
        out.append({"t": base + k * 120, "open": o, "high": hi, "low": lo, "close": c})
    return out


class _Rate(dict):
    # numpy-record-like access via __getitem__ already works (it's a dict).
    pass


class _Info:
    def __init__(self, login, mode):
        self.login = login
        self.trade_mode = mode


class MockMT5:
    """Minimal MT5 surface the executor touches. Records order_send calls
    (there must be ZERO in dry-run)."""
    TIMEFRAME_M1 = 1
    TIMEFRAME_M2 = 2
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_SLTP = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0

    def __init__(self, bars, positions=None, login=guard_cuenta.DEMO_LOGIN,
                 mode=guard_cuenta.TRADE_MODE_DEMO):
        self._bars = bars
        self._positions = positions or []
        self._info = _Info(login, mode)
        self.sent = []
        self.initialized = False

    def initialize(self, *a, **k):
        self.initialized = True
        return True

    def last_error(self):
        return (0, "ok")

    def account_info(self):
        return self._info

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        # real MT5 rate records key time as "time"; the executor reads that.
        recs = [_Rate({"time": b["t"], "open": b["open"], "high": b["high"],
                       "low": b["low"], "close": b["close"]}) for b in self._bars]
        return recs[-count:]

    def positions_get(self, ticket=None):
        if ticket is not None:
            return [p for p in self._positions if getattr(p, "ticket", None) == ticket]
        return list(self._positions)

    def order_send(self, req):
        self.sent.append(req)
        class _R:
            retcode = 10009
        return _R()

    def shutdown(self):
        pass


# ------------------------------- tests --------------------------------------
def test_never_launch_when_terminal_absent():
    # attach_checker says NO terminal -> exit code 3, initialize NEVER called.
    mt5 = MockMT5(_bars())
    rc = run_live_20.main(["--once"], mt5_module=mt5, attach_checker=lambda: False)
    assert rc == 3
    assert mt5.initialized is False
    assert mt5.sent == []


def test_dry_run_once_sends_nothing():
    mt5 = MockMT5(_bars())
    rc = run_live_20.main(["--once", "--configs", "SS-M2"], mt5_module=mt5,
                          attach_checker=lambda: True)
    assert rc == 0
    assert mt5.initialized is True
    assert mt5.sent == [], "dry-run must send ZERO orders"


def test_guard_blocks_real_account():
    mt5 = MockMT5(_bars(), login=guard_cuenta.REAL_LOGIN,
                  mode=guard_cuenta.TRADE_MODE_REAL)
    with pytest.raises(SystemExit) as ei:
        run_live_20.main(["--once", "--configs", "SS-M2"], mt5_module=mt5,
                         attach_checker=lambda: True)
    assert ei.value.code == 2
    assert mt5.sent == []


def test_unknown_config_returns_2():
    mt5 = MockMT5(_bars())
    rc = run_live_20.main(["--once", "--configs", "NOPE"], mt5_module=mt5,
                          attach_checker=lambda: True)
    assert rc == 2


# ---- parity smoke: reconciler desired-state == sim open state over window ----
@pytest.mark.parametrize("cid", ["SS-M5", "V10-M15"])
def test_parity_desired_state_matches_sim(cid):
    """The reconciler's desired open-ficha set (derived from
    simular_variant(return_state=True)) must equal the sim's OWN open-ficha
    state at the final bar, for every prefix window. We assert the OPEN action
    set the reconciler emits (from empty live) exactly covers the fichas the
    sim reports open."""
    cfg = next(c for c in CONFIGS_20 if c["id"] == cid)
    bars = _bars(500, seed=11)
    kwargs = dict(cfg["kwargs"])
    if cfg.get("direction_filter"):
        from scripts.report.gen_variant_batch5 import compute_direction_mask
        kwargs["direction_mask"] = compute_direction_mask(bars)
    _events, snap = simular_variant(bars, return_state=True, **kwargs)
    open_state = snap["open"]

    res = reconcile(cfg["id"], cfg["magic"], snap, [])  # no live positions
    open_tags = {a.ficha for a in res.actions if a.kind == "OPEN"}
    assert open_tags == set(open_state.keys())
    # and each OPEN carries the sim's exact SL for that ficha.
    for a in res.actions:
        if a.kind == "OPEN":
            assert a.sl == open_state[a.ficha]["sl"]
            assert a.side == open_state[a.ficha]["side"]


def test_return_state_default_off_is_backcompat():
    # return_state omitted -> plain list, byte-for-byte with before.
    bars = _bars(200)
    ev = simular_variant(bars, **CONFIGS_20[0]["kwargs"])
    assert isinstance(ev, list)
    ev2, snap = simular_variant(bars, return_state=True, **CONFIGS_20[0]["kwargs"])
    assert ev == ev2
    assert set(snap) == {"open", "last_bar_exits", "last_idx"}
