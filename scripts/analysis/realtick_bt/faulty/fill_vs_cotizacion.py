r"""fill_vs_cotizacion.py -- Brief H (F0-A6-FILL-0001), T0.7 / A6 Pata A / P-CAP.

Spec: .superpowers/sdd/2026-08-13-replica-motor-faulty-spec/h-fill-broker-brief.md

Mide, para las 152 posiciones reales de la cuenta 902 (304 eventos: 152
aperturas + 152 cierres), si el precio real de llenado que reportó MT5
EXISTE como cotización en el lago de ticks de Capitaria, en el segundo
entero en que MT5 dice que ocurrió el llenado.

Este script es de MEDICIÓN, autocontenido: no importa `ciclos.py`,
`estado_por_barra.py`, `llamador.py`, `comparador.py` ni `config_faulty.py`
(están congelados y otro agente puede estar leyéndolos en paralelo). Sólo
copia el patrón de lectura de parquet de esos módulos (mismo esquema:
`t_msc/1000`, `bid`, `ask`, epoch en SEGUNDOS con fracción de milisegundo,
sin ninguna conversión de huso horario).

REPORT-ONLY: este módulo no interpreta, no concluye, no recomienda. Sólo
calcula y escribe números.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[4]

RUTA_VERDAD_TERRENO = _REPO_ROOT / "data" / "analysis" / "p_cap" / "verdad_terreno_902.csv"
RUTA_COMPARACION = _REPO_ROOT / "data" / "analysis" / "p_cap" / "comparacion_p_cap.csv"
RUTA_LAGO_TICKS = _REPO_ROOT / "data" / "lake_ticks" / "XAUUSD"
MESES_LAGO = ["202607", "202608"]

RUTA_SALIDA_DIR = (
    _REPO_ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados" / "T0.7-p-cap"
)
RUTA_CSV = RUTA_SALIDA_DIR / "fill_vs_cotizacion.csv"
RUTA_JSON = RUTA_SALIDA_DIR / "fill_vs_cotizacion.json"
RUTA_MD = RUTA_SALIDA_DIR / "fill_vs_cotizacion.md"

VENTANAS_K = (1, 2, 5, 30)

RUN_ID = "F0-A6-FILL-0001"
AREA = "T0.7"
EXPERIMENTO = "fill_vs_cotizacion"
SUBSTRATE_ID = "capitaria_ticks_XAUUSD_202607_202608"
ETAPA = "medicion"
GENERADOR = "scripts/analysis/realtick_bt/faulty/fill_vs_cotizacion.py"


# --------------------------------------------------------------- (a)(b)(c)(d)
def segundo_set_mask(t_arr: np.ndarray, T: int) -> np.ndarray:
    """S = { ticks con floor(t_msc/1000) == T }, expresado como t in
    [T, T+1). No asume orden."""
    t_arr = np.asarray(t_arr, dtype=float)
    return (t_arr >= T) & (t_arr < T + 1)


def ventana_mask(t_arr: np.ndarray, T: int, k: int) -> np.ndarray:
    """Ventana continua [T-k, T+k] (cerrada en ambos extremos). No asume
    orden."""
    t_arr = np.asarray(t_arr, dtype=float)
    return (t_arr >= (T - k)) & (t_arr <= (T + k))


def tick_vigente(t_arr: np.ndarray, q_arr: np.ndarray, T: int):
    """Cotización del último tick con t <= T (lo que un sondeo justo en T
    vería). Asume `t_arr` ordenado ascendentemente (invariante del lago:
    verificado -- ver §2 del brief). Devuelve (valor, idx) o (None, None)
    si no hay ningún tick con t <= T -- nunca un valor inventado."""
    t_arr = np.asarray(t_arr, dtype=float)
    idx = int(np.searchsorted(t_arr, T, side="right")) - 1
    if idx < 0:
        return None, None
    return float(q_arr[idx]), idx


def lado_para_evento(side: str, evento: str) -> str:
    """Convención MT5 (no se cambia, §2 del brief): BUY abre a ask / cierra
    a bid; SELL abre a bid / cierra a ask."""
    tabla = {
        ("BUY", "OPEN"): "ask",
        ("SELL", "OPEN"): "bid",
        ("BUY", "CLOSE"): "bid",
        ("SELL", "CLOSE"): "ask",
    }
    return tabla[(side, evento)]


def lado_opuesto(lado: str) -> str:
    return "bid" if lado == "ask" else "ask"


def hit_exacto(precio: float, q_arr: np.ndarray) -> bool:
    """¿`precio` es exactamente igual (a 2 decimales, `round(x, 2)`,
    NUNCA `==` sobre float crudo) a algún valor de `q_arr`? Segundo/ventana
    vacíos -> False, sin error."""
    q_arr = np.asarray(q_arr, dtype=float)
    if q_arr.size == 0:
        return False
    return bool(np.any(np.round(q_arr, 2) == round(float(precio), 2)))


# ------------------------------------------------------------------ evento
def medir_evento(
    t_arr: np.ndarray,
    bid_arr: np.ndarray,
    ask_arr: np.ndarray,
    side: str,
    evento: str,
    T: int,
    P: float,
) -> dict:
    """Calcula TODAS las métricas de §3.1 (a, b, c, d) para un evento de
    llenado (apertura o cierre de una posición)."""
    lado = lado_para_evento(side, evento)
    lado_op = lado_opuesto(lado)
    q_lado = ask_arr if lado == "ask" else bid_arr
    q_op = ask_arr if lado_op == "ask" else bid_arr

    # (a) conjunto del segundo
    mask_seg = segundo_set_mask(t_arr, T)
    n_ticks_segundo = int(mask_seg.sum())
    Q_S = q_lado[mask_seg]
    Q_S_op = q_op[mask_seg]

    if n_ticks_segundo > 0:
        hit_exacto_segundo = hit_exacto(P, Q_S)
        q_min_segundo = float(Q_S.min())
        q_max_segundo = float(Q_S.max())
        dentro_rango_segundo = bool(q_min_segundo <= P <= q_max_segundo)
        dist_min_segundo = float(np.min(np.abs(Q_S - P)))
        hit_exacto_segundo_lado_opuesto = hit_exacto(P, Q_S_op)
    else:
        hit_exacto_segundo = False
        q_min_segundo = None
        q_max_segundo = None
        dentro_rango_segundo = False
        dist_min_segundo = None
        hit_exacto_segundo_lado_opuesto = False

    # (b) tick vigente
    q_vigente, idx_vigente = tick_vigente(t_arr, q_lado, T)
    if q_vigente is not None:
        hit_exacto_vigente = round(q_vigente, 2) == round(float(P), 2)
        delta_vigente = float(P) - q_vigente
        spread_tick_vigente = float(ask_arr[idx_vigente]) - float(bid_arr[idx_vigente])
    else:
        hit_exacto_vigente = False
        delta_vigente = None
        spread_tick_vigente = None

    resultado = {
        "lado": lado,
        "n_ticks_segundo": n_ticks_segundo,
        "hit_exacto_segundo": hit_exacto_segundo,
        "dentro_rango_segundo": dentro_rango_segundo,
        "dist_min_segundo": dist_min_segundo,
        "q_min_segundo": q_min_segundo,
        "q_max_segundo": q_max_segundo,
        "hit_exacto_segundo_lado_opuesto": hit_exacto_segundo_lado_opuesto,
        "q_vigente": q_vigente,
        "hit_exacto_vigente": hit_exacto_vigente,
        "delta_vigente": delta_vigente,
        "spread_tick_vigente": spread_tick_vigente,
    }

    # (c) ventanas crecientes
    for k in VENTANAS_K:
        mask_k = ventana_mask(t_arr, T, k)
        n_k = int(mask_k.sum())
        Q_k = q_lado[mask_k]
        if n_k > 0:
            resultado[f"n_ticks_{k}"] = n_k
            resultado[f"hit_exacto_{k}"] = hit_exacto(P, Q_k)
            resultado[f"dentro_rango_{k}"] = bool(Q_k.min() <= P <= Q_k.max())
            resultado[f"dist_min_{k}"] = float(np.min(np.abs(Q_k - P)))
        else:
            resultado[f"n_ticks_{k}"] = 0
            resultado[f"hit_exacto_{k}"] = False
            resultado[f"dentro_rango_{k}"] = False
            resultado[f"dist_min_{k}"] = None

    return resultado


# ---------------------------------------------------------------- carga datos
def cargar_ticks(root: Path = RUTA_LAGO_TICKS, meses=MESES_LAGO):
    """Lee los parquet de meses indicados del lago de ticks Capitaria y
    devuelve (t_arr, bid_arr, ask_arr) concatenados y ordenados por t.
    Mismo esquema que `llamador.py:135-147`: `t_msc/1000` es epoch en
    SEGUNDOS con fracción de milisegundo, reloj de servidor -- sin
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


