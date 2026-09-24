r"""scripts/research/ola1/metricas.py -- OLA1-EXEC Bloque 3.

Metricas por brazo, en CLP por 1.0 lote salvo donde se declare lo contrario.
Claves exactas (respetadas literalmente: el consolidador y el memo del
controlador dependen de ellas).

Overlay de coste de deslizamiento (E-04 SS2.5): el simulador no modela
deslizamiento en los stops. T0.7-M-H lo calibro contra la realidad de la 902
-- D-54 fijo la formula del coste, D-59(a) corrigio el valor aplicado a la
MEDIANA (no la media): 0.225 USD a spread 0.50. D-59(b) fijo que solo los
cierres server-side por nivel lo reciben.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from scripts.analysis.realtick_bt import backtest as bt
from scripts.research.ola1.sustrato import dia_servidor

# D-54 / T0.7-M-H / D-59(a): coste de deslizamiento calibrado -- mediana 0.225
# USD (no la media 0.053; D-59(a) corrige el texto de D-54) a spread 0.50, en
# cierres server-side por nivel.
COSTE_USD = 0.225
COSTE_CLP = COSTE_USD * bt.CONTRACT * bt.USDCLP  # 21_071.25 CLP por posicion y por lote

# D-59(b): FALLBACK_CLOSE_INVALID_SL / CLOSE_RECONCILER son cierres a mercado
# enviados por el ejecutor, no cierres server-side -- no reciben coste. Solo
# estos cuatro motivos de nivel lo reciben.
REASONS_CON_COSTE = frozenset({"EXIT_INITSL", "EXIT_SL_RAISED", "EXIT_TRAIL", "EXIT_STLINE"})


def _max_racha_negativa(posiciones: list[dict[str, Any]]) -> int:
    ordered = sorted(posiciones, key=lambda r: r["t_exit"])
    racha = maxima = 0
    for r in ordered:
        if r["net1"] < 0:
            racha += 1
            maxima = max(maxima, racha)
        else:
            racha = 0
    return maxima


def metricas_de_brazo(sid: str, arm: str, overlay: dict[str, Any],
                       posiciones: list[dict[str, Any]], bars: list[dict[str, Any]]
                       ) -> dict[str, Any]:
    n = len(posiciones)
    nets = [p["net1"] for p in posiciones]
    net_lote1 = sum(nets)
    net_por_posicion_lote1 = (net_lote1 / n) if n else None

    base = bt.metrics(posiciones, 1.0)
    net_lote_grid = bt.metrics(posiciones, bt.LOT_GRID)["net"]

    r_vals = [p.get("R1") for p in posiciones]
    r_computables = [r for r in r_vals if r is not None]
    n_R_no_computable = sum(1 for r in r_vals if r is None)
    if r_computables:
        R_mediana = float(np.median(r_computables))
        R_p25 = float(np.percentile(r_computables, 25))
        R_p75 = float(np.percentile(r_computables, 75))
    else:
        R_mediana = R_p25 = R_p75 = None

    en_r = [p["net1"] / p["R1"] for p in posiciones if p.get("R1") is not None]
    net_en_R_total = sum(en_r) if en_r else None
    net_en_R_por_posicion = (net_en_R_total / len(en_r)) if en_r else None

    max_perdidas_consecutivas = _max_racha_negativa(posiciones)

    if n >= 2:
        arr = np.array(nets, dtype="float64")
        std = float(arr.std(ddof=1))
        sharpe_por_posicion = float(arr.mean() / std) if std != 0 else None
    else:
        sharpe_por_posicion = None

    por_dia: dict[str, float] = {}
    for p in posiciones:
        d = dia_servidor(p["t_exit"])
        por_dia[d] = por_dia.get(d, 0.0) + p["net1"]
    if len(por_dia) >= 2:
        diario = np.array(list(por_dia.values()), dtype="float64")
        std_d = float(diario.std(ddof=1))
        sharpe_diario_ann = float(diario.mean() / std_d * np.sqrt(252)) if std_d != 0 else None
    else:
        sharpe_diario_ann = None

    n_por_reason = dict(Counter(p["reason"] for p in posiciones))

    n_flips = n  # SuperTrend: cada posicion termina en flip o toque de linea;
    # publicado igual para la escalera, donde NO significa flip (brief Bloque 3).

    net_con_coste_lote1 = 0.0
    n_posiciones_con_coste = 0
    for p in posiciones:
        if p["reason"] in REASONS_CON_COSTE:
            net_con_coste_lote1 += p["net1"] - COSTE_CLP
            n_posiciones_con_coste += 1
        else:
            net_con_coste_lote1 += p["net1"]

    return {
        "n": n,
        "net_lote1": net_lote1,
        "net_por_posicion_lote1": net_por_posicion_lote1,
        "wr": base["wr"], "pf": base["pf"], "maxdd_lote1": base["maxdd"],
        "rom": base["rom"], "avg_win": base["avg_win"], "avg_loss": base["avg_loss"],
        "net_lote_grid": net_lote_grid,
        "R_mediana": R_mediana, "R_p25": R_p25, "R_p75": R_p75,
        "n_R_no_computable": n_R_no_computable,
        "net_en_R_total": net_en_R_total, "net_en_R_por_posicion": net_en_R_por_posicion,
        "max_perdidas_consecutivas": max_perdidas_consecutivas,
        "sharpe_por_posicion": sharpe_por_posicion,
        "sharpe_diario_ann": sharpe_diario_ann,
        "n_por_reason": n_por_reason,
        "n_flips": n_flips,
        "net_con_coste_lote1": net_con_coste_lote1,
        "n_posiciones_con_coste": n_posiciones_con_coste,
    }
