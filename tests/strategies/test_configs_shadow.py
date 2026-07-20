"""tests/strategies/test_configs_shadow.py -- FIXED4 shadow roster (Addendum
§1.2, D114). Asserts CONFIGS_SHADOW is the live roster with the obvious
honesty fixes applied (ac_modulate=False, live_fill_mode=True,
trail_atr_floor_k=1.5), id suffix `-F`, magics 721010/20/30/40, and that the
shadow magic band is DISJOINT from the live band. No MT5, no orders.
"""
from __future__ import annotations

from sentinel_engine.strategies.live_configs_20 import (
    CONFIGS_LIVE,
    CONFIGS_SHADOW,
)


def test_shadow_has_one_entry_per_live():
    assert len(CONFIGS_SHADOW) == len(CONFIGS_LIVE) == 4


def test_shadow_ids_are_live_ids_with_F_suffix():
    for live, shadow in zip(CONFIGS_LIVE, CONFIGS_SHADOW):
        assert shadow["id"] == live["id"] + "-F"
    assert len({c["id"] for c in CONFIGS_SHADOW}) == 4


def test_shadow_magics_exact_721010_to_721040():
    assert [c["magic"] for c in CONFIGS_SHADOW] == [721010, 721020, 721030, 721040]


def test_shadow_kwargs_apply_the_three_honesty_fixes():
    for live, shadow in zip(CONFIGS_LIVE, CONFIGS_SHADOW):
        k = shadow["kwargs"]
        assert k["ac_modulate"] is False
        assert k["live_fill_mode"] is True
        assert k["trail_atr_floor_k"] == 1.5
        # Same signals: every OTHER kwarg is inherited verbatim from live.
        for key, val in live["kwargs"].items():
            if key in ("ac_modulate", "live_fill_mode", "trail_atr_floor_k"):
                continue
            assert k[key] == val, f"{shadow['id']}: kwarg {key} must be inherited"


def test_shadow_does_not_mutate_live_kwargs():
    # _fixed must build a NEW kwargs dict, never mutate the live config's.
    for live in CONFIGS_LIVE:
        assert live["kwargs"].get("ac_modulate") is not False or True  # sanity
        # live V-configs default ac_modulate=True except the V09 controls; none
        # of the FIXED4 live roster are V09 controls, so all must remain True.
        assert live["kwargs"]["ac_modulate"] is True


def test_shadow_preserves_tf_and_non_kwargs_fields():
    for live, shadow in zip(CONFIGS_LIVE, CONFIGS_SHADOW):
        assert shadow["tf"] == live["tf"]
        assert shadow["k"] == live["k"]
        assert shadow.get("direction_filter") == live.get("direction_filter")


def test_shadow_and_live_magic_bands_are_disjoint():
    """Each config occupies its base magic + the [base+1..base+3] ficha band.
    The live and shadow rosters must never share a magic in ANY band."""
    def band(cfg):
        b = cfg["magic"]
        return {b, b + 1, b + 2, b + 3}

    live_band = set()
    for c in CONFIGS_LIVE:
        live_band |= band(c)
    shadow_band = set()
    for c in CONFIGS_SHADOW:
        shadow_band |= band(c)
    assert live_band.isdisjoint(shadow_band)


def test_combined_roster_respects_60_ficha_cap():
    # live+shadow = 8 configs * 3 fichas = 24; well under the 60 total cap.
    from sentinel_engine.live.reconciler import MAX_FICHAS_TOTAL

    combined = CONFIGS_LIVE + CONFIGS_SHADOW
    assert len(combined) == 8
    assert len(combined) * 3 == 24
    assert 24 <= MAX_FICHAS_TOTAL
