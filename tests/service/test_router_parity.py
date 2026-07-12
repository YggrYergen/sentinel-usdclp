"""tests/service/test_router_parity.py — route-set regression gate (W0.1b).

`sentinel_engine.service.app` was split into per-domain routers under
`sentinel_engine.service.routers.*` (plan recalibration V2, W0.1 "split
app.py into routers", W0.1a + W0.1b). Every endpoint's URL/method/name must
stay byte-identical across the split — this test hardcodes the exact route
set observed by introspecting `app.routes` on the post-split app (verified
against the pre-split app before W0.1b's edits landed) so that any future
accidental deletion/rename of a route fails loudly here instead of being
discovered downstream in the frontend.
"""
from __future__ import annotations

from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import Mount, Route

# Derived by introspecting `app.routes` on the real app (FakeFeed-backed,
# autostart_loop=False) immediately after the W0.1b router split — see
# task report. Each tuple is (route_type, path, sorted(methods) or None,
# route.name).
EXPECTED_ROUTES = {
    ("Route", "/openapi.json", ("GET", "HEAD"), "openapi"),
    ("Route", "/docs", ("GET", "HEAD"), "swagger_ui_html"),
    ("Route", "/docs/oauth2-redirect", ("GET", "HEAD"), "swagger_ui_redirect"),
    ("Route", "/redoc", ("GET", "HEAD"), "redoc_html"),
    ("APIRoute", "/api/bars", ("GET",), "get_bars"),
    ("APIWebSocketRoute", "/ws/ticks", None, "ticks_ws"),
    ("APIRoute", "/api/runs", ("GET",), "get_runs"),
    ("APIRoute", "/api/runs/{run_id}", ("GET",), "get_run"),
    ("APIRoute", "/api/runs/{run_id}/trades", ("GET",), "get_run_trades"),
    ("APIRoute", "/api/runs/{run_id}/indicators", ("GET",), "get_run_indicators"),
    ("APIRoute", "/api/forward/sessions", ("GET",), "get_forward_sessions"),
    ("APIRoute", "/api/forward/{session_id}/trades", ("GET",), "get_forward_session_trades"),
    ("APIRoute", "/api/strategies", ("GET",), "get_strategies"),
    ("APIRoute", "/api/variants", ("POST",), "post_variant_create"),
    ("APIRoute", "/api/strategies/{strategy_id}/estado", ("POST",), "post_strategy_estado"),
    ("APIRoute", "/models", ("GET",), "get_models"),
    ("APIRoute", "/chat", ("POST",), "post_chat"),
    ("APIRoute", "/api/backtest", ("POST",), "post_backtest"),
    ("APIRoute", "/api/jobs/{job_id}", ("GET",), "get_job"),
    ("APIRoute", "/api/ingest/tokata", ("POST",), "post_ingest_tokata"),
    ("APIRoute", "/snapshot", ("GET",), "get_snapshot"),
    ("APIRoute", "/config", ("GET",), "get_config"),
    ("APIRoute", "/levers", ("GET",), "get_levers"),
    ("APIWebSocketRoute", "/stream", None, "stream_ws"),
    ("APIRoute", "/variants", ("GET",), "get_variants"),
    ("APIRoute", "/variant/diff", ("GET",), "get_variant_diff"),
    ("APIRoute", "/study/latest", ("GET",), "get_study_latest"),
    ("APIRoute", "/study/{study_id}", ("GET",), "get_study"),
    ("APIRoute", "/calendar", ("GET",), "get_calendar"),
    ("APIRoute", "/replay/control", ("POST",), "post_replay_control"),
    ("APIRoute", "/variant", ("POST",), "post_variant"),
    ("APIRoute", "/variant/branch", ("POST",), "post_variant_branch"),
    ("APIRoute", "/study", ("POST",), "post_study"),
    ("APIRoute", "/fleet", ("POST",), "post_fleet"),
    ("APIWebSocketRoute", "/replay", None, "replay_ws"),
    ("Mount", "", None, "web"),
}

EXPECTED_PATHS = {path for (_, path, _, _) in EXPECTED_ROUTES if path}


def _route_key(route) -> tuple[str, str | None, tuple[str, ...] | None, str | None]:
    type_name = type(route).__name__
    path = getattr(route, "path", None)
    methods = getattr(route, "methods", None)
    methods_key = tuple(sorted(methods)) if methods else None
    name = getattr(route, "name", None)
    return (type_name, path, methods_key, name)


def test_all_expected_routes_present(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    actual_routes = {_route_key(r) for r in app.routes}
    missing = EXPECTED_ROUTES - actual_routes
    assert not missing, f"routes missing/changed after router split: {missing}"


def test_all_expected_paths_present(app_factory):
    """Belt-and-suspenders path-only check (ignores method/name drift so a
    genuine method addition doesn't mask a path deletion)."""
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    actual_paths = {getattr(r, "path", None) for r in app.routes} - {None}
    missing = EXPECTED_PATHS - actual_paths
    assert not missing, f"paths missing after router split: {missing}"


def test_no_route_types_are_unexpected_stub_routers():
    """Sanity check that the well-known route/websocket/mount classes are
    the ones actually referenced above (guards against a future FastAPI
    upgrade silently changing route class names, which would make this
    test vacuously pass)."""
    seen_types = {t for (t, _, _, _) in EXPECTED_ROUTES}
    assert seen_types == {"Route", "APIRoute", "APIWebSocketRoute", "Mount"}
    assert Route.__name__ == "Route"
    assert APIRoute.__name__ == "APIRoute"
    assert APIWebSocketRoute.__name__ == "APIWebSocketRoute"
    assert Mount.__name__ == "Mount"
