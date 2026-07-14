# DIAGNÓSTICO: qué hicieron las 20 estrategias EMASAR en vivo vs qué debían hacer en teoría

**Fecha:** 2026-07-14 · **Sesión analizada:** 2026-07-14 01:06:02 → 07:57:05 (hora servidor broker; ver §7 nota de reloj)
**Cuenta:** DEMO 2883015767 (CLP) · **Símbolo:** XAUUSD, 0,01 lot = 1 oz/ficha, 3 fichas/config
**PnL real de la sesión:** −712.142 CLP ≈ **−762,9 USD** (1.011 posiciones, 2.022 deals, comisión/swap = 0)
**Método:** 4 investigaciones de solo-lectura (H1 churn, H2 SL/TP, H3+H5 spread/slip, H4 lake) ejecutadas por subagentes independientes; síntesis y verificación del orquestador. Informes fuente en `docs/superpowers/research/2026-07-14-diag-*.md` y JSONs en `scripts/report/diag_*.json`.

---

## 1. Resumen ejecutivo

La sesión no perdió dinero porque el ejecutor hiciera algo distinto de lo que la estrategia le pedía. Perdió dinero porque **la estrategia, tal como está calibrada, es estructuralmente no ejecutable en vivo**, y eso ya estaba medido y escrito el día antes de armar (informe D90, `2026-07-13-livefill-bound.md`): el 100% de las salidas por trailing de este roster dependen de conocer el high/AC de la barra *en curso* — información que un stop server-side no puede tener. El backtest clásico "ganaba" comprando información del futuro dentro de cada barra; el vivo la paga.

La descomposición de la pérdida **cierra con residuo < 0,2%**:

| paso | USD | fuente |
|---|---:|---|
| Lo que el backtest clásico proyectaba (mismas barras, misma ventana, sin spread) | **+704,1** | sim offline H1 |
| − Optimismo same-bar (clásico → `live_fill_mode=True`, la semántica ejecutable) | **−956,8** | H1 (704,1 − (−252,7)) |
| = Cota teórica ejecutable (sin fricción de fills) | **−252,7** | sim offline H1 |
| − Fricción de fills medida (spread + tick siguiente, 1.008/1.011 posiciones) | **−509,0** | H3 |
| = Esperado con fills reales | **−761,7** | |
| **Real** | **−762,9** | deals MT5 |
| **Residuo no explicado** | **−1,2 (0,16%)** | |

Es decir: **dos tercios del daño es el diseño de la salida (look-ahead same-bar) y un tercio es el peaje de spread de sobre-operar** (1.011 round-trips en 7 horas, hold mediano 132 s). Los incidentes de ejecución (10027, 10016) y el estado desincronizado tras misses quedan dentro del ruido (±$10–25) — por eso H6 no se ejecutó como investigación separada: su contribución está acotada por el residuo.

**Respuestas binarias a las preguntas de la misión:**
- **H1 — ¿estrategia o ejecutor?: ESTRATEGIA.** El sim clásico offline sobre las mismas barras genera 393 entradas ≈ 1.179 fichas con holds cuantizados a 1–2 barras — el mismo churn que el vivo (1.008 fichas abiertas según audit; 1.011 según deals). El ejecutor reprodujo fielmente la intención del sim.
- **H2 — ¿SL/TP replican al sim?: SÍ, y el TP no existe en ninguno de los dos lados.** 0 de 2.022 órdenes llevó TP; ninguna de las 20 configs puede emitir EXIT_TP (ningún `f1_tp_r`/`f2_tp_r` > 0). El SL server-side se instaló en las 1.011 aperturas. No hay divergencia de semántica SL/TP que explique la pérdida.
- **H3 — spread:** el modelo flat 0,5 no estaba mal *por unidad* (round-trip medido: mediana +0,50 USD/oz, total $509 sobre 1.008 posiciones); lo letal es la **frecuencia** con trails de ~1 pip.
- **H4 — lake:** **no hay bug de escritura.** El dump escribe solo la capa monolítica (que SÍ tiene toda la noche); los tiers los escribe únicamente `build_tiers.py`, que nadie corrió después de las 02:57. El checker lee solo tiers → ceguera. Tiers ya regenerados durante este diagnóstico.

