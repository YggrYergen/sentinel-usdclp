r"""Calendario de periodos de la ventana operativa (D-36, Paso 2b -- Artefacto 2).

Por que existe. D-34 midio que el cierre de la ventana operativa NO es un
borde fijo -- cambia una vez en 2026 (`02:00`->`03:00` ET el 2026-04-06). D-36
revoca el borde conservador fijo `18:00->02:00` ET de `ny_window.py` y ordena
modelar la ventana como CALENDARIO DE PERIODOS medido sobre el gate de
Capitaria (ver `scripts/research/medir_calendario_ventana.py` y su artefacto
`research/fases/F0-preparacion/04-resultados/T0.13-ventana-ny/calendario-ventana.json`).

R1-bis (charter SS A.11): NO modifica `scripts/analysis/realtick_bt/backtest.py`.

🔴 NO modifica `scripts/research/ny_window.py`. Ese modulo SIGUE VIGENTE:
`cost_overlay.py` depende de el (`in_ny_window`, `server_epoch_to_ny`) y no se
toca. Este modulo es una EXTENSION nueva que reutiliza `server_epoch_to_ny` y
`BROKER_TZ` (la conversion de reloj de `ny_window.py`, ya testeada) para
resolver, en vez del offset fijo `18:00->02:00`, el par (apertura, cierre)
VIGENTE en la fecha consultada segun el calendario medido.

La ventana cruza medianoche -- la pertenencia es SIEMPRE una disyuncion
(`hora >= apertura or hora < cierre`), nunca un rango (`apertura <= hora <
cierre`, que es SIEMPRE FALSO cuando apertura > cierre y devuelve el
conjunto vacio sin lanzar ningun error). Ver `in_ventana()`.

EXTRAPOLACION (la parte delicada, D-36). Capitaria solo cubre desde
`2026-01`, pero el sustrato de AVA va de 2022 a 2026. Para fechas anteriores
al primer periodo medido (`calendario["rango_medido"]["desde"]`) NO hay dato
que consultar: se aplica la regla de extrapolacion declarada por D-36 -- se
conserva la apertura `18:00` ET (ancla de mercado, ver contexto del brief:
"el borde solido... no se toca") y se aplica el cierre del periodo medido MAS
CERCANO en el calendario, respetando el DST vigente en esa fecha. Esto se
implementa mapeando (mes, dia) de la fecha consultada al "ano patron" del
primer periodo medido y resolviendo el periodo vigente en esa fecha-patron
(reproduce el mismo ciclo estacional cada ano, en vez de fijar para siempre
la regla del primer dia medido). Ningun consumidor puede ignorar si un
resultado viene de zona medida o extrapolada: `es_extrapolado()` responde esa
pregunta explicitamente, y nunca hay una extrapolacion silenciosa.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from scripts.research.ny_window import server_epoch_to_ny  # reutilizado, NO reimplementado

_CAMPOS_REQUERIDOS_CALENDARIO = ("periodos", "rango_medido")
_CAMPOS_REQUERIDOS_PERIODO = ("desde", "hasta", "apertura_ny", "cierre_ny", "n_semanas", "n_semanas_baja_cobertura")
_CAMPOS_REQUERIDOS_RANGO_MEDIDO = ("desde", "hasta")


def cargar_calendario(path) -> dict:
    """Carga el JSON de calendario producido por
    `scripts/research/medir_calendario_ventana.py`. Falla duro (nunca un
    default silencioso) si el fichero no existe, no es JSON valido, le falta
    `periodos` o `rango_medido`, la lista de periodos esta vacia, o a algun
    periodo le falta alguna clave requerida."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"calendario de ventana no encontrado: {p}")
    with p.open("r", encoding="utf-8") as f:
        calendario = json.load(f)

    faltantes = [c for c in _CAMPOS_REQUERIDOS_CALENDARIO if c not in calendario]
    if faltantes:
        raise KeyError(f"calendario incompleto: faltan las claves {faltantes} ({p})")

    if not calendario["periodos"]:
        raise ValueError(f"calendario sin periodos: {p}")

    for i, periodo in enumerate(calendario["periodos"]):
        faltantes_periodo = [c for c in _CAMPOS_REQUERIDOS_PERIODO if c not in periodo]
        if faltantes_periodo:
            raise KeyError(f"periodo #{i} incompleto: faltan las claves {faltantes_periodo} ({p})")

    faltantes_rango = [c for c in _CAMPOS_REQUERIDOS_RANGO_MEDIDO if c not in calendario["rango_medido"]]
    if faltantes_rango:
        raise KeyError(f"calendario incompleto: faltan las claves 'rango_medido.{faltantes_rango}' ({p})")

    return calendario


def _hora(hhmm: str) -> int:
    """Extrae la hora entera de un campo 'HH:MM' del calendario. La
    resolucion de medicion es 15 min; la ventana operativa se consume a
    resolucion de hora entera (mismo criterio que `ny_window.in_ny_window`),
    asi que los minutos de jitter de medicion (p.ej. '18:15' vs '18:00') no
    alteran la hora entera resultante salvo que el jitter cruce la hora."""
    return int(hhmm.split(":")[0])


def _session_date(dt_ny: datetime) -> date:
    """Fecha de SESION a la que pertenece `dt_ny`: la sesion que abre a las
    18:00 ET del dia D se extiende hasta la madrugada del dia D+1, asi que
    las horas de madrugada (hora < 12) se asignan a la sesion del dia
    ANTERIOR. Mismo criterio de agrupacion semanal usado por
    `medir_calendario_ventana.py`."""
    d = dt_ny.date()
    return d if dt_ny.hour >= 12 else d - timedelta(days=1)


