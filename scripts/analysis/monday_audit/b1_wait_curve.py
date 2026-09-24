"""B1 -- how long should the post-reopen wait gate be, in M15 bars?

THE QUESTION: when XAUUSD reopens after a break, SAR/EMA/ATR/SuperTrend are all
computed over missing data for the first bars. A proposed live gate refuses to
open positions for the first N minutes after reopen. This module builds the
curve of what that gate would have cost/saved over the 7-month real-tick
substrate, for N = 2..6 M15 bars, so the plateau/elbow question can be answered
by reading a table instead of arguing about it.

THE GRID IS IN BARS, NOT MINUTES. Entries only ever land on M15 bar
boundaries, so a wait of W minutes only ever blocks the subset of
{15, 30, 45, ...} strictly below W -- a 50-minute wait and a 60-minute wait
both block exactly {15, 30, 45} and are THE SAME EXPERIMENT under two names.
The non-degenerate grid is N in {2,3,4,5,6} bars, i.e. waits of
{30,45,60,75,90} minutes. N=1 (15 min) is excluded from the grid -- the user's
explicit instruction, not this module's choice.

THIS IS TUNING, DECLARED AS SUCH. Searching this curve for an elbow is
parameter search over the same 7 months used everywhere else in Track A. The
B1 MASK verdict (scripts/analysis/monday_audit/b6_masks.py) is pre-committed at
50 minutes and does NOT move because of anything found here -- this is a
separate, explicitly in-sample screening exercise, not a re-litigation of that
verdict. See docs/superpowers/research/2026-07-27-b1-wait-curve.md for the
ranking and the caveat that goes with it.

Reopens are read off the bar stream via session_clock.market_reopens -- NEVER
off the entry stream, which under-counts sessions by ~3x (see that module's
docstring). Timestamps are broker server time throughout; no timezone
correction is applied anywhere in this file.
"""
from __future__ import annotations

import datetime as dt

from scripts.analysis.monday_audit.a3_a4_a5_stats import profit_factor, win_rate
from scripts.analysis.monday_audit.loader import Position, load_positions, write_artifact
from scripts.analysis.monday_audit.session_clock import (
    load_bar_times, market_reopens, minutes_since_reopen)

BAR_MINUTES = 15

# N=1 (15 min) is explicitly excluded from the grid per user instruction.
RUNGS = [2, 3, 4, 5, 6]


def bars_since_reopen(t: dt.datetime, reopens: list[dt.datetime]) -> int | None:
    """Whole M15 bars elapsed since the most recent reopen at/before `t`, or
    None if `t` precedes the first known reopen.

    Entries land only on exact 15-minute multiples after a reopen (never at
    +0 -- see session_clock and the module docstring here), so dividing the
    measured minutes by 15 and rounding is exact, not an approximation."""
    minutes = minutes_since_reopen(t, reopens)
    if minutes is None:
        return None
    return round(minutes / BAR_MINUTES)


def is_blocked(bars: int | None, n: int) -> bool:
    """Would a wait of N bars have blocked an entry at this bars-since-reopen
    count? Positions with no known reopen (bars is None) are never blocked --
    there is nothing to gate them against."""
    return bars is not None and bars < n


def _summary(nets: list[float]) -> dict:
    return {
        "n_kept": len(nets),
        "net_clp": sum(nets),
        "win_rate": win_rate(nets),
        "profit_factor": profit_factor(nets),
    }


def wait_curve(rows: list[Position], reopens: list[dt.datetime],
                rungs: list[int] = RUNGS) -> dict:
    """The full B1 curve: baseline plus one entry per rung in `rungs`, each
    broken down per strategy AND combined. Pure function -- `rows` and
    `reopens` are the only inputs, so this is fully testable off synthetic
    data without touching the real substrate."""
    strategies = sorted({p.strategy for p in rows})
    groups = {s: [p for p in rows if p.strategy == s] for s in strategies}
    groups["COMBINED"] = rows

    bars_of = {p: bars_since_reopen(p.t_in, reopens) for p in rows}

    curve: dict = {}

    baseline: dict = {}
    for key, positions in groups.items():
        nets = [p.net_067lot_clp for p in positions]
        baseline[key] = {**_summary(nets), "n_blocked": 0}
    curve["baseline"] = baseline

    for n in rungs:
        rung: dict = {}
        for key, positions in groups.items():
            kept_nets = [p.net_067lot_clp for p in positions
                         if not is_blocked(bars_of[p], n)]
            base_net = baseline[key]["net_clp"]
            summ = _summary(kept_nets)
            delta = summ["net_clp"] - base_net
            delta_pct = (100.0 * delta / base_net) if base_net else 0.0
            rung[key] = {
                **summ,
                "n_blocked": len(positions) - len(kept_nets),
                "delta_clp": delta,
                "delta_pct": delta_pct,
            }
        curve[f"N{n}"] = rung

    return curve


def _rank_rungs(curve: dict, rungs: list[int]) -> list[dict]:
    """Best-to-worst ranking of the rungs by COMBINED net CLP. Recorded
    explicitly per user instruction -- this IS tuning, and the caveat that it's
    in-sample travels with the ranking wherever it's printed/written."""
    ranked = sorted(
        ({"rung": f"N{n}", "wait_minutes": n * BAR_MINUTES,
          "net_clp": curve[f"N{n}"]["COMBINED"]["net_clp"],
          "delta_pct": curve[f"N{n}"]["COMBINED"]["delta_pct"]}
         for n in rungs),
        key=lambda r: r["net_clp"], reverse=True)
    return ranked


def main() -> int:
    rows = load_positions()
    reopens = market_reopens(load_bar_times())
    curve = wait_curve(rows, reopens)
    ranking = _rank_rungs(curve, RUNGS)

    payload = {
        "n_positions": len(rows),
        "n_reopens": len(reopens),
        "bar_minutes": BAR_MINUTES,
        "rungs_bars": RUNGS,
        "rungs_excluded": [1],
        "curve": curve,
        "ranking_best_to_worst": ranking,
        "caveat": ("In-sample over the same 7 months used to build it. This is "
                   "documentation of what would have happened, not a deployment "
                   "recommendation, and is a separate experiment from the B1 mask "
                   "verdict (pre-committed at 50 minutes)."),
    }
    path = write_artifact("b1_wait_window.json", payload)
    print(f"wrote {path}")
    print(f"baseline COMBINED net = {curve['baseline']['COMBINED']['net_clp']:,.0f} CLP "
          f"(n={curve['baseline']['COMBINED']['n_kept']})")
    for r in ranking:
        print(f"  {r['rung']} ({r['wait_minutes']} min): net={r['net_clp']:,.0f} "
              f"({r['delta_pct']:+.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
