# Reporte de desempeño — S6-K2P0, S7-TPNONE, SuperTrend-p14x3-M15

> Generado 2026-07-27 (hora servidor/local, UTC-4). Cuenta **DEMO 2883016567** (Capitaria-All, CLP).
> Solo lectura: sin órdenes, sin cierres, sin cambios de código, sin commits.
> Fuente LIVE: `mt5.history_deals_get` (conexión única read-only), rango 2026-07-20 → 2026-07-28,
> filtrado con `calendar.timegm` (NO `.timestamp()` — bug de timezone conocido).

## 0. Contexto

El roster `tomachine` se armó el **2026-07-22 ~12:10** y lleva ~5 días armado. Sin embargo, la
actividad real se concentra en **2026-07-22 18:00 → 2026-07-24 03:16**. Desde el 24-jul no hay
deals nuevos: el spread de XAUUSD en Capitaria está fijo en **0.60** y el cap de apertura es
**0.50**, por lo que todas las señales se difieren (`SPREAD_GATE_SKIP`). Esto es comportamiento
correcto y esperado, no una falla.

- Balance actual: **28.998.762 CLP**, equity idéntico → **0 posiciones abiertas**.
- Entradas por día: 22-jul = 55, 23-jul = 17, 24-jul = 1, 25/26/27-jul = 0.

## 1. Resultados LIVE por estrategia

| Estrategia | Magic | Entradas | Cerradas | Wins | PF | **Neto (CLP)** |
|---|---|---:|---:|---:|---:|---:|
| **S6-K2P0** | 724010 | 39 | 39 | 3 | **1.15** | **+14.889** |
| **S7-TPNONE** | 724020 | 28 | 27 | 5 | **1.13** | **+10.088** |
| **SuperTrend-p14x3-M15** | 724070 | 1 | 1 | 1 | ∞ | **+71.707** |
| *(TK-BW2-fix2atr)* | 725010 | 5 | 5 | 1 | 0.11 | −15.158 |
| **TOTAL roster** | | **73** | **72** | **10** | | **+81.526** |

Las 3 estrategias bajo evaluación están **en verde**. El win-rate es bajo (~8–19%) con pocos
ganadores grandes que cubren muchas pérdidas chicas — perfil típico de trend-following.

Duración media de trades: S6 49 min · S7 47 min · ST 1.996 min (33 h, un solo trade).

## 2. Desglose por ficha (clave para pasar a 1 ficha)

| Estrategia | F1 | F2 | F3 |
|---|---:|---:|---:|
| S6-K2P0 | +4.976 | +4.966 | +4.948 |
| S7-TPNONE | +6.174 | +5.780 | **−1.866** |
| SuperTrend | +71.707 | — | — |

- **S6**: las 3 fichas son prácticamente idénticas (entran al mismo precio y salen casi igual).
  Reducir a 1 ficha no cambia la forma del resultado, solo la escala. **Candidata más limpia.**
- **S7**: **F3 diverge y es negativa.** En el primer trade, F1/F2 cerraron +5.744 c/u mientras F3
  cerró −2.267 en el mismo instante. Si se queda 1 sola ficha, sería F1 (la mejor).
- **ST**: ya opera con ficha única (F1). Sin cambio estructural necesario.

## 3. Análisis horario y la ventana 18:00–18:45

### PnL por hora de entrada (todas las estrategias, hora servidor = local)

| Hora | Trades | Wins | PnL (CLP) |
|---|---:|---:|---:|
| 00:00–00:59 | 10 | 1 | −13.413 |
| 02:00–02:59 | 6 | 6 | +150.625 |
| **18:00–18:59** | **7** | **3** | **+82.077** |
| 20:00–20:59 | 7 | 0 | −52.691 |
| 21:00–21:59 | 21 | 0 | −38.696 |
| 22:00–22:59 | 9 | 0 | −8.934 |
| 23:00–23:59 | 12 | 0 | −37.441 |

### Ventana 18:00–18:44 vs resto

| Ventana | Trades | Wins | PnL (CLP) |
|---|---:|---:|---:|
| **18:00–18:44** | 7 | 3 | **+82.077** |
| Resto del día | 65 | 7 | **−550** |

