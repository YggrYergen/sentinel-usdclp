"""tests/strategies/test_tk_momentum_config.py -- TK-Momentum roster + magic.

Pins the ADDITIVE deployment contract: the trader's live-forward config exists
as its own isolated roster with the all-nines position magic, disjoint from
every other magic block, and wired into the executor's engine dispatch.
"""
from __future__ import annotations

from sentinel_engine.live.reconciler import FICHA_OFFSET
from sentinel_engine.strategies.live_configs_20 import (
    CONFIG_TK_MOMENTUM,
    CONFIGS_GOLIVE,
    CONFIGS_SHADOW,
    CONFIGS_TK,
)


def test_config_identity():
    c = CONFIG_TK_MOMENTUM
    assert c["id"] == "TK-Momentum-5-8-short"
    assert c["tf"] == "M6"   # trader 2026-07-21: M10 -> M6 (faster reaction)
    assert c["engine"] == "tk_momentum"
    assert c["kwargs"]["symbol"] == "XAUUSD"
    assert c["kwargs"]["trail_usd"] == 3.0   # trader's choice (legal min is 0.6)
    assert CONFIGS_TK == [c]


def test_live_position_magic_is_all_nines():
    # the reconciler puts ficha F1 at base_magic + 1; that is what the trade
    # carries and what the trader sees.
    f1_magic = CONFIG_TK_MOMENTUM["magic"] + FICHA_OFFSET["F1"]
    assert f1_magic == 999999999


def test_magic_band_disjoint_from_other_rosters():
    tk_band = {CONFIG_TK_MOMENTUM["magic"] + o for o in range(4)}
    others = set()
    for c in list(CONFIGS_GOLIVE) + list(CONFIGS_SHADOW):
        others |= {c["magic"] + o for o in range(4)}
    assert tk_band.isdisjoint(others)


def test_executor_dispatches_the_new_engine():
    # importing the executor module wires TF maps + dispatch without MT5.
    from scripts.live import run_live_20
    # M6 is the timeframe TK now runs on (trader 2026-07-21).
    assert run_live_20.TF_MT5_MINUTES["M6"] == 6
    assert run_live_20.TF_SECONDS["M6"] == 360
    assert run_live_20.tk_momentum_5_8_target is not None
