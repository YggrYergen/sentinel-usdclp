r"""Componente D de la réplica en harness del motor faulty (tag
engine-faulty-tomachine-902 -> b113eb7): el LLAMADOR de P-CAP.

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md
§4-bis (ADDENDUM 2026-08-13 -- Componente D, el LLAMADOR de P-CAP).

Une los tres componentes ya construidos y verdes:
  A · estado_por_barra.py  -- estado deseado del sim, por vela cerrada.
  B · ciclos.py             -- el bucle de reconciliación de 15 s.
  C · config_faulty.py      -- kwargs del roster tomachine, del commit
                                congelado b113eb7 (§2-bis), NUNCA del
                                working tree.

y corre la réplica sobre ticks de Capitaria y la ventana en que operó la
cuenta 902 (VENTANA_902), una estrategia a la vez (§D.3 -- RULING: es
equivalente a la reconciliación conjunta del ejecutor vivo porque el estado
deseado de cada config depende sólo de sus propias kwargs, las gates son
globales por tick -- no por config --, y la concurrencia real es 1 posición
por estrategia. Lo único que la réplica NO modela es el margen compartido de
cuenta -- declarado no modelado, D-32).

R1-bis: este módulo IMPORTA A / B / C, backtest.py y sentinel_engine/** --
JAMÁS los edita. Si algo aquí sugiriera tocar alguno de ellos: PARAR y
escalar, no arreglarlo aquí.

D.3, prohibición dura: este fichero NO importa nada de
`sentinel_engine.strategies.live_configs_20` (`_GOLIVE_M15`,
`CONFIGS_TOMACHINE`, ni ningún otro símbolo). Las kwargs SIEMPRE salen de
`config_faulty.kwargs_de()` (Componente C). `estado_por_barra_supertrend`
(Componente A) es quien internamente usa `supertrend_always_in_target` de
ese módulo para SuperTrend -- eso es asunto de A, no de este fichero.
Verificado por `tests/analysis/test_llamador_faulty.py::
test_llamador_no_importa_live_configs_20` (AST, no grep de texto).

CLOCK CONVENTION -- igual que ciclos.py / backtest.py (§6 del spec, gotcha
medido dos veces en este proyecto): epoch -> datetime es SIEMPRE
`datetime.utcfromtimestamp()`; datetime -> epoch es SIEMPRE
`calendar.timegm()`. Nunca `fromtimestamp()` ni `.timestamp()` -- no hay
ninguna conversión de zona horaria válida en este repo.

Este módulo NO compara nada contra la verdad de terreno -- eso es el
Componente E (comparador.py). Un llamador que se entera del resultado
esperado es un llamador que puede acabar ajustándose a él.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.analysis.realtick_bt.backtest import Ticks
from scripts.analysis.realtick_bt.faulty.ciclos import correr_ciclos
from scripts.analysis.realtick_bt.faulty.config_faulty import kwargs_de
from scripts.analysis.realtick_bt.faulty.estado_por_barra import (
    estado_por_barra,
    estado_por_barra_supertrend,
)

ROOT = Path(__file__).resolve().parents[4]  # .../faulty/../../../../ -> D:\FOREX
BARS_NATIVAS = ROOT / "data" / "lake_bars_capitaria" / "XAUUSD_M15_nativas.parquet"
LAKE_TICKS_CAPITARIA = ROOT / "data" / "lake_ticks" / "XAUUSD"
OUT_DIR = ROOT / "data" / "analysis" / "p_cap" / "replica"

BAR_SEC = 900

# epoch servidor: conexión del ejecutor -> último cierre REAL (D.2, verbatim,
# corregido tras RONDA DE CORRECCIÓN 1 -- el spec traía t1=1785409304
# (2026-07-30 11:01:44, dígitos transpuestos de 1786410904 al transcribir),
# que truncaba la ventana a 2,67 de sus 14,5 dias. t1=1786431669
# (2026-08-11 07:01:09) es el ultimo t_close_epoch real de
# verdad_terreno_902.csv -- NO confundir con 1786410904 (01:15:04), que es
# la ultima APERTURA / borde de la ventana canonica, no el ultimo cierre.
VENTANA_902 = (1785178349.0, 1786431669.0)

ENGINE_SHA = "b113eb7"
SUBSTRATE_ID = "capitaria-ticks + XAUUSD_M15_nativas"
EXPERIMENTO = "T0.7-P-CAP"

# §5 trampa: grafía EXACTA de data/analysis/p_cap/verdad_terreno_902.csv --
# si no coincide, el comparador (Componente E) no empareja nada.
STRATEGY_ID_DE_CONFIG = {
    "S6-K2P0": "SAR::S6-K2P0",
    "SuperTrend-p14x3-M15": "SuperTrend::SuperTrend-p14x3-M15",
}


# --------------------------------------------------------------------- carga
def load_bars_nativas(path: str | Path) -> list[dict[str, Any]]:
    """Carga `XAUUSD_M15_nativas.parquet` con el mismo esquema de
    `backtest.load_bars()` (t/open/high/low/close/volume) -- no se reutiliza
    esa función porque tiene su ruta cableada a las barras DERIVADAS
    (`backtest.BARS_PATH`); D.1 exige poder pasar la ruta de las nativas
    como parámetro, así que este loader es nuevo pero equivalente.

    Falla ruidosamente si el fichero no existe -- el fichero de nativas vive
    bajo `data/`, fuera de git. NUNCA cae en silencio a las derivadas.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"faltan las barras nativas en {p}. Regenéralas con "
            "scripts/analysis/a6_pata_a/barras_nativas_vs_derivadas.py "
            "(attach-only, solo lectura sobre MT5). NUNCA caer a las "
            "derivadas (XAUUSD_M15.parquet): es otro sustrato (D.1)."
        )
    df = pd.read_parquet(p)
    return [
        {"t": int(r.t), "open": float(r.o), "high": float(r.h),
         "low": float(r.l), "close": float(r.c), "volume": int(r.v)}
        for r in df.itertuples()
    ]


