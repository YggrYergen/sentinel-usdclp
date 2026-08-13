r"""T0.6-B Bloque 3 pregunta 10 -- empareja cada apertura real (Bloque 1) con la linea
[SENT OPEN] retcode=10009 del log grande mas cercana en el tiempo, para el mismo config.

INVESTIGADOR REPORT-ONLY. Lee `data/analysis/p_cap/verdad_terreno_902.csv` (Bloque 1,
152 filas, ya construido por build_positions.py) y
`data/analysis/p_cap/sent_open_events.json` (171 eventos [SENT OPEN], ya extraidos por
scan_big_log.py del log grande). No vuelve a tocar el log de 69,7 MB.

El log NO imprime ticket para las aperturas (solo config + magic + retcode), asi que el
emparejamiento es por (config, cercania temporal) -- no hay clave exacta disponible. Se
declara asi explicitamente, y se reporta la distribucion de desfases, no una tasa falsa de
certeza.
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(r"D:\FOREX")
POSITIONS_CSV = ROOT / "data/analysis/p_cap/verdad_terreno_902.csv"
SENT_OPEN_JSON = ROOT / "data/analysis/p_cap/sent_open_events.json"
SL_CLAMPED_OPEN_JSON = ROOT / "data/analysis/p_cap/sl_clamped_open_events.json"

STRATEGY_TO_CONFIG = {
    "SAR::S6-K2P0": "S6-K2P0",
    "SuperTrend::SuperTrend-p14x3-M15": "SuperTrend-p14x3-M15",
}


def main():
    with open(POSITIONS_CSV, encoding="utf-8") as f:
        positions = list(csv.DictReader(f))
    with open(SENT_OPEN_JSON, encoding="utf-8") as f:
        events = json.load(f)

    for e in events:
        e["t"] = e["epoch"] + e["ms"] / 1000.0

    success_events = [e for e in events if e["retcode"] == "10009"]
    by_config = {}
    for e in success_events:
        by_config.setdefault(e["config"], []).append(e)
    for cfg in by_config:
        by_config[cfg].sort(key=lambda e: e["t"])

    used = {cfg: [False] * len(lst) for cfg, lst in by_config.items()}

    matched = []
    unmatched = []
    for p in positions:
        strat = p["strategy_id"]
        cfg = STRATEGY_TO_CONFIG.get(strat)
        t_open = int(p["t_open_epoch"])
        candidates = by_config.get(cfg, [])
        best_idx = None
        best_dt = None
        for i, e in enumerate(candidates):
            dt = e["t"] - t_open
            if best_dt is None or abs(dt) < abs(best_dt):
                best_dt = dt
                best_idx = i
        if best_idx is None:
            unmatched.append((p, None))
        else:
            matched.append((p, candidates[best_idx], best_dt))
            used[cfg][best_idx] = True

    print(f"posiciones totales: {len(positions)}")
    print(f"posiciones con al menos un evento SENT OPEN(retcode=10009) del mismo config en todo el log: {len(matched)}")
    print(f"posiciones SIN ningun evento SENT OPEN(retcode=10009) del mismo config en todo el log: {len(unmatched)}")

    offsets = [abs(dt) for _, _, dt in matched]
    offsets_sorted = sorted(offsets)
    if offsets_sorted:
        print("\ndistribucion de |desfase| (segundos) entre t_open (deals_raw) y el SENT OPEN exitoso mas cercano:")
        print(f"  min={min(offsets_sorted):.3f} p25={offsets_sorted[len(offsets_sorted)//4]:.3f} "
              f"mediana={statistics.median(offsets_sorted):.3f} p75={offsets_sorted[(3*len(offsets_sorted))//4]:.3f} "
              f"p90={offsets_sorted[int(len(offsets_sorted)*0.9)]:.3f} max={max(offsets_sorted):.3f}")

    for thr in [1, 5, 15, 30, 60, 120]:
        n = sum(1 for o in offsets if o <= thr)
        print(f"  emparejadas con |desfase| <= {thr}s: {n} / {len(positions)} ({100*n/len(positions):.1f}%)")

    print("\ncasos SIN evento SENT OPEN(retcode=10009) del mismo config en TODO el log:")
    for p, _ in unmatched:
        print(f"  position_id={p['position_id']} strategy={p['strategy_id']} t_open={p['t_open_servidor']}")

    print("\ncasos con desfase > 120s (peor emparejamiento, listados):")
    for p, e, dt in matched:
        if abs(dt) > 120:
            print(f"  position_id={p['position_id']} strategy={p['strategy_id']} t_open={p['t_open_servidor']} "
                  f"evento_mas_cercano_epoch={e['t']:.3f} desfase={dt:+.3f}s")

    for cfg, lst in by_config.items():
        n_unused = sum(1 for u in used[cfg] if not u)
        print(f"\nconfig={cfg}: eventos SENT OPEN(retcode=10009) totales={len(lst)}, "
              f"usados en algun emparejamiento={sum(used[cfg])}, sobrantes(no asignados a ninguna posicion como 'mas cercano')={n_unused}")

    # ---------- SL efectivamente enviado ----------
    print("\n=== SL con el que se mando cada apertura (solo recuperable cuando hubo clamp) ===")
    with open(SL_CLAMPED_OPEN_JSON, encoding="utf-8") as f:
        clamped_events = json.load(f)
    for e in clamped_events:
        e["t"] = e["epoch"] + e["ms"] / 1000.0
    clamped_by_config = {}
    for e in clamped_events:
        clamped_by_config.setdefault(e["config"], []).append(e)

    n_with_clamp_sl = 0
    n_without_any_sl = 0
    rows_out = []
    for p, ev, dt in matched:
        strat = p["strategy_id"]
        cfg = STRATEGY_TO_CONFIG.get(strat)
        t_open = int(p["t_open_epoch"])
        cand = clamped_by_config.get(cfg, [])
        # a SL_CLAMPED OPEN belongs to this position's send attempt if it happened at/just
        # before the matched successful SENT OPEN timestamp, within the same cycle (<=1s)
        near = [c for c in cand if 0 <= (ev["t"] - c["t"]) <= 1.0]
        if near:
            near.sort(key=lambda c: ev["t"] - c["t"])
            best = near[0]
            n_with_clamp_sl += 1
            rows_out.append((p["position_id"], strat, "CLAMPED", best["clamped"], best["desired"], best["gap"]))
        else:
            n_without_any_sl += 1
            rows_out.append((p["position_id"], strat, "NO_LOGUEADO", "", "", ""))

    print(f"aperturas con SL recuperable del log (hubo SL_CLAMPED OPEN en la misma ventana de <=1s antes del SENT OPEN exitoso): {n_with_clamp_sl}")
    print(f"aperturas SIN SL recuperable del log (no hubo clamp; el SENT OPEN no imprime el SL): {n_without_any_sl}")
    print("\nprimeras 10 filas de detalle:")
    for r in rows_out[:10]:
        print(" ", r)

    out_csv = ROOT / "data/analysis/p_cap/sl_enviado_por_apertura.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["position_id", "strategy_id", "sl_status", "sl_clamped_enviado", "sl_desired_original", "gap"])
        w.writerows(rows_out)
    print(f"\nCSV auxiliar escrito: {out_csv} ({out_csv.stat().st_size} bytes, {len(rows_out)} filas)")


if __name__ == "__main__":
    main()
