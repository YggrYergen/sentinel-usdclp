"""
SENTINEL revamp — Task 1.6b: golden-master capture harness for the headless Engine.

`capture_engine(instrument, feed_fixture)` drives `sentinel_engine.engine.Engine`
(the new, config-parameterized scoring engine — P1 Task 1.6a) for one of the
three target instruments (usdclp, gold, nasdaq) against a deterministic,
CSV-backed `FakeFeed`, and returns a plain dict snapshot (`Snapshot.to_dict()`)
of every scored output field.

This mirrors `tests/golden/capture_golden.py`'s contract exactly:
  - Returns the RAW result dict (JSON-safe types, NOT yet canonicalized) —
    callers apply `to_canonical_json` / `_clean` (both imported from
    `capture_golden`, reused unmodified here).
  - Same warmup convention: drive `engine._macro.update_tick(feed)` 34x
    BEFORE calling `engine.step()` (step() itself performs exactly 1 more
    internal `update_tick`, reaching the same WARMUP_CYCLES=35 tracker
    state `capture_golden` reaches). See `tests/test_engine.py`, which
    proves this reaches byte-identical scoring vs the legacy paths for all
    three instruments.
  - No network / MT5 / yfinance — FakeFeed only reads committed fixture CSVs.

This module is purely additive: it does not modify `capture_golden.py`,
`sentinel/`, or `sentinel_engine/engine.py`.
"""
from __future__ import annotations

from pathlib import Path

from sentinel_engine.config import load_instrument
from sentinel_engine.engine import Engine

from tests.golden.capture_golden import FIXTURES_DIR, to_canonical_json

# External update_tick calls driven on the engine's macro tracker BEFORE
# calling step() (step() itself does exactly 1 more internal update_tick,
# reaching the same 35-total-ticks-before-score state capture_golden's
# WARMUP_CYCLES=35 reaches). See tests/test_engine.py::ENGINE_WARMUP_TICKS.
ENGINE_WARMUP_TICKS = 34


def capture_engine(instrument: str, feed) -> dict:
    """Run `sentinel_engine.engine.Engine` for `instrument` against `feed`
    (a FakeFeed instance) and return the full `Snapshot.to_dict()` result
    (JSON-safe types, NOT yet canonicalized — use `to_canonical_json` for
    the serialized form).
    """
    cfg = load_instrument(instrument)
    engine = Engine(cfg, feed)
    for _ in range(ENGINE_WARMUP_TICKS):
        engine._macro.update_tick(feed)
    snap = engine.step()
    return snap.to_dict()


def write_golden(instrument: str, feed_fixture, out_dir: Path = FIXTURES_DIR) -> Path:
    """Capture and write the canonical JSON snapshot to fixtures/<instrument>.json."""
    result = capture_engine(instrument, feed_fixture)
    out_path = Path(out_dir) / f"{instrument}.json"
    out_path.write_text(to_canonical_json(result), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    from tests.golden.fake_feed import FakeFeed

    for instrument in ("usdclp", "gold", "nasdaq"):
        path = write_golden(instrument, FakeFeed())
        print(f"Wrote {path}")
