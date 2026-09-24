"""P3 Task 3.5 — basic performance sanity check on the compute+broadcast loop.

This is NOT a full performance validation against target trading hardware
(that needs the real deployment box — see the report FLAG). It only asserts
one compute-and-broadcast cycle for a single instrument completes in a
"reasonable" bound on this dev machine, as a smoke check against gross
regressions (e.g. an accidental O(n^2) or a blocking call in the loop).
"""
from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient

# Generous bound for a dev laptop — this is a smoke test, not a target-HW
# perf gate. One Engine.step() call already runs the full macro+technical+
# levels pipeline against FakeFeed.
REASONABLE_SECONDS = 2.0


def test_compute_and_broadcast_cycle_is_reasonably_fast(app_factory):
    app = app_factory(instruments=("usdclp",), autostart_loop=False)
    with TestClient(app):
        compute_and_broadcast_once = app.state.compute_and_broadcast_once

        async def _run():
            start = time.perf_counter()
            await compute_and_broadcast_once("usdclp")
            return time.perf_counter() - start

        elapsed = asyncio.run(_run())

    assert elapsed < REASONABLE_SECONDS, (
        f"compute_and_broadcast_once took {elapsed:.3f}s > {REASONABLE_SECONDS}s smoke bound"
    )
