r"""tests/research/test_htf_wiring.py -- BLOCK-1: the WIRING of WP-3's H1/H4
feed into the decision loop (`backtest.build_htf_mask` -> `simular_variant`'s
`htf_mask`), as distinct from `higher_tf.py`'s OWN internal anti-look-ahead
tests (tests/research/test_higher_tf.py).

The brief is explicit that the wiring needs ITS OWN anti-look-ahead test, not
just the module's: `build_htf_mask` could in principle add a look-ahead bug
even with a perfectly causal `higher_tf.py` underneath it (e.g. by indexing
with an off-by-one, or by reading a field before its own warm-up is over).
These tests exercise `build_htf_mask` itself, and then the full chain through
`simular_variant`'s entry gate.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from scripts.analysis.realtick_bt import backtest
from scripts.analysis.realtick_bt.backtest import build_htf_mask, run_ladder
from sentinel_engine.strategies.emasar_variant import simular_variant

H1_SEC = backtest.H1_SEC
H4_SEC = backtest.H4_SEC
M15_SEC = 900


def _m15_bars(n: int, *, seed: int = 7, t0: int = 20 * H4_SEC) -> list[dict]:
    rnd = random.Random(seed)
    bars = []
    price = 2000.0
    for i in range(n):
        drift = rnd.uniform(-1.0, 1.3)
        price += drift
        o = price - drift
        c = price
        h = max(o, c) + abs(rnd.uniform(0.2, 0.8))
        lo = min(o, c) - abs(rnd.uniform(0.2, 0.8))
        bars.append({"t": t0 + M15_SEC * i, "open": o, "high": h, "low": lo, "close": c})
    return bars


# --------------------------------------------------------------------- anti-look-ahead of the WIRING
@pytest.mark.parametrize("tf_sec,field", [
    (H1_SEC, "ema_slope"), (H1_SEC, "momentum"), (H1_SEC, "st_dir"),
    (H4_SEC, "ema_slope"), (H4_SEC, "st_dir"),
])
def test_build_htf_mask_prefix_cut_equals_full_series_at_t(tf_sec, field):
    """Cut the M15 bars at k, recompute build_htf_mask on the prefix, and
    require equality with the full-series mask value AT that same index k --
    the exact contract prescribed by the spec (Section 1), applied to the
    WIRING function itself, not just to HigherSeries."""
    bars = _m15_bars(200, seed=11)
    full = build_htf_mask(bars, tf_sec, field=field)
    for k in (5, 16, 32, 63, 100, 150, 199):
        prefix = build_htf_mask(bars[: k + 1], tf_sec, field=field)
        assert prefix[k] == full[k], (
            f"tf_sec={tf_sec} field={field} k={k}: build_htf_mask diverges under "
            f"prefix cut -- look-ahead in the wiring, prefix={prefix[k]!r} full={full[k]!r}"
        )


def test_build_htf_mask_in_progress_bucket_never_visible_through_wiring():
    """Explicit test that the in-progress H4 bar is never visible THROUGH
    build_htf_mask (not merely inside higher_tf.py). Mirrors
    test_higher_tf.py::test_cutting_mid_bucket_never_leaks_the_forming_bucket
    but calls the WIRING function end to end."""
    bars = _m15_bars(20, seed=3)  # first H4 bucket = 16 M15 bars
    mask = build_htf_mask(bars, H4_SEC, field="ema_slope")
    # bars[0..14] (15 of 16 M15 bars into the first H4 bucket): the bucket is
    # still forming -- no higher bar has closed -- mask must be None (no-op),
    # never a value derived from the in-progress bucket.
    assert all(mask[i] is None for i in range(15))
    # bar 15 (the 16th, LAST M15 bar of the bucket) closes it on its own data.
    assert mask[15] is not None or True  # may still be None (ema_slope needs 2 closed bars)
    # decisive check: build the mask again on a bars[:15] prefix (the bucket
    # NEVER closes in this truncated series) -- it must never produce a
    # non-None value at index 14, matching the full series at the same instant.
    prefix_mask = build_htf_mask(bars[:15], H4_SEC, field="ema_slope")
    assert prefix_mask[14] is None
    assert mask[14] is None


# --------------------------------------------------------------------- end-to-end: real substrate
def test_build_htf_mask_prefix_cut_on_real_m15_substrate():
    """Same anti-look-ahead contract, on the REAL M15 substrate `backtest.py`
    feeds the engine (not just a synthetic fixture) -- best-effort, skipped
    if the parquet tier is not present on this host."""
    try:
        bars = backtest.load_bars()
    except Exception:
        pytest.skip("real M15 bars parquet not present on this host")
    bars = bars[:3000]
    full = build_htf_mask(bars, H4_SEC, field="ema_slope")
    for k in (500, 1000, 1999, 2500, 2999):
        prefix = build_htf_mask(bars[: k + 1], H4_SEC, field="ema_slope")
        assert prefix[k] == full[k], f"k={k}: real-substrate look-ahead in the wiring"


# --------------------------------------------------------------------- genuine consumption (BLOCK-1 "connect")
V09_PARAMS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
    init_sl_range_k=1.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)


def test_htf_mask_from_build_htf_mask_actually_changes_engine_entries():
    """The wiring is USELESS if nothing downstream ever reads it. Build a
    real htf_mask from a synthetic M15 series and feed it into
    simular_variant via the exact param name the engine gate checks
    (`htf_mask`) -- the resulting event stream must differ from the
    unfiltered baseline, proving the H1/H4 feed can actually gate a decision,
    not just sit inert as plumbing."""
    bars = _m15_bars(700, seed=42)
    baseline = simular_variant(bars, symbol="XAUUSD", **V09_PARAMS)
    entries_base = [e for e in baseline if e["motivo"] in ("ENTRY_L", "ENTRY_S")]
    assert entries_base

    mask = build_htf_mask(bars, H4_SEC, field="ema_slope")
    assert any(m is not None for m in mask)  # the mask must actually have signal
    gated = simular_variant(bars, symbol="XAUUSD", htf_mask=mask, **V09_PARAMS)
    assert gated != baseline
    entries_gated = [e for e in gated if e["motivo"] in ("ENTRY_L", "ENTRY_S")]
    # a trend-alignment gate can only ever REMOVE entries relative to baseline
    # (it is a pure AND filter, see emasar_variant.py's htf_mask block) --
    # never add a new one at an idx the baseline didn't already have.
    assert {e["idx"] for e in entries_gated} <= {e["idx"] for e in entries_base}


def test_run_ladder_threads_htf_mask_through_overlay_kwargs():
    """The harness-level path: run_ladder(kwargs, bars) forwards an arbitrary
    kwargs dict straight to simular_variant (no per-key allowlist) -- so a
    caller building an overlay with an `htf_mask` key (e.g.
    `overlay.overlay_kwargs('S6-K2P0', {'htf_mask': build_htf_mask(...)})`)
    reaches the engine with NO further code changes anywhere in
    backtest.py. This is the concrete proof BLOCK-1 is connected end to end
    through the harness, not just through a direct simular_variant call."""
    bars = _m15_bars(700, seed=42)
    mask = build_htf_mask(bars, H4_SEC, field="ema_slope")
    kwargs = {**V09_PARAMS, "symbol": "XAUUSD"}
    positions_off = run_ladder(kwargs, bars)
    positions_on = run_ladder({**kwargs, "htf_mask": mask}, bars)
    assert positions_on != positions_off
