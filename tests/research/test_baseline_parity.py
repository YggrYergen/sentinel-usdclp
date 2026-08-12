"""Puerta de paridad de D-22 para el motor de estrategias real-tick.

Por que existe. D-22 autorizo las 12 modificaciones de motor con una condicion
explicita del user: "cada modificacion exige re-verificacion de paridad antes de
pasar a la siguiente", y el charter SS A.5 pide "suite golden + fidelidad
empirica A6 tras CADA modificacion". El recon de T0.6 (2026-08-11) verifico que
esa puerta NO existia para este codigo: `tests/golden/` cubre el motor de
SCORING (`sentinel_engine.engine.Engine`), no `simular_variant` ni el harness
real-tick de `scripts/analysis/realtick_bt/backtest.py`. Habia tests de
comportamiento (`tests/strategies/test_emasar_*`) que atraparian un cambio
grosero, pero nada atrapaba deriva numerica silenciosa en el neto.

Que hace. Re-corre S6 / S7 / SuperTrend sobre el MISMO corte de sustrato con el
que se congelo la linea base y compara posicion a posicion contra los JSON
commiteados en
`research/fases/F0-preparacion/04-resultados/T0.6-baseline/`. Cualquier
diferencia -- una posicion de mas, una de menos, un precio de fill distinto en
el decimo decimal -- rompe el test y nombra la primera discrepancia.

Como usarlo durante T0.6. Antes de cada modificacion de motor: verde. Despues:
si sigue verde, la modificacion es inerte sobre las vivas (que es lo que R1-bis
exige, SS A.11). Si se pone rojo, la modificacion cambio el comportamiento de una
estrategia VIVA y hay que PARAR y escalar -- salvo que el cambio sea deliberado
y aprobado, en cuyo caso la linea base se re-congela con causa escrita y
enmienda, nunca en silencio.

Es `slow` (re-corre el backtest sobre ticks reales, ~1 min): queda fuera de la
corrida por defecto igual que el resto de replays pesados. Correr con:
    python -m pytest tests/research/test_baseline_parity.py -m slow -q
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

BASELINE_DIR = (
    Path(__file__).resolve().parents[2]
    / "research" / "fases" / "F0-preparacion" / "04-resultados" / "T0.6-baseline"
)

pytestmark = pytest.mark.slow


def _cargar_congelado(sid: str) -> list[dict]:
    path = BASELINE_DIR / f"posiciones_{sid}.json"
    assert path.exists(), (
        f"falta la linea base congelada {path}. "
        "Regenerala con: python -m scripts.research.baseline_golden"
    )
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def recalculado() -> dict[str, list[dict]]:
    """Re-corre el baseline en memoria, sin escribir artefactos."""
    from scripts.analysis.realtick_bt import backtest as bt
    from scripts.research.baseline_golden import HOLDOUT_INI

    bars = [b for b in bt.load_bars() if b["t"] < HOLDOUT_INI]
    resolved = bt.build_all(bt.Ticks(), bars)
    return {
        sid: sorted(
            ({k: (round(v, 10) if isinstance(v, float) else v) for k, v in sorted(r.items())}
             for r in rows),
            key=lambda r: (r["t_in_exec"], r["t_exit"]),
        )
        for sid, rows in resolved.items()
    }


def test_la_linea_base_existe_y_no_esta_vacia():
    meta_path = BASELINE_DIR / "baseline.json"
    assert meta_path.exists(), f"falta {meta_path}"
    with meta_path.open(encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["estrategias"], "la linea base no declara estrategias"
    for sid in meta["estrategias"]:
        assert _cargar_congelado(sid), f"linea base vacia para {sid}"


@pytest.mark.parametrize("sid", ["S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"])
def test_paridad_posicion_a_posicion(sid: str, recalculado: dict[str, list[dict]]):
    congelado = _cargar_congelado(sid)
    actual = recalculado[sid]

    assert len(actual) == len(congelado), (
        f"{sid}: numero de posiciones cambio -- congelado={len(congelado)} "
        f"actual={len(actual)}. Una modificacion de motor altero una estrategia VIVA: "
        "PARAR y escalar (R1-bis, charter SS A.11)."
    )

    for i, (esperado, obtenido) in enumerate(zip(congelado, actual)):
        if esperado != obtenido:
            difieren = {
                k: (esperado.get(k), obtenido.get(k))
                for k in sorted(set(esperado) | set(obtenido))
                if esperado.get(k) != obtenido.get(k)
            }
            pytest.fail(
                f"{sid}: la posicion #{i} difiere de la linea base congelada.\n"
                f"  claves que cambiaron (congelado -> actual): {difieren}\n"
                "  Deriva numerica en una estrategia VIVA: PARAR y escalar."
            )
