r"""scripts/research/ola1/consolidar.py -- OLA1-EXEC Bloque 8, consolidador PRE-INTERPRETACION.

CLI: python -m scripts.research.ola1.consolidar <resultados_dir>

Lee todos los <run_key>/metricas.json bajo `resultados_dir` y produce:
  - _consolidado.json: una fila plana por brazo, con palanca/sid/clase/
    confirmatorio/overlay/metricas/pareado/secundaria.
  - _consolidado.md: una tabla por corrida (TODOS sus brazos, nunca solo el
    mejor), ordenada por el valor del parametro barrido. Banner SS8-bis.
  - BH-FDR al 5% sobre p_bootstrap, calculada DOS VECES (E-04 SS2.4):
    p_bh_confirmatorio (solo brazos confirmatorios no-control) y p_bh_total
    (todos los no-control). Brazos sin p_bootstrap quedan FUERA del
    denominador de BH y se cuentan aparte, declarados.

🔴 Este modulo NO interpreta, NO rankea, NO recomienda, NO declara ganador
(charter SS A.4, SS B). Solo numeros, grillas y diagnosticos.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.research.ola1.sustrato import respaldar_si_existe

ALPHA_BH = 0.05

BANNER = """\U0001F534 PRE-INTERPRETACION -- DATOS SIN LEER
Este fichero contiene resultados crudos de la Ola 1. NO contiene interpretacion, ni lectura,
ni veredicto, ni recomendacion (charter SS A.4).
Ninguna interpretacion de estos datos es valida hasta haber sido discutida en profundidad con
el humano y aprobada por el (directiva del user, 2026-08-16). Lo que el controlador escriba
antes de esa conversacion es PROPUESTA DE LECTURA y vive en un fichero aparte.
Estado del resultado: piloto-instrumento (D-57) -- el congelado del motor no esta firmado.

UNIDAD de `net_lote1`: CLP (peso chileno) por 1.0 lote, NO USD -- confirmado leyendo
`scripts/analysis/realtick_bt/backtest.py:520` (`net1 = diff * CONTRACT * USDCLP`) y su
docstring de cabecera (linea 12: "Net in CLP (USDCLP=936.50)"). Las magnitudes de decenas de
millones que se ven en `net_lote1` son CLP, no USD (dividir por ~936.5 para una lectura
aproximada en USD).

