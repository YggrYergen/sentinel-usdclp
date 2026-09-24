"""Adversarial tests for sentinel_engine.opt.walkforward (Task 4.3).

All data here is synthetic and deterministic (plain datetimes). No real
price data, no golden fixtures, no other opt module is touched.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sentinel_engine.opt.walkforward import Fold, anchored_walkforward


def _daily_timeline(start: datetime, n_days: int) -> list[datetime]:
    return [start + timedelta(days=i) for i in range(n_days)]


# ---------------------------------------------------------------------------
# 1. Leakage: no train sample timestamp falls within [T_i - embargo, T_i + test_span]
# ---------------------------------------------------------------------------


def test_no_train_timestamp_within_embargo_and_test_window():
    start = datetime(2024, 1, 1)
    timeline = _daily_timeline(start, 400)  # > 1 year of daily bars
    test_span = timedelta(days=60)
    step = timedelta(days=60)
    embargo = timedelta(days=1)

    folds = anchored_walkforward(timeline, test_span, step, embargo)
    assert len(folds) >= 2, "fixture must produce multiple folds to be adversarial"

    for fold in folds:
        forbidden_lo = fold.split - embargo
        forbidden_hi = fold.split + test_span
        train_ts = [ts for ts in timeline if fold.is_train(ts)]
        assert train_ts, f"fold {fold.index} has an empty train set"
        for ts in train_ts:
            assert not (forbidden_lo <= ts <= forbidden_hi), (
                f"fold {fold.index}: train timestamp {ts} leaks into "
                f"[{forbidden_lo}, {forbidden_hi}]"
            )
            # Equivalent direct assertion against the exposed boundary.
            assert ts < fold.train_end


def test_train_and_test_masks_partition_timeline_without_embargo_overlap():
    start = datetime(2024, 1, 1)
    timeline = _daily_timeline(start, 260)
    folds = anchored_walkforward(
        timeline, test_span=timedelta(days=45), step=timedelta(days=45), embargo=timedelta(days=1)
    )
    assert folds

    for fold in folds:
        train_mask = fold.train_mask(timeline)
        test_mask = fold.test_mask(timeline)
        for ts, is_tr, is_te in zip(timeline, train_mask, test_mask):
            assert not (is_tr and is_te), f"timestamp {ts} counted as both train and test"
            if is_tr:
                assert fold.train_start <= ts < fold.train_end
            if is_te:
                assert fold.test_start <= ts < fold.test_end
            if fold.is_embargo(ts):
                assert not is_tr and not is_te


# ---------------------------------------------------------------------------
# 2. Anchored train always starts at series start and grows
# ---------------------------------------------------------------------------


def test_train_always_anchored_at_series_start_and_grows():
    start = datetime(2024, 1, 1)
    timeline = _daily_timeline(start, 400)
    folds = anchored_walkforward(
        timeline, test_span=timedelta(days=60), step=timedelta(days=60), embargo=timedelta(days=1)
    )
    assert len(folds) >= 3

    for fold in folds:
        assert fold.train_start == start

    # Anchored train window strictly grows fold-over-fold (never rolls).
    train_ends = [f.train_end for f in folds]
    assert train_ends == sorted(train_ends)
    assert len(set(train_ends)) == len(train_ends), "train_end must strictly increase"


# ---------------------------------------------------------------------------
# 3. No train label horizon crosses into test -- purge check on synthetic
#    labeled series (triple-barrier-style: each label has an open time and
#    a resolution/horizon time).
# ---------------------------------------------------------------------------


def test_purge_drops_every_label_whose_horizon_crosses_the_boundary():
    start = datetime(2024, 1, 1)
    timeline = _daily_timeline(start, 200)
    folds = anchored_walkforward(
        timeline, test_span=timedelta(days=40), step=timedelta(days=40), embargo=timedelta(days=1)
    )
    assert folds
    fold = folds[0]

    # Synthetic triple-barrier labels: (open_time, resolution_time) pairs.
    # Horizons vary from 1 to 10 days, deliberately straddling train_end.
    horizons = [timedelta(days=h) for h in range(1, 11)]
    labels = []
    t = fold.train_start
    while t < fold.test_end:
        for h in horizons:
            labels.append((t, t + h))
        t += timedelta(days=3)

    def purge_train_labels(labels, fold: Fold):
        """Local synthetic stand-in for labels.purge_labels_at_boundary:
        keep only labels whose open time is in-train AND whose full event
        window resolves before the (embargoed) train boundary."""
        kept = []
        for open_t, resolve_t in labels:
            if not fold.is_train(open_t):
                continue
            if fold.label_crosses_boundary(open_t, resolve_t):
                continue
            kept.append((open_t, resolve_t))
        return kept

    kept = purge_train_labels(labels, fold)
    assert kept, "purge must not eliminate every train label in this fixture"

    for open_t, resolve_t in kept:
        assert open_t < fold.train_end
        assert resolve_t < fold.train_end, (
            f"purged-in label ({open_t} -> {resolve_t}) crosses train_end "
            f"{fold.train_end}: leakage into embargo/test"
        )

    # Every label whose horizon end reaches into [train_end, test_end] must
    # have been dropped, even if it opened safely inside train.
    dropped = [lab for lab in labels if lab not in kept and fold.is_train(lab[0])]
    for open_t, resolve_t in dropped:
        assert resolve_t >= fold.train_end


def test_label_crosses_boundary_exact_edge():
    start = datetime(2024, 1, 1)
    timeline = _daily_timeline(start, 200)
    fold = anchored_walkforward(
        timeline, test_span=timedelta(days=40), step=timedelta(days=40), embargo=timedelta(days=1)
    )[0]

    just_before = fold.train_end - timedelta(seconds=1)
    exactly_at = fold.train_end
    assert fold.label_crosses_boundary(fold.train_start, just_before) is False
    assert fold.label_crosses_boundary(fold.train_start, exactly_at) is True


# ---------------------------------------------------------------------------
# 4. Step/embargo boundaries exact
# ---------------------------------------------------------------------------


def test_fold_boundaries_are_exact():
    start = datetime(2024, 1, 1)
    timeline = _daily_timeline(start, 400)
    test_span = timedelta(days=60)
    step = timedelta(days=60)
    embargo = timedelta(days=1)

    folds = anchored_walkforward(timeline, test_span, step, embargo)
    assert len(folds) == 5  # k=1..5: split=start+60..300, test_end<=start+399

    for k, fold in enumerate(folds, start=1):
        expected_split = start + k * step
        assert fold.split == expected_split
        assert fold.train_start == start
        assert fold.train_end == expected_split - embargo
        assert fold.test_start == expected_split
        assert fold.test_end == expected_split + test_span
        assert fold.embargo == embargo
        assert fold.index == k - 1

    # No fold's test window overruns the timeline.
    end = max(timeline)
    for fold in folds:
        assert fold.test_end <= end


def test_folds_step_forward_by_exact_step_between_consecutive_splits():
    start = datetime(2024, 1, 1)
    timeline = _daily_timeline(start, 500)
    step = timedelta(days=45)
    folds = anchored_walkforward(timeline, test_span=timedelta(days=30), step=step, embargo=timedelta(days=1))
    assert len(folds) >= 3
    for a, b in zip(folds, folds[1:]):
        assert b.split - a.split == step


def test_custom_embargo_reflected_exactly_in_train_end():
    start = datetime(2024, 1, 1)
    timeline = _daily_timeline(start, 300)
    embargo = timedelta(hours=36)
    folds = anchored_walkforward(
        timeline, test_span=timedelta(days=50), step=timedelta(days=50), embargo=embargo
    )
    assert folds
    for fold in folds:
        assert fold.train_end == fold.split - embargo
        assert fold.embargo_start() == fold.split - embargo


# ---------------------------------------------------------------------------
# Input validation / edge cases
# ---------------------------------------------------------------------------


def test_empty_timeline_raises():
    with pytest.raises(ValueError):
        anchored_walkforward([], timedelta(days=10), timedelta(days=10))


def test_nonpositive_test_span_or_step_raises():
    timeline = _daily_timeline(datetime(2024, 1, 1), 100)
    with pytest.raises(ValueError):
        anchored_walkforward(timeline, timedelta(days=0), timedelta(days=10))
    with pytest.raises(ValueError):
        anchored_walkforward(timeline, timedelta(days=10), timedelta(days=-5))


def test_negative_embargo_raises():
    timeline = _daily_timeline(datetime(2024, 1, 1), 100)
    with pytest.raises(ValueError):
        anchored_walkforward(
            timeline, timedelta(days=10), timedelta(days=10), embargo=timedelta(days=-1)
        )


def test_timeline_too_short_for_one_fold_returns_empty():
    timeline = _daily_timeline(datetime(2024, 1, 1), 10)
    folds = anchored_walkforward(
        timeline, test_span=timedelta(days=60), step=timedelta(days=60), embargo=timedelta(days=1)
    )
    assert folds == []


def test_unsorted_timeline_input_is_handled_via_min_max():
    start = datetime(2024, 1, 1)
    ordered = _daily_timeline(start, 300)
    shuffled = list(reversed(ordered))
    folds_a = anchored_walkforward(
        ordered, test_span=timedelta(days=50), step=timedelta(days=50), embargo=timedelta(days=1)
    )
    folds_b = anchored_walkforward(
        shuffled, test_span=timedelta(days=50), step=timedelta(days=50), embargo=timedelta(days=1)
    )
    assert folds_a == folds_b
