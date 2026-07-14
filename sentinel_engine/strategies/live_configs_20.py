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
"""
from __future__ import annotations

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
