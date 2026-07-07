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
    with TestClient(app) as client:
        with client.websocket_connect("/stream?instrument=usdclp") as ws1, \
                client.websocket_connect("/stream?instrument=usdclp") as ws2:
            # Drain each client's connect-time seed snapshot (independent of
            # the other client's seed, delivered on accept).
            ws1.receive_json()
            ws2.receive_json()
            # The next tick is produced by exactly ONE background compute
            # and fanned out to both — payloads (including seq) must match.
            m1 = ws1.receive_json()
            m2 = ws2.receive_json()
    assert m1 == m2
    assert m1["seq"] >= 1


def test_ws_unknown_instrument_closes(app_factory):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/stream?instrument=nope"):
                pass
        assert exc_info.value.code == 4404
