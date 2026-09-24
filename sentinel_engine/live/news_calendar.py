"""sentinel_engine/live/news_calendar.py -- the STATIC, COMMITTED news
calendar behind the challenger's B2 blackout gate (spec section 4.3).

DATA, NOT A KNOB. The file is committed to the repo and read at runtime; it is
never generated, fetched or tuned. The +/-30 min window is a CONVENTION fixed by
the spec -- choosing it from a backtest sweep would be re-tuning (violates R3).

FAIL-CLOSED CONTRACT: a missing file, an unreadable file, a wrong header or an
unparseable timestamp all return None, and `risk_gates.evaluate_open_gates`
turns None into "do not open". A valid header with zero data rows returns an
empty tuple -- readable, simply no events -- and does NOT stop trading.

CLOCK: `utc_datetime` is REAL UTC (same clock as datetime.now(timezone.utc)),
NOT MT5 broker server time. A naive timestamp is read as UTC.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

CALENDAR_PATH = (Path(__file__).resolve().parents[2]
                 / "data" / "live" / "news_calendar.csv")

_REQUIRED_COLUMN = "utc_datetime"


def load_windows(path: str | Path = CALENDAR_PATH, *,
                 minutes_before: int,
                 minutes_after: int
                 ) -> tuple[tuple[datetime, datetime], ...] | None:
    """Blackout windows built from the committed calendar, sorted by start.
    Returns None on ANY read/parse problem (the fail-closed signal)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        reader = csv.DictReader(text.splitlines())
        if reader.fieldnames is None or _REQUIRED_COLUMN not in reader.fieldnames:
            return None
        windows: list[tuple[datetime, datetime]] = []
        for row in reader:
            raw = (row.get(_REQUIRED_COLUMN) or "").strip()
            if not raw:
                continue  # blank line
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts = ts.astimezone(timezone.utc)
            windows.append((ts - timedelta(minutes=minutes_before),
                            ts + timedelta(minutes=minutes_after)))
    except (ValueError, TypeError, csv.Error):
        return None
    return tuple(sorted(windows))
