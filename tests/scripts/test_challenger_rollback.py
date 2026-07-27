"""tests/scripts/test_challenger_rollback.py -- the rollback guarantee.

The challenger must be removable by pointing the executor back at the `local`
roster, WITHOUT touching a line of champion code. This test pins that down: the
champion roster served under `--configs local` must be identical whether or not
the challenger module exists.
"""
from __future__ import annotations

from sentinel_engine.strategies.live_configs_20 import CONFIGS_CHALLENGER, CONFIGS_LOCAL

# The champion roster EXACTLY as it shipped on 2026-07-22 (commit f93e54a),
# written as literals so importing the challenger cannot influence it.
_CHAMPION_AS_SHIPPED = [
    ("S6-K2P0", 724010, 0.1),
    ("S7-TPNONE", 724020, 0.1),
    ("SuperTrend-p14x3-M15", 724070, 0.1),
    ("TK-Momentum-5-8-short", 999999998, 0.01),
]


def test_champion_roster_matches_what_shipped_before_the_challenger():
    assert [(c["id"], c["magic"], c["volume"]) for c in CONFIGS_LOCAL] == _CHAMPION_AS_SHIPPED


def test_rolling_back_is_a_roster_switch_not_a_code_change():
    # The two sleeves share NO object identity: dropping the challenger from
    # the roster removes it completely, with nothing left behind in champion
    # configs.
    champion_ids = {id(c) for c in CONFIGS_LOCAL}
    challenger_ids = {id(c) for c in CONFIGS_CHALLENGER}
    assert champion_ids.isdisjoint(challenger_ids)
    for c in CONFIGS_LOCAL:
        assert "risk_gates" not in c
