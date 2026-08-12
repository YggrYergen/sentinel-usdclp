r"""Tests de la canonicalizacion de periodos en
`scripts/research/medir_calendario_ventana.py` (D-36, Paso 2b, seguimiento).

Por que existe. El agrupamiento original agrupaba periodos por igualdad
EXACTA del `cierre_ny` medido crudo (resolucion 15 min). Eso produce 11
periodos en 7 meses de 2026 por dos motivos de ruido de medicion (no
horarios de broker reales):

1. Jitter de +-15 min: semanas sueltas miden `02:15`/`03:15` donde el valor
   estructural es `02:00`/`03:00` (p.ej. semanas `2025-12-28`, `2026-02-22`,
   `2026-04-26`, `2026-05-03`, `2026-05-10`, `2026-07-26`, `2026-08-09`).
2. Una semana con medicion contaminada: `2026-03-08` (semana del cambio de
   horario de EEUU) mide `03:00` aislada entre periodos que miden `02:00` a
   ambos lados.

La senal estructural real de `cierre_ny` es el horario de verano de CHILE
(huso del servidor, `SERVER_TZ`): `02:00` mientras esta vigente, `03:00`
cuando no. Pero agrupar SOLO por Chile no basta: la PROYECCION de ese cierre
sobre UTC y hora de servidor tambien depende del horario de verano de NUEVA
YORK (que cambia en fecha distinta a la de Chile) -- agrupar solo por Chile
mezclaria, dentro de un mismo periodo, semanas cuyo `cierre_utc`/`cierre_srv`
real son distintos, y la moda publicaria un valor falso para parte del
periodo. La clave canonica es por tanto la TUPLA `(verano_chile, verano_ny)`.

Este fichero prueba las funciones puras que implementan esa
canonicalizacion: `_es_horario_verano` / `es_verano_chile` / `es_verano_ny`
(derivadas de `utcoffset()` via `zoneinfo`, NUNCA de una fecha de transicion
hardcodeada), `_clave_canonica_cierre` (la tupla) y `_agrupar_semanas_canonico`
(el agrupamiento de semanas contiguas que usa esa tupla en vez de la
igualdad exacta del valor medido crudo).

`bordes_por_semana` (el registro crudo semana a semana) NO se toca por esta
canonicalizacion -- no hay test aqui que lo ejercite, adrede.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from scripts.research.medir_calendario_ventana import (
    _agrupar_semanas_canonico,
    _clave_canonica_cierre,
    _moda,
    es_verano_chile,
    es_verano_ny,
    NY_TZ,
    SERVER_TZ,
)


# --------------------------------------------------------- es_verano_chile
class TestEsVeranoChile:
    def test_semana_2026_03_08_esta_en_verano(self):
        """La semana del cambio de horario de EEUU (medicion contaminada,
        ver D-34) cae ANTES de la transicion de Chile: debe seguir
        canonicalizada como 'verano', igual que sus vecinas."""
        assert es_verano_chile(date(2026, 3, 8), SERVER_TZ) is True

    def test_dia_04_04_2026_aun_es_verano(self):
        assert es_verano_chile(date(2026, 4, 4), SERVER_TZ) is True

    def test_dia_04_05_2026_ya_no_es_verano(self):
        """La transicion real de Chile ocurre la madrugada del 4->5 de abril
        de 2026 (docstring de ny_window.py: '-3 el 2026-04-04, -4 el
        2026-04-06'); a mediodia del 5 de abril ya rige horario estandar."""
        assert es_verano_chile(date(2026, 4, 5), SERVER_TZ) is False

    def test_enero_es_verano_julio_no(self):
        """Chile es hemisferio SUR: el estandar (invierno austral) cae en
        julio, el verano en enero."""
        assert es_verano_chile(date(2026, 1, 15), SERVER_TZ) is True
        assert es_verano_chile(date(2026, 7, 15), SERVER_TZ) is False

    def test_no_depende_de_una_fecha_hardcodeada_generaliza_a_otro_anio(self):
        """La frontera se deriva de SERVER_TZ.utcoffset(), no de una fecha
        literal -- debe seguir distinguiendo verano/invierno en un ano
        distinto de 2026 sin que el codigo de produccion mencione ese ano."""
        assert es_verano_chile(date(2027, 1, 15), SERVER_TZ) is True
        assert es_verano_chile(date(2027, 7, 15), SERVER_TZ) is False

    def test_offset_verano_es_mas_adelantado_que_invierno(self):
        """Verificacion cruzada directa contra zoneinfo: en la fecha que
        es_verano_chile marca True, el offset UTC debe ser MAYOR (mas
        adelantado, hora de verano) que en la fecha que marca False."""
        tz = SERVER_TZ
        off_verano = tz.utcoffset(datetime(2026, 1, 15, 12))
        off_invierno = tz.utcoffset(datetime(2026, 7, 15, 12))
        assert off_verano > off_invierno


# ------------------------------------------------------------- es_verano_ny
class TestEsVeranoNy:
    """Nueva York es hemisferio NORTE: al reves que Chile, el estandar
    (invierno boreal) cae en ENERO y el verano (DST, EDT) en JULIO. No se da
    por hecho que `_es_horario_verano` generalice correctamente al
    hemisferio opuesto -- se verifica aqui explicitamente (pedido explicito
    del controlador: 'verificalo con un test explicito para NY')."""

    def test_enero_es_invierno_estandar_julio_es_verano(self):
        assert es_verano_ny(date(2026, 1, 15), NY_TZ) is False
        assert es_verano_ny(date(2026, 7, 15), NY_TZ) is True

    def test_offset_verano_ny_es_mas_adelantado_que_invierno(self):
        """Misma verificacion cruzada que para Chile, pero en el hemisferio
        opuesto: el offset de julio (verano NY) debe ser MAYOR que el de
        enero (invierno NY) -- confirma que `min(offset_ene, offset_jul)`
        sigue siendo el offset ESTANDAR aunque aqui el estandar sea enero,
        no julio como en Chile."""
        off_invierno = NY_TZ.utcoffset(datetime(2026, 1, 15, 12))
        off_verano = NY_TZ.utcoffset(datetime(2026, 7, 15, 12))
        assert off_verano > off_invierno

    def test_transicion_2026_marzo_segundo_domingo(self):
        """La semana `2026-03-01` (domingo 1 de marzo) mide aun invierno
        estandar en NY; la semana `2026-03-08` (domingo 8 de marzo, dia de
        la transicion de EEUU) ya mide DST -- coincide con el momento en
        que las series crudas de cierre_utc/cierre_srv cambian de valor
        (ver docstring del modulo, semanas 2026-03-15/22/29 vs anteriores)."""
        assert es_verano_ny(date(2026, 3, 1), NY_TZ) is False
        assert es_verano_ny(date(2026, 3, 8), NY_TZ) is True

    def test_transicion_de_otono_primer_domingo_de_noviembre(self):
        assert es_verano_ny(date(2026, 10, 25), NY_TZ) is True
        assert es_verano_ny(date(2026, 11, 2), NY_TZ) is False

    def test_no_depende_de_una_fecha_hardcodeada_generaliza_a_otro_anio(self):
        assert es_verano_ny(date(2027, 1, 15), NY_TZ) is False
        assert es_verano_ny(date(2027, 7, 15), NY_TZ) is True


# --------------------------------------------------------- _clave_canonica_cierre
class TestClaveCanonicaCierre:
    def test_es_tupla_chile_ny(self):
        assert _clave_canonica_cierre(date(2026, 1, 15)) == (True, False)  # verano chile, invierno ny
        assert _clave_canonica_cierre(date(2026, 3, 8)) == (True, True)    # verano chile, ya verano ny
        assert _clave_canonica_cierre(date(2026, 4, 5)) == (False, True)   # ya invierno chile, verano ny

    def test_distingue_semanas_que_es_verano_chile_solo_confundiria(self):
        """`2026-01-15` y `2026-03-08` son AMBAS 'verano de Chile' (misma
        clave con la canonicalizacion antigua de un solo componente), pero
        difieren en NY -- la tupla las distingue; una clave de un solo
        componente (solo Chile) las habria fusionado incorrectamente."""
        assert es_verano_chile(date(2026, 1, 15), SERVER_TZ) == es_verano_chile(date(2026, 3, 8), SERVER_TZ)
        assert _clave_canonica_cierre(date(2026, 1, 15)) != _clave_canonica_cierre(date(2026, 3, 8))


# --------------------------------------------------- _agrupar_semanas_canonico
class TestAgruparSemanasCanonico:
    def test_semanas_contiguas_mismo_dst_se_fusionan(self):
        semanas = ["2026-01-04", "2026-01-11", "2026-01-18"]
        assert _agrupar_semanas_canonico(semanas) == [semanas]

    def test_semana_contaminada_2026_03_08_no_fragmenta_el_periodo(self):
        """Reproduce el fenomeno D-34: 2026-03-08 mide cierre_ny=03:00 en
        crudo (ver bordes_por_semana en el JSON), pero esta rodeada de
        semanas con su misma clave canonica (verano chile, verano ny ya
        vigente) -- la canonicalizacion por DST (no por el valor medido)
        debe mantenerla en el mismo grupo que sus vecinas."""
        semanas = ["2026-03-08", "2026-03-15", "2026-03-22"]
        assert _agrupar_semanas_canonico(semanas) == [semanas]

    def test_cambio_de_dst_chile_fragmenta_el_periodo(self):
        antes = ["2026-03-29"]  # verano chile, verano ny
        despues = ["2026-04-05"]  # invierno chile, verano ny -- cambia solo Chile
        assert _agrupar_semanas_canonico(antes + despues) == [antes, despues]

    def test_cambio_de_dst_ny_fragmenta_el_periodo_aunque_chile_no_cambie(self):
        """Es EXACTAMENTE el caso que la clave de un solo componente (solo
        Chile) se perdia: `2026-03-01` y `2026-03-08` son ambas 'verano de
        Chile', pero NY cambia de estandar a DST entre esas dos semanas --
        deben quedar en periodos distintos."""
        antes = ["2026-03-01"]  # verano chile, invierno ny
        despues = ["2026-03-08"]  # verano chile, ya verano ny
        assert es_verano_chile(date(2026, 3, 1), SERVER_TZ) == es_verano_chile(date(2026, 3, 8), SERVER_TZ)
        assert _agrupar_semanas_canonico(antes + despues) == [antes, despues]

    def test_hueco_de_calendario_fragmenta_aunque_misma_clave(self):
        """El holdout sellado de Capitaria rompe la contigüidad semanal: dos
        semanas con la MISMA clave canonica pero separadas por mas de 7 dias
        deben quedar en periodos distintos (no se afirma continuidad sobre
        territorio no medido)."""
        semanas = ["2026-05-10", "2026-07-26"]  # misma clave (invierno chile, verano ny), pero separadas >7d
        assert _clave_canonica_cierre(date(2026, 5, 10)) == _clave_canonica_cierre(date(2026, 7, 26))
        assert _agrupar_semanas_canonico(semanas) == [["2026-05-10"], ["2026-07-26"]]

    def test_lista_vacia(self):
        assert _agrupar_semanas_canonico([]) == []

    def test_semana_unica(self):
        assert _agrupar_semanas_canonico(["2026-06-01"]) == [["2026-06-01"]]

    def test_calendario_real_2026_colapsa_a_cuatro_periodos(self):
        """Fixture literal del calendario semanal real medido (ver
        bordes_por_semana en el JSON, 2025-12-28 -> 2026-08-09): con la
        canonicalizacion por tupla (Chile, NY), las 23 semanas medidas
        colapsan a 4 periodos, no 3:

        - verano chile / invierno ny: 2025-12-28 -> 2026-03-01 (10 semanas)
        - verano chile / verano ny:   2026-03-08 -> 2026-03-29 (4 semanas)
        - invierno chile / verano ny (pre-holdout): 2026-04-05 -> 2026-05-10 (6 semanas)
        - invierno chile / verano ny (post-holdout): 2026-07-26 -> 2026-08-09 (3 semanas)

        El corte extra frente a la version de un solo componente (Chile)
        NO es ruido: separa semanas cuya PROYECCION a UTC/servidor es
        realmente distinta (DST de EEUU cambia el 2026-03-08, DST de Chile
        cambia el 2026-04-05 -- fechas distintas). El hueco del holdout
        sigue fragmentando el tramo invierno/verano-ny en dos periodos
        (pre y post-holdout) igual que antes."""
        semanas = [
            "2025-12-28", "2026-01-04", "2026-01-11", "2026-01-18", "2026-01-25",
            "2026-02-01", "2026-02-08", "2026-02-15", "2026-02-22", "2026-03-01",
            "2026-03-08", "2026-03-15", "2026-03-22", "2026-03-29",
            "2026-04-05", "2026-04-12", "2026-04-19", "2026-04-26", "2026-05-03", "2026-05-10",
            "2026-07-26", "2026-08-02", "2026-08-09",
        ]
        grupos = _agrupar_semanas_canonico(semanas)
        assert [len(g) for g in grupos] == [10, 4, 6, 3]
        assert grupos[0][0] == "2025-12-28" and grupos[0][-1] == "2026-03-01"
        assert grupos[1][0] == "2026-03-08" and grupos[1][-1] == "2026-03-29"
        assert grupos[2][0] == "2026-04-05" and grupos[2][-1] == "2026-05-10"
        assert grupos[3][0] == "2026-07-26" and grupos[3][-1] == "2026-08-09"


# ------------------------------------------------------------------- _moda
class TestModaCollapsaElJitter:
    """`_moda` ya existia (usada para apertura_utc/srv y cierre_utc/srv, y
    ahora tambien cierre_ny); estos tests documentan que, combinada con el
    agrupamiento canonico de arriba, colapsa el jitter de +-15 min y la
    semana contaminada DENTRO de cada uno de los grupos reales -- sin
    necesidad de tocar ni parquet ni bordes_por_semana."""

    def test_moda_grupo1_verano_chile_invierno_ny_10_semanas(self):
        # cierre_ny crudo de las 10 semanas de ese grupo real, en orden
        valores = [
            "02:15",  # 2025-12-28 (baja cobertura, jitter)
            "02:00", "02:00", "02:00", "02:00", "02:00", "02:00", "02:00",  # ene-feb
            "02:15",  # 2026-02-22 (jitter)
            "02:00",  # 2026-03-01
        ]
        moda, n_discrepantes = _moda(valores)
        assert moda == "02:00"
        assert n_discrepantes == 2

    def test_moda_grupo2_verano_chile_verano_ny_4_semanas_absorbe_semana_contaminada(self):
        # cierre_ny crudo de las 4 semanas de ese grupo real, en orden
        valores = ["03:00", "02:00", "02:00", "02:00"]  # 03-08 (contaminada), 03-15, 03-22, 03-29
        moda, n_discrepantes = _moda(valores)
        assert moda == "02:00"
        assert n_discrepantes == 1

    def test_moda_grupo3_invierno_chile_pre_holdout_empate_desempata_a_hora_en_punto(self):
        """Caso real medido: el grupo `2026-04-05 -> 2026-05-10` (6 semanas)
        parte EXACTO 3-3 entre `03:00` y `03:15`. Sin desempate dedicado, el
        criterio alfabetico habria elegido '03:15' (jitter) sobre '03:00'
        (borde real) -- el desempate por hora-en-punto debe evitarlo."""
        valores = ["03:00", "03:00", "03:00", "03:15", "03:15", "03:15"]
        moda, n_discrepantes = _moda(valores)
        assert moda == "03:00"
        assert n_discrepantes == 3

    def test_moda_grupo4_invierno_chile_post_holdout_3_semanas(self):
        valores = ["03:15", "03:00", "03:15"]  # 07-26, 08-02, 08-09
        moda, n_discrepantes = _moda(valores)
        assert moda == "03:15"
        assert n_discrepantes == 1

    def test_moda_desempate_solo_aplica_si_hay_empate_de_conteo(self):
        """Si NO hay empate, gana el conteo mayor aunque no este alineado a
        la hora en punto -- el desempate no debe distorsionar el caso
        normal (mayoria clara)."""
        valores = ["03:15", "03:15", "03:15", "03:15", "03:00"]
        moda, n_discrepantes = _moda(valores)
        assert moda == "03:15"
        assert n_discrepantes == 1
