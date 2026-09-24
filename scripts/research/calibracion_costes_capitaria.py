r"""Calibracion del spread de Capitaria dentro de la ventana NY (T0.6 mod #10,
Paso 2a -- Artefacto 1).

Por que existe. D-21 es vinculante: los backtests sobre AVA usan precios de
AVA con un modelo de COSTES calibrado sobre Capitaria -- el spread nativo de
AVA (0.34-0.45) no se usa para veredictos porque es mas angosto que el de
Capitaria (0.50-0.60) y sesgaria todo resultado a favor de AVA. Este script
MIDE esa calibracion: la distribucion empirica del spread de Capitaria,
restringida a la ventana operativa vigente en la fecha de CADA tick, segun el
CALENDARIO DE PERIODOS de `scripts/research/ventana_calendario.py`
(D-36/D-37 revocan el borde fijo `18:00 -> 02:00` ET de D-34; el cierre
ahora es `02:00` o `03:00/03:15` ET segun el periodo), para que
`scripts/research/cost_overlay.py` pueda aplicarla despues a ticks de AVA.
REPORT-ONLY (charter SS B): este script no interpreta ni concluye, solo
calcula y persiste numeros.

🔴 La hora 2 NY entra en ventana SOLO en los periodos cuyo cierre es
`03:00`/`03:15`, y queda fuera en los que cierran a `02:00`. El predicado de
filtrado (`_ticks_en_ventana`) usa `ventana_calendario.in_ventana`, que
resuelve el periodo vigente por la FECHA del tick, no un offset fijo -- para
que la calibracion de la hora 2 no mezcle ticks de ambos regimenes (spread
estrecho del periodo donde esa hora esta en ventana, spread ancho del
periodo donde no lo esta).

R1-bis (charter SS A.11): NO modifica `scripts/analysis/realtick_bt/backtest.py`.
Reutiliza `bt.TICKDIR` para localizar los parquet de ticks; toda la logica de
este fichero es nueva, en `scripts/research/`.

🔴 NO modifica `scripts/research/ny_window.py` ni `scripts/research/ventana_calendario.py`:
ambos siguen vigentes (`ny_window.py` para otros consumidores; `ventana_calendario.py`
como fuente de verdad de la ventana periodizada que este script reutiliza).

HOLDOUT SELLADO (charter SS A.14 + D-31, acto 1): Capitaria
`2026-05-12 -> 2026-07-26` es intocable. Este script procesa DOS tramos
declarados de antemano que rodean el sello por construccion
(`[2026-01-01, 2026-05-12)` y `[2026-07-27, hoy)`) y lleva DOS guardas duras
por tramo: una ANTES de leer nada (aborta si el tramo declarado tocara el
sello) y otra DESPUES de cargar los ticks (aborta si, por un error de
particionado del parquet mensual, algun tick cargado cayera dentro del sello).
Ningun spread del tramo sellado entra jamas al histograma ni a los
percentiles.

Uso:  python -m scripts.research.calibracion_costes_capitaria
"""
from __future__ import annotations

import calendar
import json
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\FOREX")
OUT_DIR = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.6-overlay-costes"
)
OUT_PATH = OUT_DIR / "calibracion.json"

from scripts.analysis.realtick_bt import backtest as bt  # noqa: E402
from scripts.research.cost_overlay import (  # noqa: E402
    assert_fuera_holdout_capitaria,
    CAPITARIA_HOLDOUT_FIN,
    CAPITARIA_HOLDOUT_INI,
    horas_calendario,
)
from scripts.research.ny_window import server_epoch_to_ny  # noqa: E402
from scripts.research.ventana_calendario import cargar_calendario, in_ventana  # noqa: E402

BROKER = "capitaria"
# D-36/D-37 revocan el borde fijo 18:00->02:00 (D-34): la ventana operativa
# es un calendario de periodos fechado, no una tupla literal de horas -- ver
# `_ticks_en_ventana` (predicado `in_ventana`, fechado) y `main` (deriva las
# horas a calibrar de `horas_calendario(calendario)`, no de una lista escrita
# a mano).
CALENDARIO_PATH = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.13-ventana-ny" / "calendario-ventana.json"
)
RESOLUCION_HISTOGRAMA = 0.01

