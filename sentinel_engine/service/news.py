"""sentinel_engine.service.news — C1a news core: parse + dedupe + table.

Parsers accept raw strings only (no network code here — network fetching
lands in C1b). `NewsItem` is a plain dict shaped per CT-5:
`{"id","ts","source","title","url","symbols","kind","impact"}`.

Dedupe: exact-id dedupe (sha1 of canonical url / calendar event key) plus
near-duplicate title collapsing within a 48h window via
`difflib.SequenceMatcher` ratio > 0.9 (`is_dup_title`).

Symbol keyword map is a hardcoded default here; per-symbol/yaml override
is out of scope for this task (arrives in C1b).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

NewsItem = dict[str, Any]

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


def _detect_symbols(title: str) -> list[str]:
    lower = title.lower()
    hits = []
    for symbol, keywords in DEFAULT_SYMBOL_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            hits.append(symbol)
    return hits


def parse_rss(raw: str, source: str) -> list[NewsItem]:
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
        symbols = _detect_symbols(title)
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


def parse_ff_calendar(raw: str) -> list[NewsItem]:
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
        symbols = _detect_symbols(title)
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
