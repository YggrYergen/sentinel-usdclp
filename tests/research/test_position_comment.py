"""tests/research/test_position_comment.py — position_comment table +
registry helpers (Posiciones->ESTRATEGIA per-position comments, backend).

Mirrors tests/research/test_position_spread.py: covers the migration
(table exists), add-then-get, multiple comments ordered by created_at then
comment_id, empty-body rejection, delete, and the batched getter for an
empty position_ids list.
"""
from __future__ import annotations

import sqlite3

import pytest

from sentinel_engine.research.registry2 import ResearchRegistry


@pytest.fixture
def registry(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


def test_position_comment_table_created(registry):
    conn = sqlite3.connect(str(registry.db_path))
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(position_comment)").fetchall()}
    finally:
        conn.close()
    assert cols == {"comment_id", "position_id", "magic", "body", "created_at"}


def test_add_then_get_returns_it(registry):
    comment_id = registry.add_position_comment(100, "watch this one", magic=111)
    assert isinstance(comment_id, int)

    got = registry.get_position_comments([100])
    assert set(got.keys()) == {100}
    comments = got[100]
    assert len(comments) == 1
    c = comments[0]
    assert c["comment_id"] == comment_id
    assert c["position_id"] == 100
    assert c["magic"] == 111
    assert c["body"] == "watch this one"
    assert c["created_at"]


def test_add_defaults_created_at_when_not_provided(registry):
    registry.add_position_comment(100, "no ts given")
    got = registry.get_position_comments([100])
    assert got[100][0]["created_at"]


def test_multiple_comments_ordered_by_created_at_then_id(registry):
    registry.add_position_comment(100, "first", created_at="2026-07-21T10:00:00+00:00")
    registry.add_position_comment(100, "second", created_at="2026-07-21T10:00:00+00:00")
    registry.add_position_comment(100, "third", created_at="2026-07-21T09:00:00+00:00")

    got = registry.get_position_comments([100])
    bodies = [c["body"] for c in got[100]]
    # "third" has the earliest created_at -> first; "first"/"second" share a
    # timestamp -> tie-broken by comment_id ascending (insertion order).
    assert bodies == ["third", "first", "second"]


def test_add_empty_body_raises_value_error(registry):
    with pytest.raises(ValueError):
        registry.add_position_comment(100, "")
    with pytest.raises(ValueError):
        registry.add_position_comment(100, "   ")


def test_delete_position_comment_removes_it(registry):
    comment_id = registry.add_position_comment(100, "to be removed")
    assert registry.delete_position_comment(comment_id) is True

    got = registry.get_position_comments([100])
    assert got.get(100, []) == []


def test_delete_position_comment_missing_id_returns_false(registry):
    assert registry.delete_position_comment(999999) is False


def test_get_position_comments_empty_input(registry):
    assert registry.get_position_comments([]) == {}


def test_get_position_comments_missing_position_absent(registry):
    registry.add_position_comment(100, "hello")
    got = registry.get_position_comments([100, 999])
    assert set(got.keys()) == {100}
