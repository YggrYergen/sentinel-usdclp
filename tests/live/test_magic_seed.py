"""tests/live/test_magic_seed.py -- idempotent `magic_allocation` seeding
(`sentinel_engine.live.magic_seed.ensure_magic_allocations`, Task 3,
2026-07-22 machine-2 real-time attribution self-heal).

For each config, INSERT-OR-IGNORE rows for magics base+0..base+3 (schema:
magic PK, strategy_id, variant_id, asignado), naming per engine:
  tk_*                -> strategy_id "TK::<id>"
  supertrend_always_in -> strategy_id "SuperTrend::<id>"
  simular_variant (default engine key) -> strategy_id "SAR::<id>"
variant_id = "<id>" in every case. NEVER UPDATE/DELETE an existing row (even
one with different naming -- INSERT OR IGNORE, not upsert).
"""
from __future__ import annotations

import sqlite3

import pytest

from sentinel_engine.live.magic_seed import ensure_magic_allocations


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "research.db"
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE magic_allocation("
        "  magic INTEGER PRIMARY KEY, strategy_id TEXT NOT NULL, "
        "  variant_id TEXT, asignado TEXT)"
    )
    con.commit()
    con.close()
    return path


def _rows(db_path):
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT magic, strategy_id, variant_id FROM magic_allocation ORDER BY magic"
    ).fetchall()
    con.close()
    return rows


# --------------------------------------------------------------------------
# naming per engine
# --------------------------------------------------------------------------
def test_seeds_simular_variant_config_as_sar(db_path):
    cfg = {"id": "S6-K2P0", "magic": 724010, "kwargs": {}}
    inserted = ensure_magic_allocations(db_path, [cfg])
    assert inserted == 4
    rows = _rows(db_path)
    assert rows == [
        (724010, "SAR::S6-K2P0", "S6-K2P0"),
        (724011, "SAR::S6-K2P0", "S6-K2P0"),
        (724012, "SAR::S6-K2P0", "S6-K2P0"),
        (724013, "SAR::S6-K2P0", "S6-K2P0"),
    ]


def test_seeds_supertrend_always_in_config_as_supertrend(db_path):
    cfg = {"id": "SuperTrend-p14x3-M15", "magic": 724070, "kwargs": {},
           "engine": "supertrend_always_in"}
    ensure_magic_allocations(db_path, [cfg])
    rows = _rows(db_path)
    assert all(r[1] == "SuperTrend::SuperTrend-p14x3-M15" for r in rows)
    assert all(r[2] == "SuperTrend-p14x3-M15" for r in rows)


def test_seeds_tk_momentum_config_as_tk(db_path):
    cfg = {"id": "TK-Momentum-5-8-short", "magic": 999999998, "kwargs": {},
           "engine": "tk_momentum"}
    ensure_magic_allocations(db_path, [cfg])
    rows = _rows(db_path)
    assert all(r[1] == "TK::TK-Momentum-5-8-short" for r in rows)


def test_seeds_tk_bw2_fix2atr_config_as_tk(db_path):
    cfg = {"id": "TK-BW2-fix2atr", "magic": 725010, "kwargs": {},
           "engine": "tk_bw2_fix2atr"}
    ensure_magic_allocations(db_path, [cfg])
    rows = _rows(db_path)
    assert all(r[1] == "TK::TK-BW2-fix2atr" for r in rows)


# --------------------------------------------------------------------------
# idempotence
# --------------------------------------------------------------------------
def test_missing_rows_are_seeded_existing_rows_skipped(db_path):
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO magic_allocation (magic, strategy_id, variant_id, asignado) "
        "VALUES (724010, 'PRE_EXISTING', 'keep-me', 'never-touch')"
    )
    con.commit()
    con.close()

    cfg = {"id": "S6-K2P0", "magic": 724010, "kwargs": {}}
    inserted = ensure_magic_allocations(db_path, [cfg])
    assert inserted == 3  # 724011/12/13 seeded; 724010 skipped (already present)

    rows = {r[0]: r for r in _rows(db_path)}
    # the PRE-EXISTING row is untouched (no update/delete).
    assert rows[724010][1] == "PRE_EXISTING"
    assert rows[724010][2] == "keep-me"
    assert rows[724011][1] == "SAR::S6-K2P0"


def test_calling_twice_is_a_noop_the_second_time(db_path):
    cfg = {"id": "V11-M2", "magic": 724060, "kwargs": {}}
    first = ensure_magic_allocations(db_path, [cfg])
    second = ensure_magic_allocations(db_path, [cfg])
    assert first == 4
    assert second == 0
    assert len(_rows(db_path)) == 4


def test_multiple_configs_seed_independent_bands(db_path):
    configs = [
        {"id": "S6-K2P0", "magic": 724010, "kwargs": {}},
        {"id": "TK-BW2-fix2atr", "magic": 725010, "kwargs": {}, "engine": "tk_bw2_fix2atr"},
    ]
    inserted = ensure_magic_allocations(db_path, configs)
    assert inserted == 8
    rows = _rows(db_path)
    assert len(rows) == 8
    magics = {r[0] for r in rows}
    assert magics == {724010, 724011, 724012, 724013, 725010, 725011, 725012, 725013}


# --------------------------------------------------------------------------
# P2 (2026-07-22): the seeder is generic (run_live_20 calls it with the
# roster's RESOLVED configs, so `--configs local` already seeds CONFIGS_LOCAL's
# magics -- including TK-Momentum's 999999998). These tests PIN that every
# `local` and `tomachine` magic (base+0..+3) actually lands in the seed set,
# and that CONFIGS_LOCAL carries the exact target volumes and excludes V11-M2.
# --------------------------------------------------------------------------
def test_all_local_magics_are_seeded(db_path):
    from sentinel_engine.strategies.live_configs_20 import CONFIGS_LOCAL

    inserted = ensure_magic_allocations(db_path, list(CONFIGS_LOCAL))
    seeded_magics = {r[0] for r in _rows(db_path)}
    # every config's full band base+0..+3 must be present
    expected: set[int] = set()
    for cfg in CONFIGS_LOCAL:
        for off in range(4):
            expected.add(cfg["magic"] + off)
    assert expected.issubset(seeded_magics)
    # TK-Momentum's all-nines band specifically (the one the brief flags)
    assert {999999998, 999999999, 1000000000, 1000000001}.issubset(seeded_magics)
    assert inserted == len(expected)


def test_all_tomachine_magics_are_seeded(db_path):
    from sentinel_engine.strategies.live_configs_20 import CONFIGS_TOMACHINE

    ensure_magic_allocations(db_path, list(CONFIGS_TOMACHINE))
    seeded_magics = {r[0] for r in _rows(db_path)}
    for cfg in CONFIGS_TOMACHINE:
        for off in range(4):
            assert (cfg["magic"] + off) in seeded_magics


def test_local_roster_volumes_and_excludes_v11m2():
    from sentinel_engine.strategies.live_configs_20 import CONFIGS_LOCAL

    by_id = {c["id"]: c for c in CONFIGS_LOCAL}
    assert by_id["S6-K2P0"]["volume"] == 0.1
    assert by_id["S7-TPNONE"]["volume"] == 0.1
    assert by_id["SuperTrend-p14x3-M15"]["volume"] == 0.1
    assert by_id["TK-Momentum-5-8-short"]["volume"] == 0.01
    assert "V11-M2" not in by_id
