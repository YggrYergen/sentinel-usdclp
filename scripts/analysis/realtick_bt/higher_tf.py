r"""scripts/analysis/realtick_bt/higher_tf.py -- WP-3: higher-timeframe (H1/H4)
feed built by aggregating M15 bars. Sirve a P-19, P-20, P-21, P-22, P-28, P-29
(research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md,
WP-3). Self-contained: no import from `emasar_ref.py`/`emasar_variant.py` (those
are out of scope for this task -- another agent owns the AC deceleration code).

NO timezone conversion, anywhere. The M15 `bars` timestamp axis (`"t"`, bar OPEN
time) is already the broker SERVER wall clock, encoded as if it were UTC (see
`scripts/analysis/realtick_bt/backtest.py`'s CLOCK CONVENTION docstring). Bucket
boundaries for H1 (3600 s) and H4 (14400 s) are plain integer floor-division on
that SAME axis (`t // tf_sec * tf_sec`) -- this lands exactly on server-clock
00:00/04:00/08:00/... for H4 and server-clock hour marks for H1, with zero
explicit timezone arithmetic (the axis already IS server time).

Anti-look-ahead contract (spec Section 1), by construction:
  A higher-timeframe bucket is appended to the CLOSED bars list the first time
  an M15 bar is folded into it whose OWN close (`b["t"] + m15_sec`) reaches or
  passes the bucket's close boundary. This check uses ONLY that bar's own
  (already-known) open time -- never a later bar -- so a bucket can never be
  marked closed before its true close instant, and the in-progress bucket is
  never included in the closed list. `visible_count[i]` (built in the SAME
  left-to-right pass) records how many higher bars are closed as of M15 bar
  `i`'s own decision instant (`bars_m15[i]["t"] + m15_sec`); it is monotonic
  non-decreasing and never counts the bucket bar `i` itself is still filling.

Caching: `aggregate_closed_with_visibility()` and `build_higher_series()` each
make a SINGLE left-to-right pass over `bars_m15` (O(n)) and compute every
indicator over the CLOSED higher-bars array only (O(m), m = number of closed
higher bars, m << n) -- never recomputed per M15 bar. `HigherSeries.snapshot_at
` is an O(1) lookup via the precomputed `visible_count` array.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

M15_SEC_DEFAULT = 900


# --------------------------------------------------------------------- aggregation
def _bucket_start(t: float, tf_sec: int) -> float:
    return (t // tf_sec) * tf_sec


def aggregate_closed_with_visibility(
    bars_m15: list[dict[str, Any]], tf_sec: int, *, m15_sec: int = M15_SEC_DEFAULT
) -> tuple[list[dict[str, Any]], np.ndarray]:
    """Aggregate M15 bars into `tf_sec`-second buckets.

    Returns `(closed_bars, visible_count)`:
      - `closed_bars`: OHLC dicts `{"t","t_close","open","high","low","close","n_m15"}`
        for buckets that are PROVABLY closed (see module docstring) -- an
        in-progress bucket is NEVER included, no matter how many of its M15
        bars have already arrived.
      - `visible_count`: int array, `len == len(bars_m15)`. `visible_count[i]`
        = number of entries of `closed_bars` visible at M15 bar `i`'s own
        decision instant (`bars_m15[i]["t"] + m15_sec`). Monotonic
        non-decreasing.
    """
    n = len(bars_m15)
    visible_count = np.zeros(n, dtype=np.int64)
    closed: list[dict[str, Any]] = []
    cur_bucket: float | None = None
    cur: dict[str, Any] | None = None
    for i, b in enumerate(bars_m15):
        bs = _bucket_start(b["t"], tf_sec)
        if cur_bucket is None or bs != cur_bucket:
            cur_bucket = bs
            cur = {"t": bs, "t_close": bs + tf_sec, "open": b["open"], "high": b["high"],
                   "low": b["low"], "close": b["close"], "n_m15": 1}
        else:
            cur["high"] = max(cur["high"], b["high"])
            cur["low"] = min(cur["low"], b["low"])
            cur["close"] = b["close"]
            cur["n_m15"] += 1
        if b["t"] + m15_sec >= cur["t_close"]:
            closed.append(cur)
            cur = None
            cur_bucket = None
        visible_count[i] = len(closed)
    return closed, visible_count


# --------------------------------------------------------------------- indicators
# (self-contained -- no import from emasar_ref.py, out of scope for this task)
def _ema(closes: list[float], period: int) -> list[float | None]:
    n = len(closes)
    out: list[float | None] = [None] * n
    if n == 0:
        return out
    alpha = 2.0 / (period + 1)
    e = closes[0]
    out[0] = e
    for i in range(1, n):
        e = alpha * closes[i] + (1.0 - alpha) * e
        out[i] = e
    return out


def _atr_wilder(highs: list[float], lows: list[float], closes: list[float],
                 period: int) -> list[float | None]:
    n = len(highs)
    if n == 0:
        return []
    tr = [highs[0] - lows[0]] + [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(1, n)
    ]
    atr: list[float | None] = [None] * n
    if n < period:
        return atr
    atr[period - 1] = sum(tr[:period]) / period
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def _supertrend_direction(highs: list[float], lows: list[float], closes: list[float],
                           atr: list[float | None], mult: float) -> list[int | None]:
    """Vendored-math SuperTrend direction, reimplemented locally (self-contained
    module, per spec: no dependency introduced on emasar_ref.py). Same left-to-
    right recursion as `sentinel_engine.strategies._supertrend_ref.supertrend`
    (that module IS reused directly where available, e.g. in the position-level
    engine; this local copy exists only so `higher_tf.py` has zero import
    coupling to the strategies package)."""
    n = len(closes)
    fin_up = [0.0] * n
    fin_lo = [0.0] * n
    trend: list[int | None] = [None] * n
    for i in range(n):
        a = atr[i] if atr[i] is not None else 0.0
        hl2 = (highs[i] + lows[i]) / 2.0
        b_up = hl2 + mult * a
        b_lo = hl2 - mult * a
        if i == 0 or atr[i - 1] is None:
            fin_up[i] = b_up
            fin_lo[i] = b_lo
            trend[i] = +1 if closes[i] >= hl2 else -1
        else:
            fin_up[i] = b_up if (b_up < fin_up[i - 1] or closes[i - 1] > fin_up[i - 1]) else fin_up[i - 1]
            fin_lo[i] = b_lo if (b_lo > fin_lo[i - 1] or closes[i - 1] < fin_lo[i - 1]) else fin_lo[i - 1]
            prev = trend[i - 1] if trend[i - 1] is not None else (+1 if closes[i] >= hl2 else -1)
            if prev == +1 and closes[i] < fin_lo[i]:
                trend[i] = -1
            elif prev == -1 and closes[i] > fin_up[i]:
                trend[i] = +1
            else:
                trend[i] = prev
    return trend


def _momentum(closes: list[float], lookback: int) -> list[float | None]:
    n = len(closes)
    return [None if i < lookback else closes[i] - closes[i - lookback] for i in range(n)]


@dataclass
class HigherSeries:
    tf_sec: int
    bars: list[dict[str, Any]]
    ema: list[float | None]
    ema_slope: list[float | None]
    st_dir: list[int | None]
    momentum: list[float | None]
    visible_count: np.ndarray

    def snapshot_at_m15_index(self, i: int) -> dict[str, Any] | None:
        """Higher-bar + indicator snapshot visible at M15 bar `i`'s own
        decision instant. `None` if no higher bar has closed yet. O(1)."""
        vc = int(self.visible_count[i])
        if vc == 0:
            return None
        j = vc - 1
        bar = self.bars[j]
        return {
            "t": bar["t"], "t_close": bar["t_close"], "open": bar["open"],
            "high": bar["high"], "low": bar["low"], "close": bar["close"],
            "ema": self.ema[j], "ema_slope": self.ema_slope[j],
            "st_dir": self.st_dir[j], "momentum": self.momentum[j],
        }


def build_higher_series(
    bars_m15: list[dict[str, Any]], tf_sec: int, *,
    m15_sec: int = M15_SEC_DEFAULT, ema_period: int = 20,
    st_atr_period: int = 10, st_mult: float = 3.0, momentum_lookback: int = 10,
) -> HigherSeries:
    """Build the H1/H4 (or any `tf_sec`) feed off `bars_m15`. See module
    docstring for the anti-look-ahead contract and caching guarantees."""
    closed, visible_count = aggregate_closed_with_visibility(bars_m15, tf_sec, m15_sec=m15_sec)
    closes = [b["close"] for b in closed]
    highs = [b["high"] for b in closed]
    lows = [b["low"] for b in closed]
    ema = _ema(closes, ema_period)
    ema_slope: list[float | None] = [
        None if i == 0 or ema[i] is None or ema[i - 1] is None else ema[i] - ema[i - 1]
        for i in range(len(closed))
    ]
    atr = _atr_wilder(highs, lows, closes, st_atr_period)
    st_dir = _supertrend_direction(highs, lows, closes, atr, st_mult)
    momentum = _momentum(closes, momentum_lookback)
    return HigherSeries(tf_sec=tf_sec, bars=closed, ema=ema, ema_slope=ema_slope,
                         st_dir=st_dir, momentum=momentum, visible_count=visible_count)
