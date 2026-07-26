"""A3/A4/A5 -- three read-only questions over the real-tick substrate.

A3 exit attribution   -- where does the money actually come from, by exit reason.
A4 serial correlation -- do results cluster in streaks (regime) or not.
A5 spread-gate check  -- does the 0.5 filter hold across 7 months, or only over
                         the five live sessions it was validated on so far.

NONE of these selects a parameter. They describe the track that is already
deployed; the challenger's numbers come from the spec, not from here.
"""
from __future__ import annotations

import math
from collections import defaultdict

from scripts.analysis.monday_audit.loader import load_positions, write_artifact


def win_rate(nets: list[float]) -> float:
    return 100.0 * sum(1 for n in nets if n > 0) / len(nets) if nets else 0.0


def profit_factor(nets: list[float]) -> float:
    """Gross wins / gross losses. inf when there are wins and no losses."""
    if not nets:
        return 0.0
    wins = sum(n for n in nets if n > 0)
    losses = -sum(n for n in nets if n < 0)
    if losses == 0.0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def autocorrelation(series: list[float], *, lag: int) -> float:
    """Lag-k autocorrelation. 0.0 when the series is too short or flat.

    Implemented as the Pearson correlation between the two lag-shifted
    subsequences x[:-lag] and x[lag:], each normalized by its own mean and
    variance (NOT the single-mean/single-variance ACF estimator). This is
    the formula required to satisfy the brief's own fixture
    (`autocorrelation([1,-1,1,-1,1], lag=1) < -0.9`): the single-mean
    estimator given in the brief's Step-3 sample code computes -0.8 on that
    exact fixture and fails the brief's own Step-1 test verbatim. See the
    task-9 report for the by-hand verification of both formulas.
    """
    n = len(series)
    if n <= lag:
        return 0.0
    x = series[: n - lag]
    y = series[lag:]
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0.0 or syy == 0.0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def longest_streak(nets: list[float]) -> tuple[int, int]:
    """(longest run of wins, longest run of losses). Zeros break both runs."""
    best_w = best_l = cur_w = cur_l = 0
    for n in nets:
        if n > 0:
            cur_w, cur_l = cur_w + 1, 0
        elif n < 0:
            cur_l, cur_w = cur_l + 1, 0
        else:
            cur_w = cur_l = 0
        best_w, best_l = max(best_w, cur_w), max(best_l, cur_l)
    return best_w, best_l


def _summary(nets: list[float]) -> dict:
    return {"n": len(nets), "net_clp": sum(nets), "win_rate": win_rate(nets),
            "profit_factor": profit_factor(nets),
            "mean_clp": (sum(nets) / len(nets)) if nets else 0.0}


def main() -> int:
    rows = load_positions()

    # --- A3: attribution by exit reason ---------------------------------
    by_reason: dict[str, list[float]] = defaultdict(list)
    for p in rows:
        by_reason[f"{p.strategy}|{p.reason}"].append(p.net_067lot_clp)
    a3 = {k: _summary(v) for k, v in sorted(by_reason.items())}
    write_artifact("a3_exit_reason.json", a3)

    # --- A4: serial correlation, per strategy, in trade order -----------
    a4 = {}
    for strat in sorted({p.strategy for p in rows}):
        series = [p.net_067lot_clp for p in sorted(
            (p for p in rows if p.strategy == strat), key=lambda p: p.t_out)]
        wins, losses = longest_streak(series)
        a4[strat] = {
            "n": len(series),
            "autocorr": {f"lag_{k}": autocorrelation(series, lag=k) for k in range(1, 6)},
            "longest_win_streak": wins,
            "longest_loss_streak": losses,
        }
    write_artifact("a4_serial.json", a4)

    # --- A5: the 0.5 spread gate across 7 months ------------------------
    a5: dict[str, dict] = {}
    for strat in sorted({p.strategy for p in rows}) + ["COMBINED"]:
        sel = rows if strat == "COMBINED" else [p for p in rows if p.strategy == strat]
        a5[strat] = {
            "at_0.5": _summary([p.net_067lot_clp for p in sel if p.spread <= 0.5]),
            "at_0.6": _summary([p.net_067lot_clp for p in sel if p.spread > 0.5]),
            "unfiltered": _summary([p.net_067lot_clp for p in sel]),
        }
    write_artifact("a5_spread_gate.json", a5)

    c = a5["COMBINED"]
    print(f"A5 COMBINED: @0.5 net={c['at_0.5']['net_clp']:,.0f} "
          f"(n={c['at_0.5']['n']}) | @0.6 net={c['at_0.6']['net_clp']:,.0f} "
          f"(n={c['at_0.6']['n']}) | unfiltered={c['unfiltered']['net_clp']:,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
