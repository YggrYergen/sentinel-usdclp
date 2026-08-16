"""scripts.research.runner.progress -- CLI: print the current _progreso.txt.

Spec (T0.9-B SS4): prints the content of _progreso.txt for a resultados_dir
and nothing else. No watching, no polling loop, no colours.

CLI:
    python -m scripts.research.runner.progress <resultados_dir>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.research.runner.progreso import read_progress_text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Imprime el contenido de _progreso.txt de un resultados_dir."
    )
    parser.add_argument("resultados_dir", type=Path, help="ruta al directorio de resultados")
    args = parser.parse_args(argv)

    content = read_progress_text(args.resultados_dir)
    if content is None:
        print(
            f"no existe _progreso.txt en {args.resultados_dir} "
            "(la corrida aun no ha escrito progreso, o el directorio no corresponde a un run)"
        )
        return 0

    print(content, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
