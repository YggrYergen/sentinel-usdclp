r"""T0.7-p-cap -- deriva `stops_level` (Componente C de la replica del motor
faulty, tag engine-faulty-tomachine-902 -> b113eb7) desde los eventos de
clamp del ejecutor real.

INVESTIGADOR REPORT-ONLY. Brief:
.superpowers/sdd/2026-08-13-replica-motor-faulty-spec/m1-stops-level-brief.md

El ejecutor vivo aplicaba un clamp al SL antes de enviarlo al broker
(`_clamp_sl(..., level)`, unidades de precio):

  - long:  si desired_sl > ref - level  =>  clamped = ref - level, ref = bid
  - short: si desired_sl < ref + level  =>  clamped = ref + level, ref = ask

  => level = |ref - clamped| en cada evento de clamp. Debe salir constante.

Este script NO decide ni interpreta: calcula level_i por evento, verifica
signo y necesidad, y reporta objetivamente.

RONDA DE CORRECCION 1 (2026-08-13) -- el log del ejecutor NUNCA trae `ref`
para los eventos de clamp (medido: 0/122 usables via la formula del brief
original; ver la seccion "via log" del reporte y del artefacto, que se
conserva intacta -- registro aditivo). Se anade una segunda via,
independiente: inversion contra el lago de ticks reales de Capitaria
(`data/lake_ticks/XAUUSD/<YYYYMM>.parquet`, columnas `t_msc`,`bid`,`ask`).
Para cada `L` candidato en una rejilla, se comprueba si el `ref` que ese `L`
implica (`clamped + L` para long, `clamped - L` para short -- misma
aritmetica del clamp de `ciclos.py`, ver arriba) cayo dentro del rango real
de bid/ask observado en una ventana de ticks alrededor del instante del
evento. El resultado es la curva completa `L -> n_consistentes`, nunca un
unico numero elegido por el script.

Esta via SI toca `data/lake_ticks/XAUUSD/*.parquet` (solo lectura, via
pandas). Sigue sin usar red ni MT5, y sigue sin escribir en `data/lake_*`.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_EVENTOS_CSV = ROOT / "data/analysis/p_cap/eventos_ejecutor_902.csv"
DEFAULT_SL_CLAMPED_OPEN_JSON = ROOT / "data/analysis/p_cap/sl_clamped_open_events.json"
DEFAULT_VERDAD_TERRENO_CSV = ROOT / "data/analysis/p_cap/verdad_terreno_902.csv"
DEFAULT_OUT_JSON = (
    ROOT / "research/fases/F0-preparacion/04-resultados/T0.7-p-cap/stops_level_derivado.json"
)
DEFAULT_OUT_MD = (
    ROOT / "research/fases/F0-preparacion/04-resultados/T0.7-p-cap/stops_level_derivado.md"
)

ENGINE_SHA = "b113eb7"
AREA = "F0"
EXPERIMENTO = "T0.7-P-CAP-stops-level"
GENERADOR = "scripts/analysis/p_cap/derivar_stops_level.py"

ROUND_DECIMALS = 5
# Tolerancia para emparejar un evento SL_CLAMPED OPEN (sin ticket todavia,
# la posicion aun no existe) con la posicion resultante mas cercana en el
# tiempo por (config, t_open_epoch). Convencion heredada de
# scripts/analysis/p_cap/match_orders_to_positions.py (mismo umbral, 120s,
# usado alli para la misma clase de emparejamiento por cercania temporal).
MATCH_DELTA_TOLERANCE_SEC = 120

# Mismo mapeo que scripts/analysis/p_cap/match_orders_to_positions.py.
STRATEGY_TO_CONFIG = {
    "SAR::S6-K2P0": "S6-K2P0",
    "SuperTrend::SuperTrend-p14x3-M15": "SuperTrend-p14x3-M15",
}
CONFIG_TO_STRATEGY = {v: k for k, v in STRATEGY_TO_CONFIG.items()}

SIDE_TO_LS = {"BUY": "L", "SELL": "S"}

# ---------------------------------------------------------------------------
# Via ticks (ronda de correccion 1)
# ---------------------------------------------------------------------------

DEFAULT_TICKDIR = ROOT / "data/lake_ticks/XAUUSD"

# Rejilla de L candidatos, en unidades de precio del oro (2 decimales).
L_GRID_MIN = 0.00
L_GRID_MAX = 2.00
L_GRID_STEP = 0.01

# Ventanas de sensibilidad para la familia SL_CLAMPED OPEN (tiene `ms`, el
# controlador pidio ver ademas del default +/-1s las dos vecinas +/-0.25s y
# +/-3s).
OPEN_HALF_WINDOWS_SEC = (0.25, 1.00, 3.00)
OPEN_DEFAULT_HALF_WINDOW_SEC = 1.00

# La familia SL_CLAMPED (MODIFY) solo trae epoch entero (sin `ms`): menor
# resolucion temporal. +/-1s es el minimo declarado por el controlador; no
# se hace barrido de sensibilidad para esta familia (una sola ventana,
# declarada como de menor resolucion que la de OPEN).
MODIFY_HALF_WINDOW_SEC = 1.00


# ---------------------------------------------------------------------------
# Nucleo puro (testeado sin I/O)
# ---------------------------------------------------------------------------


def nivel_desde_ref_clamped(ref: float, clamped: float) -> float:
    """level_i = |ref - clamped|, redondeado a ROUND_DECIMALS para la
    comparacion de igualdad."""
    return round(abs(float(ref) - float(clamped)), ROUND_DECIMALS)


def verificar_signo(side: str, ref: float, clamped: float, level: float, tol: float = 1e-6) -> bool:
    """side en {"L","S"}. Comprueba que el clamp fue en la direccion
    correcta: long => clamped == ref - level; short => clamped == ref + level."""
    if side == "L":
        esperado = ref - level
    elif side == "S":
        esperado = ref + level
    else:
        return False
    return abs(esperado - clamped) <= tol


def verificar_necesidad(side: str, desired_sl: float, ref: float, level: float) -> bool:
    """Comprueba que el clamp realmente hacia falta: long => desired_sl > ref -
    level; short => desired_sl < ref + level."""
    if side == "L":
        return desired_sl > ref - level
    elif side == "S":
        return desired_sl < ref + level
    return False


def resumen_niveles(level_values: list[float]) -> dict:
    """Distribucion de level_i: valores distintos + frecuencia, min/max/
    mediana/moda, y si es constante. Nunca promedia ni elige un valor."""
    if not level_values:
        return {
            "n": 0,
            "valores": {},
            "min": None,
            "max": None,
            "mediana": None,
            "moda": None,
            "es_constante": None,
        }
    freq = Counter(level_values)
    ordenados = sorted(freq.items())
    moda_val, _moda_freq = freq.most_common(1)[0]
    return {
        "n": len(level_values),
        "valores": {f"{v:.5f}": c for v, c in ordenados},
        "min": min(level_values),
        "max": max(level_values),
        "mediana": statistics.median(level_values),
        "moda": moda_val,
        "es_constante": len(freq) == 1,
    }


def procesar_familia(eventos: list[dict]) -> dict:
    """eventos: lista de dicts con al menos epoch, timestamp_servidor, config,
    ficha, side ("L"/"S"/None), ref, clamped, desired_sl (todos pueden ser
    None). Devuelve el reporte completo de una familia (o del total)."""
    n = len(eventos)
    usables: list[dict] = []
    descartados: Counter = Counter()

    for ev in eventos:
        if ev.get("ref") is None:
            descartados["ref_ausente"] += 1
            continue
        if ev.get("clamped") is None:
            descartados["clamped_ausente"] += 1
            continue
        usables.append(ev)

    level_values: list[float] = []
    side_breakdown: dict[str, list[float]] = defaultdict(list)
    config_breakdown: dict[str, list[float]] = defaultdict(list)
    signo_fail: list[dict] = []
    signo_ok_n = 0
    necesidad_fail: list[dict] = []
    necesidad_ok_n = 0
    necesidad_no_evaluable_n = 0

    enriquecidos: list[dict] = []
    for ev in usables:
        level = nivel_desde_ref_clamped(ev["ref"], ev["clamped"])
        enriched = dict(ev)
        enriched["level_i"] = level
        enriquecidos.append(enriched)
        level_values.append(level)

        side = ev.get("side")
        if side:
            side_breakdown[side].append(level)
        cfg = ev.get("config")
        if cfg:
            config_breakdown[cfg].append(level)

        if side in ("L", "S"):
            if verificar_signo(side, ev["ref"], ev["clamped"], level):
                signo_ok_n += 1
            else:
                signo_fail.append(enriched)

            if ev.get("desired_sl") is not None:
                if verificar_necesidad(side, ev["desired_sl"], ev["ref"], level):
                    necesidad_ok_n += 1
                else:
                    necesidad_fail.append(enriched)
            else:
                necesidad_no_evaluable_n += 1

    resumen = resumen_niveles(level_values)

    discrepancias: list[dict] = []
    if resumen["es_constante"] is False:
        moda = resumen["moda"]
        discrepancias = [ev for ev in enriquecidos if ev["level_i"] != moda]

    return {
        "n": n,
        "n_usable": len(usables),
        "n_descartados": n - len(usables),
        "motivos_descartados": dict(descartados),
        "resumen_niveles": resumen,
        "desglose_side": {s: resumen_niveles(v) for s, v in side_breakdown.items()},
        "desglose_config": {c: resumen_niveles(v) for c, v in config_breakdown.items()},
        "discrepancias": discrepancias,
        "verificacion_signo": {
            "n_ok": signo_ok_n,
            "n_fail": len(signo_fail),
            "fails": signo_fail,
        },
        "verificacion_necesidad": {
            "n_ok": necesidad_ok_n,
            "n_fail": len(necesidad_fail),
            "n_no_evaluable": necesidad_no_evaluable_n,
            "fails": necesidad_fail,
        },
    }


# ---------------------------------------------------------------------------
# Via ticks: nucleo puro (testeado sin I/O)
# ---------------------------------------------------------------------------


def grid_L(lo: float = L_GRID_MIN, hi: float = L_GRID_MAX, step: float = L_GRID_STEP) -> list[float]:
    """Rejilla de L candidatos [lo, hi] en pasos de `step`, redondeados a 2
    decimales (precio del oro)."""
    n = round((hi - lo) / step)
    return [round(lo + i * step, 2) for i in range(n + 1)]


def ref_implicado(side: str, clamped: float, L: float) -> float | None:
    """El `ref` que un `L` candidato implica, dado `clamped`, invirtiendo la
    aritmetica del clamp de ciclos.py:
      long:  clamped = ref - L  =>  ref = clamped + L
      short: clamped = ref + L  =>  ref = clamped - L
    """
    if side == "L":
        return clamped + L
    if side == "S":
        return clamped - L
    return None


def es_consistente_con_ticks(
    side: str,
    clamped: float,
    L: float,
    bid_min: float,
    bid_max: float,
    ask_min: float,
    ask_max: float,
) -> bool:
    """Un `L` candidato es consistente con un evento si el `ref` que implica
    cayo dentro del rango de precios realmente observado en la ventana de
    ticks alrededor del evento -- bid para long (ref=bid en ciclos.py), ask
    para short (ref=ask)."""
    ref = ref_implicado(side, clamped, L)
    if ref is None:
        return False
    if side == "L":
        return bid_min <= ref <= bid_max
    return ask_min <= ref <= ask_max


def barrer_consistencia(eventos_ticks: list[dict], l_grid: list[float] | None = None) -> dict[str, int]:
    """Para cada `L` de la rejilla, cuenta cuantos eventos son consistentes.
    `eventos_ticks`: dicts con side, clamped, bid_min, bid_max, ask_min,
    ask_max. Devuelve la CURVA COMPLETA {f"{L:.2f}": n_consistentes} --
    nunca colapsa al maximo ni elige un L."""
    if l_grid is None:
        l_grid = grid_L()
    curva: dict[str, int] = {}
    for L in l_grid:
        n = sum(
            1
            for ev in eventos_ticks
            if es_consistente_con_ticks(
                ev["side"], ev["clamped"], L,
                ev["bid_min"], ev["bid_max"], ev["ask_min"], ev["ask_max"],
            )
        )
        curva[f"{L:.2f}"] = n
    return curva


def resumen_curva(curva: dict[str, int], n_evaluable: int) -> dict:
    """Maximo de la curva, si es unico, top-5 puntos, y la fraccion que
    representa sobre los eventos evaluables. No decide un `L` "correcto";
    solo describe la curva."""
    if not curva:
        return {
            "max_n": None, "fraccion_max": None,
            "L_ganador_unico": None, "L_empatados_en_max": [],
            "top5": [],
        }
    max_n = max(curva.values())
    empatados = sorted((L for L, n in curva.items() if n == max_n), key=float)
    top5 = sorted(curva.items(), key=lambda kv: (-kv[1], float(kv[0])))[:5]
    return {
        "max_n": max_n,
        "fraccion_max": (max_n / n_evaluable) if n_evaluable else None,
        "L_ganador_unico": empatados[0] if len(empatados) == 1 else None,
        "L_empatados_en_max": empatados,
        "top5": [{"L": L, "n": n} for L, n in top5],
    }


class TickWindowLoader:
    """Carga bajo demanda de `data/lake_ticks/XAUUSD/<YYYYMM>.parquet`
    (columnas t_msc, bid, ask), y consulta ventanas [t_center-hw, t_center+hw]
    por busqueda binaria sobre arrays numpy ordenados por tiempo.

    Reimplementacion propia, independiente, de solo lectura -- NO reutiliza
    la clase `Ticks` de scripts/analysis/realtick_bt/backtest.py (que
    tambien esta disponible para este uso, "importar si, editar jamas", per
    instruccion del controlador). Se opto por esta via para no arrastrar la
    cadena de imports pesada de backtest.py (sentinel_engine.*) en un script
    que solo necesita consultas de ventana estrecha alrededor de un evento
    puntual; se declara aqui explicitamente, tal como pidio el controlador.

    CLOCK CONVENTION: los epochs son hora de SERVIDOR (UTC-4) verbatim,
    igual que en ciclos.py / backtest.py -- `datetime.utcfromtimestamp()`,
    nunca `datetime.fromtimestamp()`.
    """

    def __init__(self, tickdir: Path = DEFAULT_TICKDIR) -> None:
        self._tickdir = tickdir
        self._cache: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray] | None] = {}

    def _load_month(self, ym: str):
        if ym not in self._cache:
            p = self._tickdir / f"{ym}.parquet"
            if not p.exists():
                self._cache[ym] = None
            else:
                df = pd.read_parquet(p, columns=["t_msc", "bid", "ask"])
                t_sec = df["t_msc"].to_numpy(dtype=np.float64) / 1000.0
                self._cache[ym] = (
                    t_sec,
                    df["bid"].to_numpy(dtype=np.float64),
                    df["ask"].to_numpy(dtype=np.float64),
                )
        return self._cache[ym]

    @staticmethod
    def _ym(t_sec: float) -> str:
        d = datetime.utcfromtimestamp(t_sec)
        return f"{d.year}{d.month:02d}"

    @staticmethod
    def _shift(ym: str, k: int) -> str:
        y, m = int(ym[:4]), int(ym[4:]) + k
        if m == 0:
            y, m = y - 1, 12
        elif m == 13:
            y, m = y + 1, 1
        return f"{y}{m:02d}"

    def window(self, t_center: float, half_window_s: float) -> tuple[np.ndarray, np.ndarray]:
        """(bid, ask) arrays con t en [t_center - hw, t_center + hw]."""
        t0, t1 = t_center - half_window_s, t_center + half_window_s
        yms = sorted({
            self._shift(self._ym(t0), -1), self._ym(t0),
            self._ym(t1), self._shift(self._ym(t1), 1),
        })
        bids: list[np.ndarray] = []
        asks: list[np.ndarray] = []
        for ym in yms:
            loaded = self._load_month(ym)
            if loaded is None:
                continue
            t_sec, bid, ask = loaded
            lo = int(np.searchsorted(t_sec, t0, "left"))
            hi = int(np.searchsorted(t_sec, t1, "right"))
            if hi > lo:
                bids.append(bid[lo:hi])
                asks.append(ask[lo:hi])
        if not bids:
            return np.array([]), np.array([])
        return np.concatenate(bids), np.concatenate(asks)


# ---------------------------------------------------------------------------
# Carga y emparejamiento (I/O)
# ---------------------------------------------------------------------------


def _f(row: dict, key: str) -> float | None:
    v = row.get(key, "")
    if v is None or str(v).strip() == "":
        return None
    return float(v)


def cargar_eventos_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cargar_verdad_terreno(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cargar_sl_clamped_open_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def emparejar_side_open(
    evento_csv_row: dict, verdad: list[dict]
) -> tuple[str | None, str | None, int | None]:
    """Empareja un evento SL_CLAMPED OPEN (sin ticket: la posicion aun no
    existe) con la posicion resultante via (config -> strategy_id) y
    cercania temporal a t_open_epoch. Devuelve (side L/S, position_id,
    |delta_seg|) o (None, None, delta_del_mejor_candidato_o_None) si no hay
    candidato dentro de la tolerancia."""
    config = evento_csv_row.get("config")
    epoch = evento_csv_row.get("epoch")
    if not config or epoch is None:
        return None, None, None
    strategy_id = CONFIG_TO_STRATEGY.get(config)
    if strategy_id is None:
        return None, None, None
    candidatos = [v for v in verdad if v.get("strategy_id") == strategy_id]
    if not candidatos:
        return None, None, None
    mejor = min(candidatos, key=lambda v: abs(int(v["t_open_epoch"]) - int(epoch)))
    delta = abs(int(mejor["t_open_epoch"]) - int(epoch))
    if delta > MATCH_DELTA_TOLERANCE_SEC:
        return None, None, delta
    return SIDE_TO_LS.get(mejor["side"]), mejor["position_id"], delta


def emparejar_side_por_ticket(
    ticket: str | None, verdad_por_position_id: dict[str, dict]
) -> str | None:
    """Empareja un evento SL_CLAMPED (posicion ya viva; el log usa `ticket`
    para lo que en verdad_terreno_902.csv es `position_id`, verificado
    empiricamente -- no es ticket_in/ticket_out de MT5)."""
    if not ticket:
        return None
    row = verdad_por_position_id.get(ticket)
    if row is None:
        return None
    return SIDE_TO_LS.get(row.get("side"))


def construir_eventos_familia(
    filas_csv: list[dict],
    event_name: str,
    verdad: list[dict],
    verdad_por_position_id: dict[str, dict],
) -> tuple[list[dict], dict]:
    """Convierte filas crudas del CSV de eventos en la forma que consume
    `procesar_familia`, emparejando side por la via que corresponda a la
    familia. Devuelve (eventos, stats_emparejamiento)."""
    eventos: list[dict] = []
    n_side_emparejado = 0
    n_side_no_emparejado = 0

    for row in filas_csv:
        if row.get("event") != event_name:
            continue
        epoch = row.get("epoch")
        ref = _f(row, "ref")
        clamped = _f(row, "clamped")
        desired_sl = _f(row, "desired_sl")
        if desired_sl is None:
            # Para SL_CLAMPED / SL_CLAMPED OPEN el log no llena `desired_sl`;
            # el SL deseado esta en la columna `desired`.
            desired_sl = _f(row, "desired")

        if event_name == "SL_CLAMPED OPEN":
            side, position_id, _delta = emparejar_side_open(row, verdad)
        else:
            side, position_id = emparejar_side_por_ticket(
                row.get("ticket"), verdad_por_position_id
            ), row.get("ticket")

        if side is not None:
            n_side_emparejado += 1
        else:
            n_side_no_emparejado += 1

        eventos.append(
            {
                "epoch": int(epoch) if epoch not in (None, "") else None,
                "timestamp_servidor": row.get("timestamp_servidor"),
                "config": row.get("config") or None,
                "ficha": row.get("ficha") or None,
                "ticket": row.get("ticket") or None,
                "side": side,
                "position_id_emparejado": position_id,
                "ref": ref,
                "clamped": clamped,
                "desired_sl": desired_sl,
            }
        )

    return eventos, {
        "n_side_emparejado": n_side_emparejado,
        "n_side_no_emparejado": n_side_no_emparejado,
    }


def construir_eventos_ticks_open(
    json_events: list[dict],
    verdad: list[dict],
    loader: TickWindowLoader,
    half_window_s: float,
) -> tuple[list[dict], dict]:
    """Familia SL_CLAMPED OPEN (87, via JSON, con `ms`): centro = epoch +
    ms/1000. side por (config,ficha,epoch) -> strategy_id -> posicion mas
    cercana (emparejar_side_open, mismo criterio que la via log)."""
    eventos_ticks: list[dict] = []
    n_sin_side = 0
    n_sin_ticks = 0
    for e in json_events:
        row_like = {"config": e.get("config"), "ficha": e.get("ficha"), "epoch": e.get("epoch")}
        side, position_id, _delta = emparejar_side_open(row_like, verdad)
        if side is None:
            n_sin_side += 1
            continue
        t_center = e["epoch"] + e.get("ms", 0) / 1000.0
        bid, ask = loader.window(t_center, half_window_s)
        if len(bid) == 0 or len(ask) == 0:
            n_sin_ticks += 1
            continue
        eventos_ticks.append(
            {
                "epoch": e["epoch"],
                "ms": e.get("ms"),
                "config": e.get("config"),
                "ficha": e.get("ficha"),
                "side": side,
                "position_id_emparejado": position_id,
                "clamped": float(e["clamped"]),
                "desired": float(e.get("desired")) if e.get("desired") is not None else None,
                "bid_min": float(bid.min()),
                "bid_max": float(bid.max()),
                "ask_min": float(ask.min()),
                "ask_max": float(ask.max()),
                "n_ticks_ventana": int(len(bid)),
            }
        )
    return eventos_ticks, {
        "n_total": len(json_events),
        "n_sin_side": n_sin_side,
        "n_sin_ticks_en_ventana": n_sin_ticks,
        "n_evaluable": len(eventos_ticks),
    }


def construir_eventos_ticks_modify(
    eventos_csv_family: list[dict],
    loader: TickWindowLoader,
    half_window_s: float,
) -> tuple[list[dict], dict]:
    """Familia SL_CLAMPED (35, via CSV, sin `ms`): centro = epoch (entero).
    side ya viene emparejado en `eventos_csv_family` (via ticket ==
    position_id, `construir_eventos_familia`)."""
    eventos_ticks: list[dict] = []
    n_sin_side = 0
    n_sin_ticks = 0
    for e in eventos_csv_family:
        if e.get("side") is None:
            n_sin_side += 1
            continue
        if e.get("clamped") is None or e.get("epoch") is None:
            n_sin_ticks += 1
            continue
        t_center = float(e["epoch"])
        bid, ask = loader.window(t_center, half_window_s)
        if len(bid) == 0 or len(ask) == 0:
            n_sin_ticks += 1
            continue
        eventos_ticks.append(
            {
                "epoch": e["epoch"],
                "ticket": e.get("ticket"),
                "side": e["side"],
                "position_id_emparejado": e.get("position_id_emparejado"),
                "clamped": float(e["clamped"]),
                "bid_min": float(bid.min()),
                "bid_max": float(bid.max()),
                "ask_min": float(ask.min()),
                "ask_max": float(ask.max()),
                "n_ticks_ventana": int(len(bid)),
            }
        )
    return eventos_ticks, {
        "n_total": len(eventos_csv_family),
        "n_sin_side": n_sin_side,
        "n_sin_ticks_en_ventana": n_sin_ticks,
        "n_evaluable": len(eventos_ticks),
    }


def construir_reporte_via_ticks(
    eventos_open_json: list[dict],
    eventos_modify_csv: list[dict],
    verdad: list[dict],
    tickdir: Path = DEFAULT_TICKDIR,
) -> dict:
    """Orquesta la via de inversion contra ticks para ambas familias.
    OPEN: barrido de sensibilidad en 3 ventanas (+/-0.25s, +/-1s, +/-3s).
    MODIFY: una sola ventana (+/-1s, minimo declarado -- sin `ms`)."""
    loader = TickWindowLoader(tickdir)
    l_grid = grid_L()

    resultado_open: dict[str, dict] = {}
    for hw in OPEN_HALF_WINDOWS_SEC:
        eventos_ticks, stats = construir_eventos_ticks_open(eventos_open_json, verdad, loader, hw)
        curva = barrer_consistencia(eventos_ticks, l_grid)
        resultado_open[f"{hw:.2f}"] = {
            "half_window_s": hw,
            **stats,
            "curva": curva,
            "resumen": resumen_curva(curva, stats["n_evaluable"]),
        }

    eventos_ticks_mod, stats_mod = construir_eventos_ticks_modify(
        eventos_modify_csv, loader, MODIFY_HALF_WINDOW_SEC
    )
    curva_mod = barrer_consistencia(eventos_ticks_mod, l_grid)
    resultado_modify = {
        f"{MODIFY_HALF_WINDOW_SEC:.2f}": {
            "half_window_s": MODIFY_HALF_WINDOW_SEC,
            **stats_mod,
            "curva": curva_mod,
            "resumen": resumen_curva(curva_mod, stats_mod["n_evaluable"]),
            "nota_resolucion": (
                "epoch entero, sin ms (menor resolucion temporal que la familia "
                "SL_CLAMPED OPEN); ventana minima declarada +/-1s, sin barrido de "
                "sensibilidad adicional."
            ),
        }
    }

    return {
        "fuente_ticks": "data/lake_ticks/XAUUSD/<YYYYMM>.parquet (t_msc, bid, ask), leido "
        "directamente con pandas.read_parquet en TickWindowLoader (reimplementacion propia, "
        "no reutiliza scripts/analysis/realtick_bt/backtest.py:Ticks).",
        "grid_L": {"min": L_GRID_MIN, "max": L_GRID_MAX, "step": L_GRID_STEP},
        "SL_CLAMPED OPEN": {"ventanas": resultado_open},
        "SL_CLAMPED": {"ventanas": resultado_modify},
    }


# ---------------------------------------------------------------------------
# Orquestacion + artefactos
# ---------------------------------------------------------------------------


def _ruta_reportable(path: Path) -> str:
    """Ruta relativa a ROOT en forward-slash cuando es posible, para que el
    artefacto no lleve rutas absolutas de host."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _git_sha(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "UNKNOWN"


