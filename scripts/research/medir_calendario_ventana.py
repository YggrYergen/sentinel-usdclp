r"""Medicion del calendario de periodos de la ventana operativa (D-36, Paso 2b
-- Artefacto 1).

Por que existe. D-34 midio que el cierre de la ventana operativa NO es un
borde fijo: cambia una vez en 2026 (02:00->03:00 ET el 2026-04-06). D-36
revoca el borde conservador fijo `18:00->02:00` ET y ordena modelar la
ventana como CALENDARIO DE PERIODOS medido sobre el gate de Capitaria, no
como offset unico. Este script hace esa medicion: para cada semana, localiza
el borde de apertura y el de cierre a resolucion de 15 minutos (el bucket
donde el % de ticks en estado estrecho cruza el 50%), expresa cada borde en
los tres relojes (Nueva York, UTC, servidor/Chile), y agrupa las semanas en
periodos contiguos con la misma tupla de bordes.

R1-bis (charter SS A.11): NO modifica `scripts/analysis/realtick_bt/backtest.py`.
Reutiliza `bt.TICKDIR` para localizar los parquet de ticks, igual que
`calibracion_costes_capitaria.py`. La condicion de estado "estrecho" es
copiada VERBATIM de `backtest.py:358` (`abs(spread - 0.5) <= 0.05`).

NO modifica `scripts/research/ny_window.py`: reutiliza `BROKER_TZ` (mismo
diccionario de timezones ya testeado) para construir, ademas de la conversion
a Nueva York, las conversiones paralelas a UTC y a hora de servidor (Chile),
que `ny_window.py` no expone porque no las necesita para su proposito (el
filtro de ventana solo necesita NY).

HOLDOUT SELLADO (charter SS A.14 + D-31 acto 1): Capitaria
`2026-05-12 -> 2026-07-26` es intocable. Este script mide sobre los DOS
tramos que rodean el sello por construccion: `[2026-01-01, 2026-05-12)` y
`[2026-07-27, 2026-08-13)` (el ultimo tick conocido en disco esta dentro de
ese rango). Guarda dura ANTES de leer disco (misma funcion que usa
`calibracion_costes_capitaria.py`) y guarda dura DESPUES de cargar, igual
patron.

Coste acotado (charter SS C, "pytest nunca en background" + brief punto 5):
se lee mes a mes desde `bt.TICKDIR`, se agregan los conteos de cada mes en
un diccionario por (semana, hora:minuto, reloj) y se descarta el DataFrame
crudo antes de pasar al mes siguiente. Nunca se mantienen los 28M ticks en
memoria simultaneamente.

Uso:  python -m scripts.research.medir_calendario_ventana
"""
from __future__ import annotations

import calendar
import json
import subprocess
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(r"D:\FOREX")
OUT_DIR = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.13-ventana-ny"
)
OUT_PATH = OUT_DIR / "calendario-ventana.json"

from scripts.analysis.realtick_bt import backtest as bt  # noqa: E402
from scripts.research.cost_overlay import (  # noqa: E402
    assert_fuera_holdout_capitaria,
    CAPITARIA_HOLDOUT_FIN,
    CAPITARIA_HOLDOUT_INI,
)
from scripts.research.ny_window import BROKER_TZ, NY_TZ  # noqa: E402

BROKER = "capitaria"
SERVER_TZ = BROKER_TZ[BROKER]          # America/Santiago, testeado en ny_window.py
UTC_TZ = timezone.utc

# Dos tramos declarados de antemano que rodean el holdout por construccion
# (mismo patron que calibracion_costes_capitaria.py).
SEG1_INI = calendar.timegm(datetime(2026, 1, 1).timetuple())
SEG1_FIN = CAPITARIA_HOLDOUT_INI                                 # 2026-05-12, exclusivo
SEG2_INI = CAPITARIA_HOLDOUT_FIN                                 # 2026-07-27
SEG2_FIN = calendar.timegm(datetime(2026, 8, 13).timetuple())    # exclusivo, > ultimo tick en disco

