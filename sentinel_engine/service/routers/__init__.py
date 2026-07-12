"""sentinel_engine.service.routers — APIRouter modules split out of app.py
(W0.1, plan recalibration V2).

Each submodule exposes a module-level `router: fastapi.APIRouter` that
`create_app()` includes via `app.include_router(...)`. No URL prefixes are
declared here — every route keeps its exact original path (e.g.
`/api/bars`), so splitting into routers is behavior-preserving by
construction.
"""
from __future__ import annotations
