r"""scripts/research/ola1/manifiesto.py -- OLA1-EXEC Bloque 8.

CLI: python -m scripts.research.ola1.manifiesto [--salida <ruta>] [--engine-sha <sha>]

Genera research/fases/F0-preparacion/03-runs/2026-08-16-ola1.yaml a partir de
las grillas de E-04 SS3, HARDCODEADAS AQUI (son el pre-registro `1c7279d`; no
se leen de ningun sitio configurable). Cinco corridas, 157 brazos, 44
confirmatorios (subconjunto exacto -- verificado por
tests/research/test_ola1.py::test_los_44_preregistrados_son_subconjunto_exacto).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from scripts.research.runner import lineage

SALIDA_DEFAULT = Path("research/fases/F0-preparacion/03-runs/2026-08-16-ola1.yaml")
PREREGISTRO = "research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-ola1.md"
SUBSTRATE_ID = "capitaria-ticks-2026-preholdout"

HEADER_COMMENT = """# OLA1-palancas-de-salida -- manifiesto generado (OLA1-EXEC Bloque 8)
#
# Generado por: python -m scripts.research.ola1.manifiesto
# Grillas HARDCODEADAS desde E-04 SS3 (pre-registro `1c7279d`, ampliacion `1c7279d`),
# no configurables. 5 corridas, 157 brazos totales, 44 confirmatorios (subconjunto
# exacto del pre-registro -- verificado por
# test_ola1.py::test_los_44_preregistrados_son_subconjunto_exacto).
#
# Conversion de unidades P-03 (E-04 SS2.1): el umbral se pre-registro en PIPS y
# pip_size("XAUUSD") = 0.01, luego ac_decel_umbral = umbral_pips * 0.01. El nombre
# de cada brazo lleva los pips (u25-lb1-h3 = 25 pips); el overlay lleva el valor
# ya convertido a unidades AC (ac_decel_umbral: 0.25). Las dos quedan en el YAML
# para que la traza sea legible sin recalcular nada.
#
# PRE-INTERPRETACION -- este manifiesto no contiene resultados ni conclusiones.
"""


def _fmt2(v: float) -> str:
    return f"{v:.2f}"


def _grid_p02() -> tuple[dict[str, dict], set[str]]:
    valores = [None, 4, 6, 8, 10, 12, 15, 20, 25, 30, 40, 48, 56, 64, 80, 96, 128]
    confirmatorios_n = {None, 10, 15, 20, 30, 48, 64}
    brazos = {}
    confirmatorios = set()
    for n in valores:
        nombre = "default" if n is None else f"mhb{n}"
        brazos[nombre] = {} if n is None else {"max_hold_bars": n}
        if n in confirmatorios_n:
            confirmatorios.add(nombre)
    return brazos, confirmatorios


def _grid_p03() -> tuple[dict[str, dict], set[str]]:
    umbrales = [10, 25, 50, 75, 100, 150]
    umbrales_confirm = {25, 50, 75}
    lookbacks = [1, 2, 3]
    lookbacks_confirm = {1, 2}
    holds = [1, 3, 5, 10, 20]
    holds_confirm = {3, 5, 10}

    brazos: dict[str, dict] = {"default": {}}
    confirmatorios = {"default"}
    for u in umbrales:
        for lb in lookbacks:
            for h in holds:
                nombre = f"u{u}-lb{lb}-h{h}"
                brazos[nombre] = {
                    "ac_decel_umbral": round(u * 0.01, 10),
                    "ac_decel_lookback": lb,
                    "ac_modulate_hold_bars": h,
                }
                if u in umbrales_confirm and lb in lookbacks_confirm and h in holds_confirm:
                    confirmatorios.add(nombre)
    brazos["ac_off"] = {"ac_modulate": False}
    for f in (0.10, 0.50, 0.75):
        brazos[f"factor{_fmt2(f)}"] = {"ac_modulate_factor": f}
    return brazos, confirmatorios


def _grid_p05() -> tuple[dict[str, dict], set[str]]:
    valores = [1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75,
               4.0, 4.25, 4.5, 4.75, 5.0, 5.5, 6.0]
    confirmatorios_v = {2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0}
    brazos = {}
    confirmatorios = set()
    for v in valores:
        nombre = "default" if v == 3.0 else f"mult{_fmt2(v)}"
        brazos[nombre] = {} if v == 3.0 else {"mult": v}
        if v in confirmatorios_v:
            confirmatorios.add(nombre)
    return brazos, confirmatorios


def _grid_p08() -> tuple[dict[str, dict], set[str]]:
    valores = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 1.00]
    confirmatorios_v = {0.00, 0.10, 0.20, 0.30}
    brazos = {}
    confirmatorios = set()
    for v in valores:
        nombre = "default" if v == 0.00 else f"slo{_fmt2(v)}"
        brazos[nombre] = {} if v == 0.00 else {"sl_offset": v}
        if v in confirmatorios_v:
            confirmatorios.add(nombre)
    return brazos, confirmatorios


def construir_manifiesto(*, engine_sha: str) -> dict:
    p02_s6_brazos, p02_s6_conf = _grid_p02()
    p02_s7_brazos, p02_s7_conf = _grid_p02()
    p03_brazos, p03_conf = _grid_p03()
    p05_brazos, p05_conf = _grid_p05()
    p08_brazos, p08_conf = _grid_p08()

    corridas = [
        {
            "run_key": "P02-S6", "tipo": "ola1_paired",
            "palanca": "P-02", "sid": "S6-K2P0", "clase": "1-A",
            "brazo_control": "default", "secundaria": "p02",
            "brazos": p02_s6_brazos, "confirmatorios": sorted(p02_s6_conf),
        },
        {
            "run_key": "P02-S7", "tipo": "ola1_paired",
            "palanca": "P-02", "sid": "S7-TPNONE", "clase": "1-A",
            "brazo_control": "default", "secundaria": "p02",
            "brazos": p02_s7_brazos, "confirmatorios": sorted(p02_s7_conf),
        },
        {
            "run_key": "P03-S6", "tipo": "ola1_paired",
            "palanca": "P-03", "sid": "S6-K2P0", "clase": "1-A",
            "brazo_control": "default", "secundaria": "p03",
            "brazos": p03_brazos, "confirmatorios": sorted(p03_conf),
        },
        {
            "run_key": "P05-ST", "tipo": "ola1_paired",
            "palanca": "P-05", "sid": "SuperTrend-p14x3-M15", "clase": "1-B",
            "brazo_control": "default", "secundaria": "none",
            "brazos": p05_brazos, "confirmatorios": sorted(p05_conf),
        },
        {
            "run_key": "P08-ST", "tipo": "ola1_paired",
            "palanca": "P-08", "sid": "SuperTrend-p14x3-M15", "clase": "1-A",
            "brazo_control": "default", "secundaria": "p08",
            "brazos": p08_brazos, "confirmatorios": sorted(p08_conf),
        },
    ]

    return {
        "experimento": "OLA1-palancas-de-salida",
        "area": "B",
        "etapa": "F0",
        "hipotesis": PREREGISTRO,
        "substrate_id": SUBSTRATE_ID,
        "engine_sha": engine_sha,
        "salidas": {
            "resultados": "research/fases/F0-preparacion/04-resultados/OLA1/",
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