| Estrategia | 18:00–18:44 | Resto |
|---|---:|---:|
| S6-K2P0 | n=3 · +1.149 | n=36 · +13.740 |
| S7-TPNONE | n=3 · +9.221 | n=24 · +867 |
| SuperTrend | n=1 · **+71.707** | n=0 · 0 |

### ⚠️ Lectura honesta

Los datos LIVE **NO respaldan** la hipótesis de que la ventana 18:00–18:45 sea de alto riesgo —
al contrario, fue la más rentable de la muestra. **PERO**:

1. Son **7 deals = 1 sola señal por estrategia × 3 fichas**, todas del mismo día (22-jul).
   Estadísticamente **no significativo**.
2. El +82.077 está dominado por **un único trade de SuperTrend (+71.707)** que estuvo abierto 33 h
   — su resultado refleja 33 horas de tendencia, no la calidad del momento de entrada.
3. Sin ese trade, la ventana rinde +10.370 en 6 deals — positivo pero marginal.

El argumento del owner (gaps de apertura que contaminan los indicadores en las primeras tres velas
M15) es **estructural/de dominio** y sigue siendo válido con independencia de esta muestra mínima.
Bloquear la ventana es una decisión de gestión de riesgo defendible; simplemente **no puede
justificarse ni refutarse con los datos live actuales**.

## 4. Contexto de research (calidad media — leer salvedades)

| Estrategia | Rank | Sharpe | Pooled | DSR |
|---|---|---|---|---|
| S6-K2P0 | 1/225 | +2.72 | +49.111 USD | **0 / p=1** |
| S7-TPNONE | 2/225 | +2.19 | +32.684 USD | **0 / p=1** |
| SuperTrend-p14x3-M15 | familia propia | +0.039 | +4.624 USD (201 trades) | no deflactable |

**Salvedad crítica**: DSR = 0 / p = 1 en S6 y S7 → resultados in-sample, bajo la barra de suerte,
**no son edge probado**. El "+$17.512" que circula para la familia SuperTrend está marcado por el
propio research como *evidence gap* (ledger legacy, no reproducible) y no debe citarse.

## 5. Comparativa y recomendación

| Métrica | S6-K2P0 | S7-TPNONE | SuperTrend |
|---|---|---|---|
| Neto LIVE | +14.889 | +10.088 | +71.707 |
| PF LIVE | 1.15 | 1.13 | ∞ (n=1) |
| Ficha problemática | ninguna | **F3 negativa** | n/a |
| Rank research | 1/225 | 2/225 | familia propia |
| Sharpe research | +2.72 | +2.19 | +0.039 |
| Diversificación | SAR M15 | SAR M15 (casi clon de S6) | lógica independiente |

**Recomendación: conservar S6 + ST.**

- **S6-K2P0** — mejor respaldo de research (rank 1), fichas homogéneas, el candidato más limpio
  para operar con ficha única.
- **SuperTrend** — aporta **diversificación real** (motor distinto, always-in, no es un clon de S6).
  Su Sharpe de research es pobre y su evidencia LIVE es de 1 trade: conservarla por diversificación,
  no por su desempeño demostrado.
- **S7-TPNONE** — descartable sin gran pérdida: es casi un clon de S6 (misma base SAR M15), tiene la
  única ficha negativa del roster, y en la ventana anterior (21-jul) había rendido **−38.618 CLP**
  con PF 0.38. El cambio de signo entre ventanas consecutivas confirma alta varianza.

## 6. Fuentes y calidad de datos

| Dato | Fuente | Confiabilidad |
|---|---|---|
| Trades, PnL, fichas, horarios | `mt5.history_deals_get` (pull único read-only) | **Alta** (muestra pequeña) |
| Configs y magics | `sentinel_engine/strategies/live_configs_20.py` | **Alta** (con asserts) |
| Rank/Sharpe/pooled | `docs/superpowers/research/2026-07-20-wave6-*`, `2026-07-20-wave5-p34-supertrend.md` | Media-alta, **DSR 0/p=1** |
| Ventana anterior S7 | `docs/superpowers/research/2026-07-21-live-strategies-performance-since-monday.md` | Alta |
| `data/research.db` (`trade`/`run`) | vacía | No aportó |
| Hipótesis 18:00–18:45 | 1 señal/estrategia | **Insuficiente** |

**Limitación general**: toda la evidencia LIVE proviene de ~2 días efectivos de operación
(22–24 jul). Revisar nuevamente tras 1–2 semanas de actividad real.
