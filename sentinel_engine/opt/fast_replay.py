"""
sentinel_engine.opt.fast_replay -- vectorized fast replay (P4 speed layer).

`evaluator.evaluate_config` is CORRECT but re-derives every indicator from
scratch on every M1 bar (`TechnicalScorer.score` calls `calculate_all` on a
freshly-filtered `tail(200)` slice, per timeframe, per bar -- ~190 ms/bar).
This module is a from-scratch, vectorized re-implementation of the SAME
entry-generation math that produces the SAME (tolerance-tiered, see the
test module) trades/score, computed ~1000x faster by:

  1. Computing each timeframe's technical indicators ONCE, over the full
     available history up to `window_end`, with pandas/numpy vector ops
     (reusing `sentinel.indicators.calculate_all` verbatim for the
     indicator math itself -- only the per-bar SCORING formulas from
     `sentinel_engine.technical` are re-expressed as vectorized numpy ops
     here), then as-of aligning each timeframe's per-bar score onto the
     M1 step timeline.
  2. Driving `sentinel.correlation_engine.RealtimeCorrelationTracker`
     (imported, NOT reimplemented -- the EWMA/concordance/z-score math is
     used verbatim) through a single forward Python loop over M1 steps,
     with all of its *inputs* (tick prices, recent-return lookups)
     precomputed vectorized ahead of the loop.
  3. Reusing `sentinel_engine.opt.labels.triple_barrier` verbatim for
     labeling (identical to `evaluator._label_entries`'s direction-aware
     negation trick).

This module does NOT modify or import from `sentinel_engine.engine`,
`sentinel_engine.technical`, `sentinel_engine.macro`, or
`sentinel_engine.opt.evaluator` -- it is a parallel, purely additive
fast path. `evaluator.evaluate_config` remains the correctness ORACLE;
see `tests/opt/test_fast_replay.py` for the equivalence gate.

Ambiguity log (this module):
  1. `symbols` parameter (kept in the public signature for contract
     parity with `evaluator.evaluate_config`/`make_objective_fn`) is
     INTENTIONALLY UNUSED for entry generation here. Tracing
     `engine.py::Engine.step`: the composite/direction inputs are
     `TechnicalScorer.score(feed)` (uses only `feed.get_data(target,...)`,
     never touches the `symbols` map) and `MacroScorer.update_tick/score`
     (reads `self.cfg.symbols` -- the INSTRUMENT CONFIG's own symbol map,
     never the feed's externally-injected `symbols` dict). The externally
     passed `symbols` only reaches `feed.get_all_data(...)`, which feeds
     `_correlation_legacy`/`divergences` -- reported in the Snapshot but
     NOT inputs to `composite_score`/`direction`. So entries are fully
     determined by `cfg.symbols`/`cfg.target`, independent of the
     caller's `symbols` argument.
  2. `update_tick`'s per-step "current price" is the as-of price: the close
     of the most recent bar with `ts <= bar_times[seq]` (see
     `_tick_price_array`), matching `_ReplayFeed.get_current_price`. (An
     earlier revision mirrored a tick-count-modulo-length quirk in the
     oracle that fed the correlation tracker prices marching from the
     ABSOLUTE START of history rather than the replay window; that oracle
     bug was fixed to the leakage-safe as-of price and this fast path was
     updated to match. Both remain bit-exact against each other.)
  3. `MacroScorer.score()`'s `recent_return_bps` lookup (via
     `feed.get_data(symbol, 1, bars=10)`) is a SEPARATE, properly
     leakage-safe as-of windowed lookup (unrelated to the tick-count quirk
     above) -- replicated here via `Index.searchsorted` (backward as-of)
     against each asset's own M1 timestamps, matching
     `(closes[-1]-closes[-4])/closes[-4]*10000` exactly (needs >= 4 bars
     of that asset's own history at-or-before the step time, else 0.0).
  4. Coarser-TF technical alignment: a bar's technical state at M1 step
     `t` uses the latest CLOSED bar of each timeframe with `ts <= t`
     (backward/asof, allow_exact_matches=True) -- implemented via
     `pandas.merge_asof(direction="backward")`.
  5. EMA/RSI/MACD/ATR seed-window tolerance: the oracle recomputes these
     (via `ta`'s `.ewm(..., adjust=False)` recursive filters) on a FRESH
     `tail(200)` slice every step, seeded at that slice's first row. This
     module computes each indicator ONCE, continuously, over the full
     available history (a different, much-earlier seed). Both are the
     SAME linear recursive filter; by ~150-200 steps past either seed the
     seed's own contribution has decayed to a negligible residual (alpha
     values here range ~0.04-0.15, so `(1-alpha)^200` is between ~1e-3 and
     ~1e-9) -- i.e. both computations converge to the same steady state
     well within any realistic replay window, and are numerically
     indistinguishable to the tolerance this module targets (see the test
     module's documented tier). Bollinger Bands (a bounded rolling
     mean/std over the last `bb_period` bars) and the row-local
     price-action score are NOT approximations at all -- they are
     window-invariant and match the oracle exactly regardless of seed
     position.
  6. Rows before a timeframe has >= 50 bars of its OWN history (matching
     `calculate_all`'s/`calculate_technical_score`'s `len(df) < 50`
     guards) are neutral (score 50, direction NEUTRAL), same as the
     oracle. This only affects the first ~50 bars of a lake's history --
     far before any realistic replay window.
  7. Determinism: every `fast_evaluate_config` call reads fresh from disk
     (`lake.store.read_bars`) and builds fresh `RealtimeCorrelationTracker`
     instances; there is no shared mutable module state, no wall-clock, no
     RNG. Two identical calls produce bit-identical arrays end-to-end.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from sentinel.correlation_engine import RealtimeCorrelationTracker
from sentinel.indicators import calculate_all
from sentinel_engine.config import InstrumentConfig
from sentinel_engine.lake.store import read_bars
from sentinel_engine.opt.labels import triple_barrier
from sentinel_engine.opt.levers import apply_overrides
from sentinel_engine.opt.objective import ObjectiveResult, objective

#: sub-weights for the per-timeframe composite technical score -- byte-for-
#: byte the same constants as `sentinel_engine.technical._SUBWEIGHTS`.
_SUBWEIGHTS = {"ema": 0.30, "rsi": 0.20, "macd": 0.25, "bb": 0.15, "pa": 0.10}


# ───────────────────────── study-scoped memoization ───────────────────────

class _BoundedLRU:
    """A tiny, dependency-free bounded LRU dict. Not thread-safe (this
    module has no concurrency -- a single study drives one sequential
    search loop). `get`/`put` are the only operations used; `put` evicts
    the least-recently-used entry once `maxsize` is exceeded."""

    def __init__(self, maxsize: int) -> None:
        self._maxsize = maxsize
        self._data: "OrderedDict[Any, Any]" = OrderedDict()

    def get(self, key: Any, default: Any = None) -> Any:
        if key not in self._data:
            return default
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: Any, value: Any) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        if len(self._data) > self._maxsize:
            self._data.popitem(last=False)


class FastReplayCache:
    """Study-scoped memoization for `fast_evaluate_config`'s param-
    INDEPENDENT (or mostly-independent) work. ONE instance is created per
    study/objective (`make_fast_objective_fn`) and garbage-collected with
    it -- there is NO module-global mutable state, so two studies (or two
    test cases) never share, and calling `fast_evaluate_config` with
    `cache=None` is byte-identical to the pre-caching code path.

    Cache layers (see module docstring / task brief for the exact keys):
      1. raw parquet reads (`_read_tf`, `_target_m1_frame`) -- tiny key
         space, unbounded dict.
      2. per-TF vectorized technical score (`_vectorized_tf_score`) --
         tiny key space, unbounded dict.
      3. macro per-asset tick/return/recent-return arrays -- tiny key
         space, unbounded dict.
      4. `_technical_arrays` result, keyed on window + tf_weights --
         bounded LRU (cfg-dependent, so the key space can grow across a
         study; capped to avoid unbounded memory growth on a long run).
      5. `_macro_arrays` result, keyed on window + every macro lever that
         affects the tracker loop -- bounded LRU, same rationale as #4.

    All cached numpy arrays / DataFrames are treated as READ-ONLY once
    stored: `_vectorized_tf_score`/`_asof_align`/`_technical_arrays`/
    `_macro_arrays` never mutate an input array in place (verified by
    inspection -- every transform either allocates a new array via
    `np.where`/arithmetic or builds a fresh DataFrame), so no defensive
    copy is required for correctness; as an extra safety margin, raw
    DataFrames returned from the lake-read cache are read-only pandas
    objects consumed only via `.to_numpy()`/column selection (which
    themselves allocate), never assigned into or `.loc`-mutated anywhere
    in this module.
    """

    def __init__(self, array_cache_maxsize: int = 64) -> None:
        self._raw_reads: Dict[Any, pd.DataFrame] = {}
        self._tf_scores: Dict[Any, pd.DataFrame] = {}
        self._macro_asset_arrays: Dict[Any, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        self._technical_arrays: _BoundedLRU = _BoundedLRU(array_cache_maxsize)
        self._macro_arrays: _BoundedLRU = _BoundedLRU(array_cache_maxsize)


class _Entry(NamedTuple):
    ts: pd.Timestamp
    direction: str
    price_index: int


# ─────────────────────────── lake I/O helpers ────────────────────────────

def _target_m1_frame(
    lake_root: Path,
    target: str,
    window_end: pd.Timestamp,
    cache: Optional[FastReplayCache] = None,
) -> pd.DataFrame:
    """The target's full M1 history, truncated to `ts <= window_end` --
    identical rule to `evaluator._target_m1_frame`."""
    return _read_tf(lake_root, target, 1, window_end, cache)


def _read_tf(
    lake_root: Path,
    symbol: str,
    tf_min: int,
    window_end: pd.Timestamp,
    cache: Optional[FastReplayCache] = None,
) -> pd.DataFrame:
    """Param-independent raw read, keyed `(str(lake_root), symbol, tf_min,
    window_end_ns)` when `cache` is supplied (cache layer #1)."""
    if cache is None:
        df = read_bars(lake_root, symbol, tf_min)
        if df.empty:
            return df
        return df[df.index <= window_end]

    key = (str(lake_root), symbol, tf_min, window_end.value)
    hit = cache._raw_reads.get(key)
    if hit is not None:
        return hit
    df = read_bars(lake_root, symbol, tf_min)
    if not df.empty:
        df = df[df.index <= window_end]
    cache._raw_reads[key] = df
    return df


# ────────────────────── vectorized technical scoring ─────────────────────

def _vec_score_ema(price, e9, e21, e50, cross) -> Tuple[np.ndarray, np.ndarray]:
    cond0 = (price == 0) | (e9 == 0)
    cond1 = (e9 > e21) & (e21 > e50) & (e50 > 0)
    cond2 = (e9 < e21) & (e21 < e50) & (e50 > 0)
    cnt_above = (
        ((price > e9) & (e9 > 0)).astype(int)
        + ((price > e21) & (e21 > 0)).astype(int)
        + ((price > e50) & (e50 > 0)).astype(int)
    )
    cnt_below = (
        ((price < e9) & (e9 > 0)).astype(int)
        + ((price < e21) & (e21 > 0)).astype(int)
        + ((price < e50) & (e50 > 0)).astype(int)
    )
    cond3 = cnt_above >= 2
    cond4 = cnt_below >= 2

    sc = np.full(price.shape, 50.0)
    v = np.zeros(price.shape)
    sc = np.where(cond4, 35.0, sc); v = np.where(cond4, -1.0, v)
    sc = np.where(cond3, 65.0, sc); v = np.where(cond3, 1.0, v)
    sc = np.where(cond2, 15.0, sc); v = np.where(cond2, -1.0, v)
    sc = np.where(cond1, 85.0, sc); v = np.where(cond1, 1.0, v)

    apply_cross = ~cond0
    cross_up = apply_cross & (cross == 1)
    cross_dn = apply_cross & (cross == -1)
    sc = np.where(cross_up, np.minimum(100.0, sc + 15.0), sc)
    v = np.where(cross_up, 1.0, v)
    sc = np.where(cross_dn, np.maximum(0.0, sc - 15.0), sc)
    v = np.where(cross_dn, -1.0, v)

    # early-return semantics: cond0 bypasses everything above, always 50/0
    sc = np.where(cond0, 50.0, sc)
    v = np.where(cond0, 0.0, v)
    return sc, v


def _vec_score_rsi(rsi) -> Tuple[np.ndarray, np.ndarray]:
    sc = np.where(
        rsi >= 70, 30.0,
        np.where(
            rsi <= 30, 70.0,
            np.where(
                rsi > 50,
                np.round(55.0 + (rsi - 50.0) * 0.5, 1),
                np.round(45.0 - (50.0 - rsi) * 0.5, 1),
            ),
        ),
    )
    v = np.where(rsi >= 70, -1.0, np.where(rsi <= 30, 1.0, np.where(rsi > 50, 1.0, -1.0)))
    return sc, v


def _vec_score_macd(hist, atr) -> Tuple[np.ndarray, np.ndarray]:
    valid_atr = atr > 0
    safe_atr = np.where(valid_atr, atr, 1.0)
    h_norm = hist / safe_atr
    sc_norm = np.round(np.clip(50.0 + h_norm * 40.0, 0.0, 100.0), 1)
    v_norm = np.where(hist > 0, 1.0, np.where(hist < 0, -1.0, 0.0))

    sc_raw = np.where(
        hist > 0, np.round(np.minimum(100.0, 60.0 + np.abs(hist) * 1000.0), 1),
        np.where(hist < 0, np.round(np.maximum(0.0, 40.0 - np.abs(hist) * 1000.0), 1), 50.0),
    )
    v_raw = np.where(hist > 0, 1.0, np.where(hist < 0, -1.0, 0.0))

    sc = np.where(valid_atr, sc_norm, sc_raw)
    v = np.where(valid_atr, v_norm, v_raw)
    return sc, v


def _vec_score_bb(bb_pct) -> Tuple[np.ndarray, np.ndarray]:
    sc = np.where(
        bb_pct > 0.95, 25.0,
        np.where(bb_pct < 0.05, 75.0, np.where(bb_pct > 0.7, 40.0, np.where(bb_pct < 0.3, 60.0, 50.0))),
    )
    v = np.where(bb_pct > 0.95, -1.0, np.where(bb_pct < 0.05, 1.0, 0.0))
    return sc, v


def _vec_score_pa(openp, high, low, close) -> Tuple[np.ndarray, np.ndarray]:
    body = close - openp
    rng = high - low
    safe_rng = np.where(rng == 0, 1.0, rng)
    bp = np.where(rng == 0, 0.0, np.abs(body) / safe_rng)
    strong = bp > 0.7
    sc = np.where(
        rng == 0, 50.0,
        np.where(strong & (body > 0), 70.0, np.where(strong & (body <= 0), 30.0, np.where(body > 0, 55.0, 45.0))),
    )
    v = np.where(
        rng == 0, 0.0,
        np.where(strong & (body > 0), 1.0, np.where(strong & (body <= 0), -1.0, 0.0)),
    )
    return sc, v


def _vectorized_tf_score(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized replication of
    `sentinel_engine.technical.calculate_technical_score` applied to EVERY
    row of `df` (as if that row were the last row of its own trailing
    tail-window) -- see module ambiguity #5 for the tolerance this
    implies. Returns a frame indexed like `df` with columns
    `composite_score` (float) and `direction` (str)."""
    n = len(df)
    idx = df.index
    if n < 50:
        return pd.DataFrame(
            {"composite_score": np.full(n, 50.0), "direction": np.full(n, "NEUTRAL", dtype=object)},
            index=idx,
        )

    ind = calculate_all(df)
    price = ind["close"].to_numpy(dtype=float)
    e9 = ind["ema_9"].to_numpy(dtype=float)
    e21 = ind["ema_21"].to_numpy(dtype=float)
    e50 = ind["ema_50"].to_numpy(dtype=float)
    cross = ind["ema_cross"].to_numpy(dtype=float)
    rsi = ind["rsi"].to_numpy(dtype=float)
    macd_h = ind["macd_histogram"].to_numpy(dtype=float)
    atr = ind["atr"].to_numpy(dtype=float)
    bb_pct = ind["bb_pct"].to_numpy(dtype=float)
    openp = ind["open"].to_numpy(dtype=float)
    high = ind["high"].to_numpy(dtype=float)
    low = ind["low"].to_numpy(dtype=float)
    close = ind["close"].to_numpy(dtype=float)

    sc_ema, v_ema = _vec_score_ema(price, e9, e21, e50, cross)
    sc_rsi, v_rsi = _vec_score_rsi(rsi)
    sc_macd, v_macd = _vec_score_macd(macd_h, atr)
    sc_bb, v_bb = _vec_score_bb(bb_pct)
    sc_pa, v_pa = _vec_score_pa(openp, high, low, close)

    w = _SUBWEIGHTS
    composite = sc_ema * w["ema"] + sc_rsi * w["rsi"] + sc_macd * w["macd"] + sc_bb * w["bb"] + sc_pa * w["pa"]
    composite = np.round(np.clip(composite, 0.0, 100.0), 1)
    votes = v_ema + v_rsi + v_macd + v_bb + v_pa
    direction = np.where(votes > 1, "LONG", np.where(votes < -1, "SHORT", "NEUTRAL"))

    # rows where any indicator is still NaN (indicator warm-up, matching
    # calculate_technical_score's implicit all-comparisons-False->else
    # fallback -- see ambiguity #6) are forced neutral wholesale.
    invalid = (
        np.isnan(e9) | np.isnan(e21) | np.isnan(e50) | np.isnan(rsi)
        | np.isnan(macd_h) | np.isnan(atr) | np.isnan(bb_pct)
    )
    composite = np.where(invalid, 50.0, composite)
    direction = np.where(invalid, "NEUTRAL", direction)

    return pd.DataFrame({"composite_score": composite, "direction": direction}, index=idx)


def _asof_align(tbl: pd.DataFrame, bar_times: pd.DatetimeIndex) -> pd.DataFrame:
    """As-of (backward, allow_exact_matches) alignment of a per-timeframe
    score table onto the M1 step timeline (ambiguity #4)."""
    n = len(bar_times)
    if tbl.empty:
        return pd.DataFrame(
            {"composite_score": np.full(n, 50.0), "direction": np.full(n, "NEUTRAL", dtype=object)},
            index=bar_times,
        )
    left = pd.DataFrame({"ts": bar_times})
    right = tbl.reset_index().rename(columns={tbl.index.name or "index": "ts"})
    merged = pd.merge_asof(left, right, on="ts", direction="backward", allow_exact_matches=True)
    merged = merged.set_index("ts")
    merged["composite_score"] = merged["composite_score"].fillna(50.0)
    merged["direction"] = merged["direction"].fillna("NEUTRAL")
    return merged


def _vectorized_tf_score_cached(
    lake_root: Path,
    target: str,
    tf_min: int,
    window_end: pd.Timestamp,
    cache: Optional[FastReplayCache],
) -> pd.DataFrame:
    """Cache layer #2: the per-TF vectorized score is param-independent
    (`_vectorized_tf_score`/`calculate_all` never read `cfg` levers), keyed
    `(str(lake_root), target, tf_min, window_end_ns)`."""
    if cache is None:
        raw = _read_tf(lake_root, target, tf_min, window_end, None)
        return _vectorized_tf_score(raw)

    key = (str(lake_root), target, tf_min, window_end.value)
    hit = cache._tf_scores.get(key)
    if hit is not None:
        return hit
    raw = _read_tf(lake_root, target, tf_min, window_end, cache)
    tbl = _vectorized_tf_score(raw)
    cache._tf_scores[key] = tbl
    return tbl


def _technical_arrays(
    cfg: InstrumentConfig,
    lake_root: Path,
    window_end: pd.Timestamp,
    bar_times: pd.DatetimeIndex,
    window_key: Optional[Tuple[str, int, int]] = None,
    cache: Optional[FastReplayCache] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Returns (tech_score, tech_dir) arrays aligned to `bar_times`.

    Cache layer #4 (whole-result memoization): keyed `window_key +
    sorted(tf_weights.items())` -- `tf_weights` is the only cfg dependence
    in this function's output."""
    n = len(bar_times)
    if n == 0:
        return np.zeros(0), np.full(0, "NEUTRAL", dtype=object)

    tf_weights = cfg.technical.tf_weights

    if cache is not None and window_key is not None:
        key = (window_key, tuple(sorted(tf_weights.items())))
        hit = cache._technical_arrays.get(key)
        if hit is not None:
            return hit

    aligned: Dict[str, pd.DataFrame] = {}
    for tf_name, tf_min in cfg.data.timeframes.items():
        tbl = _vectorized_tf_score_cached(lake_root, cfg.target, tf_min, window_end, cache)
        aligned[tf_name] = _asof_align(tbl, bar_times)

    wscore = np.zeros(n)
    for tf_name, weight in tf_weights.items():
        tbl = aligned.get(tf_name)
        if tbl is None:
            continue
        wscore = wscore + tbl["composite_score"].to_numpy(dtype=float) * float(weight)
    tech_score = np.round(wscore, 1)

    if "M15" in aligned:
        tech_dir = aligned["M15"]["direction"].to_numpy()
    else:
        tech_dir = np.full(n, "NEUTRAL", dtype=object)

    if cache is not None and window_key is not None:
        cache._technical_arrays.put(key, (tech_score, tech_dir))

    return tech_score, tech_dir


# ───────────────────────────── macro (fast) ───────────────────────────────

def _tick_price_array(bar_times: pd.DatetimeIndex, raw_full: pd.DataFrame) -> np.ndarray:
    """Each step's as-of current price: the close of the most recent bar with
    `ts <= bar_times[seq]` (matches `_ReplayFeed.get_current_price`). Returns
    the bid array (0.0 where no bar exists at-or-before the step -- matches
    the oracle's empty-frame zero price)."""
    n = len(bar_times)
    if raw_full.empty:
        return np.zeros(n)
    pos = raw_full.index.searchsorted(bar_times, side="right") - 1
    close = raw_full["close"].to_numpy(dtype=float)
    bid = np.where(pos >= 0, close[np.clip(pos, 0, len(close) - 1)], 0.0)
    return bid


def _tick_returns_bps(bid: np.ndarray) -> np.ndarray:
    """Byte-for-byte replication of `MacroScorer.update_tick`'s return calc
    (`(curr-prev)/prev*10000`), with `prev` carried forward across any
    zero/invalid ticks and the FIRST valid tick always yielding ret=0.0
    (matches `_prev_prices.get(key, curr_bid)`'s self-fallback)."""
    n = len(bid)
    ret = np.zeros(n)
    prev = None
    for i in range(n):
        curr = bid[i]
        if curr <= 0:
            continue  # skip: state frozen, ret stays 0 for this index
        if prev is None:
            ret[i] = 0.0
        else:
            ret[i] = (curr - prev) / prev * 10000.0
        prev = curr
    return ret


def _recent_return_bps(bar_times: pd.DatetimeIndex, raw_full: pd.DataFrame) -> np.ndarray:
    """Replicates `MacroScorer.score()`'s `recent_return_bps` lookup
    (ambiguity #3): `(closes[-1]-closes[-4])/closes[-4]*10000` off
    `feed.get_data(symbol, 1, bars=10)`, via as-of backward alignment."""
    n = len(bar_times)
    if raw_full.empty:
        return np.zeros(n)
    pos = raw_full.index.searchsorted(bar_times, side="right") - 1
    close = raw_full["close"].to_numpy(dtype=float)
    out = np.zeros(n)
    valid = pos >= 3
    p = pos[valid]
    out[valid] = (close[p] - close[p - 3]) / close[p - 3] * 10000.0
    return out


def _asset_arrays_cached(
    lake_root: Path,
    symbol: str,
    window_end: pd.Timestamp,
    bar_times: pd.DatetimeIndex,
    window_key: Optional[Tuple[str, int, int]],
    cache: Optional[FastReplayCache],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cache layer #3 (per macro asset): `_tick_price_array`,
    `_tick_returns_bps`, `_recent_return_bps` are all param-independent;
    keyed `(str(lake_root), symbol, window_key)`. Returns
    (bid, ret_bps, recent_bps)."""
    if cache is None or window_key is None:
        raw = _read_tf(lake_root, symbol, 1, window_end, cache)
        bid = _tick_price_array(bar_times, raw)
        ret = _tick_returns_bps(bid)
        recent = _recent_return_bps(bar_times, raw)
        return bid, ret, recent

    key = (str(lake_root), symbol, window_key)
    hit = cache._macro_asset_arrays.get(key)
    if hit is not None:
        return hit
    raw = _read_tf(lake_root, symbol, 1, window_end, cache)
    bid = _tick_price_array(bar_times, raw)
    ret = _tick_returns_bps(bid)
    recent = _recent_return_bps(bar_times, raw)
    result = (bid, ret, recent)
    cache._macro_asset_arrays[key] = result
    return result


def _macro_arrays(
    cfg: InstrumentConfig,
    lake_root: Path,
    window_end: pd.Timestamp,
    bar_times: pd.DatetimeIndex,
    window_key: Optional[Tuple[str, int, int]] = None,
    cache: Optional[FastReplayCache] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Returns (macro_score, macro_dir) arrays aligned to `bar_times`, via a
    SINGLE forward pass driving a fresh `RealtimeCorrelationTracker`
    (imported verbatim -- its EWMA/concordance/z-score math is not
    reimplemented).

    Cache layer #5 (whole-result memoization): keyed `window_key + sorted
    tuple of every macro input that affects the tracker loop`: lambda_var,
    lambda_cov, concordance_window, tanh_sensitivity, direction_threshold,
    asset_weights (sorted items), expected_correlations (sorted items),
    symbols (sorted items)."""
    n = len(bar_times)
    if n == 0:
        return np.zeros(0), np.full(0, "NEUTRAL", dtype=object)

    if cache is not None and window_key is not None:
        macro_key = (
            window_key,
            float(cfg.macro.tracker.lambda_var),
            float(cfg.macro.tracker.lambda_cov),
            int(cfg.macro.tracker.concordance_window),
            float(cfg.macro.tanh_sensitivity),
            float(cfg.macro.direction_threshold),
            tuple(sorted(cfg.asset_weights.items())),
            tuple(sorted(cfg.expected_correlations.items())),
            tuple(sorted(cfg.symbols.items())),
        )
        hit = cache._macro_arrays.get(macro_key)
        if hit is not None:
            return hit
    else:
        macro_key = None

    target_bid, ret_target, _ = _asset_arrays_cached(lake_root, cfg.target, window_end, bar_times, window_key, cache)

    asset_keys = list(cfg.asset_weights.keys())
    asset_bid: Dict[str, np.ndarray] = {}
    ret_asset: Dict[str, np.ndarray] = {}
    recent_bps: Dict[str, np.ndarray] = {}
    exp_sign: Dict[str, float] = {}
    base_weight: Dict[str, float] = {}
    symbol_of: Dict[str, str] = {}

    for asset_key in asset_keys:
        symbol = cfg.symbols.get(asset_key, "")
        symbol_of[asset_key] = symbol
        base_weight[asset_key] = float(cfg.asset_weights[asset_key])
        exp_sign[asset_key] = float(np.sign(cfg.expected_correlations.get(asset_key, 0.0)))
        if not symbol:
            asset_bid[asset_key] = np.zeros(n)
            ret_asset[asset_key] = np.zeros(n)
            recent_bps[asset_key] = np.zeros(n)
            continue
        asset_bid[asset_key], ret_asset[asset_key], recent_bps[asset_key] = _asset_arrays_cached(
            lake_root, symbol, window_end, bar_times, window_key, cache
        )

    tracker = RealtimeCorrelationTracker(
        lambda_var=cfg.macro.tracker.lambda_var,
        lambda_cov=cfg.macro.tracker.lambda_cov,
        concordance_window=cfg.macro.tracker.concordance_window,
    )

    tanh_sens = cfg.macro.tanh_sensitivity
    dth = cfg.macro.direction_threshold

    macro_score = np.zeros(n)
    macro_dir = np.full(n, "NEUTRAL", dtype=object)

    for seq in range(n):
        # ── update_tick ──
        if target_bid[seq] > 0:
            for asset_key in asset_keys:
                symbol = symbol_of[asset_key]
                if not symbol:
                    continue
                curr_bid = asset_bid[asset_key][seq]
                if curr_bid <= 0:
                    continue
                tracker.update(asset_key, ret_target[seq], ret_asset[asset_key][seq], exp_sign[asset_key])

        # ── score ──
        total_weighted_vote = 0.0
        total_max_weight = 0.0
        for asset_key in asset_keys:
            symbol = symbol_of[asset_key]
            if not symbol:
                continue
            confidence = tracker.get_confidence(asset_key)["confidence"]
            raw_vote = float(np.tanh(recent_bps[asset_key][seq] / tanh_sens)) * exp_sign[asset_key]
            bw = base_weight[asset_key]
            effective_weight = confidence * bw
            total_weighted_vote += raw_vote * effective_weight
            total_max_weight += confidence * bw

        consensus = total_weighted_vote / total_max_weight if total_max_weight > 0.01 else 0.0
        direction_score = round(max(0.0, min(100.0, 50.0 + consensus * 50.0)), 1)
        macro_score[seq] = direction_score
        if consensus > dth:
            macro_dir[seq] = "LONG"
        elif consensus < -dth:
            macro_dir[seq] = "SHORT"
        else:
            macro_dir[seq] = "NEUTRAL"

    if cache is not None and macro_key is not None:
        cache._macro_arrays.put(macro_key, (macro_score, macro_dir))

    return macro_score, macro_dir


# ───────────────────────── composite + direction ─────────────────────────

def _composite_and_direction(
    cfg: InstrumentConfig,
    tech_score: np.ndarray,
    tech_dir: np.ndarray,
    macro_score: np.ndarray,
    macro_dir: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    w_tech = cfg.composite.weights["technical"]
    w_corr = cfg.composite.weights["correlation"]
    composite = tech_score * w_tech + macro_score * w_corr
    composite = np.round(np.clip(composite, 0.0, 100.0), 1)

    dvw_tech = cfg.composite.direction_vote_weights["technical"]
    dvw_macro = cfg.composite.direction_vote_weights["macro"]
    long_v = (tech_dir == "LONG") * dvw_tech + (macro_dir == "LONG") * dvw_macro
    short_v = (tech_dir == "SHORT") * dvw_tech + (macro_dir == "SHORT") * dvw_macro
    neutral_v = (tech_dir == "NEUTRAL") * dvw_tech + (macro_dir == "NEUTRAL") * dvw_macro

    direction = np.where(
        (long_v >= short_v) & (long_v >= neutral_v), "LONG",
        np.where(short_v >= neutral_v, "SHORT", "NEUTRAL"),
    )
    return composite, direction


# ──────────────────────────── entries + labels ────────────────────────────

def _replay_entries_fast(
    cfg: InstrumentConfig,
    lake_root: Path,
    bar_times: pd.DatetimeIndex,
    window_end: pd.Timestamp,
    price_index: Dict[pd.Timestamp, int],
    window_key: Optional[Tuple[str, int, int]] = None,
    cache: Optional[FastReplayCache] = None,
) -> List[_Entry]:
    if len(bar_times) == 0:
        return []

    tech_score, tech_dir = _technical_arrays(cfg, lake_root, window_end, bar_times, window_key, cache)
    macro_score, macro_dir = _macro_arrays(cfg, lake_root, window_end, bar_times, window_key, cache)
    composite, direction = _composite_and_direction(cfg, tech_score, tech_dir, macro_score, macro_dir)

    thresh = cfg.composite.score_alert_threshold
    entries: List[_Entry] = []
    for seq, ts in enumerate(bar_times):
        if composite[seq] < thresh:
            continue
        d = direction[seq]
        if d not in ("LONG", "SHORT"):
            continue
        idx = price_index.get(ts)
        if idx is None:
            continue
        entries.append(_Entry(ts=ts, direction=d, price_index=idx))
    return entries


def _label_entries(
    prices: Sequence[float],
    entries: Sequence[_Entry],
    tp_r: float,
    sl: float,
    horizon: int,
) -> List[Tuple[int, float]]:
    """Identical direction-aware triple-barrier labeling to
    `evaluator._label_entries` (module ambiguity: reuse via a local copy,
    not an import of evaluator's private helper -- see mission brief)."""
    tp = tp_r * sl
    long_idx = [e.price_index for e in entries if e.direction == "LONG"]
    short_idx = [e.price_index for e in entries if e.direction == "SHORT"]

    out: List[Tuple[int, float]] = []
    if long_idx:
        for lbl in triple_barrier(prices, tp=tp, sl=sl, horizon=horizon, entry_indices=long_idx):
            out.append((lbl.entry_index, lbl.pnl_r))
    if short_idx:
        neg_prices = [-p for p in prices]
        for lbl in triple_barrier(neg_prices, tp=tp, sl=sl, horizon=horizon, entry_indices=short_idx):
            out.append((lbl.entry_index, lbl.pnl_r))

    out.sort(key=lambda pair: pair[0])
    return out


# ──────────────────────────────── public API ──────────────────────────────

def fast_evaluate_config(
    cfg: InstrumentConfig,
    param_overrides: Dict[str, float],
    lake_root: Path,
    window_start: datetime,
    window_end: datetime,
    symbols: Dict[str, str],
    *,
    horizon: int,
    tp_r: float,
    sl: float,
    reference_cfg: Optional[InstrumentConfig] = None,
    cache: Optional[FastReplayCache] = None,
    **objective_kwargs,
) -> ObjectiveResult:
    """Vectorized fast-path equivalent of
    `sentinel_engine.opt.evaluator.evaluate_config` -- SAME signature and
    return type. `symbols` is accepted for contract parity but unused for
    entry generation (ambiguity #1 -- it only ever reached legacy
    correlation/divergence reporting in the oracle, not `composite_score`/
    `direction`).

    ``cache`` (optional, default ``None``): a `FastReplayCache` for
    study-scoped memoization of the param-independent (or mostly-
    independent) work. When ``None`` (the default), behavior is byte-for-
    byte identical to the original uncached implementation -- existing
    callers that don't pass `cache` are completely unaffected. See
    `FastReplayCache`'s docstring for the exact cache keys."""
    lake_root = Path(lake_root)
    w_start = pd.Timestamp(window_start)
    w_end = pd.Timestamp(window_end)
    if w_start.tzinfo is None or w_end.tzinfo is None:
        raise ValueError("fast_evaluate_config: window_start/window_end must be tz-aware")
    w_start = w_start.tz_convert("UTC")
    w_end = w_end.tz_convert("UTC")

    cfg2 = apply_overrides(cfg, param_overrides)

    m1 = _target_m1_frame(lake_root, cfg2.target, w_end, cache)
    if m1.empty:
        prices: List[float] = []
        price_index: Dict[pd.Timestamp, int] = {}
        bar_times = pd.DatetimeIndex([])
    else:
        prices = [float(p) for p in m1["close"].tolist()]
        price_index = {ts: i for i, ts in enumerate(m1.index)}
        bar_times = pd.DatetimeIndex([t for t in m1.index if t >= w_start])

    window_key = (cfg2.target, w_start.value, w_end.value)
    candidate_entries = _replay_entries_fast(cfg2, lake_root, bar_times, w_end, price_index, window_key, cache)
    trades = _label_entries(prices, candidate_entries, tp_r=tp_r, sl=sl, horizon=horizon)
    trades_R = [pnl for _, pnl in trades]

    ref_cfg = reference_cfg if reference_cfg is not None else cfg
    ref_window_key = (ref_cfg.target, w_start.value, w_end.value)
    ref_entries = _replay_entries_fast(ref_cfg, lake_root, bar_times, w_end, price_index, ref_window_key, cache)
    n_ref = float(len(ref_entries))

    return objective(trades_R, n_ref=n_ref, **objective_kwargs)


def make_fast_objective_fn(
    cfg: InstrumentConfig,
    lake_root: Path,
    window: Tuple[datetime, datetime],
    symbols: Dict[str, str],
    **kw,
) -> Callable[[Dict[str, float]], float]:
    """Fast-path equivalent of `evaluator.make_objective_fn`. Creates ONE
    `FastReplayCache` internally, shared across every `fast_evaluate_config`
    call this objective function makes (so every trial in a staged search
    over this window reuses the same param-independent work). The cache is
    private to this closure -- garbage-collected with it, never a module
    global -- so determinism/test isolation across separate objective
    functions (or separate studies) is unaffected."""
    window_start, window_end = window
    cache = FastReplayCache()

    def _objective_fn(params: Dict[str, float]) -> float:
        result = fast_evaluate_config(
            cfg, params, lake_root, window_start, window_end, symbols, cache=cache, **kw
        )
        return result.score

    return _objective_fn
