"""
sentinel_engine.opt.evaluator -- the replay evaluator: the real-data bridge
between `sentinel_engine.engine.Engine` (config-parameterized scoring) and
the `sentinel_engine.opt` machinery (labels, objective, search) -- P4 wiring
layer. This module drives a real optimization study against the real price
lake + the scoring Engine; the other `opt/*` modules stay data-agnostic.

Ambiguity log (this module):
  1. Replay cadence: the Engine is stepped once per M1 (1-minute, the finest
     available cadence) bar of the TARGET symbol within
     `[window_start, window_end]` -- "the target's bar timestamps" per the
     task brief. Macro/technical scorers pull their own multi-TF windows
     internally via `feed.get_data(...)`; M1 is simply the tick/step
     cadence (matching `cfg.data.timeframes["M1"] == 1`).
  2. Feed wrapper symbol map: `_ReplayFeed(symbols=...)` takes the caller's
     explicit `symbols` dict (NOT `sentinel.config.SYMBOLS`), so a hermetic
     test lake with only a handful of ingested symbols works without
     pulling in the USDCLP-hardwired default. `engine.py`'s own docstring
     notes that production's `get_all_data` is "always keyed off the
     USDCLP/target symbol group regardless of the instrument being
     scored" -- that quirk lives in `FakeFeed`/`LiveMT5Feed`'s callers, not
     in any scoring code we own; we intentionally do NOT reproduce it here.
     Keying `get_all_data` off the instrument's OWN macro basket is the
     semantically-correct behavior for backtesting one specific instrument
     and touches no scoring code.
  3. `HistoricalFeed.as_of` is fixed at construction (by design, per its own
     leakage-gate docstring), which is unsuitable for a single multi-step
     replay that must keep ONE Engine's MacroScorer state alive across
     many bars. Per the task brief, a SMALL feed wrapper (`_ReplayFeed`) is
     built here instead of modifying `feed_historical.py`: it reuses
     `sentinel_engine.lake.store.read_bars` and mirrors
     `HistoricalFeed._load`'s leakage gate EXACTLY (filter to
     `ts <= as_of` BEFORE any further computation), but exposes a mutable
     `advance(t)` so the same feed instance can be stepped bar-by-bar.
  4. Entry definition: an entry fires at any replay step where
     `snap.composite_score >= cfg.composite.score_alert_threshold and not
     snap.blocked` (mirrors the live "alert" semaphore in `engine.py`);
     side is `snap.direction`. NEUTRAL-direction fires are not tradeable
     (no barrier direction to label) and are excluded from `trades_R`.
  5. Direction-aware triple-barrier: `labels.triple_barrier` only
     implements a "long-style" barrier (tp above entry, sl below). SHORT
     entries are labeled by negating the price series for those entries
     before calling `triple_barrier` -- a standard mirroring trick: a
     profitable SHORT (price falls) becomes a profitable "LONG" in the
     negated series, and the resulting `pnl_r` sign is correct without any
     change to `labels.py`.
  6. Horizon-overrun / leakage-consistent handling at `window_end`: the
     price path handed to `triple_barrier` is truncated to bars with
     `ts <= window_end` (never beyond). `triple_barrier` already silently
     skips any entry with fewer than `horizon` forward bars available in
     the array it's given (its own "undecidable outcome" rule) -- so
     entries whose horizon would cross `window_end` are DROPPED, never
     fabricated as an early vertical/timeout. This reuses `labels.py`'s
     existing behavior unmodified and treats `window_end` as a hard fold
     boundary (Lopez de Prado purging intent), matching
     `purge_labels_at_boundary`'s spirit even though that function isn't
     called directly here (there is only one fold per `evaluate_config`
     call, not a train/test pair to purge between).
  7. `n_ref` (Layer-2 reference-policy count, Fable Sec 2.4): computed by
     replaying `reference_cfg` (or, if omitted, the ORIGINAL un-overridden
     `cfg`) over the identical window and counting its entries the same
     way as the candidate. This is a second, independent replay (fresh
     `Engine` + fresh `_ReplayFeed`) so neither run's MacroScorer EWMA
     state leaks into the other.
  8. Determinism: every `evaluate_config` call constructs brand-new
     `Engine`/`_ReplayFeed` instances reading from disk
     (`lake.store.read_bars`); there is no shared mutable module-level
     state, no wall-clock, no RNG. Two identical calls read the same
     Parquet bytes and produce bit-identical `trades_R`/`score`.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

import pandas as pd

from sentinel_engine.config import InstrumentConfig
from sentinel_engine.engine import Engine
from sentinel_engine.lake.store import read_bars
from sentinel_engine.opt.labels import triple_barrier
from sentinel_engine.opt.levers import apply_overrides
from sentinel_engine.opt.objective import ObjectiveResult, objective

#: matches feed_historical.HistoricalFeed's SPREAD_PCT (kept local since we
#: must not import/modify feed_historical.py's internals).
SPREAD_PCT = 0.0002


class _ReplayFeed:
    """Small, mutable-`as_of` Feed wrapper for a single replay pass.

    Mirrors `feed_historical.HistoricalFeed`'s leakage gate EXACTLY (filter
    to `ts <= as_of` BEFORE any further computation -- see ambiguity #3)
    but exposes `advance(t)` so ONE feed instance can be stepped bar-by-bar
    across a window while keeping ONE Engine's `MacroScorer` state alive.
    Read-only: never writes to the lake, never places orders.
    """

    def __init__(self, lake_root: Path, symbols: Dict[str, str], as_of: datetime):
        self._lake_root = Path(lake_root)
        self._symbols = dict(symbols)
        self._raw_cache: Dict[Tuple[str, int], pd.DataFrame] = {}
        self._tick_idx: Dict[str, int] = {}
        self._as_of: pd.Timestamp
        self.advance(as_of)

    def advance(self, t: datetime) -> None:
        ts = pd.Timestamp(t)
        if ts.tzinfo is None:
            raise ValueError("_ReplayFeed.advance: t must be tz-aware")
        self._as_of = ts.tz_convert("UTC")

    @property
    def as_of(self) -> pd.Timestamp:
        return self._as_of

    def _raw(self, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
        key = (symbol, timeframe_minutes)
        cached = self._raw_cache.get(key)
        if cached is None:
            cached = read_bars(self._lake_root, symbol, timeframe_minutes)
            self._raw_cache[key] = cached
        return cached

    def _filtered(self, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
        df = self._raw(symbol, timeframe_minutes)
        if df.empty:
            return df
        # THE leakage gate: filter first, compute second (mirrors
        # HistoricalFeed._load exactly).
        return df[df.index <= self._as_of]

    # ── Feed protocol ─────────────────────────────────────────────────
    def get_data(self, symbol: str, timeframe_minutes: int = 15, bars: int = 200) -> pd.DataFrame:
        df = self._filtered(symbol, timeframe_minutes)
        if df.empty:
            return df
        return df.tail(bars)

    def get_current_price(self, symbol: str) -> dict:
        df1 = self._filtered(symbol, 1)
        if df1.empty:
            return {"bid": 0, "ask": 0, "spread": 0, "time": None, "source": "replay"}
        idx = self._tick_idx.get(symbol, 0)
        n = len(df1)
        i = idx % n
        self._tick_idx[symbol] = idx + 1
        bid = float(df1["close"].iloc[i])
        spread = round(bid * SPREAD_PCT, 6)
        return {"bid": bid, "ask": bid + spread, "spread": spread, "time": None, "source": "replay"}

    def get_all_data(self, timeframe_minutes: int = 15, bars: int = 200) -> dict:
        all_data = {}
        for key, symbol in self._symbols.items():
            df = self.get_data(symbol, timeframe_minutes, bars)
            if not df.empty:
                all_data[key] = df
        return all_data

    def positions(self) -> list:
        return []

    def now(self) -> datetime:
        return self._as_of.to_pydatetime()


class _Entry(NamedTuple):
    ts: pd.Timestamp
    direction: str
    price_index: int  # position within the target's truncated M1 price array


def _target_m1_frame(lake_root: Path, target: str, window_end: pd.Timestamp) -> pd.DataFrame:
    """The target's full M1 history, truncated to `ts <= window_end` (the
    leakage-consistent horizon-overrun rule, ambiguity #6)."""
    df = read_bars(lake_root, target, 1)
    if df.empty:
        return df
    return df[df.index <= window_end]


