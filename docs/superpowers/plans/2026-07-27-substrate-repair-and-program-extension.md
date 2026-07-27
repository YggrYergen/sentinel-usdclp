# Substrate Repair + Program Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Reparar los dos bugs del instrumento de análisis (pairing "reverse" + fallback de
fills), regenerar el substrato y re-correr Track A para que la entrega del lunes sea VÁLIDA;
(2) dejar cableado el programa post-lunes (catálogo v3) con routing, normas y skills explícitos
para que las sesiones frescas no pierdan la doctrina.

**Architecture:** Parte 1 = cirugía sobre `scripts/analysis/realtick_bt/backtest.py` (solo
herramienta de análisis; CERO código vivo) + regeneración + re-corrida de los módulos Track A ya
existentes + diff número-por-número. Parte 2 = fases del catálogo v3, cada una con su propio plan
detallado emitido en su momento vía `superpowers:writing-plans` (anti-alucinación: los detalles
finos se escriben contra los docs fuente, no de memoria).

**Tech Stack:** Python 3.x (pathlib, utf-8, Win10/11), pandas/numpy solo donde ya son dependencia,
pytest (foreground SIEMPRE), git en rama `equipo1`.

---

## 🔴 AL INICIO DE CADA SESIÓN FRESCA (leer ANTES de despachar nada)

El motivo de esta sección: en handoffs anteriores la sesión fresca dejó de seguir las normas
subagénticas. Por eso van aquí, al principio, y son parte del plan — no folklore de sesión.

1. Leer `pinned.md` del brain (se inyecta solo) + este plan completo (§ROUTING, §SKILLS, §NORMAS).
2. Leer el tracker `docs/superpowers/plans/2026-07-25-monday-tracker.md` (única fuente de estado).
3. Leer el catálogo `docs/superpowers/research/2026-07-27-strategy-improvement-catalog-v3.md`
   antes de tocar cualquier cosa de Parte 2.
4. Invocar `superpowers:dispatching-parallel-agents` ANTES del primer despacho paralelo de la
   sesión, y `superpowers:subagent-driven-development` para el ciclo brief→implementa→verifica.
5. NO despachar nada de Parte 2 sin que Parte 1 esté `[x]` en el tracker.

## §ROUTING (directiva user 2026-07-27 — va VERBATIM en cada brief)

> **Routing de modelos:** el subagente principal es **Sonnet 5 high effort**. Para las tareas
> que por su dificultad o criticidad lo requieran se usa **Opus 5 high effort** (justificar la
> elección en el despacho). **Las etapas de ANÁLISIS DE RESULTADOS usan SIEMPRE Opus 5 high.**
> A Sonnet 5 NUNCA se le pide interpretar resultados, hacer recomendaciones ni tomar decisiones:
> solo ejecuta, reporta objetivamente e implementa cuando el detalle exacto de lo que debe
> implementar se le ha entregado. Fable 5 = orquestador (specs cerradas, verificación, integración).
> Cada subagente recibe este contexto en su brief.

Asignación en este plan: R1, R2, R3 = Sonnet 5 high (implementación con spec cerrada).
R4 (lectura del diff y veredictos) = **Opus 5 high** (es análisis de resultados).
Task 13 (documento del lunes) = **Opus 5 high** (redacción con juicio). Task 11/12 = Sonnet 5 high.

## §SKILLS (integración explícita — cuándo se invoca cada una)

| Momento | Skill |
|---|---|
| Antes de cualquier despacho paralelo | `superpowers:dispatching-parallel-agents` |
| Ciclo por tarea (brief→implementa→verifica) | `superpowers:subagent-driven-development` |
| Cada tarea de código, sin excepción | `superpowers:test-driven-development` (rojo→mínimo→verde→commit) |
| Antes de declarar CUALQUIER tarea terminada | `superpowers:verification-before-completion` |
| Revisión de código | `superpowers:requesting-code-review`, **batcheada a fin de fase** (no por tarea) |
| Escribir el plan detallado de cada fase de Parte 2 | `superpowers:writing-plans` |
| Fin de sesión / handoff | skill `brain` (`/brain handoff`, update NO destructivo) |

## §NORMAS DE PROCESO (bloque copy-paste para TODO brief)

