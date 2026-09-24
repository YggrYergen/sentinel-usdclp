"""sentinel_engine.service.routers.news — GET /api/news (C1a) + GET
/api/news/stream (C1b).

Shape per CT-5 (frozen contract):
`GET /api/news?symbol=&impact=&kind=&limit=100` ->
`{"items":[{"id","ts","source","title","url","symbols","kind","impact"}]}`.
`GET /api/news/stream` SSE emits `news_item` events (CT-9: heartbeat 15s,
retry 3000) -- subscribe/broadcast pattern copied from
`routers/jobs.py::get_jobs_stream` / `JobsService`.

`build_router(registry, poller)` follows the same lazy-registry pattern as
`routers/positions.py`; `app.py` calls it once at `create_app()` time,
passing the same `NewsPoller` instance whose background loop is started in
the app's `lifespan`.
"""
from __future__ import annotations

import asyncio
import json
import queue as _queue_mod
from typing import Any

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from ..news import NewsPoller, query_items

# CT-9 SSE convention: heartbeat comment cadence (seconds).
_SSE_HEARTBEAT_SECONDS = 15.0


def build_router(registry: Any, poller: NewsPoller | None = None) -> APIRouter:
    r = APIRouter()

    @r.get("/api/news")
    def get_news(
        symbol: str | None = None,
        impact: str | None = None,
        kind: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        items = query_items(registry, symbol=symbol, impact=impact, kind=kind, limit=limit)
        return {"items": items}

    @r.get("/api/news/stream")
    async def get_news_stream():
        """CT-9 SSE: `news_item` event per new item broadcast by the
        `NewsPoller` background loop."""
        sub_queue = poller.subscribe()

        def _poll():
            try:
                return sub_queue.get(True, _SSE_HEARTBEAT_SECONDS)
            except _queue_mod.Empty:
                return None

        async def event_stream():
            yield "retry: 3000\n\n"
            try:
                while True:
                    body = await asyncio.to_thread(_poll)
                    if body is None:
                        yield ": hb\n\n"
                    else:
                        data = json.dumps(body)
                        yield f"event: news_item\ndata: {data}\n\n"
            finally:
                poller.unsubscribe(sub_queue)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return r
