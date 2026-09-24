r"""scripts/research/ola1/manifiesto_ola2.py -- BLOCK-B (OLA2-reporte.md).

CLI: python -m scripts.research.ola1.manifiesto_ola2 [--salida <ruta>] [--engine-sha <sha>]

Genera research/fases/F0-preparacion/03-runs/2026-08-16-ola2.yaml a partir de las
grillas de research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-OLA2.md,
HARDCODEADAS AQUI (son el pre-registro, commit `e864e5a`; no se leen de ningun sitio
configurable) -- mismo patron que manifiesto_ola1b.py.

12 corridas: P19-S6/P19-S7 (`ola1_paired`, H4 EMA) + P28-S6/P28-S7 (`ola1_paired`, H1 EMA)
+ P21-S6 (`ola1_paired`, H1 momentum) + P20-ST (`ola1_paired`, H4 SuperTrend alignment) +
P09-S6 (`ola1_paired`, gate compuesto de regimen) + SIZING-P13/P15/P16/P17/P18
(`ola1_sizing`).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from scripts.research.runner import lineage

SALIDA_DEFAULT = Path("research/fases/F0-preparacion/03-runs/2026-08-16-ola2.yaml")
PREREGISTRO = "research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-OLA2.md"
SUBSTRATE_ID_HTF = "capitaria-ticks-2026-preholdout"
SUBSTRATE_ID_SIZING = "t06-baseline-frozen-golden"

HEADER_COMMENT = """# OLA2 -- manifiesto generado (BLOCK-B de OLA2-reporte.md)
#
# Generado por: python -m scripts.research.ola1.manifiesto_ola2
# Grillas HARDCODEADAS desde el pre-registro OLA2 (commit `e864e5a`), no configurables.
# 12 corridas: P19-S6/S7, P28-S6/S7, P21-S6, P20-ST, P09-S6 (ola1_paired, htf/regimen) +
# SIZING-P13/P15/P16/P17/P18 (ola1_sizing).
#
# PRE-INTERPRETACION -- este manifiesto no contiene resultados ni conclusiones.
"""

EMA_PERIODS = [10, 15, 20, 30]


def _grid_htf_ema(tf_sec: int) -> tuple[dict[str, dict], list[str]]:
    brazos: dict[str, dict] = {"default": {}}
    confirmatorios = []
    for p in EMA_PERIODS:
        nombre = f"p{p}"
        brazos[nombre] = {"_htf": {"tf_sec": tf_sec, "field": "ema_slope", "ema_period": p}}
        confirmatorios.append(nombre)
    return brazos, confirmatorios


def _grid_p21() -> tuple[dict[str, dict], list[str]]:
    brazos = {
        "default": {},
        "momentum": {"_htf": {"tf_sec": 3600, "field": "momentum", "momentum_lookback": 2}},
        "emaslope": {"_htf": {"tf_sec": 3600, "field": "ema_slope"}},
    }
    return brazos, ["momentum", "emaslope"]


def _grid_p20() -> tuple[dict[str, dict], list[str]]:
    brazos = {
        "default": {},
        "h4st": {"_htf": {"tf_sec": 14400, "field": "st_dir",
                           "st_atr_period": 14, "st_mult": 3.0}},
    }
    return brazos, ["h4st"]


def _grid_p09() -> tuple[dict[str, dict], list[str]]:
    base = {"adx_min": 20.0, "vr_low": 1.00, "er_min": 0.35, "chop_max": 61.8}
    variantes = {
        "baseline": {},
        "adx25": {"adx_min": 25.0},
        "vr095": {"vr_low": 0.95},
        "vr105": {"vr_low": 1.05},
        "er050": {"er_min": 0.50},
        "chop38": {"chop_max": 38.0},
    }
    brazos: dict[str, dict] = {"control": {}}
    confirmatorios = []
    for k in (2, 3):
        for suf, override in variantes.items():
            nombre = f"k{k}-{suf}"
            spec = {**base, **override, "k_of_m": k}
            brazos[nombre] = {"_regime": spec}
            confirmatorios.append(nombre)
    return brazos, confirmatorios


def _grid_p13() -> tuple[dict[str, dict], list[str]]:
    brazos: dict[str, dict] = {"neutral": {}}
    confirmatorios = []
    for a in (0.25, 0.50, 1.00):
        nombre = f"alpha{a:.2f}"
        brazos[nombre] = {"kelly_mult": a}
        confirmatorios.append(nombre)
    return brazos, confirmatorios


def _grid_p15() -> tuple[dict[str, dict], list[str]]:
    brazos: dict[str, dict] = {"neutral": {}}
    confirmatorios = []
    for d in (0.70, 0.77, 0.85):
        nombre = f"disc{d:.2f}"
        brazos[nombre] = {"correlation_discount_per_extra": d}
        confirmatorios.append(nombre)
    return brazos, confirmatorios


def _grid_p16() -> tuple[dict[str, dict], list[str]]:
    brazos = {
        "neutral": {},
        "ladder": {"dd_bands": [[5.0, 1.0], [10.0, 0.75], [15.0, 0.50], [1.0e9, 0.25]]},
        "continuous": {"dd_continuous": [20.0, 0.25]},
    }
    return brazos, ["ladder", "continuous"]


def _grid_p17() -> tuple[dict[str, dict], list[str]]:
    brazos = {
        "neutral": {},
        "asym-front": {"ficha_factors": {"F1": 1.20, "F2": 1.05, "F3": 0.75}},
        "asym-back": {"ficha_factors": {"F1": 0.90, "F2": 0.90, "F3": 1.20}},
    }
    return brazos, ["asym-front", "asym-back"]


def _grid_p18() -> tuple[dict[str, dict], list[str]]:
    brazos: dict[str, dict] = {"neutral": {}}
    confirmatorios = []
    for t in (0.3, 0.5, 0.7):
        for r in (0.20, 0.30, 0.50):
            nombre = f"sh{t:.1f}-r{int(r * 100)}"
            brazos[nombre] = {"sharpe_floor": t, "sharpe_floor_factor": r}
            confirmatorios.append(nombre)
    return brazos, confirmatorios


def construir_manifiesto(*, engine_sha: str) -> dict:
    corridas = []

    for sid in ("S6-K2P0", "S7-TPNONE"):
        brazos, conf = _grid_htf_ema(14400)
        corridas.append({
            "run_key": f"P19-{sid.split('-')[0]}", "tipo": "ola1_paired",
            "palanca": "P-19", "sid": sid, "clase": "1-B",
            "brazo_control": "default", "secundaria": "none",
            "brazos": brazos, "confirmatorios": conf,
        })
    for sid in ("S6-K2P0", "S7-TPNONE"):
        brazos, conf = _grid_htf_ema(3600)
        corridas.append({
            "run_key": f"P28-{sid.split('-')[0]}", "tipo": "ola1_paired",
            "palanca": "P-28", "sid": sid, "clase": "1-B",
            "brazo_control": "default", "secundaria": "none",
            "brazos": brazos, "confirmatorios": conf,
        })

    brazos_p21, conf_p21 = _grid_p21()
    corridas.append({
        "run_key": "P21-S6", "tipo": "ola1_paired",
        "palanca": "P-21", "sid": "S6-K2P0", "clase": "1-B",
        "brazo_control": "default", "secundaria": "none",
        "brazos": brazos_p21, "confirmatorios": conf_p21,
    })

    brazos_p20, conf_p20 = _grid_p20()
    corridas.append({
        "run_key": "P20-ST", "tipo": "ola1_paired",
        "palanca": "P-20", "sid": "SuperTrend-p14x3-M15", "clase": "1-B",
        "brazo_control": "default", "secundaria": "none",
        "brazos": brazos_p20, "confirmatorios": conf_p20,
    })

    brazos_p09, conf_p09 = _grid_p09()
    corridas.append({
        "run_key": "P09-S6", "tipo": "ola1_paired",
        "palanca": "P-09", "sid": "S6-K2P0", "clase": "1-B",
        "brazo_control": "control", "secundaria": "none",
        "brazos": brazos_p09, "confirmatorios": conf_p09,
    })

    for palanca, fn in (
        ("P-13", _grid_p13), ("P-15", _grid_p15), ("P-16", _grid_p16),
        ("P-17", _grid_p17), ("P-18", _grid_p18),
    ):
        brazos, conf = fn()
        corridas.append({
            "run_key": f"SIZING-{palanca.replace('-', '')}", "tipo": "ola1_sizing",
            "palanca": palanca, "brazo_control": "neutral",
            "brazos": brazos, "confirmatorios": conf,
        })

    return {
        "experimento": "OLA2-htf-regimen-sizing",
        "area": "B",
        "etapa": "F0",
        "hipotesis": PREREGISTRO,
        "substrate_id": SUBSTRATE_ID_HTF,
        "engine_sha": engine_sha,
        "salidas": {
            "resultados": "research/fases/F0-preparacion/04-resultados/OLA2/",
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
