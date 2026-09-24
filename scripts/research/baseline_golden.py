"""Tarea 0 de T0.6 -- LINEA BASE GOLDEN de S6 / S7 / SuperTrend.

Por que existe: D-22 autorizo las 12 modificaciones de motor con una condicion
explicita del user -- "cada modificacion exige re-verificacion de paridad antes
de pasar a la siguiente" -- y el charter SS A.5 exige "suite golden + fidelidad
empirica A6 tras CADA modificacion". Verificado el 2026-08-11 (artefactos en
04-resultados/T0.6-recon/): esa puerta NO EXISTE para este codigo. tests/golden/
cubre el motor de SCORING (sentinel_engine.engine.Engine), no simular_variant ni
el harness real-tick. Sin una linea base congelada, la condicion del user es
inejecutable y R1-bis es una promesa sin test que la pruebe. Esto la construye.

🔴 R1-bis (charter SS A.11): este script NO modifica nada. Importa
scripts.analysis.realtick_bt.backtest y reutiliza sus funciones tal cual; las
estrategias vivas y el harness quedan byte-identicos. La unica libertad que se
toma es FILTRAR la lista de barras antes de pasarla a build_all(), que ya recibe
`bars` como argumento -- por eso no hace falta tocar backtest.py.

🔴 HOLDOUT SAGRADO (charter SS A.14 + D-31): el acto 1 sella Capitaria
2026-05-12 -> 2026-07-26. backtest.py no tiene filtro de fechas, asi que
correrlo tal cual leeria bid/ask del tramo sellado. Este driver corta las barras
en HOLDOUT_INI y ademas verifica DESPUES que ninguna posicion resuelta termine
dentro del sello -- si alguna lo hace, ABORTA y no escribe nada.

Sustrato: ticks reales de Capitaria (data/lake_ticks/XAUUSD/). Las barras M15
llegan solo hasta 2026-07-24 16:45 (pipeline de barras desatendido), asi que el
tramo utilizable pre-holdout es 2026-01-01 -> 2026-05-11.

Uso:  python -m scripts.research.baseline_golden
"""
from __future__ import annotations

import calendar
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FOREX")
OUT_DIR = ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados" / "T0.6-baseline"

# D-31 acto 1: Capitaria 2026-05-12 -> 2026-07-26, intocable (SS A.14).
HOLDOUT_INI = calendar.timegm(datetime(2026, 5, 12).timetuple())
HOLDOUT_FIN = calendar.timegm(datetime(2026, 7, 27).timetuple())  # exclusivo

from scripts.analysis.realtick_bt import backtest as bt  # noqa: E402


def _git_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _fmt(t: float) -> str:
    # server wall clock -- utcfromtimestamp, NUNCA fromtimestamp (backtest.py:15-26)
    return datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    bars_all = bt.load_bars()
    bars = [b for b in bars_all if b["t"] < HOLDOUT_INI]
    if not bars:
        raise SystemExit("ninguna barra fuera del holdout -- abortando")

    print(f"barras totales   : {len(bars_all):,}  {_fmt(bars_all[0]['t'])} .. {_fmt(bars_all[-1]['t'])}")
    print(f"barras usadas    : {len(bars):,}  {_fmt(bars[0]['t'])} .. {_fmt(bars[-1]['t'])}")
    print(f"holdout excluido : {_fmt(HOLDOUT_INI)} .. {_fmt(HOLDOUT_FIN)}  (D-31 acto 1)")
    print(f"descartadas por holdout: {len(bars_all) - len(bars):,} barras\n")

    ticks = bt.Ticks()
    resolved = bt.build_all(ticks, bars)

    # Guarda dura: ninguna posicion puede tocar el tramo sellado.
    intrusas = [
        (sid, r) for sid, rows in resolved.items() for r in rows
        if r["t_exit"] >= HOLDOUT_INI or r["t_in_exec"] >= HOLDOUT_INI
    ]
    if intrusas:
        for sid, r in intrusas[:5]:
            print(f"  INTRUSA {sid}: in={_fmt(r['t_in_exec'])} exit={_fmt(r['t_exit'])}")
        raise SystemExit(
            f"ABORTADO: {len(intrusas)} posiciones tocan el holdout sellado (SS A.14). "
            "No se escribio ningun artefacto."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    git_sha = _git_sha()
    resumen = {}

    for sid, rows in sorted(resolved.items()):
        m = bt.metrics(rows, bt.LOT_GRID)
        resumen[sid] = m
        # Filas ordenadas de forma determinista y con TODAS las claves: es la
        # huella contra la que se comparara tras cada modificacion de motor.
        filas = sorted(
            ({k: (round(v, 10) if isinstance(v, float) else v) for k, v in sorted(r.items())}
             for r in rows),
            key=lambda r: (r["t_in_exec"], r["t_exit"]),
        )
        path = OUT_DIR / f"posiciones_{sid}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(filas, f, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False)
        print(f"{sid:24s} n={m['n']:4d}  net={m['net']:>14,.2f}  wr={m['wr']}  pf={m['pf']}  maxdd={m['maxdd']:>12,.2f}")

    meta = {
        "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_sha": git_sha,
        "substrate_id": "capitaria-ticks-2026-preholdout",
        "sustrato": "data/lake_ticks/XAUUSD/ (ticks reales Capitaria)",
        "barras": "data/lake_ticks/XAUUSD/_bars_M15.parquet",
        "ventana_barras": [_fmt(bars[0]["t"]), _fmt(bars[-1]["t"])],
        "n_barras": len(bars),
        "holdout_excluido": [_fmt(HOLDOUT_INI), _fmt(HOLDOUT_FIN)],
        "lot": bt.LOT_GRID,
        "estrategias": bt.STRATS,
        "metricas": resumen,
        "nota": "Linea base congelada para la puerta de paridad de D-22. "
                "Toda modificacion de motor se compara contra posiciones_*.json.",
    }
    with (OUT_DIR / "baseline.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    print(f"\nartefactos en {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
