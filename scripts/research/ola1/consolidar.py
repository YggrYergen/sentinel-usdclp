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
        for arm_name, brazo in doc["brazos"].items():
            filas.append({
                "run_key": run_key,
                "palanca": lineage["palanca"],
                "sid": lineage["sid"],
                "clase": lineage["clase"],
                "arm": arm_name,
                "es_control": arm_name == doc["control"]["brazo"],
                "confirmatorio": brazo["confirmatorio"],
                "overlay": brazo["overlay"],
                "metricas": brazo["metricas"],
                "pareado": brazo.get("pareado"),
                "secundaria": brazo.get("secundaria"),
            })

    pvalues_confirm: dict[str, float] = {}
    pvalues_total: dict[str, float] = {}
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
        pvalues_total[clave] = p
        if fila["confirmatorio"]:
            pvalues_confirm[clave] = p

    rechazo_confirm = _bh_fdr(pvalues_confirm)
    rechazo_total = _bh_fdr(pvalues_total)

    for fila in filas:
        clave = f"{fila['run_key']}::{fila['arm']}"
        fila["p_bh_confirmatorio"] = rechazo_confirm.get(clave)
        fila["p_bh_total"] = rechazo_total.get(clave)

    resumen_bh = {
        "alpha": ALPHA_BH,
        "n_confirmatorio_evaluados": len(pvalues_confirm),
        "n_confirmatorio_rechazados": sum(1 for v in rechazo_confirm.values() if v),
        "n_total_evaluados": len(pvalues_total),
        "n_total_rechazados": sum(1 for v in rechazo_total.values() if v),
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
              f"BH-FDR alpha={resumen_bh['alpha']}: confirmatorio "
              f"{resumen_bh['n_confirmatorio_rechazados']}/{resumen_bh['n_confirmatorio_evaluados']} "
              f"rechazados; total {resumen_bh['n_total_rechazados']}/{resumen_bh['n_total_evaluados']} "
              f"rechazados; {resumen_bh['n_sin_p_bootstrap_fuera_del_denominador']} brazos sin "
              "p_bootstrap (fuera del denominador de BH).", "",
              f"Corridas presentes: {', '.join(resumen_bh['corridas_presentes'])}.",
              f"Corridas faltantes: {', '.join(resumen_bh['corridas_faltantes']) or '(ninguna)'}.", ""]

    for run_key in sorted(por_run):
        grupo = sorted(por_run[run_key], key=lambda f: _valor_orden(f["arm"], f["overlay"]))
        lineas.append(f"## {run_key} ({len(grupo)} brazos)")
        lineas.append("")
        lineas.append("| brazo | confirmatorio | n | net_lote1 | tasa_emparejamiento | media_diff | "
                       "ic95_bajo | ic95_alto | p_bootstrap | p_bh_conf | p_bh_total |")
        lineas.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for fila in grupo:
            m = fila["metricas"]
            p = fila["pareado"] or {}
            lineas.append(
                f"| {fila['arm']} | {fila['confirmatorio']} | {m['n']} | "
                f"{_fmt(m['net_lote1'])} | {_fmt(p.get('tasa_emparejamiento'))} | "
                f"{_fmt(p.get('media_diff'))} | {_fmt(p.get('ic95_bajo'))} | "
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
