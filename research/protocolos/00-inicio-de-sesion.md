# PROTOCOLO 00 — INICIO DE SESIÓN

> **OBLIGATORIO.** Aplica a toda sesión fresca, todo handoff y toda continuación del programa.
> **No ejecutes ninguna acción del programa antes de completar estos 6 pasos.**
> Este protocolo existe porque en handoffs anteriores la sesión fresca dejó de seguir las normas.

---

## Los 6 pasos, en orden

**1 · Lee el pinned del brain** (se inyecta solo al arrancar). Contiene las reglas duras
permanentes y el puntero a este programa.

**2 · Lee, completos y en este orden:**
   1. `research/README.md` — el mapa
   2. `research/CHARTER.md` — las 14 reglas + §ROUTING + §NORMAS
   3. `research/TRACKER.md` — **el estado real** (única fuente)
   4. `research/DECISIONES.md` — decisiones vinculantes del user
   5. `docs/superpowers/plans/2026-08-10-plan-investigacion-integral-v4.md` — el plan maestro

**3 · Invoca las skills que correspondan** — ver `protocolos/01-skills.md`.
   Como mínimo, antes del primer despacho paralelo de la sesión:
   `superpowers:dispatching-parallel-agents`; y para el ciclo por tarea:
   `superpowers:subagent-driven-development`.

**4 · Verifica que la fase previa esté `[x]`** en el TRACKER antes de despachar cualquier cosa de
   la fase siguiente. Si no lo está, no se despacha: se completa o se escala.

**5 · Comprueba los bloqueos activos** (sección BLOQUEOS del TRACKER). Si tu tarea depende de un
   bloqueo abierto, **no la empieces**: repórtalo al user.

**6 · Antes de citar cualquier número:** confirma su lineage en `LEDGER.jsonl`. Si un documento
   en prosa cita una cifra, **re-lee el JSON/artefacto de origen** — hay prosa histórica
   desactualizada en el repo (ver charter §A.9 y la lista de cuarentenas del plan §12).

---

## Preguntas que debes poder responder antes de actuar

Si no puedes responder las cinco, **no has completado el protocolo**:

1. ¿En qué fase está el programa y cuál es el criterio de cierre de esa fase?
2. ¿Cuál es la siguiente tarea ejecutable, y está desbloqueada?
3. ¿Qué modelo debe ejecutarla y en qué rol (implementador / investigador / analista)?
4. ¿Qué artefacto exacto (ruta) debe existir para poder declararla "hecha"?
5. ¿Qué decisiones del user restringen lo que puedes hacer en esa tarea?

---

## Lo que NUNCA se hace al arrancar

- Empezar a explorar el repo "para entender" antes de leer el TRACKER. El estado está escrito;
  no se re-deriva leyendo código.
- Re-correr o re-medir algo ya marcado `[x]` sin causa escrita — cuesta tiempo y contamina el
  registro.
- Confiar en la memoria de una sesión anterior. Si no está en TRACKER, LEDGER, DECISIONES o el
  plan, **no existe**.
- Asumir que un número recordado sigue vigente. Ver paso 6.

---

## Cierre de sesión / handoff

Al terminar una sesión que hizo trabajo del programa:
1. TRACKER actualizado (estado en una línea + filas de tareas + bitácora).
2. LEDGER con las filas de los experimentos corridos.
3. Backlog local de la fase actualizado si surgieron ideas (`06-observaciones.md`) — recordar
   que el backlog **no crea tareas** (charter §A.10).
4. Handoff del brain vía la skill `brain` (`/brain handoff`), **update NO destructivo**.
