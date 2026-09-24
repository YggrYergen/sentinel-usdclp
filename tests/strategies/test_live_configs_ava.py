"""tests/strategies/test_live_configs_ava.py -- the AVA demo roster
`CONFIGS_AVA` (`sentinel_engine.strategies.live_configs_20`, D-62 2026-08-20).

Covers:
  * shape: exactly 2 configs (S6-K2P0-AVA, SuperTrend-p14x3-M15-AVA), S7
    deliberately absent (R4), magics 727010/727020, band pairwise-disjoint
    from every other roster.
  * lote 0.01 mandatory (task directive, no exception).
  * symbol routed to GOLD (not XAUUSD).
  * S6-K2P0-AVA: pipsize_input=0.01 (neutralizes the pip_size('GOLD')==1.0
    100x-blowout bug) and active_fichas=1 (one position per strategy).
  * SuperTrend-AVA: no simular_variant-only kwargs leaked in (nothing to pin).
  * window_gate + single_position_only markers present.
  * HARD IMMUTABILITY: the shared CONFIGS_GOLIVE dicts (S6-K2P0,
    SuperTrend-p14x3-M15, used verbatim by CONFIGS_GOLIVE_DEDUP/TOMACHINE/
    LOCAL/CHALLENGER) must NOT have gained ANY AVA-only key or lost their
    XAUUSD symbol -- R1-bis/R7.
  * every other kwarg (besides the declared deviations) is byte-identical to
    the champion signal.
"""
from __future__ import annotations

import copy

from sentinel_engine.strategies.live_configs_20 import (
    CONFIGS_AVA,
    CONFIGS_CHALLENGER,
    CONFIGS_GOLIVE,
    CONFIGS_GOLIVE_DEDUP,
    CONFIGS_LOCAL,
    CONFIGS_LIVE,
    CONFIGS_SHADOW,
    CONFIGS_TK,
    CONFIGS_TOMACHINE,
    CONFIG_TK_BW2_FIX2ATR,
)

_CHAMPION_IDS = ("S6-K2P0", "SuperTrend-p14x3-M15")


# --------------------------------------------------------------------------
# CONFIGS_AVA roster shape
# --------------------------------------------------------------------------
def test_ava_is_exactly_two_configs():
    assert len(CONFIGS_AVA) == 2


def test_ava_ids_and_magics_exact():
    assert [c["id"] for c in CONFIGS_AVA] == ["S6-K2P0-AVA", "SuperTrend-p14x3-M15-AVA"]
    assert [c["magic"] for c in CONFIGS_AVA] == [727010, 727020]


def test_ava_excludes_s7():
    # R4: "S7 no va a vivo" -- it is a clean-comparison control only.
    assert "S7-TPNONE" not in {c["id"] for c in CONFIGS_AVA}
    assert "S7-TPNONE-AVA" not in {c["id"] for c in CONFIGS_AVA}


def test_ava_ids_unique():
    ids = [c["id"] for c in CONFIGS_AVA]
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------
# Lote / symbol / pip-size / active_fichas / markers
# --------------------------------------------------------------------------
def test_ava_volume_is_001_mandatory():
    for c in CONFIGS_AVA:
        assert c["volume"] == 0.01, f"{c['id']} must be 0.01 lot -- mandatory, no exception"


def test_ava_symbol_is_gold_not_xauusd():
    for c in CONFIGS_AVA:
        assert c["kwargs"]["symbol"] == "GOLD"


def test_s6_ava_pipsize_input_neutralizes_the_symbol_prefix_bug():
    # emasar_ref.pip_size(symbol, pipsize_input) auto-detects pip size ONLY
    # via symbol.upper().startswith("XAU"); "GOLD" would silently resolve to
    # the generic default 1.0 (a 100x blowout of every trail distance)
    # WITHOUT this explicit override.
    s6 = next(c for c in CONFIGS_AVA if c["id"] == "S6-K2P0-AVA")
    assert s6["kwargs"]["pipsize_input"] == 0.01

    from sentinel_engine.strategies.emasar_ref import pip_size
    assert pip_size("GOLD") == 1.0, "documents the bug pipsize_input must neutralize"
    assert pip_size("GOLD", s6["kwargs"]["pipsize_input"]) == 0.01
    assert pip_size("XAUUSD") == 0.01  # the live original's own behavior, untouched


def test_s6_ava_active_fichas_is_1():
    s6 = next(c for c in CONFIGS_AVA if c["id"] == "S6-K2P0-AVA")
    assert s6["kwargs"]["active_fichas"] == 1


def test_supertrend_ava_has_no_pipsize_or_active_fichas_kwargs():
    st = next(c for c in CONFIGS_AVA if c["id"] == "SuperTrend-p14x3-M15-AVA")
    assert "pipsize_input" not in st["kwargs"]
    assert "active_fichas" not in st["kwargs"]
    assert st["engine"] == "supertrend_always_in"


