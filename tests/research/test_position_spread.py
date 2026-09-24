"""tests/research/test_position_spread.py — position_spread table + registry
helpers (live-strategy positions, 2026-07-21).

Covers the migration (table exists), the OPEN-then-CLOSE upsert (CLOSE must
not clobber OPEN fields), idempotency, and the batched getter.
"""
from __future__ import annotations

import sqlite3

import pytest

from sentinel_engine.research.registry2 import ResearchRegistry


@pytest.fixture
def registry(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


def test_position_spread_table_created(registry):
    conn = sqlite3.connect(str(registry.db_path))
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(position_spread)").fetchall()}
    finally:
        conn.close()
    assert cols == {
        "position_id", "ticket_open", "spread_open", "spread_open_min",
        "spread_open_ts", "spread_close", "spread_close_ts",
    }


def test_record_open_then_close_does_not_clobber(registry):
    registry.record_position_spread(
        500, ticket_open=500, spread_open=0.50, spread_open_min=0.50, spread_open_ts=1000,
    )
    registry.record_position_spread(500, spread_close=0.62, spread_close_ts=1100)

    got = registry.get_position_spreads([500])
    assert set(got.keys()) == {500}
    row = got[500]
    assert row["ticket_open"] == 500
    assert row["spread_open"] == 0.50
    assert row["spread_open_min"] == 0.50
    assert row["spread_open_ts"] == 1000
    assert row["spread_close"] == 0.62
    assert row["spread_close_ts"] == 1100


def test_record_is_idempotent(registry):
    registry.record_position_spread(501, spread_open=0.5, spread_open_ts=10)
    registry.record_position_spread(501, spread_open=0.5, spread_open_ts=10)
    got = registry.get_position_spreads([501])
    assert list(got.keys()) == [501]


def test_get_empty_and_missing(registry):
    assert registry.get_position_spreads([]) == {}
    registry.record_position_spread(600, spread_open=0.5)
    got = registry.get_position_spreads([600, 999])
    assert set(got.keys()) == {600}
