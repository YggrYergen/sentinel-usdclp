"""sentinel_engine.strategies.live_configs_20 -- the curated 20 validated
EMASAR-variant configs for live deployment (SENTINEL, 2026-07-13).

WHAT THIS IS
------------
A single source of truth for the 20 winning strategy configurations the trader
selected to replace the ~39 legacy `TOKATA_Sapitos_v3` chart instances. Each
config is expressed as the EXACT keyword arguments to
`sentinel_engine.strategies.emasar_variant.simular_variant` -- i.e. against the
ONLY engine in this repo where the required levers (per-ficha flat trailing
ladder, ac_modulate + factor, controlled re-entry, volatility-adaptive SAR,
range initial-SL, EMA-order gate drop, SuperTrend-M15 direction mask, blocked
server hours) actually exist and are golden-tested.

WHY IT LIVES HERE (not as MQL5 .set files / MT5 chart profile)
--------------------------------------------------------------
The live execution path in this project is MQL5 EAs attached to charts in the
DEMO MT5 terminal (see the deployment report
`docs/superpowers/research/2026-07-13-live-deployment-20.md`). The shipped
EMASAR EA (`TOKATA_EMASAR_v1.mq5`) supports NONE of these levers, and there is
no Python order-routing path (`run_service.py` / `deals_watcher` are strictly
read-only; no `guard_cuenta.assert_demo` exists in Python). So this module does
NOT itself route orders -- it is the validated, machine-diffable design spec of
the 20, kept in lock-step with `simular_variant` via `tests/strategies/
test_live_configs_20.py`, ready to drive whichever executor is built/wired
next (a lever-complete EA, or a future guarded Python bridge).

Each entry: {id, tf, k, kwargs, notes}. `kwargs` are the literal
`simular_variant(**kwargs)` arguments (minus `bars`/`direction_mask`, which are
data supplied at run time). `direction_filter=True` flags configs (#14/#15)
that additionally require the caller to compute a SuperTrend-M15
`direction_mask`; `blocked_hours` (config #20) is already inside `kwargs`.

`LIVE_ROSTER`/`CONFIGS_LIVE` (bottom of this module) pin the trader-selected
subset of CONFIGS_20 currently authorized to trade live.
"""
from __future__ import annotations

import copy
from typing import Any

# Common skeleton for ALL configs except the two V09 controls.
_SKELETON: dict[str, Any] = dict(
    confirm_mode=1,
    confirm_count=2,
    require_ema_order=False,
    ema_fast=8,
    ema_slow=20,
    sar_step=0.3,
    sar_max=0.3,
    f1_trail_pips=100.0,
    f2_trail_pips=100.0,
    f3_trail_pips=100.0,
    ac_modulate=True,
    symbol="XAUUSD",
)

# Per-TF init_sl_range_k (spec init_sl_mode='range' -> simular_variant is
# always range-SL via init_sl_range_k; there is no separate mode flag).
_K_BY_TF = {"M1": 6.0, "M2": 3.0, "M5": 6.0, "M15": 2.5}

# Volatility-adaptive SAR pairs (spec: fast=(0.3,0.3), slow=(0.005,0.05),
# window=200).
_ADAPTIVE = dict(
    sar_adaptive=True,
    sar_fast=(0.3, 0.3),
    sar_slow=(0.005, 0.05),
    vol_regime_window=200,
)

# "SS" extras: ac_modulate_factor=0.01, reentry_enable, reentry_max=2, adaptive.
_SS_EXTRAS = dict(ac_modulate_factor=0.01, reentry_enable=True, reentry_max=2, **_ADAPTIVE)


def _cfg(cid: str, tf: str, *, extra: dict[str, Any], k: float | None = None,
         ac_modulate: bool | None = None, direction_filter: bool = False,
         notes: str = "") -> dict[str, Any]:
    kwargs = dict(_SKELETON)
    kwargs["init_sl_range_k"] = _K_BY_TF[tf] if k is None else k
    if ac_modulate is not None:
        kwargs["ac_modulate"] = ac_modulate
    kwargs.update(extra)
    return {"id": cid, "tf": tf, "k": kwargs["init_sl_range_k"],
            "kwargs": kwargs, "direction_filter": direction_filter, "notes": notes}


