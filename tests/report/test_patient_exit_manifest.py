"""tests/report/test_patient_exit_manifest.py -- PX-T5 (PATIENT-EXIT program, P64).

Validates the pre-registered PATIENT-EXIT manifest
(`scripts/report/patient_exit_manifest_2026_07_20.json`) that PX-T6 will feed
to `gen_honest_sweep`. This is a DATA task: the manifest is a static, hand-authored
JSON file. These tests assert its structural + preregistration invariants and,
critically, that EVERY entry's `kwargs` is a valid `simular_variant` call.

Assertions (from the brief's required TDD order):
- exactly 21 entries (14 configs + 2 base controls + 5 S7 echoes);
- unique `variant_id`s;
- every entry has tf == "M15" and windows == the 4-window list;
- every `prereg.hypothesis` is a non-empty string (P64), plus mechanism/
  metric/threshold/discard_if/date/author all populated; metric names BOTH
  net_honest and mfe_capture; date == "2026-07-20";
- every `kwargs` dict binds cleanly against `simular_variant`'s signature AND
  is accepted when the strategy is actually invoked on a tiny synthetic bar list;
- `_meta.holdout_precommit` is EXACTLY the 5 pre-committed (family -> config) pairs;
- deterministic file: parses as utf-8 JSON.
"""
from __future__ import annotations

import inspect
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sentinel_engine.strategies.emasar_variant import simular_variant

MANIFEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "report"
    / "patient_exit_manifest_2026_07_20.json"
)

WINDOWS = ["IW", "W1", "W2", "W3"]
EXPECTED_HOLDOUT = {
    "F1": "PX-RATCHET-L50",
    "F2": "PX-FLOOR-K3",
    "F3": "PX-WAIT-MAE2",
    "F4": "PX-PART-F1TP1",
    "F5": "PX-TRAIL-ARM1",
}
EXPECTED_ENTRY_COUNT = 21


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def manifest() -> dict:
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def entries(manifest: dict) -> list[dict]:
    return manifest["entries"]


def _synthetic_bars(n: int = 120, seed: int = 11) -> list[dict]:
    """Deterministic bar list -- same shape as tests/strategies/test_emasar_variant."""
    rnd = random.Random(seed)
    bars: list[dict] = []
    price = 2000.0
    base_epoch = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        open_ = price - drift
        close = price
        high = max(open_, close) + abs(rnd.uniform(0.3, 1.2))
        low = min(open_, close) - abs(rnd.uniform(0.3, 1.2))
        bars.append({
            "t": base_epoch + k * 900,
            "open": open_, "high": high, "low": low, "close": close,
            "volume": 1.0,
        })
    return bars


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------
def test_manifest_file_exists_and_is_utf8_json():
    assert MANIFEST_PATH.exists(), f"missing manifest: {MANIFEST_PATH}"
    # Round-trips as utf-8 JSON (deterministic, no BOM surprises).
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        json.load(fh)


def test_entry_count_is_21(entries):
    assert len(entries) == EXPECTED_ENTRY_COUNT


def test_variant_ids_unique(entries):
    ids = [e["variant_id"] for e in entries]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate variant_id(s): {sorted(dupes)}"
    assert len(ids) == EXPECTED_ENTRY_COUNT


def test_every_entry_tf_and_windows(entries):
    for e in entries:
        assert e["tf"] == "M15", f"{e['variant_id']}: tf != M15"
        assert e["windows"] == WINDOWS, f"{e['variant_id']}: windows != {WINDOWS}"


def test_expected_ids_present(entries):
    ids = {e["variant_id"] for e in entries}
    core = {
        "PX-RATCHET-L33", "PX-RATCHET-L50", "PX-RATCHET-L66",
        "PX-CHAND-ATR3", "PX-CHAND-ATR2",
        "PX-FLOOR-K3", "PX-FLOOR-K4",
        "PX-SAR-SLOW",
        "PX-WAIT-MAE2", "PX-WAIT-MAE3",
        "PX-PART-F1TP1", "PX-PART-F1TP0P5", "PX-PART-F1F2",
        "PX-TRAIL-ARM1",
    }
    controls = {"PX-BASE-S6K2P0", "PX-BASE-S7TPNONE"}
    echoes = {
        "PX-RATCHET-L33-S7", "PX-RATCHET-L50-S7", "PX-RATCHET-L66-S7",
        "PX-CHAND-ATR3-S7", "PX-CHAND-ATR2-S7",
    }
    assert core | controls | echoes == ids


