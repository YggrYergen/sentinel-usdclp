r"""T0.7-p-cap -- tabla de equivalencia `motivo_cierre` (réplica) <-> `reason`
(MT5), MEDIDA, no postulada.

Brief:
`.superpowers/sdd/2026-08-13-replica-motor-faulty-spec/m2-mapeo-motivos-brief.md`

INVESTIGADOR REPORT-ONLY. Lee `data/analysis/p_cap/verdad_terreno_902.csv`
(151 cierres en ventana canónica, verdad de terreno de MT5) y
`data/analysis/p_cap/eventos_ejecutor_902.csv` (1.710 filas, log del
ejecutor vivo), y produce (a) censos de ambas fuentes, (b) un emparejamiento
1-a-1 cierre-histórico <-> evento-de-log-más-cercano, (c) la matriz de
contingencia `reason_name` x `event`, y (d) las listas íntegras de residuo.

No inventa una regla nueva para absorber residuo: lo que no empareja se
reporta como residuo, tal como pide el brief §5.

CLOCK CONVENTION (igual que backtest.py / ciclos.py -- no "simplificar" esto)
-------------------------------------------------------------------------
Los epochs de MT5 codifican el reloj de SERVIDOR (UTC-4) verbatim. La única
conversión correcta epoch -> hora-del-día es `datetime.utcfromtimestamp()`.
`datetime.fromtimestamp()` re-aplica el huso local del host y es INCORRECTO
aquí. datetime -> epoch: `calendar.timegm()`, nunca `.timestamp()`.

`magic=0` en cierres SL/TP (ver §2 del brief): emparejar por `magic` pierde
precisamente esos cierres. Este módulo empareja por `ticket` / `position_id`
y usa `magic` sólo como confirmación, nunca como filtro.

La lógica de emparejamiento (`match_closures`) es código de producción del
programa -- la reutiliza el comparador de P-CAP -- no un one-off de este
script.
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import statistics
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_POSITIONS_CSV = ROOT / "data/analysis/p_cap/verdad_terreno_902.csv"
DEFAULT_EVENTS_CSV = ROOT / "data/analysis/p_cap/eventos_ejecutor_902.csv"
DEFAULT_OUT_DIR = ROOT / "research/fases/F0-preparacion/04-resultados/T0.7-p-cap"

WINDOW_START_STR = "2026-07-27 18:53:30"
WINDOW_END_STR = "2026-08-11 01:15:04"

# Valores de referencia del brief §1/§2, usados solo para *reportar*
# discrepancia si no cuadran -- nunca para forzar el resultado.
EXPECTED_REASON_COUNTS_IN_WINDOW = {"SL": 118, "EXPERT": 21, "CLIENT_manual": 11, "TP": 1}
EXPECTED_TOTAL_IN_WINDOW = 151

DEFAULT_TOLERANCE_S = 60.0

# Tipos de evento del log que representan un cierre de posición candidato al
# emparejamiento (brief §3.3). `ACTIONS_SUMMARY:SAME_BAR_EXIT_FALLBACK` se
# excluye de este conjunto -- ver `check_same_bar_exit_duplication()`, que
# mide (por epoch, no por nombre) que es la misma ocurrencia que
# `SAME_BAR_EXIT_FALLBACK` logueada por una segunda vía (resumen por barra),
# no un cierre adicional.
DEFAULT_CLOSING_EVENT_TYPES = (
    "SENT CLOSE",
    "FALLBACK_CLOSE_INVALID_SL",
    "SAME_BAR_EXIT_FALLBACK",
)

STRATEGY_TO_CONFIG = {
    "SAR::S6-K2P0": "S6-K2P0",
    "SuperTrend::SuperTrend-p14x3-M15": "SuperTrend-p14x3-M15",
}
CONFIG_TO_STRATEGY = {v: k for k, v in STRATEGY_TO_CONFIG.items()}

_TICKET_RE = re.compile(r"ticket=(\d+)")
_SAME_BAR_RAW_RE = re.compile(r"^\[SAME_BAR_EXIT_FALLBACK\]\s+(\S+)\s+(\S+)")


def epoch(s: str) -> int:
    return calendar.timegm(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timetuple())


def fmt(e: float) -> str:
    return datetime.utcfromtimestamp(e).strftime("%Y-%m-%d %H:%M:%S")


WINDOW_START = epoch(WINDOW_START_STR)
WINDOW_END = epoch(WINDOW_END_STR)


# --------------------------------------------------------------------------
# Extracción de anclas
# --------------------------------------------------------------------------
def extract_ticket(event: dict) -> str | None:
    """Ancla primaria: `ticket` de la columna estructurada, o de `raw` si la
    columna viene vacía (brief §2)."""
    t = (event.get("ticket") or "").strip()
    if t:
        return t
    m = _TICKET_RE.search(event.get("raw") or "")
    return m.group(1) if m else None


def extract_config(event: dict) -> str | None:
    """Ancla secundaria: `config` de la columna estructurada, o parseado de
    `raw` para `SAME_BAR_EXIT_FALLBACK`, que no trae columna `config`
    poblada."""
    c = (event.get("config") or "").strip()
    if c:
        return c
    m = _SAME_BAR_RAW_RE.match(event.get("raw") or "")
    return m.group(1) if m else None


# --------------------------------------------------------------------------
# Emparejamiento
# --------------------------------------------------------------------------
@dataclass
class MatchResult:
    matched: list[dict] = field(default_factory=list)
    residual_positions: list[dict] = field(default_factory=list)
    residual_events: list[dict] = field(default_factory=list)
    offsets_s: list[float] = field(default_factory=list)


def match_closures(
    positions: list[dict],
    events: list[dict],
    *,
    tolerance_s: float = DEFAULT_TOLERANCE_S,
    closing_event_types: tuple[str, ...] = DEFAULT_CLOSING_EVENT_TYPES,
) -> MatchResult:
    """Empareja cada cierre del historial (`positions`) con el evento de
    cierre del log (`events`) más cercano en el tiempo que afecte a la misma
    posición, 1-a-1 (ningún evento se consume dos veces).

    Dos fases, en este orden (brief §3.3 -- ancla primaria antes que
    secundaria):

    1. Ancla primaria `ticket`: el `ticket` del evento (columna o `raw`) se
       compara contra `position_id` (el log usa el ticket de la POSICIÓN,
       no el de los deals IN/OUT -- medido, ver reporte) y, por si acaso,
       contra `ticket_in`/`ticket_out`. Sólo se emparejan pares dentro de
       `tolerance_s`.
    2. Ancla secundaria `config + tiempo`: para eventos sin ticket
       extraíble (p.ej. `SAME_BAR_EXIT_FALLBACK`), se compara el `config`
       del evento contra `STRATEGY_TO_CONFIG[position['strategy_id']]`, y se
       exige cercanía temporal dentro de `tolerance_s`.

    Dentro de cada fase, el emparejamiento es voraz por desfase absoluto
    ascendente (gana el más cercano; ver test 3 del brief).
    """
    candidate_events = [e for e in events if e.get("event") in closing_event_types]

    positions_left = {p["position_id"]: p for p in positions}
    events_left = {id(e): e for e in candidate_events}

    matched: list[dict] = []
    offsets: list[float] = []

    # ---- Fase 1: ancla primaria (ticket / position_id) --------------------
    pairs_primary = []
    for p in positions_left.values():
        t_close = float(p["t_close_epoch"])
        pid = str(p["position_id"])
        ticket_in = str(p.get("ticket_in") or "")
        ticket_out = str(p.get("ticket_out") or "")
        for e in events_left.values():
            tk = extract_ticket(e)
            if tk is None:
                continue
            if tk not in (pid, ticket_in, ticket_out):
                continue
            dt = float(e["epoch"]) - t_close
            if abs(dt) > tolerance_s:
                continue
            pairs_primary.append((abs(dt), dt, p, e, "ticket"))

    pairs_primary.sort(key=lambda x: x[0])
    for _, dt, p, e, anchor in pairs_primary:
        pid = p["position_id"]
        eid = id(e)
        if pid not in positions_left or eid not in events_left:
            continue
        matched.append(_make_match_row(p, e, dt, anchor))
        offsets.append(dt)
        del positions_left[pid]
        del events_left[eid]

    # ---- Fase 2: ancla secundaria (config + proximidad temporal) ----------
    pairs_secondary = []
    for p in positions_left.values():
        t_close = float(p["t_close_epoch"])
        expected_config = STRATEGY_TO_CONFIG.get(p.get("strategy_id"))
        if expected_config is None:
            continue
        for e in events_left.values():
            if extract_ticket(e) is not None:
                # Ya tuvo su oportunidad en la fase 1 con ancla primaria;
                # no se le da una segunda vía por ancla secundaria.
                continue
            cfg = extract_config(e)
            if cfg != expected_config:
                continue
            dt = float(e["epoch"]) - t_close
            if abs(dt) > tolerance_s:
                continue
            pairs_secondary.append((abs(dt), dt, p, e, "config_tiempo"))

    pairs_secondary.sort(key=lambda x: x[0])
    for _, dt, p, e, anchor in pairs_secondary:
        pid = p["position_id"]
        eid = id(e)
        if pid not in positions_left or eid not in events_left:
            continue
        matched.append(_make_match_row(p, e, dt, anchor))
        offsets.append(dt)
        del positions_left[pid]
        del events_left[eid]

    return MatchResult(
        matched=matched,
        residual_positions=list(positions_left.values()),
        residual_events=list(events_left.values()),
        offsets_s=offsets,
    )


def _make_match_row(position: dict, event: dict, dt: float, anchor: str) -> dict:
    return {
        "position_id": position["position_id"],
        "reason_name": position.get("reason_name"),
        "strategy_id": position.get("strategy_id"),
        "t_close_epoch": position.get("t_close_epoch"),
        "event": event.get("event"),
        "event_epoch": event.get("epoch"),
        "anchor": anchor,
        "offset_s": dt,
        "event_raw": event.get("raw"),
        "event_ticket": extract_ticket(event),
        "event_config": extract_config(event),
        "event_magic": event.get("magic"),
    }


# --------------------------------------------------------------------------
# Matriz de contingencia
# --------------------------------------------------------------------------
def build_contingency_matrix(result: MatchResult) -> dict:
    reasons = sorted({m["reason_name"] for m in result.matched} |
                      {p.get("reason_name") for p in result.residual_positions})
    reasons = [r for r in reasons if r is not None]
    event_types = sorted({m["event"] for m in result.matched} |
                          {e.get("event") for e in result.residual_events})
    event_types = [e for e in event_types if e is not None]

    rows = reasons + ["SIN EMPAREJAR"]
    cols = event_types + ["SIN EMPAREJAR"]

    cells: dict[str, dict[str, int]] = {r: {c: 0 for c in cols} for r in rows}

    for m in result.matched:
        cells[m["reason_name"]][m["event"]] += 1

    for p in result.residual_positions:
        r = p.get("reason_name")
        if r is not None:
            cells[r]["SIN EMPAREJAR"] += 1

    for e in result.residual_events:
        et = e.get("event")
        if et is not None:
            cells["SIN EMPAREJAR"][et] += 1

    return {"rows": rows, "cols": cols, "cells": cells}


# --------------------------------------------------------------------------
# Censos
# --------------------------------------------------------------------------
def census_positions(positions: list[dict]) -> dict:
    total = len(positions)
    in_window = [p for p in positions if p.get("cerrada_fuera_de_ventana") == "False"]
    out_window = [p for p in positions if p.get("cerrada_fuera_de_ventana") == "True"]

    by_reason_all = dict(Counter(p.get("reason_name") for p in positions))
    by_reason_in = dict(Counter(p.get("reason_name") for p in in_window))
    by_reason_out = dict(Counter(p.get("reason_name") for p in out_window))
    by_strategy_in = dict(Counter(p.get("strategy_id") for p in in_window))

    discrepancy = None
    if by_reason_in != EXPECTED_REASON_COUNTS_IN_WINDOW or len(in_window) != EXPECTED_TOTAL_IN_WINDOW:
        discrepancy = {
            "esperado": {**EXPECTED_REASON_COUNTS_IN_WINDOW, "total": EXPECTED_TOTAL_IN_WINDOW},
            "medido": {**by_reason_in, "total": len(in_window)},
        }

    return {
        "total_filas": total,
        "en_ventana": len(in_window),
        "fuera_de_ventana": len(out_window),
        "por_reason_name_todas": by_reason_all,
        "por_reason_name_en_ventana": by_reason_in,
        "por_reason_name_fuera_de_ventana": by_reason_out,
        "por_strategy_id_en_ventana": by_strategy_in,
        "discrepancia_vs_esperado": discrepancy,
    }


def census_events(events: list[dict]) -> dict:
    total = len(events)
    in_window = [e for e in events if e.get("en_ventana_canonica") == "True"]
    out_window = [e for e in events if e.get("en_ventana_canonica") == "False"]

    by_event_all = dict(Counter(e.get("event") for e in events))
    by_event_in = dict(Counter(e.get("event") for e in in_window))
    by_event_out = dict(Counter(e.get("event") for e in out_window))

    return {
        "total_filas": total,
        "en_ventana_canonica": len(in_window),
        "fuera_de_ventana_canonica": len(out_window),
        "por_event_todas": by_event_all,
        "por_event_en_ventana": by_event_in,
        "por_event_fuera_de_ventana": by_event_out,
    }


def verify_window_filter(events: list[dict]) -> dict:
    """Recalcula `en_ventana_canonica` desde el epoch crudo y compara contra
    la columna ya presente en el CSV, en vez de asumirla (brief §2)."""
    mismatches = []
    for e in events:
        ep = float(e["epoch"])
        recomputed = WINDOW_START <= ep <= WINDOW_END
        stated = e.get("en_ventana_canonica") == "True"
        if recomputed != stated:
            mismatches.append({
                "epoch": e["epoch"],
                "timestamp_servidor": e.get("timestamp_servidor"),
                "en_ventana_canonica_csv": e.get("en_ventana_canonica"),
                "recalculado": recomputed,
            })
    return {"n_filas_verificadas": len(events), "n_discrepancias": len(mismatches),
            "discrepancias": mismatches}


# --------------------------------------------------------------------------
# Caracterización de los 21 EXPERT (brief §3.6)
# --------------------------------------------------------------------------
def characterize_expert_closures(positions: list[dict], match_result: MatchResult) -> list[dict]:
    matched_by_pid = {m["position_id"]: m for m in match_result.matched}
    residual_pids = {p["position_id"] for p in match_result.residual_positions}

    expert_rows = [p for p in positions if p.get("reason_name") == "EXPERT"]
    # Reapertura: ¿existe otra posición de la MISMA estrategia con t_open
    # posterior al t_close de esta?
    by_strategy = {}
    for p in positions:
        by_strategy.setdefault(p.get("strategy_id"), []).append(p)

    out = []
    for p in expert_rows:
        pid = p["position_id"]
        m = matched_by_pid.get(pid)
        t_close = float(p["t_close_epoch"])
        strat = p.get("strategy_id")
        reabierta = any(
            float(other.get("t_open_epoch", "0")) > t_close
            for other in by_strategy.get(strat, [])
            if other["position_id"] != pid
        )
        out.append({
            "position_id": pid,
            "strategy_id": strat,
            "t_close_servidor": p.get("t_close_servidor"),
            "evento_log_emparejado": m["event"] if m else None,
            "anchor": m["anchor"] if m else None,
            "offset_s": m["offset_s"] if m else None,
            "sin_emparejar": pid in residual_pids,
            "reabierta_despues_por_misma_estrategia": reabierta,
        })
    return out


# --------------------------------------------------------------------------
# Duplicidad SAME_BAR_EXIT_FALLBACK vs ACTIONS_SUMMARY (brief §3.7)
# --------------------------------------------------------------------------
def check_same_bar_exit_duplication(events: list[dict]) -> dict:
    same_bar = [e for e in events if e.get("event") == "SAME_BAR_EXIT_FALLBACK"]
    summary = [e for e in events if e.get("event") == "ACTIONS_SUMMARY:SAME_BAR_EXIT_FALLBACK"]

    summary_left = list(summary)
    pairs = []
    for e in same_bar:
        ep = float(e["epoch"])
        best = None
        best_dt = None
        for s in summary_left:
            dt = float(s["epoch"]) - ep
            if best_dt is None or abs(dt) < abs(best_dt):
                best_dt = dt
                best = s
        if best is not None:
            pairs.append({
                "same_bar_epoch": e["epoch"],
                "actions_summary_epoch": best["epoch"],
                "offset_s": best_dt,
            })
            summary_left.remove(best)

    offsets = [p["offset_s"] for p in pairs]
    return {
        "n_same_bar_exit_fallback": len(same_bar),
        "n_actions_summary_same_bar_exit_fallback": len(summary),
        "n_pares_por_epoch_mas_cercano": len(pairs),
        "n_actions_summary_sin_pareja": len(summary_left),
        "pares": pairs,
        "distribucion_offset_s": _offset_distribution(offsets),
    }


def _offset_distribution(offsets: list[float]) -> dict | None:
    if not offsets:
        return None
    abs_offsets = sorted(abs(o) for o in offsets)
    n = len(abs_offsets)
    return {
        "n": n,
        "min": abs_offsets[0],
        "max": abs_offsets[-1],
        "mediana": statistics.median(abs_offsets),
        "p90": abs_offsets[int(n * 0.9)] if n > 1 else abs_offsets[0],
    }


# --------------------------------------------------------------------------
# Lineage (charter §A.9)
# --------------------------------------------------------------------------
def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "UNKNOWN"


def build_lineage(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "area": "F0",
        "experimento": "T0.7-P-CAP-mapeo-motivos",
        "git_sha": git_sha(),
        "engine_sha": "b113eb7",
        "etapa": "F0-preparacion",
        "generador": "scripts/analysis/p_cap/mapeo_motivos_cierre.py",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# --------------------------------------------------------------------------
# Carga de CSV
# --------------------------------------------------------------------------
def load_csv(path: Path) -> list[dict]:
    import csv
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def build_report(
    positions_csv: Path = DEFAULT_POSITIONS_CSV,
    events_csv: Path = DEFAULT_EVENTS_CSV,
    tolerance_s: float = DEFAULT_TOLERANCE_S,
) -> dict:
    positions = load_csv(positions_csv)
    events = load_csv(events_csv)

    positions_in_window = [p for p in positions if p.get("cerrada_fuera_de_ventana") == "False"]

    census_pos = census_positions(positions)
    census_evt = census_events(events)
    window_check = verify_window_filter(events)

    match_result = match_closures(positions_in_window, events, tolerance_s=tolerance_s)
    matrix = build_contingency_matrix(match_result)
    expert_detail = characterize_expert_closures(positions_in_window, match_result)
    same_bar_dup = check_same_bar_exit_duplication(events)

    offset_dist = _offset_distribution(match_result.offsets_s)

    run_id = f"T0.7-p-cap-mapeo-motivos-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"

    return {
        "lineage": build_lineage(run_id),
        "parametros": {
            "positions_csv": str(positions_csv),
            "events_csv": str(events_csv),
            "tolerance_s": tolerance_s,
            "closing_event_types": list(DEFAULT_CLOSING_EVENT_TYPES),
            "window_start": WINDOW_START_STR,
            "window_end": WINDOW_END_STR,
            "window_start_epoch": WINDOW_START,
            "window_end_epoch": WINDOW_END,
        },
        "censo_historial": census_pos,
        "censo_log": census_evt,
        "verificacion_filtro_ventana_log": window_check,
        "emparejamiento": {
            "n_posiciones_en_ventana": len(positions_in_window),
            "n_matched": len(match_result.matched),
            "n_residual_positions": len(match_result.residual_positions),
            "n_residual_events": len(match_result.residual_events),
            "distribucion_offset_s": offset_dist,
            "matched": match_result.matched,
            "residual_positions": [
                {
                    "position_id": p["position_id"], "ticket_in": p.get("ticket_in"),
                    "ticket_out": p.get("ticket_out"), "epoch": p.get("t_close_epoch"),
                    "timestamp_servidor": p.get("t_close_servidor"),
                    "strategy_id": p.get("strategy_id"), "reason_name": p.get("reason_name"),
                }
                for p in match_result.residual_positions
            ],
            "residual_events": [
                {
                    "event": e.get("event"), "ticket": extract_ticket(e),
                    "epoch": e.get("epoch"), "timestamp_servidor": e.get("timestamp_servidor"),
                    "raw": e.get("raw"),
                }
                for e in match_result.residual_events
            ],
        },
        "matriz_contingencia": matrix,
        "caracterizacion_expert": expert_detail,
        "duplicidad_same_bar_exit_fallback": same_bar_dup,
    }


def write_json(report: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, sort_keys=False)


def write_markdown(report: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lin = report["lineage"]
    lines.append("# T0.7-p-cap -- mapeo motivo_cierre (réplica) <-> reason (MT5), medido")
    lines.append("")
    lines.append("INVESTIGADOR REPORT-ONLY. Sin conclusiones, hipótesis ni recomendaciones. "
                  "Lo no evaluable con los artefactos disponibles se marca como tal.")
    lines.append("")
    lines.append("## Lineage")
    lines.append("")
    for k, v in lin.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")

    lines.append("## Parámetros")
    lines.append("")
    for k, v in report["parametros"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")

    cp = report["censo_historial"]
    lines.append("## Censo del historial (verdad de terreno)")
    lines.append("")
    lines.append(f"- Filas totales: {cp['total_filas']}")
    lines.append(f"- En ventana canónica: {cp['en_ventana']}")
    lines.append(f"- Fuera de ventana canónica: {cp['fuera_de_ventana']}")
    lines.append("")
    lines.append("| reason_name | en ventana | fuera de ventana | todas |")
    lines.append("|---|---|---|---|")
    all_reasons = sorted(cp["por_reason_name_todas"].keys())
    for r in all_reasons:
        lines.append(f"| {r} | {cp['por_reason_name_en_ventana'].get(r, 0)} | "
                      f"{cp['por_reason_name_fuera_de_ventana'].get(r, 0)} | "
                      f"{cp['por_reason_name_todas'].get(r, 0)} |")
    lines.append("")
    lines.append("| strategy_id (en ventana) | count |")
    lines.append("|---|---|")
    for s, n in cp["por_strategy_id_en_ventana"].items():
        lines.append(f"| {s} | {n} |")
    lines.append("")
    if cp["discrepancia_vs_esperado"] is None:
        lines.append("Discrepancia vs. conteo esperado del brief (118/21/11/1=151): ninguna.")
    else:
        lines.append("**Discrepancia vs. conteo esperado del brief (118/21/11/1=151):**")
        lines.append("")
        lines.append(f"- esperado: `{cp['discrepancia_vs_esperado']['esperado']}`")
        lines.append(f"- medido: `{cp['discrepancia_vs_esperado']['medido']}`")
    lines.append("")

    ce = report["censo_log"]
    lines.append("## Censo del log del ejecutor")
    lines.append("")
    lines.append(f"- Filas totales: {ce['total_filas']}")
    lines.append(f"- En ventana canónica (columna `en_ventana_canonica`): {ce['en_ventana_canonica']}")
    lines.append(f"- Fuera de ventana canónica: {ce['fuera_de_ventana_canonica']}")
    lines.append("")
    lines.append("| event | en ventana | fuera de ventana | todas |")
    lines.append("|---|---|---|---|")
    all_events = sorted(ce["por_event_todas"].keys())
    for ev in all_events:
        lines.append(f"| {ev} | {ce['por_event_en_ventana'].get(ev, 0)} | "
                      f"{ce['por_event_fuera_de_ventana'].get(ev, 0)} | "
                      f"{ce['por_event_todas'].get(ev, 0)} |")
    lines.append("")

    wc = report["verificacion_filtro_ventana_log"]
    lines.append("## Verificación del filtro `en_ventana_canonica` del log")
    lines.append("")
    lines.append(f"- Filas verificadas (recálculo desde epoch crudo vs. columna del CSV): {wc['n_filas_verificadas']}")
    lines.append(f"- Discrepancias encontradas: {wc['n_discrepancias']}")
    if wc["discrepancias"]:
        lines.append("")
        lines.append("| epoch | timestamp_servidor | csv | recalculado |")
        lines.append("|---|---|---|---|")
        for d in wc["discrepancias"]:
            lines.append(f"| {d['epoch']} | {d['timestamp_servidor']} | "
                          f"{d['en_ventana_canonica_csv']} | {d['recalculado']} |")
    lines.append("")

    emp = report["emparejamiento"]
    lines.append("## Emparejamiento historial <-> log")
    lines.append("")
    lines.append(f"- Posiciones en ventana canónica: {emp['n_posiciones_en_ventana']}")
    lines.append(f"- Emparejadas: {emp['n_matched']}")
    lines.append(f"- Residuo del lado historial (cierres sin evento de log): {emp['n_residual_positions']}")
    lines.append(f"- Residuo del lado log (eventos de cierre sin cierre de historial): {emp['n_residual_events']}")
    lines.append("")
    od = emp["distribucion_offset_s"]
    if od is None:
        lines.append("Distribución de |desfase| entre cierre y evento emparejado: no evaluable "
                      "(cero emparejamientos).")
    else:
        lines.append(f"Distribución de |desfase| (s) entre cierre y evento emparejado: "
                      f"min={od['min']:.3f} mediana={od['mediana']:.3f} p90={od['p90']:.3f} max={od['max']:.3f} "
                      f"(n={od['n']}).")
    lines.append("")

    lines.append("### Emparejamientos (íntegro)")
    lines.append("")
    lines.append("| position_id | reason_name | strategy_id | event | anchor | offset_s |")
    lines.append("|---|---|---|---|---|---|")
    for m in emp["matched"]:
        lines.append(f"| {m['position_id']} | {m['reason_name']} | {m['strategy_id']} | "
                      f"{m['event']} | {m['anchor']} | {m['offset_s']:.3f} |")
    lines.append("")

    lines.append("### Residuo -- cierres del historial sin evento de log (íntegro)")
    lines.append("")
    lines.append("| position_id | ticket_in | ticket_out | epoch | timestamp_servidor | strategy_id | reason_name |")
    lines.append("|---|---|---|---|---|---|---|")
    for p in emp["residual_positions"]:
        lines.append(f"| {p['position_id']} | {p['ticket_in']} | {p['ticket_out']} | {p['epoch']} | "
                      f"{p['timestamp_servidor']} | {p['strategy_id']} | {p['reason_name']} |")
    lines.append("")

    lines.append("### Residuo -- eventos de cierre del log sin cierre del historial (íntegro)")
    lines.append("")
    lines.append("| event | ticket | epoch | timestamp_servidor | raw |")
    lines.append("|---|---|---|---|---|")
    for e in emp["residual_events"]:
        lines.append(f"| {e['event']} | {e['ticket']} | {e['epoch']} | {e['timestamp_servidor']} | "
                      f"`{e['raw']}` |")
    lines.append("")

    mx = report["matriz_contingencia"]
    lines.append("## Matriz de contingencia: reason_name x event del log emparejado")
    lines.append("")
    header = "| reason_name \\ event | " + " | ".join(mx["cols"]) + " |"
    sep = "|---" * (len(mx["cols"]) + 1) + "|"
    lines.append(header)
    lines.append(sep)
    for r in mx["rows"]:
        row_vals = " | ".join(str(mx["cells"][r][c]) for c in mx["cols"])
        lines.append(f"| {r} | {row_vals} |")
    lines.append("")

    lines.append("## Caracterización de los cierres EXPERT (uno a uno)")
    lines.append("")
    lines.append("| position_id | strategy_id | t_close_servidor | evento_log_emparejado | anchor | "
                  "offset_s | sin_emparejar | reabierta_despues_por_misma_estrategia |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in report["caracterizacion_expert"]:
        offset_str = f"{r['offset_s']:.3f}" if r["offset_s"] is not None else ""
        lines.append(f"| {r['position_id']} | {r['strategy_id']} | {r['t_close_servidor']} | "
                      f"{r['evento_log_emparejado']} | {r['anchor']} | {offset_str} | "
                      f"{r['sin_emparejar']} | {r['reabierta_despues_por_misma_estrategia']} |")
    lines.append("")

    dup = report["duplicidad_same_bar_exit_fallback"]
    lines.append("## Duplicidad SAME_BAR_EXIT_FALLBACK vs ACTIONS_SUMMARY:SAME_BAR_EXIT_FALLBACK")
    lines.append("")
    lines.append(f"- n `SAME_BAR_EXIT_FALLBACK`: {dup['n_same_bar_exit_fallback']}")
    lines.append(f"- n `ACTIONS_SUMMARY:SAME_BAR_EXIT_FALLBACK`: {dup['n_actions_summary_same_bar_exit_fallback']}")
    lines.append(f"- n pares por epoch más cercano (uno a uno, greedy): {dup['n_pares_por_epoch_mas_cercano']}")
    lines.append(f"- n `ACTIONS_SUMMARY` sin pareja: {dup['n_actions_summary_sin_pareja']}")
    dd = dup["distribucion_offset_s"]
    if dd is None:
        lines.append("- distribución de offset entre pares: no evaluable (cero pares).")
    else:
        lines.append(f"- distribución de |offset| (s) entre pares: min={dd['min']:.3f} "
                      f"mediana={dd['mediana']:.3f} p90={dd['p90']:.3f} max={dd['max']:.3f} (n={dd['n']}).")
    lines.append("")
    lines.append("| same_bar_epoch | actions_summary_epoch | offset_s |")
    lines.append("|---|---|---|")
    for p in dup["pares"]:
        lines.append(f"| {p['same_bar_epoch']} | {p['actions_summary_epoch']} | {p['offset_s']:.3f} |")
    lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--positions-csv", type=Path, default=DEFAULT_POSITIONS_CSV)
    ap.add_argument("--events-csv", type=Path, default=DEFAULT_EVENTS_CSV)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--tolerance-s", type=float, default=DEFAULT_TOLERANCE_S)
    args = ap.parse_args()

    report = build_report(args.positions_csv, args.events_csv, args.tolerance_s)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "mapeo_motivos_cierre.json"
    md_path = args.out_dir / "mapeo_motivos_cierre.md"
    write_json(report, json_path)
    write_markdown(report, md_path)

    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")
    emp = report["emparejamiento"]
    print(f"emparejadas={emp['n_matched']} residual_positions={emp['n_residual_positions']} "
          f"residual_events={emp['n_residual_events']}")


if __name__ == "__main__":
    main()
