"""sentinel_engine.service.routers.jobs — /api/backtest, /api/jobs/{job_id},
/api/ingest/tokata (W0.1b), plus CT-4 `/api/jobs/backtest` + `/api/jobs/{id}`
+ `/api/jobs/stream` (B6).

Moved verbatim out of `sentinel_engine.service.app` (plan recalibration V2,
W0.1 "split app.py into routers"). `build_router(registry, lake_root, jobs,
backtest_lock)` is called once from `create_app()`; the returned `APIRouter`
is included via `app.include_router(...)` so every path stays byte-identical
to before the split. `jobs` (the same dict object as `app.state.jobs`) and
`backtest_lock` (the same `asyncio.Lock` as `app.state.backtest_lock`) are
passed by reference rather than read off `app.state` at call time, matching
how `bars.py`/`runs.py`/`strategies.py` receive their dependencies directly.

B6 (CT-4): the legacy `/api/backtest` + `GET /api/jobs/{job_id}` (in-memory
`jobs` dict, background_tasks) are UNTOUCHED -- `test_router_parity.py`
still expects both. CT-4's job queue is a SEPARATE, SQLite-backed system
(`sentinel_engine.service.jobs.JobsService`) exposed as `POST
/api/jobs/backtest` (note the different path: `/api/jobs/backtest`, not
`/api/backtest`) + `GET /api/jobs/{id}` (same path shape as the legacy route
above but a DIFFERENT status body per CT-4: `status|progress|run_id|error`)
+ `GET /api/jobs/stream` (CT-9 SSE, `job_update` events). Since both the
legacy and CT-4 routes share the `/api/jobs/{job_id}` path/method, FastAPI
matches whichever is registered FIRST -- CT-4's `get_job_ct4` handler below
is registered on `r` (this router's own APIRouter) and takes precedence,
looking up in `JobsService` first and falling back to the legacy in-memory
`jobs` dict so both callers keep working.

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
import json
import queue as _queue_mod
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from sentinel_engine.sim.lite import run_backtest_lite
from sentinel_engine.strategies.emasar import EmasarPolicy

from ..jobs import JobsError, JobsService

router = APIRouter()

# CT-9 SSE convention: heartbeat comment cadence (seconds).
_SSE_HEARTBEAT_SECONDS = 15.0

# A2: valid tier-TF names -- coverage lookups only cover these keys, same
# filter `/api/coverage` (routers/bars.py) applies to the raw manifest.
_VALID_TF_NAMES = frozenset({"M1", "M2", "M5", "M15", "H1", "D"})


class BacktestJobRequest(BaseModel):
    variant_id: str
    symbol: str
    tf: str
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    preregistro_id: str | None = None
    exploratory: bool = False

    model_config = {"populate_by_name": True}


def _load_manifest(lake_root: Path) -> dict:
    manifest_path = Path(lake_root) / "manifest.json"
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}


def _make_coverage_check(lake_root: Path):
    """CT-4 422 validation: the requested `[from, to]` window must overlap
    the CT-1 lake coverage for `(symbol, tf)`. Missing symbol/tf -> no
    coverage -> always rejected (422), matching CT-1's "unknown" semantics."""

    def _check(symbol: str, tf: str, from_: str | None, to: str | None) -> bool:
        if tf not in _VALID_TF_NAMES:
            return False
        manifest = _load_manifest(lake_root)
        entry = manifest.get(symbol, {}).get(tf)
        if not isinstance(entry, dict):
            return False
        first = entry.get("first")
        last = entry.get("last")
        if first is None or last is None:
            return False
        from sentinel_engine.service.app import _parse_flexible_ts

        try:
            ts_from = _parse_flexible_ts(from_)
            ts_to = _parse_flexible_ts(to)
        except (ValueError, TypeError):
            return False
        from_epoch = int(ts_from.timestamp()) if ts_from is not None else first
        to_epoch = int(ts_to.timestamp()) if ts_to is not None else last
        # Window must overlap the covered range, not fall entirely outside it.
        return from_epoch <= last and to_epoch >= first

    return _check


def build_router(registry, lake_root, jobs: dict, backtest_lock: asyncio.Lock) -> APIRouter:
    from ..app import BacktestRequest, _api_error

    r = APIRouter()

    jobs_service = JobsService(registry, lake_root, coverage_check=_make_coverage_check(lake_root))

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

    @r.post("/api/jobs/backtest")
    def post_jobs_backtest(payload: BacktestJobRequest):
        try:
            job_id = jobs_service.submit_backtest(
                payload.variant_id, payload.symbol, payload.tf,
                payload.from_, payload.to,
                preregistro_id=payload.preregistro_id,
                exploratory=payload.exploratory,
            )
        except JobsError as exc:
            return _api_error(422, "window_outside_coverage", str(exc))
        return {"job_id": job_id}

    # Registered BEFORE the `/api/jobs/{job_id}` catch-all below: FastAPI
    # matches routes in registration order, and a bare `/api/jobs/{job_id}`
    # would otherwise swallow `/api/jobs/stream` (treating "stream" as a
    # job_id path param).
    @r.get("/api/jobs/stream")
    async def get_jobs_stream():
        """CT-9 SSE: `job_update` events, one per row change on ANY job
        managed by `jobs_service` (CT-4 does not scope the stream to a
        single job_id)."""
        sub_queue = jobs_service.subscribe()

        def _poll():
            try:
                return sub_queue.get(True, _SSE_HEARTBEAT_SECONDS)
            except _queue_mod.Empty:
                return None

        async def event_stream():
            yield "retry: 3000\n\n"
            try:
                while True:
                    body = await asyncio.to_thread(_poll)
                    if body is None:
                        yield ": hb\n\n"
                    else:
                        data = json.dumps(body)
                        yield f"event: job_update\ndata: {data}\n\n"
            finally:
                jobs_service.unsubscribe(sub_queue)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @r.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        """Merged handler: CT-4's SQLite-backed `JobsService` (job ids
        `jobrun-*`, from `POST /api/jobs/backtest`) is checked FIRST; if not
        found there, falls back to the legacy in-memory `jobs` dict (job ids
        `job-*`, from `POST /api/backtest`) so both callers keep working
        through the SAME path (`test_router_parity.py` only allows one route
        registered at this path/method/name)."""
        ct4_job = jobs_service.get_job(job_id)
        if ct4_job is not None:
            return ct4_job

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
