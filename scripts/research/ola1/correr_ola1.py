r"""scripts/research/ola1/correr_ola1.py -- OLA1-EXEC Bloque 8, UNA sola orden.

CLI: python -m scripts.research.ola1.correr_ola1 [--workers N] [--manifiesto <ruta>]
     [--ledger-path <ruta>]

Hace, en orden y SIN preguntar nada (D-58 punto 3 -- entre el paso 1 y el
paso 5 no interviene ningun agente):
  1. imprime `git rev-parse HEAD` y la hora de inicio;
  2. run_manifest(manifiesto, on_error="continue", workers=N) -- SIEMPRE
     "continue" (D-53): una corrida mala no mata la noche;
  3. consolidar sobre el directorio de resultados;
  4. escribe _ESTADO.md (banner SS8-bis);
  5. imprime un resumen final de dos lineas.

Codigo de salida != 0 si alguna corrida fallo.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from scripts.research.ola1.consolidar import BANNER, construir_consolidado, escribir_consolidado_md
from scripts.research.ola1.sustrato import respaldar_si_existe
from scripts.research.runner.manifest import load_manifest
from scripts.research.runner.runner import DEFAULT_LEDGER_PATH, run_manifest

MANIFIESTO_DEFAULT = Path("research/fases/F0-preparacion/03-runs/2026-08-16-ola1.yaml")


def _git_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                           check=True).stdout.strip()


def _escribir_estado(resultados_dir: Path, resumen_bh: dict, ok: list[str], fallidas: list[str],
                      *, git_sha: str, inicio: str, fin: str) -> Path:
    lineas = [BANNER, "", "# OLA1 -- estado de la corrida", "",
              f"git_sha (momento de correr): {git_sha}",
              f"iniciado: {inicio}  finalizado: {fin}",
              f"corridas ok: {len(ok)} -- {', '.join(ok) or '(ninguna)'}",
              f"corridas fallidas: {len(fallidas)} -- {', '.join(fallidas) or '(ninguna)'}",
              f"BH-FDR alpha={resumen_bh['alpha']}: confirmatorio "
              f"{resumen_bh['n_confirmatorio_rechazados']}/{resumen_bh['n_confirmatorio_evaluados']}; "
              f"total {resumen_bh['n_total_rechazados']}/{resumen_bh['n_total_evaluados']}; "
              f"{resumen_bh['n_sin_p_bootstrap_fuera_del_denominador']} sin p_bootstrap.",
              ""]
    path = resultados_dir / "_ESTADO.md"
    respaldar_si_existe(path)
    path.write_text("\n".join(lineas), encoding="utf-8")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--manifiesto", type=Path, default=MANIFIESTO_DEFAULT)
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER_PATH)
    args = parser.parse_args(argv)

    sha = _git_sha()
    inicio = datetime.now().isoformat(timespec="seconds")
    print(f"git_sha={sha}  inicio={inicio}")

    manifest = load_manifest(args.manifiesto)
    resultados_dir = Path(manifest["salidas"]["resultados"])

    resultado = run_manifest(args.manifiesto, ledger_path=args.ledger_path,
                              on_error="continue", workers=args.workers)

    filas, resumen_bh = construir_consolidado(resultados_dir)
    consolidado_json_path = resultados_dir / "_consolidado.json"
    respaldar_si_existe(consolidado_json_path)
    import json
    with consolidado_json_path.open("w", encoding="utf-8") as f:
        json.dump({"brazos": filas, "bh_fdr": resumen_bh}, f, sort_keys=True, indent=2,
                   ensure_ascii=False, allow_nan=False)
    escribir_consolidado_md(filas, resumen_bh, resultados_dir / "_consolidado.md")

    fin = datetime.now().isoformat(timespec="seconds")
    ok = [c["run_key"] for c in manifest["corridas"] if c["run_key"] not in resultado["failed_run_keys"]]
    fallidas = resultado["failed_run_keys"]
    estado_path = _escribir_estado(resultados_dir, resumen_bh, ok, fallidas,
                                    git_sha=sha, inicio=inicio, fin=fin)

    print(f"corridas ok: {len(ok)}/{len(manifest['corridas'])}  fallidas: {len(fallidas)}")
    print(f"artefactos: {resultados_dir / '_consolidado.json'} | "
          f"{resultados_dir / '_consolidado.md'} | {estado_path}")

    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
