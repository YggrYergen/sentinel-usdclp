# Viabilidad de datos para backtest largo de XAUUSD (~2 anos objetivo)

Fecha: 2026-07-27
Tipo: informe de medicion, NO de decision. Ejecutor: Sonnet 5 (solo mide y reporta,
cero interpretacion de negocio, cero recomendaciones). El analisis/decision es
responsabilidad de otra etapa (Opus / usuario).

Metodo: scripts Python efimeros (pandas/numpy) en el scratchpad de sesion, lectura
directa de parquet/CSV. Ningun fichero de codigo, `sentinel_engine/**`, `scripts/**`
ni `data/**` fue modificado. No se lanzo ningun terminal MT5 (ni MT5_Portable ni
MT5_Tester/MT5_Tester_2); toda la evidencia sobre `MT5_Tester/**` es lectura de
ficheros en disco unicamente. No se ejecuto `scripts/analysis/realtick_bt/backtest.py`.
Todos los timestamps de ticks se decodifican con la equivalencia de
`datetime.utcfromtimestamp(epoch_seconds)` (para vectorizar, `pd.to_datetime(t, unit="s")`
sin timezone, que es aritmeticamente identico elemento a elemento) -- CERO conversion de
zona horaria; el epoch ya viene en hora de servidor Capitaria.

---

## Resumen de las 3 cifras clave

| Pregunta | Cifra medida |
|---|---|
| Barras M15 de XAUUSD: hasta donde llegan hacia atras (verificado, continuo) | **2022-03-31 05:15** (server time) -> 2026-07-27 03:15. 101,233 barras. |
| Ticks reales (bid+ask) de XAUUSD: rango exacto | **2026-01-01 20:00:00.699** -> **2026-07-24 16:54:59.898** (server time). 52,599,197 ticks. |
| Fraccion de tiempo total con spread <= 0.55, sobre los ticks reales | **37.76%** del tiempo medido (metodo time-weighted, ver Seccion 3). Version no ponderada por tiempo (fraccion de ticks, no de tiempo): 33.42%. |

---

## 1. Inventario de ticks (`data/lake_ticks/XAUUSD/`)

Ficheros presentes: `202601.parquet` .. `202607.parquet` (7 meses) + `_bars_M15.parquet`
(barras M15 derivadas de estos mismos ticks, no una fuente independiente).

| Fichero | Ticks | Primer timestamp (server time) | Ultimo timestamp (server time) |
|---|---:|---|---|
| 202601.parquet | 4,302,411 | 2026-01-01 20:00:00.699 | 2026-01-30 17:54:59.918 |
| 202602.parquet | 4,019,668 | 2026-02-01 20:00:11.640 | 2026-02-27 17:54:59.697 |
| 202603.parquet | 7,337,404 | 2026-03-01 20:00:12.273 | 2026-04-01 02:59:59.900 |
| 202604.parquet | 9,740,413 | 2026-04-01 03:00:00.280 | 2026-05-01 03:59:59.979 |
| 202605.parquet | 8,621,130 | 2026-05-01 04:00:00.146 | 2026-06-01 03:59:59.946 |
| 202606.parquet | 10,307,815 | 2026-06-01 04:00:00.016 | 2026-07-01 03:59:59.953 |
| 202607.parquet | 8,270,356 | 2026-07-01 04:00:00.171 | 2026-07-24 16:54:59.898 |
| **TOTAL** | **52,599,197** | **2026-01-01 20:00:00.699** | **2026-07-24 16:54:59.898** |

Cobertura real: **~7 meses y 3 semanas** (205 dias corridos), no ~2 anos.

`_bars_M15.parquet` (M15 construido a partir de estos mismos ticks, columnas `t,o,h,l,c,v`):
13,236 filas, rango 2026-01-01 20:00:00 -> 2026-07-24 16:45:00 -- coincide exactamente
con el rango de ticks (es un derivado, no aporta historia adicional).

Esquema de los parquet de ticks: columnas `t_msc` (epoch milisegundos, int64), `bid`
(float64), `ask` (float64). No incluyen volumen ni flags de tick.

---

## 2. Inventario de BARRAS (la pregunta central)

### 2.1 Monolito `data/lake/XAUUSD/<tf_minutos>.parquet` (fuente primaria, MT5_Portable en vivo)

