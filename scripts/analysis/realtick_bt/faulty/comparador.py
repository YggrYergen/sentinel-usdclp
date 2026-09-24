r"""Componente E de la réplica en harness del motor faulty (tag
engine-faulty-tomachine-902 -> b113eb7): el COMPARADOR de P-CAP.

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md
§5-bis (ADDENDUM 2026-08-13 -- Componente E) y §3-quinquies (tabla de
equivalencia final, ya medida).

Enfrenta la corrida de la réplica (Componente D, `llamador.py`) contra la
verdad de terreno de la cuenta 902, posición a posición. El criterio de paso
de P-CAP, fijado por D-45, es bit-identidad sobre SEIS campos: precio de
entrada, instante de entrada, instante de salida, precio de salida, razón de
cierre y resultado. El SL de entrada se mide y reporta, SIN poder de
bloqueo (E.1). D-46 corrige cómo se operacionalizan los DOS campos de
instante (entrada y salida): se comparan TRUNCADOS AL SEGUNDO (floor), no en
bit-identidad estricta sobre el valor crudo -- la verdad de terreno sólo
tiene resolución de segundo entero (no existe `time_msc`) mientras la
réplica tiene resolución de tick; ver `_mismo_segundo`. Sigue siendo
criterio de paso con poder de bloqueo, no se degrada a métrica informativa;
los otros cuatro campos no cambian.

R1-bis / D.5: este módulo NO importa `sentinel_engine/**`, `backtest.py` ni
los componentes A/B/C/D -- sólo LEE los artefactos CSV/JSON que ya
produjeron. No compara contra nada que él mismo genere: los insumos (D.5,
verdad de terreno, mapeo de motivos) son de otros componentes, congelados.

Honestidad (charter §A.4/§A.13): ningún número de este módulo se inventa.
La tabla de equivalencia motivo_cierre <-> reason se CONSTRUYE desde
`mapeo_motivos_cierre.json` (el artefacto medido) más una traducción de
vocabulario puramente estructural, documentada en §3-quinquies Hueco 1/2:
el evento de log "SAME_BAR_EXIT_FALLBACK" y "SENT CLOSE" son, ambos, lo que
la réplica etiqueta como motivo_cierre="CLOSE_RECONCILER" (Hueco 1: mismo
código, mismo comment, mismo reason=EXPERT en MT5); el evento de log
"FALLBACK_CLOSE_INVALID_SL" es, literalmente, motivo_cierre=
"FALLBACK_CLOSE_INVALID_SL" en la réplica (mismo nombre, no hay traducción).
Esta correspondencia NO es una tabla nueva: es la única forma de LEER la
tabla ya medida (los ejes del `matriz_contingencia` del JSON son
reason_name(MT5) x evento_de_log, no motivo_cierre(réplica) x reason_name;
"motivo_cierre" es simplemente el nombre que Componente B usa para el mismo
hecho que el log del ejecutor llama "evento"). Ningún número de conteo se
sobreescribe a mano: los conteos por celda vienen del propio JSON.

Ningún artefacto de este módulo lleva conclusiones (charter §A.4/§A.13). El
memo de interpretación y el veredicto de P-CAP los escribe Opus, en
`05-analisis/`.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]  # .../faulty/../../../../ -> D:\FOREX

# ------------------------------------------------------------------- rutas
POSICIONES_REPLICA_CSV = ROOT / "data" / "analysis" / "p_cap" / "replica" / "posiciones_replica.csv"
EVENTOS_REPLICA_CSV = ROOT / "data" / "analysis" / "p_cap" / "replica" / "eventos_replica.csv"
METRICAS_P_CAP_JSON = ROOT / "data" / "analysis" / "p_cap" / "replica" / "metricas_p_cap.json"
VERDAD_TERRENO_CSV = ROOT / "data" / "analysis" / "p_cap" / "verdad_terreno_902.csv"
EVENTOS_EJECUTOR_CSV = ROOT / "data" / "analysis" / "p_cap" / "eventos_ejecutor_902.csv"
MAPEO_MOTIVOS_JSON = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados" / "T0.7-p-cap"
    / "mapeo_motivos_cierre.json"
)
SL_ENVIADO_CSV = ROOT / "data" / "analysis" / "p_cap" / "sl_enviado_por_apertura.csv"

OUT_CSV = ROOT / "data" / "analysis" / "p_cap" / "comparacion_p_cap.csv"
OUT_DIR_RESULTADO = ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados" / "T0.7-p-cap"
OUT_JSON = OUT_DIR_RESULTADO / "p_cap_resultado.json"
OUT_MD = OUT_DIR_RESULTADO / "p_cap_resultado.md"

# §3 del brief: guarda dura contra la corrida truncada (t1 mal transcrito).
T1_ESPERADO = 1786431669.0
T1_TRUNCADO_CONOCIDO = 1785409304.0

ENGINE_SHA = "b113eb7"
EXPERIMENTO = "T0.7-P-CAP"

# §6 del spec / E.2.2: denominador de A6 (barras-señal), NUNCA las 152
# posiciones -- las 152 son re-entradas secuenciales de una misma señal.
# Constante CITADA verbatim del spec cerrado (§6, §E.2.2): este comparador
# NO recomputa el corte por barra-señal -- no hay, entre sus insumos (§3 del
# brief), ningún artefacto que ligue barra-señal a posición. Se declara y
# se publica junto al corte por posición, etiquetado, sin mezclarlos
# (regla dura 7 / E.2.2).
DENOMINADOR_BARRAS_SENAL = {
    "S6": 49,
    "ST": 42,
    "total": 91,
    "fuente": (
        "research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md "
        "§6 y §E.2.2 -- citado verbatim, no recomputado por este comparador"
    ),
}

# Traducción de vocabulario evento_de_log(ejecutor) -> motivo_cierre(réplica)
# -- documentada en §3-quinquies Hueco 1 (CLOSE_RECONCILER cubre SENT CLOSE +
# SAME_BAR_EXIT_FALLBACK: "Lo que hace el ejecutor con una y con otra es
# idéntico" -- misma rama de execute_action, mismo req, mismo comment) y
# Hueco 2 (FALLBACK_CLOSE_INVALID_SL: nombre idéntico a ambos lados). No es
# una tabla de equivalencia nueva: es el único puente para leer
# `matriz_contingencia` (ejes reason_name x evento_de_log) con el vocabulario
# de `posiciones_replica.csv` (columna motivo_cierre).
_EVENTO_LOG_A_MOTIVO_REPLICA = {
    "FALLBACK_CLOSE_INVALID_SL": "FALLBACK_CLOSE_INVALID_SL",
    "SAME_BAR_EXIT_FALLBACK": "CLOSE_RECONCILER",
    "SENT CLOSE": "CLOSE_RECONCILER",
}

# reason_name de MT5 que NUNCA los produce el motor (intervención externa) --
# excluidos del criterio de paso, contados aparte (reglas 4/5 del brief,
# E.2.4 del spec). No entran en `equivalencia` porque ningún motivo_cierre
# de la réplica puede casar con ellos legítimamente.
REASON_EXCLUIDOS_DEL_CRITERIO = {"CLIENT_manual", "TP"}

_EPS_PRECIO = 1e-6
# D-46: los instantes ya NO se comparan con epsilon de punto flotante --
# se truncan al segundo (`_mismo_segundo`, floor). No queda ningún uso de
# un epsilon de tiempo; se retira para no sugerir que sigue vigente.


# --------------------------------------------------------------- guardas §3
class CorridaTruncadaError(RuntimeError):
    """§3 del brief: si metricas_p_cap.json trae t1=1785409304 en vez de
    1786431669, la corrida es la truncada (2,67 de 14,5 días) y hay que
    PARAR y escalar, no comparar contra ella."""


def verificar_t1(metricas: dict[str, Any]) -> None:
    t1 = float(metricas["parametros"]["t1"])
    if t1 == T1_TRUNCADO_CONOCIDO:
        raise CorridaTruncadaError(
            f"metricas_p_cap.json trae t1={t1!r} -- es la corrida TRUNCADA "
            "(2,67 de los 14,5 días de ventana, 250 velas en vez de 970). "
            "PARAR y escalar: no comparar contra esta corrida."
        )
    if t1 != T1_ESPERADO:
        raise CorridaTruncadaError(
            f"metricas_p_cap.json trae t1={t1!r}, distinto del esperado "
            f"{T1_ESPERADO!r} (último cierre real de verdad_terreno_902.csv). "
            "PARAR y escalar antes de comparar."
        )


# --------------------------------------------------------- tabla de equivalencia
def cargar_equivalencia(
    mapeo_path: str | Path = MAPEO_MOTIVOS_JSON,
) -> tuple[dict[str, set[str]], dict[tuple[str, str], int]]:
    """Construye, desde el artefacto medido `mapeo_motivos_cierre.json`, el
    mapeo motivo_cierre(réplica) -> {reason_name(MT5) legítimos}.

    Regla dura 1 (brief §4 / spec E.2.1): la tabla NO se inventa ni se
    amplía -- se consume del artefacto medido. Regla dura 2: la equivalencia
    NO es biyectiva (FALLBACK_CLOSE_INVALID_SL puede casar con EXPERT o con
    SL). Devuelve también los conteos por (motivo, reason) tal como salen de
    `matriz_contingencia`, para publicarlos como referencia en el reporte.
    """
    with open(mapeo_path, encoding="utf-8") as f:
        mapeo = json.load(f)
    matriz = mapeo["matriz_contingencia"]
    cells = matriz["cells"]

    equivalencia: dict[str, set[str]] = defaultdict(set)
    conteos: dict[tuple[str, str], int] = {}

    for reason, fila in cells.items():
        if reason == "SIN EMPAREJAR":
            # Eventos de log sin posición real emparejada -- no aportan a la
            # tabla motivo_cierre -> reason_name (no hay reason_name real).
            continue
        for evento, n in fila.items():
            n = int(n)
            if n <= 0:
                continue
            if evento == "SIN EMPAREJAR":
                # Regla dura 3 (brief §4): los cierres SL reales NO tienen
                # evento de log, y eso es correcto -- por diseño, el bróker
                # dispara el stop server-side sin que el ejecutor lo envíe.
                # Es la ÚNICA celda "sin evento" que corresponde a un
                # motivo_cierre de réplica (SL). CLIENT_manual/TP "sin
                # evento" son las exclusiones (rule 4/5): no producen
                # entrada de equivalencia -- el motor no las reproduce.
                if reason == "SL":
                    equivalencia["SL"].add("SL")
                    conteos[("SL", "SL")] = conteos.get(("SL", "SL"), 0) + n
                continue
            motivo = _EVENTO_LOG_A_MOTIVO_REPLICA.get(evento)
            if motivo is None:
                continue
            equivalencia[motivo].add(reason)
            conteos[(motivo, reason)] = conteos.get((motivo, reason), 0) + n

    return dict(equivalencia), conteos


def evaluar_razon_cierre(
    motivo_replica: str | None,
    reason_real: str | None,
    equivalencia: dict[str, set[str]],
) -> tuple[bool | None, bool]:
    """Devuelve (coincide, no_evaluable) para el campo 5 (razón de cierre).

    Regla dura 1: si `motivo_replica` no está en la tabla de equivalencia,
    la posición se marca NO_EVALUABLE -- jamás se fuerza a la categoría más
    parecida. `coincide` es `None` cuando no_evaluable es True o cuando
    falta alguno de los dos lados (sin pareja)."""
    if motivo_replica is None or reason_real is None:
        return None, False
    if motivo_replica not in equivalencia:
        return None, True
    coincide = reason_real in equivalencia[motivo_replica]
    return coincide, False


# ------------------------------------------------------------------- utilidades
def _lado_normalizado(valor: str) -> str:
    """BUY/SELL (verdad de terreno) -> L/S (grafía de la réplica). Pasa L/S
    sin cambios."""
    mapa = {"BUY": "L", "SELL": "S", "L": "L", "S": "S"}
    if valor not in mapa:
        raise ValueError(f"lado desconocido: {valor!r}")
    return mapa[valor]


def _resultado_de_signo(x: float) -> str:
    if x > 0:
        return "GANADORA"
    if x < 0:
        return "PERDEDORA"
    return "BREAKEVEN"


def resultado_real(profit_clp: float) -> str:
    return _resultado_de_signo(float(profit_clp))


def resultado_replica(side: str, precio_open: float, precio_close: float) -> str:
    lado = _lado_normalizado(side)
    diff = (precio_close - precio_open) if lado == "L" else (precio_open - precio_close)
    return _resultado_de_signo(diff)


def _cerca(a: float, b: float, eps: float) -> bool:
    if a is None or b is None:
        return False
    if (isinstance(a, float) and math.isnan(a)) or (isinstance(b, float) and math.isnan(b)):
        return False
    return abs(float(a) - float(b)) < eps


def _mismo_segundo(a: float, b: float) -> bool:
    """D-46 (research/DECISIONES.md): compara dos instantes TRUNCADOS AL
    SEGUNDO -- floor(a) == floor(b), no bit-identidad estricta sobre el
    valor crudo.

    Por qué: la verdad de terreno (`verdad_terreno_902.csv`, derivada de
    `deals_raw.csv`) tiene resolución de SEGUNDO ENTERO -- MT5 no expone
    `time_msc` en los deals de esta cuenta -- mientras la réplica
    (`posiciones_replica.csv`) cierra en instantes de resolución de TICK
    (p.ej. `1785268336.309`). Comparar ambos con `==` estricto sólo podía
    casar si el tick caía exactamente en el borde del segundo (~1 de cada
    1.000); D-45 medía, con ese criterio, que se comparaban dos relojes de
    distinta precisión, no la fidelidad de la réplica.

    `floor`, NO `round`: el instante real es el segundo en que MT5 registró
    el deal, y un tick en `...336.9` sigue perteneciendo al segundo `336`,
    no al `337`. Esto NO introduce una tolerancia de +-1 s -- sigue
    exigiendo el mismo segundo exacto, la máxima precisión que la fuente
    permite: dos instantes que truncan a segundos distintos (p.ej.
    `...336.999` vs `...337.001`, separados por 2 ms) NO casan.

    Trunca cada instante POR SU LADO, nunca el delta entre ambos --
    `floor(delta)` con delta negativo redondea para el lado equivocado
    (`floor(-0.3) == -1`, no `0`)."""
    if a is None or b is None:
        return False
    if (isinstance(a, float) and math.isnan(a)) or (isinstance(b, float) and math.isnan(b)):
        return False
    return math.floor(float(a)) == math.floor(float(b))


# ------------------------------------------------------- emparejamiento 1-a-1
def alinear_posiciones(
    real_precios: np.ndarray,
    rep_precios: np.ndarray,
    gap_cost: float = 80.0,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Alineación 1-a-1, preservando el orden cronológico (ambas listas ya
    vienen ordenadas por t_open ascendente y filtradas al mismo `side` y
    `strategy_id`), vía programación dinámica de tipo Needleman-Wunsch:
    costo de emparejar = |precio_open real - precio_open réplica| (USD);
    costo de saltar (posición real sin pareja, o réplica sin pareja) =
    `gap_cost`.

    Por qué precio y no instante: dentro de cada estrategia hay 1 sola
    ficha activa a la vez (mono-ficha, D.3) -- las posiciones son
    ESTRICTAMENTE secuenciales y no se solapan, así que preservar el orden
    es válido por construcción. Usar el INSTANTE de apertura como costo
    resultó no discriminante: el ejecutor real tiene una ventana bloqueada
    recurrente (`blocked_open_window=18:00-18:45`, ver log del ejecutor)
    que desplaza sistemáticamente la apertura real de algunas señales varias
    horas respecto a cuándo la réplica -- sin ese gate modelado igual --
    hubiera abierto; ese desplazamiento (~6.300 s, recurrente casi a
    diario) es del mismo orden que la separación entre señales distintas,
    así que el instante por sí solo cruza pares. El precio de entrada, en
    cambio, es case por caso casi idéntico entre pares genuinos (mediana de
    diferencia < 1 USD medida en la ventana) y muy distinto entre señales
    distintas (la serie se mueve cientos de USD en dos semanas) -- es la
    métrica discriminante.

    `gap_cost=80` (USD-equivalente) se validó por estabilidad, calculada
    POR LADO (`alinear_por_estrategia` separa L/S antes de llamar aquí,
    porque una SELL real nunca es pareja de una réplica L): para las 4
    combinaciones (SAR/L, SAR/S, ST/L, ST/S) el conjunto de pares y el
    delta de precio máximo dentro de esos pares son IDÉNTICOS en todo
    gap_cost∈[20, 80] (SAR/L: 39 pares, maxΔ=8.82; SAR/S: 45 pares,
    maxΔ=12.51; ST/L: 40 pares, maxΔ=21.05; ST/S: 24 pares, maxΔ=15.04).
    Por ENCIMA de 80 el resultado deja de ser estable: ST/L fuerza un par
    con Δ=155.45 en vez de dejarlo como residuo tan pronto gap_cost≥200, y
    ST/S fuerza uno con Δ=177.02 en las mismas condiciones -- es decir, un
    gap_cost demasiado alto hace más barato forzar una pareja mala que
    declararla residuo, que es exactamente el comportamiento que este
    parámetro debe evitar. 80 es el techo medido de la meseta común a las 4
    combinaciones, no un ajuste fino a un resultado esperado: es el punto
    donde, por encima, la solución empieza a moverse (y para peor) al mover
    el parámetro, y por debajo (hasta 20) no se mueve en absoluto.

    Devuelve (pares, residuo_real, residuo_replica) con índices posicionales
    (0-based) sobre los arrays de entrada."""
    n = len(real_precios)
    m = len(rep_precios)
    inf = float("inf")
    dp = np.full((n + 1, m + 1), inf)
    dp[0, 0] = 0.0
    for i in range(1, n + 1):
        dp[i, 0] = i * gap_cost
    for j in range(1, m + 1):
        dp[0, j] = j * gap_cost
    ptr = np.zeros((n + 1, m + 1), dtype=np.int8)  # 0=diag, 1=salta real, 2=salta réplica
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            costo_match = dp[i - 1, j - 1] + abs(real_precios[i - 1] - rep_precios[j - 1])
            costo_salta_real = dp[i - 1, j] + gap_cost
            costo_salta_rep = dp[i, j - 1] + gap_cost
            mejor = min(costo_match, costo_salta_real, costo_salta_rep)
            dp[i, j] = mejor
            if mejor == costo_match:
                ptr[i, j] = 0
            elif mejor == costo_salta_real:
                ptr[i, j] = 1
            else:
                ptr[i, j] = 2

    i, j = n, m
    pares: list[tuple[int, int]] = []
    residuo_real: list[int] = []
    residuo_rep: list[int] = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ptr[i, j] == 0:
            pares.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or ptr[i, j] == 1):
            residuo_real.append(i - 1)
            i -= 1
        else:
            residuo_rep.append(j - 1)
            j -= 1
    pares.reverse()
    residuo_real.reverse()
    residuo_rep.reverse()
    return pares, residuo_real, residuo_rep


