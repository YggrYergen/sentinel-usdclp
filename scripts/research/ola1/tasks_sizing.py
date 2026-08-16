r"""scripts/research/ola1/tasks_sizing.py -- OLA2 task-type `ola1_sizing`, for
P-13/P-15/P-16/P-17/P-18 (Kelly fractional, correlation discount, drawdown
throttle, ficha weights, Sharpe-rolling throttle).

Architecturally SIMPLER than `ola1_paired` (per the OLA2 brief, deliberately):
sizing is a POST-HOC lot multiplier over the SAME positions -- the T0.6 frozen
baseline for the three live strategies (S6-K2P0, S7-TPNONE,
SuperTrend-p14x3-M15), read ONCE and passed unmutated to
`sizing.apply_sizing()` for every arm. Since `apply_sizing()` preserves each
strategy's ORIGINAL per-sid order over the SAME input list (sizing.py's own
docstring/contract, WP-4), every arm's `sized[sid][i]` and the control's
`sized[sid][i]` are the SAME underlying position -- pairing is 100% by
CONSTRUCTION, not by `entry_identity` matching (there is no entry-identity
concept here: nothing about WHICH positions exist ever changes). This module
does not force sizing into `ola1_paired`'s entry-identity machinery, per the
brief's explicit instruction.

`metricas.json` is written in the SAME general shape as `ola1_paired`'s
(`lineage`/`control`/`brazos[arm].{overlay,confirmatorio,metricas,pareado}`)
so that `scripts.research.ola1.consolidar` can read sizing corridas WITHOUT
modification.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from scripts.analysis.realtick_bt.sizing import SizingConfig, apply_sizing
from scripts.research.ola1.pareado import _bootstrap_bloques
from scripts.research.ola1.sustrato import BASELINE_DIR, dia_servidor, respaldar_si_existe
from scripts.research.runner import lineage
from scripts.research.runner.tasks import register

SIDS = ["S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"]
PREREGISTRO = "research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-OLA2.md"
SUBSTRATE_ID = "t06-baseline-frozen-golden"
ETAPA = "F0"


class SizingBaselineDivergedError(Exception):
    """Lanzado cuando apply_sizing() no preserva orden/cardinalidad por sid --
    violaria el contrato de pareado trivial de este task-type (fail-loud, no
    se sigue en silencio con un pareado incorrecto)."""


def cargar_baseline() -> dict[str, list[dict[str, Any]]]:
    """T0.6 frozen-baseline resolved positions for the 3 live strategies --
    exactly the `resolved` shape `sizing.apply_sizing()` expects. Fresh dict
    per call (each arm's `apply_sizing()` call must see an unmutated
    baseline; `apply_sizing` itself never mutates its input, but this keeps
    callers independent of that guarantee too)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for sid in SIDS:
        path = BASELINE_DIR / f"posiciones_{sid}.json"
        with path.open("r", encoding="utf-8") as f:
            out[sid] = json.load(f)
    return out


