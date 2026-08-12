# TRACKER — Programa de Investigación XAUUSD 2026-H2

> **ÚNICA FUENTE DE VERDAD DEL ESTADO.** El plan dice QUÉ hacer; esto dice QUÉ SE HIZO.
> Cada agente lo actualiza al terminar SU tarea (último paso, siempre) y commitea ese cambio.
> No se edita a mitad de una tarea. Este fichero es del CONTROLADOR: un subagente solo escribe
> la fila de SU tarea.
>
> Vocabulario: `[ ]` pendiente · `[~]` en curso · `[x]` hecho y VERIFICADO · `[!]` bloqueado/escalado.

**Rama:** `equipo1`. Nunca commitear a `alvaro` ni a `master`.
**Plan maestro:** `docs/superpowers/plans/2026-08-10-plan-investigacion-integral-v4.md`
**Charter:** `research/CHARTER.md` · **Decisiones:** `research/DECISIONES.md`

---

## 🔴 ESTADO EN UNA LÍNEA (actualizar SIEMPRE)

> **2026-08-12 · FASE 0 (Preparación), EJECUTANDO.** Cerradas y verificadas contra artefactos
> crudos: T0.1, T0.0, T0.11a, T0.2, T0.9-min, T0.3a/T0.3b/T0.4a/T0.5a (tooling), **T0.3**,
> **T0.4** (top-up Capitaria, +2.584.669 ticks de julio recuperados), **T0.5** (304 deals / 152
> posiciones de la 902) y **T0.12** (holdout sellado, D-31). **B2 resuelto** (D-22): las 12
> modificaciones de motor están autorizadas.
> ✅ **B9 CERRADO 2026-08-12 por la vía de D-30** (`copy_ticks_range` contra el servidor de AVA,
> solo lectura; corridas `F0-DATA-AVA-0004/0005/0006`). Lago AVA: **56 meses / 246.448.523 ticks**,
> `2022-01-02` → `2026-08-12`. **Julio cerrado del todo** (`202607`: 2,71 M → 6,41 M ticks, 12 → 27
> días, cero días hábiles ausentes). Febrero recuperó `02-20`→`02-26`. Agosto llega hasta hoy.
> **Cero días destruidos**, verificado día a día contra los `.bak`. En 4,6 años quedan **2** días
> hábiles sin ticks y **los dos son huecos declarados** (D-29): `2022-04-15` (Viernes Santo) y
> `2026-02-27` (no existe en el feed de AVA, probado por prueba de flancos; Capitaria sí lo tiene).
> 🟢 **Sustrato AVA APTO PARA VEREDICTOS** — B11 cerrado el 2026-08-12 por **D-33**, vía exclusión
> (reducción de alcance autorizada por el user). Los huecos intradía son **56 / 344,1 h**, pero solo
> **97,7 h caen dentro de la ventana operativa `18:00→02:00` NY**; el resto es zona muerta e
> irrelevante. **Holdout intacto** (0,1 h en ventana). Los intervalos afectados quedan **declarados
> no evaluables** en `04-resultados/T0.3-continuidad/exclusiones-ava.json` y **la tabla mensual de
> BL-0 lleva columna de cobertura obligatoria** (`2026-01` pierde ≈17 % del mes, `2026-02` ≈9 %).
> ✅ **T0.12 SELLADO (D-31):** acto 1 Capitaria `2026-05-12`→`2026-07-26` (propuesta del controlador
> **aceptada por el user** el 2026-08-12); acto 2 AVA **año 2023 completo**. Holdout intocable
> desde ya (§A.14); BL-0 lo excluye.
> ✅ **T0.6 Tarea 0 HECHA (commit `bd17f60`): la puerta de paridad de D-22 ya existe.** Línea base
> golden de S6/S7/SuperTrend congelada sobre Capitaria pre-holdout (`2026-01-01`→`2026-05-11`,
> 8.334 velas, 1.503 posiciones) + `tests/research/test_baseline_parity.py`. Determinismo
> confirmado por hash; el test **verificado por mutación** (deriva de 1e-7 en 1 de 633 posiciones →
> rojo, nombrando estrategia/índice/clave). **Correr ANTES y DESPUÉS de cada una de las 12 mods.**
> ✅ **T0.13 RESUELTA de facto (commit pendiente de esta sesión): la ventana operativa es
> `18:00 → 02:00 hora de Nueva York`, todo el año** — apertura de CME Globex para el oro, precedida
> del corte diario de mantenimiento. Medido: el "gate de spread 0,50" de Capitaria **es un reloj,
> no un spread** (99-100 % estrecho dentro de la ventana, 0-5 % fuera), y salta en las fechas
> exactas de los dos DST (`2026-03-08` EEUU, `2026-04-05` Chile). Relojes de servidor **medidos**
> vía el corte de CME: **Capitaria = hora de Chile con DST (UTC−3/−4); AVA = UTC fijo**.
> ✅ **PASO 0 CERRADO 2026-08-12 (D-32): la primera tabla de números reales tiene su semántica
> establecida.** `maxDD` es pico-a-valle del **P&L cerrado** y el simulador **no impone margen ni
> margin call** → `maxDD` y `peak_margin` **NO miden supervivencia** y quedan **prohibidos** como
> criterio de aprobación o descarte; el drawdown de equity es **NO EVALUABLE** hasta la mod de motor
> **#11**. S6 y S7 pican idéntico porque **abren las mismas posiciones** (211/211 entradas comunes).
> **Concurrencia real = 3, no 7,8** (los 19,5 MM son un pico instantáneo en el `reverse`; sostenido
> **10,4 MM**; ROM corregido **S6 238,34 / S7 −106,44 / ST 1.199,74**). 🔴 **Esa tabla NO es un
> ranking entre estrategias**; lo único concluyente es **S7 en negativo** (PF 0,968 → descartada por
> D-06). Añadidas las filas `F0-INFRA-0028` (retroactiva: la línea base de `bd17f60` no tenía fila)
> y `F0-INFRA-0029`.
> ✅ **T0.13 CERRADA 2026-08-12 (D-36 + D-37): el calendario de ventana está canonicalizado y es
> consumible.** La medición cruda daba **11 periodos en 7 meses** — ruido de agrupamiento, no un
> horario de bróker. Canonicalizado por la tupla **(DST Chile, DST Nueva York)**, derivada del
> `utcoffset()` de `zoneinfo` sin fecha hardcodeada, quedan **4 periodos** con `cierre_ny` =
> `02:00` · `02:00` · `03:00` · `03:15` — **dos valores estructurales**; los cortes de más son el
> cambio de proyección de reloj del `2026-03-08` y el hueco del holdout sellado. `bordes_por_semana`
> (23 semanas) se conserva **sin canonicalizar** para auditoría. Fila `F0-INFRA-0033`. 🟠 Residuo
> declarado: desde el `2026-04-26` la mayoría de semanas mide `03:15` y no `03:00` (posible
> corrimiento real, no jitter); **inmaterial** porque la ventana se consume a hora entera.
> **Siguiente:** implementar el filtro de ventana NY sobre los dos sustratos → correr el desglose
> mensual de S6/ST sobre 3,5 años de AVA → comparar contra Capitaria en el solape (A6 Pata B) →
> resto de T0.6 → T0.7 (A6 Pata A) → T0.8 (freeze) → LBT/BL-0. **Objetivo declarado por el user
> (2026-08-12): ver S6 y SuperTrend en backtest largo cuanto antes, con la paridad AVA ↔ Capitaria
> ↔ posiciones reales confirmada primero** — A6 es el gate y no se salta. 🔴 **El filtro horario NO
> se quita** (instrucción explícita del user: el edge aparecía solo en esa franja acotada).
> 🔴 **Deuda de robustez detectada y NO resuelta** (ver B10): el predicado de completitud de
> `ticks_mt5` es ciego a agujeros en la cabeza del mes, y no hay guarda anti-destrucción. Esta
> corrida se protegió con `tolerancia_horas: 1` y verificación manual, no por diseño.
> Siguen abiertos B3 (matriz de indicadores de la autopsia) y B4 (umbrales operacionales de la
> puerta estadística), ambos del user y ninguno bloquea Fase 0.

---

## FASE 0 — PREPARACIÓN (bloqueante · nada de investigación corre antes)

