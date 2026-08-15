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
import csv
import json
import subprocess
import sys
import time as time_module
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
    16:59-17:59 hora servidor; viernes 16:55-18:49.

    CORREGIDO tras hallazgo empirico (medicion real T0.7-M-C, ventana
    2026-07-27..08-11): los instantes de viernes DESPUES de las 18:49 (fin
    del corte ampliado) devuelven el MISMO tick de reapertura dominical que
    los de sabado/domingo -- es la cola continua del mismo cierre semanal,
    no un hueco aparte. Se clasifican como `fin_de_semana`, no `otro`."""
    d = datetime.utcfromtimestamp(t_pedido)
    wd = d.weekday()  # 0=lunes .. 5=sabado, 6=domingo
    if wd in (5, 6):
        return "fin_de_semana"
    minutos = d.hour * 60 + d.minute
    if wd == 4:  # viernes
        ini, fin = 16 * 60 + 55, 18 * 60 + 49
        if minutos > fin:
            return "fin_de_semana"  # cola continua del cierre semanal
        if minutos >= ini:
            return "corte_mantenimiento"
        return "otro"
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
        "file_line": "scripts/analysis/a6_pata_a/exp_active_fichas.py:195,112",
        "clase": "bt.Ticks + bt.resolve (importados de backtest.py, sin copiar)",
        "nota": "instancia Ticks() en :195 y la pasa a resolve(p, ticks, bar_times) importado "
                "de backtest.py en :112 -- llama a los MISMOS backtest.py:353/:383, desde otro "
                "caller. Confirmado: import 'from scripts.analysis.realtick_bt.backtest import "
                "(...)' en la cabecera del modulo.",
    },
    {
        "file_line": "scripts/analysis/a6_pata_a/capa1_senal_cruda.py:389,390",
        "clase": "bt.Ticks + bt.run_supertrend (importados de backtest.py, sin copiar)",
        "nota": "instancia Ticks() en :389 y la pasa a run_supertrend(cap_bars, st_ticks) en "
                ":390. run_supertrend() usa SOLO ticks.range(t0,t1) (backtest.py:313), NUNCA "
                "first_at() -- range() esta acotado por los dos argumentos que recibe, no hace "
                "busqueda hacia adelante sin cota. DESCARTADO de la familia de riesgo de first_at.",
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


# --------------------------------------------------------------------- Q6: AVA / F0-BT-LARGO-0001


def cargar_intervalos_exclusion_ava() -> list[tuple[float, float]]:
    """Carga `exclusiones-ava.json` (D-33) y devuelve la lista de
    `(ini_epoch, fin_epoch)`. NO decide nada sobre ellos -- solo los expone
    para el cruce del Q6."""
    with EXCLUSIONES_AVA_PATH.open("r", encoding="utf-8") as f:
        d = json.load(f)
    return [(iv["ini_epoch"], iv["fin_epoch"]) for iv in d["intervalos"]]


def en_algun_intervalo(t: float, intervalos: list[tuple[float, float]]) -> bool:
    return any(ini <= t < fin for ini, fin in intervalos)


def medir_q6_ava(modo: str = "mediana") -> dict[str, Any]:
    """Reproduce las llamadas GENUINAS de `ticks.first_at()` que el motor de
    backtest largo hace de verdad al correr sobre AVA (no una rejilla
    aproximada): instrumenta `AvaTicks` (subclase que solo registra el
    argumento antes de delegar a `super().first_at()`, sin tocar
    `backtest_largo_ava.py` ni `backtest.py`) y corre `bt.build_all()` sobre
    los `bars_final` reales del propio pipeline de
    `scripts/research/backtest_largo_ava.py` (mismas funciones, mismos
    ficheros de config -- ese script SI se lee, no se edita)."""
    from scripts.analysis.realtick_bt import backtest as bt
    from scripts.research import backtest_largo_ava as blav
    from scripts.research import cost_overlay as co
    from scripts.research import ventana_calendario as vc

    class _AvaTicksInstrumentado(blav.AvaTicks):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.llamadas: list[float] = []

        def first_at(self, t_sec: float):
            self.llamadas.append(t_sec)
            return super().first_at(t_sec)

    calendario = vc.cargar_calendario(co.CALENDARIO_PATH)
    calib = co.cargar_calibracion(blav.CALIBRACION_PATH)
    horas_ventana = co.horas_calendario(calendario)
    excl_raw = blav.cargar_exclusiones(blav.EXCLUSIONES_PATH)
    intervalos_bars = [(iv["ini_epoch"], iv["fin_epoch"]) for iv in excl_raw["intervalos"]]

    bars_all = blav.load_bars_ava()
    bars_ventana = vc.filter_bars(bars_all, "ava", calendario)
    bars_final = blav.filter_exclusiones(bars_ventana, intervalos_bars)

    ticks = _AvaTicksInstrumentado(calib, modo, horas_ventana)
    t0 = time_module.time()
    resolved = bt.build_all(ticks, bars_final)
    tiempo_s = time_module.time() - t0

    llamadas = ticks.llamadas
    # medir_delays() vuelve a invocar first_at() -- se usa una instancia
    # NUEVA (sin instrumentar) para no duplicar el registro de `llamadas`.
    ticks_medicion = blav.AvaTicks(calib, modo, horas_ventana)
    rows = medir_delays(ticks_medicion, llamadas)
    resumen = resumen_delays(rows)

    n_posiciones = {sid: len(rows_) for sid, rows_ in resolved.items()}

    intervalos = cargar_intervalos_exclusion_ava()
    n_en_exclusion = sum(1 for t in llamadas if en_algun_intervalo(t, intervalos))
    ejemplos_exclusion = []
    for t in llamadas:
        if en_algun_intervalo(t, intervalos) and len(ejemplos_exclusion) < 10:
            ejemplos_exclusion.append(datetime.utcfromtimestamp(t).isoformat())

    top10 = sorted((r for r in rows if r["evaluable"]), key=lambda r: -r["delta_s"])[:10]
    ejemplos_top_delay = [{
        "t_pedido_iso": datetime.utcfromtimestamp(r["t_pedido"]).isoformat(),
        "t_devuelto_iso": datetime.utcfromtimestamp(r["t_devuelto"]).isoformat(),
        "delta_s": r["delta_s"],
    } for r in top10]

    _escribir_csv(rows, OUT_DIR / "auditoria_lookahead_ava_q6.csv")

    return {
        "modo": modo,
        "n_bars_final": len(bars_final),
        "n_posiciones_por_estrategia": n_posiciones,
        "n_llamadas_first_at": len(llamadas),
        "tiempo_medido_seg": round(tiempo_s, 2),
        "resumen_delays": resumen,
        "n_llamadas_dentro_de_exclusion_ava": n_en_exclusion,
        "n_intervalos_exclusion_ava": len(intervalos),
        "ejemplos_llamadas_dentro_de_exclusion": ejemplos_exclusion,
        "ejemplos_top10_delay": ejemplos_top_delay,
    }


# --------------------------------------------------------------------- driver (I/O real)


def _git_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _escribir_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_pedido", "t_pedido_iso", "t_devuelto", "t_devuelto_iso",
                    "delta_s", "evaluable", "clasificacion_si_gt_60s"])
        for r in rows:
            t_ped_iso = datetime.utcfromtimestamp(r["t_pedido"]).isoformat()
            if r["evaluable"]:
                t_dev_iso = datetime.utcfromtimestamp(r["t_devuelto"]).isoformat()
                clasif = clasificar_hueco(r["t_pedido"]) if r["delta_s"] > UMBRAL_60S else ""
            else:
                t_dev_iso = ""
                clasif = ""
            w.writerow([r["t_pedido"], t_ped_iso, r.get("t_devuelto") or "", t_dev_iso,
                        r["delta_s"] if r["delta_s"] is not None else "", r["evaluable"], clasif])


def main(correr_q6_ava: bool = True) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Q4/Q5: Capitaria, rejilla declarada ----
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

    _escribir_csv(rows, OUT_DIR / "auditoria_lookahead.csv")

    # ---- Q6: AVA / F0-BT-LARGO-0001 (llamadas GENUINAS del motor largo) ----
    q6: dict[str, Any] | None = None
    q6_error: str | None = None
    if correr_q6_ava:
        try:
            q6 = medir_q6_ava(modo="mediana")
        except Exception as exc:  # noqa: BLE001 -- se declara, no se oculta
            q6_error = f"{type(exc).__name__}: {exc}"

    out = {
        "lineage": {
            "run_id": f"T0.7-M-C-auditoria-lookahead-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            "area": "F0", "experimento": "T0.7-M-C-auditoria-lookahead", "etapa": "F0",
            "git_sha": _git_sha(), "generador": "scripts/analysis/realtick_bt/auditoria_lookahead.py",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        "ventana_q4q5_capitaria": {
            "t0_iso": datetime.utcfromtimestamp(WINDOW_T0).isoformat(),
            "t1_iso": datetime.utcfromtimestamp(WINDOW_T1).isoformat(),
            "n_instantes_rejilla": len(instantes),
        },
        "resumen_delays_q4": resumen,
        "clasificacion_gt_60s_q5": clasif,
        "ejemplos_gt_60s_q5": ejemplos,
        "q6_ava_f0_bt_largo_0001": q6,
        "q6_ava_error": q6_error,
        "hallazgos_repo_wide_q3": HALLAZGOS_REPO_WIDE,
    }
    with (OUT_DIR / "auditoria_lookahead.json").open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, sort_keys=False)

    print(json.dumps({"resumen_delays_q4": resumen, "clasificacion_gt_60s_q5": clasif,
                       "q6_ava_f0_bt_largo_0001": q6, "q6_ava_error": q6_error}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