| TF | Fichero | Filas | Rango (UTC, indice del parquet) | Huecos >1.5x TF | de los cuales tipo fin-de-semana (>24h) | Hueco maximo |
|---|---|---:|---|---:|---:|---|
| M1 | 1.parquet | 117,780 | 2026-03-25 19:16 -> 2026-07-27 03:25 | 88 | 18 | 72.0 h |
| M2 | 2.parquet | 109,218 | 2025-12-10 09:08 -> 2026-07-27 03:24 | 161 | 35 | 72.0 h |
| M5 | 5.parquet | 103,696 | 2025-02-04 23:15 -> 2026-07-27 03:25 | 381 | 79 | 73.1 h |
| **M15** | **15.parquet** | **101,233** | **2022-03-31 05:15 -> 2026-07-27 03:15** | 1,121 | 230 | 76.2 h |
| H1 | 60.parquet | 26,766 | 2022-01-02 20:00 -> 2026-07-27 03:00 | 1,179 | 242 | 77.0 h |
| D1 | 1440.parquet | 1,504 | 2021-09-24 00:00 -> 2026-07-26 00:00 | 253 | 253 (100%) | 72.0 h |

Los "huecos no-fin-de-semana" (M15: 891, H1: 937) son consistentes con un corte diario
recurrente (ver Seccion 3, "hora muerta" diaria del servidor) y no muestran ninguna
anomalia aislada mayor al hueco de fin de semana mas largo (~76-77h, un feriado largo).
D1 solo tiene huecos de fin de semana (0 "otros"), como cabe esperar de una barra diaria.

Las carpetas mensuales `data/lake/XAUUSD/<TF>/YYYY-MM.parquet` (M1/M2/M5/M15/H1/D) son un
**resampleo/reformateo** del mismo monolito (`sentinel_engine/lake/tiers.py`), no una fuente
independiente; sus rangos coinciden exactamente con la tabla anterior.

**Cifra central: M15 tiene 101,233 barras continuas desde 2022-03-31 hasta hoy (~4.32
anos), ya MAS que el objetivo de ~2 anos del usuario -- en terminos de precio OHLC.
Esto NO implica que haya spread real para ese periodo (ver Seccion 2.3 y Seccion 5): son
barras de precio, no de bid/ask.**

### 2.2 Procedencia de ese limite 2022-03-31 (no es un limite arbitrario del script)

`scripts/mt5_dump_history.py` (commit `828c39c`, ejecutado una vez el 2026-07-15) define
`START_BOUND = datetime(2022, 1, 1, tzinfo=timezone.utc)` y pagina hacia atras en bloques
de 20,000 barras (`copy_rates_from`) hasta alcanzar ese limite o hasta que el terminal deje
de retroceder (`earliest >= prev_earliest`, es decir, fin real de historia servida). Con
CHUNK=20000 barras y TF=M15, cada llamada cubre ~208 dias; en 8 iteraciones se habria
alcanzado 2022-01-01 sobradamente dentro del limite de 400 iteraciones del script. El hecho
de que M15 se detenga en 2022-03-31 (91 dias despues del `START_BOUND` pedido) en vez de en
2022-01-01 indica que la condicion de parada real fue "fin de historia servida por
Capitaria para M15", no el techo del script. H1 y D1 si llegaron mas atras (2022-01-02 y
2021-09-24 respectivamente) porque una barra mas gruesa consume menos "profundidad de
almacenamiento" del broker por llamada. El mensaje del commit original lo confirma
textualmente: *"D1/H1 mostly back to 2022, M1 ~3.5mo (terminal retention)"*.

`scripts/live/run_bars_ingester.py` (el daemon incremental que corre desde 2026-07-21) NUNCA
re-pagina hacia atras -- solo agrega la cola reciente (`copy_rates_from_pos`, `tail_bars=1500`).
Es decir: **el piso 2022-03-31 (M15) fue fijado una sola vez y nunca se ha vuelto a intentar
extender hacia atras** con el terminal en vivo.

### 2.3 El backfill de enero-marzo 2026 ya documenta el limite de M1 y el patron de exito/fallo por TF

Existe un intento YA EJECUTADO (no hipotetico) de extraer mas historia usando el terminal
`MT5_Tester` en vez de `MT5_Portable`: `scripts/mt5_dump_xauusd_early2026.py`, motivado por
`docs/superpowers/specs/2026-07-10-xauusd-history-feasibility.md`. Resultado verificado en
disco (`data/raw/XAUUSD/*_early2026.csv`):

| TF | Resultado | Rango obtenido |
|---|---|---|
| M1 | **VACIO** (no se genero CSV) | -- |
| M2 | OK, 40,367 filas | 2026-01-01 20:00 -> 2026-03-26 00:00 |
| M5 | OK, 16,145 filas | 2026-01-01 20:00 -> 2026-03-26 00:00 |
| M15 | OK, 5,387 filas | 2026-01-01 20:00 -> 2026-03-26 00:00 |
| H1 | OK, 1,348 filas | 2026-01-01 20:00 -> 2026-03-26 00:00 |

