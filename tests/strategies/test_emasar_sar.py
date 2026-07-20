"""tests/strategies/test_emasar_sar.py -- W2-T4 (honest program):
pins the additive stop-and-reverse lever (P55) on
`sentinel_engine.strategies.emasar_variant.simular_variant`.

  New kwarg `stop_and_reverse: bool = False` (default False = OFF). When True,
  an OPPOSITE-direction signal that fires while a position is open closes ALL
  open fichas at that bar's close (exit_reason `"reverse"`) and IMMEDIATELY
  opens the opposite direction on the SAME bar (a net reverse), instead of
  ignoring the signal (the classic `if fichas: continue` deferral). Same-
  direction signals while open keep the current no-pyramiding behavior. The
  reverse close and the new open are priced at the bar's close via the EXISTING
  honest fill path under `live_fill_mode` (no new fill route). Long and short
  are never held simultaneously.

Additive and OFF by default: the `stop_and_reverse=False` default must be
byte-identical to pre-change behavior. Pinned here.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from sentinel_engine.strategies.emasar_variant import simular_variant

# Params that actually produce entries AND direction changes (tight trails so
# fichas cycle fast and both long and short signals fire across the fixture --
# makes both byte-identity and the reverse behavior meaningful/non-vacuous).
SAR_PARAMS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=300.0, f2_trail_pips=300.0, f3_trail_pips=300.0,
    init_sl_range_k=1.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)


def _synthetic_bars(n: int = 300, seed: int = 120) -> list[dict]:
    """Same deterministic generator shape as test_emasar_confirmbar's fixture."""
    rnd = random.Random(seed)
    bars = []
    price = 4500.0
    base_epoch = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        open_ = price - drift
        close = price
        high = max(open_, close) + abs(rnd.uniform(0.3, 1.2))
        low = min(open_, close) - abs(rnd.uniform(0.3, 1.2))
        bars.append({"open": open_, "high": high, "low": low, "close": close,
                     "t": base_epoch + k * 60})
    return bars


def _entries(events: list[dict]) -> list[dict]:
    return [ev for ev in events if ev["motivo"] in ("ENTRY_L", "ENTRY_S")]


def _reverses(events: list[dict]) -> list[dict]:
    return [ev for ev in events if ev["motivo"] == "reverse"]


# ---------------------------------------------------------------------------
# (1) byte-identity: stop_and_reverse=False (default) is a byte-identical no-op
#     vs. NOT passing the kwarg at all, on params that produce direction
#     changes.
# ---------------------------------------------------------------------------

