r"""scripts.research.runner.tasks_ola1 -- task-type `ola1_paired` (OLA1-EXEC Bloque 6).

Registra `ola1_paired` en scripts.research.runner.tasks para que el manifiesto
de la Ola 1 pueda referenciarlo via `tipo: ola1_paired`.

Que hace, en orden (brief SS Bloque 6):
  1. bars = sustrato.cargar_barras()
  2. resuelve cada brazo (misma logica que paired_harness.run_paired_arms con
     pares="contra_control"), escribiendo `_brazos.txt` segun va terminando
     cada brazo (visibilidad de progreso DENTRO de la corrida).
  3. sustrato.verificar_holdout() sobre TODAS las posiciones de TODOS los brazos.
  4. sustrato.verificar_control_contra_linea_base() -- si falla, la corrida
     entera falla, ruidosamente (regla 5 del pre-registro).
  5. riesgo.r_por_posicion() por brazo -> anade la clave R1 a cada posicion.
  6. metricas.metricas_de_brazo() por brazo.
  7. pareado.pareado_vs_control() por brazo != control.
  8. la secundaria que diga params["secundaria"], por brazo != control.
  9. escribe posiciones.csv, metricas.json, alineacion.json, _brazos.txt.
  10. devuelve un dict compacto (va a _resumen.json y al LEDGER).

Fail-loud (charter, protocolo 06 SS6): holdout tocado, control que no
reproduce, identidad duplicada inesperada, o R no computable en mas del 50%
de un brazo -- todos LANZAN. Nunca se rellena con un default ni se sigue en
silencio.
"""
from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from scripts.analysis.realtick_bt import backtest
from scripts.analysis.realtick_bt import regime as regime_mod
from scripts.analysis.realtick_bt.overlay import overlay_kwargs
from scripts.analysis.realtick_bt.paired_harness import PairedResult, _align, entry_identity
from scripts.research.ola1 import metricas as metricas_mod
from scripts.research.ola1 import pareado as pareado_mod
from scripts.research.ola1 import riesgo as riesgo_mod
from scripts.research.ola1 import secundarias as secundarias_mod
from scripts.research.ola1 import sustrato as sustrato_mod
from scripts.research.runner import lineage
from scripts.research.runner.tasks import register

PREREGISTRO = "research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-ola1.md"
AMPLIACION = "research/fases/F0-preparacion/01-hipotesis/2026-08-16-ampliacion-E04-ola1.md"
SUBSTRATE_ID = "capitaria-ticks-2026-preholdout"
ETAPA = "F0"

_SECUNDARIAS = {
    "p02": lambda sid, pb, pc: secundarias_mod.secundaria_p02(sid, pb, pc),
    "p03": lambda sid, pb, pc: secundarias_mod.secundaria_p03(sid, pb),
    "p08": lambda sid, pb, pc: secundarias_mod.secundaria_p08(sid, pb, pc),
}


class Ola1RNoComputableError(Exception):
    """Lanzado cuando R1 no es computable en mas del 50% de un brazo."""


class Ola1IdentidadDuplicadaError(Exception):
    """Lanzado cuando el pareado de un brazo contra el control encuentra
    identidades de entrada duplicadas -- anomalia inesperada, no un dato."""


