# TRACKER — Entrega del lunes 2026-07-27 (campeón/retador)

> **Este archivo es la ÚNICA fuente de verdad del estado.** El plan dice QUÉ hacer; esto dice
> QUÉ SE HIZO. Cada subagente lo actualiza al terminar SU tarea (último paso de cada tarea) y
> commitea el cambio. No se edita a mitad de una tarea.
>
> - **Plan:** `docs/superpowers/plans/2026-07-25-monday-champion-challenger.md`
> - **Spec:** `docs/superpowers/specs/2026-07-25-monday-champion-challenger-design.md`
> - **Rama:** `equipo1`. **Nunca commitear a `alvaro`.**
> - **Deadline:** lunes 2026-07-27, primera hora.

Vocabulario: `[ ]` pendiente · `[~]` en curso · `[x]` hecho · `[!]` bloqueado/escalado.

---

## Rollback point

- **Tag:** `pre-challenger-2026-07-25` → SHA: `dfdc4d7cd34d473484ce20ca4d00f9e2ed52ba37`
- **Procedimiento de rollback:** _(Task 11 lo escribe aquí, 3 niveles)_

## Números que otras tareas necesitan

| Dato | Valor | Origen | Tarea que lo produce |
|---|---|---|---|
| `max_open_fichas` (cap B3) | _pendiente_ | `data/analysis/monday_audit/a2_overlap.json` | Task 8 |
| maxDD @0.1 lot | _pendiente_ (estimación previa: −28,6 %) | `a1_maxdd.json` | Task 7 |
| Cobertura del calendario B2 | _pendiente_ | `data/live/news_calendar.csv` | Task 2 |
| Veredictos de máscara B1–B4 | _pendiente_ | `b6_mask_verdicts.json` | Task 10 |

---

## Estado por tarea

| # | Tarea | Lane | Modelo | Estado | Evidencia / notas |
|---|---|---|---|---|---|
| 0 | Tag de seguridad + punto de revert | — | Sonnet 5 high | `[x]` | tag `pre-challenger-2026-07-25` → `dfdc4d7cd34d473484ce20ca4d00f9e2ed52ba37` |
| 1 | `risk_gates.py` — B1–B4 como lógica pura | B | Sonnet 5 high | `[ ]` | |
| 2 | `news_calendar.py` + calendario commiteado | B | Sonnet 5 high | `[ ]` | |
| 3 | `gap_wait.py` — máquina de estado de B1 | B | Sonnet 5 high | `[ ]` | |
| 4 | `CONFIGS_CHALLENGER` — roster espejo 726xxx | B | Sonnet 5 high | `[ ]` | **bloqueada por Task 8** |
| 5 | Plumbing del executor (gates en el OPEN) | B | **Opus 5 medium** | `[ ]` | la más compleja |
| 6 | Loader de auditoría (2.347 posiciones) | A | Sonnet 5 high | `[ ]` | |
| 7 | A1 — verificar el maxDD | A | Sonnet 5 high | `[ ]` | |
| 8 | A2 — solape, correlación y cap B3 | A | Sonnet 5 high | `[ ]` | **desbloquea Task 4** |
| 9 | A3+A4+A5 — atribución, serial, gate 0.5 | A | Sonnet 5 high | `[ ]` | |
| 10 | Máscaras retrospectivas — veredictos | A/B | Sonnet 5 high | `[ ]` | necesita 6, 8, 2 |
| 11 | Ensayo de revert | B | Sonnet 5 high | `[ ]` | |
| 12 | Despliegue máq1 | B | Sonnet 5 high | `[ ]` | 🙋 **pasos 5-6 = manos del user** |
| 13 | Documento del lunes | — | Opus 5 medium | `[ ]` | |
| 14 | Track C — entrada aleatoria | A | Sonnet 5 high | `[ ]` | **NO bloquea el lunes** |

---

## Criterio de aceptación (spec §9)

- [ ] Sleeve A corriendo, verificablemente idéntico a hoy (snapshot verde).
- [ ] Sleeve B corriendo a 0.02 con B1–B4 activos, en la banda 726xxx.
- [ ] Máscara retrospectiva corrida para cada wrapper, veredicto registrado (veto / no-veto /
      no-evaluable), **sin haberla usado para seleccionar**.
- [ ] Tag de git sobre el commit vivo + revert de un paso probado.
- [ ] Pista A completa, con el maxDD confirmado o corregido.
- [ ] Documento entregado (= emitido; "entregado" de verdad solo tras revisión del user).
- [ ] Pista C corriendo o entregada (no bloquea el lunes).

---

## Reglas de ejecución (doctrina D152 — leer antes de despachar)

- **Implementadores e investigadores = Sonnet 5 high.** Solo Task 5 y Task 13 = **Opus 5 medium**.
- **Máximo 2 subagentes en paralelo**, y nunca dos que escriban archivos que se solapen.
  Lane A (`scripts/analysis/**`, `data/analysis/**`) y Lane B (`sentinel_engine/**`,
  `scripts/live/**`) son disjuntas por diseño: esas dos sí pueden ir juntas.
- **Briefs exhaustivos.** El subagente recibe la tarea COMPLETA copiada del plan + este tracker +
  las Global Constraints. Si tiene que inferir algo, el brief está mal escrito.
- **TDD obligatorio** (`superpowers:test-driven-development`): test rojo → mínimo código → verde →
  commit. Los pasos del plan ya vienen en ese orden.
- **Techo por subagente: ~30 min / ~300k tokens.** Al tocarlo: actualizar este tracker, hacer
  `/brain update` y pasar a un subagente NUEVO de la misma categoría con el estado en la mano.
- **Al terminar cada tarea: actualizar este tracker y commitearlo.** Sin excepción.

## Reglas de honestidad (no negociables)

- **Prohibido re-tunear cualquier parámetro** (R3). Ni un barrido, ni un "probé y este va mejor".
- **Las máscaras VETAN, nunca SELECCIONAN** (spec §4.4). Si te sorprendes comparando variantes de
  un wrapper por su resultado retrospectivo, para: eso es exactamente el error que esta entrega
  existe para no repetir.
- **Todo número lo calcula código** (R5). Ninguna cifra escrita a mano en ningún artefacto.
- **Lo no evaluable se declara no evaluable.** B2 fuera del rango del calendario y B4 sin columna
  de SL no son "sin problema": son "sin evidencia", y así van al documento.

---

## Bitácora

_(cada subagente añade una línea al terminar: fecha ISO · tarea · qué quedó · commit)_

- 2026-07-25 · Task 0 · Tag anotado `pre-challenger-2026-07-25` creado sobre HEAD (`dfdc4d7`, resuelto por `git rev-parse` sin editar a mano); working tree confirmado limpio (`git status --porcelain -uno` vacío) y `git diff 496fecf..HEAD --stat` verificado solo-docs antes de taguear. Punto de revert registrado arriba. · commit `chore(tracker): rollback tag pre-challenger-2026-07-25 recorded`