**Hallazgo operativo nuevo:** el daemon `run_deals_watcher` está **zombie** desde las 02:54:18 (proceso vivo PID 75512, tabla `deals_raw` congelada). Coincide temporalmente con la corrida de dump/tiers de las ~02:54–02:57. Requiere reinicio (decisión del usuario).

---

## 2. H1 — El churn es de la estrategia (evidencia)

Fuente: `2026-07-14-diag-h1-churn.md` / `diag_h1_churn.json`. Las 20 configs se re-simularon offline sobre los parquets monolíticos (que cubren toda la noche), con warmup de 10.000 barras (idéntico al `window` del ejecutor), en dos modos: CLÁSICO (el que corre dentro del ejecutor) y LIVE-FILL (la semántica server-side).

- **Clásico offline: 393 entradas = 1.179 fichas cerradas en ventana, PnL +704 USD/oz.** Vivo: 1.008 fichas abiertas (audit) / 1.011 (deals). El orden de magnitud y la cuantización de holds (mediana = exactamente 1 barra del TF en casi todas las configs) coinciden: **el churn es by-design**. La diferencia clásico-vs-audit (~15% menos aperturas en vivo) proviene de incidentes (33 aperturas perdidas por 10027/10016), del recómputo con ventana deslizante del ejecutor, y de tramos desincronizados — nada de eso cambia el veredicto.
- **Live-fill offline: 354 entradas, 747 same-bar fallbacks, PnL −252,7 USD/oz.** El audit registró 954 SAME_BAR_EXIT_FALLBACK con gap$ acumulado −1.032,85 (el gap$ del audit mide sim-fill vs live-fill, una vara distinta del PnL — ambas cuentan la misma patología).
- La coincidencia exacta de conteos same-bar sim-vs-audit en 7 configs (todas M5/M15: 39/39, 48/48, 27/27, 9/9…) y la divergencia en M1/M2 es consistente con la sensibilidad del recómputo por ventana deslizante en TFs rápidos; no altera los totales.
- 94% de las posiciones reales salió por fallback same-bar; 761/1.011 duraron ≤5 min.

**Por qué el backtest "ganaba" con el mismo churn:** llenaba cada salida AL NIVEL exacto del trail recién subido con el high de esa misma barra, sin spread. El D90 ya lo había cuantificado: al pasar a `live_fill_mode`, el net de TODAS las configs M1/M2/M5 se vuelve negativo en TODAS las ventanas históricas (mediana de caída ≈ −121%), y el eje `ac_modulate_factor` 0,01/0,10/0,25 deja de discriminar (nets idénticos en M15). La ventaja in-sample de f=0,01 *era* el look-ahead.

## 3. H2 — SL/TP: el ejecutor replica al sim; el broker casi no participó en las salidas

Fuente: `2026-07-14-diag-h2-sltp.md` / `diag_h2_sltp.json`.

- **TP:** no existe campo `tp` en ninguna request (OPEN: `action,symbol,volume,type,price,sl,deviation,magic,comment,type_filling`; MODIFY: `action=SLTP,symbol,position,sl,magic`), el reconciler no tiene acción de TP, y **ninguna config puede emitir EXIT_TP** (ningún `f?_tp_r`>0). Confirmado contra broker: **0/2.022 órdenes con tp≠0; 1.011/1.011 aperturas con sl≠0**. La sospecha "el live se pierde TPs del sim" queda **descartada**: el sim tampoco los tiene.
- **Razón de cierre (histograma de 1.011 OUT):** EXPERT (cierre a mercado del ejecutor) = **1.002 (99,1%)**; SL server-side = **9 (0,9%, todos SS-M1)**, ejecutados exactamente al nivel instalado (gap 0,00). El SL server-side funcionó cuando le tocó; simplemente casi nunca le tocó, porque el sim salía same-bar antes de que el precio tocara el stop resting.
- **MODIFY:** 297 intentos → 198 OK, 99 fallos (todos 10016, todos SS-M1, 18 tickets; 12 recuperaron MODIFY después, 6 se cerraron a mercado en ≤75 s). El clamp commiteado en c93fcd0 (aún no activo esta noche) elimina esta clase; su valor económico es ~±$5–15, marginal.
- **Asimetría long/short:** LONG 552 posiciones −$314; SHORT 459 −$448. El short paga el ask en la salida a mercado (mediana +0,71 USD/oz vs +0,19 del long-OUT) — consistente con OHLC bid-based; es parte de los $509 de fricción, no un bug.

