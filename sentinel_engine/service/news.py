"""sentinel_engine.service.news — C1a news core + C1b poller loop.

Parsers accept raw strings only. `NewsItem` is a plain dict shaped per
CT-5: `{"id","ts","source","title","url","symbols","kind","impact"}`.

Dedupe: exact-id dedupe (sha1 of canonical url / calendar event key) plus
near-duplicate title collapsing within a 48h window via
`difflib.SequenceMatcher` ratio > 0.9 (`is_dup_title`).

Symbol keyword map is a hardcoded default (`DEFAULT_SYMBOL_KEYWORDS`);
`load_news_config` (C1b) reads `news.yaml` and can override it per-symbol.

C1b additions: `load_news_config` (yaml loader) and `NewsPoller` (90s-cadence
background loop -- injectable `fetcher(url, etag, last_modified) ->
(status, headers, body)`, defaults to stdlib `urllib.request`; conditional
GET honors ETag/Last-Modified, 304 => skip; new items only => broadcast to
subscribers for `GET /api/news/stream`, CT-9 SSE `news_item` event). The
poller never raises out of `poll_once`/the background loop -- fetch/parse
errors are logged and the loop continues.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import queue
import sqlite3
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

import yaml

NewsItem = dict[str, Any]

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 90.0

_DUP_WINDOW_SECONDS = 48 * 3600
_TITLE_DUP_RATIO = 0.9

# Default symbol -> keyword map (case-insensitive substring match against
# title). Per-symbol yaml override arrives in C1b -- not implemented here.
DEFAULT_SYMBOL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "XAUUSD": ("gold", "oro", "xau"),
    "DXY": ("dxy", "dollar index", "us dollar index"),
    "VIX": ("vix", "volatility index"),
}


def _canonical_url(url: str) -> str:
    """Strip query string and fragment, lowercase scheme/host, drop
    trailing slash -- so trivially-varying URLs (tracking params, http vs
    https) dedupe to the same id."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, "", ""))


def dedupe_key(item: NewsItem) -> str:
    """sha1 of canonical url for news items, or sha1 of the calendar event
    key (`kind|source|ts|title`) for calendar items lacking a url."""
    url = item.get("url")
    if url:
        basis = _canonical_url(url)
    else:
        basis = "|".join(
            str(item.get(k, "")) for k in ("kind", "source", "ts", "title")
        )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def is_dup_title(a: NewsItem, b: NewsItem) -> bool:
    """True when two items are near-duplicate titles (ratio > 0.9) AND
    fall within a 48h window of each other by ts."""
    ts_a, ts_b = a.get("ts"), b.get("ts")
    if ts_a is None or ts_b is None:
        return False
    if abs(ts_a - ts_b) > _DUP_WINDOW_SECONDS:
        return False
    title_a, title_b = a.get("title") or "", b.get("title") or ""
    ratio = SequenceMatcher(None, title_a, title_b).ratio()
    return ratio > _TITLE_DUP_RATIO


def _detect_symbols(
    title: str, symbol_keywords: dict[str, Any] | None = None
) -> list[str]:
    lower = title.lower()
    keyword_map = symbol_keywords if symbol_keywords else DEFAULT_SYMBOL_KEYWORDS
    hits = []
    for symbol, keywords in keyword_map.items():
        if any(kw in lower for kw in keywords):
            hits.append(symbol)
    return hits