| Estado | # | Tarea | Routing | Notas / bloqueo |
|---|---|---|---|---|
| `[x]` | T0.1 | Backup del plan previo | — | `docs/superpowers/plans/backups/2026-08-10-programa-exploracion-artifact-PRE-INTEGRACION.html` (71,7 KB) |
| `[x]` | T0.0 | Plan v4 redactado + Research OS construido | Fable | Plan: `plans/2026-08-10-plan-investigacion-integral-v4.md` · OS: `research/**` |
| `[x]` | T0.11a | Descarga de 28 transcripciones YouTube | Fable | `data/literature/youtube_transcripts/` · 28/28 · **~233.723 tokens** · NINGUNA leída |
| `[x]` | T0.2 | Propuesta de limpieza disco C: (95 % lleno) | Sonnet · INVESTIGADOR | ✅ **VERIFICADO.** `04-resultados/T0.2-disco-C/inventario-espacio.md` (574 líneas). D-04 respetada (0 comandos destructivos, comprobado). C: 22,19 GB libres (4,92 %). Fila `F0-INFRA-0018`. ✅ **CERRADA por el user 2026-08-10**: vació `Downloads` a mano → **+53,75 GB** (C: 22,19 → 75,94 GB libres, verificado). Cachés de dev (~41 GB) quedan como reserva |
| `[x]` | T0.3a | Captura de especificación del feed AVA | Sonnet · INVESTIGADOR REPORT-ONLY | ✅ **VERIFICADO.** Artefacto `research/fases/F0-preparacion/04-resultados/T0.3-ava/especificacion-feed.md` (368 líneas, 17.841 bytes, confirmado en disco por el orquestador; el fichero creció después por un addendum, ver Bitácora). Identidad verificada: login `101744074`, servidor **`Ava-Demo 1-MT5`**, `Ava Trade Ltd.`, `ACCOUNT_TRADE_MODE_DEMO`. Símbolo **`GOLD`**: `trade_contract_size` = **100.0**, `digits` = 2, `point` = 0.01 — **idénticos a Capitaria**; el dimensionamiento de "1 ficha de 0,67" transfiere sin ajuste. Tick de captura: bid 4382.83 / ask 4383.28, spread 0,45. Attach-only respetado (`initialize()` sin `path=`). Efecto colateral declarado: `symbol_select("GOLD", True)` cambió el Market Watch del terminal (no destructivo). Fila `F0-INFRA-0020` |
| `[x]` | T0.3 | **R6-AVA**: descarga real-tick ≥2 años (objetivo 4) | Sonnet | ✅ **VERIFICADA, con la salvedad de B9** (ver Bloqueos Activos). Commits `f538106` (task-type) + `fd80772` (corrección de arrastre). **209.894.471 ticks** ingeridos, **1,64 GB** en 52 parquet mensuales, cero `.tmp`/`.bak` pendientes, `filas_leidas == filas_escritas`. 🟢 Ida y vuelta de timestamps probada contra la fuente: primer tick `2022-01-02 23:01:00.106` = primera fila del CSV; último `2026-08-10 22:46:13.322` = marca del nombre del fichero de origen — valida empíricamente `calendar.timegm()` frente a `.timestamp()`. 🟢 Consistencia interna del arrastre: `ticks_ask_arrastrado=11.779.095` / `ticks_bid_arrastrado=11.157.025` coinciden exactamente con los conteos de `<FLAGS>`=2/4. 🟢 `<FLAGS>` en los 4,6 años completos solo toma 2, 4 y 6 — nunca 8 (LAST) ni 16 (VOLUME): el feed de AVA no publica volumen negociado. Checksum SHA-256 del CSV origen `e2a4eed5a383230d41064d76a22cbf8dcc4bf7dfd2d5719ef60b130fb0b8ae74`. 🔴 **BLOQUEO B9: faltan los meses 202603-202604-202605-202606 (mar-jun 2026) — el lago tiene 52 meses, no 56.** No es fallo de ingesta (lo leído coincide con lo escrito): el CSV de origen no contiene esos meses. El hueco está en medio del sustrato, cae justo antes de la ventana en que operó la 902 (ata A6), y cualquier backtest que lo cruce daría resultados incompletos sin avisar. **Sustrato AVA NO apto para veredictos hasta que B9 se cierre.** Fila LEDGER: `F0-DATA-AVA-0001` (escrita por el runner). 🔄 **ACTUALIZACIÓN 2026-08-11:** el diagnóstico de B9 citado en esta fila (*"faltan los meses 202603-202606"*) **era incorrecto por defecto** — se midió por presencia de fichero mensual. Medido por día (`F0-DATA-AVA-0003`), el hueco era `2026-02-20`→`2026-07-17`, 106 días hábiles, con `202602` y `202607` presentes pero truncados. Corrida `F0-DATA-AVA-0002` ingerida: lago a **56 meses / 241.000.303 ticks**, quedan 19 días hábiles. Ver B9 corregido en Bloqueos Activos |
| `[x]` | T0.3b | Task-type `ticks_csv_mt5` — ingesta del CSV de ticks AVA a parquet | Sonnet · IMPLEMENTADOR · TDD | ✅ **VERIFICADO.** Commit `f538106`, scoped a 4 ficheros. `pytest tests/research/ -q` re-corrido por el orquestador en foreground → **156 passed**. `scripts/research/__init__.py` sigue ausente. **Punto crítico verificado leyendo el código:** codifica `t_msc` con `calendar.timegm()`, **nunca** `.timestamp()` — `timegm` es la inversa exacta de `utcfromtimestamp()`, que es como el lago decodifica; usar `.timestamp()` habría consultado el huso del host y desplazado los 4,6 años **cuatro horas en silencio**. Grep confirma cero `utcnow`, `tz_localize` y `astimezone` en el módulo. Lago destino `data/lake_ticks_ava/GOLD/`, con guarda que aborta si el destino cae dentro de `data/lake_ticks/`. Fila `F0-INFRA-0023` |
| `[x]` | T0.4a | Guard de identidad en el task-type `ticks_mt5` | Sonnet · IMPLEMENTADOR · TDD | ✅ **VERIFICADO** por el orquestador contra artefactos crudos, no contra el reporte: `pytest tests/research/ -q` re-corrido en foreground → **137 passed**; commit `cab4acb` scoped a 3 ficheros; `extract_ticks.py` sin tocar desde `1b9e968` (2026-07-26) y `guard_cuenta.py` desde `6467046` (2026-07-15), ambos anteriores; `scripts/research/__init__.py` sigue ausente; **orden del guard confirmado leyendo el código**: `account_info()` en L197, guard en L213-235, primer `copy_ticks_range` en L286. Aborta con `TicksMT5IdentityError` si falla login, servidor, `trade_mode != DEMO` o el símbolo no resuelve. Desbloquea T0.4 y T0.5. Fila `F0-INFRA-0021` |
| `[x]` | T0.4 | **Top-up ticks Capitaria** (ventana completa de la 902) | Sonnet impl. + runner | ✅ **T0.4-impl HECHA y verificada** (`6544a1f`, fila `F0-INFRA-0019`); guard de identidad añadido y verificado (`cab4acb`, fila `F0-INFRA-0021`). ✅ **VERIFICADA — descarga real completada.** Identidad ejercida y registrada en métricas: `login 2883015767, server Capitaria-All, symbol_resuelto XAUUSD, trade_mode 0`. 🟢 **Casi-incidente de julio, demostrado con números:** `202607.parquet` pasó de **8.270.356** a **10.855.025** ticks (**+2.584.669 recuperados**) — bajo la regla original ("si el mes existe, sáltalo") esos ticks nunca se habrían descargado. Sobrescritura segura ejercida: original conservado como `202607.parquet.bak-20260811222730`, no borrado. `202608.parquet` nuevo, 3.324.988 ticks. Cobertura verificada leyendo los parquet: `202607` del 2026-07-01 04:00:00 al 2026-07-31 16:54:59; `202608` del 2026-08-02 18:00:05 al 2026-08-11 22:27:31 — el salto entre ambos es el fin de semana con mercado cerrado, no un hueco de datos. 🟢 **Cubre íntegramente la ventana de la 902** (primera apertura 2026-07-27 18:53:30, última 2026-08-11 01:15:04): **A6 Pata A tiene su sustrato completo por el lado de Capitaria.** Insumo directo de A6 Pata A: ver **ENMIENDA E-01**. Primer cliente del runner (D-18). Filas LEDGER: `F0-DATA-0001` / `F0-DATA-0002` (escritas por el runner) |
| `[x]` | T0.5a | Separación de autoridad lectura/orden en `pull_account_deals.py` (implementa D-28) | Sonnet · IMPLEMENTADOR · TDD | ✅ **VERIFICADO.** Commit `f3271ad`, scoped a 2 ficheros. `pytest tests/analysis -q` re-corrido por el orquestador → **97 passed**. **Verificado que la autoridad de orden NO se movió:** `guard_cuenta.py` sin tocar desde `6467046` (2026-07-15), anterior a este trabajo; `SANCTIONED_DEMO_LOGINS` y `REAL_LOGIN` intactos. Bloqueo duro de `REAL_LOGIN` presente en las dos comprobaciones (líneas ~246 y ~445). Gate de `trade_mode` real, usando la constante canónica `guard_cuenta.TRADE_MODE_DEMO`, no un literal. Las llamadas capaces de operar solo aparecen en el comentario de cabecera y en la lista de prohibidas del test. Desbloquea **T0.5**. Fila `F0-INFRA-0024` |
| `[x]` | T0.5 | Export historial cuenta 902 (deals/órdenes/balance) | Sonnet | ✅ **VERIFICADA.** Vía `MT5_Tester_2` (terminal de Capitaria — ver **ENMIENDA E-02**). **SOLO LECTURA** (charter §A.12). Ejecutada por el orquestador con credenciales aportadas por el user en tiempo de ejecución vía variable de entorno; **la contraseña no se persistió en ningún fichero**. Guard de identidad de lectura (D-28) pasó y quedó impreso; el script cerró con "No order was placed/modified/closed". **304 deals, 152 posiciones.** Artefactos en disco: `data/analysis/2883016902/2883016902_deals_raw.csv` (305 líneas) y `_positions.csv` (153 líneas). Balance **64.646.947,55 CLP**, equity **65.177.999,07 CLP**. Neto por estrategia, posiciones cerradas: **S6-K2P0**: 84 cerradas, 0 abiertas, +9.272.144,35 CLP · **SuperTrend-p14x3-M15**: 67 cerradas, 1 abierta, +5.930.966,98 CLP. ⚠️ **Dato de alcance, no veredicto:** consultado desde 2024-01-01, toda la historia existente va del 2026-07-27 al 2026-08-11 (~2 semanas, 152 posiciones, todas `tanda2`) — hecho sobre el tamaño de la base de evidencia viva, sin calificar las estrategias. Fila LEDGER `F0-INFRA-0025` |
| `[ ]` | T0.6 | **12 modificaciones de motor** (inventario en plan §4.1) | Spec: Opus · Impl: Sonnet TDD | ✅ **B2 RESUELTO (D-22): SIGN-OFF recibido del user.** TODAS juntas, antes del freeze. R1-bis vigente sin excepción; **paridad re-verificada tras CADA modificación**, nunca al final del lote |
| `[ ]` | T0.7 | **A6 — Fidelidad** (diseño de dos patas, plan §4.2) | Impl: Sonnet · Análisis: Opus | **GATE DE TODO EL PROGRAMA.** Objetivo: señal bit-idéntica; neto ≤0,3 % (99,7) / ideal ≤0,15 % (99,85) |
| `[ ]` | T0.8 | Freeze del motor (tag + SHA anotado aquí) | Controlador | Solo tras T0.6 + T0.7 verdes |
| `[x]` | T0.9-min | **Scaffold mínimo de runner** (D-18) | Sonnet · impl. TDD | ✅ **VERIFICADO** por el controlador contra artefactos crudos. `scripts/research/runner/` (7 módulos) + `tests/research/test_runner_scaffold.py`. Commit `b9ce5f2`, 8 ficheros / 606 líneas. 5/5 tests re-corridos en foreground; `tests/research` 118 passed. Fila `F0-INFRA-0017`. 4 observaciones diferidas → `BACKLOG.md` |
| `[ ]` | T0.9 | Research OS — resto (supervisión durable) | Sonnet | Estructura y protocolos: `[x]`. Scaffold de runner: T0.9-min. Falta: supervisión durable de watcher/ingesta |
| `[ ]` | T0.10 | Literatura formal — 7 áreas | Recolección: Sonnet · Memos: Opus | Cada área ANTES de cerrar su grilla |
| `[ ]` | T0.11b | Análisis de las 28 transcripciones | Ver protocolo dedicado | **Protocolo exacto:** `research/fases/F0-preparacion/PROTOCOLO-REVISION-VIDEOS.md` |
| `[x]` | T0.12 | Sellar el holdout | Controlador | ✅ **SELLADO 2026-08-12 — ver D-31 para el cuerpo completo y las consecuencias.** Los dos actos cerrados el mismo día: **acto 1** (Capitaria) = **`2026-05-12`→`2026-07-26`**, la propuesta del controlador **aceptada explícitamente por el user**; corta en el 26-jul para dejar fuera del sello los 16 días de la ventana de la 902 (`2026-07-27`→`2026-08-11`) que **A6 Pata A** necesita — el holdout protege contra sobreajuste de *selección* de estrategias y A6 Pata A no selecciona nada. **Acto 2** (AVA) = **año 2023 completo** (`2023-01-01`→`2023-12-31`), que es el ejemplo literal de D-01, año natural completo y no adyacente al acto 1; fechable solo ahora, porque hasta el cierre de B9 no había rango real contra el que fijarlo. Verificado en disco: 2023 sin un solo día hábil ausente (auditoría D-29 `04-resultados/T0.3-continuidad/continuidad-diaria-ava-2026-08-12.txt`). 🔴 **Desde este momento ambos tramos son intocables** (§A.14): ni abrir, ni muestrear, ni graficar, ni backtestear; UNA sola evaluación final autorizada por el user. **BL-0 (D-23) excluye el holdout** → ≈3,5 años efectivos de AVA de los 4,6 |
| `[x]` | T0.13 | Modelado de la hora muerta desplazante | Sonnet · análisis Opus | ✅ **CERRADA 2026-08-12.** Llevada a código en tres pasos, los tres verificados por el controlador contra artefactos crudos (no contra el reporte del agente): (1) `scripts/research/ny_window.py` + 17 tests, filtro de ventana NY (`f537646`, **D-34**); (2) `scripts/research/ventana_calendario.py` + 15 tests, calendario de periodos (`bc19867`, **D-36**); (3) canonicalización del cierre en `scripts/research/medir_calendario_ventana.py` + 26 tests nuevos (**D-37**, fila `F0-INFRA-0033`). 🟢 **La canonicalización era imprescindible:** la medición cruda daba **11 periodos en 7 meses**, que es ruido y no un horario de bróker — jitter de ±15 min por cruzar el 50 % a resolución de 15 minutos, más la semana `2026-03-08` (DST de EEUU) con medición contaminada, que en D-34 salía al 63,5 %. Agrupando por la tupla **(DST Chile, DST Nueva York)**, derivada del `utcoffset()` de `zoneinfo` **sin fecha de transición hardcodeada**, quedan **4 periodos**: `2026-01-01→03-06` NY `18:00→02:00` · `2026-03-08→04-02` NY `18:00→02:00` · `2026-04-05→05-11` NY `18:00→03:00` · `2026-07-26→08-11` NY `18:00→03:15`. Son **dos valores estructurales** del cierre NY; los dos cortes de más son el cambio de proyección de reloj del `2026-03-08` (que NO mueve la ventana, solo su expresión en UTC y hora de servidor) y **el hueco del holdout sellado**, que fragmenta por diseño. 🔴 **Un error real detectado por el controlador y corregido antes de commitear:** la primera versión agrupaba solo por el DST de Chile y publicaba `UTC 07:00` para un periodo de 14 semanas de las cuales **5 medían `06:00`** — degradación silenciosa (§A.13) que `ventana_calendario.py` no habría detectado, porque solo consume `apertura_ny`/`cierre_ny`. 🟠 **Residuo declarado:** desde el `2026-04-26` la mayoría de semanas mide `03:15` y no `03:00` (el periodo 3 empata **exacto 3-3** y se resuelve por desempate a hora en punto); podría ser corrimiento real del cierre y no jitter. **Inmaterial para el backtest** porque `ventana_calendario._hora()` consume hora entera y ambos dan `3`; anotado por si A6 Pata B lo hace visible. `bordes_por_semana` (23 semanas) se conserva **sin canonicalizar** para auditoría. **Historial del análisis, se conserva:** 🟢 **RESUELTO ANALÍTICAMENTE 2026-08-12 (falta llevarlo a código).** Surgió al buscar cómo trasladar el gate de spread a AVA. **Hallazgo central: el "gate 0,50" de Capitaria es un RELOJ, no un spread.** Por hora de servidor, el estado estrecho está al 99-100 % dentro de una ventana y al 0-5 % fuera — es un interruptor, no una tendencia. **Ventana medida por semana:** `20:00→03:59` (05-ene→01-mar) · `19:00→02:59` (16-mar→30-mar) · `18:00→02:59` (13-abr→10-ago), con la **hora muerta siempre 1 h antes** de la apertura (19 · 18 · 17). Los dos saltos caen en las fechas exactas de los DST: semana del **`2026-03-09`** (EEUU arrancó el 08-mar) y del **`2026-04-06`** (Chile terminó el 05-abr). **Convertido a Nueva York las tres filas son el mismo horario: `18:00 → 02:00 ET`, todo el año** = apertura de la sesión electrónica de oro de CME Globex, y la hora muerta = su corte diario de mantenimiento 17:00-18:00 ET. **Relojes de servidor MEDIDOS con el corte de CME como ancla** (no inferidos), en 2022/2024/2026 y en ambas estaciones: **AVA = UTC fijo sin DST** (hora muerta 22 en enero, 21 en julio: se mueve solo con el DST de EEUU) · **Capitaria = hora de Chile con DST, UTC−3/−4** (hora muerta 19 en enero, 17 en julio: acumula los dos DST). ⚠️ El segundo ancla programado (apertura del domingo) **no llegó a correr** por un error de aritmética de día de la semana: la conclusión se apoya en un solo ancla, consistente en 4 muestras. **Pendiente:** llevar la regla a código como filtro de ventana NY aplicado a ambos sustratos, sustituyendo el gate de spread |

**Criterio de cierre de Fase 0:** T0.3..T0.13 en `[x]`, motor congelado con SHA registrado abajo,
A6 verde y firmada por Opus, holdout sellado con constancia en `DECISIONES.md`.

**SHA del motor congelado:** _(pendiente — se escribe aquí al cerrar T0.8)_

---

## FASES SIGUIENTES (no iniciables hasta cerrar la anterior)

| Estado | Fase | Contenido | Gate de entrada |
|---|---|---|---|
| `[ ]` | **A0** | Autopsia de posiciones (dossiers 4 capas, matriz de indicadores, episodios C0, lateralidad, curvas de recuperación) | Fase 0 cerrada + motor mod #11 (instrumentación de camino) |
| `[ ]` | **S0** | Screening retrospectivo de features (reglas de decisión pre-fijadas) | A0 cerrada |
| `[ ]` | **GR** | Ola de grillas B · C · D · LS · F · G · H sobre harness pareado | S0 cerrada |
| `[ ]` | **D170'** | Puerta estadística (gates: neto>0 + consistencia; descriptores: top-K) | GR cerrada |
| `[ ]` | **LBT** | Backtest largo real-tick (AVA 2–4 años, overlay validado) | D170' + T0.3 |
| `[ ]` | **E0** | 🔴 CHECKPOINT CONVERSADO con el user (todas las netas positivas + S6/ST) | LBT cerrada |
| `[ ]` | **E** | Familia E — recombinación, ensambles, sizing | E0 con OK explícito del user |
| `[ ]` | **HO** | Holdout sagrado — UNA sola pasada | E cerrada + autorización explícita del user |
| `[ ]` | **FIN** | Síntesis final ("el libro") | HO cerrada |

---

## BLOQUEOS ACTIVOS

