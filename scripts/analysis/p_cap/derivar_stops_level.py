r"""T0.7-p-cap -- deriva `stops_level` (Componente C de la replica del motor
faulty, tag engine-faulty-tomachine-902 -> b113eb7) desde los eventos de
clamp del ejecutor real.

INVESTIGADOR REPORT-ONLY. Brief:
.superpowers/sdd/2026-08-13-replica-motor-faulty-spec/m1-stops-level-brief.md

El ejecutor vivo aplicaba un clamp al SL antes de enviarlo al broker
(`_clamp_sl(..., level)`, unidades de precio):

  - long:  si desired_sl > ref - level  =>  clamped = ref - level, ref = bid
  - short: si desired_sl < ref + level  =>  clamped = ref + level, ref = ask

  => level = |ref - clamped| en cada evento de clamp. Debe salir constante.

Este script NO decide ni interpreta: calcula level_i por evento, verifica
signo y necesidad, y reporta objetivamente. `data/analysis/p_cap/` es la
unica fuente que lee; no toca `data/lake_*`, no usa red, no usa MT5.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_EVENTOS_CSV = ROOT / "data/analysis/p_cap/eventos_ejecutor_902.csv"
DEFAULT_SL_CLAMPED_OPEN_JSON = ROOT / "data/analysis/p_cap/sl_clamped_open_events.json"
DEFAULT_VERDAD_TERRENO_CSV = ROOT / "data/analysis/p_cap/verdad_terreno_902.csv"
DEFAULT_OUT_JSON = (
    ROOT / "research/fases/F0-preparacion/04-resultados/T0.7-p-cap/stops_level_derivado.json"
)
DEFAULT_OUT_MD = (
    ROOT / "research/fases/F0-preparacion/04-resultados/T0.7-p-cap/stops_level_derivado.md"
)

ENGINE_SHA = "b113eb7"
AREA = "F0"
EXPERIMENTO = "T0.7-P-CAP-stops-level"
GENERADOR = "scripts/analysis/p_cap/derivar_stops_level.py"

ROUND_DECIMALS = 5
# Tolerancia para emparejar un evento SL_CLAMPED OPEN (sin ticket todavia,
# la posicion aun no existe) con la posicion resultante mas cercana en el
# tiempo por (config, t_open_epoch). Convencion heredada de
# scripts/analysis/p_cap/match_orders_to_positions.py (mismo umbral, 120s,
# usado alli para la misma clase de emparejamiento por cercania temporal).
MATCH_DELTA_TOLERANCE_SEC = 120

# Mismo mapeo que scripts/analysis/p_cap/match_orders_to_positions.py.
STRATEGY_TO_CONFIG = {
    "SAR::S6-K2P0": "S6-K2P0",
    "SuperTrend::SuperTrend-p14x3-M15": "SuperTrend-p14x3-M15",
}
CONFIG_TO_STRATEGY = {v: k for k, v in STRATEGY_TO_CONFIG.items()}

SIDE_TO_LS = {"BUY": "L", "SELL": "S"}


# ---------------------------------------------------------------------------
# Nucleo puro (testeado sin I/O)
# ---------------------------------------------------------------------------


def nivel_desde_ref_clamped(ref: float, clamped: float) -> float:
    """level_i = |ref - clamped|, redondeado a ROUND_DECIMALS para la
    comparacion de igualdad."""
    return round(abs(float(ref) - float(clamped)), ROUND_DECIMALS)


def verificar_signo(side: str, ref: float, clamped: float, level: float, tol: float = 1e-6) -> bool:
    """side en {"L","S"}. Comprueba que el clamp fue en la direccion
    correcta: long => clamped == ref - level; short => clamped == ref + level."""
    if side == "L":
        esperado = ref - level
    elif side == "S":
        esperado = ref + level
    else:
        return False
    return abs(esperado - clamped) <= tol


def verificar_necesidad(side: str, desired_sl: float, ref: float, level: float) -> bool:
    """Comprueba que el clamp realmente hacia falta: long => desired_sl > ref -
    level; short => desired_sl < ref + level."""
    if side == "L":
        return desired_sl > ref - level
    elif side == "S":
        return desired_sl < ref + level
    return False


def resumen_niveles(level_values: list[float]) -> dict:
    """Distribucion de level_i: valores distintos + frecuencia, min/max/
    mediana/moda, y si es constante. Nunca promedia ni elige un valor."""
    if not level_values:
        return {
            "n": 0,
            "valores": {},
            "min": None,
            "max": None,
            "mediana": None,
            "moda": None,
            "es_constante": None,
        }
    freq = Counter(level_values)
    ordenados = sorted(freq.items())
    moda_val, _moda_freq = freq.most_common(1)[0]
    return {
        "n": len(level_values),
        "valores": {f"{v:.5f}": c for v, c in ordenados},
        "min": min(level_values),
        "max": max(level_values),
        "mediana": statistics.median(level_values),
        "moda": moda_val,
        "es_constante": len(freq) == 1,
    }


def procesar_familia(eventos: list[dict]) -> dict:
    """eventos: lista de dicts con al menos epoch, timestamp_servidor, config,
    ficha, side ("L"/"S"/None), ref, clamped, desired_sl (todos pueden ser
    None). Devuelve el reporte completo de una familia (o del total)."""
    n = len(eventos)
    usables: list[dict] = []
    descartados: Counter = Counter()

    for ev in eventos:
        if ev.get("ref") is None:
            descartados["ref_ausente"] += 1
            continue
        if ev.get("clamped") is None:
            descartados["clamped_ausente"] += 1
            continue
        usables.append(ev)

    level_values: list[float] = []
    side_breakdown: dict[str, list[float]] = defaultdict(list)
    config_breakdown: dict[str, list[float]] = defaultdict(list)
    signo_fail: list[dict] = []
    signo_ok_n = 0
    necesidad_fail: list[dict] = []
    necesidad_ok_n = 0
    necesidad_no_evaluable_n = 0

    enriquecidos: list[dict] = []
    for ev in usables:
        level = nivel_desde_ref_clamped(ev["ref"], ev["clamped"])
        enriched = dict(ev)
        enriched["level_i"] = level
        enriquecidos.append(enriched)
        level_values.append(level)

        side = ev.get("side")
        if side:
            side_breakdown[side].append(level)
        cfg = ev.get("config")
        if cfg:
            config_breakdown[cfg].append(level)

        if side in ("L", "S"):
            if verificar_signo(side, ev["ref"], ev["clamped"], level):
                signo_ok_n += 1
            else:
                signo_fail.append(enriched)

            if ev.get("desired_sl") is not None:
                if verificar_necesidad(side, ev["desired_sl"], ev["ref"], level):
                    necesidad_ok_n += 1
                else:
                    necesidad_fail.append(enriched)
            else:
                necesidad_no_evaluable_n += 1

    resumen = resumen_niveles(level_values)

    discrepancias: list[dict] = []
    if resumen["es_constante"] is False:
        moda = resumen["moda"]
        discrepancias = [ev for ev in enriquecidos if ev["level_i"] != moda]

    return {
        "n": n,
        "n_usable": len(usables),
        "n_descartados": n - len(usables),
        "motivos_descartados": dict(descartados),
        "resumen_niveles": resumen,
        "desglose_side": {s: resumen_niveles(v) for s, v in side_breakdown.items()},
        "desglose_config": {c: resumen_niveles(v) for c, v in config_breakdown.items()},
        "discrepancias": discrepancias,
        "verificacion_signo": {
            "n_ok": signo_ok_n,
            "n_fail": len(signo_fail),
            "fails": signo_fail,
        },
        "verificacion_necesidad": {
            "n_ok": necesidad_ok_n,
            "n_fail": len(necesidad_fail),
            "n_no_evaluable": necesidad_no_evaluable_n,
            "fails": necesidad_fail,
        },
    }


# ---------------------------------------------------------------------------
# Carga y emparejamiento (I/O)
# ---------------------------------------------------------------------------


def _f(row: dict, key: str) -> float | None:
    v = row.get(key, "")
    if v is None or str(v).strip() == "":
        return None
    return float(v)


def cargar_eventos_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cargar_verdad_terreno(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cargar_sl_clamped_open_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def emparejar_side_open(
    evento_csv_row: dict, verdad: list[dict]
) -> tuple[str | None, str | None, int | None]:
    """Empareja un evento SL_CLAMPED OPEN (sin ticket: la posicion aun no
    existe) con la posicion resultante via (config -> strategy_id) y
    cercania temporal a t_open_epoch. Devuelve (side L/S, position_id,
    |delta_seg|) o (None, None, delta_del_mejor_candidato_o_None) si no hay
    candidato dentro de la tolerancia."""
    config = evento_csv_row.get("config")
    epoch = evento_csv_row.get("epoch")
    if not config or epoch is None:
        return None, None, None
    strategy_id = CONFIG_TO_STRATEGY.get(config)
    if strategy_id is None:
        return None, None, None
    candidatos = [v for v in verdad if v.get("strategy_id") == strategy_id]
    if not candidatos:
        return None, None, None
    mejor = min(candidatos, key=lambda v: abs(int(v["t_open_epoch"]) - int(epoch)))
    delta = abs(int(mejor["t_open_epoch"]) - int(epoch))
    if delta > MATCH_DELTA_TOLERANCE_SEC:
        return None, None, delta
    return SIDE_TO_LS.get(mejor["side"]), mejor["position_id"], delta


def emparejar_side_por_ticket(
    ticket: str | None, verdad_por_position_id: dict[str, dict]
) -> str | None:
    """Empareja un evento SL_CLAMPED (posicion ya viva; el log usa `ticket`
    para lo que en verdad_terreno_902.csv es `position_id`, verificado
    empiricamente -- no es ticket_in/ticket_out de MT5)."""
    if not ticket:
        return None
    row = verdad_por_position_id.get(ticket)
    if row is None:
        return None
    return SIDE_TO_LS.get(row.get("side"))


def construir_eventos_familia(
    filas_csv: list[dict],
    event_name: str,
    verdad: list[dict],
    verdad_por_position_id: dict[str, dict],
) -> tuple[list[dict], dict]:
    """Convierte filas crudas del CSV de eventos en la forma que consume
    `procesar_familia`, emparejando side por la via que corresponda a la
    familia. Devuelve (eventos, stats_emparejamiento)."""
    eventos: list[dict] = []
    n_side_emparejado = 0
    n_side_no_emparejado = 0

    for row in filas_csv:
        if row.get("event") != event_name:
            continue
        epoch = row.get("epoch")
        ref = _f(row, "ref")
        clamped = _f(row, "clamped")
        desired_sl = _f(row, "desired_sl")
        if desired_sl is None:
            # Para SL_CLAMPED / SL_CLAMPED OPEN el log no llena `desired_sl`;
            # el SL deseado esta en la columna `desired`.
            desired_sl = _f(row, "desired")

        if event_name == "SL_CLAMPED OPEN":
            side, position_id, _delta = emparejar_side_open(row, verdad)
        else:
            side, position_id = emparejar_side_por_ticket(
                row.get("ticket"), verdad_por_position_id
            ), row.get("ticket")

        if side is not None:
            n_side_emparejado += 1
        else:
            n_side_no_emparejado += 1

        eventos.append(
            {
                "epoch": int(epoch) if epoch not in (None, "") else None,
                "timestamp_servidor": row.get("timestamp_servidor"),
                "config": row.get("config") or None,
                "ficha": row.get("ficha") or None,
                "ticket": row.get("ticket") or None,
                "side": side,
                "position_id_emparejado": position_id,
                "ref": ref,
                "clamped": clamped,
                "desired_sl": desired_sl,
            }
        )

    return eventos, {
        "n_side_emparejado": n_side_emparejado,
        "n_side_no_emparejado": n_side_no_emparejado,
    }


# ---------------------------------------------------------------------------
# Orquestacion + artefactos
# ---------------------------------------------------------------------------


def _ruta_reportable(path: Path) -> str:
    """Ruta relativa a ROOT en forward-slash cuando es posible, para que el
    artefacto no lleve rutas absolutas de host."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _git_sha(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "UNKNOWN"