Este es el UNICO caso documentado en el repo de intentar leer el cache historico de
`MT5_Tester` (en vez del terminal en vivo). Confirma dos cosas relevantes para la pregunta
central: (a) el cache de `MT5_Tester` SI pudo servir M2/M5/M15/H1 para una ventana que el
terminal en vivo ya no serv�a (M1 en el lake solo llegaba a 2026-03-25); (b) para esa misma
ventana, **M1 fallo incluso desde el cache del Tester** -- la sola presencia de un fichero
`.hcc` grande no garantiza que `copy_rates_range` pueda extraer esa granularidad.

### 2.4 Caches binarios bajo `MT5_Tester/**` y `MT5_Tester_2/**` (solo lectura, NO se lanzo ningun terminal)

Estructura estandar de MT5 (`Bases/<server>/history/<symbol>/<year>.hcc` +
`Bases/<server>/history/<symbol>/cache/<TF>.hc` + `Bases/<server>/ticks/<symbol>/<YYYYMM>.tkc`).
Formato binario propietario de MetaQuotes, no documentado publicamente; **no se decodifico**
(ni se intento) -- solo se midieron tamanos de fichero:

| Anio | `MT5_Tester/.../history/XAUUSD/<anio>.hcc` | `MT5_Tester_2` (misma ruta) |
|---|---:|---:|
| 2014 | 84,366 B | 84,366 B |
| 2015 | 92,085 B | 92,085 B |
| 2016 | 92,334 B | 92,334 B |
| 2017 | 91,836 B | 91,836 B |
| 2018 | 118,083 B | 118,083 B |
| 2019 | 15,379,743 B | 15,379,743 B |
| 2020 | 20,962,383 B | 20,962,383 B |
| 2021 | 20,958,720 B | 20,958,720 B |
| 2022 | 21,105,294 B | 21,105,294 B |
| 2023 | 21,043,845 B | 21,043,845 B |
| 2024 | 21,190,521 B | 21,190,521 B |
| 2025 | 21,214,692 B | 21,214,692 B |
| 2026 | 11,595,126 B | 11,593,557 B |

`cache/` (formato construido, un fichero por TF, sin particion anual): `Daily.hc` 300,608 B,
`H1.hc` 2,824,148 B, `M1.hc` 6,071,480 B, `M15.hc` 185,822 B, `M2.hc` 250,802 B, `M5.hc`
6,069,848 B. `ticks/XAUUSD/`: `202601.tkc` .. `202607.tkc` (7 ficheros, 7.4-58 MB cada uno) +
`ticks.dat` (123,312 B). Existe tambien un backup manual
`history/XAUUSD_backup_20260710` y `ticks/XAUUSD_backup_20260710` (copias identicas, mismos
tamanos), y en `MT5_Tester_2/Tester/bases/.../history/XAUUSD` (ruta distinta, propia del motor
de Strategy Tester) solo `2025.hcs` / `2026.hcs`.

**Lectura de esta evidencia, explicitamente como senal indirecta, no como medicion
confirmada de contenido:** el salto de tamano entre 2014-2018 (~85-118 KB, sugestivo de
placeholder/pocos datos) y 2019-2026 (~11-21 MB, orden de magnitud consistente con un anio
de M1 real) es **sugestivo pero NO probado** -- la Seccion 2.3 ya muestra un caso real donde
un `.hcc` de tamano grande (2026, 11.6 MB) NO produjo M1 al pedirselo via API para una
ventana especifica dentro de ese mismo anio. Extrapolar "2019.hcc pesa 15MB -> tiene M1 real
de 2019" **no esta verificado** y esta clasificado como **NO EVALUABLE sin abrir un terminal
MT5 contra ese `Bases/` y ejecutar `copy_rates_range`** -- accion expresamente prohibida en
esta tarea ("NO lances terminales"). Lo unico verificado con ejecucion real es la ventana
2026-01-01/2026-03-26 (Seccion 2.3).

### 2.5 Otras fuentes de barras en el repo

- `sentinel_engine/lake/ingest_dukascopy.py`: adaptador YA ESCRITO para CSV de Dukascopy
  (formato `Gmt time,Open,High,Low,Close,Volume`), pero el propio docstring declara:
  *"NEEDS REAL-SAMPLE VALIDATION: no real Dukascopy historical-data export exists in this
  repo"* -- solo probado contra un fixture sintetico (`tests/lake/fixtures/dukascopy_sample.csv`).
  **No hay ningun dato real de Dukascopy en el repo.** Este adaptador solo mapea columnas
  OHLCV; no lee ni bid ni ask aunque el export de Dukascopy los tenga (ver Seccion 4).
