r"""A6 Pata A -- CAPA 1: techo alcanzable de la señal cruda de indicadores,
SIN estado de posición y SIN gate de spread.

Por qué. `scripts/analysis/a6_pata_a/signal_level.py` (NO tocado por este
script) midió la paridad de señal usando `run_ladder()`/`run_supertrend()` de
`scripts/analysis/realtick_bt/backtest.py`, que mezclan tres capas: (1) señal
cruda de indicadores, (2) estado de posición (el motor no re-evalúa entrada
mientras hay ficha abierta -- el choke `if fichas: continue`), y (3) gate de
spread (fuera del alcance de este script). Este script AISLA la capa 1: para
cada barra M15, evalúa si la condición de entrada ES CIERTA en términos
puramente deterministas de barras + config, IGNORANDO si el motor "real"
habría estado ocupado en ese instante.

CLASIFICACIÓN DEL BLOQUE DE ENTRADA DE S6-K2P0
-----------------------------------------------
Fuente: `sentinel_engine/strategies/emasar_variant.py` (NO modificado -- R1-bis),
función `simular_variant`, bucle principal `for i in range(n):` (línea 704).

ESTADO-LIBRES (función determinista de bars + config; SÍ se re-implementan
en este módulo):
  * emasar_variant.py:568-584 -- régimen SAR adaptativo (V-15, `sar_adaptive`):
    dos series SAR (`sar_fast`/`sar_slow`) + mediana móvil de ATR14 sobre
    `vol_regime_window` barras decide, POR BARRA, cuál serie de SAR-trend está
    activa. Depende solo de bars + config, no de si hay ficha abierta.
    Copiado VERBATIM abajo (no es una función nombrada a nivel de módulo, así
    que no es importable -- ver `_sar_trend_adaptive` más abajo).
  * emasar_variant.py:1169-1175 -- filtro de hora bloqueada (V-11,
    `blocked_hours`): función determinista de `bar["t"]` + config. NO-OP para
    S6-K2P0 (`blocked_hours=None` en `_GL["S6-K2P0"]`, el default).
  * emasar_variant.py:1214-1277 -- cómputo de `long_ok`/`short_ok` vía
    `gate_long`/`gate_short` de `emasar_ref.py` (importados sin modificar):
    para `entry_timing=0` (el default, y el valor efectivo de la config viva
    S6-K2P0, que no lo sobre-escribe) es la rama `else` (líneas 1269-1277):
    dos llamadas a `gate_long`/`gate_short` con `confirm_mode`, `confirm_count`,
    `require_ema_order` de la config -- función pura de bars + las series de
    indicador (EMA8/20, SAR-trend, AO, AC, Momentum) computadas más arriba
    (emasar_variant.py:558-563). CERO dependencia de fichas abiertas.
  * emasar_variant.py:1279-1293 -- filtro G5 "rojo->verde" (V-08, `g5_mode`):
    determinista de la serie AC. NO-OP para S6-K2P0 (`g5_mode='ref'`, default).
  * emasar_variant.py:1295-1304 -- filtro de régimen SuperTrend-M15
    (V-10, `direction_mask`): determinista de una máscara precomputada por
    barra. NO-OP para S6-K2P0 (`direction_mask=None`, default).
  * emasar_variant.py:1410-1439 (la mitad "cuál lado" del bloque, IGNORANDO el
    guard de arriba) -- `if long_ok and allow_long: ENTRY_L / elif short_ok
    and allow_short: ENTRY_S`. `allow_long`/`allow_short` son flags de config
    (no de estado); S6-K2P0 no los sobre-escribe (ambos True por default).

ESTADO-DEPENDIENTES (dependen de si hay posición abierta, de cooldowns, de
reversals o de pendientes entre barras; NO se re-implementan -- se OMITEN a
propósito, que es justamente lo que separa la Capa 1 de `run_ladder`):
  * emasar_variant.py:1117 `if fichas:` -- el choke de ocupación: mientras hay
    alguna ficha abierta, la evaluación de entrada de esta barra se salta
    (`continue`) salvo que `stop_and_reverse` dispare un reverse. Depende del
    diccionario `fichas` (estado mutable entre barras). ESTE es el guard que
    la Capa 1 elimina deliberadamente: aquí se evalúa la condición de entrada
    en TODAS las barras, esté el motor "ocupado" o no.
  * emasar_variant.py:1117-1159 -- mecánica de `stop_and_reverse` (P55):
    cuando hay posición abierta Y `stop_and_reverse=True` (cierto para
    S6-K2P0), se re-evalúa el gate para decidir si hay reverse -- pero la
    llamada a gate_long/gate_short en sí (líneas 1121-1128) usa los MISMOS
    parámetros que la rama estado-libre de abajo, así que no aporta ninguna
    condición NUEVA sobre la señal cruda; lo que SÍ es estado-dependiente es
    si el evento ENTRY_L/ENTRY_S llega a emitirse (solo se emite si antes hubo
    reverse O si no había ficha abierta). Es decir: el candidato crudo ya
    incluye estas barras (mismo gate), pero `run_ladder` puede NO emitir un
    evento ahí si el motor seguía ocupado sin reverse.
  * emasar_variant.py:1102-1105, 1161-1212 -- reentrada V-13 (`reentry_enable`,
    `reentry_armed`, `reentry_count`, `reentry_lado`): estado que persiste
    entre barras (armado tras un trail-out completo). NO-OP para S6-K2P0
    (`reentry_enable=False`, default -- no está en `_GL["S6-K2P0"]`).
  * emasar_variant.py:1306-1355 -- confirmación diferida (P54, `confirm_bar`):
    `pending_confirm_lado` persiste un bar. NO-OP para S6-K2P0
    (`confirm_bar=False`, default).
  * emasar_variant.py:1357-1408 -- límite pullback resting (P33,
    `pullback_limit`): `pending_limit_lado` persiste un bar. NO-OP para
    S6-K2P0 (`pullback_limit=False`, default).

Como los cinco bloques NO-OP de arriba son en efecto inertes para la config
viva S6-K2P0 (verificado por `_ASSERT_NOOP_KWARGS` abajo, que aborta si algún
día la config deja de serlo), la Capa 1 de S6-K2P0 se reduce exactamente a:
"para cada barra i, ¿`gate_long`/`gate_short` da True con los parámetros de
`_GL['S6-K2P0']`?" -- sin mirar nunca si el motor tenía una ficha abierta.

SuperTrend-p14x3-M15 (Paso 3 del prompt): candidato crudo = flip de tendencia
del SuperTrend(14, 3.0) vendido en `_supertrend_ref.supertrend`, que ya es
puramente causal/determinista (no usa ningún estado de posición) -- se
reutiliza tal cual, replicando el preámbulo de
`scripts/analysis/realtick_bt/backtest.py:288-307` (`run_supertrend`).

Salida: data/analysis/a6_pata_a/capa1_senal_cruda.json
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
import pandas as pd

ROOT = Path(r"D:\FOREX")
sys.path.insert(0, str(ROOT))

from scripts.analysis.realtick_bt.backtest import (  # noqa: E402
    _GL, run_ladder, run_supertrend, Ticks,
)
from sentinel_engine.strategies.emasar_ref import (  # noqa: E402
    ema_series, sar_series, ao_series, ac_series, momentum_series,
    gate_long, gate_short, _atr_wilder,
)
from sentinel_engine.strategies._supertrend_ref import supertrend  # noqa: E402

BAR_SEC = 900
POS_CSV = ROOT / "data" / "analysis" / "2883016902" / "2883016902_positions.csv"
CAPITARIA_BARS = ROOT / "data" / "lake_bars_capitaria" / "XAUUSD_M15.parquet"
OUT_JSON = ROOT / "data" / "analysis" / "a6_pata_a" / "capa1_senal_cruda.json"
THIS_SCRIPT = Path(__file__).resolve()

WINDOW_START = "2026-07-27 18:53:30"
WINDOW_END = "2026-08-11 01:15:04"

STRAT_S6 = "S6-K2P0"
STRAT_ST = "SuperTrend-p14x3-M15"
STRATS = [STRAT_S6, STRAT_ST]


def to_epoch(s: str) -> float:
    """Server-wall-clock string -> epoch, WITHOUT reapplying host-local offset."""
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    return float(calendar.timegm(dt.timetuple()))


WIN0 = to_epoch(WINDOW_START)
WIN1 = to_epoch(WINDOW_END)


def fmt(t: float) -> str:
    return datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- bars
def load_bars(path: Path) -> list[dict[str, Any]]:
    df = pd.read_parquet(path)
    return [{"t": int(r.t), "open": float(r.o), "high": float(r.h),
              "low": float(r.l), "close": float(r.c), "volume": int(r.v)}
             for r in df.itertuples()]


# --------------------------------------------------------------------------- real ground truth
# Replica EXACTA de scripts/analysis/a6_pata_a/signal_level.py:145-167
# (léelo -- no adivinado). load_real_signals() no se importa porque ese
# módulo no expone nada a nivel de paquete pensado para reimport limpio
# (es un script `if __name__ == "__main__"`); se reproduce aquí la MISMA
# lógica, bucket=epoch//900*900, dir BUY->L/SELL->S.
def load_real_signals() -> dict[str, dict[str, Any]]:
    df = pd.read_csv(POS_CSV)
    df["epoch"] = df["open_srv"].map(to_epoch)
    df = df[(df["epoch"] >= WIN0) & (df["epoch"] <= WIN1)].copy()
    df["bucket"] = (df["epoch"] // BAR_SEC * BAR_SEC).astype(int)
    df["dir"] = df["side"].map({"BUY": "L", "SELL": "S"})

    out: dict[str, dict[str, Any]] = {}
    for strat in STRATS:
        sub = df[df["strategy"] == strat]
        g = sub.groupby(["bucket", "dir"])
        n_pos_per_bar = g.size()
        sigs = []
        for (bucket, d), cnt in n_pos_per_bar.items():
            sigs.append({"t": int(bucket), "dir": d, "n_positions": int(cnt)})
        dirs_per_bucket = sub.groupby("bucket")["dir"].nunique()
        mixed = int((dirs_per_bucket > 1).sum())
        sigs.sort(key=lambda x: x["t"])
        out[strat] = {"signals": sigs, "n_positions_total": int(len(sub)),
                       "n_signal_bars": len(sigs), "mixed_direction_bars": mixed,
                       "sub_df": sub}
    return out


# --------------------------------------------------------------------------- S6-K2P0 capa 1
def _sar_trend_adaptive(highs: list[float], lows: list[float], closes: list[float],
                         sar_fast: tuple[float, float], sar_slow: tuple[float, float],
                         vol_regime_window: int) -> list[int]:
    """Copiado VERBATIM de emasar_variant.py:568-584 (bloque `if sar_adaptive:`
    dentro de `simular_variant`) -- NO es una función nombrada a nivel de
    módulo en el motor (vive inline en el bucle de `simular_variant`), así
    que no es importable; se re-implementa aquí citando la fuente exacta,
    byte-por-byte salvo el envoltorio en función. Estado-libre: función pura
    de bars + config, no de si hay ficha abierta."""
    n = len(closes)
    _sar_val_fast, sar_trend_fast = sar_series(highs, lows, sar_fast[0], sar_fast[1])
    _sar_val_slow, sar_trend_slow = sar_series(highs, lows, sar_slow[0], sar_slow[1])
    atr14 = _atr_wilder(highs, lows, closes, 14)
    sar_trend = [0] * n
    for i in range(n):
        regime_fast = False
        if atr14[i] is not None:
            lo = max(0, i - vol_regime_window)
            window_vals = [v for v in atr14[lo:i] if v is not None]
            if len(window_vals) >= max(1, vol_regime_window // 2):
                sorted_vals = sorted(window_vals)
                m = len(sorted_vals)
                median = (sorted_vals[m // 2] if m % 2 == 1
                          else (sorted_vals[m // 2 - 1] + sorted_vals[m // 2]) / 2.0)
                regime_fast = atr14[i] > median
        sar_trend[i] = sar_trend_fast[i] if regime_fast else sar_trend_slow[i]
    return sar_trend


# Kwargs que, si distintos de su valor NO-OP en la config viva, invalidarían
# la reducción documentada arriba (la Capa 1 de S6-K2P0 == gate_long/gate_short
# puro). Si alguno cambia de valor en `_GL["S6-K2P0"]` este script debe PARAR,
# no seguir reportando cifras silenciosamente erróneas.
_NOOP_DEFAULTS = {
    "entry_timing": 0,
    "g5_mode": "ref",
    "direction_mask": None,
    "confirm_bar": False,
    "pullback_limit": False,
    "blocked_hours": None,
    "reentry_enable": False,
}


def _assert_noop_kwargs(kwargs: dict[str, Any], strat_id: str) -> None:
    for k, expected in _NOOP_DEFAULTS.items():
        actual = kwargs.get(k, expected)
        if actual != expected:
            raise RuntimeError(
                f"ANOMALIA: {strat_id} kwargs[{k!r}]={actual!r} != no-op esperado "
                f"{expected!r}. La reduccion de la Capa 1 documentada en el modulo "
                f"asume que este kwarg es un no-op para la config viva -- ya no lo "
                f"es, PARAR y re-evaluar la clasificacion estado-libre/estado-"
                f"dependiente antes de confiar en las cifras de este script.")


def s6_raw_candidates(bars: list[dict[str, Any]], kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    """Capa 1 de S6-K2P0: gate_long/gate_short puro, evaluado en TODAS las
    barras, sin mirar el estado de ocupación del motor (emasar_variant.py:1117
    `if fichas: continue` -- deliberadamente omitido)."""
    _assert_noop_kwargs(kwargs, STRAT_S6)

    n = len(bars)
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]

    ema_fast = kwargs.get("ema_fast", 5)
    ema_slow = kwargs.get("ema_slow", 8)
    ema_f = ema_series(closes, ema_fast)      # "ema8" gate arg (emasar_variant.py:558)
    ema_s = ema_series(closes, ema_slow)      # "ema20" gate arg (emasar_variant.py:559)
    ema5_unused = [None] * n                  # V1 (use_ema5=False) ignores this
    ao = ao_series(highs, lows)
    ac = ac_series(highs, lows)
    mom_period = kwargs.get("mom_period", 14)
    mom = momentum_series(closes, mom_period)

    sar_adaptive = kwargs.get("sar_adaptive", False)
    if sar_adaptive:
        sar_fast = kwargs.get("sar_fast", (0.3, 0.3))
        sar_slow = kwargs.get("sar_slow", (0.005, 0.05))
        vol_regime_window = kwargs.get("vol_regime_window", 200)
        sar_trend = _sar_trend_adaptive(highs, lows, closes, sar_fast, sar_slow, vol_regime_window)
    else:
        sar_step = kwargs.get("sar_step", 0.3)
        sar_max = kwargs.get("sar_max", 0.3)
        _sar_val, sar_trend = sar_series(highs, lows, sar_step, sar_max)

    confirm_mode = kwargs.get("confirm_mode", 2)
    confirm_count = kwargs.get("confirm_count", 2)
    require_ema_order = kwargs.get("require_ema_order", True)
    allow_long = kwargs.get("allow_long", True)
    allow_short = kwargs.get("allow_short", True)

    candidates: list[dict[str, Any]] = []
    for i in range(n):
        long_ok, _ = gate_long(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                                confirm_mode=confirm_mode, use_ema5=False,
                                confirm_count=confirm_count, require_ema_order=require_ema_order)
        short_ok, _ = gate_short(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                                  confirm_mode=confirm_mode, use_ema5=False,
                                  confirm_count=confirm_count, require_ema_order=require_ema_order)
        if long_ok and allow_long:
            candidates.append({"t": int(bars[i]["t"]), "dir": "L"})
        elif short_ok and allow_short:
            candidates.append({"t": int(bars[i]["t"]), "dir": "S"})
    return candidates


# --------------------------------------------------------------------------- SuperTrend capa 1
def st_raw_candidates(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Candidatos crudos ST = flips de tendencia, replicando el preámbulo de
    run_supertrend (scripts/analysis/realtick_bt/backtest.py:288-307)."""
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    atr = _atr_wilder(highs, lows, closes, 14)
    atrf = [a if a is not None else 0.0 for a in atr]
    trend, line = supertrend(highs, lows, closes, atrf, 3.0)
    fv = next((i for i in range(len(atr)) if atr[i] is not None), None)
    if fv is None:
        return []
    candidates = []
    for j in range(fv + 1, len(bars)):
        if trend[j] != trend[j - 1]:
            candidates.append({"t": int(bars[j]["t"]), "dir": "L" if trend[j] == 1 else "S"})
    return candidates


