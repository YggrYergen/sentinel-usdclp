r"""divergencia_neto.py -- T0.7-M-0, T0.7 / A6 Pata A / P-CAP.

Spec: research/fases/F0-preparacion/02-specs/T0.7-M-0-brief-divergencia-neto.md

Mide la divergencia de NETO (resultado monetario) entre la réplica del motor
faulty y las 152 posiciones reales de la cuenta 902 -- el segundo criterio de
paso de T0.7 (junto a la paridad campo-a-campo de `comparador.py`), que nunca
se había computado.

Este script es de MEDICIÓN, autocontenido: no importa `ciclos.py`,
`estado_por_barra.py`, `llamador.py`, `comparador.py` ni `config_faulty.py`
(están congelados y otro agente puede estar leyéndolos en paralelo).

Fuentes (corrida vigente, reloj reconstruido -- NUNCA la rejilla sintética
ni sensibilidad_cadencia_15.0):
  - data/analysis/p_cap/replica/posiciones_replica.csv (157 posiciones réplica)
  - data/analysis/p_cap/comparacion_p_cap.csv (162 filas = 152 REAL + 10
    REPLICA_SIN_PAREJA, ya trae las columnas replica_* emparejadas)

REPORT-ONLY: este módulo no interpreta, no concluye, no recomienda. Sólo
calcula y escribe números. Ningún veredicto pasa/no-pasa.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[4]

RUTA_REPLICA = _REPO_ROOT / "data" / "analysis" / "p_cap" / "replica" / "posiciones_replica.csv"
RUTA_COMPARACION = _REPO_ROOT / "data" / "analysis" / "p_cap" / "comparacion_p_cap.csv"
RUTA_P_CAP_RESULTADO = (
    _REPO_ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.7-p-cap" / "p_cap_resultado.json"
)

RUTA_SALIDA_DIR = (
    _REPO_ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados" / "T0.7-p-cap"
)
RUTA_CSV = RUTA_SALIDA_DIR / "divergencia_neto.csv"
RUTA_JSON = RUTA_SALIDA_DIR / "divergencia_neto.json"
RUTA_MD = RUTA_SALIDA_DIR / "divergencia_neto.md"

# --- constantes fijadas por el brief (verbatim, no recalculadas) -----------
VOLUMEN_VIVO = 0.67           # F0-INFRA-0025 / verificado uniforme en 152 reales
TAMANO_CONTRATO = 100.0       # F0-INFRA-0020 (trade_contract_size)
UMBRAL_ACEPTABLE_PCT = 0.3    # criterio de paso, TRACKER T0.7
UMBRAL_IDEAL_PCT = 0.15

RUN_ID = "T0.7-M-0-DIVNETO-0001"
AREA = "F0"
EXPERIMENTO = "T0.7-M-0-divergencia-neto"
SUBSTRATE_ID = "posiciones_replica.csv(reloj_reconstruido) + comparacion_p_cap.csv"
ETAPA = "medicion"
GENERADOR = "scripts/analysis/realtick_bt/faulty/divergencia_neto.py"


# --------------------------------------------------------------- dirección
def direccion_real(side):
    """BUY -> +1.0, SELL -> -1.0. Cualquier otro valor -> NaN (nunca
    inventa signo). Acepta escalar o vector (Series/ndarray)."""
    if isinstance(side, (pd.Series, np.ndarray, list)):
        s = pd.Series(side)
        return s.map({"BUY": 1.0, "SELL": -1.0}).astype(float).to_numpy() if not isinstance(side, pd.Series) else s.map({"BUY": 1.0, "SELL": -1.0}).astype(float)
    return {"BUY": 1.0, "SELL": -1.0}.get(side, float("nan"))


def direccion_replica(side):
    """L -> +1.0 (BUY/long), S -> -1.0 (SELL/short). Cualquier otro valor ->
    NaN. Mapeo verificado 1:1 contra `real_side` en las 157 posiciones
    emparejadas (crosstab: 78 BUY-L / 69 SELL-S, cero discrepancias)."""
    if isinstance(side, (pd.Series, np.ndarray, list)):
        s = pd.Series(side)
        return s.map({"L": 1.0, "S": -1.0}).astype(float).to_numpy() if not isinstance(side, pd.Series) else s.map({"L": 1.0, "S": -1.0}).astype(float)
    return {"L": 1.0, "S": -1.0}.get(side, float("nan"))


# --------------------------------------------------------------- bruto_usd
def bruto_usd(precio_open, precio_close, direccion, volumen=VOLUMEN_VIVO, contrato=TAMANO_CONTRATO):
    """bruto_usd = (precio_close - precio_open) * direccion * volumen * contrato.
    Fórmula verbatim del brief (§1). Vectorizable (acepta escalares o
    Series/ndarray de igual forma)."""
    return (precio_close - precio_open) * direccion * volumen * contrato


# --------------------------------------------------------------- tasa implícita
def tasa_implicita(profit_clp, bruto_usd_val):
    """tasa_i = profit_clp_i / bruto_usd_i. bruto_usd_i == 0 -> NaN (no
    evaluable, división imposible), NUNCA 0 ni inf."""
    profit_clp = pd.Series(profit_clp).astype(float).reset_index(drop=True)
    bruto_usd_val = pd.Series(bruto_usd_val).astype(float).reset_index(drop=True)
    out = profit_clp / bruto_usd_val.replace(0.0, np.nan)
    return out


# --------------------------------------------------------------- stats_control
def stats_control(tasa: pd.Series) -> dict:
    """n, p10, p50, p90, min, max, dispersión relativa (std/mean) de una
    serie de tasas. Usa pd.isna() para filtrar -- gotcha del brief: pandas
    convierte None a NaN en columnas float y `v is not None` no lo detecta."""
    s = pd.Series(tasa).astype(float)
    s = s[~s.isna()]
    if s.size == 0:
        return {
            "n": 0, "p10": None, "p50": None, "p90": None,
            "min": None, "max": None, "dispersion_relativa": None,
        }
    mean = float(s.mean())
    std = float(s.std())
    return {
        "n": int(s.size),
        "p10": float(s.quantile(0.10)),
        "p50": float(s.quantile(0.50)),
        "p90": float(s.quantile(0.90)),
        "min": float(s.min()),
        "max": float(s.max()),
        "dispersion_relativa": (std / mean) if mean != 0 else None,
    }


# --------------------------------------------------------------- tasa por día
def tasa_por_dia(df: pd.DataFrame, col_day: str, col_tasa: str) -> pd.Series:
    """Tasa media por día de cierre (método de emparejamiento declarado en
    §3 del brief). pd.isna() implícito vía groupby (pandas excluye NaN de
    la media por defecto)."""
    return df.groupby(col_day)[col_tasa].mean()


def mapear_tasa_dia(dias: pd.Series, tabla: pd.Series) -> pd.Series:
    """Empareja cada posición de la réplica con la tasa del día de su
    cierre. Día ausente de la tabla -> NaN (no evaluable), nunca 0 ni un
    valor inventado."""
    return pd.Series(dias).map(tabla)


# --------------------------------------------------------------- divergencia
def divergencia(neto_real: float, neto_replica: float, n_real: int, n_replica: int) -> dict:
    """divergencia_pct = (neto_replica - neto_real) / |neto_real| * 100.
    Fórmula verbatim del brief (§3). neto_real == 0 -> divergencia_pct no
    evaluable (None), nunca inf."""
    diff_abs = neto_replica - neto_real
    if neto_real == 0:
        pct = None
    else:
        pct = diff_abs / abs(neto_real) * 100.0
    return {
        "neto_real": float(neto_real),
        "neto_replica": float(neto_replica),
        "n_real": int(n_real),
        "n_replica": int(n_replica),
        "diff_abs": float(diff_abs),
        "divergencia_pct": pct,
    }


# --------------------------------------------------------------- descomposición
def descomponer(term_replica_sin_pareja: float, term_real_sin_pareja: float,
                 term_matched_diff: float, diff_total: float) -> dict:
    """Reparte diff_total en 3 sumandos (brief §6):
      1. term_replica_sin_pareja: bruto de posiciones que la réplica abrió
         y no existieron (aporta con su signo propio al total réplica).
      2. term_real_sin_pareja: bruto de posiciones reales que la réplica NO
         reprodujo -- entra en la fórmula como -term_real_sin_pareja (falta
         en el lado réplica).
      3. term_matched_diff: diferencia (réplica - real) de las posiciones
         SÍ emparejadas.
    Si los tres sumandos no reconstruyen diff_total exacto, se reporta el
    residuo, nunca se fuerza a cuadrar."""
    term_real_sin_pareja_neg = -term_real_sin_pareja
    suma = term_replica_sin_pareja + term_real_sin_pareja_neg + term_matched_diff
    return {
        "term_replica_sin_pareja": float(term_replica_sin_pareja),
        "term_real_sin_pareja_neg": float(term_real_sin_pareja_neg),
        "term_matched_diff": float(term_matched_diff),
        "suma_terminos": float(suma),
        "diff_total": float(diff_total),
        "residuo": float(diff_total - suma),
    }


# ============================================================ orquestación
def _cargar_datos():
    rep = pd.read_csv(RUTA_REPLICA)
    cmp = pd.read_csv(RUTA_COMPARACION)
    return rep, cmp


def _preparar_replica(rep: pd.DataFrame) -> pd.DataFrame:
    rep = rep.copy()
    rep["direccion"] = direccion_replica(rep["side"])
    rep["bruto_usd"] = bruto_usd(rep["precio_open"], rep["precio_close"], rep["direccion"])
    rep["close_day"] = rep["t_close_servidor"].astype(str).str.slice(0, 10)
    return rep


def _preparar_real(cmp: pd.DataFrame) -> pd.DataFrame:
    real = cmp[cmp["tipo_fila"] == "REAL"].copy()
    real["direccion"] = direccion_real(real["real_side"])
    real["real_bruto_usd"] = bruto_usd(real["real_precio_open"], real["real_precio_close"], real["direccion"])
    # OJO indice: `real` conserva el indice original no contiguo de `cmp`
    # (filas REPLICA_SIN_PAREJA intercaladas). tasa_implicita() devuelve una
    # Series con indice nuevo (0..n-1) -- asignar directamente alinearia por
    # INDICE y colaria NaN silenciosos. Se fuerza asignacion POSICIONAL con
    # .to_numpy() (ver test_tasa_implicita_asignable_a_dataframe_con_indice_no_contiguo).
    real["tasa"] = tasa_implicita(real["real_profit_clp"].to_numpy(), real["real_bruto_usd"].to_numpy()).to_numpy()
    real["close_day"] = real["real_t_close_servidor"].astype(str).str.slice(0, 10)
    return real


def _preparar_matched(cmp: pd.DataFrame) -> pd.DataFrame:
    """Filas de comparacion_p_cap.csv con réplica emparejada (replica_side
    no nulo): las 147 = 152 real - 5 sin pareja = 157 réplica - 10 sin pareja."""
    sub = cmp[cmp["replica_side"].notna() & (cmp["tipo_fila"] == "REAL")].copy()
    sub["real_direccion"] = direccion_real(sub["real_side"])
    sub["real_bruto_usd"] = bruto_usd(sub["real_precio_open"], sub["real_precio_close"], sub["real_direccion"])
    sub["replica_direccion"] = direccion_replica(sub["replica_side"])
    sub["replica_bruto_usd"] = bruto_usd(sub["replica_precio_open"], sub["replica_precio_close"], sub["replica_direccion"])
    sub["replica_close_day"] = sub["replica_t_close_servidor"].astype(str).str.slice(0, 10)
    return sub


def _preparar_real_sin_pareja(cmp: pd.DataFrame) -> pd.DataFrame:
    sub = cmp[(cmp["tipo_fila"] == "REAL") & (cmp["replica_side"].isna())].copy()
    sub["real_direccion"] = direccion_real(sub["real_side"])
    sub["real_bruto_usd"] = bruto_usd(sub["real_precio_open"], sub["real_precio_close"], sub["real_direccion"])
    return sub


def _preparar_replica_sin_pareja(cmp: pd.DataFrame) -> pd.DataFrame:
    sub = cmp[cmp["tipo_fila"] == "REPLICA_SIN_PAREJA"].copy()
    sub["replica_direccion"] = direccion_replica(sub["replica_side"])
    sub["replica_bruto_usd"] = bruto_usd(sub["replica_precio_open"], sub["replica_precio_close"], sub["replica_direccion"])
    sub["replica_close_day"] = sub["replica_t_close_servidor"].astype(str).str.slice(0, 10)
    return sub


def construir_csv_posicion_a_posicion(cmp: pd.DataFrame, rep: pd.DataFrame, tabla_tasa: pd.Series) -> pd.DataFrame:
    """Una fila por cada una de las 162 posiciones de comparacion_p_cap.csv
    (152 REAL + 10 REPLICA_SIN_PAREJA), con bruto_usd real y réplica,
    tasa implícita, tasa del día emparejada, profit_clp estimado de la
    réplica, y flags de pertenencia a las poblaciones (a)/(b)/(c)."""
    df = cmp.copy()

    real_dir = direccion_real(df["real_side"])
    df["real_bruto_usd"] = bruto_usd(df["real_precio_open"], df["real_precio_close"], real_dir)
    df["tasa_implicita"] = tasa_implicita(df["real_profit_clp"].to_numpy(), df["real_bruto_usd"].to_numpy())

    rep_dir = direccion_replica(df["replica_side"])
    df["replica_bruto_usd"] = bruto_usd(df["replica_precio_open"], df["replica_precio_close"], rep_dir)

    replica_close_day = df["replica_t_close_servidor"].astype(str).str.slice(0, 10)
    replica_close_day = replica_close_day.where(df["replica_t_close_servidor"].notna(), np.nan)
    df["replica_close_day"] = replica_close_day
    df["tasa_dia_replica"] = mapear_tasa_dia(df["replica_close_day"], tabla_tasa)
    df["replica_profit_clp_estimado"] = df["replica_bruto_usd"] * df["tasa_dia_replica"]

    tiene_replica = df["replica_side"].notna()
    es_real = df["tipo_fila"] == "REAL"
    es_pareja_real_replica = es_real & tiene_replica  # las 147: REAL con réplica emparejada
    df["poblacion_a_emparejada_evaluable"] = es_pareja_real_replica & (df["excluido_criterio"] == False)  # noqa: E712
    df["poblacion_b_incluida"] = True  # (b) incluye todo, sin excluir nada
    # (c): SOLO pares REAL+réplica (147). Las 10 filas REPLICA_SIN_PAREJA
    # tienen replica_side poblado (es su propio lado), pero NO son un par
    # -- por definición no tienen contraparte real, así que NO cuentan
    # como "matched" aunque tiene_replica sea True para ellas.
    df["poblacion_c_matched"] = es_pareja_real_replica

    df["diff_bruto_usd"] = np.where(es_pareja_real_replica, df["replica_bruto_usd"] - df["real_bruto_usd"], np.nan)

    return df


def _git_sha() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def _lineage() -> dict:
    return {
        "run_id": RUN_ID,
        "area": AREA,
        "experimento": EXPERIMENTO,
        "substrate_id": SUBSTRATE_ID,
        "git_sha": _git_sha(),
        "etapa": ETAPA,
        "generador": GENERADOR,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def construir_resultado(cmp: pd.DataFrame, rep: pd.DataFrame) -> dict:
    real = _preparar_real(cmp)
    matched = _preparar_matched(cmp)
    real_sin_pareja = _preparar_real_sin_pareja(cmp)
    replica_sin_pareja = _preparar_replica_sin_pareja(cmp)
    rep_full = _preparar_replica(rep)

    # ---------- pregunta 1: bruto réplica por posición, por estrategia, global
    q1_global = {"n": int(len(rep_full)), "sum_bruto_usd": float(rep_full["bruto_usd"].sum())}
    q1_por_estrategia = {
        strat: {"n": int(len(g)), "sum_bruto_usd": float(g["bruto_usd"].sum())}
        for strat, g in rep_full.groupby("strategy_id")
    }

    # ---------- pregunta 2: control
    n_bruto_cero = int((real["real_bruto_usd"] == 0).sum())
    stats_tasa = stats_control(real["tasa"])
    tabla_tasa_dia = tasa_por_dia(real, "close_day", "tasa")
    stats_por_dia = {
        day: stats_control(g["tasa"]) for day, g in real.groupby("close_day")
    }

    # ---------- pregunta 3: divergencia primaria (poblacion a) + CLP secundaria
    pop_a = matched[matched["excluido_criterio"] == False]  # noqa: E712
    div_a_usd = divergencia(
        neto_real=float(pop_a["real_bruto_usd"].sum()),
        neto_replica=float(pop_a["replica_bruto_usd"].sum()),
        n_real=int(len(pop_a)), n_replica=int(len(pop_a)),
    )
    div_a_usd_por_estrategia = {}
    for strat, g in pop_a.groupby("strategy_id"):
        div_a_usd_por_estrategia[strat] = divergencia(
            neto_real=float(g["real_bruto_usd"].sum()),
            neto_replica=float(g["replica_bruto_usd"].sum()),
            n_real=int(len(g)), n_replica=int(len(g)),
        )

    pop_a_clp = pop_a.copy()
    pop_a_clp["tasa_dia_replica"] = mapear_tasa_dia(pop_a_clp["replica_close_day"], tabla_tasa_dia)
    pop_a_clp["replica_profit_clp_est"] = pop_a_clp["replica_bruto_usd"] * pop_a_clp["tasa_dia_replica"]
    n_sin_tasa_a = int(pop_a_clp["tasa_dia_replica"].isna().sum())
    div_a_clp = divergencia(
        neto_real=float(pop_a_clp["real_profit_clp"].sum()),
        neto_replica=float(pop_a_clp["replica_profit_clp_est"].sum(skipna=True)),
        n_real=int(len(pop_a_clp)), n_replica=int(pop_a_clp["replica_profit_clp_est"].notna().sum()),
    )
    div_a_clp_por_estrategia = {}
    for strat, g in pop_a_clp.groupby("strategy_id"):
        div_a_clp_por_estrategia[strat] = divergencia(
            neto_real=float(g["real_profit_clp"].sum()),
            neto_replica=float(g["replica_profit_clp_est"].sum(skipna=True)),
            n_real=int(len(g)), n_replica=int(g["replica_profit_clp_est"].notna().sum()),
        )

    # ---------- pregunta 4: sesgo diferencial S6 vs SuperTrend (población a, USD)
    claves = list(div_a_usd_por_estrategia.keys())
    q4 = {"claves": claves}
    if len(claves) == 2:
        d0 = div_a_usd_por_estrategia[claves[0]]
        d1 = div_a_usd_por_estrategia[claves[1]]
        mismo_signo = (d0["diff_abs"] >= 0) == (d1["diff_abs"] >= 0)
        cociente_magnitud = (abs(d1["diff_abs"]) / abs(d0["diff_abs"])) if d0["diff_abs"] != 0 else None
        # normalizado por n (lote es constante 0.67 en ambas estrategias, asi
        # que "por lote" y "por n" difieren solo por ese factor constante)
        diff_por_n_0 = d0["diff_abs"] / d0["n_real"] if d0["n_real"] else None
        diff_por_n_1 = d1["diff_abs"] / d1["n_real"] if d1["n_real"] else None
        diff_por_lote_0 = diff_por_n_0 / VOLUMEN_VIVO if diff_por_n_0 is not None else None
        diff_por_lote_1 = diff_por_n_1 / VOLUMEN_VIVO if diff_por_n_1 is not None else None
        q4.update({
            "mismo_signo": bool(mismo_signo),
            "cociente_magnitud_abs_diff": cociente_magnitud,
            "diff_abs_por_estrategia": {claves[0]: d0["diff_abs"], claves[1]: d1["diff_abs"]},
            "diff_por_posicion": {claves[0]: diff_por_n_0, claves[1]: diff_por_n_1},
            "diff_por_lote": {claves[0]: diff_por_lote_0, claves[1]: diff_por_lote_1},
            "cociente_diff_por_posicion": (
                abs(diff_por_n_1) / abs(diff_por_n_0)
                if diff_por_n_0 not in (None, 0) else None
            ),
        })

    # ---------- pregunta 5: sensibilidad al conjunto evaluado
    # (a) ya calculado arriba (div_a_usd)
    div_b_usd = divergencia(
        neto_real=float(real["real_bruto_usd"].sum()),
        neto_replica=float(rep_full["bruto_usd"].sum()),
        n_real=int(len(real)), n_replica=int(len(rep_full)),
    )
    pop_c = matched  # 147, sin filtrar por excluido_criterio
    div_c_usd = divergencia(
        neto_real=float(pop_c["real_bruto_usd"].sum()),
        neto_replica=float(pop_c["replica_bruto_usd"].sum()),
        n_real=int(len(pop_c)), n_replica=int(len(pop_c)),
    )

    # CLP para (b): usando el mismo metodo de tasa-por-dia sobre los 157 replica
    rep_full_clp = rep_full.copy()
    rep_full_clp["tasa_dia"] = mapear_tasa_dia(rep_full_clp["close_day"], tabla_tasa_dia)
    rep_full_clp["profit_clp_estimado"] = rep_full_clp["bruto_usd"] * rep_full_clp["tasa_dia"]
    n_sin_tasa_b = int(rep_full_clp["tasa_dia"].isna().sum())
    neto_real_clp_152 = float(real["real_profit_clp"].sum())
    div_b_clp = divergencia(
        neto_real=neto_real_clp_152,
        neto_replica=float(rep_full_clp["profit_clp_estimado"].sum(skipna=True)),
        n_real=int(len(real)), n_replica=int(rep_full_clp["profit_clp_estimado"].notna().sum()),
    )

    # 12 excluidos, aparte (nunca fundidos en el neto del criterio)
    excl = cmp[(cmp["tipo_fila"] == "REAL") & (cmp["excluido_criterio"] == True)].copy()  # noqa: E712
    excl_dir = direccion_real(excl["real_side"])
    excl["real_bruto_usd"] = bruto_usd(excl["real_precio_open"], excl["real_precio_close"], excl_dir)
    excl_aparte = {
        "n": int(len(excl)),
        "sum_real_bruto_usd": float(excl["real_bruto_usd"].sum()),
        "sum_real_profit_clp": float(excl["real_profit_clp"].sum()),
        "por_categoria": {
            cat: {
                "n": int(len(g)),
                "sum_real_bruto_usd": float(g["real_bruto_usd"].sum()),
                "sum_real_profit_clp": float(g["real_profit_clp"].sum()),
            }
            for cat, g in excl.groupby("categoria_exclusion")
        },
    }

    # ---------- pregunta 6: descomposición (sobre poblacion b = total sin exclusiones)
    term_replica_sin_pareja = float(replica_sin_pareja["replica_bruto_usd"].sum())
    term_real_sin_pareja = float(real_sin_pareja["real_bruto_usd"].sum())
    term_matched_diff = float((pop_c["replica_bruto_usd"] - pop_c["real_bruto_usd"]).sum())
    descomposicion = descomponer(
        term_replica_sin_pareja=term_replica_sin_pareja,
        term_real_sin_pareja=term_real_sin_pareja,
        term_matched_diff=term_matched_diff,
        diff_total=div_b_usd["diff_abs"],
    )

    # ---------- pregunta 7: no evaluables
    no_evaluables = {
        "real_bruto_usd_cero": n_bruto_cero,
        "real_sin_pareja_replica": {
            "n": int(len(real_sin_pareja)),
            "position_id": [float(x) for x in real_sin_pareja["position_id"].tolist()],
        },
        "replica_sin_pareja_real": {"n": int(len(replica_sin_pareja))},
        "tasa_dia_no_evaluable_poblacion_a": n_sin_tasa_a,
        "tasa_dia_no_evaluable_poblacion_b": n_sin_tasa_b,
        "delta_precio_open_nulo_origen": int(cmp["delta_precio_open"].isna().sum()) - len(
            cmp[(cmp["tipo_fila"] == "REPLICA_SIN_PAREJA")]
        ),
    }

    discrepancia_brief_vs_artefacto = {
        "descripcion": (
            "El brief (prosa, no el artefacto) menciona 137 posiciones emparejadas "
            "('128 de 137', '131 de 137'). El artefacto p_cap_resultado.json "
            "(criterio_de_paso_6_campos.n_emparejadas) dice 135, y recomputado "
            "directamente de comparacion_p_cap.csv (140 evaluables - 5 sin pareja) "
            "da tambien 135. Se usa 135 (gana el artefacto, por instrucción del "
            "propio brief: 'Verifica contra el artefacto, nunca contra lo que yo "
            "te diga')."
        ),
        "brief_dice": 137,
        "artefacto_p_cap_resultado_json": 135,
        "recomputado_de_comparacion_p_cap_csv": int(len(pop_c[pop_c["excluido_criterio"] == False])),  # noqa: E712
    }

    return {
        "lineage": _lineage(),
        "umbrales_pct": {"aceptable": UMBRAL_ACEPTABLE_PCT, "ideal": UMBRAL_IDEAL_PCT},
        "parametros": {"volumen_vivo": VOLUMEN_VIVO, "tamano_contrato": TAMANO_CONTRATO},
        "discrepancia_brief_vs_artefacto_n_emparejadas": discrepancia_brief_vs_artefacto,
        "q1_bruto_replica": {"global": q1_global, "por_estrategia": q1_por_estrategia},
        "q2_control": {
            "n_bruto_usd_cero": n_bruto_cero,
            "tasa_stats_global": stats_tasa,
            "tasa_stats_por_dia": stats_por_dia,
        },
        "q3_divergencia": {
            "usd_poblacion_a_emparejadas_evaluables": div_a_usd,
            "usd_poblacion_a_por_estrategia": div_a_usd_por_estrategia,
            "clp_poblacion_a_emparejadas_evaluables": div_a_clp,
            "clp_poblacion_a_por_estrategia": div_a_clp_por_estrategia,
            "clp_poblacion_b_conexion_con_16146299_81": div_b_clp,
            "neto_real_clp_152_registrado_referencia": 16146299.81,
        },
        "q4_sesgo_diferencial_poblacion_a_usd": q4,
        "q5_sensibilidad_poblaciones": {
            "a_emparejadas_evaluables": div_a_usd,
            "b_todas_sin_excluir": div_b_usd,
            "c_matched_sin_filtrar_criterio": div_c_usd,
            "excluidos_12_aparte": excl_aparte,
        },
        "q6_descomposicion": descomposicion,
        "q7_no_evaluables": no_evaluables,
    }


def escribir_md(resultado: dict, comando: str, fecha: str) -> str:
    L = resultado["lineage"]
    lineas = [
        "# divergencia_neto -- T0.7-M-0",
        "",
        f"Comando: `{comando}`",
        "",
        f"Fecha: {fecha} · git_sha: `{L['git_sha']}` · run_id: `{L['run_id']}`",
        "",
        "REPORT-ONLY. Sin interpretación, sin veredicto. Divergencia situada junto a los "
        f"umbrales {UMBRAL_ACEPTABLE_PCT}% (aceptable) / {UMBRAL_IDEAL_PCT}% (ideal), sin emitirlo.",
        "",
        "## 0 · Discrepancia brief vs artefacto (n emparejadas)",
        "",
        resultado["discrepancia_brief_vs_artefacto_n_emparejadas"]["descripcion"],
        "",
        f"- brief (prosa): {resultado['discrepancia_brief_vs_artefacto_n_emparejadas']['brief_dice']}",
        f"- artefacto p_cap_resultado.json: {resultado['discrepancia_brief_vs_artefacto_n_emparejadas']['artefacto_p_cap_resultado_json']}",
        f"- recomputado de comparacion_p_cap.csv: {resultado['discrepancia_brief_vs_artefacto_n_emparejadas']['recomputado_de_comparacion_p_cap_csv']}",
        "",
        "## 1 · Resultado monetario de cada posición de la réplica",
        "",
        f"Global: n={resultado['q1_bruto_replica']['global']['n']}, "
        f"sum_bruto_usd={resultado['q1_bruto_replica']['global']['sum_bruto_usd']:.2f}",
        "",
        "| estrategia | n | sum_bruto_usd |",
        "|---|---|---|",
    ]
    for strat, d in resultado["q1_bruto_replica"]["por_estrategia"].items():
        lineas.append(f"| {strat} | {d['n']} | {d['sum_bruto_usd']:.2f} |")
    lineas += [
        "",
        "Detalle posición a posición: ver `divergencia_neto.csv`, columna `bruto_usd` "
        "(filas del fichero réplica, 157) y `replica_bruto_usd` (vista unida con el real, "
        "en `divergencia_neto.csv` de comparacion_p_cap).",
        "",
        "## 2 · CONTROL de la fórmula (antes de creer nada del punto 1)",
        "",
        f"n_bruto_usd_cero (división imposible, excluidas): {resultado['q2_control']['n_bruto_usd_cero']}",
        "",
        "Tasa implícita global (152 reales evaluables):",
        "",
        f"n={resultado['q2_control']['tasa_stats_global']['n']}, "
        f"p10={resultado['q2_control']['tasa_stats_global']['p10']:.4f}, "
        f"p50={resultado['q2_control']['tasa_stats_global']['p50']:.4f}, "
        f"p90={resultado['q2_control']['tasa_stats_global']['p90']:.4f}, "
        f"min={resultado['q2_control']['tasa_stats_global']['min']:.4f}, "
        f"max={resultado['q2_control']['tasa_stats_global']['max']:.4f}, "
        f"dispersion_relativa={resultado['q2_control']['tasa_stats_global']['dispersion_relativa']:.6f}",
        "",
        "Tasa implícita por día de cierre (dispersión relativa dentro de cada día):",
        "",
        "| día | n | p50 | dispersion_relativa |",
        "|---|---|---|---|",
    ]
    for day, d in sorted(resultado["q2_control"]["tasa_stats_por_dia"].items()):
        dr = "n/e" if d["dispersion_relativa"] is None else f"{d['dispersion_relativa']:.6f}"
        p50 = "n/e" if d["p50"] is None else f"{d['p50']:.4f}"
        lineas.append(f"| {day} | {d['n']} | {p50} | {dr} |")

    lineas += [
        "",
        "## 3 · La divergencia de neto (cifra pedida)",
        "",
        "### Primaria en dólares, población (a) = emparejadas evaluables (n=135, ver §0)",
        "",
    ]
    da = resultado["q3_divergencia"]["usd_poblacion_a_emparejadas_evaluables"]
    lineas.append(
        f"neto_real_usd={da['neto_real']:.4f}, neto_replica_usd={da['neto_replica']:.4f}, "
        f"diff_abs={da['diff_abs']:.4f}, divergencia_pct={da['divergencia_pct']:.6f} "
        f"(n_real={da['n_real']}, n_replica={da['n_replica']})"
    )
    lineas += [
        "",
        f"Umbrales: aceptable ≤{UMBRAL_ACEPTABLE_PCT}%, ideal ≤{UMBRAL_IDEAL_PCT}%. Sin veredicto.",
        "",
        "Por estrategia:",
        "",
        "| estrategia | neto_real_usd | neto_replica_usd | diff_abs | divergencia_pct | n |",
        "|---|---|---|---|---|---|",
    ]
    for strat, d in resultado["q3_divergencia"]["usd_poblacion_a_por_estrategia"].items():
        lineas.append(
            f"| {strat} | {d['neto_real']:.4f} | {d['neto_replica']:.4f} | {d['diff_abs']:.4f} | "
            f"{d['divergencia_pct']:.6f} | {d['n_real']} |"
        )
    lineas += [
        "",
        "### Secundaria en pesos (población a), tasa emparejada por día de cierre de la réplica",
        "",
    ]
    dac = resultado["q3_divergencia"]["clp_poblacion_a_emparejadas_evaluables"]
    lineas.append(
        f"neto_real_clp={dac['neto_real']:.2f}, neto_replica_clp_estimado={dac['neto_replica']:.2f}, "
        f"diff_abs={dac['diff_abs']:.2f}, divergencia_pct={dac['divergencia_pct']:.6f} "
        f"(n_real={dac['n_real']}, n_replica_evaluable={dac['n_replica']})"
    )
    lineas += [
        "",
        "Por estrategia (CLP, población a):",
        "",
        "| estrategia | neto_real_clp | neto_replica_clp_est | diff_abs | divergencia_pct |",
        "|---|---|---|---|---|",
    ]
    for strat, d in resultado["q3_divergencia"]["clp_poblacion_a_por_estrategia"].items():
        lineas.append(
            f"| {strat} | {d['neto_real']:.2f} | {d['neto_replica']:.2f} | {d['diff_abs']:.2f} | "
            f"{d['divergencia_pct']:.6f} |"
        )
    dbc = resultado["q3_divergencia"]["clp_poblacion_b_conexion_con_16146299_81"]
    lineas += [
        "",
        "### Conexión con el neto real registrado (16.146.299,81 CLP), población (b) = 152 real / 157 réplica, sin excluir nada",
        "",
        f"neto_real_clp (152, recomputado) = {dbc['neto_real']:.2f} "
        f"(registrado en p_cap_resultado.json: 16146299.81)",
        f"neto_replica_clp_estimado (157, tasa por día) = {dbc['neto_replica']:.2f} "
        f"(n_evaluable={dbc['n_replica']}/{resultado['q1_bruto_replica']['global']['n']})",
        f"diff_abs = {dbc['diff_abs']:.2f}, divergencia_pct = {dbc['divergencia_pct']:.6f}",
        "",
        "## 4 · ¿El sesgo es diferencial? (población a, USD)",
        "",
    ]
    q4 = resultado["q4_sesgo_diferencial_poblacion_a_usd"]
    if "mismo_signo" in q4:
        lineas.append(f"claves: {q4['claves']}")
        lineas.append(f"mismo_signo: {q4['mismo_signo']}")
        lineas.append(f"cociente_magnitud_abs_diff (diff2/diff1): {q4['cociente_magnitud_abs_diff']}")
        lineas.append(f"diff_abs_por_estrategia: {q4['diff_abs_por_estrategia']}")
        lineas.append(f"diff_por_posicion (diff_abs/n): {q4['diff_por_posicion']}")
        lineas.append(f"diff_por_lote (diff_por_posicion/{VOLUMEN_VIVO}): {q4['diff_por_lote']}")
        lineas.append(f"cociente_diff_por_posicion: {q4['cociente_diff_por_posicion']}")
    lineas += [
        "",
        "## 5 · Sensibilidad al conjunto evaluado",
        "",
        "| población | n_real | n_replica | neto_real_usd | neto_replica_usd | diff_abs | divergencia_pct |",
        "|---|---|---|---|---|---|---|",
    ]
    for etiqueta, key in [
        ("(a) emparejadas evaluables", "a_emparejadas_evaluables"),
        ("(b) todas sin excluir", "b_todas_sin_excluir"),
        ("(c) matched sin filtrar criterio", "c_matched_sin_filtrar_criterio"),
    ]:
        d = resultado["q5_sensibilidad_poblaciones"][key]
        lineas.append(
            f"| {etiqueta} | {d['n_real']} | {d['n_replica']} | {d['neto_real']:.4f} | "
            f"{d['neto_replica']:.4f} | {d['diff_abs']:.4f} | {d['divergencia_pct']:.6f} |"
        )
    excl = resultado["q5_sensibilidad_poblaciones"]["excluidos_12_aparte"]
    lineas += [
        "",
        f"Excluidos del criterio (12, aparte, nunca fundidos en el neto): n={excl['n']}, "
        f"sum_real_bruto_usd={excl['sum_real_bruto_usd']:.2f}, "
        f"sum_real_profit_clp={excl['sum_real_profit_clp']:.2f}",
        "",
        "| categoría | n | sum_real_bruto_usd | sum_real_profit_clp |",
        "|---|---|---|---|",
    ]
    for cat, d in excl["por_categoria"].items():
        lineas.append(f"| {cat} | {d['n']} | {d['sum_real_bruto_usd']:.2f} | {d['sum_real_profit_clp']:.2f} |")

    desc = resultado["q6_descomposicion"]
    lineas += [
        "",
        "## 6 · Descomposición de la divergencia (sobre población (b), USD)",
        "",
        f"term_replica_sin_pareja (10 posiciones) = {desc['term_replica_sin_pareja']:.4f}",
        f"term_real_sin_pareja_neg (-1 × 5 posiciones) = {desc['term_real_sin_pareja_neg']:.4f}",
        f"term_matched_diff (147 posiciones, réplica-real) = {desc['term_matched_diff']:.4f}",
        f"suma_terminos = {desc['suma_terminos']:.6f}",
        f"diff_total (población b) = {desc['diff_total']:.6f}",
        f"residuo = {desc['residuo']:.9f} ({desc['residuo']:.3e}, ruido de punto flotante si es de este orden)",
        "",
        "## 7 · No evaluables",
        "",
    ]
    ne = resultado["q7_no_evaluables"]
    lineas += [
        f"- real_bruto_usd == 0 (división imposible para tasa implícita): {ne['real_bruto_usd_cero']}",
        f"- reales sin réplica (fuera de comparación pareada): {ne['real_sin_pareja_replica']['n']} "
        f"(position_id: {ne['real_sin_pareja_replica']['position_id']})",
        f"- réplica sin real (fuera de comparación pareada): {ne['replica_sin_pareja_real']['n']}",
        f"- tasa del día no evaluable, población (a): {ne['tasa_dia_no_evaluable_poblacion_a']}",
        f"- tasa del día no evaluable, población (b): {ne['tasa_dia_no_evaluable_poblacion_b']}",
        f"- delta_precio_open nulo desde el origen (propagado, no relleno): {ne['delta_precio_open_nulo_origen']}",
        "",
    ]
    return "\n".join(lineas)


def main() -> None:
    rep, cmp = _cargar_datos()

    resultado = construir_resultado(cmp, rep)

    real = _preparar_real(cmp)
    tabla_tasa_dia = tasa_por_dia(real, "close_day", "tasa")
    df_csv = construir_csv_posicion_a_posicion(cmp, rep, tabla_tasa_dia)

    RUTA_SALIDA_DIR.mkdir(parents=True, exist_ok=True)

    # respaldo si ya existe algo (resiliencia de sesión)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for ruta in (RUTA_CSV, RUTA_JSON, RUTA_MD):
        if ruta.exists():
            ruta.rename(ruta.with_name(f"{ruta.name}.bak-{ts}"))

    df_csv.to_csv(RUTA_CSV, index=False)

    with open(RUTA_JSON, "w", encoding="utf-8") as fh:
        json.dump(resultado, fh, indent=2, ensure_ascii=False, allow_nan=False, default=lambda o: None)

    comando = "python scripts/analysis/realtick_bt/faulty/divergencia_neto.py"
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md = escribir_md(resultado, comando, fecha)
    with open(RUTA_MD, "w", encoding="utf-8") as fh:
        fh.write(md)

    print(f"filas CSV: {len(df_csv)}")
    print(f"CSV: {RUTA_CSV}")
    print(f"JSON: {RUTA_JSON}")
    print(f"MD: {RUTA_MD}")


if __name__ == "__main__":
    main()