- No se encontro ningun otro parquet/CSV de barras XAUUSD en el repo fuera de
  `data/lake/XAUUSD/**` y `data/raw/XAUUSD/**` (busqueda exhaustiva por nombre de fichero y
  contenido de directorio).

---

## 3. Estructura del spread sobre los 52,599,197 ticks reales

### 3.1 Metodologia (para que los numeros sean reproducibles)

"Fraccion de tiempo" != "fraccion de ticks": se calculo el tiempo de vida de cada tick
(`dt = t[i+1] - t[i]`, en segundos) **capado a un maximo de 60s** para que un hueco de
mercado cerrado (fin de semana, ~65h) no se le asigne integramente al ultimo tick antes del
cierre. Con ese `dt` capado, se suma el tiempo en que `spread <= 0.55` y se divide por el
tiempo total medido, por bucket (hora de servidor 0-23) x (dia de semana, lunes=0). Se
reporta tambien la version simple no ponderada (fraccion de ticks que cumplen el gate) como
comparacion. El hueco capado descarta implicitamente el tiempo de mercado cerrado del
denominador (no hay ticks ahi, luego no aporta "tiempo medido").

### 3.2 Histograma de spread (`ask - bid`)

El spread **no es continuo**: se concentra en 3 valores discretos (bins de 0.01):

| Bin | Ticks | % del total |
|---|---:|---:|
| [0.49, 0.50) | 1,780 | 0.003% |
| **[0.50, 0.51)** | **17,579,207** | **33.421%** |
| [0.56, 0.57) .. [0.58,0.59) | 0 | 0.000% |
| [0.59, 0.60) | 16,174,443 | 30.750% |
| [0.60, 0.61) | 18,843,767 | 35.825% |
| resto de bins (0.00-0.49, 0.51-0.56, 0.61-3.00) | 0 | 0.000% |

Es decir: **spread=0.50 en 33.42% de los ticks, spread~0.60 (bins 0.59+0.60, artefacto de
redondeo de punto flotante entre si) en 66.58% de los ticks**, y absolutamente nada entre
medias ni fuera de ese rango. Esto confirma cuantitativamente el patron bimodal 0.50/0.60 ya
conocido cualitativamente.

### 3.3 Fraccion de tiempo con spread <= 0.55

- **Time-weighted (metodo de la Seccion 3.1): 37.76%** del tiempo medido.
- Tick-count fraction (naive, sin ponderar por tiempo): 33.42% (identico al bin [0.50,0.51)
  del histograma, como cabe esperar ya que no hay valores entre 0.51 y 0.55).
- La diferencia (37.76% vs 33.42%) indica que, en promedio, los periodos de spread=0.50
  tienen una tasa de llegada de ticks ligeramente MENOR que los periodos de spread=0.60 (si
  no, ambas fracciones coincidirian).

### 3.4 Tabla completa hora (servidor) x dia de semana -- fraccion de tiempo con spread<=0.55

**ADVERTENCIA METODOLOGICA (ver 3.6): esta tabla agrupa los 7 meses en un solo eje de
"hora de servidor 0-23", pero se detecto empiricamente un corrimiento tipo-DST de esa hora
dentro del propio periodo (Seccion 3.6). Esta tabla es un promedio borroso de al menos 2
regimenes distintos; las tablas por regimen (3.6) son la referencia mas limpia.**

| hora | Lun | Mar | Mie | Jue | Vie | Sab | Dom |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.931 | 1.000 | 1.000 | 1.000 | 1.000 | - | - |
| 1 | 0.931 | 1.000 | 1.000 | 1.000 | 1.000 | - | - |
| 2 | 0.929 | 0.995 | 0.998 | 1.000 | 1.000 | - | - |
| 3 | 0.409 | 0.399 | 0.490 | 0.404 | 0.441 | - | - |
| 4 | 0.049 | 0.045 | 0.077 | 0.067 | 0.029 | - | - |
| 5 | 0.000 | 0.034 | 0.043 | 0.034 | 0.000 | - | - |
| 6 | 0.000 | 0.024 | 0.034 | 0.034 | 0.000 | - | - |
| 7 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 8 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 9 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 10 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 11 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 12 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 13 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 14 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 15 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 16 | 0.000 | 0.000 | 0.034 | 0.034 | 0.000 | - | - |
| 17 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | - | - |
| 18 | 0.663 | 0.498 | 0.570 | 0.589 | - | - | 0.683 |
| 19 | 0.983 | 0.895 | 0.945 | 0.993 | - | - | 0.891 |
| 20 | 0.946 | 0.952 | 0.991 | 1.000 | - | - | 0.894 |
| 21 | 0.966 | 0.966 | 1.000 | 1.000 | - | - | 0.931 |
| 22 | 0.966 | 0.981 | 1.000 | 1.000 | - | - | 0.931 |
| 23 | 0.974 | 1.000 | 1.000 | 1.000 | - | - | 0.931 |

