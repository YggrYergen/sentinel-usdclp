"""tests/analysis/test_config_faulty.py -- Componente C de la réplica del motor
faulty (tag engine-faulty-tomachine-902 -> b113eb7).

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md
§2-bis (ADDENDUM 2026-08-13 -- Componente C).

El working tree tiene un roster `tomachine` DISTINTO del que realmente corrió
en la cuenta 902 (4 configs, selección 2026-07-22, sin `active_fichas` en
S6-K2P0, `volume`/`max_volume` en None) frente al roster congelado en
`b113eb7` (2 configs, selección 2026-07-27, `volume`/`max_volume` = 0.67,
`active_fichas` = 1 en S6-K2P0). Este módulo prueba que `config_faulty.py`
lee EXCLUSIVAMENTE del commit congelado, nunca del working tree.

R1-bis: nada aquí modifica `emasar_variant.py` / `live_configs_20.py` (vivo) /
ningún módulo vivo de `sentinel_engine/`. `_vendored_live_configs_20_b113eb7.py`
es una copia congelada, byte a byte, del blob de git en `b113eb7`; no se edita.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.analysis.realtick_bt.faulty.config_faulty import (
    configs_tomachine,
    kwargs_de,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VENDORED_PATH = (
    _REPO_ROOT
    / "scripts"
    / "analysis"
    / "realtick_bt"
    / "faulty"
    / "_vendored_live_configs_20_b113eb7.py"
)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={result.returncode}): {result.stderr}"
        )
    return result.stdout.strip()


def _git_available() -> bool:
    try:
        subprocess.run(
            ["git", "--version"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


# --- Test anti-deriva -------------------------------------------------------
# El que da valor a todo esto: si alguien edita el vendorizado, este test se
# pone rojo. Es la garantía de que la copia no se despega del motor que
# replica.


def test_vendored_module_matches_frozen_blob_hash():
    if not _git_available():
        pytest.skip("git no disponible en este entorno; no se puede verificar el hash")
    hash_local = _git("hash-object", str(_VENDORED_PATH))
    hash_congelado = _git("rev-parse", "b113eb7:sentinel_engine/strategies/live_configs_20.py")
    assert hash_local == hash_congelado, (
        "el módulo vendorizado difiere del blob congelado en b113eb7 -- "
        f"local={hash_local!r} congelado={hash_congelado!r}"
    )


_MODULO_VIVO_DOTTED = "sentinel_engine.strategies.live_configs_20"


def _importa_modulo_vivo(codigo_fuente: str) -> bool:
    """True si `codigo_fuente` contiene un `import`/`from ... import ...` real
    que resuelve a `sentinel_engine.strategies.live_configs_20` -- nunca una
    mención en comentario o docstring. Basado en `ast`, no en subcadenas: un
    docstring que explique "no importar de X" no debe contar como import de X.

    Detecta:
      - `import sentinel_engine.strategies.live_configs_20[ as alias]`
      - `import sentinel_engine.strategies.live_configs_20.<algo>` (submódulo)
      - `from sentinel_engine.strategies.live_configs_20 import <algo>`
      - `from sentinel_engine.strategies import live_configs_20`
    """
    arbol = ast.parse(codigo_fuente)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                nombre = alias.name
                if nombre == _MODULO_VIVO_DOTTED or nombre.startswith(
                    _MODULO_VIVO_DOTTED + "."
                ):
                    return True
        elif isinstance(nodo, ast.ImportFrom):
            modulo = nodo.module or ""
            if modulo == _MODULO_VIVO_DOTTED:
                return True
            if modulo == "sentinel_engine.strategies" and any(
                alias.name == "live_configs_20" for alias in nodo.names
            ):
                return True
    return False


def test_config_faulty_no_importa_del_modulo_vivo():
    """`config_faulty.py` no debe importar del módulo vivo
    `sentinel_engine.strategies.live_configs_20`. Un import REAL de esa ruta
    en el fichero es un fallo de la tarea; una mención en docstring/comentario
    (p. ej. explicando qué NO hay que importar) no cuenta -- se comprueba
    parseando con `ast`, no buscando subcadenas en el texto."""
    modulo_path = (
        _REPO_ROOT
        / "scripts"
        / "analysis"
        / "realtick_bt"
        / "faulty"
        / "config_faulty.py"
    )
    codigo_fuente = modulo_path.read_text(encoding="utf-8")
    assert not _importa_modulo_vivo(codigo_fuente), (
        "config_faulty.py no debe importar del módulo vivo "
        "sentinel_engine.strategies.live_configs_20 -- debe usar el vendorizado"
    )


@pytest.mark.parametrize(
    "codigo_sintetico",
    [
        "from sentinel_engine.strategies.live_configs_20 import CONFIGS_TOMACHINE\n",
        "import sentinel_engine.strategies.live_configs_20\n",
        "import sentinel_engine.strategies.live_configs_20 as lc20\n",
        "from sentinel_engine.strategies import live_configs_20\n",
    ],
)
def test_importa_modulo_vivo_detecta_import_prohibido_de_verdad(codigo_sintetico):
    """Comprobación negativa: si `_importa_modulo_vivo` estuviera mal escrito
    (p. ej. devolviera siempre False), este test lo delataría. Sin esto, un
    comprobador roto podría quedarse verde para siempre."""
    assert _importa_modulo_vivo(codigo_sintetico) is True


def test_importa_modulo_vivo_no_marca_mencion_en_docstring():
    """Comprobación negativa complementaria: una mención en prosa (docstring o
    comentario) de la ruta prohibida NO debe marcarse como import -- es
    exactamente el falso positivo que tenía la versión anterior de este test,
    basada en subcadenas."""
    codigo_sintetico = (
        '"""Este módulo NO importa de '
        "sentinel_engine.strategies.live_configs_20"
        ', usa el vendorizado en su lugar."""\n'
        "# tampoco: sentinel_engine.strategies.live_configs_20\n"
        "import copy\n"
    )
    assert _importa_modulo_vivo(codigo_sintetico) is False


