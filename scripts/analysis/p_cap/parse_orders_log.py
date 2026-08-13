r"""T0.6-B Bloque 3 pregunta 9 -- eventos del ejecutor (log de ordenes).

INVESTIGADOR REPORT-ONLY. Lee, en streaming (nunca entero en memoria),
`audit_ventana_SOLO_ORDENES.log` (204 KB, 1.710 lineas -- cabe entero, pero se procesa igual
linea a linea por uniformidad con el log grande). Extrae los eventos
OPEN_SKIPPED_SL_CROSSED, SL_CLAMPED (con y sin sufijo OPEN), FALLBACK_CLOSE_INVALID_SL,
ALARM, SAME_BAR_EXIT_FALLBACK, SENT OPEN/CLOSE/MODIFY, SAME, con su timestamp y los campos
numericos que lleve cada linea. Escribe una fila por evento a
`data/analysis/p_cap/eventos_ejecutor_902.csv`.

Convencion de reloj: los timestamps del log ya son hora de SERVIDOR en texto plano
("YYYY-MM-DD HH:MM:SS,mmm"), impresos por el propio ejecutor. No se aplica ninguna
conversion de zona horaria -- se parsean literalmente.
"""
from __future__ import annotations

import calendar
import csv
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FOREX")
LOG = ROOT / "data/entregas/2026-08-12-maquina2-tomachine-902/logs_ejecutor/audit_ventana_SOLO_ORDENES.log"
OUT_CSV = ROOT / "data/analysis/p_cap/eventos_ejecutor_902.csv"

WINDOW_START_STR = "2026-07-27 18:53:30"
WINDOW_END_STR = "2026-08-11 01:15:04"


def epoch(s: str) -> int:
    return calendar.timegm(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timetuple())


WINDOW_START = epoch(WINDOW_START_STR)
WINDOW_END = epoch(WINDOW_END_STR)

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) (\w+)\s+(.*)$")

NUM_FIELD_RE = re.compile(r"(\w+\$?)=(-?\d+(?:\.\d+)?)")

# Known event tags, searched anywhere in the line (not just the leading bracket) --
# some lines carry the event inside "actions: TAG/F1" rather than as the leading "[TAG]".
KNOWN_TAGS = [
    "OPEN_SKIPPED_SL_CROSSED",
    "SL_CLAMPED OPEN",
    "SL_CLAMPED",
    "FALLBACK_CLOSE_INVALID_SL",
    "ALARM",
    "SAME_BAR_EXIT_FALLBACK",
    "SENT OPEN",
    "SENT CLOSE",
    "SENT MODIFY",
]


def parse_line(line: str):
    m = TS_RE.match(line)
    if not m:
        return None
    date_s, ms, level, rest = m.groups()
    ts_epoch = epoch(date_s)
    tag = None
    bm = re.match(r"^\[([^\]]+)\]", rest)
    leading_bracket = bm.group(1) if bm else None
    if leading_bracket in KNOWN_TAGS:
        tag = leading_bracket
    else:
        # "actions:" summary lines carry the event as "actions: TAG/ficha" instead of
        # a leading bracket -- tag them distinctly so they are never confused with (nor
        # double-counted against) the primary per-event detail line.
        am = re.search(r"actions:\s*([A-Z_]+)/", rest)
        if am and am.group(1) in KNOWN_TAGS:
            tag = f"ACTIONS_SUMMARY:{am.group(1)}"
        elif leading_bracket is not None:
            tag = leading_bracket
        else:
            tag = "OTRO"
    fields = dict(NUM_FIELD_RE.findall(rest))
    # non-numeric key=value tokens (config=, ficha=, motivo=)
    kv = dict(re.findall(r"(\w+)=([^\s]+)", rest))
    retcode_m = re.search(r"retcode=(\d+)", rest)
    return {
        "timestamp_servidor": f"{date_s},{ms}",
        "epoch": ts_epoch,
        "level": level,
        "event": tag.strip(),
        "raw": rest.strip(),
        "fields_numeric": fields,
        "kv": kv,
        "retcode": retcode_m.group(1) if retcode_m else "",
    }


def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp_servidor", "epoch", "en_ventana_canonica", "level", "event",
        "config", "ficha", "ticket", "magic", "desired_sl", "desired", "ref", "clamped",
        "gap", "gap_usd", "sim_fill", "live_fill", "motivo", "bid", "retcode", "raw",
    ]
    n_total = 0
    n_in_window = 0
    counts_all = {}
    counts_window = {}
    with open(LOG, encoding="utf-8", errors="replace") as fin, open(
        OUT_CSV, "w", newline="", encoding="utf-8"
    ) as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        for line in fin:
            n_total += 1
            parsed = parse_line(line)
            if parsed is None:
                continue
            ev = parsed["event"]
            counts_all[ev] = counts_all.get(ev, 0) + 1
            in_window = WINDOW_START <= parsed["epoch"] <= WINDOW_END
            if in_window:
                n_in_window += 1
                counts_window[ev] = counts_window.get(ev, 0) + 1
            kv = parsed["kv"]
            fields = parsed["fields_numeric"]
            row = {
                "timestamp_servidor": parsed["timestamp_servidor"],
                "epoch": parsed["epoch"],
                "en_ventana_canonica": in_window,
                "level": parsed["level"],
                "event": ev,
                "config": kv.get("config", "") or (parsed["raw"].split("]", 1)[0].lstrip("[") if ev.startswith("ACTIONS_SUMMARY") else ""),
                "ficha": kv.get("ficha", ""),
                "ticket": kv.get("ticket", ""),
                "magic": kv.get("magic", ""),
                "desired_sl": fields.get("desired_sl", ""),
                "desired": fields.get("desired", ""),
                "ref": fields.get("ref", ""),
                "clamped": fields.get("clamped", ""),
                "gap": fields.get("gap", ""),
                "gap_usd": fields.get("gap$", ""),
                "sim_fill": fields.get("sim_fill", ""),
                "live_fill": fields.get("live_fill", ""),
                "motivo": kv.get("motivo", ""),
                "bid": fields.get("bid", ""),
                "retcode": parsed["retcode"],
                "raw": parsed["raw"],
            }
            writer.writerow(row)

    print(f"lineas totales en el fichero: {n_total}")
    print(f"lineas con timestamp+tag parseadas: {sum(counts_all.values())}")
    print(f"lineas en ventana canonica: {n_in_window}")
    print("\n=== conteo por evento (TODO el fichero, 2026-07-27 18:52:29 -> 2026-08-12 09:37:02) ===")
    for k in sorted(counts_all):
        print(f"  {k}: {counts_all[k]}")
    print("\n=== conteo por evento (SOLO ventana canonica 2026-07-27 18:53:30 -> 2026-08-11 01:15:04) ===")
    for k in sorted(counts_window):
        print(f"  {k}: {counts_window[k]}")
    print(f"\nCSV escrito: {OUT_CSV} ({OUT_CSV.stat().st_size} bytes, {n_total} filas de datos)")


if __name__ == "__main__":
    main()