CONFIGS_20: list[dict[str, Any]] = [
    # 1
    _cfg("SS-M2", "M2", extra=dict(_SS_EXTRAS)),
    # 2
    _cfg("V06D-M2", "M2", extra=dict(ac_modulate_factor=0.01)),
    # 3
    _cfg("V15-M2", "M2", extra=dict(ac_modulate_factor=0.25, **_ADAPTIVE)),
    # 4
    _cfg("SS-M5", "M5", extra=dict(_SS_EXTRAS)),
    # 5
    _cfg("V06D-M5", "M5", extra=dict(ac_modulate_factor=0.01)),
    # 6
    _cfg("V13-M5", "M5", extra=dict(ac_modulate_factor=0.25, reentry_enable=True, reentry_max=2)),
    # 7  -- SS at M15 but NO sar_adaptive per spec
    _cfg("SS-M15", "M15", extra=dict(ac_modulate_factor=0.01, reentry_enable=True, reentry_max=2)),
    # 8
    _cfg("V13-M15", "M15", extra=dict(ac_modulate_factor=0.25, reentry_enable=True, reentry_max=2)),
    # 9
    _cfg("V06D-M15", "M15", extra=dict(ac_modulate_factor=0.01)),
    # 10
    _cfg("V06C-M5", "M5", extra=dict(ac_modulate_factor=0.10)),
    # 11
    _cfg("V06C-M15", "M15", extra=dict(ac_modulate_factor=0.10)),
    # 12
    _cfg("V06B-M15", "M15", extra=dict(ac_modulate_factor=0.25)),
    # 13
    _cfg("V15-M15", "M15", extra=dict(ac_modulate_factor=0.25, **_ADAPTIVE)),
    # 14  -- direction filter (SuperTrend-M15 prev-closed bar)
    _cfg("V10-M5", "M5", extra=dict(ac_modulate_factor=0.25), direction_filter=True,
         notes="direction_mask: SuperTrend(14,3.0) on previous CLOSED M15 bar"),
    # 15
    _cfg("V10-M15", "M15", extra=dict(ac_modulate_factor=0.25), direction_filter=True,
         notes="direction_mask: SuperTrend(14,3.0) on previous CLOSED M15 bar"),
    # 16
    _cfg("V13-M2", "M2", extra=dict(ac_modulate_factor=0.25, reentry_enable=True, reentry_max=2)),
    # 17  -- V09 control: ac_modulate=False, k=1.0
    _cfg("V09-CTRL-M5", "M5", extra={}, k=1.0, ac_modulate=False,
         notes="control baseline"),
    # 18
    _cfg("V09-CTRL-M15", "M15", extra={}, k=1.0, ac_modulate=False,
         notes="control baseline"),
    # 19  -- M1 observation slot
    _cfg("SS-M1", "M1", extra=dict(_SS_EXTRAS),
         notes="observation slot -- first net-positive M1"),
    # 20  -- hour blocking on server hours {0,6,16,18,23}
    _cfg("V11-M2", "M2", extra=dict(ac_modulate_factor=0.25,
                                    blocked_hours=frozenset({0, 6, 16, 18, 23})),
         notes="no NEW entries in blocked server hours; exits unaffected"),
]

assert len(CONFIGS_20) == 20, "expected exactly 20 configs"
assert len({c["id"] for c in CONFIGS_20}) == 20, "config ids must be unique"

# --- PHASE 3.5 (live shadow parity): magic-number assignment -----------------
# Base magic per config = 720000 + 10*position (1-based): 720010..720200.
# Leaves room for the TOKATA per-ficha offset convention (base+1/+2/+3 =
# F1/F2/F3); no collision with legacy Sapitos (330xxx/334xxx/335xxx), the
# EMASAR EA default (710000) or the IA band (900000-900999).
_MAGIC_BASE = 720000
for _i, _c in enumerate(CONFIGS_20, start=1):
    _c["magic"] = _MAGIC_BASE + 10 * _i

MAGIC_BY_ID: dict[str, int] = {c["id"]: c["magic"] for c in CONFIGS_20}
assert len(set(MAGIC_BY_ID.values())) == 20, "magics must be unique"

# --- LIVE ROSTER (trader selection 2026-07-14) ---------------------------
# The subset of CONFIGS_20 currently authorized to trade live. Selected by
# the trader from the 2026-07-14 diagnostic + candidates evidence (the 3
# net-positive configs of the first armed sessions plus V15-M15). The other
# 16 configs remain DEFINED (parity/backtest tooling uses them) but are NOT
# traded by the live executor when it is started with `--configs live`.
LIVE_ROSTER: tuple[str, ...] = ("V11-M2", "V15-M2", "V13-M2", "V15-M15")
CONFIGS_LIVE: list[dict[str, Any]] = [c for c in CONFIGS_20 if c["id"] in LIVE_ROSTER]
assert len(CONFIGS_LIVE) == len(LIVE_ROSTER), "every LIVE_ROSTER id must exist in CONFIGS_20"

# --- SHADOW ROSTER (FIXED4, Addendum §1.2, D114) -------------------------
# FIXED4: the live roster with the obvious honesty fixes.
# Same signals; honest exits. Magics 721010/721020/721030/721040 (+1..+3 fichas).
# ac_modulate=False   -> no anti-correlation trail modulation (raw trail).
# live_fill_mode=True  -> honest broker-RESTING SL in open_state (Task A1); the
#                         reported open_state[tag]["sl"] is one bar behind the
#                         classic raised trail by design -- the executor uses it
#                         verbatim as the resting level and must NOT "fix" it.
# trail_atr_floor_k=1.5-> ATR floor under the flat pip trail (Task A1).
# Magic base 721000 keeps the shadow band [721010..721043] fully DISJOINT from
# the live band [720010..720203] and from every other magic block (legacy
# Sapitos 33xxxx, EMASAR EA 710000, IA 900xxx). Machine-2 runs `--configs
# shadow` ONLY; the uncorrected live-4 never arms there (D114).
def _fixed(cfg: dict[str, Any], new_magic: int) -> dict[str, Any]:
    k = dict(cfg["kwargs"], ac_modulate=False, live_fill_mode=True,
             trail_atr_floor_k=1.5)
    return {**cfg, "id": cfg["id"] + "-F", "kwargs": k, "magic": new_magic}