| # | Bloqueo | Bloquea a | Dueño |
|---|---|---|---|
| ~~B1~~ | ~~Credenciales de AVA~~ | — | ✅ **RESUELTO 2026-08-10** (D-19). Quedan dos prerrequisitos operativos de T0.3, no bloqueos de programa: terminal AVA abierto + autorización del guard |
| ~~B2~~ | ~~Sign-off del inventario de 12 modificaciones de motor~~ | — | ✅ **RESUELTO 2026-08-11** (D-22). El user aprobó las 12 modificaciones de motor. Desbloquea T0.6 → T0.7 → T0.8 |
| ~~B3~~ | ✅ **CERRADO 2026-08-12 (D-35):** el user eligió la **matriz COMPLETA** del plan §5.2, la lista entera. Razón registrada: se instrumenta una sola vez (motor mod #11) y añadir un indicador después obliga a re-correr 3,5 años de ticks. **Desbloquea el motor mod #11 → A0** | — | ✅ |
| ~~B4~~ | ✅ **CERRADO 2026-08-12 (D-35):** umbrales **medios** — consistencia mensual **≥55 %** de meses positivos · **bootstrap por bloques a nivel de episodio al 95 % que excluya 0** · **PBO < 0,5**. Razón: exigir 65 % eliminaría estrategias sanas, porque en trend-following la asimetría es el diseño y penalizarla es el mismo error que amputar top-K (§A.2) | — | ✅ |
| — | ✅ **A6 Pata B — umbrales fijados y fechados ANTES de correr (D-35, lo exige D-24):** emparejado de entradas **≥90 % dentro de ±1 barra M15** · divergencia de neto **≤25 %** · meses del mismo signo **≥70 %**. 🔴 **Condición del user:** el informe reporta **la divergencia real como número exacto**, no solo pasa/no-pasa | — | ✅ |
| ~~B5~~ | ~~Autorización explícita para extender `SANCTIONED_DEMO` (`extract_ticks.py:34`) con la demo AVA `101744074` — es código de seguridad~~ | — | **RETIRADO 2026-08-11** (D-20). Ya no existe la necesidad: la ingesta de ticks AVA es un CSV exportado a mano, no llama a la API de MT5 |
| ~~B6~~ | ~~No hay terminal de AVA instalado~~ | — | ✅ **RESUELTO 2026-08-11.** No hizo falta instalar un terminal AVA aparte; el user inició sesión en la demo AVA dentro del terminal existente `D:\FOREX\MT5_Tester`. Servidor confirmado: `Ava-Demo 1-MT5` |
| ~~B7~~ | ~~Conflicto entre dos reglas del user: `PROTOCOLO-REVISION-VIDEOS.md` manda 2 orquestadores Sonnet × ~11 subagentes Haiku (anidamiento), y el charter §C fija **máx 2 en paralelo**~~ | — | ✅ **RESUELTO 2026-08-11** (D-25, ruling del orquestador comunicado al user y no objetado, **revocable por él**). El máx-2 gobierna la concurrencia del *controlador*; los lectores Haiku son read-only, un fichero cada uno, sin escritura al repo. Resolución: ≤2 orquestadores Sonnet concurrentes, y cada uno procesa sus ~10 videos en tandas de ≤3 Haiku simultáneos |
| ~~B8~~ | ~~¿El login sancionado `2883016567` y la cuenta de Capitaria terminada en 902 son la misma cuenta o dos distintas?~~ | — | ✅ **RESUELTO 2026-08-11** por el user, en persona: son cuentas **distintas**. La 902 es login **`2883016902`**, servidor **`Capitaria Latam Spa`**. `2883016567` es otra cuenta, no la 902. La afirmación de un subagente anterior de que eran la misma cuenta queda anulada. Añadida a `CUENTAS.md` (NO-R&D / SOLO LECTURA, sin contraseña persistida — charter §A.12) |
| ~~B9~~ | ✅ **CERRADO 2026-08-12.** El agujero del sustrato AVA quedó cerrado por la vía que autorizó **D-30**: `copy_ticks_range` contra el servidor de AVA, en solo lectura, desde el terminal que el user abrió a mano (manifiesto **nuevo** `03-runs/T0.3-ava-topup-servidor.yaml`, corridas `F0-DATA-AVA-0004` julio / `0005` febrero / `0006` agosto; el manifiesto CSV original no se editó). **Resultado verificado por el controlador contra los parquet, no contra el reporte del runner:** lago AVA **56 meses / 246.448.523 ticks** (241.000.303 + 3.703.411 + 1.424.611 + 320.198, cuadra exacto), rango `2022-01-02` → `2026-08-12`. `202607` pasó de **2.707.151 a 6.410.562** ticks y de 12 a 27 días — **cero días hábiles ausentes en julio**; `202602` recuperó `02-20`→`02-26`; `202608` llega hasta hoy. **Cero destrucción**, comprobada día a día contra los tres `.bak` (ningún día presente en el `.bak` falta en el fichero nuevo); 0 `.tmp` residuales. **Auditoría de continuidad D-29 sobre el lago completo** (`04-resultados/T0.3-continuidad/continuidad-diaria-ava-2026-08-12.txt`): **2 días hábiles sin ticks en 4,6 años, y los dos son huecos DECLARADOS** — `2022-04-15` (Viernes Santo) y `2026-02-27` (ausente del feed de AVA, probado por prueba de flancos; Capitaria sí lo tiene). 🟢 **Sustrato AVA APTO para veredictos**; desbloquea A6 Pata B, LBT y **T0.12 acto 2** (sellado el mismo día, D-31). 🟢 **Ningún código de seguridad tocado**, verificado leyendo el módulo: `tasks_ticks.py` no importa `guard_cuenta` ni `extract_ticks`, y `expected_login`/`expected_server`/`logins_sancionados` son campos del manifiesto sin default (L179-182) — declarar ahí la demo de AVA no amplía ninguna lista blanca de autoridad de orden. Guard de identidad ejercido y registrado en métricas: `login 101744074, server "Ava-Demo 1-MT5", trade_mode 0, symbol_resuelto GOLD`. ⚠️ **Artefacto de reloj declarado (no es un fallo):** julio arranca `2026-07-01 04:00:00.024` porque `copy_ticks_range` interpreta datetimes naive en el reloj del host — el mismo desfase de 4 h que ya tiene el `202607` de Capitaria. **Historial del bloqueo, se conserva íntegro abajo:** ~~🔴 Agujero en el sustrato AVA. Diagnóstico CORREGIDO 2026-08-11 — el original se quedó corto.~~ Se diagnosticó contando **nombres de fichero mensual** ("faltan 202603..202606") y la presencia de un fichero no implica que el mes esté completo. Medido a nivel de **día** sobre los propios datos (fila LEDGER `F0-DATA-AVA-0003`), el hueco real era **un único tramo continuo `2026-02-20` → `2026-07-17`, 106 días hábiles**: `202602` estaba truncado el día 19 y `202607` empezaba el día 19 — ambos **presentes pero incompletos**. ✅ **Cierre parcial:** la corrida `F0-DATA-AVA-0002` (CSV del user `2026-03-01`→`2026-06-30`) recuperó 87 de esos 106 días hábiles; el lago pasa a **56 meses / 241.000.303 ticks**. 🔴 **SIGUE ABIERTO — faltan 19 días hábiles en dos tramos:** `2026-02-20`→`2026-02-27` (6, dentro de `202602`) y `2026-07-01`→`2026-07-17` (13, dentro de `202607`). 🔴 **Y no basta con que el user re-exporte:** la idempotencia del task-type `ticks_csv_mt5` es **por presencia de `<YYYYMM>.parquet`**, así que se saltaría `202602` y `202607` **en silencio** y reportaría éxito — mismo modo de fallo que motivó D-29, un nivel más abajo, y gemelo del casi-incidente de T0.4. Requiere **reprocesado explícito de mes** en el ingestor antes de poder ingerir nada más sobre un mes existente | Declaración de aptitud del sustrato AVA para veredictos; A6 Pata B; LBT; **T0.12 acto 2** | **User** (exportar) + **controlador** (reprocesado de mes). **Estado de las exportaciones al 2026-08-11 23:45, verificado leyendo los CSV (no sus nombres):** ⚠️ `GOLD_202602012305_202602262359.csv` cubre `2026-02-01`→`2026-02-26` — sirve (trae el 20 y del 22 al 26) pero **le falta el viernes 2026-02-27**, último día hábil del mes; ingerirlo tal cual dejaría `202602` truncado el 26 en vez del 19, el mismo problema movido. ❌ `GOLD_202607300000_202607302359.csv` y `GOLD_202608100000_202608102359.csv` son exportaciones de **un solo día** (`2026-07-30` y `2026-08-10`), ambos **ya presentes** en el lago: no aportan nada y reescribirían el mes destruyendo el resto. 🟡 `GOLD_202608110000_202608112323.csv` (`2026-08-11`) **sí es dato nuevo** — el lago termina el 2026-08-10 22:46 — pero solo es ingerible dentro de una exportación de agosto completo. **Pedido al user, con fecha inicial y final DISTINTAS:** `2026.02.01`→`2026.02.28`, `2026.07.01`→`2026.07.31`, `2026.08.01`→`2026.08.11`. 🔴 **HALLAZGO 2026-08-11 23:55 — `2026-02-27` NO EXISTE en el feed de AVA, y es irreducible.** Demostrado por prueba de flancos: la exportación `GOLD_202602260000_202603012359.csv` pidió `2026-02-26`→`2026-03-01`, un rango que **atraviesa** el 27, y devolvió `2026.02.26` y `2026.03.01` pero **no el 27** (verificado con `cut -f1 \| sort -u`). Volvieron los dos días que lo flanquean, luego la ausencia es de la fuente, no de la petición. **Consecuencia: febrero queda tan completo como AVA puede darlo (`2026-02-01`→`2026-02-26`) y B9 no puede exigir más.** Capitaria **sí** tiene ese día (su `202602` llega a `2026-02-27 17:54`), así que el día es real y está cubierto por el otro sustrato. Este hueco pasa a ser un **hueco declarado** en el sentido de D-29, no un fallo. **Falta aún, y solo esto:** `2026-07-01`→`2026-07-15` (11 días hábiles; el 16 llegó vía `julio del 1 al 17.csv` y el 17 vía `GOLD_202607170000_202607192359.csv`) y, como extensión no exigida por B9, agosto completo `2026.08.01`→`2026.08.11`. 🟢 **AVA SÍ TIENE datos en el tramo de julio — probado.** La exportación `julio del 1 al 17.csv` (2026-08-12 00:05) pidió `2026-07-01`→`2026-07-17` y devolvió **`2026.07.16` completo** (`00:00:00.312`→`23:59:56.146`), un día que estaba **dentro** del hueco. Luego julio **no** es un agujero de origen como el 27-feb: el dato existe y **lo que falla es la exportación manual**. 🔴 **El diálogo de exportación no honra el rango pedido.** Evidencia de la noche: `1→17 jul` devolvió 1 día · `26-feb→1-mar` devolvió 2 · `17→19 jul` devolvió 2 · y la de `mar→jun` de las 23:19 devolvió **4 meses / 1,3 GB**. Desde esa corrida grande, todas las posteriores vuelven con uno o dos días. Ficheros renombrados por el user: `agosto.csv`=`2026.08.10`, `27 febrero.csv`=`2026.02.26`, `julio.csv`=`2026.07.17`, `julioooo.csv`=`2026.07.30` — estos dos últimos con **MD5 idéntico** a exportaciones `GOLD_*` previas: son copias renombradas, no intentos nuevos. **Hueco restante: `2026-07-01`→`2026-07-15`, 11 días hábiles.** ✅ **VÍA AUTORIZADA POR EL USER — D-30 (2026-08-12):** se deja de exportar a mano y se piden los ticks que faltan **al servidor de AVA** con `copy_ticks_range`, en **solo lectura**, desde el terminal ya logueado. D-20 no se revoca: se le cayó la premisa (*"la ingesta AVA es CSV manual, no API MT5"*), y su principio —*no se toca código de seguridad por un requisito que dejó de existir*— sigue vigente. Se aplica el precedente **D-28**: `guard_cuenta.py` y `extract_ticks.py:34` **NO se tocan**; la vía de lectura exige login+servidor declarados, gate real de `trade_mode==DEMO` y aborto fail-loud. **Primero leer `scripts/research/runner/tasks_ticks.py`: puede que su guard ya admita un login declarado en el manifiesto y no haya que tocar nada.** Ver D-30 para las condiciones completas |
| ~~B11~~ | ✅ **CERRADO 2026-08-12 por D-33 — por EXCLUSIÓN, no por reparación** (reducción de alcance autorizada por escrito por el user, §A.13). Se elimina del alcance: clasificar los huecos contra calendario de festivos, y rellenarlos desde Capitaria. Se conserva la localización, porque no se puede excluir lo que no se ha ubicado — hecha el mismo día: `04-resultados/T0.3-continuidad/huecos_intradia_ava.py` → `huecos-intradia-ava-2026-08-12.txt` + **`exclusiones-ava.json`** (lista de intervalos consumible por el backtest). Fila `F0-DATA-AVA-0007`. 🟢 **El problema resultó ser 4× menor de lo temido, y la razón es T0.13:** como el sistema solo opera `18:00→02:00` NY, de **344,1 h** de hueco total solo **97,7 h caen dentro de la ventana operativa**; las otras **246,4 h están en zona muerta y no afectan a ningún backtest**. 🟢 **El holdout queda prácticamente intacto:** sus 2 huecos (15,3 h) aportan **0,1 h** en ventana. 🔴 **Confirmada la sospecha que motivó B11 — el promedio SÍ escondía concentración:** de las 97,7 h en ventana, **49,3 h (la mitad) caen en el solape con Capitaria**, y dentro de él `2026-01` pierde **29,1 h ≈ 17 % del mes** y `2026-02` **14,0 h ≈ 9 %**; el resto de meses afectados ronda el 5 %. Por eso D-33 exige **columna de cobertura en la tabla mensual de BL-0**: excluir sin declarar convertiría un mes mutilado en un mes normal con menos operaciones. 🔴 **Corrección de un número ya registrado:** eran **56 huecos / 344,1 h**, no 53 / 306,9 h. La diferencia son exactamente **3 huecos que cruzan frontera de mes** (25,0 + 7,5 + 4,6 = 37,1 h); el barrido anterior procesaba cada parquet aislado y no encadenaba el último tick de un mes con el primero del siguiente. 53+3=56 y 306,9+37,1=344,0 ≈ 344,1: la discrepancia queda **completamente explicada** y sirvió para validar el instrumento nuevo. El tercero es el **artefacto de reloj ya declarado** en B9 (julio arranca 04:00), no un corte de feed. **Historial íntegro abajo:** ~~🟠 **La continuidad DIARIA de D-29 no mide cobertura DENTRO del día — y el feed de AVA tiene huecos intradía sustanciales.** Detectado el 2026-08-12 al revisar los informes de integridad del top-up: `202602` traía dos huecos de **884,6 min (14,7 h)** y **1.223,9 min (20,4 h)**, cuando el patrón normal es 62 min (cierre diario del XAUUSD) o ~2.941 min (fin de semana). Un día con un agujero de 15 h **pasa el chequeo de D-29** —tiene ticks— y aun así es inservible para un backtest real-tick. **Barrido del lago completo** (huecos >90 min y <2.800 min, es decir ni cierre diario ni fin de semana): **53 huecos, ~306,9 h en 4,6 años (≈0,9 % del tiempo de mercado)**. 🟢 **NO los introdujo el top-up de hoy, y esto está medido, no supuesto:** de los 3 meses redescargados salen **2 huecos / 35,1 h**, mientras que los **53 meses intactos** aportan **51 huecos / 271,8 h**. Los mayores son festivos evidentes (`2024-12-24/25`, `2025-12-25`, `2026-01-01`, Viernes Santo `2024-03-29` y `2025-04-18`). 🔴 **Pero los de 2026 no son festivos:** `202601` es el **peor mes del lago con 6 huecos / 65,3 h** —y no se tocó— con cortes como `2026-01-21 23:59`→`01-22 20:18` (20,3 h) y `2026-01-29 23:59`→`01-30 16:20` (16,3 h); `202602` aporta `2026-02-19 23:59`→`02-20 14:44` y `2026-02-22 23:59`→`02-23 20:23`. Son cortes del feed de AVA. **Lo que hay que hacer antes de declarar el sustrato apto para VEREDICTOS:** (1) clasificar los 53 huecos en festivo declarado vs corte de feed, con calendario; (2) cuantificar el impacto por ventana de backtest, no en agregado — 0,9 % global puede ser 15 % de un mes concreto; (3) decidir política: declarar los tramos afectados como no evaluables, o rellenarlos desde Capitaria donde solape (ene-ago 2026 solapa, y **es justo donde se concentran** los cortes). 🟢 Nota favorable: los peores meses de AVA caen dentro del rango que Capitaria cubre, así que A6 Pata B puede medir precisamente ahí. ⚠️ Este hallazgo **no reabre B9** (que era sobre días y meses ausentes) ni afecta al sellado del holdout: 2023 tiene 1 hueco intradía de 10,5 h el `2023-01-02`, festivo~~ | ~~Declaración de aptitud del sustrato AVA para VEREDICTOS; LBT/BL-0. No bloquea T0.6 ni A6 Pata A (que corre sobre Capitaria)~~ | **Controlador** |
| B12 | 🔴 **A6 PATA A NO ES EJECUTABLE HOY: no existen barras M15 de Capitaria para la ventana en que operaron las estrategias vivas.** Medido el 2026-08-12 leyendo los dos ficheros, no inferido: `data/lake_ticks/XAUUSD/_bars_M15.parquet` cubre `2026-01-01 20:00` → **`2026-07-24 16:45`**, y la ventana viva de la 902 va de **`2026-07-27 18:53:30`** a `2026-08-11 01:15:04`. **El solape es CERO.** Sin barras M15 no hay señal: S6 y SuperTrend son estrategias M15, así que el motor no puede reproducir ni una sola de las 152 posiciones reales (84 de S6, 68 de SuperTrend). Esto explica por qué A6 nunca se midió: no es que se pospusiera, es que **le faltaba el insumo y nadie lo había comprobado**. 🟢 **Es reparable hoy y con material ya probado:** los ticks de Capitaria SÍ cubren la ventana entera (T0.4 recuperó julio y agosto, +2.584.669 ticks, verificado), y el patrón para derivar barras M15 desde ticks ya existe y está commiteado — `scripts/research/build_bars_ava.py` hace exactamente eso para AVA (fila `F0-DATA-AVA-0008`). Falta su gemelo para Capitaria sobre `2026-07-27`→`2026-08-11`. **Es el desbloqueo de mayor valor del programa**, porque A6 Pata A es lo único que responde a la pregunta "¿el motor es par con lo que pasó de verdad, y con qué fidelidad?" | **A6 Pata A (T0.7) → T0.8 (freeze) → todo veredicto** | **Controlador** |
| B10 | 🟠 **Deuda de robustez en el task-type `ticks_mt5` — tres huecos, detectados leyendo el código el 2026-08-12 y NO resueltos.** No bloquean Fase 0 (la corrida de B9 se protegió a mano), pero cualquier top-up futuro que no repita esa protección manual puede fallar en silencio. **(a) El predicado de completitud es ciego a agujeros en la CABEZA del mes.** `tasks_ticks.py:271` calcula `completo = (fin_de_mes − max(t_msc)) <= tolerancia`: solo mira `max`, así que detecta una cola truncada y no ve un hueco al principio ni en medio. Medido el 2026-08-12 sobre el lago real: `202607` tenía una cola de **3,0 h** (→ "completo", se habría **saltado en silencio** reportando éxito) pese a que le faltaban sus **13 primeros días hábiles**. Es el modo de fallo de **D-29** un nivel más abajo. Mitigación usada en `F0-DATA-AVA-0004/5/6`: `tolerancia_horas: 1`, que fuerza la redescarga — **funciona por coincidencia aritmética, no por diseño**. Arreglo correcto: que la completitud sea el chequeo de continuidad diaria de D-29 (embrión ya escrito y commiteado en `04-resultados/T0.3-continuidad/continuidad_ava.py`), más una opción explícita de manifiesto (`meses_a_reprocesar`) donde **el operador nombra los meses**, nunca automático. **(b) No hay guarda anti-destrucción.** `_atomic_write_validated` (L135-156) valida integridad del mes nuevo (`bid`/`ask`/monotonía) pero **no compara su cobertura contra el fichero que reemplaza**: si el servidor devolviera un mes parcial, se instalaría igual y el runner reportaría éxito. Es recuperable —el anterior se renombra a `.bak-<ts>` y **nunca** se borra— pero la degradación sería **silenciosa**, que es justo lo que el charter §A.13 prohíbe. Debe **abortar** si el mes nuevo cubre menos días hábiles que el que reemplaza. La comparación se hizo **a mano** esta vez. **(c) No hay guarda de destino.** L247 es un `mkdir` pelado; a diferencia de `ticks_csv_mt5`, nada impide que un manifiesto mal escrito vuelque ticks de AVA dentro de `data/lake_ticks/` (el sustrato Capitaria que usa A6 Pata A). D-30 exige ese destino de forma explícita y la única defensa hoy es escribir bien la ruta | Ningún top-up futuro de ticks es fiable sin repetir la protección manual. No bloquea T0.6/T0.7 | **Controlador** (spec cerrada) + Sonnet impl. TDD |

---

## ENMIENDAS (append-only · formato `protocolos/04-enmiendas-trazabilidad.md`)

> Nota del registrador (actualización 2026-08-11): la propagación de E-02 al plan maestro
> `docs/superpowers/plans/2026-08-10-plan-investigacion-integral-v4.md`, pendiente en la tarea
> anterior por falta de alcance de escritura sobre ese fichero, **se completó** en esta tarea (ver
> Bitácora). **Corrección posterior, mismo día:** el cuerpo original de E-02 (y su propagación al
> plan) afirmaba que este equipo tiene **un único terminal** MT5. Esa afirmación era **falsa** —
> ver el cuerpo corregido de E-02 abajo y la Bitácora. `MT5_Tester_2` **sí existe** y sus
> referencias, tachadas por error en una ronda anterior, quedan revertidas a texto normal (fila
> T0.5 de este TRACKER y §0.12 + fila T0.5 del plan).

### ENMIENDA E-02 · 2026-08-11 · Corrección de nomenclatura de terminales MT5
**Fase / frontera:** Fase 0, en curso (no hay experimento a mitad — corrección de un hecho de
infraestructura).
**Causa:** el plan y varios briefs usan los nombres `MT5_Tester_1` y `MT5_Tester_2`. Verificado en
disco el 2026-08-11 con `Test-Path` sobre `terminal64.exe` y **confirmado por el user**:
`D:\FOREX\MT5_Tester\terminal64.exe` existe (es el terminal al que coloquialmente se llama "tester
1" — por eso `MT5_Tester_1` no existe: va **sin sufijo**; alojó la sesión de AVA);
`D:\FOREX\MT5_Tester_2\terminal64.exe` **existe** (terminal de Capitaria, no estaba corriendo al
comprobar); `D:\FOREX\MT5_Tester_1\` **no existe**; existe además una instalación en
`C:\Program Files\MetaTrader 5`. Evidencia:
`research/fases/F0-preparacion/04-resultados/T0.3-ava/especificacion-feed.md` (sección "Anomalía de
nomenclatura de terminales").
🔴 **Corrección del propio registro:** una versión anterior de esta enmienda (misma fecha) afirmó
que "en este equipo hay un único terminal" — **esa afirmación era falsa** y quedó corregida antes
de que el orquestador la diera por definitiva; ver Bitácora.
**Cambio exacto:** **único cambio real: toda referencia a `MT5_Tester_1` se lee `MT5_Tester`.** Las
referencias a `MT5_Tester_2` son correctas y se conservan **sin marca** — cualquier tachado que se
les haya puesto queda revertido (fila T0.5 de este TRACKER; §0.12 y fila T0.5 del plan maestro).
**Afecta a:** fila T0.5 de este TRACKER; el plan maestro
`docs/superpowers/plans/2026-08-10-plan-investigacion-integral-v4.md` (§0.12 y fila T0.5 de la
tabla de Fase 0, más el cuerpo de esta misma enmienda en su §15).
**Re-validación requerida:** no. Es corrección de nomenclatura, no de resultados. Consecuencia
metodológica que se conserva y se refuerza — **los DOS riesgos de identidad están vivos, no uno**:
(a) hay varios terminales instalados, luego `initialize()` sin `path=` puede engancharse al que no
es; y (b) un mismo terminal sirve datos de un bróker u otro según qué sesión esté logueada —
`MT5_Tester` alojó la sesión de AVA. El guard de identidad (T0.4, fila `F0-INFRA-0021` del LEDGER)
defiende contra ambos y su justificación queda reforzada, no debilitada. **Regla operativa
derivada:** un solo terminal MT5 abierto a la vez durante cualquier corrida de extracción.
**Firmada por:** controlador (Opus), sobre verificación de terreno del 2026-08-11 y confirmación
del user.

---

## BITÁCORA (append-only · más reciente arriba)

- **2026-08-12** · Opus 5 · 🔴 **CORRECCIÓN: «AVA se encareció desde 2025» era una lectura ERRÓNEA
  del controlador.** La objeción del user (AVA promociona spread más bajo y es un bróker grande;
  mentir ahí tendría consecuencias legales) resultó correcta al medirla. Ver **adenda de D-38**.
  - Medido en ventana, los dos feeds a la vez, meses fuera del holdout: **en media son idénticos**
    (`2026-04`: AVA 0,5066 vs Capitaria 0,5071 · `2026-08`: 0,5049 vs 0,5018) y **en mediana AVA es
    MEJOR** (0,45 vs 0,50), con p10 muy superior (0,32 vs 0,50). **La promesa de AVA se sostiene.**
  - 🔴 **El hallazgo real es otro y es peor:** Capitaria es **degenerada** —
    `p10=p50=p75=p90=0,500`, `p99=0,600`— o sea **una función escalón fijada por el bróker**, no un
    spread de mercado. AVA sí tiene distribución real (`p10 0,32 · p50 0,45 · p90 0,73 · p99 1,19`).
    Y el feed de AVA también era degenerado en 2022/2024 (`p50=p75=p90`): **lo que cambió en 2025
    no es el precio, es la granularidad con que su feed reporta el spread.**
  - 🔴 **Consecuencia sobre D-21:** su premisa (AVA siempre más angosto ⇒ el overlay siempre
    ensancha) **no se sostiene en 2026**. El overlay no encarece AVA hasta el coste real:
    **sustituye una distribución realista por el escalón plano de Capitaria**, y D-38 además
    **retira la cola** — los momentos en que operar costaba caro de verdad. **Eso vuelve el
    backtest OPTIMISTA, no conservador.** Refuerza la tercera vía (`max(nativo, calibrado)`).
    Queda a decisión del user; no se aplicó nada por iniciativa propia.

- **2026-08-12** · Opus 5 · 🔴 **ANÁLISIS DE FIABILIDAD, a petición del user tras el backtest
  largo: "¿de qué datos fiarnos? para eso era el gate de paridad".** Conclusión: **la puerta de
  paridad funcionó correctamente y no podía haber detectado esto**, y el gate que sí lo detectaría
  **nunca ha corrido**. Nuevo bloqueo **B12**.
  (a) **Qué mide realmente la puerta de paridad (D-22).** Re-corre S6/S7/ST sobre el **mismo corte
  de sustrato** con que se congeló la línea base y compara **posición a posición** contra los JSON
  de `T0.6-baseline/`. Es un **detector de regresión del motor contra sí mismo**: responde "¿cambió
  el motor su salida?". Estuvo verde todo el tiempo — **correctamente**, porque el motor no
  cambió. Lo que se rompió cae **fuera de su alcance por construcción**: el **sustrato** (el spread
  de AVA cambió de régimen en 2025) y la **premisa del modelo de costes** (D-21 asumía AVA
  siempre más angosto). Ninguna prueba de paridad puede detectar eso: compararía el error consigo
  mismo y saldría verde.
  (b) **El gate que responde "¿son fiables estos números?" es A6 (T0.7), y está `[ ]`.** No
  fallamos un gate: **generamos números antes del gate**, que fue una decisión declarada y
  consciente (brújula del user: "ver S6 y ST en backtest largo cuanto antes... no pide saltarse
  A6"). El backtest largo es legítimo como **instrumento de diagnóstico**; no lo es como veredicto,
  y así quedó escrito en `F0-BT-LARGO-0001`.
  (c) 🔴 **Y al ir a medir A6 apareció el hallazgo duro: A6 Pata A NO ES EJECUTABLE HOY.** Las
  barras M15 de Capitaria terminan el **`2026-07-24 16:45`** y la ventana viva de la 902 empieza el
  **`2026-07-27 18:53:30`**: **solape cero**. S6 y SuperTrend son estrategias M15, así que sin
  barras no hay señal y el motor no puede reproducir ninguna de las **152** posiciones reales.
  **A6 no estaba pospuesta: le faltaba el insumo y nadie lo había comprobado.** Ver B12.
  (d) 🟢 **Reparable hoy con material ya probado:** los ticks de Capitaria cubren la ventana entera
  (T0.4), y `build_bars_ava.py` ya deriva barras M15 desde ticks para AVA. Falta su gemelo para
  Capitaria en `2026-07-27`→`2026-08-11`.
  (e) ⚠️ **Aviso de higiene:** `backtest.py:466-468` tiene constantes `LIVE` hardcodeadas
  (`S6-K2P0: (69, 114348.06)`, `SuperTrend: (5, 122249.30)`…) de un informe del **2026-07-25** con
  otro alcance. **No son las cifras de la 902** (que son 84 y 68 posiciones, netos +9.272.144 y
  +5.930.966 CLP, fila `F0-INFRA-0025`). Nadie debe leerlas como medición de fidelidad.

- **2026-08-12** · Sonnet 5 impl. + Opus 5 corrección/corrida/interpretación · 🔴 **PASO 3b HECHO:
  EL BACKTEST LARGO EXISTE. S6 y SuperTrend sobre 3,5 años de AVA.** Fila `F0-BT-LARGO-0001`.
  🔴 **NO ES UN VEREDICTO: A6 (T0.7) es el gate y sigue abierto.**
  (a) **Cómo se hizo, sin violar R1-bis:** `scripts/research/backtest_largo_ava.py` subclasea
  `bt.Ticks` y sobrescribe **solo `_load`** —único método que toca disco— para servir ticks de AVA
  con el overlay aplicado. `first_at`, `range` y `_candidates` se heredan byte-idénticos.
  `backtest.py` **no se toca**. Barras: 85.101 → **31.731** tras ventana periodizada → **31.700**
  tras exclusiones D-33. Holdout de AVA 2023 verificado en los dos extremos. 208,0 s en primer
  plano.
  (b) 🔴 **D-38 — el user resolvió una ambigüedad de D-21 y la consecuencia es enorme.** Los ticks
  cuyo spread nativo ya supera al calibrado se declaran **no evaluables** y se retiran. Un
  subagente había estimado "~0,016 %" midiendo **un solo mes de 2022**; medido sobre el sustrato
  entero son **16.549.795 ticks**, y **concentrados**: 14.059 en 2022 · 125.105 en 2024 ·
  **5.941.924 en 2025** · **10.468.707 en 2026**. Es un **cambio de régimen del feed de AVA desde
  2025**, no outliers dispersos — y cae justo en el tramo del solape con Capitaria que A6 Pata B
  necesita. Con la regla rechazada S6 daba 117,4 MM y ST 168,6 MM; con la del user dan **84,9 MM**
  y **19,4 MM**: **SuperTrend cae un 88 % por una sola decisión de tratamiento de datos.**
  (c) **Resultados, modo `mediana`** (`media` difiere <1 %, coherente con el spread bimodal):

  | Estrategia | n | Neto CLP | WR | PF | Meses + |
  |---|---:|---:|---:|---:|---:|
  | S6-K2P0 | 4.578 | 84.913.485 | 33,2 % | **1,051** | **51,2 %** |
  | SuperTrend-p14x3-M15 | 1.617 | 19.380.203 | 22,0 % | **1,029** | **51,2 %** |
  | *(S7-TPNONE, no reportada)* | 5.364 | 143.613.155 | 34,3 % | 1,102 | — |

  (d) 🔴 **Las dos FALLAN el umbral que el propio user fijó en D-35 (B4): 51,2 % de meses
  positivos frente al ≥55 % exigido.** Es el primer gate de la puerta estadística y lo fallan las
  dos, antes incluso de correr bootstrap por bloques y PBO.
  (e) 🔴 **Concentración extrema:** en ambas, los **tres mejores meses aportan ~263 % del neto** —
  sin ellos las dos quedan en negativo. Y no hay estabilidad temporal: S6 pierde **107,1 MM en
  2025** y gana **171,0 MM en 2026**; SuperTrend gana en 2024-2025 y pierde en 2022 y 2026.
  (f) 🟠 **S7-TPNONE, descartada por D-06 sobre Capitaria (PF 0,968), sale aquí con el neto MÁS
  ALTO de las tres.** Otro sustrato y otro periodo, así que no revoca el descarte — pero exige
  revisarlo antes de darlo por cerrado.

- **2026-08-12** · Sonnet 5 impl. + Opus 5 verif. · **PASO 3a HECHO: el overlay de costes consume
  la ventana PERIODIZADA — el backtest largo queda desbloqueado.** Filas `F0-INFRA-0034` y
  `F0-DATA-AVA-0008` (retroactiva).
  (a) 🔴 **Bloqueo encontrado por el controlador leyendo el código, no reportado por nadie:**
  `cost_overlay.py` y `calibracion_costes_capitaria.py` estaban cableados a la ventana **fija** de
  8 horas de D-34 (`18..23, 0, 1`) y `calibracion.json` cubría exactamente esas. Con la ventana
  periodizada, el cierre `03:00` mete **la hora 2 de NY dentro de ventana** y `spread_calibrado`
  **lanzaba `KeyError`**: el backtest largo habría reventado — o, si alguien capturase la
  excepción, se habría saltado la hora 2 **en silencio**.
  (b) **Arreglo:** el predicado pasa de `in_ny_window` (fijo) a `ventana_calendario.in_ventana`
  (fechado), y las horas se derivan de `horas_calendario(calendario)` en vez de una tupla literal.
  Horas cubiertas ahora **`[0,1,2,18,19,20,21,22,23]`** — la 2 y ninguna más (`03:15` canonicaliza
  a hora entera `3`, y `hora < cierre` es estricto).
  (c) 🟢 **El punto delicado quedó resuelto por construcción, no por conteo final:** la hora 2 se
  calibra **solo** sobre ticks cuya fecha cae en un periodo de cierre `03:00`. Calibrarla sobre
  todos sus ticks habría mezclado régimen estrecho y ancho e inflado el coste. El número lo
  confirma: la hora 2 es la **más limpia** del conjunto (std `0,0074`, sin cola hacia `0,60`),
  coherente con estar en pleno centro de la ventana donde aplica. La **hora 18** es la más sucia
  (std `0,0386`, `p95 = 0,60`), consistente con el gap de apertura de mercado.
  (d) **Aritmética que cuadra y valida el instrumento:** las 9 horas suman **10.528.975** ticks,
  exactamente `n_ticks_dentro_ventana`, y la hora 2 (**739.530**) es exactamente el incremento
  sobre el total de 8 horas (**9.789.445**). Como la apertura `18:00` es constante en los 4
  periodos, el predicado fijo y el fechado **solo pueden diferir en la hora 2** — y difieren en
  eso y nada más.
  (e) **Verificado por el controlador** re-corriendo en primer plano: `tests/research`
  **255 passed** (245 + 10) + 4 desel · `tests/analysis` **88** · paridad D-22 **`4 passed`** ·
  `test_ventana_calendario.py` **15 passed sin editarlo**. `git diff --stat` **vacío** sobre
  `backtest.py`, `ny_window.py`, `ventana_calendario.py` y su test (R1-bis).
  (f) ⚠️ **Corrección del controlador:** el docstring de `cost_overlay.py` afirmaba que el módulo
  no lee disco, y con `_hours_ventana_calendario` pasó a ser **falso**. Reescrito para declarar
  las dos lecturas. Prosa desactualizada es deuda (§A.9).
  (g) 🟢 **Fila retroactiva `F0-DATA-AVA-0008`:** `build_bars_ava.py` estaba commiteado
  (`335f512`) **sin fila de LEDGER**, así que por D-17 las barras M15 de AVA **no eran citables** —
  y son el sustrato del backtest largo. Verificadas leyendo el parquet: **85.101 barras**,
  `2022-01-02` → `2026-08-12`, y **2023 con 0 barras**: el holdout acto 2 queda sellado **por
  construcción del propio fichero**, no por la disciplina de quien corra el backtest.

- **2026-08-12** · Sonnet 5 impl. + Opus 5 verif. · **PASO 2c HECHO: cierre del calendario
  CANONICALIZADO — T0.13 queda cerrada y el backtest largo está desbloqueado.** D-37 (ruling del
  controlador, revocable por el user). Fila `F0-INFRA-0033`.
  (a) **La clave de agrupamiento pasa a ser la tupla `(es_verano_chile, es_verano_ny)`**, ambos
  componentes derivados del `utcoffset()` de `zoneinfo` — **sin ninguna fecha de transición
  hardcodeada**, para que la regla siga siendo correcta si el script se re-corre en otro año.
  **11 periodos → 4**, con `cierre_ny` `02:00 · 02:00 · 03:00 · 03:15`: dos valores estructurales.
  (b) 🔴 **Un error real, detectado por el controlador leyendo el JSON crudo y corregido ANTES de
  commitear.** La primera versión del agente agrupaba solo por el DST de Chile. Eso es correcto para
  `cierre_ny`, pero mezcla en un mismo periodo semanas cuya **proyección** a UTC y a hora de
  servidor difiere, porque el DST estadounidense cae en otra fecha: el periodo 1 publicaba
  `UTC 23:00→07:00` para 14 semanas de las cuales **5 medían `06:00`** (y 6 discrepaban en la
  apertura). Degradación silenciosa (§A.13) que **`ventana_calendario.py` nunca habría detectado**,
  porque solo consume `apertura_ny`/`cierre_ny`. Con la tupla, los discrepantes caen a 2/10 y 1/4, y
  el único que queda en el periodo 2 es **la propia semana contaminada `2026-03-08`**, absorbida por
  moda dentro de su grupo en vez de fabricar un periodo propio — que era justo el objetivo.
  (c) **Verificado por el controlador, re-corriendo todo en primer plano:** `tests/research`
  **245 passed** (219 + 26 nuevos) + 4 deselected · `tests/analysis` **88 passed** · paridad D-22
  **`4 passed`** · `test_ventana_calendario.py` **15 passed sin haberlo editado**. `git diff --stat`
  **vacío** sobre `ny_window.py`, `ventana_calendario.py`, su test y `backtest.py` (R1-bis).
  (d) ⚠️ **Incidencia de proceso, segunda vez la misma:** el agente volvió a lanzar la medición en
  background pese a la prohibición escrita en el brief, y su proceso murió sin escribir el artefacto.
  El controlador la relanzó en primer plano: **6 min 41 s**, holgadamente dentro del timeout de 10
  minutos de una llamada en foreground. El background nunca fue necesario.
  (e) 🟠 **Residuo declarado:** desde el `2026-04-26` la mayoría de semanas mide `03:15` y no
  `03:00` — el periodo 3 empata **exacto 3-3** y se resuelve por desempate a hora en punto. Podría
  ser corrimiento real del cierre, no jitter. **Inmaterial** para el backtest (hora entera → `3` en
  ambos casos); anotado por si A6 Pata B lo hace visible.

- **2026-08-12** · Sonnet 5 impl. + Opus 5 verif. · **PASO 2b HECHO: el calendario de ventana por
  periodos existe (`bc19867`), y trae un problema de sobre-fragmentación que hay que resolver antes
  de usarlo.** Fila `F0-INFRA-0032`. ✅ **Resuelto el mismo día por D-37 — ver la entrada de arriba.**
  (a) **Verificado por el controlador:** `backtest.py` **intacto** y `ny_window.py` **intacto**
  (último commit suyo `f537646`, anterior — el agente respetó la orden de no tocarlo y construyó un
  módulo nuevo); `tests/research` **219 passed** (204+15) + 4 deselected; **paridad `4 passed` antes
  y después**. Medición sobre **34.004.053 ticks**, 23 semanas, los dos tramos fuera del holdout.
  (b) 🟢 **La propiedad que define la tarea está verificada en el módulo:** `2026-04-05 → (18, 2)` y
  `2026-04-06 → (18, 3)`. El cruce cae donde D-34 lo había medido.
  (c) 🔴 **PROBLEMA ABIERTO — el calendario sale con 11 periodos en 7 meses, y eso no es un horario
  de bróker: es ruido de medición.** Los cierres emitidos son `02:15 · 02:00 · 02:15 · 02:00 ·
  03:00 · 02:00 · 03:00 · 03:15 · 03:15 · 03:00 · 03:15`. El jitter de ±15 min proviene de cruzar
  el 50 % a resolución de 15 min, y **la semana `2026-03-08→03-13` mide `03:00` aislada entre dos
  periodos de `02:00`** — es justo la semana del DST estadounidense, que en la medición anterior
  (D-34) salía al **63,5 %**, o sea por debajo de cualquier umbral limpio. **Aplicar los 11 periodos
  al backtest largo codificaría ruido como si fuera señal.**
  🟢 **La señal estructural sí está y es la de D-34:** cierre `02:00/02:15` **antes** del 5-abr y
  `03:00/03:15` **después**. El agente reportó los 11 periodos sin interpretarlos, que es lo que se
  le pidió, y **ya canonicalizó la apertura a 18:00** conservando el jitter crudo en
  `bordes_por_semana` para auditoría.
  🔴 **PENDIENTE PARA LA SIGUIENTE SESIÓN, antes del backtest largo:** aplicar al **cierre** el mismo
  tratamiento que ya recibió la apertura — canonicalizar a los **dos periodos estructuralmente
  respaldados** (`02:00` hasta `2026-04-05`, `03:00` desde `2026-04-06`), conservando la medición
  cruda por semana en el JSON. Es un pase de canonicalización pequeño; el módulo y los tests están
  bien y no se tocan.

- **2026-08-12** · Sonnet 5 impl. + Opus 5 verif. · **PASO 2a HECHO: overlay de costes de AVA
  (`ae3574a`), que es la modificación de motor #10.** Fila `F0-INFRA-0031`.
  (a) **Verificado por el controlador contra artefactos crudos:** `backtest.py` **intacto**;
  `tests/research` **204 passed** (181+23) + 4 deselected; **paridad D-22 `4 passed` antes y
  después**. Regla del overlay leída en el código y confirmada: **conserva el mid de AVA y sustituye
  la anchura por la calibrada** (`bid'=mid−s/2`, `ask'=mid+s/2`) — precios de AVA, costes de
  Capitaria, que es literalmente D-21.
  (b) 🟢 **Hallazgo medido: dentro de la ventana NY el spread de Capitaria toma EXACTAMENTE DOS
  valores discretos** — `0,50` (**95,7717 %**) y `0,60` (**4,2283 %**), sobre 9.789.445 ticks. No es
  un continuo. **Confirma sobre el sustrato la bimodalidad que llevaba tiempo registrada como
  observación y nunca se había medido.** Mediana = p25 = p75 = p95 = `0,50` en las 8 horas; solo la
  hora 18 tiene p95 = 0,60 y una std bastante mayor (0,0386 contra 0,011-0,020 del resto).
  (c) **Consecuencia de diseño (controlador):** el gate vivo es `abs(sp−0.5)<=0.05`, que **excluye
  0,60** — en vivo solo se opera a 0,50, luego el modo `mediana` **no subestima el coste: reproduce
  la conducta viva**. 🟠 **Aproximación declarada:** sobre AVA se usa el filtro de ventana en lugar
  del gate de spread, así que se operará también en ese 4,2283 % del tiempo de ventana en que
  Capitaria estaba a 0,60, y ahí `mediana` sí subestima. Se hace constar además que **`p75` coincide
  con la mediana en 7 de las 8 horas y por tanto NO es el modo conservador** que su nombre sugiere;
  el contraste útil de sensibilidad es `media` (0,504228) o forzar 0,60.
  (d) **Anomalía de entorno aclarada, y no era del agente:** `tests/analysis` dio **88** y no 97. La
  causa fue el renombrado de `tests/analysis/test_bar_fill.py` a `.OBSOLETO` que hizo **el
  controlador** (D-35 punto 4) mientras el agente trabajaba. El agente lo detectó, lo declaró fuera
  de su alcance y **no lo tocó** — conducta correcta. 🔴 **NUEVA LÍNEA BASE: `tests/analysis` = 88.**

- **2026-08-12** · User + Opus 5 controlador · **B3 y B4 CERRADOS, umbrales de A6 Pata B fijados, y
  el borde de la ventana REVOCADO por el user.** Ver **D-35** y **D-36**. (a) **B3:** matriz de
  indicadores **completa** (plan §5.2) — desbloquea el motor mod #11 → A0. (b) **B4:** umbrales
  medios (≥55 % meses positivos · bootstrap por bloques 95 % excluyendo 0 · PBO < 0,5). (c) **A6
  Pata B:** ≥90 % de entradas dentro de ±1 barra M15 · neto ≤25 % · ≥70 % de meses con el mismo
  signo, **fijados antes de correr** como exige D-24, y con la condición añadida por el user de
  **reportar la divergencia real como cifra exacta**, no solo el veredicto. (d) 🔴 **D-36 revoca el
  punto 3 de D-34:** el borde conservador fijo se sustituye por un **calendario de periodos medido**
  ("lo que sea correcto según periodos y cambios de horario para Chile respecto al mercado"). Lo
  medido lo respalda: **ningún reloj deja el cierre constante** — en NY salta con el DST chileno, en
  hora de servidor con el estadounidense, y cada uno lo explica con un salto distinto; luego la
  regla correcta es fechada, no un offset fijo. 🔴 **Limitación declarada por adelantado:** Capitaria
  solo cubre desde `2026-01`, así que el calendario **se mide en 2026 y se extrapola** a 2022-2025
  de AVA, donde no hay gate observable. La apertura (18:00 ET = Globex) es la parte sólida por ser
  ancla de mercado; **el cierre extrapolado es la parte frágil**, y así debe figurar en todo
  artefacto del backtest largo. (e) **Higiene ejecutada:** borrados los 3 artefactos del `2026-08-02`
  en `data/analysis/2883016902/` (convivían con los de T0.5 del 11-ago y podían leerse como si lo
  fueran); `bar_fill.py` / `test_bar_fill.py` renombrados a `.OBSOLETO` (nunca estuvieron en git;
  premisa muerta al cerrarse B9).

- **2026-08-12** · Sonnet 5 impl. + Opus 5 verif. · **PASO 1 HECHO: el filtro de ventana NY existe
  (`f537646`), y su validación destapó que el spec de T0.13 estaba incompleto.** Ver **D-34**.
  (a) **Verificado por el controlador contra artefactos crudos, no contra el reporte:** `backtest.py`
  **sin tocar** (último commit suyo `4bb0fc4`, anterior); `tests/research` **181 passed** (164→181,
  17 nuevos) + 4 deselected; `tests/analysis` **97 passed**; **paridad D-22 `4 passed` antes Y
  después**, re-corrida por el controlador. Módulo `scripts/research/ny_window.py` leído línea a
  línea: la cadena de reloj es la correcta (`utcfromtimestamp` → adjuntar tz del bróker → NY), la
  condición es la **disyunción** y no un rango, y el `fold=0` está justificado.
  (b) 🟢 **El implementador PARÓ y escaló donde debía.** El brief le ordenaba parar si la validación
  divergía en los cruces de DST; divergió, y **no diagnosticó**. Tercer caso del programa en que un
  implementador escala en vez de resolver por su cuenta, y el primero en que la instrucción de
  parada estaba escrita de antemano en el brief.
  (c) **Diagnóstico del controlador (D-14: la interpretación no se delega). La apertura está
  CONFIRMADA en `18:00` NY** — es el único de los tres relojes candidatos que la mantiene estable
  (NY 1 valor dominante en 20 semanas; UTC 4; servidor 6). **El cierre NO está anclado a NY:** la
  hora `02:00` ET pasa de 9,5 % / 7,9 % de estado estrecho a **99,9 % desde el 6-abr**, saltando con
  el **fin del DST chileno**, no el estadounidense. En hora de servidor el cierre se estabiliza en
  `03:00` y atraviesa ese DST sin moverse: es un horario del lado del bróker.
  (d) **Decisión D-34: se adopta el borde conservador `18:00→02:00` ET.** Es subconjunto estricto
  del tiempo operable — sesga en contra del sistema, nunca a favor — y es el que reproduce la
  conducta viva, porque el gate de spread en esa hora no se abre. Coste declarado, no silencioso:
  desde el 6-abr se descarta ≈1 h/día operable. **La hora en disputa entra como variante de grilla
  en D3**, donde se mide en vez de suponerse. El código no se toca: lo incompleto era el spec.

- **2026-08-12** · Opus 5 controlador · **B11 CERRADO por exclusión (D-33). El problema era 4×
  menor de lo temido, y la razón es T0.13.** Instrucción del user: dejar fuera los huecos en vez de
  repararlos, para avanzar. Es reducción de alcance y la autoriza él por escrito (§A.13); se
  registra como **D-33**. (a) **Lo que se elimina:** clasificación contra calendario de festivos y
  relleno desde Capitaria. **Lo que se conserva:** la localización — no se puede excluir lo que no
  se ha ubicado, y es la parte barata (solo `t_msc`, holdout-safe por D-31). Artefacto
  `04-resultados/T0.3-continuidad/huecos_intradia_ava.py` → informe + **`exclusiones-ava.json`**,
  la lista de intervalos que consumirá el backtest largo. Fila `F0-DATA-AVA-0007`.
  (b) 🟢 **El hallazgo que reduce el problema: la ventana operativa lo absorbe.** De **344,1 h** de
  hueco total, solo **97,7 h** caen dentro de `18:00→02:00` NY; las otras **246,4 h están en zona
  muerta**, donde el sistema no opera, y por tanto no afectan a ningún backtest. Es la primera
  consecuencia práctica de T0.13 más allá del propio filtro.
  (c) 🟢 **El holdout queda prácticamente intacto:** sus 2 huecos suman 15,3 h pero solo **0,1 h**
  dentro de la ventana. El sello no se degrada.
  (d) 🔴 **Pero la sospecha que motivó B11 se confirma: el promedio escondía concentración.** De las
  97,7 h en ventana, **49,3 h — la mitad — caen en el solape con Capitaria**, y ahí `2026-01` pierde
  **29,1 h ≈ 17 % de su mes** y `2026-02` **14,0 h ≈ 9 %**, contra ≈5 % del resto. Por eso D-33
  **exige columna de cobertura en la tabla mensual de BL-0**: excluir sin declararlo convertiría un
  mes mutilado en un mes normal con menos operaciones, y el desglose mensual es precisamente una
  comparación entre meses. Sin esa columna, la exclusión sería degradación silenciosa (§A.13).
  (e) 🔴 **Corrección de un número que yo mismo registré ayer: eran 56 huecos / 344,1 h, no 53 /
  306,9 h.** La diferencia son exactamente **3 huecos que cruzan frontera de mes** (25,0 + 7,5 +
  4,6 = 37,1 h): el barrido anterior procesaba cada parquet mensual aislado y **no encadenaba el
  último tick de un mes con el primero del siguiente**. 53+3=56 y 306,9+37,1=344,0 ≈ 344,1 — la
  discrepancia queda **completamente explicada**, y el hecho de que cuadre al decimal es lo que
  valida el instrumento nuevo. El tercero de esos huecos es el **artefacto de reloj ya declarado**
  en B9 (julio arranca a las 04:00), no un corte del feed. **Es el mismo modo de fallo que ya costó
  cinco errores al programa: medir sobre una partición y olvidar las costuras.**

- **2026-08-12** · Opus 5 controlador · **PASO 0 — la primera tabla de números reales queda con su
  semántica establecida ANTES de propagarse a 3,5 años. Dos preguntas del user, tres hallazgos.**
  Todo leído en el código y medido sobre los artefactos crudos, nunca deducido. Cuerpo completo en
  **D-32**; artefacto `04-resultados/T0.6-baseline/semantica_metricas.py` →
  `semantica-metricas.txt`; filas `F0-INFRA-0028` y `F0-INFRA-0029`.
  (a) **`maxDD`: las dos hipótesis del user eran ciertas a la vez.** Es pico-a-valle del **P&L
  cerrado** (`backtest.py:423-427`, ordenado por `t_exit`) **y** el simulador **no impone margen ni
  margin call** — cero `equity`/`balance`/`margin_call`/`free_margin`/`liquidat`/`capital` en todo
  `scripts/analysis/realtick_bt/`; `margin1` se calcula y se reporta, pero ninguna apertura se
  rechaza. Los 73,8 MM sobre "una cuenta de 50 MM" no son imposibles: **en el simulador no existe
  la cuenta.** 🔴 Y el número **subestima** el riesgo: al excluir el flotante es **cota inferior**
  del drawdown de equity, que queda **NO EVALUABLE** hasta la modificación de motor **#11**
  (MFE/MAE). `maxDD` y `peak_margin` quedan **prohibidos** como criterio de aprobación o descarte.
  (b) **El margen idéntico al céntimo no es un tope, ni agregación a nivel de cuenta, ni un error de
  contabilidad cruzada** — las tres explicaciones que el user enumeró quedan descartadas por
  medición. `peak_margin` se calcula **por estrategia**, y **S6 y S7 abren las mismas posiciones**:
  las **211 entradas de S6 están las 211 en S7** (S7 tiene 28 más), 3 fichas por instante al mismo
  precio, y el pico cae en ambas en `2026-02-26 00:15:00` con las mismas 6 filas. Confirma
  empíricamente el supuesto del plan §7.A5: **misma señal, distintas salidas.**
  (c) 🔴 **Hallazgo no buscado, y corrige una cifra que yo mismo escribí ayer: la concurrencia de 6
  es un artefacto del desempate.** `backtest.py:404` ordena por `(t, -delta)`, luego a igual
  timestamp las **aperturas cuentan antes que los cierres**; un `stop_and_reverse` cierra 3 y abre 3
  **en el mismo segundo**, y el pico de S6 y de S7 cae **exactamente** en uno de esos instantes (23
  y 12 solapes). Margen **sostenido** = **10.402.061,93** en ambas, con **máximo 3 simultáneas** —
  la escalera, constante. **ROM corregido: S6 238,34 % · S7 −106,44 % · ST 1.199,74 %** (ST idéntico
  bajo los dos desempates: no tiene reverses). **La cifra "≈7,8 simultáneas" que escribí ayer queda
  ANULADA.** `backtest.py` **no se corrige** (R1-bis + motor congelado + instrucción explícita del
  user): con cuenta *hedging* el desempate del harness es la lectura peor-caso instantánea y es
  defendible; lo prohibido es usarlo como denominador de ROM como si fuera capital sostenido.
  (d) 🔴 **Tercer hallazgo, de gobierno: la línea base de `bd17f60` no tenía fila en el LEDGER.**
  `baseline_golden.py` no es un runner y no escribe al registro, así que por la regla derivada de
  **D-17** ninguno de esos números era citable — incluidos los que el user acaba de pedirme
  interpretar. Corregido con la fila retroactiva `F0-INFRA-0028`, con `git_sha bd17f60` verificado
  con `git show --stat` (los cuatro artefactos están en ese commit). **Lección de proceso: el
  registro solo es automático cuando el ejecutor es el runner; todo driver ad-hoc lo deja huérfano
  en silencio.**
  (e) **Advertencia vinculante escrita junto a los números**, no solo en un memo: ver el bloque
  🔴🔴 en la entrada de bitácora de abajo. **Lo único concluyente de esa tabla es S7 en negativo**
  (PF 0,968), que por **D-06** basta para descartarla sin compararla con nada.

- **2026-08-12** · Opus 5 controlador · **T0.6 Tarea 0 construida, y T0.13 resuelta por el camino.
  Primeros números reales de S6/ST del programa.** (a) **Linea base golden + puerta de paridad**
  (`bd17f60`): `scripts/research/baseline_golden.py` congela 1.503 posiciones de S6/S7/ST sobre
  Capitaria pre-holdout. R1-bis intacto — no toca `backtest.py` ni las estrategias; solo filtra la
  lista de barras antes de `build_all()`, que ya la recibe como argumento. Doble guarda de holdout:
  corta en `2026-05-12` **y** aborta si alguna posición resuelta cayera dentro del sello.
  Determinismo probado con hashes SHA-256 en dos corridas. El test se **verificó por mutación** (una
  deriva de 1e-7 en 1 de 633 posiciones lo pone rojo y nombra estrategia, índice y clave; S7 y ST
  siguen verdes): un test que solo se ha visto pasar no está verificado. `tests/research` 164
  passed, sin cambios. **Resultados (lot 0,67, ticks reales, holdout excluido, DESCRIPTIVOS y NO
  veredictos — es la config del harness, no la VIVA):** ST +41.254.539 CLP / PF 1,457 / 153 pos ·
  S6 +24.792.629 / PF 1,068 / 633 pos · S7 −11.072.071 / PF 0,968 / 717 pos. 🟢 **`peak_margin`
  cuantifica la cuarentena §2.1:** ST pica 3,4 MM (≈1 posición a la vez, como en vivo), S6 y S7
  pican 19,5 MM (~~**≈7,8 simultáneas**~~, la escalera del ladder) — el S6 del backtest **no es** el S6
  de la 902. ROM: ST 1.199,7 % contra S6 127,0 %.
  🔴🔴 **ADVERTENCIA VINCULANTE — VA PEGADA A ESTA TABLA DONDEQUIERA QUE APAREZCA (D-32,
  2026-08-12). ESTA TABLA NO ES UN RANKING ENTRE ESTRATEGIAS Y NO DEBE LEERSE COMO TAL.**
  (a) **`maxDD` no mide supervivencia.** Es pico-a-valle del **P&L cerrado** (`backtest.py:423-427`)
  y el simulador **no impone margen ni margin call** (cero `equity`/`balance`/`margin_call` en todo
  `realtick_bt`; `margin1` se reporta, nunca bloquea una apertura). Los 73,8 MM de S6 "sobre una
  cuenta de 50 MM" no son imposibles: **en el simulador no existe la cuenta.** Además **excluye el
  flotante**, luego es **cota inferior** del drawdown de equity — el drawdown real es NO EVALUABLE
  hasta la modificación de motor #11 (MFE/MAE). 🔴 **`maxDD` y `peak_margin` quedan PROHIBIDOS como
  criterio para aprobar o descartar cualquier config.**
  (b) **El ROM de ST (1.199,7 %) frente al de S6 es casi enteramente artefacto de la concurrencia**,
  no una medida de calidad relativa: una posición contra la escalera de 3 fichas. El S6 del backtest
  no es el S6 de la 902, y **por eso mismo tampoco es comparable con el SuperTrend de este mismo
  backtest**.
  (c) 🔴 **Cifras corregidas por medición (D-32):** la concurrencia máxima real es **3**, no 7,8 —
  el "≈7,8" queda **anulado**. Los 19,5 MM son el pico **instantáneo** en un `stop_and_reverse`
  (`backtest.py:404` cuenta las aperturas antes que los cierres al mismo timestamp, y el pico de S6
  y de S7 cae exactamente en uno de esos instantes). Margen **sostenido** = **10.402.061,93** en
  ambas. **ROM corregido: S6 238,34 % · S7 −106,44 % · ST 1.199,74 %** (ST sin cambio, no tiene
  reverses). S6 y S7 coinciden **al céntimo** porque **abren las mismas posiciones**: las 211
  entradas de S6 están las 211 en S7, misma señal y distintas salidas.
  (d) 🟢 **Lo único que es señal limpia en esta tabla es S7 en negativo** (neto −11,07 MM, PF 0,968):
  por **D-2026-08-10-b / D-06** ("ganadora = neto positivo", no "mejor que S6/ST"), eso basta para
  descartarla **sin compararla con nada**. Es el único uso legítimo de la tabla hoy. (b) **Velas M15 de AVA** (`335f512`) derivadas de
  los ticks, 85.101 velas, 2023 excluido **del fichero** (el sello no depende de la disciplina de
  quien corra después) y destino fuera del lago de ticks para no repetir la trampa del sidecar.
  (c) 🔴 **Dos hipótesis del orquestador REFUTADAS con datos, no con argumentos.** Primera: correr
  el harness tal cual sobre AVA daría ~0 posiciones en 2022 y 2024 — el gate `abs(sp−0.5)<=0.05`
  solo lo pasa el 0,047 % / 0,430 % de los ticks de esos años, y el desglose mensual habría
  parecido decir "las estrategias dejaron de funcionar" cuando la puerta no se abrió nunca.
  Segunda, propuesta por el user y por el controlador: que el gate fuera un filtro de
  liquidez/volumen. **Es al revés y es monótono:** el estado que deja operar tiene volumen mediano
  2.496 contra 3.336 del que no (0,75×), y por deciles de volumen el % en estado estrecho baja
  62,6 → 13,9 sin una sola inversión. Capitaria **ensancha** el spread cuando hay actividad. Solape
  con un umbral de volumen equivalente: 23,2 % — demasiado flojo para sustituir nada. Va a
  `NEGATIVOS.md`. (d) 🟢 **Lo que sí resultó ser: T0.13.** Ver la fila T0.13 — la ventana es
  `18:00→02:00 ET` todo el año (CME Globex), los saltos caen en los DST exactos, y los relojes de
  servidor quedaron **medidos** con el corte de CME como ancla: AVA = UTC fijo, Capitaria = Chile
  con DST. (e) **Instrucción del user registrada:** el filtro horario **no se quita** — el edge
  aparecía exclusivamente en esa franja acotada. La propuesta previa del controlador de correr "sin
  gate" queda **retirada**.

- **2026-08-12** · Opus 5 controlador · **B9 CERRADO y holdout SELLADO en la misma sesión. La
  pregunta que D-30 mandaba responder leyendo el código tenía la respuesta buena: no había que
  tocar nada.** (a) **Verificación previa, no asunción.** D-30 ordenaba leer
  `scripts/research/runner/tasks_ticks.py` antes de escribir código, por si su guard ya admitía un
  login declarado en el manifiesto. Lo admite: `expected_login`, `expected_server` y
  `logins_sancionados` son campos del manifiesto **sin default** (L179-182, `KeyError` si faltan) y
  el módulo **no importa** `guard_cuenta` ni `extract_ticks` (imports L63-75). Declarar la demo de
  AVA en un manifiesto nuevo **no amplía ninguna autoridad de orden**: `guard_cuenta.py` y
  `extract_ticks.py:34` quedan byte-idénticos, como exigen D-30 y el precedente D-28. **Cero líneas
  de código escritas para cerrar B9.** (b) 🔴 **Hallazgo que habría hecho fracasar la corrida en
  silencio.** El TRACKER registraba la idempotencia como *"por presencia de `<YYYYMM>.parquet`"* —
  cierto para `ticks_csv_mt5`, **falso para `ticks_mt5`**, que sí redescarga el mes entero con
  sobrescritura segura. Pero su criterio de completitud es un chequeo de **cola**
  (`fin_de_mes − max(t_msc) <= tolerancia`): medido sobre los parquet reales, `202607` tenía una
  cola de **3,0 h** y por tanto se habría considerado completo y **saltado en silencio**, pese a
  faltarle sus 13 primeros días hábiles. El predicado detecta una cola truncada y es **ciego a un
  agujero en la cabeza**. Se neutralizó declarando `tolerancia_horas: 1` en el manifiesto (una
  exigencia más estricta, no un rodeo), y el defecto de fondo quedó registrado como **B10** junto a
  otros dos huecos del mismo módulo: no hay guarda anti-destrucción ni guarda de destino. **Lección
  de método, la cuarta del programa en la misma dirección:** el TRACKER describía el
  comportamiento de un task-type usando lo que era cierto de *otro*; solo leer el código lo
  desmintió. (c) **Corrida `T0.3-ava-topup-servidor`** (manifiesto **nuevo**; el CSV original no se
  editó): `F0-DATA-AVA-0004` julio, `0005` febrero, `0006` agosto. Guard de identidad ejercido y
  registrado: `login 101744074, server "Ava-Demo 1-MT5", trade_mode 0, symbol GOLD`. Lago AVA
  **241.000.303 → 246.448.523 ticks** (+5.448.220; la suma de los tres deltas cuadra exacto), 56
  meses, `2022-01-02` → `2026-08-12`. **Julio: 2.707.151 → 6.410.562 ticks, 12 → 27 días, cero días
  hábiles ausentes.** (d) **La verificación que el código no hace, la hizo el controlador:**
  comparación **día a día** de cada mes nuevo contra su `.bak` — **ningún día presente en el `.bak`
  falta en el fichero nuevo**, en los tres meses. 0 `.tmp` residuales, 3 `.bak` conservados.
  (e) **Gate D-29 sobre el lago completo:** **2 días hábiles sin ticks en 4,6 años y los dos son
  huecos declarados** — `2022-04-15` (Viernes Santo) y `2026-02-27` (ausente del feed de AVA,
  probado antes por prueba de flancos; Capitaria sí lo tiene). Artefacto:
  `04-resultados/T0.3-continuidad/continuidad-diaria-ava-2026-08-12.txt`. **Sustrato AVA APTO para
  veredictos.** (f) **Artefacto de reloj declarado, no corregido:** julio arranca
  `2026-07-01 04:00:00.024` porque `copy_ticks_range` interpreta datetimes naive en el reloj del
  host — el mismo desfase de 4 h que ya tiene el `202607` de Capitaria. Se declara en el manifiesto
  y aquí; no se corrige, porque el módulo nunca decodifica `t_msc` a datetime. (g) **T0.12 sellado
  (D-31):** el user aceptó explícitamente la propuesta del acto 1 (Capitaria
  `2026-05-12`→`2026-07-26`) y el acto 2 (AVA, año **2023** completo) pasó a ser fechable en cuanto
  cerró B9. Ambos tramos son intocables desde ya. (h) **Higiene de holdout:** toda la medición de
  esta sesión leyó **solo `t_msc`**, jamás `bid`/`ask`. (i) **Directiva del user registrada:** ver
  S6 y SuperTrend en backtest largo cuanto antes, **con la paridad AVA ↔ Capitaria ↔ posiciones
  reales confirmada primero** — confirma A6 como gate, no lo salta. (j) 🔴 **Auto-corrección en la
  misma sesión, antes de que el error se propagara: nace B11.** El controlador había escrito
  *"sustrato AVA APTO para veredictos"* apoyándose en el gate de D-29. Al revisar los informes de
  integridad del propio top-up aparecieron en `202602` dos huecos de **14,7 h y 20,4 h** — y **la
  continuidad diaria de D-29 no los ve**, porque solo comprueba que el día tenga *algún* tick. Un
  día con un agujero de 15 h pasa el chequeo y es inservible igual. Barrido del lago completo: **53
  huecos intradía, ~306,9 h (≈0,9 %)**. Medido antes de acusar a la descarga: **51 huecos / 271,8 h
  están en los 53 meses que NO se tocaron** y solo 2 / 35,1 h en los tres redescargados, luego el
  top-up no los introdujo. Los mayores son festivos; los de `202601` (65,3 h, el peor mes del lago,
  intacto) y `202602` no lo son. La afirmación de aptitud quedó **rebajada a "apto en continuidad
  diaria, aptitud para veredictos pendiente de B11"**. Es el mismo patrón que ya costó cuatro
  errores al programa —validar un proxy (¿el día existe?) en vez de la cosa (¿el día está
  cubierto?)—, esta vez detectado antes de que ningún experimento se apoyara en él.

- **2026-08-11** · Opus 5 controlador · **Segunda tanda de exportaciones de AVA: 2 de 3 inservibles,
  detectado leyendo los ficheros y no sus nombres.** El user entregó tres CSV. Verificación en
  disco (`sed -n '2p'`, `tail -1`, `cut -f1 | sort -u`): el de **febrero** cubre `2026-02-01`→
  `2026-02-26`, 23 días distintos — aporta el 20 y del 22 al 26, pero **le falta el viernes
  2026-02-27**; ingerirlo dejaría `202602` truncado el 26 en lugar del 19, el mismo defecto
  desplazado. Los de **julio y agosto** son exportaciones de **un solo día** (`2026-07-30` y
  `2026-08-10`), y ambos días **ya están** en el lago (`202607` = 19→31 jul, `202608` = 2→10 ago):
  no aportan nada y, bajo reescritura mensual, **habrían destruido el resto del mes**. Causa
  probable: fechas de inicio y fin iguales en el diálogo de exportación de MT5. Se repitió el
  pedido con fechas explícitamente distintas. **Nada se ingirió**: el reprocesado explícito de mes
  sigue sin implementarse, así que ninguno de estos ficheros era ingerible aunque hubiera servido.
  Que `2026-02-27` es día hábil real está corroborado de forma independiente por el lago de
  Capitaria, cuyo `202602` llega hasta `2026-02-27 17:54`. **Nota de método:** los nombres de estos
  CSV son fiables (MT5 los compone con el primer y último tick), pero el diagnóstico se hizo contra
  el contenido — es la tercera vez en el programa que fiarse de un proxy en vez del dato habría
  metido un error en un artefacto.

- **2026-08-11** · Opus 5 controlador · 🔴 **B9 estaba mal diagnosticado: el agujero era mayor de lo
  registrado, y se descubrió por no fiarse del diagnóstico heredado.** Antes de ingerir el CSV que
  el user re-exportó (`GOLD_202603012305_202606302323.csv`, 1,29 GB), el controlador comprobó los
  **bordes** del hueco leyendo los parquet vecinos: `202602` terminaba el **2026-02-19** y `202607`
  empezaba el **2026-07-19** — o sea que ambos meses **existían pero estaban truncados**, y el
  diagnóstico original de B9 ("faltan los meses 202603..202606"), hecho contando **nombres de
  fichero**, subestimaba el agujero. Auditoría de continuidad a nivel de **día** sobre los 52
  parquet (fila `F0-DATA-AVA-0003`, artefacto en `04-resultados/T0.3-continuidad/`): el hueco real
  era **un único tramo `2026-02-20`→`2026-07-17`, 106 días hábiles**. El resto de los 4,6 años está
  limpio: todos los demás huecos son fines de semana y **un solo día hábil ausente en toda la
  serie**, el `2022-04-15` — Viernes Santo. **Lección de método, la misma que ya costó dos errores
  al programa:** presencia de fichero ≠ completitud de contenido; el chequeo tiene que mirar los
  datos, no el directorio. Es exactamente lo que D-29 exige y lo que el casi-incidente de T0.4 ya
  había enseñado en el lago de Capitaria. **Ingesta ejecutada** (`F0-DATA-AVA-0002`, corrida nueva
  en el manifiesto — la corrida original **no se editó**, su lineage ya estaba en git y en el
  LEDGER): 4 meses escritos, cero `.tmp`/`.bak` residuales, lago a **56 meses / 241.000.303 ticks**
  (209.894.471 + 31.105.832, cuadra exacto). Continuidad re-auditada: **106 días hábiles perdidos →
  20**. 🔴 **Dos hallazgos que bloquean el cierre de B9:** (a) faltan aún `2026-02-20`→`2026-02-27`
  y `2026-07-01`→`2026-07-17`, dentro de meses que **ya existen**; (b) la idempotencia del
  task-type es **por presencia de `<YYYYMM>.parquet`**, así que una re-exportación perfecta de esos
  meses **se saltaría en silencio** y el runner reportaría éxito — se pidieron al user las tres
  exportaciones por **meses completos** (feb, jul, ago) y queda pendiente el reprocesado explícito
  de mes en el ingestor. Un CSV de un solo día (`2026-08-11`) que el user empezó a bajar se
  descartó como insumo aislado: `202608` ya cubre del 2 al 10 de agosto y una reescritura mensual
  desde ese CSV los habría borrado. **Higiene de holdout:** toda la auditoría leyó **solo la
  columna `t_msc`**; en ningún momento se leyeron `bid` ni `ask`, luego no constituye exploración
  del sustrato (charter §A.14). 🟠 **T0.12 acto 1 escalado al user:** el "trimestre más reciente"
  de D-01 contiene la ventana de la 902 que A6 Pata A necesita — el propio ejemplo de D-01
  ("may–jul 2026") la solapa cinco días. Propuesta del controlador: holdout Capitaria
  `2026-05-12`→`2026-07-26`, dejando fuera del sello los 16 días de A6, con el argumento de que el
  holdout protege contra el sobreajuste de **selección de estrategias** y A6 Pata A no selecciona
  nada. Sin resolver: no se sella nada hasta que el user decida.

- **2026-08-11** · Opus 5 controlador · **Verificación independiente del registro del registrador y
  commit del mismo.** Todas las cifras que el registrador escribió se re-derivaron desde los
  artefactos crudos, no desde su reporte: **AVA** 52 parquet / **209.894.471** ticks / 1,638 GB
  leídos con `pyarrow` (coincide exactamente), serie `202201…202602` + `202607…202608` — el hueco
  **202603–202606** confirmado en disco, luego **B9 es real**; cero `.tmp`/`.bak` en el lago AVA.
  **Capitaria**: `202607.parquet` = **10.855.025** ticks frente a `202607.parquet.bak-20260811222730`
  = **8.270.356** → **+2.584.669** exactos; `202608.parquet` = **3.324.988**. **902**: `deals_raw.csv`
  305 líneas / `positions.csv` 153; neto por estrategia **recalculado por el controlador** desde
  `positions.csv` — S6-K2P0 84 cerradas / 0 abiertas / **+9.272.144,35 CLP**, SuperTrend-p14x3-M15
  67 cerradas / 1 abierta / **+5.930.966,98 CLP**, 152 posiciones todas `tanda2`, ventana
  2026-07-27 18:53:30 → 2026-08-11 01:15:04. Los 4 artefactos de corrida del runner existen
  (268 KB, no ignorados) y sus JSON de integridad dan `n_no_monotonicos=0` y `n_bid_ask_invalidos=0`,
  con huecos de ~61 min diarios (cierre diario del XAUUSD) y ~2945–3180 min (fines de semana).
  **Cuatro correcciones del controlador antes de commitear:** (a) las 4 filas marcadas
  `PENDIENTE-ORQUESTADOR` en la columna de ID reciben identificador estable — **T0.3a** (spec del
  feed AVA), **T0.3b** (`ticks_csv_mt5`), **T0.4a** (guard de identidad de `ticks_mt5`), **T0.5a**
  (separación lectura/orden); (b) el **ESTADO EN UNA LÍNEA** llevaba desde el 2026-08-10 diciendo
  "en curso T0.2 y T0.9-min" y "sigue bloqueado B2" — reescrito al estado real; (c) **B7 cerrado**
  en la tabla de bloqueos: D-25 lo resolvió y la fila se había quedado abierta; (d) observación
  nueva al `BACKLOG.md` — las filas del LEDGER escritas por el runner usan separadores de ruta de
  Windows en `artefactos`, contra el `/` de las escritas por agentes; se corrige en el runner, no
  en las filas (append-only).

- **2026-08-11** · Sonnet 5 registrador · **T0.3, T0.4 y T0.5 cierran `[x]` VERIFICADAS; nace el
  bloqueo B9; cierra la observación 3 del backlog.** (a) **T0.3** verificada con salvedad: 52
  meses / 209.894.471 ticks ingeridos correctamente (ida y vuelta de timestamps probada contra la
  fuente, arrastre consistente con `<FLAGS>`, feed AVA confirmado sin volumen), pero **falta el
  tramo 202603-202606** — el CSV de origen no lo trae. Nace **D-29** (continuidad temporal como
  chequeo obligatorio antes de declarar apto cualquier sustrato) y **B9** (sustrato AVA NO apto
  para veredictos hasta re-exportar mar-jun 2026). Fila LEDGER de la ingesta real ya existía,
  escrita por el runner (`F0-DATA-AVA-0001`) — no se duplica. (b) **T0.4** verificada: top-up real
  de Capitaria completado, `202607.parquet` recuperó +2.584.669 ticks del hueco 24→31 jul, cubre
  íntegramente la ventana de la 902. Filas LEDGER ya escritas por el runner (`F0-DATA-0001`,
  `F0-DATA-0002`) — no se duplican. (c) **T0.5** verificada: export de la cuenta 902 vía
  `pull_account_deals.py` con el guard de lectura de D-28, 304 deals / 152 posiciones, balance
  64.646.947,55 CLP. Sin fila LEDGER previa para este experimento — se añade fila nueva
  `F0-INFRA-0025`. (d) **Cierra la observación 3 del backlog** (2026-08-11, faltaba la
  especificación de `XAUUSD` de Capitaria): capturada en solo lectura sobre `2883015767 @
  Capitaria-All` — `digits=2`, `point=0.01`, `trade_contract_size=100.0`, `trade_tick_size=0.01`,
  `trade_tick_value=913.15`, `volume_min/max/step=0.01/10.0/0.01`, `filling_mode=3`, `spread=50`,
  `spread_float=False`, monedas USD/USD/USD, `swap_mode=1`, `swap_long=-65.0`, `swap_short=+30.0`.
  Idéntica a AVA `GOLD` en `digits`/`point`/`trade_contract_size` — dimensionamiento comparable
  entre sustratos sin ajuste. Dos observaciones nuevas al `BACKLOG.md` (spread declarado fijo vs.
  el comportamiento bimodal documentado antes; swap asimétrico largo/corto). Ver cierre formal en
  `BACKLOG.md`. (e) **Dos hechos de proceso registrados, no numéricos:** primero, la validación
  fail-loud del task-type `ticks_csv_mt5` abortó la primera corrida real de T0.3 **en la línea 6**
  del CSV por un error de spec del propio orquestador ("bid/ask en cada fila", generalizado desde 4
  filas de muestra que casualmente tenían `<FLAGS>`=6) — evitó una ingesta de 8,65 GB con el 10,9 %
  de los ticks mal tratados (proporción de `<FLAGS>` distinto de 6 sobre el total de 209.894.471).
  Segundo: este es ya el **tercer caso documentado** del programa en que el orquestador afirma un
  hecho de entorno generalizando desde una muestra insuficiente (los dos anteriores: la existencia
  de `MT5_Tester_2` bajo ENMIENDA E-02, y el formato `<FLAGS>` del CSV de AVA, ambos en la entrada
  de bitácora de más abajo) — las tres veces el error llegó hasta un artefacto antes de detectarse.
  Ninguna operación de git ejecutada por este agente (solo lectura: `git log`, `git status`).
- **2026-08-11** · Sonnet 5 registrador · **Task-type `ticks_csv_mt5` (T0.3, código) y separación de
  autoridad lectura/orden en `pull_account_deals.py` (D-28), ambas VERIFICADAS y registradas.**
  (a) **Aborto de la primera corrida real de T0.3, no del código:** el task-type `ticks_csv_mt5`
  quedó hecho y verificado (commit `f538106`, fila `F0-INFRA-0023`, 156 passed), pero al lanzar la
  ingesta real sobre el CSV de AVA abortó en la **línea 6** por un **error de spec del
  orquestador** — afirmó "bid/ask en cada fila" generalizando desde 4 filas de muestra que
  casualmente tenían `<FLAGS>`=6, cuando la exportación de MT5 deja vacío el lado que no cambió en
  cada tick (`<FLAGS>`: 2=solo bid, 4=solo ask, 6=ambos). La validación fail-loud del implementador
  **lo detuvo en la línea 6 y no tras millones de filas** — es el mecanismo funcionando como debe,
  no un fallo del implementador. Corrección en curso: arrastre del último valor conocido (lo que
  `copy_ticks_range` reconstruye por su cuenta, comparable con el lago de Capitaria), con conteos
  de arrastre y distribución de `<FLAGS>` en las métricas para auditar, y aborto si el vacío
  aparece antes de conocer el primer valor. T0.3 pasa a `[~]` en curso. (b) **Segundo caso del
  programa en que un implementador paró y escaló** en vez de resolver una contradicción de
  seguridad por su cuenta: `pull_account_deals.py` (solo lectura) usaba
  `guard_cuenta.SANCTIONED_DEMO_LOGINS` — una lista de **autoridad de orden**, no de lectura — para
  decidir si podía conectarse a la cuenta 902; añadirla a esa lista habría concedido autoridad de
  operación a una cuenta NO-R&D de solo lectura (charter §A.12). Escalado al user, que decidió
  **D-28**: separar las dos autoridades tocando únicamente la vía de lectura; `guard_cuenta.py`
  queda sin tocar, `pull_account_deals.py` gana gate real de `trade_mode`, coincidencia obligatoria
  de login y servidor, y un test estructural que prueba ausencia de llamadas capaces de operar.
  Commit `f3271ad`, fila `F0-INFRA-0024`, 97 passed, desbloquea T0.5. (c) **Nota de proceso:** el
  orquestador ha cometido **dos veces** el mismo tipo de fallo — afirmar un hecho de entorno
  generalizando desde una muestra insuficiente (la existencia de `MT5_Tester_2`, sección más abajo
  de esta bitácora; y ahora el formato de las filas del CSV de AVA) — y en ambos casos el error
  llegó hasta un artefacto antes de detectarse. Tres observaciones nuevas al `BACKLOG.md` (no
  bloqueantes: `<LAST>`/`<VOLUME>` descartados, criterio de "mes completo" no detecta
  automáticamente un origen sustituido, divergencia de limpieza de `.tmp` entre task-types ante
  aborto). Ninguna operación de git ejecutada por este agente.
- **2026-08-11** · Sonnet 5 registrador · **Registro con retraso de D-25/D-26/D-27** (protocolo de
  revisión de videos vs. máx-2 en paralelo, cierra B7 · holdout en dos actos · verificación
  estructural de artefactos report-only). Se registran tarde porque el despacho original que los
  llevaba fue sustituido por otro flujo — **error de proceso del orquestador**, no de contenido: las
  tres ya estaban decididas y comunicadas, solo faltaba dejarlas escritas en `DECISIONES.md`.
  Búsqueda de referencias erróneas a "D-23" en el contexto de la retirada de B5 / no-ampliación de
  `SANCTIONED_DEMO`: **ninguna encontrada** en `DECISIONES.md`, `TRACKER.md` ni `BACKLOG.md` — las
  dos únicas menciones de "D-23" en el repo son al Baseline Largo (BL-0), correctas, sin tocar.
  **`F0-INFRA-0020` corregida por `supersedes`** (fila `F0-INFRA-0022`): sus métricas (368
  líneas / 17.841 bytes) fueron medidas por el orquestador **antes** de un addendum que añadió al
  artefacto la Sección F (calendario de sesión, no evaluable) y su salida cruda en anexo; medición
  propia del registrador sobre el fichero en disco confirma **840 líneas / 32.463 bytes**. La fila
  `0020` no se editó. **Propagación de ENMIENDA E-02 al plan maestro completada** (quedó pendiente
  en la tarea anterior por falta de alcance de escritura sobre ese fichero): añadida a §15 del plan
  y referenciada en §0.12 y en la fila T0.5 de la tabla de Fase 0 (§4). 🔴 **Corrección posterior,
  misma tarea:** ver entrada siguiente — el cuerpo de E-02 propagado en esta ronda contenía un
  hecho invertido (afirmaba "un único terminal"), corregido antes de cerrar la tarea. Ninguna
  operación de git ejecutada por este agente.
- **2026-08-11** · Sonnet 5 registrador · 🔴 **CORRECCIÓN — E-02 quedó escrita con el hecho
  invertido.** La versión de E-02 registrada más arriba en esta misma tarea (y propagada al plan
  maestro) afirmaba que "este equipo tiene un único terminal" y que `MT5_Tester_1`/`MT5_Tester_2`
  no existían por separado. **Falso.** El orquestador verificó en disco con `Test-Path` sobre
  `terminal64.exe`, confirmado por el user: `D:\FOREX\MT5_Tester\terminal64.exe` **existe** (es el
  terminal al que coloquialmente se llama "tester 1" — el nombre erróneo es `MT5_Tester_1`, que va
  **sin sufijo**; alojó la sesión de AVA); `D:\FOREX\MT5_Tester_2\terminal64.exe` **existe**
  (terminal de Capitaria, no corriendo al comprobar); `D:\FOREX\MT5_Tester_1\` **no existe**; existe
  además `C:\Program Files\MetaTrader 5`. Causa raíz: **un subagente reportó un hecho de disco
  incorrecto (que no existían carpetas con sufijo numérico) y el orquestador no lo verificó de
  forma independiente antes de convertirlo en enmienda formal — fallo de verificación del
  orquestador**, no del registrador que transcribió el brief. Corregido: cuerpo de E-02 reescrito
  (arriba, en la sección ENMIENDAS), fila T0.5 de este TRACKER y §0.12 + fila T0.5 del plan maestro
  revertidos (tachados de `MT5_Tester_2` quitados — esas referencias eran correctas). También se
  cierra **B8** en esta misma entrada: el user confirmó en persona que la 902 y el login sancionado
  `2883016567` son cuentas **distintas** — ver fila B8 (BLOQUEOS ACTIVOS) y `CUENTAS.md`. Ninguna
  operación de git ejecutada por este agente.
- **2026-08-11** · Sonnet 5 investigador + Opus 5 verif. · **Captura de especificación del feed
  AVA VERIFICADA.** Artefacto `04-resultados/T0.3-ava/especificacion-feed.md`. Identidad: login
  `101744074`, servidor `Ava-Demo 1-MT5`, `Ava Trade Ltd.`, DEMO. Símbolo `GOLD`:
  `trade_contract_size=100.0`, `digits=2`, `point=0.01` — idénticos a Capitaria. Fila
  `F0-INFRA-0020`. 🔴 **Anomalía reportada por el propio agente, no resuelta por él:** el brief
  suponía dos terminales locales (`MT5_Tester_1`/`MT5_Tester_2`); ~~solo existe uno
  (`D:\FOREX\MT5_Tester`)~~ **[corrección posterior: SÍ existen dos — `MT5_Tester` (el mal llamado
  `MT5_Tester_1`) y `MT5_Tester_2`, ambos en disco; ver ENMIENDA E-02 corregida]** → ver
  **ENMIENDA E-02**.
- **2026-08-11** · Opus 5 · Addendum a la captura anterior: se pidió `symbol_info_session_quote` /
  `symbol_info_session_trade` sobre `GOLD`. **Esas funciones no existen en la API Python de MT5
  instalada** (paquete `5.0.5735`; `dir(mt5)` — 269 atributos públicos, ninguno con la subcadena
  `session`). El agente declaró el punto **no evaluable, con evidencia**, en vez de inventar un
  valor o estimar un formato de retorno. **Error de brief del orquestador, no del agente.**
- **2026-08-11** · Sonnet 5 impl. + Opus 5 verif. · **Guard de identidad en `ticks_mt5`
  VERIFICADO.** Commit `cab4acb`, 3 ficheros. `pytest tests/research/ -q` → 137 passed, re-corrido
  en foreground por el controlador. Guard confirmado leyendo el código: `account_info()` L197,
  guard L213-235, primer `copy_ticks_range` L286; aborta con `TicksMT5IdentityError` si falla
  login, servidor, `trade_mode != DEMO` o el símbolo no resuelve. Desbloquea T0.4 y T0.5. Fila
  `F0-INFRA-0021`.
- **2026-08-11** · User + Opus 5 · **B2 RESUELTO** (D-22): el user aprobó las 12 modificaciones de
  motor, con R1-bis y re-verificación de paridad tras cada una vinculantes sin excepción.
  Desbloquea T0.6 → T0.7 → T0.8. **B5 RETIRADO** (D-20): la ingesta AVA es CSV manual, no API MT5,
  así que ampliar `SANCTIONED_DEMO` ya no responde a ninguna necesidad — principio fijado: no se
  modifica código de seguridad por un requisito que dejó de existir. **B6 RESUELTO**: el user
  inició sesión en la demo AVA dentro del terminal local existente, sin instalar uno nuevo.
- **2026-08-11** · Opus 5 · **D-21**: los backtests sobre AVA usan precios de AVA con un modelo de
  costes calibrado sobre Capitaria; el spread nativo de AVA (0,34–0,45 medidos) no se usa para
  veredictos. **D-23** (Baseline Largo BL-0): desglose mes a mes de S6 y SuperTrend vivas sobre el
  sustrato largo certificado, como primer entregable de LBT con A6 como puerta de entrada,
  instrumentado una sola vez y rico (MFE/MAE, spread entrada/salida, equity barra a barra),
  descriptivo y no selectivo. **D-24**: A6 Pata B mide transferibilidad con tolerancia temporal y
  umbral de divergencia de neto fijados de antemano, no bit-identidad (inalcanzable entre dos
  brókers con feeds distintos).
- **2026-08-11** · Opus 5 · 🟠 **B8 abierto:** ¿el login sancionado `2883016567` y la cuenta de
  Capitaria terminada en 902 son la misma cuenta? `CUENTAS.md` no documenta ninguna de las dos. No
  bloquea T0.4; sí afecta a A6 Pata A. Un subagente afirmó que son la misma; no verificado por el
  orquestador, escalado sin resolver. **[B8 RESUELTO 2026-08-11 por el user — ver entrada más
  arriba y fila B8 en BLOQUEOS ACTIVOS: son cuentas distintas; la 902 es `2883016902`, servidor
  `Capitaria Latam Spa`.]**
- **2026-08-11** · Opus 5 · **ENMIENDA E-02**: corrección de nomenclatura de terminales — ~~un único
  terminal local (`D:\FOREX\MT5_Tester`), no `MT5_Tester_1`/`MT5_Tester_2`~~ **[corrección
  posterior: hecho invertido — `MT5_Tester_1` no existe (ese terminal va sin sufijo: `MT5_Tester`),
  pero `MT5_Tester_2` SÍ existe; ver ENMIENDA E-02 corregida y entrada más arriba]**; la 902 opera
  desde el otro equipo. Propagada a la fila T0.5 de este TRACKER. Pendiente de propagar al plan
  maestro por un agente con alcance de escritura sobre ese fichero (ver nota en la sección
  ENMIENDAS). **[Propagación completada 2026-08-11, con el texto corregido — ver entrada más
  arriba.]**

- **2026-08-10** · Sonnet 5 impl. + Opus 5 verif. · **T0.4-impl HECHA y verificada** (`6544a1f`).
  🔴 **Casi-incidente evitado por el protocolo:** el spec del controlador se contradecía —
  idempotencia "por presencia" en el test vs "por completitud" en la prosa. Con la regla por
  presencia, la corrida habría **saltado `202607.parquet`, que está truncado al 24-jul**, dejando
  sin descargar el hueco 24→31 jul que necesita **A6 Pata A**, y reportando éxito. El implementador
  implementó el test literal, **no tocó el activo de datos** y **escaló** en vez de resolverlo solo.
  Corregido en ronda 1: completitud por tolerancia (72 h por defecto) + sobrescritura segura
  `tmp → validar → bak → rename`, con el fichero previo **renombrado, jamás borrado**.
  Verificación del controlador: md5 de `202607.parquet` idéntico antes y después, `runner.py`
  modificado en exactamente 1 línea, sin `.tmp`/`.bak` huérfanos.
- **2026-08-10** · Opus 5 · Auditoría de terreno pedida por el user antes de seguir. Hallazgos:
  (a) **no hay terminal de AVA instalado** → **B6**; (b) el servidor de AVA sigue sin confirmar;
  (c) **ningún terminal MT5 corriendo**, así que T0.4/T0.3/T0.5 están parados hasta que el user
  abra uno; (d) el protocolo de videos exige anidamiento de subagentes y choca con el máx-2 del
  charter → **B7**; (e) **T0.12 se sella en dos actos**, no uno (la mitad AVA depende de T0.3).
  Espacio: el user vació `Downloads` (+53,75 GB en C:); para AVA lo que cuenta es **D: con
  153,88 GB libres**, suficiente para el objetivo de 4 años.
- **2026-08-10** · Opus 5 · **T0.4 partida en dos**: `T0.4-impl` (task-type `ticks_mt5` del runner
  + validación de integridad + manifiesto + tests **sin MT5**) y la descarga real, que ejecuta el
  controlador cuando el user abra el terminal. No es reducción de alcance: T0.4 no se marca `[x]`
  hasta que los ticks estén en disco y validados.
- **2026-08-10** · Sonnet 5 impl. + Opus 5 verif. · **T0.9-min HECHA y verificada** (`b9ce5f2`).
  Scaffold de runner en `scripts/research/runner/`: manifiesto YAML validado con fail-loud, tags
  de lineage, escritor append-only del LEDGER con validación de los 13 campos, estado reanudable,
  registro de task-types y CLI. 5 tests obligatorios + smoke del CLI. Verificación independiente
  del controlador: tests re-corridos, `scripts/research/__init__.py` NO creado, scripts previos
  intactos, LEDGER real sin tocar por el agente. 4 observaciones al backlog (ninguna bloqueante).
- **2026-08-10** · User + Opus 5 · **Arranque autorizado.** Freeze de D-05 levantado para el orden
  0→7. Decisiones nuevas **D-16** (commitear el Research OS antes de despachar; `data/literature`
  NO entra al repo), **D-17** (lineage retroactivo acotado a `monday_audit/*.json` y
  `realtick_bt/positions_*.csv`), **D-18** (T0.4 sale como primer runner, scaffold mínimo ⇒ T0.9
  se parte en T0.9-min + T0.9), **D-19** (credenciales AVA entregadas ⇒ **B1 resuelto**; nace **B5**:
  extender el guard `SANCTIONED_DEMO` requiere autorización explícita del user).
- **2026-08-10** · Opus 5 · **ENMIENDA E-01** (plan §15): la justificación de la prioridad de T0.4
  era incorrecta — el histórico viejo ya está en disco y el hueco jul-ago no se pierde. Motivo real:
  **A6 Pata A necesita esa ventana**. Sin cambio de alcance, sin re-validación. Propagada a
  `fases/F0-preparacion/00-README.md` y a la fila T0.4. Adoptado además: **T0.4 × holdout —
  descargar sí, mirar no**; T0.12 va inmediatamente después de T0.4.
- **2026-08-10** · Opus 5 · Auditoría de arranque: (a) el Research OS y el plan v4 estaban **sin
  commitear** (HEAD `41fdb25`, del 2026-07-27) — corregido por D-16; (b) el LEDGER tenía 3 filas,
  todas INFRA, con `git_sha` de un commit que no contenía sus artefactos — corregido con filas
  `supersedes`; (c) `CUENTAS.md` no menciona el login `2883016567` que `extract_ticks.py:34`
  sanciona, ni la 902 ni `MT5_Tester_2` → anotado en `BACKLOG.md` por decisión del user.
- **2026-08-10** · Fable 5 · Research OS construido (`research/**`: charter, tracker, decisiones,
  ledger, backlog, negativos, 5 protocolos, estructura de fases) + plan v4 emitido + brain
  actualizado (pinned/INDEX apuntaban al plan obsoleto del 2026-07-19; corregido).
- **2026-08-10** · Fable 5 · T0.11a: 28/28 transcripciones descargadas, ~233.723 tokens medidos,
  ninguna leída. Protocolo de análisis registrado para su etapa.
- **2026-08-10** · User · Decisiones: holdout aprobado · método AVA (GUI, credenciales pendientes) ·
  lista de 28 videos entregada · limpieza de C: aprobada solo como propuesta · plan a detallar
  exhaustivamente antes de ejecutar.
- **2026-08-09/10** · Fable 5 · Integración del documento exhaustivo del user (31 deltas) → plan v4.
- **2026-08-10** · Fable 5 · Backup del plan previo (T0.1).
