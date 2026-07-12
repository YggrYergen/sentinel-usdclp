"""sentinel_engine.service.routers.jobs — /api/backtest, /api/jobs/{job_id},
/api/ingest/tokata (W0.1b).

Moved verbatim out of `sentinel_engine.service.app` (plan recalibration V2,
W0.1 "split app.py into routers"). `build_router(registry, lake_root, jobs,
backtest_lock)` is called once from `create_app()`; the returned `APIRouter`
is included via `app.include_router(...)` so every path stays byte-identical
to before the split. `jobs` (the same dict object as `app.state.jobs`) and
`backtest_lock` (the same `asyncio.Lock` as `app.state.backtest_lock`) are
passed by reference rather than read off `app.state` at call time, matching
how `bars.py`/`runs.py`/`strategies.py` receive their dependencies directly.

Deliberately NOT using `from __future__ import annotations` (same reason as
`routers/strategies.py`): `BacktestRequest` is only reachable through a lazy
(function-local) import of `sentinel_engine.service.app` (a top-level import
would be circular). Deferred string annotations would resolve to nothing and
FastAPI would silently mis-treat `payload` as an unresolvable param instead
of a JSON body model. Without the future-import, Python evaluates
annotations eagerly at function-definition time (inside `build_router`,
after the lazy import).
"""

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks

from sentinel_engine.sim.lite import run_backtest_lite
from sentinel_engine.strategies.emasar import EmasarPolicy

router = APIRouter()


def build_router(registry, lake_root, jobs: dict, backtest_lock: asyncio.Lock) -> APIRouter:
    from ..app import BacktestRequest, _api_error

    r = APIRouter()

    def _build_policy(variant: dict[str, Any]):
        """Policy dispatch by `familia` — only EMASAR exists in this lean
        M2.5 slice; other families are rejected with a clear error rather
        than silently defaulting to the wrong strategy."""
        familia = (variant.get("familia") or "").lower()
        if familia != "emasar":
            raise ValueError(f"no backtest-lite policy registered for familia: {familia!r}")
        return EmasarPolicy(variant.get("params_delta") or {})

    def _run_backtest_job(job_id: str, variant_id: str, symbol: str, tf: str,
                           desde: str | None, hasta: str | None) -> None:
        jobs[job_id]["status"] = "running"
        try:
            variant = registry.get_variant(variant_id)
            if variant is None:
                raise ValueError(f"unknown variant_id: {variant_id}")
            policy = _build_policy(variant)
            run, trades = run_backtest_lite(
                policy, symbol, tf, desde, hasta, lake_root=lake_root,
            )
            run_id = f"sim-{uuid.uuid4().hex[:16]}"
            run["run_id"] = run_id
            run["variant_id"] = variant_id
            for t in trades:
                t["trade_id"] = f"simtr-{uuid.uuid4().hex[:16]}"
            registry.insert_run(run)
            registry.insert_trades(run_id, trades)
            registry.audit("api", "backtest_done", {
                "job_id": job_id, "variant_id": variant_id, "run_id": run_id,
                "trades": len(trades),
            })
            jobs[job_id]["status"] = "done"
            jobs[job_id]["run_id"] = run_id
        except Exception as exc:  # noqa: BLE001 - job errors are reported via GET /api/jobs, never raised
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(exc)
            registry.audit("api", "backtest_failed", {"job_id": job_id, "variant_id": variant_id, "error": str(exc)})

    async def _run_backtest_job_locked(job_id: str, variant_id: str, symbol: str, tf: str,
                                        desde: str | None, hasta: str | None) -> None:
        async with backtest_lock:
            await asyncio.to_thread(_run_backtest_job, job_id, variant_id, symbol, tf, desde, hasta)

    @r.post("/api/backtest")
    def post_backtest(payload: BacktestRequest, background_tasks: BackgroundTasks):
        if registry.get_variant(payload.variant_id) is None:
            return _api_error(404, "variant_not_found", f"unknown variant_id: {payload.variant_id}")
        job_id = f"job-{uuid.uuid4().hex[:16]}"
        jobs[job_id] = {"status": "queued", "run_id": None}
        background_tasks.add_task(
            _run_backtest_job_locked, job_id, payload.variant_id, payload.symbol,
            payload.tf, payload.desde, payload.hasta,
        )
        return {"job_id": job_id, "status": "queued"}

    @r.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            return _api_error(404, "job_not_found", f"unknown job_id: {job_id}")
        out = {"status": job["status"]}
        if job.get("run_id"):
            out["run_id"] = job["run_id"]
        if job.get("error"):
            out["error"] = job["error"]
        return out

    @r.post("/api/ingest/tokata")
    def post_ingest_tokata(payload: dict[str, Any] | None = None):
        from sentinel_engine.ingest_tokata.runner import import_all

        payload = payload or {}
        root_raw = payload.get("tokata_root") or "D:/WebDev/TOKATA"
        root = Path(root_raw)
        if not root.exists() or not root.is_dir():
            return _api_error(404, "tokata_root_not_found", f"tokata_root does not exist: {root}")
        try:
            report = import_all(root, registry)
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the client
            return _api_error(500, "ingest_failed", str(exc))
        return {
            "files": report.files,
            "rows_new": report.rows_new,
            "rows_skipped": report.rows_skipped,
            "errors": report.errors,
        }

    return r