# Dos tramos declarados de antemano que rodean el holdout por construccion.
SEG1_INI = calendar.timegm(datetime(2026, 1, 1).timetuple())
SEG1_FIN = CAPITARIA_HOLDOUT_INI  # 2026-05-12, exclusivo
SEG2_INI = CAPITARIA_HOLDOUT_FIN  # 2026-07-27
SEG2_FIN = calendar.timegm(datetime(2026, 8, 13).timetuple())  # exclusivo, > ultimo tick conocido


def _months_in_range(ini: float, fin: float) -> list[str]:
    d0 = datetime.utcfromtimestamp(ini)
    d1 = datetime.utcfromtimestamp(fin)
    out = []
    y, m = d0.year, d0.month
    while (y, m) <= (d1.year, d1.month):
        out.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _load_segment(ini: float, fin: float) -> pd.DataFrame:
    """Carga ticks (t, bid, ask) de bt.TICKDIR para [ini, fin), recorta por t
    exacto. Guarda dura ANTES de tocar disco: aborta si [ini, fin) tocara el
    holdout sellado."""
    assert_fuera_holdout_capitaria(ini, fin)

    frames = []
    for ym in _months_in_range(ini, fin):
        p = bt.TICKDIR / f"{ym}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p, columns=["t_msc", "bid", "ask"])
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["t", "bid", "ask"])
    df = pd.concat(frames, ignore_index=True)
    t = df["t_msc"].to_numpy() / 1000.0
    mask = (t >= ini) & (t < fin)
    out = df.loc[mask, ["bid", "ask"]].copy()
    out["t"] = t[mask]

    # Guarda dura DESPUES de cargar: ningun tick cargado puede caer en el sello.
    intrusos = out[(out["t"] >= CAPITARIA_HOLDOUT_INI) & (out["t"] < CAPITARIA_HOLDOUT_FIN)]
    if len(intrusos):
        raise SystemExit(
            f"ABORTADO: {len(intrusos)} ticks cargados caen dentro del holdout "
            "sellado (SS A.14 + D-31). No se escribio ningun artefacto."
        )
    return out.sort_values("t").reset_index(drop=True)