CONFIGS_SHADOW: list[dict[str, Any]] = [
    _fixed(c, 721000 + 10 * (i + 1)) for i, c in enumerate(CONFIGS_LIVE)
]
assert len(CONFIGS_SHADOW) == len(CONFIGS_LIVE), "one shadow config per live config"
assert len({c["id"] for c in CONFIGS_SHADOW}) == len(CONFIGS_SHADOW), \
    "shadow config ids must be unique"
assert len({c["magic"] for c in CONFIGS_SHADOW}) == len(CONFIGS_SHADOW), \
    "shadow magics must be unique"
# live vs shadow magic bands ([base .. base+3]) must never intersect.
_live_band = {c["magic"] + o for c in CONFIGS_LIVE for o in range(4)}
_shadow_band = {c["magic"] + o for c in CONFIGS_SHADOW for o in range(4)}
assert _live_band.isdisjoint(_shadow_band), "live/shadow magic bands must be disjoint"

# --- GO-LIVE ROSTER (GL-T1, Wave-6 selection 2026-07-20) -----------------
# The six live-forward OOS candidates chosen from the Wave-6 honest league
# (`docs/superpowers/research/2026-07-20-wave6-tp-trailhalf-findings.md`,
# league v3, 225 cells): the FIVE net-positive M15 V-15 SAR-tuned winners
# (top-5 pooled net across {IW,W1,W2,W3}) plus V11-M2 (the existing
# least-negative M2 line, reused verbatim from CONFIGS_20).
#
# HONESTY FRAMING (D18): none of the five is DSR-significant (DSR 0 / p 1
# across all 225 trials); they are in-sample winners, sub-luck-bar. This
# roster is a LIVE-FORWARD OOS TEST on the Capitaria DEMO, not a proven edge.
# The `tp_min` lever was DECISIVELY REFUTED (most harmful lever tested) and is
# deliberately ABSENT here.
#
# The five SAR winners are built VERBATIM from the manifest cells that
# produced the honest league (`scripts/report/honest_manifest_full_2026_07_20_v3.json`),
# so the live params == the honestly-scored params, byte-for-byte:
#   S6-K2P0      = HON-W2-S6-K2P0-M15-SAR   (rank 1, +49,111.5)
#   S7-TPNONE    = HON-W2-S7-TPNONE-M15-SAR (rank 2, +32,683.5)
#   S6-K1P5      = HON-W2-S6-K1P5-M15-SAR   (rank 3, +32,493.0)
#   S7-TP1P0     = HON-W2-S7-TP1P0-M15-SAR  (rank 4, +30,642.5)
#   S7-TPNONE-F2 = HON-W2-S7-TPNONE-M15-SAR-F2 (rank 5, +21,789.0)
# All five share the champion M15 SAR (+vol-target) base (ema 8/20, sar
# 0.3/0.3 adaptive, f{1,2,3}_trail_pips 100, init_sl_range_k 2.5,
# vol_regime_window 200, confirm_count 2, confirm_mode 1, ac_modulate_factor
# 0.25, stop_and_reverse, live_fill_mode) and differ ONLY by the per-cell
# deltas below (ac_modulate, trail_atr_floor_k, be_at_r, f1_tp_r,
# active_fichas).
#
# MAGICS -- FRESH BLOCK 7240x0 (724010..724060), fichas +1..+3 =>
# band [724011..724063]. Chosen to be CLEARLY FREE and disjoint from:
#   * 720xxx classic live band,       * 721xxx FIXED4 shadow band,
#   * 722xxx (reserved "NEW6" per W8-T6 ops plan), and
#   * 723xxx (reserved "NEW6-TP suite" per W8-T6 ops plan),
#   * legacy Sapitos 33xxxx, EMASAR EA 710000, IA 900xxx.
# 7220xx is the plan's intended NEW6 block, but W8-T6's NEW6 is a DIFFERENT
# six (top-5 + V15-M15-F, not V11-M2) with a DIFFERENT selection freeze; to
# avoid clobbering that reserved block (and its 723xxx TP-suite sibling) this
# GL-T1 roster takes the next clearly-free block, 724xxx. See report.
_GOLIVE_BASE_M15: dict[str, Any] = dict(
    _SKELETON,
    init_sl_range_k=_K_BY_TF["M15"],   # 2.5
    ac_modulate_factor=0.25,
    stop_and_reverse=True,
    live_fill_mode=True,
    **_ADAPTIVE,
)


