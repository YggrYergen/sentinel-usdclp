# TK-BW — Opción B: régimen como ESTADO sostenido (plan de implementación)

> Fecha: 2026-07-21 · Autor: sesión brain unfiled-20260707 · Símbolo: XAUUSD
> Branch: alvaro · Ejecución: subagent-driven-development, ≤2 en paralelo SOLO si
> archivos/tareas disjuntos (aquí las tareas son SECUENCIALES: T2 depende de T1).
> Implementers: Opus 4.8 (según directiva de sesión). Investigación: Sonnet 5 high report-only.

## Contexto (por qué) — evidencia dura

El motor `tk_bw` (commit fe7e775) toma **0 posiciones** en M15/M5/M2 sobre el lake real
(ventana 2026-07-20..21). NO es datos (lake fresco) ni bug del runner. Un investigador
cuantificó (2504 pasos M1/TF, consistente en los 3 TF):

- El AND completo de las 9 condiciones de entrada = **0, nunca ocurre**.
- **Killer dominante = régimen-vs-pullback.** c5–c9 (EMA5/EMA8/AO/MOM/AC las 5 con
  pendiente positiva de 1 paso) vs c1 (precio < EMA8, el pullback): co-ocurrencia
  observada = **0.16x–0.32x** de la esperada si fueran independientes. Cuando el
  régimen acelerado (1 paso) está activo, el precio casi nunca está a la vez bajo EMA8.
- SAR(0.3,30) (c3) es fricción SECUNDARIA (0.58x–0.61x), no el killer.
- Causa: se mide la pendiente de la tendencia (última vs penúltima vela cerrada) EN EL
  MISMO instante que se exige el dip bajo EMA8. Pero un pullback ocurre 1–2 velas
  DESPUÉS del empuje alcista; para entonces la pendiente de 1 paso ya se aplanó/giró.
  La tendencia y el dip pelean en el tiempo.

**Decisión del trader/usuario:** leer el régimen como ESTADO sostenido (últimas K velas
cerradas), no como pendiente de 1 paso. Medir efectividad (B primero); si sirve, ver los
trades REALES graficados en "Trade View" (datos backtest lo más reales, spread 0.60).

## Decisión de diseño (D-B1) — cerrada

"creciente/decreciente" para c5–c9 (EMA8, EMA5, AO, MOM, AC) pasa de pendiente de 1 paso
(`cur > prev`) a **estado neto sobre K velas cerradas**:
  - creciente ⟺ `series[-1] > series[-1-K]`  (subida NETA en K velas)
  - decreciente ⟺ `series[-1] < series[-1-K]`
Nuevo parámetro `regime_lookback: int = 1`. **K=1 reproduce EXACTAMENTE el comportamiento
actual** (`series[-1] > series[-2]`), por lo que el cambio es ADITIVO y no altera parity
con el default. K>1 = lectura de estado.

**NO cambian** (siguen siendo nivel/gatillo instantáneo, verbatim del motor actual):
c1 `price<EMA8`, c2 vela-en-formación alcista/bajista, c3 `SAR<EMA8/>EMA8`, c4 ruptura del
high/low de la última vela opuesta; ni la lógica de SL/BE/trailing ni los TP F1/F2/F3.
Rationale: el estado-neto-sobre-K mantiene el régimen "arriba" DURANTE el dip, resolviendo
la pelea temporal medida (0.16x–0.32x).

## Global Constraints (para reviewers — copiar verbatim)

- Cambio **ADITIVO y retro-compatible**: `regime_lookback` default 1 ⇒ trades idénticos
  a hoy. Los tests existentes de `tk_bw` deben seguir verdes SIN modificarlos.
- Reutilizar los mismos índices/series ya calculados en `_Regime` (EMA/AO/AC/MOM); NO
  reimplementar indicadores; NO tocar `emasar_ref`/`_supertrend_ref`.
- Solo c5–c9 cambian a estado-sobre-K. c1,c2,c3,c4, SL/BE/trailing, F1/F2/F3: INTACTOS.
- Params exactos del backtest sin cambio: spread=0.60, commission=0, ema_fast=5,
  ema_slow=8, sar_step=0.3, sar_max=30.0, mom_period=14, st_period=14, st_mult=3.0,
  be_trigger=0.60, trail_usd=5.0, init_sl_offset=0.60, 3 fichas 0.01 lote, 1 posición máx.
- Determinismo: mismo lake + mismos params (incl. K) ⇒ mismo trade list.
- Registry: `engine="sentinel-sim"` (CHECK), `fidelity="research"`,
  `modelo_sim="tk_bw-v1-intrabar-m1"` (o sufijo `-kN` si se registra un K≠1),
  `familia="TK"`, `params_delta` EmasarPolicy-completo. `metrics_json` NOT NULL.
- Windows 10/11: pathlib, utf-8 explícito, sin APIs OS-version. El backtest NO abre órdenes.

---

## Task 1 — Motor: `regime_lookback` (estado-sobre-K) en `tk_bw.py`