# Condicion de estado estrecho, copiada VERBATIM de backtest.py:358.
def _es_estrecho(spread: np.ndarray) -> np.ndarray:
    return np.abs(spread - 0.5) <= 0.05


# Orden cronologico de sesion (candidato ancho, cubre cualquier borde con
# margen): 15:00 -> 23:45 del dia D, luego 00:00 -> 08:45 del dia D+1. Se
# excluyen solo las horas de mitad de dia (09:00-14:59), donde ningun borde
# medido por D-34/D-36 cae en ninguno de los tres relojes.
_HOURS_ORDER = list(range(15, 24)) + list(range(0, 9))  # 18 horas, 72 buckets de 15 min


def _bucket_rank(hour: int, minute: int) -> int:
    """Indice 0..71 de un bucket de 15 min en el orden cronologico de sesion
    `_HOURS_ORDER`. Lanza si `hour` no esta en la ventana candidata (no debe
    ocurrir: se filtra antes de llamar)."""
    idx_hora = _HOURS_ORDER.index(hour)
    return idx_hora * 4 + minute // 15


def _bucket_label(hour: int, minute: int) -> str:
    return f"{hour:02d}:{(minute // 15) * 15:02d}"


def _months_in_range(ini: float, fin: float) -> list[str]:
    d0 = datetime.utcfromtimestamp(ini)
    d1 = datetime.utcfromtimestamp(fin)
    out = []
    y, m = d0.year, d0.month
    while (y, m) <= (d1.year, d1.month):
        out.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _load_segment_month(ym: str, ini: float, fin: float) -> pd.DataFrame:
    """Carga UN mes de ticks de bt.TICKDIR, recorta a [ini, fin). Vacio si el
    fichero no existe o no queda ningun tick en rango."""
    p = bt.TICKDIR / f"{ym}.parquet"
    if not p.exists():
        return pd.DataFrame(columns=["t", "bid", "ask"])
    df = pd.read_parquet(p, columns=["t_msc", "bid", "ask"])
    t = df["t_msc"].to_numpy() / 1000.0
    mask = (t >= ini) & (t < fin)
    if not mask.any():
        return pd.DataFrame(columns=["t", "bid", "ask"])
    out = df.loc[mask, ["bid", "ask"]].copy()
    out["t"] = t[mask]
    return out.reset_index(drop=True)


def _week_start_sunday(d: date) -> date:
    """Domingo de la semana que contiene `d` (Domingo..Sabado), mismo criterio
    que T0.13 (`validacion.json`, `fecha_ini`/`fecha_fin`)."""
    dias_desde_domingo = (d.weekday() + 1) % 7  # Monday=0 .. Sunday=6 -> domingo=0
    return d - timedelta(days=dias_desde_domingo)


