"""sentinel_engine.service.routers.strategies — /api/strategies*, /api/variants (W0.1a).

Moved verbatim out of `sentinel_engine.service.app` (plan recalibration V2,
W0.1 "split app.py into routers"). `build_router(registry)` is called once
from `create_app()`; the returned `APIRouter` is included via
`app.include_router(...)` so every path stays byte-identical to before the
split.

Deliberately NOT using `from __future__ import annotations` in this module
(unlike the rest of the package): FastAPI resolves each endpoint's parameter
annotations via `typing.get_type_hints()` against the enclosing function's
`__globals__` when annotations are stored as deferred strings — since
`VariantCreateRequest`/`StrategyEstadoRequest` are only reachable through a
lazy (function-local) import of `sentinel_engine.service.app` (a top-level
import would be circular — `app.py` imports this module at its own
top-level to register the router), deferred string annotations would
resolve to nothing and FastAPI would silently treat `payload` as an
unresolvable/query param (422 "field required") instead of a JSON body
model. Without the future-import, Python evaluates annotations eagerly at
function-definition time (inside `build_router`, after the lazy import),
capturing the real class object directly — no globals lookup needed.
"""

import json
from typing import Any

from fastapi import APIRouter

from ...research import scorecard as scorecard_mod

router = APIRouter()


# --- chart-spec derivation (Task 1a: GET /api/strategies/chart-specs) -----
# Read-only projection of `sentinel_engine.strategies.live_configs_20` rosters
# into { indicators, rules } the frontend chart/description panel consumes.
# The source module is imported lazily (inside the route closure, following
# this module's existing lazy-import convention) and NEVER mutated.

_INDICATOR_COLORS = {
    "EMA": "#42a5f5",
    "SMA": "#ffa726",
    "SAR": "#ab47bc",
    "SUPERTREND": "#26a69a",
    "MOM": "#ef5350",
}


def _indicator(kind: str, params: dict[str, Any], label: str, pane: str = "price") -> dict[str, Any]:
    return {
        "type": kind,
        "params": params,
        "label": label,
        "pane": pane,
        "color": _INDICATOR_COLORS.get(kind, "#888888"),
    }


def _simular_variant_indicators(config: dict[str, Any]) -> list[dict[str, Any]]:
    kwargs = config.get("kwargs") or {}
    ema_fast = kwargs.get("ema_fast", 8)
    ema_slow = kwargs.get("ema_slow", 20)
    indicators = [
        _indicator("EMA", {"period": ema_fast}, f"EMA {ema_fast}"),
        _indicator("EMA", {"period": ema_slow}, f"EMA {ema_slow}"),
    ]
    if kwargs.get("sar_adaptive"):
        sar_params = {
            "adaptive": True,
            "sar_fast": kwargs.get("sar_fast"),
            "sar_slow": kwargs.get("sar_slow"),
            "vol_regime_window": kwargs.get("vol_regime_window"),
        }
        sar_label = "SAR adaptive"
    else:
        sar_params = {"step": kwargs.get("sar_step"), "max": kwargs.get("sar_max")}
        sar_label = "SAR"
    indicators.append(_indicator("SAR", sar_params, sar_label))
    if config.get("direction_filter"):
        indicators.append(_indicator(
            "SUPERTREND", {"atr_period": 14, "mult": 3.0, "tf": "M15"},
            "SuperTrend 14x3 (M15 direction mask)",
        ))
    return indicators


def _supertrend_always_in_indicators() -> list[dict[str, Any]]:
    return [_indicator(
        "SUPERTREND", {"atr_period": 14, "mult": 3.0},
        "SuperTrend 14x3 (SL)",
    )]


def _tk_momentum_indicators(config: dict[str, Any]) -> list[dict[str, Any]]:
    kwargs = config.get("kwargs") or {}
    ma_fast = kwargs.get("ma_fast", 5)
    ma_slow = kwargs.get("ma_slow", 8)
    mom_period = kwargs.get("mom_period", 2)
    return [
        _indicator("SMA", {"period": ma_fast}, f"SMA {ma_fast}"),
        _indicator("SMA", {"period": ma_slow}, f"SMA {ma_slow}"),
        _indicator("MOM", {"period": mom_period, "line": 100},
                   f"MOM {mom_period}", pane="sub"),
    ]