class _TicksCapitaria(Ticks):
    """Subclase de `backtest.Ticks` que permite parametrizar el directorio
    del lago de ticks (D.2: `ticks_root` no puede ir cableado -- el llamador
    lo recibe como parámetro). Reutiliza `first_at` / `range` / `_ym` /
    `_shift` / `_candidates` tal cual (heredados sin cambios); sólo
    sobreescribe `_load` para leer de `self._root` en vez del `TICKDIR`
    módulo-global de backtest.py. No es una reescritura de Ticks: es la
    única forma de parametrizar la ruta sin editar backtest.py (R1-bis)."""

    def __init__(self, root: str | Path) -> None:
        super().__init__()
        self._root = Path(root)

    def _load(self, ym: str):
        if ym not in self._m:
            p = self._root / f"{ym}.parquet"
            if not p.exists():
                self._m[ym] = (np.array([]), np.array([]), np.array([]))
            else:
                df = pd.read_parquet(p)
                self._m[ym] = (
                    df.t_msc.to_numpy() / 1000.0,
                    df.bid.to_numpy(),
                    df.ask.to_numpy(),
                )
        return self._m[ym]


# ------------------------------------------------------------------ acotado
def idx_desde_idx_hasta(bar_times: np.ndarray, t0: float, t1: float) -> tuple[int, int]:
    """D.4: acota el cálculo O(n^2) de estado_por_barra a las velas que la
    ventana [t0, t1] realmente necesita.

    `idx_desde`: índice de la última vela cuyo CIERRE <= t0 -- exactamente
    la fórmula del paso 1 de `ciclos.correr_ciclos` evaluada en t=t0, así que
    es la vela que el PRIMER ciclo de la simulación verá.
    `idx_hasta`: la misma fórmula evaluada en t=t1 -- la última vela cuyo
    cierre cae dentro de la ventana (cota superior segura: el bucle real
    nunca alcanza t1, `while t < t1`, así que el último índice accedido es
    <= idx_hasta).
    """
    bar_closes = np.asarray(bar_times, dtype=float) + BAR_SEC
    idx_desde = int(np.searchsorted(bar_closes, t0, side="right")) - 1
    idx_hasta = int(np.searchsorted(bar_closes, t1, side="right")) - 1
    if idx_desde < 0 or idx_hasta < 0:
        raise ValueError(
            f"no hay ninguna vela cerrada en/antes de t0={t0} o t1={t1}: "
            "las barras nativas no cubren la ventana pedida."
        )
    return idx_desde, idx_hasta


