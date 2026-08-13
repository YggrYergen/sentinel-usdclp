r"""T0.6-B -- verdad de terreno de la cuenta 902, posicion a posicion.

INVESTIGADOR REPORT-ONLY. Solo lee `research.db` de la entrega de maquina 2, en modo
`mode=ro`. No escribe nada fuera de `data/analysis/p_cap/` y stdout.

Convencion de reloj (obligatoria, ver research/motores/FAULTY-tomachine-902.md y
scripts/analysis/realtick_bt/backtest.py:15-26): `deals_raw.time` es un epoch MT5 que YA
codifica la hora de SERVIDOR. La unica conversion correcta a datetime es
`datetime.utcfromtimestamp()` (offset cero). PROHIBIDA cualquier conversion de zona horaria
adicional (`.fromtimestamp()`, `astimezone()`, etc). Los limites de la ventana canonica se
codifican al reves con `calendar.timegm()` sobre la cadena literal "YYYY-MM-DD HH:MM:SS",
que es la funcion inversa exacta.

reason de MT5: 0=CLIENT(manual) 1=MOBILE 2=WEB 3=EXPERT 4=SL 5=TP 6=SO
"""
from __future__ import annotations

import calendar
import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FOREX")
DB = ROOT / "data/entregas/2026-08-12-maquina2-tomachine-902/repo/data/research.db"
OUT_DIR = ROOT / "data/analysis/p_cap"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_START_STR = "2026-07-27 18:53:30"
WINDOW_END_STR = "2026-08-11 01:15:04"


def epoch(s: str) -> int:
    return calendar.timegm(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timetuple())


def fmt(e: int) -> str:
    return datetime.utcfromtimestamp(e).strftime("%Y-%m-%d %H:%M:%S")


WINDOW_START = epoch(WINDOW_START_STR)
WINDOW_END = epoch(WINDOW_END_STR)

REASON_NAMES = {0: "CLIENT_manual", 1: "MOBILE", 2: "WEB", 3: "EXPERT", 4: "SL", 5: "TP", 6: "SO"}


