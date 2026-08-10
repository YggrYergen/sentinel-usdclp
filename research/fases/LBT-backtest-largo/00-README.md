# FASE LBT — BACKTEST LARGO REAL-TICK

## Objetivo

Re-correr las configuraciones que pasaron la puerta estadística sobre **2–4 años de ticks reales**
(AVA + overlay de costos Capitaria validado), para distinguir lo robusto de lo que solo funcionó
en la ventana de 7 meses.

## Gate de entrada

Puerta estadística superada · T0.3 (ticks AVA descargados y validados) · **A6 Pata B validada**
(divergencia de feed cuantificada y overlay calibrado).

## Reglas de la fase

- El sustrato es real-tick. `substrate_id` obligatorio, típicamente
  `ava-ticks-<rango>+overlay-capitaria`.
- 🔴 Ninguna cifra AVA-cruda se compara contra cifras Capitaria sin declarar el ajuste. El spread
  de AVA es **menor** (máximo y mínimo), así que el backtest crudo es **optimista** respecto de
  operar en Capitaria.
- La hora muerta se modela como **desplazante** (T0.13). Está prohibido aplicar una máscara horaria
  fija: el dato de 7 meses ya refutó ese supuesto (la hora muerta se movió 19 → 18 → 17).
- Reporte obligatorio de consistencia **inter-anual** e **inter-mensual**, no solo el neto total.
- 🔴 El **holdout no se toca** en esta fase, bajo ninguna circunstancia.

## Criterio de cierre

- [ ] Todas las configs candidatas corridas sobre el período largo
- [ ] Consistencia inter-anual e inter-mensual reportada por config
- [ ] Comparación honesta contra los resultados de 7 meses: qué se sostiene, qué no, qué queda
      indeterminado
- [ ] Configs que dejan de ser netas positivas en el período largo → registro de negativos
- [ ] Memo Opus + revisión batcheada + TRACKER/LEDGER
