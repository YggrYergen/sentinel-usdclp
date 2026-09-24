"""A2 -- how much the three strategies overlap, and the exposure cap that
follows from it (spec section 5.1 item 2; feeds the challenger's B3 gate).

THE CAP RULE WAS FIXED IN ADVANCE: B3's cap is the OBSERVED MAXIMUM of
simultaneous fichas across the 7 months. It is therefore a bound that would
never have bitten -- conservative by construction -- and NOT a number chosen by
comparing outcomes. Choosing it by outcome would be re-tuning (spec R3).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations

from scripts.analysis.monday_audit.loader import load_positions, write_artifact


def max_concurrency(intervals: list[tuple[datetime, datetime]]
                    ) -> tuple[int, dict[int, int]]:
    """Peak simultaneous intervals, plus a histogram of how many distinct
    moments ran at each level. Exits are processed BEFORE entries at an equal
    timestamp, so a close-then-open at the same instant is sequential."""
    events: list[tuple[datetime, int]] = []
    for start, end in intervals:
        events.append((start, +1))
        events.append((end, -1))
    events.sort(key=lambda e: (e[0], e[1]))  # -1 sorts before +1
    live = 0
    peak = 0
    hist: Counter[int] = Counter()
    for _t, delta in events:
        live += delta
        peak = max(peak, live)
        hist[live] += 1
    return peak, dict(hist)


def pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation; 0.0 when either series has zero variance."""
    n = len(xs)
    if n == 0 or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0.0 or syy == 0.0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def _percentile_level(hist: dict[int, int], pct: float) -> int:
    """Highest concurrency level at or below the given percentile of moments."""
    total = sum(hist.values())
    if total == 0:
        return 0
    running = 0
    for level in sorted(hist):
        running += hist[level]
        if running / total >= pct:
            return level
    return max(hist)


def main() -> int:
    rows = load_positions()
    peak, hist = max_concurrency([(p.t_in, p.t_out) for p in rows])

    daily: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for p in rows:
        daily[p.strategy][p.t_out.date().isoformat()] += p.net_067lot_clp
    strategies = sorted(daily)
    all_days = sorted({d for s in strategies for d in daily[s]})
    corr = {}
    for a, b in combinations(strategies, 2):
        xs = [daily[a].get(d, 0.0) for d in all_days]
        ys = [daily[b].get(d, 0.0) for d in all_days]
        corr[f"{a}|{b}"] = pearson(xs, ys)

    moments = sum(hist.values())
    payload = {
        "n_positions": len(rows),
        "max_simultaneous_fichas": peak,
        "simultaneous_histogram": hist,
        "p95_simultaneous": _percentile_level(hist, 0.95),
        "p99_simultaneous": _percentile_level(hist, 0.99),
        "pct_time_with_any_position": (
            100.0 * sum(c for lvl, c in hist.items() if lvl > 0) / moments
            if moments else 0.0),
        "pairwise_daily_net_correlation": corr,
        "n_trading_days": len(all_days),
    }
    path = write_artifact("a2_overlap.json", payload)
    print(f"wrote {path}")
    print(f"B3 CAP (observed peak simultaneous fichas) = {peak}")
    for k, v in corr.items():
        print(f"  corr {k}: {v:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
