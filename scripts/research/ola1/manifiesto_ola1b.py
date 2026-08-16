r"""scripts/research/ola1/manifiesto_ola1b.py -- BLOCK-3 (OLA1B-reporte.md).

CLI: python -m scripts.research.ola1.manifiesto_ola1b [--salida <ruta>] [--engine-sha <sha>]

Genera research/fases/F0-preparacion/03-runs/2026-08-16-ola1b.yaml a partir de las
grillas de research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-OLA1B.md,
HARDCODEADAS AQUI (son el pre-registro, commit `8e9d708`; no se leen de ningun sitio
configurable) -- mismo patron que manifiesto.py (Ola 1 original).

Tres corridas:
  - P02-S6 / P02-S7: MISMA grilla que manifiesto._grid_p02 (reutilizada, no
    reimplementada), con margen_extra_s=sustrato.MARGEN_P02_S (D-60) -- unico cambio
    frente a la Ola 1 original.
  - P03FLOOR-S6: NUEVO, factorial ac_modulate_floor_relief_k x ac_decel_umbral (20
    brazos, todos confirmatorios).
  - P34-S6: NUEVO LEVER, barrido de trail_atr_floor_k (9 brazos, todos confirmatorios,
    control=2.0 incluido en la grilla).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from scripts.research.ola1.manifiesto import _grid_p02
from scripts.research.ola1.sustrato import MARGEN_P02_S
from scripts.research.runner import lineage

SALIDA_DEFAULT = Path("research/fases/F0-preparacion/03-runs/2026-08-16-ola1b.yaml")
PREREGISTRO = "research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-OLA1B.md"
SUBSTRATE_ID = "capitaria-ticks-2026-preholdout"
SUBSTRATE_ID_P02 = "capitaria-ticks-2026-preholdout-recortado-p02-d60"

HEADER_COMMENT = """# OLA1B -- manifiesto generado (BLOCK-3 de OLA1B-reporte.md)
#
# Generado por: python -m scripts.research.ola1.manifiesto_ola1b
# Grillas HARDCODEADAS desde el pre-registro OLA1B (commit `8e9d708`), no configurables.
# 3 corridas: P02-S6/P02-S7 (re-run, sustrato recortado D-60) + P03FLOOR-S6 (NUEVO,
# ac_modulate_floor_relief_k x ac_decel_umbral) + P34-S6 (NUEVO LEVER, trail_atr_floor_k).
#
# PRE-INTERPRETACION -- este manifiesto no contiene resultados ni conclusiones.
"""


def _fmt2(v: float) -> str:
    return f"{v:.2f}"


def _grid_p03floor() -> tuple[dict[str, dict], set[str]]:
    relief_vals = [1.00, 0.75, 0.50, 0.25, 0.00]
    umbral_pips = [0, 25, 50, 75]
    brazos: dict[str, dict] = {}
    confirmatorios: set[str] = set()
    for relief in relief_vals:
        for u in umbral_pips:
            nombre = f"relief{_fmt2(relief)}-u{u}"
            overlay: dict = {}
            if relief != 1.00:
                overlay["ac_modulate_floor_relief_k"] = relief
            if u != 0:
                overlay["ac_decel_umbral"] = round(u * 0.01, 10)
            brazos[nombre] = overlay
            confirmatorios.add(nombre)  # todos confirmatorios (SS2 del pre-registro)
    return brazos, confirmatorios


def _grid_p34() -> tuple[dict[str, dict], set[str]]:
    valores = [2.00, 1.75, 1.50, 1.25, 1.00, 0.75, 0.50, 0.25, 0.00]
    brazos: dict[str, dict] = {}
    confirmatorios: set[str] = set()
    for v in valores:
        nombre = "default" if v == 2.00 else f"floork{_fmt2(v)}"
        brazos[nombre] = {} if v == 2.00 else {"trail_atr_floor_k": v}
        confirmatorios.add(nombre)  # todos confirmatorios (SS3 del pre-registro)
    return brazos, confirmatorios


def construir_manifiesto(*, engine_sha: str) -> dict:
    p02_s6_brazos, p02_s6_conf = _grid_p02()
    p02_s7_brazos, p02_s7_conf = _grid_p02()
    p03floor_brazos, p03floor_conf = _grid_p03floor()
    p34_brazos, p34_conf = _grid_p34()

    corridas = [
        {
            "run_key": "P02-S6", "tipo": "ola1_paired",
            "palanca": "P-02", "sid": "S6-K2P0", "clase": "1-A",
            "brazo_control": "default", "secundaria": "p02",
            "margen_extra_s": MARGEN_P02_S,
            "brazos": p02_s6_brazos, "confirmatorios": sorted(p02_s6_conf),
        },
        {
            "run_key": "P02-S7", "tipo": "ola1_paired",
            "palanca": "P-02", "sid": "S7-TPNONE", "clase": "1-A",
            "brazo_control": "default", "secundaria": "p02",
            "margen_extra_s": MARGEN_P02_S,
            "brazos": p02_s7_brazos, "confirmatorios": sorted(p02_s7_conf),
        },
        {
            "run_key": "P03FLOOR-S6", "tipo": "ola1_paired",
            "palanca": "P-03-floor", "sid": "S6-K2P0", "clase": "1-A",
            "brazo_control": "relief1.00-u0", "secundaria": "p03",
            "brazos": p03floor_brazos, "confirmatorios": sorted(p03floor_conf),
        },
        {
            "run_key": "P34-S6", "tipo": "ola1_paired",
            "palanca": "P-34", "sid": "S6-K2P0", "clase": "1-A",
            "brazo_control": "default", "secundaria": "none",
            "brazos": p34_brazos, "confirmatorios": sorted(p34_conf),
        },
    ]

    return {
        "experimento": "OLA1B-palancas-de-salida",
        "area": "B",
        "etapa": "F0",
        "hipotesis": PREREGISTRO,
        "substrate_id": SUBSTRATE_ID,
        "engine_sha": engine_sha,
        "salidas": {
            "resultados": "research/fases/F0-preparacion/04-resultados/OLA1B/",
            "ledger": "append",
        },
        "corridas": corridas,
    }


def escribir_manifiesto(data: dict, salida: Path) -> None:
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", encoding="utf-8") as f:
        f.write(HEADER_COMMENT)
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=100)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", type=Path, default=SALIDA_DEFAULT)
    parser.add_argument("--engine-sha", type=str, default=None)
    args = parser.parse_args(argv)

    engine_sha = args.engine_sha or lineage.git_sha()
    data = construir_manifiesto(engine_sha=engine_sha)
    escribir_manifiesto(data, args.salida)

    n_brazos = sum(len(c["brazos"]) for c in data["corridas"])
    n_confirm = sum(len(c["confirmatorios"]) for c in data["corridas"])
    print(f"manifiesto escrito en {args.salida}")
    print(f"corridas: {len(data['corridas'])}  brazos totales: {n_brazos}  "
          f"confirmatorios totales: {n_confirm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
