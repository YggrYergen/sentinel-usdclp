"""tests/strategies/test_live_configs_tomachine.py -- TK-BW2-fix2atr live
config + the machine-2 `tomachine` roster (`sentinel_engine.strategies.
live_configs_20`, owner's machine-2 selection 2026-07-27).

Covers:
  * `CONFIG_TK_BW2_FIX2ATR`: id/tf/engine/magic band + kwargs == the EXACT
    fix2atr params from `scripts.research.run_tk_bw_v2_backtest` (single
    source of truth -- no re-typed params allowed to drift). The config stays
    DEFINED in the module even though it left the tomachine roster on
    2026-07-27, so this coverage stays valid as-is.
  * `CONFIGS_TOMACHINE`: exactly 2 configs -- S6-K2P0 (724010) and
    SuperTrend-p14x3-M15 (724070), magics UNCHANGED from CONFIGS_GOLIVE, each
    at 0.3 lot, S6 single-ficha (`active_fichas == 1`) and SuperTrend without
    the kwarg (its always-in engine takes none). Unique ids, pairwise-disjoint
    magic bands, and explicitly WITHOUT S7-TPNONE, TK-BW2-fix2atr, V11-M2,
    TK-Momentum or the FIXED4 shadow configs.
  * IMMUTABILITY: the 0.3 / active_fichas=1 overrides live on independent deep
    COPIES -- the SHARED go-live dicts keep no `volume` and no `active_fichas`.
"""
from __future__ import annotations

from scripts.research.run_tk_bw_v2_backtest import _COMMON_PARAMS, CONFIGS
from sentinel_engine.strategies.live_configs_20 import (
    CONFIG_TK_BW2_FIX2ATR,
    CONFIGS_GOLIVE,
    CONFIGS_SHADOW,
    CONFIGS_TOMACHINE,
)

_TOMACHINE_IDS = ("S6-K2P0", "SuperTrend-p14x3-M15")
# the go-live dicts shared by reference across CONFIGS_GOLIVE /
# CONFIGS_GOLIVE_DEDUP that tomachine and local both deep-copy from.
_SHARED_GOLIVE_IDS = ("S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15")


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
def test_tomachine_is_exactly_two_configs():
    assert len(CONFIGS_TOMACHINE) == 2


def test_tomachine_ids_unique():
    ids = [c["id"] for c in CONFIGS_TOMACHINE]
    assert len(ids) == len(set(ids))


def test_tomachine_ids_and_magics_exact():
    assert [c["id"] for c in CONFIGS_TOMACHINE] == [
        "S6-K2P0", "SuperTrend-p14x3-M15",
    ]
    assert [c["magic"] for c in CONFIGS_TOMACHINE] == [724010, 724070]


def test_tomachine_excludes_shadow_fixed4():
    tomachine_ids = {c["id"] for c in CONFIGS_TOMACHINE}
    tomachine_magics = {c["magic"] for c in CONFIGS_TOMACHINE}
    for c in CONFIGS_SHADOW:
        assert c["id"] not in tomachine_ids
        assert c["magic"] not in tomachine_magics
        assert 721000 <= c["magic"] <= 721999, \
            "sanity: shadow magics expected in the 721xxx band"


def test_tomachine_contains_two_named_golive_configs_unchanged_magics():
    by_id = {c["id"]: c for c in CONFIGS_TOMACHINE}
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for cid in _TOMACHINE_IDS:
        assert cid in by_id, f"{cid} missing from tomachine roster"
        assert by_id[cid]["magic"] == golive_by_id[cid]["magic"], \
            f"{cid} magic must be UNCHANGED from CONFIGS_GOLIVE"
    assert by_id["S6-K2P0"]["magic"] == 724010
    assert by_id["SuperTrend-p14x3-M15"]["magic"] == 724070


def test_tomachine_does_not_contain_tk_bw2_fix2atr():
    # TK-BW2-fix2atr LEFT the roster on 2026-07-27 (owner's selection). The
    # roster must be EXACTLY the trader's selection -- nothing extra survives
    # here just because it is still defined in the module.
    ids = {c["id"] for c in CONFIGS_TOMACHINE}
    assert "TK-BW2-fix2atr" not in ids


def test_tomachine_excludes_v11_m2_tk_momentum_s7_and_tk_bw2():
    ids = {c["id"] for c in CONFIGS_TOMACHINE}
    assert "V11-M2" not in ids
    assert "TK-Momentum-5-8-short" not in ids
    # dropped by the owner's 2026-07-27 selection (S6 + SuperTrend only).
    assert "S7-TPNONE" not in ids
    assert "TK-BW2-fix2atr" not in ids


def test_tomachine_magic_bands_pairwise_disjoint():
    seen: set[int] = set()
    for c in CONFIGS_TOMACHINE:
        band = {c["magic"] + off for off in range(4)}
        assert seen.isdisjoint(band), f"magic band overlap at {c['id']}"
        seen |= band


# --------------------------------------------------------------------------
# owner's 2026-07-27 sizing + single-ficha decision
# --------------------------------------------------------------------------
def test_tomachine_volume_is_zero_point_three_on_both_configs():
    for c in CONFIGS_TOMACHINE:
        assert c["volume"] == 0.3, f"{c['id']} tomachine volume must be 0.3"


def test_tomachine_s6_runs_a_single_ficha():
    by_id = {c["id"]: c for c in CONFIGS_TOMACHINE}
    assert by_id["S6-K2P0"]["kwargs"]["active_fichas"] == 1


def test_tomachine_supertrend_has_no_active_fichas_kwarg():
    # `supertrend_always_in_target` accepts only `bars` and already emits a
    # single ficha F1 -- passing active_fichas would be inert and wrong.
    by_id = {c["id"]: c for c in CONFIGS_TOMACHINE}
    st = by_id["SuperTrend-p14x3-M15"]
    assert st["engine"] == "supertrend_always_in"
    assert "active_fichas" not in st["kwargs"]
    assert st["kwargs"] == {"symbol": "XAUUSD"}


# --------------------------------------------------------------------------
# HARD IMMUTABILITY -- overrides live on independent deep COPIES
# --------------------------------------------------------------------------
def test_tomachine_uses_independent_copies_not_shared_golive_objects():
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    tomachine_by_id = {c["id"]: c for c in CONFIGS_TOMACHINE}
    for cid in _TOMACHINE_IDS:
        assert tomachine_by_id[cid] is not golive_by_id[cid], \
            f"{cid} tomachine config must be an independent COPY"
        assert tomachine_by_id[cid]["kwargs"] is not golive_by_id[cid]["kwargs"], \
            f"{cid} tomachine kwargs must be a deep COPY, not the shared dict"


def test_shared_golive_dicts_have_no_volume_and_no_active_fichas():
    # tomachine's 0.3 / active_fichas=1 must NOT have leaked into the SHARED
    # S6/S7/SuperTrend dicts served by CONFIGS_GOLIVE + CONFIGS_GOLIVE_DEDUP
    # (they must keep the global --volume and the engine default 3 fichas).
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for cid in _SHARED_GOLIVE_IDS:
        src = golive_by_id[cid]
        assert "volume" not in src, f"a per-config volume leaked into shared {cid}"
        assert "active_fichas" not in src["kwargs"], \
            f"active_fichas leaked into shared {cid} kwargs (default 3 broken)"
