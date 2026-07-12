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