def alinear_por_estrategia(
    real_df: pd.DataFrame,
    rep_df: pd.DataFrame,
    gap_cost: float = 80.0,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Como `alinear_posiciones`, pero separa primero por `side` (una
    posición SELL nunca puede ser la pareja de una BUY/L) y recompone los
    índices posicionales sobre `real_df`/`rep_df` completos (ya ordenados
    por t_open ascendente, ya filtrados a una sola estrategia)."""
    pares: list[tuple[int, int]] = []
    residuo_real: list[int] = []
    residuo_rep: list[int] = []
    for lado in ("L", "S"):
        idx_real = [k for k in range(len(real_df)) if _lado_normalizado(real_df.iloc[k]["side"]) == lado]
        idx_rep = [k for k in range(len(rep_df)) if _lado_normalizado(rep_df.iloc[k]["side"]) == lado]
        if not idx_real and not idx_rep:
            continue
        real_p = real_df.iloc[idx_real]["precio_open"].to_numpy(dtype=float)
        rep_p = rep_df.iloc[idx_rep]["precio_open"].to_numpy(dtype=float)
        p, ur, urp = alinear_posiciones(real_p, rep_p, gap_cost=gap_cost)
        pares.extend((idx_real[a], idx_rep[b]) for a, b in p)
        residuo_real.extend(idx_real[a] for a in ur)
        residuo_rep.extend(idx_rep[b] for b in urp)
    return pares, residuo_real, residuo_rep


# --------------------------------------------------------------------- carga
def _cargar_insumos(
    *,
    posiciones_replica_csv: str | Path,
    verdad_terreno_csv: str | Path,
    sl_enviado_csv: str | Path,
    metricas_json: str | Path,
    mapeo_json: str | Path,
) -> dict[str, Any]:
    with open(metricas_json, encoding="utf-8") as f:
        metricas = json.load(f)
    verificar_t1(metricas)

    verdad = pd.read_csv(verdad_terreno_csv)
    replica = pd.read_csv(posiciones_replica_csv)
    sl_enviado = pd.read_csv(sl_enviado_csv).set_index("position_id")
    equivalencia, conteos_equivalencia = cargar_equivalencia(mapeo_json)

    return {
        "metricas": metricas,
        "verdad": verdad,
        "replica": replica,
        "sl_enviado": sl_enviado,
        "equivalencia": equivalencia,
        "conteos_equivalencia": conteos_equivalencia,
    }


# ----------------------------------------------------------- fila por posición
def _fila_real(row: pd.Series, sl_enviado: pd.DataFrame) -> dict[str, Any]:
    position_id = int(row["position_id"])
    fila: dict[str, Any] = {
        "tipo_fila": "REAL",
        "pareja": "SIN_PAREJA",
        "position_id": position_id,
        "strategy_id": row["strategy_id"],
        "real_side": row["side"],
        "real_t_open_epoch": row["t_open_epoch"],
        "real_t_open_servidor": row["t_open_servidor"],
        "real_precio_open": row["precio_open"],
        "real_t_close_epoch": row["t_close_epoch"],
        "real_t_close_servidor": row["t_close_servidor"],
        "real_precio_close": row["precio_close"],
        "real_reason_name": row["reason_name"],
        "real_profit_clp": row["profit"],
        "real_volume": row["volume"],
        "real_profit_por_lote_clp": (
            float(row["profit"]) / float(row["volume"]) if float(row["volume"]) else float("nan")
        ),
        "real_resultado": resultado_real(row["profit"]),
        "excluido_criterio": row["reason_name"] in REASON_EXCLUIDOS_DEL_CRITERIO,
        "categoria_exclusion": row["reason_name"] if row["reason_name"] in REASON_EXCLUIDOS_DEL_CRITERIO else "",
    }
    if position_id in sl_enviado.index:
        estado_sl = sl_enviado.loc[position_id]
        fila["real_sl_status"] = estado_sl["sl_status"]
        fila["real_sl_enviado"] = estado_sl["sl_clamped_enviado"]
    else:
        fila["real_sl_status"] = "NO_LOGUEADO"
        fila["real_sl_enviado"] = float("nan")
    return fila


def _completar_pareja_replica(fila: dict[str, Any], rep_row: pd.Series, equivalencia: dict[str, set[str]]) -> None:
    fila["pareja"] = "EMPAREJADA"
    fila["replica_side"] = rep_row["side"]
    fila["replica_t_open"] = rep_row["t_open"]
    fila["replica_t_open_servidor"] = rep_row["t_open_servidor"]
    fila["replica_precio_open"] = rep_row["precio_open"]
    fila["replica_t_close"] = rep_row["t_close"]
    fila["replica_t_close_servidor"] = rep_row["t_close_servidor"]
    fila["replica_precio_close"] = rep_row["precio_close"]
    fila["replica_motivo_cierre"] = rep_row["motivo_cierre"]
    fila["replica_sl_open_enviado"] = rep_row["sl_open_enviado"]
    fila["replica_resultado"] = resultado_replica(rep_row["side"], rep_row["precio_open"], rep_row["precio_close"])

    fila["delta_precio_open"] = float(fila["real_precio_open"]) - float(rep_row["precio_open"])
    fila["delta_t_open_s"] = float(fila["real_t_open_epoch"]) - float(rep_row["t_open"])
    fila["delta_t_close_s"] = float(fila["real_t_close_epoch"]) - float(rep_row["t_close"])
    fila["delta_precio_close"] = float(fila["real_precio_close"]) - float(rep_row["precio_close"])

    fila["coincide_precio_open"] = _cerca(fila["real_precio_open"], rep_row["precio_open"], _EPS_PRECIO)
    # D-46: los instantes se comparan TRUNCADOS AL SEGUNDO (floor), no en
    # bit-identidad estricta -- ver docstring de `_mismo_segundo`. Se aplica
    # a los dos campos de instante, entrada y salida.
    fila["coincide_t_open"] = _mismo_segundo(fila["real_t_open_epoch"], rep_row["t_open"])
    fila["coincide_t_close"] = _mismo_segundo(fila["real_t_close_epoch"], rep_row["t_close"])
    fila["coincide_precio_close"] = _cerca(fila["real_precio_close"], rep_row["precio_close"], _EPS_PRECIO)

    coincide_razon, no_evaluable_razon = evaluar_razon_cierre(
        rep_row["motivo_cierre"], fila["real_reason_name"], equivalencia
    )
    fila["coincide_razon_cierre"] = coincide_razon
    fila["razon_cierre_no_evaluable"] = no_evaluable_razon
    fila["coincide_resultado"] = fila["real_resultado"] == fila["replica_resultado"]

    if fila["real_sl_status"] == "CLAMPED":
        fila["sl_evaluable"] = True
        fila["delta_sl"] = float(fila["real_sl_enviado"]) - float(rep_row["sl_open_enviado"])
        fila["coincide_sl"] = _cerca(fila["real_sl_enviado"], rep_row["sl_open_enviado"], _EPS_PRECIO)
    else:
        fila["sl_evaluable"] = False
        fila["delta_sl"] = float("nan")
        fila["coincide_sl"] = None

    campos_criterio = [
        fila["coincide_precio_open"], fila["coincide_t_open"], fila["coincide_t_close"],
        fila["coincide_precio_close"], bool(coincide_razon) if coincide_razon is not None else False,
        fila["coincide_resultado"],
    ]
    fila["n_campos_coinciden"] = sum(1 for c in campos_criterio if c)
    fila["casa_6_campos"] = all(campos_criterio) and not no_evaluable_razon


def _fila_replica_huerfana(rep_row: pd.Series) -> dict[str, Any]:
    return {
        "tipo_fila": "REPLICA_SIN_PAREJA",
        "pareja": "SIN_PAREJA",
        "position_id": None,
        "strategy_id": rep_row["strategy_id"],
        "replica_side": rep_row["side"],
        "replica_t_open": rep_row["t_open"],
        "replica_t_open_servidor": rep_row["t_open_servidor"],
        "replica_precio_open": rep_row["precio_open"],
        "replica_t_close": rep_row["t_close"],
        "replica_t_close_servidor": rep_row["t_close_servidor"],
        "replica_precio_close": rep_row["precio_close"],
        "replica_motivo_cierre": rep_row["motivo_cierre"],
        "replica_sl_open_enviado": rep_row["sl_open_enviado"],
        "replica_resultado": resultado_replica(rep_row["side"], rep_row["precio_open"], rep_row["precio_close"]),
    }


# ------------------------------------------------------------- categoría D.6
def _marcar_primera_orden_conocida(filas: list[dict[str, Any]]) -> None:
    """§5 del brief / D.6 del spec: la primera orden real salió con
    retcode=10027 (AutoTrading deshabilitado) y reabrió 60 s más tarde. Ese
    desfase de la PRIMERA posición es artefacto del entorno -- se etiqueta
    con su propia categoría, no se cuenta como fallo genérico de paridad de
    instante de entrada, y NO se ajusta nada para hacerlo cuadrar (se sigue
    reportando el delta real, sólo se añade la etiqueta)."""
    candidatas = [f for f in filas if f["tipo_fila"] == "REAL"]
    if not candidatas:
        return
    primera = min(candidatas, key=lambda f: float(f["real_t_open_epoch"]))
    primera["categoria_conocida"] = "PRIMERA_ORDEN_RETCODE_10027_60S"
    for f in filas:
        f.setdefault("categoria_conocida", "")


# --------------------------------------------------------------- construcción
def construir_comparacion(
    verdad: pd.DataFrame,
    replica: pd.DataFrame,
    sl_enviado: pd.DataFrame,
    equivalencia: dict[str, set[str]],
    *,
    gap_cost: float = 80.0,
) -> pd.DataFrame:
    """Regla dura 6: emparejamiento 1-a-1 -- ninguna posición real sirve de
    pareja a dos de la réplica ni al revés. Ambos residuos se listan
    íntegros (no resumidos), como filas propias."""
    filas: list[dict[str, Any]] = []

    for strategy_id in sorted(verdad["strategy_id"].unique()):
        real_s = verdad[verdad["strategy_id"] == strategy_id].sort_values("t_open_epoch").reset_index(drop=True)
        rep_s = replica[replica["strategy_id"] == strategy_id].sort_values("t_open").reset_index(drop=True)

        pares, residuo_real, residuo_rep = alinear_por_estrategia(real_s, rep_s, gap_cost=gap_cost)
        pares_por_real = dict(pares)

        for k in range(len(real_s)):
            fila = _fila_real(real_s.iloc[k], sl_enviado)
            if k in pares_por_real:
                _completar_pareja_replica(fila, rep_s.iloc[pares_por_real[k]], equivalencia)
            filas.append(fila)

        for j in residuo_rep:
            filas.append(_fila_replica_huerfana(rep_s.iloc[j]))

    _marcar_primera_orden_conocida(filas)

    df = pd.DataFrame(filas)
    if "excluido_criterio" in df.columns:
        # las filas REPLICA_SIN_PAREJA no tienen este campo -> NaN, lo que
        # deja la columna en dtype 'object' y rompe `~serie` (invierte bits
        # de los bool de Python en vez de negar lógicamente). Se normaliza
        # a bool explícito; sólo aplica semánticamente a filas REAL.
        df["excluido_criterio"] = [bool(v) if v is True or v is False else False for v in df["excluido_criterio"]]
    orden_t = df.apply(
        lambda r: float(r["real_t_open_epoch"]) if r["tipo_fila"] == "REAL" else float(r["replica_t_open"]),
        axis=1,
    )
    df = df.assign(_orden_t=orden_t).sort_values(["strategy_id", "_orden_t"]).drop(columns="_orden_t")
    return df.reset_index(drop=True)


# ------------------------------------------------------------------ resumen
def resumen_agregado(
    comparacion: pd.DataFrame,
    *,
    conteos_equivalencia: dict[tuple[str, str], int],
) -> dict[str, Any]:
    reales = comparacion[comparacion["tipo_fila"] == "REAL"]
    huerfanas_replica = comparacion[comparacion["tipo_fila"] == "REPLICA_SIN_PAREJA"]

    evaluables = reales[~reales["excluido_criterio"]]
    excluidos = reales[reales["excluido_criterio"]]

    denominador_posiciones = int(len(evaluables))

    emparejadas_evaluables = evaluables[evaluables["pareja"] == "EMPAREJADA"]
    sin_pareja_evaluables = evaluables[evaluables["pareja"] == "SIN_PAREJA"]

    def _tasa_campo(col: str, delta_col: str | None = None) -> dict[str, Any]:
        vals = emparejadas_evaluables[col]
        si = int((vals == True).sum())  # noqa: E712 -- distinguir True de NaN/None
        no = int((vals == False).sum())  # noqa: E712
        no_evaluable = int(vals.isna().sum())
        salida: dict[str, Any] = {"si": si, "no": no, "no_evaluable": no_evaluable}
        if delta_col is not None:
            # precio_open/precio_close: "coincide" == delta exactamente 0
            # (D-45, con eps de punto flotante). t_open/t_close: "coincide"
            # == mismo segundo tras floor (D-46), no delta==0 -- ver
            # `_mismo_segundo`. En los dos casos la cuenta binaria puede
            # quedar 0/N sin que eso signifique que la réplica está lejos --
            # se publica también la distribución del |delta| crudo (sin
            # truncar) como contexto, sin decidir un umbral de paso (eso es
            # de Opus, §9 del spec).
            abs_delta = emparejadas_evaluables[delta_col].abs().dropna()
            if len(abs_delta):
                salida["delta_abs_stats"] = {
                    "n": int(len(abs_delta)),
                    "min": float(abs_delta.min()),
                    "p50": float(abs_delta.median()),
                    "p90": float(np.percentile(abs_delta, 90)),
                    "max": float(abs_delta.max()),
                }
            else:
                salida["delta_abs_stats"] = None
        return salida

    campos = {
        "precio_open": _tasa_campo("coincide_precio_open", "delta_precio_open"),
        "t_open": _tasa_campo("coincide_t_open", "delta_t_open_s"),
        "t_close": _tasa_campo("coincide_t_close", "delta_t_close_s"),
        "precio_close": _tasa_campo("coincide_precio_close", "delta_precio_close"),
        "razon_cierre": _tasa_campo("coincide_razon_cierre"),
        "resultado": _tasa_campo("coincide_resultado"),
    }

    n_casa_6 = int(emparejadas_evaluables["casa_6_campos"].sum())
    n_no_casa_6 = int(len(emparejadas_evaluables) - n_casa_6)

    sl_evaluable = emparejadas_evaluables[emparejadas_evaluables["sl_evaluable"] == True]  # noqa: E712
    n_sl_evaluable = int(len(sl_evaluable))
    n_sl_coincide = int((sl_evaluable["coincide_sl"] == True).sum())  # noqa: E712

    por_categoria_exclusion = (
        excluidos.groupby("categoria_exclusion").size().to_dict() if len(excluidos) else {}
    )

    residuo_real_ids = sin_pareja_evaluables["position_id"].tolist()
    residuo_real_ids_excluidos_no_aplica = excluidos[excluidos["pareja"] == "SIN_PAREJA"]["position_id"].tolist()

    resumen = {
        "denominadores": {
            "posiciones": {
                "valor": denominador_posiciones,
                "formula": "152 posiciones reales en ventana VENTANA_902 - 11 CLIENT_manual - 1 TP",
                "detalle_por_estrategia": {
                    sid: int((evaluables["strategy_id"] == sid).sum())
                    for sid in sorted(evaluables["strategy_id"].unique())
                },
            },
            "barras_senal": DENOMINADOR_BARRAS_SENAL,
            "nota": (
                "Dos denominadores distintos, NUNCA se mezclan (regla dura 7 / "
                "E.2.2): 'posiciones' cuenta re-entradas secuenciales de una "
                "misma señal; 'barras_senal' cuenta candidatos de A6 a nivel de "
                "vela. El corte por barra-señal es citado del spec, no "
                "recomputado por este comparador."
            ),
        },
        "criterio_de_paso_6_campos": {
            "denominador_evaluable": denominador_posiciones,
            "n_emparejadas": int(len(emparejadas_evaluables)),
            "n_sin_pareja_real": int(len(sin_pareja_evaluables)),
            "position_id_sin_pareja_real": residuo_real_ids,
            "casa_los_6_campos": n_casa_6,
            "no_casa_los_6_campos": n_no_casa_6,
            "por_campo": campos,
        },
        "excluidos_del_criterio": {
            "total": int(len(excluidos)),
            "por_categoria": {str(k): int(v) for k, v in por_categoria_exclusion.items()},
            "profit_clp_client_manual": float(
                excluidos[excluidos["categoria_exclusion"] == "CLIENT_manual"]["real_profit_clp"].sum()
            ) if len(excluidos) else 0.0,
        },
        "sl_de_entrada_no_gating": {
            "n_evaluable": n_sl_evaluable,
            "n_no_evaluable": int(len(emparejadas_evaluables) - n_sl_evaluable),
            "n_coincide": n_sl_coincide,
        },
        "residuos_1_a_1": {
            "replica_sin_pareja_total": int(len(huerfanas_replica)),
            "replica_sin_pareja_por_estrategia": {
                sid: int((huerfanas_replica["strategy_id"] == sid).sum())
                for sid in sorted(huerfanas_replica["strategy_id"].unique())
            } if len(huerfanas_replica) else {},
            "real_sin_pareja_total": int(len(comparacion[comparacion["pareja"] == "SIN_PAREJA"]) - len(huerfanas_replica)),
        },
        "divergencia_conocida_primera_orden": {
            "descripcion": (
                "primera orden real: retcode=10027 (AutoTrading deshabilitado), "
                "reabre 60s despues (D.6). No se cuenta como fallo generico de "
                "paridad de instante de entrada; se reporta con su propio delta."
            ),
            "n_posiciones_marcadas": int((comparacion["categoria_conocida"] == "PRIMERA_ORDEN_RETCODE_10027_60S").sum()),
        },
        "monetario_clp": {
            "neto_152_posiciones_clp": float(reales["real_profit_clp"].sum()),
            "neto_152_posiciones_clp_por_lote": float(
                (reales["real_profit_clp"] / reales["real_volume"]).sum()
            ),
            "lote_vivo": 0.67,
        },
        "equivalencia_motivo_reason_referencia": {
            f"{motivo}|{reason}": n for (motivo, reason), n in sorted(conteos_equivalencia.items())
        },
    }
    return resumen


# --------------------------------------------------------------------- lineage
def _git_sha(root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except Exception:
        return "NO_EVALUABLE"


def _config_hash_desde_metricas(metricas: dict[str, Any]) -> str:
    v = metricas.get("lineage", {}).get("config_hash")
    if v:
        return v
    return hashlib.sha256(b"sin config_hash en metricas_p_cap.json").hexdigest()


def _lineage(metricas: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": f"T0.7-P-CAP-comparador-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        "area": "F0",
        "experimento": EXPERIMENTO,
        "config_hash": _config_hash_desde_metricas(metricas),
        "substrate_id": "posiciones_replica.csv + verdad_terreno_902.csv",
        "engine_sha": ENGINE_SHA,
        "git_sha": _git_sha(ROOT),
        "etapa": "F0",
        "generador": "scripts/analysis/realtick_bt/faulty/comparador.py",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ------------------------------------------------------------------- reporte md
def _md_tabla(headers: list[str], filas: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for f in filas:
        out.append("| " + " | ".join(str(x) for x in f) + " |")
    return "\n".join(out)


def _escribir_md(resultado: dict[str, Any], path: Path) -> None:
    d = resultado["denominadores"]
    c = resultado["criterio_de_paso_6_campos"]
    e = resultado["excluidos_del_criterio"]
    sl = resultado["sl_de_entrada_no_gating"]
    r = resultado["residuos_1_a_1"]
    dc = resultado["divergencia_conocida_primera_orden"]
    m = resultado["monetario_clp"]

    partes = [
        "# P-CAP -- resultado del comparador (Componente E)",
        "",
        "Sin conclusiones ni veredicto (charter §A.4/§A.13) -- el memo de "
        "interpretación lo escribe Opus en `05-analisis/`.",
        "",
        "## Denominadores (regla dura 7 -- nunca se mezclan)",
        "",
        _md_tabla(
            ["corte", "valor", "detalle"],
            [
                ["posiciones (este comparador)", d["posiciones"]["valor"], d["posiciones"]["formula"]],
                ["barras-señal (A6, citado)", d["barras_senal"]["total"],
                 f"S6={d['barras_senal']['S6']} / ST={d['barras_senal']['ST']}"],
            ],
        ),
        "",
        "## Criterio de paso -- 6 campos (D-45, D-46)",
        "",
        f"Denominador evaluable: **{c['denominador_evaluable']}** "
        f"(emparejadas: {c['n_emparejadas']}, sin pareja real: {c['n_sin_pareja_real']}).",
        "",
        f"Casan los 6 campos: **{c['casa_los_6_campos']}**. No casan: **{c['no_casa_los_6_campos']}**.",
        "",
        "### Por campo (sobre las emparejadas evaluables)",
        "",
        "'si'/'no' es bit-identidad estricta (delta==0, D-45) para "
        "precio_open/precio_close/razon_cierre/resultado; para t_open/"
        "t_close es mismo segundo tras truncar -- floor, no round (D-46). "
        "Para los 4 campos numéricos se añade la distribución de |delta| "
        "crudo (sin truncar) como contexto -- no decide ningún umbral de "
        "paso.",
        "",
        _md_tabla(
            ["campo", "si", "no", "no_evaluable"],
            [[k, v["si"], v["no"], v["no_evaluable"]] for k, v in c["por_campo"].items()],
        ),
        "",
        "### Distribución de |delta| (campos numéricos, emparejadas evaluables)",
        "",
        _md_tabla(
            ["campo", "n", "min", "p50", "p90", "max"],
            [
                [k, s["n"], f"{s['min']:.4f}", f"{s['p50']:.4f}", f"{s['p90']:.4f}", f"{s['max']:.4f}"]
                for k, v in c["por_campo"].items()
                if (s := v.get("delta_abs_stats")) is not None
            ],
        ),
        "",
        "## Excluidos del criterio de paso",
        "",
        _md_tabla(
            ["categoria", "n"],
            [[k, v] for k, v in e["por_categoria"].items()] + [["total", e["total"]]],
        ),
        f"\nProfit CLIENT_manual: {e['profit_clp_client_manual']:,.2f} CLP.",
        "",
        "## SL de entrada (medido, sin poder de bloqueo)",
        "",
        _md_tabla(
            ["evaluable", "no_evaluable", "coincide"],
            [[sl["n_evaluable"], sl["n_no_evaluable"], sl["n_coincide"]]],
        ),
        "",
        "## Residuos del emparejamiento 1-a-1",
        "",
        f"Réplica sin pareja: **{r['replica_sin_pareja_total']}** "
        f"({r['replica_sin_pareja_por_estrategia']}). "
        f"Real sin pareja (evaluables): **{r['real_sin_pareja_total']}**.",
        "",
        "## Divergencia conocida -- primera orden",
        "",
        dc["descripcion"],
        f"\nPosiciones marcadas: {dc['n_posiciones_marcadas']}.",
        "",
        "## Monetario (CLP, charter §A.1)",
        "",
        _md_tabla(
            ["neto 152 posiciones (CLP)", "neto por lote (CLP/lote)", "lote vivo"],
            [[f"{m['neto_152_posiciones_clp']:,.2f}", f"{m['neto_152_posiciones_clp_por_lote']:,.2f}", m["lote_vivo"]]],
        ),
        "",
        "## Lineage",
        "",
        _md_tabla(
            list(resultado["lineage"].keys()),
            [list(resultado["lineage"].values())],
        ),
        "",
    ]
    path.write_text("\n".join(partes), encoding="utf-8")


# ------------------------------------------------------------------- orquesta
def comparar_p_cap(
    *,
    posiciones_replica_csv: str | Path = POSICIONES_REPLICA_CSV,
    verdad_terreno_csv: str | Path = VERDAD_TERRENO_CSV,
    sl_enviado_csv: str | Path = SL_ENVIADO_CSV,
    metricas_json: str | Path = METRICAS_P_CAP_JSON,
    mapeo_json: str | Path = MAPEO_MOTIVOS_JSON,
    out_csv: str | Path = OUT_CSV,
    out_json: str | Path = OUT_JSON,
    out_md: str | Path = OUT_MD,
    gap_cost: float = 80.0,
) -> dict[str, Any]:
    """Corre el Componente E completo: carga, verifica t1, empareja,
    compara campo a campo, agrega y escribe los 3 artefactos de §6/E.3."""
    insumos = _cargar_insumos(
        posiciones_replica_csv=posiciones_replica_csv,
        verdad_terreno_csv=verdad_terreno_csv,
        sl_enviado_csv=sl_enviado_csv,
        metricas_json=metricas_json,
        mapeo_json=mapeo_json,
    )
    comparacion = construir_comparacion(
        insumos["verdad"], insumos["replica"], insumos["sl_enviado"],
        insumos["equivalencia"], gap_cost=gap_cost,
    )

    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    comparacion.to_csv(out_csv, index=False)

    resumen = resumen_agregado(comparacion, conteos_equivalencia=insumos["conteos_equivalencia"])
    resumen["lineage"] = _lineage(insumos["metricas"])

    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False, default=str)

    out_md = Path(out_md)
    _escribir_md(resumen, out_md)

    return resumen


if __name__ == "__main__":
    resultado = comparar_p_cap()
    print(json.dumps(resultado, indent=2, ensure_ascii=False, default=str))