# --- Tests de contenido, aserción exacta ------------------------------------


def test_configs_tomachine_devuelve_exactamente_2_configs_con_ids_correctos():
    configs = configs_tomachine()
    assert len(configs) == 2
    assert [c["id"] for c in configs] == ["S6-K2P0", "SuperTrend-p14x3-M15"]


def test_kwargs_de_s6_k2p0_active_fichas_es_1():
    kwargs = kwargs_de("S6-K2P0")
    assert kwargs["active_fichas"] == 1


def test_configs_tomachine_volume_y_max_volume_067_en_ambos():
    configs = configs_tomachine()
    by_id = {c["id"]: c for c in configs}
    for cid in ("S6-K2P0", "SuperTrend-p14x3-M15"):
        assert by_id[cid]["volume"] == 0.67, f"{cid} volume debe ser 0.67"
        assert by_id[cid]["max_volume"] == 0.67, f"{cid} max_volume debe ser 0.67"


def test_supertrend_config_engine_y_sin_active_fichas():
    configs = configs_tomachine()
    by_id = {c["id"]: c for c in configs}
    st = by_id["SuperTrend-p14x3-M15"]
    assert st["engine"] == "supertrend_always_in"
    assert "active_fichas" not in st["kwargs"]


def test_kwargs_de_supertrend_no_lleva_active_fichas():
    kwargs = kwargs_de("SuperTrend-p14x3-M15")
    assert "active_fichas" not in kwargs


def test_kwargs_de_config_id_desconocido_lanza_keyerror_con_ids_disponibles():
    with pytest.raises(KeyError) as exc_info:
        kwargs_de("no-existe")
    mensaje = str(exc_info.value)
    assert "S6-K2P0" in mensaje
    assert "SuperTrend-p14x3-M15" in mensaje


# --- Regresión que esta tarea existe para impedir ---------------------------
# El roster vendorizado (b113eb7, lo que corrió en la 902) DEBE diferir del
# roster del working tree (CONFIGS_TOMACHINE actual): 2 configs vs 4. Si algún
# día coincidieran, sería señal de que el vendorizado se desactualizó respecto
# al motor congelado, o de que el working tree "alcanzó" por casualidad al
# congelado -- cualquiera de las dos merece re-examen, no un verde silencioso.


def test_roster_vendorizado_difiere_del_working_tree_2_vs_4_configs():
    from sentinel_engine.strategies.live_configs_20 import (
        CONFIGS_TOMACHINE as CONFIGS_TOMACHINE_WORKING_TREE,
    )

    configs_congelados = configs_tomachine()
    assert len(configs_congelados) == 2, "el roster congelado (b113eb7) debe tener 2 configs"
    assert len(CONFIGS_TOMACHINE_WORKING_TREE) == 4, (
        "el roster del working tree debe tener 4 configs -- si esto cambió, "
        "la divergencia documentada en el addendum ya no aplica y hay que "
        "escalar, no ajustar este test en silencio"
    )
    ids_congelados = {c["id"] for c in configs_congelados}
    ids_working_tree = {c["id"] for c in CONFIGS_TOMACHINE_WORKING_TREE}
    assert ids_congelados != ids_working_tree

    s6_congelado = {c["id"]: c for c in configs_congelados}["S6-K2P0"]
    s6_working_tree = {c["id"]: c for c in CONFIGS_TOMACHINE_WORKING_TREE}["S6-K2P0"]
    assert s6_congelado["kwargs"]["active_fichas"] == 1
    assert "active_fichas" not in s6_working_tree["kwargs"], (
        "si el working tree ya trae active_fichas en S6-K2P0, la divergencia "
        "documentada se cerró y hay que escalar, no editar este test"
    )
