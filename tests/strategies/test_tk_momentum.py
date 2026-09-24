"""tests/strategies/test_tk_momentum.py -- TK-Momentum-5-8-short engine.

A NEW additive engine (NOT simular_variant / supertrend_always_in): on M6
CLOSED bars, a SINGLE position opens by STATE (not by cross, trader 2026-07-21
v2) -- SHORT when SMA5<SMA8 AND MOM2<100, LONG when SMA5>SMA8 AND MOM2>100 -- and
holds until either the MOM2 line is crossed back (momentum reversion) OR a
0.5-USD trailing stop is touched.

`tk_momentum_5_8_target(bars, *, trail_usd)` emits the reconciler `return_state`
snapshot shape (single ficha F1), so it reconciles like any other magic with NO
change to the ladder reconciler. No MT5, no orders.
"""
from __future__ import annotations

from sentinel_engine.strategies.tk_momentum import (
    momentum,
    sma,
    tk_momentum_5_8_target,
)


def _bars(closes: list[float], *, wick: float = 0.1,
          highs: list[float] | None = None,
          lows: list[float] | None = None) -> list[dict]:
    """Bars from a close series. By default high/low hug the close (+/- `wick`)
    so no spurious trailing-stop touches; pass explicit highs/lows to force a
    stop-out."""
    t = 1_700_000_000
    out = []
    for i, c in enumerate(closes):
        hi = highs[i] if highs is not None else c + wick
        lo = lows[i] if lows is not None else c - wick
        out.append({"t": t + 600 * i, "open": c, "high": hi, "low": lo, "close": c})
    return out


# --------------------------- indicator helpers ------------------------------
def test_sma_warmup_and_values():
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_momentum_ratio_times_100():
    m = momentum([100.0, 110.0, 121.0, 133.1], 2)
    assert m[0] is None and m[1] is None
    assert round(m[2], 4) == 121.0        # 121/100*100
    assert round(m[3], 4) == 121.0        # 133.1/110*100


# ------------------------------- structure ----------------------------------
def test_empty_and_warmup_is_flat():
    assert tk_momentum_5_8_target([])["open"] == {}
    # fewer than SMA8 warmup bars -> flat
    assert tk_momentum_5_8_target(_bars([1, 2, 3, 4, 5]))["open"] == {}


def test_snapshot_shape_is_reconciler_ready():
    snap = tk_momentum_5_8_target(_bars([120, 118, 116, 114, 112, 110, 108, 108, 108, 106]))
    assert set(snap) >= {"open", "last_bar_exits", "last_idx"}
    assert snap["last_bar_exits"] == {}
    assert snap["last_idx"] == 9
    assert list(snap["open"]) == ["F1"]
    d = snap["open"]["F1"]
    assert set(d) >= {"side", "entry", "sl", "max_fav"}


# ------------------------- entries (STATE, not cross) -----------------------
def test_short_entry_on_state_in_short_regime():
    # Down regime (SMA5<SMA8) + MOM2<100 => SHORT opens on the FIRST warmed bar
    # the state holds (i=7 here, entry 108), not on any cross.
    snap = tk_momentum_5_8_target(_bars([120, 118, 116, 114, 112, 110, 108, 108]))
    d = snap["open"]["F1"]
    assert d["side"] == "S"
    assert d["entry"] == 108
    assert d["sl"] == 108 + 0.5          # short SL sits ABOVE entry
    assert d["sl"] > d["entry"]


def test_long_entry_on_state_in_long_regime():
    # Up regime (SMA5>SMA8) + MOM2>100 => LONG opens on the first warmed bar the
    # state holds (i=7 here, entry 104).
    snap = tk_momentum_5_8_target(_bars([92, 94, 96, 98, 100, 102, 104, 104]))
    d = snap["open"]["F1"]
    assert d["side"] == "L"
    assert d["entry"] == 104
    assert d["sl"] == 104 - 0.5          # long SL sits BELOW entry
    assert d["sl"] < d["entry"]


def test_state_opens_without_a_cross():
    # THE state-vs-cross distinction: a monotonic decline keeps MOM2 BELOW 100
    # the whole time (it never crosses DOWN through 100), yet the down-regime +
    # MOM2<100 STATE still opens a SHORT. Under the old cross logic this was flat.
    snap = tk_momentum_5_8_target(_bars([120, 118, 116, 114, 112, 110, 108, 106, 104, 102]))
    assert snap["open"]["F1"]["side"] == "S"


