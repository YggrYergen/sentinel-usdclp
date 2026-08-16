r"""tests/research/test_regime_gate_wiring.py -- BLOCK-1 addendum: the
harness-level post-filter that connects WP-5's regime.py (deliberately NOT
wired into sentinel_engine, see its own module docstring and the spec's WP-5
table row "sin tocar el nucleo") to something runnable for P-09's S6
entry-gate half, via `backtest.apply_regime_gate_by_entry_bar`.

This is a POST-HOC filter over `run_ladder`'s output, not an engine change --
consistent with the spec. `cfg=None`/`cfg.enabled=False` (library default)
must be byte-identical no-ops.
"""
from __future__ import annotations

import random

from scripts.analysis.realtick_bt.backtest import apply_regime_gate_by_entry_bar
from scripts.analysis.realtick_bt.regime import (
    RegimeGateConfig,
    compute_regime_series,
)

M15_SEC = 900


def _bars(n: int, seed: int = 5) -> list[dict]:
    rnd = random.Random(seed)
    bars = []
    price = 2000.0
    t0 = 1_700_000_000
    for i in range(n):
        drift = rnd.uniform(-1.2, 1.5)
        price += drift
        o = price - drift
        c = price
        h = max(o, c) + abs(rnd.uniform(0.2, 0.9))
        lo = min(o, c) - abs(rnd.uniform(0.2, 0.9))
        bars.append({"t": t0 + M15_SEC * i, "open": o, "high": h, "low": lo, "close": c})
    return bars


def _fake_positions(bars: list[dict]) -> list[dict]:
    # every 7th bar is a synthetic "entry" -- enough spread to exercise the
    # gate across warm-up and post-warm-up regions.
    return [{"t_in": bars[i]["t"], "t_out": bars[i]["t"] + M15_SEC, "side": "LONG",
              "net1": 1.0} for i in range(0, len(bars), 7)]


def test_cfg_none_is_byte_identical_noop():
    bars = _bars(200)
    positions = _fake_positions(bars)
    series = compute_regime_series(bars)
    out = apply_regime_gate_by_entry_bar(positions, bars, series, None)
    assert out is positions  # same object, not merely equal


def test_cfg_disabled_is_byte_identical_noop():
    bars = _bars(200)
    positions = _fake_positions(bars)
    series = compute_regime_series(bars)
    cfg = RegimeGateConfig(enabled=False, adx_min=50.0)  # a threshold that would reject everything if enabled
    out = apply_regime_gate_by_entry_bar(positions, bars, series, cfg)
    assert out is positions


def test_cfg_enabled_strict_threshold_drops_positions():
    bars = _bars(300, seed=11)
    positions = _fake_positions(bars)
    assert positions
    series = compute_regime_series(bars)
    # impossible ADX threshold (ADX in [0,100]) -- everything with a resolved
    # ADX value must be dropped; warm-up (ADX None) is also a fail (see
    # regime.regime_gate docstring: missing counts as fail, never pass).
    cfg = RegimeGateConfig(enabled=True, adx_min=999.0)
    out = apply_regime_gate_by_entry_bar(positions, bars, series, cfg)
    assert out == []


def test_cfg_enabled_permissive_threshold_keeps_everything_resolvable():
    bars = _bars(300, seed=11)
    positions = _fake_positions(bars)
    series = compute_regime_series(bars)
    cfg = RegimeGateConfig(enabled=True, adx_min=-1.0)  # ADX is always >= 0 -- always passes once resolved
    out = apply_regime_gate_by_entry_bar(positions, bars, series, cfg)
    # only entries inside the ADX warm-up (None) can be dropped; anything
    # with a resolved ADX must survive an always-true threshold.
    kept_t = {p["t_in"] for p in out}
    t_to_idx = {b["t"]: i for i, b in enumerate(bars)}
    for p in positions:
        idx = t_to_idx[p["t_in"]]
        if series.adx[idx] is not None:
            assert p["t_in"] in kept_t
