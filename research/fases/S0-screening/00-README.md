# FASE S0 — SCREENING RETROSPECTIVO DE FEATURES

## Objetivo

Evaluar features candidatas sobre posiciones y señales **ya registradas** (costo ~cero, sin
backtests nuevos) y podar la cola con **reglas de decisión fijadas antes de mirar**.

Así se consigue el "de un viaje": las ramas condicionales quedan declaradas desde el día uno y el
proceso solo las poda. El plan está cerrado aunque las respuestas todavía no lo estén.

## Gate de entrada

A0 cerrada.

## Entradas

Dossiers y expectancy condicional de A0 · sustrato reparado · ticks.

## Features a screenear

- Cruces de ATR multi-TF (2, 3 o más timeframes)
- Sumas y combinaciones de momentum (1m + 10m, y otras que tengan sentido)
- Pendiente del Choppiness Index (hipótesis: CHOP decreciente = des-lateralización)
- Crystal Heiken Ashi
- Zonas del indicador Supply & Demand de tienda, **contra** las zonas propias
- Score D1b (número de TFs alineados como nota, no veto)
- Índice de coherencia D1f (1m → H1)
- **F0 kill-criteria de la familia F**: señales/día del gate literal × costo de spread, contra la
  envolvente de edge conocida

## Regla de decisión (pre-fijada — charter §A.3)

> Separación con intervalo de confianza que **excluye 0** → su grilla entra a la cola de la fase GR.
> Si no → `research/NEGATIVOS.md`, con su evidencia, y **no se corre**.

🔴 **Ninguna feature se poda por prior del orquestador.** "Esto seguro correlaciona con lo que ya
tenemos" no es un criterio: se mide. Si un indicador difiere un 10 % de otro y ese 10 % es el edge,
solo la medición lo encuentra.

Para los indicadores de tienda se mide **ambas cosas**: valor standalone y valor **incremental**
condicional a los gates existentes.

## Criterio de cierre

- [ ] Toda feature de la lista evaluada, con veredicto de la regla pre-fijada
- [ ] Negativos registrados con su evidencia
- [ ] Cola de grillas de la fase GR emitida y **congelada**
- [ ] Revisión batcheada + memo Opus + backlog + TRACKER/LEDGER