class _EstadosFueraDeAcotado(RuntimeError):
    """D.4: si `correr_ciclos` pide un índice de `estados` fuera de
    [idx_desde, idx_hasta] (o no calculado), eso es un ERROR DE ACOTADO y
    debe reventar -- nunca tratarse silenciosamente como 'sin ficha
    deseada'. Un acotado insuficiente que no revienta es una réplica que
    simula con menos señal de la que el motor vivo tuvo, sin avisar."""


class _EstadosParaCiclos:
    """Adapta la salida del Componente A al contrato que espera el
    Componente B.

    Dos diferencias de forma, resueltas aquí (no en A ni en B, que están
    congelados):
      1. `estado_por_barra` / `estado_por_barra_supertrend` devuelven el
         snapshot COMPLETO de `simular_variant(..., return_state=True)` /
         `supertrend_always_in_target`: `{"open": {ficha: {...}},
         "last_bar_exits": {...}, "last_idx": int}`. `correr_ciclos` espera
         el dict PLANO `{ficha: {...}}` (ver `ciclos.py`: indexa
         `estado[ficha_id]` y hace `len(estado)` directo, y
         `tests/analysis/test_ciclos_faulty.py::_estado_long` usa esa forma
         plana). Este wrapper desenvuelve `["open"]` en cada acceso.
      2. Fuera de [idx_desde, idx_hasta] el Componente A deja `None`.
         `correr_ciclos` accede con `estados[idx] if idx < len(estados) else
         None` -- una única lectura de `None` ahí NO dispara excepción por
         sí sola (B está congelado y no se toca). Este wrapper es quien
         convierte ese acceso en un reventón ruidoso (`_EstadosFueraDeAcotado`),
         cumpliendo D.4.
    """

    def __init__(self, estados: list[dict | None]):
        self._estados = estados

    def __len__(self) -> int:
        return len(self._estados)

    def __getitem__(self, idx: int):
        v = self._estados[idx]
        if v is None:
            raise _EstadosFueraDeAcotado(
                f"estados[{idx}] es None: fuera de [idx_desde, idx_hasta] o "
                "no calculado. correr_ciclos lo necesitaba -- error de "
                "acotado (D.4), no 'sin ficha deseada'."
            )
        return v["open"]


# ------------------------------------------------------------------ cableado
def _correr_estrategia(
    *,
    config_id: str,
    strategy_id: str,
    bars: list[dict[str, Any]],
    bar_times: np.ndarray,
    ticks: Any,
    t0: float,
    t1: float,
    window: int,
    stops_level: float,
    max_spread_open: float,
    cycle_sec: float,
    idx_desde: int,
    idx_hasta: int,
) -> tuple[list[dict], list[dict]]:
    """Corre A + B para UNA estrategia (§D.3 -- las dos corren por separado,
    llamadas independientes a `correr_ciclos`). `config_id` es el id del
    roster tomachine ('S6-K2P0' | 'SuperTrend-p14x3-M15'); `strategy_id` es
    la grafía del comparador que se estampa en cada posición/evento."""
    if config_id == "SuperTrend-p14x3-M15":
        # SuperTrend no usa simular_variant -- D.3, §5 trampa.
        estados = estado_por_barra_supertrend(
            bars, window=window, idx_desde=idx_desde, idx_hasta=idx_hasta
        )
    else:
        kwargs = kwargs_de(config_id)
        estados = estado_por_barra(
            bars, kwargs, window=window, idx_desde=idx_desde, idx_hasta=idx_hasta
        )

    estados_env = _EstadosParaCiclos(estados)
    posiciones, eventos = correr_ciclos(
        estados_env, bar_times, ticks, t0, t1,
        max_spread_open=max_spread_open,
        stops_level=stops_level,
        cycle_sec=cycle_sec,
    )
    for p in posiciones:
        p["strategy_id"] = strategy_id
    for e in eventos:
        e["strategy_id"] = strategy_id
    return posiciones, eventos


