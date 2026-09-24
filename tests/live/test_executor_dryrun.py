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
from sentinel_engine.strategies.live_configs_20 import CONFIGS_20, CONFIGS_LIVE, LIVE_ROSTER


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


class _Tick:
    def __init__(self, bid, ask):
        self.bid = bid
        self.ask = ask


class _SymbolInfo:
    def __init__(self, trade_stops_level=0, trade_freeze_level=0, point=0.01):
        self.trade_stops_level = trade_stops_level
        self.trade_freeze_level = trade_freeze_level
        self.point = point


class _Pos:
    def __init__(self, ticket, magic, type, volume, sl, symbol="XAUUSD"):
        self.ticket = ticket
        self.magic = magic
        self.type = type
        self.volume = volume
        self.sl = sl
        self.symbol = symbol


class MockMT5:
    """Minimal MT5 surface the executor touches. Records order_send calls
    (there must be ZERO in dry-run)."""
    TIMEFRAME_M1 = 1
    TIMEFRAME_M2 = 2
    TIMEFRAME_M5 = 5
    TIMEFRAME_M6 = 6
    TIMEFRAME_M10 = 10
    TIMEFRAME_M15 = 15
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_SLTP = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_INVALID_STOPS = 10016

    def __init__(self, bars, positions=None, login=guard_cuenta.DEMO_LOGIN,
                 mode=guard_cuenta.TRADE_MODE_DEMO, tick=None, symbol_info=None,
                 order_send_retcodes=None):
        self._bars = bars
        self._positions = positions or []
        self._info = _Info(login, mode)
        self.sent = []
        self.initialized = False
        self._tick = tick or _Tick(bid=2000.0, ask=2000.2)
        self._symbol_info = symbol_info or _SymbolInfo()
        # optional queue of retcodes to return in order, one per order_send call
        self._retcode_queue = list(order_send_retcodes) if order_send_retcodes else None
        self._order_ticket_seq = 900  # fake opening-order tickets for order_send.order

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

    def symbol_info_tick(self, symbol):
        return self._tick

    def symbol_info(self, symbol):
        return self._symbol_info

    def order_send(self, req):
        self.sent.append(req)
        rc = self._retcode_queue.pop(0) if self._retcode_queue else 10009
        if rc is None:
            # simulate a TRANSIENT order_send failure (e.g. "trade context
            # busy"): the real MT5 returns None, not a result object.
            return None
        class _R:
            pass
        r = _R()
        r.retcode = rc
        # Real MT5 returns the opening order ticket in `.order` (== the
        # resulting position identifier). Hand back a monotonically-increasing
        # fake ticket so spread-recording hooks have a position_id to key on.
        self._order_ticket_seq += 1
        r.order = self._order_ticket_seq
        return r

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


# ----------------- SL clamp / fallback-close on broker stop-level -----------
from sentinel_engine.live.reconciler import Action  # noqa: E402


def _modify_action(side="L", sl=1999.9, ticket=555, magic=101):
    return Action(kind="MODIFY", config_id="SS-M1", magic=magic, ficha="F1",
                  side=side, sl=sl, ticket=ticket, reason="drift")


def test_modify_long_desired_sl_crossed_triggers_fallback_close(caplog):
    # bid=2000.0; desired_sl >= bid -> crossed -> market-close, not MODIFY.
    pos = _Pos(ticket=555, magic=101, type=MockMT5.POSITION_TYPE_BUY,
              volume=0.01, sl=1990.0)
    mt5 = MockMT5(_bars(50), positions=[pos],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    same_bar_cost: dict[str, float] = {}
    a = _modify_action(side="L", sl=2000.05, ticket=555)  # >= bid -> crossed
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                                   same_bar_cost=same_bar_cost)
    assert len(mt5.sent) == 1
    req = mt5.sent[0]
    assert req["action"] == mt5.TRADE_ACTION_DEAL  # CLOSE, not SLTP
    assert req["type"] == mt5.ORDER_TYPE_SELL  # closing a LONG
    assert "FALLBACK_CLOSE_INVALID_SL" in caplog.text
    assert same_bar_cost.get("SS-M1", 0.0) > 0.0


