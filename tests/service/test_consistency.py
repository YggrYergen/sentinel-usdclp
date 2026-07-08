"""UI rework acceptance gate #3 (spec §10.3): two WS clients on the same
instrument observe byte-identical snapshot JSON for a given seq. The
service already guarantees this by construction (ONE InstrumentRunner per
instrument, ONE Broadcaster fan-out per compute) — this test is the
explicit regression lock for that invariant."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_two_clients_same_instrument_see_identical_snapshot(app_factory):
    app = app_factory(instruments=("gold",), autostart_loop=False)
    with TestClient(app) as client:
        with client.websocket_connect("/stream?instrument=gold") as ws_a, \
             client.websocket_connect("/stream?instrument=gold") as ws_b:
            snap_a = ws_a.receive_json()
            snap_b = ws_b.receive_json()
            assert snap_a["seq"] == snap_b["seq"]
            assert snap_a == snap_b
