r"""T0.6-B Bloque 1, 2 y 4 -- tabla posicion a posicion + concurrencia + distribucion horaria.

INVESTIGADOR REPORT-ONLY. Lee `research.db` (modo `mode=ro`) de la entrega de maquina 2.
Construye la tabla de posiciones de la ventana canonica y responde, con calculo de codigo,
las preguntas 1-8, 13 y 14 de T0.6-B. Escribe
`data/analysis/p_cap/verdad_terreno_902.csv`.

Convencion de reloj: ver docstring de build_verdad_terreno.py. `datetime.utcfromtimestamp()`
exclusivamente; PROHIBIDA cualquier conversion de zona horaria.
"""
from __future__ import annotations

import calendar
import csv
import json
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FOREX")
DB = ROOT / "data/entregas/2026-08-12-maquina2-tomachine-902/repo/data/research.db"
OUT_CSV = ROOT / "data/analysis/p_cap/verdad_terreno_902.csv"

WINDOW_START_STR = "2026-07-27 18:53:30"
WINDOW_END_STR = "2026-08-11 01:15:04"

REASON_NAMES = {0: "CLIENT_manual", 1: "MOBILE", 2: "WEB", 3: "EXPERT", 4: "SL", 5: "TP", 6: "SO"}


def epoch(s: str) -> int:
    return calendar.timegm(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timetuple())


def fmt(e) -> str:
    if e is None:
        return ""
    return datetime.utcfromtimestamp(e).strftime("%Y-%m-%d %H:%M:%S")


