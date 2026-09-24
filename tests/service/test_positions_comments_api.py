"""tests/service/test_positions_comments_api.py — TDD for per-position
comment endpoints (Posiciones->ESTRATEGIA backend).

Mirrors tests/service/test_positions_api.py's harness for building a test
app + throwaway registry (tmp_path db).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.app import create_app
from tests.golden.fake_feed import FakeFeed


@pytest.fixture
def registry(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


@pytest.fixture
def client(registry):
    shared_feed = FakeFeed()
    app = create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        registry=registry,
    )
    with TestClient(app) as c:
        yield c


def test_post_comment_creates_and_returns_comment_id(client):
    resp = client.post("/api/positions/100/comments", json={"body": "watch this", "magic": 111})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["comment_id"], int)
    assert body["position_id"] == 100
    assert body["body"] == "watch this"
    assert body["magic"] == 111
    assert body["created_at"]


def test_post_comment_without_magic(client):
    resp = client.post("/api/positions/100/comments", json={"body": "no magic given"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["magic"] is None


def test_get_comments_lists_in_order(client):
    client.post("/api/positions/100/comments", json={"body": "first"})
    client.post("/api/positions/100/comments", json={"body": "second"})

    resp = client.get("/api/positions/100/comments")
    assert resp.status_code == 200
    comments = resp.json()["comments"]
    assert [c["body"] for c in comments] == ["first", "second"]


def test_get_comments_empty_for_position_without_comments(client):
    resp = client.get("/api/positions/999/comments")
    assert resp.status_code == 200
    assert resp.json() == {"comments": []}


def test_delete_comment_removes_it(client):
    post_resp = client.post("/api/positions/100/comments", json={"body": "to remove"})
    comment_id = post_resp.json()["comment_id"]

    del_resp = client.delete(f"/api/positions/100/comments/{comment_id}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"deleted": True}

    get_resp = client.get("/api/positions/100/comments")
    assert get_resp.json() == {"comments": []}


def test_delete_comment_missing_id_returns_false(client):
    resp = client.delete("/api/positions/100/comments/999999")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": False}


def test_post_comment_empty_body_returns_400(client):
    resp = client.post("/api/positions/100/comments", json={"body": ""})
    assert resp.status_code == 400


def test_post_comment_whitespace_body_returns_400(client):
    resp = client.post("/api/positions/100/comments", json={"body": "   "})
    assert resp.status_code == 400