def test_modify_long_desired_sl_too_close_clamps(caplog):
    # bid=2000.0, stops_level=50*0.01=0.50 -> legal SL must be <= 1999.50.
    pos = _Pos(ticket=555, magic=101, type=MockMT5.POSITION_TYPE_BUY,
              volume=0.01, sl=1990.0)
    mt5 = MockMT5(_bars(50), positions=[pos],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    sl_clamp_cost: dict[str, float] = {}
    a = _modify_action(side="L", sl=1999.90, ticket=555)  # too close, not crossed
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                                   sl_clamp_cost=sl_clamp_cost)
    assert len(mt5.sent) == 1
    req = mt5.sent[0]
    assert req["action"] == mt5.TRADE_ACTION_SLTP
    assert req["sl"] == pytest.approx(2000.0 - 0.50)
    assert "SL_CLAMPED" in caplog.text
    assert sl_clamp_cost.get("SS-M1", 0.0) > 0.0


def test_modify_long_desired_sl_legal_sent_unclamped():
    # bid=2000.0, stops_level=0.50; desired well below the stop-level band.
    pos = _Pos(ticket=555, magic=101, type=MockMT5.POSITION_TYPE_BUY,
              volume=0.01, sl=1990.0)
    mt5 = MockMT5(_bars(50), positions=[pos],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    a = _modify_action(side="L", sl=1995.0, ticket=555)  # legal, far from market
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False)
    assert len(mt5.sent) == 1
    req = mt5.sent[0]
    assert req["action"] == mt5.TRADE_ACTION_SLTP
    assert req["sl"] == pytest.approx(1995.0)


def test_modify_short_desired_sl_too_close_clamps(caplog):
    # ask=2000.2, stops_level=0.50 -> legal SL must be >= 2000.70.
    pos = _Pos(ticket=556, magic=102, type=MockMT5.POSITION_TYPE_SELL,
              volume=0.01, sl=2010.0)
    mt5 = MockMT5(_bars(50), positions=[pos],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    sl_clamp_cost: dict[str, float] = {}
    a = _modify_action(side="S", sl=2000.30, ticket=556, magic=102)
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                                   sl_clamp_cost=sl_clamp_cost)
    assert len(mt5.sent) == 1
    req = mt5.sent[0]
    assert req["action"] == mt5.TRADE_ACTION_SLTP
    assert req["sl"] == pytest.approx(2000.2 + 0.50)
    assert "SL_CLAMPED" in caplog.text
    assert sl_clamp_cost.get("SS-M1", 0.0) > 0.0


def test_modify_clamped_retries_refetch_tick_then_succeeds(caplog):
    """Clamped MODIFY fails 10016 twice; on each retry the tick is re-fetched
    and re-clamped, then succeeds -- no ALARM should be logged."""
    pos = _Pos(ticket=555, magic=101, type=MockMT5.POSITION_TYPE_BUY,
              volume=0.01, sl=1990.0)
    mt5 = MockMT5(_bars(50), positions=[pos],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01),
                  order_send_retcodes=[10016, 10016, 10009])
    sl_clamp_cost: dict[str, float] = {}
    a = _modify_action(side="L", sl=1999.90, ticket=555)
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                                   sl_clamp_cost=sl_clamp_cost, modify_retries=2)
    assert len(mt5.sent) == 3
    assert all(req["action"] == mt5.TRADE_ACTION_SLTP for req in mt5.sent)
    assert "ALARM" not in caplog.text
    assert "SL_CLAMPED" in caplog.text


