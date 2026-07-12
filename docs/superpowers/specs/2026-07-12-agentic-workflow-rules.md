# Reglas del Workflow Agéntico — Recalibración V2 (Capa-4, OBLIGATORIO)

Aplica al plan `docs/superpowers/plans/2026-07-12-v2-recalibration-plan.md`. Objetivo: implementar
rápido y barato SIN pérdida de calidad. Estas reglas son NO negociables para orquestador e implementadores.

## 1. Roles y modelos
- **Orquestador** = la sesión principal (modelo de la sesión; opera LEAN: no implementa código, no
  pega specs enteras en prompts — despacha bloques de tarea verbatim + este preámbulo).
- **Implementadores** = subagentes **Sonnet 5** (Agent tool, `model: "sonnet"`, general-purpose),
  **máx 3 concurrentes, uno por lane (A servicio / B web / C data-engines)**.
- Escalada 2-strikes: si una tarea falla 2 despachos → NO cambiar de modelo; re-scopear/partir la
  tarea y aumentar detalle del prompt (regla de routing vigente: Sonnet implementa, Opus no implementa).

## 2. ⏱️ Presupuesto de tiempo por subagente (REGLA DURA del usuario)
- Toda tarea se diseña para **≤10 min** de ejecución Sonnet-5-high.
- **>12 min = problema**: revisar el diff con lupa; probablemente la tarea estaba mal dimensionada.
- **>20 min = problema grave**: detener consideración normal; aceptar SOLO si diff pequeño + gate verde;
  si no, descartar y partir la tarea.
- **>35 min = se asume trabajo mayormente malo**: DESCARTAR el diff sin piedad (git checkout --),
  partir la tarea en ≥2, re-despachar.
- El orquestador registra la duración (viene en la task-notification) en el ledger junto al estado.
- Prevención: tareas = 1 endpoint | 1 componente | 1 módulo + sus tests. Si el bloque de tarea del plan
  dice "2 dispatches", partir ANTES de despachar, no después de que tarde.

## 3. Prevención de conflictos (NUNCA interferencia entre subagentes)
- **Un archivo = un dueño en vuelo.** Prohibido despachar 2 tareas cuya lista Files se interseque.
- **CHOKE files** (`web/index.html`, `web/style.css`, `web/app.js`, `web/lib/chart.js`,
  `sentinel_engine/research/registry2.py`): máx UNA tarea en vuelo puede declararlos; el orquestador
  verifica antes de cada despacho contra las tareas activas.
- Implementadores NO tocan archivos fuera de su lista Files (crear tests nuevos en el subtree de sus
  archivos sí está permitido y esperado).
- Implementadores **NUNCA hacen git commit/add/push** (evita carreras de índice). Solo el orquestador
  commitea, tarea por tarea, tras revisar el diff.
- Contratos CT-1..CT-9 congelados: si un implementador cree que un contrato está mal, PARA y reporta;
  jamás lo cambia unilateralmente. Cambio de contrato = enmienda del plan por el orquestador.

## 4. Memoria y estado (sin corrupción entre agentes)
- **Solo el orquestador escribe**: ledger del plan, tracker (`~/.claude/brains/D--FOREX/project/tracker.md`),
  thread, memoria. Los subagentes reportan; NUNCA escriben en Capa-1/2/4 ni en `~/.claude/**`.
- Ledger se tickea SOLO tras: diff revisado + gate verde + commit hecho. Formato: `[x]` + hash corto + duración.
- Fin de cada turno del orquestador: primeras líneas del mensaje = estado técnico clave (crumb anti-interrupción).
- Handoff de sesión: /brain handoff (thread reescrito UNA vez, secciones volátiles reemplazadas).

## 5. Preámbulo de despacho (COPIAR VERBATIM en cada prompt de subagente, + el bloque de tarea del plan)
```
Eres un implementador Sonnet en el proyecto SENTINEL (D:\FOREX). Ejecuta EXACTAMENTE la tarea de abajo.
REGLAS DURAS:
1. SOLO puedes crear/modificar los archivos listados en Files (+ tests en su subtree). NADA más.
2. NO hagas git commit/add. NO escribas en tracker/brain/memoria/docs. NO toques contratos CT-*.
3. TDD: test que falla → implementación mínima → test verde. Sin refactors fuera de spec. Sin deps nuevas.
4. Windows 10+11: pathlib, encoding="utf-8" explícito. Sin supuestos WSL.
5. Gate al final: [COMANDO DEL GATE DE LA TAREA]. Pega el output resumido.
6. OBJETIVO ≤10 minutos. Si a los 2 intentos algo sigue fallando: DETENTE y reporta el bloqueo.
7. Si la spec es ambigua en algo: elige la interpretación más simple que cumpla el contrato y DECLÁRALA
   en DESVIACIONES (no inventes alcance).
REPORTE FINAL (≤30 líneas): FILES: (creados/modificados) | TESTS: (nombres + PASS/FAIL) |
GATE: (comando + resultado) | DESVIACIONES: (o "ninguna") | NOTAS: (1-3 líneas).
```

## 6. Loop del orquestador
1. Elegir tareas `Ready` (columna Ready-when satisfecha) sin colisión de archivos; despachar ≤3 (1/lane).
2. Al completar: leer reporte → diff review rápido (correcto vs spec, sin archivos extra, sin deps) →
   correr gate si el reporte no lo prueba → commit `feat(<task-id>): <resumen>` (+Co-Authored-By Sonnet) →
   tickear ledger → despachar siguiente.
3. **Review batched** (regla de memoria vigente): review PROFUNDO por LOTE al cierre de cada Wave
   (no por tarea); paridad golden SIEMPRE antes de cerrar Wave. /code-review al cierre de Waves A y B.
4. Tareas UI: verificación navegador headless obligatoria al cierre de Wave (regla de memoria:
   elementFromPoint/interacción real, no razonar) — ORC-5 mantiene el checklist.
5. Waves C/D/E: al inicio de la wave el orquestador EXPANDE cada bloque de tarea a pasos TDD completos
   (writing-plans estándar) usando los contratos ya congelados; E sólo tras cerrar E0 con el usuario.
6. Ante task-notification con duración >12/20/35 min: aplicar §2.

## 7. Verificación y calidad
- Gate rápido por tarea (subset); NUNCA la suite completa (tests/opt ~30min prohibido en subagentes).
- Paridad golden intocable; cualquier rojo en golden = STOP total del pipeline hasta resolver.
- Presupuestos perf del plan son criterios de aceptación testeables (payload cap, vlist, heap budget manual).
- e2e del día (meta del usuario): al cerrar Wave A+B correr ORC-5 (servicio :8601 + navegador headless:
  charts window+TF switch+indicadores, TV split/dot/replay, positions cards, run launcher happy-path).

## 8. Costos
- Prompts de despacho mínimos: preámbulo §5 + bloque de tarea + SOLO los contratos CT-* que la tarea consume.
- Sin subagentes "exploradores" salvo bloqueo real. Sin re-lecturas de docs largos por implementadores.
- Modelos: implementación 100% Sonnet 5; mini-eval usa sonnet+haiku según C6; Opus 4.8 solo en E2 runtime (producto, no implementación).