# ------------------------------------------------------------------- salida
def _servidor_texto(t: float) -> str:
    """epoch -> texto legible, hora de SERVIDOR. Nunca fromtimestamp()."""
    return datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


_COLUMNAS_POSICIONES = [
    "strategy_id", "ficha", "side",
    "t_open", "t_open_servidor", "precio_open",
    "sl_open_deseado", "sl_open_enviado", "clamp_aplicado",
    "t_close", "t_close_servidor", "precio_close", "motivo_cierre",
]
_COLUMNAS_EVENTOS = ["strategy_id", "t", "tipo", "detalle"]


def _posiciones_a_df(posiciones: list[dict]) -> pd.DataFrame:
    if not posiciones:
        return pd.DataFrame(columns=_COLUMNAS_POSICIONES)
    filas = []
    for p in posiciones:
        fila = dict(p)
        fila["t_open_servidor"] = _servidor_texto(fila["t_open"])
        fila["t_close_servidor"] = _servidor_texto(fila["t_close"])
        filas.append(fila)
    df = pd.DataFrame(filas)
    presentes = [c for c in _COLUMNAS_POSICIONES if c in df.columns]
    resto = [c for c in df.columns if c not in presentes]
    return df[presentes + resto]


def _eventos_a_df(eventos: list[dict]) -> pd.DataFrame:
    if not eventos:
        return pd.DataFrame(columns=_COLUMNAS_EVENTOS)
    filas = []
    for e in eventos:
        fila = dict(e)
        fila["detalle"] = json.dumps(fila.get("detalle", {}), ensure_ascii=False, sort_keys=True)
        filas.append(fila)
    df = pd.DataFrame(filas)
    presentes = [c for c in _COLUMNAS_EVENTOS if c in df.columns]
    resto = [c for c in df.columns if c not in presentes]
    return df[presentes + resto]