("-" = sin ticks medidos en ese bucket: mercado cerrado sabado completo, y domingo/viernes
parcial por apertura/cierre semanal.)

Sanity check -- horas de tiempo medido por bucket (deberia ser ~29h, una por cada semana del
periodo de 7 meses, salvo bordes de semana/dia de cierre):

| hora | Lun | Mar | Mie | Jue | Vie | Sab | Dom |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 11.0 | 13.0 | 13.0 | 13.0 | 12.1 | 0.0 | 0.0 |
| 18 | 23.1 | 25.1 | 25.1 | 25.1 | 0.0 | 0.0 | 16.0 |
| resto de horas | ~26-29 (normal) | | | | | | |

La hora 17 tiene sistematicamente ~11-13h de las ~29 esperadas -> corte diario recurrente
("hora muerta") de mantenimiento/rollover, ver 3.6.

### 3.5 Estabilidad mes a mes

| Mes | Fraccion de tiempo spread<=0.55 |
|---|---:|
| 2026-01 | 0.3531 |
| 2026-02 | 0.3622 |
| 2026-03 | 0.3243 |
| 2026-04 | 0.4181 |
| 2026-05 | 0.3933 |
| 2026-06 | 0.3887 |
| 2026-07 | 0.4102 |

Rango: 32.43% (marzo, minimo) a 41.81% (abril, maximo) -- **9.38 puntos porcentuales de
variacion** entre el mes mas bajo y el mas alto dentro de la misma muestra de 7 meses.
Correlacion de cada perfil mensual hora x dia contra el perfil global agrupado: 0.934-0.982
(alta), con diferencia absoluta maxima por celda de 0.34-0.66 (los meses de mayor diferencia,
enero-marzo, son justo los que preceden al corrimiento tipo-DST detectado en 3.6; los meses
posteriores, abril-julio, tienen menor diferencia maxima entre si, 0.34-0.44).

### 3.6 Hallazgo: la "hora de servidor" no es estable en si misma dentro del periodo medido

Se detecto, buscando la hora con recuento de ticks casi nulo en dias laborables (proxy de un
corte diario de mantenimiento/rollover), que esa hora **se desplaza dos veces** dentro de los
7 meses:

| Periodo | Hora "muerta" (servidor) |
|---|---:|
| 2026-01-01 .. 2026-03-06 (aprox.) | 19 |
| 2026-03-09 .. 2026-04-02 (aprox.) | 18 |
| 2026-04-06 en adelante (hasta fin de datos, 2026-07-24) | 17 |

Transiciones localizadas por dia exacto (recuento de ticks por hora, dias laborables):
la hora 19 pasa a hora 18 entre **2026-03-05 (jue) y 2026-03-09 (lun)**; la hora 18 pasa a
hora 17 entre **2026-04-02 (jue) y 2026-04-06 (lun)**. Dos corrimientos de 1 hora cada uno,
separados por ~4 semanas, ambos "hacia atras" (la hora muerta ocurre cada vez mas temprano en
el reloj de servidor). Esto es un hecho medido directamente sobre los ticks, no una
inferencia externa; una causa plausible (no verificada, solo consistente con las fechas) es
que el cierre diario este anclado a una hora fija de un mercado de referencia (p.ej. NY) que
cambia de horario de verano una vez, mientras el propio reloj del servidor del broker
tambien tiene su propio cambio de horario en fecha distinta -- pero la causa exacta **no es
evaluable** con los datos disponibles; lo unico verificado es el corrimiento en si.

Consecuencia directa para cualquier uso de "hora de servidor" como mascara temporal fija
(ver Seccion 5): **la tabla 3.4, al agrupar los 7 meses en un solo eje de horas 0-23, mezcla
al menos 2 regimenes con la ventana desplazada 1-2 horas entre si.** Las tablas por regimen
(abajo) son la referencia mas limpia.

**REGIMEN A (enero-febrero, hora muerta=19)** -- fraccion global spread<=0.55: 0.3576

| hora | Lun | Mar | Mie | Jue | Vie | Dom |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0.931 | 0.967 | 0.989 | 0.999 | - | 0.877 |
| 21 | 1.000 | 1.000 | 1.000 | 1.000 | - | 1.000 |
| 22 | 1.000 | 1.000 | 1.000 | 1.000 | - | 1.000 |
| 23 | 1.000 | 1.000 | 1.000 | 1.000 | - | 1.000 |
| 0-2 | 1.000 (todas) | | | | | |
| 3 | 0.998 | 0.970 | 0.982 | 1.000 | 0.980 | - |
| 4-18 | <=0.16 (practicamente sin ventana 0.5), hora 19 sin datos | | | | | |