def connect():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def load_all_deals(con):
    cur = con.cursor()
    cur.execute(
        "SELECT ticket, position_id, symbol, side, volume, price, profit, magic, time, "
        "entry_type, origin, strategy_id, variant_id, leverage, contract_size, comment, reason "
        "FROM deals_raw ORDER BY time"
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows


def load_position_spread(con):
    cur = con.cursor()
    cur.execute(
        "SELECT position_id, ticket_open, spread_open, spread_open_min, spread_open_ts, "
        "spread_close, spread_close_ts FROM position_spread"
    )
    cols = [d[0] for d in cur.description]
    return {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}


def main():
    con = connect()
    all_deals = load_all_deals(con)
    pspread = load_position_spread(con)

    print(f"=== VENTANA CANONICA ===")
    print(f"inicio literal: {WINDOW_START_STR} -> epoch {WINDOW_START}")
    print(f"fin literal:    {WINDOW_END_STR} -> epoch {WINDOW_END}")
    print(f"total filas deals_raw (sin filtro): {len(all_deals)}")

    # Exclude balance deals globally (position_id=0, symbol empty) -- documented as first 2 rows
    balance_deals = [d for d in all_deals if d["position_id"] == 0 and d["symbol"] == ""]
    print(f"\n=== DEALS DE BALANCE (excluidos de todo calculo de PnL) ===")
    for d in balance_deals:
        print(d["ticket"], d["position_id"], d["symbol"], d["profit"], d["time"], fmt(d["time"]))

    non_balance = [d for d in all_deals if not (d["position_id"] == 0 and d["symbol"] == "")]

    in_window = [d for d in non_balance if WINDOW_START <= d["time"] <= WINDOW_END]
    print(f"\n=== DEALS EN VENTANA (time BETWEEN inicio Y fin, ambos inclusive; sin balance) ===")
    print(f"total: {len(in_window)}")
    by_entry = {}
    for d in in_window:
        by_entry.setdefault(d["entry_type"], 0)
        by_entry[d["entry_type"]] += 1
    print("por entry_type:", by_entry)

    # Build position_id -> {IN: deal, OUT: deal(s)} using ALL non-balance deals (not just in-window)
    # so we can detect cross-boundary orphans.
    pos_map: dict[int, dict[str, list[dict]]] = {}
    for d in non_balance:
        pos_map.setdefault(d["position_id"], {"IN": [], "OUT": []})
        pos_map[d["position_id"]][d["entry_type"]].append(d)

    # Positions with an IN inside the window
    positions_open_in_window = {
        pid for pid, m in pos_map.items() if any(WINDOW_START <= d["time"] <= WINDOW_END for d in m["IN"])
    }
    # Positions with an OUT inside the window
    positions_close_in_window = {
        pid for pid, m in pos_map.items() if any(WINDOW_START <= d["time"] <= WINDOW_END for d in m["OUT"])
    }

    print(f"\n=== CONTEO DE POSICIONES (definicion: posicion = position_id con >=1 deal IN o OUT dentro de la ventana) ===")
    all_pids_touching_window = positions_open_in_window | positions_close_in_window
    print(f"position_id distintos que tocan la ventana: {len(all_pids_touching_window)}")
    print(f"con IN dentro de la ventana: {len(positions_open_in_window)}")
    print(f"con OUT dentro de la ventana: {len(positions_close_in_window)}")
    print(f"con IN y OUT ambos dentro de la ventana: {len(positions_open_in_window & positions_close_in_window)}")
    print(f"con IN dentro pero SIN OUT en absoluto (abiertas al final, o sin OUT en toda la tabla): "
          f"{len({p for p in positions_open_in_window if not pos_map[p]['OUT']})}")
    print(f"con IN dentro pero OUT fuera de la ventana (cierre despues del fin de ventana): "
          f"{len([p for p in positions_open_in_window if pos_map[p]['OUT'] and not any(WINDOW_START <= d['time'] <= WINDOW_END for d in pos_map[p]['OUT'])])}")
    print(f"con OUT dentro pero IN fuera de la ventana (apertura antes del inicio de ventana): "
          f"{len([p for p in positions_close_in_window if pos_map[p]['IN'] and not any(WINDOW_START <= d['time'] <= WINDOW_END for d in pos_map[p]['IN'])])}")
    print(f"con OUT dentro pero SIN IN en absoluto (huerfano total): "
          f"{len({p for p in positions_close_in_window if not pos_map[p]['IN']})}")

    # Enumerate the specific orphan cases
    print("\n--- Detalle: IN dentro de ventana, OUT fuera de ventana (o inexistente) ---")
    for p in sorted(positions_open_in_window):
        m = pos_map[p]
        outs_in_win = [d for d in m["OUT"] if WINDOW_START <= d["time"] <= WINDOW_END]
        if not outs_in_win:
            if m["OUT"]:
                for d in m["OUT"]:
                    print(f"  pid={p} IN@{fmt(m['IN'][0]['time'])} OUT fuera@{fmt(d['time'])} ticket={d['ticket']} strategy={d['strategy_id']}")
            else:
                ind = m["IN"][0]
                print(f"  pid={p} IN@{fmt(ind['time'])} ticket={ind['ticket']} strategy={ind['strategy_id']} comment={ind['comment']} volume={ind['volume']} -- SIN OUT EN TODA LA TABLA (abierta)")

    print("\n--- Detalle: OUT dentro de ventana, IN fuera de ventana (o inexistente) ---")
    for p in sorted(positions_close_in_window):
        m = pos_map[p]
        ins_in_win = [d for d in m["IN"] if WINDOW_START <= d["time"] <= WINDOW_END]
        if not ins_in_win:
            if m["IN"]:
                for d in m["IN"]:
                    print(f"  pid={p} IN fuera@{fmt(d['time'])} ticket={d['ticket']} strategy={d['strategy_id']}")
            else:
                outd = m["OUT"][0]
                print(f"  pid={p} SIN IN EN TODA LA TABLA. OUT@{fmt(outd['time'])} ticket={outd['ticket']} strategy={outd['strategy_id']} profit={outd['profit']} reason={outd['reason']}")

    con.close()


if __name__ == "__main__":
    main()
