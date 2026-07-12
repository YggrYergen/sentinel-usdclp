"""sentinel_engine.service.routers.bars — /api/bars, /ws/ticks (W0.1a).

Moved verbatim out of `sentinel_engine.service.app` (plan recalibration V2,
W0.1 "split app.py into routers"). `build_router(lake_root, tick_hub)` is
called once from `create_app()` after those two dependencies exist; the
returned `APIRouter` is included via `app.include_router(...)` so the final
paths (`/api/bars`, `/ws/ticks`) are byte-identical to before the split.

`_parse_flexible_ts` and `_api_error` are imported lazily (inside
`build_router`, not at module import time) from `sentinel_engine.service.app`
to avoid a circular import — `app.py` imports this module at its own
top-level to register the router.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ..bars import BarsError, bars_payload
from ..stream import TickHub

router = APIRouter()


def build_router(lake_root, tick_hub: TickHub) -> APIRouter:
    from ..app import _api_error, _parse_flexible_ts

    r = APIRouter()

    @r.get("/api/bars")
    def get_bars(
        symbol: str,
        tf: str = "M1",
        from_: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        max_points: int = 3000,
    ) -> Any:
        try:
            ts_from = _parse_flexible_ts(from_)
            ts_to = _parse_flexible_ts(to)
        except (ValueError, TypeError) as exc:
            return _api_error(400, "bad_range", f"invalid from/to: {exc}")
        try:
            payload = bars_payload(lake_root, symbol, tf, ts_from, ts_to, max_points)
        except BarsError as exc:
            return _api_error(400, "bad_tf", str(exc))
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the client
            return _api_error(500, "bars_failed", str(exc))
        return payload

    @r.websocket("/ws/ticks")
    async def ticks_ws(websocket: WebSocket) -> None:
        """`ticks:{SYMBOL}` channel (plan §D.6): client sends
        `{"sub":"ticks:XAUUSD"}` / `{"unsub":"ticks:XAUUSD"}`; server pushes
        `{"ch":"ticks:XAUUSD","t":epoch_ms,"bid","ask"}` on-change ~250ms,
        only while this socket (or another) is subscribed to that symbol.
        Subscribing to a second symbol on the same socket is additive."""
        await websocket.accept()
        subscribed: set[str] = set()
        try:
            while True:
                msg = await websocket.receive_json()
                sub = msg.get("sub")
                unsub = msg.get("unsub")
                if isinstance(sub, str) and sub.startswith("ticks:"):
                    symbol = sub[len("ticks:"):]
                    await tick_hub.subscribe(websocket, symbol)
                    subscribed.add(symbol)
                if isinstance(unsub, str) and unsub.startswith("ticks:"):
                    symbol = unsub[len("ticks:"):]
                    await tick_hub.unsubscribe(websocket, symbol)
                    subscribed.discard(symbol)
        except WebSocketDisconnect:
            pass
        finally:
            for symbol in list(subscribed):
                await tick_hub.unsubscribe(websocket, symbol)

    return r
