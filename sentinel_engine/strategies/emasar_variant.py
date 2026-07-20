"""sentinel_engine.strategies.emasar_variant -- EMASAR V1 with PER-FICHA
trailing (SENTINEL experiment 2026-07-13, trader request).

WHY THIS EXISTS
---------------
The frozen reference engine `emasar_ref.simular` can only trail F3; F1 exits
by bearish/bullish engulfing and F2 by SuperTrend flip. The trader asked for a
variant where EACH ficha (F1/F2/F3) trails with its OWN distance (a "trailing
ladder"), plus two entry tweaks (faster EMAs 5/8 and dropping the EMA-order
gate G1). To honour the "DO NOT EDIT the vendored frozen file" rule (see
`emasar_ref.py` header + golden test `tests/strategies/test_emasar_ref.py`),
this module does NOT touch `emasar_ref`; it IMPORTS its validated indicator +
gate math and only reimplements the position-management loop.

ENTRY PARITY: the entry decision calls the SAME `gate_long`/`gate_short` from
`emasar_ref` with the same parameters, so given identical params entries match
the reference engine exactly. Only the EXITS differ (all trailing, no
engulfing / no SuperTrend flip).

SCOPE: V1 only (3 fichas F1/F2/F3), close-entry (entry_timing=0), shared
initial range-SL (the "legal" stop). This is intentionally a focused
experiment simulator, not a general re-implementation of every Fase-1 branch.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .emasar_ref import (
    ema_series,
    sar_series,
    ao_series,
    ac_series,
    ac_desacelerando,
    momentum_series,
    gate_long,
    gate_short,
    pip_size,
    _Ficha,
    _toque_long,
    _toque_short,
    _atr_wilder,
)


def _gate_g1_g4_only(ema_f, ema_s, sar_trend, i: int, lado: int) -> bool:
    """G1 (EMA order, always required here)+G2 (same-slope, no cruzadas)+G4
    (SAR trend) ONLY -- direct evaluation, copied verbatim from
    `emasar_ref.gate_long`/`gate_short`'s own G1/G2/G4 formulas (G3 pullback
    is evaluated separately by the caller; G5 oscillator confirmation is
    DELIBERATELY omitted -- this is the 'full-gate re-entry, G5-bypassed'
    building block for V-13; see `simular_variant`'s re-entry docstring for
    why no clean bypass exists via the frozen gate_long/gate_short callables
    themselves). lado: +1 long, -1 short."""
    if i < 2:
        return False
    e8, e8p = ema_f[i], ema_f[i - 1]
    e20, e20p = ema_s[i], ema_s[i - 1]
    if None in (e8, e8p, e20, e20p) or sar_trend[i] is None:
        return False
    slope8 = e8 - e8p
    slope20 = e20 - e20p
    cruzadas = (slope8 > 0 and slope20 < 0) or (slope8 < 0 and slope20 > 0)
    if lado == +1:
        g1 = e8 > e20
        g2 = (slope8 > 0 and slope20 > 0) and not cruzadas
        g4 = sar_trend[i] == +1
    else:
        g1 = e8 < e20
        g2 = (slope8 < 0 and slope20 < 0) and not cruzadas
        g4 = sar_trend[i] == -1
    return g1 and g2 and g4


def _gate_g3_only(bars, ema_pull, i: int, lado: int) -> bool:
    """G3 (pullback), copied verbatim from `emasar_ref.gate_long`/`gate_short`'s
    own G3 formula (skip_g3=False path). lado: +1 long, -1 short."""
    if ema_pull[i] is None:
        return False
    bar1 = bars[i]
    if lado == +1:
        return (bar1["low"] < ema_pull[i]) and (bar1["close"] > bar1["open"])
    return (bar1["high"] > ema_pull[i]) and (bar1["close"] < bar1["open"])


def simular_variant(
    bars: list[dict[str, Any]],
    *,
    confirm_mode: int = 2,
    symbol: str = "XAUUSD",
    pipsize_input: float = 0.0,
    ema_fast: int = 5,
    ema_slow: int = 8,
    sar_step: float = 0.3,
    sar_max: float = 0.3,
    mom_period: int = 14,
    confirm_count: int = 2,
    require_ema_order: bool = False,
    init_sl_range_k: float = 1.0,
    f1_trail_pips: float = 289.0,
    f2_trail_pips: float = 230.0,
    f3_trail_pips: float = 170.0,
    allow_long: bool = True,
    allow_short: bool = True,
    be_at_r: float = 0.0,
    be_offset_pips: float = 0.5,
    trail_mode_ladder: str = "pips",
    f1_trail_range_k: float = 2.0,
    f2_trail_range_k: float = 3.0,
    f3_trail_range_k: float = 4.0,
    f1_tp_r: float = 0.0,
    f2_tp_r: float = 0.0,
    ac_modulate: bool = False,
    ac_modulate_factor: float = 0.5,
    f3_ac_decel_exit: bool = False,
    f3_ac_decel_bars: int = 2,
    g5_mode: str = "ref",
    blocked_hours: frozenset[int] | None = None,
    entry_timing: int = 0,
    direction_mask: list[int] | None = None,
    reentry_enable: bool = False,
    reentry_max: int = 1,
    sar_adaptive: bool = False,
    sar_fast: tuple[float, float] = (0.3, 0.3),
    sar_slow: tuple[float, float] = (0.005, 0.05),
    vol_regime_window: int = 200,
    return_state: bool = False,
    live_fill_mode: bool = False,
    trail_atr_floor_k: float = 0.0,
    max_hold_bars: int | None = None,
    confirm_bar: bool = False,
    stop_and_reverse: bool = False,
    active_fichas: int = 3,
    pullback_limit: bool = False,
    tp_min_pips: float | None = None,
    ratchet_lock_frac: float = 0.0,
    ratchet_arm_r: float = 1.0,
    ratchet_atr_k: float = 0.0,
    wait_mae_atr_k: float = 0.0,
    wait_be_exit: bool = False,
    trail_arm_r: float = 0.0,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
    """Simulate EMASAR V1 with a per-ficha trailing ladder.

    Returns the same event shape as `emasar_ref.simular`:
    [{'idx', 'lado':'L'|'S', 'precio', 'motivo', 'ficha':'F1'|'F2'|'F3'|None}].
    motivo in {ENTRY_L, ENTRY_S, EXIT_INITSL, EXIT_TRAIL}.

    Entry: identical to `emasar_ref` V1 close-entry (gate_long/gate_short with
    use_ema5=False). `require_ema_order=False` drops G1 (EMA-order) leaving G2
    (same-slope). `ema_fast`/`ema_slow` feed the two EMAs (the pullback gate G3
    references the FAST EMA in V1).

    Exit: all three fichas share the initial range-SL
    (LONG sl = low[i] - k*(high[i]-low[i]); SHORT mirror). Then each ficha
    trails with ITS OWN distance (`f1/f2/f3_trail_pips` * pip, or, when
    `trail_mode_ladder='range'`, `fN_trail_range_k * (bar['high'] -
    bar['low'])` of the CURRENT bar -- same semantics as `emasar_ref`'s
    `trail_mode='range'`). An early stop-out at the untouched initial SL is
    tagged EXIT_INITSL; a stop-out after the trailing raised the stop is
    tagged EXIT_TRAIL. There is NO engulfing exit and NO SuperTrend flip exit
    in this variant.

    Breakeven (`be_at_r > 0`, default 0.0 = disabled = EXACT current
    behavior): per ficha, R = |entry - initial_SL|. Once the ficha's
    `max_fav` reaches `entry + be_at_r*R` (long; mirror short), its SL is
    raised to at least `entry + be_offset_pips*pip` (long; mirror short) --
    SL only ever tightens (never loosens vs. either the initial SL or the
    trailing SL); ordinary trailing continues to run on top of this floor.

    Staggered take-profit by R multiples (V-05; `f1_tp_r`/`f2_tp_r`, default
    0.0 = disabled = EXACT current behavior): per signal, R =
    |entry - initial_SL| (shared across fichas, computed at entry). Checked
    BEFORE the initial-SL and trailing checks each bar: for F1 (uses
    `f1_tp_r`) and F2 (uses `f2_tp_r`) only -- long closes the ficha at
    exactly `entry + fN_tp_r*R` when `bar['high'] >= entry + fN_tp_r*R`
    (mirror short with `bar['low']`), tagged motivo EXIT_TP. F3 never TPs
    (keeps trailing as today). CONSERVATIVE FILL ASSUMPTION: if both the TP
    level and the initial/trailing SL would be touched by the SAME bar, the
    SL is counted first (the SL check runs after this block returns without
    having closed the ficha only when the TP didn't trigger; when TP DOES
    trigger the ficha is closed immediately on this check and the SL checks
    below are skipped for it this bar -- but since this TP check runs before
    the SL checks in bar order, ties are effectively decided by evaluating
    SL-first: see the code, the TP check for a ficha is skipped when its SL
    would already be hit this bar, so SL wins on same-bar collisions).

    AC-modulated trailing (V-06; `ac_modulate`, default False = disabled =
    EXACT current behavior): the module already computes `ac = ac_series(...)`.
    When `ac_modulate` is True and AC is decelerating against a ficha's
    favorable direction on the current bar (`ac_desacelerando`, same
    semantics as `emasar_ref`'s `ac_modulate_trail`), that ficha's effective
    trailing distance for the bar is multiplied by `ac_modulate_factor`
    (tighter stop). Applies to the whole per-ficha ladder (F1/F2/F3), unlike
    `emasar_ref`'s `ac_modulate_trail` which only ever applied to F3.

    Runner exit on sustained AC deceleration (V-07; `f3_ac_decel_exit`,
    default False = disabled = EXACT current behavior): F3 only. Each bar, if
    AC decelerates against the F3 position (same `ac_desacelerando` test as
    V-06) a per-ficha consecutive-bar counter increments; any other bar
    resets it to 0. When the counter reaches `f3_ac_decel_bars`, F3 is closed
    at that bar's CLOSE price, tagged motivo EXIT_ACDECEL. Checked AFTER the
    SL/trailing checks each bar (stop-outs take precedence on the same bar).

    AC "rojo->verde" transition entry gate (V-08; `g5_mode`, default 'ref' =
    EXACT current behavior): when `g5_mode='ac4_transition'`, an ADDITIONAL
    requirement is imposed on top of the existing `gate_long`/`gate_short`
    result: the signal bar's AC series must show an upturn transition --
    long: `ac[i] > ac[i-1] and ac[i-1] <= ac[i-2]` (short mirrors:
    `ac[i] < ac[i-1] and ac[i-1] >= ac[i-2]`); all three AC values must be
    non-None, else the signal is rejected. `g5_mode='ref'` skips this check
    entirely (identical to pre-V-08 behavior).

    Session/hour entry filter (V-11; `blocked_hours`, default None =
    disabled = EXACT current behavior): a `frozenset[int]` of UTC hours
    (0-23, from the signal bar's `t` epoch field). When the signal bar's
    hour is in `blocked_hours`, entry evaluation is skipped entirely for
    that bar (no gate call, no entry event) -- exits of already-open fichas
    are UNAFFECTED. Requires bars to carry a `t` (epoch seconds) field when
    `blocked_hours` is not None; bars without `t` raise if a blocked hour
    check is attempted (mirrors how the research harness already threads
    `t` through every bar dict).

    Intrabar entry + timing (V-12; `entry_timing`, default 0 = close-entry =
    EXACT current behavior): `entry_timing=1` mirrors `emasar_ref.simular`'s
    `entry_timing=1` EXACTLY for this ladder engine -- G3 (the pullback gate)
    is replaced by an intrabar touch approximation (`_toque_long`/
    `_toque_short`: long fires as soon as `bar['low'] <= ema_pull[i]`, at
    entry price = that EMA level; short mirrors with `bar['high'] >=
    ema_pull[i]`), and the REST of the gate (G1/G2/G4/G5, plus this batch's
    G5-mode/hour-filter extensions) is evaluated on the same bar `i` with
    `skip_g3=True`. `ema_pull` is `ema_f` (the "ema8" gate arg) in this V1
    ladder engine, same as `emasar_ref`'s V1 (`use_ema5=False`).

    Causal next-open entry (V-12 look-ahead audit, 2026-07-13; `entry_timing=
    2`, additive): gates evaluated on bar i's CLOSE exactly like
    `entry_timing=0` (no G3 replacement), but the fill only executes at bar
    i+1's OPEN -- the earliest price a strictly-causal system could act on a
    close-i signal. No entry if bar i is the last bar (no i+1 to fill at).
    Initial SL still uses the SIGNAL bar i's range (unchanged).

    Adverse-fill worst-case bound (V-12 look-ahead audit, 2026-07-13;
    `entry_timing=3`, additive): same signal bar and gate structure as
    `entry_timing=1` (G3 replaced by the intrabar touch test, skip_g3=True),
    but the FILL PRICE is forced to the worst price of the signal bar for the
    side (bar `high` for long, bar `low` for short) instead of the touched
    EMA level -- a deliberately pessimistic bound on how bad a same-bar
    intrabar fill could realistically be.

    SuperTrend-M15 regime filter (V-10; `direction_mask`, default None =
    disabled = EXACT current behavior): an optional list, one entry per bar
    in `bars` (same length/index alignment), of `+1` (long-only allowed),
    `-1` (short-only allowed), or `0` (both allowed). Computed by the CALLER
    (the research harness resamples the loaded bars to M15, runs SuperTrend,
    and maps each bar's mask from the previous CLOSED M15 bar -- no
    look-ahead; see `scripts/report/gen_variant_batch5.py::compute_direction_mask`).
    Checked in the entry block: a long signal is skipped if
    `direction_mask[i] == -1`; a short signal is skipped if
    `direction_mask[i] == +1`. `direction_mask=None` is a no-op (identical to
    pre-V-10 behavior); when a mask IS given, `mask[i] is None` is treated the
    same as `0` (both allowed, e.g. warmup bars with no SuperTrend value yet).

    Controlled re-entry after full trail-out (V-13; `reentry_enable`,
    default False = disabled = EXACT current behavior): when ALL 3 fichas of
    a signal have closed and EVERY exit motivo for that signal was
    EXIT_TRAIL (none EXIT_INITSL/EXIT_TP/EXIT_ACDECEL), a re-entry is ARMED
    for that signal's direction. On each subsequent bar (while armed and the
    re-entry count for this signal is below `reentry_max`), IF (a)
    `sar_trend[i]` still equals the original signal's direction AND (b) the
    G3 pullback condition holds (`_gate_g3_only`, same formula as
    `emasar_ref.gate_long`/`gate_short`'s own G3) -- a NEW full 3-ficha
    position is entered (fresh legal-range stop from that bar, entry price =
    close, tagged ENTRY_L/ENTRY_S normally, `entry_timing` respected for the
    price/G3 mechanics). The arm is cancelled (no more re-entries for that
    lineage) if `sar_trend[i]` flips away from the original direction before
    a re-entry fires. This is 'FULL-GATE re-entry with the G5
    oscillator-confirmation vote BYPASSED' (G1/G2/G4 are still required, via
    `_gate_g1_g4_only`) -- deliberately not "G3-only" as a literal reading of
    'the G3 pullback condition holds' might suggest, because a bare G3 check
    with no trend/slope confirmation at all fires far too often to be a
    faithful reading of "the gate would fire" (see module-level rationale:
    `gate_long`/`gate_short` have no built-in G5 bypass parameter, and
    `emasar_ref.py` is frozen, so G1/G2/G3/G4 are evaluated directly here via
    formulas copied verbatim from that module's own gate functions -- see
    `_gate_g1_g4_only`/`_gate_g3_only` above). Since ordinary re-entry
    already happens for ANY new full-gate (G1-G5) signal once all fichas are
    flat, this relaxed (G5-bypassed) re-entry is the only lever that can fire
    on bars where the STRICT gate would have stayed closed -- that is the
    measurable difference this variant tests.

    Volatility-adaptive SAR (V-15; `sar_adaptive`, default False = disabled
    = EXACT current behavior): when True, TWO SAR series are computed --
    `sar_fast` (step, max) and `sar_slow` (step, max) -- and ATR(14) Wilder
    (`_atr_wilder`, same formula `emasar_ref.simular` uses for its own
    SuperTrend ATR) is computed over the bars. Per bar `i`, `regime[i]` =
    'fast' if `atr[i]` is not None AND the rolling median of the previous
    `vol_regime_window` bars' non-None ATR values (requiring at least
    `vol_regime_window // 2` non-None values in that lookback, else regime
    defaults to 'slow') is exceeded by `atr[i]`; otherwise 'slow'. The
    EFFECTIVE `sar_trend` used everywhere in the entry gate (G4, and V-13's
    re-entry SAR check) is `sar_trend_fast[i]` when `regime[i]=='fast'` else
    `sar_trend_slow[i]`. `sar_adaptive=False` skips all of this and uses the
    single `sar_step`/`sar_max` series exactly as before.

    Live-fill bound (2026-07-13; `live_fill_mode`, default False = disabled =
    EXACT current ("classic") behavior): mirrors the live executor's
    server-side SL semantics, which cannot raise a trailing stop and act on
    that SAME bar's own high (only knowable at that bar's close). When True:
      1. Intra-bar stop checks for bar i use the SL level AS OF THE END OF
         BAR i-1 (the "server-side order"): the initial range-SL (unchanged,
         known at entry) and the trailing level LAST SET at the close of bar
         i-1. If bar i's low (long; mirror short) touches that level, the
         ficha exits AT THAT LEVEL, motivo unchanged (EXIT_INITSL/EXIT_TRAIL).
      2. Trailing updates (max_fav from bar i's high, trail distance incl.
         ac_modulate using ac[i]) are still computed AT THE CLOSE of bar i,
         exactly as in classic mode, but the newly raised level only becomes
         the active server-side level from bar i+1 onward.
      3. SAME-BAR FALLBACK: if, after computing bar i's raised trailing SL,
         that new level is already violated by bar i's OWN close (long:
         close_i <= new_sl; short mirror) -- i.e. classic mode would have
         exited intrabar at the raised level but the live server-side SL
         (still at the i-1 level) was never touched -- the ficha is closed
         AT BAR i's CLOSE price, motivo EXIT_TRAIL, and the emitted event
         dict carries `"same_bar_fallback": True`.
    Everything else (entries at close, reentry, sar_adaptive, BE/TP/AC-decel
    when enabled, etc.) is unchanged. `live_fill_mode=False` reproduces the
    classic event stream byte-for-byte (no `same_bar_fallback` key is ever
    added to events in that mode). Under `live_fill_mode=True`, the
    `return_state` `open` snapshot reports each still-open ficha's SERVER-side
    SL (the level resting during the last bar, i.e. the i-1 level), not the
    classic look-ahead `f.sl` just raised from the last bar's own high -- so a
    live reconciler consuming the state does not chase a one-bar-ahead stop.

    ATR14 trail floor (`trail_atr_floor_k`, default 0.0 = disabled = EXACT
    current behavior, byte-identical no-op): when > 0.0, every ficha's
    effective per-bar trailing distance is raised to at least
    `trail_atr_floor_k * ATR14[i]` (Wilder ATR14, price units, None during the
    14-bar warmup -> no floor). Applied AFTER the range/pips ladder and any
    AC-modulate tightening, so it is the last word on the trail distance.

    Time-stop exit (P51; `max_hold_bars`, default None = disabled = EXACT
    current behavior, byte-identical no-op): when set to N (> 0), any ficha
    still open N bars after its ENTRY bar (bar-count: `i - entry_bar_idx >= N`)
    is closed at THAT bar's CLOSE price, motivo "time_stop". Per ficha. Checked
    AFTER the SL/trailing/AC-decel checks each bar, so a same-bar stop-out
    (EXIT_INITSL/EXIT_TP/EXIT_TRAIL/EXIT_ACDECEL) takes precedence -- the
    `continue` statements above already skip this ficha for the rest of the bar
    in that case. `_Ficha` is frozen (`__slots__`, vendored from `emasar_ref`),
    so the per-ficha entry bar index is tracked out-of-band in
    `entry_bar_by_tag`, set at every entry site (strict long/short + V-13
    re-entry) and 1:1 with `fichas` while a position is open. Honest under
    `live_fill_mode`: priced at the bar close (the honest fill for a
    close-of-bar exit), no new fill route invented. `max_hold_bars=None` (or a
    non-positive value) skips this block entirely.

    Confirmation-bar entry (P54; `confirm_bar`, default False = disabled =
    EXACT current behavior, byte-identical no-op): when True, a signal raised
    at bar `i` does NOT enter at `i`. It is held PENDING (function-local state,
    reset per run) for exactly ONE bar and enters at bar `i+1` ONLY if bar
    `i+1` confirms the direction beyond the signal bar's own extreme -- LONG
    confirmed iff `close[i+1] > high[i]` (the signal bar's high), SHORT iff
    `close[i+1] < low[i]` (the signal bar's low). If bar `i+1` does not confirm,
    the pending signal is DROPPED (no entry; a one-bar window only, no carry
    beyond i+1). The deferred entry is priced at the CONFIRMATION bar via the
    EXISTING entry fill path (for the default entry_timing=0 that is the
    confirmation bar's own close `px`) -- honest under `live_fill_mode`, no new
    fill route. The confirmation check is evaluated at the top of the entry
    section (before the strict-gate signal path), mirroring V-13's re-entry
    arm; a fresh signal on bar `i` overwrites any (already-dropped) prior
    pending. Pending state never crosses a run boundary (declared before the
    bar loop, alongside `reentry_armed`/`entry_bar_by_tag`). `confirm_bar=False`
    reproduces the classic event stream byte-for-byte.

    Stop-and-reverse (P55; `stop_and_reverse`, default False = disabled = EXACT
    current behavior). Today the `if fichas: continue` choke defers ALL entry
    evaluation -- including an opposite-direction signal -- while any ficha is
    open, so a net reverse can only ever happen on a LATER bar via the ordinary
    exit paths. When `stop_and_reverse=True`, at that choke the strict close-of-
    bar gates are evaluated for the current bar; if a signal in the OPPOSITE
    direction to the open position fires, ALL open fichas are closed at THIS
    bar's CLOSE (`px`, exit_reason `"reverse"`) and the guard is NOT taken, so
    control falls through into the normal entry section and the opposite
    direction OPENS on the SAME bar `i` via the existing entry/fill path (priced
    at `px` under the default entry_timing, honest under `live_fill_mode`, no
    new fill route). Same-direction signals while open keep the classic no-
    pyramiding deferral (the guard still `continue`s). Long and short are never
    held simultaneously. `stop_and_reverse=False` reproduces the classic event
    stream byte-for-byte.

    Ficha-count lever (P46 escalera; `active_fichas`, default 3 = EXACT current
    behavior, byte-identical no-op): the escalera "1-vs-2-vs-3 fichas" study
    needs to SIMULATE with fewer fichas, not post-hoc drop rows (the fichas
    share trail/BE/SL/reentry state, so dropping F2/F3 events is not equivalent
    to never opening them). When `active_fichas=N` (1 or 2), EVERY entry site
    (strict long, strict short, and V-13 re-entry) opens only fichas F1..FN
    (N=1 -> just F1; N=2 -> F1+F2) instead of the full F1/F2/F3 dict. The
    exit/trail/BE/SL/AC-decel/time-stop loops already iterate over whatever
    fichas are present (`for tag in list(fichas.keys())`, `trail_by_tag[tag]`,
    etc.), so the reduced ladder flows through with no other change: identical
    signals, identical per-ficha trail params for the fichas that exist, honest
    under `live_fill_mode` (no new fill route -- the surviving fichas price
    exactly as they would in the full ladder). `active_fichas=3` builds the
    classic full dict and is byte-identical to pre-change behavior. Values
    outside {1, 2, 3} raise ValueError.

    Fixed-pip minimum take-profit (Wave6 Family-A; `tp_min_pips`, default None
    = disabled = EXACT current behavior, byte-identical no-op; a non-positive
    value <= 0 is treated the same as None): the sim proxy for the live
    executor's "tightest legal TP" (`max(stops_level, spread)`). At each ficha's
    fill a FIXED take-profit target is armed at `entry + tp_min_pips*pip` (long)
    / `entry - tp_min_pips*pip` (short), for ALL fichas F1/F2/F3 -- distinct
    from the R-multiple `f1_tp_r`/`f2_tp_r` (V-05) which arm F1/F2 only. The
    target is fixed once armed (derived from the ficha's own `entry`, so it does
    NOT move as the trail runs). Ordinary per-ficha trailing continues on top;
    whichever level a bar touches first exits the ficha (tagged EXIT_TP for the
    fixed-TP hit). CONSERVATIVE same-bar fill: if a single bar would touch BOTH
    the fixed TP and the initial/trailing SL, the SL takes precedence (the ficha
    exits at the SL, NOT the TP) -- checked exactly like V-05: the TP fires only
    when this bar's active SL (`sl_check`, the server-side level under
    `live_fill_mode`) is NOT also hit. No new fill route invented (touch
    semantics as today, priced at the fixed TP level on a hit). Checked in the
    same per-ficha exit block as V-05, right after it, so both TP levels share
    the SL-first collision convention; `tp_min_pips=None`/<=0 skips the block
    entirely and reproduces the classic event stream byte-for-byte.

    F1 profit-ratchet / chandelier (PX-T1; `ratchet_lock_frac`/`ratchet_arm_r`/
    `ratchet_atr_k`, defaults `0.0`/`1.0`/`0.0` = disabled = EXACT current
    behavior, byte-identical no-op): a give-back-protection lever -- a RISING
    FLOOR that locks a fraction of the peak favourable excursion. Per ficha,
    once `peak_fav` (`f.max_fav`, the running max/min favourable price already
    tracked) has moved at least `ratchet_arm_r*R` in favour (R = |entry -
    initial_SL|), the ficha SL is raised to a FLOOR that only ever TIGHTENS
    (never lowering below the current SL / BE / trail):
      - fraction form (`ratchet_lock_frac > 0`):
        `floor = entry + ratchet_lock_frac*(peak_fav - entry)` (long; mirror
        short). Locks `ratchet_lock_frac` of the peak gain.
      - chandelier form (`ratchet_atr_k > 0`):
        `floor = peak_fav - ratchet_atr_k*ATR14[i]` (long; mirror short), using
        the SAME Wilder ATR14 (`_atr_wilder`, period 14) the engine already
        computes -- no new indicator.
    The two forms are MUTUALLY EXCLUSIVE: `ratchet_lock_frac > 0` AND
    `ratchet_atr_k > 0` raises ValueError. The floor is BELOW price and rises
    WITH the peak, so it NEVER caps the runner (no ceiling above price). Placed
    in the per-ficha exit block AFTER the break-even block, as one more
    max()-with-current-SL floor. Honest under `live_fill_mode`: the raised
    floor becomes active on the NEXT bar via the existing server-side-SL path
    (`server_sl_by_tag`), and a floor already violated by the current bar's own
    close uses the existing same-bar-fallback exit in the trailing block -- no
    new fill route, no look-ahead. All three defaults reproduce the classic
    event stream byte-for-byte.

    F3 bounded stop-and-wait (PX-T2; `wait_mae_atr_k`/`wait_be_exit`, defaults
    `0.0`/`False` = disabled = EXACT current behavior, byte-identical no-op): the
    whipsaw/B-core lever -- instead of dumping a ficha at the worst tick of a
    range-SL, tolerate a BOUNDED adverse excursion and prefer exiting at
    break-even-or-better once price recovers. Composed ENTIRELY from OHLC-honest
    primitives:
      - `wait_mae_atr_k > 0`: the initial protective stop is a WIDER, explicitly
        bounded max-adverse-excursion stop at `entry - wait_mae_atr_k*ATR14[i]`
        (long; mirror short), taken as the WIDER of {this, the existing range-SL}
        DISTANCES -- i.e. `min()` of the two SL LEVELS for a long (lower = wider)
        / `max()` for a short (higher = wider). CHOICE: max-distance, so the
        bounded MAE never TIGHTENS the legal stop, only ever widens it. Reuses
        the engine's existing Wilder ATR14 (`_atr_wilder`, period 14) -- no new
        indicator. During the 14-bar ATR warmup (`ATR14[i]` is None) the MAE stop
        is undefined, so the initial SL FALLS BACK to the range-SL alone.
      - MANDATORY BOUND (Constraint 2, INVIOLABLE martingale guard): `ValueError`
        if `wait_mae_atr_k > 0` and `max_hold_bars is None`. A price bound
        (`wait_mae_atr_k`) and a time bound (`max_hold_bars`, P51) are hard-
        required TOGETHER -- an unbounded hold is refused by the engine itself.
        `max_hold_bars` is reused as the time bound (no second time-bound kwarg).
      - `wait_be_exit = True` (only meaningful when `wait_mae_atr_k > 0`; inert
        otherwise, no error): the floor holds BE-or-better once the ficha is
        at/above entry -- it arms IMMEDIATELY when the trade is green (long:
        `f.max_fav >= entry`, and `f.max_fav` initializes at entry, so this is
        true as soon as price is at/above water; mirror short with min/<=). Raise
        the SL to the break-even floor (`entry + be_offset_pips*pip` long; mirror
        short) so the exit is at BE-or-better rather than chasing the wide stop
        back down. This is a FLOOR that ONLY TIGHTENS (exactly like the BE/ratchet
        blocks) -- it NEVER loosens an existing tighter stop, and NEVER caps the
        runner (it is below price, not a ceiling above it).
    CONSERVATIVE LOWER BOUND on OHLC: a single bar whose extreme touches BOTH the
    MAE bound AND the BE-recovery is resolved SL-FIRST (the stop-out is scored
    before the BE floor arms this bar), which UNDER-states the mechanism's upside
    -- documented as the honest pessimistic bound. Honest under `live_fill_mode`:
    the widened initial SL is known at entry (unchanged intrabar semantics), and
    the BE-recovery raise (computed from this bar's own high/low) becomes active
    on the NEXT bar via the existing server-side-SL path (`server_sl_by_tag`); a
    floor already violated by this bar's own close uses the existing trailing
    same-bar fallback -- no new fill route, no look-ahead. Both defaults reproduce
    the classic event stream byte-for-byte.

    F5 trail-start-delay (PX-T3; `trail_arm_r`, default `0.0` = the trail arms
    immediately = EXACT current behavior, byte-identical no-op): give the runner
    early room -- the per-ficha TRAILING raise (the pips/range-trail tightening,
    INCLUDING its ATR-floor term and AC-modulate) does not begin until the ficha
    has EARNED it. The trailing raise is GATED: it only starts tightening the SL
    once `f.max_fav` has reached `entry + trail_arm_r*R` (long; mirror short with
    `<=` and `entry - trail_arm_r*R`), where `R = |entry - initial_SL|` (the same
    `sl_inicial_by_tag` convention the ratchet arm uses). Before arming, ONLY the
    initial-SL protects the ficha (plus any OTHER armed floor -- BE, ratchet,
    wait-BE -- which have their OWN arming conditions; this gate applies to the
    TRAILING block ALONE and never suppresses those floors). The gate changes
    WHEN the trail begins raising, NOT how a raise propagates: `f.max_fav` is
    still updated from this bar's high/low every bar (monotone -- once armed,
    stays armed, no disarm), the exit checks against the current SL still run, and
    a stop ALREADY raised by BE/ratchet/wait-BE stays raised (stops never loosen).
    NEVER caps the runner -- this lever only DELAYS tightening, it never widens an
    already-raised stop. Default `0.0` means `max_fav >= entry` is true from entry
    (R>=0), so the trail arms on the very first bar exactly as today -- the raise
    proceeds unconditionally, reproducing the classic event stream byte-for-byte
    in BOTH live_fill_mode values and with return_state on/off. Honest under
    `live_fill_mode` exactly as today (server-side next-bar discipline and the
    same-bar fallback in the trailing block are untouched; when unarmed no raise
    is computed, so neither the server-side raise nor the same-bar fallback fires
    for that ficha this bar).
    """
    if active_fichas not in (1, 2, 3):
        raise ValueError(
            f"active_fichas must be 1, 2 or 3, got {active_fichas!r}")
    # V-12 causal cousin (P33): the strictly-causal resting pullback-LIMIT lever
    # operates ONLY from the classic close-entry signal path (entry_timing==0)
    # and does not compose with the other deferred-entry mechanics. Reject the
    # out-of-scope combos loudly rather than silently mutate those paths.
    if pullback_limit:
        if entry_timing != 0:
            raise ValueError(
                "pullback_limit requires entry_timing=0 (close-entry signal "
                f"path); got entry_timing={entry_timing!r}")
        if confirm_bar:
            raise ValueError(
                "pullback_limit does not compose with confirm_bar")
    # F1 profit-ratchet / chandelier (PX-T1): the two floor FORMS are mutually
    # exclusive -- fraction (`ratchet_lock_frac>0`) and chandelier
    # (`ratchet_atr_k>0`) cannot both be active in one config. Both defaulting
    # to 0.0 is the byte-identical no-op (block skipped entirely below).
    if ratchet_lock_frac > 0.0 and ratchet_atr_k > 0.0:
        raise ValueError(
            "ratchet_lock_frac and ratchet_atr_k are mutually exclusive "
            f"(fraction vs chandelier form); got lock_frac={ratchet_lock_frac!r}, "
            f"atr_k={ratchet_atr_k!r}")
    # F3 bounded stop-and-wait (PX-T2): the INVIOLABLE martingale guard
    # (Constraint 2). A positive `wait_mae_atr_k` (wider bounded-MAE price stop)
    # MUST be paired with a `max_hold_bars` (P51) time bound -- an unbounded hold
    # is refused by the engine itself. `wait_mae_atr_k` defaulting to 0.0 is the
    # byte-identical no-op (the wider stop / BE-exit blocks are skipped below);
    # `wait_be_exit` without `wait_mae_atr_k>0` is inert (no error).
    if wait_mae_atr_k > 0.0 and max_hold_bars is None:
        raise ValueError(
            "wait_mae_atr_k > 0 requires max_hold_bars (bounded waiting only: "
            "the price bound and the time bound are hard-required together); "
            f"got wait_mae_atr_k={wait_mae_atr_k!r}, max_hold_bars=None")
    n = len(bars)
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]

    ema_f = ema_series(closes, ema_fast)   # passed as the "ema8" gate arg
    ema_s = ema_series(closes, ema_slow)   # passed as the "ema20" gate arg
    ema5_unused = [None] * n               # V1 (use_ema5=False) ignores this
    ao = ao_series(highs, lows)
    ac = ac_series(highs, lows)
    mom = momentum_series(closes, mom_period)

    # Volatility-adaptive SAR (V-15; sar_adaptive=False disables this block
    # entirely -- sar_trend is then the single sar_step/sar_max series,
    # preserving current behavior byte-for-byte).
    if sar_adaptive:
        _sar_val_fast, sar_trend_fast = sar_series(highs, lows, sar_fast[0], sar_fast[1])
        _sar_val_slow, sar_trend_slow = sar_series(highs, lows, sar_slow[0], sar_slow[1])
        atr14 = _atr_wilder(highs, lows, closes, 14)
        sar_trend = [0] * n
        for i in range(n):
            regime_fast = False
            if atr14[i] is not None:
                lo = max(0, i - vol_regime_window)
                window_vals = [v for v in atr14[lo:i] if v is not None]
                if len(window_vals) >= max(1, vol_regime_window // 2):
                    sorted_vals = sorted(window_vals)
                    m = len(sorted_vals)
                    median = (sorted_vals[m // 2] if m % 2 == 1
                              else (sorted_vals[m // 2 - 1] + sorted_vals[m // 2]) / 2.0)
                    regime_fast = atr14[i] > median
            sar_trend[i] = sar_trend_fast[i] if regime_fast else sar_trend_slow[i]
    else:
        _sar_val, sar_trend = sar_series(highs, lows, sar_step, sar_max)

    pip = pip_size(symbol, pipsize_input)
    # ATR14 trail floor (trail_atr_floor_k>0.0): raise every ficha's effective
    # per-bar trail distance to at least `trail_atr_floor_k * ATR14[i]` (price
    # units, same as `trail_efectivo`). Computed here ONCE per bar (not per
    # ficha) with the same Wilder ATR14 the regime logic uses, and ONLY when
    # the floor is active -- so the default 0.0 is a byte-identical no-op with
    # no extra work. ATR14[i] is None during the 14-bar warmup -> no floor.
    # Shared Wilder ATR14 for the trail floor (trail_atr_floor_k), the F1
    # chandelier ratchet form (PX-T1; ratchet_atr_k), AND the F3 bounded-MAE
    # initial stop (PX-T2; wait_mae_atr_k). Computed ONCE, and ONLY when at least
    # one consumer is active, so the all-defaults path (every k==0.0) does no
    # extra work and stays a byte-identical no-op. ATR14[i] is None during the
    # 14-bar warmup -> the MAE stop falls back to the range-SL alone.
    atr14_floor = (_atr_wilder(highs, lows, closes, 14)
                   if (trail_atr_floor_k > 0.0 or ratchet_atr_k > 0.0
                       or wait_mae_atr_k > 0.0) else None)
    # Ficha-count lever (P46; active_fichas): the ORDERED tags opened at every
    # entry site. active_fichas=3 -> the classic full ("F1","F2","F3"), so the
    # entry-site dicts below are byte-identical to before. N=1/2 truncates to
    # F1..FN; the exit/trail loops iterate over whatever tags exist, so fewer
    # fichas flow through naturally with no other change.
    active_tags = ("F1", "F2", "F3")[:active_fichas]
    trail_by_tag = {
        "F1": f1_trail_pips * pip,
        "F2": f2_trail_pips * pip,
        "F3": f3_trail_pips * pip,
    }
    trail_range_by_tag = {
        "F1": f1_trail_range_k,
        "F2": f2_trail_range_k,
        "F3": f3_trail_range_k,
    }

    def _sl_inicial(lado: int, idx: int) -> float:
        rango = bars[idx]["high"] - bars[idx]["low"]
        return (bars[idx]["low"] - init_sl_range_k * rango) if lado == +1 \
            else (bars[idx]["high"] + init_sl_range_k * rango)

    def _sl_inicial_bounded(lado: int, idx: int, entry_px: float) -> float:
        """Initial SL for a fill at `entry_px` on bar `idx`. Default
        (`wait_mae_atr_k==0.0`) returns the plain range-SL `_sl_inicial`, so the
        no-op path is byte-identical. When `wait_mae_atr_k > 0` (PX-T2), the stop
        is the WIDER of {range-SL, `entry_px -/+ wait_mae_atr_k*ATR14[idx]`}
        DISTANCES -- i.e. the LOWER level for a long / HIGHER for a short (a
        wider, explicitly bounded max-adverse-excursion stop that never tightens
        the legal stop). During the ATR14 warmup (`atr14_floor[idx]` is None) the
        MAE stop is undefined, so this falls back to the range-SL alone."""
        base = _sl_inicial(lado, idx)
        if wait_mae_atr_k <= 0.0 or atr14_floor is None or atr14_floor[idx] is None:
            return base
        atr_dist = wait_mae_atr_k * atr14_floor[idx]
        if lado == +1:
            mae_sl = entry_px - atr_dist
            return min(base, mae_sl)   # wider (lower) of the two levels
        mae_sl = entry_px + atr_dist
        return max(base, mae_sl)       # wider (higher) of the two levels

    eventos: list[dict[str, Any]] = []
    fichas: dict[str, _Ficha] = {}
    # _Ficha uses __slots__ (vendored from emasar_ref, frozen -- cannot add
    # attributes), so the per-ficha initial SL used for the R distance in the
    # breakeven block is tracked out-of-band, keyed by tag (1:1 with `fichas`
    # while a position is open; reset on every new entry).
    sl_inicial_by_tag: dict[str, float] = {}
    # live_fill_mode: the SL level "as of the end of the PREVIOUS bar" (the
    # server-side order a live executor would actually have resting) --
    # keyed by tag, reset on every new entry to the fresh initial SL, and
    # advanced to `f.sl` at the END of each bar's processing (so bar i's
    # intrabar check always reads the i-1 snapshot). Unused (dead weight)
    # when live_fill_mode=False.
    server_sl_by_tag: dict[str, float] = {}
    # V-05: shared R = |entry - initial_SL| per signal (same for F1/F2/F3
    # since they share the same entry price + initial SL), keyed by tag.
    r_by_tag: dict[str, float] = {}
    tp_by_tag = {"F1": f1_tp_r, "F2": f2_tp_r}
    # V-07: consecutive-bar AC-deceleration-against-position counter, F3 only.
    ac_decel_consec_by_tag: dict[str, int] = {}
    # P51 (max_hold_bars): the ENTRY bar index per open ficha, keyed by tag and
    # reset on every new entry (1:1 with `fichas` while a position is open).
    # `_Ficha` is frozen (__slots__), so bars-held is derived from this
    # out-of-band index (`i - entry_bar_by_tag[tag]`). Dead weight when
    # max_hold_bars is None.
    entry_bar_by_tag: dict[str, int] = {}
    # V-13: exit-motivo bookkeeping for the CURRENTLY open signal (reset on
    # every new entry), used to detect "all 3 fichas closed, all EXIT_TRAIL"
    # at the moment the last ficha of a signal closes. Re-entry "arm" state
    # persists across bars once a signal fully trails out; cancelled on a
    # SAR-trend flip or after `reentry_max` re-entries for that lineage.
    signal_exit_motivos: list[str] = []
    reentry_armed = False
    reentry_lado = 0
    reentry_count = 0
    # P54 (confirm_bar): one-bar-deferred pending signal. When confirm_bar is
    # True, a strict-gate signal on bar i is NOT entered at i -- it is held here
    # (side + the signal bar's extreme) and, at bar i+1, entered only if i+1's
    # close confirms beyond that extreme; otherwise dropped (one-bar window).
    # Function-local, reset per run; dead weight when confirm_bar=False.
    pending_confirm_lado = 0        # +1 long / -1 short / 0 none pending
    pending_confirm_high = 0.0      # signal bar's high (long confirm reference)
    pending_confirm_low = 0.0       # signal bar's low (short confirm reference)
    # P33 pullback-LIMIT state (V-12 causal cousin): a signal at bar i places a
    # resting LIMIT at ema_f[i] for bar i+1 ONLY. side=+1 BUY LIMIT (fill iff
    # bars[i+1].low<=level) / -1 SELL LIMIT (fill iff bars[i+1].high>=level);
    # next-bar expiry (never carried past i+1). Dead weight when
    # pullback_limit=False. Function-local, reset per run.
    pending_limit_lado = 0          # +1 long / -1 short / 0 none resting
    pending_limit_level = 0.0       # the LIMIT price = ema_f[signal bar]
    # live_fill_mode + return_state: the SERVER-side SL a broker is actually
    # RESTING with DURING the currently-processing bar (the i-1 level, before
    # this bar's own high/AC raises f.sl). Captured at the START of each bar so
    # that after the loop it holds the level resting during the LAST bar -- the
    # honest value the reconciler must consume (the end-of-bar advance at the
    # bottom of the loop otherwise pushes `server_sl_by_tag` up to the raised
    # `f.sl`, which is a one-bar-ahead look-ahead). Dead weight otherwise.
    server_sl_during_bar: dict[str, float] = {}

    for i in range(n):
        bar = bars[i]
        px = bar["close"]
        _n_eventos_before_exits = len(eventos)
        if live_fill_mode and return_state:
            server_sl_during_bar = {
                tag: server_sl_by_tag.get(tag, f.sl)
                for tag, f in fichas.items() if f.abierta
            }

        # ---- 1) exits for open fichas (each trails with its own distance) ----
        for tag in list(fichas.keys()):
            f = fichas[tag]
            if not f.abierta:
                continue
            lado_txt = "L" if f.lado == +1 else "S"

            # Staggered take-profit by R multiples (V-05; f1_tp_r/f2_tp_r,
            # F1/F2 only -- F3 never TPs). Checked FIRST, but only fires when
            # this bar's SL (initial or trailing, whichever is currently
            # active) is NOT also hit -- i.e. on a same-bar TP+SL collision,
            # the SL wins (conservative fill assumption; see docstring).
            # live_fill_mode: intrabar checks use the SERVER-SIDE SL (the
            # level as of the end of bar i-1) instead of `f.sl` (which, in
            # classic mode, may already reflect a raise computed from THIS
            # bar's own high -- knowable only at close, not intrabar live).
            sl_check = server_sl_by_tag.get(tag, f.sl) if live_fill_mode else f.sl

            tp_r = tp_by_tag.get(tag, 0.0)
            if tp_r > 0.0:
                sl_hit_this_bar = (
                    (f.lado == +1 and bar["low"] <= sl_check)
                    or (f.lado == -1 and bar["high"] >= sl_check)
                )
                if not sl_hit_this_bar:
                    r_dist = r_by_tag.get(tag, 0.0)
                    if r_dist > 0.0:
                        if f.lado == +1:
                            tp_price = f.entry + tp_r * r_dist
                            if bar["high"] >= tp_price:
                                f.abierta = False
                                eventos.append({"idx": i, "lado": lado_txt, "precio": tp_price,
                                                "motivo": "EXIT_TP", "ficha": tag})
                                continue
                        else:
                            tp_price = f.entry - tp_r * r_dist
                            if bar["low"] <= tp_price:
                                f.abierta = False
                                eventos.append({"idx": i, "lado": lado_txt, "precio": tp_price,
                                                "motivo": "EXIT_TP", "ficha": tag})
                                continue

            # Fixed-pip minimum take-profit (Wave6 Family-A; tp_min_pips=None or
            # <=0 disables this block entirely -> byte-identical no-op). ALL
            # fichas (F1/F2/F3), distinct from V-05's R-multiple F1/F2-only TP.
            # Target is FIXED at entry (entry +/- tp_min_pips*pip, derived from
            # this ficha's own entry so it never moves). Same SL-first collision
            # convention as V-05: fire only when this bar's active SL (sl_check
            # -- the server-side level under live_fill_mode) is NOT also hit.
            if tp_min_pips is not None and tp_min_pips > 0.0:
                sl_hit_this_bar = (
                    (f.lado == +1 and bar["low"] <= sl_check)
                    or (f.lado == -1 and bar["high"] >= sl_check)
                )
                if not sl_hit_this_bar:
                    if f.lado == +1:
                        tp_min_price = f.entry + tp_min_pips * pip
                        if bar["high"] >= tp_min_price:
                            f.abierta = False
                            eventos.append({"idx": i, "lado": lado_txt, "precio": tp_min_price,
                                            "motivo": "EXIT_TP", "ficha": tag})
                            continue
                    else:
                        tp_min_price = f.entry - tp_min_pips * pip
                        if bar["low"] <= tp_min_price:
                            f.abierta = False
                            eventos.append({"idx": i, "lado": lado_txt, "precio": tp_min_price,
                                            "motivo": "EXIT_TP", "ficha": tag})
                            continue

            # Initial SL (still-untouched stop) -- checked before this bar's
            # trailing raise, so a same-bar hit here is tagged EXIT_INITSL.
            # live_fill_mode: exits AT the server-side level (`sl_check`),
            # which for a still-untouched stop equals `f.sl` anyway (the
            # initial SL never moves before the first trailing raise), so
            # the fill price is unchanged either way.
            if f.lado == +1 and bar["low"] <= sl_check:
                f.abierta = False
                eventos.append({"idx": i, "lado": lado_txt, "precio": sl_check,
                                "motivo": "EXIT_INITSL", "ficha": tag})
                continue
            if f.lado == -1 and bar["high"] >= sl_check:
                f.abierta = False
                eventos.append({"idx": i, "lado": lado_txt, "precio": sl_check,
                                "motivo": "EXIT_INITSL", "ficha": tag})
                continue

            # Breakeven-at-R (be_at_r=0.0 disables this block entirely,
            # preserving current behavior byte-for-byte): once max_fav has
            # reached entry +/- be_at_r*R, raise the SL to at least the BE
            # floor. SL only ever tightens (never loosens).
            if be_at_r > 0.0:
                r_dist = abs(f.entry - sl_inicial_by_tag[tag])
                if f.lado == +1:
                    f.max_fav = max(f.max_fav, bar["high"])
                    if r_dist > 0.0 and f.max_fav >= f.entry + be_at_r * r_dist:
                        be_floor = f.entry + be_offset_pips * pip
                        if f.sl is None or be_floor > f.sl:
                            f.sl = be_floor
                else:
                    f.max_fav = min(f.max_fav, bar["low"])
                    if r_dist > 0.0 and f.max_fav <= f.entry - be_at_r * r_dist:
                        be_floor = f.entry - be_offset_pips * pip
                        if f.sl is None or be_floor < f.sl:
                            f.sl = be_floor

                # Re-check: the BE-raised SL may already be hit intrabar.
                # live_fill_mode: BE is itself computed from THIS bar's
                # high/low (max_fav update above), so like trailing it is
                # only knowable at close live -- reuse `sl_check` (the prior
                # server-side level) for the intrabar test, not the
                # just-raised `f.sl`. be_at_r defaults to 0.0 (disabled) for
                # every config this task touches, so this path is inert
                # there; kept correct for completeness/parity.
                be_check = sl_check if live_fill_mode else f.sl
                if f.lado == +1 and bar["low"] <= be_check:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": be_check,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue
                if f.lado == -1 and bar["high"] >= be_check:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": be_check,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue

            # F1 profit-ratchet / chandelier rising floor (PX-T1; both
            # ratchet_lock_frac and ratchet_atr_k default 0.0 -> this block is
            # skipped ENTIRELY, byte-identical no-op). Placed AFTER the BE block
            # and treated as one more FLOOR that only ever TIGHTENS the SL --
            # same discipline as break-even/trailing raises, never lowering it.
            #   - Arm once peak_fav (f.max_fav, the running max/min favourable
            #     price the engine already tracks) has moved >= ratchet_arm_r*R
            #     in favour, R = |entry - initial_SL|.
            #   - fraction form (ratchet_lock_frac>0):
            #       floor = entry + lock_frac*(peak_fav - entry)   (long; mirror)
            #   - chandelier form (ratchet_atr_k>0):
            #       floor = peak_fav - atr_k*ATR14[i]              (long; mirror)
            #     (the two forms are mutually exclusive -- ValueError above).
            # The floor is BELOW price and rises WITH the peak, so it NEVER caps
            # the runner. Honest under live_fill_mode: the raise (like BE/trail)
            # is knowable only at this bar's close, so it becomes active on the
            # NEXT bar via server_sl_by_tag; a floor already violated by this
            # bar's own close is handled by the existing trailing same-bar
            # fallback below (no new fill route, no look-ahead).
            if ratchet_lock_frac > 0.0 or ratchet_atr_k > 0.0:
                r_dist = abs(f.entry - sl_inicial_by_tag[tag])
                if f.lado == +1:
                    f.max_fav = max(f.max_fav, bar["high"])
                    if r_dist > 0.0 and f.max_fav >= f.entry + ratchet_arm_r * r_dist:
                        if ratchet_lock_frac > 0.0:
                            ratchet_floor = f.entry + ratchet_lock_frac * (f.max_fav - f.entry)
                        elif atr14_floor is not None and atr14_floor[i] is not None:
                            ratchet_floor = f.max_fav - ratchet_atr_k * atr14_floor[i]
                        else:
                            ratchet_floor = None
                        if ratchet_floor is not None and (f.sl is None or ratchet_floor > f.sl):
                            f.sl = ratchet_floor
                else:
                    f.max_fav = min(f.max_fav, bar["low"])
                    if r_dist > 0.0 and f.max_fav <= f.entry - ratchet_arm_r * r_dist:
                        if ratchet_lock_frac > 0.0:
                            ratchet_floor = f.entry - ratchet_lock_frac * (f.entry - f.max_fav)
                        elif atr14_floor is not None and atr14_floor[i] is not None:
                            ratchet_floor = f.max_fav + ratchet_atr_k * atr14_floor[i]
                        else:
                            ratchet_floor = None
                        if ratchet_floor is not None and (f.sl is None or ratchet_floor < f.sl):
                            f.sl = ratchet_floor

                # Re-check: the ratchet-raised SL may already be hit intrabar.
                # live_fill_mode: the floor was computed from THIS bar's own
                # high/low (max_fav update above), so like BE/trailing it is
                # only knowable at close live -- use `sl_check` (the prior
                # server-side level) for the intrabar test, never the just-
                # raised f.sl; the same-bar fallback (below, in the trailing
                # block) then closes a floor violated by this bar's own close.
                ratchet_check = sl_check if live_fill_mode else f.sl
                if f.lado == +1 and bar["low"] <= ratchet_check:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": ratchet_check,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue
                if f.lado == -1 and bar["high"] >= ratchet_check:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": ratchet_check,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue

            # F3 bounded stop-and-wait BE-or-better floor (PX-T2; only armed when
            # BOTH wait_mae_atr_k>0 AND wait_be_exit=True -> this block is skipped
            # ENTIRELY otherwise, byte-identical no-op). Once the ficha is at/above
            # entry (long; mirror short) -- which, since f.max_fav initializes at
            # entry, is true as soon as the trade is green (arms immediately) --
            # raise the SL to the break-even floor
            # (entry + be_offset_pips*pip, long; mirror short) so the exit is at
            # BE-or-better instead of chasing the wide stop back down. One more
            # FLOOR that only ever TIGHTENS -- never loosening the current SL,
            # never a ceiling above price. Placed AFTER the ratchet block; the
            # same-bar MAE-stop hit is already resolved by the EXIT_INITSL /
            # EXIT_TRAIL checks ABOVE (SL-FIRST conservatism -- a bar that both
            # pierces the wide stop and recovers to BE exits at the stop, the
            # honest OHLC lower bound). Honest under live_fill_mode: the raise is
            # knowable only at this bar's close, so like BE/ratchet it becomes
            # active on the NEXT bar via server_sl_by_tag; a floor already
            # violated by this bar's own close is handled by the trailing same-
            # bar fallback below. `be_offset_pips` is shared with the be_at_r
            # break-even lever (same floor definition).
            if wait_mae_atr_k > 0.0 and wait_be_exit:
                if f.lado == +1:
                    f.max_fav = max(f.max_fav, bar["high"])
                    if f.max_fav >= f.entry:
                        be_floor = f.entry + be_offset_pips * pip
                        if f.sl is None or be_floor > f.sl:
                            f.sl = be_floor
                else:
                    f.max_fav = min(f.max_fav, bar["low"])
                    if f.max_fav <= f.entry:
                        be_floor = f.entry - be_offset_pips * pip
                        if f.sl is None or be_floor < f.sl:
                            f.sl = be_floor

                # Re-check: the BE-raised SL may already be hit intrabar.
                # live_fill_mode: BE is computed from THIS bar's high/low (the
                # max_fav update above), so like BE/ratchet/trailing it is only
                # knowable at close live -- use `sl_check` (the prior server-side
                # level) for the intrabar test, never the just-raised f.sl; the
                # trailing same-bar fallback (below) then closes a floor violated
                # by this bar's own close.
                wait_be_check = sl_check if live_fill_mode else f.sl
                if f.lado == +1 and bar["low"] <= wait_be_check:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": wait_be_check,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue
                if f.lado == -1 and bar["high"] >= wait_be_check:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": wait_be_check,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue

            # Per-ficha trailing: SL only tightens toward price; the range-SL
            # is the floor until the trailing overtakes it.
            if trail_mode_ladder == "range":
                trail_efectivo = trail_range_by_tag[tag] * (bar["high"] - bar["low"])
            else:
                trail_efectivo = trail_by_tag[tag]
            # AC-modulated trailing (V-06; ac_modulate=False disables this
            # block entirely, preserving current behavior byte-for-byte):
            # when AC is decelerating against this ficha's favorable
            # direction on the current bar, tighten the trail distance.
            if ac_modulate and ac_desacelerando(ac, i, f.lado):
                trail_efectivo = trail_efectivo * ac_modulate_factor
            # ATR14 trail floor (trail_atr_floor_k=0.0 default -> atr14_floor is
            # None -> this block is skipped entirely, byte-identical no-op).
            if atr14_floor is not None and atr14_floor[i] is not None:
                trail_efectivo = max(trail_efectivo,
                                     trail_atr_floor_k * atr14_floor[i])
            if f.lado == +1:
                f.max_fav = max(f.max_fav, bar["high"])
                # F5 trail-start-delay (PX-T3; trail_arm_r=0.0 default -> armed
                # is unconditionally True from entry, so the raise below runs
                # exactly as today = byte-identical no-op). Gate the TRAILING
                # RAISE ONLY: it may tighten f.sl only once max_fav has reached
                # entry + trail_arm_r*R (R = |entry - initial_SL|, the ratchet-
                # arm convention). Before arming, f.sl stays at whatever the
                # initial-SL / BE / ratchet / wait-BE floors set it to (those
                # floors keep their OWN arming conditions; this gate is trailing
                # -only). max_fav is still updated (monotone -> stays armed), the
                # exit checks below still fire, and a stop already raised stays
                # raised -- the lever only DELAYS tightening, never widens.
                r_dist_trail = abs(f.entry - sl_inicial_by_tag[tag])
                trail_armed = (trail_arm_r <= 0.0
                               or f.max_fav >= f.entry + trail_arm_r * r_dist_trail)
                nuevo_sl = f.max_fav - trail_efectivo
                if trail_armed and (f.sl is None or nuevo_sl > f.sl):
                    f.sl = nuevo_sl
                if live_fill_mode:
                    # Server-side order still resting at the PRIOR level
                    # (`sl_check`) -- bar i's own high (used above to raise
                    # `f.sl`) cannot have moved that resting order yet.
                    if bar["low"] <= sl_check:
                        f.abierta = False
                        eventos.append({"idx": i, "lado": lado_txt, "precio": sl_check,
                                        "motivo": "EXIT_TRAIL", "ficha": tag})
                        continue
                    # SAME-BAR FALLBACK: the just-raised `f.sl` is already
                    # violated by this bar's own CLOSE -- classic mode would
                    # have exited intrabar at the raised level, but live's
                    # server-side SL (still at `sl_check`) was never touched.
                    # Close at market (this bar's close), tagged EXIT_TRAIL,
                    # flagged for the reconciler/analysis.
                    if bar["close"] <= f.sl:
                        f.abierta = False
                        eventos.append({"idx": i, "lado": lado_txt, "precio": bar["close"],
                                        "motivo": "EXIT_TRAIL", "ficha": tag,
                                        "same_bar_fallback": True})
                        continue
                elif bar["low"] <= f.sl:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": f.sl,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue
            else:
                f.max_fav = min(f.max_fav, bar["low"])
                # F5 trail-start-delay (PX-T3), short mirror of the long branch:
                # gate the trailing RAISE ONLY until max_fav (running min) has
                # reached entry - trail_arm_r*R. trail_arm_r=0.0 -> unconditional
                # (byte-identical no-op). See the long-branch comment above.
                r_dist_trail = abs(f.entry - sl_inicial_by_tag[tag])
                trail_armed = (trail_arm_r <= 0.0
                               or f.max_fav <= f.entry - trail_arm_r * r_dist_trail)
                nuevo_sl = f.max_fav + trail_efectivo
                if trail_armed and (f.sl is None or nuevo_sl < f.sl):
                    f.sl = nuevo_sl
                if live_fill_mode:
                    if bar["high"] >= sl_check:
                        f.abierta = False
                        eventos.append({"idx": i, "lado": lado_txt, "precio": sl_check,
                                        "motivo": "EXIT_TRAIL", "ficha": tag})
                        continue
                    if bar["close"] >= f.sl:
                        f.abierta = False
                        eventos.append({"idx": i, "lado": lado_txt, "precio": bar["close"],
                                        "motivo": "EXIT_TRAIL", "ficha": tag,
                                        "same_bar_fallback": True})
                        continue
                elif bar["high"] >= f.sl:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": f.sl,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue

            # Runner exit on sustained AC deceleration (V-07; F3 only,
            # f3_ac_decel_exit=False disables this block entirely). Checked
            # AFTER SL/trailing above, so a same-bar stop-out takes
            # precedence over this (the `continue` statements above already
            # skip this ficha for the rest of the bar in that case).
            if f3_ac_decel_exit and tag == "F3":
                if ac_desacelerando(ac, i, f.lado):
                    ac_decel_consec_by_tag[tag] = ac_decel_consec_by_tag.get(tag, 0) + 1
                else:
                    ac_decel_consec_by_tag[tag] = 0
                if ac_decel_consec_by_tag[tag] >= f3_ac_decel_bars:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": px,
                                    "motivo": "EXIT_ACDECEL", "ficha": tag})
                    continue

            # Time-stop exit (P51; max_hold_bars=None disables this block
            # entirely, preserving current behavior byte-for-byte). Checked
            # LAST -- after all SL/trailing/AC-decel checks -- so any same-bar
            # stop-out (whose `continue` above already skipped this ficha) wins.
            # Closes at THIS bar's CLOSE (`px`), the honest fill for a
            # close-of-bar exit (unchanged under live_fill_mode). Bars-held is
            # `i - entry_bar_by_tag[tag]` (frozen _Ficha carries no counter).
            if max_hold_bars is not None and max_hold_bars > 0:
                entry_idx = entry_bar_by_tag.get(tag)
                if entry_idx is not None and (i - entry_idx) >= max_hold_bars:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": px,
                                    "motivo": "time_stop", "ficha": tag})
                    continue

        # V-13: record this bar's new EXIT_* motivos against the currently
        # open signal's lineage (reentry_enable=False -> this bookkeeping is
        # harmless dead weight, never read below).
        if reentry_enable:
            for ev in eventos[_n_eventos_before_exits:]:
                if ev["motivo"].startswith("EXIT"):
                    signal_exit_motivos.append(ev["motivo"])

        # live_fill_mode: advance the server-side SL snapshot to THIS bar's
        # close-of-bar `f.sl` for every ficha still open -- it becomes the
        # active server-side level starting bar i+1 (point 2 of the
        # docstring). Dead weight when live_fill_mode=False.
        if live_fill_mode:
            for tag, f in fichas.items():
                if f.abierta:
                    server_sl_by_tag[tag] = f.sl

        fichas = {k: v for k, v in fichas.items() if v.abierta}

        # V-13: the signal just fully closed (all 3 fichas flat) -- arm a
        # re-entry IFF every recorded exit motivo was EXIT_TRAIL (a full
        # trail-out, no EXIT_INITSL/EXIT_TP/EXIT_ACDECEL anywhere in the
        # lineage). Only meaningful the bar the LAST ficha of a signal
        # closes; `signal_exit_motivos` is reset on every new entry below.
        if reentry_enable and not fichas and signal_exit_motivos:
            if all(m == "EXIT_TRAIL" for m in signal_exit_motivos) and reentry_count < reentry_max:
                reentry_armed = True
            signal_exit_motivos = []

        # ---- 2) entry (no reentry while any ficha is open) ----
        # Stop-and-reverse (P55; stop_and_reverse=False disables this block
        # entirely -- the guard collapses to the classic `if fichas: continue`,
        # preserving current behavior byte-for-byte). When True and a position
        # is open, evaluate the strict close-of-bar gates for THIS bar; if a
        # signal OPPOSITE to the open side fires, close ALL open fichas at THIS
        # bar's close (`px`, motivo "reverse") and DO NOT `continue` -- fall
        # through so the opposite direction opens on the SAME bar via the normal
        # entry path below (priced at `px`, honest under live_fill_mode). Same-
        # direction (or no) signal keeps the classic deferral (`continue`).
        if fichas:
            if not stop_and_reverse:
                continue
            open_lado = next(iter(fichas.values())).lado
            _sar_long, _ = gate_long(
                bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                confirm_mode=confirm_mode, use_ema5=False,
                confirm_count=confirm_count, require_ema_order=require_ema_order)
            _sar_short, _ = gate_short(
                bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                confirm_mode=confirm_mode, use_ema5=False,
                confirm_count=confirm_count, require_ema_order=require_ema_order)
            _sar_signal = 0
            if _sar_long and allow_long:
                _sar_signal = +1
            elif _sar_short and allow_short:
                _sar_signal = -1
            if _sar_signal == 0 or _sar_signal == open_lado:
                # No signal, or same-direction: classic no-pyramiding deferral.
                continue
            # Opposite-direction signal while open -> net reverse. Close every
            # open ficha at THIS bar's close, then fall through to open the
            # opposite direction on the same bar.
            for tag in list(fichas.keys()):
                f = fichas[tag]
                if not f.abierta:
                    continue
                f.abierta = False
                eventos.append({
                    "idx": i,
                    "lado": "L" if f.lado == +1 else "S",
                    "precio": px,
                    "motivo": "reverse",
                    "ficha": tag,
                })
            if reentry_enable:
                for ev in eventos[_n_eventos_before_exits:]:
                    if ev["motivo"].startswith("EXIT"):
                        signal_exit_motivos.append(ev["motivo"])
            fichas = {k: v for k, v in fichas.items() if v.abierta}
            # Any re-entry arm from the closed lineage is moot after a reverse.
            reentry_armed = False
            reentry_lado = 0

        # V-13: while armed, cancel the arm outright if SAR trend has
        # flipped away from the original signal's direction (checked BEFORE
        # any entry evaluation this bar, per spec: "the arm is cancelled if
        # SAR trend flips").
        if reentry_armed and sar_trend[i] is not None and sar_trend[i] != reentry_lado:
            reentry_armed = False
            reentry_lado = 0

        # Session/hour filter (V-11; blocked_hours=None disables this check
        # entirely, preserving current behavior byte-for-byte): skip entry
        # evaluation outright for bars whose UTC hour is blocked.
        if blocked_hours is not None:
            bar_hour = datetime.fromtimestamp(bar["t"], tz=timezone.utc).hour
            if bar_hour in blocked_hours:
                continue

        # V-13: relaxed (G5-bypassed) re-entry check -- evaluated BEFORE the
        # normal strict-gate entry path below, so a re-entry can fire on a
        # bar the strict gate G1-G5 would have rejected (the measurable
        # difference this variant tests; see docstring). G1/G2/G4 required
        # via `_gate_g1_g4_only`, G3 via `_gate_g3_only` (or the intrabar
        # touch when entry_timing=1); SAR-trend match already re-checked
        # just above (also re-checked inline here for clarity/safety).
        if reentry_armed and sar_trend[i] == reentry_lado:
            if entry_timing == 1:
                if reentry_lado == +1:
                    touch_ok, touch_px = _toque_long(bars, ema_f, i)
                else:
                    touch_ok, touch_px = _toque_short(bars, ema_f, i)
                g3_ok = touch_ok
                reentry_px = touch_px if touch_ok else None
            else:
                g3_ok = _gate_g3_only(bars, ema_f, i, reentry_lado)
                reentry_px = px
            if g3_ok and _gate_g1_g4_only(ema_f, ema_s, sar_trend, i, reentry_lado):
                lado_txt = "L" if reentry_lado == +1 else "S"
                eventos.append({"idx": i, "lado": lado_txt, "precio": reentry_px,
                                "motivo": "ENTRY_L" if reentry_lado == +1 else "ENTRY_S", "ficha": None})
                sl = _sl_inicial_bounded(reentry_lado, i, reentry_px)
                fichas = {t: _Ficha(reentry_lado, reentry_px, sl) for t in active_tags}
                sl_inicial_by_tag = {t: sl for t in active_tags}
                server_sl_by_tag = {t: sl for t in active_tags}
                r_dist = abs(reentry_px - sl)
                r_by_tag = {t: r_dist for t in active_tags}
                ac_decel_consec_by_tag = {}
                entry_bar_by_tag = {t: i for t in active_tags}
                signal_exit_motivos = []
                reentry_count += 1
                if reentry_count >= reentry_max:
                    reentry_armed = False
                    reentry_lado = 0
                continue

        if entry_timing in (1, 3):
            # Intrabar entry (V-12; mirrors emasar_ref.simular's
            # entry_timing=1 EXACTLY): G3 is replaced by the intrabar touch
            # approximation on the SAME bar i; the rest of the gate
            # (G1/G2/G4/G5) is evaluated with skip_g3=True.
            # entry_timing=3 (audit, additive; 2026-07-13 look-ahead audit):
            # ADVERSE-FILL bound -- same gates/signal bar as timing=1, but the
            # fill price is forced to the WORST price of the signal bar for
            # the side (bar high for long, bar low for short) instead of the
            # touched EMA level, a pessimistic upper bound on how bad a
            # same-bar intrabar fill could realistically be.
            long_ok, entry_px_l = _toque_long(bars, ema_f, i)
            short_ok, entry_px_s = _toque_short(bars, ema_f, i)
            if entry_timing == 3:
                if long_ok:
                    entry_px_l = bars[i]["high"]
                if short_ok:
                    entry_px_s = bars[i]["low"]
            if long_ok:
                g_rest, _ = gate_long(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                                       confirm_mode=confirm_mode, use_ema5=False,
                                       confirm_count=confirm_count, require_ema_order=require_ema_order,
                                       skip_g3=True)
                long_ok = g_rest
            if short_ok:
                g_rest, _ = gate_short(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                                        confirm_mode=confirm_mode, use_ema5=False,
                                        confirm_count=confirm_count, require_ema_order=require_ema_order,
                                        skip_g3=True)
                short_ok = g_rest
            px_long = entry_px_l
            px_short = entry_px_s
        elif entry_timing == 2:
            # Causal next-open (V-12 audit; entry_timing=2, additive,
            # 2026-07-13 look-ahead audit): gates evaluated on bar i's CLOSE
            # exactly like entry_timing=0 (no G3 replacement, no skip_g3),
            # but the fill only executes at bar i+1's OPEN -- the earliest
            # price a strictly-causal system could act on the close-i
            # signal. If bar i is the LAST bar in the series there is no i+1
            # to fill at, so the signal is dropped (no entry event). Initial
            # SL is still computed from the SIGNAL bar i's range (unchanged
            # `_sl_inicial(lado, i)` call below), per spec.
            long_ok, _ = gate_long(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                                   confirm_mode=confirm_mode, use_ema5=False,
                                   confirm_count=confirm_count, require_ema_order=require_ema_order)
            short_ok, _ = gate_short(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                                     confirm_mode=confirm_mode, use_ema5=False,
                                     confirm_count=confirm_count, require_ema_order=require_ema_order)
            if i + 1 >= n:
                long_ok = False
                short_ok = False
                px_long = px_short = None
            else:
                px_long = bars[i + 1]["open"]
                px_short = bars[i + 1]["open"]
        else:
            long_ok, _ = gate_long(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                                   confirm_mode=confirm_mode, use_ema5=False,
                                   confirm_count=confirm_count, require_ema_order=require_ema_order)
            short_ok, _ = gate_short(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                                     confirm_mode=confirm_mode, use_ema5=False,
                                     confirm_count=confirm_count, require_ema_order=require_ema_order)
            px_long = px
            px_short = px

        # AC "rojo->verde" transition gate (V-08; g5_mode='ref' disables
        # this check entirely, preserving current behavior byte-for-byte):
        # ADDITIONALLY require the signal bar's AC to show an upturn
        # transition (long: ac[i] > ac[i-1] <= ac[i-2]; short mirrors).
        if g5_mode == "ac4_transition":
            if long_ok:
                long_ok = (
                    i >= 2 and ac[i] is not None and ac[i - 1] is not None and ac[i - 2] is not None
                    and ac[i] > ac[i - 1] and ac[i - 1] <= ac[i - 2]
                )
            if short_ok:
                short_ok = (
                    i >= 2 and ac[i] is not None and ac[i - 1] is not None and ac[i - 2] is not None
                    and ac[i] < ac[i - 1] and ac[i - 1] >= ac[i - 2]
                )

        # SuperTrend-M15 regime filter (V-10; direction_mask=None disables
        # this check entirely, preserving current behavior byte-for-byte):
        # mask[i]==-1 blocks long entries, mask[i]==+1 blocks short entries,
        # 0/None allows both.
        if direction_mask is not None:
            mask_i = direction_mask[i]
            if long_ok and mask_i == -1:
                long_ok = False
            if short_ok and mask_i == +1:
                short_ok = False

        # Confirmation-bar entry (P54; confirm_bar=False disables this block
        # entirely, preserving current behavior byte-for-byte -- the branch is
        # never entered and long_ok/short_ok/px_long/px_short flow straight into
        # the entry block below exactly as before). When True, a bar-i signal
        # (long_ok/short_ok just computed) does NOT enter at i: it is captured
        # as PENDING (side + this bar's high/low extreme) for the NEXT bar, and
        # long_ok/short_ok are cleared so the entry block below does not fire on
        # the signal bar. Any signal PENDING FROM BAR i-1 is resolved here first:
        # it enters on THIS bar (via the existing entry block, priced at
        # px_long/px_short -- the confirmation bar's own fill) IFF this bar's
        # close confirms beyond the signal bar's extreme (long: close > high,
        # short: close < low); otherwise it is dropped. One-bar window only: the
        # pending is consumed (entered or dropped) every bar, never carried past
        # i+1.
        if confirm_bar:
            new_signal_lado = 0
            if long_ok and allow_long:
                new_signal_lado = +1
            elif short_ok and allow_short:
                new_signal_lado = -1

            # Resolve the pending signal from bar i-1 against THIS bar's close.
            confirm_long = False
            confirm_short = False
            if pending_confirm_lado == +1:
                confirm_long = px > pending_confirm_high
            elif pending_confirm_lado == -1:
                confirm_short = px < pending_confirm_low

            # This bar's own signal (if any) becomes next bar's pending; the
            # signal bar itself never enters. A fresh signal overwrites any
            # already-resolved (entered/dropped) prior pending. BUT if this bar
            # is itself confirming a prior pending (a position is about to
            # open), the fresh signal is dropped -- it could never be resolved
            # next bar anyway (the `if fichas: continue` guard would skip it),
            # so capturing it would leak the pending past its one-bar window.
            if (confirm_long or confirm_short):
                pending_confirm_lado = 0
            elif new_signal_lado != 0:
                pending_confirm_lado = new_signal_lado
                pending_confirm_high = bar["high"]
                pending_confirm_low = bar["low"]
            else:
                pending_confirm_lado = 0

            # Only a CONFIRMED pending signal enters on this bar, via the
            # existing entry block below (px_long/px_short = the confirmation
            # bar's fill under the active entry_timing).
            long_ok = confirm_long
            short_ok = confirm_short

        # Pullback-LIMIT entry (P33; V-12 causal cousin; pullback_limit=False
        # disables this block entirely, preserving current behavior byte-for-
        # byte -- long_ok/short_ok/px_long/px_short flow straight into the entry
        # block below exactly as before). When True (entry_timing==0 only): a
        # bar-i signal (long_ok/short_ok just computed) does NOT enter at i. A
        # resting LIMIT at level=ema_f[i] (known once bar i closes) is captured
        # for the NEXT bar. Any LIMIT PENDING FROM BAR i-1 is resolved here
        # first against THIS bar's OHLC (a strictly LATER bar than the signal
        # bar -- no look-ahead): LONG fills iff bar.low<=level, SHORT iff
        # bar.high>=level, at price=level; otherwise the order EXPIRES. One-bar
        # window only: the pending is consumed (filled or expired) every bar,
        # never carried past i+1. A last-bar signal has no i+1 and drops.
        if pullback_limit:
            new_signal_lado = 0
            if long_ok and allow_long:
                new_signal_lado = +1
            elif short_ok and allow_short:
                new_signal_lado = -1

            # Resolve the resting LIMIT from bar i-1 against THIS bar's OHLC.
            fill_long = False
            fill_short = False
            if pending_limit_lado == +1:
                fill_long = bar["low"] <= pending_limit_level
            elif pending_limit_lado == -1:
                fill_short = bar["high"] >= pending_limit_level

            # This bar's own signal (if any) places NEXT bar's resting LIMIT at
            # ema_f[i]; the signal bar itself never enters. A fresh signal
            # overwrites any already-resolved (filled/expired) prior pending. BUT
            # if this bar is itself filling a prior LIMIT (a position is about to
            # open), the fresh signal is dropped -- it could never be resolved
            # next bar (the `if fichas: continue` guard would skip it), so
            # capturing it would leak the pending past its one-bar window.
            if fill_long or fill_short:
                pending_limit_lado = 0
            elif new_signal_lado != 0:
                pending_limit_lado = new_signal_lado
                pending_limit_level = ema_f[i]
            else:
                pending_limit_lado = 0

            # Only a FILLED resting LIMIT enters on this bar, priced at the LIMIT
            # level (NOT the close). The initial SL below still uses signal bar
            # i's range via _sl_inicial(lado, i), consistent with the sibling
            # deferred-entry levers.
            long_ok = fill_long
            short_ok = fill_short
            if fill_long:
                px_long = pending_limit_level
            if fill_short:
                px_short = pending_limit_level

        if long_ok and allow_long:
            eventos.append({"idx": i, "lado": "L", "precio": px_long, "motivo": "ENTRY_L", "ficha": None})
            sl = _sl_inicial_bounded(+1, i, px_long)
            fichas = {t: _Ficha(+1, px_long, sl) for t in active_tags}
            sl_inicial_by_tag = {t: sl for t in active_tags}
            server_sl_by_tag = {t: sl for t in active_tags}
            r_dist = abs(px_long - sl)
            r_by_tag = {t: r_dist for t in active_tags}
            ac_decel_consec_by_tag = {}
            entry_bar_by_tag = {t: i for t in active_tags}
            # V-13: a fresh STRICT-gate entry starts a brand-new lineage --
            # any previous re-entry arm/count is unrelated to this signal.
            signal_exit_motivos = []
            reentry_armed = False
            reentry_lado = +1
            reentry_count = 0
        elif short_ok and allow_short:
            eventos.append({"idx": i, "lado": "S", "precio": px_short, "motivo": "ENTRY_S", "ficha": None})
            sl = _sl_inicial_bounded(-1, i, px_short)
            fichas = {t: _Ficha(-1, px_short, sl) for t in active_tags}
            sl_inicial_by_tag = {t: sl for t in active_tags}
            server_sl_by_tag = {t: sl for t in active_tags}
            r_dist = abs(px_short - sl)
            r_by_tag = {t: r_dist for t in active_tags}
            ac_decel_consec_by_tag = {}
            entry_bar_by_tag = {t: i for t in active_tags}
            signal_exit_motivos = []
            reentry_armed = False
            reentry_lado = -1
            reentry_count = 0

    if return_state:
        # Additive, default-OFF snapshot (parity-by-construction for the live
        # reconciler): the still-open fichas AFTER processing the last bar in
        # `bars`, i.e. the desired live positions at that (closed) bar. Each
        # ficha reports its side, entry price and CURRENT stop (initial or
        # trailed, whichever is active) -- the exact SL the sim would have on
        # the broker. When `bars` is empty or the last bar is flat, `fichas`
        # is empty -> {} (desired: no open positions). Only the reconciler
        # passes return_state=True; every other caller/test path is untouched.
        # live_fill_mode: report the SERVER-side SL the broker is actually
        # resting with (the level as of the PRIOR bar's close, captured in
        # `server_sl_during_bar` at the start of the last bar), NOT the classic
        # `f.sl` that was just raised using the last bar's OWN high -- a live
        # executor consuming the state would otherwise chase a one-bar-ahead
        # stop. Classic mode (live_fill_mode=False) is unchanged: reports f.sl.
        open_state = {
            tag: {"side": "L" if f.lado == +1 else "S", "entry": f.entry,
                  "sl": (server_sl_during_bar.get(tag, f.sl)
                         if live_fill_mode else f.sl),
                  "max_fav": f.max_fav}
            for tag, f in fichas.items() if f.abierta
        }
        # Same-bar-exit support (live reconciler addendum 2026-07-13): the sim
        # can raise a ficha's trail using the LAST bar's OWN high/AC and exit
        # WITHIN that same just-closed bar -- live (whose server-side SL was at
        # the prior bar's level) can't replicate that mid-bar, so the daemon
        # must close at market next tick and account the by-design price gap.
        # Expose the exit events that fired ON THE LAST bar so the reconciler
        # can attach the sim's fill price/level per ficha.
        last_idx = n - 1 if n else -1
        last_bar_exits = {
            ev["ficha"]: {"price": ev["precio"], "motivo": ev["motivo"],
                          "side": ev["lado"], "idx": ev["idx"]}
            for ev in eventos
            if ev["idx"] == last_idx and ev["motivo"].startswith("EXIT")
            and ev.get("ficha") is not None
        }
        return eventos, {"open": open_state, "last_bar_exits": last_bar_exits,
                         "last_idx": last_idx}
    return eventos