> **R1-bis (verbatim, sin excepción):** Los S6/S7/SuperTrend VIVOS se preservan byte-identical,
> as-is (engines, kwargs, config dicts, code paths). Toda modificacion va sobre copia
> independiente (cfg deep-copy, modulo nuevo, banda magica nueva), JAMAS sobre el original.
> Un implementador que concluya que hay que tocar el original esta equivocado sobre la tarea:
> debe PARAR y escalar.
> **Paralelismo:** máx 3 subagentes, NUNCA dos sobre los mismos ficheros. Ficheros compartidos
> (tracker, planes, `.gitignore`) son del CONTROLADOR, jamás de un agente.
> **Git:** commitear solo las rutas propias: `git add -- <rutas>` y
> `git commit -m "<msg>" -- <rutas>` (el `-m` va ANTES del `--`). Verificar `git status --short`
> antes y después. Ni `git add .`, ni `-A`, ni rebase, ni push, ni tags.
> **Pytest:** PROHIBIDO en background. Foreground con timeout largo. Suites dirigidas
> (`tests/analysis`, `tests/live`), no la suite completa (13 rojos conocidos por fuga de env
> vars del host vivo; lentos ya en cuarentena `slow`).
> **MT5:** cuentas reales READ-ONLY; attach-only (nadie lanza terminales); toda orden requiere
> `guard_cuenta.assert_demo()`; nada se despliega sin decisión explícita del user.
> **Honestidad:** todo número lo calcula código (R5); lo no evaluable se declara no evaluable;
> registro aditivo (nunca borrar/mutar filas de resultados); veredictos bajo métrica D170
> (neto + consistencia mensual + recorte top-K).

## Global Constraints

- Rama `equipo1`. Nunca commitear a `alvaro`. HEAD al escribir esto: `4019654`.
- Deadline lunes 2026-07-27 RELAJADO por el user: "calidad prioritaria, sin apuro".
- Parte 1 toca SOLO `scripts/analysis/realtick_bt/**`, `data/analysis/**`,
  `tests/analysis/**`, docs. CERO cambios bajo `sentinel_engine/**` o `scripts/live/**`
  (excepción única y acotada: R4 puede actualizar el valor B3 del roster retador SI cambia,
  por el mismo mecanismo de lectura-de-artefacto de Task 4).
- Substrato: `data/lake_ticks/XAUUSD/` = ticks mensuales `2026xx.parquet` + `_bars_M15.parquet`.
  **NO existe `_bars_M1.parquet`** (verificado 2026-07-27) — R2 lo tiene en cuenta.
- Timestamps = hora de servidor broker (UTC−4). PROHIBIDA toda conversión de zona horaria
  (bug de reloj ya arreglado en origen; ver tracker §Bug de reloj).

---

# PARTE 1 — Validez del lunes (bloqueante)

Contexto de los bugs (hallados 2026-07-27, verificados por el controller):
- `run_ladder()` (`backtest.py:149-183`) solo empareja `motivo.startswith("EXIT") or
  motivo == "time_stop"` (línea 164). El motivo `"reverse"` (cierre por stop-and-reverse,
  `emasar_variant.py:1140-1151`) NO emite fila: ~504 cierres S6 + ~240 S7 ausentes de
  `positions_*.csv` (~24% de los cierres de señal). Grep confirmado: 0 filas "reverse" en CSVs.
- `resolve()` (`backtest.py:234-293`): para `reason in LEVEL_EXITS`, si ningún tick cruza el
  nivel dentro de la barra, cae en silencio al primer tick de la barra siguiente (líneas
  280-285) — 321/891 (36%) de los EXIT_INITSL de S6 tienen exit_fill en dirección de ganancia.

### Task R1: Emparejar los cierres "reverse" en `run_ladder`

**Files:**
- Modify: `scripts/analysis/realtick_bt/backtest.py:149-183` (solo `run_ladder`)
- Test: `tests/analysis/test_realtick_pairing.py` (nuevo)

**Interfaces:**
- Produces: filas de posición con `reason="reverse"` en la salida de `run_ladder` (mismas
  claves que las demás: side_l/side/ficha/t_in/t_out/entry_bid/exit_bid/reason/same_bar).
- `resolve()` NO cambia para esto: `"reverse"` ∉ `LEVEL_EXITS`, así que toma el camino de
  cierre-a-precio-de-barra-siguiente (líneas 280-285), que es la semántica correcta de un
  cierre a mercado al cierre de barra. Verificarlo con un assert en el test, no asumirlo.

- [ ] **Step 1: caracterizar el evento.** Replay corto de `simular_variant` con los kwargs vivos
  de S6-K2P0 sobre un slice de barras que contenga al menos un reverse; imprimir los eventos
  `motivo=="reverse"`: ¿traen clave `ficha` (uno por ficha) o son un solo evento por señal?
  Pegar la salida real en el reporte de la tarea. (El brief no lo presupone: se mide.)
- [ ] **Step 2: test rojo.** En `tests/analysis/test_realtick_pairing.py`, feed sintético de
  eventos a `run_ladder` (ENTRY_L → reverse) y asertar: (a) emite exactamente una fila por
  ficha abierta, `reason="reverse"`, `t_out` = barra del evento, `exit_bid` = `ev["precio"]`;
  (b) el diccionario `open_pos` queda sin la señal (no quedan fichas huérfanas); (c) una
  entrada nueva posterior en la misma barra se empareja limpio. Correr: debe FALLAR (hoy las
  filas no existen).
