r"""T0.6-B Bloque 3 preguntas 10, 11 y 12 -- barrido de una sola pasada del log grande
(69,7 MB, 561.988 lineas) `audit_ventana_2026-07-27_2026-08-12.log`.

INVESTIGADOR REPORT-ONLY. Procesa el fichero linea a linea (streaming), nunca lo carga
entero en memoria. Todo en foreground.

Calcula:
  Q11 -- todas las lineas "=== cycle ... ===" (ciclos de reconciliacion): cuenta total,
         deltas entre ciclos consecutivos, mediana y percentiles, restringido tambien a
         la ventana canonica.
  Q12 -- reconteo independiente de los 13 contadores agregados publicados por maquina 2,
         contando directamente sobre este fichero.
  Q10 -- extrae TODAS las lineas [SENT OPEN] con su config, timestamp y retcode (lista
         pequena, cabe en memoria) para que build_positions_match_orders.py la empareje
         contra las 152 posiciones reales.

Convencion de reloj: identica a los demas scripts de esta tarea -- `datetime.utcfromtimestamp()`,
timestamps del log parseados literalmente sin conversion de zona horaria.
"""
from __future__ import annotations

import calendar
import csv
import json
import re
import statistics
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FOREX")
LOG = ROOT / "data/entregas/2026-08-12-maquina2-tomachine-902/logs_ejecutor/audit_ventana_2026-07-27_2026-08-12.log"
OUT_SENT_OPEN_JSON = ROOT / "data/analysis/p_cap/sent_open_events.json"

WINDOW_START_STR = "2026-07-27 18:53:30"
WINDOW_END_STR = "2026-08-11 01:15:04"


def epoch(s: str) -> int:
    return calendar.timegm(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timetuple())


WINDOW_START = epoch(WINDOW_START_STR)
WINDOW_END = epoch(WINDOW_END_STR)

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
CYCLE_RE = re.compile(r"=== cycle ")
SENT_OPEN_RE = re.compile(r"\[SENT OPEN\] (\S[^F]*?) F1 magic=(\d+) -> retcode=(\d+)")
SL_CLAMPED_OPEN_RE = re.compile(
    r"\[SL_CLAMPED OPEN\] config=(\S+) ficha=(\S+) desired=(-?[\d.]+) clamped=(-?[\d.]+) gap=(-?[\d.]+)"
)


def line_epoch_ms(line: str):
    m = TS_RE.match(line)
    if not m:
        return None, None
    date_s, ms = m.groups()
    return epoch(date_s), int(ms)


