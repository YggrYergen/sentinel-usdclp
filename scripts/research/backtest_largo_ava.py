r"""Backtest largo de S6 / SuperTrend sobre ~3.5 anos de ticks reales de AVA
(T0.6, ultimo entregable del programa BL-0 -- D-23).

Por que existe. El sustrato de AVA (`data/lake_ticks_ava/GOLD/`) cubre
2022-01-02 -> 2026-08-12, casi 4.6 anos, con el holdout (D-31 acto 2, ano 2023
completo) sellado. `scripts/analysis/realtick_bt/backtest.py` esta cableado a
Capitaria (`TICKDIR`, `BARS_PATH`); este modulo lo conduce SIN TOCARLO
(R1-bis, charter SS A.11) para correr sobre AVA en su lugar.

EL PUNTO DE INSERCION LIMPIO es `bt.Ticks._load(ym)`: es el UNICO metodo que
toca disco; `first_at`, `range` y `_candidates` funcionan sin cambios sobre lo
que `_load` devuelva. `AvaTicks` (abajo) subclasea `bt.Ticks` y sobrescribe
solo `_load` para (a) leer del lago de AVA en vez de Capitaria y (b) aplicar
el overlay de costes (D-21, mod #10) a los arrays bid/ask antes de
devolverlos -- ahi vive la modificacion de motor #10, como envoltorio y no
como parche.

RELOJES (charter SS A.11 + docstring de backtest.py:15-26). Todo epoch del
lago de AVA codifica el reloj del SERVIDOR del broker; AVA = UTC fijo sin
DST (`ny_window.BROKER_TZ["ava"]`). Se decodifica con `utcfromtimestamp()`,
NUNCA `fromtimestamp()`. La hora de Nueva York de un tick se obtiene con
`ny_window.server_epoch_to_ny(t, "ava")` (ya testeada); `ny_hours_ava()` de
este modulo es una version VECTORIZADA de esa misma conversion para arrays de
millones de ticks (pandas tz_convert en vez de un bucle Python de objetos
datetime) -- NO reimplementa la regla de DST, la vectoriza para el caso AVA
(sin ambiguedad de reloj de host que evitar, a diferencia de Capitaria);
verificada elemento a elemento contra la funcion escalar ya testeada en
`tests/research/test_backtest_largo_ava.py`.

QUE SE APLICA, Y EN QUE ORDEN
------------------------------
1. Overlay de costes (D-21) -- en `AvaTicks._load`, sobre los ticks CRUDOS
   del mes, antes de que el harness los use para nada. Se CONSERVA el mid de
   AVA y se SUSTITUYE la anchura por la calibrada sobre Capitaria
   (`cost_overlay.overlay_arrays`). Guarda D-21 en `_overlay_month`: verifica
   que la anchura resultante sea EXACTAMENTE la calibrada para esa hora/modo
   y que el mid se conserve -- NO compara contra el spread nativo del tick
   (medido en datos reales: ~0,016% de los ticks de AVA tiene spread nativo
   anomalo de hasta 3,00, mas ancho que cualquier valor calibrado; el
   overlay debe sustituir esa anchura igual, no "ensanchar respecto a ella").
2. Ventana operativa periodizada (D-36 + D-37) -- se filtran las BARRAS
   (`ventana_calendario.filter_bars`) antes de pasarlas a `bt.build_all()`.
   NUNCA `ny_window.in_ny_window` (borde fijo, revocado por D-36).
3. Exclusiones de continuidad (D-33) -- los intervalos de
   `T0.3-continuidad/exclusiones-ava.json` (huecos intradia del feed de AVA
   que caen dentro de la ventana) se descartan de las barras YA filtradas por
   ventana.
4. Columna de cobertura (D-33, obligatoria) -- por mes, que fraccion de las
   barras-ventana (paso 2) sobrevive al paso 3.

HOLDOUT (charter SS A.14 + D-31 acto 2: AVA 2023 completo). Doble guarda:
  (a) ANTES de leer disco -- `cost_overlay.assert_fuera_holdout_ava` sobre
      los dos tramos declarados que rodean el holdout (2022 y 2024-2026), y
      un chequeo de que `load_bars_ava()` no trae NINGUNA barra de 2023 (el
      fichero de barras ya esta sellado por construccion, pero no nos
      fiamos). `AvaTicks._load` ademas NUNCA lee un parquet de un mes 2023 --
      ni siquiera por el "neighbour month probing" de `Ticks._candidates`
      (que sondea ym-1/ym/ym+1 en TODA llamada, cruzando de Dic-2022 a
      Ene-2023 y de Dic-2023 a Ene-2024 de forma rutinaria e inocente): para
      esos meses devuelve arrays vacios sin abrir el fichero, igual que la
      clase base hace para un fichero inexistente. Esto degrada con gracia
      (una posicion que necesitara ticks de 2023 para resolverse simplemente
      se descarta, como si no hubiera dato) en vez de abortar toda la corrida
      por un sondeo de vecindad inocuo.
  (b) DESPUES de resolver -- igual que `baseline_golden.py`: si alguna
      posicion resuelta toca el holdout, ABORTA sin escribir nada.

Uso:  python -m scripts.research.backtest_largo_ava
"""
from __future__ import annotations

