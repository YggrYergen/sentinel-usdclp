"""tests/strategies/test_live_configs_tomachine.py -- TK-BW2-fix2atr live
config + the machine-2 `tomachine` roster (`sentinel_engine.strategies.
live_configs_20`, 2026-07-22 trader's machine-2 selection).

Covers:
  * `CONFIG_TK_BW2_FIX2ATR`: id/tf/engine/magic band + kwargs == the EXACT
    fix2atr params from `scripts.research.run_tk_bw_v2_backtest` (single
    source of truth -- no re-typed params allowed to drift).
  * `CONFIGS_TOMACHINE`: 3 named golive configs (S6-K2P0, S7-TPNONE,
    SuperTrend-p14x3-M15) + CONFIG_TK_BW2_FIX2ATR == 4 configs, unique ids,
    pairwise-disjoint magic bands, and explicitly WITHOUT the FIXED4 shadow
    configs, V11-M2, or TK-Momentum (trader's machine-2 selection
    2026-07-22 -- shadow configs removed from this roster).
"""
from __future__ import annotations

from scripts.research.run_tk_bw_v2_backtest import _COMMON_PARAMS, CONFIGS
from sentinel_engine.strategies.live_configs_20 import (
    CONFIG_TK_BW2_FIX2ATR,
    CONFIGS_GOLIVE,
    CONFIGS_SHADOW,
    CONFIGS_TOMACHINE,
)


# --------------------------------------------------------------------------
# CONFIG_TK_BW2_FIX2ATR
# --------------------------------------------------------------------------
def test_tk_bw2_fix2atr_id_tf_engine():
    c = CONFIG_TK_BW2_FIX2ATR
    assert c["id"] == "TK-BW2-fix2atr"
    assert c["tf"] == "M5"
    assert c["engine"] == "tk_bw2_fix2atr"
    assert c["kwargs"]["symbol"] == "XAUUSD"


def test_tk_bw2_fix2atr_magic_base_and_band():
    c = CONFIG_TK_BW2_FIX2ATR
    assert c["magic"] == 725010
    band = {c["magic"] + off for off in range(4)}
    assert band == {725010, 725011, 725012, 725013}


def test_tk_bw2_fix2atr_band_disjoint_from_all_existing_and_reserved():
    c = CONFIG_TK_BW2_FIX2ATR
    band = {c["magic"] + off for off in range(4)}
    from sentinel_engine.strategies.live_configs_20 import (
        CONFIGS_20, CONFIGS_SHADOW as _SHADOW, CONFIGS_GOLIVE as _GOLIVE,
        CONFIGS_TK as _TK,
    )
    other_bands = set()
    for cfg in list(CONFIGS_20) + list(_SHADOW) + list(_GOLIVE) + list(_TK):
        other_bands |= {cfg["magic"] + off for off in range(4)}
    assert band.isdisjoint(other_bands), "TK-BW2-fix2atr band overlaps an existing config band"
    # RESERVED 722xxx/723xxx blocks (per plan) must never be touched either.
    assert all(not (722000 <= m <= 723999) for m in band)


def test_tk_bw2_fix2atr_kwargs_match_runner_single_source_of_truth():
    """The live engine params MUST equal the research runner's fix2atr
    config exactly -- imported/replicated from ONE source, never re-typed."""
    expected = dict(_COMMON_PARAMS)
    expected.update(CONFIGS["fix2atr"])
    c = CONFIG_TK_BW2_FIX2ATR
    live_engine_kwargs = {k: v for k, v in c["kwargs"].items() if k != "symbol"}
    assert live_engine_kwargs == expected


# --------------------------------------------------------------------------
# CONFIGS_TOMACHINE roster
# --------------------------------------------------------------------------
def test_tomachine_is_exactly_four_configs():
    assert len(CONFIGS_TOMACHINE) == 4


def test_tomachine_ids_unique():
    ids = [c["id"] for c in CONFIGS_TOMACHINE]
    assert len(ids) == len(set(ids))


def test_tomachine_ids_and_magics_exact():
    assert [c["id"] for c in CONFIGS_TOMACHINE] == [
        "S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15", "TK-BW2-fix2atr",
    ]
    assert [c["magic"] for c in CONFIGS_TOMACHINE] == [
        724010, 724020, 724070, 725010,
    ]


def test_tomachine_excludes_shadow_fixed4():
    tomachine_ids = {c["id"] for c in CONFIGS_TOMACHINE}
    tomachine_magics = {c["magic"] for c in CONFIGS_TOMACHINE}
    for c in CONFIGS_SHADOW:
        assert c["id"] not in tomachine_ids
        assert c["magic"] not in tomachine_magics
        assert 721000 <= c["magic"] <= 721999, \
            "sanity: shadow magics expected in the 721xxx band"


def test_tomachine_contains_three_named_golive_configs_unchanged_magics():
    by_id = {c["id"]: c for c in CONFIGS_TOMACHINE}
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for cid in ("S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"):
        assert cid in by_id, f"{cid} missing from tomachine roster"
        assert by_id[cid]["magic"] == golive_by_id[cid]["magic"], \
            f"{cid} magic must be UNCHANGED from CONFIGS_GOLIVE"
    assert by_id["S6-K2P0"]["magic"] == 724010
    assert by_id["S7-TPNONE"]["magic"] == 724020
    assert by_id["SuperTrend-p14x3-M15"]["magic"] == 724070


def test_tomachine_contains_tk_bw2_fix2atr():
    ids = {c["id"] for c in CONFIGS_TOMACHINE}
    assert "TK-BW2-fix2atr" in ids


def test_tomachine_excludes_v11_m2_and_tk_momentum():
    ids = {c["id"] for c in CONFIGS_TOMACHINE}
    assert "V11-M2" not in ids
    assert "TK-Momentum-5-8-short" not in ids


def test_tomachine_magic_bands_pairwise_disjoint():
    seen: set[int] = set()
    for c in CONFIGS_TOMACHINE:
        band = {c["magic"] + off for off in range(4)}
        assert seen.isdisjoint(band), f"magic band overlap at {c['id']}"
        seen |= band
