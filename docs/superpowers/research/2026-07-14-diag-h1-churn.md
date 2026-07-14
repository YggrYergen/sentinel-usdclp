# Diagnostico H1: churn de la sesion live vs simulador offline (2026-07-14 01:06:02 -> 07:57:05 UTC)

Solo hechos y numeros. Sin hipotesis de causa, sin recomendaciones.

## Fuentes de datos y ventana

- Ventana de sesion: `2026-07-14T01:06:02Z` -> `2026-07-14T07:57:05Z` (6h51m03s).
- Barras: `data/lake/XAUUSD/{1,2,5,15}.parquet` (M1/M2/M5/M15), cobertura confirmada hasta 2026-07-14 07:45-07:53 UTC. Warmup: 10,000 barras antes del primer bar con open-time >= 01:06:00Z, para las 20 configs (ninguna config tuvo warmup insuficiente -- `warmup_note` es `null` en las 20 filas).
- Configs: `sentinel_engine.strategies.live_configs_20.CONFIGS_20` (20 dicts). `symbol` esta incluido en `kwargs` y es aceptado directamente por `simular_variant` (no requiere filtrado).
- Simulador: `sentinel_engine.strategies.emasar_variant.simular_variant`. Se corrio 2 veces por config sobre la MISMA slice de barras (10,000 de warmup + sesion):
  - **CLASSIC**: `simular_variant(bars_slice, **kwargs)` (+ `direction_mask` para V10-M5/V10-M15).
  - **LIVE-FILL**: igual + `live_fill_mode=True`.
- Para V10-M5/V10-M15 (`direction_filter=True`) se calculo `direction_mask` con `scripts.report.gen_variant_batch5.compute_direction_mask(bars_slice)` sobre la misma slice pasada al simulador.
- Audit log: `scripts/live/run_live_20.audit.log`, 54,190 lineas totales. Region armada confirmada por la linea `2026-07-14 01:03:20,155 INFO connected + guard OK: DEMO login 2883015767 (dry_run=False, 20 configs, window=10000)` en la linea 2920. El archivo completo se extiende hasta `2026-07-14 08:56:03` (mas alla del fin de sesion 07:57:05); se filtro estrictamente al intervalo `[01:06:02, 07:57:05]` UTC.
- Deals reales: sqlite `data/research.db`, tabla `deals_raw`, abierta read-only (`mode=ro`). Filtrado por magic en bandas `base+1..base+3` por config (magics 720011-720203). La tabla `trade` en la misma DB es exclusivamente historica de simulacion (`ts_in` max = `2026.07.07 18:52:00`, `origin='strategy'` en el 100% de filas, 0 filas `origin='live'`) -- no aporta datos de la sesion live y no se uso.

## Chequeo de sanidad (hecho critico)

`deals_raw` completo tiene 330 filas, rango de tiempo `MIN(time)=1783991162` (`2026-07-14T01:06:02Z`) a `MAX(time)=1783997658` (`2026-07-14T02:54:18Z`). Es decir, **`deals_raw` cubre solo 1h48m16s de las 6h51m03s de la sesion** (empieza exactamente en el arranque de la sesion pero termina a las 02:54:18 UTC, no a las 07:57:05 UTC).

Como resultado:

| metrica | dato dado (sesion completa) | calculado desde `deals_raw` (parcial, hasta 02:54:18) |
|---|---|---|
| posiciones reales | 1,011 | **174** (distinct `position_id` con deal `IN`, magics 720011-720203) |
| PnL real | -712,142 CLP (~-762.9 USD) | **-78,517.72 CLP** (~-84.11 USD) |
| hold mediano real | 132 s | no calculado a nivel global (ver tabla por config; varias configs M15 no tienen ninguna posicion real en `deals_raw`) |
| SAME_BAR_EXIT_FALLBACK (audit) | 954 | **954** (exacto, ventana estricta 01:06:02-07:57:05, patron `[SAME_BAR_EXIT_FALLBACK] <config> ... gap$=`) |
| SENT OPEN retcode=10009 (audit) | 1,011 | **1,008** (ventana estricta) |

