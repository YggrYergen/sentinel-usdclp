"""P3 Task 3.2/3.3 — WS broadcaster: monotonic seq + single-compute fan-out
(the state-consistency correctness fix: N clients never trigger N
recomputes, they all observe the byte-identical snapshot for a given seq)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_ws_client_receives_monotonically_increasing_seq(app_factory):
    app = app_factory(instruments=("usdclp",), loop_interval=0.02, autostart_loop=True)
    with TestClient(app) as client:
        with client.websocket_connect("/stream?instrument=usdclp") as ws:
            seqs = [ws.receive_json()["seq"] for _ in range(4)]
    assert all(b > a for a, b in zip(seqs, seqs[1:])), seqs


def test_ws_two_simultaneous_clients_get_identical_snapshot(app_factory):
    app = app_factory(instruments=("usdclp",), loop_interval=0.02, autostart_loop=True)
    # State-consistency invariant: a snapshot is computed exactly ONCE per seq
    # and fanned out unmodified, so for ANY seq both clients observed, the
    # payloads must be byte-identical. We collect a window from each client and
    # compare on the overlapping seqs — robust to connect-time queue offset
    # (clients connect a beat apart against a free-running loop), which a
    # single "next tick must align" assertion was not (load-timing flaky).
    with TestClient(app) as client:
        with client.websocket_connect("/stream?instrument=usdclp") as ws1, \
                client.websocket_connect("/stream?instrument=usdclp") as ws2:
            msgs1 = {m["seq"]: m for m in (ws1.receive_json() for _ in range(8))}
            msgs2 = {m["seq"]: m for m in (ws2.receive_json() for _ in range(8))}
    shared = set(msgs1) & set(msgs2)
    assert shared, (sorted(msgs1), sorted(msgs2))  # windows must overlap
    for seq in shared:
        assert msgs1[seq] == msgs2[seq]  # same seq => identical fan-out
    assert max(shared) >= 1


def test_ws_unknown_instrument_closes(app_factory):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/stream?instrument=nope"):
                pass
        assert exc_info.value.code == 4404
