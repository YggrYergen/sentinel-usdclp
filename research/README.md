# RESEARCH OS — Programa de Investigación XAUUSD 2026-H2

> **PUNTO DE ENTRADA ÚNICO.** Si llegaste acá desde una sesión fresca, un handoff, o un
> despacho de subagente: **este fichero es el mapa**. No ejecutes nada antes de completar
> `protocolos/00-inicio-de-sesion.md`.

---

## Qué es este programa (en 6 líneas)

Investigación exhaustiva para maximizar el desempeño de estrategias sobre **XAUUSD**.
Dos objetivos simultáneos: **(a) pulir las estrategias vivas** (S6 + SuperTrend, que dan neto
positivo consistente en live-test *sin* haber tocado aún las áreas que la literatura señala como
de mayor beneficio — son gemas en bruto), y **(b) buscar edge estructural** en familias nuevas.
**Filosofía:** la composición de mejoras marginales en MUCHAS áreas produce retornos
exponenciales — por eso nada se descarta por "parece menor", y por eso la exhaustividad no es
lujo sino el método. Ejecución **agéntica/sub-agéntica** durante días o semanas, decenas de
sesiones, con cero tolerancia a drift.

## Los 5 ficheros que gobiernan todo

| Fichero | Qué es | Cuándo se lee |
|---|---|---|
| **`CHARTER.md`** | Las 14 reglas doctrinales + §ROUTING + §NORMAS. **Bloques copy-paste obligatorios en TODO brief.** | Siempre. Al inicio de sesión y al armar cada brief. |
| **`TRACKER.md`** | **ÚNICA FUENTE DE VERDAD DEL ESTADO.** Qué se hizo, qué está en curso, qué sigue. | Siempre. Se actualiza al terminar cada tarea. |
| **`DECISIONES.md`** | Decisiones del user, fechadas y vinculantes. | Siempre al inicio; al dudar sobre alcance. |
| **`../docs/superpowers/plans/2026-08-10-plan-investigacion-integral-v4.md`** | **EL PLAN MAESTRO.** Qué hacer, en qué orden, con qué grillas exactas. | Al inicio, completo. Luego por sección. |
| **`LEDGER.jsonl`** | Registro append-only, una línea por experimento, con lineage completo. | Al registrar o rastrear cualquier número. |

## Mapa de carpetas

```
research/
  README.md              ← estás aquí · punto de entrada
  CHARTER.md             ← reglas + routing + normas (copy-paste a briefs)
  TRACKER.md             ← ÚNICA fuente de estado
  DECISIONES.md          ← decisiones del user, fechadas
  LEDGER.jsonl           ← append-only, un experimento por línea
  LEDGER.schema.md       ← esquema y significado de cada campo
  BACKLOG.md             ← observaciones/ideas que NO crean tareas
  NEGATIVOS.md           ← registro de negativos (lo que NO funcionó, con evidencia)
  protocolos/
    00-inicio-de-sesion.md      ← QUÉ LEER Y EN QUÉ ORDEN antes de actuar
    01-skills.md                ← qué skill se invoca en qué momento (obligatorio)
    02-briefs.md                ← plantillas de brief (implementador / investigador / analista)
    03-verificacion.md          ← definición de "hecho" + anti-drift + STOP&escalar
    04-enmiendas-trazabilidad.md ← enmiendas, backlog, tags de lineage
    06-runners.md               ← manifiestos y ejecución por scripts (no por LLM)
  fases/
    README.md                   ← estructura estándar de cada fase
    F0-preparacion/             ← fase actual
    A0-autopsia/
    S0-screening/
    GR-grillas/
    LBT-backtest-largo/
    E-recombinacion/
    HO-holdout/
```

## Estructura interna de cada fase

Toda fase en `fases/<ID>/` usa la MISMA estructura (ver `fases/README.md`):

```
00-README.md          objetivo de la fase, entradas, salidas, criterio de cierre
01-hipotesis/         pre-registros (hipótesis + métrica + regla de decisión) ANTES de correr
02-specs/             specs cerradas para implementadores
03-runs/              manifiestos de corridas (declarativos, los ejecuta un runner)
04-resultados/        capa máquina: JSON/parquet/CSV con tags de lineage
05-analisis/          memos de interpretación (SOLO Opus) — separados de los datos
06-observaciones.md   backlog local de la fase (no crea tareas)
```

## Las tres cosas que jamás se hacen

1. **Interpretar sin ser Opus.** Sonnet reporta números y rutas. Nunca conclusiones.
2. **Declarar "hecho" sin artefacto verificable.** Ver `protocolos/03-verificacion.md`.
3. **Continuar ante una anomalía.** Se hace STOP y se escala al user. Siempre.

## Estado actual

Ver **`TRACKER.md`** — es la única fuente. Este README no lleva estado a propósito
(un README con estado se desactualiza y miente).