def _expandir_htf_en_brazos(brazos: dict[str, dict[str, Any]],
                             bars: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """BLOCK-1 'siguiente ola' hook: un overlay de brazo puede llevar una
    clave `_htf` (params LOGICOS, nunca el array crudo -- el YAML del
    manifiesto no tiene que serializar 8.334 floats) en vez de `htf_mask`
    directamente:

        brazos:
          h4ema20: {_htf: {tf_sec: 14400, field: ema_slope, ema_period: 20}}

    Se expande AQUI, contra el `bars` YA recortado de esta corrida (respeta
    D-60 si `margen_extra_s>0`), a `backtest.build_htf_mask(bars, tf_sec,
    field=field, **resto)` y se sustituye por la clave `htf_mask` real que
    `simular_variant` consume (BLOCK-1, commit `a6a6979`/`877e5cd`). Overlays
    sin `_htf` pasan sin tocar -- no-op para P-02/P-03/P-05/P-08/P-34/etc.
    """
    out: dict[str, dict[str, Any]] = {}
    for arm_name, overlay in brazos.items():
        if "_htf" not in overlay:
            out[arm_name] = overlay
            continue
        spec = dict(overlay["_htf"])
        tf_sec = spec.pop("tf_sec")
        field = spec.pop("field")
        mask = backtest.build_htf_mask(bars, tf_sec, field=field, **spec)
        out[arm_name] = {**{k: v for k, v in overlay.items() if k != "_htf"}, "htf_mask": mask}
    return out


def _extraer_regime_de_brazos(
    brazos: dict[str, dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], dict[str, "regime_mod.RegimeGateConfig | None"]]:
    """OLA2 (P-09) hook, mismo patron que `_expandir_htf_en_brazos`: un overlay
    de brazo puede llevar una clave `_regime` (kwargs LOGICOS de
    `regime.RegimeGateConfig`, sin `enabled` -- se fuerza `enabled=True` aqui)
    en vez de que el gate viaje como kwarg real del motor (no lo es: ni
    `run_ladder` ni `run_supertrend` aceptan un `regime_cfg`). Se extrae ANTES
    de `overlay_kwargs`/`run_supertrend`, nunca llega a esas llamadas.
    Overlays sin `_regime` devuelven `None` en el segundo dict -- no-op para
    el resto de brazos/palancas (P-02/P-03/P-05/P-08/P-19/P-20/P-21/P-28/
    P-34/etc.)."""
    out: dict[str, dict[str, Any]] = {}
    cfg_por_brazo: dict[str, "regime_mod.RegimeGateConfig | None"] = {}
    for arm_name, overlay in brazos.items():
        if "_regime" not in overlay:
            out[arm_name] = overlay
            cfg_por_brazo[arm_name] = None
            continue
        spec = dict(overlay["_regime"])
        cfg_por_brazo[arm_name] = regime_mod.RegimeGateConfig(enabled=True, **spec)
        out[arm_name] = {k: v for k, v in overlay.items() if k != "_regime"}
    return out, cfg_por_brazo


def _resolver_brazos_con_progreso(sid: str, arms: dict[str, dict[str, Any]],
                                   bars: list[dict[str, Any]], ticks: "backtest.Ticks",
                                   out_dir: Path, *,
                                   regime_cfg_por_brazo: dict[str, "regime_mod.RegimeGateConfig | None"] | None = None,
                                   regime_series: "regime_mod.RegimeSeries | None" = None) -> tuple[dict, dict]:
    """Corre cada brazo UNA vez, en el orden del dict `arms`, escribiendo una
    linea en <out_dir>/_brazos.txt (append atomico, flush) segun cada uno
    termina -- visibilidad de progreso DENTRO de la corrida (95 brazos en
    P-03 no mueven el _progreso.txt del runner hasta el final).

    Misma logica exacta que paired_harness.run_paired_arms (mismo orden,
    mismos call-sites de backtest.run_supertrend/run_ladder/resolve), MAS
    (OLA2, P-09) un post-filtro opcional de regimen sobre las posiciones de
    SENAL (antes de resolve()) cuando `regime_cfg_por_brazo[arm_name]` no es
    `None` -- `backtest.apply_regime_gate_by_entry_bar`, harness-level, nunca
    toca `sentinel_engine` (WP-5). Byte-identico cuando `regime_cfg_por_brazo`
    es `None`/vacio o todas sus entradas son `None` -- probado idéntico en
    test_ola1.py::test_resolver_con_progreso_idem_run_paired_arms.
    """
    bar_times = np.array([b["t"] for b in bars], dtype="float64")
    signal_positions: dict[str, list[dict[str, Any]]] = {}
    resolved: dict[str, list[dict[str, Any]]] = {}
    brazos_path = out_dir / "_brazos.txt"
    out_dir.mkdir(parents=True, exist_ok=True)
    for arm_name, overlay in arms.items():
        t0 = time.monotonic()
        if sid == "SuperTrend-p14x3-M15":
            raw = backtest.run_supertrend(bars, ticks, **overlay)
        else:
            eff_kwargs = overlay_kwargs(sid, overlay)
            raw = backtest.run_ladder(eff_kwargs, bars)
        cfg = (regime_cfg_por_brazo or {}).get(arm_name)
        if cfg is not None:
            raw = backtest.apply_regime_gate_by_entry_bar(raw, bars, regime_series, cfg)
        signal_positions[arm_name] = raw
        out = []
        for p in raw:
            r = backtest.resolve(p, ticks, bar_times)
            if r is not None:
                out.append(r)
        resolved[arm_name] = out
        net_lote1 = sum(p["net1"] for p in out)
        segundos = time.monotonic() - t0
        linea = f"{arm_name}\t{len(out)}\t{net_lote1:.2f}\t{segundos:.3f}\n"
        with brazos_path.open("a", encoding="utf-8") as f:
            f.write(linea)
            f.flush()
        print(linea, end="", flush=True)
    return signal_positions, resolved


def _construir_paired_result(sid: str, arms: dict[str, dict[str, Any]],
                              signal_positions: dict, resolved: dict,
                              brazo_control: str) -> PairedResult:
    alignment_signal: dict[tuple[str, str], dict[str, Any]] = {}
    alignment_filled: dict[tuple[str, str], dict[str, Any]] = {}
    for other in arms:
        if other == brazo_control:
            continue
        a, b = brazo_control, other
        ids_a_sig = {entry_identity(sid, p) for p in signal_positions[a]}
        ids_b_sig = {entry_identity(sid, p) for p in signal_positions[b]}
        alignment_signal[(a, b)] = _align(ids_a_sig, ids_b_sig)
        ids_a_fill = {entry_identity(sid, p) for p in resolved[a]}
        ids_b_fill = {entry_identity(sid, p) for p in resolved[b]}
        alignment_filled[(a, b)] = _align(ids_a_fill, ids_b_fill)
    return PairedResult(sid=sid, arms=resolved, signal_positions=signal_positions,
                         alignment_signal=alignment_signal, alignment_filled=alignment_filled)


def _serializar_alineacion(tabla: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for (a, b), datos in tabla.items():
        out[f"{a}->{b}"] = {
            "n_casadas": datos["n_casadas"],
            "n_solo_A": datos["n_solo_A"],
            "n_solo_B": datos["n_solo_B"],
            "no_casadas_total": len(datos["no_casadas"]),
            "no_casadas": [list(ident) for ident in datos["no_casadas"][:50]],
        }
    return out


def _escribir_posiciones_csv(out_dir: Path, result: PairedResult) -> None:
    rows = result.rows()
    path = out_dir / "posiciones.csv"
    sustrato_mod.respaldar_si_existe(path)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({k for r in rows for k in r})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def ola1_paired(params: dict, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    palanca = params["palanca"]
    sid = params["sid"]
    clase = params["clase"]
    brazo_control = params["brazo_control"]
    secundaria_tipo = params.get("secundaria", "none")
    brazos: dict[str, dict[str, Any]] = params["brazos"]
    confirmatorios = set(params.get("confirmatorios", []))
    margen_extra_s = float(params.get("margen_extra_s", 0.0))

    bars = sustrato_mod.cargar_barras(margen_extra_s=margen_extra_s)
    brazos = _expandir_htf_en_brazos(brazos, bars)
    brazos, regime_cfg_por_brazo = _extraer_regime_de_brazos(brazos)
    regime_series = None
    if any(c is not None for c in regime_cfg_por_brazo.values()):
        # OLA2 (P-09): periodos FIJOS del pre-registro -- ADX(14), VR(lag=5,
        # ventana=100), ER(20), CHOP(14) -- nunca barridos, solo los umbrales
        # y k_of_m lo son (ver preregistro-OLA2.md SS P-09).
        regime_series = regime_mod.compute_regime_series(
            bars, adx_period=14, vr_window=100, vr_q=5, er_period=20, chop_period=14
        )
    ticks = backtest.Ticks()

    signal_positions, resolved = _resolver_brazos_con_progreso(
        sid, brazos, bars, ticks, out_dir,
        regime_cfg_por_brazo=regime_cfg_por_brazo, regime_series=regime_series,
    )
    result = _construir_paired_result(sid, brazos, signal_positions, resolved, brazo_control)

    todas_las_posiciones = [p for positions in result.arms.values() for p in positions]
    sustrato_mod.verificar_holdout(todas_las_posiciones)

    if margen_extra_s > 0.0:
        control_check = sustrato_mod.verificar_control_contra_linea_base_recortada(
            sid, result.arms[brazo_control], bars[-1]["t"]
        )
    else:
        control_check = sustrato_mod.verificar_control_contra_linea_base(
            sid, result.arms[brazo_control]
        )

    r_por_brazo: dict[str, list[float | None]] = {}
    for arm_name, overlay in brazos.items():
        r_vals = riesgo_mod.r_por_posicion(sid, overlay, result.arms[arm_name], bars)
        for p, r in zip(result.arms[arm_name], r_vals):
            p["R1"] = r
            p["net1_con_coste"] = (
                p["net1"] - metricas_mod.COSTE_CLP
                if p["reason"] in metricas_mod.REASONS_CON_COSTE else p["net1"]
            )
        r_por_brazo[arm_name] = r_vals

        n = len(r_vals)
        if n > 0:
            n_none = sum(1 for r in r_vals if r is None)
            if n_none / n > 0.5:
                raise Ola1RNoComputableError(
                    f"{sid}/{arm_name}: R no computable en {n_none}/{n} posiciones (>50%)"
                )

    metricas_por_brazo = {
        arm_name: metricas_mod.metricas_de_brazo(sid, arm_name, overlay,
                                                  result.arms[arm_name], bars)
        for arm_name, overlay in brazos.items()
    }

    pareado_por_brazo: dict[str, dict[str, Any]] = {}
    for arm_name in brazos:
        if arm_name == brazo_control:
            continue
        p = pareado_mod.pareado_vs_control(
            sid, result.arms[arm_name], result.arms[brazo_control], r_por_brazo[brazo_control]
        )
        if p["n_identidades_duplicadas"] > 0:
            raise Ola1IdentidadDuplicadaError(
                f"{sid}/{arm_name}: {p['n_identidades_duplicadas']} identidades de entrada "
                "duplicadas -- anomalia inesperada, no un dato"
            )
        pareado_por_brazo[arm_name] = p

    secundaria_por_brazo: dict[str, dict[str, Any]] = {}
    if secundaria_tipo != "none":
        fn = _SECUNDARIAS[secundaria_tipo]
        for arm_name in brazos:
            if arm_name == brazo_control:
                continue
            secundaria_por_brazo[arm_name] = fn(
                sid, result.arms[arm_name], result.arms[brazo_control]
            )

    _escribir_posiciones_csv(out_dir, result)

    run_id = out_dir.name
    sha = lineage.git_sha()
    lineage_block = {
        "run_id": run_id, "palanca": palanca, "sid": sid, "clase": clase,
        "substrate_id": SUBSTRATE_ID, "engine_sha": sha, "git_sha": sha,
        "etapa": ETAPA, "generador": "runner:tasks_ola1.ola1_paired",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "estado_investigacion": "piloto-instrumento",
        "preregistro": PREREGISTRO, "ampliacion": AMPLIACION,
    }
    sustrato_block = {
        "n_barras": len(bars), "t0": bars[0]["t"], "t1": bars[-1]["t"],
        "holdout_excluido": sustrato_mod.HOLDOUT_INI,
        "margen_extra_s": margen_extra_s,
    }
    control_block = {"brazo": brazo_control, **control_check}

    brazos_out: dict[str, Any] = {}
    for arm_name, overlay in brazos.items():
        entry: dict[str, Any] = {
            "overlay": overlay,
            "confirmatorio": arm_name in confirmatorios,
            "metricas": metricas_por_brazo[arm_name],
        }
        if arm_name in pareado_por_brazo:
            entry["pareado"] = pareado_por_brazo[arm_name]
        if arm_name in secundaria_por_brazo:
            entry["secundaria"] = secundaria_por_brazo[arm_name]
        brazos_out[arm_name] = entry

    metricas_json = {
        "lineage": lineage_block,
        "sustrato": sustrato_block,
        "control": control_block,
        "brazos": brazos_out,
    }
    metricas_path = out_dir / "metricas.json"
    sustrato_mod.respaldar_si_existe(metricas_path)
    with metricas_path.open("w", encoding="utf-8") as f:
        json.dump(metricas_json, f, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    alineacion_json = {
        "alignment_signal": _serializar_alineacion(result.alignment_signal),
        "alignment_filled": _serializar_alineacion(result.alignment_filled),
    }
    alineacion_path = out_dir / "alineacion.json"
    sustrato_mod.respaldar_si_existe(alineacion_path)
    with alineacion_path.open("w", encoding="utf-8") as f:
        json.dump(alineacion_json, f, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    resumen_brazos: dict[str, Any] = {}
    for arm_name in brazos:
        m = metricas_por_brazo[arm_name]
        entry = {
            "n": m["n"], "net_lote1": m["net_lote1"],
            "net_por_posicion_lote1": m["net_por_posicion_lote1"],
        }
        if arm_name in pareado_por_brazo:
            p = pareado_por_brazo[arm_name]
            entry.update({
                "tasa_emparejamiento": p["tasa_emparejamiento"],
                "media_diff": p["media_diff"],
                "ic95_bajo": p["ic95_bajo"], "ic95_alto": p["ic95_alto"],
                "ic_excluye_0": p["ic_excluye_0"], "p_bootstrap": p["p_bootstrap"],
            })
        resumen_brazos[arm_name] = entry

    return {
        "palanca": palanca, "sid": sid, "clase": clase,
        "n_brazos": len(brazos),
        "n_confirmatorios": len(confirmatorios),
        "estado_investigacion": "piloto-instrumento",
        "control_reproduce_linea_base": control_check["identico"],
        "brazos": resumen_brazos,
    }


register("ola1_paired", ola1_paired, parallelizable=True)