import calendar
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(r"D:\FOREX")
OUT_DIR = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.6-backtest-largo-ava"
)

from scripts.analysis.realtick_bt import backtest as bt  # noqa: E402
from scripts.research import cost_overlay as co  # noqa: E402
from scripts.research import ventana_calendario as vc  # noqa: E402
from scripts.research.ny_window import server_epoch_to_ny  # noqa: E402

# --------------------------------------------------------------------- rutas
TICKDIR_AVA = ROOT / "data" / "lake_ticks_ava" / "GOLD"
BARS_PATH_AVA = ROOT / "data" / "lake_bars_ava" / "GOLD_M15.parquet"
CALIBRACION_PATH = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.6-overlay-costes" / "calibracion.json"
)
EXCLUSIONES_PATH = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.3-continuidad" / "exclusiones-ava.json"
)

MODOS = ("mediana", "media")  # p75 NO se usa -- D-19/brief: coincide con la mediana en 7/8 horas
ESTRATEGIAS_REPORTADAS = ("S6-K2P0", "SuperTrend-p14x3-M15")
ESTRATEGIA_NO_REPORTADA = "S7-TPNONE"  # D-06: PF 0.968, neto negativo -- se calcula, no se reporta

# D-31 acto 2, reexportado de cost_overlay (no se re-deriva de forma
# independiente: una sola fuente de verdad para el sello).
AVA_HOLDOUT_INI = co.AVA_HOLDOUT_INI
AVA_HOLDOUT_FIN = co.AVA_HOLDOUT_FIN
_HOLDOUT_YEAR = "2023"

# Tramos declarados de antemano que rodean el holdout AVA, mismo patron que
# `calibracion_costes_capitaria.py` / `medir_calendario_ventana.py` usan para
# Capitaria: invocar la guarda ANTES de leer disco sobre cada tramo
# explicito, nunca sobre un rango que atraviese el sello.
_SEG1_INI = calendar.timegm(datetime(2022, 1, 1).timetuple())
_SEG1_FIN = AVA_HOLDOUT_INI
_SEG2_INI = AVA_HOLDOUT_FIN
_SEG2_FIN = calendar.timegm(datetime(2026, 8, 13).timetuple())  # exclusivo, > ultimo tick conocido


def _git_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _fmt(t: float) -> str:
    # server wall clock -- utcfromtimestamp, NUNCA fromtimestamp (backtest.py:15-26)
    return datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------- barras
def load_bars_ava() -> list[dict[str, Any]]:
    """Mismo shape que `bt.load_bars()`, leyendo de `BARS_PATH_AVA`."""
    df = pd.read_parquet(BARS_PATH_AVA)
    return [{"t": int(r.t), "open": float(r.o), "high": float(r.h),
              "low": float(r.l), "close": float(r.c), "volume": int(r.v)}
             for r in df.itertuples()]


# --------------------------------------------------------------------- reloj
def ny_hours_ava(t: np.ndarray) -> np.ndarray:
    """Version vectorizada de `server_epoch_to_ny(t, "ava").hour` para
    arrays. AVA = UTC fijo sin DST (`ny_window.BROKER_TZ["ava"]`), asi que el
    epoch YA es un epoch UTC estandar: convertirlo a hora de Nueva York con
    pandas (`tz_convert`) es matematicamente identico a la cadena
    utcfromtimestamp -> replace(tzinfo=UTC) -> astimezone(NY) que hace la
    funcion escalar, solo que sin construir un objeto datetime por tick.
    Verificado elemento a elemento en tests/research/test_backtest_largo_ava.py."""
    idx = pd.to_datetime(np.asarray(t, dtype="float64"), unit="s", utc=True)
    return idx.tz_convert("America/New_York").hour.to_numpy()


