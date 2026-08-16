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

import argparse
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

# --- T0.7-M-H (D-54): coste de deslizamiento modelado, flag apagado por defecto
RUTA_FILL_VS_COTIZACION = RUTA_SALIDA_DIR / "fill_vs_cotizacion.csv"
RUTA_CSV_DESLIZ = RUTA_SALIDA_DIR / "divergencia_neto_con_deslizamiento.csv"
RUTA_JSON_DESLIZ = RUTA_SALIDA_DIR / "divergencia_neto_con_deslizamiento.json"
RUTA_MD_DESLIZ = RUTA_SALIDA_DIR / "divergencia_neto_con_deslizamiento.md"

RUN_ID_DESLIZ = "T0.7-M-H-DIVNETO-DESLIZ-0001"
EXPERIMENTO_DESLIZ = "T0.7-M-H-divergencia-neto-con-deslizamiento"
SUBSTRATE_ID_DESLIZ = (
    "posiciones_replica.csv(reloj_reconstruido) + comparacion_p_cap.csv + fill_vs_cotizacion.csv"
)
GENERADOR_DESLIZ = "scripts/analysis/realtick_bt/faulty/divergencia_neto.py --coste-deslizamiento"

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


# ================================================== T0.7-M-H (D-54): coste
# ---------------------------------------------------------------- calibración
def calibrar_coste_deslizamiento(ruta_fill: Path = RUTA_FILL_VS_COTIZACION) -> dict:
    """Calibra el coste de deslizamiento desde `fill_vs_cotizacion.csv`
    (D-54, Bloque 1 del brief T0.7-M-H). Modelo:
      deslizamiento(spread) = mediana|delta_vigente|(cierres por stop, ese
      spread) - mediana|delta_vigente|(cierres a mercado).
    `delta_vigente` = precio_real - cotización vigente (última con t<=T, lado
    BUY/SELL correspondiente) ya viene calculado en `fill_vs_cotizacion.py`
    (mismo campo, sin recomputar la cotización). "Cierres por stop" =
    `reason_name == 'SL'` (119 filas). "Cierres a mercado" =
    `reason_name == 'EXPERT'` (21 filas, ejecutor cerrando a mercado -- ver
    brief §0). Todo número lo calcula este código, no se copian cifras del
    brief ni de D-54."""
    df = pd.read_csv(ruta_fill)
    closes = df[df["evento"] == "CLOSE"].copy()
    closes["spread_r"] = closes["spread_tick_vigente"].round(2)

    stops = closes[closes["reason_name"] == "SL"]
    mercado = closes[closes["reason_name"] == "EXPERT"]

    n_stop_spread_no_recuperable = int(stops["spread_tick_vigente"].isna().sum())

    stats_por_spread = {}
    for spread, g in stops.groupby("spread_r"):
        vals = g["delta_vigente"].dropna().abs()
        stats_por_spread[float(spread)] = {
            "n": int(vals.size),
            "mediana_abs_delta_vigente": float(vals.median()) if vals.size else None,
        }

    vals_mercado = mercado["delta_vigente"].dropna().abs()
    mediana_abs_delta_mercado = float(vals_mercado.median()) if vals_mercado.size else None
    n_mercado = int(vals_mercado.size)
    n_mercado_no_evaluable = int(len(mercado) - vals_mercado.size)

    coste_por_spread = {
        spread: (stats["mediana_abs_delta_vigente"] - mediana_abs_delta_mercado)
        for spread, stats in stats_por_spread.items()
        if stats["mediana_abs_delta_vigente"] is not None and mediana_abs_delta_mercado is not None
    }

    # spread dominante entre los cierres por stop (recuperable ahí; NO
    # recuperable por posición ni en rep ni en cmp -- ver Normas específicas
    # del brief: "el spread por operación no se registra hoy"). Se usa como
    # modo de fallback para aplicar el coste a la réplica.
    conteo_spread_stops = stops["spread_r"].value_counts(dropna=True)
    spread_dominante = float(conteo_spread_stops.idxmax()) if len(conteo_spread_stops) else None
    coste_aplicado_replica = coste_por_spread.get(spread_dominante)

    d0 = stats_por_spread.get(0.5, {})
    d1 = stats_por_spread.get(0.6, {})
    discrepancia_vs_d54 = {
        "d54_mediana_stop_spread050": 0.255,
        "recalculo_mediana_stop_spread050": d0.get("mediana_abs_delta_vigente"),
        "d54_n_stop_spread050": 110,
        "recalculo_n_stop_spread050": d0.get("n"),
        "d54_mediana_stop_spread060": 0.270,
        "recalculo_mediana_stop_spread060": d1.get("mediana_abs_delta_vigente"),
        "d54_n_stop_spread060": 9,
        "recalculo_n_stop_spread060": d1.get("n"),
        "d54_mediana_mercado": 0.053,
        "recalculo_mediana_mercado": mediana_abs_delta_mercado,
        "d54_n_mercado": 21,
        "recalculo_n_mercado": n_mercado,
        "d54_coste_spread050": 0.202,
        "recalculo_coste_spread050": coste_por_spread.get(0.5),
        "d54_coste_spread060": 0.217,
        "recalculo_coste_spread060": coste_por_spread.get(0.6),
        "nota_mediana_mercado": (
            "mediana|delta_vigente| en reason_name=='EXPERT' (n=21) recalculada por este "
            "código = 0.03 (redondeado), NO 0.053. La MEDIA aritmética de la misma serie SI "
            "da 0.0529 (~0.053) -- coincide con la cifra citada por D-54, que por tanto parece "
            "una media, no una mediana, pese a que el propio texto de D-54 dice 'mediana'. El "
            "Bloque 1 del brief especifica la fórmula con 'mediana', así que gana la mediana "
            "recalculada (0.03) según instrucción explícita del brief ('si no coinciden, gana "
            "tu recálculo')."
        ),
    }

    return {
        "columna_delta": "delta_vigente (fill_vs_cotizacion.csv)",
        "definicion_stop": "reason_name == 'SL' (cierres por stop server-side, n=119)",
        "definicion_mercado": "reason_name == 'EXPERT' (cierres a mercado del ejecutor, n=21)",
        "stats_por_spread_stop": stats_por_spread,
        "n_stop_spread_no_recuperable_en_fill_vs_cotizacion": n_stop_spread_no_recuperable,
        "mediana_abs_delta_mercado": mediana_abs_delta_mercado,
        "n_mercado_evaluable": n_mercado,
        "n_mercado_no_evaluable": n_mercado_no_evaluable,
        "coste_por_spread": coste_por_spread,
        "conteo_spread_entre_stops": {float(k): int(v) for k, v in conteo_spread_stops.items()},
        "spread_dominante_modo": spread_dominante,
        "coste_aplicado_replica": coste_aplicado_replica,
        "razon_modo_dominante": (
            "El spread por operación no se registra ni en posiciones_replica.csv ni en "
            "comparacion_p_cap.csv (columnas verificadas, ninguna contiene 'spread'); no es "
            "recuperable por posición para NINGUNA de las filas de la réplica. Se usa el modo "
            "dominante entre los propios cierres por stop de fill_vs_cotizacion.csv "
            f"({spread_dominante}) para el 100% de los cierres por stop de la réplica."
        ),
        "discrepancia_vs_d54": discrepancia_vs_d54,
    }