## 4. H3 + H5 — La fricción de fills, medida

Fuente: `2026-07-14-diag-h3h5-spread-slip.md` / `diag_h3h5_*.json`, `diag_h5_parity_full.json`.

- **Round-trip medido** (vs proxy bid = close M1 del mismo minuto): mediana +0,495 USD/oz, p90 +2,33, **total $509,03**. El modelo flat "0,5 por lado" ($1.011) sobreestimaba; "0,5 por round-trip" ($505,50) clava el total. Peores horas (hora servidor): 07 (+$155) y 04 (+$121).
- **Slippage de entrada** (fill real vs close de la barra de señal, 1.011/1.011 SENT OPEN pareados 1:1 con deals): total **−$255,74** (media −0,25 USD/oz). Es una *vista parcial* de los mismos $509, no un costo adicional — no se suman.
- **Checker oficial full-night** (con tiers regenerados y deals reconstruidos de MT5): ENTRY_NEXT_BAR 259 pares (−$124 en su métrica), SAME_BAR_OPTIMISM 631 (−$1.147), 2 MATCH / 18 DIVERGENCE con 136 hard — las divergencias duras siguen trazando a incidentes y tramos desincronizados, no a lógica.
- Spread snapshot actual (no la noche): 0,60 USD/oz fijo (`spread_float=False`).

## 5. H4 — Lake: no hubo bug; faltaba correr build_tiers (+ watcher zombie)

Fuente: `2026-07-14-diag-h4-lake.md` / `diag_h4_lake.json`.

- `mt5_dump_history.py` → `ingest_mt5_csv` → `store.write_bars` escribe SOLO la capa monolítica (`data/lake/XAUUSD/<min>.parquet`), que quedó completa hasta las 07:45–07:53 con **cero pérdida de filas** (raw CSV ≡ monolito). `drop_forming_bar` solo puede descartar la última fila por construcción — inocente.
- Los tiers (`XAUUSD/M5/2026-07.parquet`…) los escribe **únicamente** `scripts/build_tiers.py`, cuya última corrida fue 02:57. El dump no invoca tiers en ningún punto. `check_live_sim_parity.load_bars` lee **exclusivamente** tiers → por eso todo lo offline "terminaba a las 02:54".
- **Acción ya tomada (pre-aprobada, sin cambio de código):** tiers regenerados durante el diagnóstico; ahora cubren hasta 07:53.
- **Pendiente de decisión:** (a) encadenar `build_tiers` al final del dump (cambio de código pequeño + test), y (b) reiniciar `run_deals_watcher` (zombie desde 02:54:18; el proceso no murió pero dejó de escribir — su causa exacta no se investigó; candidata natural: pérdida silenciosa de la conexión IPC MT5 sin reintento).

## 6. Correcciones propuestas, rankeadas por impacto $/esfuerzo (NINGUNA implementada)

El criterio de validación de TODAS las candidatas cambia a partir de hoy: **se mide contra `live_fill_mode=True` + spread realista, nunca contra el backtest clásico.** El D90 ya da la línea base: bajo esa vara, M15 es el único TF con celdas positivas históricas (W2/W3).