# --------------------------------------------------------------------- overlay
def _overlay_month(
    t: np.ndarray, bid: np.ndarray, ask: np.ndarray,
    calib: dict, modo: str, horas_ventana: tuple[int, ...],
) -> tuple[np.ndarray, np.ndarray]:
    """Aplica `cost_overlay.overlay_arrays` (D-21) solo a los ticks cuya hora
    NY cae dentro de la union de horas cubiertas por el calendario de
    ventana (`horas_ventana`); el resto se devuelve SIN TOCAR -- son ticks
    fuera de la ventana operativa en TODOS los periodos, que las barras
    filtradas (paso 2 del modulo) nunca van a necesitar, y la calibracion no
    los cubre (`spread_calibrado` lanzaria KeyError si se le pidieran).

    Construye los `datetime` que exige la firma de `overlay_arrays` con la
    hora YA calculada por `ny_hours_ava` (vectorizado) en vez de volver a
    convertir cada tick con `server_epoch_to_ny` -- `overlay_arrays` solo lee
    `.hour` de cada uno (ver cost_overlay.py:207), asi que un datetime
    minimo con esa hora es equivalente para su contrato, sin pagar dos veces
    la conversion de zona horaria.

    🔴 REGLA D-21, resuelta por el user el 2026-08-12 (ver D-38). El overlay
    NUNCA puede estrechar. En datos reales de AVA existe una minoria de ticks
    cuyo spread NATIVO ya es mas ancho que el calibrado (huecos / iliquidez
    puntual: medido en 2022-01, 259 de 1,58 M ticks -- ~0,016% -- llegan a
    3,00 frente al 0,34 tipico, y la calibracion ronda 0,50-0,60). Sobre esos
    ticks, sustituir la anchura por la calibrada ESTRECHARIA -- que es
    exactamente el fallo que D-21 existe para impedir.

    **Esos ticks NO se estrechan y NO se conservan crudos: se declaran NO
    EVALUABLES y se RETIRAN** del store que ve el simulador (mismo trato que
    D-33 da a los huecos de continuidad). El fill usa el siguiente tick
    evaluable. Se cuentan y se declaran en el artefacto: excluir sin declarar
    es justamente lo que el charter SS A.13 prohibe.

    Devuelve `(t, bid, ask, n_no_evaluables)` ya filtrados."""
    if len(t) == 0:
        return t.copy(), bid.copy(), ask.copy(), 0
    horas = ny_hours_ava(t)
    mask = np.isin(horas, horas_ventana)
    if not mask.any():
        return t.copy(), bid.copy(), ask.copy(), 0

    # --- D-38: retirar los ticks que el overlay estrecharia ------------------
    # Se comparan anchuras ANTES de aplicar nada: el ancho nativo frente al
    # calibrado de su propia hora. `>` estricto -- la igualdad no estrecha.
    ancho_nativo = ask - bid
    ancho_calib = np.empty(len(t), dtype="float64")
    ancho_calib.fill(np.nan)
    for h in np.unique(horas[mask]):
        sel = mask & (horas == h)
        ancho_calib[sel] = co.spread_calibrado(
            datetime(2000, 1, 1, hour=int(h)), calib, modo
        )
    no_evaluable = mask & (ancho_nativo > ancho_calib)
    n_no_evaluables = int(no_evaluable.sum())
    if n_no_evaluables:
        keep = ~no_evaluable
        t, bid, ask, horas, mask = t[keep], bid[keep], ask[keep], horas[keep], mask[keep]

    bid_out = bid.copy()
    ask_out = ask.copy()
    if not mask.any():
        return t.copy(), bid_out, ask_out, n_no_evaluables
    dts = [datetime(2000, 1, 1, hour=int(h)) for h in horas[mask]]
    b2, a2 = co.overlay_arrays(bid[mask], ask[mask], dts, calib, modo)

    # Guarda D-21 -- invariante ESTRUCTURAL, no una comparacion contra el
    # spread nativo del tick. Medido en datos reales (2022-01, AVA): la
    # inmensa mayoria de ticks tiene spread nativo 0.34, pero 259 de 1,58M
    # (~0,016%) llegan hasta 3,00 (huecos/iliquidez puntual) -- MAS ancho que
    # cualquier valor calibrado (~0.5-0.6). Comparar "ancho nuevo >= ancho
    # nativo" por tick dispara sobre esos outliers legitimos y no prueba nada
    # sobre el overlay: la regla D-21 es "se SUSTITUYE la anchura nativa por
    # la calibrada", no "la calibrada es mayor que cualquier tick nativo
    # posible". Lo que SI debe cumplirse siempre, por construccion de
    # `overlay_arrays` (cost_overlay.py, no reimplementado aqui): (a) el
    # ancho resultante es EXACTAMENTE el calibrado para esa hora/modo -- así
    # se detecta una inversion del sentido (min() en vez de sustitucion,
    # exactamente el bug que D-21 existe para impedir, ver
    # tests/research/test_cost_overlay.py::test_overlay_ensancha_nunca_estrecha)
    # -- y (b) el mid de AVA se conserva.
    horas_mask = horas[mask]
    ancho_nuevo = a2 - b2
    for h in np.unique(horas_mask):
        esperado = co.spread_calibrado(datetime(2000, 1, 1, hour=int(h)), calib, modo)
        obtenido = ancho_nuevo[horas_mask == h]
        if not np.allclose(obtenido, esperado, atol=1e-9):
            raise SystemExit(
                f"ABORTADO: el overlay de costes no produjo la anchura calibrada "
                f"para la hora NY {h} (modo={modo!r}); esperado {esperado}. "
                "Posible inversion del overlay -- viola D-21. No se leyo mas disco."
            )
    mid_orig = (bid[mask] + ask[mask]) / 2.0
    mid_new = (b2 + a2) / 2.0
    if not np.allclose(mid_new, mid_orig, atol=1e-6):
        raise SystemExit(
            "ABORTADO: el overlay de costes no conservo el mid de AVA -- "
            "viola D-21. No se leyo mas disco."
        )

    # Tras retirar los no evaluables (D-38), esta invariante ya no puede
    # fallar por outliers nativos: si falla, es una inversion real del
    # overlay en el codigo.
    nativo_restante = (ask - bid)[mask]
    if np.any(ancho_nuevo < nativo_restante - 1e-9):
        raise SystemExit(
            "ABORTADO: el overlay ESTRECHO el spread de algun tick evaluable -- "
            "viola D-21/D-38. No se leyo mas disco."
        )

    bid_out[mask] = b2
    ask_out[mask] = a2
    return t.copy(), bid_out, ask_out, n_no_evaluables