El audit log (SENT OPEN=1008, SAME_BAR_EXIT_FALLBACK=954) SI cubre la sesion completa y coincide (1008 vs 1011 dentro de tolerancia de 3; 954 vs 954 exacto). `deals_raw` NO cubre la sesion completa -- los numeros de "real_positions" / "real_pnl_usd" / "real_median_hold_s" en la tabla de abajo son PARCIALES (solo hasta 02:54:18 UTC) y no son comparables 1:1 con los 1,011 / -712,142 CLP / 132s dados como hechos de sesion completa. Se reportan tal cual, sin ajustar.

## Tabla completa, 20 configs

Columnas: sim CLASSIC (entries=eventos ENTRY_L/ENTRY_S; fichas=cierres F1+F2+F3 pareados; PnL$/oz=suma de (precio_salida-precio_entrada)*signo sobre las 3 fichas, todas las entradas del config); sim LIVE-FILL (mismo + conteo de eventos con `same_bar_fallback=True`); audit log (conteo de lineas `[SENT OPEN] <config> ... retcode=10009` y `[SAME_BAR_EXIT_FALLBACK] <config> ...` con su gap$ sumado); reales desde `deals_raw` (parcial, ver arriba).

| config | tf | classic entries | classic fichas | classic PnL $/oz | classic med hold s | live entries | live sbf | live PnL $/oz | live med hold s | audit SENT | audit sbf | audit sbf gap$ | real pos | real PnL USD | real med hold s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SS-M2 | M2 | 33 | 99 | 42.27 | 120 | 30 | 60 | 4.14 | 120.0 | 90 | 93 | -51.63 | 21 | -3.39 | 117 |
| V06D-M2 | M2 | 39 | 117 | 44.07 | 120 | 34 | 66 | 8.52 | 120.0 | 102 | 93 | -51.46 | 18 | -15.50 | 128.5 |
| V15-M2 | M2 | 30 | 90 | 31.59 | 120.0 | 27 | 51 | 14.16 | 120 | 84 | 84 | -40.32 | 15 | 1.63 | 132 |
| SS-M5 | M5 | 19 | 57 | 51.21 | 300 | 16 | 39 | -14.61 | 300.0 | 42 | 39 | -49.42 | 9 | -13.62 | 449.0 |
| V06D-M5 | M5 | 21 | 63 | 45.36 | 300 | 19 | 48 | -53.04 | 300 | 51 | 48 | -87.23 | 6 | -1.28 | 297 |
| V13-M5 | M5 | 22 | 66 | 46.98 | 300.0 | 20 | 48 | -61.92 | 300.0 | 54 | 48 | -86.34 | 6 | -1.63 | 296 |
| SS-M15 | M15 | 7 | 21 | 51.42 | 900 | 7 | 21 | -8.28 | 900 | 12 | 12 | -44.29 | 0 | 0.00 | None |
| V13-M15 | M15 | 7 | 21 | 49.98 | 900 | 7 | 21 | -8.28 | 900 | 12 | 12 | -44.72 | 0 | 0.00 | None |
| V06D-M15 | M15 | 6 | 18 | 38.28 | 900.0 | 6 | 18 | -14.01 | 900.0 | 15 | 15 | -49.02 | 0 | 0.00 | None |
| V06C-M5 | M5 | 21 | 63 | 45.09 | 300 | 19 | 48 | -53.04 | 300 | 51 | 48 | -90.12 | 6 | -1.28 | 297 |
| V06C-M15 | M15 | 6 | 18 | 37.74 | 900.0 | 6 | 18 | -14.01 | 900.0 | 15 | 15 | -47.78 | 0 | 0.00 | None |
| V06B-M15 | M15 | 6 | 18 | 36.84 | 900.0 | 6 | 18 | -14.01 | 900.0 | 15 | 15 | -47.00 | 0 | 0.00 | None |
| V15-M15 | M15 | 3 | 9 | 18.21 | 900 | 3 | 9 | 2.94 | 900 | 9 | 9 | -19.58 | 0 | 0.00 | None |
| V10-M5 | M5 | 13 | 39 | 26.58 | 300 | 11 | 27 | -28.71 | 300 | 27 | 27 | -52.61 | 3 | -1.23 | 297 |
| V10-M15 | M15 | 3 | 9 | 18.21 | 900 | 3 | 9 | 2.94 | 900 | 9 | 9 | -19.93 | 0 | 0.00 | None |
| V13-M2 | M2 | 39 | 117 | 36.87 | 120 | 34 | 66 | 8.52 | 120.0 | 102 | 93 | -56.98 | 18 | -15.72 | 126.5 |
| V09-CTRL-M5 | M5 | 21 | 63 | 42.39 | 300 | 19 | 45 | -55.74 | 300 | 51 | 48 | -88.94 | 6 | -0.52 | 296 |
| V09-CTRL-M15 | M15 | 6 | 18 | 32.34 | 900.0 | 6 | 18 | -14.01 | 900.0 | 15 | 15 | -43.95 | 0 | 0.00 | None |
| SS-M1 | M1 | 61 | 183 | -22.11 | 60 | 54 | 69 | 28.35 | 120.0 | 171 | 156 | -22.83 | 48 | -14.56 | 63 |
| V11-M2 | M2 | 30 | 90 | 30.75 | 120.0 | 27 | 48 | 17.40 | 120 | 81 | 75 | -38.70 | 18 | -17.01 | 127.0 |
| **TOTAL** | - | **393** | **1179** | **704.07** | - | **354** | **747** | **-252.69** | - | **1008** | **954** | **-1032.85** | **174** | **-84.11** | - |

