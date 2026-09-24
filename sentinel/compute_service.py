"""
sentinel/compute_service.py — Task 0.8 Streamlit performance stopgap.

Moves the expensive `SentinelCore.calculate_composite()` call OFF the
synchronous Streamlit rerun path. A single background thread computes
composites on a fixed cadence and publishes each result to a thread-safe
`SnapshotHolder`; every Streamlit rerun then just READS the latest snapshot
(cheap) instead of recomputing it (expensive).

No Streamlit import here on purpose — this module is pure stdlib plus the
zero-arg `compute_fn() -> dict` contract, so it can be unit-tested without
spinning up Streamlit, MT5, or the real SentinelCore.

Threading-safety contract (see task 0.8 report for the full audit):
- `compute_fn` (in production, `core.calculate_composite`) MUST be called by
  ONLY the background worker thread, never concurrently from the main
  (Streamlit render) thread — it mutates `core.macro_scorer`'s stateful EWMA
  tracker, and concurrent calls could corrupt that state.
- The main/render thread only ever calls `SnapshotHolder.get_latest()`,
  which returns a reference to an already-fully-built dict; it never
  mutates anything the worker touches.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("sentinel.compute_service")


class SnapshotHolder:
    """Thread-safe single-slot holder for the latest computed snapshot.

    Exactly one thread (the background worker) is expected to call
    `publish()`. Any number of threads/reruns may call `get_latest()` to
    read the most recently published snapshot without recomputing it.

    Python dict/reference assignment is already atomic under the GIL, so
    a torn read of `_latest` itself can't happen even without the lock —
    the lock here exists to make that guarantee explicit and testable
    (and to keep `_publish_count` consistent), not to work around a real
    race in reference assignment.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: Optional[Dict[str, Any]] = None
        self._ready = threading.Event()
        self._publish_count = 0

    def publish(self, snapshot: Dict[str, Any]) -> None:
        """Publish a new snapshot. Replaces whatever was there before."""
        with self._lock:
            self._latest = snapshot
            self._publish_count += 1
        self._ready.set()

    def get_latest(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Return the most recently published snapshot.

        Cold start (nothing published yet):
        - `timeout=None` (default): block indefinitely until the first
          publish (used by the dashboards so the first paint isn't blank).
        - `timeout=0`: never block; returns None immediately if nothing has
          been published yet.
        - `timeout=<seconds>`: block up to that many seconds, then return
          whatever is available (None if still nothing).
        """
        if not self._ready.is_set():
            if timeout == 0:
                return None
            self._ready.wait(timeout)
        with self._lock:
            return self._latest

    @property
    def publish_count(self) -> int:
        with self._lock:
            return self._publish_count


class ComputeWorker:
    """Background thread that repeatedly calls `compute_fn` and publishes
    each result to a `SnapshotHolder` on a fixed cadence.

    `compute_fn` must be a zero-argument callable returning a dict (in
    production, `core.calculate_composite`). This worker is designed to be
    the ONLY caller of `compute_fn` for the lifetime of the process.
    """

    def __init__(
        self,
        compute_fn: Callable[[], Dict[str, Any]],
        holder: SnapshotHolder,
        interval_seconds: float,
        on_publish: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self._compute_fn = compute_fn
        self._holder = holder
        self._interval_seconds = interval_seconds
        self._on_publish = on_publish
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="sentinel-compute-worker", daemon=True
        )

    def start(self) -> "ComputeWorker":
        self._thread.start()
        return self

    def stop(self, join_timeout: Optional[float] = 2.0) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(join_timeout)

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                result = self._compute_fn()
                self._holder.publish(result)
                if self._on_publish is not None:
                    try:
                        self._on_publish(result)
                    except Exception:
                        logger.exception(
                            "compute_service: on_publish callback failed"
                        )
            except Exception:
                logger.exception(
                    "compute_service: compute_fn failed; will retry next cycle"
                )
            # Interruptible wait so stop() doesn't have to wait a full cycle.
            self._stop_event.wait(self._interval_seconds)


def start_worker(
    compute_fn: Callable[[], Dict[str, Any]],
    interval_seconds: float,
    on_publish: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Tuple[SnapshotHolder, ComputeWorker]:
    """Create a SnapshotHolder + ComputeWorker pair and start the worker.

    Convenience factory for callers (dashboards) that just want "give me a
    holder that's being kept fresh in the background."
    """
    holder = SnapshotHolder()
    worker = ComputeWorker(
        compute_fn, holder, interval_seconds, on_publish=on_publish
    ).start()
    return holder, worker


# ══════════════════════════════════════════════════════════
# Per-core worker registry
# ══════════════════════════════════════════════════════════
# SENTINEL serves two Streamlit pages (dashboard.py / dashboard_v2.py).
# Each page defines its OWN `@st.cache_resource def init_system()`, and
# `st.cache_resource` keys its cache off the (module, qualname) of the
# decorated function — NOT off "this represents the same logical
# resource". So dashboard.py and dashboard_v2.py each end up with their
# OWN SentinelCore instance, each with its own stateful `macro_scorer`
# EWMA tracker. There is no single shared core.
#
# Because of that, a single process-wide worker singleton is WRONG: it
# would capture only the first caller's `compute_fn` (bound to the first
# caller's core), and every other core's page would silently read that
# first core's composite — wrong scoring output, since each core's
# macro_scorer EWMA state has diverged.
#
# get_or_start_shared_worker() instead keeps a PER-CORE registry keyed by
# the identity of an explicit `key` object (in production, `key=_core`,
# i.e. each dashboard's own `SentinelCore` instance). The guarantee this
# provides is: one worker PER core, keyed by core identity —
# - the SAME key → the SAME holder, and starts NO second worker thread
#   (preserves the no-concurrent-mutation guarantee for that one core's
#   macro_scorer EWMA tracker);
# - two DIFFERENT keys → two DIFFERENT holders, each fed by its own
#   single worker calling its own core's compute_fn.
#
# The registry keys off `id(key)` but also holds a strong reference to
# `key` itself for as long as the entry is live, so `id()` cannot be
# reused/aliased by an unrelated object being garbage-collected into the
# same address while an entry is still registered.
_registry_lock = threading.Lock()
_registry: Dict[int, Tuple[Any, SnapshotHolder, ComputeWorker]] = {}


def get_or_start_shared_worker(
    compute_fn: Callable[[], Dict[str, Any]],
    interval_seconds: float,
    on_publish: Optional[Callable[[Dict[str, Any]], None]] = None,
    *,
    key: Any,
) -> SnapshotHolder:
    """Return the holder for the worker associated with `key`, starting
    that worker on the first call for this `key`. Safe to call from any
    thread/module any number of times.

    `key` identifies the core this worker computes for (in production,
    the dashboard's own `SentinelCore` instance, e.g. `key=_core`). Only
    the FIRST caller for a given `key` actually supplies the
    `compute_fn`/`on_publish` used by that key's worker; later calls with
    the SAME key just return the existing holder for it. Calls with a
    DIFFERENT key get their own independent holder/worker pair.
    """
    with _registry_lock:
        entry = _registry.get(id(key))
        if entry is None:
            holder, worker = start_worker(
                compute_fn, interval_seconds, on_publish=on_publish
            )
            _registry[id(key)] = (key, holder, worker)
            return holder
        _, holder, _ = entry
        return holder


def _reset_shared_worker_for_tests() -> None:
    """Test-only escape hatch: stop and clear every worker in the registry
    so each test starts from a clean slate. Not used by production code.
    """
    with _registry_lock:
        for _key, _holder, worker in _registry.values():
            worker.stop()
        _registry.clear()