class AvaTicks(bt.Ticks):
    """`bt.Ticks` para el lago de AVA, con overlay de costes (D-21, mod #10).

    Unico metodo sobrescrito: `_load`. `first_at`, `range` y `_candidates`
    (heredados byte-identicos) funcionan sin cambios sobre lo que este
    `_load` devuelva -- ese es exactamente el punto de insercion limpio que
    R1-bis exige (charter SS A.11): `backtest.py` no se toca."""

    def __init__(self, calib: dict, modo: str, horas_ventana: tuple[int, ...]) -> None:
        super().__init__()
        self._calib = calib
        self._modo = modo
        self._horas_ventana = horas_ventana
        # D-38: ticks retirados por no evaluables, por mes. Se declara en el
        # artefacto -- excluir sin declarar viola SS A.13.
        self.no_evaluables_por_mes: dict[str, int] = {}

    def _load(self, ym: str):
        if ym not in self._m:
            if ym[:4] == _HOLDOUT_YEAR:
                # Holdout sellado (D-31 acto 2, charter SS A.14): nunca se
                # lee, ni siquiera por el sondeo inocente de mes vecino de
                # `Ticks._candidates`. Se comporta como un fichero
                # inexistente (arrays vacios), no como un abort -- ver
                # docstring del modulo, punto (a).
                self._m[ym] = (np.array([]), np.array([]), np.array([]))
            else:
                p = TICKDIR_AVA / f"{ym}.parquet"
                if not p.exists():
                    self._m[ym] = (np.array([]), np.array([]), np.array([]))
                else:
                    df = pd.read_parquet(p)
                    t = df.t_msc.to_numpy() / 1000.0
                    bid = df.bid.to_numpy()
                    ask = df.ask.to_numpy()
                    t2, bid2, ask2, n_no_eval = _overlay_month(
                        t, bid, ask, self._calib, self._modo, self._horas_ventana
                    )
                    if n_no_eval:
                        self.no_evaluables_por_mes[ym] = n_no_eval
                    self._m[ym] = (t2, bid2, ask2)
        return self._m[ym]


