r"""scripts/research/ola1/sustrato.py -- OLA1-EXEC Bloque 1.

Sustrato de la Ola 1 (barras M15 pre-holdout) y las dos guardas duras que
protegen la validez del instrumento ANTES de leer nada mas (pre-registro
regla 5; charter SS A.14):

  - verificar_holdout: ninguna posicion resuelta puede tocar el holdout
    sellado de D-31 acto 1 (mismo criterio que
    scripts/research/baseline_golden.py:75-85).
  - verificar_control_contra_linea_base: el brazo `default` (=config VIVA
    sin tocar) de cada palanca tiene que reproducir byte a byte la linea
    base congelada de research/fases/F0-preparacion/04-resultados/T0.6-baseline/,
    con la MISMA normalizacion que tests/research/test_baseline_parity.py.

Todos los timestamps son hora de servidor del broker (UTC-4);
`datetime.utcfromtimestamp` siempre, `datetime.fromtimestamp` jamas (D-31,
backtest.py:15-26).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.analysis.realtick_bt import backtest as bt
from scripts.research.baseline_golden import HOLDOUT_INI

BASELINE_DIR = (
    Path(__file__).resolve().parents[3]
    / "research" / "fases" / "F0-preparacion" / "04-resultados" / "T0.6-baseline"
)


class HoldoutVioladoError(Exception):
    """Raised when a resolved position touches the sealed holdout (charter SS A.14)."""


class ControlNoReproduceLineaBaseError(Exception):
    """Raised when the control arm fails to reproduce the frozen baseline
    (pre-registro regla 5: si el control no reproduce, la corrida entera es
    invalida y los demas brazos no son interpretables)."""


def cargar_barras(*, margen_extra_s: float = 0.0) -> list[dict[str, Any]]:
    """Barras M15 pre-holdout: bt.load_bars() filtrado por
    b["t"] < HOLDOUT_INI - margen_extra_s.

    Reutiliza HOLDOUT_INI de scripts.research.baseline_golden -- no se
    redefine aqui.

    `margen_extra_s=0.0` (default) es BYTE-IDENTICO al sustrato de siempre
    (b["t"] < HOLDOUT_INI) -- el corte que usan P-03/P-05/P-08 y la linea
    base T0.6-baseline.

    `margen_extra_s > 0.0` (D-60, BLOCK-3(a) de este task): recorta el
    sustrato MAS, para que ningun `max_hold_bars` de la grilla de P-02 pueda
    empujar una salida `resolve()`-`t_exit` hasta el sello del holdout
    (`first_at(t_exit)` devuelve el primer tick EN O DESPUES de t_exit --
    ver DECISIONES.md D-60 para la medicion exacta que fuerza esto). El
    llamador calcula `margen_extra_s = (max(grilla_max_hold_bars) + 1) * BAR_SEC`
    -- ver `MARGEN_P02_S` mas abajo, que es el valor exacto usado por la
    grilla de P-02 congelada en manifiesto.py.
    """
    return [b for b in bt.load_bars() if b["t"] < HOLDOUT_INI - margen_extra_s]


# D-60: margen para P-02. max(grilla) = 128 (manifiesto._grid_p02), BAR_SEC=900.
# margen = (128 + 1) * 900 = 116100 s (~32.25 h) antes de HOLDOUT_INI.
MAX_MAX_HOLD_BARS_GRID_P02 = 128
MARGEN_P02_S = (MAX_MAX_HOLD_BARS_GRID_P02 + 1) * bt.BAR_SEC


def verificar_control_contra_linea_base_recortada(
    sid: str, posiciones_control: list[dict[str, Any]], ultimo_t_bar: float
) -> dict:
    """Variante de `verificar_control_contra_linea_base` para un sustrato
    RECORTADO (D-60, P-02): compara el brazo de control, no contra la linea
    base T0.6 completa (que corrio sobre el sustrato SIN recortar y por
    tanto tiene mas posiciones cerca del holdout), sino contra el PREFIJO de
    esa misma linea base filtrado a `t_exit <= ultimo_t_bar`.

    Justificacion de por que esto es una comparacion valida y no una
    relajacion: el motor es causal -- una posicion que CIERRA en o antes de
    `ultimo_t_bar` en la corrida completa depende solo de barras
    `<= ultimo_t_bar`, exactamente las mismas barras que ve la corrida
    recortada. Por tanto el conjunto de posiciones CERRADAS del brazo de
    control recortado debe ser EXACTAMENTE el prefijo (por t_exit) de la
    linea base congelada, ni una posicion de mas ni de menos -- cualquier
    diferencia es una regresion real, no un artefacto del recorte.
    """
    path = BASELINE_DIR / f"posiciones_{sid}.json"
    with path.open("r", encoding="utf-8") as f:
        congelado_completo = json.load(f)

    congelado_recortado = _normalizar(
        [p for p in congelado_completo if p["t_exit"] <= ultimo_t_bar]
    )
    control = _normalizar(posiciones_control)

    if len(control) != len(congelado_recortado):
        raise ControlNoReproduceLineaBaseError(
            f"{sid}: numero de posiciones del brazo de control recortado ({len(control)}) "
            f"!= prefijo de la linea base congelada hasta t_exit<={ultimo_t_bar} "
            f"({len(congelado_recortado)}) -- el instrumento no reproduce la linea base "
            "bajo el sustrato recortado de P-02, la corrida es invalida"
        )

    for i, (esperado, obtenido) in enumerate(zip(congelado_recortado, control)):
        for k, v_esperado in esperado.items():
            v_obtenido = obtenido.get(k)
            if v_esperado != v_obtenido:
                raise ControlNoReproduceLineaBaseError(
                    f"{sid}: posicion recortada #{i} difiere del prefijo de la linea base "
                    f"congelada -- clave={k!r} congelado={v_esperado!r} control={v_obtenido!r}"
                )

    return {"n_congelado_recortado": len(congelado_recortado), "n_control": len(control),
            "identico": True}


def dia_servidor(t: float) -> str:
    """Dia natural del reloj de servidor (UTC-4) del instante `t` (E-04 SS2.4).

    Ground truth de resolucion de segundo entero (D-46); `utcfromtimestamp`
    aplica offset cero y devuelve el reloj de servidor tal cual (el epoch ya
    lo codifica) -- jamas `fromtimestamp`.
    """
    return datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")


def verificar_holdout(posiciones: list[dict[str, Any]]) -> None:
    """Guarda dura del charter SS A.14. Mismo criterio, literalmente, que
    scripts/research/baseline_golden.py:75-85: si `t_exit` o `t_in_exec` de
    cualquier posicion resuelta cae dentro o despues del sello, lanza
    nombrando la primera intrusa."""
    for r in posiciones:
        if r["t_exit"] >= HOLDOUT_INI or r["t_in_exec"] >= HOLDOUT_INI:
            raise HoldoutVioladoError(
                "posicion toca el holdout sellado (D-31 acto 1, charter SS A.14): "
                f"t_in_exec={r['t_in_exec']} t_exit={r['t_exit']} "
                f"HOLDOUT_INI={HOLDOUT_INI} -- posicion completa: {r}"
            )


def _normalizar(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Misma normalizacion que test_baseline_parity.py: floats redondeados a
    10 decimales, claves ordenadas, filas ordenadas por (t_in_exec, t_exit)."""
    return sorted(
        ({k: (round(v, 10) if isinstance(v, float) else v) for k, v in sorted(r.items())}
         for r in rows),
        key=lambda r: (r["t_in_exec"], r["t_exit"]),
    )


