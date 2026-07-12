"""sentinel_engine.service.jobs — CT-4 backtest job queue (B6).

`JobsService` owns:

- the `jobs` SQLite table (registry migration lives in
  `sentinel_engine.research.registry2.ResearchRegistry._migrate_additive`,
  applied on every registry construction, including boot -- any job left
  `queued`/`running` from a prior process is marked `error:"interrupted"`
  there, BEFORE this service ever touches the table).
- a single background worker thread consuming an in-process `queue.Queue`
  (CT-4: "Worker pool size 1") that runs backtest jobs one at a time via
  `sentinel_engine.sim.lite.run_backtest_lite` (the same M2.7 entry point
  `routers/jobs.py`'s legacy `/api/backtest` already uses).
- a broadcaster (`subscribe`/`unsubscribe`/row-update push) so
  `GET /api/jobs/stream` (CT-9 SSE, `job_update` events) can fan out every
  row change without polling the DB.

Kept deliberately dependency-free (stdlib `threading`/`queue` only, no new
deps) and framework-agnostic -- the SSE/HTTP wiring lives in
`routers/jobs.py`, this module only owns state + the worker loop.
"""
from __future__ import annotations

import json
import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from ..sim.lite import run_backtest_lite
from ..strategies.emasar import EmasarPolicy


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobsError(ValueError):
    """Raised for CT-4's 422 window-vs-coverage validation failure."""


def _build_policy(variant: dict[str, Any]):
    familia = (variant.get("familia") or "").lower()
    if familia != "emasar":
        raise ValueError(f"no backtest-lite policy registered for familia: {familia!r}")
    return EmasarPolicy(variant.get("params_delta") or {})


class JobsService:
    """Backtest job queue: SQLite-backed rows (`registry`'s `jobs` table) +
    a single consumer thread + an SSE broadcaster.

    `runner` is injectable (tests pass a stub instead of the real
    `run_backtest_lite` path) -- signature: `runner(variant, symbol, tf,
    desde, hasta, progress_cb) -> (run_dict, trades)`.
    """

    def __init__(
        self,
        registry,
        lake_root,
        coverage_check: Callable[[str, str, int | None, int | None], bool] | None = None,
        runner: Callable[..., tuple[dict, list]] | None = None,
    ) -> None:
        self._registry = registry
        self._lake_root = lake_root
        self._coverage_check = coverage_check
        self._runner = runner or self._default_runner
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._subscribers: list["queue.Queue[dict]"] = []
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    def _connect(self):
        return self._registry._connect()  # noqa: SLF001 - same connection pattern registry itself uses internally

    def _row_to_dict(self, row) -> dict[str, Any]:
        return {
            "status": row[0],
            "progress": row[1],
            "run_id": row[2],
            "error": row[3],
        }

    def _update_job(self, job_id: str, **fields: Any) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                sets = ", ".join(f"{k}=?" for k in fields)
                values = list(fields.values())
                conn.execute(
                    f"UPDATE jobs SET {sets}, updated_at=? WHERE id=?",
                    (*values, _utcnow_iso(), job_id),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT status, progress, run_id, error FROM jobs WHERE id=?",
                    (job_id,),
                ).fetchone()
            finally:
                conn.close()
        body = self._row_to_dict(row)
        self._broadcast(body)
        return body

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def submit_backtest(
        self,
        variant_id: str,
        symbol: str,
        tf: str,
        from_: str | None,
        to: str | None,
        preregistro_id: str | None = None,
        exploratory: bool = False,
    ) -> str:
        """Validate the window against CT-1 coverage (raises `JobsError` ->
        caller returns 422), insert a `queued` row, enqueue for the worker,
        return the new `job_id`."""
        if self._coverage_check is not None and not self._coverage_check(symbol, tf, from_, to):
            raise JobsError(f"requested window outside coverage for {symbol}/{tf}")

        job_id = f"jobrun-{uuid.uuid4().hex[:16]}"
        params = {
            "variant_id": variant_id, "symbol": symbol, "tf": tf,
            "from": from_, "to": to, "preregistro_id": preregistro_id,
            "exploratory": exploratory,
        }
        now = _utcnow_iso()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO jobs(id, kind, params_json, status, progress, run_id, error, "
                    "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (job_id, "backtest", json.dumps(params), "queued", 0.0, None, None, now, now),
                )
                conn.commit()
            finally:
                conn.close()
        self._broadcast({"status": "queued", "progress": 0.0, "run_id": None, "error": None})
        self._queue.put(job_id)
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT status, progress, run_id, error FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_dict(row)

    # ------------------------------------------------------------------
    # SSE broadcast (CT-9)
    # ------------------------------------------------------------------
    def subscribe(self) -> "queue.Queue[dict]":
        q: "queue.Queue[dict]" = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue[dict]") -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _broadcast(self, body: dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            q.put(body)

    # ------------------------------------------------------------------
    # worker
    # ------------------------------------------------------------------
    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._run_job(job_id)
            except Exception:  # noqa: BLE001 - worker thread must never die
                pass

    def _run_job(self, job_id: str) -> None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT params_json FROM jobs WHERE id=?", (job_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return
        params = json.loads(row[0])

        self._update_job(job_id, status="running", progress=0.0)

        def progress_cb(fraction: float) -> None:
            self._update_job(job_id, progress=max(0.0, min(1.0, fraction)))

        try:
            variant = self._registry.get_variant(params["variant_id"])
            if variant is None:
                raise ValueError(f"unknown variant_id: {params['variant_id']}")
            run_dict, trades = self._runner(
                variant, params["symbol"], params["tf"], params["from"], params["to"],
                progress_cb,
            )
            run_id = f"sim-{uuid.uuid4().hex[:16]}"
            run_dict["run_id"] = run_id
            run_dict["variant_id"] = params["variant_id"]
            if params.get("preregistro_id"):
                run_dict["preregistro_id"] = params["preregistro_id"]
            for t in trades:
                t["trade_id"] = f"simtr-{uuid.uuid4().hex[:16]}"
            self._registry.insert_run(run_dict)
            self._registry.insert_trades(run_id, trades)
            self._registry.audit("api", "job_backtest_done", {
                "job_id": job_id, "variant_id": params["variant_id"], "run_id": run_id,
                "trades": len(trades),
            })
            self._update_job(job_id, status="done", progress=1.0, run_id=run_id)
        except Exception as exc:  # noqa: BLE001 - job errors are reported via GET /api/jobs, never raised
            self._update_job(job_id, status="error", error=str(exc))

    # ------------------------------------------------------------------
    # default runner (real backtest-lite path, M2.7)
    # ------------------------------------------------------------------
    def _default_runner(self, variant, symbol, tf, desde, hasta, progress_cb):
        policy = _build_policy(variant)
        progress_cb(0.0)
        run_dict, trades = run_backtest_lite(policy, symbol, tf, desde, hasta, lake_root=self._lake_root)
        progress_cb(1.0)
        return run_dict, trades