def _procesar_mes(
    df: pd.DataFrame,
    acumulador: dict,
    totales_semana: dict,
    fechas_semana: dict,
) -> None:
    """Procesa un mes ya cargado en memoria: calcula los tres relojes de
    forma vectorizada, agrega en `acumulador[reloj][semana][bucket_label] =
    [n, n_narrow]` restringido a las 18 horas candidatas, en
    `totales_semana[semana]` acumula el conteo TOTAL de ticks de la semana
    (todas las horas, para el umbral de baja_cobertura), y en
    `fechas_semana[semana] = [min_fecha, max_fecha]` la fecha (sesion NY)
    real minima y maxima observada -- para que los periodos reporten fechas
    de datos reales, no aritmetica de limite de semana."""
    if df.empty:
        return

    t = df["t"].to_numpy()
    spread = (df["ask"] - df["bid"]).to_numpy()
    narrow = _es_estrecho(spread)

    naive = pd.to_datetime(t, unit="s")
    aware_srv = naive.tz_localize(SERVER_TZ, ambiguous=True, nonexistent="shift_forward")
    dt_ny = aware_srv.tz_convert(NY_TZ)
    dt_utc = aware_srv.tz_convert(UTC_TZ)
    dt_srv = aware_srv  # ya en hora de servidor (Chile)

    # Conteo total semanal (todas las horas), agrupado por sesion NY (la
    # sesion que abre el dia D se cuenta como semana de D, incluida su cola
    # de madrugada del dia D+1).
    ny_date = dt_ny.date
    ny_hour = dt_ny.hour
    session_date = np.where(ny_hour >= 12, ny_date, [d - timedelta(days=1) for d in ny_date])
    semana = pd.Series([_week_start_sunday(d) for d in session_date])
    for wk, cnt in semana.value_counts().items():
        totales_semana[wk.isoformat()] += int(cnt)
    fechas_serie = pd.Series(list(session_date))
    for wk, grupo in fechas_serie.groupby(semana.to_numpy()):
        wk_key = wk.isoformat()
        mn, mx = min(grupo), max(grupo)
        if wk_key not in fechas_semana:
            fechas_semana[wk_key] = [mn, mx]
        else:
            fechas_semana[wk_key][0] = min(fechas_semana[wk_key][0], mn)
            fechas_semana[wk_key][1] = max(fechas_semana[wk_key][1], mx)

    relojes = {"ny": dt_ny, "utc": dt_utc, "srv": dt_srv}
    for nombre_reloj, dt_idx in relojes.items():
        hour = dt_idx.hour.to_numpy()
        minute = dt_idx.minute.to_numpy()
        candidato = np.isin(hour, _HOURS_ORDER)
        if not candidato.any():
            continue
        sub_semana = semana.to_numpy()[candidato]
        sub_hour = hour[candidato]
        sub_min = minute[candidato]
        sub_narrow = narrow[candidato]
        labels = np.array([_bucket_label(h, m) for h, m in zip(sub_hour, sub_min)])

        tmp = pd.DataFrame({
            "semana": sub_semana,
            "bucket": labels,
            "narrow": sub_narrow,
        })
        grp = tmp.groupby(["semana", "bucket"])["narrow"].agg(["size", "sum"])
        for (wk, bucket), row in grp.iterrows():
            acc = acumulador[nombre_reloj][wk.isoformat()][bucket]
            acc[0] += int(row["size"])
            acc[1] += int(row["sum"])


def _edges_from_buckets(buckets: dict[str, list[int]]) -> tuple[str | None, str | None, dict]:
    """Dado `{bucket_label: [n, n_narrow]}`, ordena por `_bucket_rank` y
    localiza la PRIMERA transicion de <50% a >=50% (apertura) y la PRIMERA
    transicion de >=50% a <50% DESPUES de la apertura (cierre). Devuelve
    `(apertura_label, cierre_label, detalle)`; `detalle` trae la serie
    ordenada de (bucket, n, n_narrow, pct) para auditoria."""
    items = []
    for label, (n, n_narrow) in buckets.items():
        h, m = int(label[:2]), int(label[3:5])
        items.append((_bucket_rank(h, m), label, n, n_narrow))
    items.sort(key=lambda x: x[0])

    apertura = None
    cierre = None
    prev_pct = None
    for rank, label, n, n_narrow in items:
        pct = (n_narrow / n) if n else None
        if pct is not None:
            if apertura is None and prev_pct is not None and prev_pct < 0.5 <= pct:
                apertura = label
            elif apertura is not None and cierre is None and prev_pct is not None and prev_pct >= 0.5 > pct:
                cierre = label
            prev_pct = pct
    detalle = {
        "serie": [
            {"bucket": label, "n": n, "n_narrow": n_narrow,
             "pct_estrecho": round(100.0 * n_narrow / n, 4) if n else None}
            for _, label, n, n_narrow in items
        ]
    }
    return apertura, cierre, detalle