def main():
    n_lines = 0
    cycle_epochs_ms = []  # (epoch_seconds, ms) tuples, full precision via seconds+ms
    counters = {
        "SPREAD_GATE_SKIP": 0,
        "TIME_GATE_SKIP": 0,
        "OPEN_SKIPPED_SL_CROSSED": 0,
        "SL_CLAMPED_exact": 0,
        "SL_CLAMPED_OPEN": 0,
        "FALLBACK_CLOSE_INVALID_SL": 0,
        "ALARM": 0,
        "actions_OPEN_F1": 0,
        "actions_NOOP_F1": 0,
        "actions_none": 0,
        "actions_MODIFY_F1": 0,
        "actions_SAME_BAR_EXIT_FALLBACK_F1": 0,
        "actions_CLOSE_OPEN": 0,
        "cycle_lines": 0,
    }
    counters_window = {k: 0 for k in counters}

    sent_open_events = []  # list of dicts: config, epoch, ms, retcode
    sl_clamped_open_events = []  # list of dicts: config, ficha, epoch, ms, desired, clamped, gap

    with open(LOG, encoding="utf-8", errors="replace") as f:
        for line in f:
            n_lines += 1
            e, ms = line_epoch_ms(line)
            in_win = e is not None and WINDOW_START <= e <= WINDOW_END

            if "=== cycle " in line:
                counters["cycle_lines"] += 1
                if in_win:
                    counters_window["cycle_lines"] += 1
                if e is not None:
                    cycle_epochs_ms.append(e + ms / 1000.0)
                continue

            if "actions: " in line:
                if "actions: OPEN/F1" in line:
                    counters["actions_OPEN_F1"] += 1
                    if in_win:
                        counters_window["actions_OPEN_F1"] += 1
                elif "actions: NOOP/F1" in line:
                    counters["actions_NOOP_F1"] += 1
                    if in_win:
                        counters_window["actions_NOOP_F1"] += 1
                elif "actions: none" in line:
                    counters["actions_none"] += 1
                    if in_win:
                        counters_window["actions_none"] += 1
                elif "actions: MODIFY/F1" in line:
                    counters["actions_MODIFY_F1"] += 1
                    if in_win:
                        counters_window["actions_MODIFY_F1"] += 1
                elif "actions: SAME_BAR_EXIT_FALLBACK/F1" in line:
                    counters["actions_SAME_BAR_EXIT_FALLBACK_F1"] += 1
                    if in_win:
                        counters_window["actions_SAME_BAR_EXIT_FALLBACK_F1"] += 1
                elif "actions: CLOSE/F1" in line and "OPEN/F1" in line:
                    counters["actions_CLOSE_OPEN"] += 1
                    if in_win:
                        counters_window["actions_CLOSE_OPEN"] += 1

            if "SPREAD_GATE_SKIP" in line:
                counters["SPREAD_GATE_SKIP"] += 1
                if in_win:
                    counters_window["SPREAD_GATE_SKIP"] += 1
            if "TIME_GATE_SKIP" in line:
                counters["TIME_GATE_SKIP"] += 1
                if in_win:
                    counters_window["TIME_GATE_SKIP"] += 1
            if "OPEN_SKIPPED_SL_CROSSED" in line:
                counters["OPEN_SKIPPED_SL_CROSSED"] += 1
                if in_win:
                    counters_window["OPEN_SKIPPED_SL_CROSSED"] += 1
            if "SL_CLAMPED OPEN" in line:
                counters["SL_CLAMPED_OPEN"] += 1
                if in_win:
                    counters_window["SL_CLAMPED_OPEN"] += 1
            elif "SL_CLAMPED" in line:
                counters["SL_CLAMPED_exact"] += 1
                if in_win:
                    counters_window["SL_CLAMPED_exact"] += 1
            if "FALLBACK_CLOSE_INVALID_SL" in line:
                counters["FALLBACK_CLOSE_INVALID_SL"] += 1
                if in_win:
                    counters_window["FALLBACK_CLOSE_INVALID_SL"] += 1
            if "[ALARM]" in line:
                counters["ALARM"] += 1
                if in_win:
                    counters_window["ALARM"] += 1

            sm = SENT_OPEN_RE.search(line)
            if sm and e is not None:
                sent_open_events.append(
                    {
                        "config": sm.group(1).strip(),
                        "epoch": e,
                        "ms": ms,
                        "retcode": sm.group(3),
                    }
                )

            cm = SL_CLAMPED_OPEN_RE.search(line)
            if cm and e is not None:
                sl_clamped_open_events.append(
                    {
                        "config": cm.group(1),
                        "ficha": cm.group(2),
                        "epoch": e,
                        "ms": ms,
                        "desired": float(cm.group(3)),
                        "clamped": float(cm.group(4)),
                        "gap": float(cm.group(5)),
                    }
                )

    print(f"lineas totales procesadas: {n_lines}")
    print(f"\n=== Q12: contadores reconteados (TODO el log, 2026-07-27 18:52:29 -> 2026-08-12 09:37:02) ===")
    for k, v in counters.items():
        print(f"  {k}: {v}")
    print(f"\n=== Q12: mismos contadores, RESTRINGIDO a la ventana canonica ===")
    for k, v in counters_window.items():
        print(f"  {k}: {v}")

    print(f"\n=== Q11: ciclos de reconciliacion ===")
    print(f"total lineas '=== cycle ': {len(cycle_epochs_ms)}")
    cycle_epochs_ms.sort()
    deltas = [cycle_epochs_ms[i] - cycle_epochs_ms[i - 1] for i in range(1, len(cycle_epochs_ms))]
    deltas_sorted = sorted(deltas)

    def pct(p):
        idx = int(len(deltas_sorted) * p)
        idx = min(idx, len(deltas_sorted) - 1)
        return deltas_sorted[idx]

    print(f"deltas entre ciclos consecutivos: n={len(deltas)}")
    print(f"  min={min(deltas):.3f}s p10={pct(0.10):.3f}s p25={pct(0.25):.3f}s "
          f"mediana={statistics.median(deltas):.3f}s p75={pct(0.75):.3f}s p90={pct(0.90):.3f}s "
          f"p99={pct(0.99):.3f}s max={max(deltas):.3f}s media={statistics.mean(deltas):.3f}s")

    # restrict to canonical window
    cyc_win = [t for t in cycle_epochs_ms if WINDOW_START <= t <= WINDOW_END]
    deltas_win = [cyc_win[i] - cyc_win[i - 1] for i in range(1, len(cyc_win))]
    deltas_win_sorted = sorted(deltas_win)

    def pct_w(p):
        idx = int(len(deltas_win_sorted) * p)
        idx = min(idx, len(deltas_win_sorted) - 1)
        return deltas_win_sorted[idx]

    print(f"\nciclos dentro de la ventana canonica: {len(cyc_win)}")
    if deltas_win:
        print(f"  min={min(deltas_win):.3f}s p10={pct_w(0.10):.3f}s p25={pct_w(0.25):.3f}s "
              f"mediana={statistics.median(deltas_win):.3f}s p75={pct_w(0.75):.3f}s p90={pct_w(0.90):.3f}s "
              f"p99={pct_w(0.99):.3f}s max={max(deltas_win):.3f}s media={statistics.mean(deltas_win):.3f}s")

    # duration span
    if cycle_epochs_ms:
        span = cycle_epochs_ms[-1] - cycle_epochs_ms[0]
        print(f"\nprimer ciclo: epoch {cycle_epochs_ms[0]:.3f} = {datetime.utcfromtimestamp(cycle_epochs_ms[0])}")
        print(f"ultimo ciclo: epoch {cycle_epochs_ms[-1]:.3f} = {datetime.utcfromtimestamp(cycle_epochs_ms[-1])}")
        print(f"span total: {span:.1f}s = {span/3600:.2f}h")
        print(f"ciclos teoricos a intervalo nominal 15.0s: {span/15.0:.1f}")
        print(f"ciclos medidos / ciclos teoricos: {len(cycle_epochs_ms)/(span/15.0):.4f}")

    OUT_SENT_OPEN_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_SENT_OPEN_JSON, "w", encoding="utf-8") as f:
        json.dump(sent_open_events, f)
    print(f"\nSENT OPEN events extraidos: {len(sent_open_events)} -> {OUT_SENT_OPEN_JSON}")
    from collections import Counter
    retcode_counts = Counter(e["retcode"] for e in sent_open_events)
    print("retcodes:", dict(retcode_counts))
    cfg_counts = Counter(e["config"] for e in sent_open_events)
    print("por config:", dict(cfg_counts))

    out_clamped_json = OUT_SENT_OPEN_JSON.parent / "sl_clamped_open_events.json"
    with open(out_clamped_json, "w", encoding="utf-8") as f:
        json.dump(sl_clamped_open_events, f)
    print(f"\nSL_CLAMPED OPEN events extraidos: {len(sl_clamped_open_events)} -> {out_clamped_json}")


if __name__ == "__main__":
    main()
