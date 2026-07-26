"""A1 -- verify the max drawdown of the S6+S7+SuperTrend track at 0.1 lot.

The -28,6 % figure in circulation is a rule of three from the 0.67-lot number,
never checked against the position stream. The trader has already fixed the lot
at 0.1 regardless (spec R2), so this cannot change a deployment decision: it
exists so the number that goes into the Monday document is a computed one.

Equity is stepped at t_out (a trade moves the balance when it CLOSES).
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.analysis.monday_audit.loader import load_positions, write_artifact

ACCOUNT_BALANCE_CLP = 59_600_000.0
CHAMPION_LOT = 0.1


@dataclass(frozen=True)
class Drawdown:
    max_dd: float
    peak_equity: float
    trough_equity: float
    peak_index: int
    trough_index: int


def max_drawdown(deltas: list[float]) -> Drawdown:
    """Largest peak-to-trough drop of the cumulative sum of `deltas`."""
    equity = 0.0
    peak = 0.0
    peak_i = -1
    best = Drawdown(0.0, 0.0, 0.0, -1, -1)
    for i, d in enumerate(deltas):
        equity += d
        if equity > peak:
            peak, peak_i = equity, i
        drop = peak - equity
        if drop > best.max_dd:
            best = Drawdown(drop, peak, equity, peak_i, i)
    return best


def main() -> int:
    rows = sorted(load_positions(), key=lambda p: (p.t_out, p.strategy, p.t_in))
    deltas = [p.net_at_lot(CHAMPION_LOT) for p in rows]
    dd = max_drawdown(deltas)
    payload = {
        "lot": CHAMPION_LOT,
        "account_balance_clp": ACCOUNT_BALANCE_CLP,
        "n_positions": len(rows),
        "final_net_clp": sum(deltas),
        "max_dd_clp": dd.max_dd,
        "max_dd_pct_of_initial": 100.0 * dd.max_dd / ACCOUNT_BALANCE_CLP,
        "max_dd_pct_of_peak_equity": (
            100.0 * dd.max_dd / (ACCOUNT_BALANCE_CLP + dd.peak_equity)),
        "peak_equity_clp": dd.peak_equity,
        "trough_equity_clp": dd.trough_equity,
        "t_peak": rows[dd.peak_index].t_out if dd.peak_index >= 0 else None,
        "t_trough": rows[dd.trough_index].t_out if dd.trough_index >= 0 else None,
    }
    path = write_artifact("a1_maxdd.json", payload)
    print(f"wrote {path}")
    print(f"max DD @{CHAMPION_LOT} lot: {dd.max_dd:,.0f} CLP = "
          f"{payload['max_dd_pct_of_initial']:.2f}% of the initial balance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
