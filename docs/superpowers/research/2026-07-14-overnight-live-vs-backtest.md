# Overnight live vs backtest — sesión ARMADA EMASAR 20 configs (2026-07-14)

**Autor:** análisis de solo lectura · **Fecha:** 2026-07-14 ~12:00 UTC
**Cuenta:** MT5 DEMO 2883015767 (moneda **CLP**, equity ≈ 62.674.710 CLP)
**Ventana:** 2026-07-14 01:06:02 → 07:57:05 UTC (primera noche armada, `dry_run=False` desde 01:03:20)
**Símbolo/lote:** XAUUSD, 0,01 lot = 1 oz por ficha, 3 fichas/config, contract_size=100
**Tipo de cambio usado:** 933,5 CLP/USD (derivado de `profit_CLP / (Δpx·100·vol)` por posición; mediana 933,50, media 933,15 — muy estable)

---

## 1. Resumen ejecutivo

La primera sesión armada operó de forma **masiva y auto-destructiva**: el ejecutor abrió y cerró
**1.011 posiciones** (fichas) en menos de 7 horas, con una **duración mediana de 132 s** por posición.
El **94 % de las posiciones (954/1011) salió por `SAME_BAR_EXIT_FALLBACK`** — es decir, abrió y cerró
prácticamente en la misma barra a través de un trailing que el propio sim in-process subía usando el
high/AC de la barra recién cerrada. El resultado es un *churn* de round-trips que sangran spread + gap de
fill en cada ciclo.

- **PnL real total: −712.142 CLP ≈ −762,9 USD/oz.**
- El *cost by-design* acumulado del same-bar exit (registrado por el propio ejecutor) fue **−1.032,85 USD**,
  superior a la pérdida realizada — porque es una penalización modelada (sim-optimista vs live-fill), no la
  P&L contable; pero confirma que **el same-bar exit es el motor casi exclusivo del gap**.
- **La proyección offline del backtest NO es representativa de esta ventana:** el lake sólo tiene barras
  hasta **02:54 UTC** (ver §Apéndice/limitación crítica). Sólo **171 de 1.011 aperturas (17 %)** caen en
  la ventana con datos; las **840 aperturas restantes ($-692 de los $-763 de pérdida) ocurrieron entre
  02:54 y 07:57, un tramo que el lake nunca capturó**. Por eso el sim offline sólo reproduce 63 entradas
  (189 fichas) y proyecta +93 USD engañosos: está ciego a 5 de las 7 horas.
- La **fuente de verdad de la intención del sim es el audit log** (`run_live_20.audit.log`): registra
  1.011 `SENT OPEN` con retcode 10009 (= exactamente los 1.011 IN reales) y 954 eventos same-bar.
- Divergencias duras (checker oficial sobre la sub-ventana con barras): **13 MATCH / 7 DIVERGENCE**,
  32 hard-divergences, todas atribuibles a incidentes 10027/10016 (entradas perdidas/extra) — ver §4.

### Los 5 números más importantes
1. **PnL real: −712.142 CLP ≈ −762,9 USD.**
2. **Same-bar exit by-design cost: −1.032,85 USD** (954 eventos = 94 % de las posiciones).
3. **1.011 posiciones abiertas** (median hold 132 s; 761 de 1011 cerraron en ≤5 min).
4. **840/1011 aperturas (−692 USD) cayeron fuera del lake** (>02:54 UTC) → el backtest offline sólo
   cubre el 17 % de la sesión.
5. **Incidentes de rechazo: 21× retcode 10027 (Algo-OFF) + 12× 10016 en OPEN + trail-clamp 10016 en MODIFY** —
   coste directo estimado modesto (≈ −5…−15 USD, ver §4), muy inferior al same-bar.

---

## 2. Tabla por config

`real_USD` = suma de `profit` de deals OUT (CLP) / 933,5. `audit_open` = `SENT OPEN` retcode 10009
(fichas realmente abiertas, del audit log). `sb_events`/`sb_cost$` = eventos y coste `SAME_BAR_EXIT_FALLBACK`
del audit log (gap$ firmado, por diseño). `sim_off` = entradas que reproduce el sim offline sobre el lake
(≤02:54) — se muestra sólo para evidenciar la ceguera del lake.