# --------------------------------------------------------------- exclusiones
def cargar_exclusiones(path) -> dict:
    """Carga `exclusiones-ava.json` (D-33). Falla duro si falta la clave
    `intervalos` o algun intervalo no trae `ini_epoch`/`fin_epoch`."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"exclusiones no encontradas: {p}")
    with p.open("r", encoding="utf-8") as f:
        d = json.load(f)
    if "intervalos" not in d:
        raise KeyError(f"exclusiones sin clave 'intervalos': {p}")
    for i, iv in enumerate(d["intervalos"]):
        faltan = [c for c in ("ini_epoch", "fin_epoch") if c not in iv]
        if faltan:
            raise KeyError(f"intervalo #{i} incompleto: faltan {faltan} ({p})")
    return d


def filter_exclusiones(bars: list[dict[str, Any]], intervalos: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Descarta las barras cuyo `t` cae en `[ini_epoch, fin_epoch)` de algun
    intervalo de continuidad (D-33). Devuelve una lista NUEVA; no muta
    `bars`. Ticks reloj AVA = UTC fijo, mismo eje de epoch que `bars["t"]`
    (backtest.py CLOCK CONVENTION), asi que la comparacion es directa."""
    if not intervalos or not bars:
        return list(bars)
    ts = np.array([b["t"] for b in bars], dtype="float64")
    excluded = np.zeros(len(ts), dtype=bool)
    for ini, fin in intervalos:
        excluded |= (ts >= ini) & (ts < fin)
    return [b for b, ex in zip(bars, excluded) if not ex]