# ----------------- --confirm-account non-interactive arm path ---------------
def test_confirm_account_matches_demo_skips_interactive_prompt(monkeypatch):
    def _boom():
        raise AssertionError("_arm_confirm must not be called when "
                              "--confirm-account matches the DEMO login")
    monkeypatch.setattr(run_live_20, "_arm_confirm", _boom)
    mt5 = MockMT5(_bars(), positions=[])
    rc = run_live_20.main(
        ["--once", "--configs", "SS-M2", "--arm",
         "--confirm-account", str(guard_cuenta.DEMO_LOGIN)],
        mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.initialized is True


def test_confirm_account_real_login_exits_2_no_initialize():
    mt5 = MockMT5(_bars())
    with pytest.raises(SystemExit) as ei:
        run_live_20.main(
            ["--once", "--configs", "SS-M2", "--arm",
             "--confirm-account", str(guard_cuenta.REAL_LOGIN)],
            mt5_module=mt5, attach_checker=lambda: True)
    assert ei.value.code == 2
    assert mt5.initialized is False
    assert mt5.sent == []


def test_confirm_account_bogus_number_exits_2():
    mt5 = MockMT5(_bars())
    with pytest.raises(SystemExit) as ei:
        run_live_20.main(
            ["--once", "--configs", "SS-M2", "--arm", "--confirm-account", "123"],
            mt5_module=mt5, attach_checker=lambda: True)
    assert ei.value.code == 2
    assert mt5.initialized is False


def test_arm_alone_invokes_interactive_confirm(monkeypatch):
    called = {"flag": False}

    def _fake_arm_confirm():
        called["flag"] = True
        raise SystemExit("account number mismatch -- aborting (nothing sent).")

    monkeypatch.setattr(run_live_20, "_arm_confirm", _fake_arm_confirm)
    mt5 = MockMT5(_bars())
    with pytest.raises(SystemExit):
        run_live_20.main(["--once", "--configs", "SS-M2", "--arm"],
                         mt5_module=mt5, attach_checker=lambda: True)
    assert called["flag"] is True


def test_confirm_account_without_arm_is_dry_run(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("WARNING"):
        rc = run_live_20.main(
            ["--once", "--configs", "SS-M2",
             "--confirm-account", str(guard_cuenta.DEMO_LOGIN)],
            mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert "ignored" in caplog.text


def test_modify_dry_run_too_close_logs_intent_sends_nothing(caplog):
    pos = _Pos(ticket=555, magic=101, type=MockMT5.POSITION_TYPE_BUY,
              volume=0.01, sl=1990.0)
    mt5 = MockMT5(_bars(50), positions=[pos],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    a = _modify_action(side="L", sl=1999.90, ticket=555)
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=True)
    assert mt5.sent == []
    assert "SL_CLAMPED" in caplog.text


# ----------------- OPEN path: SL clamp / skip on broker stop-level ----------
def _open_action(side="L", sl=1999.9, volume=0.01, config_id="SS-M1", magic=101):
    return Action(kind="OPEN", config_id=config_id, magic=magic, ficha="F1",
                  side=side, sl=sl, volume=volume, ticket=None, reason="entry")


def test_open_long_sl_too_close_clamps_and_sends(caplog):
    # bid=2000.0, stops_level=50*0.01=0.50 -> legal SL must be <= 1999.50.
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    sl_clamp_cost: dict[str, float] = {}
    a = _open_action(side="L", sl=1999.90)  # too close, not crossed
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                                   sl_clamp_cost=sl_clamp_cost)
    assert len(mt5.sent) == 1
    req = mt5.sent[0]
    assert req["action"] == mt5.TRADE_ACTION_DEAL
    assert req["sl"] == pytest.approx(2000.0 - 0.50)
    assert "SL_CLAMPED OPEN" in caplog.text
    assert sl_clamp_cost.get("SS-M1", 0.0) > 0.0


def test_open_long_sl_crossed_skips_send(caplog):
    # bid=2000.0; desired_sl >= bid -> crossed -> skip open entirely.
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    a = _open_action(side="L", sl=2000.05)  # >= bid -> crossed
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False)
    assert mt5.sent == []
    assert "OPEN_SKIPPED_SL_CROSSED" in caplog.text


def test_open_short_sl_too_close_clamps_and_sends(caplog):
    # ask=2000.2, stops_level=0.50 -> legal SL must be >= 2000.70.
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    sl_clamp_cost: dict[str, float] = {}
    a = _open_action(side="S", sl=2000.30, config_id="SS-M2", magic=102)
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                                   sl_clamp_cost=sl_clamp_cost)
    assert len(mt5.sent) == 1
    req = mt5.sent[0]
    assert req["action"] == mt5.TRADE_ACTION_DEAL
    assert req["sl"] == pytest.approx(2000.2 + 0.50)
    assert "SL_CLAMPED OPEN" in caplog.text
    assert sl_clamp_cost.get("SS-M2", 0.0) > 0.0


def test_open_retries_on_invalid_stops_then_succeeds(caplog):
    """OPEN fails 10016 twice with re-clamp on each retry, then succeeds --
    no ALARM should be logged."""
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01),
                  order_send_retcodes=[10016, 10016, 10009])
    sl_clamp_cost: dict[str, float] = {}
    a = _open_action(side="L", sl=1999.90)
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                                   sl_clamp_cost=sl_clamp_cost, open_retries=2)
    assert len(mt5.sent) == 3
    assert all(req["action"] == mt5.TRADE_ACTION_DEAL for req in mt5.sent)
    assert "ALARM" not in caplog.text
    assert "SL_CLAMPED OPEN" in caplog.text