def _replay_entries(
    cfg: InstrumentConfig,
    lake_root: Path,
    symbols: Dict[str, str],
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    price_index: Dict[pd.Timestamp, int],
) -> List[_Entry]:
    """Step ONE `Engine` (holding one `MacroScorer`, alive for the whole
    replay) across the target's M1 bar timestamps in
    `[window_start, window_end]`; record every bar where the Engine fires
    an alert-or-stronger, non-blocked, directional signal (ambiguity #4)."""
    target = cfg.target
    m1 = _target_m1_frame(lake_root, target, window_end)
    if m1.empty:
        return []
    bar_times = [t for t in m1.index if t >= window_start]
    if not bar_times:
        return []

    feed = _ReplayFeed(lake_root, symbols, as_of=bar_times[0].to_pydatetime())
    eng = Engine(cfg, feed)

    entries: List[_Entry] = []
    for seq, ts in enumerate(bar_times):
        feed.advance(ts.to_pydatetime())
        snap = eng.step(seq=seq)
        if snap.blocked:
            continue
        if snap.composite_score < cfg.composite.score_alert_threshold:
            continue
        if snap.direction not in ("LONG", "SHORT"):
            continue
        idx = price_index.get(ts)
        if idx is None:
            continue  # defensive: ts always comes from the same m1 index
        entries.append(_Entry(ts=ts, direction=snap.direction, price_index=idx))
    return entries