# --------------------------------------------------------------------------- coverage
def coverage(real_signals: list[dict[str, Any]], cand_set: set[tuple[int, str]],
             shifts: tuple[int, ...]) -> dict[str, Any]:
    """Una barra-señal real (t, dir) está cubierta si existe un candidato
    crudo (t + shift*BAR_SEC, dir) para algún shift en `shifts`."""
    n_real = len(real_signals)
    covered = []
    uncovered = []
    for s in real_signals:
        hit = any((s["t"] + sh * BAR_SEC, s["dir"]) in cand_set for sh in shifts)
        (covered if hit else uncovered).append(s)
    n_cov = len(covered)
    pct = round(100.0 * n_cov / n_real, 2) if n_real else None
    return {
        "n_real": n_real, "n_cubiertas": n_cov, "pct_cubiertas": pct,
        "no_cubiertas": [
            {"t": s["t"], "t_srv": fmt(s["t"]), "dir": s["dir"], "n_positions": s["n_positions"]}
            for s in sorted(uncovered, key=lambda x: x["t"])
        ],
    }


def percentile_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "min": None, "p25": None, "mediana": None, "p75": None, "max": None,
                "n_primeros_60s": 0}
    arr = np.array(values, dtype="float64")
    return {
        "n": len(values),
        "min": float(np.min(arr)),
        "p25": float(np.percentile(arr, 25)),
        "mediana": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "max": float(np.max(arr)),
        "n_primeros_60s": int(np.sum(arr < 60)),
    }