def parse_rss(raw: str, source: str, symbol_keywords: dict[str, Any] | None = None) -> list[NewsItem]:
    """Parse an RSS 2.0 XML string into a list of NewsItem dicts.

    Uses stdlib `xml.etree.ElementTree` only (no feedparser dependency).
    Each `<item>` becomes one NewsItem with `kind="news"`.
    """
    root = ElementTree.fromstring(raw)
    items: list[NewsItem] = []
    for item_el in root.iter("item"):
        title = (item_el.findtext("title") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        pub_date = item_el.findtext("pubDate")
        ts = _parse_rfc822_ts(pub_date) if pub_date else None
        symbols = _detect_symbols(title, symbol_keywords)
        news_item: NewsItem = {
            "id": "",
            "ts": ts,
            "source": source,
            "title": title,
            "url": link,
            "symbols": symbols,
            "kind": "news",
            "impact": None,
        }
        news_item["id"] = dedupe_key(news_item)
        items.append(news_item)
    return items


def _parse_rfc822_ts(raw: str) -> int | None:
    from email.utils import parsedate_to_datetime

    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    return int(dt.timestamp())


def parse_ff_calendar(raw: str, symbol_keywords: dict[str, Any] | None = None) -> list[NewsItem]:
    """Parse a ForexFactory-style weekly calendar JSON string into a list
    of NewsItem dicts (`kind="calendar"`).

    Expected shape (per-entry, list of objects): `title`, `country`,
    `date` (ISO-8601 string), `impact` ("High"/"Medium"/"Low"), and
    optionally `url`.
    """
    data = json.loads(raw)
    items: list[NewsItem] = []
    for entry in data:
        title = (entry.get("title") or "").strip()
        date_str = entry.get("date")
        ts = _parse_iso_ts(date_str) if date_str else None
        impact_raw = (entry.get("impact") or "").strip().lower()
        impact = impact_raw if impact_raw in ("high", "medium", "low") else None
        symbols = _detect_symbols(title, symbol_keywords)
        news_item: NewsItem = {
            "id": "",
            "ts": ts,
            "source": "ff_calendar",
            "title": title,
            "url": entry.get("url"),
            "symbols": symbols,
            "kind": "calendar",
            "impact": impact,
        }
        news_item["id"] = dedupe_key(news_item)
        items.append(news_item)
    return items


def _parse_iso_ts(raw: str) -> int | None:
    from datetime import datetime

    try:
        s = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return int(dt.timestamp())


def dedupe_items(items: list[NewsItem]) -> list[NewsItem]:
    """Collapse exact-id duplicates first, then near-duplicate titles
    within the 48h window (keeps the first-seen item of each cluster)."""
    by_id: dict[str, NewsItem] = {}
    for item in items:
        by_id.setdefault(item["id"], item)
    unique = list(by_id.values())

    kept: list[NewsItem] = []
    for item in unique:
        if any(is_dup_title(item, existing) for existing in kept):
            continue
        kept.append(item)
    return kept


def upsert_items(registry: Any, items: list[NewsItem]) -> None:
    """Insert-or-replace NewsItems into `news_items`. Dedupes the input
    batch first (exact id + near-dup title)."""
    items = dedupe_items(items)
    conn = registry._connect()  # noqa: SLF001 - same pattern as routers/positions.py
    try:
        for item in items:
            conn.execute(
                "INSERT OR REPLACE INTO news_items"
                "(id, ts, source, title, url, symbols_json, kind, impact) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["id"],
                    item.get("ts"),
                    item.get("source"),
                    item.get("title"),
                    item.get("url"),
                    json.dumps(item.get("symbols") or []),
                    item.get("kind"),
                    item.get("impact"),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def query_items(
    registry: Any,
    symbol: str | None = None,
    impact: str | None = None,
    kind: str | None = None,
    limit: int = 100,
) -> list[NewsItem]:
    """Query `news_items`, most-recent-first by ts, filtered by symbol
    (substring match inside `symbols_json`), impact, kind, capped at
    `limit`."""
    conn = registry._connect()  # noqa: SLF001
    conn.row_factory = sqlite3.Row
    try:
        clauses = []
        params: list[Any] = []
        if impact:
            clauses.append("impact = ?")
            params.append(impact)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM news_items {where} ORDER BY ts DESC",
            params,
        ).fetchall()
    finally:
        conn.close()

    results: list[NewsItem] = []
    for row in rows:
        symbols = json.loads(row["symbols_json"] or "[]")
        if symbol and symbol not in symbols:
            continue
        results.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "source": row["source"],
                "title": row["title"],
                "url": row["url"],
                "symbols": symbols,
                "kind": row["kind"],
                "impact": row["impact"],
            }
        )
        if len(results) >= limit:
            break
    return results


# ---------------------------------------------------------------------------
# C1b: news.yaml loader
# ---------------------------------------------------------------------------
def load_news_config(path: Path) -> dict[str, Any]:
    """Load `news.yaml`: `{"rss": [...], "ff_calendar": <url|None>,
    "symbol_keywords": {...}}`. `symbol_keywords` overrides
    `DEFAULT_SYMBOL_KEYWORDS` wholesale when present and non-empty."""
    with Path(path).open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return {
        "rss": raw.get("rss") or [],
        "ff_calendar": raw.get("ff_calendar"),
        "symbol_keywords": raw.get("symbol_keywords") or {},
    }


# ---------------------------------------------------------------------------
# C1b: default fetcher (stdlib urllib, conditional GET)
# ---------------------------------------------------------------------------
def _default_fetcher(
    url: str, etag: str | None, last_modified: str | None
) -> tuple[int, dict[str, str], bytes]:
    """`fetcher(url, etag, last_modified) -> (status, headers, body)`.
    Conditional GET via `If-None-Match`/`If-Modified-Since`; a 304 response
    surfaces as `(304, {}, b"")` rather than raising (urllib raises
    `HTTPError` for non-2xx, including 304)."""
    req = urllib.request.Request(url)
    if etag:
        req.add_header("If-None-Match", etag)
    if last_modified:
        req.add_header("If-Modified-Since", last_modified)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except HTTPError as exc:
        if exc.code == 304:
            return 304, {}, b""
        raise


