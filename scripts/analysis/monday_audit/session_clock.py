"""scripts/analysis/monday_audit/session_clock.py -- when did the market reopen?

Shared by every audit question that depends on the hour of day. It exists as its
own module so that the mask verdicts (B1) and the wait-curve screening cannot
drift apart in how they define a session.

WHY THIS IS MEASURED AND NOT ASSUMED
------------------------------------
XAUUSD at this broker does NOT reopen at a fixed wall-clock hour. Measured over
the 7-month substrate, the daily break lasts exactly 1:15:00 and the reopen
lands at 18:00 (64x), 20:00 (36x) or 19:00 (15x) server time -- the drift is New
York observing DST against a server pinned at UTC-4. Hardcoding "18:00" would
silently mislabel a third of the sessions. So we read the reopens off the bar
stream itself, which is the same signal the LIVE gate uses: `gap_wait.py`
declares a session reset after a gap of >= SESSION_GAP_MINUTES with no
observation.

The entry stream is NOT a valid substitute for the bar stream. Entries are
signal-driven and sparse, so a one-hour lull between two trades is routine
mid-session and says nothing about market availability. An earlier version of
the B1 mask used exactly that proxy, invented 415 "sessions" where there are
~145, and produced a -114% verdict that measured nothing.

CLOCK: the bar epochs and the regenerated position CSVs are BOTH in broker
server time (UTC-4) as of the 2026-07-27 fix to realtick_bt/backtest.py. Do NOT
apply any timezone correction on top -- that bug is fixed at the source.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

BARS_PATH = (Path(__file__).resolve().parents[3] / "data" / "lake_ticks"
             / "XAUUSD" / "_bars_M15.parquet")

# Same threshold as the live gate's SESSION_GAP_MINUTES: a gap this long with no
# quote means the market went away, so whatever comes back is a fresh session.
SESSION_GAP_MINUTES = 60


def market_reopens(bar_times: list[dt.datetime], *,
                   gap_minutes: int = SESSION_GAP_MINUTES) -> list[dt.datetime]:
    """Timestamps at which the market resumed: the first bar of the substrate,
    plus every bar that follows a gap of >= `gap_minutes`.

    Pure. `bar_times` need not be sorted."""
    out: list[dt.datetime] = []
    prev: dt.datetime | None = None
    for t in sorted(bar_times):
        if prev is None or (t - prev) >= dt.timedelta(minutes=gap_minutes):
            out.append(t)
        prev = t
    return out


def load_bar_times(path: str | Path = BARS_PATH) -> list[dt.datetime]:
    """Every M15 bar timestamp, in broker server time.

    The parquet stores raw MT5 epochs, which already encode server wall clock,
    so the decode is `utcfromtimestamp` -- NOT `fromtimestamp`, which would
    re-apply the host's (DST-varying) local offset. See the module docstring of
    scripts/analysis/realtick_bt/backtest.py."""
    import pandas as pd
    df = pd.read_parquet(path)
    return [dt.datetime.utcfromtimestamp(int(t)) for t in df["t"]]


def minutes_since_reopen(t: dt.datetime, reopens: list[dt.datetime]) -> float | None:
    """Minutes elapsed from the most recent reopen at or before `t`.

    None when `t` precedes every known reopen (i.e. outside the substrate).
    `reopens` MUST be sorted ascending -- `market_reopens` returns it that way."""
    import bisect
    i = bisect.bisect_right(reopens, t) - 1
    if i < 0:
        return None
    return (t - reopens[i]).total_seconds() / 60.0
