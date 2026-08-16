r"""scripts/research/ola1/pareado.py -- OLA1-EXEC Bloque 4.

Comparacion pareada de un brazo contra el brazo de control, sobre el
subconjunto casado por identidad de entrada (E-04 SS2.3-2.4, D-56 -- la
degradacion automatica a 1-B si la tasa de emparejamiento cae por debajo de
0.90).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from scripts.analysis.realtick_bt.paired_harness import entry_identity
from scripts.research.ola1.sustrato import dia_servidor

B_BOOTSTRAP = 10_000
SEED_BOOTSTRAP = 20260816  # E-04 SS2.4: semilla fija, reproducible bit a bit.
UMBRAL_DEGRADACION = 0.90  # D-56: tasa_emparejamiento < 0.90 => degradado a 1-B.


def _mapa_identidad(sid: str, posiciones: list[dict[str, Any]]) -> tuple[dict[Any, dict], int]:
    """Identidad -> posicion, quedandose con la PRIMERA por t_exit si una
    identidad se repite dentro del mismo brazo (nunca se descarta en
    silencio: se cuenta). Devuelve (mapa, n_duplicadas)."""
    ordenadas = sorted(posiciones, key=lambda p: p["t_exit"])
    mapa: dict[Any, dict] = {}
    n_dup = 0
    for p in ordenadas:
        ident = entry_identity(sid, p)
        if ident in mapa:
            n_dup += 1
            continue
        mapa[ident] = p
    return mapa, n_dup


def _bootstrap_bloques(dias: list[str], suma_dia: dict[str, float], n_dia: dict[str, int],
                        *, B: int = B_BOOTSTRAP, seed: int = SEED_BOOTSTRAP) -> dict[str, Any]:
    """Bootstrap por bloques de dia de servidor (E-04 SS2.4), vectorizado:
    precalcula suma_dia[d]/n_dia[d] y remuestrea DIAS (no posiciones
    individuales) -- la media de un remuestreo es
    sum(suma_dia[muestra]) / sum(n_dia[muestra]), exactamente la media del
    pool remuestreado, en O(B * n_dias)."""
    n_dias = len(dias)
    rng = np.random.default_rng(seed)
    sumas = np.array([suma_dia[d] for d in dias], dtype="float64")
    ns = np.array([n_dia[d] for d in dias], dtype="float64")
    idx = rng.integers(0, n_dias, size=(B, n_dias))
    stat = sumas[idx].sum(axis=1) / ns[idx].sum(axis=1)
    ic_bajo, ic_alto = (float(x) for x in np.percentile(stat, [2.5, 97.5]))
    ic_excluye_0 = bool(ic_bajo > 0 or ic_alto < 0)
    frac_le0 = float(np.mean(stat <= 0))
    frac_ge0 = float(np.mean(stat >= 0))
    p = min(max(2 * min(frac_le0, frac_ge0), 0.0), 1.0)
    return {"ic95_bajo": ic_bajo, "ic95_alto": ic_alto, "ic_excluye_0": ic_excluye_0,
            "p_bootstrap": p, "n_dias_bloque": n_dias}


def pareado_vs_control(sid: str, posiciones_brazo: list[dict[str, Any]],
                        posiciones_control: list[dict[str, Any]],
                        r_control: list[float | None]) -> dict[str, Any]:
    """`r_control` viene en el MISMO orden/longitud que `posiciones_control`
    (tipicamente riesgo.r_por_posicion(sid, overlay_control, posiciones_control, bars))."""
    mapa_brazo, n_dup_brazo = _mapa_identidad(sid, posiciones_brazo)
    mapa_control, n_dup_control = _mapa_identidad(sid, posiciones_control)
    n_identidades_duplicadas = n_dup_brazo + n_dup_control

    if len(posiciones_control) != len(r_control):
        raise ValueError(
            "r_control debe venir en el mismo orden/longitud que posiciones_control "
            f"(recibido len(r_control)={len(r_control)} vs "
            f"len(posiciones_control)={len(posiciones_control)})"
        )
    # r_control viene en el orden ORIGINAL de posiciones_control (no el
    # ordenado-por-t_exit de mapa_control) -- se hace zip primero y LUEGO se
    # ordena el par (posicion, R) por t_exit, con el mismo criterio de
    # "primera por t_exit gana" que _mapa_identidad, para que la R publicada
    # sea la de la MISMA posicion que sobrevive la deduplicacion.
    pares_control_r = sorted(zip(posiciones_control, r_control), key=lambda pr: pr[0]["t_exit"])
    r_por_identidad: dict[Any, float | None] = {}
    for p, r in pares_control_r:
        ident = entry_identity(sid, p)
        r_por_identidad.setdefault(ident, r)

    ids_control = set(mapa_control)
    ids_brazo = set(mapa_brazo)
    casadas = sorted(ids_control & ids_brazo, key=repr)
    n_control = len(mapa_control)
    n_brazo = len(mapa_brazo)
    n_casadas = len(casadas)
    tasa_emparejamiento = (n_casadas / n_control) if n_control else 0.0
    n_solo_control = len(ids_control - ids_brazo)
    n_solo_brazo = len(ids_brazo - ids_control)
    degradado_a_1B = tasa_emparejamiento < UMBRAL_DEGRADACION

    diffs: list[float] = []
    dias_pares: list[str] = []
    r_control_de_par: list[float | None] = []
    for ident in casadas:
        p_b = mapa_brazo[ident]
        p_c = mapa_control[ident]
        diff = p_b["net1"] - p_c["net1"]
        diffs.append(diff)
        dias_pares.append(dia_servidor(p_c["t_in_exec"]))
        r_control_de_par.append(r_por_identidad.get(ident))

    if diffs:
        arr = np.array(diffs, dtype="float64")
        media_diff = float(arr.mean())
        mediana_diff = float(np.median(arr))
        suma_diff = float(arr.sum())
        desvio_diff = float(arr.std(ddof=1)) if len(arr) >= 2 else None
    else:
        media_diff = mediana_diff = suma_diff = desvio_diff = None

    en_r = [(d / r) for d, r in zip(diffs, r_control_de_par) if r is not None]
    n_excluidas_por_R = sum(1 for r in r_control_de_par if r is None)
    media_diff_en_R = float(np.mean(en_r)) if en_r else None

    resultado: dict[str, Any] = {
        "n_control": n_control, "n_brazo": n_brazo, "n_casadas": n_casadas,
        "tasa_emparejamiento": tasa_emparejamiento,
        "n_solo_control": n_solo_control, "n_solo_brazo": n_solo_brazo,
        "degradado_a_1B": degradado_a_1B,
        "media_diff": media_diff, "mediana_diff": mediana_diff,
        "suma_diff": suma_diff, "desvio_diff": desvio_diff,
        "media_diff_en_R": media_diff_en_R, "n_excluidas_por_R": n_excluidas_por_R,
        "n_identidades_duplicadas": n_identidades_duplicadas,
    }

    if n_casadas == 0:
        resultado.update({"ic95_bajo": None, "ic95_alto": None, "ic_excluye_0": None,
                           "p_bootstrap": None, "n_dias_bloque": 0,
                           "motivo_no_evaluable": "n_casadas == 0"})
        return resultado

    suma_dia: dict[str, float] = {}
    n_dia: dict[str, int] = {}
    for d, diff in zip(dias_pares, diffs):
        suma_dia[d] = suma_dia.get(d, 0.0) + diff
        n_dia[d] = n_dia.get(d, 0) + 1
    dias = sorted(suma_dia)

    if len(dias) < 2:
        resultado.update({"ic95_bajo": None, "ic95_alto": None, "ic_excluye_0": None,
                           "p_bootstrap": None, "n_dias_bloque": len(dias),
                           "motivo_no_evaluable": "n_dias_bloque < 2"})
        return resultado

    resultado.update(_bootstrap_bloques(dias, suma_dia, n_dia))
    return resultado