def _git_sha(root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root,
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except Exception:
        return "NO_EVALUABLE"


def _config_hash() -> str:
    vendored = Path(__file__).parent / "_vendored_live_configs_20_b113eb7.py"
    return hashlib.sha256(vendored.read_bytes()).hexdigest()


# --------------------------------------------------------------------- D.2
def correr_p_cap(
    *,
    bars_path: str | Path = BARS_NATIVAS,
    ticks_root: str | Path = LAKE_TICKS_CAPITARIA,
    t0: float = VENTANA_902[0],
    t1: float = VENTANA_902[1],
    stops_level: float,  # SIN default (D.2): el llamador de arriba lo aporta
    window: int = 10_000,
    cycle_sec: float = 15.0,
    max_spread_open: float = 0.50,
    out_dir: str | Path = OUT_DIR,
) -> dict:
    """Corre la réplica del motor faulty sobre las 2 estrategias del roster
    tomachine (§D.3: llamadas independientes a `correr_ciclos`, una por
    estrategia). Devuelve un dict de métricas y escribe los 3 artefactos de
    D.5 en `out_dir`."""
    t_inicio_total = time.perf_counter()

    bars = load_bars_nativas(bars_path)
    bar_times = np.array([b["t"] for b in bars], dtype=float)
    idx_desde, idx_hasta = idx_desde_idx_hasta(bar_times, t0, t1)
    ticks = _TicksCapitaria(ticks_root)

    tiempos_calculo: dict[str, float] = {}
    todas_posiciones: list[dict] = []
    todos_eventos: list[dict] = []

    for config_id, strategy_id in STRATEGY_ID_DE_CONFIG.items():
        t_ini = time.perf_counter()
        posiciones, eventos = _correr_estrategia(
            config_id=config_id, strategy_id=strategy_id,
            bars=bars, bar_times=bar_times, ticks=ticks,
            t0=t0, t1=t1, window=window, stops_level=stops_level,
            max_spread_open=max_spread_open, cycle_sec=cycle_sec,
            idx_desde=idx_desde, idx_hasta=idx_hasta,
        )
        tiempos_calculo[config_id] = time.perf_counter() - t_ini
        todas_posiciones.extend(posiciones)
        todos_eventos.extend(eventos)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    posiciones_df = _posiciones_a_df(todas_posiciones)
    eventos_df = _eventos_a_df(todos_eventos)
    posiciones_df.to_csv(out_dir / "posiciones_replica.csv", index=False)
    eventos_df.to_csv(out_dir / "eventos_replica.csv", index=False)

    posiciones_por_estrategia = {
        sid: int((posiciones_df["strategy_id"] == sid).sum()) if len(posiciones_df) else 0
        for sid in STRATEGY_ID_DE_CONFIG.values()
    }
    eventos_por_tipo = (
        {str(k): int(v) for k, v in eventos_df.groupby("tipo").size().items()}
        if len(eventos_df) else {}
    )
    eventos_por_tipo_por_estrategia: dict[str, dict[str, int]] = {}
    for sid in STRATEGY_ID_DE_CONFIG.values():
        if len(eventos_df):
            sub = eventos_df[eventos_df["strategy_id"] == sid]
            eventos_por_tipo_por_estrategia[sid] = (
                {str(k): int(v) for k, v in sub.groupby("tipo").size().items()}
                if len(sub) else {}
            )
        else:
            eventos_por_tipo_por_estrategia[sid] = {}

    tiempo_total_seg = time.perf_counter() - t_inicio_total

    metricas = {
        "posiciones_por_estrategia": posiciones_por_estrategia,
        "eventos_por_tipo": eventos_por_tipo,
        "eventos_por_tipo_por_estrategia": eventos_por_tipo_por_estrategia,
        "tiempo_calculo_seg": {
            **{k: round(v, 3) for k, v in tiempos_calculo.items()},
            "total": round(tiempo_total_seg, 3),
        },
        "parametros": {
            "t0": t0, "t1": t1, "window": window, "cycle_sec": cycle_sec,
            "stops_level": stops_level, "max_spread_open": max_spread_open,
            "bars_path": str(bars_path), "ticks_root": str(ticks_root),
            "idx_desde": idx_desde, "idx_hasta": idx_hasta,
        },
        "lineage": {
            "run_id": f"T0.7-P-CAP-replica-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            "area": "F0",
            "experimento": EXPERIMENTO,
            "config_hash": _config_hash(),
            "substrate_id": SUBSTRATE_ID,
            "engine_sha": ENGINE_SHA,
            "git_sha": _git_sha(ROOT),
            "etapa": "F0",
            "generador": "scripts/analysis/realtick_bt/faulty/llamador.py",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    }

    with open(out_dir / "metricas_p_cap.json", "w", encoding="utf-8") as f:
        json.dump(metricas, f, indent=2, ensure_ascii=False)

    return metricas


if __name__ == "__main__":
    # stops_level=0.50: derivado 2026-08-13 por inversión contra el lago de
    # ticks (research/fases/F0-preparacion/04-resultados/T0.7-p-cap/
    # stops_level_derivado.{json,md}). Default SÓLO aquí, en el script de
    # entrada -- NUNCA como default de correr_p_cap() (D.2).
    resultado = correr_p_cap(stops_level=0.50)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