def construir_filas(
    df_vt: pd.DataFrame,
    df_cmp_real: pd.DataFrame,
    t_arr: np.ndarray,
    bid_arr: np.ndarray,
    ask_arr: np.ndarray,
) -> list[dict]:
    """Construye las 304 filas (152 aperturas + 152 cierres), una por
    evento de llenado, con todas las columnas de §3.1 más las de cruce con
    la réplica y las de la verdad de terreno."""
    cmp_por_pos = df_cmp_real.set_index("position_id")[
        ["delta_precio_open", "delta_t_open_s"]
    ]

    filas = []
    for row in df_vt.itertuples(index=False):
        position_id = row.position_id
        strategy_id = row.strategy_id
        side = row.side

        if position_id in cmp_por_pos.index:
            delta_precio_open = cmp_por_pos.loc[position_id, "delta_precio_open"]
            delta_t_open_s = cmp_por_pos.loc[position_id, "delta_t_open_s"]
        else:
            delta_precio_open = None
            delta_t_open_s = None

        # --- apertura
        T_open = int(row.t_open_epoch)
        m_open = medir_evento(
            t_arr, bid_arr, ask_arr, side, "OPEN", T_open, float(row.precio_open)
        )
        fila_open = {
            "position_id": position_id,
            "strategy_id": strategy_id,
            "side": side,
            "evento": "OPEN",
            "reason_name": None,
            "t_epoch": T_open,
            "precio_real": float(row.precio_open),
            "delta_precio_open": delta_precio_open,
            "delta_t_open_s": delta_t_open_s,
            "spread_open": row.spread_open,
            "spread_close": row.spread_close,
        }
        fila_open.update(m_open)
        filas.append(fila_open)

        # --- cierre
        T_close = int(row.t_close_epoch)
        m_close = medir_evento(
            t_arr, bid_arr, ask_arr, side, "CLOSE", T_close, float(row.precio_close)
        )
        fila_close = {
            "position_id": position_id,
            "strategy_id": strategy_id,
            "side": side,
            "evento": "CLOSE",
            "reason_name": row.reason_name,
            "t_epoch": T_close,
            "precio_real": float(row.precio_close),
            "delta_precio_open": None,
            "delta_t_open_s": None,
            "spread_open": row.spread_open,
            "spread_close": row.spread_close,
        }
        fila_close.update(m_close)
        filas.append(fila_close)

    return filas


