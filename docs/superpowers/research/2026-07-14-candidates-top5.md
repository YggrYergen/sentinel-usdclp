# Ranking mecánico de los 20 configs EMASAR en vivo — evidencia para elegir 3

**Fecha:** 2026-07-14 · **Rol:** tabla de evidencia, sin recomendación (decide el usuario)
**Regla de ranking (mecánica, sin desviación):** `rank_score = livefill_sim_night_usd + real_usd_night + real_usd_today`, orden descendente (menos negativo = mejor). Donde `livefill_sim_night_usd` fuera null se trataría como 0 y se marcaría — **no ocurrió: los 20 configs tienen valor de simulación live-fill**.

## Fuentes y ventanas

| Fuente | Contenido |
|---|---|
| `data/research.db` → `deals_raw` (solo lectura) | Deals reales; CLP→USD ÷ 933.5. Noche = epoch [1783991162, 1784015825] (01:06:02–07:57:05 hora servidor, 6.85 h). Hoy = epoch > 1784020000 (post-reinicio). |
| `scripts/report/diag_h1_churn.json` | Sim offline sobre las barras exactas de anoche: entradas/PnL clásico y live-fill, conteos de audit SENT OPEN / SAME_BAR. |
| `scripts/report/livefill_bound_raw.json` | Estudio D90 (2026-07-13): nets clásico vs live-fill sobre ventanas de escala mensual (IW/W1/W2/W3). Solo 13 de los 20 ids aparecen. |
| `scripts/report/diag_h3h5_entry_slip.json` | Slip de entrada por config (total USD, noche). |

**Suficiencia de datos:** flag `LOW` si `n_pos_night + n_pos_today < 10`, si no `OK`.

## Cross-checks (obligatorios)

- Total `n_pos_night` computado: **1,011** — esperado ~1,011 → **coincide exacto**.
- Total `real_usd_night` computado: **−762.87 USD** — esperado ≈ −762.9 → **coincide**.
- Filtros usados: posiciones = `COUNT(DISTINCT position_id)` de deals `entry_type='IN'` con magic ∈ {base+1, base+2, base+3}; PnL = `SUM(profit)` de deals `entry_type='OUT'` mismos magics/ventana, ÷ 933.5.
- Nota: `diag_h1_churn.json` advertía que `deals_raw` cubría solo ~1h48m; a la fecha de este informe la DB está backfilled y cubre la sesión completa más la mañana de hoy (máx epoch 1784023750). Por eso las cifras `real_*` de este informe (calculadas directo de la DB) superan a las `real_*` parciales de ese JSON.

## Tabla completa (20 filas, orden por rank_score desc)

