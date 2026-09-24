"""tests/live/test_spread_store.py -- GL-T2 adaptive running-min spread store.

Covers: strictly-smaller ratchet, larger-appends-but-no-ratchet, threshold =
min+eps, persistence across reload, atomic-write survives a simulated mid-write
interruption, samples log append-only. All in a tmp dir; no MT5, no orders.
"""
from __future__ import annotations

import json

import pytest

from sentinel_engine.live.spread_store import SpreadStore


def _store(tmp_path, **kw):
    return SpreadStore(store_path=tmp_path / "store.json",
                       samples_path=tmp_path / "samples.csv", **kw)


# -- ratchet semantics -------------------------------------------------------
def test_record_first_sample_sets_min(tmp_path):
    s = _store(tmp_path)
    assert s.running_min is None
    assert s.record(0.60, ts=1.0) == pytest.approx(0.60)
    assert s.running_min == pytest.approx(0.60)
    assert s.sample_count == 1


def test_record_ratchets_min_only_on_strictly_smaller(tmp_path):
    s = _store(tmp_path)
    s.record(0.60, ts=1.0)
    # strictly smaller -> ratchets down
    s.record(0.40, ts=2.0)
    assert s.running_min == pytest.approx(0.40)
    assert s.sample_count == 2


def test_larger_spread_appended_but_does_not_change_min(tmp_path):
    s = _store(tmp_path)
    s.record(0.40, ts=1.0)
    rm = s.record(0.90, ts=2.0)  # larger
    assert rm == pytest.approx(0.40), "min must NOT rise on a larger spread"
    assert s.running_min == pytest.approx(0.40)
    assert s.sample_count == 2, "the larger spread IS still counted/appended"
    assert s.last_spread == pytest.approx(0.90)


def test_equal_spread_does_not_ratchet_but_is_counted(tmp_path):
    # equal is NOT strictly-smaller -> min unchanged, ts of min preserved.
    s = _store(tmp_path)
    s.record(0.60, ts=1.0)
    s.record(0.60, ts=2.0)
    assert s.running_min == pytest.approx(0.60)
    assert s.running_min_ts is not None
    assert s.sample_count == 2


def test_bad_spread_ignored(tmp_path):
    s = _store(tmp_path)
    s.record(0.60, ts=1.0)
    assert s.record(float("nan"), ts=2.0) == pytest.approx(0.60)
    assert s.record(-1.0, ts=3.0) == pytest.approx(0.60)
    assert s.sample_count == 1, "bad ticks are not recorded"


# -- threshold ---------------------------------------------------------------
def test_threshold_is_min_plus_eps(tmp_path):
    s = _store(tmp_path)
    s.record(0.60, ts=1.0)
    assert s.threshold(0.0) == pytest.approx(0.60)
    assert s.threshold(0.02) == pytest.approx(0.62)


def test_threshold_none_when_empty(tmp_path):
    s = _store(tmp_path)
    assert s.threshold(0.05) is None


def test_fixed_060_admitted_by_default_eps(tmp_path):
    # Regression for the fixed-0.60 demo regime: min becomes 0.60, threshold is
    # essentially 0.60 (tiny eps), so 0.60 trades but 0.61 does NOT.
    from scripts.live.run_live_20 import DEFAULT_SPREAD_EPS
    s = _store(tmp_path)
    s.record(0.60, ts=1.0)
    thr = s.threshold(DEFAULT_SPREAD_EPS)
    assert 0.60 <= thr  # min admitted
    assert 0.61 > thr, "eps must be a tiny tolerance, NOT a 0.10 band -> 0.61 excluded"
    assert DEFAULT_SPREAD_EPS < 0.01, "eps must be sub-tick (float-equality only)"


# -- persistence -------------------------------------------------------------
def test_persistence_survives_reload(tmp_path):
    s = _store(tmp_path)
    s.record(0.60, ts=1.0)
    s.record(0.35, ts=2.0)
    s.record(0.80, ts=3.0)
    # brand-new instance pointed at the same files
    s2 = _store(tmp_path)
    assert s2.running_min == pytest.approx(0.35)
    assert s2.sample_count == 3
    assert s2.last_spread == pytest.approx(0.80)
    # a further-smaller sample continues ratcheting from the reloaded state
    s2.record(0.20, ts=4.0)
    assert s2.running_min == pytest.approx(0.20)
    assert s2.sample_count == 4


def test_samples_log_is_append_only(tmp_path):
    s = _store(tmp_path)
    s.record(0.60, ts=1.0)
    s.record(0.40, ts=2.0)
    text = (tmp_path / "samples.csv").read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[0] == "ts,spread"
    assert len(lines) == 3  # header + 2 rows
    # reopening + recording appends, does not rewrite the header
    s2 = _store(tmp_path)
    s2.record(0.30, ts=3.0)
    lines2 = [ln for ln in (tmp_path / "samples.csv").read_text().splitlines() if ln.strip()]
    assert len(lines2) == 4
    assert lines2.count("ts,spread") == 1


# -- atomic write ------------------------------------------------------------
def test_atomic_write_survives_midwrite_interruption(tmp_path, monkeypatch):
    """Simulate a crash DURING a record's persist (os.replace raises). The
    ORIGINAL store file must remain valid & complete (old running-min), and no
    torn temp file should be left masquerading as the store."""
    s = _store(tmp_path)
    s.record(0.60, ts=1.0)  # establishes a good store on disk

    import sentinel_engine.live.spread_store as mod

    real_replace = mod.os.replace

    def _boom(src, dst):
        raise OSError("simulated crash during os.replace")

    monkeypatch.setattr(mod.os, "replace", _boom)
    with pytest.raises(OSError):
        s.record(0.20, ts=2.0)  # would ratchet, but the write is interrupted
    monkeypatch.setattr(mod.os, "replace", real_replace)

    # the on-disk store must still be the last GOOD one (0.60), fully valid JSON
    on_disk = json.loads((tmp_path / "store.json").read_text(encoding="utf-8"))
    assert on_disk["running_min"] == pytest.approx(0.60)
    # and a fresh reload reads the good value, not a corrupt/torn file
    s2 = _store(tmp_path)
    assert s2.running_min == pytest.approx(0.60)
    # no leftover temp file pretending to be the store
    leftovers = list(tmp_path.glob("store.json.*.tmp"))
    assert leftovers == []


def test_corrupt_store_treated_as_empty(tmp_path):
    (tmp_path / "store.json").write_text("{ this is not json", encoding="utf-8")
    s = _store(tmp_path)  # load() must not crash
    assert s.running_min is None
    # and it can still start recording fresh
    s.record(0.5, ts=1.0)
    assert s.running_min == pytest.approx(0.5)
