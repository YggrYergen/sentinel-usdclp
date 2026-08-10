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
| `[~]` | T0.2 | Propuesta de limpieza disco C: (95 % lleno) | Sonnet · INVESTIGADOR | **SOLO PROPUESTA. PROHIBIDO BORRAR** (D-04). El user borra a mano. Cruzar tamaño × antigüedad. 🔴 **Primera entrega: el user la lee antes que nada** |
| `[ ]` | T0.3 | **R6-AVA**: descarga real-tick ≥2 años (objetivo 4) | Sonnet | ✅ **B1 DESBLOQUEADO** (D-19): demo AVA `101744074`. Requiere (a) terminal AVA abierto por el user (attach-only) y (b) 🔴 **autorización explícita para extender `SANCTIONED_DEMO`** en `extract_ticks.py:34` |
| `[ ]` | T0.4 | **Top-up ticks Capitaria** (ventana completa de la 902) | Sonnet impl. + runner | Insumo directo de **A6 Pata A** (ventana en que operó la 902) — **no** es urgencia de ventana rodante: ver **ENMIENDA E-01**. Primer cliente del runner (D-18). Requiere `MT5_Tester` abierto por el user |
| `[ ]` | T0.5 | Export historial cuenta 902 (deals/órdenes/balance) | Sonnet | Vía `MT5_Tester_2`. **SOLO LECTURA** (charter §A.12) |
| `[ ]` | T0.6 | **12 modificaciones de motor** (inventario en plan §4.1) | Spec: Opus · Impl: Sonnet TDD | 🔴 **Requiere SIGN-OFF del user antes de implementar.** TODAS juntas, antes del freeze |
| `[ ]` | T0.7 | **A6 — Fidelidad** (diseño de dos patas, plan §4.2) | Impl: Sonnet · Análisis: Opus | **GATE DE TODO EL PROGRAMA.** Objetivo: señal bit-idéntica; neto ≤0,3 % (99,7) / ideal ≤0,15 % (99,85) |
| `[ ]` | T0.8 | Freeze del motor (tag + SHA anotado aquí) | Controlador | Solo tras T0.6 + T0.7 verdes |
| `[x]` | T0.9-min | **Scaffold mínimo de runner** (D-18) | Sonnet · impl. TDD | ✅ **VERIFICADO** por el controlador contra artefactos crudos. `scripts/research/runner/` (7 módulos) + `tests/research/test_runner_scaffold.py`. Commit `b9ce5f2`, 8 ficheros / 606 líneas. 5/5 tests re-corridos en foreground; `tests/research` 118 passed. Fila `F0-INFRA-0017`. 4 observaciones diferidas → `BACKLOG.md` |
| `[ ]` | T0.9 | Research OS — resto (supervisión durable) | Sonnet | Estructura y protocolos: `[x]`. Scaffold de runner: T0.9-min. Falta: supervisión durable de watcher/ingesta |
| `[ ]` | T0.10 | Literatura formal — 7 áreas | Recolección: Sonnet · Memos: Opus | Cada área ANTES de cerrar su grilla |
| `[ ]` | T0.11b | Análisis de las 28 transcripciones | Ver protocolo dedicado | **Protocolo exacto:** `research/fases/F0-preparacion/PROTOCOLO-REVISION-VIDEOS.md` |
| `[ ]` | T0.12 | Sellar el holdout | Controlador | ✅ **Partición APROBADA por el user 2026-08-10.** Falta ejecutarlo y dejar constancia |
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
| B2 | Sign-off del inventario de 12 modificaciones de motor | T0.6 → T0.7 → T0.8 → **A6 → todo** | **User** |
| B3 | Cierre de la matriz de indicadores de la autopsia (plan §5.2) | Motor mod #11 → A0 | **User** |
| B4 | Umbrales operacionales de la puerta estadística (§9) | D170' | **User** (a fijar con Opus) |
| B5 | Autorización explícita para extender `SANCTIONED_DEMO` (`extract_ticks.py:34`) con la demo AVA `101744074` — es código de seguridad | T0.3 | **User** |

---

## BITÁCORA (append-only · más reciente arriba)

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