def _es_horario_verano(fecha: date, tz: ZoneInfo) -> bool:
    """True si el horario de verano (DST) de `tz` esta vigente en `fecha`
    (evaluada a mediodia local, para no caer en la hora ambigua/inexistente
    del propio cambio de hora), False si rige horario estandar.

    La frontera se deriva PROGRAMATICAMENTE del offset UTC de `tz` (via
    `zoneinfo`) -- NUNCA de una fecha de transicion hardcodeada. Se calcula
    el offset ESTANDAR del anio de `fecha` como el MAS ATRASADO (mas
    negativo) entre dos fechas de muestreo fijas -- 15 de enero y 15 de
    julio -- y se compara el offset de `fecha` contra ese estandar. El
    criterio `min(offset_ene, offset_jul)` da el offset estandar en
    CUALQUIER hemisferio sin necesidad de saber cual es cual: en el
    hemisferio sur (Chile) el estandar es julio (invierno austral) y el
    verano es enero; en el hemisferio norte (Nueva York) es al reves --
    estandar en enero (invierno boreal), verano en julio -- pero el minimo
    de los dos offsets sigue siendo el estandar en ambos casos, porque DST
    siempre ADELANTA el reloj (offset mas alto) respecto del estandar. Ver
    test dedicado para Nueva York que verifica esto explicitamente, no lo da
    por hecho. Generaliza sin cambios a cualquier anio en que este script se
    vuelva a correr."""
    anio = fecha.year
    offset_ene = tz.utcoffset(datetime(anio, 1, 15, 12))
    offset_jul = tz.utcoffset(datetime(anio, 7, 15, 12))
    offset_estandar = min(offset_ene, offset_jul)
    offset_actual = tz.utcoffset(datetime(fecha.year, fecha.month, fecha.day, 12))
    return offset_actual != offset_estandar


def es_verano_chile(fecha: date, tz: ZoneInfo) -> bool:
    """Horario de verano de Chile (`SERVER_TZ`, `America/Santiago`) vigente
    en `fecha`. Gobierna directamente `cierre_ny` (ver docstring de
    `_clave_canonica_cierre`). Envoltorio de `_es_horario_verano` -- no
    duplica la logica de muestreo de offset."""
    return _es_horario_verano(fecha, tz)


def es_verano_ny(fecha: date, tz: ZoneInfo) -> bool:
    """Horario de verano de Nueva York (`NY_TZ`) vigente en `fecha`. Gobierna
    la PROYECCION de la ventana (anclada a NY) sobre los relojes UTC y de
    servidor -- ver docstring de `_clave_canonica_cierre`. Envoltorio de
    `_es_horario_verano` -- no duplica la logica de muestreo de offset."""
    return _es_horario_verano(fecha, tz)


def _clave_canonica_cierre(fecha: date) -> tuple[bool, bool]:
    """Clave CANONICA de agrupamiento de periodo: tupla `(verano_chile,
    verano_ny)` en la fecha de la semana.

    `cierre_ny` esta anclado al DST de CHILE (el servidor cuyo reloj de
    pared decodifica los epochs, ver docstring del modulo) -- es estable
    mientras `es_verano_chile` no cambie. Pero su PROYECCION a UTC y a hora
    de servidor depende TAMBIEN del DST de NUEVA YORK, que desplaza esos dos
    relojes +-1h de forma independiente del de Chile (el DST de EEUU y el de
    Chile no coinciden en fecha). Agrupar solo por Chile mezclaria, dentro
    de un mismo periodo, semanas cuyo `apertura_utc`/`cierre_utc`/
    `apertura_srv`/`cierre_srv` real son distintos -- la moda publicaria
    entonces un valor FALSO para la mitad del periodo (degradacion
    silenciosa, charter SS A.13). La tupla evita eso sin fecha hardcodeada:
    cada componente se deriva de `zoneinfo` via `_es_horario_verano`."""
    return (es_verano_chile(fecha, SERVER_TZ), es_verano_ny(fecha, NY_TZ))


