# FASE GR — OLA DE GRILLAS

## Objetivo

Correr las grillas de las familias **B · C · D · LS · F · G · H** sobre sustrato real-tick, con
harness pareado y ejecución por runners.

## Gate de entrada

S0 cerrada (cola congelada) + umbrales operacionales de la puerta estadística fijados con el user
(cuántos meses positivos de N para "consistencia", nivel de confianza, q del FDR).

## Reglas de la fase

- Toda grilla lleva su **pre-registro** en `01-hipotesis/` **antes** de correr: hipótesis, grilla
  exacta, sustrato, métrica, regla de decisión, y qué NO podrá concluirse con ese diseño.
- Todo corre sobre **copias** de las estrategias (charter §A.11 — R1-bis). Los vivos no se tocan.
- Manifiestos declarativos en `03-runs/`; los ejecuta un **runner**, no un LLM (protocolo 06).
- **Harness pareado siempre que aplique**: K políticas de salida sobre un mismo stream de entradas.
  Es la mayor palanca de potencia estadística del programa — elimina la varianza común.
- Sin priors direccionales: toda grilla incluye `off` y ambas direcciones.
- **Regla de meseta**: meseta detectada → refinar con paso ≤0.25. Un pico aislado es sospecha de
  sobreajuste, no un hallazgo.
- Lote estandarizado idéntico en todo; resultados en unidades por-lote **y** en R.
- **Familia C**: C0 (análisis de episodios, de A0) va primero; la grilla se diseña con sus resultados.
- **Familia E NO pertenece a esta fase** — está gateada tras el checkpoint E0.

## Orden interno sugerido

B (salidas — el área de mayor presupuesto, porque con 0 TP toda la captura vive ahí) ·
C (companion obligatorio de B) · D (entradas, zonas, régimen) · LS (concurrencia direccional) ·
F (familia del trader) · G (composición, embudo) · H (lateralidad, si A0 la confirmó).

## Criterio de cierre

- [ ] Todas las grillas de la cola corridas, con lineage completo en el LEDGER
- [ ] Resultados agregados por familia y **comparables entre sí**
- [ ] Negativos registrados
- [ ] Memos de interpretación por familia (Opus)
- [ ] Revisión batcheada + backlog + TRACKER/LEDGER
