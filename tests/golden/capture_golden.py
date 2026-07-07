"""
SENTINEL revamp — Task 0.1: golden-master capture harness.

`capture_golden(instrument, feed_fixture)` drives the CURRENT (pre-refactor)
scoring path for one of the three target instruments (usdclp, gold, nasdaq)
against a deterministic, CSV-backed `FakeFeed`, and returns a plain dict
snapshot of every scored output field.

Determinism traps handled here (see task brief):
  - SentinelCore.calculate_composite()'s `meta.timestamp` (wall-clock) is
    stripped before returning/serializing.
  - MacroScorer is stateful (EWMA tracker) and reports confidence=0 until
    it has seen >=30 update cycles. We drive a FIXED number of warmup
    update cycles (WARMUP_CYCLES) before reading the score, so re-running
    against the same fixture always reaches the same tracker state.
  - No network / MT5 / yfinance — FakeFeed only reads committed fixture CSVs.

Gold and NASDAQ do NOT go through SentinelCore (it is hardwired to
USDCLP via sentinel.config.SYMBOLS / EXPECTED_CORRELATIONS). Their scoring
lives in sentinel.instrument_panel's pure compute functions
(`_update_macro`, `_calc_macro`), called directly here — never
`render_panel`, which is Streamlit + wall-clock coupled.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Number of MacroScorer EWMA-tracker warmup cycles to drive before reading
# a score. Must be >= the tracker's warmup threshold (30, see
# RealtimeCorrelationTracker.get_confidence) so confidence is non-zero
# and reproducible. Fixed constant => same fixture always yields the
# same number of ticks => byte-identical output.
WARMUP_CYCLES = 35


# ══════════════════════════════════════════════════════════════════
# Canonical JSON serialization
# ══════════════════════════════════════════════════════════════════

def _clean(obj: Any) -> Any:
    """Recursively convert to plain JSON-safe python types, rounding all
    floats to a fixed precision so re-runs can never differ due to float
    representation noise."""
    # numpy scalar types (np.floating / np.integer / np.bool_) all expose
    # .item(); check before generic float/int handling.
    if hasattr(obj, "item") and not isinstance(obj, (dict, list, tuple, str, bytes)):
        try:
            obj = obj.item()
        except Exception:
            pass

    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return round(obj, 6)
    if isinstance(obj, int):
        return obj
    if obj is None or isinstance(obj, str):
        return obj
    # Fallback for anything unexpected (e.g. pandas Timestamp) — stringify
    # deterministically rather than fail.
    return str(obj)


def to_canonical_json(result: dict) -> str:
    """Canonical JSON: sorted keys, fixed float precision, ensure_ascii=False,
    utf-8 text (caller writes with encoding='utf-8')."""
    cleaned = _clean(result)
    return json.dumps(cleaned, sort_keys=True, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════
# Per-instrument capture
# ══════════════════════════════════════════════════════════════════

def _capture_usdclp(feed) -> dict:
    from sentinel.sentinel_core import SentinelCore

    core = SentinelCore(feed)
    # Drive fixed warmup cycles on the SAME macro_scorer instance
    # calculate_composite() will use (it calls update_tick once more
    # internally before scoring, so WARMUP_CYCLES-1 here + 1 = WARMUP_CYCLES).
    for _ in range(WARMUP_CYCLES - 1):
        core.macro_scorer.update_tick(feed)

    result = core.calculate_composite()
    result.pop("meta", None)  # wall-clock timestamp — excluded from golden
    return result


def _capture_panel_instrument(feed, symbols_cfg, asset_weights, expected_corrs) -> dict:
    from sentinel.macro_scorer import MacroScorer
    from sentinel.technical_scorer import calculate_multi_tf_score
    from sentinel.levels_engine import calculate_levels
    from sentinel.instrument_panel import _update_macro, _calc_macro

    target = symbols_cfg["target"]

    ms = MacroScorer()
    for _ in range(WARMUP_CYCLES):
        _update_macro(ms, feed, symbols_cfg, asset_weights, expected_corrs)
    macro = _calc_macro(ms, feed, symbols_cfg, expected_corrs, asset_weights)

    technical = calculate_multi_tf_score(feed, target)
    levels = calculate_levels(feed, target)

    return {
        "technical": technical,
        "macro": macro,
        "levels": levels,
    }


def _capture_gold(feed) -> dict:
    from sentinel.config import SYMBOLS_GOLD, ASSET_WEIGHTS_GOLD, EXPECTED_CORRELATIONS_GOLD
    return _capture_panel_instrument(feed, SYMBOLS_GOLD, ASSET_WEIGHTS_GOLD, EXPECTED_CORRELATIONS_GOLD)


def _capture_nasdaq(feed) -> dict:
    from sentinel.config import SYMBOLS_NASDAQ, ASSET_WEIGHTS_NASDAQ, EXPECTED_CORRELATIONS_NASDAQ
    return _capture_panel_instrument(feed, SYMBOLS_NASDAQ, ASSET_WEIGHTS_NASDAQ, EXPECTED_CORRELATIONS_NASDAQ)


_CAPTURERS = {
    "usdclp": _capture_usdclp,
    "gold": _capture_gold,
    "nasdaq": _capture_nasdaq,
}


def capture_golden(instrument: str, feed_fixture) -> dict:
    """Run the current scoring path for `instrument` against `feed_fixture`
    (a FakeFeed instance) and return the full result dict (JSON-safe types,
    NOT yet canonicalized — use `to_canonical_json` for the serialized form).
    """
    if instrument not in _CAPTURERS:
        raise ValueError(f"Unknown instrument: {instrument!r} (expected one of {sorted(_CAPTURERS)})")
    return _CAPTURERS[instrument](feed_fixture)


def write_golden(instrument: str, feed_fixture, out_dir: Path = FIXTURES_DIR) -> Path:
    """Capture and write the canonical JSON snapshot to fixtures/<instrument>.json."""
    result = capture_golden(instrument, feed_fixture)
    out_path = Path(out_dir) / f"{instrument}.json"
    out_path.write_text(to_canonical_json(result), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    from tests.golden.fake_feed import FakeFeed

    for instrument in _CAPTURERS:
        path = write_golden(instrument, FakeFeed())
        print(f"Wrote {path}")