def _jsonable(obj: Any) -> Any:
    """Convierte Counters/valores no serializables a formas planas para json.dump."""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, Counter):
        return dict(obj)
    return obj


def construir_reporte(
    eventos_csv: Path,
    sl_clamped_open_json: Path,
    verdad_terreno_csv: Path,
) -> dict:
    filas_csv = cargar_eventos_csv(eventos_csv)
    verdad = cargar_verdad_terreno(verdad_terreno_csv)
    verdad_por_position_id = {v["position_id"]: v for v in verdad}
    json_87 = cargar_sl_clamped_open_json(sl_clamped_open_json)

    eventos_open, stats_open = construir_eventos_familia(
        filas_csv, "SL_CLAMPED OPEN", verdad, verdad_por_position_id
    )
    eventos_modify, stats_modify = construir_eventos_familia(
        filas_csv, "SL_CLAMPED", verdad, verdad_por_position_id
    )
    eventos_total = eventos_open + eventos_modify

    familia_open = procesar_familia(eventos_open)
    familia_modify = procesar_familia(eventos_modify)
    familia_total = procesar_familia(eventos_total)

    cuadre_json = {
        "n_json_sl_clamped_open_events": len(json_87),
        "n_csv_sl_clamped_open": familia_open["n"],
        "coincide": len(json_87) == familia_open["n"],
    }

    reporte = {
        "lineage": {
            "run_id": f"T0.7-p-cap-stops-level-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "area": AREA,
            "experimento": EXPERIMENTO,
            "git_sha": _git_sha(ROOT),
            "engine_sha": ENGINE_SHA,
            "etapa": "F0",
            "generador": GENERADOR,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "fuentes": {
            "eventos_csv": _ruta_reportable(eventos_csv),
            "sl_clamped_open_json": _ruta_reportable(sl_clamped_open_json),
            "verdad_terreno_csv": _ruta_reportable(verdad_terreno_csv),
        },
        "cuadre_json_87": cuadre_json,
        "emparejamiento_side": {
            "SL_CLAMPED OPEN": stats_open,
            "SL_CLAMPED": stats_modify,
        },
        "familias": {
            "SL_CLAMPED OPEN": familia_open,
            "SL_CLAMPED": familia_modify,
            "TOTAL": familia_total,
        },
    }
    return reporte


def _fmt_num(v):
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.5f}"
    return str(v)