**REGIMEN B (abril-julio, hora muerta=17)** -- fraccion global spread<=0.55: 0.4021

| hora | Lun | Mar | Mie | Jue | Vie | Dom |
|---:|---:|---:|---:|---:|---:|---:|
| 18 | 0.957 | 0.782 | 0.896 | 0.925 | - | 0.683 |
| 19 | 1.000 | 0.887 | 1.000 | 1.000 | - | 0.928 |
| 20 | 1.000 | 0.938 | 1.000 | 1.000 | - | 0.994 |
| 21 | 1.000 | 0.938 | 1.000 | 1.000 | - | 1.000 |
| 22 | 1.000 | 0.966 | 1.000 | 1.000 | - | 1.000 |
| 23 | 1.000 | 1.000 | 1.000 | 1.000 | - | 1.000 |
| 0-2 | ~0.996-1.000 (todas) | | | | | |
| 3 | 0.176 | 0.102 | 0.237 | 0.142 | 0.179 | - |
| 4-16 | <=0.069 (miercoles/jueves muestran ~0.059 residual en varias horas, no explicado; lunes/martes/viernes en 0.000) | | | | | |
| 17 | 0.000 (mie/jue; hora muerta real en lun/mar/vie) | | | | | |

(marzo se excluyo de este split por ser el mes de transicion interna entre ambos regimenes;
sus datos SI estan incluidos en la tabla agregada 3.4 y en la fila mensual de 3.5.)

Comparando A vs B: la ventana de spread ajustado (fraccion >= ~0.9) ocupa servidor-hora
20-23,0-2 en el Regimen A, y servidor-hora 18-23,0-2 en el Regimen B -- **desplazada
aproximadamente 2 horas hacia atras**, consistente con el corrimiento de la hora muerta
medido arriba. La FORMA de la ventana (duracion ~6-7h, mismos dias activos) es similar entre
regimenes; su POSICION en el eje de "hora de servidor" no lo es.

---

## 4. Viabilidad de fuentes externas de ~2 anos de XAUUSD (investigacion de escritorio, nada descargado)

| Fuente | Granularidad | Profundidad historica | Bid Y Ask? | Formato | Friccion / coste |
|---|---|---|---|---|---|
| **Dukascopy** (export oficial + `dukascopy-node`/`duka`/TheoryCraft) | Tick, s1, m1, m5, m15, m30, h1, h4, d1, mn1 | 15+ anos, incluye XAUUSD ("Spot gold") | **SI** en el tick export (bid+ask+bid_vol+ask_vol por tick). Para OHLC agregado, Dukascopy permite elegir tipo de precio (bid u ask) por separado -- una serie OHLC de spread requeriria descargar AMBAS series (bid-OHLC y ask-OHLC) y emparejarlas, no viene junto en un solo archivo de barras. | CSV/JSON (tick export oficial); CSV via herramientas de terceros | Gratis; requiere descarga/CLI (no hay datos ya en el repo: `sentinel_engine/lake/ingest_dukascopy.py` existe pero SIN muestra real validada) |
| **HistData.com** | M1 bar (Generic ASCII) y Tick 1s (Generic ASCII) | M1 desde 2000 | **M1 bar: NO** (solo "Bar OPEN/HIGH/LOW/CLOSE BID Quote" -- una sola cotizacion, sin ask). **Tick (Generic ASCII): SI** -- fila confirmada `DateTime Stamp,Bid Quote,Ask Quote,Volume` (bid y ask juntos por tick, verificado en su pagina de especificacion). | CSV | Gratis, descarga manual mes a mes o via herramientas de terceros (`histdata` PyPI, etc.). Timestamps en **EST fijo, sin ajuste de horario de verano** (documentado explicitamente por HistData) -- friccion de alineacion con la hora de servidor Capitaria, que si tiene corrimientos tipo-DST (Seccion 3.6). |
| **TrueFX** | Tick-by-tick ("top-of-book") | No verificable en esta sesion | **NO VERIFICADO** -- la pagina oficial de descargas no lista instrumentos ni confirma bid+ask; resultados de busqueda mencionan "Gold" pero no se pudo confirmar contra la fuente primaria (requiere registro/login). Historicamente TrueFX es conocido por cubrir pares FX mayores, no metales -- esto es conocimiento previo, no confirmado en esta sesion. | Desconocido sin registro | Requiere cuenta/registro para verificar cobertura real |
| **Tickstory** | Tick (via Dukascopy) | XAUUSD desde ~2003, vía backend Dukascopy | Mismo SI que Dukascopy (Tickstory es una app de escritorio que descarga y convierte datos de Dukascopy; no es una fuente de datos independiente, es un envoltorio de conveniencia) | Convierte a formatos MT4/MT5-compatibles | App de escritorio, gratis, requiere instalacion; su cobertura y fidelidad heredan integramente las de Dukascopy |

