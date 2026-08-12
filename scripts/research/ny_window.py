r"""Filtro de ventana Nueva York -- T0.13 llevado a codigo.

Por que existe. T0.13 (cerrado, ver research/NEGATIVOS.md) midio que el "gate
de spread 0.5" que usa el sistema vivo de Capitaria no es un filtro de spread:
es un reloj. Por hora de servidor, el estado de spread estrecho esta al
99-100% dentro de una ventana concreta y al 0-5% fuera de ella. Convertida a
hora de Nueva York, esa ventana es 18:00 -> 02:00 ET, todo el ano (apertura de
la sesion electronica del oro en CME Globex). El backtest largo corre sobre el
sustrato de AVA, cuyo feed no codifica ese estado en el spread (es casi
unimodal), asi que la ventana debe reconstruirse aqui como regla de reloj
explicita en vez de heredarse "gratis" del gate de spread.

R1-bis (charter SS A.11): este modulo NO toca
`scripts/analysis/realtick_bt/backtest.py`. Es un envoltorio nuevo en
`scripts/research/`, igual que `scripts/research/baseline_golden.py`. La unica
dependencia de backtest.py es documental: reproduce su misma convencion de
reloj (docstring, backtest.py:15-26) para poder consumir sus mismos epochs.

EL PUNTO DE MAXIMO RIESGO -- leer dos veces
--------------------------------------------
`backtest.py` decodifica epochs con `datetime.utcfromtimestamp(t)` y lo
documenta el mismo (backtest.py:15-26) como "server wall clock": para
Capitaria, ese naive NO es UTC, es la hora de pared del servidor CHILENO
(zona horaria America/Santiago, con DST propio y variable segun el ano). Para
AVA, el servidor SI es UTC fijo (sin DST). La cadena correcta es:

    epoch -> utcfromtimestamp() -> naive en hora de pared DEL SERVIDOR
          -> se le adjunta la tz del broker (America/Santiago | UTC)
          -> .astimezone(America/New_York)

Escribir `naive.replace(tzinfo=timezone.utc).astimezone(NY)` para Capitaria
seria incorrecto por 3-4 horas, y el error seria silencioso: el backtest
seguiria devolviendo operaciones, solo que en la ventana equivocada. Ver
`tests/research/test_ny_window.py::test_capitaria_naive_no_es_utc_diverge_3_4h`.

No se hardcodean reglas de DST: Chile cambio sus reglas de DST varias veces
entre 2022 y 2026, asi que una regla escrita a mano seria falsa en algun ano.
Se delega en `zoneinfo` (tzdata del sistema), que ya reproduce los saltos
medidos por el controlador (T0.13): -3 el 2026-04-04, -4 el 2026-04-06.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Broker no declarado -> KeyError duro (BROKER_TZ[broker]), nunca un default
# silencioso. Ver server_epoch_to_ny().
BROKER_TZ: dict[str, timezone | ZoneInfo] = {
    "capitaria": ZoneInfo("America/Santiago"),
    "ava": timezone.utc,
}

NY_TZ = ZoneInfo("America/New_York")

# Ventana medida por T0.13: 18:00 -> 02:00 hora de Nueva York, todo el ano.
_WINDOW_START_HOUR = 18
_WINDOW_END_HOUR = 2


def server_epoch_to_ny(t: float, broker: str) -> datetime:
    """Convierte un epoch en convencion `backtest.py` (server wall clock, ver
    backtest.py:15-26) a un datetime aware en America/New_York.

    `broker` debe ser una clave de BROKER_TZ; cualquier otro valor lanza
    KeyError -- no hay default silencioso, porque tratar un broker no
    declarado como UTC (o como cualquier otra cosa) seria exactamente el tipo
    de error de 3-4h silencioso que esta funcion existe para evitar.

    Eleccion de `fold=0` en las horas ambiguas del cruce de DST (la hora que
    se repite al retroceder el reloj): se adjunta la tz ANTES de resolver la
    ambiguedad, y `fold=0` selecciona la primera ocurrencia (offset previo al
    cambio), que es el comportamiento por defecto de Python al construir un
    datetime aware sin especificar fold. No se necesita mayor precision aqui:
    la ventana de negocio (18:00->02:00 NY) no se solapa con la ventana de
    ambiguedad de 1h de ningun DST relevante (madrugada local del broker), asi
    que la eleccion de fold no cambia si un instante cae dentro o fuera de la
    ventana NY.
    """
    if broker not in BROKER_TZ:
        raise KeyError(
            f"broker no declarado en BROKER_TZ: {broker!r}. "
            f"Brokers conocidos: {sorted(BROKER_TZ)}. No hay default silencioso."
        )
    naive = datetime.utcfromtimestamp(t)  # server wall clock, NUNCA fromtimestamp()
    aware_server = naive.replace(tzinfo=BROKER_TZ[broker], fold=0)
    return aware_server.astimezone(NY_TZ)


def in_ny_window(dt_ny: datetime) -> bool:
    """True si `dt_ny` (se usa solo `.hour`, cualquier tz o naive) cae dentro
    de la ventana 18:00 -> 02:00 hora de Nueva York.

    La ventana cruza medianoche, asi que la condicion DEBE ser una
    disyuncion (`hora >= 18 or hora < 2`), nunca un rango (`18 <= hora < 2`,
    que es SIEMPRE FALSO y devolveria el conjunto vacio sin lanzar error).
    """
    hour = dt_ny.hour
    return hour >= _WINDOW_START_HOUR or hour < _WINDOW_END_HOUR


def filter_bars_ny(bars: list[dict], broker: str) -> list[dict]:
    """Filtra `bars` (dicts con clave `"t"`, epoch en convencion backtest.py)
    a los que caen dentro de la ventana NY. Devuelve una lista NUEVA; no muta
    `bars` ni los dicts que contiene."""
    return [b for b in bars if in_ny_window(server_epoch_to_ny(b["t"], broker))]
