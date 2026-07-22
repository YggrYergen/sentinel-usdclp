"""sentinel_engine.strategies.tk_bw2_live -- TK-BW v2 "fix2atr" LIVE target
adapter (2026-07-22). A NEW additive module: turns a plain window of CLOSED
M5 bars (the shape the live executor's `fetch_bars` returns -- no M1
sub-bars, no still-forming bar; Task 2's dispatch is CLOSED-BARS-ONLY, not
intrabar) into the reconciler's `return_state` snapshot, by REPLAYING the
window through the REAL `tk_bw_v2.tk_bw_v2_run` engine (never reimplementing
the state machine) with the EXACT fix2atr params.

PARITY-BY-CONSTRUCTION
-----------------------
`bars_to_closed_only_steps` builds ONE step per closed bar: that bar is
simultaneously the step's `forming` (so the engine's intra-candle TP1 /
stop checks see its OHLC) with `is_close=True` and `price=bar["close"]`
(close-driven -- no intrabar peeking), and is appended to `closed` for the
NEXT step only (mirrors the runner's `build_steps` `is_close` contract: this
step's own `closed` list must NOT yet include this bar). This is exactly the
shape the live executor can build from `copy_rates_from_pos` closed bars
(no M1 granularity available/needed), and is proven byte-parity-equivalent
to a direct `tk_bw_v2_run(steps, return_state=True, **fix2atr_params)` call
over the SAME bars in `tests/live/test_tk_bw2_live.py`.

`tk_bw2_fix2atr_target(bars, **kwargs)` runs that replay and returns
{"open": {tag: {"side","entry","sl","max_fav"}}, "last_bar_exits": {},
"last_idx": n-1} -- up to 3 fichas (F1/F2/F3, TK-BW's shared-stop 3-ficha
ladder), each with a non-None `sl` (the OPEN-SL reconciler invariant).
Default kwargs are the EXACT fix2atr engine params (imported from the
research runner -- single source of truth, never re-typed here).

No MT5 import, no orders: this decides WHAT the desired state is; the
guarded executor (`scripts/live/run_live_20.py`) turns it into
(dry-run/armed) actions.
"""
from __future__ import annotations

from typing import Any

from .tk_bw_v2 import tk_bw_v2_run


def _fix2atr_defaults() -> dict[str, Any]:
    """The EXACT fix2atr engine params -- single source of truth: imported
    from the research runner (`scripts.research.run_tk_bw_v2_backtest`), not
    re-typed here. Imported lazily (inside the function) to avoid a module-
    load-order cycle (the runner imports registry/bars-loading modules this
    strategies package must stay independent of at import time)."""
    from scripts.research.run_tk_bw_v2_backtest import _COMMON_PARAMS, CONFIGS
    params = dict(_COMMON_PARAMS)
    params.update(CONFIGS["fix2atr"])
    return params


def bars_to_closed_only_steps(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the `tk_bw_v2_run` `steps` sequence from a flat list of CLOSED
    native bars (sim dict shape {t,open,high,low,close}), ONE step per bar:
    step i's `closed` = bars[:i] (bars strictly BEFORE i -- i itself is not
    in `closed` yet, matching the runner's `is_close` contract), `forming` =
    bars[i], `price` = bars[i]["close"], `is_close` = True."""
    steps: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    for bar in bars:
        steps.append({
            "ts": bar["t"],
            "closed": list(closed),
            "forming": dict(bar),
            "price": bar["close"],
            "is_close": True,
        })
        closed.append(bar)
    return steps


_SIDE_TO_RECONCILER = {"LONG": "L", "SHORT": "S"}


def tk_bw2_fix2atr_target(bars: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Replay `bars` (CLOSED M5 bars) through the REAL v2 engine with the
    fix2atr params (overridable via `kwargs`, defaulting to the exact
    research-runner fix2atr config) and return the reconciler snapshot for
    the currently-open position(s).

    Returns {"open": {"F1"|"F2"|"F3": {"side","entry","sl","max_fav"}} | {},
    "last_bar_exits": {}, "last_idx": n-1}. Every emitted ficha carries a
    non-None `sl` (TK-BW v2 always initializes/tracks a stop the instant a
    position opens -- see `_open_position`). `side` is normalized from the
    engine's native "LONG"/"SHORT" to the reconciler's "L"/"S" convention
    (the SAME convention `tk_momentum_5_8_target` / `supertrend_always_in_
    target` already emit -- `sentinel_engine.live.reconciler` compares this
    field directly against a live position's normalized side).

    COST WARNING: `tk_bw_v2_run` recomputes every indicator series over the
    ENTIRE `closed` bar list on every step, so this replay is O(n^2) in
    `len(bars)` (measured: 500 bars -> 1.6s, 2000 bars -> 17.7s). Callers on
    a tight poll budget (e.g. `scripts/live/run_live_20.py`) MUST cap the
    bar tail they pass in -- do not feed it a full multi-thousand-bar
    `--window` directly."""
    n = len(bars)
    if n == 0:
        return {"open": {}, "last_bar_exits": {}, "last_idx": -1}

    params = _fix2atr_defaults()
    params.update(kwargs)

    steps = bars_to_closed_only_steps(bars)
    _trades, snapshot = tk_bw_v2_run(steps, return_state=True, **params)
    open_state = {
        tag: {**d, "side": _SIDE_TO_RECONCILER.get(d["side"], d["side"])}
        for tag, d in snapshot["open"].items()
    }
    return {**snapshot, "open": open_state}
