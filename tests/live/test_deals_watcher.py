"""tests/live/test_deals_watcher.py — TDD for DealsWatcher (B1a-1 + B1a-2).

Covers: attach-guard skip (never calls MT5 client when terminal64.exe is
absent), idempotent upsert into `deals_raw` by ticket, correct field
mapping from a stub `mt5_client.history_deals_get(...)`, magic-based
attribution (strategy/ia/human, B1a-2), and `last_sync` persistence across
watcher restarts (B1a-2).
"""
from __future__ import annotations

import sqlite3

import pytest

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
