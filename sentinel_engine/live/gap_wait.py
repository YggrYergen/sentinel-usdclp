"""sentinel_engine/live/gap_wait.py -- B1's state: how long the thin-spread
regime has held since the market last reopened (spec section 4.3, B1).

WHY IT EXISTS: XAUUSD is disabled by the broker around 05-06 server time and
over the weekend; the first candles after a reopen are tainted by the gap
(see the project's `xauusd-market-open-gap-wait` lesson). B1 refuses to open
until 50 minutes after the spread first comes back down to the thin regime.

The 50 comes from that earlier diagnosis, NOT from a sweep run this weekend.

SEMANTICS
  * A SESSION BOUNDARY is any gap of >= SESSION_GAP_MINUTES since the previous
    observation (executor down, or market closed). Crossing one resets the clock.
  * The clock STARTS at the first observation with spread <= THIN_SPREAD.
  * The clock DOES NOT restart if the spread later widens: the rule is "50 min
    after the spread comes down", not "50 consecutive thin minutes".
  * A missing/corrupt state file loads FRESH (spread_ok_since=None), which
    DENIES opens until the wait accumulates. Corruption must never admit.

CLOCK: both `last_seen` and `spread_ok_since` are REAL UTC (the same clock as
datetime.now(timezone.utc)), NEVER an MT5 broker server-time bar timestamp.
Task 5's caller is responsible for passing real UTC into `now=`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

THIN_SPREAD = 0.5
SESSION_GAP_MINUTES = 60

STATE_PATH = (Path(__file__).resolve().parents[2]
              / "data" / "live" / "gap_wait_state.json")


@dataclass(frozen=True)
class GapWaitState:
    last_seen: datetime | None = None
    spread_ok_since: datetime | None = None


def advance(state: GapWaitState, *, now: datetime, spread: float | None,
            thin_spread: float = THIN_SPREAD,
            session_gap_minutes: int = SESSION_GAP_MINUTES) -> GapWaitState:
    """Fold one cycle's observation into the state. Pure."""
    spread_ok_since = state.spread_ok_since
    if (state.last_seen is None
            or (now - state.last_seen) >= timedelta(minutes=session_gap_minutes)):
        spread_ok_since = None  # a new session started; restart the wait clock
    if spread_ok_since is None and spread is not None and spread <= thin_spread:
        spread_ok_since = now
    return GapWaitState(last_seen=now, spread_ok_since=spread_ok_since)


def _parse(raw: str | None) -> datetime | None:
    if not raw:
        return None
    ts = datetime.fromisoformat(raw)
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def load(path: str | Path = STATE_PATH) -> GapWaitState:
    """Read the persisted state. ANY problem -> a fresh (denying) state."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return GapWaitState(last_seen=_parse(data.get("last_seen")),
                            spread_ok_since=_parse(data.get("spread_ok_since")))
    except (OSError, ValueError, TypeError, AttributeError):
        return GapWaitState(None, None)


def save(state: GapWaitState, path: str | Path = STATE_PATH) -> None:
    """Best-effort persist. A write failure must NEVER abort a trading cycle:
    the next cycle simply reloads a fresh (conservative) state."""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "last_seen": state.last_seen.isoformat() if state.last_seen else None,
            "spread_ok_since": (state.spread_ok_since.isoformat()
                                if state.spread_ok_since else None),
        }), encoding="utf-8")
    except OSError:
        pass
