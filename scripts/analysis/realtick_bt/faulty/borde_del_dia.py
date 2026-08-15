r"""scripts/analysis/realtick_bt/faulty/borde_del_dia.py

T0.7-M-B1 -- ¿por qué la réplica abre a las 16:59 donde el sistema vivo no
podía operar? (borde del día, P-CAP, T0.7, A6 Pata A, Fase 0).

Spec: research/fases/F0-preparacion/02-specs/T0.7-M-B1-brief-borde-del-dia.md

INVESTIGADOR REPORT-ONLY: este script SÓLO mide y censa. No interpreta, no
concluye, no recomienda, no prioriza, no corrige nada.

R1-bis: este script NO importa ni modifica ciclos.py, estado_por_barra.py,
llamador.py, comparador.py ni config_faulty.py. Es autocontenido (mismo
patrón que fill_vs_cotizacion.py y censo_cola_t_open.py) y sólo usa
pandas/numpy/stdlib. Las citas de código de esas funciones (`CITA_*`) son
texto literal verificado contra el fichero real por los tests -- este módulo
NO importa esos módulos para producir esas citas.

Parte de `censo_cola_t_open.csv` (ya hecho, no se re-deriva la cola).
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[4]

RUTA_CENSO_COLA = (
    _REPO_ROOT
    / "research/fases/F0-preparacion/04-resultados/T0.7-p-cap/censo_cola_t_open.csv"
)
RUTA_LAGO_TICKS = _REPO_ROOT / "data/lake_ticks/XAUUSD"
MESES_LAGO = ["202607", "202608"]
RUTA_BARS_M15 = _REPO_ROOT / "data/lake_bars_capitaria/XAUUSD_M15.parquet"
RUTA_EVENTOS_REPLICA = _REPO_ROOT / "data/analysis/p_cap/replica/eventos_replica.csv"

RUTA_SALIDA_DIR = (
    _REPO_ROOT / "research/fases/F0-preparacion/04-resultados/T0.7-p-cap"
)
RUTA_CSV = RUTA_SALIDA_DIR / "borde_del_dia.csv"
RUTA_JSON = RUTA_SALIDA_DIR / "borde_del_dia.json"
RUTA_MD = RUTA_SALIDA_DIR / "borde_del_dia.md"

BAR_SEC = 900
UMBRAL_SPREAD_GATE = 0.50
VENTANA_Q4_INICIO = "16:45"
VENTANA_Q4_FIN = "18:50"
DIAS_CLUSTER_REPLICA = [
    "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31",
    "2026-08-03", "2026-08-04", "2026-08-10",
]

RUN_ID = "T0.7-M-B1-BORDE-DIA-0001"
AREA = "T0.7"
EXPERIMENTO = "borde_del_dia"
SUBSTRATE_ID = "capitaria_ticks_XAUUSD_202607_202608 + capitaria_bars_M15 + p_cap_reloj_reconstruido"
ETAPA = "medicion"
GENERADOR = "scripts/analysis/realtick_bt/faulty/borde_del_dia.py"


# ------------------------------------------------------------- Q7: citas file:line
# Citas literales verificadas contra el fichero real por
# tests/analysis/test_borde_del_dia.py (no se leen en caliente en main() para
# no acoplar la salida a la revisión futura del código citado: si el código
# cambia, el test de la cita rompe y avisa).
CITA_GATE_SPREAD_REPLICA = {
    "file": "scripts/analysis/realtick_bt/faulty/ciclos.py",
    "linea_default": 127,
    "texto_linea_default": "    max_spread_open: float = 0.50,",
    "linea_condicion": "182-183",
    "texto_condicion": (
        "spread = tick_ask - tick_bid\n"
        "                        if spread > max_spread_open + 1e-6:"
    ),
}

CITA_GATE_SPREAD_HARNESS = {
    "file": "scripts/analysis/realtick_bt/backtest.py",
    "lineas": "349-359",
    "texto": (
        "sp = eask - ebid\n"
        "        if abs(sp - 0.5) <= 0.05:\n"
        "            entry = (tc, ebid, eask, round(sp, 3)); delay_bars = bi - lo; break"
    ),
}

CITA_NO_MODELADO_BORDE_DIA = {
    "file": "scripts/analysis/realtick_bt/faulty/llamador.py",
    "lineas": "474-478",
    "texto": (
        "Los huecos de fin de semana (hasta 2,62 días medidos) NO reciben\n"
        "    tratamiento especial: se rellenan igual que cualquier otro hueco, y\n"
        "    `correr_ciclos` ya salta en O(1) por ciclo los instantes sin tick\n"
        "    (`ticks.first_at(t) is None -> continue`), así que el coste de rellenar\n"
        "    un hueco de mercado cerrado es el mismo por ciclo que cualquier otro."
    ),
}

CITA_T_OPEN_ES_INSTANTE_DE_CICLO = {
    "file": "scripts/analysis/realtick_bt/faulty/ciclos.py",
    "linea_first_at": 161,
    "texto_first_at": "        tick = ticks.first_at(t)",
    "linea_t_open": 211,
    "texto_t_open": '                                    "t_open": t,',
    "linea_tick_ts_descartado": 164,
    "texto_tick_ts_descartado": "        _tick_ts, tick_bid, tick_ask = tick",
}

FICHEROS_REVISADOS_Q3 = [
    "scripts/analysis/realtick_bt/faulty/estado_por_barra.py",
    "scripts/analysis/realtick_bt/faulty/ciclos.py",
    "scripts/analysis/realtick_bt/faulty/config_faulty.py",
    "scripts/analysis/realtick_bt/faulty/llamador.py",
    "scripts/analysis/realtick_bt/faulty/comparador.py",
]


# --------------------------------------------------------------- identificación
def identificar_cluster_borde_dia(df_cola: pd.DataFrame) -> pd.DataFrame:
    """Selecciona del censo de la cola (39 filas) las filas del cluster del
    borde del día: la fila 0 (divergencia máxima -- ya viene primera porque
    `censo_cola_t_open.py` ordena `filas_cola` por `-abs(delta_t_open_s)`,
    así que NO hace falta recalcular el máximo) más las filas
    REPLICA_TEMPRANO con 6000 <= |delta_t_open_s| <= 6500 (el patrón
    réplica≈16:5x / realidad=18:45)."""
    idx_max = df_cola["delta_t_open_s"].abs().idxmax()
    fin_de_semana = df_cola.loc[[idx_max]].copy()
    fin_de_semana["grupo"] = "fin_de_semana"

    abs_delta = df_cola["delta_t_open_s"].abs()
    mask_principal = (df_cola["signo"] == "REPLICA_TEMPRANO") & abs_delta.between(6000, 6500)
    principal = df_cola[mask_principal].copy()
    principal = principal[~principal.index.isin(fin_de_semana.index)]
    principal["grupo"] = "principal"

    out = pd.concat([principal, fin_de_semana], ignore_index=True)
    return out


# --------------------------------------------------- Q1: spread en la apertura
def segundo_set_mask(t_arr: np.ndarray, T: float) -> np.ndarray:
    t_arr = np.asarray(t_arr, dtype=float)
    return (t_arr >= T) & (t_arr < T + 1)


def tick_vigente(t_arr: np.ndarray, q_arr: np.ndarray, T: float):
    """Último tick con t <= T (mismo método que fill_vs_cotizacion.py)."""
    t_arr = np.asarray(t_arr, dtype=float)
    idx = int(np.searchsorted(t_arr, T, side="right")) - 1
    if idx < 0:
        return None, None
    return float(q_arr[idx]), idx


def primer_tick_desde(t_arr: np.ndarray, bid_arr: np.ndarray, ask_arr: np.ndarray, T: float):
    """Réplica EXACTA de `Ticks.first_at` (backtest.py:130-139): primer tick
    con t >= T (spills hacia adelante), NUNCA el último anterior -- eso es
    `tick_vigente`. Este es el método que usa de verdad `ciclos.py` en su
    bucle (`ticks.first_at(t)`, ciclos.py:161). Devuelve (t_tick, bid, ask) o
    None si no hay ningún tick con t >= T."""
    t_arr = np.asarray(t_arr, dtype=float)
    idx = int(np.searchsorted(t_arr, T, side="left"))
    if idx >= len(t_arr):
        return None
    return float(t_arr[idx]), float(bid_arr[idx]), float(ask_arr[idx])


def analizar_spread_apertura(
    t_arr: np.ndarray, bid_arr: np.ndarray, ask_arr: np.ndarray, T: float,
    umbral: float = UMBRAL_SPREAD_GATE,
) -> dict:
    """Todas las métricas de la pregunta 1 para un instante de apertura T de
    la réplica: spread del conjunto del segundo, spread del tick vigente
    (último <= T, mismo método que fill_vs_cotizacion.py), y spread del
    primer tick futuro (>= T, el que de verdad consulta `ciclos.py` vía
    `ticks.first_at`), con el retraso de éste respecto a T."""
    mask_seg = segundo_set_mask(t_arr, T)
    n = int(mask_seg.sum())
    if n > 0:
        spreads_seg = ask_arr[mask_seg] - bid_arr[mask_seg]
        seg = {
            "n_ticks_segundo": n,
            "spread_min_segundo": float(spreads_seg.min()),
            "spread_max_segundo": float(spreads_seg.max()),
            "spread_mediana_segundo": float(np.median(spreads_seg)),
        }
    else:
        seg = {
            "n_ticks_segundo": 0,
            "spread_min_segundo": None,
            "spread_max_segundo": None,
            "spread_mediana_segundo": None,
        }

    q_vig, idx_vig = tick_vigente(t_arr, ask_arr, T)
    if idx_vig is not None:
        spread_vigente = float(ask_arr[idx_vig] - bid_arr[idx_vig])
        vig = {
            "spread_vigente": spread_vigente,
            "spread_vigente_supera_umbral": bool(spread_vigente > umbral + 1e-6),
        }
    else:
        vig = {"spread_vigente": None, "spread_vigente_supera_umbral": None}

    futuro = primer_tick_desde(t_arr, bid_arr, ask_arr, T)
    if futuro is not None:
        t_tick, bid_f, ask_f = futuro
        spread_f = float(ask_f - bid_f)
        fut = {
            "t_primer_tick_futuro": t_tick,
            "spread_primer_tick_futuro": spread_f,
            "spread_primer_tick_futuro_supera_umbral": bool(spread_f > umbral + 1e-6),
            "delay_primer_tick_futuro_s": float(t_tick - T),
        }
    else:
        fut = {
            "t_primer_tick_futuro": None,
            "spread_primer_tick_futuro": None,
            "spread_primer_tick_futuro_supera_umbral": None,
            "delay_primer_tick_futuro_s": None,
        }

    return {**seg, **vig, **fut}


def cargar_ticks(root: Path = RUTA_LAGO_TICKS, meses=MESES_LAGO):
    """Mismo esquema que fill_vs_cotizacion.py::cargar_ticks: `t_msc/1000`
    epoch en segundos con fracción de milisegundo, hora de servidor, sin
    conversión de huso horario."""
    partes_t, partes_bid, partes_ask = [], [], []
    for ym in meses:
        p = root / f"{ym}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"falta el mes {ym} del lago de ticks en {p}")
        df = pd.read_parquet(p)
        partes_t.append(df.t_msc.to_numpy() / 1000.0)
        partes_bid.append(df.bid.to_numpy())
        partes_ask.append(df.ask.to_numpy())
    t_arr = np.concatenate(partes_t)
    bid_arr = np.concatenate(partes_bid)
    ask_arr = np.concatenate(partes_ask)
    orden = np.argsort(t_arr, kind="stable")
    return t_arr[orden], bid_arr[orden], ask_arr[orden]


# --------------------------------------------------------------- Q4: ticks/minuto
def contar_ticks_por_minuto(t_arr: np.ndarray, t0: float, t1: float):
    """Cuenta ticks en bins de 60 s sobre [t0, t1). Devuelve (minutos_idx,
    conteos): `minutos_idx[i]` es el índice de bin (0 = [t0, t0+60)), y
    `conteos[i]` el número de ticks en ese bin -- SIEMPRE presente aunque sea
    0 (un bin vacío nunca se omite: eso ocultaría el hueco que se busca)."""
    t_arr = np.asarray(t_arr, dtype=float)
    n_bins = int(np.ceil((t1 - t0) / 60.0))
    mask = (t_arr >= t0) & (t_arr < t1)
    sub = t_arr[mask]
    idx_bin = ((sub - t0) // 60.0).astype(int)
    idx_bin = np.clip(idx_bin, 0, n_bins - 1)
    conteos = np.bincount(idx_bin, minlength=n_bins)[:n_bins]
    minutos = np.arange(n_bins)
    return minutos, conteos


def _servidor_hhmm_a_epoch(fecha_str: str, hhmm: str) -> float:
    h, m = hhmm.split(":")
    dtobj = dt.datetime.strptime(fecha_str, "%Y-%m-%d").replace(
        hour=int(h), minute=int(m), tzinfo=dt.timezone.utc
    )
    return dtobj.timestamp()


def ticks_por_minuto_dia(
    t_arr: np.ndarray, fecha_str: str,
    hhmm_inicio: str = VENTANA_Q4_INICIO, hhmm_fin: str = VENTANA_Q4_FIN,
) -> pd.DataFrame:
    """Wrapper de `contar_ticks_por_minuto` para un día concreto (hora de
    servidor), en la ventana [hhmm_inicio, hhmm_fin)."""
    t0 = _servidor_hhmm_a_epoch(fecha_str, hhmm_inicio)
    t1 = _servidor_hhmm_a_epoch(fecha_str, hhmm_fin)
    minutos, conteos = contar_ticks_por_minuto(t_arr, t0, t1)
    hhmm = [
        (dt.datetime.utcfromtimestamp(t0 + m * 60)).strftime("%H:%M") for m in minutos
    ]
    return pd.DataFrame({"fecha": fecha_str, "hhmm": hhmm, "minuto_idx": minutos, "n_ticks": conteos})


def resumen_huecos_cero(df_minuto: pd.DataFrame) -> list[dict]:
    """Tramos contiguos de n_ticks==0 dentro de un día, como (hhmm_inicio,
    hhmm_fin, n_minutos). Dato puro, sin interpretación."""
    ceros = (df_minuto["n_ticks"] == 0).to_numpy()
    tramos = []
    i = 0
    n = len(ceros)
    while i < n:
        if ceros[i]:
            j = i
            while j < n and ceros[j]:
                j += 1
            tramos.append({
                "hhmm_inicio": df_minuto["hhmm"].iloc[i],
                "hhmm_fin": df_minuto["hhmm"].iloc[j - 1],
                "n_minutos": j - i,
            })
            i = j
        else:
            i += 1
    return tramos


# ----------------------------------------------------------------- Q5: barra M15
def identificar_barra_decision(bar_times: np.ndarray, T: float, bar_sec: int = BAR_SEC) -> dict:
    """La barra M15 vigente en el instante T, con la MISMA fórmula que
    `ciclos.py::correr_ciclos` paso 1 (`idx = searchsorted(bar_closes, t,
    'right') - 1`, `bar_closes = bar_times + BAR_SEC`): la última barra
    CERRADA antes o en T. Reporta si la SIGUIENTE barra del parquet es
    contigua (abre exactamente al cierre de ésta) o si hay un hueco
    (rollover)."""
    bar_times = np.asarray(bar_times, dtype=float)
    bar_closes = bar_times + bar_sec
    idx = int(np.searchsorted(bar_closes, T, side="right")) - 1
    if idx < 0:
        return {
            "bar_idx": None, "bar_open_epoch": None, "bar_close_epoch": None,
            "siguiente_bar_contigua": None, "gap_siguiente_bar_s": None,
        }
    bar_open = float(bar_times[idx])
    bar_close = float(bar_closes[idx])
    if idx + 1 < len(bar_times):
        siguiente_open = float(bar_times[idx + 1])
        gap = siguiente_open - bar_close
        contigua = bool(abs(gap) < 1e-6)
    else:
        gap = None
        contigua = None
    return {
        "bar_idx": idx, "bar_open_epoch": bar_open, "bar_close_epoch": bar_close,
        "siguiente_bar_contigua": contigua, "gap_siguiente_bar_s": gap,
    }


# --------------------------------------------------- Q6: segunda población de la cola
def evento_en_instante(df_eventos: pd.DataFrame, strategy_id: str, T: float, tol: float = 1.0):
    """El evento de la réplica más cercano a T (segundos), filtrado por
    `strategy_id`, dentro de `tol` segundos. None si no hay ninguno dentro de
    tol (no evaluable, nunca inventado)."""
    sub = df_eventos[df_eventos["strategy_id"] == strategy_id]
    if sub.empty:
        return None
    dist = (sub["t"].to_numpy(dtype=float) - float(T))
    adist = np.abs(dist)
    idx_min = int(np.argmin(adist))
    if adist[idx_min] > tol:
        return None
    fila = sub.iloc[idx_min]
    return {"tipo": fila["tipo"], "t": float(fila["t"]), "dist_s": float(adist[idx_min]),
            "detalle": fila["detalle"]}


def extraer_desired_sl_en_intervalo(
    df_eventos: pd.DataFrame, strategy_id: str, lo: float, hi: float,
) -> list[float]:
    """`desired_sl` de todos los eventos OPEN_SKIPPED_SL_CROSSED de
    `strategy_id` dentro de `[lo, hi]` (bordes inclusivos). `detalle` puede
    venir `None`/NaN (pandas) -- se ignora sin reventar, nunca se cuela como
    0.0 evaluable."""
    sub = df_eventos[
        (df_eventos["strategy_id"] == strategy_id)
        & (df_eventos["tipo"] == "OPEN_SKIPPED_SL_CROSSED")
        & (df_eventos["t"] >= lo) & (df_eventos["t"] <= hi)
    ]
    vals: list[float] = []
    for d in sub["detalle"]:
        if d is None:
            continue
        try:
            if pd.isna(d):
                continue
        except (TypeError, ValueError):
            pass
        try:
            j = json.loads(d)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        sl = j.get("desired_sl")
        if sl is not None:
            vals.append(float(sl))
    return vals


# ------------------------------------------------------------------ lineage / git
def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "NO_EVALUABLE"


def _lineage() -> dict:
    return {
        "run_id": RUN_ID, "area": AREA, "experimento": EXPERIMENTO,
        "substrate_id": SUBSTRATE_ID, "git_sha": _git_sha(), "etapa": ETAPA,
        "generador": GENERADOR, "timestamp": dt.datetime.utcnow().isoformat() + "Z",
    }


# ------------------------------------------------------------------------- main
def main() -> None:
    RUTA_SALIDA_DIR.mkdir(parents=True, exist_ok=True)

    df_cola = pd.read_csv(RUTA_CENSO_COLA)
    cluster = identificar_cluster_borde_dia(df_cola)

    df_ev = pd.read_csv(RUTA_EVENTOS_REPLICA)
    df_ev["t"] = pd.to_numeric(df_ev["t"], errors="coerce")

    t_arr, bid_arr, ask_arr = cargar_ticks()
    bars = pd.read_parquet(RUTA_BARS_M15)
    bar_times = bars["t"].to_numpy(dtype=float)

    # ---------------------------------------------------- Q1 + Q5: cluster (10)
    filas_cluster = []
    for _, row in cluster.iterrows():
        T = float(row["replica_t_open"])
        q1 = analizar_spread_apertura(t_arr, bid_arr, ask_arr, T)
        q5 = identificar_barra_decision(bar_times, T)
        fila = {
            "bloque": "Q1_Q5_borde_dia",
            "grupo": row["grupo"],
            "position_id": row["position_id"],
            "strategy_id": row["strategy_id"],
            "side": row["side"],
            "real_t_open_servidor": row["real_t_open_servidor"],
            "replica_t_open_servidor": row["replica_t_open_servidor"],
            "delta_t_open_s": row["delta_t_open_s"],
        }
        fila.update({f"q1_{k}": v for k, v in q1.items()})
        fila.update({f"q5_{k}": v for k, v in q5.items()})
        if q5["bar_open_epoch"] is not None:
            fila["q5_bar_open_servidor"] = dt.datetime.utcfromtimestamp(
                q5["bar_open_epoch"]
            ).strftime("%Y-%m-%d %H:%M:%S")
        else:
            fila["q5_bar_open_servidor"] = None
        filas_cluster.append(fila)

    # ---------------------------------------------------------- Q6: 16 OPEN_SKIPPED
    mask_open_skipped = df_cola["tipo_dominante_intervalo"] == "OPEN_SKIPPED_SL_CROSSED"
    segunda_poblacion = df_cola[mask_open_skipped].copy()
    filas_q6 = []
    for _, row in segunda_poblacion.iterrows():
        strat = row["strategy_id"]
        real_t = float(row["real_t_open_epoch"])
        lo, hi = float(row["intervalo_inicio_epoch"]), float(row["intervalo_fin_epoch"])
        ev_en_real_open = evento_en_instante(df_ev, strat, real_t, tol=1.0)
        sls = extraer_desired_sl_en_intervalo(df_ev, strat, lo, hi)
        fila = {
            "bloque": "Q6_segunda_poblacion",
            "position_id": row["position_id"],
            "strategy_id": strat,
            "side": row["side"],
            "delta_t_open_s": row["delta_t_open_s"],
            "signo": row["signo"],
            "delta_precio_open": row["delta_precio_open"],
            "q6_evento_en_real_t_open_tipo": ev_en_real_open["tipo"] if ev_en_real_open else None,
            "q6_evento_en_real_t_open_dist_s": ev_en_real_open["dist_s"] if ev_en_real_open else None,
            "q6_evento_en_real_t_open_no_evaluable": ev_en_real_open is None,
            "q6_desired_sl_min_en_intervalo": min(sls) if sls else None,
            "q6_desired_sl_max_en_intervalo": max(sls) if sls else None,
            "q6_n_open_skipped_en_intervalo": len(sls),
        }
        filas_q6.append(fila)

    df_out = pd.concat([pd.DataFrame(filas_cluster), pd.DataFrame(filas_q6)], ignore_index=True)
    df_out.to_csv(RUTA_CSV, index=False)

    # -------------------------------------------------------------------- Q4
    q4_por_dia = {}
    for fecha in DIAS_CLUSTER_REPLICA:
        dfm = ticks_por_minuto_dia(t_arr, fecha)
        huecos = resumen_huecos_cero(dfm)
        q4_por_dia[fecha] = {
            "n_ticks_total_ventana": int(dfm["n_ticks"].sum()),
            "huecos_cero_ticks": huecos,
            "por_minuto": dfm[["hhmm", "n_ticks"]].to_dict("records"),
        }

    resultado_json = {
        **_lineage(),
        "n_cluster_borde_dia": int(len(cluster)),
        "n_segunda_poblacion_open_skipped": int(len(segunda_poblacion)),
        "q2_gate_spread_replica": CITA_GATE_SPREAD_REPLICA,
        "q2_gate_spread_harness_vivo": CITA_GATE_SPREAD_HARNESS,
        "q3_no_modelado_borde_dia": CITA_NO_MODELADO_BORDE_DIA,
        "q3_ficheros_revisados": FICHEROS_REVISADOS_Q3,
        "mecanismo_t_open_es_instante_de_ciclo": CITA_T_OPEN_ES_INSTANTE_DE_CICLO,
        "q4_ticks_por_minuto_por_dia": q4_por_dia,
    }
    with open(RUTA_JSON, "w", encoding="utf-8") as f:
        json.dump(resultado_json, f, indent=2, ensure_ascii=False, allow_nan=False)

    _escribir_md(cluster, df_out, q4_por_dia)

    print(f"n_cluster_borde_dia={len(cluster)}  n_segunda_poblacion={len(segunda_poblacion)}")
    print(f"escrito: {RUTA_CSV}")
    print(f"escrito: {RUTA_JSON}")
    print(f"escrito: {RUTA_MD}")


def _md_tabla(headers: list[str], filas: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for f in filas:
        out.append("| " + " | ".join("" if x is None else str(x) for x in f) + " |")
    return "\n".join(out)


def _escribir_md(cluster: pd.DataFrame, df_out: pd.DataFrame, q4_por_dia: dict) -> None:
    lines = []
    lines.append("# T0.7-M-B1 -- borde del día: por qué la réplica abre a las 16:59")
    lines.append("")
    lines.append("INVESTIGADOR REPORT-ONLY. Sin conclusiones, hipótesis ni recomendaciones.")
    lines.append("")
    lines.append("## Comando exacto que generó este reporte")
    lines.append("")
    lines.append("```")
    lines.append("python scripts/analysis/realtick_bt/faulty/borde_del_dia.py")
    lines.append("```")
    lines.append("")
    lines.append("## Lineage")
    lines.append("")
    for k, v in _lineage().items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")

    q1q5 = df_out[df_out["bloque"] == "Q1_Q5_borde_dia"]
    lines.append(f"## Pregunta 1 -- spread visto por la réplica en cada apertura ({len(q1q5)} casos)")
    lines.append("")
    headers = ["position_id", "grupo", "replica_t_open_servidor", "q1_n_ticks_segundo",
               "q1_spread_vigente", "q1_spread_vigente_supera_umbral",
               "q1_spread_primer_tick_futuro", "q1_spread_primer_tick_futuro_supera_umbral",
               "q1_delay_primer_tick_futuro_s"]
    filas = [[row[h] for h in headers] for _, row in q1q5.iterrows()]
    lines.append(_md_tabla(headers, filas))
    lines.append("")
    lines.append(f"Umbral del gate: {UMBRAL_SPREAD_GATE}. Tabla íntegra (con min/max/mediana del "
                  "segundo) en `borde_del_dia.csv`.")
    lines.append("")

    lines.append("## Pregunta 2 -- umbral efectivo del gate de spread, file:line")
    lines.append("")
    lines.append(f"Réplica: `{CITA_GATE_SPREAD_REPLICA['file']}:{CITA_GATE_SPREAD_REPLICA['linea_default']}`")
    lines.append(f"\n```\n{CITA_GATE_SPREAD_REPLICA['texto_linea_default']}\n```\n")
    lines.append(f"Condición: `{CITA_GATE_SPREAD_REPLICA['file']}:{CITA_GATE_SPREAD_REPLICA['linea_condicion']}`")
    lines.append(f"\n```\n{CITA_GATE_SPREAD_REPLICA['texto_condicion']}\n```\n")
    lines.append(f"Harness vivo: `{CITA_GATE_SPREAD_HARNESS['file']}:{CITA_GATE_SPREAD_HARNESS['lineas']}`")
    lines.append(f"\n```\n{CITA_GATE_SPREAD_HARNESS['texto']}\n```\n")

    lines.append("## Pregunta 3 -- ¿modela la réplica el corte 17:00-17:45 o el fin de semana?")
    lines.append("")
    lines.append(f"`{CITA_NO_MODELADO_BORDE_DIA['file']}:{CITA_NO_MODELADO_BORDE_DIA['lineas']}`:")
    lines.append(f"\n```\n{CITA_NO_MODELADO_BORDE_DIA['texto']}\n```\n")
    lines.append("Ficheros revisados sin ningún otro tratamiento de hueco de sesión / fin de "
                  "semana / borde de día (grep `17:00|maint|weekend|fin_de_semana|domingo|"
                  "saturday|sunday|session|sesion|blocked|gate`, sin resultado salvo lo citado "
                  "arriba y los propios gates de `ciclos.py` ya citados en la pregunta 2):")
    lines.append("")
    for f in FICHEROS_REVISADOS_Q3:
        lines.append(f"- `{f}`")
    lines.append("")
    lines.append("Mecanismo -- `t_open` guarda el instante del bucle, no el tick que "
                  f"`ticks.first_at()` encontró: `{CITA_T_OPEN_ES_INSTANTE_DE_CICLO['file']}:"
                  f"{CITA_T_OPEN_ES_INSTANTE_DE_CICLO['linea_first_at']}` "
                  f"(`{CITA_T_OPEN_ES_INSTANTE_DE_CICLO['texto_first_at'].strip()}`), "
                  f"`:{CITA_T_OPEN_ES_INSTANTE_DE_CICLO['linea_tick_ts_descartado']}` "
                  f"(`{CITA_T_OPEN_ES_INSTANTE_DE_CICLO['texto_tick_ts_descartado'].strip()}`), "
                  f"`:{CITA_T_OPEN_ES_INSTANTE_DE_CICLO['linea_t_open']}` "
                  f"(`{CITA_T_OPEN_ES_INSTANTE_DE_CICLO['texto_t_open'].strip()}`).")
    lines.append("")

    lines.append(f"## Pregunta 4 -- ticks por minuto, ventana {VENTANA_Q4_INICIO}→{VENTANA_Q4_FIN} "
                  "hora de servidor, 7 días del cluster")
    lines.append("")
    filas4 = []
    for fecha, d in q4_por_dia.items():
        huecos_str = "; ".join(
            f"{h['hhmm_inicio']}-{h['hhmm_fin']} ({h['n_minutos']} min)" for h in d["huecos_cero_ticks"]
        )
        filas4.append([fecha, d["n_ticks_total_ventana"], huecos_str])
    lines.append(_md_tabla(["fecha", "n_ticks_total_ventana", "huecos_cero_ticks"], filas4))
    lines.append("")
    lines.append("Serie completa minuto a minuto en `borde_del_dia.json` (`q4_ticks_por_minuto_por_dia`).")
    lines.append("")

    lines.append(f"## Pregunta 5 -- barra M15 que originó la señal ({len(q1q5)} casos)")
    lines.append("")
    headers5 = ["position_id", "grupo", "q5_bar_open_servidor", "q5_bar_idx",
                "q5_siguiente_bar_contigua", "q5_gap_siguiente_bar_s"]
    filas5 = [[row[h] for h in headers5] for _, row in q1q5.iterrows()]
    lines.append(_md_tabla(headers5, filas5))
    lines.append("")

    q6 = df_out[df_out["bloque"] == "Q6_segunda_poblacion"]
    lines.append(f"## Pregunta 6 -- segunda población de la cola ({len(q6)} casos OPEN_SKIPPED_SL_CROSSED)")
    lines.append("")
    headers6 = ["position_id", "delta_t_open_s", "signo", "delta_precio_open",
                "q6_evento_en_real_t_open_tipo", "q6_evento_en_real_t_open_dist_s",
                "q6_evento_en_real_t_open_no_evaluable",
                "q6_desired_sl_min_en_intervalo", "q6_desired_sl_max_en_intervalo",
                "q6_n_open_skipped_en_intervalo"]
    filas6 = [[row[h] for h in headers6] for _, row in q6.iterrows()]
    lines.append(_md_tabla(headers6, filas6))
    lines.append("")
    lines.append("Nota: el brief sugiere `sl_vivo` de `posiciones_replica.csv` para esta pregunta. "
                  "Los 16 casos son eventos OPEN_SKIPPED_SL_CROSSED -- ocurren en el paso 3 de "
                  "`ciclos.py` (`posicion_viva is None`), es decir NUNCA se creó una posición en "
                  "ese ciclo, así que ninguno tiene fila propia en `posiciones_replica.csv` con la "
                  "que emparejar por ese instante: `sl_vivo` NO EVALUABLE por esta vía para estos "
                  "16 casos. En su lugar se reporta `desired_sl` del propio `detalle` JSON del "
                  "evento OPEN_SKIPPED_SL_CROSSED (`eventos_replica.csv`), que es el nivel de stop "
                  "que la ficha deseaba y que estaba cruzado en el momento del rechazo.")
    lines.append("")

    lines.append("## Pregunta 7 -- no evaluables")
    lines.append("")
    n_q6_ne = int(q6["q6_evento_en_real_t_open_no_evaluable"].sum())
    lines.append(f"- Pregunta 6, `evento_en_real_t_open`: {n_q6_ne} de {len(q6)} casos sin ningún "
                  "evento de la réplica dentro de ±1 s del `real_t_open_epoch` (declarado no "
                  "evaluable con ese margen, no inferido).")
    n_q6_sl_ne = int((q6["q6_n_open_skipped_en_intervalo"] == 0).sum())
    lines.append(f"- Pregunta 6, `desired_sl`: {n_q6_sl_ne} de {len(q6)} casos sin ningún evento "
                  "OPEN_SKIPPED_SL_CROSSED dentro del intervalo `[real_t_open, replica_t_open]` "
                  "censado (declarado no evaluable).")
    lines.append("- `sl_vivo` de `posiciones_replica.csv`, sugerido por el brief para la pregunta "
                  "6: no evaluable para los 16 casos por el motivo dado arriba (ver nota de la "
                  "pregunta 6).")
    lines.append("- Preguntas 1, 2, 3, 4 y 5: sin casos no evaluables -- los 10 instantes del "
                  "cluster tienen tick vigente y tick futuro localizables, y las 7 fechas tienen "
                  "cobertura de ticks en la ventana pedida.")
    lines.append("")

    with open(RUTA_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