def test_regime_gates_opposite_side():
    # UP regime (SMA5>SMA8) but MOM2 dipped BELOW 100: no LONG (MOM2<100) and no
    # SHORT (regime is up) -> both states fail -> stay flat. Regime still gates.
    snap = tk_momentum_5_8_target(_bars([90, 92, 94, 100, 102, 104, 101, 100, 101]))
    assert snap["open"] == {}


def test_strict_inequality_no_entry_on_equality():
    # All-equal closes: SMA5==SMA8 and MOM2==100 -> strict inequalities fail on
    # BOTH sides -> no entry.
    snap = tk_momentum_5_8_target(_bars([100, 100, 100, 100, 100, 100, 100, 100, 100, 100]))
    assert snap["open"] == {}


# ------------------------------- exits --------------------------------------
def test_momentum_reversion_closes_the_position():
    closes = [120, 118, 116, 114, 112, 110, 108, 108, 108, 106, 108, 110]
    # far trailing stop so ONLY the momentum reversion can close it.
    before = tk_momentum_5_8_target(_bars(closes[:11]), trail_usd=50.0)
    after = tk_momentum_5_8_target(_bars(closes), trail_usd=50.0)
    assert before["open"]["F1"]["side"] == "S"   # still short before the up-cross
    assert after["open"] == {}                   # up-cross at the last bar closed it


def test_trailing_stop_touch_closes_the_position():
    # Short entry at bar 9 (entry 106, sl 106.5), then bar 10 spikes UP through
    # the trailing stop (high 108 >= 106.5) -> stopped out -> flat.
    closes = [120, 118, 116, 114, 112, 110, 108, 108, 108, 106, 107]
    highs = [c + 0.1 for c in closes]
    highs[10] = 108.0
    snap = tk_momentum_5_8_target(_bars(closes, highs=highs), trail_usd=0.5)
    assert snap["open"] == {}


def test_trailing_stop_ratchets_monotonically_tighter():
    # Short opens by STATE at i=7 (entry 108, sl 110 = 108+2), then favorable
    # (lower) bars: the short's SL only moves DOWN, never up.
    closes = [120, 118, 116, 114, 112, 110, 108, 108, 108, 106, 104, 102]
    sl_entry = tk_momentum_5_8_target(_bars(closes[:8]), trail_usd=2.0)["open"]["F1"]["sl"]
    sl_mid = tk_momentum_5_8_target(_bars(closes[:11]), trail_usd=2.0)["open"]["F1"]["sl"]
    sl_end = tk_momentum_5_8_target(_bars(closes), trail_usd=2.0)["open"]["F1"]["sl"]
    assert sl_entry == 110.0              # 108 (i=7 entry) + 2
    assert sl_mid < sl_entry
    assert sl_end < sl_mid


def test_no_same_bar_reentry_after_exit():
    # Short enters at bar 9; bar 10 is a sharp reversal UP that is BOTH a MOM2
    # up-cross (closes the short) AND a long regime (SMA5>SMA8). The strategy
    # must NOT immediately re-open a long on that same bar (single position;
    # wait next bar) -> flat. If same-bar re-entry leaked, open would be F1/L.
    closes = [120, 118, 116, 114, 112, 110, 108, 108, 108, 106, 140]
    snap = tk_momentum_5_8_target(_bars(closes), trail_usd=50.0)
    assert snap["open"] == {}


# --------------------- single-position invariant (trader) -------------------
def test_never_more_than_one_open_position():
    # Trader 2026-07-21: "solo una posicion, nunca mas de una." The engine is
    # single-slot by construction, so NO bar series -- entries, exits,
    # re-entries across bars, both regimes -- may ever produce >1 open ficha.
    import random

    rng = random.Random(20260721)
    for _ in range(400):
        n = rng.randint(0, 60)
        closes = [100.0]
        for _ in range(n):
            closes.append(round(closes[-1] * (1 + rng.uniform(-0.02, 0.02)), 3))
        snap = tk_momentum_5_8_target(
            _bars(closes), trail_usd=rng.choice([0.5, 1.0, 3.0, 50.0]))
        assert len(snap["open"]) <= 1
        assert set(snap["open"]) <= {"F1"}
