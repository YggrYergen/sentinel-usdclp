"""tests/live/test_tk_bw2_live.py -- TK-BW2 fix2atr LIVE target adapter
(`sentinel_engine.strategies.tk_bw2_live.tk_bw2_fix2atr_target`).

The live executor only has CLOSED M5 bars (no M1 sub-bar granularity, no
still-forming bar -- Task 2's dispatch is closed-bars-only, NOT intrabar).
This adapter REPLAYS that bar window through the REAL v2 engine
(`tk_bw_v2.tk_bw_v2_run`, `return_state=True`) using the EXACT fix2atr engine
params, and emits the reconciler's `return_state` snapshot for the
currently-open position(s) -- up to 3 fichas (F1/F2/F3), each with a
non-None `sl`.

PARITY (mandatory, plan Task 1): building `steps` from a flat M5 bar list via
one-bar-per-step (each closed bar is simultaneously that step's `forming`
bar, `is_close=True`, then appended to `closed` for the next step -- the
live executor's exact shape, since it has no M1 data) and running it through
`tk_bw2_fix2atr_target` must produce the SAME sequence of opens/closes
(same entry/exit bar times, sides, per-ficha) as calling `tk_bw_v2_run`
directly over the identical steps with the identical fix2atr params.
"""
from __future__ import annotations

from sentinel_engine.strategies.tk_bw2_live import (
    bars_to_closed_only_steps,
    tk_bw2_fix2atr_target,
)
from sentinel_engine.strategies.tk_bw_v2 import tk_bw_v2_run
from scripts.research.run_tk_bw_v2_backtest import _COMMON_PARAMS, CONFIGS

from tests.strategies.test_tk_bw import T0, _bar, _long_entry_closed_bars

FIX2ATR_PARAMS = dict(_COMMON_PARAMS)
FIX2ATR_PARAMS.update(CONFIGS["fix2atr"])
# fix2atr forces allow_short=False in these fixtures (they're built for the
# natural LONG-entry setup only; parity is about the replay contract, not
# re-deriving a natural SHORT).
FIX2ATR_PARAMS["allow_short"] = False


def _long_entry_bars():
    """`_long_entry_closed_bars()` (40 mildly-declining + 1 spike-up native
    candle) PLUS the entry-triggering bar `test_tk_bw._open_long_steps` uses
    as its `forming` step (close=98.50, inside (last_bear_high, ema8_closed)
    -- breakout + still-below-EMA8) -- as an ordinary CLOSED bar, so the
    closed-bars-only adapter can open the SAME LONG this fixture opens in
    the v1/v2 step-based tests."""
    closed = _long_entry_closed_bars()
    last_bear_high = closed[39]["high"]
    ema8_closed = 98.80277777777789
    forming_open = 98.20
    forming_price = 98.50
    assert last_bear_high < forming_price < ema8_closed
    entry_bar = _bar(T0 + 41 * 300, forming_open, forming_price + 0.01,
                     forming_open - 0.01, forming_price)
    return closed + [entry_bar]


# --------------------------------------------------------------------------
# bars_to_closed_only_steps: one-bar-per-step shape
# --------------------------------------------------------------------------
def test_bars_to_closed_only_steps_empty():
    assert bars_to_closed_only_steps([]) == []


def test_bars_to_closed_only_steps_shape():
    bars = _long_entry_closed_bars()[:3]
    steps = bars_to_closed_only_steps(bars)
    assert len(steps) == 3
    # step i: closed == bars[:i], forming == bars[i], is_close True, price==close
    assert steps[0]["closed"] == []
    assert steps[0]["forming"] == bars[0]
    assert steps[0]["price"] == bars[0]["close"]
    assert steps[0]["is_close"] is True
    assert steps[0]["ts"] == bars[0]["t"]
    assert steps[2]["closed"] == bars[:2]
    assert steps[2]["forming"] == bars[2]


# --------------------------------------------------------------------------
# structure / flat cases
# --------------------------------------------------------------------------
def test_empty_bars_is_flat():
    snap = tk_bw2_fix2atr_target([])
    assert snap["open"] == {}
    assert snap["last_bar_exits"] == {}
    assert snap["last_idx"] == -1


def test_warmup_only_bars_is_flat():
    # A handful of bars -- nowhere near enough for ATR14/EMA8/regime warmup.
    bars = _long_entry_closed_bars()[:5]
    snap = tk_bw2_fix2atr_target(bars)
    assert snap["open"] == {}


def test_snapshot_shape_is_reconciler_ready():
    bars = _long_entry_closed_bars()
    snap = tk_bw2_fix2atr_target(bars)
    assert set(snap) >= {"open", "last_bar_exits", "last_idx"}
    assert snap["last_bar_exits"] == {}
    assert snap["last_idx"] == len(bars) - 1


def test_open_fichas_have_non_none_sl():
    # The natural-uptrend fixture opens a LONG on the entry-triggering bar
    # under fix2atr params too (forced entry, same c1_tol/regime -- only
    # stops differ), and must actually be open here (non-empty check).
    bars = _long_entry_bars()
    snap = tk_bw2_fix2atr_target(bars)
    assert snap["open"], "fixture must actually open a position"
    for tag, d in snap["open"].items():
        assert d["sl"] is not None, f"{tag} must always carry a non-None sl"
        assert d["side"] in ("L", "S")