\U0001F7E1 UN NETO ABSOLUTO NO ES UNA CIFRA DE FIAR POR SI SOLA. El simulador diverge 3.28% del
neto real (D-54/T0.7-M-H, tras modelar el deslizamiento de los stops) y el sesgo tiene SIGNO
OPUESTO por estrategia (penaliza a S6, favorece a SuperTrend -- N-xx 2026-08-15 en NEGATIVOS.md).
Lo que sobrevive a esa divergencia es la DIFERENCIA PAREADA contra el control (misma entrada,
mismo simulador, el sesgo se cancela en la resta) -- NUNCA el nivel absoluto. Las columnas
`net_positivo`/`diff_positivo` de abajo marcan un HECHO (el signo del numero), no un veredicto:
priorizar SIEMPRE `diff_positivo` (columna `media_diff`) sobre `net_positivo` al leer esta tabla.
"""


def _bh_fdr(pvalues_por_brazo: dict[str, float], *, alpha: float = ALPHA_BH) -> dict[str, bool]:
    """Benjamini-Hochberg al `alpha`. Devuelve {clave: rechaza_H0} para cada
    clave de `pvalues_por_brazo`. Lista vacia -> dict vacio."""
    items = sorted(pvalues_por_brazo.items(), key=lambda kv: kv[1])
    m = len(items)
    if m == 0:
        return {}
    umbral_k = 0
    for k, (_clave, p) in enumerate(items, start=1):
        if p <= (k / m) * alpha:
            umbral_k = k
    rechaza = {clave: (i <= umbral_k) for i, (clave, _p) in enumerate(items, start=1)}
    return rechaza


def _valor_orden(nombre: str, overlay: dict[str, Any]) -> tuple:
    """Clave de orden por el valor del parametro barrido -- nunca por
    resultado. `default` primero; despues por el/los valores numericos del
    overlay; fallback alfabetico."""
    if nombre == "default":
        return (0, 0.0, nombre)
    numeros = re.findall(r"-?\d+\.?\d*", nombre)
    if numeros:
        return (1, tuple(float(n) for n in numeros), nombre)
    return (2, 0.0, nombre)


def _cargar_corridas(resultados_dir: Path) -> dict[str, dict]:
    corridas: dict[str, dict] = {}
    for metricas_path in sorted(resultados_dir.glob("*/metricas.json")):
        run_key = metricas_path.parent.name
        with metricas_path.open("r", encoding="utf-8") as f:
            corridas[run_key] = json.load(f)
    return corridas


def _corridas_faltantes(resultados_dir: Path, presentes: set[str]) -> list[str]:
    """Subdirectorios de resultados_dir que NO tienen metricas.json --
    tipicamente corridas fallidas (fail-loud abortadas antes de escribir)."""
    faltantes = []
    for d in sorted(resultados_dir.iterdir()):
        if d.is_dir() and d.name not in presentes and not d.name.startswith("_"):
            faltantes.append(d.name)
    return faltantes


def construir_consolidado(resultados_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    corridas = _cargar_corridas(resultados_dir)

    filas: list[dict[str, Any]] = []
    for run_key, doc in corridas.items():
        lineage = doc["lineage"]
        # OLA2 (BLOCK-D): BH-FDR se corrige POR LOTE, nunca mezclando familias
        # de corridas distintas dentro de la misma consolidacion (pre-registro
        # OLA2 SS8) -- el lote lo identifica `lineage.generador` (ya presente
        # en todo metricas.json de ola1_paired/ola1_sizing); ausente ->
        # "sin_generador" (fallback, preserva el comportamiento de un unico
        # lote implicito para consolidaciones anteriores a este cambio, p.ej.
        # los fixtures de TestConsolidarMarcaPositivo).
        lote = lineage.get("generador") or "sin_generador"
        for arm_name, brazo in doc["brazos"].items():
            filas.append({
                "run_key": run_key,
                "palanca": lineage["palanca"],
                "sid": lineage["sid"],
                "clase": lineage["clase"],
                "lote_bh": lote,
                "arm": arm_name,
                "es_control": arm_name == doc["control"]["brazo"],
                "confirmatorio": brazo["confirmatorio"],
                "overlay": brazo["overlay"],
                "metricas": brazo["metricas"],
                "pareado": brazo.get("pareado"),
                "secundaria": brazo.get("secundaria"),
            })

    pvalues_confirm_por_lote: dict[str, dict[str, float]] = {}
    pvalues_total_por_lote: dict[str, dict[str, float]] = {}
    n_sin_p = 0
    for fila in filas:
        if fila["es_control"]:
            continue
        pareado = fila["pareado"]
        clave = f"{fila['run_key']}::{fila['arm']}"
        p = pareado.get("p_bootstrap") if pareado else None
        if p is None:
            n_sin_p += 1
            continue
        pvalues_total_por_lote.setdefault(fila["lote_bh"], {})[clave] = p
        if fila["confirmatorio"]:
            pvalues_confirm_por_lote.setdefault(fila["lote_bh"], {})[clave] = p

    rechazo_confirm_por_lote = {l: _bh_fdr(d) for l, d in pvalues_confirm_por_lote.items()}
    rechazo_total_por_lote = {l: _bh_fdr(d) for l, d in pvalues_total_por_lote.items()}

    for fila in filas:
        clave = f"{fila['run_key']}::{fila['arm']}"
        lote = fila["lote_bh"]
        fila["p_bh_confirmatorio"] = rechazo_confirm_por_lote.get(lote, {}).get(clave)
        fila["p_bh_total"] = rechazo_total_por_lote.get(lote, {}).get(clave)
        # Coordinador (clarificacion mid-task): marcar hecho (signo), nunca
        # veredicto -- ver BANNER para la prioridad diff_positivo > net_positivo.
        fila["net_positivo"] = fila["metricas"]["net_lote1"] > 0
        media_diff = (fila["pareado"] or {}).get("media_diff") if fila["pareado"] else None
        fila["diff_positivo"] = None if (fila["es_control"] or media_diff is None) else media_diff > 0

    lotes = sorted(set(pvalues_confirm_por_lote) | set(pvalues_total_por_lote))
    bh_por_lote = {
        l: {
            "n_confirmatorio_evaluados": len(pvalues_confirm_por_lote.get(l, {})),
            "n_confirmatorio_rechazados": sum(
                1 for v in rechazo_confirm_por_lote.get(l, {}).values() if v
            ),
            "n_total_evaluados": len(pvalues_total_por_lote.get(l, {})),
            "n_total_rechazados": sum(1 for v in rechazo_total_por_lote.get(l, {}).values() if v),
        }
        for l in lotes
    }
    resumen_bh = {
        "alpha": ALPHA_BH,
        "lotes": lotes,
        "bh_por_lote": bh_por_lote,
        "n_confirmatorio_evaluados": sum(v["n_confirmatorio_evaluados"] for v in bh_por_lote.values()),
        "n_confirmatorio_rechazados": sum(v["n_confirmatorio_rechazados"] for v in bh_por_lote.values()),
        "n_total_evaluados": sum(v["n_total_evaluados"] for v in bh_por_lote.values()),
        "n_total_rechazados": sum(v["n_total_rechazados"] for v in bh_por_lote.values()),
        "n_sin_p_bootstrap_fuera_del_denominador": n_sin_p,
        "corridas_presentes": sorted(corridas),
        "corridas_faltantes": _corridas_faltantes(resultados_dir, set(corridas)),
    }
    return filas, resumen_bh


def _fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def escribir_consolidado_md(filas: list[dict[str, Any]], resumen_bh: dict[str, Any],
                             path: Path) -> None:
    por_run: dict[str, list[dict[str, Any]]] = {}
    for fila in filas:
        por_run.setdefault(fila["run_key"], []).append(fila)

    lineas = [BANNER, "", f"# OLA1 -- consolidado ({sum(len(v) for v in por_run.values())} brazos "
              f"en {len(por_run)} corridas)", "",
              f"BH-FDR alpha={resumen_bh['alpha']} (agregado de {len(resumen_bh.get('lotes', []))} "
              "lote(s), NUNCA mezclados entre si -- ver desglose por lote abajo): confirmatorio "
              f"{resumen_bh['n_confirmatorio_rechazados']}/{resumen_bh['n_confirmatorio_evaluados']} "
              f"rechazados; total {resumen_bh['n_total_rechazados']}/{resumen_bh['n_total_evaluados']} "
              f"rechazados; {resumen_bh['n_sin_p_bootstrap_fuera_del_denominador']} brazos sin "
              "p_bootstrap (fuera del denominador de BH).", ""]
    for lote in resumen_bh.get("lotes", []):
        b = resumen_bh["bh_por_lote"][lote]
        lineas.append(
            f"- lote `{lote}`: confirmatorio {b['n_confirmatorio_rechazados']}/"
            f"{b['n_confirmatorio_evaluados']} rechazados; total {b['n_total_rechazados']}/"
            f"{b['n_total_evaluados']} rechazados."
        )
    lineas += ["",
               f"Corridas presentes: {', '.join(resumen_bh['corridas_presentes'])}.",
               f"Corridas faltantes: {', '.join(resumen_bh['corridas_faltantes']) or '(ninguna)'}.", ""]

    for run_key in sorted(por_run):
        grupo = sorted(por_run[run_key], key=lambda f: _valor_orden(f["arm"], f["overlay"]))
        lineas.append(f"## {run_key} ({len(grupo)} brazos)")
        lineas.append("")

        positivos_diff = [f["arm"] for f in grupo
                           if not f["es_control"] and (f["pareado"] or {}).get("media_diff", 0) is not None
                           and (f["pareado"] or {}).get("media_diff", -1) > 0]
        positivos_net = [f["arm"] for f in grupo if f["metricas"]["net_lote1"] > 0]
        lineas.append(f"- Brazos con `media_diff` (pareado vs. control) POSITIVO: "
                       f"{', '.join(positivos_diff) or '(ninguno)'}")
        lineas.append(f"- Brazos con `net_lote1` (absoluto, ver aviso arriba) POSITIVO: "
                       f"{', '.join(positivos_net) or '(ninguno)'}")
        lineas.append("")

        lineas.append("| brazo | control | confirmatorio | n | net_lote1 | net_positivo | "
                       "tasa_emparejamiento | media_diff | diff_positivo | "
                       "ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |")
        lineas.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for fila in grupo:
            m = fila["metricas"]
            p = fila["pareado"] or {}
            media_diff = p.get("media_diff")
            diff_positivo = "n/a (control)" if fila["es_control"] else (
                "" if media_diff is None else str(media_diff > 0))
            lineas.append(
                f"| {fila['arm']} | {fila['es_control']} | {fila['confirmatorio']} | {m['n']} | "
                f"{_fmt(m['net_lote1'])} | {m['net_lote1'] > 0} | "
                f"{_fmt(p.get('tasa_emparejamiento'))} | "
                f"{_fmt(media_diff)} | {diff_positivo} | {_fmt(p.get('ic95_bajo'))} | "
                f"{_fmt(p.get('ic95_alto'))} | {_fmt(p.get('p_bootstrap'))} | "
                f"{_fmt(fila['p_bh_confirmatorio'])} | {_fmt(fila['p_bh_total'])} |"
            )
        lineas.append("")

    respaldar_si_existe(path)
    path.write_text("\n".join(lineas), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("resultados_dir", type=Path)
    args = parser.parse_args(argv)

    resultados_dir = Path(args.resultados_dir)
    filas, resumen_bh = construir_consolidado(resultados_dir)

    consolidado_json_path = resultados_dir / "_consolidado.json"
    respaldar_si_existe(consolidado_json_path)
    with consolidado_json_path.open("w", encoding="utf-8") as f:
        json.dump({"brazos": filas, "bh_fdr": resumen_bh}, f, sort_keys=True, indent=2,
                   ensure_ascii=False, allow_nan=False)

    escribir_consolidado_md(filas, resumen_bh, resultados_dir / "_consolidado.md")

    print(f"consolidado escrito en {resultados_dir} -- {len(filas)} brazos, "
          f"{len(resumen_bh['corridas_presentes'])} corridas presentes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