def _label_entries(
    prices: Sequence[float],
    entries: Sequence[_Entry],
    tp_r: float,
    sl: float,
    horizon: int,
) -> List[Tuple[int, float]]:
    """Direction-aware triple-barrier labeling (ambiguity #5). Returns
    `(price_index, pnl_r)` pairs sorted chronologically by `price_index`."""
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


def evaluate_config(
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
    **objective_kwargs,
) -> ObjectiveResult:
    """Evaluate one candidate config (`cfg` + `param_overrides`) by
    replaying the Engine over `[window_start, window_end]` and scoring the
    resulting trades via `sentinel_engine.opt.objective.objective`.

    Args:
        cfg: base `InstrumentConfig` (e.g. `load_instrument("gold")`).
        param_overrides: lever values to apply via
            `sentinel_engine.opt.levers.apply_overrides` (may be empty for
            the unmodified baseline).
        lake_root: Parquet lake root (see `sentinel_engine.lake.store`).
        window_start / window_end: tz-aware replay window (inclusive).
        symbols: macro-basket symbol map used to build the feed (passed
            explicitly, NOT read from `cfg.symbols`, so a caller can use a
            hermetic/partial test lake -- see ambiguity #2).
        horizon, tp_r, sl: triple-barrier params (`tp = tp_r * sl`, both in
            the target's raw price units; `horizon` in bars).
        reference_cfg: the fixed Layer-2 reference policy for `n_ref`
            (defaults to the UNMODIFIED `cfg`, i.e. current production).
        **objective_kwargs: forwarded to `objective()` (e.g. `n_min`,
            `pf_cap`, `win_rate_min`, `max_dd_mult`, `baseline_maxDD_R`).

    Returns:
        `ObjectiveResult` scoring the candidate's replayed trades.
    """
    lake_root = Path(lake_root)
    w_start = pd.Timestamp(window_start)
    w_end = pd.Timestamp(window_end)
    if w_start.tzinfo is None or w_end.tzinfo is None:
        raise ValueError("evaluate_config: window_start/window_end must be tz-aware")
    w_start = w_start.tz_convert("UTC")
    w_end = w_end.tz_convert("UTC")

    cfg2 = apply_overrides(cfg, param_overrides)

    m1 = _target_m1_frame(lake_root, cfg2.target, w_end)
    if m1.empty:
        prices: List[float] = []
        price_index: Dict[pd.Timestamp, int] = {}
    else:
        prices = [float(p) for p in m1["close"].tolist()]
        price_index = {ts: i for i, ts in enumerate(m1.index)}

    candidate_entries = _replay_entries(cfg2, lake_root, symbols, w_start, w_end, price_index)
    trades = _label_entries(prices, candidate_entries, tp_r=tp_r, sl=sl, horizon=horizon)
    trades_R = [pnl for _, pnl in trades]

    ref_cfg = reference_cfg if reference_cfg is not None else cfg
    ref_entries = _replay_entries(ref_cfg, lake_root, symbols, w_start, w_end, price_index)
    n_ref = float(len(ref_entries))

    return objective(trades_R, n_ref=n_ref, **objective_kwargs)


def make_objective_fn(
    cfg: InstrumentConfig,
    lake_root: Path,
    window: Tuple[datetime, datetime],
    symbols: Dict[str, str],
    **kw,
) -> Callable[[Dict[str, float]], float]:
    """Return a plain `Dict[str, float] -> float` callable suitable for
    `sentinel_engine.opt.search.staged_search`'s `objective_fn` contract:
    each call evaluates one candidate param dict against `evaluate_config`
    and returns its `.score`.

    `window` is `(window_start, window_end)`; `**kw` is forwarded to
    `evaluate_config` (must include `horizon`, `tp_r`, `sl`; may include
    `reference_cfg` and any `objective()` kwarg).
    """
    window_start, window_end = window

    def _objective_fn(params: Dict[str, float]) -> float:
        result = evaluate_config(cfg, params, lake_root, window_start, window_end, symbols, **kw)
        return result.score

    return _objective_fn