# --------------------------------------------------------------------------
# PARITY (mandatory): adapter's replayed open/close sequence == tk_bw_v2_run
# --------------------------------------------------------------------------
def _extend_with_stopout(bars):
    """Append a sharp drop bar after the natural LONG entry so the position
    actually closes within the window (non-trivial trade sequence). The
    drop clears both the fixed 1.5xATR14 initial SL AND any BE/trail level
    comfortably (ATR14 on this fixture is a few USD; 100 is overkill on
    purpose so the test is not sensitive to the exact ATR value)."""
    last = bars[-1]
    drop_close = last["close"] - 100.0
    drop = _bar(last["t"] + 300, last["close"], last["close"] + 0.1,
                drop_close - 0.5, drop_close)
    return bars + [drop]


_SIDE_TO_RECONCILER = {"LONG": "L", "SHORT": "S"}


def _normalize_open(open_state):
    return {tag: {**d, "side": _SIDE_TO_RECONCILER.get(d["side"], d["side"])}
            for tag, d in open_state.items()}


def test_parity_adapter_matches_direct_engine_call_open_position():
    bars = _long_entry_bars()
    steps = bars_to_closed_only_steps(bars)
    direct_trades, direct_snap = tk_bw_v2_run(steps, return_state=True, **FIX2ATR_PARAMS)
    adapter_snap = tk_bw2_fix2atr_target(bars, **FIX2ATR_PARAMS)
    # side is normalized LONG/SHORT -> L/S by the adapter (reconciler
    # convention); everything else (entry/sl/max_fav per ficha) is identical.
    assert adapter_snap["open"] == _normalize_open(direct_snap["open"])
    assert adapter_snap["open"], "fixture must actually open a position"
    assert direct_trades == []  # still open at window end (parity precondition)


def test_parity_adapter_matches_direct_engine_call_after_stopout():
    bars = _extend_with_stopout(_long_entry_bars())
    steps = bars_to_closed_only_steps(bars)
    direct_trades, direct_snap = tk_bw_v2_run(steps, return_state=True, **FIX2ATR_PARAMS)
    adapter_snap = tk_bw2_fix2atr_target(bars, **FIX2ATR_PARAMS)
    assert adapter_snap["open"] == direct_snap["open"] == {}
    assert len(direct_trades) == 3  # all 3 fichas closed together (shared SL)
    by_ficha = {t["ficha"]: t for t in direct_trades}
    assert set(by_ficha) == {"F1", "F2", "F3"}


def test_default_kwargs_are_fix2atr():
    # Calling with NO kwargs must use the exact fix2atr params (single source
    # of truth import), not tk_bw_v2_run's bare defaults.
    bars = _long_entry_bars()
    default_call = tk_bw2_fix2atr_target(bars)
    explicit_call = tk_bw2_fix2atr_target(bars, **FIX2ATR_PARAMS)
    assert default_call == explicit_call
    assert default_call["open"], "fixture must actually open a position"


# --------------------------------------------------------------------------
# unit: SL always present, BE/trail progression moves SL monotonically
# --------------------------------------------------------------------------
def test_be_trail_progression_moves_sl_monotonically_toward_profit():
    bars = _long_entry_bars()
    snap_at_entry = tk_bw2_fix2atr_target(bars)
    assert snap_at_entry["open"], "fixture must actually open a position"
    sl_entry = snap_at_entry["open"]["F1"]["sl"]

    # push price up hard (well past BE + trail arming for ATR-based stops).
    # low stays comfortably ABOVE the entry SL (not just above `open`, which
    # is close to it) so the SL-first check never crosses the still-live
    # entry SL on the way up.
    last = bars[-1]
    peak_close = last["close"] + 40.0
    peak_open = last["close"]
    peak_low = sl_entry + 0.5
    peak_bar = _bar(last["t"] + 300, peak_open, peak_close + 0.5,
                    peak_low, peak_close)
    bars_peak = bars + [peak_bar]
    snap_peak = tk_bw2_fix2atr_target(bars_peak)
    assert snap_peak["open"], "peak bar must not have stopped the position out"
    sl_peak = snap_peak["open"]["F1"]["sl"]

    assert sl_peak > sl_entry, "LONG SL must ratchet UP (toward profit) as price rises"

    # push further still -- SL must never loosen back down.
    peak2_close = peak_close + 10.0
    peak2_open = peak_close
    peak2_low = sl_peak + 0.5
    peak2_bar = _bar(peak_bar["t"] + 300, peak2_open, peak2_close + 0.5,
                     peak2_low, peak2_close)
    bars_peak2 = bars_peak + [peak2_bar]
    snap_peak2 = tk_bw2_fix2atr_target(bars_peak2)
    assert snap_peak2["open"], "second peak bar must not have stopped the position out"
    sl_peak2 = snap_peak2["open"]["F1"]["sl"]
    assert sl_peak2 >= sl_peak, "trailing SL must be monotonic, never loosen"
