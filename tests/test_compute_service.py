"""
Tests for sentinel.compute_service (Task 0.8 Streamlit performance stopgap).

Covers the SnapshotHolder/ComputeWorker contract in isolation, using a fake
zero-arg compute_fn — no MT5, no Streamlit, no real SentinelCore involved.

Focus areas (per task 0.8 acceptance criteria):
- publish()/get_latest() thread-safety: concurrent publish+get never
  returns a torn/partial dict.
- get_latest() returns the LAST published snapshot without recomputing
  (the compute_fn is never called by the holder itself).
- Cold-start behavior: get_latest() blocks until the first publish (or
  returns None immediately/after a bounded wait if asked not to block).
- ComputeWorker calls compute_fn on its own thread only, on a cadence, and
  publishes each result; a failing compute_fn cycle is swallowed and
  retried next cycle rather than killing the worker thread.
"""
import threading
import time

import pytest

from sentinel.compute_service import (
    ComputeWorker,
    SnapshotHolder,
    _reset_shared_worker_for_tests,
    get_or_start_shared_worker,
    start_worker,
)


@pytest.fixture(autouse=True)
def _clean_shared_singleton():
    """Every test gets a fresh process-wide singleton (and leaves none
    running after it finishes) — the singleton is process-global state,
    so tests must not leak a live thread into the next test.
    """
    _reset_shared_worker_for_tests()
    yield
    _reset_shared_worker_for_tests()


# ══════════════════════════════════════════════════════════
# SnapshotHolder
# ══════════════════════════════════════════════════════════

def test_get_latest_blocks_until_first_publish_then_returns_it():
    holder = SnapshotHolder()
    result_box = {}

    def _reader():
        result_box["snapshot"] = holder.get_latest()

    t = threading.Thread(target=_reader)
    t.start()
    # Reader should be blocked (no publish yet) — give it a moment to prove
    # it hasn't returned prematurely.
    time.sleep(0.05)
    assert "snapshot" not in result_box

    holder.publish({"composite_score": 42})
    t.join(timeout=2)
    assert not t.is_alive()
    assert result_box["snapshot"] == {"composite_score": 42}


def test_get_latest_nonblocking_returns_none_before_first_publish():
    holder = SnapshotHolder()
    assert holder.get_latest(timeout=0) is None


def test_get_latest_returns_last_published_without_recomputing():
    holder = SnapshotHolder()
    calls = []

    holder.publish({"composite_score": 1, "seq": "a"})
    holder.publish({"composite_score": 2, "seq": "b"})
    holder.publish({"composite_score": 3, "seq": "c"})

    # Multiple reads return the same last-published dict; get_latest never
    # invokes anything that could increment a call counter — nothing to
    # recompute, it's a pure read.
    first_read = holder.get_latest()
    second_read = holder.get_latest()
    assert first_read == {"composite_score": 3, "seq": "c"}
    assert second_read == first_read
    assert holder.publish_count == 3
    assert calls == []  # sanity: nothing was ever "called" by get_latest


def test_concurrent_publish_and_get_never_returns_torn_dict():
    """Hammer publish() from one thread while many threads read
    concurrently; every read must be one of the exact dicts that was
    published (by identity of shape), never a partially-written mix.
    """
    holder = SnapshotHolder()
    n_publishes = 500
    stop = threading.Event()
    bad_reads = []

    def _publisher():
        for i in range(n_publishes):
            # A "wide" dict so a torn read (some keys from snapshot i,
            # some from i+1) would be detectable via the invariant below.
            snap = {"seq": i, "a": i, "b": i, "c": i, "d": i}
            holder.publish(snap)
        stop.set()

    def _reader():
        while not stop.is_set():
            snap = holder.get_latest(timeout=0)
            if snap is not None:
                values = {snap["seq"], snap["a"], snap["b"], snap["c"], snap["d"]}
                if len(values) != 1:
                    bad_reads.append(snap)

    readers = [threading.Thread(target=_reader) for _ in range(4)]
    pub = threading.Thread(target=_publisher)
    for t in readers:
        t.start()
    pub.start()
    pub.join(timeout=10)
    for t in readers:
        t.join(timeout=10)

    assert bad_reads == []
    assert holder.publish_count == n_publishes
    final = holder.get_latest()
    assert final["seq"] == n_publishes - 1


# ══════════════════════════════════════════════════════════
# ComputeWorker / start_worker
# ══════════════════════════════════════════════════════════

def test_worker_calls_compute_fn_on_background_thread_and_publishes():
    call_count = {"n": 0}
    main_thread_id = threading.get_ident()
    seen_thread_ids = []

    def fake_compute():
        call_count["n"] += 1
        seen_thread_ids.append(threading.get_ident())
        return {"composite_score": call_count["n"]}

    holder, worker = start_worker(fake_compute, interval_seconds=0.02)
    try:
        first = holder.get_latest(timeout=5)
        assert first is not None
        # Let it publish a couple more times.
        deadline = time.time() + 2
        while call_count["n"] < 3 and time.time() < deadline:
            time.sleep(0.02)
        assert call_count["n"] >= 3
        assert all(tid != main_thread_id for tid in seen_thread_ids)
        latest = holder.get_latest()
        assert latest["composite_score"] == call_count["n"]
    finally:
        worker.stop()