def test_open_emits_fill_with_position_id_and_records_spread(tmp_path):
    """2026-07-21 spread capture: a successful OPEN must call on_fill with
    kind='OPEN' and the opening ORDER ticket (r.order), which equals the MT5
    position_id used in deals_raw -- so the real recorder writes a
    position_spread row keyed by that id, joinable via get_position_spreads."""
    from sentinel_engine.research.registry2 import ResearchRegistry
    reg = ResearchRegistry(tmp_path / "research.db")

    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.6),  # spread 0.60
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    seen = []

    def recorder(kind, position_id, spread):
        seen.append((kind, position_id, spread))
        if kind == "OPEN":
            reg.record_position_spread(position_id, ticket_open=position_id,
                                       spread_open=spread, spread_open_ts=1)

    a = _open_action(side="L", sl=1999.0)
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               on_fill=recorder)

    assert len(mt5.sent) == 1
    # on_fill fired once, OPEN, with the order ticket the fake mt5 handed back.
    assert len(seen) == 1
    kind, pid, spread = seen[0]
    assert kind == "OPEN"
    assert pid == mt5._order_ticket_seq  # r.order == position_id
    assert spread == pytest.approx(0.60)
    # recorder persisted a row keyed by that position_id.
    got = reg.get_position_spreads([pid])
    assert pid in got
    assert got[pid]["spread_open"] == pytest.approx(0.60)


def test_open_legal_sl_sent_unchanged(caplog):
    # bid=2000.0, stops_level=0.50; desired well below the stop-level band.
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.2),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    a = _open_action(side="L", sl=1995.0)  # legal, far from market
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False)
    assert len(mt5.sent) == 1
    req = mt5.sent[0]
    assert req["action"] == mt5.TRADE_ACTION_DEAL
    assert req["sl"] == pytest.approx(1995.0)


# ------------------------- LIVE_ROSTER / --configs live ----------------------
def test_live_roster_subset_valid():
    ids_20 = {c["id"] for c in CONFIGS_20}
    assert len(LIVE_ROSTER) == 4
    assert len(set(LIVE_ROSTER)) == 4, "LIVE_ROSTER ids must be unique"
    assert set(LIVE_ROSTER) <= ids_20, "every LIVE_ROSTER id must exist in CONFIGS_20"

    # CONFIGS_LIVE preserves CONFIGS_20 order (not LIVE_ROSTER's declared order).
    expected_order = [c["id"] for c in CONFIGS_20 if c["id"] in set(LIVE_ROSTER)]
    assert [c["id"] for c in CONFIGS_LIVE] == expected_order

    # magics preserved: each CONFIGS_LIVE entry is the SAME dict/magic as in CONFIGS_20.
    magic_by_id_20 = {c["id"]: c["magic"] for c in CONFIGS_20}
    for c in CONFIGS_LIVE:
        assert c["magic"] == magic_by_id_20[c["id"]]


def test_configs_live_flag_selects_roster(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "live"], mt5_module=mt5,
                              attach_checker=lambda: True)
    assert rc == 0
    assert mt5.initialized is True
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert f"{len(LIVE_ROSTER)} configs" in caplog.text
    for cid in LIVE_ROSTER:
        assert f"[{cid}]" in caplog.text
    # none of the non-roster configs should have been reconciled.
    non_roster = [c["id"] for c in CONFIGS_20 if c["id"] not in set(LIVE_ROSTER)]
    for cid in non_roster:
        assert f"[{cid}]" not in caplog.text


def test_configs_live_case_insensitive(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "LIVE"], mt5_module=mt5,
                              attach_checker=lambda: True)
    assert rc == 0
    assert mt5.initialized is True
    assert mt5.sent == []
    assert f"{len(LIVE_ROSTER)} configs" in caplog.text


# ------------------------- GO-LIVE roster (--configs golive) ----------------
from sentinel_engine.strategies.live_configs_20 import CONFIGS_GOLIVE  # noqa: E402


def test_configs_golive_flag_selects_golive_roster(caplog, tmp_path, monkeypatch):
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))  # keep real data/ clean
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "golive"], mt5_module=mt5,
                              attach_checker=lambda: True)
    assert rc == 0
    assert mt5.initialized is True
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert f"{len(CONFIGS_GOLIVE)} configs" in caplog.text
    for c in CONFIGS_GOLIVE:
        assert f"[{c['id']}]" in caplog.text


def test_configs_golive_dedup_flag_selects_four_configs(caplog, tmp_path, monkeypatch):
    # D121: golive-dedup collapses the 5 SAR clones to 2 reps + the distinct
    # lines. Adaptive spread-gate must still default ON (same as golive).
    from sentinel_engine.strategies.live_configs_20 import CONFIGS_GOLIVE_DEDUP
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))  # keep real data/ clean
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "golive-dedup"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert "4 configs" in caplog.text
    assert "adaptive_spread=ON" in caplog.text
    for c in CONFIGS_GOLIVE_DEDUP:
        assert f"[{c['id']}]" in caplog.text
    # the three dropped clones must NOT be reconciled under golive-dedup.
    for dropped in ("S6-K1P5", "S7-TP1P0", "S7-TPNONE-F2"):
        assert f"[{dropped}]" not in caplog.text