# ------------------------------------------------------------- agregación §3.2
_COLS_DIST = ["dist_min_segundo"] + [f"dist_min_{k}" for k in VENTANAS_K]
_COLS_HIT = (
    ["hit_exacto_segundo", "hit_exacto_vigente", "hit_exacto_segundo_lado_opuesto"]
    + [f"hit_exacto_{k}" for k in VENTANAS_K]
)
_COLS_DENTRO = ["dentro_rango_segundo"] + [f"dentro_rango_{k}" for k in VENTANAS_K]


def _percentiles(valores) -> dict:
    arr = np.array([v for v in valores if v is not None and not (isinstance(v, float) and np.isnan(v))], dtype=float)
    if arr.size == 0:
        return {"p50": None, "p90": None, "max": None, "n_evaluable": 0}
    return {
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "max": float(np.max(arr)),
        "n_evaluable": int(arr.size),
    }


def _pct_true(valores) -> dict:
    arr = np.array(list(valores), dtype=bool)
    n = int(arr.size)
    if n == 0:
        return {"pct": None, "n_true": 0, "n": 0}
    return {"pct": float(arr.mean() * 100.0), "n_true": int(arr.sum()), "n": n}


def agregar_subset(df: pd.DataFrame) -> dict:
    """Agregados de §3.2 para un subconjunto de filas: conteos y
    percentiles (p50, p90, max) de dist_min_*, y % de hit_exacto_* /
    dentro_rango_*. Sólo números."""
    agg: dict = {
        "n_eventos": int(len(df)),
        "n_ticks_segundo_cero": int((df["n_ticks_segundo"] == 0).sum()),
        "n_vigente_no_evaluable": int(df["q_vigente"].isna().sum()),
    }
    for k in VENTANAS_K:
        agg[f"n_ticks_{k}_cero"] = int((df[f"n_ticks_{k}"] == 0).sum())
    for c in _COLS_DIST:
        agg[c] = _percentiles(df[c].tolist())
    for c in _COLS_HIT:
        agg[c] = _pct_true(df[c].tolist())
    for c in _COLS_DENTRO:
        agg[c] = _pct_true(df[c].tolist())
    return agg


