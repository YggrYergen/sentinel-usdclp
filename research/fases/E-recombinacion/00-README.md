# FASE E — ESTRUCTURA Y RECOMBINACIÓN 🔒

## Objetivo

Componer las mejoras validadas: escalera de fichas diferenciada, ensambles por perfil de riesgo,
`stop_and_reverse` como lever, piramidación.

## Gate de entrada — DOBLE

**1 · E0 · CHECKPOINT CONVERSADO CON EL USER (obligatorio).**
Revisión conjunta de **todas** las configs netas positivas + S6/ST, con datos live-demo **y**
backtest real-tick sobre la mesa, discutiendo pros y contras honestamente.

> 🔴 "Ganadora" = **neto positivo** (decisión D-06), **NO** "supera a S6/ST". Ninguna config queda
> fuera de esta conversación por no batir a las vivas, ni por depender de sus top-K.

**2 · OK explícito del user** para arrancar la fase.

## Contenido

| ID | Qué | Nota |
|---|---|---|
| E1 | Escalera de fichas diferenciada | Plantilla heredada de TOKATA (~206 celdas diseñadas y jamás corridas). Los números viejos se descartan; se reutiliza la estructura. En el live actual **no hay ladder** (1 ficha): esto es diseño de investigación |
| E2 | S6+S7 como una sola estrategia de 6 fichas | Evaluar si conserva sentido tras A0 — S7 murió en live |
| E3 | `stop_and_reverse` {on, off} como lever | Lo decide A3 (economía de la reversa) |
| E4 | Piramidación | Último: requiere la información de casi todo el programa |
| E5 | Ensambles por perfil de riesgo | Solo configs que pasaron gates + holdout. **Pesos NO optimizados** (equal-weight / inversa-vol): los pesos de ensamble son otra superficie de sobreajuste |

**Sizing:** la curva tamaño↔drawdown se explora como hipótesis y se **conversa con el user**
(puntos tolerados, pros y contras). El **vol-targeting va al final de todo** — antes rompería la
comparabilidad, que es la directiva #1.

## Criterio de cierre

- [ ] E0 realizado y documentado (con la lista completa de netas positivas revisadas)
- [ ] Configs compuestas evaluadas con la misma puerta estadística que las individuales
- [ ] Memo Opus + revisión batcheada + TRACKER/LEDGER