def escribir_json(reporte: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_jsonable(reporte), fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")


def _md_familia(nombre: str, familia: dict, stats_side: dict) -> list[str]:
    lines = [f"## Familia `{nombre}`", ""]
    lines.append(f"- n eventos: {familia['n']}")
    lines.append(f"- n usables (ref y clamped presentes): {familia['n_usable']}")
    lines.append(f"- n descartados: {familia['n_descartados']}")
    for motivo, c in familia["motivos_descartados"].items():
        lines.append(f"  - {motivo}: {c}")
    lines.append(
        f"- side emparejado: {stats_side['n_side_emparejado']} / "
        f"no emparejado: {stats_side['n_side_no_emparejado']}"
    )
    lines.append("")
    r = familia["resumen_niveles"]
    lines.append("### Distribucion de `level_i`")
    lines.append("")
    if r["n"] == 0:
        lines.append("Sin eventos usables -- no hay `level_i` que reportar.")
    else:
        lines.append(f"- n: {r['n']}")
        lines.append(f"- min: {_fmt_num(r['min'])} · max: {_fmt_num(r['max'])} · "
                      f"mediana: {_fmt_num(r['mediana'])} · moda: {_fmt_num(r['moda'])}")
        lines.append(f"- constante: {r['es_constante']}")
        lines.append("")
        lines.append("| level_i | frecuencia |")
        lines.append("|---|---|")
        for v, c in r["valores"].items():
            lines.append(f"| {v} | {c} |")
    lines.append("")

    lines.append("### Desglose por side")
    lines.append("")
    if not familia["desglose_side"]:
        lines.append("(sin eventos con side emparejado y usable)")
    else:
        for side, rs in familia["desglose_side"].items():
            lines.append(f"- `{side}`: n={rs['n']}, valores={rs['valores']}")
    lines.append("")

    lines.append("### Desglose por config")
    lines.append("")
    if not familia["desglose_config"]:
        lines.append("(sin eventos con config y usable)")
    else:
        for cfg, rs in familia["desglose_config"].items():
            lines.append(f"- `{cfg}`: n={rs['n']}, valores={rs['valores']}")
    lines.append("")

    if familia["discrepancias"]:
        lines.append("### Eventos discrepantes (level_i != moda)")
        lines.append("")
        lines.append("| epoch | timestamp_servidor | config | ficha | ref | clamped | level_i |")
        lines.append("|---|---|---|---|---|---|---|")
        for ev in familia["discrepancias"]:
            lines.append(
                f"| {ev.get('epoch')} | {ev.get('timestamp_servidor')} | "
                f"{ev.get('config')} | {ev.get('ficha')} | {_fmt_num(ev.get('ref'))} | "
                f"{_fmt_num(ev.get('clamped'))} | {_fmt_num(ev.get('level_i'))} |"
            )
        lines.append("")

    vs = familia["verificacion_signo"]
    lines.append("### Verificacion de signo")
    lines.append("")
    lines.append(f"- ok: {vs['n_ok']} · fail: {vs['n_fail']}")
    if vs["fails"]:
        lines.append("")
        lines.append("| epoch | config | ficha | side | ref | clamped | level_i |")
        lines.append("|---|---|---|---|---|---|---|")
        for ev in vs["fails"]:
            lines.append(
                f"| {ev.get('epoch')} | {ev.get('config')} | {ev.get('ficha')} | "
                f"{ev.get('side')} | {_fmt_num(ev.get('ref'))} | {_fmt_num(ev.get('clamped'))} | "
                f"{_fmt_num(ev.get('level_i'))} |"
            )
    lines.append("")

    vn = familia["verificacion_necesidad"]
    lines.append("### Verificacion de necesidad")
    lines.append("")
    lines.append(
        f"- ok: {vn['n_ok']} · fail: {vn['n_fail']} · no evaluable (sin desired_sl): "
        f"{vn['n_no_evaluable']}"
    )
    if vn["fails"]:
        lines.append("")
        lines.append("| epoch | config | ficha | side | desired_sl | ref | level_i |")
        lines.append("|---|---|---|---|---|---|---|")
        for ev in vn["fails"]:
            lines.append(
                f"| {ev.get('epoch')} | {ev.get('config')} | {ev.get('ficha')} | "
                f"{ev.get('side')} | {_fmt_num(ev.get('desired_sl'))} | {_fmt_num(ev.get('ref'))} | "
                f"{_fmt_num(ev.get('level_i'))} |"
            )
    lines.append("")
    return lines


def escribir_md(reporte: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lin = reporte["lineage"]
    lines = [
        "# T0.7-P-CAP -- stops_level derivado de eventos de clamp (b113eb7)",
        "",
        "INVESTIGADOR REPORT-ONLY. Sin conclusiones ni recomendaciones: numeros, "
        "rutas y conteos.",
        "",
        "## Lineage",
        "",
        f"- run_id: `{lin['run_id']}`",
        f"- area: `{lin['area']}`",
        f"- experimento: `{lin['experimento']}`",
        f"- git_sha: `{lin['git_sha']}`",
        f"- engine_sha: `{lin['engine_sha']}`",
        f"- etapa: `{lin['etapa']}`",
        f"- generador: `{lin['generador']}`",
        f"- timestamp: `{lin['timestamp']}`",
        "",
        "## Fuentes",
        "",
        f"- eventos_csv: `{reporte['fuentes']['eventos_csv']}`",
        f"- sl_clamped_open_json: `{reporte['fuentes']['sl_clamped_open_json']}`",
        f"- verdad_terreno_csv: `{reporte['fuentes']['verdad_terreno_csv']}`",
        "",
        "## Cuadre contra la fuente secundaria (87 eventos SL_CLAMPED OPEN)",
        "",
        f"- n en JSON: {reporte['cuadre_json_87']['n_json_sl_clamped_open_events']}",
        f"- n en CSV (event=SL_CLAMPED OPEN): {reporte['cuadre_json_87']['n_csv_sl_clamped_open']}",
        f"- coincide: {reporte['cuadre_json_87']['coincide']}",
        "",
    ]
    for nombre in ("SL_CLAMPED OPEN", "SL_CLAMPED", "TOTAL"):
        stats_side = reporte["emparejamiento_side"].get(
            nombre, {"n_side_emparejado": "n/a", "n_side_no_emparejado": "n/a"}
        )
        lines.extend(_md_familia(nombre, reporte["familias"][nombre], stats_side))

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eventos-csv", type=Path, default=DEFAULT_EVENTOS_CSV)
    ap.add_argument("--sl-clamped-open-json", type=Path, default=DEFAULT_SL_CLAMPED_OPEN_JSON)
    ap.add_argument("--verdad-terreno-csv", type=Path, default=DEFAULT_VERDAD_TERRENO_CSV)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = ap.parse_args()

    reporte = construir_reporte(
        args.eventos_csv, args.sl_clamped_open_json, args.verdad_terreno_csv
    )
    escribir_json(reporte, args.out_json)
    escribir_md(reporte, args.out_md)

    total = reporte["familias"]["TOTAL"]
    print(f"SL_CLAMPED OPEN: n={reporte['familias']['SL_CLAMPED OPEN']['n']}, "
          f"usable={reporte['familias']['SL_CLAMPED OPEN']['n_usable']}")
    print(f"SL_CLAMPED: n={reporte['familias']['SL_CLAMPED']['n']}, "
          f"usable={reporte['familias']['SL_CLAMPED']['n_usable']}")
    print(f"TOTAL: n={total['n']}, usable={total['n_usable']}")
    print(f"JSON escrito: {args.out_json}")
    print(f"MD escrito: {args.out_md}")


if __name__ == "__main__":
    main()
