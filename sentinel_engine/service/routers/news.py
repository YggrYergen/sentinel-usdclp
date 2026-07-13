"""sentinel_engine.service.routers.news — GET /api/news (C1a).

Shape per CT-5 (frozen contract):
`GET /api/news?symbol=&impact=&kind=&limit=100` ->
`{"items":[{"id","ts","source","title","url","symbols","kind","impact"}]}`.

`GET /api/news/stream` SSE is NOT part of this task (arrives in C1b).

`build_router(registry)` follows the same lazy-registry pattern as
`routers/positions.py`; `app.py` calls it once at `create_app()` time.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..news import query_items


def build_router(registry: Any) -> APIRouter:
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

    return r