| config        | tf  | real_CLP | real_USD | audit_open | sb_events | sb_cost$ | sim_off (fichas≈) |
|---------------|-----|---------:|---------:|-----------:|----------:|---------:|------------------:|
| SS-M1         | M1  |  −84.678 |   −90,7  |       171  |      156  |  −22,83  |  51 (17 ent)      |
| V13-M5        | M5  |  −66.966 |   −71,7  |        54  |       48  |  −86,34  |   6 (2)           |
| V06C-M5       | M5  |  −61.383 |   −65,8  |        51  |       48  |  −90,12  |   6 (2)           |
| V13-M2        | M2  |  −61.144 |   −65,5  |       102  |       93  |  −56,98  |  21 (7)           |
| V06D-M5       | M5  |  −58.655 |   −62,8  |        51  |       48  |  −87,23  |   6 (2)           |
| V09-CTRL-M5   | M5  |  −56.819 |   −60,9  |        51  |       48  |  −88,94  |   6 (2)           |
| V06D-M2       | M2  |  −50.475 |   −54,1  |       102  |       93  |  −51,46  |  21 (7)           |
| V11-M2        | M2  |  −41.490 |   −44,5  |        81  |       75  |  −38,70  |  21 (7)           |
| SS-M2         | M2  |  −29.757 |   −31,9  |        93  |       93  |  −51,63  |  21 (7)           |
| V10-M5        | M5  |  −29.234 |   −31,3  |        27  |       27  |  −52,61  |   3 (1)           |
| V15-M2        | M2  |  −25.331 |   −27,1  |        84  |       84  |  −40,32  |  15 (5)           |
| V06B-M15      | M15 |  −23.361 |   −25,0  |        15  |       15  |  −47,00  |   0               |
| V06C-M15      | M15 |  −23.203 |   −24,9  |        15  |       15  |  −47,78  |   0               |
| V09-CTRL-M15  | M15 |  −22.398 |   −24,0  |        15  |       15  |  −43,95  |   0               |
| V06D-M15      | M15 |  −22.316 |   −23,9  |        15  |       15  |  −49,02  |   0               |
| SS-M5         | M5  |  −14.942 |   −16,0  |        42  |       39  |  −49,42  |  12 (4)           |
| V13-M15       | M15 |  −11.795 |   −12,6  |        12  |       12  |  −44,72  |   0               |
| SS-M15        | M15 |  −11.245 |   −12,1  |        12  |       12  |  −44,29  |   0               |
| V15-M15       | M15 |   −9.208 |    −9,9  |         9  |        9  |  −19,58  |   0               |
| V10-M15       | M15 |   −7.743 |    −8,3  |         9  |        9  |  −19,93  |   0               |
| **TOTAL**     |     | **−712.142** | **−762,9** | **1.011** | **954** | **−1.032,85** | **189 (63 ent)** |

**Lectura de la tabla:**
- Los configs **M15** (`sim_off = 0`) son la prueba más limpia: el sim offline no abre ninguna entrada,
  pero live abrió 9–15 fichas cada uno y **todas** salieron same-bar. Esto sólo es posible si el sim
  in-process operó sobre barras que el lake no tiene → confirma la ceguera de datos + el mecanismo same-bar.
- Los **M5/M2** de alta frecuencia (V13/V06C/V06D-M5, V13/V06D-M2) concentran el mayor `sb_cost$`
  (−86…−90 USD cada M5), coherente con más ciclos de trailing por hora.
- **SS-M1** es el mayor perdedor absoluto (−90,7 USD) por volumen: 171 aperturas en M1.

---

## 3. Descomposición del gap (real − proyectado)

Dado que la proyección offline es no representativa (§Apéndice), la descomposición se hace contra el
**modelo del propio ejecutor** (audit log + checker oficial sobre la sub-ventana con barras).

| componente | fuente | magnitud | signo |
|---|---|---|---|
| **(b) Same-bar exit optimism** (dominante) | audit `gap$` × 954 eventos | **−1.032,85 USD** modelado | negativo |
| (a) Slippage de entrada (fill N+1) | checker `entry_slip_cost` (39 pares N+1, sub-ventana) | −13,91 USD sub-ventana; extrapolado ≈ −30…−50 USD full | negativo |
| (c) Trades perdidos/extra por incidentes | checker HARD (12 missed, 7 extra, 4 side, 7 px-oot) | ≈ −5…−15 USD (ver §4) | mixto |
| (d) Residuo (spread por round-trip, timing, encadenado) | real − Σ(a,b,c) | absorbido en el spread implícito de 954 round-trips | negativo |

