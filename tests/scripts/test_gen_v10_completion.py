"""tests/scripts/test_gen_v10_completion.py -- Wave 5, Task V-10 honest completion.

Pins the ADDITIVE-ONLY extension to `scripts/report/gen_oow_validation.py` that
brings the V-10 `direction_mask` family to M1/M2 (in addition to the existing
M5/M15 cells), plus the small `gen_v10_completion` coverage helper.

Constraints enforced here:
- ADDITIVE-ONLY: the pre-existing `v10-m5` / `v10-m15` CONFIGS entries and their
  shape are UNCHANGED (no regression to persisted rows).
- The new `v10-m1` / `v10-m2` CONFIGS entries mirror the v10-m5 / v10-m15 shape:
  same `direction_mask=True` flag, same `ac_modulate_factor=0.25` lever, correct
  `tf`. M1 gains an `init_sl_range_k` entry so `skeleton_kwargs("M1")` resolves.
- No lake / research.db dependency: all assertions are on module constants and
  pure helpers (config_kwargs stubs the mask so it never touches the lake).
"""
from __future__ import annotations

from scripts.report import gen_oow_validation as m
from scripts.report import gen_v10_completion as vc


# ---------------------------------------------------------------------------
# Additive CONFIGS: new v10-m1 / v10-m2 present and well-formed.
# ---------------------------------------------------------------------------
def test_v10_m1_m2_configs_added_and_wellformed() -> None:
    for cfg_id, tf in (("v10-m1", "M1"), ("v10-m2", "M2")):
        assert cfg_id in m.CONFIGS, f"{cfg_id} missing from CONFIGS"
        cfg = m.CONFIGS[cfg_id]
        assert cfg["tf"] == tf
        assert cfg.get("direction_mask") is True, f"{cfg_id} must carry direction_mask=True"
        assert cfg["extra"]["ac_modulate_factor"] == 0.25


def test_m1_tf_supported_in_skeleton() -> None:
    # M1 must resolve an init_sl_range_k so skeleton_kwargs("M1") does not KeyError.
    assert "M1" in m.INIT_SL_RANGE_K
    kw = m.skeleton_kwargs("M1")
    assert kw["init_sl_range_k"] == m.INIT_SL_RANGE_K["M1"]


# ---------------------------------------------------------------------------
# Additive-only: existing v10-m5 / v10-m15 entries UNCHANGED.
# ---------------------------------------------------------------------------
def test_existing_v10_m5_m15_unchanged() -> None:
    assert m.CONFIGS["v10-m15"] == dict(
        tf="M15", extra=dict(ac_modulate_factor=0.25), direction_mask=True)
    assert m.CONFIGS["v10-m5"] == dict(
        tf="M5", extra=dict(ac_modulate_factor=0.25), direction_mask=True)


def test_config_kwargs_v10_m1_masks_via_stub(monkeypatch) -> None:
    # config_kwargs must rebuild the mask array via _mask_for for the new M1
    # entry, exactly like it does for m5/m15 -- stub _mask_for so no lake needed.
    monkeypatch.setattr(m, "_mask_for", lambda tf, win: [0, 1, -1])
    kwargs = m.config_kwargs("v10-m1", "W1")
    assert kwargs["direction_mask"] == [0, 1, -1]
    assert kwargs["init_sl_range_k"] == m.INIT_SL_RANGE_K["M1"]
    assert kwargs["ac_modulate_factor"] == 0.25


# ---------------------------------------------------------------------------
# gen_v10_completion coverage matrix: honest lake-feasibility, no fabrication.
# ---------------------------------------------------------------------------
def test_lake_feasibility_matrix_marks_missing_windows() -> None:
    # M1 lake starts 2026-03 -> W3 (2025-10) and W2 warmup (2026-02) unavailable;
    # M2 lake starts 2025-12 -> W3 unavailable. This is a pure month-set check,
    # so it runs with no lake files present.
    feasible = vc.lake_feasible
    assert feasible("M5", "W1") and feasible("M5", "W3")
    assert feasible("M15", "W2")
    assert feasible("M1", "W1") is True
    assert feasible("M1", "W3") is False
    assert feasible("M2", "W3") is False
    assert feasible("M2", "W1") is True and feasible("M2", "W2") is True