def _ticks_en_ventana(
    t: np.ndarray, broker: str, calendario: dict
) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve `(dentro, horas_ny)` para un array de epochs `t` (convencion
    `backtest.py`). `dentro[i]` es True si el tick `i` cae dentro de la
    ventana operativa VIGENTE EN SU PROPIA FECHA, segun `calendario`
    (`ventana_calendario.in_ventana`, D-36/D-37) -- sustituye el predicado
    fijo `ny_window.in_ny_window` (D-34, revocado por D-36). El mismo valor
    de hora (p.ej. la 2 NY) puede dar veredictos opuestos segun la fecha del
    tick: dentro en los periodos que cierran a las 03:00/03:15, fuera en los
    que cierran a las 02:00. Mezclar ambos regimenes al calibrar
    contaminaria el numero con ticks de spread ancho (fuera de ventana) que
    no corresponden a ninguna condicion real de operacion."""
    dts_ny = [server_epoch_to_ny(float(x), broker) for x in t]
    dentro = np.array([in_ventana(d, calendario) for d in dts_ny], dtype=bool)
    horas = np.array([d.hour for d in dts_ny], dtype=int)
    return dentro, horas


def _stats(spread: np.ndarray) -> dict:
    if spread.size == 0:
        return {"n": 0}
    pcts = np.percentile(spread, [5, 25, 50, 75, 95])
    return {
        "n": int(spread.size),
        "p5": round(float(pcts[0]), 6),
        "p25": round(float(pcts[1]), 6),
        "mediana": round(float(pcts[2]), 6),
        "p75": round(float(pcts[3]), 6),
        "p95": round(float(pcts[4]), 6),
        "media": round(float(spread.mean()), 6),
        "std": round(float(spread.std(ddof=0)), 6),
    }


def _git_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def main() -> int:
    calendario = cargar_calendario(CALENDARIO_PATH)
    horas_ventana = horas_calendario(calendario)

    seg1 = _load_segment(SEG1_INI, SEG1_FIN)
    seg2 = _load_segment(SEG2_INI, SEG2_FIN)
    df = pd.concat([seg1, seg2], ignore_index=True).sort_values("t").reset_index(drop=True)
    if df.empty:
        raise SystemExit("ningun tick cargado en ninguno de los dos tramos -- abortando")

    dentro, horas = _ticks_en_ventana(df["t"].to_numpy(), BROKER, calendario)
    ventana = df.loc[dentro].copy()
    ventana["hora_ny"] = horas[dentro]
    ventana["mes"] = ventana["t"].map(lambda t: datetime.utcfromtimestamp(t).strftime("%Y-%m"))

    if ventana.empty:
        raise SystemExit("ningun tick cae dentro de la ventana NY -- abortando")

    spread = (ventana["ask"] - ventana["bid"]).to_numpy()
    spread_r = np.round(spread, 2)

    # Histograma a resolucion 0.01.
    valores, cuentas = np.unique(spread_r, return_counts=True)
    histograma = {f"{v:.2f}": int(c) for v, c in zip(valores, cuentas)}

    n_050 = int((spread_r == 0.50).sum())
    n_060 = int((spread_r == 0.60).sum())
    n_total = int(spread_r.size)

    por_hora = {}
    for h in horas_ventana:
        sub = spread[ventana["hora_ny"].to_numpy() == h]
        por_hora[str(h)] = _stats(sub)

    por_mes = {}
    for mes, sub in ventana.groupby("mes"):
        s = (sub["ask"] - sub["bid"]).to_numpy()
        por_mes[mes] = _stats(s)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resultado = {
        "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_sha": _git_sha(),
        "substrate_id": "capitaria-ticks-2026-preholdout-y-postholdout",
        "sustrato": "data/lake_ticks/XAUUSD/ (ticks reales Capitaria)",
        "tramos_medidos": [
            [datetime.utcfromtimestamp(SEG1_INI).strftime("%Y-%m-%d"),
             datetime.utcfromtimestamp(SEG1_FIN).strftime("%Y-%m-%d")],
            [datetime.utcfromtimestamp(SEG2_INI).strftime("%Y-%m-%d"),
             datetime.utcfromtimestamp(SEG2_FIN).strftime("%Y-%m-%d")],
        ],
        "holdout_excluido": [
            datetime.utcfromtimestamp(CAPITARIA_HOLDOUT_INI).strftime("%Y-%m-%d"),
            datetime.utcfromtimestamp(CAPITARIA_HOLDOUT_FIN).strftime("%Y-%m-%d"),
        ],
        "ventana_ny": (
            "calendario de periodos fechado (D-36/D-37), apertura 18:00 ET fija, "
            "cierre 02:00/03:00/03:15 ET segun el periodo vigente en la fecha del tick"
        ),
        "calendario_usado": str(CALENDARIO_PATH),
        "calendario_generado": calendario.get("generado"),
        "calendario_git_sha": calendario.get("git_sha"),
        "horas_cubiertas": list(horas_ventana),
        "resolucion_histograma": RESOLUCION_HISTOGRAMA,
        "n_ticks_totales_cargados": int(len(df)),
        "n_ticks_dentro_ventana": n_total,
        "global": _stats(spread),
        "histograma": histograma,
        "bimodalidad_050_060": {
            "n_spread_050": n_050,
            "n_spread_060": n_060,
            "pct_spread_050": round(100.0 * n_050 / n_total, 4) if n_total else None,
            "pct_spread_060": round(100.0 * n_060 / n_total, 4) if n_total else None,
        },
        "por_hora": por_hora,
        "por_mes": por_mes,
    }
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, sort_keys=False, indent=2, ensure_ascii=False, allow_nan=False)

    print(f"n_ticks_dentro_ventana: {n_total:,}")
    print(f"global: {resultado['global']}")
    print(f"bimodalidad 0.50/0.60: {resultado['bimodalidad_050_060']}")
    for h in horas_ventana:
        print(f"  hora {h:>2d} ET: {por_hora[str(h)]}")
    for mes in sorted(por_mes):
        print(f"  mes {mes}: {por_mes[mes]}")
    print(f"\nartefacto: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