def _jsonable(obj: Any) -> Any:
    """Convierte Counters/valores no serializables a formas planas para json.dump."""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, Counter):
        return dict(obj)
    return obj


def construir_reporte(
    eventos_csv: Path,
    sl_clamped_open_json: Path,
    verdad_terreno_csv: Path,
    tickdir: Path = DEFAULT_TICKDIR,
    incluir_via_ticks: bool = True,
) -> dict:
    filas_csv = cargar_eventos_csv(eventos_csv)
    verdad = cargar_verdad_terreno(verdad_terreno_csv)
    verdad_por_position_id = {v["position_id"]: v for v in verdad}
    json_87 = cargar_sl_clamped_open_json(sl_clamped_open_json)

    eventos_open, stats_open = construir_eventos_familia(
        filas_csv, "SL_CLAMPED OPEN", verdad, verdad_por_position_id
    )
    eventos_modify, stats_modify = construir_eventos_familia(
        filas_csv, "SL_CLAMPED", verdad, verdad_por_position_id
    )
    eventos_total = eventos_open + eventos_modify

    familia_open = procesar_familia(eventos_open)
    familia_modify = procesar_familia(eventos_modify)
    familia_total = procesar_familia(eventos_total)

    cuadre_json = {
        "n_json_sl_clamped_open_events": len(json_87),
        "n_csv_sl_clamped_open": familia_open["n"],
        "coincide": len(json_87) == familia_open["n"],
    }

    via_ticks = None
    if incluir_via_ticks:
        via_ticks = construir_reporte_via_ticks(json_87, eventos_modify, verdad, tickdir)

    reporte = {
        "lineage": {
            "run_id": f"T0.7-p-cap-stops-level-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "area": AREA,
            "experimento": EXPERIMENTO,
            "git_sha": _git_sha(ROOT),
            "engine_sha": ENGINE_SHA,
            "etapa": "F0",
            "generador": GENERADOR,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "fuentes": {
            "eventos_csv": _ruta_reportable(eventos_csv),
            "sl_clamped_open_json": _ruta_reportable(sl_clamped_open_json),
            "verdad_terreno_csv": _ruta_reportable(verdad_terreno_csv),
        },
        "cuadre_json_87": cuadre_json,
        "emparejamiento_side": {
            "SL_CLAMPED OPEN": stats_open,
            "SL_CLAMPED": stats_modify,
        },
        "familias": {
            "SL_CLAMPED OPEN": familia_open,
            "SL_CLAMPED": familia_modify,
            "TOTAL": familia_total,
        },
        "via_ticks": via_ticks,
    }
    return reporte


def _fmt_num(v):
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.5f}"
    return str(v)