| # | Config | TF | rank_score | n_pos noche | USD noche | n_pos hoy | USD hoy | USD/pos noche | churn (pos/h) | %same-bar | sim LF noche USD | LF entradas | D90 ventanas + / presentes | slip entrada USD | Suficiencia |
|---|--------|----|-----------:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|:---:|
| 1 | V10-M15 | M15 | **−5.35** | 9 | −8.29 | 0 | 0.00 | −0.92 | 1.31 | 100% | +2.94 | 3 | — (ausente) | −6.57 | **LOW** |
| 2 | V15-M15 | M15 | **−6.92** | 9 | −9.86 | 0 | 0.00 | −1.10 | 1.31 | 100% | +2.94 | 3 | — (ausente) | −8.29 | **LOW** |
| 3 | SS-M15 | M15 | **−20.33** | 12 | −12.05 | 0 | 0.00 | −1.00 | 1.75 | 100% | −8.28 | 7 | 2 / 4 | −2.72 | OK |
| 4 | V13-M15 | M15 | **−20.92** | 12 | −12.64 | 0 | 0.00 | −1.05 | 1.75 | 100% | −8.28 | 7 | 2 / 4 | −3.13 | OK |
| 5 | V15-M2 | M2 | **−36.49** | 84 | −27.14 | 15 | −23.52 | −0.32 | 12.26 | 100% | +14.16 | 27 | 0 / 3 | −22.77 | OK |
| 6 | SS-M5 | M5 | −37.23 | 42 | −16.01 | 6 | −6.61 | −0.38 | 6.13 | 92.9% | −14.61 | 16 | 0 / 4 | −5.93 | OK |
| 7 | V06D-M15 | M15 | −37.92 | 15 | −23.91 | 0 | 0.00 | −1.59 | 2.19 | 100% | −14.01 | 6 | 2 / 4 | −7.56 | OK |
| 8 | V09-CTRL-M15 | M15 | −38.00 | 15 | −23.99 | 0 | 0.00 | −1.60 | 2.19 | 100% | −14.01 | 6 | — (ausente) | −7.42 | OK |
| 9 | V06C-M15 | M15 | −38.87 | 15 | −24.86 | 0 | 0.00 | −1.66 | 2.19 | 100% | −14.01 | 6 | 2 / 4 | −9.29 | OK |
| 10 | V06B-M15 | M15 | −39.03 | 15 | −25.02 | 0 | 0.00 | −1.67 | 2.19 | 100% | −14.01 | 6 | 2 / 4 | −9.12 | OK |
| 11 | SS-M2 | M2 | −54.37 | 93 | −31.88 | 15 | −26.63 | −0.34 | 13.58 | 103.3%* | +4.14 | 30 | 0 / 3 | −27.45 | OK |
| 12 | V11-M2 | M2 | −58.38 | 81 | −44.45 | 15 | −31.33 | −0.55 | 11.83 | 92.6% | +17.40 | 27 | — (ausente) | −22.47 | OK |
| 13 | V10-M5 | M5 | −69.73 | 27 | −31.32 | 6 | −9.71 | −1.16 | 3.94 | 100% | −28.71 | 11 | — (ausente) | −6.46 | OK |
| 14 | V06D-M2 | M2 | −72.01 | 102 | −54.07 | 15 | −26.46 | −0.53 | 14.89 | 91.2% | +8.52 | 34 | 0 / 3 | −28.67 | OK |
| 15 | V13-M2 | M2 | −88.26 | 102 | −65.50 | 15 | −31.28 | −0.64 | 14.89 | 91.2% | +8.52 | 34 | — (ausente) | −29.98 | OK |
| 16 | V06D-M5 | M5 | −122.70 | 51 | −62.83 | 6 | −6.82 | −1.23 | 7.45 | 94.1% | −53.04 | 19 | 0 / 4 | −4.66 | OK |
| 17 | V06C-M5 | M5 | −127.30 | 51 | −65.76 | 6 | −8.51 | −1.29 | 7.45 | 94.1% | −53.04 | 19 | 0 / 4 | −4.38 | OK |
| 18 | V09-CTRL-M5 | M5 | −129.41 | 51 | −60.87 | 6 | −12.80 | −1.19 | 7.45 | 94.1% | −55.74 | 19 | — (ausente) | +0.64 | OK |
| 19 | V13-M5 | M5 | −141.00 | 54 | −71.74 | 6 | −7.34 | −1.33 | 7.88 | 88.9% | −61.92 | 20 | 0 / 4 | −4.42 | OK |
| 20 | SS-M1 | M1 | −145.50 | 171 | −90.71 | 45 | −83.14 | −0.53 | 24.96 | 91.2% | +28.35 | 54 | 0 / 3 | −45.09 | OK |

\* SS-M2: el audit registra 93 SAME_BAR contra 90 SENT OPEN en la ventana (ratio > 1 tal cual sale de los conteos del JSON fuente; se reporta sin ajustar).

Columna "D90 ventanas + / presentes": ventanas mensuales live-fill con net > 0 sobre las presentes en `livefill_bound_raw.json`. "— (ausente)": el id no está en el roster D90 (solo 13 de 20 ids presentes).

Los detalles completos por ventana D90 (nets IW/W1/W2/W3 en USD/oz de sim) están en `scripts/report/candidates_top5.json`.

## TOP-5 por rank_score (perfil factual, sin recomendación)

**1. V10-M15 (720150) — rank_score −5.35 — flag LOW.**
Noche: 9 posiciones, −8.29 USD (−0.92 USD/pos); hoy: 0. Churn 1.31 pos/h, el más bajo de los 20. Sim live-fill de anoche: +2.94 USD con 3 entradas. Ausente del estudio D90 (sin evidencia de escala mensual). Su rank_score descansa en 9 posiciones reales y 3 entradas simuladas: muestra mínima.

