# DIAG-P03 -- progreso (una linea por bloque)

- Leido CHARTER.md, commit `1c7279d` (preregistro ampliado E-04), WP-2b-reporte.md,
  OLA1-EXEC-reporte.md, manifiesto `03-runs/2026-08-16-ola1.yaml`, `_brazos.txt`/`metricas.json`
  de `04-resultados/OLA1/P03-S6/` -- confirmado 95/95 brazos con `n=624`, `net_lote1=40246087.50`
  byte-identico, incluido `ac_off`.
- Localizado el condicional (`ac_desacelerando`, `sentinel_engine/strategies/emasar_ref.py:291-307`)
  y su punto de consumo (`sentinel_engine/strategies/emasar_variant.py:992-1003`).
- Confirmado por lectura que `overlay_kwargs` (`scripts/analysis/realtick_bt/overlay.py:19-30`)
  parte de `backtest._GL["S6-K2P0"]` (kwargs VIVOS), que trae `ac_modulate=True,
  ac_modulate_factor=0.25, trail_atr_floor_k=2.0` (`sentinel_engine/strategies/live_configs_20.py:256-257`,
  `_GOLIVE_BASE_M15` linea 235) -- el mecanismo SI esta activo por defecto en el brazo `default`.
- Escrito `research/fases/F0-preparacion/02-specs/diag_p03_activacion.py` (unico script de
  diagnostico, no toca el motor): serie AC + conteo de disparo sobre las 8.334 barras del
  sustrato Ola 1 (`scripts/research/ola1/sustrato.py:cargar_barras`), ATR14 Wilder sobre el mismo
  sustrato, comparacion contra el piso `trail_atr_floor_k*ATR14`, y un spy en memoria (revertido al
  terminar, sin tocar ficheros) sobre `ac_desacelerando` durante una unica corrida real de
  `simular_variant` para `default` y para `ac_off`.
- Primera corrida: bug de ruta (`parents[2]` en vez de `parents[1]`) escribio en
  `research/fases/04-resultados/...` (directorio nunca antes existente). Detectado, borrado el
  directorio espurio (no rastreado por git, sin impacto), corregido el `Path`, re-corrido.
- Corrida final OK: `research/fases/F0-preparacion/04-resultados/OLA1/P03-S6/diag_activacion.json`
  escrito. Resultado: el piso ATR domina el 100% de las 8.321 barras con ATR14 valido
  (`frac_floor_domina_trail_MODULADO=1.0`), y el spy confirma 6.306/13.947 disparos reales en la
  simulacion del brazo `default` con `eventos_default == eventos_ac_off` (2.497 eventos, identicos).
- Redactado `DIAG-P03-reporte.md`. Commit de las rutas propias (`diag_p03_activacion.py`,
  `diag_activacion.json`, `DIAG-P03-progreso.md`, `DIAG-P03-reporte.md`).