def verificar_control_contra_linea_base(sid: str, posiciones_control: list[dict[str, Any]]) -> dict:
    """Regla 5 del pre-registro: el instrumento se valida contra la linea
    base congelada ANTES de leer nada mas. Compara SOLO las claves que trae
    el congelado (el brazo de control puede traer claves extra, p.ej. R1,
    que este chequeo ignora deliberadamente). Cualquier diferencia lanza
    ControlNoReproduceLineaBaseError nombrando la primera posicion que
    difiere, la clave y los dos valores."""
    path = BASELINE_DIR / f"posiciones_{sid}.json"
    with path.open("r", encoding="utf-8") as f:
        congelado = json.load(f)

    control = _normalizar(posiciones_control)

    if len(control) != len(congelado):
        raise ControlNoReproduceLineaBaseError(
            f"{sid}: numero de posiciones del brazo de control ({len(control)}) "
            f"!= linea base congelada ({len(congelado)}) -- el instrumento no "
            "reproduce la linea base, la corrida es invalida"
        )

    for i, (esperado, obtenido) in enumerate(zip(congelado, control)):
        for k, v_esperado in esperado.items():
            v_obtenido = obtenido.get(k)
            if v_esperado != v_obtenido:
                raise ControlNoReproduceLineaBaseError(
                    f"{sid}: posicion #{i} difiere de la linea base congelada -- "
                    f"clave={k!r} congelado={v_esperado!r} control={v_obtenido!r}"
                )

    return {"n_congelado": len(congelado), "n_control": len(control), "identico": True}


def respaldar_si_existe(path: Path) -> None:
    """Backup obligatorio antes de regenerar un artefacto: renombra a
    <name>.bak-<UTC timestamp> si el fichero ya existe. El fichero anterior
    nunca se borra."""
    path = Path(path)
    if path.exists():
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path.rename(path.with_name(path.name + f".bak-{ts}"))
