"""sentinel_engine.service.routers.system — leftovers: /snapshot, /config,
/levers, /stream (WS), gated placeholder endpoints, /replay (WS), and the
static-web mount (W0.1b).

Moved verbatim out of `sentinel_engine.service.app` (plan recalibration V2,
W0.1 "split app.py into routers"). `build_router(runners, broadcaster)` is
called once from `create_app()`; the returned `APIRouter` is included via
`app.include_router(...)` so every path stays byte-identical to before the
split. `mount_static(app, web_dir)` reproduces the original static-files
mount (kept as a separate helper since a `StaticFiles` mount isn't an
`APIRouter` route and must be attached to the `FastAPI` app directly).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from sentinel_engine.config import config_hash
from sentinel_engine.opt.levers import LEVER_GROUPS, priors_for

router = APIRouter()

# Asset-version token (W0.2): index.html ships with the literal `__ASSET_V__`
# in every `?v=...` query string instead of a hand-bumped date string.
# `mount_static()` intercepts `/` and `/index.html` (added to the router
# *before* the StaticFiles catch-all mount, so Starlette matches it first),
# reads index.html fresh off disk on every request (no disk mutation),
# and substitutes the token for `compute_asset_version(web_dir)` before
# returning the response. Cache is lazy + per-process: the version is
# computed on the first request that needs it and reused after that (an app
# restart is what "bumps" the version in production; tests call
# `compute_asset_version()` directly to sidestep the cache).
ASSET_VERSION_TOKEN = "__ASSET_V__"

_asset_version_cache: dict[Path, str] = {}


def compute_asset_version(web_dir: Path) -> str:
    """First 10 hex chars of sha1(str(max mtime of web/**/*.js + web/**/*.css)).

    Recomputes every call (no caching here) so tests can monkeypatch mtimes
    and observe a changed version without reimporting the module.
    """
    mtimes = [p.stat().st_mtime for p in web_dir.rglob("*.js")]
    mtimes += [p.stat().st_mtime for p in web_dir.rglob("*.css")]
    latest = max(mtimes) if mtimes else 0.0
    digest = hashlib.sha1(str(latest).encode("utf-8")).hexdigest()
    return digest[:10]


def _cached_asset_version(web_dir: Path) -> str:
    version = _asset_version_cache.get(web_dir)
    if version is None:
        version = compute_asset_version(web_dir)
        _asset_version_cache[web_dir] = version
    return version


def _gated(capability: str) -> JSONResponse:
    """Every gated route (spec §6) — replay/variant-registry/study/fleet/
    calendar orchestration is future work (P2/P4/P6); this contract lets
    the frontend's gating probes render a labeled placeholder instead of
    a 404/blocked UI (spec §10 acceptance gate #6)."""
    return JSONResponse(
        status_code=501,
        content={"error": "not_implemented", "capability": capability},
    )


def build_router(runners: dict, broadcaster) -> APIRouter:
    r = APIRouter()

    def _resolve(instrument: str | None):
        name = instrument or next(iter(runners))
        runner = runners.get(name)
        if runner is None:
            raise HTTPException(status_code=404, detail=f"unknown instrument: {name}")
        return runner

    @r.get("/snapshot")
    def get_snapshot(instrument: str | None = None) -> dict:
        runner = _resolve(instrument)
        if runner.latest is None:
            raise HTTPException(status_code=503, detail="snapshot not ready")
        return runner.latest

    @r.get("/config")
    def get_config(instrument: str | None = None) -> dict[str, Any]:
        runner = _resolve(instrument)
        return {
            "instrument": runner.name,
            "config_hash": config_hash(runner.cfg),
            "config": _asdict_cfg(runner.cfg),
            "instruments": list(runners.keys()),
        }

    @r.get("/levers")
    def get_levers(instrument: str | None = None) -> dict[str, Any]:
        runner = _resolve(instrument)
        priors = priors_for(runner.cfg)
        groups = []
        for group in LEVER_GROUPS:
            params = []
            for p in group.params:
                params.append({
                    "name": p.name,
                    "lo": p.low,
                    "hi": p.high,
                    "is_int": p.is_int,
                    "production_value": priors[group.name][p.name],
                })
            groups.append({"name": group.name, "params": params})
        return {"instrument": runner.name, "groups": groups}

    @r.websocket("/stream")
    async def stream_ws(websocket: WebSocket, instrument: str | None = None) -> None:
        name = instrument or next(iter(runners))
        if name not in runners:
            await websocket.close(code=4404)
            return
        await broadcaster.connect(websocket, name)
        try:
            runner = runners[name]
            if runner.latest is not None:
                await websocket.send_json(runner.latest)
            while True:
                # Keepalive: client need not send anything meaningful; this
                # just parks the coroutine until disconnect. Broadcasts are
                # pushed independently by the background loop via `send_json`
                # inside Broadcaster.broadcast.
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            broadcaster.disconnect(websocket, name)

    @r.get("/variants")
    def get_variants() -> JSONResponse:
        return _gated("variant_registry")

    @r.get("/variant/diff")
    def get_variant_diff(a: str | None = None, b: str | None = None) -> JSONResponse:
        return _gated("variant_registry")

    @r.get("/study/latest")
    def get_study_latest(instrument: str | None = None) -> JSONResponse:
        return _gated("study")

    @r.get("/study/{study_id}")
    def get_study(study_id: str) -> JSONResponse:
        return _gated("study")

    @r.get("/calendar")
    def get_calendar(within: str | None = None) -> JSONResponse:
        return _gated("calendar")

    @r.post("/replay/control")
    def post_replay_control(payload: dict) -> JSONResponse:
        return _gated("replay")

    @r.post("/variant")
    def post_variant(payload: dict) -> JSONResponse:
        return _gated("variant_registry")

    @r.post("/variant/branch")
    def post_variant_branch(payload: dict) -> JSONResponse:
        return _gated("variant_registry")

    @r.post("/study")
    def post_study(payload: dict) -> JSONResponse:
        return _gated("study")

    @r.post("/fleet")
    def post_fleet(payload: dict) -> JSONResponse:
        return _gated("fleet")

    @r.websocket("/replay")
    async def replay_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"error": "not_implemented", "capability": "replay"})
        await websocket.close()

    return r