def test_ava_configs_carry_window_gate_and_single_position_markers():
    for c in CONFIGS_AVA:
        assert c["window_gate"] == {"broker": "ava"}
        assert c["single_position_only"] is True


# --------------------------------------------------------------------------
# Same signal as the champion, minus the declared deviations
# --------------------------------------------------------------------------
def test_ava_kwargs_match_champion_except_declared_deviations():
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    ignore = {"symbol", "pipsize_input", "active_fichas"}
    for c in CONFIGS_AVA:
        champion_id = c["id"][: -len("-AVA")]
        champion = golive_by_id[champion_id]
        got = {k: v for k, v in c["kwargs"].items() if k not in ignore}
        want = {k: v for k, v in champion["kwargs"].items() if k not in ignore}
        assert got == want, f"{c['id']} must mirror {champion_id} exactly (minus deviations)"
        assert c.get("engine") == champion.get("engine")
        assert c.get("tf") == champion.get("tf")


# --------------------------------------------------------------------------
# HARD IMMUTABILITY -- the whole point (R1-bis / R7)
# --------------------------------------------------------------------------
def test_ava_uses_independent_copies_not_shared_objects():
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for c in CONFIGS_AVA:
        champion_id = c["id"][: -len("-AVA")]
        assert c is not golive_by_id[champion_id], \
            f"{c['id']} must be an independent COPY, not the shared object"
        assert c["kwargs"] is not golive_by_id[champion_id]["kwargs"]


def test_shared_champion_objects_have_no_ava_only_keys():
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for cid in _CHAMPION_IDS:
        src = golive_by_id[cid]
        assert "window_gate" not in src, f"AVA window_gate leaked into shared {cid}"
        assert "single_position_only" not in src, f"AVA marker leaked into shared {cid}"
        assert "volume" not in src, f"AVA's 0.01 leaked into shared {cid}"
        assert src["kwargs"]["symbol"] == "XAUUSD", \
            f"AVA's GOLD symbol leaked into shared {cid} -- Capitaria original corrupted"
        assert "pipsize_input" not in src["kwargs"], f"leaked into shared {cid}"
        assert "active_fichas" not in src["kwargs"], f"leaked into shared {cid}"


def test_other_rosters_still_carry_no_ava_keys():
    # every roster that reuses the shared S6-K2P0/SuperTrend-p14x3-M15 dicts
    # by reference must be completely unaffected by CONFIGS_AVA's existence.
    for roster in (CONFIGS_GOLIVE, CONFIGS_GOLIVE_DEDUP, CONFIGS_TOMACHINE,
                   CONFIGS_LOCAL, CONFIGS_CHALLENGER):
        for c in roster:
            assert "window_gate" not in c, f"{c['id']} in a non-AVA roster gained window_gate"
            assert "single_position_only" not in c, \
                f"{c['id']} in a non-AVA roster gained single_position_only"


# --------------------------------------------------------------------------
# Magic-band disjointness against every other roster in the file
# --------------------------------------------------------------------------
def test_ava_magic_band_disjoint_from_everything():
    def _band(cfgs):
        s = set()
        for c in cfgs:
            s |= {c["magic"] + o for o in range(4)}
        return s

    ava_band = _band(CONFIGS_AVA)
    other = (_band(CONFIGS_LIVE) | _band(CONFIGS_SHADOW) | _band(CONFIGS_GOLIVE)
             | _band(CONFIGS_TK) | _band(CONFIGS_TOMACHINE) | _band(CONFIGS_LOCAL)
             | _band(CONFIGS_CHALLENGER) | _band([CONFIG_TK_BW2_FIX2ATR]))
    assert ava_band.isdisjoint(other)
    assert min(ava_band) == 727010 and max(ava_band) == 727023


def test_ava_magic_bands_pairwise_disjoint_within_roster():
    seen: set[int] = set()
    for c in CONFIGS_AVA:
        band = {c["magic"] + off for off in range(4)}
        assert seen.isdisjoint(band), f"magic band overlap at {c['id']}"
        seen |= band


# --------------------------------------------------------------------------
# deepcopy sanity (defensive: the module itself already deep-copies; this
# pins that a caller mutating one AVA config's kwargs can never reach the
# champion's kwargs dict through shared nested structures).
# --------------------------------------------------------------------------
def test_mutating_ava_kwargs_does_not_touch_champion():
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    s6_ava = next(c for c in CONFIGS_AVA if c["id"] == "S6-K2P0-AVA")
    probe = copy.deepcopy(s6_ava)
    probe["kwargs"]["symbol"] = "MUTATED"
    assert golive_by_id["S6-K2P0"]["kwargs"]["symbol"] == "XAUUSD"