**Declarado explicitamente: los productos de barras de UN SOLO tipo de precio (HistData
M1 bid-only; cualquier descarga de OHLC de Dukascopy si solo se pide un tipo de precio) NO
sirven para reconstruir spread, sin importar el proveedor -- es una limitacion estructural
de "una sola cotizacion por barra", no del proveedor en si.** Los unicos productos
verificados con bid+ask simultaneo son: Dukascopy tick export, HistData tick (Generic ASCII)
export. TrueFX queda **NO EVALUABLE** (cobertura de XAUUSD sin confirmar; requiere acceso
directo a la cuenta). Tickstory no es una fuente propia, hereda la respuesta de Dukascopy.

Sobre la politica de retencion propia de Capitaria: no se encontro ninguna documentacion
publica (sitio oficial, foros MQL5, reviews de terceros) que declare el periodo de
retencion de historial M1/M15 para XAUUSD. Los dos hechos verificados en este repo sobre esa
politica son los de la Seccion 2 (piso M15 en vivo = 2022-03-31; piso M1 en vivo =
2026-03-25; fallo de M1 incluso desde el cache del Tester para enero-marzo 2026).

---

## 5. El problema del spread ajeno: espacio de opciones tecnicas (sin elegir ninguna)

Contexto fijo: el gate operativo de las estrategias es `abs(spread - 0.5) <= 0.05`
(equivalente a spread en `[0.45, 0.55]`, y empiricamente en Seccion 3.2 casi siempre
exactamente 0.50). Un tick de otro proveedor trae SU propio spread, no el de Capitaria.

**(a) Aplicar el gate directamente al spread de la fuente externa** (si la fuente trae
bid+ask real, p.ej. Dukascopy o HistData tick).
- Supuesto: el nivel absoluto y la dinamica del spread de la fuente externa son
  suficientemente parecidos al de Capitaria como para que `abs(spread_externo - 0.5) <= 0.05`
  seleccione un conjunto de momentos equivalente al que seleccionaria Capitaria. Esto asume
  que dos brokers/venues distintos cotizan el mismo instrumento con markups de spread
  comparables en valor absoluto -- no garantizado a priori (distintos proveedores de
  liquidez, distinto modelo de precios).
- Que dato local lo validaria o refutaria: los 7 meses de ticks Capitaria ya medidos
  (Seccion 3) SI se solapan en calendario con cualquier fuente externa que cubra 2026
  ene-jul. Si se obtuviera esa misma ventana de la fuente externa, se podria comparar
  directamente su histograma de spread (Seccion 3.2) y su tabla hora x dia (Seccion 3.4/3.6)
  contra los de Capitaria en el MISMO periodo -- una discrepancia de escala o de forma
  refutaria el supuesto para esa fuente. Hoy esa comparacion NO EVALUABLE (no se descargo
  ningun dato externo).

**(b) Extrapolar la ventana horaria de Capitaria (Seccion 3.4/3.6) como mascara temporal
fija**, aplicada sobre precio (OHLC) de una fuente externa o del propio historial de barras
Capitaria pre-2026, ignorando el spread propio de esa fuente/periodo.
- Supuesto: la ventana de spread ajustado es un rasgo estructural/de liquidez del mercado
  (sesion de Londres/NY, etc.), estable en el tiempo y transferible fuera de la ventana
  medida -- no algo propio del libro de Capitaria en particular.
- Que dato local lo valida o refuta: la Seccion 3.5 (variacion mes a mes, 32.4%-41.8%,
  9.4pp de rango) y sobre todo la Seccion 3.6 (la hora de servidor en si se desplazo 2 veces
  en 7 meses) son evidencia DIRECTA de que la mascara NO es un simple "hora fija de reloj de
  servidor" ano tras ano -- debe aplicarse en terminos relativos a sesion (con el
  corrimiento tipo-DST corregido), no en terminos de hora de servidor cruda, si se extiende
  mas alla de una ventana de ~1 ano. Ademas, no existe ningun dato anterior a 2026-01 para
  comprobar si esta misma forma horaria era valida en 2022-2025 -- es un supuesto no
  verificable con los datos disponibles hoy.