def _agrupar_semanas_canonico(semanas_ordenadas: list[str]) -> list[list[str]]:
    """Agrupa `semanas_ordenadas` (ISO `YYYY-MM-DD`, domingo de inicio de
    semana, YA ordenadas cronologicamente) en rachas maximas de semanas
    CONSECUTIVAS (salto de exactamente 7 dias, sin huecos de calendario) que
    comparten la misma clave CANONICA de cierre: `_clave_canonica_cierre()`
    de la fecha de la semana -- ver su docstring para por que es una tupla
    (Chile, Nueva York) y no solo Chile.

    Reemplaza la igualdad exacta del `cierre_ny` medido crudo (sujeto a
    jitter de +-15 min por la resolucion de bucket, y a semanas de medicion
    contaminada como la del cambio de horario de EEUU, `2026-03-08`) como
    clave de agrupamiento de periodos: la clave aqui depende SOLO de la
    fecha de la semana, nunca del valor medido, asi que el ruido de
    medicion no fragmenta el calendario. El hueco de un tramo no medido
    (p.ej. el holdout sellado de Capitaria) SI fragmenta, aunque ambos lados
    compartan la misma clave canonica -- no se afirma continuidad sobre
    territorio no medido."""
    periodos: list[list[str]] = []
    actual: list[str] = []
    for wk in semanas_ordenadas:
        wk_date = date.fromisoformat(wk)
        if not actual:
            actual = [wk]
            continue
        prev_date = date.fromisoformat(actual[-1])
        contiguas = (wk_date - prev_date).days == 7
        misma_clave = _clave_canonica_cierre(wk_date) == _clave_canonica_cierre(prev_date)
        if contiguas and misma_clave:
            actual.append(wk)
        else:
            periodos.append(actual)
            actual = [wk]
    if actual:
        periodos.append(actual)
    return periodos


def _moda(valores: list[str | None]) -> tuple[str | None, int]:
    """Valor mas frecuente de una lista (ignora None). Devuelve
    `(moda, n_discrepantes)`: n_discrepantes = semanas cuyo valor NO es la
    moda (jitter de medicion, declarado, no descartado). Combinada con
    `_agrupar_semanas_canonico` (que ya no fragmenta el calendario por ruido
    de agrupamiento), esta funcion es la que colapsa ese ruido DENTRO de
    cada grupo canonico: si el grupo tiene 14 semanas y 11 miden `02:00`,
    2 miden `02:15` (jitter) y 1 mide `03:00` (semana contaminada), la moda
    del grupo es `02:00` con 3 discrepantes -- ni se descartan ni fragmentan
    el periodo, quedan declarados en `n_semanas_bordes_discrepantes`.

    Desempate en caso de empate de conteo (posible con grupos pequenos, p.ej.
    un grupo de 6 semanas partido 3-3 entre `03:00` y `03:15`, caso real
    medido en el tramo `2026-04-05 -> 2026-05-10`): se prefiere el valor
    ALINEADO A LA HORA EN PUNTO (sufijo `:00`) sobre el valor con jitter de
    15 min, porque la resolucion de medicion es de bloques de 15 min
    alrededor de un borde real que, por diseno de esta medicion, siempre cae
    en la hora en punto -- el jitter es siempre el desviado, nunca el borde
    en si. Si ninguno de los empatados esta alineado a la hora (o ambos lo
    estan), se desempata alfabeticamente por determinismo."""
    limpios = [v for v in valores if v is not None]
    if not limpios:
        return None, len(valores)
    conteo: dict[str, int] = defaultdict(int)
    for v in limpios:
        conteo[v] += 1
    mejor = max(conteo.items(), key=lambda kv: (kv[1], kv[0].endswith(":00"), kv[0]))[0]
    n_discrepantes = sum(1 for v in valores if v != mejor)
    return mejor, n_discrepantes


def _git_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


UMBRAL_MIN_TICKS_SEMANA = 500_000  # declarado de antemano: separa semanas
# completas (~800k-2.5M ticks/semana, medido) de semanas parciales genuinas
# (semana del 2025-12-28: solo 2026-01-01, festivo; semana del 2026-05-10:
# solo 2 dias, el resto la corta el holdout del 2026-05-12).