def _golive_m15(cid: str, *, ac_modulate: bool, trail_atr_floor_k: float,
                extra: dict[str, Any] | None = None,
                notes: str = "") -> dict[str, Any]:
    """One M15 V-15 SAR go-live winner: champion base + per-cell deltas.
    kwargs are byte-identical to the honest-league manifest cell."""
    k = dict(_GOLIVE_BASE_M15, ac_modulate=ac_modulate,
             trail_atr_floor_k=trail_atr_floor_k)
    if extra:
        k.update(extra)
    return {"id": cid, "tf": "M15", "k": k["init_sl_range_k"],
            "kwargs": k, "direction_filter": False, "notes": notes}


_GOLIVE_M15: list[dict[str, Any]] = [
    _golive_m15("S6-K2P0", ac_modulate=True, trail_atr_floor_k=2.0,
                notes="HON-W2-S6-K2P0-M15-SAR (league rank 1)"),
    _golive_m15("S7-TPNONE", ac_modulate=False, trail_atr_floor_k=1.5,
                extra=dict(be_at_r=1.0),
                notes="HON-W2-S7-TPNONE-M15-SAR (league rank 2)"),
    _golive_m15("S6-K1P5", ac_modulate=True, trail_atr_floor_k=1.5,
                notes="HON-W2-S6-K1P5-M15-SAR (league rank 3)"),
    _golive_m15("S7-TP1P0", ac_modulate=False, trail_atr_floor_k=1.5,
                extra=dict(f1_tp_r=1.0, be_at_r=1.0),
                notes="HON-W2-S7-TP1P0-M15-SAR (league rank 4)"),
    _golive_m15("S7-TPNONE-F2", ac_modulate=False, trail_atr_floor_k=1.5,
                extra=dict(be_at_r=1.0, active_fichas=2),
                notes="HON-W2-S7-TPNONE-M15-SAR-F2 (league rank 5)"),
]

# V11-M2: the existing least-negative M2 line -- reuse its CONFIGS_20 live
# definition verbatim (params + tf + k), only re-magicked into the GO-LIVE
# block. This preserves its blocked_hours / ac_modulate_factor exactly.
_V11_M2_SRC = next(c for c in CONFIGS_20 if c["id"] == "V11-M2")
_GOLIVE_V11_M2: dict[str, Any] = {
    "id": "V11-M2", "tf": _V11_M2_SRC["tf"], "k": _V11_M2_SRC["k"],
    "kwargs": dict(_V11_M2_SRC["kwargs"]),
    "direction_filter": _V11_M2_SRC.get("direction_filter", False),
    "notes": "existing least-negative M2 line, reused verbatim (GL-T1)",
}

# --- SuperTrend-p14x3-M15: the 7th GO-LIVE strategy (GL-T3) ----------------
# ALWAYS-IN, NOT a simular_variant ladder. SuperTrend(atr_period=14, mult=3.0)
# on M15: the desired live target is a SINGLE position, LONG when the last
# closed bar's trend is +1 (price above the SuperTrend line) and SHORT when
# -1 (below), FLIPPING when price crosses the line. The SuperTrend line is the
# server-side SL. This is the honestly-scored "always-in" engine from Wave-5
# P34 (`scripts/report/gen_p34_supertrend_honest.py`,
# `docs/superpowers/research/2026-07-20-wave5-p34-supertrend.md`), reusing the
# vendored SuperTrend math verbatim (ZERO new indicator code).
#
# WHY IT FITS ADDITIVELY (parity-by-construction, no reconciler refactor):
# the go-live reconciler diffs a `simular_variant(return_state=True)`-shaped
# snapshot -- {"open": {tag: {side, entry, sl}}, ...} -- against live positions
# in the config's ficha band. `supertrend_always_in_target` emits that SAME
# shape with a SINGLE ficha F1 on the SuperTrend side, so the reconciler
# OPENs it (spread-gated), trails its SL (MODIFY) and, on a trend flip, CLOSEs
# the old side (live side != desired side) then re-OPENs the opposite next
# cycle -- the always-in flip -- with NO change to the ladder reconciler. The
# executor branches on `engine == "supertrend_always_in"` to build the target
# instead of calling `simular_variant`.
_ST_ATR_PERIOD = 14
_ST_MULT = 3.0


