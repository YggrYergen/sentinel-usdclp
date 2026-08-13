# PROTOCOLO 01 — SKILLS OBLIGATORIAS POR MOMENTO

> Las skills no son opcionales en este programa. Si una aplica, se invoca **antes** de actuar.
> Regla general de Superpowers: si hay ≥1 % de probabilidad de que una skill aplique, se invoca.

---

## Tabla de obligatoriedad

| Momento | Skill | Obligatoria |
|---|---|---|
| Arranque de cualquier sesión | `superpowers:using-superpowers` (se auto-inyecta) + `protocolos/00-inicio-de-sesion.md` | ✅ |
| Antes del **primer despacho paralelo** de la sesión | `superpowers:dispatching-parallel-agents` | ✅ |
| Ciclo por tarea (brief → implementa → verifica) | `superpowers:subagent-driven-development` | ✅ |
| Ejecutar un plan ya escrito, en esta sesión | `superpowers:executing-plans` | ✅ (alternativa a la anterior) |
| **Toda** tarea de código, sin excepción | `superpowers:test-driven-development` (rojo → mínimo → verde → commit) | ✅ · ⚠️ **una excepción acotada: ver D-47** |
| Antes de declarar CUALQUIER tarea terminada | `superpowers:verification-before-completion` | ✅ |
| Escribir el plan detallado de una fase (en su frontera) | `superpowers:writing-plans` | ✅ |
| Revisión de código | `superpowers:requesting-code-review` — **batcheada a fin de fase**, no por tarea | ✅ |
| Recibir feedback de revisión | `superpowers:receiving-code-review` | ✅ |
| Antes de cualquier trabajo creativo/de diseño nuevo | `superpowers:brainstorming` | ✅ |
| Ante cualquier bug, fallo de test o comportamiento inesperado | `superpowers:systematic-debugging` | ✅ |
| Aislar trabajo de una fase larga del workspace actual | `superpowers:using-git-worktrees` | Según el caso |
| Cierre de sesión / handoff | skill `brain` (`/brain handoff`, update **NO destructivo**) | ✅ |
| Transcripciones de YouTube | `yt-transcripts` | ✅ para esa tarea |
| Cualquier gráfico, tabla visual o dashboard | `dataviz` (+ `artifact-design` si es artifact) | ✅ para esa tarea |

---

## Reglas de aplicación

**Prioridad:** las skills de *proceso* van primero y fijan el enfoque; las de *implementación*
lo ejecutan. "Construyamos X" → `brainstorming` primero. "Arregla este bug" →
`systematic-debugging` primero.

**Anuncio:** al invocar una skill, se anuncia — "Uso [skill] para [propósito]" — y si trae
checklist, se crea un todo por ítem.

**Prohibido racionalizar la omisión.** "Es una pregunta simple", "primero necesito contexto",
"me acuerdo de esa skill", "es overkill" — todos son señales de que SÍ hay que invocarla.
Las skills evolucionan: recordar una no equivale a haberla leído.

**Precedencia:** instrucciones del user > CLAUDE.md / charter del programa > skills >
comportamiento por defecto. Una skill nunca sobrescribe una decisión del user
(`research/DECISIONES.md`).

**En briefs de subagente:** si la tarea es de código, el brief debe **exigir explícitamente**
`test-driven-development` y `verification-before-completion`, y decir que se rechazará la entrega
que no muestre la salida real de los tests.

---

## ⚠️ Única excepción vigente al TDD obligatorio — D-47 (2026-08-13, instrucción del user)

**Alcance: EXCLUSIVAMENTE las 12 modificaciones de motor de T0.6** (plan §4.1). Fuera de T0.6 esta
excepción **no aplica**, y ningún brief puede invocarla por analogía.

Dentro de T0.6 y **sólo** para las mods de vía rápida (**1, 3, 4, 5, 6, 7, 8, 9** — las puramente
aditivas), se sustituye el ciclo TDD completo por un **smoke test breve, y sólo donde la mod tenga
lógica no obvia**. Las mods **2, 10, 11 y 12** van por **vía normal**: spec propia y TDD completo,
porque tocan un camino compartido o cambian una semántica existente.

🔴 **Lo que NINGÚN brief de T0.6 puede omitir**, ni siquiera en vía rápida:
- **La puerta de paridad golden tras CADA modificación**, con el flag obligatorio:
  `pytest tests/research/test_baseline_parity.py -q **-m slow**` → **4 passed en ~2,01 s**.
  ⚠️ **Sin `-m slow` devuelve `4 deselected in 0.03s`**, un verde que no probó nada. El brief exige
  **la salida real pegada**, y una entrega con `deselected` se rechaza.
- **R1-bis** (charter §A.11), sin excepción: los vivos byte-idénticos, todo sobre copias, PARAR y
  escalar quien crea que hay que tocar un original. La vía rápida acelera; **no** afloja esto.
- **Declarar `no corrido`** todo test que no se haya corrido. Está prohibido insinuar una cobertura
  que no existe: eso es exactamente lo que el charter §A.13 llama degradación silenciosa.

`superpowers:verification-before-completion` **sigue siendo obligatoria** también en vía rápida.
Lo que se relaja es cuánto se prueba, jamás la honestidad sobre qué se probó.
