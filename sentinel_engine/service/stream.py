"""
sentinel_engine.service.stream — WS fan-out broadcaster (P3, Task 3.2/3.3)
and the `ticks:{SYMBOL}` channel (M1.2, plan §D.6).

`Broadcaster` holds, per instrument, the set of currently-connected
websockets and exposes `broadcast(instrument, snapshot)`. The snapshot
dict passed to `broadcast` is computed EXACTLY ONCE by the caller (the
background compute loop in `app.py`) and fanned out unmodified to every
connected client — this is the state-consistency correctness fix: N
clients watching the same instrument always see the byte-identical
payload for a given `seq`, never N independent recomputes.

`TickHub` (M1.2) is the analogous mechanism for the `ticks:{SYMBOL}` WS
channel: on subscribe, it lazily starts ONE polling task per symbol that
calls a caller-supplied read-only `tick_source(symbol) -> (bid, ask) | None`
on an ~250ms cadence, pushing `{"ch":"ticks:{SYMBOL}","t":epoch_ms,"bid","ask"}`
to every subscriber ONLY when the tick changed; the poll task is cancelled
the instant the last subscriber for that symbol unsubscribes/disconnects —
there is never a polling task running for a symbol with zero subscribers,
and `tick_source` is never anything that can place an order (the caller
wires it to `mt5.symbol_info_tick` or a fake in tests, read-only by
construction — this module has no MT5 import and no order-side code path).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable


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


TickSource = Callable[[str], tuple[float, float] | None]


class TickHub:
    """Per-symbol `ticks:{SYMBOL}` subscriber registry + on-change poll loop.

    `tick_source(symbol)` must be read-only (e.g. `mt5.symbol_info_tick`)
    and return `(bid, ask)` or `None` if unavailable. The poll task for a
    symbol exists ONLY while `client_count(symbol) >= 1`; it is created on
    the first subscribe and cancelled synchronously on the last unsubscribe
    (clean shutdown — no orphaned task ever outlives its subscribers).
    """

    def __init__(self, tick_source: TickSource, poll_interval: float = 0.25) -> None:
        self._tick_source = tick_source
        self._poll_interval = poll_interval
        self._clients: dict[str, set[Any]] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._last: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    def client_count(self, symbol: str) -> int:
        return len(self._clients.get(symbol, ()))

    async def subscribe(self, ws: Any, symbol: str) -> None:
        async with self._lock:
            self._clients.setdefault(symbol, set()).add(ws)
            if symbol not in self._tasks:
                self._tasks[symbol] = asyncio.create_task(self._poll_loop(symbol))

    async def unsubscribe(self, ws: Any, symbol: str) -> None:
        async with self._lock:
            clients = self._clients.get(symbol)
            if clients is not None:
                clients.discard(ws)
                if not clients:
                    self._clients.pop(symbol, None)
                    self._last.pop(symbol, None)
                    task = self._tasks.pop(symbol, None)
                    if task is not None:
                        task.cancel()

    async def unsubscribe_all(self, ws: Any) -> None:
        """Remove `ws` from every symbol it may be subscribed to (WS close)."""
        for symbol in list(self._clients.keys()):
            await self.unsubscribe(ws, symbol)

    async def _poll_loop(self, symbol: str) -> None:
        try:
            while True:
                tick = self._tick_source(symbol)
                if tick is not None:
                    bid, ask = tick
                    if self._last.get(symbol) != (bid, ask):
                        self._last[symbol] = (bid, ask)
                        payload = {
                            "ch": f"ticks:{symbol}",
                            "t": int(time.time() * 1000),
                            "bid": bid,
                            "ask": ask,
                        }
                        clients = list(self._clients.get(symbol, ()))
                        for ws in clients:
                            try:
                                await ws.send_json(payload)
                            except Exception:
                                await self.unsubscribe(ws, symbol)
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            pass
