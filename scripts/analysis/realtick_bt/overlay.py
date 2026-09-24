r"""scripts/analysis/realtick_bt/overlay.py -- WP-1+2 Bloque 2.

Deep-copy overlay of kwargs on top of the live go-live roster (`backtest._GL`),
so grid levers (e.g. P-02 `max_hold_bars`, P-03 `ac_modulate*`) can be swept
WITHOUT ever mutating the live kwargs dicts (R1-bis, charter SS A.11).

`_GL` and the underlying `_GOLIVE_M15` roster are NEVER mutated by this
module: `overlay_kwargs` always starts from `copy.deepcopy(_GL[sid])`, never
`dict.update` on the original.
"""
from __future__ import annotations

import copy
from typing import Any

from scripts.analysis.realtick_bt import backtest


def overlay_kwargs(sid: str, overlay: dict[str, Any]) -> dict[str, Any]:
    """Effective kwargs for ladder strategy `sid` = deep-copy of the live
    `backtest._GL[sid]` kwargs with `overlay` applied on top.

    With `overlay == {}` the result equals `backtest._GL[sid]` by value (a
    deep copy, never the same object) -- i.e. today's behavior, unchanged.
    `backtest._GL[sid]` (and `_GOLIVE_M15` it is built from) is never mutated:
    this function only ever writes into the deep copy.
    """
    effective = copy.deepcopy(backtest._GL[sid])
    effective.update(overlay)
    return effective
