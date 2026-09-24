"""sentinel_engine.live.ava_window_gate -- R1 (blackout de apertura) + R2
(ventana operativa) para el despliegue AVA de S6-K2P0 y SuperTrend-p14x3-M15
ORIGINALES (D-62, 2026-08-20; spec
`research/fases/F0-preparacion/02-specs/2026-08-19-reglas-operativas-ava.md`).

QUE ES Y QUE NO ES
-------------------
Este modulo es infraestructura del EJECUTOR (`scripts/live/run_live_20.py`),
NO una estrategia viva -- R1-bis/R7 (byte-identidad de S6/S7/SuperTrend) no lo
alcanza. Es un gate OPT-IN, evaluado SOLO para configs que lleven la clave
`cfg["window_gate"]` (ver `sentinel_engine.strategies.live_configs_20.
CONFIGS_AVA`); un config sin esa clave nunca toca este modulo y su
comportamiento no cambia en absoluto.

R1 -- blackout de apertura (INVIOLABLE). Ninguna posicion en las primeras 3
velas M15 tras la apertura (18:00 ET, ancla de mercado = reapertura de CME
Globex). Primera vela elegible: la 4a, es decir la que ABRE a las 18:45 ET.
El ancla se deriva del CALENDARIO medido (ver R2), nunca de un "18" hardcodeado
suelto, para que R1 seguir cableado a la misma apertura que R2 si esta se
recalibra alguna vez.

R2 -- ventana operativa. Reutiliza EXACTAMENTE el calendario de periodos
medido por D-36/D-37 (`scripts/research/ventana_calendario.py` +
`research/fases/F0-preparacion/04-resultados/T0.13-ventana-ny/
calendario-ventana.json`) -- NO se re-deriva ni se inventa. Ese calendario fue
medido sobre el gate de spread de CAPITARIA (broker="capitaria" en
`ny_window.BROKER_TZ`), pero la propia D-36 ya declara la extrapolacion a
otros sustratos como HIPOTESIS, no como hecho medido -- aqui se aplica esa
misma hipotesis declarada al reloj de AVA. La conversion de reloj usa
`ny_window.server_epoch_to_ny(t, "ava")`: el broker AVA corre en UTC fijo, sin
DST (verificado T0.14 y reconfirmado en vivo, ver informe del implementador),
asi que la conversion es real y no un supuesto adicional de este modulo.

CAVEAT DE HONESTIDAD (R3/R6, no resuelto aqui, no se decide aqui): T0.15
midio, sobre el sustrato de Capitaria, que el gate de VENTANA SOLO (sin
spread) NO reproduce fielmente el desempeno historico de S6/S7 bajo el gate de
spread (divergencia de neto 73%/302%, ambos fallan el umbral de <=25%);
SuperTrend si pasa. R2 es el PISO exigido por el user (replicar el horario),
no el objetivo final (R3) -- este modulo implementa el piso tal como esta
especificado, sin inventar un gate mejor ni prometer paridad de resultado.

FALLO DUERO, NUNCA UN DEFAULT SILENCIOSO: si el calendario no existe, esta mal
formado, o el broker no esta en `BROKER_TZ`, este modulo deja propagar la
excepcion -- un gate de apertura roto debe DETENER las aperturas, nunca
abrirlas "por si acaso" (igual criterio que `gap_wait.load()`, que sí admite
fail-open hacia "denegar", nunca hacia "permitir").
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CALENDARIO_PATH = (REPO_ROOT / "research" / "fases" / "F0-preparacion"
                    / "04-resultados" / "T0.13-ventana-ny"
                    / "calendario-ventana.json")

# R1: velas M15 bloqueadas tras la apertura (3 -> elegible desde la 4a, +45 min).
R1_BLACKOUT_CANDLES = 3
BAR_MINUTES_M15 = 15
R1_BLACKOUT_MINUTES = R1_BLACKOUT_CANDLES * BAR_MINUTES_M15  # 45

DEFAULT_BROKER = "ava"


@lru_cache(maxsize=4)
def _cargar_calendario_cached(path_str: str) -> dict:
    from scripts.research import ventana_calendario
    return ventana_calendario.cargar_calendario(Path(path_str))


def cargar_calendario_ava(path: Path | str = CALENDARIO_PATH) -> dict:
    """Carga (con cache por ruta) el calendario de periodos D-36/D-37. Falla
    duro (`FileNotFoundError`/`KeyError`/`ValueError`, ver
    `ventana_calendario.cargar_calendario`) si el fichero falta o esta
    incompleto -- nunca un calendario vacio silencioso."""
    return _cargar_calendario_cached(str(path))


def r1_ok(dt_ny: datetime, apertura_hora: int) -> bool:
    """True si `dt_ny` (hora de Nueva York) NO cae en las primeras
    `R1_BLACKOUT_CANDLES` velas M15 tras `apertura_hora`. `apertura_hora` se
    deriva SIEMPRE del calendario vigente (ver `open_allowed`), nunca de un
    literal hardcodeado aparte de R2 -- si el calendario cambiara su hora de
    apertura, R1 se mueve con el sin requerir un segundo cambio de codigo.

    Bloquea `apertura_hora:00`, `:15`, `:30` (velas 1-3, identificadas por su
    hora de APERTURA, igual convencion que MT5/`calendario-ventana.json`).
    Elegible desde `apertura_hora:45` (vela 4) en adelante."""
    return not (dt_ny.hour == apertura_hora and dt_ny.minute < R1_BLACKOUT_MINUTES)


def open_allowed(bar_t: float, calendario: dict, *, broker: str = DEFAULT_BROKER) -> bool:
    """True si una apertura evaluada sobre la barra M15 CERRADA `bar_t` (epoch
    en la convencion de `fetch_bars`/`backtest.py`: server wall clock del
    broker `broker`) cumple R1 Y R2 simultaneamente.

    `bar_t` es la hora de APERTURA de la barra cerrada (convencion MT5:
    `rates["time"]`), consistente con como `calendario-ventana.json` y
    `r1_ok` identifican velas por su apertura."""
    from scripts.research import ny_window, ventana_calendario
    dt_ny = ny_window.server_epoch_to_ny(bar_t, broker)
    apertura_hora, _cierre_hora = ventana_calendario.ventana_para(dt_ny, calendario)
    return (ventana_calendario.in_ventana(dt_ny, calendario)
            and r1_ok(dt_ny, apertura_hora))
