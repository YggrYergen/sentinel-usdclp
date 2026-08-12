r"""Overlay de costes de AVA calibrado sobre Capitaria (T0.6 mod #10, Paso 2a
-- Artefacto 2).

Por que existe. D-21 es vinculante: "los backtests sobre datos de AVA usan
precios de AVA con un modelo de costes calibrado sobre Capitaria. El spread
nativo de AVA no se usa para veredictos." Sin este overlay, el backtest largo
(que corre sobre AVA, ~3.5 anos efectivos) usaria el spread nativo de AVA
(0.34-0.45, mas angosto que el 0.50-0.60 de Capitaria) y AVA saldria
sistematicamente mejor -- el resultado no seria comparable con nada.

REGLA EXACTA, no se reinterpreta: se CONSERVA el mid de AVA (`mid =
(bid+ask)/2`, que es la senal de precio real de AVA) y se SUSTITUYE la
anchura por la calibrada sobre Capitaria: `bid' = mid - s/2`, `ask' = mid +
s/2`. Precios de AVA, costes de Capitaria -- literalmente lo que dice D-21.
El overlay SIEMPRE ENSANCHA (spread de Capitaria > spread nativo de AVA);
invertir el sentido (estrechar) es exactamente el fallo que D-21 existe para
impedir, porque haria a AVA salir aun mejor.

Funciones puras, sin efectos de lado. Este modulo no lee disco ni escribe
nada; `cargar_calibracion` es la unica que toca el sistema de ficheros, y
solo para leer el JSON que produce
`scripts/research/calibracion_costes_capitaria.py`.

R1-bis (charter SS A.11): NO modifica `scripts/analysis/realtick_bt/backtest.py`.

HOLDOUT SELLADO (charter SS A.14 + D-31): este modulo tambien expone las dos
guardas duras que protegen los dos sellos --Capitaria (acto 1) y AVA (acto
2)-- para que cualquier script que declare un rango de lectura de ticks
(calibracion sobre Capitaria, aplicacion del overlay sobre AVA) las invoque
ANTES de leer disco.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Sequence

import numpy as np

from scripts.research.ny_window import in_ny_window

# --------------------------------------------------------------------- HOLDOUT
# D-31 acto 1: Capitaria 2026-05-12 -> 2026-07-26, intocable (charter SS A.14).
CAPITARIA_HOLDOUT_INI = calendar.timegm(datetime(2026, 5, 12).timetuple())
CAPITARIA_HOLDOUT_FIN = calendar.timegm(datetime(2026, 7, 27).timetuple())  # exclusivo

# D-31 acto 2: AVA ano 2023 completo, intocable (charter SS A.14).
AVA_HOLDOUT_INI = calendar.timegm(datetime(2023, 1, 1).timetuple())
AVA_HOLDOUT_FIN = calendar.timegm(datetime(2024, 1, 1).timetuple())  # exclusivo


def assert_fuera_holdout_capitaria(ini: float, fin: float) -> None:
    """Guarda dura (charter SS A.14 + D-31 acto 1): aborta si el rango
    declarado `[ini, fin)` tocara el holdout sellado de Capitaria
    (2026-05-12 -> 2026-07-26). `fin` es exclusivo, igual que el sello."""
    if ini < CAPITARIA_HOLDOUT_FIN and fin > CAPITARIA_HOLDOUT_INI:
        raise SystemExit(
            f"ABORTADO: el rango solicitado [{ini}, {fin}) toca el holdout "
            f"sellado de Capitaria [{CAPITARIA_HOLDOUT_INI}, {CAPITARIA_HOLDOUT_FIN}) "
            "(charter SS A.14 + D-31 acto 1). No se leyo ningun tick."
        )


def assert_fuera_holdout_ava(ini: float, fin: float) -> None:
    """Guarda dura (charter SS A.14 + D-31 acto 2): aborta si el rango
    declarado `[ini, fin)` tocara el holdout sellado de AVA (ano 2023
    completo). `fin` es exclusivo, igual que el sello."""
    if ini < AVA_HOLDOUT_FIN and fin > AVA_HOLDOUT_INI:
        raise SystemExit(
            f"ABORTADO: el rango solicitado [{ini}, {fin}) toca el holdout "
            f"sellado de AVA [{AVA_HOLDOUT_INI}, {AVA_HOLDOUT_FIN}) "
            "(charter SS A.14 + D-31 acto 2). No se leyo ningun tick."
        )


# ------------------------------------------------------------------ CALIBRACION
HOURS_VENTANA = (18, 19, 20, 21, 22, 23, 0, 1)  # las 8 horas de la ventana NY (D-34)
MODOS = ("mediana", "media", "p75")


def cargar_calibracion(path) -> dict:
    """Carga el JSON de calibracion producido por
    `scripts/research/calibracion_costes_capitaria.py`. Falla duro (nunca un
    default silencioso) si el fichero no existe, no es JSON valido, le falta
    la clave `por_hora`, le falta alguna de las 8 horas de la ventana NY, o a
    alguna hora le falta alguno de los tres modos."""
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"calibracion no encontrada: {p}")
    with p.open("r", encoding="utf-8") as f:
        calib = json.load(f)

    if "por_hora" not in calib:
        raise KeyError(f"calibracion sin clave 'por_hora': {p}")
    por_hora = calib["por_hora"]
    faltantes_hora = [h for h in HOURS_VENTANA if str(h) not in por_hora]
    if faltantes_hora:
        raise KeyError(
            f"calibracion incompleta: faltan las horas {faltantes_hora} en 'por_hora' ({p})"
        )
    for h in HOURS_VENTANA:
        entrada = por_hora[str(h)]
        faltantes_modo = [m for m in MODOS if m not in entrada]
        if faltantes_modo:
            raise KeyError(
                f"calibracion incompleta: hora {h} sin los modos {faltantes_modo} ({p})"
            )
    return calib


def spread_calibrado(dt_ny: datetime, calib: dict, modo: str = "mediana") -> float:
    """Devuelve el spread de Capitaria a aplicar para la hora NY de `dt_ny`,
    segun `modo` (`{"mediana", "media", "p75"}`; `p75` es el modo
    conservador -- ensancha mas). Falla duro si `modo` no es uno de los tres,
    o si la hora de `dt_ny` no esta cubierta por la calibracion (fuera de la
    ventana operativa NY, D-34)."""
    if modo not in MODOS:
        raise ValueError(f"modo desconocido: {modo!r}. Validos: {MODOS}")
    hora = dt_ny.hour
    if hora not in HOURS_VENTANA:
        raise KeyError(
            f"hora {hora} fuera de la ventana operativa NY {HOURS_VENTANA} (D-34); "
            "la calibracion no cubre esa hora."
        )
    return float(calib["por_hora"][str(hora)][modo])


def aplicar_overlay(
    bid: float, ask: float, dt_ny: datetime, calib: dict, modo: str = "mediana"
) -> tuple[float, float]:
    """Aplica el overlay de costes a UN tick de AVA. Regla exacta (D-21): se
    CONSERVA el mid de AVA y se SUSTITUYE la anchura por la calibrada sobre
    Capitaria. `mid = (bid+ask)/2`; `bid' = mid - s/2`; `ask' = mid + s/2`."""
    mid = (bid + ask) / 2.0
    s = spread_calibrado(dt_ny, calib, modo)
    return mid - s / 2.0, mid + s / 2.0


def overlay_arrays(
    bids: Sequence[float],
    asks: Sequence[float],
    dts_ny: Sequence[datetime],
    calib: dict,
    modo: str = "mediana",
) -> tuple[np.ndarray, np.ndarray]:
    """Version vectorizada (numpy) de `aplicar_overlay` para millones de
    ticks sin bucle Python por tick. Coincide elemento a elemento con llamar
    a `aplicar_overlay` en un bucle."""
    if modo not in MODOS:
        raise ValueError(f"modo desconocido: {modo!r}. Validos: {MODOS}")

    bids = np.asarray(bids, dtype=float)
    asks = np.asarray(asks, dtype=float)
    horas = np.array([dt.hour for dt in dts_ny], dtype=int)

    # Tabla de lookup hora -> spread calibrado (NaN donde la calibracion no
    # cubre esa hora), construida UNA vez, no por tick.
    lut = np.full(24, np.nan, dtype=float)
    for h in HOURS_VENTANA:
        lut[h] = float(calib["por_hora"][str(h)][modo])

    s = lut[horas]
    if np.isnan(s).any():
        malas = sorted(set(int(h) for h in horas[np.isnan(s)]))
        raise KeyError(
            f"horas {malas} fuera de la ventana operativa NY {HOURS_VENTANA} (D-34); "
            "la calibracion no cubre esas horas."
        )

    mid = (bids + asks) / 2.0
    return mid - s / 2.0, mid + s / 2.0