**2. V15-M15 (720130) — rank_score −6.92 — flag LOW.**
Noche: 9 posiciones, −9.86 USD (−1.10 USD/pos); hoy: 0. Churn 1.31 pos/h. Sim live-fill de anoche: +2.94 USD (3 entradas, verdicto MATCH en paridad). Ausente del D90. Misma limitación que V10-M15: 9 posiciones totales, bajo el umbral de 10.

**3. SS-M15 (720070) — rank_score −20.33 — flag OK.**
Noche: 12 posiciones, −12.05 USD (−1.00 USD/pos); hoy: 0. Churn 1.75 pos/h; 100% same-bar. Sim live-fill de anoche: −8.28 USD (7 entradas). D90: 2 de 4 ventanas live-fill netas positivas (IW −1,124.4; W1 −8,137.2; W2 +9,265.8; W3 +1,614.6).

**4. V13-M15 (720080) — rank_score −20.92 — flag OK.**
Noche: 12 posiciones, −12.64 USD (−1.05 USD/pos); hoy: 0. Churn 1.75 pos/h; 100% same-bar. Sim live-fill de anoche: −8.28 USD (7 entradas). D90: 2 de 4 ventanas positivas (IW −1,124.4; W1 −8,094.0; W2 +9,281.7; W3 +1,989.3). Números casi idénticos a SS-M15.

**5. V15-M2 (720030) — rank_score −36.49 — flag OK.**
Noche: 84 posiciones, −27.14 USD (−0.32 USD/pos, la mejor pérdida por posición entre los M2); hoy: 15 posiciones, −23.52 USD. Churn 12.26 pos/h. Sim live-fill de anoche: +14.16 USD (27 entradas). D90: 0 de 3 ventanas positivas (IW −26,674.5; W1 −33,887.7; W2 −21,234.9; W3 sin datos). Único config del top-5 con muestra en vivo de dos dígitos altos (99 posiciones).

## Datos insuficientes (flag LOW y ausencias)

| Config | Qué falta exactamente |
|---|---|
| **V10-M15** (LOW) | Solo 9 posiciones reales (9 noche + 0 hoy, < 10). Ausente del roster D90 → cero evidencia live-fill de escala mensual. Solo 3 entradas en la sim de anoche. |
| **V15-M15** (LOW) | Solo 9 posiciones reales (9 + 0, < 10). Ausente del roster D90. Solo 3 entradas en la sim de anoche. |

Además, aunque con flag OK por conteo, **ningún config M15 operó hoy** (0 posiciones post-reinicio) y todos los M15 tienen ≤ 15 posiciones de noche: la evidencia real de todo el bloque M15 es delgada — se declara, no se oculta.

Configs ausentes del D90 (sin nets mensuales live-fill, campos null en el JSON): **V10-M15, V15-M15, V09-CTRL-M15, V11-M2, V10-M5, V13-M2, V09-CTRL-M5** (7 de 20).

## Caveats (hechos, no opiniones)

- **La muestra en vivo es una sola sesión de 6.9 h más una mañana parcial.** Todo `real_usd_*` y `usd_per_pos` proviene de ese único tramo; no hay más historia en vivo de estos magics.
- **Las ventanas D90 son la única evidencia live-fill a escala mensual.** Para los 7 configs ausentes del roster D90 no existe ninguna evidencia mensual live-fill.
- **Las diferencias de ranking nocturno entre hermanos M2/M5 están dentro del ruido de spread.** P. ej. V06D-M5 / V06C-M5 / V09-CTRL-M5 / V13-M5 difieren en pocos USD sobre ~51-54 posiciones con slip medio de ~±0.1-0.3 USD por entrada; el orden entre ellos no es distinguible del azar de ejecución.
- **El rank_score mezcla escalas** (USD reales de cuenta + USD/oz de sim tal como vienen de las fuentes); es la regla mecánica especificada, aplicada sin desviación.
- Los 20 rank_scores son negativos: en la evidencia disponible ningún config fue neto positivo bajo la métrica combinada.

## Archivos

- Tabla completa (todos los campos, incl. nets D90 por ventana): `scripts/report/candidates_top5.json`
- Fuentes: `data/research.db` (ro), `scripts/report/diag_h1_churn.json`, `scripts/report/livefill_bound_raw.json`, `scripts/report/diag_h3h5_entry_slip.json`, `sentinel_engine/strategies/live_configs_20.py`