def escribir_json(reporte: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_jsonable(reporte), fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")


def _md_familia(nombre: str, familia: dict, stats_side: dict) -> list[str]:
    lines = [f"## Familia `{nombre}`", ""]
    lines.append(f"- n eventos: {familia['n']}")
    lines.append(f"- n usables (ref y clamped presentes): {familia['n_usable']}")
    lines.append(f"- n descartados: {familia['n_descartados']}")
    for motivo, c in familia["motivos_descartados"].items():
        lines.append(f"  - {motivo}: {c}")
    lines.append(
        f"- side emparejado: {stats_side['n_side_emparejado']} / "
        f"no emparejado: {stats_side['n_side_no_emparejado']}"
    )
    lines.append("")
    r = familia["resumen_niveles"]
    lines.append("### Distribucion de `level_i`")
    lines.append("")
    if r["n"] == 0:
        lines.append("Sin eventos usables -- no hay `level_i` que reportar.")
    else:
        lines.append(f"- n: {r['n']}")
        lines.append(f"- min: {_fmt_num(r['min'])} · max: {_fmt_num(r['max'])} · "
                      f"mediana: {_fmt_num(r['mediana'])} · moda: {_fmt_num(r['moda'])}")
        lines.append(f"- constante: {r['es_constante']}")
        lines.append("")
        lines.append("| level_i | frecuencia |")
        lines.append("|---|---|")
        for v, c in r["valores"].items():
            lines.append(f"| {v} | {c} |")
    lines.append("")

    lines.append("### Desglose por side")
    lines.append("")
    if not familia["desglose_side"]:
        lines.append("(sin eventos con side emparejado y usable)")
    else:
        for side, rs in familia["desglose_side"].items():
            lines.append(f"- `{side}`: n={rs['n']}, valores={rs['valores']}")
    lines.append("")

    lines.append("### Desglose por config")
    lines.append("")
    if not familia["desglose_config"]:
        lines.append("(sin eventos con config y usable)")
    else:
        for cfg, rs in familia["desglose_config"].items():
            lines.append(f"- `{cfg}`: n={rs['n']}, valores={rs['valores']}")
    lines.append("")

    if familia["discrepancias"]:
        lines.append("### Eventos discrepantes (level_i != moda)")
        lines.append("")
        lines.append("| epoch | timestamp_servidor | config | ficha | ref | clamped | level_i |")
        lines.append("|---|---|---|---|---|---|---|")
        for ev in familia["discrepancias"]:
            lines.append(
                f"| {ev.get('epoch')} | {ev.get('timestamp_servidor')} | "
                f"{ev.get('config')} | {ev.get('ficha')} | {_fmt_num(ev.get('ref'))} | "
                f"{_fmt_num(ev.get('clamped'))} | {_fmt_num(ev.get('level_i'))} |"
            )
        lines.append("")

    vs = familia["verificacion_signo"]
    lines.append("### Verificacion de signo")
    lines.append("")
    lines.append(f"- ok: {vs['n_ok']} · fail: {vs['n_fail']}")
    if vs["fails"]:
        lines.append("")
        lines.append("| epoch | config | ficha | side | ref | clamped | level_i |")
        lines.append("|---|---|---|---|---|---|---|")
        for ev in vs["fails"]:
            lines.append(
                f"| {ev.get('epoch')} | {ev.get('config')} | {ev.get('ficha')} | "
                f"{ev.get('side')} | {_fmt_num(ev.get('ref'))} | {_fmt_num(ev.get('clamped'))} | "
                f"{_fmt_num(ev.get('level_i'))} |"
            )
    lines.append("")

    vn = familia["verificacion_necesidad"]
    lines.append("### Verificacion de necesidad")
    lines.append("")
    lines.append(
        f"- ok: {vn['n_ok']} · fail: {vn['n_fail']} · no evaluable (sin desired_sl): "
        f"{vn['n_no_evaluable']}"
    )
    if vn["fails"]:
        lines.append("")
        lines.append("| epoch | config | ficha | side | desired_sl | ref | level_i |")
        lines.append("|---|---|---|---|---|---|---|")
        for ev in vn["fails"]:
            lines.append(
                f"| {ev.get('epoch')} | {ev.get('config')} | {ev.get('ficha')} | "
                f"{ev.get('side')} | {_fmt_num(ev.get('desired_sl'))} | {_fmt_num(ev.get('ref'))} | "
                f"{_fmt_num(ev.get('level_i'))} |"
            )
    lines.append("")
    return lines


def _md_ventana_ticks(nombre_familia: str, hw_key: str, v: dict) -> list[str]:
    lines = [f"### Ventana +/-{v['half_window_s']}s", ""]
    lines.append(f"- eventos fuente: {v['n_total']}")
    lines.append(f"- sin side emparejado: {v['n_sin_side']}")
    lines.append(f"- sin ticks en la ventana: {v['n_sin_ticks_en_ventana']}")
    lines.append(f"- evaluables: {v['n_evaluable']}")
    if v.get("nota_resolucion"):
        lines.append(f"- nota de resolucion: {v['nota_resolucion']}")
    lines.append("")
    r = v["resumen"]
    if r["max_n"] is None:
        lines.append("Sin eventos evaluables -- no hay curva que reportar.")
    else:
        lines.append(f"- max_n consistentes: {r['max_n']} de {v['n_evaluable']} "
                      f"(fraccion: {_fmt_num(r['fraccion_max'])})")
        lines.append(f"- L ganador unico: {r['L_ganador_unico'] if r['L_ganador_unico'] else 'n/a (empate)'}")
        lines.append(f"- L empatados en el maximo: {r['L_empatados_en_max']}")
        lines.append("")
        lines.append("Top-5 puntos de la curva (L, n_consistentes):")
        lines.append("")
        lines.append("| L | n_consistentes |")
        lines.append("|---|---|")
        for item in r["top5"]:
            lines.append(f"| {item['L']} | {item['n']} |")
        lines.append("")
        lines.append("Curva completa `L -> n_consistentes` (rejilla 0.00-2.00, paso 0.01): "
                      "ver capa maquina (`stops_level_derivado.json`, "
                      f"`via_ticks.{nombre_familia!r}.ventanas[{hw_key!r}].curva`).")
    lines.append("")
    return lines


def _md_via_ticks(via_ticks: dict | None) -> list[str]:
    lines = ["## Via ticks (ronda de correccion 1 -- inversion contra ticks reales)", ""]
    if via_ticks is None:
        lines.append("No se ejecuto (via_ticks=None).")
        lines.append("")
        return lines
    lines.append(f"- fuente de ticks: {via_ticks['fuente_ticks']}")
    g = via_ticks["grid_L"]
    lines.append(f"- rejilla de L: [{g['min']}, {g['max']}], paso {g['step']}")
    lines.append("")
    for nombre in ("SL_CLAMPED OPEN", "SL_CLAMPED"):
        lines.append(f"### Familia `{nombre}`")
        lines.append("")
        ventanas = via_ticks[nombre]["ventanas"]
        for hw_key in sorted(ventanas.keys(), key=float):
            lines.extend(_md_ventana_ticks(nombre, hw_key, ventanas[hw_key]))
    return lines


def escribir_md(reporte: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lin = reporte["lineage"]
    lines = [
        "# T0.7-P-CAP -- stops_level derivado de eventos de clamp (b113eb7)",
        "",
        "INVESTIGADOR REPORT-ONLY. Sin conclusiones ni recomendaciones: numeros, "
        "rutas y conteos.",
        "",
        "## Lineage",
        "",
        f"- run_id: `{lin['run_id']}`",
        f"- area: `{lin['area']}`",
        f"- experimento: `{lin['experimento']}`",
        f"- git_sha: `{lin['git_sha']}`",
        f"- engine_sha: `{lin['engine_sha']}`",
        f"- etapa: `{lin['etapa']}`",
        f"- generador: `{lin['generador']}`",
        f"- timestamp: `{lin['timestamp']}`",
        "",
        "## Fuentes",
        "",
        f"- eventos_csv: `{reporte['fuentes']['eventos_csv']}`",
        f"- sl_clamped_open_json: `{reporte['fuentes']['sl_clamped_open_json']}`",
        f"- verdad_terreno_csv: `{reporte['fuentes']['verdad_terreno_csv']}`",
        "",
        "## Cuadre contra la fuente secundaria (87 eventos SL_CLAMPED OPEN)",
        "",
        f"- n en JSON: {reporte['cuadre_json_87']['n_json_sl_clamped_open_events']}",
        f"- n en CSV (event=SL_CLAMPED OPEN): {reporte['cuadre_json_87']['n_csv_sl_clamped_open']}",
        f"- coincide: {reporte['cuadre_json_87']['coincide']}",
        "",
    ]
    for nombre in ("SL_CLAMPED OPEN", "SL_CLAMPED", "TOTAL"):
        stats_side = reporte["emparejamiento_side"].get(
            nombre, {"n_side_emparejado": "n/a", "n_side_no_emparejado": "n/a"}
        )
        lines.extend(_md_familia(nombre, reporte["familias"][nombre], stats_side))

    lines.append("")
    lines.extend(_md_via_ticks(reporte.get("via_ticks")))

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eventos-csv", type=Path, default=DEFAULT_EVENTOS_CSV)
    ap.add_argument("--sl-clamped-open-json", type=Path, default=DEFAULT_SL_CLAMPED_OPEN_JSON)
    ap.add_argument("--verdad-terreno-csv", type=Path, default=DEFAULT_VERDAD_TERRENO_CSV)
    ap.add_argument("--tickdir", type=Path, default=DEFAULT_TICKDIR)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    ap.add_argument("--sin-via-ticks", action="store_true",
                     help="omite la via de inversion contra ticks (mas rapido; solo la via log).")
    args = ap.parse_args()

    reporte = construir_reporte(
        args.eventos_csv, args.sl_clamped_open_json, args.verdad_terreno_csv,
        tickdir=args.tickdir, incluir_via_ticks=not args.sin_via_ticks,
    )
    escribir_json(reporte, args.out_json)
    escribir_md(reporte, args.out_md)

    total = reporte["familias"]["TOTAL"]
    print(f"SL_CLAMPED OPEN: n={reporte['familias']['SL_CLAMPED OPEN']['n']}, "
          f"usable={reporte['familias']['SL_CLAMPED OPEN']['n_usable']}")
    print(f"SL_CLAMPED: n={reporte['familias']['SL_CLAMPED']['n']}, "
          f"usable={reporte['familias']['SL_CLAMPED']['n_usable']}")
    print(f"TOTAL: n={total['n']}, usable={total['n_usable']}")
    if reporte.get("via_ticks"):
        for nombre in ("SL_CLAMPED OPEN", "SL_CLAMPED"):
            ventanas = reporte["via_ticks"][nombre]["ventanas"]
            for hw_key, v in sorted(ventanas.items(), key=lambda kv: float(kv[0])):
                r = v["resumen"]
                print(f"via_ticks[{nombre} +/-{hw_key}s]: evaluable={v['n_evaluable']} "
                      f"max_n={r['max_n']} L_ganador={r['L_ganador_unico']} "
                      f"empatados={r['L_empatados_en_max']}")
    print(f"JSON escrito: {args.out_json}")
    print(f"MD escrito: {args.out_md}")


if __name__ == "__main__":
    main()