def _periodos_ordenados(calendario: dict) -> list[dict]:
    return sorted(calendario["periodos"], key=lambda p: p["desde"])


def _periodo_vigente_en(periodos_ordenados: list[dict], d: date) -> dict:
    """Ultimo periodo (por 'desde') cuyo 'desde' <= d. Un periodo mide la
    regla vigente DESDE su inicio hasta que el siguiente periodo la
    reemplaza; esto cubre por diseno los huecos de calendario sin datos
    (fines de semana, el holdout sellado) con la ultima regla conocida,
    sin inventar un periodo nuevo para ellos."""
    candidato = None
    for p in periodos_ordenados:
        if date.fromisoformat(p["desde"]) <= d:
            candidato = p
        else:
            break
    if candidato is None:
        # d es anterior al primer periodo -- no deberia llegar aqui: el
        # llamador (ventana_para) desvia a extrapolacion antes de esto.
        candidato = periodos_ordenados[0]
    return candidato


def _dia_del_anio_normalizado(mes: int, dia: int) -> tuple[int, int]:
    """Clampa 29-feb a 28-feb para poder mapear fechas de cualquier ano al
    'ano patron' de la medicion sin reventar en anos no bisiestos."""
    if mes == 2 and dia == 29:
        return 2, 28
    return mes, dia


def _periodo_extrapolado(calendario: dict, d_query: date) -> dict:
    """Regla de extrapolacion (D-36): se mapea (mes, dia) de `d_query` al
    'ano patron' del primer periodo medido y se resuelve el periodo vigente
    en esa fecha-patron -- reproduce el mismo ciclo estacional (DST) cada
    ano en vez de fijar para siempre la regla del primer dia medido. Si la
    fecha-patron cae fuera del rango medido (p.ej. un mes/dia de
    sept-dic, que Capitaria nunca cubrio), se usa el periodo cuyo borde
    (primero o ultimo) tiene menor distancia circular de dia-del-anio."""
    periodos_ordenados = _periodos_ordenados(calendario)
    primer_desde = date.fromisoformat(periodos_ordenados[0]["desde"])
    ultimo_hasta = date.fromisoformat(periodos_ordenados[-1]["hasta"])
    anio_patron = primer_desde.year

    mes, dia = _dia_del_anio_normalizado(d_query.month, d_query.day)
    fecha_patron = date(anio_patron, mes, dia)

    if primer_desde <= fecha_patron <= ultimo_hasta:
        return _periodo_vigente_en(periodos_ordenados, fecha_patron)

    # Fecha-patron fuera del rango medido: distancia circular (en dias del
    # anio) a los dos bordes del rango medido: el mas cercano gana.
    doy = fecha_patron.timetuple().tm_yday
    doy_ini = primer_desde.timetuple().tm_yday
    doy_fin = ultimo_hasta.timetuple().tm_yday
    dist_ini = min(abs(doy - doy_ini), 365 - abs(doy - doy_ini))
    dist_fin = min(abs(doy - doy_fin), 365 - abs(doy - doy_fin))
    return periodos_ordenados[0] if dist_ini <= dist_fin else periodos_ordenados[-1]


def ventana_para(dt_ny: datetime, calendario: dict) -> tuple[int, int]:
    """Devuelve `(hora_apertura, hora_cierre)` vigente en la fecha de sesion
    de `dt_ny`, segun `calendario`. Si la fecha es anterior al primer
    periodo medido (`calendario["rango_medido"]["desde"]`), aplica la regla
    de extrapolacion de D-36 (ver `_periodo_extrapolado`)."""
    d_query = _session_date(dt_ny)
    rango_desde = date.fromisoformat(calendario["rango_medido"]["desde"])

    if d_query < rango_desde:
        periodo = _periodo_extrapolado(calendario, d_query)
    else:
        periodo = _periodo_vigente_en(_periodos_ordenados(calendario), d_query)

    return _hora(periodo["apertura_ny"]), _hora(periodo["cierre_ny"])


def es_extrapolado(dt_ny: datetime, calendario: dict) -> bool:
    """True si `dt_ny` cae en fecha anterior al primer periodo medido
    (`rango_medido.desde`) -- zona EXTRAPOLADA, no medida. False si cae
    dentro del rango medido, aunque el dato puntual de esa fecha no exista
    (p.ej. el holdout sellado): sigue dentro de `rango_medido`, solo que sin
    tick observable en ese tramo especifico."""
    d_query = _session_date(dt_ny)
    rango_desde = date.fromisoformat(calendario["rango_medido"]["desde"])
    return d_query < rango_desde


def in_ventana(dt_ny: datetime, calendario: dict) -> bool:
    """True si `dt_ny` cae dentro de la ventana operativa vigente en su
    fecha, segun `calendario`.

    🔴 La ventana cruza medianoche: la condicion DEBE ser una disyuncion
    (`hora >= apertura or hora < cierre`), NUNCA un rango (`apertura <= hora
    < cierre`, que es SIEMPRE FALSO cuando apertura > cierre -- como aqui,
    18 > 2/3 -- y devuelve el conjunto vacio sin lanzar ningun error)."""
    apertura, cierre = ventana_para(dt_ny, calendario)
    hour = dt_ny.hour
    return hour >= apertura or hour < cierre


def filter_bars(bars: list[dict], broker: str, calendario: dict) -> list[dict]:
    """Filtra `bars` (dicts con clave `"t"`, epoch en convencion
    `backtest.py`, ver `ny_window.server_epoch_to_ny`) a los que caen dentro
    de la ventana operativa vigente en su fecha, segun `calendario`.
    Devuelve una lista NUEVA; no muta `bars` ni los dicts que contiene."""
    return [b for b in bars if in_ventana(server_epoch_to_ny(b["t"], broker), calendario)]
