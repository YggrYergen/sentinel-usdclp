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

> **2026-08-10 · FASE 0 (Preparación), EJECUTANDO.** El user levantó el freeze de D-05 para el
> orden de arranque autorizado (D-16…D-19). **B1 desbloqueado** (credenciales AVA entregadas).
> Research OS commiteado. **En curso ahora: T0.2 (propuesta de disco C:, primera entrega) y
> T0.9-min (scaffold de runner), en paralelo.** Luego T0.4 → T0.12 → T0.3 → T0.5 → T0.11b.
> **Sigue bloqueado B2** (sign-off del inventario de 12 mods de motor) → T0.6/T0.7/T0.8 y con
> ellos A6, que es el gate de todo el programa.

---

## FASE 0 — PREPARACIÓN (bloqueante · nada de investigación corre antes)

| Estado | # | Tarea | Routing | Notas / bloqueo |
|---|---|---|---|---|
| `[x]` | T0.1 | Backup del plan previo | — | `docs/superpowers/plans/backups/2026-08-10-programa-exploracion-artifact-PRE-INTEGRACION.html` (71,7 KB) |
| `[x]` | T0.0 | Plan v4 redactado + Research OS construido | Fable | Plan: `plans/2026-08-10-plan-investigacion-integral-v4.md` · OS: `research/**` |
| `[x]` | T0.11a | Descarga de 28 transcripciones YouTube | Fable | `data/literature/youtube_transcripts/` · 28/28 · **~233.723 tokens** · NINGUNA leída |
| `[x]` | T0.2 | Propuesta de limpieza disco C: (95 % lleno) | Sonnet · INVESTIGADOR | ✅ **VERIFICADO.** `04-resultados/T0.2-disco-C/inventario-espacio.md` (574 líneas). D-04 respetada (0 comandos destructivos, comprobado). C: 22,19 GB libres (4,92 %). Fila `F0-INFRA-0018`. ✅ **CERRADA por el user 2026-08-10**: vació `Downloads` a mano → **+53,75 GB** (C: 22,19 → 75,94 GB libres, verificado). Cachés de dev (~41 GB) quedan como reserva |
| `[x]` | PENDIENTE-ORQUESTADOR | Captura de especificación del feed AVA | Sonnet · INVESTIGADOR REPORT-ONLY | ✅ **VERIFICADO.** Artefacto `research/fases/F0-preparacion/04-resultados/T0.3-ava/especificacion-feed.md` (368 líneas, 17.841 bytes, confirmado en disco por el orquestador; el fichero creció después por un addendum, ver Bitácora). Identidad verificada: login `101744074`, servidor **`Ava-Demo 1-MT5`**, `Ava Trade Ltd.`, `ACCOUNT_TRADE_MODE_DEMO`. Símbolo **`GOLD`**: `trade_contract_size` = **100.0**, `digits` = 2, `point` = 0.01 — **idénticos a Capitaria**; el dimensionamiento de "1 ficha de 0,67" transfiere sin ajuste. Tick de captura: bid 4382.83 / ask 4383.28, spread 0,45. Attach-only respetado (`initialize()` sin `path=`). Efecto colateral declarado: `symbol_select("GOLD", True)` cambió el Market Watch del terminal (no destructivo). Fila `F0-INFRA-0020` |
| `[ ]` | T0.3 | **R6-AVA**: descarga real-tick ≥2 años (objetivo 4) | Sonnet | ✅ **B1 DESBLOQUEADO** (D-19). ✅ **B5 RETIRADO** (D-20): ya no hace falta extender `SANCTIONED_DEMO` — la ingesta AVA es CSV manual, no API MT5. ✅ **B6 RESUELTO**: demo AVA logueada en el terminal existente `D:\FOREX\MT5_Tester` |
| `[x]` | PENDIENTE-ORQUESTADOR | Guard de identidad en el task-type `ticks_mt5` | Sonnet · IMPLEMENTADOR · TDD | ✅ **VERIFICADO** por el orquestador contra artefactos crudos, no contra el reporte: `pytest tests/research/ -q` re-corrido en foreground → **137 passed**; commit `cab4acb` scoped a 3 ficheros; `extract_ticks.py` sin tocar desde `1b9e968` (2026-07-26) y `guard_cuenta.py` desde `6467046` (2026-07-15), ambos anteriores; `scripts/research/__init__.py` sigue ausente; **orden del guard confirmado leyendo el código**: `account_info()` en L197, guard en L213-235, primer `copy_ticks_range` en L286. Aborta con `TicksMT5IdentityError` si falla login, servidor, `trade_mode != DEMO` o el símbolo no resuelve. Desbloquea T0.4 y T0.5. Fila `F0-INFRA-0021` |
| `[~]` | T0.4 | **Top-up ticks Capitaria** (ventana completa de la 902) | Sonnet impl. + runner | ✅ **T0.4-impl HECHA y verificada** (`6544a1f`, fila `F0-INFRA-0019`): task-type `ticks_mt5` + validación de integridad + manifiesto `03-runs/T0.4-topup-capitaria.yaml` + 11 tests, 129 en la suite. ✅ **Guard de identidad añadido y verificado** (`cab4acb`, fila `F0-INFRA-0021`). 🔴 **FALTA la descarga real** — requiere que el user abra `MT5_Tester`. Insumo directo de **A6 Pata A** (ventana en que operó la 902) — **no** es urgencia de ventana rodante: ver **ENMIENDA E-01**. Primer cliente del runner (D-18). Requiere `MT5_Tester` abierto por el user |
| `[ ]` | T0.5 | Export historial cuenta 902 (deals/órdenes/balance) | Sonnet | Vía `MT5_Tester_2` (terminal de Capitaria — ver **ENMIENDA E-02**: nombre correcto, no estaba corriendo al verificar). **SOLO LECTURA** (charter §A.12) |
| `[ ]` | T0.6 | **12 modificaciones de motor** (inventario en plan §4.1) | Spec: Opus · Impl: Sonnet TDD | ✅ **B2 RESUELTO (D-22): SIGN-OFF recibido del user.** TODAS juntas, antes del freeze. R1-bis vigente sin excepción; **paridad re-verificada tras CADA modificación**, nunca al final del lote |
| `[ ]` | T0.7 | **A6 — Fidelidad** (diseño de dos patas, plan §4.2) | Impl: Sonnet · Análisis: Opus | **GATE DE TODO EL PROGRAMA.** Objetivo: señal bit-idéntica; neto ≤0,3 % (99,7) / ideal ≤0,15 % (99,85) |
| `[ ]` | T0.8 | Freeze del motor (tag + SHA anotado aquí) | Controlador | Solo tras T0.6 + T0.7 verdes |
| `[x]` | T0.9-min | **Scaffold mínimo de runner** (D-18) | Sonnet · impl. TDD | ✅ **VERIFICADO** por el controlador contra artefactos crudos. `scripts/research/runner/` (7 módulos) + `tests/research/test_runner_scaffold.py`. Commit `b9ce5f2`, 8 ficheros / 606 líneas. 5/5 tests re-corridos en foreground; `tests/research` 118 passed. Fila `F0-INFRA-0017`. 4 observaciones diferidas → `BACKLOG.md` |
| `[ ]` | T0.9 | Research OS — resto (supervisión durable) | Sonnet | Estructura y protocolos: `[x]`. Scaffold de runner: T0.9-min. Falta: supervisión durable de watcher/ingesta |
| `[ ]` | T0.10 | Literatura formal — 7 áreas | Recolección: Sonnet · Memos: Opus | Cada área ANTES de cerrar su grilla |
| `[ ]` | T0.11b | Análisis de las 28 transcripciones | Ver protocolo dedicado | **Protocolo exacto:** `research/fases/F0-preparacion/PROTOCOLO-REVISION-VIDEOS.md` |
| `[ ]` | T0.12 | Sellar el holdout | Controlador | ✅ Partición APROBADA (D-01). 🟠 **Se sella en DOS ACTOS, no uno**: la mitad Capitaria (trimestre más reciente) tras T0.4; la mitad AVA (año completo no adyacente) **solo tras T0.3**, porque hasta entonces no hay rango real contra el que fijar fechas |
| `[ ]` | T0.13 | Modelado de la hora muerta desplazante | Sonnet · análisis Opus | 3 fuentes: ticks AVA, ticks Capitaria (7 m), historiales MT5 (~3 meses en suma) |

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
| B3 | Cierre de la matriz de indicadores de la autopsia (plan §5.2) | Motor mod #11 → A0 | **User** |
| B4 | Umbrales operacionales de la puerta estadística (§9) | D170' | **User** (a fijar con Opus) |
| ~~B5~~ | ~~Autorización explícita para extender `SANCTIONED_DEMO` (`extract_ticks.py:34`) con la demo AVA `101744074` — es código de seguridad~~ | — | **RETIRADO 2026-08-11** (D-20). Ya no existe la necesidad: la ingesta de ticks AVA es un CSV exportado a mano, no llama a la API de MT5 |
| ~~B6~~ | ~~No hay terminal de AVA instalado~~ | — | ✅ **RESUELTO 2026-08-11.** No hizo falta instalar un terminal AVA aparte; el user inició sesión en la demo AVA dentro del terminal existente `D:\FOREX\MT5_Tester`. Servidor confirmado: `Ava-Demo 1-MT5` |
| B7 | Conflicto entre dos reglas del user: `PROTOCOLO-REVISION-VIDEOS.md` manda 2 orquestadores Sonnet × ~11 subagentes Haiku (anidamiento), y el charter §C fija **máx 2 en paralelo**. No se resuelve por cuenta propia | T0.11b | **User** |
| ~~B8~~ | ~~¿El login sancionado `2883016567` y la cuenta de Capitaria terminada en 902 son la misma cuenta o dos distintas?~~ | — | ✅ **RESUELTO 2026-08-11** por el user, en persona: son cuentas **distintas**. La 902 es login **`2883016902`**, servidor **`Capitaria Latam Spa`**. `2883016567` es otra cuenta, no la 902. La afirmación de un subagente anterior de que eran la misma cuenta queda anulada. Añadida a `CUENTAS.md` (NO-R&D / SOLO LECTURA, sin contraseña persistida — charter §A.12) |

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