- [ ] **Step 3: implementación mínima.** Añadir rama `elif motivo == "reverse":` que cierre
  TODAS las fichas restantes de la señal activa (o la ficha del evento, según lo medido en
  Step 1), emitiendo una fila por ficha, y haga `open_pos.pop`. No tocar la rama existente.
- [ ] **Step 4: verde.** `python -m pytest tests/analysis/test_realtick_pairing.py -v` → PASS;
  `python -m pytest tests/analysis -q` → sin regresiones (57 passed era el baseline).
- [ ] **Step 5: commit** `git commit -m "fix(realtick): pair reverse closures as positions" --
  scripts/analysis/realtick_bt/backtest.py tests/analysis/test_realtick_pairing.py`

### Task R2: Jerarquía de fills con procedencia + asserts

**Files:**
- Modify: `scripts/analysis/realtick_bt/backtest.py:234-293` (`resolve`) + el writer de CSV
  (añadir columna `fill_source`)
- Test: `tests/analysis/test_realtick_fills.py` (nuevo)

**Diseño (cerrado):** para `reason in LEVEL_EXITS` sin cruce de tick en la ventana de la barra:
1. **Diagnóstico embebido:** contar y clasificar — ¿la ventana tiene ticks pero ninguno cruza
   (nivel jamás tocado según ticks), o la ventana está VACÍA de ticks (hueco de cobertura)?
   Son dos patologías distintas y el artefacto las reporta por separado.
2. **Fallback:** si hay hueco de cobertura, intentar bucket M1 construido AL VUELO de los
   parquets de ticks del mes (no hay `_bars_M1.parquet` en el lake — verificado); si tampoco
   hay dato, la fila sale marcada `fill_source="unresolved"` y `exit_fill` al precio del nivel
   (conservador: un stop se asume ejecutado en su nivel, no a un precio inventado mejor).
   Si la ventana tiene ticks y el nivel NO se tocó, la fila sale `fill_source="level_uncrossed"`
   con cierre a barra-siguiente (comportamiento actual) — eso ya no es un fill inventado sino
   una discrepancia señal-vs-ticks DECLARADA, que el diff de R3 cuantifica.
3. **Columna `fill_source`** en toda fila: `tick | m1 | level_assumed | level_uncrossed`.
4. **Assert aritmético:** para `fill_source in {tick, m1, level_assumed}` y reason de stop:
   long ⇒ `exit_fill <= level + SLIP_TOL`; short ⇒ `exit_fill >= level - SLIP_TOL`. Violación
   = excepción que aborta la corrida (no una fila más).

- [ ] **Step 1: test rojo** con ticks sintéticos para los cuatro caminos (cruce real, hueco con
  M1, hueco sin nada, nivel no tocado) + el assert direccional.
- [ ] **Step 2: implementar** la jerarquía y la columna.
- [ ] **Step 3: verde** dirigido + suite `tests/analysis` completa.
- [ ] **Step 4: commit** scoped a los dos ficheros.

### Task R3: Regenerar substrato + re-correr Track A + DIFF número por número

**Files:**
- Regenera: `data/analysis/realtick_bt/positions_*.csv` (versionados, R5)
- Re-corre: `a1_maxdd.py`, `a2_overlap.py`, `a3_a4_a5_stats.py`, `b6_masks.py`,
  `b1_wait_curve.py`, `b1_robustness.py` → sus JSON
- Create: `docs/superpowers/research/2026-07-27-substrate-repair-diff.md`

- [ ] **Step 1:** snapshot previo — copiar los CSVs y JSONs actuales a
  `data/analysis/realtick_bt/pre_repair_snapshot/` (el bug del reporte mensual reescrito sin
  snapshot NO se repite).
- [ ] **Step 2:** regenerar con R1+R2 integrados. Conteos esperados: n_posiciones SUBE
  (~2.347 + ~744 filas reverse ± lo que el pairing real determine); las 2.347 filas viejas
  deben seguir existiendo con su mismo net (verificable por multiset de `(t_in, ficha,
  strategy, net)` — si una fila vieja cambió sin explicación por R2/fill_source, PARAR y escalar).
- [ ] **Step 3:** re-correr los seis módulos Track A en orden (a1→a2→a3a4a5→b6→b1_wait→b1_rob).
- [ ] **Step 4:** escribir el diff doc: tabla vieja-vs-nueva para CADA número citado en el
  tracker §"Números que otras tareas necesitan" + curva B1 + robustez M1/M2/M3 + concentración
  + correlaciones + maxDD + neto total. Sin interpretación (eso es R4/Opus): solo cifras.