# ---------------------------------------------------------------------------
# C1b: NewsPoller -- background loop + SSE broadcaster
# ---------------------------------------------------------------------------
class NewsPoller:
    """Polls `config["rss"]` (+ `config["ff_calendar"]` if set) on a 90s
    cadence, upserts new items into `news_items`, and broadcasts each new
    item to subscribers (`GET /api/news/stream`, CT-9 SSE `news_item`
    event).

    `fetcher(url, etag, last_modified) -> (status, headers, body)` is
    injectable (tests pass a fake; production defaults to
    `_default_fetcher`, stdlib `urllib.request` only). Conditional GET:
    per-url ETag/Last-Modified from the previous response are sent on the
    next poll; a 304 response means "unchanged" -- skipped, no parse, no
    broadcast.

    `poll_once()` and the background loop never raise: fetch errors,
    malformed feed bodies, etc. are logged and that source is skipped for
    this cycle -- the loop (and other sources) keep going.
    """

    def __init__(
        self,
        registry: Any,
        config: dict[str, Any],
        fetcher: Callable[[str, str | None, str | None], tuple[int, dict[str, str], bytes]]
        | None = None,
    ) -> None:
        self._registry = registry
        self._config = config
        self._fetcher = fetcher or _default_fetcher
        self._symbol_keywords = config.get("symbol_keywords") or None
        self._cache: dict[str, dict[str, str | None]] = {}  # url -> {"etag","last_modified"}
        self._subscribers: list["queue.Queue[dict]"] = []

    # ------------------------------------------------------------------
    # SSE broadcast (CT-9)
    # ------------------------------------------------------------------
    def subscribe(self) -> "queue.Queue[dict]":
        q: "queue.Queue[dict]" = queue.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue[dict]") -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def _broadcast(self, item: NewsItem) -> None:
        for q in list(self._subscribers):
            q.put(item)

    # ------------------------------------------------------------------
    # polling
    # ------------------------------------------------------------------
    def _sources(self) -> list[tuple[str, str]]:
        """`[(url, source_kind), ...]` where `source_kind` is `"rss"` or
        `"ff_calendar"`."""
        sources = [(url, "rss") for url in (self._config.get("rss") or [])]
        ff_url = self._config.get("ff_calendar")
        if ff_url:
            sources.append((ff_url, "ff_calendar"))
        return sources

    def _poll_source(self, url: str, source_kind: str) -> None:
        cached = self._cache.get(url, {})
        try:
            status, headers, body = self._fetcher(
                url, cached.get("etag"), cached.get("last_modified")
            )
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            logger.warning("news poller: fetch failed for %s: %s", url, exc)
            return

        if status == 304:
            return
        if status != 200:
            logger.warning("news poller: unexpected status %s for %s", status, url)
            return

        etag = headers.get("ETag") or headers.get("Etag")
        last_modified = headers.get("Last-Modified")
        self._cache[url] = {"etag": etag, "last_modified": last_modified}

        raw = body.decode("utf-8", errors="replace")
        try:
            if source_kind == "ff_calendar":
                items = parse_ff_calendar(raw, self._symbol_keywords)
            else:
                items = parse_rss(raw, source=url, symbol_keywords=self._symbol_keywords)
        except Exception as exc:  # noqa: BLE001 - malformed feed must not kill the loop
            logger.warning("news poller: failed to parse %s: %s", url, exc)
            return

        if not items:
            return

        existing_ids = {row["id"] for row in query_items(self._registry, limit=10_000)}
        new_items = [item for item in dedupe_items(items) if item["id"] not in existing_ids]
        if not new_items:
            return

        upsert_items(self._registry, new_items)
        for item in new_items:
            self._broadcast(item)

    def poll_once(self) -> None:
        """One pass over every configured source. Never raises -- each
        source's errors are caught and logged individually."""
        for url, source_kind in self._sources():
            try:
                self._poll_source(url, source_kind)
            except Exception as exc:  # noqa: BLE001 - the loop must survive any single source's failure
                logger.warning("news poller: unhandled error polling %s: %s", url, exc)

    async def run_forever(self, interval: float = POLL_INTERVAL_SECONDS) -> None:
        """Background task entry point (same pattern as `app.py`'s compute
        loop): `poll_once()` runs off the event loop thread via
        `asyncio.to_thread` since the default fetcher does blocking I/O."""
        while True:
            try:
                await asyncio.to_thread(self.poll_once)
            except Exception as exc:  # noqa: BLE001 - defense in depth, poll_once already catches internally
                logger.warning("news poller: loop iteration failed: %s", exc)
            await asyncio.sleep(interval)
