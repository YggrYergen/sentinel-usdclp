# FASE A0 — AUTOPSIA DE POSICIONES

## Objetivo

Producir el inventario cuantitativo **y cualitativo** de CADA posición tomada por las estrategias
ganadoras: no solo el resultado, sino **el camino por el que pasó para llegar ahí**. Es el insumo
que calibra el diseño de salidas (B), re-entradas (C), zonas (D2) y lateralidad (H). Nunca se ha
hecho un análisis propio de este tipo — hasta ahora solo se han mirado netos y drawdown.

## Gate de entrada

F0 cerrada (motor congelado + A6 verde) · motor mod #11 (instrumentación de camino) implementado ·
matriz de indicadores cerrada con el user (plan §5.2).

> ⚠️ La matriz de indicadores debe cerrarse **antes** de instrumentar: añadir un indicador después
> obliga a re-correr la autopsia completa.

## Entradas

Historial de la cuenta 902 · historiales MT5 de las demás cuentas (~3 meses en suma) · ~2.542
posiciones del sustrato reparado · ticks Capitaria de las ventanas correspondientes.

## Salidas

| Salida | Ruta |
|---|---|
| Dossiers de 4 capas por posición | `04-resultados/dossiers/` (parquet) |
| Expectancy condicional por covariable | `04-resultados/expectancy-condicional/` |
| Episodios de re-entrada (insumo de C0) | `04-resultados/episodios/` |
| Curvas de recuperación | `04-resultados/recuperacion/` |
| Inventario escrito en formato tesis | `05-analisis/inventario-posiciones.md` |

## Las 4 capas del dossier

1. **Contexto de entrada** — snapshot de la matriz de indicadores al abrir.
2. **Camino** — MFE/MAE en el tiempo (tick/M1) + evolución de los indicadores durante la vida.
3. **Contexto de salida** — qué la cerró, estado de los indicadores, y qué hizo el precio DESPUÉS
   (¿fue buena la salida ex-post?).
4. **Contrafactuales** — qué habrían hecho K salidas alternativas sobre esa misma entrada.

## Preguntas que esta fase debe responder

- ¿Qué fracción de las perdedoras estuvo en verde, y cuánto?
- Cuando una posición está en negativo, ¿cuántas veces históricamente se recuperó, y desde qué
  profundidad de MAE / tiempo bajo agua?
- **C0:** ¿las grandes ganadoras fueron re-aperturas tras una reversión pequeña, o ahí se esconde
  un porcentaje grande de las pérdidas?
- ¿Es cierta la hipótesis de lateralidad, y qué significa empíricamente "suficientemente lateral"?
- ¿Qué covariables separan expectancy de forma estable (mismo signo en descubrimiento y confirmación)?

## Criterio de cierre

- [ ] Dossier completo para el 100 % de las posiciones alcanzables; las no alcanzables, declaradas
- [ ] Expectancy condicional con **split descubrimiento/confirmación** y **FDR** aplicado
- [ ] C0 respondido con datos, no con razonamiento
- [ ] Hipótesis de lateralidad con veredicto: confirmada / refutada / indeterminada
- [ ] Curvas de recuperación disponibles para B9-hazard y B2-P
- [ ] Todo hallazgo convertido en hipótesis pre-registrada para las fases siguientes
- [ ] Revisión batcheada + memo Opus + backlog + TRACKER/LEDGER

## Riesgos

Comparaciones múltiples masivas ⇒ FDR y split obligatorios. Riesgo real: encontrar cosas
**espurias** y tratarlas como descubrimientos — por eso nada pasa a grilla sin pre-registro.