- [ ] **Step 5:** commit scoped (CSVs + JSONs + snapshot + diff doc).

### Task R4 (Opus 5 high — análisis de resultados): veredictos sobre el diff

- [ ] Leer el diff de R3 y dictaminar, número por número: qué conclusión previa se sostiene,
  cuál cambia, cuál queda indeterminada. En particular: cap B3 (si ≠7, actualizar el valor en
  el roster retador por el mismo mecanismo lee-artefacto de Task 4 + re-correr sus tests),
  veredicto NO-VETO de B1@50min, ranking N3>N4, concentración top-K, correlaciones.
- [ ] Actualizar tracker §"Números que otras tareas necesitan" + una entrada de bitácora.
- [ ] Salida: memo corto en el mismo diff doc (§Veredictos) — este memo SÍ interpreta (Opus).

### Tasks 11, 12, 13 del plan del lunes (sin re-especificar aquí)

Viven en `docs/superpowers/plans/2026-07-25-monday-champion-challenger.md`. Cambios:
- **Task 11 (ensayo de revert):** sin cambios, puede correr en paralelo con R1/R2 (ficheros
  disjuntos), PERO no simultáneo con commits de otros (muta estado git). Secuenciar.
- **Task 12 (despliegue):** pasos 5-6 = manos del user. Recomendado tras R4 por si B3≠7.
  Decisión de timing = del user, no del controlador.
- **Task 13 (documento, Opus 5 high):** GATEADA por R3+R4. Ahora lleva CUATRO correcciones
  narrativas obligatorias: (1) "SuperTrend casi independiente" ya no se sostiene (corr 0,35);
  (2) grilla mensual regenerada; (3) reporte mensual reescrito sin snapshot — regenerable;
  (4) 🆕 disclosure del bug reverse + fills con el resultado del re-run (no números viejos).

# PARTE 2 — Programa post-lunes (catálogo v3)

Fuente de verdad: `docs/superpowers/research/2026-07-27-strategy-improvement-catalog-v3.md`
(familias A-E, grillas exactas, reglas del programa) + matriz FINAL + plan v2. NO re-derivar
de memoria: si un detalle no está en esos docs, se pregunta al user o se lee del repo.

- [ ] **Fase M0 — integrar matriz v4:** aplicar las 6 correcciones listadas en el catálogo §
  "Correcciones a la matriz FINAL" emitiendo `2026-07-2X-FINAL-experiment-matrix-v4.md`
  (la v3 del 07-22 NO se edita: registro aditivo). Requiere OK del user sobre el catálogo.
- [ ] **Fase A** (catálogo A2-A5; A1 ya es Parte 1): mapa MFE/MAE, economía de la reversa,
  spread-regime, experimento natural S6-vs-S7. Cada una: plan detallado propio vía
  `superpowers:writing-plans`, implementadores Sonnet 5 high, análisis de salida Opus 5 high.
- [ ] **Fases B/C/D:** grillas de salidas + políticas de re-entrada + entradas/zonas/MTF,
  por estrategia, sobre substrato reparado. Screening in-sample → puerta D170 → cola de
  backtest largo (`docs/superpowers/specs/2026-07-27-long-backtest-queue.md`) → holdout.
- [ ] **Fase E:** 🔒 gateada — solo si quedan ≥2-3 configs estadísticamente ganadoras tras B/C/D.

## Verification (Parte 1 end-to-end)

1. `python -m pytest tests/analysis -q` verde (incluye los dos ficheros de test nuevos).
2. El multiset de las 2.347 filas pre-existentes sobrevive intacto en los CSVs regenerados.
3. `positions_*.csv` contienen filas `reason="reverse"` y columna `fill_source`; cero filas
   de stop con fill en dirección de ganancia sin marca `level_uncrossed`.
4. Diff doc existe con TODAS las cifras del tracker cubiertas, y §Veredictos (R4) firmado.
5. Tracker actualizado; documento del lunes (Task 13) escrito SOLO después de eso.

## Self-Review (hecho al escribir este plan)

- Cobertura: bugs reverse/fills → R1/R2; validez del lunes → R3/R4 + gating de Task 13;
  extensión v2 → Parte 2 + M0; normas/routing/skills → §§ dedicadas al frente. Sin huecos.
- Sin placeholders: los cuatro caminos de R2 están cerrados; el único punto abierto declarado
  (forma del evento reverse, por-ficha o por-señal) tiene su paso de medición explícito (R1.1).
- Consistencia de tipos: R1 produce filas con las mismas claves que consume R2/R3 (verificado
  contra `backtest.py:174-179` real).