**Nota metodológica sobre (b):** el checker offline sólo "ve" 79 eventos same-bar (−111,82 USD) porque
sólo reproduce las 189 fichas de la sub-ventana con datos. El audit log, que corrió con las barras reales
en memoria, registra los 954 eventos (−1.032,85 USD). **La cifra del audit log es la verdadera.**

**Residuo (d):** el churn de 1.011 posiciones a spread XAUUSD (~0,5 USD/oz por lado ≈ 1,0 USD round-trip
por oz) implica un peaje de spread del orden de **~1.011 USD** sólo en cruzar el bid/ask — que es el mismo
orden de magnitud que la pérdida realizada. Es decir: **la estrategia no pierde por dirección de mercado
sino por sobre-operar** (median hold 132 s), pagando spread+gap en cada micro-ciclo. El same-bar exit
es a la vez el síntoma (sale demasiado pronto) y el amplificador (paga el gap de fallback).

---

## 4. Incidentes de la noche y su coste

| incidente | ventana | tickets/afectados | efecto | coste estimado |
|---|---|---|---|---|
| **Algo-OFF (retcode 10027)** | 01:03–01:05 + reintentos | 21 OPEN rechazados (SS-M5 y otros al arranque) | entradas perdidas al inicio | bajo: las señales se re-evaluaron en ciclos siguientes; ≈ −0…−5 USD |
| **10016 en OPEN** (SL dentro de stops_level=50 pts) | ~02:46 + otros | 12 OPEN rechazados | entradas perdidas (MISSED_ENTRY en checker) | ≈ −3…−8 USD (algunas señales perdidas eran perdedoras → coste real puede ser positivo) |
| **10016 en MODIFY** (trail SL dentro de stops_level) | ~04:45 (55112106-08), ~05:17 (55112547-49), ~06:12 (55112843-45) | ≥ 33 MODIFY rechazados persistentes | trailing no se ajustó → SL se quedó más lejos → **puede haber protegido o perjudicado**; efecto neto pequeño | ≈ ±5 USD |

**Cuantificación del clamp ya commiteado (no activo):** el fix que hace *clamp* del SL al `stops_level`
elimina los 10016 (12 OPEN + 33 MODIFY). Su beneficio esta noche es **modesto (< 15 USD)** — no es el
problema. **El clamp NO ataca el same-bar exit**, que es el 99 % del gap.

Total incidentes ≈ **−10…−25 USD** (banda ancha). Confirmado por el checker: las 32 hard-divergences son
todas MISSED/EXTRA/SIDE/PRICE-OOT localizadas en los timestamps de 10027/10016, no divergencias sistémicas
de lógica.

---

## 5. Correcciones rankeadas por $/esfuerzo

| # | corrección | ataca | impacto estimado | esfuerzo |
|---|---|---|---|---|
| **1** | **Subir `ac_modulate_factor` y/o alejar el trailing (f*_trail_pips) en los configs 0,01/M1-M2-M5**, o retirar los que salen same-bar >90 % | (b) same-bar exit — **el 99 % del gap** | **hasta ≈ +1.000 USD/noche** si se elimina el churn; el mismo capital deja de pagar spread cada 132 s | bajo (parámetros; ya validado en tests) |
| **2** | **Prohibir salida same-bar** (exigir que el trail no use el high/AC de la barra en curso; salir sólo en barra ≥ N+1) | (b) mecanismo raíz | reduce sb_cost drásticamente sin cerrar señales buenas | medio (toca `emasar_variant` — fuera de misión) |
| **3** | **Reducir frecuencia: pasar los M1/M2 de alto churn a M5/M15** o subir `confirm_count` | sobre-operar (residuo d) | menos round-trips → menos peaje de spread | bajo |
| **4** | **Clamp de SL al `stops_level` (ya commiteado, activarlo)** | (c) 10016 OPEN+MODIFY | ≈ +10…+15 USD/noche | nulo (sólo desplegar el código ya escrito) |
| **5** | **Órdenes limit en la entrada** en vez de market | (a) slippage N+1 | ≈ +30…+50 USD/noche (irreducible salvo esto), a costa de fills perdidos | alto |
| **6** | **Arrancar con Algo-Trading ON**; verificar guard antes de armar | (c) 10027 | ≈ +0…+5 USD; evita ruido al inicio | nulo |

