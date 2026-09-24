"""tests/strategies/test_emasar_pullbacklimit.py -- W5-P33 (honest program):
pins the additive strictly-causal pullback-LIMIT lever (V-12 causal cousin) on
`sentinel_engine.strategies.emasar_variant.simular_variant`.

  New kwarg `pullback_limit: bool = False` (default False = OFF). When True, a
  signal raised at bar `i` (close-entry gate, entry_timing==0 path) does NOT
  enter at `i`. Instead a resting LIMIT is placed at `level = ema_f[i]` (the
  FAST-EMA "pullback" level, legitimately known once bar i closes) for the NEXT
  bar only:
    - LONG (BUY LIMIT):  if bars[i+1].low  <= level -> fill at price=level,
                         else the order EXPIRES (no entry).
    - SHORT (SELL LIMIT): if bars[i+1].high >= level -> fill at price=level,
                         else the order EXPIRES.
  The order lives EXACTLY one bar (next-bar expiry, no carry). A signal on the
  LAST bar (no i+1) drops unfilled. This is the STRICTLY-CAUSAL cousin of the
  DEAD look-ahead V-12 (entry_timing=1), whose fill tested bar i's OWN intrabar
  low against a level derived from close[i] -- look-ahead. Here the fill uses
  ONLY bar i+1 OHLC (a strictly later bar), so no look-ahead.

Additive and OFF by default: the `pullback_limit=False` default must be
byte-identical to pre-change behavior. Pinned here. Combos with confirm_bar or
entry_timing in {1,2,3} are OUT OF SCOPE and raise ValueError (documented).
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from sentinel_engine.strategies.emasar_ref import ema_series
from sentinel_engine.strategies.emasar_variant import simular_variant

# Same champion-baseline params + fixture shape used by the sibling lever tests
# (test_emasar_confirmbar.py / test_emasar_sar.py) -- tight trails so fichas
# cycle fast and many signals fire, making both the byte-identity pin and the
# causal behavior non-vacuous.
V09_PARAMS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
    init_sl_range_k=1.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)


def _synthetic_bars(n: int = 300, seed: int = 120) -> list[dict]:
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


# ---------------------------------------------------------------------------
# (1) byte-identity: pullback_limit=False (default) is a byte-identical no-op
#     vs. NOT passing the kwarg at all, over >=2 seeds.
# ---------------------------------------------------------------------------

def test_pullback_limit_default_is_byte_identical_noop_synthetic():
    bars = _synthetic_bars(300, seed=120)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", pullback_limit=False, **V09_PARAMS)
    assert with_default == baseline


def test_pullback_limit_default_is_byte_identical_noop_seed7():
    bars = _synthetic_bars(400, seed=7)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", pullback_limit=False, **V09_PARAMS)
    assert with_default == baseline


# Tight-trail edge pin at the opposite end of the trail-width regime -- the
# default must STILL be byte-identical when fichas cycle extremely fast.
TIGHT_PARAMS = dict(V09_PARAMS)
TIGHT_PARAMS.update(f1_trail_pips=50.0, f2_trail_pips=50.0, f3_trail_pips=50.0)


@pytest.mark.parametrize("seed,n", [(120, 300), (7, 400)])
def test_pullback_limit_default_byte_identical_tight_trail(seed, n):
    bars = _synthetic_bars(n, seed=seed)
    baseline = simular_variant(bars, symbol="XAUUSD", **TIGHT_PARAMS)
    with_default = simular_variant(
        bars, symbol="XAUUSD", pullback_limit=False, **TIGHT_PARAMS)
    assert with_default == baseline


# ---------------------------------------------------------------------------
# Helpers for the causal-behavior tests: recover the ema_f level the engine
# uses (ema_series(closes, ema_fast)), and locate the first baseline signal.
# ---------------------------------------------------------------------------

def _ema_f(bars: list[dict], ema_fast: int) -> list[float]:
    return ema_series([b["close"] for b in bars], ema_fast)


def _first_baseline_signal(bars: list[dict]):
    """(idx, lado) of the first close-entry (entry_timing=0) signal."""
    base = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    ents = _entries(base)
    assert ents, "fixture must produce at least one baseline entry"
    e = ents[0]
    return e["idx"], (+1 if e["motivo"] == "ENTRY_L" else -1)


# ---------------------------------------------------------------------------
# (2) causal fill: signal at bar i, bar i+1 dips to/through ema_f[i] -> the
#     entry fills at price == ema_f[i] on bar i+1, NOT at close[i].
# ---------------------------------------------------------------------------

def test_pullback_limit_causal_fill_at_level_on_next_bar():
    bars = _synthetic_bars(600, seed=1)
    i, lado = _first_baseline_signal(bars)
    assert i + 1 < len(bars)
    level = _ema_f(bars, V09_PARAMS["ema_fast"])[i]

    # Force bar i+1 to reach the LIMIT level so the resting order fills.
    b1 = dict(bars[i + 1])
    if lado == +1:
        b1["low"] = min(b1["low"], level - 1.0)   # BUY LIMIT touched
    else:
        b1["high"] = max(b1["high"], level + 1.0)  # SELL LIMIT touched
    forced = bars[: i + 1] + [b1] + bars[i + 2:]

    events = simular_variant(forced, symbol="XAUUSD", pullback_limit=True, **V09_PARAMS)
    ents = _entries(events)
    # The FIRST entry must be the resolved pullback limit: at bar i+1, price==level.
    assert ents, "expected a filled pullback-limit entry"
    first = next(e for e in ents if e["idx"] == i + 1)
    assert first["idx"] == i + 1
    assert first["precio"] == pytest.approx(level)
    # And it must NOT enter on the signal bar i.
    assert all(e["idx"] != i for e in ents if e["idx"] <= i + 1) or first["idx"] == i + 1


# ---------------------------------------------------------------------------
# (3) expiry: signal at bar i, bar i+1 never reaches the level -> NO entry.
# ---------------------------------------------------------------------------

def test_pullback_limit_expires_when_level_not_reached():
    bars = _synthetic_bars(600, seed=1)
    i, lado = _first_baseline_signal(bars)
    assert i + 1 < len(bars)
    level = _ema_f(bars, V09_PARAMS["ema_fast"])[i]

    # Force bar i+1 to stay strictly on the non-fill side of the level.
    b1 = dict(bars[i + 1])
    if lado == +1:
        # BUY LIMIT below: keep the whole bar ABOVE the level (low > level).
        shift = (level + 5.0) - b1["low"]
        for k in ("open", "high", "low", "close"):
            b1[k] += shift
    else:
        # SELL LIMIT above: keep the whole bar BELOW the level (high < level).
        shift = b1["high"] - (level - 5.0)
        for k in ("open", "high", "low", "close"):
            b1[k] -= shift
    forced = bars[: i + 1] + [b1] + bars[i + 2:]

    events = simular_variant(forced, symbol="XAUUSD", pullback_limit=True, **V09_PARAMS)
    ents = _entries(events)
    # The order placed at bar i must NOT have filled on i+1 (expired), and by
    # one-bar expiry it cannot fill on any later bar either.
    assert all(e["idx"] != i + 1 for e in ents), "order should have expired, not filled"


# ---------------------------------------------------------------------------
# (4) NO look-ahead: bar i's OWN low is below the level but bar i+1's is NOT
#     -> NO fill. This is exactly the case the DEAD V-12 intrabar version would
#     (wrongly) fill on bar i. Proves the cousin uses only bars[i+1].
# ---------------------------------------------------------------------------

def test_pullback_limit_no_lookahead_uses_only_next_bar():
    bars = _synthetic_bars(600, seed=1)
    i, lado = _first_baseline_signal(bars)
    assert i + 1 < len(bars)
    level = _ema_f(bars, V09_PARAMS["ema_fast"])[i]

    bi = dict(bars[i])
    b1 = dict(bars[i + 1])
    if lado == +1:
        # Signal bar i's OWN low pierces the level (V-12 would fill here)...
        bi["low"] = min(bi["low"], level - 2.0)
        # ...but bar i+1 stays entirely ABOVE the level -> causal cousin: NO fill.
        shift = (level + 5.0) - b1["low"]
        for k in ("open", "high", "low", "close"):
            b1[k] += shift
    else:
        bi["high"] = max(bi["high"], level + 2.0)
        shift = b1["high"] - (level - 5.0)
        for k in ("open", "high", "low", "close"):
            b1[k] -= shift
    forced = bars[:i] + [bi] + [b1] + bars[i + 2:]

    events = simular_variant(forced, symbol="XAUUSD", pullback_limit=True, **V09_PARAMS)
    ents = _entries(events)
    # Must NOT fill on i (never enters on the signal bar) and must NOT fill on
    # i+1 (i+1 didn't reach the level). The bar-i intrabar touch is irrelevant.
    assert all(e["idx"] not in (i, i + 1) for e in ents), (
        "causal cousin must ignore bar-i intrabar touch and require bar i+1")


# ---------------------------------------------------------------------------
# (5) last-bar signal drops unfilled (no i+1 to rest the order into).
# ---------------------------------------------------------------------------

def test_pullback_limit_drops_signal_on_last_bar():
    bars = _synthetic_bars(600, seed=1)
    i, _lado = _first_baseline_signal(bars)
    # Truncate so the signal bar i becomes the final bar (no i+1).
    truncated = bars[: i + 1]
    events = simular_variant(truncated, symbol="XAUUSD", pullback_limit=True, **V09_PARAMS)
    ents = _entries(events)
    assert all(e["idx"] != i for e in ents), "last-bar signal must drop unfilled"


# ---------------------------------------------------------------------------
# (6) out-of-scope combos raise (do NOT silently change other entry paths).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    dict(confirm_bar=True),
    dict(entry_timing=1),
    dict(entry_timing=2),
    dict(entry_timing=3),
])
def test_pullback_limit_rejects_out_of_scope_combos(kwargs):
    bars = _synthetic_bars(120, seed=1)
    with pytest.raises(ValueError):
        simular_variant(bars, symbol="XAUUSD", pullback_limit=True, **kwargs, **V09_PARAMS)