def main() -> int:
    assert_fuera_holdout_capitaria(SEG1_INI, SEG1_FIN)
    assert_fuera_holdout_capitaria(SEG2_INI, SEG2_FIN)

    acumulador: dict = {r: defaultdict(lambda: defaultdict(lambda: [0, 0])) for r in ("ny", "utc", "srv")}
    totales_semana: dict = defaultdict(int)
    fechas_semana: dict = {}

    n_ticks_totales = 0
    for seg_ini, seg_fin in ((SEG1_INI, SEG1_FIN), (SEG2_INI, SEG2_FIN)):
        for ym in _months_in_range(seg_ini, seg_fin):
            df = _load_segment_month(ym, seg_ini, seg_fin)
            if df.empty:
                continue
            # Guarda dura DESPUES de cargar (mismo patron que calibracion_costes_capitaria.py).
            intrusos = df[(df["t"] >= CAPITARIA_HOLDOUT_INI) & (df["t"] < CAPITARIA_HOLDOUT_FIN)]
            if len(intrusos):
                raise SystemExit(
                    f"ABORTADO: {len(intrusos)} ticks cargados de {ym} caen dentro del "
                    "holdout sellado (SS A.14 + D-31). No se escribio ningun artefacto."
                )
            n_ticks_totales += len(df)
            _procesar_mes(df, acumulador, totales_semana, fechas_semana)
            print(f"  mes {ym}: {len(df):,} ticks procesados")

    if n_ticks_totales == 0:
        raise SystemExit("ningun tick cargado en ninguno de los dos tramos -- abortando")

    semanas_ordenadas = sorted(totales_semana.keys())

    # ---- bordes por semana, en los tres relojes -----------------------------
    bordes_semana: dict[str, dict] = {}
    for wk in semanas_ordenadas:
        entry = {"n_ticks_semana": totales_semana[wk], "baja_cobertura": totales_semana[wk] < UMBRAL_MIN_TICKS_SEMANA}
        for reloj in ("ny", "utc", "srv"):
            buckets = acumulador[reloj].get(wk, {})
            apertura, cierre, detalle = _edges_from_buckets(buckets) if buckets else (None, None, {"serie": []})
            entry[f"apertura_{reloj}"] = apertura
            entry[f"cierre_{reloj}"] = cierre
        bordes_semana[wk] = entry

    # ---- agrupacion en periodos contiguos (canonicalizada) -------------------
    # Un periodo es una racha maxima de semanas CONSECUTIVAS (sin salto de
    # calendario, es decir semanas contiguas domingo-a-domingo) con la MISMA
    # clave CANONICA de cierre: `_clave_canonica_cierre()` de la fecha de la
    # semana -- la tupla (verano_chile, verano_ny), NO la igualdad exacta del
    # `cierre_ny` medido crudo. Agrupar por el valor crudo produce ruido de
    # agrupamiento (11 periodos medidos en 7 meses de 2026): jitter de +-15
    # min de resolucion de bucket en semanas sueltas, y la semana
    # `2026-03-08` (cambio de horario de EEUU), cuya medicion esta
    # documentada como contaminada (D-34: 63.5% de tasa espectro-estrecho,
    # muy por debajo de cualquier umbral limpio) y que aparece aislada
    # midiendo `03:00` entre dos periodos `02:00`. Agrupar SOLO por Chile
    # (que es lo unico que gobierna `cierre_ny`) no basta: la PROYECCION de
    # ese cierre sobre UTC y hora de servidor tambien depende del DST de
    # Nueva York (fechas de transicion distintas de las de Chile), asi que
    # la clave es una tupla de los dos -- ver docstring de
    # `_clave_canonica_cierre`. Ambos componentes se derivan solo de la
    # fecha (via `zoneinfo`), nunca del valor medido, asi que el ruido de
    # medicion no fragmenta el calendario; el jitter y la semana contaminada
    # quedan dentro de su grupo correcto y son resueltos por moda mas abajo.
    # La apertura NO participa de la clave de agrupacion: D-34/D-36 la
    # establecen como el borde solido, "estable en todo el periodo... no se
    # toca" (contexto del brief); su propio jitter de +-15min (D-34: "18:00
    # en 16 de 20 semanas, 18:15 en 3 parciales") queda intacto y visible en
    # `bordes_por_semana` (auditoria semana a semana), sin fragmentar el
    # calendario de periodos. El hueco del holdout (2026-05-12 -> 2026-07-26,
    # sin datos) SI rompe la contiguidad por construccion, aunque comparta
    # clave canonica con el tramo anterior: no se afirma continuidad sobre
    # territorio no medido.
    periodos = _agrupar_semanas_canonico(semanas_ordenadas)

    calendario_periodos = []
    for semanas_periodo in periodos:
        wk0 = semanas_periodo[0]
        e0 = dict(bordes_semana[wk0])
        # Apertura canonicalizada a 18:00 ET (D-34/D-36: borde solido, no se
        # toca). cierre_ny, apertura_utc/apertura_srv y cierre_utc/cierre_srv:
        # moda entre las semanas del periodo (filtra el jitter de +-15 min y
        # la semana contaminada 2026-03-08 sin descartarlos -- ver
        # n_semanas_bordes_discrepantes). cierre_ny DEBE ir por moda igual que
        # los demas campos: con el agrupamiento canonico por DST, un periodo
        # ya no garantiza que todas sus semanas compartan el mismo cierre_ny
        # crudo (esa es justo la fragmentacion de ruido que la
        # canonicalizacion colapsa) -- tomar el valor crudo de wk0 sin moda
        # filtrarlo dejaria pasar silenciosamente el jitter/contaminacion si
        # la PRIMERA semana del periodo resulta ser una de las discrepantes
        # (p.ej. 2025-12-28, cuyo cierre_ny crudo es '02:15').
        e0["apertura_ny"] = "18:00"
        n_discrep = {}
        for campo in ("cierre_ny", "apertura_utc", "apertura_srv", "cierre_utc", "cierre_srv"):
            moda, n_disc = _moda([bordes_semana[w][campo] for w in semanas_periodo])
            e0[campo] = moda
            n_discrep[campo] = n_disc
        n_ticks_periodo = sum(bordes_semana[w]["n_ticks_semana"] for w in semanas_periodo)

        # % de acierto: entre las semanas de este periodo, cuantos ticks
        # estrechos caen DENTRO de la ventana (apertura_ny<=h o h<cierre_ny,
        # a resolucion de hora entera) frente a cuantos caen FUERA. Reusa las
        # series por bucket ya acumuladas en el reloj NY (unico reloj sobre
        # el que se define "dentro"/"fuera" de la ventana operativa).
        narrow_dentro = 0
        narrow_fuera = 0
        for w in semanas_periodo:
            buckets = acumulador["ny"].get(w, {})
            for label, (n, n_narrow) in buckets.items():
                h = int(label[:2])
                apertura_h = int(e0["apertura_ny"][:2]) if e0["apertura_ny"] else None
                cierre_h = int(e0["cierre_ny"][:2]) if e0["cierre_ny"] else None
                if apertura_h is None or cierre_h is None:
                    continue
                dentro = (h >= apertura_h) or (h < cierre_h)
                if dentro:
                    narrow_dentro += n_narrow
                else:
                    narrow_fuera += n_narrow
        total_clasificado = narrow_dentro + narrow_fuera
        pct_acierto = round(100.0 * narrow_dentro / total_clasificado, 4) if total_clasificado else None

        desde_real = fechas_semana[semanas_periodo[0]][0].isoformat()
        hasta_real = fechas_semana[semanas_periodo[-1]][1].isoformat()

        calendario_periodos.append({
            "desde": desde_real,
            "hasta": hasta_real,
            "semana_desde": semanas_periodo[0],
            "semana_hasta": semanas_periodo[-1],
            "apertura_ny": e0["apertura_ny"],
            "cierre_ny": e0["cierre_ny"],
            "apertura_utc": e0["apertura_utc"],
            "cierre_utc": e0["cierre_utc"],
            "apertura_srv": e0["apertura_srv"],
            "cierre_srv": e0["cierre_srv"],
            "n_ticks": n_ticks_periodo,
            "semanas": semanas_periodo,
            "n_semanas": len(semanas_periodo),
            "n_semanas_baja_cobertura": sum(1 for w in semanas_periodo if bordes_semana[w]["baja_cobertura"]),
            "n_semanas_bordes_discrepantes": n_discrep,
            "ticks_estrechos_dentro": narrow_dentro,
            "ticks_estrechos_fuera": narrow_fuera,
            "pct_acierto": pct_acierto,
        })

    rango_medido = {
        "desde": datetime.utcfromtimestamp(SEG1_INI).strftime("%Y-%m-%d"),
        "hasta": datetime.utcfromtimestamp(SEG2_FIN).strftime("%Y-%m-%d"),
    }

    resultado = {
        "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_sha": _git_sha(),
        "broker": BROKER,
        "substrate_id": "capitaria-ticks-2026-preholdout-y-postholdout",
        "sustrato": "data/lake_ticks/XAUUSD/ (ticks reales Capitaria)",
        "condicion_estrecho": "abs((ask-bid) - 0.5) <= 0.05  (backtest.py:358, verbatim)",
        "resolucion_borde": "15 minutos (bucket donde el % estrecho cruza 50%)",
        "tramos_medidos": [
            [datetime.utcfromtimestamp(SEG1_INI).strftime("%Y-%m-%d"), datetime.utcfromtimestamp(SEG1_FIN).strftime("%Y-%m-%d")],
            [datetime.utcfromtimestamp(SEG2_INI).strftime("%Y-%m-%d"), datetime.utcfromtimestamp(SEG2_FIN).strftime("%Y-%m-%d")],
        ],
        "holdout_excluido": [
            datetime.utcfromtimestamp(CAPITARIA_HOLDOUT_INI).strftime("%Y-%m-%d"),
            datetime.utcfromtimestamp(CAPITARIA_HOLDOUT_FIN).strftime("%Y-%m-%d"),
        ],
        "rango_medido": rango_medido,
        "umbral_min_ticks_semana": UMBRAL_MIN_TICKS_SEMANA,
        "n_ticks_totales_cargados": n_ticks_totales,
        "n_semanas_medidas": len(semanas_ordenadas),
        "n_semanas_baja_cobertura": sum(1 for e in bordes_semana.values() if e["baja_cobertura"]),
        "periodos": calendario_periodos,
        "bordes_por_semana": bordes_semana,
        "regla_extrapolacion": (
            "Para fechas anteriores a rango_medido.desde: se conserva la apertura "
            "18:00 ET (ancla de mercado) y se aplica el cierre del periodo medido "
            "mas cercano en el calendario, respetando el DST vigente en esa fecha "
            "(D-36). Aplicado por scripts/research/ventana_calendario.py, marcado "
            "via es_extrapolado()."
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, sort_keys=False, indent=2, ensure_ascii=False, allow_nan=False)

    print(f"\nn_ticks_totales_cargados: {n_ticks_totales:,}")
    print(f"n_semanas_medidas: {len(semanas_ordenadas)}  (baja_cobertura: {resultado['n_semanas_baja_cobertura']})")
    print(f"n_periodos: {len(calendario_periodos)}")
    for p in calendario_periodos:
        print(
            f"  [{p['desde']} -> {p['hasta']}] NY {p['apertura_ny']}->{p['cierre_ny']}  "
            f"UTC {p['apertura_utc']}->{p['cierre_utc']}  SRV {p['apertura_srv']}->{p['cierre_srv']}  "
            f"n_ticks={p['n_ticks']:,}  semanas={p['n_semanas']} (baja_cob={p['n_semanas_baja_cobertura']})  "
            f"pct_acierto={p['pct_acierto']}"
        )
    print(f"\nartefacto: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
