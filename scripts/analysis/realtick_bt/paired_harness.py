r"""scripts/analysis/realtick_bt/paired_harness.py -- WP-1+2 Bloque 3.

Harness pareado de K brazos (cada brazo = estrategia + overlay de kwargs, ver
`overlay.overlay_kwargs`). Corre cada brazo UNA sola vez, resuelve sus
posiciones UNA sola vez, y mide (nunca asume) el solape de identidad de
entrada entre cada par de brazos, en dos niveles: senal (antes de resolve())
y rellenado (despues de resolve()).

Identidad de entrada (brief SS Bloque 3):
  - Ladder (S6/S7): (sid, ficha, t_in, side).
  - SuperTrend:     (t_in, side)               -- sin sid/ficha, always-in.

PROHIBIDO ASUMIR que dos brazos comparten entradas: S6/S7 corren con
`stop_and_reverse=True`, así que una salida distinta puede generar una
ENTRADA distinta aguas abajo (ver test_alignment_table_measures_not_assumes_overlap
en tests/research/test_harness_pareado.py). `resolve()` además descarta
posiciones que no pasaron el gate de spread -- por eso el nivel "rellenado"
puede tener menos entradas que el nivel "senal" incluso dentro del MISMO
brazo, y los dos numeros importan por separado.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from scripts.analysis.realtick_bt import backtest
from scripts.analysis.realtick_bt.overlay import overlay_kwargs

Identity = tuple


def entry_identity(sid: str, pos: dict[str, Any]) -> Identity:
    """Entry identity for one position row (works on both signal-level rows
    from run_ladder/run_supertrend AND filled-level rows from resolve() --
    both share the t_in/side/ficha keys)."""
    if sid == "SuperTrend-p14x3-M15":
        return (pos["t_in"], pos["side"])
    return (sid, pos.get("ficha"), pos["t_in"], pos["side"])


def _align(ids_a: set[Identity], ids_b: set[Identity]) -> dict[str, Any]:
    """Measured overlap between two sets of entry identities -- never assumed
    equal. `no_casadas` lists every identity present in exactly one side."""
    casadas = ids_a & ids_b
    solo_a = ids_a - ids_b
    solo_b = ids_b - ids_a
    return {
        "n_casadas": len(casadas),
        "n_solo_A": len(solo_a),
        "n_solo_B": len(solo_b),
        "no_casadas": sorted(solo_a | solo_b, key=repr),
    }


@dataclass
class PairedResult:
    sid: str
    arms: dict[str, list[dict[str, Any]]]              # arm -> resolved (post-resolve) rows
    signal_positions: dict[str, list[dict[str, Any]]]  # arm -> raw (pre-resolve) rows
    alignment_signal: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    alignment_filled: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def rows(self) -> list[dict[str, Any]]:
        """Columnar output, unible por `pos_id` sin ambiguedad: una fila por
        (brazo, posicion resuelta), con `arm`, `sid` y `pos_id` (identidad de
        entrada serializada) añadidos."""
        out = []
        for arm, positions in self.arms.items():
            for p in positions:
                ident = entry_identity(self.sid, p)
                out.append({**p, "arm": arm, "sid": self.sid,
                            "pos_id": "|".join(str(x) for x in ident)})
        return out


def run_paired_arms(sid: str, arms: dict[str, dict[str, Any]],
                     bars: list[dict[str, Any]], ticks: "backtest.Ticks | None" = None
                     ) -> PairedResult:
    """Run the K `arms` of strategy `sid` (each value = overlay dict for
    `overlay.overlay_kwargs`, or -- for SuperTrend -- kwargs of
    `backtest.run_supertrend` itself), resolve each arm's positions once, and
    measure pairwise entry-identity overlap at both levels.

    Entries are computed exactly once per arm (no re-simulation per policy
    inside an arm). `bars` are shared across arms (comparability, charter
    regla 1); `ticks` defaults to a fresh `backtest.Ticks()` reader.
    """
    if ticks is None:
        ticks = backtest.Ticks()
    bar_times = np.array([b["t"] for b in bars], dtype="float64")

    signal_positions: dict[str, list[dict[str, Any]]] = {}
    resolved: dict[str, list[dict[str, Any]]] = {}
    for arm_name, overlay in arms.items():
        if sid == "SuperTrend-p14x3-M15":
            raw = backtest.run_supertrend(bars, ticks, **overlay)
        else:
            eff_kwargs = overlay_kwargs(sid, overlay)
            raw = backtest.run_ladder(eff_kwargs, bars)
        signal_positions[arm_name] = raw
        out = []
        for p in raw:
            r = backtest.resolve(p, ticks, bar_times)
            if r is not None:
                out.append(r)
        resolved[arm_name] = out

    alignment_signal: dict[tuple[str, str], dict[str, Any]] = {}
    alignment_filled: dict[tuple[str, str], dict[str, Any]] = {}
    for a, b in itertools.combinations(arms.keys(), 2):
        ids_a_sig = {entry_identity(sid, p) for p in signal_positions[a]}
        ids_b_sig = {entry_identity(sid, p) for p in signal_positions[b]}
        alignment_signal[(a, b)] = _align(ids_a_sig, ids_b_sig)

        ids_a_fill = {entry_identity(sid, p) for p in resolved[a]}
        ids_b_fill = {entry_identity(sid, p) for p in resolved[b]}
        alignment_filled[(a, b)] = _align(ids_a_fill, ids_b_fill)

    return PairedResult(sid=sid, arms=resolved, signal_positions=signal_positions,
                         alignment_signal=alignment_signal, alignment_filled=alignment_filled)