def test_stop_and_reverse_default_is_byte_identical_noop_synthetic():
    bars = _synthetic_bars(300, seed=120)
    baseline = simular_variant(bars, symbol="XAUUSD", **SAR_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", stop_and_reverse=False, **SAR_PARAMS)
    assert with_default == baseline


def test_stop_and_reverse_default_is_byte_identical_noop_seed7():
    bars = _synthetic_bars(400, seed=7)
    baseline = simular_variant(bars, symbol="XAUUSD", **SAR_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", stop_and_reverse=False, **SAR_PARAMS)
    assert with_default == baseline


# Tight-trail byte-identity: with a 50-pip trail fichas cycle so fast an
# opposite signal never fires while open (zero reverses), yet the default must
# STILL be byte-identical -- an independent no-op pin at the opposite end of
# the trail-width regime from SAR_PARAMS.
TIGHT_PARAMS = dict(SAR_PARAMS)
TIGHT_PARAMS.update(f1_trail_pips=50.0, f2_trail_pips=50.0, f3_trail_pips=50.0)


@pytest.mark.parametrize("seed,n", [(120, 300), (7, 400)])
def test_stop_and_reverse_default_byte_identical_tight_trail(seed, n):
    bars = _synthetic_bars(n, seed=seed)
    baseline = simular_variant(bars, symbol="XAUUSD", **TIGHT_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", stop_and_reverse=False, **TIGHT_PARAMS)
    assert with_default == baseline


# ---------------------------------------------------------------------------
# (2) behavior: stop_and_reverse=True fires at least one "reverse" exit; on the
#     reverse bar an opposite-direction position opens the SAME bar; no bar
#     holds both long and short fichas; and the trades differ from the no-op.
# ---------------------------------------------------------------------------

def _find_reversing_seed():
    for seed in range(1, 80):
        bars = _synthetic_bars(500, seed=seed)
        events = simular_variant(
            bars, symbol="XAUUSD", stop_and_reverse=True, **SAR_PARAMS)
        if _reverses(events):
            return seed, bars, events
    raise AssertionError("no seed in 1..79 produced a reverse exit")


def test_stop_and_reverse_true_reverses_opens_same_bar_and_differs():
    seed, bars, sar_events = _find_reversing_seed()
    baseline = simular_variant(bars, symbol="XAUUSD", **SAR_PARAMS)

    reverses = _reverses(sar_events)
    # (a) at least one reverse exit occurs.
    assert reverses, f"expected >=1 reverse exit (seed {seed})"

    # (b) on each reverse bar, an opposite-direction position opens the SAME
    #     bar (close+open same bar i). Group events by idx; a reverse exit of
    #     side X must be accompanied by an entry of the opposite side at the
    #     same idx.
    by_idx: dict[int, list[dict]] = {}
    for ev in sar_events:
        by_idx.setdefault(ev["idx"], []).append(ev)
    for rev in reverses:
        i = rev["idx"]
        same_bar = by_idx[i]
        entries_here = [e for e in same_bar if e["motivo"] in ("ENTRY_L", "ENTRY_S")]
        assert entries_here, (
            f"reverse at idx {i} must open an opposite position the same bar")
        rev_side = rev["lado"]  # side being CLOSED
        opp = "ENTRY_S" if rev_side == "L" else "ENTRY_L"
        assert any(e["motivo"] == opp for e in entries_here), (
            f"reverse closing {rev_side} at idx {i} must open the opposite side")

    # (c) no bar ever holds both long and short fichas open simultaneously.
    #     Reconstruct open side over time from the event stream: an ENTRY sets
    #     the open side; any EXIT/reverse of all fichas clears it. Simpler
    #     invariant: at every entry, the immediately-preceding open lineage (if
    #     any) must have been closed at the same-or-earlier bar. We assert the
    #     stronger structural invariant by replaying opens/closes.
    open_side = None      # 'L' | 'S' | None
    open_tags: set[str] = set()
    for ev in sar_events:
        m = ev["motivo"]
        if m in ("ENTRY_L", "ENTRY_S"):
            # An entry may only start when flat.
            assert not open_tags, (
                f"entry at idx {ev['idx']} while {open_side} fichas still open")
            open_side = "L" if m == "ENTRY_L" else "S"
            open_tags = {"F1", "F2", "F3"}
        elif m.startswith("EXIT") or m in ("reverse", "time_stop"):
            tag = ev.get("ficha")
            if m == "reverse":
                # reverse closes ALL open fichas at once.
                open_tags.clear()
                open_side = None
            elif tag in open_tags:
                open_tags.discard(tag)
                if not open_tags:
                    open_side = None

    # (d) trades differ from the no-op run.
    assert _entries(sar_events) != _entries(baseline), (
        "stop_and_reverse=True should differ from the no-op run")


# ---------------------------------------------------------------------------
# (3) honesty: the reverse close AND the new opposite open are priced at bar
#     i's close under live_fill_mode=True.
# ---------------------------------------------------------------------------

def test_stop_and_reverse_priced_at_bar_close_under_live_fill():
    seed, bars, _ = _find_reversing_seed()
    events = simular_variant(
        bars, symbol="XAUUSD", stop_and_reverse=True, live_fill_mode=True,
        **SAR_PARAMS)
    reverses = _reverses(events)
    assert reverses, f"expected >=1 reverse exit under live_fill (seed {seed})"

    by_idx: dict[int, list[dict]] = {}
    for ev in events:
        by_idx.setdefault(ev["idx"], []).append(ev)

    for rev in reverses:
        i = rev["idx"]
        # reverse close priced at bar i's close.
        assert rev["precio"] == bars[i]["close"], (
            f"reverse close at idx {i} must be priced at bar close: "
            f"got {rev['precio']!r} vs {bars[i]['close']!r}")
        # the same-bar opposite open priced at bar i's close.
        opens = [e for e in by_idx[i] if e["motivo"] in ("ENTRY_L", "ENTRY_S")]
        assert opens, f"reverse at idx {i} must open a position same bar"
        for e in opens:
            assert e["precio"] == bars[i]["close"], (
                f"reverse open at idx {i} must be priced at bar close: "
                f"got {e['precio']!r} vs {bars[i]['close']!r}")