def _asdict_cfg(cfg) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(cfg)


def mount_static(app, web_dir: Path) -> None:
    """Reproduces the original static-files mount verbatim: `no-cache`
    (revalidate every time), NOT `no-store` — the browser still keeps a
    copy but must revalidate via ETag/Last-Modified on each load, so
    StaticFiles returns 304 when unchanged and fresh 200 the moment a file
    is edited. Without this, StaticFiles sends no Cache-Control and browsers
    heuristically serve stale app.js/style.css from memory cache on a plain
    F5 — making edits appear to have "no effect" until a hard reload. This
    keeps local dev edits always visible."""
    if not web_dir.exists():
        return

    index_path = web_dir / "index.html"

    def _serve_index() -> HTMLResponse:
        html = index_path.read_text(encoding="utf-8")
        version = _cached_asset_version(web_dir)
        html = html.replace(ASSET_VERSION_TOKEN, version)
        return HTMLResponse(content=html, headers={"Cache-Control": "no-cache"})

    if index_path.exists():
        @app.get("/", include_in_schema=False)
        def _get_root() -> HTMLResponse:
            return _serve_index()

        @app.get("/index.html", include_in_schema=False)
        def _get_index_html() -> HTMLResponse:
            return _serve_index()

    class _NoCacheStatic(StaticFiles):
        async def get_response(self, path, scope):
            response = await super().get_response(path, scope)
            response.headers["Cache-Control"] = "no-cache"
            return response

    app.mount("/", _NoCacheStatic(directory=str(web_dir), html=True), name="web")
