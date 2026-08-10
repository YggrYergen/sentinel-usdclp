# PROTOCOLO — REVISIÓN DE LITERATURA INFORMAL (28 videos)

> **Dictado por el user, 2026-08-10. De cumplimiento obligatorio y literal.**
> Tarea T0.11b del TRACKER. **NO EJECUTAR** hasta que el plan esté cerrado y el user lo indique.
> Estado de la etapa previa: T0.11a ✅ — 28/28 transcripciones descargadas, **ninguna leída**.

---

## Regla de hierro (aplica a TODA esta tarea)

🔴 **UN VIDEO = UN CONTEXTO DE ANÁLISIS.** Jamás se mezclan dos videos en la misma pregunta ni en
el mismo contexto de subagente. Compartimentación total, para que lo que dice un video no tiña ni
envenene la interpretación de otro.

---

## Datos de partida

- Transcripciones: `data/literature/youtube_transcripts/<videoId>.txt`
- Lista y orden: `data/literature/youtube_transcripts/urls.txt`
- Total del corpus: **~233.723 tokens** (28 videos)

### Bloque 1 — 20 videos bajo 8k tokens

| videoId | ~tokens | | videoId | ~tokens |
|---|---:|---|---|---:|
| `jU2YQC7TC0k` | 3.231 | | `_UmlGzR88Fs` | 1.725 |
| `en8RMFRqSME` | 7.798 | | `RetsRS5u-8Q` | 5.430 |
| `bITIVwysCzM` | 4.296 | | `C_R4sLaM0eo` | 7.885 |
| `fV02FcLmFpA` | 6.207 | | `FbuYWdwA_wU` | 7.474 |
| `B4ch-Lf8wJc` | 2.333 | | `KML09tRtHM8` | 5.283 |
| `fi7OxEzvhjw` | 2.111 | | `PnIkSLm2yRk` | 9.090* |
| `yHAC0xtBR2Q` | 5.161 | | `Fb7G5SNpaes` | 6.238 |
| `nkMzaQqpFbw` | 4.560 | | `6njREUQAFdg` | 5.219 |
| `h52a9zFp1d8` | 2.592 | | `nLQhKkjkuWI` | 5.593 |
| `R24f53OtTgE` | 4.410 | | `wm4A6qo0g3I` | 8.682* |
| `lYmmBoYQvWM` | 6.564 | | `uGMen58jwxE` | 5.245 |

\* `PnIkSLm2yRk` (9.090) y `wm4A6qo0g3I` (8.682) superan levemente los 8k pero están muy por
debajo de 15k: van en el Bloque 1. Total del bloque: 21 videos ⇒ ver nota de reparto abajo.

### Bloque 2 — videos grandes (lectura parcial primero)

| videoId | ~tokens | Título abreviado |
|---|---:|---|
| `znSRU984kc8` | 30.039 | Elite Scalper — pattern of trading champions |
| `m5zu_X-_51I` | 26.696 | $1.000.000 en 51 días |
| `oDK0hbAMWbU` | 15.892 | $50 → $21.873 en 10 trades |
| `ksVXut9bSSg` | 15.796 | Complete Trading System Revealed |
| `xGIa8Vg0PWM` | 15.356 | $2k → $65.662 en 30 días |
| `hC4g7qY6UcQ` | 12.817 | Risk Management Masterclass (100M trader) |
| `oDK0hbAMWbU`… | — | *(ver nota)* |

Los ≥12k tokens son **6** videos. La instrucción del user habla de "los 8 restantes sobre 15k":
la lista real arroja 5 videos ≥15k y 1 de 12,8k. **Reparto a confirmar con el user al ejecutar**:
la interpretación por defecto es tratar como Bloque 2 los **6 videos ≥12k** y repartirlos 3+3
entre los dos subagentes (en vez de 4+4).

---

## ETAPA 1 — Bloque 1 (los chicos), lectura completa

**Despacho:** **2 agentes orquestadores Sonnet 5 high effort**, cada uno responsable de la mitad
del bloque. Cada orquestador despacha **1 subagente Haiku max effort por video** (≈10-11 cada uno).

```
Controlador (Opus 5 high, este chat)
├── Orquestador A · Sonnet 5 high  →  ~11 subagentes Haiku max effort (1 por video)
└── Orquestador B · Sonnet 5 high  →  ~10 subagentes Haiku max effort (1 por video)
```

**Restricciones del despacho:**
- Cada subagente Haiku lee **UN SOLO** fichero de transcripción. Nunca dos.
- Los subagentes son **REPORT-ONLY** (plantilla B de `protocolos/02-briefs.md`): extraen lo que el
  video dice; no evalúan si es bueno, ni lo comparan con nuestro sistema, ni recomiendan.
- Prohibido a los orquestadores Sonnet interpretar o sintetizar juicio: consolidan y reportan.
- **La interpretación la hace el controlador Opus, en este chat, cuando lleguen los 21 reportes.**

**Qué extrae cada subagente (por video, formato fijo):**
1. Estrategia(s) descrita(s): entradas, salidas, gestión, timeframes, instrumentos.
2. Reglas concretas y parámetros numéricos mencionados (valores exactos).
3. Indicadores usados y cómo.
4. Gestión de riesgo / sizing / re-entradas.
5. Afirmaciones sobre resultados (y si aportan evidencia o no).
6. Cualquier mención de: zonas S/R, momentum, ATR, régimen/lateralidad, trailing/ratchet,
   noticias, oro/XAUUSD específicamente.
7. Qué NO cubre el video.

**Salida:** `research/fases/F0-preparacion/04-resultados/videos/<videoId>.md`, con tags de lineage.

---

## ETAPA 2 — Consolidación (controlador Opus, en el chat)

Se **espera a tener los 21 reportes**. El controlador los analiza en este chat: qué temas se
repiten, qué es aplicable a nuestro contexto (XAUUSD, nuestros timeframes, nuestro spread), qué
contradice o confirma la literatura formal, y qué entra al catálogo como candidato de grilla.

---

## ETAPA 3 — Bloque 2 (los grandes), lectura parcial primero

**Solo después** de la Etapa 2.

**Despacho:** **2 subagentes Sonnet 5 medium effort**, cada uno lee los **primeros ~800 tokens**
de sus videos asignados (3 y 3 según la nota de reparto, o 4+4 si el user lo confirma así).

**Criterio de decisión (lo aplica el controlador Opus, no los subagentes):**
> Si por lo que dicen en su inicio parece que vale la pena revisarlos en detalle, se hace —
> **considerando lo ya aprendido en los 21 videos del Bloque 1**. Si van a hablar de temas
> repetidos o no alineados con el objetivo, **no vale la pena** y no se leen completos.

Cada decisión (leer completo / descartar) se registra con su razón en
`research/fases/F0-preparacion/05-analisis/videos-bloque2-triage.md`.

---

## Presupuesto y routing

- Bloque 1 completo: ~120k tokens de entrada, repartidos en 21 contextos Haiku aislados.
- Bloque 2 etapa parcial: ~4.800 tokens (6 × 800).
- Bloque 2 completo (si se decidiera leer todo): ~117k adicionales — por eso el triage existe.
- Alternativa evaluable en su momento: Vertex AI / Gemini con los ~USD 100/mes de créditos
  disponibles, para el Bloque 2 completo. Decisión del user con los números en mano.
