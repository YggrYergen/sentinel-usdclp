"""tests/strategies/test_emasar_ref.py — golden test for the VENDORED
`sentinel_engine.strategies.emasar_ref` (frozen mirror of TOKATA's validated
`mt5/scripts/emasar_ref.py`, design spec
docs/superpowers/specs/2026-07-10-emasar-v1-mt5-integration-design.md,
Component 5).

Pins `simular()` output on a small FIXED bar fixture so the vendored copy
can't silently drift from the TOKATA original. Also smoke-tests the
individual indicator series (ema/sar/ao/ac/momentum) are importable and
produce the same shape TOKATA's own emasar_ref does.
"""
from __future__ import annotations

import random

from sentinel_engine.strategies.emasar_ref import (
    ac_series,
    ao_series,
    ema_series,
    momentum_series,
    sar_series,
    simular,
)


def _synthetic_bars(n: int = 120, seed: int = 120) -> list[dict]:
    """Deterministic OHLC series (fixed `random.Random(seed)` -- reproducible
    bar-for-bar, not wall-clock/entropy-seeded) with enough trend/pullback
    structure to trigger EMASAR V1 entries and exits. seed=120 was picked by
    scanning seeds 0..500 for one that reliably produces entries+exits on
    strategy_mode=1 with the sar3m3 params (0.3/0.3) -- see design spec
    Component 5."""
    rnd = random.Random(seed)
    bars = []
    price = 4500.0
    for _ in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        open_ = price - drift
        close = price
        high = max(open_, close) + abs(rnd.uniform(0.3, 1.2))
        low = min(open_, close) - abs(rnd.uniform(0.3, 1.2))
        bars.append({"open": open_, "high": high, "low": low, "close": close})
    return bars


def test_simular_golden_v1_events_on_fixed_fixture():
    """Pins the exact event sequence emitted by V1 (strategy_mode=1) on a
    deterministic fixture. If this ever fails after a vendoring refresh, the
    vendored copy has drifted from TOKATA's validated emasar_ref -- do not
    "fix" the vendored file to make it pass; re-vendor from source instead."""
    bars = _synthetic_bars(200, seed=120)
    events = simular(
        bars, strategy_mode=1, confirm_mode=1, symbol="XAUUSD",
        sar_step=0.3, sar_max=0.3,
    )
    assert len(events) > 0
    motivos = {e["motivo"] for e in events}
    assert motivos <= {
        "ENTRY_L", "ENTRY_S", "EXIT_ENGULF", "EXIT_STFLIP", "EXIT_TRAIL",
        "EXIT_INITSL", "EXIT_ACDECEL", "EXIT_MOMSLOPE", "EXIT_MOMSTALL",
    }
    # First event on this fixture must be an entry (no exits before an
    # entry has ever happened).
    assert events[0]["motivo"] in ("ENTRY_L", "ENTRY_S")
    # V1 opens fichas F1/F2/F3 tagged on entry-adjacent exit events.
    fichas_seen = {e["ficha"] for e in events if e["ficha"] is not None}
    assert fichas_seen <= {"F1", "F2", "F3"}
    # Golden pin: exact event count + first 4 events' (idx, lado, motivo,
    # ficha). Recorded from a run of THIS fixture against the vendored
    # engine (seed=120, n=200, strategy_mode=1, sar 0.3/0.3).
    assert len(events) == 128
    first_four = [(e["idx"], e["lado"], e["motivo"], e["ficha"]) for e in events[:4]]
    assert first_four == [
        (34, "S", "ENTRY_S", None),
        (35, "S", "EXIT_INITSL", "F1"),
        (35, "S", "EXIT_INITSL", "F2"),
        (35, "S", "EXIT_INITSL", "F3"),
    ]


def test_indicator_series_importable_and_shaped():
    bars = _synthetic_bars(60)
    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]

    ema8 = ema_series(closes, 8)
    sar, trend = sar_series(highs, lows, 0.3, 0.3)
    ao = ao_series(highs, lows)
    ac = ac_series(highs, lows)
    mom = momentum_series(closes, 14)

    assert len(ema8) == len(sar) == len(ao) == len(ac) == len(mom) == 60
    assert any(v is not None for v in ema8)
    assert any(v is not None for v in sar)


def test_supertrend_computed_internally_for_f2_exit():
    """V1's F2 exits on SuperTrend flip (EXIT_STFLIP) -- proves the vendored
    simular() wires up its own SuperTrend (via the vendored _supertrend_ref)
    without any external TOKATA import at runtime. A wider init SL (so
    fichas survive long enough to reach a SuperTrend flip instead of always
    hitting the tight 3-pip default first) reliably surfaces EXIT_STFLIP on
    this deterministic seed."""
    bars = _synthetic_bars(300, seed=19)
    events = simular(
        bars, strategy_mode=1, confirm_mode=1, symbol="XAUUSD",
        sar_step=0.3, sar_max=0.3, init_sl_pips=50.0,
    )
    assert any(e["motivo"] == "EXIT_STFLIP" for e in events)