# ------------------------------------------------------------- aplicación
def _direccion_generica(side_series: pd.Series, mapa: dict) -> np.ndarray:
    return pd.Series(side_series).map(mapa).astype(float).to_numpy()


def aplicar_deslizamiento_precio_close(
    precio_close: np.ndarray, direccion: np.ndarray, es_stop: np.ndarray, coste: float
) -> np.ndarray:
    """Aplica el coste EN CONTRA de la posición, sólo donde `es_stop` es
    True (brief §Bloque 2): LONG (direccion>0) -> precio_close - coste (el
    cierre más bajo posible); SHORT (direccion<0) -> precio_close + coste
    (el cierre más alto posible). Vectorizado; filas con es_stop=False no se
    tocan."""
    precio_close = np.asarray(precio_close, dtype=float)
    direccion = np.asarray(direccion, dtype=float)
    es_stop = np.asarray(es_stop, dtype=bool)
    ajuste = np.where(direccion > 0, -coste, coste)
    return np.where(es_stop, precio_close + ajuste, precio_close)


def aplicar_coste_a_rep(rep: pd.DataFrame, coste: float, solo_stops: bool = True) -> pd.DataFrame:
    """Copia de `rep` (posiciones_replica.csv, 157 filas) con `precio_close`
    ajustado. `solo_stops=True` (comportamiento del Bloque 2): sólo
    motivo_cierre=='SL'. `solo_stops=False` (control del Bloque 3): TODAS
    las filas, para medir cuánto se movería el sesgo si el coste no fuera
    exclusivo de los stops."""
    rep2 = rep.copy()
    direccion = _direccion_generica(rep2["side"], {"L": 1.0, "S": -1.0})
    if solo_stops:
        es_stop = (rep2["motivo_cierre"] == "SL").to_numpy()
    else:
        es_stop = np.ones(len(rep2), dtype=bool)
    rep2["precio_close"] = aplicar_deslizamiento_precio_close(
        rep2["precio_close"].to_numpy(), direccion, es_stop, coste
    )
    return rep2