**(c) Enfoque hibrido: calibrar un gate propio de la fuente externa** (encontrar su propia
moda de spread estrecho, analogo al bimodal 0.50/0.60 de Capitaria) e intersectarlo
temporalmente con la mascara horaria de Capitaria (b).
- Supuesto: ni (a) ni (b) son suficientes por si solos; se necesitan ambos filtros a la vez
  (la fuente esta en su propio regimen de spread estrecho, Y ese momento cae dentro de la
  ventana horaria historica de Capitaria).
- Que dato local lo valida o refuta: igual que (a), requiere una fuente externa con datos
  para el periodo ya medido (ene-jul 2026) para verificar si las modas de spread estrecho de
  ambas fuentes coinciden en el tiempo. NO EVALUABLE hoy sin esos datos.

**(d) No traer ningun proveedor externo de precio: usar las barras M15 OHLC de Capitaria ya
verificadas (Seccion 2, 2022-03-31 en adelante) y aplicarles SOLO la mascara horaria
Capitaria (b) como filtro temporal**, sin ninguna serie de spread externa.
- Supuesto: el precio (OHLC) si es genuinamente de Capitaria para todo el periodo (a
  diferencia de (a)/(b)/(c), que mezclan una fuente de precio ajena); lo unico asumido es que
  el spread durante 2022-2025 siguio la misma forma horaria medida en 2026 -- no verificable
  con los datos en mano (7 meses es la unica ventana con spread real).
- Que dato local lo valida o refuta: nada en el repo permite verificar el spread real de
  Capitaria antes de 2026-01 (los ticks no llegan mas atras, Seccion 1). El supuesto es, con
  los datos actuales, **no falsable**.

**(e) No extrapolar nada: restringir el backtest a la ventana con ticks reales (ene-jul
2026, ~7 meses)**, donde barra y spread son ambos genuinamente Capitaria y simultaneos.
- Supuesto: ninguno adicional a lo ya medido.
- Validacion: ya esta totalmente validado por las Secciones 1-3; el costo es no alcanzar el
  objetivo de ~2 anos.

Ninguna de las cinco opciones fue seleccionada ni descartada por este informe; se listan con
sus supuestos y la via de validacion/refutacion disponible para que la decision se tome con
estos numeros delante.

---

## Fuentes consultadas (Seccion 4, busqueda web -- nada descargado)

- [Forex Historical Data Export -- Dukascopy Bank SA](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- [dukascopy-node -- xauusd instrument page](https://www.dukascopy-node.app/instrument/xauusd)
- [dukascopy-node](https://www.dukascopy-node.app/)
- [duka -- Dukascopy data downloader](https://giuse88.github.io/duka/)
- [GitHub -- theorycraft-trading/dukascopy](https://github.com/theorycraft-trading/dukascopy)
- [HistData.com -- Data Files: Detailed Specification](https://www.histdata.com/f-a-q/data-files-detailed-specification/)
- [HistData.com -- Download Free Forex Historical Data](https://www.histdata.com/download-free-forex-historical-data/)
- [TrueFX -- Historical Downloads](https://www.truefx.com/truefx-historical-downloads/)
- [Tickstory -- Download Dukascopy Historical Data: Available Date Ranges](https://tickstory.com/dukascopy-historical-data-available-date-ranges/)
- [Tickstory -- Historical data for GOLD (forum)](https://tickstory.com/forum/viewtopic.php?t=2184)
- Referencia interna previa (ya en el repo, reutilizada como insumo de esta seccion):
  `docs/superpowers/specs/2026-07-10-xauusd-history-feasibility.md`

## Ficheros/rutas relevantes citados en este informe

- `data/lake_ticks/XAUUSD/202601.parquet` .. `202607.parquet`, `_bars_M15.parquet`
- `data/lake/XAUUSD/1.parquet`, `2.parquet`, `5.parquet`, `15.parquet`, `60.parquet`, `1440.parquet`
- `data/lake/XAUUSD/{M1,M2,M5,M15,H1,D}/*.parquet` (tiers mensuales)
- `data/raw/XAUUSD/{15,2,5,60}_early2026.csv`
- `scripts/mt5_dump_history.py`, `scripts/mt5_dump_xauusd_early2026.py`, `scripts/live/run_bars_ingester.py`
- `sentinel_engine/lake/ingest_dukascopy.py`, `sentinel_engine/lake/tiers.py`
- `MT5_Tester/Bases/Capitaria-All/history/XAUUSD/*.hcc`, `.../cache/*.hc`, `MT5_Tester/Bases/Capitaria-All/ticks/XAUUSD/*.tkc`
- `MT5_Tester_2/Bases/Capitaria-All/...` (duplicado), `MT5_Tester_2/Tester/bases/Capitaria-All/history/XAUUSD/*.hcs`
- `docs/superpowers/specs/2026-07-10-xauusd-history-feasibility.md` (investigacion previa reutilizada)
