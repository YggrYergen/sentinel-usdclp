"""4.1 -- Triple-barrier labeler + purging-at-boundary.

Machinery only (Fable SS2.4 / SS2.6, plan Phase 4 task 4.1). Operates on plain
synthetic price/time arrays -- no real data is read or referenced here. The
real optimization study runs later, on the user's real lake data, in a
separate component.

Triple-barrier labeling (Lopez de Prado, adapted per Fable SS2.4):
    For each entry index i, walk forward from i+1 through i+horizon (inclusive)
    and find the FIRST bar whose price touches either the take-profit barrier
    (entry_price + tp, for a long-style reference policy) or the stop-loss
    barrier (entry_price - sl). Whichever is touched first wins ("first
    touch"); if both are touched on the SAME bar, stop-loss wins (conservative
    tie-break: intrabar path is unknown, so we assume the worse outcome can
    happen first). If neither barrier is touched within the horizon, the label
    is the vertical/timeout outcome, scored at the horizon bar's price.

    PnL is reported in R-multiples, where 1R == sl (the risk taken). This is
    the "reference-policy" PnL -- it grades the *market path*, not any live
    strategy's actual entries/exits; real trades are only ever used later as
    an independent validation set (Fable SS2.4/SS4 item 5), never fit here.

Purging (Lopez de Prado purged K-fold, adapted to walk-forward, Fable SS2.6):
    A label's "horizon window" spans [entry_index, entry_index + horizon].
    Any label whose horizon window crosses a train/test fold boundary
    (i.e. the window overlaps both sides of the boundary) leaks test-set
    information into the train fold and must be dropped from train.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class BarrierOutcome(str, Enum):
    """Which barrier was touched first for a given entry."""

    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    VERTICAL = "vertical"  # timeout: neither barrier touched within horizon


@dataclass(frozen=True)
class TripleBarrierLabel:
    """One triple-barrier label for an entry at `entry_index`.

    Attributes:
        entry_index: index into the `prices` array where the (hypothetical)
            reference-policy entry occurs.
        touch_index: index of the bar where the outcome was decided (the
            barrier-touch bar, or the horizon bar for a vertical/timeout).
        outcome: which barrier was touched first (or VERTICAL for timeout).
        pnl_r: reference-policy PnL in R-multiples (R == sl distance).
            +tp/sl on take-profit, -1.0 on stop-loss, and the (clipped,
            price-move / sl) ratio on vertical timeout.
        horizon_end_index: entry_index + horizon -- the last index the
            label's decision window could possibly reach. Used for purging.
    """

    entry_index: int
    touch_index: int
    outcome: BarrierOutcome
    pnl_r: float
    horizon_end_index: int


def triple_barrier(
    prices: Sequence[float],
    tp: float,
    sl: float,
    horizon: int,
    entry_indices: Sequence[int] | None = None,
) -> list[TripleBarrierLabel]:
    """Label each entry with its triple-barrier outcome.

    Args:
        prices: synthetic price series (e.g. M1 closes), point-in-time
            ordered (index i is chronologically before index i+1).
        tp: take-profit barrier distance in price units (must be > 0).
        sl: stop-loss barrier distance in price units (must be > 0).
        horizon: max number of bars forward to search before declaring a
            vertical/timeout outcome (must be > 0).
        entry_indices: which indices in `prices` to treat as entries. If
            None, every index that has at least 1 bar of room before the end
            of the series is used (0 .. len(prices)-2).

    Returns:
        One TripleBarrierLabel per entry index that has at least one bar of
        forward data available. Entries with zero forward bars available
        (i.e. the last bar in the series) are silently skipped since no
        outcome can be determined.
    """
    if tp <= 0 or sl <= 0:
        raise ValueError("tp and sl must both be positive barrier distances")
    if horizon <= 0:
        raise ValueError("horizon must be a positive integer")

    n = len(prices)
    if entry_indices is None:
        entry_indices = range(0, max(n - 1, 0))

    labels: list[TripleBarrierLabel] = []
    for i in entry_indices:
        if i < 0 or i >= n - 1:
            continue  # no forward bars available -- outcome undecidable
        entry_price = prices[i]
        tp_price = entry_price + tp
        sl_price = entry_price - sl

        last_index = min(i + horizon, n - 1)
        outcome: BarrierOutcome | None = None
        touch_index = last_index

        for j in range(i + 1, last_index + 1):
            p = prices[j]
            hit_tp = p >= tp_price
            hit_sl = p <= sl_price
            if hit_tp and hit_sl:
                # Both barriers reachable on the same bar: intrabar path is
                # unknown from a single price point, so the stop-loss wins
                # (conservative tie-break).
                outcome = BarrierOutcome.STOP_LOSS
                touch_index = j
                break
            if hit_sl:
                outcome = BarrierOutcome.STOP_LOSS
                touch_index = j
                break
            if hit_tp:
                outcome = BarrierOutcome.TAKE_PROFIT
                touch_index = j
                break

        if outcome is None:
            outcome = BarrierOutcome.VERTICAL
            touch_index = last_index

        if outcome is BarrierOutcome.TAKE_PROFIT:
            pnl_r = tp / sl
        elif outcome is BarrierOutcome.STOP_LOSS:
            pnl_r = -1.0
        else:
            move = prices[touch_index] - entry_price
            pnl_r = move / sl

        labels.append(
            TripleBarrierLabel(
                entry_index=i,
                touch_index=touch_index,
                outcome=outcome,
                pnl_r=pnl_r,
                horizon_end_index=i + horizon,
            )
        )

    return labels


def purge_labels_at_boundary(
    labels: Sequence[TripleBarrierLabel],
    train_end_index: int,
    embargo: int = 0,
) -> list[TripleBarrierLabel]:
    """Drop any train-fold label whose horizon window crosses into the test fold.

    Per Fable SS2.6 (Lopez de Prado purged K-fold adapted to walk-forward): a
    label belongs to "train" if its entry_index <= train_end_index. Such a
    label leaks test-set information if its horizon window extends past the
    boundary, i.e. `horizon_end_index > train_end_index`. Those labels are
    dropped. Labels entirely on the test side (entry_index > train_end_index)
    are left untouched -- purging only ever removes labels FROM train.

    An optional `embargo` further pulls the effective boundary back so that
    train labels must not only end at-or-before the boundary but also leave
    an embargo gap before it: the survival condition tightens to
    `horizon_end_index <= train_end_index - embargo`.

    Args:
        labels: labels produced by `triple_barrier`, unfiltered.
        train_end_index: last index (inclusive) belonging to the train fold;
            everything with entry_index > train_end_index is test.
        embargo: number of bars of additional purge margin before the
            boundary (Fable SS2.6 specifies a 1-day embargo for the real
            walk-forward; this parameter is left generic in bars/days units
            matching whatever the caller's index unit is).

    Returns:
        The filtered label list: all test-side labels, plus train-side
        labels whose horizon window does not cross the (embargo-adjusted)
        boundary.
    """
    if embargo < 0:
        raise ValueError("embargo must be >= 0")

    purge_cutoff = train_end_index - embargo
    kept: list[TripleBarrierLabel] = []
    for label in labels:
        is_train = label.entry_index <= train_end_index
        if is_train and label.horizon_end_index > purge_cutoff:
            continue  # purged: horizon window crosses into test/embargo
        kept.append(label)
    return kept
