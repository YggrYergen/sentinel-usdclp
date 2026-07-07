"""
sentinel_engine.service.stream — WS fan-out broadcaster (P3, Task 3.2/3.3).

`Broadcaster` holds, per instrument, the set of currently-connected
websockets and exposes `broadcast(instrument, snapshot)`. The snapshot
dict passed to `broadcast` is computed EXACTLY ONCE by the caller (the
background compute loop in `app.py`) and fanned out unmodified to every
connected client — this is the state-consistency correctness fix: N
clients watching the same instrument always see the byte-identical
payload for a given `seq`, never N independent recomputes.
"""
from __future__ import annotations

import asyncio
from typing import Any


class Broadcaster:
    """Per-instrument WS client registry + fan-out broadcast."""

    def __init__(self) -> None:
        self._clients: dict[str, set[Any]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: Any, instrument: str) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.setdefault(instrument, set()).add(ws)

    def disconnect(self, ws: Any, instrument: str) -> None:
        clients = self._clients.get(instrument)
        if clients is not None:
            clients.discard(ws)

    async def broadcast(self, instrument: str, snapshot: dict) -> None:
        """Push the SAME already-computed `snapshot` dict to every client
        currently subscribed to `instrument`. Dead/erroring sockets are
        dropped rather than raising."""
        clients = list(self._clients.get(instrument, ()))
        for ws in clients:
            try:
                await ws.send_json(snapshot)
            except Exception:
                self.disconnect(ws, instrument)

    def client_count(self, instrument: str) -> int:
        return len(self._clients.get(instrument, ()))