| # | corrección | ataca | impacto estimado (noche tipo) | esfuerzo | riesgo |
|---|---|---|---|---|---|
| 1 | **Pausar ya los TF rápidos** (M1/M2/M5 = 12 configs; el D90 no les encuentra NINGUNA celda positiva bajo live-fill) y dejar solo M15 | −$650 aprox. del daño nocturno (M1+M2+M5 concentran ~85% de la pérdida) | operativo/config; requiere cambio de código para retirar configs individuales (PAUSAR_TRADING.bat congela TODO) | bajo — es dejar de operar lo que pierde |
| 2 | **Recalibrar la salida contra live_fill**: trail más ancho (fN_trail_pips ≫ rango de barra), `ac_modulate_factor` alto o `ac_modulate=False`, y/o lógica "next-bar-only" (el trail nunca usa la barra en curso) | el 100% same-bar (−$957) | potencialmente convierte la cota −$253 en positiva; a validar offline primero | medio: barrido de parámetros offline + variantes shadow | medio — puede matar el edge de entrada si el trail ancho devuelve demasiado |
| 3 | **Programa de variantes shadow en demo** (lo pedido por el usuario): correr N versiones corregidas junto a las actuales, magics nuevos (721000+), para confirmar/negar hipótesis con dinero demo | valida #2 antes de comprometerse | n/a (instrumento de medición) | medio: lista `CONFIGS_SHADOW`, subir/gestionar `MAX_FICHAS_TOTAL` (hoy 60 = 20×3 justo), tests | bajo si se respeta el cap y el guard |
| 4 | **Activar el código ya commiteado** (clamp SL, c93fcd0) reiniciando el ejecutor con `INICIAR_TRADING_LIVE.bat` | 10016 OPEN/MODIFY (~±$10) | +$10–15/noche | nulo (ya escrito) | nulo |
| 5 | **Encadenar build_tiers al dump** + **watchdog/reintento en deals_watcher** | ceguera offline y DB congelada (no PnL) | evita diagnósticos ciegos futuros | bajo | nulo |
| 6 | Órdenes limit en la entrada | parte de los $509 de fricción | +$100–250/noche si mantiene fill-rate | alto | medio (fills perdidos) |

**Recomendación de pausa inmediata** (si se decide operar esta noche sin fixes): pausar TODO (PAUSAR_TRADING.bat) o, si se acepta el cambio de código mínimo para retirar configs, dejar solo las 8 M15 — que esta noche perdieron "solo" ~$140 de los $763 y son las únicas con soporte histórico bajo live-fill. **Mi lectura estricta de los datos: con la calibración actual, ninguna config tiene expectativa positiva en vivo; la opción conservadora es pausar todo hasta tener las variantes corregidas.**

## 7. Apéndice — reloj, unidades y validez

- **Reloj:** toda la cadena (barras MT5, deals, audit log) comparte la MISMA escala: hora del servidor del broker = UTC_PC − 4h (verificado con `symbol_info_tick.time`). Las horas citadas ("01:06–07:57") son hora-servidor; en UTC real la sesión fue 05:06–11:57. Internamente todo es coherente; solo afecta la interpretación de "qué hora del mundo era" (p. ej., los buckets horarios de spread).
- **Unidades:** sim PnL en USD/oz con fichas de 1 oz → USD equivalentes; deals en CLP convertidos a 933,5 (derivado y estable). El gap$ del audit (−1.033) mide sim-fill vs live-fill por evento; NO es sumable con la descomposición de §1 (doble contaría).
- **Advertencias:** (i) el sim offline no es bit-a-bit el sim in-process (ventana deslizante); los totales coinciden, el per-config M1/M2 no siempre. (ii) `deals_raw` solo cubre hasta 02:54 — todo lo full-night usó `history_deals_get` directo. (iii) la descomposición usa el proxy M1-close para la fricción; el cierre a $1 del real tiene componente de suerte, pero cada término está medido de forma independiente.

*Generado por la sesión de diagnóstico 2026-07-14. Investigadores: 4 subagentes Sonnet de solo-lectura. Nada del código de estrategia/ejecutor fue modificado; únicos cambios de estado: regeneración de tiers del lake (pre-aprobada) y archivos nuevos de reporte.*
