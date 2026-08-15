r"""T0.7-M-C -- Auditoria look-ahead del harness de backtest largo.

INVESTIGADOR REPORT-ONLY. Brief:
research/fases/F0-preparacion/02-specs/T0.7-M-C-brief-auditoria-lookahead-harness.md

No modifica `scripts/analysis/realtick_bt/backtest.py` ni ningun otro modulo
vivo (R1-bis, charter SS A.11): se importa read-only. `Ticks.first_at` (el
metodo bajo auditoria) NO se toca -- se caracteriza con datos sinteticos
(tests) y se ejecuta tal cual sobre el sustrato real (este script).

CLOCK CONVENTION (identica a backtest.py:15-26): todo epoch de este repo
codifica la hora de SERVIDOR del broker. Se decodifica SIEMPRE con
`datetime.utcfromtimestamp()` y se codifica con `calendar.timegm()`, nunca
`.fromtimestamp()`/`.timestamp()` (ambos re-aplican el offset local del host).

AMBIGUEDAD DECLARADA (pregunta 4/5 del brief, ver T0.7-M-C-progreso.md):
`_bars_M15.parquet` (sustrato de barras Capitaria del harness) solo cubre
hasta 2026-07-24 16:45:00, ANTES de la ventana pedida
2026-07-27 -> 2026-08-11. El harness NO PUEDE generar posiciones reales
(ENTRY/EXIT) en esa ventana por falta de barras -- no hay senal que
resolver. REJILLA DECLARADA: los dos call sites de first_at()
(backtest.py:353 y :383) SIEMPRE construyen su argumento como
"limite de vela M15 + BAR_SEC" (un cierre de vela: `bar_times[bi] + 900` o
`pos['t_out'] + 900`, y `pos['t_out']` es a su vez un `bar['t']`). Por eso
`decision_grid()` genera TODOS los cierres de vela M15 (multiplos de 900s)
de la ventana pedida y se les aplica `ticks.first_at()` directamente: esto
reproduce la FORMA EXACTA del argumento sin necesitar posiciones reales que
no existen por falta de barras.
"""
from __future__ import annotations

import calendar
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(r"D:\FOREX")
sys.path.insert(0, str(ROOT))

from scripts.analysis.realtick_bt.backtest import Ticks, BAR_SEC  # noqa: E402  (read-only import)

TICKDIR = ROOT / "data" / "lake_ticks" / "XAUUSD"
OUT_DIR = ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados" / "T0.7-p-cap"
EXCLUSIONES_AVA_PATH = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.3-continuidad" / "exclusiones-ava.json"
)
BACKTEST_LARGO_AVA_META_PATH = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.6-backtest-largo-ava" / "backtest-largo-ava.json"
)

# Ventana de medicion Q4/Q5 (hora servidor Capitaria).
WINDOW_T0 = float(calendar.timegm(datetime(2026, 7, 27).timetuple()))
WINDOW_T1 = float(calendar.timegm(datetime(2026, 8, 12).timetuple()))  # exclusivo

UMBRAL_60S = 60.0
UMBRAL_15MIN = 15 * 60.0
UMBRAL_1H = 3600.0


# --------------------------------------------------------------------- Q4: rejilla + medicion