**Archivos (exclusivos):** `sentinel_engine/strategies/tk_bw.py`,
`tests/strategies/test_tk_bw.py`.

**Qué construir:**
1. Extender `_Regime` para exponer, además de `*_cur`/`*_prev`, el valor "K velas atrás"
   de cada serie de régimen: EMA fast, EMA slow, AO, AC, MOM. Recibir `regime_lookback`
   en `_Regime.__init__` (o pasar las series y calcular el índice `n-1-K`). Mantener
   `__slots__`. El valor K-back es `serie[n-1-K]` si `0 <= n-1-K < len(serie)`, si no `None`.
2. En `tk_bw_run`, añadir param `regime_lookback: int = 1` a la firma (después de
   `st_mult`, antes de `be_trigger`, o donde sea limpio) y propagarlo a `_Regime`.
3. Reemplazar las 10 asignaciones de pendiente (ema_fast_rising/falling,
   ema_slow_rising/falling, ao_rising/falling, ac_rising/falling, mom_rising/falling)
   para comparar `*_cur` contra `*_back` (K velas atrás) en vez de `*_prev`. Con K=1,
   `*_back == *_prev`, así que el resultado es idéntico.
4. c1,c2,c3,c4 y todo el bloque de TP/SL/BE/trailing quedan **sin tocar**.

**Tests (mecánicos, alto valor):**
- **Parity K=1:** con un fixture (puede ser el de smoke/entrada ya existente), `tk_bw_run(steps)`
  (default) y `tk_bw_run(steps, regime_lookback=1)` producen la MISMA lista de trades.
- **Estado desbloquea:** construir una serie de ~40 velas cerradas donde en el paso de
  evaluación la pendiente de 1 paso de al menos una de c5–c9 sea negativa/plana (dip
  reciente) PERO el neto sobre K=3 sea positivo, y las demás condiciones (c1–c4, c3 SAR,
  vela en formación) estén dadas ⇒ con `regime_lookback=1` NO entra, con `regime_lookback=3`
  SÍ abre 3 fichas LONG. (Verificar numéricamente el fixture, máx 2–3 intentos; si cuesta,
  basta un test unitario directo del predicado de régimen rising-sobre-K sin forzar la
  entrada completa.) NO perseguir un fixture natural caro — directiva del trader "minimizar tests".
- **Default intacto:** los tests existentes de `test_tk_bw.py` siguen verdes sin editarlos.

**Report contract:** escribir informe en el path del dispatch; status (DONE/…); commits;
resumen 1 línea de tests (N/N, comando exacto); concerns.

---

## Task 2 — Runner: `--regime-lookback` + barrido de medición (depende de T1)

**Archivos (exclusivos):** `scripts/research/run_tk_bw_backtest.py`,
`tests/scripts/test_run_tk_bw_backtest.py`.

**Qué construir:**
1. Añadir CLI `--regime-lookback K` (default 1) que se pasa a `tk_bw_run(...)` en
   `run_one_tf` (propagar por la firma; no romper la firma existente).
2. Añadir modo de MEDICIÓN dry-run `--sweep-regime "1,2,3,4,5"` (lista de K): para cada TF
   y cada K corre el backtest en memoria (sin escribir) e imprime una fila por (TF,K):
   `trades`, `signals`, `net`, `pf`, `wr`, `maxdd`. Así el controlador ve de un vistazo si
   B desbloquea entradas y con qué K. Sin `--sweep-regime`, comportamiento actual intacto.
3. `--write` sigue registrando; cuando `--regime-lookback K≠1`, el `run_id`/`variant_id`
   y `modelo_sim` deben llevar sufijo `-kN` para no colisionar con los runs K=1, y
   `metrics_json` debe incluir `regime_lookback=K`.

**Tests (integración, fixture mínimo / tmp_path):** que `--regime-lookback` se propague
(el trade list cambia vs default en un fixture donde K importa, o al menos que el param
llegue a `tk_bw_run`); que `--sweep-regime` corra y no escriba; que `--write` con K≠1 use
run_ids con sufijo y registre `regime_lookback` en metrics_json; determinismo dado el fixture.

**Report contract:** igual que Task 1.

---

## Post-tareas (las hace el CONTROLADOR, no subagente)

1. Correr `python -m scripts.research.run_tk_bw_backtest --sweep-regime "1,2,3,4,5"` sobre
   el lake real → tabla (TF,K) con trades/net/pf/wr. **Punto de decisión: ¿B desbloquea
   entradas con señal razonable?** Reportar al usuario los números.
2. Si B es efectiva: elegir K (con el usuario si hay ambigüedad), correr `--write
   --regime-lookback K` para registrar los 3 runs, levantar el service y **CDP-verificar
   Trade View**: velas + entradas/salidas por ficha centradas + equity + overlays
   EMA5/EMA8/SAR(0.3,30)/ST/AO/AC/MOM. Avisar al usuario con números + capturas.
3. Luego **Opción A** (report-only, Sonnet 5 high): sensibilidad leave-one-out por
   condición + swap SAR(0.02,0.2), para caracterizar cuánto aporta cada palanca.
