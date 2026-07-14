"""tests/live/test_deals_watcher.py — TDD for DealsWatcher (B1a-1 + B1a-2).

Covers: attach-guard skip (never calls MT5 client when terminal64.exe is
absent), idempotent upsert into `deals_raw` by ticket, correct field
mapping from a stub `mt5_client.history_deals_get(...)`, magic-based
attribution (strategy/ia/human, B1a-2), and `last_sync` persistence across
watcher restarts (B1a-2).

Also covers the self-heal reconnect logic added to the standalone runner
`scripts/live/run_deals_watcher.py` (`_connection_healthy`, `_reconnect`,
and `main()`'s self-heal integration) -- fully offline via stub `mt5`
modules, never a real `MetaTrader5` import.
"""
from __future__ import annotations

import sqlite3

import pytest

from scripts.live import run_deals_watcher as rdw
from sentinel_engine.live import guard_cuenta
from sentinel_engine.live.deals_watcher import DealsWatcher, WatchReport
from sentinel_engine.research.registry2 import ResearchRegistry


class _StubMt5Client:
    """Fixed list of deal dicts, shaped like MT5 `history_deals_get` (as a
    tuple of namedtuple-ish objects in real MT5 -- here plain dicts per the
    task spec, since the watcher maps dict keys)."""

    def __init__(self, deals):
        self._deals = deals
        self.calls = 0

    def history_deals_get(self, from_ts, to_ts):
        self.calls += 1
        return list(self._deals)


_SAMPLE_DEALS = [
    {
        "ticket": 1001,
        "position_id": 5001,
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": 0.1,
        "price": 2400.5,
        "profit": 12.3,
        "magic": 100123,
        "time": 1750000000,
        "entry_type": "IN",
    },
    {
        "ticket": 1002,
        "position_id": 5001,
        "symbol": "XAUUSD",
        "side": "SELL",
        "volume": 0.1,
        "price": 2405.0,
        "profit": -1.0,
        "magic": 100123,
        "time": 1750000100,
        "entry_type": "OUT",
    },
]


@pytest.fixture
def reg(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


def _always_attached() -> bool:
    return True


def _never_attached() -> bool:
    return False


def test_attach_guard_skips_when_terminal_not_running(reg):
    client = _StubMt5Client(_SAMPLE_DEALS)
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_never_attached)

    report = watcher.poll_once()

    assert isinstance(report, WatchReport)
    assert report.attached is False
    assert report.skipped is True
    assert report.deals_seen == 0
    assert report.upserted == 0
    assert client.calls == 0


def test_poll_once_upserts_deals_when_attached(reg):
    client = _StubMt5Client(_SAMPLE_DEALS)
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)

    report = watcher.poll_once()

    assert report.attached is True
    assert report.skipped is False
    assert report.deals_seen == 2
    assert report.upserted == 2
    assert client.calls == 1

    conn = sqlite3.connect(str(reg.db_path))
    try:
        rows = conn.execute("SELECT COUNT(*) FROM deals_raw").fetchone()
        assert rows[0] == 2
    finally:
        conn.close()


def test_poll_once_is_idempotent_on_repeated_deals(reg):
    client = _StubMt5Client(_SAMPLE_DEALS)
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)

    watcher.poll_once()
    second_report = watcher.poll_once()

    assert second_report.deals_seen == 2
    assert second_report.upserted == 2

    conn = sqlite3.connect(str(reg.db_path))
    try:
        count = conn.execute("SELECT COUNT(*) FROM deals_raw").fetchone()[0]
        assert count == 2
    finally:
        conn.close()