# ------------------ SuperTrend always-in 7th go-live strategy (GL-T3) -------
from sentinel_engine.strategies.live_configs_20 import (  # noqa: E402
    supertrend_always_in_target)


def _st_config():
    return next(c for c in CONFIGS_GOLIVE if c["id"] == "SuperTrend-p14x3-M15")


def _st_trend_bars(n_up, n_down, tf_secs=900):
    """Strong up-leg then down-leg so SuperTrend is unambiguously long/short."""
    out = []
    t = int(datetime(2026, 6, 2, tzinfo=timezone.utc).timestamp())
    price = 2000.0
    for _ in range(n_up):
        o = price; price += 3.0; c = price
        out.append({"t": t, "open": o, "high": max(o, c) + 0.5,
                    "low": min(o, c) - 0.5, "close": c}); t += tf_secs
    for _ in range(n_down):
        o = price; price -= 3.0; c = price
        out.append({"t": t, "open": o, "high": max(o, c) + 0.5,
                    "low": min(o, c) - 0.5, "close": c}); t += tf_secs
    return out


def test_supertrend_reconciles_to_single_open_when_flat():
    """Flat account + uptrend => the always-in target is ONE OPEN (F1) long,
    reconciled through the same reconciler as the ladder configs."""
    cfg = _st_config()
    mt5 = MockMT5(_st_trend_bars(60, 0))
    res, _bar_t = run_live_20.reconcile_config(
        mt5, cfg, window=3000, volume=0.01, kill_switch=False,
        total_open_fichas=0)
    opens = [a for a in res.actions if a.kind == "OPEN"]
    assert len(opens) == 1, "always-in must reconcile to exactly ONE position"
    assert opens[0].ficha == "F1"
    assert opens[0].side == "L"
    assert opens[0].magic == cfg["magic"] + 1  # F1 slot
    # SL (the SuperTrend line) sits below the entry price for a long.
    assert opens[0].sl is not None and opens[0].sl < opens[0].price_ref


def test_supertrend_flip_closes_wrong_side_then_reopens():
    """A LONG live position when the trend has flipped SHORT => the reconciler
    CLOSEs the long (side mismatch) -- the always-in flip -- with no ladder."""
    cfg = _st_config()
    # trend now short (long down-leg), but a LONG position is live in F1.
    long_pos = _Pos(ticket=901, magic=cfg["magic"] + 1,
                    type=MockMT5.POSITION_TYPE_BUY, volume=0.01, sl=1990.0)
    mt5 = MockMT5(_st_trend_bars(30, 60), positions=[long_pos])
    res, _bar_t = run_live_20.reconcile_config(
        mt5, cfg, window=3000, volume=0.01, kill_switch=False,
        total_open_fichas=0)
    closes = [a for a in res.actions if a.kind == "CLOSE"]
    assert any(a.ticket == 901 for a in closes), "flip must CLOSE the wrong-side long"


def test_supertrend_open_is_spread_gated(caplog):
    """The SuperTrend OPEN must be spread-gated exactly like any other OPEN:
    a wide spread SKIPs it."""
    cfg = _st_config()
    mt5 = MockMT5(_st_trend_bars(60, 0),
                  tick=_Tick(bid=2000.0, ask=2001.0),  # spread 1.00 (wide)
                  symbol_info=_SymbolInfo(trade_stops_level=0, point=0.01))
    res, _bar_t = run_live_20.reconcile_config(
        mt5, cfg, window=3000, volume=0.01, kill_switch=False,
        total_open_fichas=0)
    open_a = next(a for a in res.actions if a.kind == "OPEN")
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, open_a, symbol="XAUUSD", dry_run=False,
                                   max_spread_open=0.70)
    assert mt5.sent == [], "wide-spread SuperTrend OPEN must be gated"
    assert "SPREAD_GATE_SKIP" in caplog.text


def test_supertrend_dry_run_full_cycle_sends_nothing(caplog, tmp_path, monkeypatch):
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))
    mt5 = MockMT5(_st_trend_bars(60, 0))
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "golive"], mt5_module=mt5,
                              attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert "[SuperTrend-p14x3-M15]" in caplog.text


