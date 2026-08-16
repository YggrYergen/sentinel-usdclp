r"""scripts/analysis/realtick_bt/sizing.py -- WP-4: per-position sizing hook +
account-level aggregate state. Sirve a P-13..P-18
(research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md,
WP-4). Self-contained: no import from `emasar_ref.py`/`emasar_variant.py`.

The engine (`scripts/analysis/realtick_bt/backtest.py`) has no per-position
sizing mechanism today -- `metrics()`/`peak_margin()` scale every row by ONE
global `lot`. This module computes a per-position lot MULTIPLIER (never
touching `net1`/`margin1`, which stay per-1.0-lot as always) from account-level
state that does not exist in the engine today:

  - equity peak / current drawdown (running cumulative `net1` across ALL
    resolved positions of ALL strategies -- a proxy equity curve; `net1` is
    per-1.0-lot CLP so it is a consistent, comparable unit across the account);
  - rolling Sharpe per strategy over its last `sharpe_window` (default 50)
    CLOSED trades;
  - a per-server-day consecutive-loss counter (a DISCRETE event counter,
    distinct from the continuous drawdown figure).

`apply_sizing(resolved, cfg)` reconstructs this state by walking every
resolved position of every strategy in ONE explicit, deterministic
chronological order (`sorted` by `(t_exit, t_in_exec, sid, ficha,
original_flat_index)` -- never Python dict/list iteration order, which is an
implementation detail of `build_all()`'s internal dict, not a guarantee).
Given the SAME `resolved` input, `apply_sizing` ALWAYS produces the SAME
output, regardless of what order `resolved`'s dict keys or its per-strategy
lists happen to be in when this function is called (see
`test_sizing.py::test_apply_sizing_is_independent_of_dict_iteration_order`).

`cfg=None` (the default the caller must pass explicitly to opt in) returns
`resolved` UNCHANGED (same object, no copy) -- this is the byte-identical,
off-by-default path. `apply_sizing(resolved, SizingConfig())` (every knob at
its neutral default) attaches `lot_mult=1.0` to every position and changes
NOTHING else -- combined with `lot_fn(base_lot)` fed into
`backtest.peak_margin`/`backtest.metrics`'s new `lot_fn` kwarg, this reproduces
today's numbers exactly (WP-4 acceptance: "con multiplicador fijo en 1.0,
resultado byte-identico al de hoy").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass
class SizingConfig:
    # Fractional Kelly (P-13): kelly_mult in [0.25, 0.5] per spec, applied to
    # f* = win_rate - (1-win_rate)/payoff_ratio, estimated from the
    # strategy's own rolling trade history (state.trade_returns[sid]).
    kelly_mult: float | None = None
    kelly_payoff_default: float = 1.0
    kelly_clip: tuple[float, float] = (0.0, 1.0)

    # Inverse-ATR constant-volatility target (P-14). Needs a per-position ATR
    # value the caller supplies via `atr_fn` (this module never computes ATR
    # itself -- ATR-at-entry lives with whoever owns the bar/indicator axis
    # for the position, keeping this module decoupled from `bars`).
    atr_target: float | None = None
    atr_clip: tuple[float, float] = (0.25, 4.0)

    # Current drawdown band (P-15/16): list of (dd_pct_upper_bound, factor),
    # sorted ascending by threshold. First band whose threshold >= current
    # drawdown-% wins; if none matches, the LAST band's factor applies
    # (worst-case / deepest band).
    dd_bands: list[tuple[float, float]] | None = None

    # Ficha index (P-17): S6 trades F1/F2/F3 per signal; per-ficha factor.
    ficha_factors: dict[str, float] | None = None

    # Rolling Sharpe over the last N closed trades, per strategy (P-18).
    sharpe_window: int = 50
    sharpe_floor: float | None = None
    sharpe_floor_factor: float = 0.5

    # Per-day consecutive-loss counter (discrete event, distinct from
    # drawdown) -- throttle once >= cutoff losses hit today.
    loss_streak_cutoff: int | None = None
    loss_streak_factor: float = 0.0

    # Correlation discount: S6/S7/ST share 60-77% of their signals: discount
    # per EXTRA strategy concurrently open at this position's entry (n=1 -> no
    # discount).
    correlation_discount_per_extra: float = 0.0

    clip: tuple[float, float] = (0.0, 3.0)


@dataclass
class AccountState:
    equity: float = 0.0
    equity_peak: float = 0.0
    trade_returns: dict[str, list[float]] = field(default_factory=dict)
    current_day: str | None = None
    consecutive_losses_today: int = 0

    @property
    def drawdown_pct(self) -> float:
        if self.equity_peak <= 0:
            return 0.0
        return max(0.0, self.equity_peak - self.equity) / self.equity_peak * 100.0


def rolling_sharpe(returns: list[float]) -> float | None:
    """Mean/stdev of the (unweighted) trade-return sample. `None` when there
    are fewer than 2 samples or the sample is degenerate (zero variance) --
    a Sharpe figure is not meaningful in either case."""
    n = len(returns)
    if n < 2:
        return None
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    if var <= 0:
        return None
    sd = var ** 0.5
    return mean / sd


def _server_day(t: float) -> str:
    # Server wall clock, zero-offset trick -- see backtest.py's CLOCK
    # CONVENTION docstring. No timezone conversion, per spec Section 4.
    d = datetime.utcfromtimestamp(t)
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def kelly_factor(state: AccountState, sid: str, cfg: SizingConfig) -> float:
    returns = state.trade_returns.get(sid, [])
    if not returns:
        win_rate, payoff = 0.5, cfg.kelly_payoff_default
    else:
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]
        win_rate = len(wins) / len(returns)
        avg_win = (sum(wins) / len(wins)) if wins else 0.0
        avg_loss = (-sum(losses) / len(losses)) if losses else 0.0
        payoff = (avg_win / avg_loss) if avg_loss > 0 else cfg.kelly_payoff_default
    if payoff <= 0:
        payoff = cfg.kelly_payoff_default
    f_star = win_rate - (1.0 - win_rate) / payoff
    lo, hi = cfg.kelly_clip
    f_star = max(lo, min(hi, f_star))
    assert cfg.kelly_mult is not None
    return cfg.kelly_mult * f_star


def _dd_band_factor(dd_pct: float, bands: list[tuple[float, float]]) -> float:
    for threshold, factor in bands:
        if dd_pct <= threshold:
            return factor
    return bands[-1][1]


def _concurrency_at_open(items: list[tuple[str, dict[str, Any]]]) -> dict[int, int]:
    """For each position, the number of DISTINCT strategy ids with at least
    one open position at the moment this one opens (including itself). Pure
    event sweep, explicit deterministic sort -- opens before closes at the
    same instant (mirrors `backtest.peak_margin`'s tie-break)."""
    events = []
    for sid, pos in items:
        events.append((pos["t_in_exec"], 0, sid, id(pos)))
        events.append((pos["t_exit"], 1, sid, id(pos)))
    events.sort(key=lambda e: (e[0], e[1]))
    open_counts: dict[str, int] = {}
    result: dict[int, int] = {}
    for _, kind, sid, pid in events:
        if kind == 0:
            active = {s for s, c in open_counts.items() if c > 0}
            active.add(sid)
            result[pid] = len(active)
            open_counts[sid] = open_counts.get(sid, 0) + 1
        else:
            open_counts[sid] = open_counts.get(sid, 0) - 1
    return result


def lot_multiplier(pos: dict[str, Any], sid: str, state: AccountState, cfg: SizingConfig,
                    n_concurrent_sids: int, atr_fn: Callable[[dict[str, Any]], float | None] | None) -> float:
    mult = 1.0
    if cfg.kelly_mult is not None:
        mult *= kelly_factor(state, sid, cfg)
    if cfg.atr_target is not None and atr_fn is not None:
        atr_now = atr_fn(pos)
        if atr_now is not None and atr_now > 0:
            f = cfg.atr_target / atr_now
            lo, hi = cfg.atr_clip
            mult *= max(lo, min(hi, f))
    if cfg.dd_bands:
        mult *= _dd_band_factor(state.drawdown_pct, cfg.dd_bands)
    if cfg.ficha_factors:
        mult *= cfg.ficha_factors.get(pos.get("ficha"), 1.0)
    if cfg.sharpe_floor is not None:
        sh = rolling_sharpe(state.trade_returns.get(sid, []))
        if sh is not None and sh < cfg.sharpe_floor:
            mult *= cfg.sharpe_floor_factor
    if cfg.loss_streak_cutoff is not None and state.consecutive_losses_today >= cfg.loss_streak_cutoff:
        mult *= cfg.loss_streak_factor
    if cfg.correlation_discount_per_extra:
        n_extra = max(0, n_concurrent_sids - 1)
        mult *= 1.0 / (1.0 + cfg.correlation_discount_per_extra * n_extra)
    lo, hi = cfg.clip
    return max(lo, min(hi, mult))


def _roll_day(state: AccountState, pos: dict[str, Any]) -> None:
    """Advances the per-day consecutive-loss counter's day boundary BEFORE the
    sizing decision for `pos` is made -- the day a trade falls on is known in
    advance (its own `t_exit`), unlike its PnL, so this must NOT wait until
    after `lot_multiplier()` runs (that would size the first trade of a new
    day using yesterday's leftover streak)."""
    day = _server_day(pos["t_exit"])
    if state.current_day != day:
        state.current_day = day
        state.consecutive_losses_today = 0


def _update_account_state(state: AccountState, sid: str, pos: dict[str, Any], sharpe_window: int) -> None:
    ret = pos["net1"]
    state.equity += ret
    state.equity_peak = max(state.equity_peak, state.equity)
    lst = state.trade_returns.setdefault(sid, [])
    lst.append(ret)
    if len(lst) > sharpe_window:
        del lst[: len(lst) - sharpe_window]
    if ret < 0:
        state.consecutive_losses_today += 1
    else:
        state.consecutive_losses_today = 0


def apply_sizing(resolved: dict[str, list[dict[str, Any]]], cfg: SizingConfig | None, *,
                  atr_fn: Callable[[dict[str, Any]], float | None] | None = None
                  ) -> dict[str, list[dict[str, Any]]]:
    """`cfg=None` -> `resolved` returned UNCHANGED (byte-identical, off by
    default). Otherwise: every position gains a `lot_mult` key (existing keys
    untouched); output preserves each strategy's ORIGINAL per-sid order
    (unaffected by the internal chronological processing order used only to
    reconstruct account state)."""
    if cfg is None:
        return resolved
    flat: list[tuple[str, int, dict[str, Any]]] = []
    for sid, rows in resolved.items():
        for i, pos in enumerate(rows):
            flat.append((sid, i, pos))
    concurrency = _concurrency_at_open([(sid, pos) for sid, _, pos in flat])
    order = sorted(
        range(len(flat)),
        key=lambda k: (flat[k][2]["t_exit"], flat[k][2]["t_in_exec"], flat[k][0],
                        flat[k][2].get("ficha", ""), k),
    )
    state = AccountState()
    mult_by_flat_idx: dict[int, float] = {}
    for k in order:
        sid, _, pos = flat[k]
        _roll_day(state, pos)
        mult_by_flat_idx[k] = lot_multiplier(pos, sid, state, cfg, concurrency.get(id(pos), 1), atr_fn)
        _update_account_state(state, sid, pos, cfg.sharpe_window)
    out: dict[str, list[dict[str, Any]]] = {sid: [] for sid in resolved}
    for k, (sid, _, pos) in enumerate(flat):
        out[sid].append({**pos, "lot_mult": mult_by_flat_idx[k]})
    return out


def lot_fn(base_lot: float) -> Callable[[dict[str, Any]], float]:
    """Convenience adapter: `backtest.metrics(rows, base_lot, lot_fn=sizing.lot_fn(base_lot))`
    after `apply_sizing` has attached `lot_mult`. Positions without `lot_mult`
    (e.g. sizing never applied) fall back to `base_lot` unchanged."""
    return lambda r: base_lot * r.get("lot_mult", 1.0)