def main() -> int:
    print(f"window: {WINDOW_START} .. {WINDOW_END}  epoch [{WIN0},{WIN1}]")

    real = load_real_signals()
    for strat in STRATS:
        r = real[strat]
        print(f"  REAL {strat}: {r['n_positions_total']} posiciones -> {r['n_signal_bars']} "
              f"barras-señal (mixed_direction_bars={r['mixed_direction_bars']})")

    expected_n = {STRAT_S6: 49, STRAT_ST: 42}
    for strat in STRATS:
        got = real[strat]["n_signal_bars"]
        if got != expected_n[strat]:
            raise RuntimeError(
                f"ANOMALIA: {strat} produjo {got} barras-señal reales, se esperaban "
                f"{expected_n[strat]}. PARAR -- la ventana/agrupación no coincide con "
                f"signal_level.py:145-167.")

    cap_bars = load_bars(CAPITARIA_BARS)
    print(f"capitaria bars: {len(cap_bars)}  {fmt(cap_bars[0]['t'])} .. {fmt(cap_bars[-1]['t'])}")

    # ---- S6-K2P0 ----
    s6_kwargs = _GL[STRAT_S6]
    s6_cands = s6_raw_candidates(cap_bars, s6_kwargs)
    s6_cand_set = {(c["t"], c["dir"]) for c in s6_cands}

    s6_ladder_raw = run_ladder(s6_kwargs, cap_bars)
    s6_entries = sorted({(int(p["t_in"]), p["side_l"]) for p in s6_ladder_raw})
    s6_missing = [{"t": t, "t_srv": fmt(t), "dir": d} for t, d in s6_entries
                  if (t, d) not in s6_cand_set]
    s6_superset_ok = len(s6_missing) == 0
    print(f"\nS6-K2P0: candidatos crudos={len(s6_cands)}  run_ladder entradas unicas="
          f"{len(s6_entries)}  faltantes={len(s6_missing)}  superset_ok={s6_superset_ok}")

    # ---- SuperTrend-p14x3-M15 ----
    st_cands = st_raw_candidates(cap_bars)
    st_cand_epochs = {c["t"] for c in st_cands}

    st_ticks = Ticks()
    st_positions = run_supertrend(cap_bars, st_ticks)
    st_flip_exits = sorted({int(p["t_out"]) for p in st_positions if p["reason"] == "EXIT_STFLIP"})
    st_missing = [{"t": t, "t_srv": fmt(t)} for t in st_flip_exits if t not in st_cand_epochs]
    st_superset_ok = len(st_missing) == 0
    print(f"SuperTrend: candidatos crudos (flips)={len(st_cands)}  EXIT_STFLIP unicos="
          f"{len(st_flip_exits)}  faltantes={len(st_missing)}  superset_ok={st_superset_ok}")

    if not s6_superset_ok:
        print("\n*** FALLO DE AUTO-VERIFICACION S6 -- ver 'faltantes' en el JSON. PARAR. ***")
    if not st_superset_ok:
        print("\n*** FALLO DE AUTO-VERIFICACION ST -- ver 'faltantes' en el JSON. PARAR. ***")

    # ---- coverage ----
    shift_defs = {
        "cobertura_shift1": (-1,),
        "cobertura_shift0": (0,),
        "cobertura_shift1_mas_menos1": (-2, -1, 0),
    }
    coverage_out: dict[str, Any] = {}
    for strat, cand_set in [(STRAT_S6, s6_cand_set), (STRAT_ST, {(c["t"], c["dir"]) for c in st_cands})]:
        real_sigs = real[strat]["signals"]
        coverage_out[strat] = {name: coverage(real_sigs, cand_set, shifts)
                                for name, shifts in shift_defs.items()}

    n_cand_window = {
        STRAT_S6: sum(1 for c in s6_cands if WIN0 <= c["t"] <= WIN1),
        STRAT_ST: sum(1 for c in st_cands if WIN0 <= c["t"] <= WIN1),
    }

    # ---- Paso 5: segundos-en-barra de la PRIMERA posicion de cada barra-señal ----
    paso5: dict[str, Any] = {}
    for strat in STRATS:
        sub = real[strat]["sub_df"]
        first_per_bucket = sub.sort_values("epoch").groupby(["bucket", "dir"], as_index=False).first()
        secs = list((first_per_bucket["epoch"] % BAR_SEC).astype(float))
        paso5[strat] = percentile_summary(secs)

    # ---- metadatos ----
    try:
        git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                  text=True, check=True).stdout.strip()
    except Exception as exc:  # pragma: no cover
        git_sha = f"ERROR: {exc}"

    result: dict[str, Any] = {
        "window": {"start": WINDOW_START, "end": WINDOW_END, "epoch": [WIN0, WIN1]},
        "unit": "capa 1 -- señal cruda de indicador, SIN estado de posición, SIN gate de spread",
        "real_ground_truth": {
            strat: {
                "signals": real[strat]["signals"],
                "n_positions_total": real[strat]["n_positions_total"],
                "n_signal_bars": real[strat]["n_signal_bars"],
                "mixed_direction_bars": real[strat]["mixed_direction_bars"],
            } for strat in STRATS
        },
        "verificacion_superset": {
            STRAT_S6: {
                "n_entradas_run_ladder": len(s6_entries),
                "n_contenidas_en_candidatos": len(s6_entries) - len(s6_missing),
                "verificacion_superset_ok": s6_superset_ok,
                "faltantes": s6_missing,
            },
            STRAT_ST: {
                "n_exit_stflip_run_supertrend": len(st_flip_exits),
                "n_contenidas_en_candidatos": len(st_flip_exits) - len(st_missing),
                "verificacion_superset_ok": st_superset_ok,
                "faltantes": st_missing,
                "nota_st_reentradas": (
                    "Las re-entradas always-in tras EXIT_STLINE (toque intrabar de la linea "
                    "SuperTrend, run_supertrend() en scripts/analysis/realtick_bt/backtest.py:"
                    "288-332) NO estan en el conjunto de flips de este script: dependen del "
                    "estado (si la posicion always-in seguia abierta y a que precio tocaba la "
                    "linea intra-barra via ticks), no de un cambio de trend[] en el cierre de "
                    "barra. Es un hecho estructural del diseño always-in de ST, no una omision "
                    "de este script -- los flips de trend[] son el UNICO evento estado-libre "
                    "que produce SuperTrend(14,3.0)."
                ),
            },
        },
        "cobertura": coverage_out,
        "n_candidatos_crudos": {
            STRAT_S6: {"total": len(s6_cands), "en_ventana": n_cand_window[STRAT_S6]},
            STRAT_ST: {"total": len(st_cands), "en_ventana": n_cand_window[STRAT_ST]},
        },
        "candidatos_crudos": {
            STRAT_S6: s6_cands,
            STRAT_ST: st_cands,
        },
        "paso5_segundos_en_barra": paso5,
        "metadatos": {
            "generador": "scripts/analysis/a6_pata_a/capa1_senal_cruda.py",
            "git_sha": git_sha,
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "ficheros_entrada": [
                str(POS_CSV.relative_to(ROOT)).replace("\\", "/"),
                str(CAPITARIA_BARS.relative_to(ROOT)).replace("\\", "/"),
                "scripts/analysis/realtick_bt/backtest.py (run_ladder, run_supertrend, Ticks, _GL)",
                "sentinel_engine/strategies/emasar_variant.py (clasificacion estado-libre/"
                "estado-dependiente, NO modificado)",
                "sentinel_engine/strategies/emasar_ref.py (gate_long, gate_short, ema_series, "
                "sar_series, ao_series, ac_series, momentum_series, _atr_wilder -- importados, "
                "NO modificados)",
                "sentinel_engine/strategies/_supertrend_ref.py (supertrend -- importado, NO "
                "modificado)",
                "sentinel_engine/strategies/live_configs_20.py (_GOLIVE_M15 -- config viva, NO "
                "modificado)",
            ],
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {OUT_JSON}")

    # ---- console summary table ----
    print("\n== RESUMEN COBERTURA (Capa 1: señal cruda, sin estado, sin gate) ==")
    for strat in STRATS:
        print(f"\n-- {strat} --")
        for name in shift_defs:
            c = coverage_out[strat][name]
            print(f"  {name:28s} n_real={c['n_real']:3d} n_cubiertas={c['n_cubiertas']:3d} "
                  f"pct={c['pct_cubiertas']:>6}%")
        nc = n_candidatos_str = result["n_candidatos_crudos"][strat]
        print(f"  n_candidatos_crudos: total={nc['total']}  en_ventana={nc['en_ventana']}")
        p5 = paso5[strat]
        print(f"  Paso5 segundos-en-barra (n={p5['n']}): min={p5['min']} p25={p5['p25']} "
              f"mediana={p5['mediana']} p75={p5['p75']} max={p5['max']} "
              f"primeros_60s={p5['n_primeros_60s']}/{p5['n']}")

    print("\n== AUTO-VERIFICACION (gate duro) ==")
    print(f"  S6-K2P0: verificacion_superset_ok={s6_superset_ok}  "
          f"(run_ladder={len(s6_entries)}, contenidas={len(s6_entries) - len(s6_missing)})")
    print(f"  SuperTrend: verificacion_superset_ok={st_superset_ok}  "
          f"(EXIT_STFLIP={len(st_flip_exits)}, contenidas={len(st_flip_exits) - len(st_missing)})")

    return 0 if (s6_superset_ok and st_superset_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
