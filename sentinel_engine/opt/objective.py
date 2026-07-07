"""P4.2 — Objective metric + constraint gates (Fable Sec 2.4 / Sec 4 item 1).

Scalar for the search:

    J = ProfitFactor_capped(3.0) x sqrt(n_trades / n_ref)

expressed in R-multiples (PnL / initial risk), subject to constraint gates:

    maxDD_R    <= max_dd_mult * baseline_maxDD_R   (default mult 1.25)
    n_trades   >= n_min                            (statistical floor, default 30)
    win_rate   >= win_rate_min                      (default 0.35)

Constraint violations are NOT optimized around softly -- they are heavily
penalized (the caller can treat ``gates_passed=False`` as a signal to prune
the Optuna trial outright). ``score_accuracy`` and ``filter_rate_pct`` are
deliberately NOT inputs to this module: per Fable Sec 2.4/Sec 4 item 1 they
are validation GATES applied elsewhere in the pipeline (Layer 3, real-trade
cross-check), never optimization targets here.

This module is pure/data-agnostic: it consumes a plain sequence of realized
trade R-multiples (``trades_R``) plus a handful of scalars. It does not read
any live config, price lake, or golden fixtures -- callers (walk-forward,
search) are responsible for producing ``trades_R`` from real or synthetic
data.

Ambiguity resolutions (spec silent on exact mechanics, resolved here):
  - ``n_ref`` (the reference-policy trade count for the sqrt(n) term) is a
    required caller-supplied input -- it comes from Layer 2's fixed
    reference policy per fold (Fable Sec 2.4), which this module does not
    compute. If ``n_ref <= 0`` the ratio term is treated as 0 (no reference
    signal -> no reward), not a divide-by-zero crash.
  - ``baseline_maxDD_R`` (for the maxDD gate) is optional. When omitted, the
    maxDD-vs-baseline gate is skipped (flagged in the result as
    ``constraints_skipped``) rather than silently passing or crashing --
    walk-forward will supply the production baseline once it exists.
  - Profit factor with zero losing R (all wins) is defined as exactly the
    cap (``pf_cap``), not +inf -- consistent with "capped PF" intent and
    avoids infinite/undefined scores.
  - Daily-R Sharpe requires a date axis this module doesn't have from a bare
    R-multiple list. Callers may pass ``daily_returns_R`` (one aggregated R
    figure per calendar day) for a true daily Sharpe; if omitted, a
    trade-level Sharpe (mean/stdev of ``trades_R``) is reported instead and
    flagged via ``sharpe_is_trade_level=True`` so callers never mistake it
    for the real day-indexed figure.
  - On gate violation the score is pinned to ``PENALTY_SCORE`` (a sentinel
    below any attainable passing score, since a passing score is always
    >= 0) rather than 0.0, so a config that barely fails a gate is never
    numerically confused with a config that passes but has legitimately
    zero edge (PF capped at 0 because it lost every trade, e.g.).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

#: score assigned to any gate-violating trial; guaranteed to be lower than
#: any passing trial's score (passing scores are always >= 0).
PENALTY_SCORE = -1.0

DEFAULT_PF_CAP = 3.0
DEFAULT_N_MIN = 30
DEFAULT_WIN_RATE_MIN = 0.35
DEFAULT_MAX_DD_MULT = 1.25


@dataclass(frozen=True)
class ObjectiveResult:
    """Full result of scoring one candidate's trade set.

    ``score`` is the scalar handed to the search/pruner. ``metrics`` is the
    full persisted metric set (Fable Sec 2.4: "full metric set persisted").
    """

    score: float
    gates_passed: bool
    violations: List[str] = field(default_factory=list)
    constraints_skipped: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


#: sentinel raw profit-factor value used when there are zero losing R
#: (division would otherwise be +inf, which is not JSON/SQLite-persistable
#: and not meaningfully comparable). Large enough to always be > any
#: realistic pf_cap so it never masquerades as a normal finite PF.
_UNCAPPED_PF_SENTINEL = 1.0e6


def _profit_factor(trades_R: Sequence[float]) -> float:
    """Raw (uncapped) profit factor: sum(wins) / abs(sum(losses)).

    Zero losing R with positive gains maps to ``_UNCAPPED_PF_SENTINEL``
    (finite, persistable) rather than +inf; zero gains and zero losses maps
    to 0.0 (no edge either way).
    """
    gains = sum(r for r in trades_R if r > 0)
    losses = -sum(r for r in trades_R if r < 0)
    if losses <= 0:
        return _UNCAPPED_PF_SENTINEL if gains > 0 else 0.0
    return gains / losses


def _max_drawdown_R(trades_R: Sequence[float]) -> float:
    """Max drawdown, in R, of the cumulative-R equity curve in trade order."""
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in trades_R:
        equity += r
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _sharpe(series: Sequence[float]) -> float:
    n = len(series)
    if n < 2:
        return 0.0
    mean = sum(series) / n
    var = sum((x - mean) ** 2 for x in series) / (n - 1)
    stdev = math.sqrt(var)
    if stdev == 0.0:
        return 0.0
    return mean / stdev


def objective(
    trades_R: Sequence[float],
    *,
    n_ref: float,
    baseline_maxDD_R: Optional[float] = None,
    daily_returns_R: Optional[Sequence[float]] = None,
    pf_cap: float = DEFAULT_PF_CAP,
    n_min: int = DEFAULT_N_MIN,
    win_rate_min: float = DEFAULT_WIN_RATE_MIN,
    max_dd_mult: float = DEFAULT_MAX_DD_MULT,
) -> ObjectiveResult:
    """Score one candidate's realized trade set.

    Args:
        trades_R: realized PnL per trade, in R-multiples (PnL / initial
            risk), in chronological order (order matters for the drawdown
            calculation).
        n_ref: reference-policy trade count for this fold/slice (Layer 2,
            fixed reference policy) -- the denominator of the trade-count
            ratio term.
        baseline_maxDD_R: production/baseline max drawdown in R for the
            maxDD gate. If ``None`` the gate is skipped and flagged.
        daily_returns_R: optional per-day aggregated R series for a true
            daily-R Sharpe. If omitted, a trade-level Sharpe is reported
            (flagged in metrics).
        pf_cap: profit-factor cap (default 3.0 per Fable Sec 2.4).
        n_min: minimum trade count floor (default 30/fold per Fable Sec 4).
        win_rate_min: minimum win-rate gate (default 0.35).
        max_dd_mult: maxDD gate multiplier vs baseline (default 1.25).

    Returns:
        ObjectiveResult with the scalar ``score`` for search plus the full
        metric set for reporting.
    """
    n_trades = len(trades_R)
    violations: List[str] = []
    constraints_skipped: List[str] = []

    net_pnl_R = float(sum(trades_R))
    n_wins = sum(1 for r in trades_R if r > 0)
    win_rate = (n_wins / n_trades) if n_trades > 0 else 0.0
    avg_R = (net_pnl_R / n_trades) if n_trades > 0 else 0.0
    maxDD_R = _max_drawdown_R(trades_R)
    profit_factor_raw = _profit_factor(trades_R)
    profit_factor_capped = min(profit_factor_raw, pf_cap)

    if daily_returns_R is not None:
        sharpe_daily_R = _sharpe(daily_returns_R)
        sharpe_is_trade_level = False
    else:
        sharpe_daily_R = _sharpe(trades_R)
        sharpe_is_trade_level = True

    # --- constraint gates (Fable Sec 2.4 / Sec 4 item 1) ---
    if n_trades < n_min:
        violations.append(
            f"n_trades {n_trades} < n_min {n_min} (trade-starvation floor)"
        )

    if n_trades > 0 and win_rate < win_rate_min:
        violations.append(
            f"win_rate {win_rate:.4f} < win_rate_min {win_rate_min}"
        )
    elif n_trades == 0:
        violations.append("n_trades 0: win_rate undefined, treated as failing gate")

    if baseline_maxDD_R is None:
        constraints_skipped.append("maxDD (no baseline_maxDD_R supplied)")
    else:
        max_allowed_dd = max_dd_mult * baseline_maxDD_R
        if maxDD_R > max_allowed_dd:
            violations.append(
                f"maxDD_R {maxDD_R:.4f} > {max_dd_mult} x baseline "
                f"{baseline_maxDD_R:.4f} = {max_allowed_dd:.4f}"
            )

    gates_passed = len(violations) == 0

    trade_count_ratio = (n_trades / n_ref) if n_ref > 0 else 0.0
    raw_score = profit_factor_capped * math.sqrt(max(trade_count_ratio, 0.0))

    score = raw_score if gates_passed else PENALTY_SCORE

    metrics: Dict[str, float] = {
        "net_pnl_R": net_pnl_R,
        "win_rate": win_rate,
        "maxDD_R": maxDD_R,
        "avg_R": avg_R,
        "profit_factor": profit_factor_raw,
        "profit_factor_capped": profit_factor_capped,
        "sharpe_daily_R": sharpe_daily_R,
        "sharpe_is_trade_level": sharpe_is_trade_level,
        "n_trades": n_trades,
        "n_ref": n_ref,
        "trade_count_ratio": trade_count_ratio,
        "raw_score": raw_score,
        "score": score,
    }

    return ObjectiveResult(
        score=score,
        gates_passed=gates_passed,
        violations=violations,
        constraints_skipped=constraints_skipped,
        metrics=metrics,
    )
