"""scripts/analysis/realtick_bt/faulty/censo_cola_t_open.py

BRIEF I -- Censo de la cola del p90 de |delta t_open| entre la RÉPLICA del
motor faulty y las 152 posiciones reales de la cuenta 902 (P-CAP, T0.7,
A6 Pata A, Fase 0).

Spec cerrada: .superpowers/sdd/2026-08-13-replica-motor-faulty-spec/i-cola-p90-brief.md

INVESTIGADOR REPORT-ONLY: este script SÓLO mide y censa. No interpreta, no
concluye, no recomienda, no prioriza, no corrige nada. Es RECOLECCIÓN de
datos aditiva sobre artefactos ya producidos (solo lectura).

R1-bis: este script NO importa ni modifica ciclos.py, estado_por_barra.py,
llamador.py, comparador.py, config_faulty.py ni nada de sentinel_engine/ o
backtest.py. Es autocontenido y sólo usa pandas/numpy/stdlib.

Insumos (solo lectura, rutas verificadas en el brief §2):
  - data/analysis/p_cap/comparacion_p_cap.csv        (162 filas)
  - data/analysis/p_cap/verdad_terreno_902.csv        (152 filas)
  - data/analysis/p_cap/replica/eventos_replica.csv   (142.961 filas)
  - data/analysis/p_cap/eventos_ejecutor_902.csv      (1.710 filas)

NO se usan los ficheros *.rejilla-sintetica.* ni *.criterio-estricto.* (reloj
viejo, corridas conservadas para auditoría -- brief §2).

Artefactos producidos (brief §4):
  - research/fases/F0-preparacion/04-resultados/T0.7-p-cap/censo_cola_t_open.csv
  - research/fases/F0-preparacion/04-resultados/T0.7-p-cap/censo_sin_pareja.csv
  - research/fases/F0-preparacion/04-resultados/T0.7-p-cap/censo_cola_t_open.json
  - research/fases/F0-preparacion/04-resultados/T0.7-p-cap/censo_cola_t_open.md
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]

COMPARACION_CSV = ROOT / "data/analysis/p_cap/comparacion_p_cap.csv"
VERDAD_CSV = ROOT / "data/analysis/p_cap/verdad_terreno_902.csv"
EVENTOS_REPLICA_CSV = ROOT / "data/analysis/p_cap/replica/eventos_replica.csv"
EVENTOS_EJECUTOR_CSV = ROOT / "data/analysis/p_cap/eventos_ejecutor_902.csv"

OUT_DIR = ROOT / "research/fases/F0-preparacion/04-resultados/T0.7-p-cap"
OUT_COLA_CSV = OUT_DIR / "censo_cola_t_open.csv"
OUT_SIN_PAREJA_CSV = OUT_DIR / "censo_sin_pareja.csv"
OUT_JSON = OUT_DIR / "censo_cola_t_open.json"
OUT_MD = OUT_DIR / "censo_cola_t_open.md"

# 9 tipos exactos de eventos_replica.csv (brief §2, conteos verificados)
TIPOS_REPLICA = [
    "NOOP",
    "SPREAD_GATE_SKIP",
    "OPEN_SKIPPED_SL_CROSSED",
    "TIME_GATE_SKIP",
    "MODIFY",
    "SL_CLAMPED",
    "OPEN",
    "CLOSE",
    "FALLBACK_CLOSE_INVALID_SL",
]

# Tramos de estratificación de |delta_t_open_s| (brief §3.1). Partición
# monótona sin solapes; el límite superior de cada tramo es exclusivo salvo
# el último.
TRAMOS = [
    ("<1 s", 0.0, 1.0),
    ("1-16 s", 1.0, 16.0),
    ("16-60 s", 16.0, 60.0),
    ("1-15 min", 60.0, 900.0),
    ("15-60 min", 900.0, 3600.0),
    ("1-6 h", 3600.0, 21600.0),
    (">6 h", 21600.0, float("inf")),
]

STRATEGY_MAGIC = {
    "SAR::S6-K2P0": "724011",
    "SuperTrend::SuperTrend-p14x3-M15": "724071",
}


# --------------------------------------------------------------- utilidades
def signo_delta(delta_t_open_s: float) -> str:
    """positivo (>=0) => la réplica abrió después (TARDE); negativo => antes
    (TEMPRANO). Convención fijada en brief §3.2. El caso 0.0 (sin diferencia
    real) se asigna a TARDE por convención (no aparece en la cola: |0|<=60)."""
    return "REPLICA_TARDE" if delta_t_open_s >= 0 else "REPLICA_TEMPRANO"


def epoch_a_servidor_str(epoch: Any) -> str:
    """epoch (segundos, hora de servidor) -> texto legible, con la MISMA
    convención que usa verdad_terreno_902.csv (t_open_servidor): el epoch se
    interpreta directamente como UTC ingenuo (sin offset adicional).
    Verificado en el reporte contra 3 filas reales (brief §3.4)."""
    if epoch is None:
        return ""
    try:
        if pd.isna(epoch):
            return ""
    except (TypeError, ValueError):
        pass
    return dt.datetime.utcfromtimestamp(float(epoch)).strftime("%Y-%m-%d %H:%M:%S")


def epoch_en_blocked_window(epoch: Any, inicio: str = "18:00", fin: str = "18:45") -> bool | None:
    """True/False si el epoch cae en [inicio, fin) hora de servidor; None si
    epoch no está disponible (p.ej. la mitad ausente de una fila SIN_PAREJA)."""
    if epoch is None:
        return None
    try:
        if pd.isna(epoch):
            return None
    except (TypeError, ValueError):
        pass
    hhmm = dt.datetime.utcfromtimestamp(float(epoch)).strftime("%H:%M")
    return inicio <= hhmm < fin


def censar_intervalo_replica(df_eventos_replica: pd.DataFrame, strategy_id: str, lo: float, hi: float) -> dict:
    """Censo de eventos de la réplica en [lo, hi] (bordes inclusivos),
    filtrado a `strategy_id`. Devuelve conteos por los 9 tipos, total,
    tipo_dominante_intervalo (excluyendo NOOP; SOLO_NOOP si sólo hay NOOP;
    SIN_EVENTOS si no hay nada) y el primer evento no-NOOP con su epoch."""
    sub = df_eventos_replica[
        (df_eventos_replica["strategy_id"] == strategy_id)
        & (df_eventos_replica["t"] >= lo)
        & (df_eventos_replica["t"] <= hi)
    ].sort_values("t")

    n_total = int(len(sub))
    counts = {f"eventos_{tipo}": int((sub["tipo"] == tipo).sum()) for tipo in TIPOS_REPLICA}

    no_noop = sub[sub["tipo"] != "NOOP"]
    if n_total == 0:
        dominante = "SIN_EVENTOS"
    elif no_noop.empty:
        dominante = "SOLO_NOOP"
    else:
        vc = no_noop["tipo"].value_counts()
        top = vc.max()
        candidatos = sorted(vc[vc == top].index.tolist())
        if len(candidatos) == 1:
            dominante = candidatos[0]
        else:
            # desempate determinista: el tipo (entre los empatados en
            # frecuencia) cuyo primer evento ocurre más temprano en el
            # intervalo.
            primeros = {tp: no_noop[no_noop["tipo"] == tp]["t"].min() for tp in candidatos}
            dominante = min(primeros, key=lambda tp: (primeros[tp], tp))

    if no_noop.empty:
        primer_evento_no_noop = ""
        t_primer_evento_no_noop: Any = ""
    else:
        primera_fila = no_noop.iloc[0]
        primer_evento_no_noop = primera_fila["tipo"]
        t_primer_evento_no_noop = primera_fila["t"]

    result: dict[str, Any] = {
        "n_eventos_intervalo": n_total,
        "tipo_dominante_intervalo": dominante,
        "primer_evento_no_noop": primer_evento_no_noop,
        "t_primer_evento_no_noop": t_primer_evento_no_noop,
    }
    result.update(counts)
    return result


def censar_intervalo_ejecutor(df_eventos_ejecutor: pd.DataFrame, lo: float, hi: float) -> dict:
    """Censo de eventos del log del ejecutor real en [lo, hi] (bordes
    inclusivos). Conteo por valor DISTINTO de la columna `event`, tal cual,
    sin normalizar. NO se filtra por estrategia: ver nota metodológica en el
    reporte .md (columnas `magic`/`config` del log sólo identifican la
    estrategia para una parte de los tipos de evento; ver anomalía A1)."""
    sub = df_eventos_ejecutor[
        (df_eventos_ejecutor["epoch"] >= lo) & (df_eventos_ejecutor["epoch"] <= hi)
    ]
    conteo = sub["event"].value_counts().to_dict()
    return {
        "n_eventos_ejecutor_intervalo": int(len(sub)),
        "ejecutor_eventos_conteo": {str(k): int(v) for k, v in conteo.items()},
    }


def clasificar_tramo(abs_delta: float) -> str:
    for nombre, lo, hi in TRAMOS:
        if lo <= abs_delta < hi:
            return nombre
    return ">6 h"


def percentiles(serie: pd.Series) -> dict[str, float]:
    s = serie.dropna()
    if s.empty:
        return {"p50": None, "p75": None, "p90": None, "p95": None, "p99": None, "max": None, "n": 0}
    return {
        "p50": float(np.percentile(s, 50)),
        "p75": float(np.percentile(s, 75)),
        "p90": float(np.percentile(s, 90)),
        "p95": float(np.percentile(s, 95)),
        "p99": float(np.percentile(s, 99)),
        "max": float(s.max()),
        "n": int(len(s)),
    }


def _git_sha(root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except Exception:
        return "NO_EVALUABLE"


def _lineage() -> dict[str, Any]:
    return {
        "run_id": "F0-A6-COLA-0001",
        "area": "T0.7",
        "experimento": "censo_cola_t_open",
        "substrate_id": "p_cap_reloj_reconstruido",
        "git_sha": _git_sha(ROOT),
        "etapa": "medicion",
        "generador": "scripts/analysis/realtick_bt/faulty/censo_cola_t_open.py",
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
    }


# ------------------------------------------------------------- carga de datos
def _cargar_comparacion() -> pd.DataFrame:
    return pd.read_csv(COMPARACION_CSV)


def _cargar_eventos_replica() -> pd.DataFrame:
    df = pd.read_csv(EVENTOS_REPLICA_CSV)
    df["t"] = pd.to_numeric(df["t"], errors="coerce")
    return df


def _cargar_eventos_ejecutor() -> pd.DataFrame:
    df = pd.read_csv(EVENTOS_EJECUTOR_CSV)
    df["epoch"] = pd.to_numeric(df["epoch"], errors="coerce")
    return df


def _blocked_window_desde_log(df_ejecutor: pd.DataFrame) -> tuple[str, str]:
    raw0 = str(df_ejecutor.iloc[0]["raw"])
    marker = "blocked_open_window="
    idx = raw0.find(marker)
    if idx == -1:
        return ("18:00", "18:45")  # NO_EVALUABLE en el log; se usa el valor citado en el brief
    resto = raw0[idx + len(marker):]
    rango = resto.split(")")[0].split(",")[0].strip()
    inicio, fin = rango.split("-")
    return (inicio.strip(), fin.strip())


# ------------------------------------------------------------- construcción
def _num_o_none(v: Any) -> float | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return float(v)


def _pos_id_str(v: Any) -> str:
    n = _num_o_none(v)
    if n is None:
        return ""
    return str(int(n))


def construir_fila_cola(row: pd.Series, df_replica: pd.DataFrame, df_ejecutor: pd.DataFrame) -> dict:
    real_t_open = float(row["real_t_open_epoch"])
    replica_t_open = float(row["replica_t_open"])
    delta_signed = replica_t_open - real_t_open
    lo, hi = min(real_t_open, replica_t_open), max(real_t_open, replica_t_open)

    censo_r = censar_intervalo_replica(df_replica, row["strategy_id"], lo, hi)
    censo_e = censar_intervalo_ejecutor(df_ejecutor, lo, hi)

    fila: dict[str, Any] = {
        "position_id": _pos_id_str(row["position_id"]),
        "strategy_id": row["strategy_id"],
        "side": row["real_side"],
        "real_t_open_epoch": real_t_open,
        "real_t_open_servidor": epoch_a_servidor_str(real_t_open),
        "replica_t_open": replica_t_open,
        "replica_t_open_servidor": epoch_a_servidor_str(replica_t_open),
        "delta_t_open_s": delta_signed,
        "signo": signo_delta(delta_signed),
        "delta_precio_open": _num_o_none(row.get("delta_precio_open")),
        "real_reason_name": row.get("real_reason_name", ""),
        "n_campos_coinciden": _num_o_none(row.get("n_campos_coinciden")),
        "intervalo_inicio_epoch": lo,
        "intervalo_fin_epoch": hi,
        "n_eventos_intervalo": censo_r["n_eventos_intervalo"],
        "tipo_dominante_intervalo": censo_r["tipo_dominante_intervalo"],
        "primer_evento_no_noop": censo_r["primer_evento_no_noop"],
        "t_primer_evento_no_noop": censo_r["t_primer_evento_no_noop"],
        "n_eventos_ejecutor_intervalo": censo_e["n_eventos_ejecutor_intervalo"],
        "ejecutor_eventos_conteo_json": json.dumps(censo_e["ejecutor_eventos_conteo"], ensure_ascii=False, sort_keys=True),
        "real_open_en_blocked_window": epoch_en_blocked_window(real_t_open, *BLOCKED_WINDOW),
        "replica_open_en_blocked_window": epoch_en_blocked_window(replica_t_open, *BLOCKED_WINDOW),
    }
    for tipo in TIPOS_REPLICA:
        fila[f"eventos_{tipo}"] = censo_r[f"eventos_{tipo}"]
    return fila


def construir_fila_sin_pareja(row: pd.Series, df_replica: pd.DataFrame) -> dict:
    tipo_fila = row["tipo_fila"]
    if tipo_fila == "REAL":
        t_open = _num_o_none(row["real_t_open_epoch"])
        side = row["real_side"]
        precio_open = _num_o_none(row.get("real_precio_open"))
        motivo_cierre = row.get("real_reason_name", "")
        real_epoch, replica_epoch = t_open, None
    else:  # REPLICA_SIN_PAREJA
        t_open = _num_o_none(row["replica_t_open"])
        side = row["replica_side"]
        precio_open = _num_o_none(row.get("replica_precio_open"))
        motivo_cierre = row.get("replica_motivo_cierre", "")
        real_epoch, replica_epoch = None, t_open

    ventana_lo, ventana_hi = t_open - 900.0, t_open + 900.0
    censo_r = censar_intervalo_replica(df_replica, row["strategy_id"], ventana_lo, ventana_hi)

    fila: dict[str, Any] = {
        "tipo_fila": tipo_fila,
        "position_id": _pos_id_str(row.get("position_id")),
        "strategy_id": row["strategy_id"],
        "side": side,
        "t_open_epoch": t_open,
        "t_open_servidor": epoch_a_servidor_str(t_open),
        "precio_open": precio_open,
        "motivo_cierre": motivo_cierre,
        "ventana_inicio_epoch": ventana_lo,
        "ventana_fin_epoch": ventana_hi,
        "n_eventos_intervalo": censo_r["n_eventos_intervalo"],
        "tipo_dominante_intervalo": censo_r["tipo_dominante_intervalo"],
        "primer_evento_no_noop": censo_r["primer_evento_no_noop"],
        "t_primer_evento_no_noop": censo_r["t_primer_evento_no_noop"],
        "real_open_en_blocked_window": epoch_en_blocked_window(real_epoch, *BLOCKED_WINDOW),
        "replica_open_en_blocked_window": epoch_en_blocked_window(replica_epoch, *BLOCKED_WINDOW),
    }
    for tipo in TIPOS_REPLICA:
        fila[f"eventos_{tipo}"] = censo_r[f"eventos_{tipo}"]
    return fila


# ---------------------------------------------------------------------- main
BLOCKED_WINDOW: tuple[str, str] = ("18:00", "18:45")  # sobreescrito en main() desde el log


def _md_tabla(headers: list[str], filas: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for f in filas:
        out.append("| " + " | ".join("" if x is None else str(x) for x in f) + " |")
    return "\n".join(out)


def main() -> None:
    global BLOCKED_WINDOW
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    comp = _cargar_comparacion()
    df_replica = _cargar_eventos_replica()
    df_ejecutor = _cargar_eventos_ejecutor()

    BLOCKED_WINDOW = _blocked_window_desde_log(df_ejecutor)

    # ---- verificación de la conversión epoch<->servidor (brief §3.4) ----
    verdad = pd.read_csv(VERDAD_CSV)
    verif_rows = verdad[["t_open_epoch", "t_open_servidor"]].head(3)
    verificacion = []
    for _, r in verif_rows.iterrows():
        calculado = epoch_a_servidor_str(r["t_open_epoch"])
        verificacion.append({
            "epoch": float(r["t_open_epoch"]),
            "t_open_servidor_csv": r["t_open_servidor"],
            "calculado": calculado,
            "coincide": calculado == r["t_open_servidor"],
        })

    # ---------------------------------------------------------- §3.1
    emp = comp[(comp["tipo_fila"] == "REAL") & (comp["pareja"] == "EMPAREJADA")].copy()
    emp["delta_t_open_s_signed"] = emp["replica_t_open"] - emp["real_t_open_epoch"]
    emp["abs_delta_t_open_s"] = emp["delta_t_open_s_signed"].abs()
    emp["tramo"] = emp["abs_delta_t_open_s"].apply(clasificar_tramo)

    n_emp = len(emp)
    tramo_counts = emp["tramo"].value_counts().reindex([t[0] for t in TRAMOS], fill_value=0)
    estratificacion = {
        "n_emparejadas": int(n_emp),
        "por_tramo": {
            nombre: {"n": int(tramo_counts[nombre]), "pct": round(100.0 * tramo_counts[nombre] / n_emp, 4)}
            for nombre in tramo_counts.index
        },
        "percentiles_global": percentiles(emp["abs_delta_t_open_s"]),
        "percentiles_por_estrategia": {
            strat: percentiles(g["abs_delta_t_open_s"]) for strat, g in emp.groupby("strategy_id")
        },
        "percentiles_por_side": {
            side: percentiles(g["abs_delta_t_open_s"]) for side, g in emp.groupby("real_side")
        },
    }

    # ---------------------------------------------------------- §3.2 cola
    cola_df = emp[emp["abs_delta_t_open_s"] > 60.0].copy()
    filas_cola = [construir_fila_cola(row, df_replica, df_ejecutor) for _, row in cola_df.iterrows()]
    filas_cola.sort(key=lambda f: -abs(f["delta_t_open_s"]))

    conteo_dominante_cola = pd.Series([f["tipo_dominante_intervalo"] for f in filas_cola]).value_counts().to_dict()

    # ---------------------------------------------------------- §3.3 sin pareja
    sinpareja_df = comp[comp["pareja"] == "SIN_PAREJA"].copy()
    filas_sinpareja = [construir_fila_sin_pareja(row, df_replica) for _, row in sinpareja_df.iterrows()]

    # ---------------------------------------------------------- escritura
    cola_out = pd.DataFrame(filas_cola)
    cola_out.to_csv(OUT_COLA_CSV, index=False)

    sinpareja_out = pd.DataFrame(filas_sinpareja)
    sinpareja_out.to_csv(OUT_SIN_PAREJA_CSV, index=False)

    resultado_json = {
        "estratificacion_delta_t_open": estratificacion,
        "n_cola_gt_60s": int(len(filas_cola)),
        "n_sin_pareja": int(len(filas_sinpareja)),
        "conteo_tipo_dominante_intervalo_cola": {str(k): int(v) for k, v in conteo_dominante_cola.items()},
        "blocked_open_window": {"inicio": BLOCKED_WINDOW[0], "fin": BLOCKED_WINDOW[1]},
        "verificacion_epoch_servidor": verificacion,
        **_lineage(),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(resultado_json, f, ensure_ascii=False, indent=2, sort_keys=False)

    _escribir_md(estratificacion, filas_cola, filas_sinpareja, conteo_dominante_cola, verificacion)

    print(f"n_emparejadas={n_emp}  n_cola(>60s)={len(filas_cola)}  n_sin_pareja={len(filas_sinpareja)}")
    print(f"blocked_open_window={BLOCKED_WINDOW}")
    print(f"escrito: {OUT_COLA_CSV}")
    print(f"escrito: {OUT_SIN_PAREJA_CSV}")
    print(f"escrito: {OUT_JSON}")
    print(f"escrito: {OUT_MD}")


def _escribir_md(estratificacion, filas_cola, filas_sinpareja, conteo_dominante_cola, verificacion) -> None:
    lines = []
    lines.append("# T0.7-p-cap -- censo de la cola de |delta t_open| (réplica vs. 152 posiciones reales, 902), medido")
    lines.append("")
    lines.append("INVESTIGADOR REPORT-ONLY. Sin conclusiones, hipótesis ni recomendaciones. Recolección de datos.")
    lines.append("")
    lines.append("## Comando exacto que generó este reporte")
    lines.append("")
    lines.append("```")
    lines.append("python scripts/analysis/realtick_bt/faulty/censo_cola_t_open.py")
    lines.append("```")
    lines.append("")
    lines.append("## Lineage")
    lines.append("")
    lin = _lineage()
    for k, v in lin.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")

    lines.append("## §3.1 -- Estratificación de |delta_t_open_s| (147 emparejadas)")
    lines.append("")
    lines.append(f"n_emparejadas = {estratificacion['n_emparejadas']}")
    lines.append("")
    filas_tramo = [[nombre, d["n"], f"{d['pct']:.2f}%"] for nombre, d in estratificacion["por_tramo"].items()]
    lines.append(_md_tabla(["tramo", "n", "%"], filas_tramo))
    lines.append("")
    lines.append("### Percentiles globales (s)")
    lines.append("")
    p = estratificacion["percentiles_global"]
    lines.append(_md_tabla(
        ["n", "p50", "p75", "p90", "p95", "p99", "max"],
        [[p["n"], p["p50"], p["p75"], p["p90"], p["p95"], p["p99"], p["max"]]],
    ))
    lines.append("")
    lines.append("### Percentiles por estrategia (s)")
    lines.append("")
    filas_pe = []
    for strat, pp in estratificacion["percentiles_por_estrategia"].items():
        filas_pe.append([strat, pp["n"], pp["p50"], pp["p75"], pp["p90"], pp["p95"], pp["p99"], pp["max"]])
    lines.append(_md_tabla(["strategy_id", "n", "p50", "p75", "p90", "p95", "p99", "max"], filas_pe))
    lines.append("")
    lines.append("### Percentiles por side (s)")
    lines.append("")
    filas_ps = []
    for side, pp in estratificacion["percentiles_por_side"].items():
        filas_ps.append([side, pp["n"], pp["p50"], pp["p75"], pp["p90"], pp["p95"], pp["p99"], pp["max"]])
    lines.append(_md_tabla(["side", "n", "p50", "p75", "p90", "p95", "p99", "max"], filas_ps))
    lines.append("")

    lines.append(f"## §3.2 -- La cola: {len(filas_cola)} posiciones con |delta_t_open_s| > 60 s")
    lines.append("")
    lines.append("Tabla íntegra en `censo_cola_t_open.csv`. Resumen de identificación:")
    lines.append("")
    headers = ["position_id", "strategy_id", "side", "real_t_open_servidor", "replica_t_open_servidor",
               "delta_t_open_s", "signo", "n_eventos_intervalo", "tipo_dominante_intervalo",
               "n_eventos_ejecutor_intervalo", "real_open_en_blocked_window", "replica_open_en_blocked_window"]
    filas_resumen = [[f[h] for h in headers] for f in filas_cola]
    lines.append(_md_tabla(headers, filas_resumen))
    lines.append("")
    lines.append("### Conteo de `tipo_dominante_intervalo` sobre la cola")
    lines.append("")
    lines.append(_md_tabla(["tipo_dominante_intervalo", "n"], [[k, v] for k, v in conteo_dominante_cola.items()]))
    lines.append("")

    lines.append(f"## §3.3 -- Las {len(filas_sinpareja)} filas SIN_PAREJA")
    lines.append("")
    headers2 = ["tipo_fila", "position_id", "strategy_id", "side", "t_open_servidor", "precio_open",
                "motivo_cierre", "n_eventos_intervalo", "tipo_dominante_intervalo",
                "real_open_en_blocked_window", "replica_open_en_blocked_window"]
    filas_resumen2 = [[f[h] for h in headers2] for f in filas_sinpareja]
    lines.append(_md_tabla(headers2, filas_resumen2))
    lines.append("")

    lines.append("## §3.4 -- Verificación epoch<->hora de servidor (3 filas de verdad_terreno_902.csv)")
    lines.append("")
    lines.append(_md_tabla(
        ["epoch", "t_open_servidor (csv)", "calculado", "coincide"],
        [[v["epoch"], v["t_open_servidor_csv"], v["calculado"], v["coincide"]] for v in verificacion],
    ))
    lines.append("")
    lines.append(f"`blocked_open_window` leído del log (fila 0, columna `raw`): {lin_blocked_window()}")
    lines.append("")

    lines.append("## Nota metodológica -- censo del log del ejecutor real (dato, no interpretación)")
    lines.append("")
    lines.append(
        "En `eventos_ejecutor_902.csv`, la columna `magic` sólo está poblada para el evento "
        "`SENT OPEN` (724011 / 724071); la columna `config` sólo está poblada para "
        "`OPEN_SKIPPED_SL_CROSSED`, `SL_CLAMPED OPEN`, `ALARM` y `ACTIONS_SUMMARY:SAME_BAR_EXIT_FALLBACK`. "
        "Para `SENT MODIFY` (431 filas), `SL_CLAMPED` (35), `SENT CLOSE` (3), "
        "`FALLBACK_CLOSE_INVALID_SL` (9), `SAME_BAR_EXIT_FALLBACK` (11) y `OTRO` (5), ninguna de las "
        "dos columnas identifica la estrategia. Por eso el censo del log del ejecutor en §3.2 "
        "**no está filtrado por estrategia** (a diferencia del censo de la réplica, que sí lo está): "
        "cuenta todos los eventos del ejecutor en el intervalo, sin importar a qué posición "
        "pertenecen. La columna `ejecutor_eventos_conteo_json` en `censo_cola_t_open.csv` lista los "
        "valores distintos de `event` encontrados y su conteo, tal cual, sin normalizar."
    )
    lines.append("")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def lin_blocked_window() -> str:
    return f"{BLOCKED_WINDOW[0]}-{BLOCKED_WINDOW[1]}"


if __name__ == "__main__":
    main()
