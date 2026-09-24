"""tests/strategies/test_live_configs_local.py -- the machine-1 LOCAL roster
`CONFIGS_LOCAL` (`sentinel_engine.strategies.live_configs_20`, trader's
machine-1 selection 2026-07-22).

Covers:
  * `CONFIGS_LOCAL`: exactly 4 configs -- S6-K2P0, S7-TPNONE,
    SuperTrend-p14x3-M15 (magics 724010/724020/724070 UNCHANGED) at 0.1 lot +
    TK-Momentum-5-8-short (magic 999999998) at 0.01 lot; NO V11-M2, NO shadow;
    pairwise-disjoint magic bands.
  * HARD IMMUTABILITY: local's per-config volumes are on INDEPENDENT COPIES --
    the SHARED S6-K2P0/S7-TPNONE/SuperTrend dicts (served by CONFIGS_GOLIVE /
    CONFIGS_TOMACHINE) and CONFIG_TK_MOMENTUM must NOT have gained a `volume`
    key, so machine-2's tomachine lot stays the global --volume.
"""
from __future__ import annotations

from sentinel_engine.strategies.live_configs_20 import (
    CONFIG_TK_MOMENTUM,
    CONFIGS_GOLIVE,
    CONFIGS_LOCAL,
    CONFIGS_SHADOW,
    CONFIGS_TOMACHINE,
)

_SHARED_GOLIVE_IDS = ("S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15")


# --------------------------------------------------------------------------
# CONFIGS_LOCAL roster shape
# --------------------------------------------------------------------------
def test_local_is_exactly_four_configs():
    assert len(CONFIGS_LOCAL) == 4


def test_local_ids_and_magics_exact():
    assert [c["id"] for c in CONFIGS_LOCAL] == [
        "S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15", "TK-Momentum-5-8-short",
    ]
    assert [c["magic"] for c in CONFIGS_LOCAL] == [
        724010, 724020, 724070, 999999998,
    ]


def test_local_ids_unique():
    ids = [c["id"] for c in CONFIGS_LOCAL]
    assert len(ids) == len(set(ids))


def test_local_excludes_v11_m2():
    assert "V11-M2" not in {c["id"] for c in CONFIGS_LOCAL}


def test_local_excludes_shadow_fixed4():
    local_ids = {c["id"] for c in CONFIGS_LOCAL}
    for c in CONFIGS_SHADOW:
        assert c["id"] not in local_ids


def test_local_volumes():
    by_id = {c["id"]: c for c in CONFIGS_LOCAL}
    for cid in _SHARED_GOLIVE_IDS:
        assert by_id[cid]["volume"] == 0.1, f"{cid} local volume must be 0.1"
    assert by_id["TK-Momentum-5-8-short"]["volume"] == 0.01


def test_local_magic_bands_pairwise_disjoint():
    seen: set[int] = set()
    for c in CONFIGS_LOCAL:
        band = {c["magic"] + off for off in range(4)}
        assert seen.isdisjoint(band), f"magic band overlap at {c['id']}"
        seen |= band


# --------------------------------------------------------------------------
# HARD IMMUTABILITY -- the whole point: no volume leak into shared objects
# --------------------------------------------------------------------------
def test_local_uses_independent_copies_not_shared_objects():
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    local_by_id = {c["id"]: c for c in CONFIGS_LOCAL}
    for cid in _SHARED_GOLIVE_IDS:
        assert local_by_id[cid] is not golive_by_id[cid], \
            f"{cid} local config must be an independent COPY, not the shared object"
    assert local_by_id["TK-Momentum-5-8-short"] is not CONFIG_TK_MOMENTUM


def test_shared_golive_objects_have_no_volume_key():
    # local's 0.1 must NOT have leaked into the SHARED S6/S7/SuperTrend dicts.
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for cid in _SHARED_GOLIVE_IDS:
        assert "volume" not in golive_by_id[cid], \
            f"local's 0.1 leaked into shared CONFIGS_GOLIVE[{cid}]"


def test_tomachine_configs_have_no_volume_key():
    # tomachine's S6/S7/SuperTrend are the SAME shared dicts -> must stay
    # volume-free so machine-2's lot stays the global --volume (0.01).
    for c in CONFIGS_TOMACHINE:
        assert "volume" not in c, \
            f"tomachine config {c['id']} must NOT carry a volume (leak protection)"


def test_shared_tk_momentum_object_has_no_volume_key():
    assert "volume" not in CONFIG_TK_MOMENTUM, \
        "local's 0.01 leaked into the shared CONFIG_TK_MOMENTUM dict"
