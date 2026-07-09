"""sentinel_engine.strategies.emasar — EmasarPolicy (M2.5).

Ported from `D:/WebDev/TOKATA/mt5/scripts/emasar_ref.py` (READ-ONLY
reference — never written to). This is the **V2 mode** of that reference
(strategy_mode=2): single position ("ficha"), entry gate = EMA8/EMA20
trend + slope + EMA5 pullback + Parabolic SAR direction + a 2-of-3
{AO, AC, Momentum} oscillator confirmation (ConfirmMode 1 = "creciente"),
exit = bearish/bullish engulfing (symmetric long/short). This is the
leanest faithful slice of the reference suitable for the M2.5 minimal
backtest-lite engine (plan §B1 says the full V1/runner/trailing/ConfirmMode
2/EntryTiming machinery is BACKLOG — not built here).

All indicator math (EMA seed+recursion, Wilder Parabolic SAR, AO/AC,
Momentum, the gate composition, engulfing patterns) is copied verbatim
from the reference so entry/exit conditions match it bar-for-bar; only
the API shape (a `StrategyPolicy`-like class consumed by
`sentinel_engine.sim.lite.run_backtest_lite`) is new.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------
# Pure indicator helpers (ported verbatim from emasar_ref.py)
# ---------------------------------------------------------------------
def _sma_maybe(vals: list[float | None], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(vals)
    for i in range(len(vals)):
        if i < n - 1:
            continue
        window = vals[i - n + 1:i + 1]
        if any(v is None for v in window):
            continue
        out[i] = sum(window) / n
    return out


def ema_series(closes: list[float], period: int) -> list[float | None]:
    n = len(closes)
    out: list[float | None] = [None] * n
    if n < period:
        return out
    k = 2.0 / (period + 1)
    seed = sum(closes[0:period]) / period
    out[period - 1] = seed
    for i in range(period, n):
        out[i] = closes[i] * k + out[i - 1] * (1 - k)
    return out


def sar_series(highs: list[float], lows: list[float], step: float, max_step: float):
    n = len(highs)
    if n == 0:
        return [], []
    sar: list[float | None] = [None] * n
    trend = [0] * n
    up = True if n < 2 else highs[1] >= highs[0]
    ep = highs[0] if up else lows[0]
    af = step
    sar[0] = lows[0] if up else highs[0]
    trend[0] = +1 if up else -1
    for i in range(1, n):
        cur = sar[i - 1] + af * (ep - sar[i - 1])
        if up:
            ceiling = min(lows[i - 1], lows[i - 2]) if i >= 2 else lows[i - 1]
            cur = min(cur, ceiling)
            if lows[i] < cur:
                up = False
                cur = ep
                ep = lows[i]
                af = step
            elif highs[i] > ep:
                ep = highs[i]
                af = min(af + step, max_step)
        else:
            floor = max(highs[i - 1], highs[i - 2]) if i >= 2 else highs[i - 1]
            cur = max(cur, floor)
            if highs[i] > cur:
                up = True
                cur = ep
                ep = highs[i]
                af = step
            elif lows[i] < ep:
                ep = lows[i]
                af = min(af + step, max_step)
        sar[i] = cur
        trend[i] = +1 if up else -1
    return sar, trend


def ao_series(highs: list[float], lows: list[float]) -> list[float | None]:
    median = [(highs[i] + lows[i]) / 2.0 for i in range(len(highs))]
    sma5 = _sma_maybe(median, 5)
    sma34 = _sma_maybe(median, 34)
    return [None if (sma5[i] is None or sma34[i] is None) else sma5[i] - sma34[i]
            for i in range(len(median))]


def ac_series(highs: list[float], lows: list[float]) -> list[float | None]:
    ao = ao_series(highs, lows)
    ao_sma5 = _sma_maybe(ao, 5)
    return [None if (ao[i] is None or ao_sma5[i] is None) else ao[i] - ao_sma5[i]
            for i in range(len(ao))]


def momentum_series(closes: list[float], period: int) -> list[float | None]:
    n = len(closes)
    out: list[float | None] = [None] * n
    for i in range(period, n):
        out[i] = 100.0 * closes[i] / closes[i - period]
    return out


def oscillator_favorable(osc, i, mode, direction) -> bool:
    if i < 1 or osc[i] is None or osc[i - 1] is None:
        return False
    if mode == 1:
        return (osc[i] > osc[i - 1]) if direction == +1 else (osc[i] < osc[i - 1])
    if mode == 2:
        if i < 2 or osc[i - 2] is None:
            return False
        d1 = osc[i] - osc[i - 1]
        d2 = osc[i - 1] - osc[i - 2]
        return (d1 > d2) if direction == +1 else (d1 < d2)
    raise ValueError(f"invalid ConfirmMode: {mode}")


def g5_confirmation(ao, ac, mom, i, mode, direction, *, confirm_count=2, ac_mag_threshold=0.0) -> bool:
    votes = sum([
        oscillator_favorable(ao, i, mode, direction),
        oscillator_favorable(mom, i, mode, direction),
        oscillator_favorable(ac, i, mode, direction),
    ])
    if votes < confirm_count:
        return False
    if ac_mag_threshold > 0.0:
        if i < 1 or ac[i] is None or ac[i - 1] is None:
            return False
        if abs(ac[i] - ac[i - 1]) <= ac_mag_threshold:
            return False
    return True


def bearish_engulfing(o1, c1, o2, c2) -> bool:
    return (c1 < o1) and (c2 > o2) and (o1 >= c2) and (c1 <= o2)


def bullish_engulfing(o1, c1, o2, c2) -> bool:
    return (c1 > o1) and (c2 < o2) and (o1 <= c2) and (c1 >= o2)


def gate_long(bars, ema8, ema20, ema5, sar_trend, ao, ac, mom, i, *, confirm_mode, use_ema5,
              confirm_count=2, ac_mag_threshold=0.0):
    if i < 2:
        return False
    e8, e8p = ema8[i], ema8[i - 1]
    e20, e20p = ema20[i], ema20[i - 1]
    if None in (e8, e8p, e20, e20p) or sar_trend[i] is None:
        return False
    g1 = e8 > e20
    slope8 = e8 - e8p
    slope20 = e20 - e20p
    crossed = (slope8 > 0 and slope20 < 0) or (slope8 < 0 and slope20 > 0)
    g2 = (slope8 > 0 and slope20 > 0) and not crossed
    ema_pull = ema5[i] if use_ema5 else ema8[i]
    if ema_pull is None:
        return False
    bar1 = bars[i]
    g3 = (bar1["low"] < ema_pull) and (bar1["close"] > bar1["open"])
    g4 = sar_trend[i] == +1
    g5 = g5_confirmation(ao, ac, mom, i, confirm_mode, +1,
                          confirm_count=confirm_count, ac_mag_threshold=ac_mag_threshold)
    return g1 and g2 and g3 and g4 and g5


def gate_short(bars, ema8, ema20, ema5, sar_trend, ao, ac, mom, i, *, confirm_mode, use_ema5,
               confirm_count=2, ac_mag_threshold=0.0):
    if i < 2:
        return False
    e8, e8p = ema8[i], ema8[i - 1]
    e20, e20p = ema20[i], ema20[i - 1]
    if None in (e8, e8p, e20, e20p) or sar_trend[i] is None:
        return False
    g1 = e8 < e20
    slope8 = e8 - e8p
    slope20 = e20 - e20p
    crossed = (slope8 > 0 and slope20 < 0) or (slope8 < 0 and slope20 > 0)
    g2 = (slope8 < 0 and slope20 < 0) and not crossed
    ema_pull = ema5[i] if use_ema5 else ema8[i]
    if ema_pull is None:
        return False
    bar1 = bars[i]
    g3 = (bar1["high"] > ema_pull) and (bar1["close"] < bar1["open"])
    g4 = sar_trend[i] == -1
    g5 = g5_confirmation(ao, ac, mom, i, confirm_mode, -1,
                          confirm_count=confirm_count, ac_mag_threshold=ac_mag_threshold)
    return g1 and g2 and g3 and g4 and g5


# ---------------------------------------------------------------------
# EmasarPolicy — StrategyPolicy-shaped adapter for sim/lite.py
# ---------------------------------------------------------------------
_DEFAULT_PARAMS: dict[str, Any] = {
    "confirm_mode": 1,
    "ema_fast": 8,
    "ema_slow": 20,
    "ema_pull": 5,
    "sar_step": 0.02,
    "sar_max": 0.20,
    "mom_period": 14,
    "confirm_count": 2,
    "ac_mag_threshold": 0.0,
    "allow_long": True,
    "allow_short": True,
}


@dataclass
class EmasarPolicy:
    """V2-mode EMASAR policy: on each new bar, given the OHLC history up to
    and including that bar, decide whether to enter/exit. Stateless w.r.t.
    open position — `sim.lite.run_backtest_lite` owns position state and
    only asks `should_exit`/`should_enter` per bar; this class only computes
    indicator series (memoized per `bars` identity) and evaluates gates.
    """

    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        merged = dict(_DEFAULT_PARAMS)
        merged.update(self.params or {})
        self.params = merged
        self._cache_key: int | None = None
        self._cache: dict[str, list] = {}

    def _indicators(self, bars: list[dict]) -> dict[str, list]:
        key = id(bars)
        if self._cache_key == key and len(self._cache.get("closes", [])) == len(bars):
            return self._cache
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        closes = [b["close"] for b in bars]
        p = self.params
        ema8 = ema_series(closes, p["ema_fast"])
        ema20 = ema_series(closes, p["ema_slow"])
        ema5 = ema_series(closes, p["ema_pull"])
        _sar_val, sar_trend = sar_series(highs, lows, p["sar_step"], p["sar_max"])
        ao = ao_series(highs, lows)
        ac = ac_series(highs, lows)
        mom = momentum_series(closes, p["mom_period"])
        cache = {
            "bars": bars, "ema8": ema8, "ema20": ema20, "ema5": ema5,
            "sar_trend": sar_trend, "ao": ao, "ac": ac, "mom": mom,
        }
        self._cache_key = key
        self._cache = cache
        return cache

    def signal_at(self, bars: list[dict], i: int) -> str | None:
        """Entry signal at closed bar index `i`: `"LONG"`, `"SHORT"`, or
        `None`. `bars[0..i]` must be the causal history up to and including
        bar `i` (no look-ahead: gates only reference `<= i`)."""
        c = self._indicators(bars)
        p = self.params
        long_ok = gate_long(
            bars, c["ema8"], c["ema20"], c["ema5"], c["sar_trend"], c["ao"], c["ac"], c["mom"], i,
            confirm_mode=p["confirm_mode"], use_ema5=True,
            confirm_count=p["confirm_count"], ac_mag_threshold=p["ac_mag_threshold"],
        )
        if long_ok and p["allow_long"]:
            return "LONG"
        short_ok = gate_short(
            bars, c["ema8"], c["ema20"], c["ema5"], c["sar_trend"], c["ao"], c["ac"], c["mom"], i,
            confirm_mode=p["confirm_mode"], use_ema5=True,
            confirm_count=p["confirm_count"], ac_mag_threshold=p["ac_mag_threshold"],
        )
        if short_ok and p["allow_short"]:
            return "SHORT"
        return None

    def should_exit(self, bars: list[dict], i: int, side: str) -> bool:
        """Engulfing-only exit (V2 mode, no trailing/SL beyond the sim
        engine's own SL-first intrabar check): needs bars[i] and bars[i-1]."""
        if i < 1:
            return False
        bar, prev = bars[i], bars[i - 1]
        o1, c1, o2, c2 = bar["open"], bar["close"], prev["open"], prev["close"]
        if side == "LONG":
            return bearish_engulfing(o1, c1, o2, c2)
        return bullish_engulfing(o1, c1, o2, c2)
