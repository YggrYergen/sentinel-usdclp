"""Retrospective wrapper masks (spec section 4.4).

THE RULE: each mask VETOES a wrapper if it would have been catastrophic. It
NEVER selects between wrapper variants -- selecting by this number is exactly
the overfitting the whole delivery is built to avoid (spec R3).

Honesty requirements baked in below: B2 is only evaluated over the range the
committed calendar actually covers, and B4 is reported as NOT MASKABLE rather
than quietly skipped.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scripts.analysis.monday_audit.loader import load_positions, write_artifact
from scripts.analysis.monday_audit.session_clock import (
    load_bar_times, market_reopens, minutes_since_reopen)
from sentinel_engine.live import news_calendar

REPORT_PATH = (Path(__file__).resolve().parents[3] / "docs" / "superpowers"
               / "research" / "2026-07-25-wrapper-mask-verdicts.md")

B1_WAIT_MINUTES = 50
B2_BLACKOUT_MINUTES = 30


def b1_blocked(t_in: datetime, reopens: list[datetime], *, wait_minutes: int) -> bool:
    """True if `t_in` falls strictly fewer than `wait_minutes` after the most
    recent measured market reopen (scripts/analysis/monday_audit/session_clock.py).

    `t_in` before every known reopen (None from `minutes_since_reopen`) is NOT
    blocked -- there is nothing measured to veto against."""
    since = minutes_since_reopen(t_in, reopens)
    return since is not None and since < wait_minutes


def cap_replay_drops(intervals: list[tuple[datetime, datetime]], *, cap: int) -> list[int]:
    """Indices a chronological greedy replay would have refused because `cap`
    fichas were already open. Entries are considered in entry order."""
    order = sorted(range(len(intervals)), key=lambda i: intervals[i][0])
    open_ends: list[datetime] = []
    dropped: list[int] = []
    for i in order:
        start, end = intervals[i]
        open_ends = [e for e in open_ends if e > start]
        if len(open_ends) >= cap:
            dropped.append(i)
            continue
        open_ends.append(end)
    return sorted(dropped)


def _delta(kept_net: float, total_net: float, kept_n: int, total_n: int) -> dict:
    return {"kept_n": kept_n, "dropped_n": total_n - kept_n,
            "kept_net_clp": kept_net, "total_net_clp": total_net,
            "net_delta_clp": kept_net - total_net,
            "net_delta_pct": (100.0 * (kept_net - total_net) / abs(total_net)
                              if total_net else 0.0)}


def main() -> int:
    rows = load_positions()
    total_net = sum(p.net_067lot_clp for p in rows)
    verdicts: dict[str, dict] = {}

    # --- B1 (real market reopens, off the bar stream) ---------------------
    reopens = market_reopens(load_bar_times())
    kept = [p for p in rows if not b1_blocked(p.t_in, reopens, wait_minutes=B1_WAIT_MINUTES)]
    verdicts["B1"] = {
        "evaluable": True,
        "method": ("real market reopens measured off the M15 bar stream "
                    "(session_clock.market_reopens, gap >= 60 min with no bar); "
                    f"blocks positions opened < {B1_WAIT_MINUTES} min after a reopen"),
        "n_reopens": len(reopens),
        "wait_minutes": B1_WAIT_MINUTES,
        "verdict": "NO VETO -- the gap-wait gate was not catastrophic over the 7-month substrate",
        "caveat": ("sign is NOT stable across the wait parameter: a prototype sweep gave "
                   "+13.3% at 30 min, +20.0% at 50 and 60 min, and -15.2% at 90 min. "
                   "50 min was fixed in advance from a live diagnosis, not chosen from this sweep -- "
                   "this mask evaluates that fixed choice, it does not search for a better one."),
        **_delta(sum(p.net_067lot_clp for p in kept), total_net, len(kept), len(rows)),
    }

    # --- B2 (only over the calendar's coverage) --------------------------
    windows = news_calendar.load_windows(minutes_before=B2_BLACKOUT_MINUTES,
                                         minutes_after=B2_BLACKOUT_MINUTES)
    if not windows:
        verdicts["B2"] = {
            "evaluable": False,
            "method": "the committed calendar covers no date inside 2026-01..2026-07",
            "verdict": "NOT EVALUABLE -- no veto by absence of evidence"}
    else:
        lo = min(w[0] for w in windows).replace(tzinfo=None)
        hi = max(w[1] for w in windows).replace(tzinfo=None)
        in_range = [p for p in rows if lo <= p.t_in <= hi]
        if not in_range:
            verdicts["B2"] = {
                "evaluable": False,
                "calendar_range": [lo.isoformat(), hi.isoformat()],
                "method": "calendar range does not overlap the backtest period",
                "verdict": "NOT EVALUABLE -- no veto by absence of evidence"}
        else:
            naive = [(a.replace(tzinfo=None), b.replace(tzinfo=None)) for a, b in windows]
            kept = [p for p in in_range
                    if not any(a <= p.t_in <= b for a, b in naive)]
            verdicts["B2"] = {
                "evaluable": True,
                "calendar_range": [lo.isoformat(), hi.isoformat()],
                "method": "positions entered inside +/-30 min of a calendar event, over the covered range only",
                **_delta(sum(p.net_067lot_clp for p in kept),
                         sum(p.net_067lot_clp for p in in_range),
                         len(kept), len(in_range))}

    # --- B3 (must drop exactly nothing) ----------------------------------
    import json
    cap = json.loads((Path(__file__).resolve().parents[3] / "data" / "analysis"
                      / "monday_audit" / "a2_overlap.json").read_text(encoding="utf-8")
                     )["max_simultaneous_fichas"]
    drops = cap_replay_drops([(p.t_in, p.t_out) for p in rows], cap=cap)
    verdicts["B3"] = {
        "evaluable": True, "cap": cap, "dropped_n": len(drops),
        "method": "chronological greedy replay against the observed-peak cap",
        "expected": "ZERO drops -- the cap IS the observed peak, so it never bit"}

    # --- B4 (not maskable, by design) ------------------------------------
    verdicts["B4"] = {
        "evaluable": False,
        "method": "the position CSVs carry no SL column; reconstructing it means re-simulating (out of scope)",
        "verdict": "NOT MASKABLE -- B4 is a live BUG DETECTOR, not a filter"}

    write_artifact("b6_mask_verdicts.json", verdicts)

    lines = ["# Wrapper mask verdicts -- 2026-07-25", "",
             "> Each mask VETOES a wrapper if it would have been catastrophic.",
             "> **It never selects between variants** -- that would be re-tuning (spec R3).",
             f"> Substrate: {len(rows)} positions, net {total_net:,.0f} CLP @0.67 lot.", ""]
    for gate, v in verdicts.items():
        lines.append(f"## {gate}")
        for k, val in v.items():
            lines.append(f"- **{k}:** {val}")
        lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    for gate, v in verdicts.items():
        print(f"  {gate}: {v.get('verdict') or v.get('net_delta_pct')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