def _indicators_for(config: dict[str, Any]) -> list[dict[str, Any]]:
    engine = config.get("engine", "simular_variant")
    if engine == "supertrend_always_in":
        return _supertrend_always_in_indicators()
    if engine == "tk_momentum":
        return _tk_momentum_indicators(config)
    return _simular_variant_indicators(config)


def _simular_variant_rules(config: dict[str, Any]) -> dict[str, Any]:
    kwargs = config.get("kwargs") or {}
    entry = (
        f"EMA{kwargs.get('ema_fast', 8)}/EMA{kwargs.get('ema_slow', 20)} + SAR confirm, "
        f"confirm_count={kwargs.get('confirm_count')} mode={kwargs.get('confirm_mode')}"
    )
    long_side = "EMA fast > EMA slow with SAR/confirm gate"
    short_side = "EMA fast < EMA slow with SAR/confirm gate"
    if config.get("direction_filter"):
        note = config.get("notes") or "SuperTrend-M15 direction mask required"
        long_side = f"{long_side}; direction_filter: {note}"
        short_side = f"{short_side}; direction_filter: {note}"

    exit_ = {
        "sl": f"range init SL k={kwargs.get('init_sl_range_k')}",
        "tp": (f"f1_tp_r={kwargs['f1_tp_r']}" if "f1_tp_r" in kwargs
               else (f"be_at_r={kwargs['be_at_r']}" if "be_at_r" in kwargs else "none")),
        "trailing": {
            "f1_trail_pips": kwargs.get("f1_trail_pips"),
            "f2_trail_pips": kwargs.get("f2_trail_pips"),
            "f3_trail_pips": kwargs.get("f3_trail_pips"),
            "trail_atr_floor_k": kwargs.get("trail_atr_floor_k"),
        },
        "reentry": {
            "enable": kwargs.get("reentry_enable", False),
            "max": kwargs.get("reentry_max"),
        },
        "stop_and_reverse": kwargs.get("stop_and_reverse", False),
        "blocked_hours": sorted(kwargs["blocked_hours"]) if kwargs.get("blocked_hours") else None,
        "ac_modulate": kwargs.get("ac_modulate", False),
        "ac_modulate_factor": kwargs.get("ac_modulate_factor"),
        "active_fichas": kwargs.get("active_fichas"),
    }
    return {"entry": entry, "long": long_side, "short": short_side, "exit": exit_}


def _supertrend_always_in_rules() -> dict[str, Any]:
    entry = "always-in: long when price above SuperTrend line, short below, flip on cross"
    return {
        "entry": entry,
        "long": "price above SuperTrend(14,3.0) line",
        "short": "price below SuperTrend(14,3.0) line",
        "exit": {
            "sl": "SuperTrend line",
            "tp": "none",
            "trailing": None,
            "reentry": None,
            "stop_and_reverse": True,
            "blocked_hours": None,
            "ac_modulate": False,
            "ac_modulate_factor": None,
            "active_fichas": 1,
        },
    }


def _tk_momentum_rules(config: dict[str, Any]) -> dict[str, Any]:
    kwargs = config.get("kwargs") or {}
    trail_usd = kwargs.get("trail_usd", 0.5)
    entry = "SMA5/SMA8 regime + MOM2 100-line cross"
    return {
        "entry": entry,
        "long": "SMA5 > SMA8 (alcista) AND MOM2 > 100",
        "short": "SMA5 < SMA8 (bajista) AND MOM2 < 100",
        "exit": {
            "sl": f"trailing {trail_usd} USD",
            "tp": "none",
            "trailing": {"trail_usd": trail_usd},
            "reentry": {"enable": False, "max": None},
            "stop_and_reverse": False,
            "blocked_hours": None,
            "ac_modulate": False,
            "ac_modulate_factor": None,
            "active_fichas": 1,
        },
    }


def _rules_for(config: dict[str, Any]) -> dict[str, Any]:
    engine = config.get("engine", "simular_variant")
    if engine == "supertrend_always_in":
        rules = _supertrend_always_in_rules()
    elif engine == "tk_momentum":
        rules = _tk_momentum_rules(config)
    else:
        rules = _simular_variant_rules(config)
    rules["tf"] = config.get("tf")
    rules["engine"] = engine
    rules["magic"] = config.get("magic")
    rules["notes"] = config.get("notes", "")
    return rules


def _chart_spec(config: dict[str, Any]) -> dict[str, Any]:
    engine = config.get("engine", "simular_variant")
    return {
        "id": config["id"],
        "tf": config.get("tf"),
        "engine": engine,
        "magic": config.get("magic"),
        "indicators": _indicators_for(config),
        "rules": _rules_for(config),
        "notes": config.get("notes", ""),
    }


