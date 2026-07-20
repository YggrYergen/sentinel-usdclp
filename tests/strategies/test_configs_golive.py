"""tests/strategies/test_configs_golive.py -- GL-T1 GO-LIVE roster
(`CONFIGS_GOLIVE`): the FIVE net-positive M15 V-15 SAR winners
(HON-W2-{S6-K2P0,S7-TPNONE,S6-K1P5,S7-TP1P0,S7-TPNONE-F2}-M15-SAR) built
VERBATIM from the honest-league v3 manifest cells, plus V11-M2 reused verbatim
from CONFIGS_20.

Asserts:
  * exactly SIX configs with the expected ids;
  * fresh magic block 7240x0 (724010..724060), DISJOINT from the classic
    live band (720xxx), the FIXED4 shadow band (721xxx) AND the plan-reserved
    722xxx/723xxx (NEW6 / NEW6-TP) blocks;
  * the shared champion M15 SAR base params (the winner param diff) plus the
    exact per-cell deltas (ac_modulate / trail_atr_floor_k / be_at_r / f1_tp_r
    / active_fichas);
  * V11-M2 inherits its CONFIGS_20 kwargs verbatim (blocked_hours etc.);
  * every config is a runnable simular_variant(**kwargs) call.
No MT5, no orders.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from sentinel_engine.strategies.emasar_variant import simular_variant
from sentinel_engine.strategies.live_configs_20 import (
    CONFIGS_20,
    CONFIGS_GOLIVE,
    CONFIGS_LIVE,
    CONFIGS_SHADOW,
    MAGIC_BY_ID_GOLIVE,
)

# The winning champion M15 V-15 SAR (+vol-target) base -- the winner PARAMETER
# DIFF shared by all five SAR winners (per docs/superpowers/research/
# 2026-07-20-honest-league-v3.md + wave6 findings).
_WINNER_BASE = dict(
    ema_fast=8, ema_slow=20, sar_step=0.3, sar_max=0.3,
    f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
    init_sl_range_k=2.5, vol_regime_window=200, confirm_count=2,
    confirm_mode=1, ac_modulate_factor=0.25, sar_adaptive=True,
    stop_and_reverse=True, live_fill_mode=True,
)

# id -> per-cell deltas ON TOP of the shared base (from the manifest cells).
_GOLIVE_SAR = {
    "S6-K2P0":      dict(ac_modulate=True,  trail_atr_floor_k=2.0),
    "S7-TPNONE":    dict(ac_modulate=False, trail_atr_floor_k=1.5, be_at_r=1.0),
    "S6-K1P5":      dict(ac_modulate=True,  trail_atr_floor_k=1.5),
    "S7-TP1P0":     dict(ac_modulate=False, trail_atr_floor_k=1.5, f1_tp_r=1.0,
                         be_at_r=1.0),
    "S7-TPNONE-F2": dict(ac_modulate=False, trail_atr_floor_k=1.5, be_at_r=1.0,
                         active_fichas=2),
}
_GOLIVE_IDS = ("S6-K2P0", "S7-TPNONE", "S6-K1P5", "S7-TP1P0", "S7-TPNONE-F2",
               "V11-M2")


def _bars(n=500, seed=13):
    rnd = random.Random(seed)
    price = 2000.0
    base = int(datetime(2026, 6, 2, tzinfo=timezone.utc).timestamp())
    out = []
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        o = price - drift
        c = price
        hi = max(o, c) + abs(rnd.uniform(0.3, 1.2))
        lo = min(o, c) - abs(rnd.uniform(0.3, 1.2))
        out.append({"t": base + k * 900, "open": o, "high": hi, "low": lo, "close": c})
    return out


def test_golive_is_exactly_six_expected_ids():
    assert len(CONFIGS_GOLIVE) == 6
    assert [c["id"] for c in CONFIGS_GOLIVE] == list(_GOLIVE_IDS)
    assert len({c["id"] for c in CONFIGS_GOLIVE}) == 6


def test_golive_magics_are_fresh_7240_block():
    assert [c["magic"] for c in CONFIGS_GOLIVE] == [724010, 724020, 724030,
                                                    724040, 724050, 724060]
    assert MAGIC_BY_ID_GOLIVE == {c["id"]: c["magic"] for c in CONFIGS_GOLIVE}


def test_golive_band_disjoint_from_all_other_blocks():
    """Go-live band [base..base+3] must not intersect the classic live band,
    the FIXED4 shadow band, or the plan-reserved 722xxx/723xxx blocks."""
    def band(cfg):
        b = cfg["magic"]
        return {b, b + 1, b + 2, b + 3}

    golive = set().union(*(band(c) for c in CONFIGS_GOLIVE))
    live = set().union(*(band(c) for c in CONFIGS_LIVE))
    shadow = set().union(*(band(c) for c in CONFIGS_SHADOW))
    assert golive.isdisjoint(live)
    assert golive.isdisjoint(shadow)
    # reserved plan blocks (NEW6 722xxx, NEW6-TP 723xxx) -- go-live must avoid
    # them; every go-live magic stays inside 7240xx.
    assert all(724000 <= m <= 724099 for m in golive)
    reserved_722 = set(range(722000, 723000))
    reserved_723 = set(range(723000, 724000))
    assert golive.isdisjoint(reserved_722)
    assert golive.isdisjoint(reserved_723)


def test_golive_sar_winners_match_winner_param_diff_and_deltas():
    by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for cid, deltas in _GOLIVE_SAR.items():
        k = by_id[cid]["kwargs"]
        assert by_id[cid]["tf"] == "M15", cid
        assert k["symbol"] == "XAUUSD", cid
        assert k["sar_adaptive"] is True, cid
        # sar_fast/slow + window carried by the shared _ADAPTIVE base.
        assert k["sar_fast"] == (0.3, 0.3), cid
        assert k["sar_slow"] == (0.005, 0.05), cid
        # shared winner param diff.
        for key, val in _WINNER_BASE.items():
            assert k[key] == val, f"{cid}: base kwarg {key} = {k.get(key)} != {val}"
        # per-cell deltas.
        for key, val in deltas.items():
            assert k[key] == val, f"{cid}: delta {key} = {k.get(key)} != {val}"
        # tp_min must NEVER appear (decisively refuted lever).
        assert "tp_min_pips" not in k, f"{cid}: tp_min must not be deployed"


def test_golive_tp_and_active_ficha_levers_only_where_expected():
    by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    # f1_tp_r only on S7-TP1P0.
    assert by_id["S7-TP1P0"]["kwargs"].get("f1_tp_r") == 1.0
    assert "f1_tp_r" not in by_id["S6-K2P0"]["kwargs"]
    assert "f1_tp_r" not in by_id["S7-TPNONE"]["kwargs"]
    # active_fichas only on the F2 variant.
    assert by_id["S7-TPNONE-F2"]["kwargs"].get("active_fichas") == 2
    assert "active_fichas" not in by_id["S7-TPNONE"]["kwargs"]


def test_golive_v11_m2_reused_verbatim_from_configs_20():
    src = next(c for c in CONFIGS_20 if c["id"] == "V11-M2")
    got = next(c for c in CONFIGS_GOLIVE if c["id"] == "V11-M2")
    assert got["tf"] == src["tf"] == "M2"
    assert got["k"] == src["k"]
    # kwargs inherited verbatim (blocked_hours, ac_modulate_factor, etc.).
    assert got["kwargs"] == src["kwargs"]
    # but re-magicked into the go-live block.
    assert got["magic"] == 724060 != src["magic"]


def test_golive_configs_all_run_simular_variant():
    bars = _bars()
    for c in CONFIGS_GOLIVE:
        events = simular_variant(bars, **c["kwargs"])
        assert isinstance(events, list), c["id"]


def test_golive_roster_respects_60_ficha_cap():
    from sentinel_engine.live.reconciler import MAX_FICHAS_TOTAL

    assert len(CONFIGS_GOLIVE) * 3 == 18
    assert 18 <= MAX_FICHAS_TOTAL