def supertrend_always_in_target(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Always-in SuperTrend(14, 3.0) desired target on the LAST CLOSED bar,
    in the reconciler's `return_state` snapshot shape.

    Returns {"open": {"F1": {"side","entry","sl","max_fav"}} | {},
             "last_bar_exits": {}, "last_idx": n-1}. A SINGLE position (F1):
    LONG when the last bar's SuperTrend trend is +1 (price above the line),
    SHORT when -1; `sl` is the SuperTrend line (server-side stop). Empty/short
    bars -> flat ({} open). The vendored `_supertrend_ref.supertrend` + Wilder
    ATR provide the math verbatim -- no indicator code is re-implemented here.
    """
    # Local imports keep this module import-light (the 20-config spec must load
    # without dragging in the SuperTrend/ATR refs unless the flavor is used).
    from sentinel_engine.strategies._supertrend_ref import supertrend
    from sentinel_engine.strategies.emasar_ref import _atr_wilder

    n = len(bars)
    if n == 0:
        return {"open": {}, "last_bar_exits": {}, "last_idx": -1}
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    atr = _atr_wilder(highs, lows, closes, _ST_ATR_PERIOD)
    # No valid ATR yet (feed shorter than the ATR warmup) -> flat, matching the
    # honest engine's "first valid ATR bar" open rule.
    if all(a is None for a in atr):
        return {"open": {}, "last_bar_exits": {}, "last_idx": n - 1}
    atr_filled = [a if a is not None else 0.0 for a in atr]
    trend, line = supertrend(highs, lows, closes, atr_filled, _ST_MULT)
    side = "L" if trend[-1] == 1 else "S"
    open_state = {"F1": {"side": side, "entry": closes[-1], "sl": line[-1],
                         "max_fav": None}}
    return {"open": open_state, "last_bar_exits": {}, "last_idx": n - 1}


_GOLIVE_SUPERTREND: dict[str, Any] = {
    "id": "SuperTrend-p14x3-M15", "tf": "M15", "k": None,
    # NOT simular_variant kwargs: the executor builds the always-in target from
    # `engine` instead. `symbol` is the only kwarg the executor reads (bars +
    # spread-gate). direction_filter irrelevant for always-in.
    "kwargs": {"symbol": "XAUUSD"},
    "engine": "supertrend_always_in",
    "direction_filter": False,
    "notes": ("Wave-5 P34 always-in SuperTrend(14,3.0) M15; single flipping "
              "position, SL=SuperTrend line; reconciled additively (GL-T3)"),
}

CONFIGS_GOLIVE: list[dict[str, Any]] = [*_GOLIVE_M15, _GOLIVE_V11_M2,
                                        _GOLIVE_SUPERTREND]

_GOLIVE_MAGIC_BASE = 724000
for _i, _c in enumerate(CONFIGS_GOLIVE, start=1):
    _c["magic"] = _GOLIVE_MAGIC_BASE + 10 * _i   # 724010..724070

assert len(CONFIGS_GOLIVE) == 7, "GO-LIVE roster must be exactly 7 configs"
assert len({c["id"] for c in CONFIGS_GOLIVE}) == 7, "go-live ids must be unique"
assert [c["magic"] for c in CONFIGS_GOLIVE] == [724010, 724020, 724030, 724040,
                                                724050, 724060, 724070], \
    "go-live magics must be the fresh 7240x0 block"
# Exactly the six ladder configs run simular_variant; the 7th is always-in.
assert sum(1 for c in CONFIGS_GOLIVE
           if c.get("engine", "simular_variant") == "simular_variant") == 6, \
    "exactly six go-live configs run simular_variant (the 7th is SuperTrend)"
assert _GOLIVE_SUPERTREND["engine"] == "supertrend_always_in"
# go-live band ([base .. base+3]) must be disjoint from live AND shadow bands
# AND from the plan-reserved 722xxx/723xxx blocks.
_golive_band = {c["magic"] + o for c in CONFIGS_GOLIVE for o in range(4)}
assert _golive_band.isdisjoint(_live_band), "go-live/live magic bands must be disjoint"
assert _golive_band.isdisjoint(_shadow_band), "go-live/shadow magic bands must be disjoint"
assert all(724000 <= m <= 724099 for m in _golive_band), \
    "go-live band must stay inside 7240xx (clear of reserved 722xxx/723xxx)"

MAGIC_BY_ID_GOLIVE: dict[str, int] = {c["id"]: c["magic"] for c in CONFIGS_GOLIVE}

# --- DEDUP GO-LIVE roster (D121, 2026-07-20) -------------------------------
# The five M15 SAR configs are ONE signal fivefold (Wave-4 measured 60-77%
# pairwise signal overlap): fielding all five multiplies a single whipsaw --
# the demonstrated driver of live round-1's clone-bloc loss (-58,445 CLP, the 5
# near-clones stopped out together). This DEDUPLICATED roster keeps only the TWO
# best SAR representatives -- S6-K2P0 (league rank 1, profit leader in-sample
# AND on the untouched holdout) and S7-TPNONE (rank 2, break-even-at-+1R
# give-back protection) -- plus the two GENUINELY DISTINCT lines already in the
# roster: V11-M2 (M2 timeframe, the only live-winner line) and the always-in
# SuperTrend engine. It drops NO distinct signal, only redundant clones.
# Magics are inherited UNCHANGED from CONFIGS_GOLIVE (each kept config keeps its
# 7240x0 magic), so the go-live band + disjointness invariants still hold and
# open positions on the kept reps re-sync seamlessly on a daemon restart.
CONFIGS_GOLIVE_DEDUP_IDS: tuple[str, ...] = (
    "S6-K2P0", "S7-TPNONE", "V11-M2", "SuperTrend-p14x3-M15")
CONFIGS_GOLIVE_DEDUP: list[dict[str, Any]] = [
    c for c in CONFIGS_GOLIVE if c["id"] in CONFIGS_GOLIVE_DEDUP_IDS]

assert [c["id"] for c in CONFIGS_GOLIVE_DEDUP] == list(CONFIGS_GOLIVE_DEDUP_IDS), \
    "dedup roster must preserve CONFIGS_GOLIVE order == the canonical dedup ids"
assert [c["magic"] for c in CONFIGS_GOLIVE_DEDUP] == [724010, 724020, 724060, 724070], \
    "dedup roster magics must be inherited unchanged from the go-live block"
# still exactly one always-in engine (SuperTrend); the other three run simular_variant.
assert sum(1 for c in CONFIGS_GOLIVE_DEDUP
           if c.get("engine", "simular_variant") == "simular_variant") == 3, \
    "dedup roster has exactly three simular_variant configs (the 4th is SuperTrend)"

# --- TK-Momentum-5-8-short (2026-07-21) ------------------------------------
# A trader's live-forward test on XAUUSD, run as its OWN isolated roster
# (`--configs tk-momentum`) ALONGSIDE the other strategies. NEW additive engine
# `tk_momentum` (SMA5/SMA8 regime + MOM2 100-line cross, 0.5-USD trailing stop;
# see sentinel_engine.strategies.tk_momentum and the design spec
# docs/superpowers/specs/2026-07-21-tk-momentum-5-8-short-design.md). Single
# position -> reconciled through the SAME ladder reconciler as SuperTrend.
#
# MAGIC: the trader asked for an all-nines magic. The reconciler puts ficha F1
# at base_magic+1, so base 999999998 => the LIVE POSITION carries magic
# 999999999 ("puros nueves", what shows on the trade). Band [999999999 ..
# 1000000001] is CLEARLY disjoint from every block in use (720xxx classic,
# 721xxx shadow, 724xxx go-live, legacy Sapitos 33xxxx, EMASAR EA 710000, IA
# 900xxx).
TK_MOMENTUM_MAGIC_BASE = 999999998
CONFIG_TK_MOMENTUM: dict[str, Any] = {
    "id": "TK-Momentum-5-8-short",
    "tf": "M6",
    "k": None,
    "kwargs": {"symbol": "XAUUSD", "trail_usd": 3.0, "intrabar": True},
    "engine": "tk_momentum",
    "direction_filter": False,
    "magic": TK_MOMENTUM_MAGIC_BASE,
    "notes": ("SMA5/SMA8 regime + MOM2(2) 100-line cross entry, exit on "
              "momentum reversion OR 3.0-USD trailing stop (trader's choice, "
              "2026-07-21: XAUUSD trade_stops_level=50pts=0.5 USD so a 0.5 SL "
              "is illegal; 3.0 is comfortably legal and gives room); "
              "single position (never more than one open at a time -- trader "
              "2026-07-21); M6 bars (trader 2026-07-21: switched from M10 to "
              "M6 for a faster reaction; the 5/8/2 periods are kept so they now "
              "span 30/48/12 min instead of 50/80/20); INTRABAR (evaluates the "
              "still-forming M6 bar live, enters without waiting for bar close "
              "-- trader request 2026-07-21; repaints + diverges from the "
              "close-driven backtest); trader live-forward test (GL/TK-2026-07-21)"),
}
CONFIGS_TK: list[dict[str, Any]] = [CONFIG_TK_MOMENTUM]

assert CONFIG_TK_MOMENTUM["magic"] + 1 == 999999999, \
    "TK-Momentum ficha F1 magic must be the all-nines 999999999 the trader asked for"
_tk_band = {CONFIG_TK_MOMENTUM["magic"] + o for o in range(4)}
assert _tk_band.isdisjoint(_live_band) and _tk_band.isdisjoint(_shadow_band) \
    and _tk_band.isdisjoint(_golive_band), \
    "TK-Momentum magic band must be disjoint from live/shadow/go-live bands"
assert 999999999 in _tk_band and min(_tk_band) >= TK_MOMENTUM_MAGIC_BASE, \
    "TK-Momentum band must live in the all-nines high block (F1 == 999999999)"

# --- TK-BW2-fix2atr (2026-07-22) -------------------------------------------
# The TK-BW v2 "fixes matrix" fix2atr config -- forced (c1_tol) entries with
# ATR-frozen stops (SL 1.5xATR14, BE at 1.0xATR14, trail 2.5xATR14), M5
# CLOSED bars -- made live-runnable through the guarded executor (Task 1,
# `sentinel_engine.strategies.tk_bw2_live.tk_bw2_fix2atr_target`). Reference
# backtest: `sim-tk_bw2-m5-20260720-20260721-fix2atr` in data/research.db
# (48 trades) over the real lake window 2026-07-20 -> 2026-07-21.
#
# ENGINE PARAMS -- SINGLE SOURCE OF TRUTH: imported verbatim from the
# research runner (`scripts.research.run_tk_bw_v2_backtest`), not re-typed
# here, so the live config can NEVER drift from the backtested fix2atr
# config (pinned by `tests/strategies/test_live_configs_tomachine.py::
# test_tk_bw2_fix2atr_kwargs_match_runner_single_source_of_truth`). Imported
# lazily (module-level, but via a local function) to avoid dragging the
# runner's registry/bars-loading imports into every `live_configs_20` import
# (mirrors `tk_bw2_live._fix2atr_defaults`'s own lazy-import rationale).
def _tk_bw2_fix2atr_engine_kwargs() -> dict[str, Any]:
    from scripts.research.run_tk_bw_v2_backtest import _COMMON_PARAMS, CONFIGS
    kwargs = dict(_COMMON_PARAMS)
    kwargs.update(CONFIGS["fix2atr"])
    kwargs["symbol"] = "XAUUSD"
    return kwargs


# MAGIC: fresh 7250xx block -- band [725010..725013], clear of every other
# block in use (720xxx classic, 721xxx shadow, 724xxx go-live, 999999998+
# TK-Momentum) and of the plan-reserved 722xxx/723xxx blocks.
TK_BW2_FIX2ATR_MAGIC_BASE = 725010
CONFIG_TK_BW2_FIX2ATR: dict[str, Any] = {
    "id": "TK-BW2-fix2atr",
    "tf": "M5",
    "k": None,
    "kwargs": _tk_bw2_fix2atr_engine_kwargs(),
    "engine": "tk_bw2_fix2atr",
    "direction_filter": False,
    "magic": TK_BW2_FIX2ATR_MAGIC_BASE,
    "notes": ("TK-BW v2 fixes-matrix fix2atr: forced c1_tol=3.0 entries + "
              "ATR-frozen stops (SL 1.5xATR14, BE 1.0xATR14, trail "
              "2.5xATR14), M5 CLOSED bars only (not intrabar); reference "
              "backtest sim-tk_bw2-m5-20260720-20260721-fix2atr (48 trades); "
              "machine-2 roster addition 2026-07-22."),
}

_tk_bw2_band = {CONFIG_TK_BW2_FIX2ATR["magic"] + o for o in range(4)}
assert _tk_bw2_band.isdisjoint(_live_band) and _tk_bw2_band.isdisjoint(_shadow_band) \
    and _tk_bw2_band.isdisjoint(_golive_band) and _tk_bw2_band.isdisjoint(_tk_band), \
    "TK-BW2-fix2atr magic band must be disjoint from live/shadow/go-live/TK bands"
assert all(not (722000 <= m <= 723999) for m in _tk_bw2_band), \
    "TK-BW2-fix2atr magic band must stay clear of the reserved 722xxx/723xxx blocks"
assert min(_tk_bw2_band) == 725010 and max(_tk_bw2_band) == 725013, \
    "TK-BW2-fix2atr band must be the fresh 725010..725013 block"

# --- MACHINE-2 ROSTER "tomachine" (trader selection 2026-07-22) -----------
# The machine-2 executor's full roster: THREE named go-live configs kept
# VERBATIM (id + magic UNCHANGED) from CONFIGS_GOLIVE -- S6-K2P0, S7-TPNONE,
# SuperTrend-p14x3-M15 -- + the new CONFIG_TK_BW2_FIX2ATR. Deliberately
# EXCLUDES the FIXED4 shadow configs (CONFIGS_SHADOW), V11-M2, and
# TK-Momentum-5-8-short (trader's machine-2 selection 2026-07-22 -- the
# shadow configs were dropped from this roster; none of these three run
# here).
_TOMACHINE_GOLIVE_IDS: tuple[str, ...] = ("S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15")
_tomachine_golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE if c["id"] in _TOMACHINE_GOLIVE_IDS}
assert set(_tomachine_golive_by_id) == set(_TOMACHINE_GOLIVE_IDS), \
    "every _TOMACHINE_GOLIVE_IDS entry must exist in CONFIGS_GOLIVE"

CONFIGS_TOMACHINE: list[dict[str, Any]] = [
    *[_tomachine_golive_by_id[cid] for cid in _TOMACHINE_GOLIVE_IDS],
    CONFIG_TK_BW2_FIX2ATR,
]

assert len(CONFIGS_TOMACHINE) == 4, "tomachine roster must be exactly 4 configs"
assert len({c["id"] for c in CONFIGS_TOMACHINE}) == 4, "tomachine config ids must be unique"
assert "V11-M2" not in {c["id"] for c in CONFIGS_TOMACHINE}, \
    "tomachine roster must NOT include V11-M2 (trader's machine-2 selection 2026-07-22)"
assert "TK-Momentum-5-8-short" not in {c["id"] for c in CONFIGS_TOMACHINE}, \
    "tomachine roster must NOT include TK-Momentum (trader's machine-2 selection 2026-07-22)"
assert {c["id"] for c in CONFIGS_SHADOW}.isdisjoint({c["id"] for c in CONFIGS_TOMACHINE}), \
    "tomachine roster must NOT include any FIXED4 shadow config (trader's 2026-07-22 removal)"

_tomachine_bands: list[set[int]] = []
_seen_tomachine_magics: set[int] = set()
for _c in CONFIGS_TOMACHINE:
    _band = {_c["magic"] + _o for _o in range(4)}
    assert _seen_tomachine_magics.isdisjoint(_band), \
        f"tomachine magic band overlap at {_c['id']}"
    _seen_tomachine_magics |= _band
    _tomachine_bands.append(_band)

# --- MACHINE-1 LOCAL ROSTER "local" (trader selection 2026-07-22) ----------
# The machine-1 LOCAL executor's roster: THREE named go-live configs
# (S6-K2P0, S7-TPNONE, SuperTrend-p14x3-M15, magics 724010/724020/724070
# UNCHANGED) each sized at 0.1 lot per ficha, PLUS TK-Momentum-5-8-short
# (magic 999999998 unchanged) at 0.01 lot. Deliberately EXCLUDES V11-M2 and
# the FIXED4 shadow configs.
#
# HARD IMMUTABILITY (the whole point): the S6-K2P0 / S7-TPNONE /
# SuperTrend-p14x3-M15 dicts are SHARED BY REFERENCE across CONFIGS_GOLIVE,
# CONFIGS_GOLIVE_DEDUP and CONFIGS_TOMACHINE. Adding a per-config `volume`
# here uses INDEPENDENT deep COPIES so machine-2's `tomachine` lot (and every
# other roster) is never touched -- their configs stay volume-free (=> global
# --volume). If a `volume` key ever appeared on a shared object, tomachine's
# lot would silently become 0.1; the copies below prevent that (proven by
# tests/scripts/test_run_live_20.py's tomachine-volume-None snapshot).
#
# PER-CONFIG VOLUME: the executor's OPEN path reads `cfg.get("volume", <global
# --volume>)`, so a config WITHOUT the key behaves exactly as today. Here the
# 3 SAR/ST copies carry 0.1 and the TK copy carries 0.01.
_LOCAL_GOLIVE_IDS: tuple[str, ...] = ("S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15")
_golive_by_id_for_local = {c["id"]: c for c in CONFIGS_GOLIVE}


def _local_copy(cid: str, volume: float) -> dict[str, Any]:
    """Independent deep COPY of a shared config carrying a per-config volume.
    NEVER mutates the source dict (the immutability invariant)."""
    c = copy.deepcopy(_golive_by_id_for_local[cid])
    c["volume"] = volume
    return c


CONFIGS_LOCAL: list[dict[str, Any]] = [
    *[_local_copy(cid, 0.1) for cid in _LOCAL_GOLIVE_IDS],
    {**copy.deepcopy(CONFIG_TK_MOMENTUM), "volume": 0.01},
]

assert len(CONFIGS_LOCAL) == 4, "local roster must be exactly 4 configs"
assert [c["id"] for c in CONFIGS_LOCAL] == [
    "S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15", "TK-Momentum-5-8-short"], \
    "local roster ids must be the 3 SAR/ST configs + TK-Momentum, in order"
assert len({c["id"] for c in CONFIGS_LOCAL}) == 4, "local config ids must be unique"
assert "V11-M2" not in {c["id"] for c in CONFIGS_LOCAL}, \
    "local roster must NOT include V11-M2 (trader's machine-1 selection 2026-07-22)"
assert {c["id"] for c in CONFIGS_SHADOW}.isdisjoint({c["id"] for c in CONFIGS_LOCAL}), \
    "local roster must NOT include any FIXED4 shadow config"
assert [c["magic"] for c in CONFIGS_LOCAL] == [724010, 724020, 724070, 999999998], \
    "local roster magics must be inherited UNCHANGED (724010/724020/724070/999999998)"
# the 3 SAR/ST copies carry 0.1, TK carries 0.01.
for _c in CONFIGS_LOCAL:
    if _c["id"] == "TK-Momentum-5-8-short":
        assert _c["volume"] == 0.01, "TK-Momentum local volume must be 0.01"
    else:
        assert _c["volume"] == 0.1, f"{_c['id']} local volume must be 0.1"
# IMMUTABILITY: the SHARED source objects must NOT have gained a volume key.
for _cid in _LOCAL_GOLIVE_IDS:
    assert "volume" not in _golive_by_id_for_local[_cid], \
        f"local's 0.1 leaked into the shared {_cid} dict (immutability violated)"
assert "volume" not in CONFIG_TK_MOMENTUM, \
    "local's 0.01 leaked into the shared CONFIG_TK_MOMENTUM dict"
# pairwise magic-band disjointness.
_seen_local_magics: set[int] = set()
for _c in CONFIGS_LOCAL:
    _band = {_c["magic"] + _o for _o in range(4)}
    assert _seen_local_magics.isdisjoint(_band), \
        f"local magic band overlap at {_c['id']}"
    _seen_local_magics |= _band