def _pool(sized: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sid in SIDS:
        out.extend(sized[sid])
    return out


def _metricas_arm(sized: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    pool = _pool(sized)
    n = len(pool)
    net_lote1 = sum(p["net1"] * p.get("lot_mult", 1.0) for p in pool)
    return {
        "n": n,
        "net_lote1": net_lote1,
        "net_por_posicion_lote1": (net_lote1 / n) if n else None,
        "net_lote1_por_sid": {
            sid: sum(p["net1"] * p.get("lot_mult", 1.0) for p in sized[sid]) for sid in SIDS
        },
        "n_por_sid": {sid: len(sized[sid]) for sid in SIDS},
    }


def _pareado_trivial(sized_brazo: dict[str, list[dict[str, Any]]],
                      sized_control: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Pairing by POSITION (index-aligned per sid), never by entry_identity --
    see module docstring. Asserts the contract that makes this valid
    (same cardinality/order per sid); fails loud, never silently degrades to
    a partial/best-effort pairing."""
    diffs: list[float] = []
    dias: list[str] = []
    for sid in SIDS:
        pb = sized_brazo[sid]
        pc = sized_control[sid]
        if len(pb) != len(pc):
            raise SizingBaselineDivergedError(
                f"{sid}: sizing must never change WHICH positions exist or their count "
                f"({len(pb)} != {len(pc)}) -- sizing is a post-hoc multiplier, not a filter"
            )
        for a, c in zip(pb, pc):
            if a["t_in_exec"] != c["t_in_exec"] or a["t_exit"] != c["t_exit"]:
                raise SizingBaselineDivergedError(
                    f"{sid}: position order diverged between arm and control -- "
                    "apply_sizing must preserve per-sid order"
                )
            diff = a["net1"] * a.get("lot_mult", 1.0) - c["net1"] * c.get("lot_mult", 1.0)
            diffs.append(diff)
            dias.append(dia_servidor(c["t_exit"]))

    n = len(diffs)
    resultado: dict[str, Any] = {
        "n_control": n, "n_brazo": n, "n_casadas": n, "tasa_emparejamiento": 1.0,
        "n_solo_control": 0, "n_solo_brazo": 0, "degradado_a_1B": False,
        "n_identidades_duplicadas": 0,
    }
    if n == 0:
        resultado.update({"media_diff": None, "mediana_diff": None, "suma_diff": None,
                           "desvio_diff": None, "ic95_bajo": None, "ic95_alto": None,
                           "ic_excluye_0": None, "p_bootstrap": None, "n_dias_bloque": 0,
                           "motivo_no_evaluable": "n == 0"})
        return resultado

    arr = np.array(diffs, dtype="float64")
    resultado["media_diff"] = float(arr.mean())
    resultado["mediana_diff"] = float(np.median(arr))
    resultado["suma_diff"] = float(arr.sum())
    resultado["desvio_diff"] = float(arr.std(ddof=1)) if n >= 2 else None

    suma_dia: dict[str, float] = {}
    n_dia: dict[str, int] = {}
    for d, diff in zip(dias, diffs):
        suma_dia[d] = suma_dia.get(d, 0.0) + diff
        n_dia[d] = n_dia.get(d, 0) + 1
    dias_u = sorted(suma_dia)
    if len(dias_u) < 2:
        resultado.update({"ic95_bajo": None, "ic95_alto": None, "ic_excluye_0": None,
                           "p_bootstrap": None, "n_dias_bloque": len(dias_u),
                           "motivo_no_evaluable": "n_dias_bloque < 2"})
        return resultado

    resultado.update(_bootstrap_bloques(dias_u, suma_dia, n_dia))
    return resultado


def ola1_sizing(params: dict, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    palanca = params["palanca"]
    brazo_control = params["brazo_control"]
    brazos_cfg: dict[str, dict[str, Any]] = params["brazos"]
    confirmatorios = set(params.get("confirmatorios", []))

    baseline = cargar_baseline()

    sized_por_brazo: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for arm_name, cfg_kwargs in brazos_cfg.items():
        cfg = SizingConfig(**cfg_kwargs)
        sized_por_brazo[arm_name] = apply_sizing(baseline, cfg)

    metricas_por_brazo = {arm: _metricas_arm(s) for arm, s in sized_por_brazo.items()}

    pareado_por_brazo: dict[str, dict[str, Any]] = {}
    for arm_name in brazos_cfg:
        if arm_name == brazo_control:
            continue
        pareado_por_brazo[arm_name] = _pareado_trivial(
            sized_por_brazo[arm_name], sized_por_brazo[brazo_control]
        )

    sha = lineage.git_sha()
    lineage_block = {
        "run_id": out_dir.name, "palanca": palanca, "sid": "ALL-S6-S7-ST",
        "clase": "1-A", "substrate_id": SUBSTRATE_ID,
        "engine_sha": sha, "git_sha": sha, "etapa": ETAPA,
        "generador": "runner:tasks_sizing.ola1_sizing",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "estado_investigacion": "piloto-instrumento", "preregistro": PREREGISTRO,
    }
    control_block = {
        "brazo": brazo_control, "identico": True,
        "nota": ("sizing es 100% pareado por construccion (misma posicion, "
                 "mismo indice por sid) -- no requiere entry_identity"),
    }

    brazos_out: dict[str, Any] = {}
    for arm_name, cfg_kwargs in brazos_cfg.items():
        entry: dict[str, Any] = {
            "overlay": cfg_kwargs,
            "confirmatorio": arm_name in confirmatorios,
            "metricas": metricas_por_brazo[arm_name],
        }
        if arm_name in pareado_por_brazo:
            entry["pareado"] = pareado_por_brazo[arm_name]
        brazos_out[arm_name] = entry

    metricas_json = {
        "lineage": lineage_block,
        "control": control_block,
        "brazos": brazos_out,
    }
    metricas_path = out_dir / "metricas.json"
    respaldar_si_existe(metricas_path)
    with metricas_path.open("w", encoding="utf-8") as f:
        json.dump(metricas_json, f, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    return {
        "palanca": palanca, "sid": "ALL-S6-S7-ST", "clase": "1-A",
        "n_brazos": len(brazos_cfg), "n_confirmatorios": len(confirmatorios),
        "estado_investigacion": "piloto-instrumento",
    }


register("ola1_sizing", ola1_sizing, parallelizable=True)
