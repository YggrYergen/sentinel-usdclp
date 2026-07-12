"""tests/live/test_deals_watcher.py — TDD for DealsWatcher (B1a-1, NUCLEO).

Covers: attach-guard skip (never calls MT5 client when terminal64.exe is
absent), idempotent upsert into `deals_raw` by ticket, and correct field
mapping from a stub `mt5_client.history_deals_get(...)`. Attribution
(magic -> strategia/ia/human) and `last_sync` persistence are explicitly
OUT of scope here (B1a-2) -- this stub just passes `magic` through raw.
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