def test_worker_survives_compute_fn_exception_and_keeps_retrying():
    state = {"n": 0}

    def flaky_compute():
        state["n"] += 1
        if state["n"] <= 2:
            raise RuntimeError("transient failure")
        return {"composite_score": state["n"]}

    holder, worker = start_worker(flaky_compute, interval_seconds=0.02)
    try:
        result = holder.get_latest(timeout=5)
        assert result is not None
        assert result["composite_score"] >= 3
        assert worker.is_alive
    finally:
        worker.stop()


def test_on_publish_callback_invoked_with_each_published_snapshot():
    published = []

    def fake_compute():
        return {"composite_score": len(published)}

    def on_publish(snapshot):
        published.append(snapshot)

    holder, worker = start_worker(fake_compute, interval_seconds=0.02, on_publish=on_publish)
    try:
        deadline = time.time() + 2
        while len(published) < 3 and time.time() < deadline:
            time.sleep(0.02)
        assert len(published) >= 3
        assert holder.get_latest()["composite_score"] == published[-1]["composite_score"]
    finally:
        worker.stop()


# ══════════════════════════════════════════════════════════
# get_or_start_shared_worker — per-core registry, keyed by `key`
# ══════════════════════════════════════════════════════════

def test_shared_worker_singleton_returns_same_holder_across_calls():
    calls = {"n": 0}

    def fake_compute():
        calls["n"] += 1
        return {"composite_score": calls["n"]}

    same_key = object()
    holder1 = get_or_start_shared_worker(fake_compute, interval_seconds=0.02, key=same_key)
    holder1.get_latest(timeout=5)
    holder2 = get_or_start_shared_worker(fake_compute, interval_seconds=0.02, key=same_key)

    assert holder1 is holder2


def test_shared_worker_singleton_does_not_start_a_second_thread():
    """Simulates the SAME core's dashboard page asking for a worker twice
    (e.g. across Streamlit reruns) — must never end up with two threads
    calling that core's compute_fn concurrently (the exact race this
    stopgap must avoid for core.macro_scorer's stateful EWMA tracker)."""
    concurrent_calls = {"n": 0, "max_concurrent": 0}
    call_lock = threading.Lock()

    def fake_compute():
        with call_lock:
            concurrent_calls["n"] += 1
            concurrent_calls["max_concurrent"] = max(
                concurrent_calls["max_concurrent"], concurrent_calls["n"]
            )
        time.sleep(0.05)  # hold the "critical section" open to expose overlap
        with call_lock:
            concurrent_calls["n"] -= 1
        return {"composite_score": 1}

    same_key = object()
    # First call for this core/key.
    holder_a = get_or_start_shared_worker(fake_compute, interval_seconds=0.02, key=same_key)
    # A later call (e.g. next rerun) for the SAME core/key.
    holder_b = get_or_start_shared_worker(fake_compute, interval_seconds=0.02, key=same_key)

    holder_a.get_latest(timeout=5)
    time.sleep(0.2)

    assert holder_a is holder_b
    assert concurrent_calls["max_concurrent"] <= 1


def test_shared_worker_different_keys_get_independent_holders_and_workers():
    """IMP-1 regression test: dashboard.py and dashboard_v2.py each build
    their OWN SentinelCore (separate st.cache_resource entries), so they
    must each get their OWN worker/holder — not silently share the first
    caller's compute_fn/core, which was the bug (v2 reading v1's stale
    macro_scorer-derived composite)."""
    k1 = object()
    k2 = object()

    def compute_fn_1():
        return {"composite_score": "from_core_1"}

    def compute_fn_2():
        return {"composite_score": "from_core_2"}

    holder1 = get_or_start_shared_worker(compute_fn_1, interval_seconds=0.02, key=k1)
    holder2 = get_or_start_shared_worker(compute_fn_2, interval_seconds=0.02, key=k2)

    snap1 = holder1.get_latest(timeout=5)
    snap2 = holder2.get_latest(timeout=5)

    assert holder1 is not holder2
    assert snap1["composite_score"] == "from_core_1"
    assert snap2["composite_score"] == "from_core_2"


def test_stop_halts_further_compute_fn_calls():
    call_count = {"n": 0}

    def fake_compute():
        call_count["n"] += 1
        return {"composite_score": call_count["n"]}

    holder, worker = start_worker(fake_compute, interval_seconds=0.02)
    holder.get_latest(timeout=5)
    worker.stop()
    n_after_stop = call_count["n"]
    time.sleep(0.15)
    # No further increments once stopped (allow the in-flight cycle to
    # finish, but no NEW cycle should start).
    assert call_count["n"] == n_after_stop
