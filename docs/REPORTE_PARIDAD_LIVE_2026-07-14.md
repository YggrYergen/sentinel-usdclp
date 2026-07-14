# Paridad live vs sim — primera sesión armada (2026-07-14)

## Contexto
Primera sesión con el ejecutor **armado** en DEMO 2883015767 (20 configs EMASAR,
XAUUSD, 0.01 lot/ficha, magics 720011-720203). Trading real desde las **01:06 UTC**
(arme 01:03; Algo Trading habilitado 01:05). Deals capturados en `deals_raw`
por `run_deals_watcher` (330+ deals). Checker: `check_live_sim_parity` con
warmup 10k barras, matching de entrada N/N+1 (`ENTRY_NEXT_BAR`) y taxonomía
`SAME_BAR_OPTIMISM`. JSON: `scripts/live/fill_parity_20260714_v2.json`.

## Veredicto global (ventana 01:06 → corte ~02:57 UTC)
- **13/20 configs MATCH** (todas las M5/M15 salvo SS-M5; las M15 no operaron — sin señal, correcto).
- **7/20 DIVERGENCE, 32 hard** — concentradas en M1/M2 (SS-M2, V06D-M2, V15-M2,
  V13-M2, V11-M2, SS-M1, SS-M5). Trazables a incidentes operativos puntuales,
  no a lógica de señal:
  1. Ventana **Algo Trading OFF** (01:03-01:05): señales del sim sin posición live.
  2. **OPEN rechazado 10016** (02:46, mercado rápido, SL inicial ilegal): entradas
     perdidas o corridas 1-2 barras → cascada de estado en configs de ciclo corto.
  3. **MODIFY 10016** (SL trail dentro de stops_level=50 pts): SL desactualizado
     ~1 min en dos episodios; se auto-sanó por reintento.

## Gaps cuantificados (costo en $ por oz, fichas de 1 oz)
- **Same-bar exits** (by design, no divergencia): |gap| total **~$111.8** en ~2h,
  dominado por SS-M1 ($27.5) y SS-M2 ($20.5) — las configs de trail ~1 pip.
  El neto FIRMADO del ejecutor osciló entre +$7.9 y -$18.4 según el tramo:
  el gap va a favor o en contra según la dirección del tick posterior; el neto
  de sesión completa es el árbitro económico (D90).
- **Slippage de entrada** (fill en barra N+1, esperado): total **~$13.9**,
  mediana ~$0.2-0.3/ficha; SS-M1 concentra $5.5.
- Precios de salida con match: dentro de tolerancia (spread+tick).

## Mitigaciones ya implementadas (activan al reiniciar el ejecutor)
- Clamp de SL a banda legal del broker en **MODIFY y OPEN** (re-fetch de tick por
  intento, fallback close si el stop ya cruzó, contadores `sl_clamp_cost`).
- `--confirm-account` (autorizado por el usuario) + watchdog
  `INICIAR_TRADING_LIVE.bat` para operación continua.
- Alarma de piso: balance/equity ≤ 30.000.000 CLP → kill-switch STOP automático.

## Lectura para D90
La maquinaria de medición está operativa: cada sesión produce el neto firmado
same-bar por config (audit log) y el desglose del checker. Las configs 0.01
(SS-*) son las de mayor exposición al gap, como predijo la auditoría. Se
requieren más horas de sesión (idealmente sesión europea/US con spread distinto)
antes de emitir veredicto económico.