def test_deal_fields_are_mapped_correctly(reg):
    client = _StubMt5Client(_SAMPLE_DEALS)
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)

    watcher.poll_once()

    conn = sqlite3.connect(str(reg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM deals_raw WHERE ticket=?", (1001,)
        ).fetchone()
        assert row is not None
        d = dict(row)
        assert d["ticket"] == 1001
        assert d["position_id"] == 5001
        assert d["symbol"] == "XAUUSD"
        assert d["side"] == "BUY"
        assert d["volume"] == 0.1
        assert d["price"] == 2400.5
        assert d["profit"] == 12.3
        assert d["magic"] == 100123
        assert d["time"] == 1750000000
        assert d["entry_type"] == "IN"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1a-2: magic attribution matrix
# ---------------------------------------------------------------------------

def test_attribution_strategy_when_magic_is_allocated(reg):
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "V1", {}, "M5", "XAUUSD", "original")
    magic = reg.allocate_magic(sid, vid)  # 100000 (strategy_seq=0, variant_seq=0)

    deal = dict(_SAMPLE_DEALS[0])
    deal["ticket"] = 2001
    deal["magic"] = magic
    client = _StubMt5Client([deal])
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)

    watcher.poll_once()

    conn = sqlite3.connect(str(reg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM deals_raw WHERE ticket=?", (2001,)).fetchone()
        d = dict(row)
        assert d["origin"] == "strategy"
        assert d["strategy_id"] == sid
        assert d["variant_id"] == vid
    finally:
        conn.close()


def test_attribution_ia_when_magic_in_ia_range_and_unallocated(reg):
    deal = dict(_SAMPLE_DEALS[0])
    deal["ticket"] = 2002
    deal["magic"] = 900500
    client = _StubMt5Client([deal])
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)

    watcher.poll_once()

    conn = sqlite3.connect(str(reg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM deals_raw WHERE ticket=?", (2002,)).fetchone()
        d = dict(row)
        assert d["origin"] == "ia"
        assert d["strategy_id"] is None
        assert d["variant_id"] is None
    finally:
        conn.close()


def test_attribution_human_when_magic_unassigned_and_outside_ia_range(reg):
    deal = dict(_SAMPLE_DEALS[0])
    deal["ticket"] = 2003
    deal["magic"] = 12345
    client = _StubMt5Client([deal])
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)

    watcher.poll_once()

    conn = sqlite3.connect(str(reg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM deals_raw WHERE ticket=?", (2003,)).fetchone()
        d = dict(row)
        assert d["origin"] == "human"
        assert d["strategy_id"] is None
        assert d["variant_id"] is None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1a-2: last_sync persistence across restarts
# ---------------------------------------------------------------------------

def test_last_sync_persists_across_watcher_restart(reg):
    client = _StubMt5Client(_SAMPLE_DEALS)
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)
    assert watcher.last_sync == 0.0

    watcher.poll_once()
    assert watcher.last_sync > 0.0
    persisted_value = watcher.last_sync

    # A brand-new watcher built on the SAME registry must resume from the
    # persisted last_sync, not restart at 0.0.
    client2 = _StubMt5Client(_SAMPLE_DEALS)
    watcher2 = DealsWatcher(reg, client2, poll_s=5, attach_checker=_always_attached)
    assert watcher2.last_sync == persisted_value


def test_last_sync_defaults_to_zero_on_fresh_registry(reg):
    client = _StubMt5Client(_SAMPLE_DEALS)
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)
    assert watcher.last_sync == 0.0


# ---------------------------------------------------------------------------
# B1c: leverage + contract_size capture (pct = profit/margin inputs)
# ---------------------------------------------------------------------------

class _AccountInfo:
    def __init__(self, leverage):
        self.leverage = leverage


class _SymbolInfo:
    def __init__(self, trade_contract_size):
        self.trade_contract_size = trade_contract_size


class _StubMt5ClientWithLeverage(_StubMt5Client):
    """Adds account_info()/symbol_info(sym) per B1c spec."""

    def __init__(self, deals, leverage=100, contract_sizes=None):
        super().__init__(deals)
        self._leverage = leverage
        self._contract_sizes = contract_sizes or {}
        self.symbol_info_calls = []

    def account_info(self):
        return _AccountInfo(self._leverage)

    def symbol_info(self, symbol):
        self.symbol_info_calls.append(symbol)
        size = self._contract_sizes.get(symbol)
        if size is None:
            return None
        return _SymbolInfo(size)


def test_leverage_and_contract_size_populated_when_client_supports_them(reg):
    client = _StubMt5ClientWithLeverage(
        _SAMPLE_DEALS, leverage=200, contract_sizes={"XAUUSD": 100.0}
    )
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)

    watcher.poll_once()

    conn = sqlite3.connect(str(reg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM deals_raw WHERE ticket=?", (1001,)).fetchone()
        d = dict(row)
        assert d["leverage"] == 200
        assert d["contract_size"] == 100.0
    finally:
        conn.close()

    # symbol_info cached once per distinct symbol in the batch (both sample
    # deals share "XAUUSD").
    assert client.symbol_info_calls == ["XAUUSD"]


def test_leverage_and_contract_size_null_when_client_lacks_methods(reg):
    client = _StubMt5Client(_SAMPLE_DEALS)  # old-style stub: no account_info/symbol_info
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)

    report = watcher.poll_once()

    assert report.upserted == 2  # no crash

    conn = sqlite3.connect(str(reg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM deals_raw WHERE ticket=?", (1001,)).fetchone()
        d = dict(row)
        assert d["leverage"] is None
        assert d["contract_size"] is None
    finally:
        conn.close()


def test_leverage_and_contract_size_idempotent_on_repeated_poll(reg):
    client = _StubMt5ClientWithLeverage(
        _SAMPLE_DEALS, leverage=500, contract_sizes={"XAUUSD": 100.0}
    )
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)

    watcher.poll_once()
    second_report = watcher.poll_once()

    assert second_report.upserted == 2

    conn = sqlite3.connect(str(reg.db_path))
    try:
        count = conn.execute("SELECT COUNT(*) FROM deals_raw").fetchone()[0]
        assert count == 2
    finally:
        conn.close()


def test_reupsert_with_null_leverage_preserves_previous_values(reg):
    """REV-4 Fix 4: a re-poll over the overlap window whose account_info/
    symbol_info transiently fail (-> None leverage/contract_size) must NOT
    wipe the good values captured on the first poll -- COALESCE keeps them."""
    good_client = _StubMt5ClientWithLeverage(
        _SAMPLE_DEALS, leverage=200, contract_sizes={"XAUUSD": 100.0}
    )
    watcher = DealsWatcher(reg, good_client, poll_s=5, attach_checker=_always_attached)
    watcher.poll_once()

    # Same tickets again, but now the client can't provide leverage/
    # contract_size (old-style stub with neither method).
    degraded_client = _StubMt5Client(_SAMPLE_DEALS)
    watcher2 = DealsWatcher(reg, degraded_client, poll_s=5, attach_checker=_always_attached)
    report = watcher2.poll_once()
    assert report.upserted == 2

    conn = sqlite3.connect(str(reg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        for ticket in (1001, 1002):
            row = conn.execute(
                "SELECT * FROM deals_raw WHERE ticket=?", (ticket,)
            ).fetchone()
            d = dict(row)
            assert d["leverage"] == 200, f"ticket {ticket}: leverage wiped"
            assert d["contract_size"] == 100.0, f"ticket {ticket}: contract_size wiped"
    finally:
        conn.close()


def test_reupsert_updates_other_fields_with_new_values(reg):
    """Non-leverage/contract_size columns still take the NEW value on
    conflict (INSERT OR REPLACE semantics preserved for them)."""
    client = _StubMt5ClientWithLeverage(
        _SAMPLE_DEALS, leverage=200, contract_sizes={"XAUUSD": 100.0}
    )
    watcher = DealsWatcher(reg, client, poll_s=5, attach_checker=_always_attached)
    watcher.poll_once()

    updated = [dict(d) for d in _SAMPLE_DEALS]
    updated[0]["profit"] = 99.9
    client2 = _StubMt5ClientWithLeverage(
        updated, leverage=300, contract_sizes={"XAUUSD": 100.0}
    )
    watcher2 = DealsWatcher(reg, client2, poll_s=5, attach_checker=_always_attached)
    watcher2.poll_once()

    conn = sqlite3.connect(str(reg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        d = dict(conn.execute("SELECT * FROM deals_raw WHERE ticket=?", (1001,)).fetchone())
        assert d["profit"] == 99.9
        assert d["leverage"] == 300  # new non-null value wins
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Self-heal reconnect: `scripts/live/run_deals_watcher.py`
# `_connection_healthy` / `_reconnect` / `main()` integration.
# ---------------------------------------------------------------------------

_WRONG_LOGIN = 999


class _AccountInfoLogin:
    def __init__(self, login):
        self.login = login


class _HealthMt5Stub:
    """Minimal stub mt5 module for `_connection_healthy`/`_reconnect` unit
    tests -- not a full runner stub (see `_RunnerMt5Stub` below for `main()`
    integration tests)."""

    def __init__(self, account_info_fn=None, initialize_results=None,
                 raise_on_account_info=False):
        self._account_info_fn = account_info_fn
        self._initialize_results = list(initialize_results or [])
        self._raise_on_account_info = raise_on_account_info
        self.initialize_calls = 0
        self.shutdown_calls = 0

    def account_info(self):
        if self._raise_on_account_info:
            raise RuntimeError("simulated IPC failure")
        if self._account_info_fn is None:
            return None
        return self._account_info_fn()

    def initialize(self, path=None, portable=None):
        self.initialize_calls += 1
        if self._initialize_results:
            return self._initialize_results.pop(0)
        return True

    def shutdown(self):
        self.shutdown_calls += 1

    def last_error(self):
        return (0, "ok")


def test_connection_healthy_states():
    # account_info() returns None -> unhealthy, "no_info".
    mt5_none = _HealthMt5Stub(account_info_fn=lambda: None)
    assert rdw._connection_healthy(mt5_none) == (False, "no_info")

    # account_info() raises -> unhealthy, "no_info".
    mt5_raises = _HealthMt5Stub(raise_on_account_info=True)
    assert rdw._connection_healthy(mt5_raises) == (False, "no_info")

    # account_info() reports the wrong login -> unhealthy, "wrong_login".
    mt5_wrong = _HealthMt5Stub(account_info_fn=lambda: _AccountInfoLogin(_WRONG_LOGIN))
    assert rdw._connection_healthy(mt5_wrong) == (False, "wrong_login")

    # account_info() reports the sanctioned DEMO login -> healthy.
    mt5_ok = _HealthMt5Stub(account_info_fn=lambda: _AccountInfoLogin(guard_cuenta.DEMO_LOGIN))
    assert rdw._connection_healthy(mt5_ok) == (True, "ok")


def test_reconnect_success_after_one_failure():
    mt5 = _HealthMt5Stub(
        account_info_fn=lambda: _AccountInfoLogin(guard_cuenta.DEMO_LOGIN),
        initialize_results=[False, True],
    )
    sleeps = []

    result = rdw._reconnect(
        mt5, attach_checker=lambda: True, sleep_fn=lambda s: sleeps.append(s))

    assert result is True
    assert mt5.initialize_calls == 2
    assert sleeps == [5.0]


def test_reconnect_never_launches_when_terminal_gone():
    mt5 = _HealthMt5Stub(account_info_fn=lambda: _AccountInfoLogin(guard_cuenta.DEMO_LOGIN))
    sleeps = []

    result = rdw._reconnect(
        mt5, attach_checker=lambda: False, sleep_fn=lambda s: sleeps.append(s))

    assert result is False
    assert mt5.initialize_calls == 0
    assert mt5.shutdown_calls == 1  # shutdown() attempted before the check
    assert sleeps == []


def test_reconnect_wrong_login_aborts():
    mt5 = _HealthMt5Stub(
        account_info_fn=lambda: _AccountInfoLogin(_WRONG_LOGIN),
        initialize_results=[True],
    )
    sleeps = []

    result = rdw._reconnect(
        mt5, attach_checker=lambda: True, sleep_fn=lambda s: sleeps.append(s))

    assert result is False
    assert mt5.initialize_calls == 1
    assert sleeps == []


# ---------------------------------------------------------------------------
# `main()` self-heal integration -- reuses the runner-level fake mt5 module
# shape from tests/scripts/test_run_deals_watcher.py (account_info,
# history_deals_get, initialize, shutdown, last_error).
# ---------------------------------------------------------------------------

class _RunnerFakeDeal:
    def __init__(self, ticket, position_id, symbol, side, volume, price,
                 profit, magic, time, entry):
        self.ticket = ticket
        self.position_id = position_id
        self.symbol = symbol
        self.type = 0 if side == "BUY" else 1
        self.volume = volume
        self.price = price
        self.profit = profit
        self.magic = magic
        self.time = time
        self.entry = entry


_RUNNER_SAMPLE_DEALS = [
    _RunnerFakeDeal(1001, 5001, "XAUUSD", "BUY", 0.1, 2400.5, 12.3, 100123, 1750000000, 0),
]


class _RunnerMt5Stub:
    """Fake `MetaTrader5` module for `main()` self-heal integration tests.
    `account_info()` calls are counted; the caller supplies a list of
    logins to report on successive calls (last value repeats once
    exhausted) so the FIRST loop health check can report unhealthy
    ("no_info" via None) while startup's `_check_login` (the very first
    call) still passes."""

    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def __init__(self, account_info_sequence):
        self._sequence = list(account_info_sequence)
        self.account_info_calls = 0
        self.initialize_calls = 0
        self.shutdown_calls = 0
        self.history_calls = 0

    def _next_login(self):
        if self._sequence:
            value = self._sequence.pop(0)
        else:
            value = self._sequence[-1] if self._sequence else guard_cuenta.DEMO_LOGIN
        return value

    def account_info(self):
        self.account_info_calls += 1
        value = self._next_login()
        if value is None:
            return None
        return _AccountInfoLogin(value)

    def initialize(self, path=None, portable=None):
        self.initialize_calls += 1
        return True

    def last_error(self):
        return (0, "ok")

    def history_deals_get(self, from_ts, to_ts):
        self.history_calls += 1
        return list(_RUNNER_SAMPLE_DEALS)

    def symbol_info(self, symbol):
        return None

    def shutdown(self):
        self.shutdown_calls += 1


class _RecordingWatcher:
    """Stub `DealsWatcher` replacement recording how many times
    `poll_once()` ran, without touching real DealsWatcher internals."""

    def __init__(self, registry, mt5_client, poll_s=5, attach_checker=None):
        self.mt5_client = mt5_client
        self.poll_calls = 0

    def poll_once(self):
        self.poll_calls += 1
        return WatchReport(attached=True, deals_seen=1, upserted=1, skipped=False)


def test_main_self_heals_then_polls(tmp_path):
    # Sequence of account_info() logins:
    #   1) _check_login() at startup -> DEMO_LOGIN (passes)
    #   2) loop health check #1 -> None ("no_info" -> unhealthy)
    #   3) _reconnect()'s post-initialize health check -> DEMO_LOGIN (heals)
    #   4) loop health check #2 (next iteration, but --once already broke)
    mt5 = _RunnerMt5Stub([guard_cuenta.DEMO_LOGIN, None, guard_cuenta.DEMO_LOGIN])
    watchers = []

    def watcher_factory(registry, client, poll_s=5, attach_checker=None):
        w = _RecordingWatcher(registry, client, poll_s=poll_s, attach_checker=attach_checker)
        watchers.append(w)
        return w

    rc = rdw.main(
        ["--db", str(tmp_path / "t.db"), "--once"],
        mt5_module=mt5, attach_checker=lambda: True,
        watcher_factory=watcher_factory,
    )

    assert rc == 0
    assert len(watchers) == 1
    assert watchers[0].poll_calls == 1
    assert mt5.initialize_calls == 2  # startup connect + reconnect


def test_main_wrong_login_mid_run_exits_2(tmp_path):
    # _check_login() at startup passes (DEMO_LOGIN), then the first loop
    # health check reports the wrong login -> hard exit 2, poll_once never
    # called.
    mt5 = _RunnerMt5Stub([guard_cuenta.DEMO_LOGIN, _WRONG_LOGIN])
    watchers = []

    def watcher_factory(registry, client, poll_s=5, attach_checker=None):
        w = _RecordingWatcher(registry, client, poll_s=poll_s, attach_checker=attach_checker)
        watchers.append(w)
        return w

    rc = rdw.main(
        ["--db", str(tmp_path / "t.db"), "--once"],
        mt5_module=mt5, attach_checker=lambda: True,
        watcher_factory=watcher_factory,
    )

    assert rc == 2
    assert len(watchers) == 1
    assert watchers[0].poll_calls == 0