def agregar_delta_vigente_signo(df: pd.DataFrame) -> dict:
    """Corte §3.2.5: mediana de delta_vigente CON SIGNO, por side y por
    evento, y conteo de >0 / ==0 / <0 en cada celda."""
    salida = {}
    for side in sorted(df["side"].dropna().unique()):
        for evento in ("OPEN", "CLOSE"):
            sub = df[(df["side"] == side) & (df["evento"] == evento)]
            vals = sub["delta_vigente"].dropna()
            key = f"{side}|{evento}"
            salida[key] = {
                "n_total": int(len(sub)),
                "n_evaluable": int(len(vals)),
                "n_no_evaluable": int(len(sub) - len(vals)),
                "mediana_con_signo": float(vals.median()) if len(vals) else None,
                "n_positivo": int((vals > 0).sum()),
                "n_cero": int((vals == 0).sum()),
                "n_negativo": int((vals < 0).sum()),
            }
    return salida


def construir_agregados(df: pd.DataFrame) -> dict:
    agregados: dict = {
        "global": agregar_subset(df),
        "por_evento": {
            evento: agregar_subset(df[df["evento"] == evento])
            for evento in ("OPEN", "CLOSE")
        },
        "por_reason_close": {
            reason: agregar_subset(df[(df["evento"] == "CLOSE") & (df["reason_name"] == reason)])
            for reason in ("SL", "EXPERT", "CLIENT_manual", "TP")
        },
        "por_estrategia": {
            estrategia: agregar_subset(df[df["strategy_id"] == estrategia])
            for estrategia in sorted(df["strategy_id"].dropna().unique())
        },
        "por_side": {
            side: agregar_subset(df[df["side"] == side])
            for side in sorted(df["side"].dropna().unique())
        },
        "delta_vigente_signo_por_side_evento": agregar_delta_vigente_signo(df),
    }
    return agregados


# ------------------------------------------------------------------ git sha
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


# ------------------------------------------------------------------ markdown
def _fmt_num(x, nd=4):
    if x is None:
        return "n/e"
    return f"{x:.{nd}f}"