WINDOW_START = epoch(WINDOW_START_STR)
WINDOW_END = epoch(WINDOW_END_STR)


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
    return [dict(zip(cols, r)) for r in cur.fetchall()]


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
    con.close()

    non_balance = [d for d in all_deals if not (d["position_id"] == 0 and d["symbol"] == "")]

    pos_map: dict[int, dict[str, list[dict]]] = {}
    for d in non_balance:
        pos_map.setdefault(d["position_id"], {"IN": [], "OUT": []})
        pos_map[d["position_id"]][d["entry_type"]].append(d)

    positions_open_in_window = sorted(
        pid for pid, m in pos_map.items() if any(WINDOW_START <= d["time"] <= WINDOW_END for d in m["IN"])
    )

    rows = []
    for pid in positions_open_in_window:
        m = pos_map[pid]
        d_in = m["IN"][0]
        outs = m["OUT"]
        d_out = outs[0] if outs else None
        sp = pspread.get(pid)
        t_open = d_in["time"]
        t_close = d_out["time"] if d_out else None
        duration = (t_close - t_open) if t_close is not None else None
        rows.append(
            {
                "position_id": pid,
                "strategy_id": d_in["strategy_id"],
                "comment": d_in["comment"],
                "magic": d_in["magic"],
                "side": d_in["side"],
                "volume": d_in["volume"],
                "ticket_in": d_in["ticket"],
                "t_open_epoch": t_open,
                "t_open_servidor": fmt(t_open),
                "precio_open": d_in["price"],
                "ticket_out": d_out["ticket"] if d_out else "",
                "t_close_epoch": t_close if t_close is not None else "",
                "t_close_servidor": fmt(t_close) if t_close is not None else "",
                "precio_close": d_out["price"] if d_out else "",
                "reason_code": d_out["reason"] if d_out else "",
                "reason_name": REASON_NAMES.get(d_out["reason"], "?") if d_out else "ABIERTA_AL_CIERRE_VENTANA",
                "profit": d_out["profit"] if d_out else "",
                "origin_out": d_out["origin"] if d_out else "",
                "duration_seconds": duration if duration is not None else "",
                "cerrada_fuera_de_ventana": bool(d_out and not (WINDOW_START <= d_out["time"] <= WINDOW_END)),
                "spread_open": sp["spread_open"] if sp else "",
                "spread_open_min": sp["spread_open_min"] if sp else "",
                "spread_close": sp["spread_close"] if sp else "",
                "position_spread_disponible": sp is not None,
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"CSV escrito: {OUT_CSV} ({OUT_CSV.stat().st_size} bytes, {len(rows)} filas)")

    # ---------- Q2: conteo ----------
    print("\n=== Q2: conteo de posiciones ===")
    print(f"total posiciones (IN dentro de ventana inclusive en ambos bordes): {len(rows)}")
    closed = [r for r in rows if r["t_close_epoch"] != ""]
    open_at_end = [r for r in rows if r["t_close_epoch"] == "" or r["cerrada_fuera_de_ventana"]]
    print(f"con OUT (cualquiera): {len(closed)}")
    print(f"sin OUT en absoluto (abiertas al final del dataset): {len([r for r in rows if r['t_close_epoch']=='' ])}")
    print(f"con OUT pero fuera de la ventana (abiertas al cierre de la ventana canonica): {len([r for r in rows if r['cerrada_fuera_de_ventana']])}")
    closes_in_window = [r for r in rows if r["t_close_epoch"] != "" and not r["cerrada_fuera_de_ventana"]]
    print(f"cierres DENTRO de la ventana: {len(closes_in_window)}")
    reason_counts = defaultdict(int)
    for r in closes_in_window:
        reason_counts[r["reason_name"]] += 1
    print("reparto de cierres-en-ventana por reason:", dict(reason_counts))
    net_all = sum(r["profit"] for r in closes_in_window if isinstance(r["profit"], (int, float)))
    print(f"neto (solo cierres dentro de ventana): {net_all:,.2f}")
    net_all_deals = sum(r["profit"] for r in closed if isinstance(r["profit"], (int, float)))
    print(f"neto (todos los OUT emparejados a un IN-en-ventana, incluido el que cierra fuera): {net_all_deals:,.2f}")

    # ---------- Q4: magic=0 ----------
    print("\n=== Q4: magic=0 dentro de la ventana ===")
    magic0_in = [d for d in non_balance if WINDOW_START <= d["time"] <= WINDOW_END and d["magic"] == 0]
    print(f"deals con magic=0 en ventana: {len(magic0_in)}")
    attributed = [d for d in magic0_in if d["strategy_id"] is not None]
    unattributed = [d for d in magic0_in if d["strategy_id"] is None]
    print(f"atribuidos via strategy_id: {len(attributed)}")
    print(f"NO atribuidos: {len(unattributed)}")
    for d in unattributed:
        print("  ", d)

    # ---------- Q5: concurrencia maxima por estrategia ----------
    print("\n=== Q5: concurrencia maxima por estrategia (linea temporal real IN/OUT) ===")
    by_strategy = defaultdict(list)
    for r in rows:
        by_strategy[r["strategy_id"]].append(r)

    for strat, plist in by_strategy.items():
        events = []
        for r in plist:
            events.append((r["t_open_epoch"], 1, r["position_id"]))
            if r["t_close_epoch"] != "":
                events.append((r["t_close_epoch"], -1, r["position_id"]))
            # positions still open past window end: no close event added (still open)
        events.sort(key=lambda x: (x[0], -x[1]))  # opens before closes at same instant
        cur = 0
        max_conc = 0
        max_intervals = []
        active = set()
        interval_start = None
        for t, delta, pid in events:
            prev = cur
            if delta == 1:
                active.add(pid)
            else:
                active.discard(pid)
            cur += delta
            if cur > max_conc:
                max_conc = cur
        # find intervals where concurrency == max_conc (only meaningful if max_conc>1)
        if max_conc > 1:
            active2 = {}
            timeline = []
            for r in plist:
                timeline.append((r["t_open_epoch"], "open", r["position_id"]))
                if r["t_close_epoch"] != "":
                    timeline.append((r["t_close_epoch"], "close", r["position_id"]))
            timeline.sort(key=lambda x: (x[0], 0 if x[1] == "open" else 1))
            open_set = {}
            level = 0
            for t, kind, pid in timeline:
                if kind == "open":
                    level += 1
                    open_set[pid] = t
                    if level == max_conc:
                        start_t = t
                else:
                    if level == max_conc:
                        max_intervals.append((start_t, t, sorted(open_set.keys())))
                    level -= 1
                    open_set.pop(pid, None)
        print(f"  {strat}: max concurrencia = {max_conc} (sobre {len(plist)} posiciones)")
        for iv in max_intervals:
            print(f"      intervalo {fmt(iv[0])} -> {fmt(iv[1])} position_ids={iv[2]}")

    # ---------- Q6: re-entradas secuenciales ----------
    print("\n=== Q6: re-entradas secuenciales (mismo strategy_id, cierre seguido de apertura) ===")
    reentry_gaps = defaultdict(list)
    for strat, plist in by_strategy.items():
        plist_sorted = sorted(plist, key=lambda r: r["t_open_epoch"])
        for i in range(1, len(plist_sorted)):
            prev = plist_sorted[i - 1]
            cur_r = plist_sorted[i]
            if prev["t_close_epoch"] == "":
                continue
            gap = cur_r["t_open_epoch"] - prev["t_close_epoch"]
            same_dir = prev["side"] == cur_r["side"]
            reentry_gaps[strat].append((gap, same_dir, prev["position_id"], cur_r["position_id"]))

    for strat, gaps in reentry_gaps.items():
        vals = [g[0] for g in gaps]
        same_dir_count = sum(1 for g in gaps if g[1])
        diff_dir_count = sum(1 for g in gaps if not g[1])
        neg_gap = sum(1 for g in gaps if g[0] < 0)
        print(f"  {strat}: n={len(gaps)} misma_direccion={same_dir_count} distinta_direccion={diff_dir_count} gap<0(solape)={neg_gap}")
        if vals:
            svals = sorted(vals)
            print(
                f"     gap segundos: min={min(svals)} p25={svals[len(svals)//4]} mediana={statistics.median(svals)} "
                f"p75={svals[(3*len(svals))//4]} max={max(svals)} media={statistics.mean(svals):.1f}"
            )

    # ---------- Q7: agrupacion por barra M15 de apertura ----------
    print("\n=== Q7: posiciones por barra M15 de apertura, por estrategia ===")
    for strat, plist in by_strategy.items():
        bar_counts = defaultdict(int)
        for r in plist:
            bar_start = (r["t_open_epoch"] // 900) * 900
            bar_counts[bar_start] += 1
        dist = defaultdict(int)
        for bar, n in bar_counts.items():
            dist[n] += 1
        print(f"  {strat}: distribucion {{posiciones_por_barra: n_barras}} = {dict(sorted(dist.items()))}")
        multi = {fmt(b): n for b, n in bar_counts.items() if n > 1}
        if multi:
            print(f"     barras con >1 posicion: {multi}")

    # ---------- Q8: tiempo con posicion abierta vs plana ----------
    print("\n=== Q8: tiempo con posicion abierta vs plana, por estrategia (% de la ventana) ===")
    window_len = WINDOW_END - WINDOW_START
    strat_busy_intervals = {}
    for strat, plist in by_strategy.items():
        intervals = []
        for r in plist:
            t0 = max(r["t_open_epoch"], WINDOW_START)
            t1 = min(r["t_close_epoch"], WINDOW_END) if r["t_close_epoch"] != "" else WINDOW_END
            if t1 > t0:
                intervals.append((t0, t1))
        intervals.sort()
        merged = []
        for iv in intervals:
            if merged and iv[0] <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], iv[1]))
            else:
                merged.append(list(iv))
        merged = [tuple(x) for x in merged]
        busy = sum(b - a for a, b in merged)
        strat_busy_intervals[strat] = merged
        pct_busy = 100.0 * busy / window_len
        print(f"  {strat}: ocupado={busy}s ({pct_busy:.2f}%) plano={window_len-busy}s ({100-pct_busy:.2f}%)")

    # both flat at once
    strats = list(strat_busy_intervals.keys())
    if len(strats) == 2:
        a_int = strat_busy_intervals[strats[0]]
        b_int = strat_busy_intervals[strats[1]]

        def union(intervals):
            merged = []
            for iv in sorted(intervals):
                if merged and iv[0] <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], iv[1]))
                else:
                    merged.append(list(iv))
            return [tuple(x) for x in merged]

        both_busy_union = union(a_int + b_int)
        either_busy_time = sum(b - a for a, b in both_busy_union)
        both_flat_time = window_len - either_busy_time
        print(
            f"  AMBAS planas a la vez: {both_flat_time}s "
            f"({100.0*both_flat_time/window_len:.2f}% de la ventana)"
        )

    # ---------- Q13: distribucion horaria ----------
    print("\n=== Q13: distribucion por hora de servidor (0-23) -- DATO PURO ===")
    open_hour = defaultdict(int)
    close_hour_reason = defaultdict(lambda: defaultdict(int))
    profit_hour = defaultdict(float)
    for r in rows:
        h = datetime.utcfromtimestamp(r["t_open_epoch"]).hour
        open_hour[h] += 1
    for r in closes_in_window:
        h = datetime.utcfromtimestamp(r["t_close_epoch"]).hour
        close_hour_reason[h][r["reason_name"]] += 1
        if isinstance(r["profit"], (int, float)):
            profit_hour[h] += r["profit"]
    print("aperturas por hora:")
    for h in range(24):
        print(f"  {h:02d}: {open_hour.get(h,0)}")
    print("cierres por hora y reason:")
    for h in range(24):
        if h in close_hour_reason:
            print(f"  {h:02d}: {dict(close_hour_reason[h])}")
    print("suma profit por hora de cierre:")
    for h in range(24):
        if h in profit_hour:
            print(f"  {h:02d}: {profit_hour[h]:,.2f}")

    # ---------- Q14: primera y ultima apertura por dia ----------
    print("\n=== Q14: primera y ultima apertura de cada dia de la ventana (hora de servidor) ===")
    by_day = defaultdict(list)
    for r in rows:
        day = datetime.utcfromtimestamp(r["t_open_epoch"]).strftime("%Y-%m-%d")
        by_day[day].append(r["t_open_epoch"])
    for day in sorted(by_day):
        times = sorted(by_day[day])
        print(f"  {day}: primera={fmt(times[0])} ultima={fmt(times[-1])} n_aperturas={len(times)}")


if __name__ == "__main__":
    main()