# ---------------------------------------------------------------------------
# Preregistration (P64)
# ---------------------------------------------------------------------------
def test_every_entry_has_full_prereg(entries):
    required = ("hypothesis", "mechanism", "metric", "threshold",
                "discard_if", "date", "author")
    for e in entries:
        pr = e.get("prereg")
        assert isinstance(pr, dict), f"{e['variant_id']}: prereg missing"
        for field in required:
            assert field in pr, f"{e['variant_id']}: prereg.{field} missing"
        assert isinstance(pr["hypothesis"], str) and pr["hypothesis"].strip(), (
            f"{e['variant_id']}: empty hypothesis"
        )
        for field in ("mechanism", "discard_if"):
            assert isinstance(pr[field], str) and pr[field].strip(), (
                f"{e['variant_id']}: empty prereg.{field}"
            )
        assert pr["date"] == "2026-07-20", f"{e['variant_id']}: bad date"
        assert isinstance(pr["author"], str) and pr["author"].strip()


def test_metric_names_both_signals(entries):
    for e in entries:
        metric = e["prereg"]["metric"]
        assert "net_honest" in metric, f"{e['variant_id']}: metric lacks net_honest"
        assert "mfe_capture" in metric, f"{e['variant_id']}: metric lacks mfe_capture"


# ---------------------------------------------------------------------------
# _meta holdout precommit
# ---------------------------------------------------------------------------
def test_meta_holdout_precommit_exact(manifest):
    meta = manifest["_meta"]
    assert meta["holdout_precommit"] == EXPECTED_HOLDOUT
    assert meta["holdout_window"] == "HOLDOUT-2026-01"


def test_every_entry_has_family_and_problem_tags(entries):
    for e in entries:
        assert e.get("family"), f"{e['variant_id']}: family tag missing"
        assert e.get("problem") in ("A", "B"), (
            f"{e['variant_id']}: problem tag not A/B"
        )


# ---------------------------------------------------------------------------
# kwargs validity: EVERY entry must be a valid simular_variant call
# ---------------------------------------------------------------------------
def test_every_kwargs_binds_to_signature(entries):
    sig = inspect.signature(simular_variant)
    bars = _synthetic_bars()
    for e in entries:
        kwargs = e["kwargs"]
        assert isinstance(kwargs, dict)
        # 1. every key is a real keyword-only param of simular_variant
        for key in kwargs:
            assert key in sig.parameters, (
                f"{e['variant_id']}: kwarg {key!r} is not a simular_variant param"
            )
        # 2. the signature binds cleanly (positional bars + these kwargs)
        try:
            sig.bind(bars, **kwargs)
        except TypeError as exc:  # pragma: no cover - failure path
            pytest.fail(f"{e['variant_id']}: bind failed: {exc}")


def test_every_kwargs_actually_runs(entries):
    """The strongest check: invoke simular_variant on a tiny synthetic bar list
    with each entry's kwargs; it must return without raising."""
    bars = _synthetic_bars()
    for e in entries:
        try:
            out = simular_variant(bars, **e["kwargs"])
        except Exception as exc:  # pragma: no cover - failure path
            pytest.fail(f"{e['variant_id']}: simular_variant raised: {exc!r}")
        assert isinstance(out, list), f"{e['variant_id']}: unexpected return type"


def test_sar_slow_encoded_as_list(entries):
    """JSON has no tuples: sar_slow (and sar_fast) must be 2-element lists that
    the engine indexes without error."""
    for e in entries:
        for key in ("sar_slow", "sar_fast"):
            if key in e["kwargs"]:
                val = e["kwargs"][key]
                assert isinstance(val, list) and len(val) == 2, (
                    f"{e['variant_id']}: {key} must be a 2-element list"
                )


# ---------------------------------------------------------------------------
# Base-control fidelity: controls carry no delta vs their named v3 bases.
# ---------------------------------------------------------------------------
def test_base_controls_match_v3_bases(entries):
    v3_path = (
        MANIFEST_PATH.parent / "honest_manifest_full_2026_07_20_v3.json"
    )
    with v3_path.open(encoding="utf-8") as fh:
        v3 = {x["variant_id"]: x for x in json.load(fh)["entries"]}
    by_id = {e["variant_id"]: e for e in entries}
    assert by_id["PX-BASE-S6K2P0"]["kwargs"] == v3["HON-W2-S6-K2P0-M15-SAR"]["kwargs"]
    assert by_id["PX-BASE-S7TPNONE"]["kwargs"] == v3["HON-S7-V15-TPNONE-BE1P0-M15"]["kwargs"]
