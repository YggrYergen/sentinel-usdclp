r"""B11 -- localizacion de los huecos intradia del lago AVA, para EXCLUIRLOS.

Por que existe: D-33 (2026-08-12) cerro B11 por la via de la exclusion en vez de
la reparacion. Para excluir un hueco hay que saber donde esta, asi que esto lo
localiza y emite la lista de intervalos excluidos que consumira el backtest largo.

Lo que este script NO hace, por decision del user (D-33): clasificar los huecos
contra un calendario de festivos, y rellenarlos desde Capitaria en el solape.

🔴 HOLDOUT (charter SS A.14 + D-31): lee UNICAMENTE la columna `t_msc`. Nunca
bid/ask. D-31 declara explicitamente que leer solo t_msc para auditorias de
continuidad no constituye exploracion del sustrato.

Medicion clave que dimensiona el problema real: el sistema solo opera en la
ventana 18:00 -> 02:00 hora de Nueva York (T0.13). Un hueco que cae entero en la
zona muerta no afecta a ningun backtest. Por eso se reporta, para cada hueco, su
solape EN HORAS con la ventana operativa, y ese es el numero que cuenta.

Reloj: AVA = UTC fijo sin DST (T0.13, medido con el corte de CME como ancla).
Nueva York = UTC-5 en invierno, UTC-4 en DST (2do domingo de marzo -> 1er domingo
de noviembre).

Uso:  python research/fases/F0-preparacion/04-resultados/T0.3-continuidad/huecos_intradia_ava.py
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq

LAKE = Path(r"D:\FOREX\data\lake_ticks_ava\GOLD")
OUT = Path(__file__).resolve().parent

# Convencion de la medicion previa (bitacora 2026-08-12), reproducida para
# validar el instrumento: hueco = >90 min y <2800 min (ni cierre diario ~62 min
# ni fin de semana ~2941 min).
MIN_GAP_S = 90 * 60
MAX_GAP_S = 2800 * 60

# D-31: holdout AVA = ano 2023 completo.
HOLDOUT = (datetime(2023, 1, 1), datetime(2024, 1, 1))
# Solape con el lago de Capitaria (sustrato de A6 Pata B).
SOLAPE = (datetime(2026, 1, 1), datetime(2026, 8, 13))


def _dst_us(d: datetime) -> bool:
    """DST de EEUU: 2do domingo de marzo -> 1er domingo de noviembre."""
    y = d.year
    mar = datetime(y, 3, 1)
    ini = mar + timedelta(days=(6 - mar.weekday()) % 7 + 7)   # 2do domingo
    nov = datetime(y, 11, 1)
    fin = nov + timedelta(days=(6 - nov.weekday()) % 7)       # 1er domingo
    return ini <= d < fin


def _ny(d: datetime) -> datetime:
    return d - timedelta(hours=4 if _dst_us(d) else 5)


def _en_ventana(d_ny: datetime) -> bool:
    """Ventana operativa: 18:00 <= hora_NY < 02:00. Cruza medianoche -> DISYUNCION."""
    return d_ny.hour >= 18 or d_ny.hour < 2


def solape_ventana_horas(ini: datetime, fin: datetime) -> float:
    """Horas del intervalo [ini, fin) que caen dentro de la ventana NY.

    Se resuelve por barrido de minutos: el intervalo mayor del lago es de ~20 h,
    asi que el coste es trivial y evita errores de aritmetica de bordes con DST.
    """
    total = 0
    t = ini.replace(second=0, microsecond=0)
    while t < fin:
        if _en_ventana(_ny(t)):
            total += 1
        t += timedelta(minutes=1)
    return total / 60.0


def main() -> int:
    L: list[str] = []

    def p(s: str = "") -> None:
        print(s)
        L.append(s)

    meses = sorted(LAKE.glob("*.parquet"))
    p("B11 -- HUECOS INTRADIA DEL LAGO AVA (para exclusion, D-33)")
    p(f"generado: {datetime.utcnow().isoformat(timespec='seconds')}Z")
    p(f"lago    : {LAKE}  ({len(meses)} meses)")
    p(f"criterio: hueco = >{MIN_GAP_S // 60} min y <{MAX_GAP_S // 60} min")
    p("lectura : SOLO columna t_msc (holdout-safe, D-31)")
    p("")

    huecos: list[dict] = []
    prev_t: float | None = None
    n_ticks = 0

    for m in meses:
        col = pq.read_table(m, columns=["t_msc"]).column("t_msc").to_numpy()
        n_ticks += len(col)
        if len(col) == 0:
            continue
        ts = col / 1000.0
        if prev_t is not None:
            d = ts[0] - prev_t
            if MIN_GAP_S < d < MAX_GAP_S:
                huecos.append({"ini": prev_t, "fin": float(ts[0]), "seg": float(d),
                               "mes": m.stem, "cruza_mes": True})
        diffs = ts[1:] - ts[:-1]
        idx = ((diffs > MIN_GAP_S) & (diffs < MAX_GAP_S)).nonzero()[0]
        for i in idx:
            huecos.append({"ini": float(ts[i]), "fin": float(ts[i + 1]),
                           "seg": float(diffs[i]), "mes": m.stem, "cruza_mes": False})
        prev_t = float(ts[-1])

    p(f"ticks leidos: {n_ticks:,}")
    p(f"huecos encontrados: {len(huecos)}   total {sum(h['seg'] for h in huecos) / 3600:,.1f} h")
    p("")

    # Enriquecer: fechas, solape con la ventana operativa, con holdout y con el solape Capitaria.
    for h in huecos:
        a, b = datetime.utcfromtimestamp(h["ini"]), datetime.utcfromtimestamp(h["fin"])
        h["ini_utc"], h["fin_utc"] = a.strftime("%Y-%m-%d %H:%M:%S"), b.strftime("%Y-%m-%d %H:%M:%S")
        h["horas"] = h["seg"] / 3600.0
        h["horas_en_ventana"] = solape_ventana_horas(a, b)
        h["en_holdout"] = HOLDOUT[0] <= a < HOLDOUT[1]
        h["en_solape_capitaria"] = SOLAPE[0] <= a < SOLAPE[1]

    dentro = [h for h in huecos if h["horas_en_ventana"] > 0]
    p("=" * 78)
    p("DIMENSION REAL DEL PROBLEMA -- solape con la ventana operativa 18:00->02:00 NY")
    p("=" * 78)
    p(f"huecos que tocan la ventana : {len(dentro)} de {len(huecos)}")
    p(f"horas totales de hueco      : {sum(h['horas'] for h in huecos):,.1f} h")
    p(f"horas DENTRO de la ventana  : {sum(h['horas_en_ventana'] for h in huecos):,.1f} h")
    p(f"horas en zona muerta (irrelevantes): "
      f"{sum(h['horas'] - h['horas_en_ventana'] for h in huecos):,.1f} h")
    p("")

    p("=" * 78)
    p("EPISODIOS ORDENADOS POR HORAS DENTRO DE LA VENTANA")
    p("=" * 78)
    p(f"{'inicio UTC':20s} {'fin UTC':20s} {'horas':>7s} {'en_vent':>8s}  {'holdout':>7s} {'solape':>7s}")
    for h in sorted(huecos, key=lambda x: -x["horas_en_ventana"]):
        p(f"{h['ini_utc']:20s} {h['fin_utc']:20s} {h['horas']:>7.1f} {h['horas_en_ventana']:>8.1f}"
          f"  {'SI' if h['en_holdout'] else '-':>7s} {'SI' if h['en_solape_capitaria'] else '-':>7s}")
    p("")

    p("=" * 78)
    p("AGREGADO POR MES (solo meses con huecos)")
    p("=" * 78)
    por_mes: dict[str, list[dict]] = {}
    for h in huecos:
        por_mes.setdefault(h["mes"], []).append(h)
    p(f"{'mes':8s} {'n':>3s} {'horas':>8s} {'en_ventana':>11s} {'mayor':>8s}")
    for mes in sorted(por_mes):
        hs = por_mes[mes]
        p(f"{mes:8s} {len(hs):>3d} {sum(x['horas'] for x in hs):>8.1f} "
          f"{sum(x['horas_en_ventana'] for x in hs):>11.1f} {max(x['horas'] for x in hs):>8.1f}")
    p("")

    p("=" * 78)
    p("CRUCES CRITICOS")
    p("=" * 78)
    hd = [h for h in huecos if h["en_holdout"]]
    hs_ = [h for h in huecos if h["en_solape_capitaria"]]
    p(f"huecos en el HOLDOUT (AVA 2023): {len(hd)}  "
      f"total {sum(h['horas'] for h in hd):.1f} h  en ventana {sum(h['horas_en_ventana'] for h in hd):.1f} h")
    for h in hd:
        p(f"   {h['ini_utc']} -> {h['fin_utc']}  {h['horas']:.1f} h (en ventana {h['horas_en_ventana']:.1f} h)")
    p(f"huecos en el SOLAPE con Capitaria (A6 Pata B): {len(hs_)}  "
      f"total {sum(h['horas'] for h in hs_):.1f} h  en ventana {sum(h['horas_en_ventana'] for h in hs_):.1f} h")
    for h in hs_:
        p(f"   {h['ini_utc']} -> {h['fin_utc']}  {h['horas']:.1f} h (en ventana {h['horas_en_ventana']:.1f} h)")

    (OUT / "huecos-intradia-ava-2026-08-12.txt").write_text("\n".join(L) + "\n", encoding="utf-8")

    # Artefacto consumible: los intervalos a EXCLUIR del backtest (D-33), que son
    # exclusivamente los que tocan la ventana operativa.
    excl = [{"ini_utc": h["ini_utc"], "fin_utc": h["fin_utc"],
             "ini_epoch": h["ini"], "fin_epoch": h["fin"],
             "horas": round(h["horas"], 3), "horas_en_ventana": round(h["horas_en_ventana"], 3),
             "mes": h["mes"]}
            for h in sorted(dentro, key=lambda x: x["ini"])]
    with (OUT / "exclusiones-ava.json").open("w", encoding="utf-8") as f:
        json.dump({
            "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "decision": "D-33",
            "criterio": f">{MIN_GAP_S // 60} min y <{MAX_GAP_S // 60} min, con solape > 0 con la ventana 18:00-02:00 NY",
            "reloj_ava": "UTC fijo sin DST (T0.13)",
            "n_intervalos": len(excl),
            "horas_excluidas_en_ventana": round(sum(h["horas_en_ventana"] for h in dentro), 3),
            "intervalos": excl,
        }, f, indent=1, ensure_ascii=False)

    print(f"\nartefactos: {OUT / 'huecos-intradia-ava-2026-08-12.txt'}")
    print(f"            {OUT / 'exclusiones-ava.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
