"""sentinel_engine/live/risk_gates.py -- OPT-IN opening gates for the
CHALLENGER sleeve (2026-07-25 Monday delivery, spec section 4.3).

THE ISOLATION CONTRACT: a config WITHOUT a `risk_gates` key never reaches this
module, so the champion sleeve's OPEN decisions stay byte-identical to what has
been running in production. Everything here is a PURE function of an immutable
`GateInput` -- no MT5, no clock, no filesystem -- so the whole risk layer is
unit-testable without a terminal.

The four gates, evaluated in this fixed order (the FIRST denial is the one
reported, so the audit log always names the outermost reason):

  B1 `gap_wait_minutes`      -- do not open until N minutes after the spread
                                first printed thin following a session reopen.
  B2 `news_blackout_minutes` -- do not open inside +/-N min of a calendar event.
                                FAIL-CLOSED: no calendar => no opens.
  B3 `max_open_fichas`       -- cap simultaneous fichas in the sleeve. Expressed
                                in FICHAS, so it is independent of lot size.
  B4 `min_sl_distance`       -- refuse an SL closer to market than the broker
                                minimum. A hit here is a BUG, not a filter.

A key that is absent is a gate that is not evaluated. NEVER add a gate key to a
shared config dict (that would leak into the champion) -- see live_configs_20.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GateInput:
    """Everything the gates need, captured once per OPEN decision.

    `now` is REAL UTC (the machine clock), never an MT5 bar timestamp -- the
    broker's server clock is a different clock and mixing them silently shifts
    every news window by hours.
    """
    now: datetime
    spread_ok_since: datetime | None
    open_fichas: int
    desired_sl: float | None
    market_ref: float | None
    news_windows: tuple[tuple[datetime, datetime], ...] | None


@dataclass(frozen=True)
class GateDecision:
    allow: bool
    gate: str
    reason: str


_ALLOW = GateDecision(True, "", "all gates passed")


def evaluate_open_gates(gates: dict[str, Any] | None, gi: GateInput) -> GateDecision:
    """Decide whether ONE new position may be opened. Never raises for ordinary
    inputs; callers still wrap it fail-closed (a bug in the challenger's risk
    layer must never abort the champion's cycle)."""
    if not gates:
        return _ALLOW

    wait_min = gates.get("gap_wait_minutes")
    if wait_min is not None:
        if gi.spread_ok_since is None:
            return GateDecision(
                False, "B1",
                f"gap-wait: the thin-spread regime has not started since the "
                f"session reopened (need {wait_min} min after it does)")
        waited = (gi.now - gi.spread_ok_since).total_seconds() / 60.0
        if waited < wait_min:
            return GateDecision(
                False, "B1",
                f"gap-wait: only {waited:.1f} of {wait_min} min elapsed since "
                f"spread went thin at {gi.spread_ok_since.isoformat()}")

    blackout_min = gates.get("news_blackout_minutes")
    if blackout_min is not None:
        if gi.news_windows is None:
            return GateDecision(
                False, "B2",
                "news calendar missing or unreadable -> fail-closed (the "
                "challenger does not open without a calendar)")
        for start, end in gi.news_windows:
            if start <= gi.now <= end:
                return GateDecision(
                    False, "B2",
                    f"inside news blackout {start.isoformat()}..{end.isoformat()} "
                    f"(+/-{blackout_min} min, by convention -- never tuned)")

    cap = gates.get("max_open_fichas")
    if cap is not None and gi.open_fichas >= cap:
        return GateDecision(
            False, "B3",
            f"exposure cap: {gi.open_fichas} fichas already open in the sleeve "
            f"(cap {cap})")

    min_dist = gates.get("min_sl_distance")
    if min_dist is not None:
        if gi.desired_sl is None or gi.market_ref is None:
            return GateDecision(
                False, "B4",
                "SL legality unverifiable (no desired SL or no market ref) "
                "-> fail-closed")
        dist = abs(gi.market_ref - gi.desired_sl)
        if dist < min_dist:
            return GateDecision(
                False, "B4",
                f"ILLEGAL SL: distance {dist:.5f} < broker minimum "
                f"{min_dist:.5f} (sl={gi.desired_sl} ref={gi.market_ref}) -- "
                f"THIS IS A BUG, investigate; do not 'compensate' with a filter")

    return _ALLOW