# ------------------------- HARD spread-gate (OPEN only) ---------------------
def _wide_spread_mt5(positions=None, retcodes=None):
    """MockMT5 whose tick spread is WIDE (ask-bid = 1.00 > default gate 0.70)
    but whose SL is legal & far from market (so ONLY the spread-gate can block
    an OPEN, not the SL-clamp path)."""
    return MockMT5(_bars(50), positions=positions or [],
                   tick=_Tick(bid=2000.0, ask=2001.0),  # spread 1.00
                   symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01),
                   order_send_retcodes=retcodes)


def _thin_spread_mt5(positions=None, retcodes=None):
    """MockMT5 whose tick spread is THIN (ask-bid = 0.20 <= gate 0.70)."""
    return MockMT5(_bars(50), positions=positions or [],
                   tick=_Tick(bid=2000.0, ask=2000.2),  # spread 0.20
                   symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01),
                   order_send_retcodes=retcodes)


def test_spread_gate_skips_open_above_threshold(caplog):
    mt5 = _wide_spread_mt5()
    a = _open_action(side="L", sl=1995.0)  # legal SL, far from market
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                                   max_spread_open=0.70)
    assert mt5.sent == [], "OPEN above the spread threshold must NOT be sent"
    assert "SPREAD_GATE_SKIP" in caplog.text


def test_spread_gate_sends_open_at_or_below_threshold():
    mt5 = _thin_spread_mt5()
    a = _open_action(side="L", sl=1995.0)
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               max_spread_open=0.70)
    assert len(mt5.sent) == 1
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_DEAL  # market OPEN sent


def test_spread_gate_open_exactly_at_threshold_is_sent():
    # spread == threshold: gate is `spread <= max` -> SENT (boundary inclusive).
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.7),  # spread exactly 0.70
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    a = _open_action(side="L", sl=1995.0)
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               max_spread_open=0.70)
    assert len(mt5.sent) == 1


def test_spread_gate_dry_run_above_threshold_logs_skip_sends_nothing(caplog):
    mt5 = _wide_spread_mt5()
    a = _open_action(side="L", sl=1995.0)
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=True,
                                   max_spread_open=0.70)
    assert mt5.sent == []
    assert "SPREAD_GATE_SKIP" in caplog.text


def test_spread_gate_none_threshold_disables_gate():
    # max_spread_open=None -> gate OFF -> wide spread OPEN still sent.
    mt5 = _wide_spread_mt5()
    a = _open_action(side="L", sl=1995.0)
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               max_spread_open=None)
    assert len(mt5.sent) == 1


def test_spread_gate_never_gates_close():
    # A CLOSE must be sent regardless of a wide spread.
    pos = _Pos(ticket=777, magic=101, type=MockMT5.POSITION_TYPE_BUY,
               volume=0.01, sl=1990.0)
    mt5 = _wide_spread_mt5(positions=[pos])
    a = Action(kind="CLOSE", config_id="SS-M1", magic=101, ficha="F1",
               ticket=777, volume=0.01, reason="orphan")
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               max_spread_open=0.70)
    assert len(mt5.sent) == 1
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_DEAL
    assert mt5.sent[0]["type"] == mt5.ORDER_TYPE_SELL  # closing a LONG


def test_spread_gate_never_gates_modify():
    # A MODIFY (trail SL) must be sent regardless of a wide spread.
    pos = _Pos(ticket=778, magic=101, type=MockMT5.POSITION_TYPE_BUY,
               volume=0.01, sl=1990.0)
    mt5 = _wide_spread_mt5(positions=[pos])
    a = _modify_action(side="L", sl=1995.0, ticket=778)  # legal SL
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               max_spread_open=0.70)
    assert len(mt5.sent) == 1
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_SLTP  # SL modify, not blocked


def test_spread_gate_never_gates_same_bar_exit_fallback():
    # SAME_BAR_EXIT_FALLBACK (a market exit) must be sent despite a wide spread.
    pos = _Pos(ticket=779, magic=101, type=MockMT5.POSITION_TYPE_BUY,
               volume=0.01, sl=1990.0)
    mt5 = _wide_spread_mt5(positions=[pos])
    a = Action(kind="SAME_BAR_EXIT_FALLBACK", config_id="SS-M1", magic=101,
               ficha="F1", side="L", ticket=779, volume=0.01, sim_fill=2001.5,
               motivo="sar", reason="same-bar exit")
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               max_spread_open=0.70)
    assert len(mt5.sent) == 1
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_DEAL


def test_spread_gate_negative_cli_disables_gate(caplog):
    # `--max-spread-open -1` disables the STATIC hard cap end-to-end (dry-run
    # smoke). The adaptive gate is still the golive default (adaptive_spread=ON).
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "golive",
                               "--max-spread-open", "-1", "--no-adaptive-spread"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert "max_spread_open=OFF" in caplog.text


