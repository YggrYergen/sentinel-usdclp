r"""PASO 0 -- semantica de maxDD y peak_margin en el harness real-tick.

Por que existe: la linea base golden (commit bd17f60) produjo los primeros
numeros reales de S6/S7/SuperTrend del programa. Antes de propagarlos al
backtest largo hay que saber QUE MIDEN exactamente dos de sus columnas, porque
si la semantica esta mal el error se multiplica sobre 3,5 anos.

Dos preguntas del user (2026-08-12):
  1. Que mide maxDD? S6 da 73,8 MM sobre una cuenta de 50 MM -- imposible en una
     cuenta real, que se habria liquidado antes.
  2. Por que S6 y S7 pican EXACTAMENTE el mismo margen (19.516.812,09, al centimo)
     con 633 y 717 posiciones?

Este script NO interpreta: mide y vuelca. La lectura esta en el TRACKER y en
D-32. Report-only, solo lectura, no toca ningun artefacto de la linea base.

R1-bis (charter SS A.11): no modifica backtest.py ni las estrategias. Solo lee
los JSON de posiciones ya congelados y re-implementa las formulas del harness
para poder contrastar variantes de desempate.

Uso:  python research/fases/F0-preparacion/04-resultados/T0.6-baseline/semantica_metricas.py
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

D = Path(__file__).resolve().parent

# Constantes del harness -- backtest.py:46-50, 465. Se re-declaran para que este
# script sea auditable sin importar el harness (y no pueda alterarlo).
LOT = 0.67          # backtest.py:465  LOT_GRID
USDCLP = 936.50     # backtest.py:48
LEVERAGE = 100.0    # backtest.py:49
CONTRACT = 100.0    # backtest.py:50  oz por lote 1.0

SIDS = ["S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"]


def f(t: float) -> str:
    # reloj de servidor -- utcfromtimestamp, NUNCA fromtimestamp (backtest.py:15-26)
    return datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def margen(r: dict) -> float:
    """backtest.py:391 -- margin1 = CONTRACT * entry_fill * USDCLP / LEVERAGE."""
    return CONTRACT * r["entry_fill"] * USDCLP / LEVERAGE * LOT


def maxdd_realizado(rows: list[dict]) -> float:
    """Replica exacta de backtest.py:423-427.

    Ordena por t_exit y acumula net1*lot. Es pico-a-valle de la curva de P&L
    CERRADO. No hay saldo inicial, ni equity, ni P&L flotante de las posiciones
    abiertas en cada instante.
    """
    cum = peak = mdd = 0.0
    for r in sorted(rows, key=lambda r: r["t_exit"]):
        cum += r["net1"] * LOT
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
    return mdd


def curva_margen(rows: list[dict], abre_primero: bool):
    """peak_margin con desempate configurable a igual timestamp.

    backtest.py:404 ordena por (t, -delta): a igual instante las APERTURAS
    cuentan antes que los CIERRES. Un stop_and_reverse cierra N fichas y abre N
    en el mismo segundo, asi que bajo ese desempate el instante del reverse
    cuenta 2N simultaneas. abre_primero=False mide el desempate contrario.
    """
    ev = []
    for i, r in enumerate(rows):
        m = margen(r)
        ev.append((r["t_in_exec"], +m, +1, i))
        ev.append((r["t_exit"], -m, -1, i))
    ev.sort(key=lambda x: (x[0], -x[1] if abre_primero else x[1]))
    cur = peak = 0.0
    n = nmax = 0
    abiertas: set[int] = set()
    pico = None
    for t, d, s, i in ev:
        cur += d
        n += s
        abiertas.add(i) if s > 0 else abiertas.discard(i)
        nmax = max(nmax, n)
        if cur > peak:
            peak = cur
            pico = (t, sorted(abiertas))
    return peak, nmax, pico


def main() -> int:
    L: list[str] = []
    def p(s: str = "") -> None:
        print(s)
        L.append(s)

    p("SEMANTICA DE maxDD Y peak_margin -- linea base golden T0.6 Tarea 0")
    p(f"generado: {datetime.utcnow().isoformat(timespec='seconds')}Z")
    p(f"fuente  : {D}  (posiciones_*.json, commit bd17f60)")
    p(f"lote={LOT}  USDCLP={USDCLP}  LEVERAGE={LEVERAGE}  CONTRACT={CONTRACT}")
    p("")

    p("=" * 78)
    p("P1 -- QUE MIDE maxDD")
    p("=" * 78)
    p("Codigo: backtest.py:423-427. Ordena las posiciones por t_exit, acumula")
    p("net1*lot y toma el maximo pico-a-valle. Es la curva de P&L CERRADO.")
    p("Grep sobre todo scripts/analysis/realtick_bt/ de: equity, balance,")
    p("margin_call, free_margin, liquidat, capital, INITIAL -> CERO ocurrencias")
    p("funcionales. No existe saldo de cuenta en el simulador.")
    p("margin1 (backtest.py:391) se calcula pero solo se REPORTA: ninguna")
    p("apertura se rechaza por margen, no hay margin call ni liquidacion.")
    p("")

    datos = {}
    for sid in SIDS:
        rows = json.loads((D / f"posiciones_{sid}.json").read_text(encoding="utf-8"))
        datos[sid] = rows
        net = sum(r["net1"] * LOT for r in rows)
        p(f"{sid:24s} n={len(rows):4d}  net={net:>16,.2f}  maxdd_realizado={maxdd_realizado(rows):>16,.2f}")
    p("")
    p("Consecuencia medible: maxDD NO incluye el flotante de las posiciones")
    p("abiertas, luego es una COTA INFERIOR del drawdown de equity, no una")
    p("medida de supervivencia. Cuantificar el drawdown de equity real exige el")
    p("camino intra-posicion (MFE/MAE), que es la modificacion de motor #11 y")
    p("todavia no existe -> NO EVALUABLE con la instrumentacion actual.")
    p("")

    p("=" * 78)
    p("P2 -- POR QUE S6 Y S7 PICAN EL MISMO MARGEN")
    p("=" * 78)
    for sid in SIDS:
        rows = datos[sid]
        pa, ca, pico = curva_margen(rows, True)
        pb, cb, _ = curva_margen(rows, False)
        p(f"\n{sid}")
        p(f"  desempate del harness (aperturas primero): peak={pa:>16,.2f}  max_simultaneas={ca}")
        p(f"  desempate contrario   (cierres primero)  : peak={pb:>16,.2f}  max_simultaneas={cb}")
        t, idx = pico
        p(f"  instante del pico: {f(t)}  ({len(idx)} posiciones contadas)")
        for i in idx:
            r = rows[i]
            p(f"    in={f(r['t_in_exec'])} out={f(r['t_exit'])} {r['side']:5s} "
              f"entry_fill={r['entry_fill']:>9.3f} ficha={r.get('ficha')} reason={r.get('reason')}")
        ins = Counter(r["t_in_exec"] for r in rows)
        outs = Counter(r["t_exit"] for r in rows)
        p(f"  fichas por instante de apertura: {dict(Counter(ins.values()))}")
        p(f"  instantes con cierre Y apertura simultaneos: {len(set(ins) & set(outs))}")

    s6 = {(r["t_in_exec"], r["entry_fill"], r["side"]) for r in datos["S6-K2P0"]}
    s7 = {(r["t_in_exec"], r["entry_fill"], r["side"]) for r in datos["S7-TPNONE"]}
    p("")
    p("Entradas S6 vs S7 (clave = t_in_exec + entry_fill + side):")
    p(f"  unicas S6={len(s6)}  unicas S7={len(s7)}  interseccion={len(s6 & s7)}")
    p(f"  solo en S6={len(s6 - s7)}   solo en S7={len(s7 - s6)}")
    p("")

    p("=" * 78)
    p("ROM RECALCULADO CON EL MARGEN SOSTENIDO (cierres primero)")
    p("=" * 78)
    p(f"{'estrategia':24s} {'net':>16s} {'ROM harness':>13s} {'ROM sostenido':>15s}")
    for sid in SIDS:
        rows = datos[sid]
        net = sum(r["net1"] * LOT for r in rows)
        pa, _, _ = curva_margen(rows, True)
        pb, _, _ = curva_margen(rows, False)
        p(f"{sid:24s} {net:>16,.2f} {100 * net / pa:>12.2f}% {100 * net / pb:>14.2f}%")

    (D / "semantica-metricas.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nartefacto: {D / 'semantica-metricas.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