def aplicar_coste_a_cmp_replica(cmp: pd.DataFrame, coste: float, solo_stops: bool = True) -> pd.DataFrame:
    """Copia de `cmp` (comparacion_p_cap.csv) con `replica_precio_close`
    ajustado (columna del lado RÉPLICA únicamente; `real_precio_close`
    NUNCA se toca -- brief: 'los cierres a mercado no se tocan' y el coste
    es sólo de la réplica). `solo_stops` igual que en `aplicar_coste_a_rep`."""
    cmp2 = cmp.copy()
    tiene_replica = cmp2["replica_side"].notna()
    direccion = _direccion_generica(cmp2["replica_side"], {"L": 1.0, "S": -1.0})
    if solo_stops:
        es_stop = (cmp2["replica_motivo_cierre"] == "SL").to_numpy() & tiene_replica.to_numpy()
    else:
        es_stop = tiene_replica.to_numpy()
    nuevo = aplicar_deslizamiento_precio_close(
        cmp2["replica_precio_close"].to_numpy(), direccion, es_stop, coste
    )
    # sólo sobreescribe donde había réplica; NaN se preserva donde no la hay
    cmp2["replica_precio_close"] = np.where(tiene_replica.to_numpy(), nuevo, cmp2["replica_precio_close"])
    return cmp2


def frecuencia_stops_por_estrategia(pop_a: pd.DataFrame) -> dict:
    """Bloque 3, punto 3: nº y % de cierres por stop sobre el total de cada
    estrategia, en la realidad (`real_reason_name=='SL'`) y en la réplica
    (`replica_motivo_cierre=='SL'`), más USD afectados (bruto_usd, SIN
    ajuste de deslizamiento -- son los USD que la posición ya tenía antes de
    aplicar ningún coste, para medir el peso del mecanismo, no su efecto)."""
    salida = {}
    for strat, g in pop_a.groupby("strategy_id"):
        n = int(len(g))
        real_stop = g["real_reason_name"] == "SL"
        replica_stop = g["replica_motivo_cierre"] == "SL"
        salida[strat] = {
            "n_total": n,
            "real": {
                "n_stop": int(real_stop.sum()),
                "pct_stop": (float(real_stop.sum()) / n * 100.0) if n else None,
                "usd_stop": float(g.loc[real_stop, "real_bruto_usd"].sum()),
                "usd_no_stop": float(g.loc[~real_stop, "real_bruto_usd"].sum()),
            },
            "replica": {
                "n_stop": int(replica_stop.sum()),
                "pct_stop": (float(replica_stop.sum()) / n * 100.0) if n else None,
                "usd_stop": float(g.loc[replica_stop, "replica_bruto_usd"].sum()),
                "usd_no_stop": float(g.loc[~replica_stop, "replica_bruto_usd"].sum()),
            },
        }
    return salida


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