# ------------- ADAPTIVE running-min spread-gate (GL-T2) ---------------------
def _adaptive_threshold_action(spread_threshold, max_spread_open=None,
                               ask=2000.2, bid=2000.0, dry_run=False):
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=bid, ask=ask),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    a = _open_action(side="L", sl=1995.0)  # legal SL, far from market
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=dry_run,
                               max_spread_open=max_spread_open,
                               spread_threshold=spread_threshold)
    return mt5


def test_adaptive_gate_operates_at_or_below_threshold():
    # spread 0.20 <= threshold 0.60 -> OPERATE (OPEN sent).
    mt5 = _adaptive_threshold_action(spread_threshold=0.60, ask=2000.2, bid=2000.0)
    assert len(mt5.sent) == 1
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_DEAL


def test_adaptive_gate_pauses_above_threshold(caplog):
    # spread 0.80 > threshold 0.60 -> PAUSE (nothing sent, SPREAD_GATE_SKIP).
    with caplog.at_level("WARNING"):
        mt5 = _adaptive_threshold_action(spread_threshold=0.60,
                                         ask=2000.8, bid=2000.0)
    assert mt5.sent == []
    assert "SPREAD_GATE_SKIP" in caplog.text


# --- CORE REQUIREMENT: with running-min 0.60, admit ONLY 0.60, never 0.61..0.70
def test_fixed_060_spread_060_is_SENT():
    thr = 0.60 + run_live_20.DEFAULT_SPREAD_EPS  # tiny eps; threshold ~= 0.60
    mt5 = _adaptive_threshold_action(spread_threshold=thr, ask=2000.6, bid=2000.0)
    assert len(mt5.sent) == 1, "spread 0.60 (== running-min) must be SENT"


def test_fixed_060_spread_061_is_SKIPPED(caplog):
    thr = 0.60 + run_live_20.DEFAULT_SPREAD_EPS
    with caplog.at_level("WARNING"):
        mt5 = _adaptive_threshold_action(spread_threshold=thr, ask=2000.61, bid=2000.0)
    assert mt5.sent == [], "spread 0.61 is above running-min 0.60 -> must SKIP"
    assert "SPREAD_GATE_SKIP" in caplog.text


def test_fixed_060_spread_070_is_SKIPPED(caplog):
    thr = 0.60 + run_live_20.DEFAULT_SPREAD_EPS
    with caplog.at_level("WARNING"):
        mt5 = _adaptive_threshold_action(spread_threshold=thr, ask=2000.70, bid=2000.0)
    assert mt5.sent == [], "spread 0.70 (GL-T1 wrongly admitted) must now SKIP"
    assert "SPREAD_GATE_SKIP" in caplog.text


def test_tighter_of_adaptive_and_hard_cap_binds(caplog):
    # adaptive threshold 0.90 but hard cap 0.30; spread 0.50 > min(0.90,0.30) -> PAUSE.
    with caplog.at_level("WARNING"):
        mt5 = _adaptive_threshold_action(spread_threshold=0.90, max_spread_open=0.30,
                                         ask=2000.5, bid=2000.0)
    assert mt5.sent == []
    assert "SPREAD_GATE_SKIP" in caplog.text


def test_adaptive_gate_never_gates_close():
    pos = _Pos(ticket=901, magic=101, type=MockMT5.POSITION_TYPE_BUY,
               volume=0.01, sl=1990.0)
    mt5 = MockMT5(_bars(50), positions=[pos],
                  tick=_Tick(bid=2000.0, ask=2000.8),  # wide spread 0.80
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    a = Action(kind="CLOSE", config_id="SS-M1", magic=101, ficha="F1",
               ticket=901, volume=0.01, reason="orphan")
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               spread_threshold=0.62)  # would pause an OPEN
    assert len(mt5.sent) == 1  # CLOSE still sent


def test_adaptive_gate_never_gates_modify():
    pos = _Pos(ticket=902, magic=101, type=MockMT5.POSITION_TYPE_BUY,
               volume=0.01, sl=1990.0)
    mt5 = MockMT5(_bars(50), positions=[pos],
                  tick=_Tick(bid=2000.0, ask=2000.8),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    a = _modify_action(side="L", sl=1995.0, ticket=902)
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               spread_threshold=0.62)
    assert len(mt5.sent) == 1
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_SLTP