**Prioridad clara:** #1 y #2 (same-bar) dominan todo lo demás por dos órdenes de magnitud. El clamp (#4),
que era el foco de la noche, es correcto pero marginal para la P&L.

---

## 6. Apéndice metodológico

### Fuentes
- **Real (P&L ejecutado):** `mt5.history_deals_get(start,end)` filtrado a magics 720011–720203, agrupado
  por `position_id` (IN/OUT). Se usó la columna `profit` (CLP) tal cual; conversión a USD con 933,5 CLP/USD
  derivado internamente de `profit / (Δpx·contract·vol)`. commission=0, swap=0 en toda la ventana.
  Volcado a `scripts/report/mt5_deals_overnight.json` (1.011 IN + 1.011 OUT = 2.022 deals).
  *Corrección de un bug de zona horaria:* la primera consulta usó `datetime(...).timestamp()` (tz local
  CLT −4h) y devolvió una ventana corrida a 05:00–09:00; se re-consultó con `tzinfo=timezone.utc`.
- **Proyectado (backtest):** `simular_variant(**cfg.kwargs)` sobre barras del lake vía
  `load_bars_with_warmup(..., warmup=10000)` del checker; direction_mask vía
  `gen_variant_batch5.compute_direction_mask` para V10; P&L por oz sumando `(exit−entry)·signo` por ficha.
- **Intención del sim in-process:** `scripts/live/run_live_20.audit.log` (región armada desde línea 2921,
  `dry_run=False`). `SENT OPEN retcode=10009` = fichas abiertas; `SAME_BAR_EXIT_FALLBACK … gap$=` = coste
  same-bar por diseño; línea `SAME_BAR cumulative` final = −1.033,61 USD (coherente con mi suma −1.032,85).
- **Checker oficial:** `python -m scripts.live.check_live_sim_parity --config all
  --start 2026-07-14T01:06:00 --end 2026-07-14T08:00:00 --json scripts/report/parity_overnight.json`
  → 13 MATCH / 7 DIVERGENCE, 32 hard. Clases `SAME_BAR_OPTIMISM` (79, −111,82 USD),
  `ENTRY_NEXT_BAR` (39, slip −13,91 USD).

### Limitación crítica de datos (afecta a toda la sección "proyectado")
Tras ejecutar `python scripts/mt5_dump_history.py` (finalizó 07:55, reportó "..2026-07-14"), **el parquet
`data/lake/XAUUSD/{M1,M2,M5,M15}/2026-07.parquet` sigue terminando en 02:54 UTC** (M5 en 02:50, M15 en
02:45). MT5 sí tiene barras hasta 07:55 (`copy_rates_from_pos` lo confirma), pero **el escritor del lake no
persistió el tramo 02:54→07:55**. Consecuencia: el backtest offline sólo cubre 01:06–02:54 (171/1011
aperturas, −70,8 USD de los −762,9). **La proyección offline por config NO debe interpretarse como
"lo que el backtest esperaba en la sesión"** salvo para esa primera sub-ventana; la referencia válida para
el 83 % restante es el audit log del sim in-process. Recomendación operativa: investigar por qué el dump no
escribió las barras recientes (posible dedup por rango o append que no re-abre la partición del mes en
curso) antes de la próxima validación offline.

### Reconciliación
- `SENT OPEN` (10009) = **1.011** ≡ **1.011** deals IN reales de MT5. ✔
- Same-bar audit sum = **−1.032,85 USD** ≈ `SAME_BAR cumulative` del propio log (−1.033,61). ✔
- Tipo de cambio: `total_CLP / 933,5 = −762,9 USD` ≡ suma directa por posición (−762,87). ✔

Artefactos generados (JSON temporales bajo `scripts/report/`, permitido):
`mt5_deals_overnight.json`, `parity_overnight.json`, `overnight_analysis.json`.
