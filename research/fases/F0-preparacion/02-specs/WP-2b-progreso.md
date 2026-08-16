# WP-2b — Progreso (bitácora de una línea por bloque)

- **Bloque 0** (2026-08-16): línea de partida medida — paridad `4 passed`; `tests/analysis` `1 failed, 306 passed` (rojo = el que arregla Bloque 1); `tests/research` `300 passed, 4 deselected`; `tests/strategies` `272 passed`. Coincide con la línea de partida esperada del brief (medida en `659a121`).
- **Bloque 1** (2026-08-16): cita por contenido en `test_cita_gate_spread_harness_verificada_contra_el_fichero_real` — verde: `tests/analysis` `307 passed`; paridad `4 passed`; mutación (a) borrar → "desaparecio"; mutación (b) duplicar → ambigüedad con líneas `[400, 401]`; `backtest.py` sin modificar.
