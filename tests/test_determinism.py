"""
P1 Task 1.8 — determinism gate: same feed + config => identical snapshot.

Pinned hard rule: for a fixed FakeFeed fixture and a fixed InstrumentConfig,
`Engine.step()` must produce an IDENTICAL Snapshot across arbitrarily many runs —
identical `config_hash`, deterministic `seq` stamping, and byte-identical canonical
JSON of the full snapshot. This locks out any hidden nondeterminism (dict/set
iteration order, wall-clock, randomness) a future refactor might introduce.

Warmup convention mirrors `tests/golden/capture_engine.py` (34 external ticks on
the macro tracker before `step()`, which does 1 more internally => WARMUP_CYCLES=35).
"""
from __future__ import annotations

import pytest

from sentinel_engine.config import load_instrument
from sentinel_engine.engine import Engine
from tests.golden.capture_engine import ENGINE_WARMUP_TICKS
from tests.golden.capture_golden import to_canonical_json
from tests.golden.fake_feed import FakeFeed

INSTRUMENTS = ["usdclp", "gold", "nasdaq"]

# Content-addressed hash over each instrument's config surface (pinned in the SDD
# ledger). A change here means the config surface changed and MUST be intentional.
EXPECTED_CONFIG_HASH = {
    "usdclp": "31c9325c7534",
    "gold": "6034eb02112d",
    "nasdaq": "3b022d347462",
}

N_RUNS = 100


def _run(instrument: str, seq: int = 0) -> dict:
    """One full engine snapshot for `instrument` on a fresh deterministic feed."""
    cfg = load_instrument(instrument)
    feed = FakeFeed()
    engine = Engine(cfg, feed)
    for _ in range(ENGINE_WARMUP_TICKS):
        engine._macro.update_tick(feed)
    return engine.step(seq=seq).to_dict()


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_snapshot_byte_identical_across_100_runs(instrument):
    """100 independent runs (fresh feed + config each) => one distinct snapshot."""
    canon = {to_canonical_json(_run(instrument)) for _ in range(N_RUNS)}
    assert len(canon) == 1, (
        f"{instrument}: {len(canon)} distinct snapshots across {N_RUNS} runs "
        f"— nondeterminism leaked into the engine"
    )


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_config_hash_stable_and_pinned(instrument):
    """config_hash is stable across runs and matches the pinned ledger value."""
    hashes = {_run(instrument)["config_hash"] for _ in range(N_RUNS)}
    assert len(hashes) == 1, f"{instrument}: config_hash not stable: {hashes}"
    got = hashes.pop()
    assert got == EXPECTED_CONFIG_HASH[instrument], (
        f"{instrument}: config_hash {got!r} != pinned {EXPECTED_CONFIG_HASH[instrument]!r}"
    )


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_seq_is_stamped_deterministically(instrument):
    """seq is faithfully stamped and does not perturb any other field."""
    base = _run(instrument, seq=0)
    # Same feed+config+seq => byte-identical (repeat of the 100-run guarantee at seq!=0).
    assert to_canonical_json(_run(instrument, seq=7)) == to_canonical_json(_run(instrument, seq=7))
    for k in (0, 1, 42, 999):
        snap = _run(instrument, seq=k)
        assert snap["seq"] == k, f"{instrument}: seq {snap['seq']} != requested {k}"
        # seq is the ONLY field that may move with seq: strip it and compare to base.
        assert {kk: v for kk, v in snap.items() if kk != "seq"} == {
            kk: v for kk, v in base.items() if kk != "seq"
        }, f"{instrument}: changing seq perturbed a non-seq field"