def _tabla_dist_hit(nombre: str, agg: dict) -> list[str]:
    lineas = [f"### {nombre}", "", f"n_eventos = {agg['n_eventos']}", ""]
    lineas.append("| métrica | p50 | p90 | max | n_evaluable |")
    lineas.append("|---|---|---|---|---|")
    for c in _COLS_DIST:
        d = agg[c]
        lineas.append(
            f"| {c} | {_fmt_num(d['p50'])} | {_fmt_num(d['p90'])} | {_fmt_num(d['max'])} | {d['n_evaluable']} |"
        )
    lineas.append("")
    lineas.append("| métrica | % true | n_true | n |")
    lineas.append("|---|---|---|---|")
    for c in _COLS_HIT + _COLS_DENTRO:
        h = agg[c]
        pct = "n/e" if h["pct"] is None else f"{h['pct']:.2f}"
        lineas.append(f"| {c} | {pct} | {h['n_true']} | {h['n']} |")
    lineas.append("")
    extra = [f"n_ticks_segundo_cero = {agg['n_ticks_segundo_cero']}",
             f"n_vigente_no_evaluable = {agg['n_vigente_no_evaluable']}"]
    for k in VENTANAS_K:
        extra.append(f"n_ticks_{k}_cero = {agg[f'n_ticks_{k}_cero']}")
    lineas.append(", ".join(extra))
    lineas.append("")
    return lineas


def escribir_md(agregados: dict, comando: str, fecha: str) -> str:
    lineas = [
        "# fill_vs_cotizacion -- F0-A6-FILL-0001",
        "",
        f"Comando: `{comando}`",
        "",
        f"Fecha: {fecha}",
        "",
        "REPORT-ONLY. Sin interpretación.",
        "",
        "## Global",
        "",
    ]
    lineas += _tabla_dist_hit("global", agregados["global"])

    lineas.append("## Por evento")
    lineas.append("")
    for evento, agg in agregados["por_evento"].items():
        lineas += _tabla_dist_hit(f"evento = {evento}", agg)

    lineas.append("## Por reason_name (sólo cierres)")
    lineas.append("")
    for reason, agg in agregados["por_reason_close"].items():
        lineas += _tabla_dist_hit(f"reason_name = {reason}", agg)

    lineas.append("## Por estrategia")
    lineas.append("")
    for estrategia, agg in agregados["por_estrategia"].items():
        lineas += _tabla_dist_hit(f"strategy_id = {estrategia}", agg)

    lineas.append("## Por side")
    lineas.append("")
    for side, agg in agregados["por_side"].items():
        lineas += _tabla_dist_hit(f"side = {side}", agg)

    lineas.append("## Signo de delta_vigente, por side x evento")
    lineas.append("")
    lineas.append("| side|evento | n_total | n_evaluable | n_no_evaluable | mediana_con_signo | n_positivo | n_cero | n_negativo |")
    lineas.append("|---|---|---|---|---|---|---|---|")
    for key, d in agregados["delta_vigente_signo_por_side_evento"].items():
        lineas.append(
            f"| {key} | {d['n_total']} | {d['n_evaluable']} | {d['n_no_evaluable']} | "
            f"{_fmt_num(d['mediana_con_signo'])} | {d['n_positivo']} | {d['n_cero']} | {d['n_negativo']} |"
        )
    lineas.append("")
    return "\n".join(lineas)


# ------------------------------------------------------------------------ main
def main() -> None:
    df_vt = pd.read_csv(RUTA_VERDAD_TERRENO)
    df_cmp = pd.read_csv(RUTA_COMPARACION)
    df_cmp_real = df_cmp[df_cmp["tipo_fila"] == "REAL"].copy()

    t_arr, bid_arr, ask_arr = cargar_ticks()

    filas = construir_filas(df_vt, df_cmp_real, t_arr, bid_arr, ask_arr)
    df_out = pd.DataFrame(filas)

    RUTA_SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(RUTA_CSV, index=False)

    agregados = construir_agregados(df_out)
    salida_json = {"lineage": _lineage(), "agregados": agregados}
    with open(RUTA_JSON, "w", encoding="utf-8") as fh:
        json.dump(salida_json, fh, indent=2, ensure_ascii=False, allow_nan=False)

    comando = "python scripts/analysis/realtick_bt/faulty/fill_vs_cotizacion.py"
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md = escribir_md(agregados, comando, fecha)
    with open(RUTA_MD, "w", encoding="utf-8") as fh:
        fh.write(md)

    print(f"filas escritas: {len(df_out)}")
    print(f"CSV: {RUTA_CSV}")
    print(f"JSON: {RUTA_JSON}")
    print(f"MD: {RUTA_MD}")


if __name__ == "__main__":
    main()