def _build_chart_specs() -> dict[str, dict[str, Any]]:
    """De-duplicated union of every `live_configs_20` roster, keyed by config
    `id`. When the same id appears in more than one roster (only V11-M2 in
    practice, across CONFIGS_20/CONFIGS_GOLIVE), the go-live/dedup/TK
    definition wins -- those rosters are consulted before CONFIGS_20."""
    from ...strategies.live_configs_20 import (
        CONFIG_TK_MOMENTUM,
        CONFIGS_20,
        CONFIGS_GOLIVE,
        CONFIGS_GOLIVE_DEDUP,
    )

    specs: dict[str, dict[str, Any]] = {}
    for roster in (
        [CONFIG_TK_MOMENTUM],
        CONFIGS_GOLIVE_DEDUP,
        CONFIGS_GOLIVE,
        CONFIGS_20,
    ):
        for config in roster:
            cid = config["id"]
            if cid not in specs:
                specs[cid] = _chart_spec(config)
    return specs


def build_router(registry) -> APIRouter:
    from ..app import (
        StrategyEstadoRequest,
        VariantCreateRequest,
        _api_error,
        _display_color,
    )

    r = APIRouter()

    @r.get("/api/strategies")
    def get_strategies() -> dict[str, Any]:
        rows = registry.query_strategies()
        for row in rows:
            row["display_color"] = _display_color(row.get("color_idx"))
        return {"strategies": rows}

    @r.get("/api/strategies/chart-specs")
    def get_strategies_chart_specs() -> dict[str, Any]:
        return {"specs": _build_chart_specs()}

    @r.post("/api/variants")
    def post_variant_create(payload: VariantCreateRequest):
        strategy = registry.get_strategy(payload.strategy_id)
        if strategy is None:
            return _api_error(404, "strategy_not_found", f"unknown strategy_id: {payload.strategy_id}")

        schema_json = strategy.get("param_schema_json") or "{}"
        try:
            schema = json.loads(schema_json)
        except (TypeError, ValueError):
            schema = {}
        if schema:
            unknown = [k for k in payload.params_delta if k not in schema]
            if unknown:
                return _api_error(
                    400, "invalid_params_delta",
                    f"params_delta has keys not in param_schema: {unknown}",
                )

        instrumento = payload.instrumento or ""
        variant_id = f"{strategy['familia']}_{instrumento}_{payload.variant_suffix}"
        if registry.variant_exists(variant_id):
            return _api_error(409, "variant_exists", f"variant already exists: {variant_id}")

        registry.insert_variant(
            payload.strategy_id, variant_id, payload.params_delta,
            payload.tf, payload.instrumento, payload.modo_salida,
        )
        try:
            registry.allocate_magic(payload.strategy_id, variant_id)
        except ValueError as exc:
            return _api_error(400, "magic_allocation_failed", str(exc))
        registry.audit("api", "variant_created", {
            "strategy_id": payload.strategy_id, "variant_id": variant_id,
            "params_delta": payload.params_delta,
        })
        return {"variant_id": variant_id}

    _VALID_ESTADOS = {"activa", "pausada", "graduada"}

    @r.post("/api/strategies/{strategy_id}/estado")
    def post_strategy_estado(strategy_id: str, payload: StrategyEstadoRequest):
        if registry.get_strategy(strategy_id) is None:
            return _api_error(404, "strategy_not_found", f"unknown strategy_id: {strategy_id}")
        if payload.estado not in _VALID_ESTADOS:
            return _api_error(
                400, "invalid_estado",
                f"estado must be one of {sorted(_VALID_ESTADOS)}: got {payload.estado!r}",
            )
        registry.set_strategy_estado(strategy_id, payload.estado)
        registry.audit("api", "strategy_estado_changed", {
            "strategy_id": strategy_id, "estado": payload.estado,
        })
        return {"strategy_id": strategy_id, "estado": payload.estado}

    @r.get("/api/strategies/{strategy_id}/scorecard")
    def get_strategy_scorecard(strategy_id: str, tf: str = "M5"):
        card = scorecard_mod.build_scorecard(registry, strategy_id, tf=tf)
        if card is None:
            return _api_error(404, "strategy_not_found", f"unknown strategy_id: {strategy_id}")
        return card

    return r