def decision_grid(t0: float, t1: float, bar_sec: int = BAR_SEC) -> list[float]:
    """Rejilla DECLARADA (ver docstring del modulo): todos los cierres de
    vela M15 (multiplos de `bar_sec`) que caen en `[t0, t1)`."""
    if t1 <= t0:
        return []
    first_close = (int(t0) // bar_sec) * bar_sec
    if first_close < t0:
        first_close += bar_sec
    out: list[float] = []
    t = float(first_close)
    while t < t1:
        out.append(t)
        t += bar_sec
    return out


def medir_delays(ticks: Ticks, instantes: list[float]) -> list[dict[str, Any]]:
    """Para cada instante pedido, llama `ticks.first_at()` tal cual (sin
    tocarlo) y registra `t_devuelto - t_pedido`."""
    rows: list[dict[str, Any]] = []
    for t in instantes:
        e = ticks.first_at(t)
        if e is None:
            rows.append({"t_pedido": t, "t_devuelto": None, "delta_s": None, "evaluable": False})
        else:
            t_dev, bid, ask = e
            rows.append({
                "t_pedido": t, "t_devuelto": t_dev, "delta_s": t_dev - t,
                "evaluable": True,
            })
    return rows


def resumen_delays(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Distribucion de `delta_s` sobre las filas evaluables: n, p50, p90,
    p99, max, y cuantas superan 60s / 15min / 1h."""
    deltas = [r["delta_s"] for r in rows if r["evaluable"]]
    n_total = len(rows)
    n_eval = len(deltas)
    n_no_eval = n_total - n_eval
    if not deltas:
        return {
            "n_total": n_total, "n_evaluable": 0, "n_no_evaluable": n_no_eval,
            "p50": None, "p90": None, "p99": None, "max": None,
            "n_gt_60s": 0, "n_gt_15min": 0, "n_gt_1h": 0,
        }
    arr = np.array(deltas, dtype="float64")
    return {
        "n_total": n_total, "n_evaluable": n_eval, "n_no_evaluable": n_no_eval,
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "p99": float(np.percentile(arr, 99)),
        "max": float(arr.max()),
        "n_gt_60s": int((arr > UMBRAL_60S).sum()),
        "n_gt_15min": int((arr > UMBRAL_15MIN).sum()),
        "n_gt_1h": int((arr > UMBRAL_1H).sum()),
    }


# --------------------------------------------------------------------- Q5: clasificacion de huecos


def clasificar_hueco(t_pedido: float) -> str:
    """Clasifica un instante (hora servidor, SIEMPRE decodificado con
    `utcfromtimestamp`) como `fin_de_semana` / `corte_mantenimiento` / `otro`,
    segun los horarios MEDIDOS citados en el brief (gotchas): corte normal
    16:59-17:59 hora servidor; viernes 16:55-18:49."""
    d = datetime.utcfromtimestamp(t_pedido)
    wd = d.weekday()  # 0=lunes .. 5=sabado, 6=domingo
    if wd in (5, 6):
        return "fin_de_semana"
    minutos = d.hour * 60 + d.minute
    if wd == 4:  # viernes
        ini, fin = 16 * 60 + 55, 18 * 60 + 49
    else:
        ini, fin = 16 * 60 + 59, 17 * 60 + 59
    if ini <= minutos <= fin:
        return "corte_mantenimiento"
    return "otro"


# --------------------------------------------------------------------- Q3: barrido repo-wide (declarado a mano, ver progreso.md)


HALLAZGOS_REPO_WIDE = [
    {
        "file_line": "scripts/analysis/realtick_bt/backtest.py:353",
        "clase": "bt.Ticks.first_at (bajo auditoria)",
        "nota": "resolve(), entrada; argumento = bar_times[bi] + BAR_SEC",
    },
    {
        "file_line": "scripts/analysis/realtick_bt/backtest.py:383",
        "clase": "bt.Ticks.first_at (bajo auditoria)",
        "nota": "resolve(), salida fallback; argumento = pos['t_out'] + BAR_SEC",
    },
    {
        "file_line": "scripts/research/backtest_largo_ava.py (AvaTicks, clase completa)",
        "clase": "subclase de bt.Ticks -- first_at/range/_candidates HEREDADOS byte-identicos",
        "nota": "unico metodo sobrescrito es _load(); confirmado por lectura del modulo. "
                "Este es 'el motor de backtest largo' del brief; produjo F0-BT-LARGO-0001.",
    },
    {
        "file_line": "scripts/analysis/a6_pata_a/signal_level.py:90-133",
        "clase": "Ticks propia, reimplementacion independiente (mismo patron)",
        "nota": "NO es la clase del harness -- reimplementacion paralela para un analisis A6 distinto.",
    },
    {
        "file_line": "scripts/analysis/a6_pata_a/capa3_gate_spread.py:36-38,111-168",
        "clase": "importa Ticks/resolve de backtest.py (read-only)",
        "nota": "replica las dos llamadas de resolve() para instrumentar el gate de spread; "
                "analisis A6 aparte, no forma parte del harness del backtest largo.",
    },
    {
        "file_line": "scripts/analysis/a6_pata_a/exp_active_fichas.py:195",
        "clase": "instancia Ticks() (a confirmar import exacto)",
        "nota": "modulo A6, fuera del alcance de esta auditoria.",
    },
    {
        "file_line": "scripts/analysis/a6_pata_a/capa1_senal_cruda.py:389",
        "clase": "instancia Ticks() (a confirmar import exacto)",
        "nota": "modulo A6, fuera del alcance de esta auditoria.",
    },
    {
        "file_line": "tests/analysis/test_realtick_pairing.py:61-78",
        "clase": "Ticks propia en fixture de test",
        "nota": "reimplementacion independiente en un test, no es el harness.",
    },
    {
        "file_line": "sentinel_engine/ai/dossier.py:254, "
                     "sentinel_engine/opt/fast_replay.py:230,236,528,561, "
                     "sentinel_engine/service/routers/runs.py:81",
        "clase": "pandas Index.searchsorted, DESCARTADO",
        "nota": "lookup 'as-of' HACIA ATRAS sobre barras (side='right')-1), no acceso a ticks "
                "por instante hacia adelante -- no es la misma familia de riesgo.",
    },
]


# --------------------------------------------------------------------- driver (I/O real)


def _git_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ticks = Ticks()
    instantes = decision_grid(WINDOW_T0, WINDOW_T1, BAR_SEC)
    rows = medir_delays(ticks, instantes)
    resumen = resumen_delays(rows)

    clasif: dict[str, int] = {"fin_de_semana": 0, "corte_mantenimiento": 0, "otro": 0}
    ejemplos: dict[str, list[dict[str, Any]]] = {"fin_de_semana": [], "corte_mantenimiento": [], "otro": []}
    for r in rows:
        if not r["evaluable"] or r["delta_s"] is None or r["delta_s"] <= UMBRAL_60S:
            continue
        c = clasificar_hueco(r["t_pedido"])
        clasif[c] += 1
        if len(ejemplos[c]) < 5:
            ejemplos[c].append({
                "t_pedido_iso": datetime.utcfromtimestamp(r["t_pedido"]).isoformat(),
                "t_devuelto_iso": datetime.utcfromtimestamp(r["t_devuelto"]).isoformat(),
                "delta_s": r["delta_s"],
            })

    out = {
        "lineage": {
            "run_id": f"T0.7-M-C-auditoria-lookahead-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            "area": "F0", "experimento": "T0.7-M-C-auditoria-lookahead", "etapa": "F0",
            "git_sha": _git_sha(), "generador": "scripts/analysis/realtick_bt/auditoria_lookahead.py",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        "ventana": {
            "t0_iso": datetime.utcfromtimestamp(WINDOW_T0).isoformat(),
            "t1_iso": datetime.utcfromtimestamp(WINDOW_T1).isoformat(),
            "n_instantes_rejilla": len(instantes),
        },
        "resumen_delays": resumen,
        "clasificacion_gt_60s": clasif,
        "ejemplos_gt_60s": ejemplos,
        "hallazgos_repo_wide": HALLAZGOS_REPO_WIDE,
    }
    with (OUT_DIR / "auditoria_lookahead.json").open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, sort_keys=False)

    print(json.dumps({"resumen_delays": resumen, "clasificacion_gt_60s": clasif}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
