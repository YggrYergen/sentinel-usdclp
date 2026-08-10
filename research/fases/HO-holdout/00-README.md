# FASE HO — HOLDOUT SAGRADO 🔴

## Objetivo

Una única evaluación final, sobre datos que **ninguna decisión del programa tocó jamás**, para
saber qué sobrevive de verdad.

## Por qué existe

Cada vez que se mira un dato y se decide algo (ajustar una grilla, descartar una variante), ese
dato deja de ser evidencia independiente: se "gasta" a través de las decisiones, aunque nunca se
haya usado para entrenar. Con cientos de experimentos, todo el dataset explorado queda contaminado
por el propio proceso de búsqueda y los resultados son optimistas por construcción. El holdout es
el antídoto.

## Gate de entrada

Fase E cerrada + **autorización explícita del user**.

## Reglas — las más duras del programa

1. 🔴 **UNA SOLA PASADA.** Evaluar dos veces quema el holdout y lo invalida para siempre.
2. Las hipótesis y los criterios de éxito se escriben y fechan **ANTES** de abrir nada.
3. 🔴 Prohibido abrir, muestrear, graficar o "echarle un vistazo" al holdout por cualquier motivo,
   durante **todo** el programa, hasta esta fase.
4. El resultado se reporta **tal cual salga** — incluido el caso de que no sobreviva nada. Ese
   también es un resultado válido del programa, y probablemente el más valioso si ocurre.

## Partición sellada

Ver `research/DECISIONES.md` D-01: trimestre más reciente del sustrato combinado + un año completo
**no adyacente** de AVA. Las fechas exactas se registran al sellar (T0.12), contra el rango real
efectivamente descargado.

## Criterio de cierre

- [ ] Hipótesis y criterios escritos y fechados **antes** de la evaluación
- [ ] Una sola pasada ejecutada, con constancia en el LEDGER
- [ ] Resultado reportado sin edulcorar
- [ ] Memo Opus + TRACKER actualizado