Notas de la tabla:
- "classic med hold s" y "live med hold s" son la mediana de hold-time por ficha (exit `t` - entry `t`, pareado FIFO por ficha F1/F2/F3 dentro de la ventana de sesion). Ambas quedan cuantizadas exactamente al tamano de barra del TF (M1=60s, M2=120s, M5=300s, M15=900s) en la enorme mayoria de configs, salvo SS-M1 (classic med=60s, live med=120s).
- `real med hold s` = mediana de (`time` OUT - `time` IN) por `position_id`, solo con datos parciales de `deals_raw` (hasta 02:54:18 UTC). Configs M15 (SS-M15, V13-M15, V06D-M15, V06C-M15, V06B-M15, V15-M15, V10-M15, V09-CTRL-M15): **0 posiciones reales** registradas en la ventana parcial de `deals_raw` -- `real med hold s = None`.
- "classic PnL $/oz" y "live PnL $/oz" son la suma sobre TODAS las fichas cerradas en ventana (3 fichas por entrada), no por-oz-por-ficha promediada; unidad es precio del activo (USD/oz XAUUSD), no USD de cuenta.
- "audit sbf gap$" = suma de `gap$=` en las lineas `[SAME_BAR_EXIT_FALLBACK] <config> ...` (unidad: USD/oz, gap entre fill simulado y fill real reportado por el propio ejecutor live).

## Comparacion de tres vias (hechos, sin interpretacion)

Totales, sesion completa donde aplica (audit) vs parcial donde aplica (`deals_raw`):

| fuente | entries/aperturas | exits/fichas cerradas o sbf | PnL |
|---|---|---|---|
| sim CLASSIC (offline) | 393 | 1,179 fichas cerradas | +704.07 (USD/oz, suma cruda) |
| sim LIVE-FILL (offline) | 354 | 747 eventos con `same_bar_fallback=True` | -252.69 (USD/oz, suma cruda) |
| audit log (sesion completa, 01:06:02-07:57:05) | 1,008 SENT OPEN retcode=10009 | 954 SAME_BAR_EXIT_FALLBACK | gap$ sum = -1,032.85 |
| `deals_raw` (parcial, 01:06:02-02:54:18 solamente) | 174 posiciones (distinct position_id con IN) | 156 deals OUT | -78,517.72 CLP / -84.11 USD |
| Dado (hecho externo, sesion completa) | 1,011 posiciones | 954 SAME_BAR_EXIT_FALLBACK | -712,142 CLP / -762.9 USD |