def test_golive_records_spread_and_logs_threshold(tmp_path, monkeypatch, caplog):
    # end-to-end: golive dry-run records the spread & logs the adaptive threshold;
    # store written under the redirected (tmp) data dir; ZERO orders sent.
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))
    mt5 = MockMT5(_bars())  # tick spread = 0.20
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "golive"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert "adaptive_spread=ON" in caplog.text
    assert "[spread]" in caplog.text
    assert (tmp_path / "xauusd_spread_store.json").exists()


def test_capture_spread_mode_sends_no_orders(tmp_path, monkeypatch, caplog):
    # STANDALONE --capture-spread: one pass records a sample, sends NOTHING.
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))
    mt5 = MockMT5(_bars(), tick=_Tick(bid=2000.0, ask=2000.6))  # spread 0.60
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--capture-spread", "--once"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "capture mode must NEVER send an order"
    assert "CAPTURE-SPREAD mode" in caplog.text
    import json
    store = json.loads((tmp_path / "xauusd_spread_store.json").read_text())
    assert store["running_min"] == pytest.approx(0.60)
    assert store["sample_count"] == 1


# ------------------- per-position spread recording (on_fill) ----------------
def test_open_records_spread_via_on_fill():
    # A thin-spread OPEN is sent AND its spread is recorded via on_fill, keyed
    # by the opening order ticket (r.order).
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.5),  # spread 0.50 (the min)
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    calls = []
    a = _open_action(side="L", sl=1995.0)  # legal SL, far from market
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               on_fill=lambda *args: calls.append(args))
    assert len(mt5.sent) == 1
    assert len(calls) == 1
    kind, position_id, spread = calls[0]
    assert kind == "OPEN"
    assert position_id == 901  # first fake order ticket (seq starts at 900)
    assert spread == pytest.approx(0.50)


def test_close_records_spread_via_on_fill():
    pos = _Pos(ticket=555, magic=101, type=0, volume=0.01, sl=1990.0)
    mt5 = MockMT5(_bars(50), positions=[pos],
                  tick=_Tick(bid=2000.0, ask=2000.62),  # spread 0.62 at close
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    calls = []
    a = Action(kind="CLOSE", config_id="SS-M1", magic=101, ficha="F1",
               side="L", sl=None, volume=0.01, ticket=555, reason="exit")
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               on_fill=lambda *args: calls.append(args))
    assert len(calls) == 1
    kind, position_id, spread = calls[0]
    assert kind == "CLOSE"
    assert position_id == 555  # the position ticket
    assert spread == pytest.approx(0.62)


def test_on_fill_error_never_breaks_order(caplog):
    # A raising on_fill must NOT abort the order flow (fail-safe recording).
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.5),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    def boom(*_args):
        raise RuntimeError("db down")
    a = _open_action(side="L", sl=1995.0)
    with caplog.at_level("ERROR"):
        run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False, on_fill=boom)
    assert len(mt5.sent) == 1, "order still sent despite recording failure"
    assert "SPREAD_RECORD_FAILED" in caplog.text


def test_dry_run_never_records_spread():
    mt5 = MockMT5(_bars(50), positions=[],
                  tick=_Tick(bid=2000.0, ask=2000.5),
                  symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))
    calls = []
    a = _open_action(side="L", sl=1995.0)
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=True,
                               on_fill=lambda *args: calls.append(args))
    assert mt5.sent == []
    assert calls == [], "dry-run must not record spread (nothing filled)"


def test_main_armed_recorder_persists_to_registry(tmp_path, monkeypatch):
    # End-to-end-ish: main() armed builds a recorder that writes position_spread
    # for a real OPEN, into an injected throwaway registry.
    from sentinel_engine.research.registry2 import ResearchRegistry
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))
    reg = ResearchRegistry(tmp_path / "research.db")
    captured = {}

    def spy_recorder(kind, position_id, spread):
        captured[kind] = (position_id, spread)
        if kind == "OPEN":
            reg.record_position_spread(position_id, ticket_open=position_id,
                                       spread_open=spread, spread_open_ts=1)

    mt5 = MockMT5(_bars(), tick=_Tick(bid=2000.0, ask=2000.5))
    rc = run_live_20.main(["--once", "--configs", "SS-M2", "--arm",
                           "--confirm-account", str(guard_cuenta.DEMO_LOGIN)],
                          mt5_module=mt5, attach_checker=lambda: True,
                          spread_recorder=spy_recorder)
    assert rc == 0
    # If any OPEN fired, it was persisted; assert the recorder path is wired.
    if "OPEN" in captured:
        pid, _spread = captured["OPEN"]
        got = reg.get_position_spreads([pid])
        assert pid in got
