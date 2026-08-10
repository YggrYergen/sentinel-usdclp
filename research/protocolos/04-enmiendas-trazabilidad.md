# PROTOCOLO 04 — ENMIENDAS, BACKLOG Y TRAZABILIDAD

---

# PARTE 1 · ENMIENDAS

## Por qué existe este protocolo

El objetivo es **cero drift**: que el plan se ejecute como fue diseñado. Pero un programa de
semanas **va a** encontrar sorpresas (precedente real: dos bugs de instrumento invalidaron un
track completo, y dos confounds aparecieron antes de correr una fase). Prohibir toda enmienda
haría que las sorpresas se resolvieran de forma silenciosa e indocumentada — que es exactamente
el drift que queremos evitar. La solución es **gobernar** la enmienda, no fingir que no ocurrirá.

## Reglas

1. **Solo en fronteras de fase.** Jamás a mitad de un experimento. Las grillas quedan congeladas
   mientras la fase corre.
2. **Con causa escrita**: qué se descubrió, por qué invalida o extiende lo planeado, qué cambia
   exactamente, y qué resultados previos quedan afectados.
3. **Firmada por el user** si toca: alcance, grillas, criterios estadísticos, el motor congelado,
   o cualquier decisión de `DECISIONES.md`.
4. **Aditiva**: la enmienda se añade al plan como sección fechada; el texto original no se borra.
5. **Registrada** en el TRACKER (bitácora) y en el LEDGER si afecta experimentos.

## Formato

```markdown
### ENMIENDA E-nn · <fecha> · <título>
**Fase / frontera:** <cuál>
**Causa:** <qué se descubrió, con evidencia — ruta del artefacto>
**Cambio exacto:** <qué se añade / modifica / congela>
**Afecta a:** <experimentos, tareas o conclusiones previas>
**Re-validación requerida:** <sí/no — qué hay que re-correr>
**Firmada por:** <user / controlador>
```

## Excepción: el motor congelado

Cualquier cambio al motor después del freeze exige, además: re-correr la suite golden **y** la
fidelidad empírica A6 completa, y registrar el nuevo SHA en el TRACKER. Todo experimento corrido
bajo el SHA anterior queda etiquetado con ese SHA y **no es directamente comparable** con los
posteriores hasta demostrar equivalencia.

---

# PARTE 2 · BACKLOG

**El backlog NO crea tareas.** Es donde van las ideas, observaciones y "esto habría que mirarlo"
que surgen mientras se ejecuta. Se revisa **solo en la frontera de fase**, y ahí se decide qué se
promueve (vía enmienda) y qué se queda anotado.

- Backlog **local de fase**: `fases/<ID>/06-observaciones.md`
- Backlog **global**: `research/BACKLOG.md`

Formato de entrada: `<fecha> · <quién> · <observación> · <de dónde salió: ruta/experimento>`.

Escribir en el backlog es **obligatorio** cuando un agente detecta algo interesante fuera de su
alcance — así no se pierde, y así tampoco descarrila la tarea en curso.

---

# PARTE 3 · TRAZABILIDAD

## Esquema de tags (obligatorio en todo artefacto)

| Campo | Qué es | Ejemplo |
|---|---|---|
| `run_id` | Identificador único de la corrida | `GR-B1-0007` |
| `area` | Familia / área del catálogo | `B` |
| `experimento` | ID del experimento pre-registrado | `B1-be-grid` |
| `config_hash` | Hash de la configuración exacta | `sha256:9f2c…` |
| `substrate_id` | Qué datos se usaron | `capitaria-ticks-2026H1-repaired` |
| `engine_sha` | SHA del motor congelado | `4019654` |
| `git_sha` | SHA del repo al correr | `41fdb25` |
| `etapa` | Fase del programa | `F0` / `A0` / `GR` |
| `generador` | Quién/qué lo produjo | `runner:backtest_queue.py` / `agent:sonnet-impl` |
| `timestamp` | Cuándo (hora servidor, UTC−4) | `2026-08-10T05:12:00` |

## `substrate_id` — vocabulario controlado

Es el tag más importante y el que más daño evita. Valores válidos:

- `capitaria-ticks-<rango>` — ticks reales Capitaria (**sustrato de veredicto**)
- `ava-ticks-<rango>` — ticks AVA (**sustrato de veredicto** solo con overlay validado en A6-Pata B)
- `ava-ticks-<rango>+overlay-capitaria` — AVA con overlay de costos aplicado
- `bars-M15-<rango>` — 🔴 **NON-VERDICT**: solo estadísticas de señal sobre cierres
- `repaired-7m` — el sustrato de 7 meses posterior a la reparación del instrumento
- `pre-repair` — 🔴 **HISTÓRICO, NO USAR** para conclusiones
- `live-902-<rango>` — historial real de la cuenta live-test (solo lectura)

**Regla dura:** ningún artefacto sin `substrate_id`. Ningún veredicto sobre `bars-*` o `pre-repair`.

## LEDGER

`research/LEDGER.jsonl` — un objeto JSON por línea, append-only. Ver `LEDGER.schema.md`.
Se escribe **al terminar** cada experimento, por el runner (preferido) o por el agente.
Nunca se edita una línea existente: para corregir, se añade una nueva con
`supersedes: "<run_id>"` y `reason`.

## Prueba de aceptación del sistema

> Toma cualquier número de cualquier documento del programa. Debes poder llegar, en menos de un
> minuto y sin preguntarle a nadie, a: qué experimento lo produjo, con qué configuración, sobre
> qué sustrato, con qué versión del motor, quién lo generó y cuándo.

Si eso no se cumple, el sistema de trazabilidad está roto y arreglarlo es prioritario sobre
seguir midiendo.