Coincidencias exactas o cercanas:
- `audit SAME_BAR_EXIT_FALLBACK` (954, ventana estricta) == dado (954). Coincidencia exacta.
- `audit SENT OPEN` (1,008, ventana estricta) vs dado (1,011). Diferencia de 3 (0.3%).
- Por config, `sim LIVE-FILL same_bar_fallback` vs `audit same_bar_fallback` coincide exactamente en 6/20 configs: SS-M5 (39/39), V06D-M5 (48/48), V13-M5 (48/48 -- ver fila, ambos 48), V06C-M5 (48/48), V10-M5 (27/27), V10-M15 (9/9), V15-M15 (9/9). En las demas 13 configs no coincide (ver tabla; por ejemplo SS-M2: sim=60 vs audit=93; SS-M1: sim=69 vs audit=156).
- `sim CLASSIC fichas cerradas` no coincide exactamente con `audit SENT OPEN` en ninguna config (ejemplo SS-M2: 99 vs 90; SS-M1: 183 vs 171).

No-coincidencias:
- `deals_raw real_positions` total (174) vs dado (1,011): diferencia de 837 posiciones (82.8% menos), explicada factualmente por la cobertura parcial de `deals_raw` (termina a las 02:54:18 UTC, ~4h a mitad de sesion).
- `deals_raw real_pnl_usd` total (-84.11) vs dado (-762.9): diferencia de -678.79 USD, misma causa de cobertura parcial.
- 8 de 20 configs (todas las de tf=M15 excepto ninguna: SS-M15, V13-M15, V06D-M15, V06C-M15, V06B-M15, V15-M15, V10-M15, V09-CTRL-M15) tienen 0 posiciones reales en `deals_raw` en absoluto, pese a tener audit SENT OPEN > 0 (12, 12, 15, 15, 15, 9, 9, 15 respectivamente) y sim CLASSIC/LIVE-FILL entries > 0.
- El sim CLASSIC total de fichas cerradas (1,179) es mayor que el audit SENT OPEN total (1,008) y que el sim LIVE-FILL entries (354, menor que classic 393).

## Configs que no se pudieron correr

Ninguna. Las 20 configs corrieron sin excepcion en ambos modos (CLASSIC y LIVE-FILL); `errors` en el JSON esta vacio. Ninguna config tuvo warmup insuficiente (las 20 tuvieron las 10,000 barras completas de warmup antes del inicio de sesion disponibles en el parquet correspondiente).

## Nota metodologica sobre pareo de hold-time (correccion aplicada durante el analisis)

El pareo FIFO entrada-a-salida por ficha (F1/F2/F3), restringido a eventos cuyo bar open-time cae en la ventana `[01:06:02, 07:57:05]` UTC, produjo inicialmente un hold-time mediano negativo (-150s) en SS-M1: la primera salida en ventana pertenecia a una posicion abierta ANTES del inicio de la ventana (entrada fuera de ventana, evento de entrada por tanto excluido del filtrado), y el pareo FIFO ingenuo la emparejaba incorrectamente con la primera entrada SI visible en ventana. Se corrigio descartando las salidas "huerfanas" (cuyo timestamp es anterior a la primera entrada en-ventana de esa ficha) antes del pareo. El conteo de salidas huerfanas descartadas por config y por modo esta en el campo `orphan_leading_exits_dropped` del JSON (`hold_time_distributions.<config>.classic_orphan_leading_exits_dropped` / `livefill_orphan_leading_exits_dropped`). Tras la correccion, las 20 configs en ambos modos dieron hold-time medianas >= 0.

## Archivos generados

- `docs/superpowers/research/2026-07-14-diag-h1-churn.md` (este archivo)
- `scripts/report/diag_h1_churn.json` (tabla completa + histogramas de motivo de salida + deciles de hold-time por config y modo)