# ----------------------------------------------------------------- cobertura
def cobertura_mensual(
    bars_ventana: list[dict[str, Any]], bars_final: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """D-33, columna OBLIGATORIA: por mes calendario (hora servidor AVA =
    UTC), que fraccion de las barras-ventana (tras el filtro de ventana
    operativa, ANTES de exclusiones) sobrevive tras aplicar las exclusiones
    de continuidad. Un mes sin barras-ventana no aporta denominador (no se
    opero ese mes en absoluto, cobertura=None, distinto de un mes mutilado)."""
    def _mes(b):
        return bt.ym_of(b["t"])

    n_ventana: dict[str, int] = {}
    for b in bars_ventana:
        m = _mes(b)
        n_ventana[m] = n_ventana.get(m, 0) + 1
    n_final: dict[str, int] = {}
    for b in bars_final:
        m = _mes(b)
        n_final[m] = n_final.get(m, 0) + 1

    out: dict[str, dict[str, Any]] = {}
    for m in sorted(n_ventana):
        nv = n_ventana[m]
        nf = n_final.get(m, 0)
        out[m] = {
            "n_barras_ventana": nv,
            "n_barras_tras_exclusiones": nf,
            "cobertura_pct": round(100.0 * nf / nv, 3) if nv else None,
        }
    return out


# --------------------------------------------------------------------- driver
def main() -> int:
    t0 = time.time()

    calendario = vc.cargar_calendario(co.CALENDARIO_PATH)
    calib = co.cargar_calibracion(CALIBRACION_PATH)
    horas_ventana = co.horas_calendario(calendario)
    excl_raw = cargar_exclusiones(EXCLUSIONES_PATH)
    intervalos = [(iv["ini_epoch"], iv["fin_epoch"]) for iv in excl_raw["intervalos"]]

    # ---- (a) guarda dura ANTES de leer disco, sobre los dos tramos que rodean el holdout ----
    co.assert_fuera_holdout_ava(_SEG1_INI, _SEG1_FIN)
    co.assert_fuera_holdout_ava(_SEG2_INI, _SEG2_FIN)

    bars_all = load_bars_ava()
    bars_2023 = [b for b in bars_all if datetime.utcfromtimestamp(b["t"]).year == 2023]
    if bars_2023:
        raise SystemExit(
            f"ABORTADO: {len(bars_2023)} barras caen en 2023 (holdout AVA sellado, "
            "D-31 acto 2). El fichero de barras deberia estar sellado por "
            "construccion -- no se confio en eso y la verificacion fallo. "
            "No se leyo ningun tick."
        )

    n_barras_todas = len(bars_all)
    bars_ventana = vc.filter_bars(bars_all, "ava", calendario)
    n_barras_ventana = len(bars_ventana)
    bars_final = filter_exclusiones(bars_ventana, intervalos)
    n_barras_final = len(bars_final)
    if not bars_final:
        raise SystemExit("ninguna barra tras ventana+exclusiones -- abortando")

    cobertura = cobertura_mensual(bars_ventana, bars_final)

    print(f"barras totales (AVA)      : {n_barras_todas:,}  {_fmt(bars_all[0]['t'])} .. {_fmt(bars_all[-1]['t'])}")
    print(f"barras tras ventana NY     : {n_barras_ventana:,}")
    print(f"barras tras exclusiones D-33: {n_barras_final:,}  {_fmt(bars_final[0]['t'])} .. {_fmt(bars_final[-1]['t'])}")

    # ---- correr las dos variantes de overlay ----
    resolved_by_modo: dict[str, dict[str, list[dict[str, Any]]]] = {}
    tiempos: dict[str, float] = {}
    no_eval_por_modo: dict[str, dict[str, int]] = {}
    for modo in MODOS:
        tm0 = time.time()
        ticks = AvaTicks(calib, modo, horas_ventana)
        resolved_by_modo[modo] = bt.build_all(ticks, bars_final)
        tiempos[modo] = round(time.time() - tm0, 2)
        no_eval_por_modo[modo] = dict(sorted(ticks.no_evaluables_por_mes.items()))
        n_no_eval = sum(no_eval_por_modo[modo].values())
        print(f"  [{modo}] resuelto en {tiempos[modo]:.1f}s  "
              f"ticks no evaluables retirados (D-38): {n_no_eval:,}")

    # ---- (b) guarda dura DESPUES de resolver: ninguna posicion toca el holdout ----
    intrusas: list[tuple[str, str, dict]] = []
    for modo, resolved in resolved_by_modo.items():
        for sid, rows in resolved.items():
            for r in rows:
                if (AVA_HOLDOUT_INI <= r["t_in_exec"] < AVA_HOLDOUT_FIN) or \
                   (AVA_HOLDOUT_INI <= r["t_exit"] < AVA_HOLDOUT_FIN):
                    intrusas.append((modo, sid, r))
    if intrusas:
        for modo, sid, r in intrusas[:5]:
            print(f"  INTRUSA [{modo}] {sid}: in={_fmt(r['t_in_exec'])} exit={_fmt(r['t_exit'])}")
        raise SystemExit(
            f"ABORTADO: {len(intrusas)} posiciones tocan el holdout AVA sellado "
            "(charter SS A.14 + D-31 acto 2). No se escribio ningun artefacto."
        )

    # ---- escribir artefactos ----
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    git_sha = _git_sha()

    metricas_globales: dict[str, dict[str, Any]] = {}
    mensual: dict[str, dict[str, Any]] = {}
    for modo, resolved in resolved_by_modo.items():
        metricas_globales[modo] = {}
        mensual[modo] = {}
        for sid, rows in sorted(resolved.items()):
            m = bt.metrics(rows, bt.LOT_GRID)
            metricas_globales[modo][sid] = m

            meses = sorted({bt.ym_of(r["t_in_exec"]) for r in rows}) if rows else []
            tabla_mes: dict[str, Any] = {}
            for mo in meses:
                mr = [r for r in rows if bt.ym_of(r["t_in_exec"]) == mo]
                mm = bt.metrics(mr, bt.LOT_GRID)
                mm["cobertura"] = cobertura.get(mo)
                tabla_mes[mo] = mm
            mensual[modo][sid] = tabla_mes

            filas = sorted(
                ({k: (round(v, 10) if isinstance(v, float) else v) for k, v in sorted(r.items())}
                 for r in rows),
                key=lambda r: (r["t_in_exec"], r["t_exit"]),
            )
            path = OUT_DIR / f"posiciones_{sid}_{modo}.json"
            with path.open("w", encoding="utf-8") as f:
                json.dump(filas, f, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False)
            print(f"[{modo}] {sid:24s} n={m['n']:5d}  net={m['net']:>16,.2f}  wr={m['wr']}  pf={m['pf']}  maxdd={m['maxdd']:>14,.2f}")

    meta = {
        "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_sha": git_sha,
        "substrate_id": "ava-ticks-2022-2026-sans-holdout",
        "sustrato_ticks": "data/lake_ticks_ava/GOLD/ (ticks reales AVA)",
        "sustrato_barras": "data/lake_bars_ava/GOLD_M15.parquet",
        "ventana_barras_todas": [_fmt(bars_all[0]["t"]), _fmt(bars_all[-1]["t"])],
        "ventana_barras_finales": [_fmt(bars_final[0]["t"]), _fmt(bars_final[-1]["t"])],
        "n_barras_todas": n_barras_todas,
        "n_barras_tras_ventana_ny": n_barras_ventana,
        "n_barras_tras_exclusiones_d33": n_barras_final,
        "holdout_ava_excluido": [_fmt(AVA_HOLDOUT_INI), _fmt(AVA_HOLDOUT_FIN)],
        "calendario_ventana": {
            "path": str(co.CALENDARIO_PATH),
            "git_sha": calendario.get("git_sha"),
            "generado": calendario.get("generado"),
        },
        "calibracion_costes": {
            "path": str(CALIBRACION_PATH),
            "git_sha": calib.get("git_sha"),
            "generado": calib.get("generado"),
        },
        "exclusiones_continuidad": {
            "path": str(EXCLUSIONES_PATH),
            "n_intervalos": excl_raw.get("n_intervalos"),
            "horas_excluidas_en_ventana": excl_raw.get("horas_excluidas_en_ventana"),
        },
        "modos_overlay": list(MODOS),
        "lot": bt.LOT_GRID,
        "estrategias_reportadas": list(ESTRATEGIAS_REPORTADAS),
        "estrategias_no_reportadas": {
            ESTRATEGIA_NO_REPORTADA:
                "descartada del informe por D-06 (PF 0.968, neto negativo); "
                "numeros calculados como subproducto gratis de build_all() "
                "(que corre las 3 estrategias en una pasada) y dejados en "
                "'metricas_globales'/'mensual' para quien los necesite, pero "
                "fuera del informe (brief T0.6-backtest-largo-ava).",
        },
        "ticks_no_evaluables_d38": {
            "regla": (
                "D-21, interpretada por el user el 2026-08-12 (D-38): el overlay "
                "NUNCA estrecha. Los ticks cuyo spread NATIVO de AVA ya es mas "
                "ancho que el calibrado de su hora (huecos / iliquidez puntual) "
                "se declaran NO EVALUABLES y se RETIRAN del store que ve el "
                "simulador; el fill usa el siguiente tick evaluable. NO se "
                "estrechan y NO se conservan crudos."
            ),
            "por_modo_y_mes": no_eval_por_modo,
            "total_por_modo": {m: sum(v.values()) for m, v in no_eval_por_modo.items()},
        },
        "limitaciones_declaradas": [
            "D-38: una minoria de ticks de AVA se retira por NO EVALUABLE (ver "
            "'ticks_no_evaluables_d38'). Es una exclusion declarada, no un "
            "filtro silencioso, y va en el mismo espiritu que D-33.",
            "D-36: la extrapolacion del calendario de ventana operativa a "
            "2022-2025 es una HIPOTESIS, no un hecho medido -- Capitaria solo "
            "cubre desde 2026-01 y no hay gate de spread observable antes de "
            "esa fecha con el que verificarla.",
            "D-32: 'maxdd' y 'peak_margin' (dentro de cada entrada de "
            "'metricas_globales'/'mensual') estan PROHIBIDOS como criterio de "
            "aprobacion o descarte. maxDD es pico-a-valle del P&L CERRADO "
            "(backtest.py:412-435) y el simulador no impone margen ni margin "
            "call -- no son medidas de supervivencia, son descriptores de "
            "excursion y de capital comprometido, nada mas.",
        ],
        "cobertura_mensual": cobertura,
        "metricas_globales": metricas_globales,
        "mensual": mensual,
        "tiempo_medido_seg": {**tiempos, "total": round(time.time() - t0, 2)},
    }
    with (OUT_DIR / "backtest-largo-ava.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    print(f"\nartefactos en {OUT_DIR}")
    print(f"tiempo total: {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