def escribir_md_deslizamiento(salida: dict, comando: str, fecha: str) -> str:
    L = salida["lineage"]
    cal = salida["calibracion_deslizamiento"]
    tres = salida["tres_numeros_bloque_3"]
    ctrl = salida["control_coste_uniforme_todas_posiciones"]
    lineas = [
        "# divergencia_neto_con_deslizamiento -- T0.7-M-H (D-54)",
        "",
        f"Comando: `{comando}`",
        "",
        f"Fecha: {fecha} · git_sha: `{L['git_sha']}` · run_id: `{L['run_id']}`",
        "",
        "REPORT-ONLY. Sin interpretación, sin veredicto. `T0.7-M-A` (precio de cierre contra el "
        "nivel del stop) queda diferida por D-54 y NO se corre aquí: parte del desvío medido en "
        "`fill_vs_cotizacion.py:69-77` es artefacto del método (la referencia es la cotización al "
        "PRINCIPIO del segundo, y un stop se dispara durante un movimiento en contra), no dinero "
        "perdido.",
        "",
        "## 1 · Calibración del coste (Bloque 1)",
        "",
        f"Columna usada: `{cal['columna_delta']}`. Stop: {cal['definicion_stop']}. "
        f"Mercado: {cal['definicion_mercado']}.",
        "",
        "| spread | n (stop) | mediana|delta| (stop) | coste = stop - mercado |",
        "|---|---|---|---|",
    ]
    for spread, stats in sorted(cal["stats_por_spread_stop"].items()):
        coste_sp = cal["coste_por_spread"].get(spread)
        coste_str = "n/e" if coste_sp is None else f"{coste_sp:.6f}"
        med_str = "n/e" if stats["mediana_abs_delta_vigente"] is None else f"{stats['mediana_abs_delta_vigente']:.6f}"
        lineas.append(f"| {spread} | {stats['n']} | {med_str} | {coste_str} |")
    lineas += [
        "",
        f"mediana|delta| (mercado, n={cal['n_mercado_evaluable']}): {cal['mediana_abs_delta_mercado']:.6f}",
        "",
        f"spread dominante (fallback, spread no recuperable por posición en réplica): "
        f"{cal['spread_dominante_modo']}",
        f"coste aplicado a la réplica: {cal['coste_aplicado_replica']:.6f}",
        "",
        cal["razon_modo_dominante"],
        "",
        "### Discrepancia vs D-54",
        "",
        cal["discrepancia_vs_d54"]["nota_mediana_mercado"],
        "",
        "| cifra | D-54 | recálculo (este código) |",
        "|---|---|---|",
    ]
    dvd = cal["discrepancia_vs_d54"]
    pares = [
        ("mediana stop spread 0.50", "d54_mediana_stop_spread050", "recalculo_mediana_stop_spread050"),
        ("n stop spread 0.50", "d54_n_stop_spread050", "recalculo_n_stop_spread050"),
        ("mediana stop spread 0.60", "d54_mediana_stop_spread060", "recalculo_mediana_stop_spread060"),
        ("n stop spread 0.60", "d54_n_stop_spread060", "recalculo_n_stop_spread060"),
        ("mediana mercado", "d54_mediana_mercado", "recalculo_mediana_mercado"),
        ("n mercado", "d54_n_mercado", "recalculo_n_mercado"),
        ("coste spread 0.50", "d54_coste_spread050", "recalculo_coste_spread050"),
        ("coste spread 0.60", "d54_coste_spread060", "recalculo_coste_spread060"),
    ]
    for etiqueta, k_d54, k_rec in pares:
        lineas.append(f"| {etiqueta} | {dvd[k_d54]} | {dvd[k_rec]} |")

    lineas += [
        "",
        "## 2 · Los tres números del Bloque 3",
        "",
        "### (1) Divergencia global (población a, USD)",
        "",
        f"antes: {tres['1_divergencia_global_pct']['antes']:.6f} %",
        f"después (coste sólo en stops): {tres['1_divergencia_global_pct']['despues_stops_only']:.6f} %",
        "",
        "### (2) Sesgo por posición por estrategia (diff_abs / n, población a, USD)",
        "",
        f"antes: {tres['2_sesgo_por_posicion_por_estrategia']['antes']}",
        f"después (coste sólo en stops): {tres['2_sesgo_por_posicion_por_estrategia']['despues_stops_only']}",
        f"cociente antes: {tres['2_sesgo_por_posicion_por_estrategia']['cociente_antes']}",
        f"cociente después (stops only): {tres['2_sesgo_por_posicion_por_estrategia']['cociente_despues_stops_only']}",
        "",
        "### (3) Frecuencia y peso de los cierres por stop por estrategia (población a)",
        "",
        "| estrategia | n_total | real n_stop | real % | real USD stop | réplica n_stop | réplica % | réplica USD stop |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for strat, d in tres["3_frecuencia_y_peso_stops_por_estrategia"].items():
        r, p = d["real"], d["replica"]
        lineas.append(
            f"| {strat} | {d['n_total']} | {r['n_stop']} | {r['pct_stop']:.2f} | {r['usd_stop']:.2f} | "
            f"{p['n_stop']} | {p['pct_stop']:.2f} | {p['usd_stop']:.2f} |"
        )

    lineas += [
        "",
        "## 3 · Control -- coste uniforme a TODAS las posiciones de la réplica",
        "",
        ctrl["descripcion"],
        "",
        f"cociente antes (sin coste): {ctrl['cociente_antes']}",
        f"cociente después, coste sólo en stops: {ctrl['cociente_stops_only']}",
        f"cociente después, coste uniforme (control): {ctrl['cociente_uniforme']}",
        f"diff_por_posicion, coste uniforme: {ctrl['diff_por_posicion_uniforme']}",
        "",
    ]
    return "\n".join(lineas)


def _ejecutar_con_deslizamiento(cmp: pd.DataFrame, rep: pd.DataFrame, resultado_base: dict) -> None:
    """T0.7-M-H (D-54), Bloques 1-3. Sólo se invoca con `--coste-deslizamiento`.
    NUNCA toca `rep`/`cmp` originales (trabaja sobre copias vía
    `aplicar_coste_a_rep` / `aplicar_coste_a_cmp_replica`) ni los artefactos
    `divergencia_neto.*` (escribe únicamente en `*_con_deslizamiento.*`)."""
    calibracion = calibrar_coste_deslizamiento()
    coste = calibracion["coste_aplicado_replica"]
    if coste is None:
        raise RuntimeError(
            "calibrar_coste_deslizamiento() no produjo un coste aplicable (spread dominante o "
            "medianas no evaluables) -- no se puede continuar con --coste-deslizamiento."
        )

    # Bloque 2: coste sólo en los cierres por stop de la réplica
    rep2 = aplicar_coste_a_rep(rep, coste, solo_stops=True)
    cmp2 = aplicar_coste_a_cmp_replica(cmp, coste, solo_stops=True)
    resultado2 = construir_resultado(cmp2, rep2)
    real2 = _preparar_real(cmp2)
    tabla_tasa_dia2 = tasa_por_dia(real2, "close_day", "tasa")
    df_csv2 = construir_csv_posicion_a_posicion(cmp2, rep2, tabla_tasa_dia2)

    # Bloque 3, control: mismo coste, aplicado a TODAS las posiciones réplica
    rep3 = aplicar_coste_a_rep(rep, coste, solo_stops=False)
    cmp3 = aplicar_coste_a_cmp_replica(cmp, coste, solo_stops=False)
    resultado3 = construir_resultado(cmp3, rep3)

    # Bloque 3, punto 3: frecuencia/peso de los stops (población a, sin ajustar)
    matched = _preparar_matched(cmp)
    pop_a = matched[matched["excluido_criterio"] == False]  # noqa: E712
    frecuencia = frecuencia_stops_por_estrategia(pop_a)

    lineage2 = {
        "run_id": RUN_ID_DESLIZ,
        "area": AREA,
        "experimento": EXPERIMENTO_DESLIZ,
        "substrate_id": SUBSTRATE_ID_DESLIZ,
        "git_sha": _git_sha(),
        "etapa": ETAPA,
        "generador": GENERADOR_DESLIZ,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    q3a = resultado_base["q3_divergencia"]["usd_poblacion_a_emparejadas_evaluables"]
    q4a = resultado_base["q4_sesgo_diferencial_poblacion_a_usd"]
    q3d = resultado2["q3_divergencia"]["usd_poblacion_a_emparejadas_evaluables"]
    q4d = resultado2["q4_sesgo_diferencial_poblacion_a_usd"]
    q4u = resultado3["q4_sesgo_diferencial_poblacion_a_usd"]

    tres_numeros = {
        "1_divergencia_global_pct": {
            "antes": q3a["divergencia_pct"],
            "despues_stops_only": q3d["divergencia_pct"],
        },
        "2_sesgo_por_posicion_por_estrategia": {
            "antes": q4a.get("diff_por_posicion"),
            "despues_stops_only": q4d.get("diff_por_posicion"),
            "cociente_antes": q4a.get("cociente_diff_por_posicion"),
            "cociente_despues_stops_only": q4d.get("cociente_diff_por_posicion"),
        },
        "3_frecuencia_y_peso_stops_por_estrategia": frecuencia,
    }
    control = {
        "descripcion": (
            "coste aplicado a TODAS las posiciones de la réplica por igual (no sólo a los "
            "cierres por stop), para separar 'el coste importa' de 'el coste importa de forma "
            "asimétrica entre estrategias'."
        ),
        "cociente_antes": q4a.get("cociente_diff_por_posicion"),
        "cociente_stops_only": q4d.get("cociente_diff_por_posicion"),
        "cociente_uniforme": q4u.get("cociente_diff_por_posicion"),
        "diff_por_posicion_uniforme": q4u.get("diff_por_posicion"),
    }

    salida = {
        "lineage": lineage2,
        "calibracion_deslizamiento": calibracion,
        "tres_numeros_bloque_3": tres_numeros,
        "control_coste_uniforme_todas_posiciones": control,
        "resultado_completo_despues_stops_only": resultado2,
        "resultado_completo_control_uniforme": resultado3,
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for ruta in (RUTA_CSV_DESLIZ, RUTA_JSON_DESLIZ, RUTA_MD_DESLIZ):
        if ruta.exists():
            ruta.rename(ruta.with_name(f"{ruta.name}.bak-{ts}"))

    df_csv2.to_csv(RUTA_CSV_DESLIZ, index=False)

    with open(RUTA_JSON_DESLIZ, "w", encoding="utf-8") as fh:
        json.dump(salida, fh, indent=2, ensure_ascii=False, allow_nan=False, default=lambda o: None)

    comando2 = "python scripts/analysis/realtick_bt/faulty/divergencia_neto.py --coste-deslizamiento"
    fecha2 = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md2 = escribir_md_deslizamiento(salida, comando2, fecha2)
    with open(RUTA_MD_DESLIZ, "w", encoding="utf-8") as fh:
        fh.write(md2)

    print(f"[deslizamiento] coste aplicado (spread {calibracion['spread_dominante_modo']}): {coste:.6f}")
    print(f"[deslizamiento] filas CSV: {len(df_csv2)}")
    print(f"[deslizamiento] CSV: {RUTA_CSV_DESLIZ}")
    print(f"[deslizamiento] JSON: {RUTA_JSON_DESLIZ}")
    print(f"[deslizamiento] MD: {RUTA_MD_DESLIZ}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coste-deslizamiento",
        action="store_true",
        default=False,
        help=(
            "T0.7-M-H (D-54): calibra y aplica el coste de deslizamiento a los cierres por stop "
            "de la réplica; escribe artefactos NUEVOS "
            "divergencia_neto_con_deslizamiento.{csv,json,md}. Apagado por defecto -- sin este "
            "flag el script reproduce exactamente el comportamiento anterior."
        ),
    )
    args = parser.parse_args()

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

    if args.coste_deslizamiento:
        _ejecutar_con_deslizamiento(cmp, rep, resultado)


if __name__ == "__main__":
    main()
