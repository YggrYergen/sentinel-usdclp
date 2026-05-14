# 🛡️ SENTINEL v3.6 — USD/CLP Scalping Intelligence Engine

> Sistema de análisis en tiempo real para scalping de USD/CLP.
> Conecta con MetaTrader 5 para datos en vivo, calcula scores técnicos multi-timeframe,
> correlaciones cross-asset, señales con derivadas de precio, backtesting y chat con IA.

---

## ⚡ Inicio Rápido

**Doble click en `SENTINEL.bat`** — eso es todo.

El launcher automáticamente:
1. ✅ Verifica si ya está corriendo (si sí, abre el navegador)
2. ✅ Busca actualizaciones en la rama `release`
3. ✅ Instala/actualiza dependencias si es necesario
4. ✅ Lanza el dashboard y abre el navegador

### Primera vez (requisitos)
- **Python 3.11+** — [descargar](https://python.org/downloads) ⚠️ Marcar "Add to PATH"
- **Git** — [descargar](https://git-scm.com/downloads)
- **MetaTrader 5** instalado con cuenta Capitaria activa

```bash
git clone https://github.com/YggrYergen/sentinel-usdclp.git
cd sentinel-usdclp
SENTINEL.bat
```

---

## 🏗️ Arquitectura del Sistema

```
SENTINEL.bat                  ← Un click para todo
sentinel/
├── dashboard.py              # UI principal (Streamlit) — renderiza todo
├── sentinel_core.py          # Cerebro: orquesta scoring compuesto
├── technical_scorer.py       # Score técnico multi-TF (EMA, RSI, MACD, BB, PA)
├── correlation_engine.py     # Correlaciones cross-asset (8 instrumentos)
├── levels_engine.py          # Niveles S/R (Camarilla + Swing Detection)
├── data_feed.py              # Fuente de datos (MT5 real-time + Yahoo fallback)
├── indicators.py             # Cálculo de indicadores técnicos (librería `ta`)
├── backtester.py             # Motor de backtesting + replay de scores
├── ai_chat.py                # Asistente IA (Claude Opus 4.7 / Sonnet 4.6)
├── config.py                 # Pesos, umbrales, símbolos MT5, parámetros
├── version.py                # Versión actual del sistema
├── check_state.py            # Diagnóstico programático
├── launcher.py               # Auto-updater, instalación portable
└── requirements.txt          # Dependencias Python
```

### Flujo de datos (macro → micro)

```
MT5 / Yahoo Finance
     │
     ▼
  DataFeed (data_feed.py)     ← Abstrae fuente, cache, normalización
     │
     ├──▶ SentinelCore        ← Orquesta el cálculo completo
     │       │
     │       ├── TechnicalScorer   → Score técnico 0-100 por TF
     │       ├── CorrelationEngine → Score correlación 0-100
     │       └── LevelsEngine      → Niveles S/R price-action
     │
     ▼
  Dashboard (dashboard.py)    ← Renderiza UI, señales v1/v2, derivadas
```

---

## 📊 Sistema de Scoring Compuesto

### Fórmula del Score Final (0-100)

```
Score = TechScore × 0.75 + CorrScore × 0.25
```

| Componente | Peso | Descripción |
|---|---|---|
| **Técnico** | 75% | EMA, RSI, MACD, Bollinger Bands, Price Action — multi-timeframe |
| **Correlación** | 25% | Consenso de 8 cross-assets ponderados por relevancia |

### Semáforo de Score

| Score | Señal | Acción |
|---|---|---|
| ≥ 75 | 🟢 **FUERTE** | Alta confluencia técnica + correlación → entrar con convicción |
| ≥ 65 | 🟡 **ALERTA** | Señales parciales → buscar confirmación antes de entrar |
| < 65 | 🔴 **ESPERAR** | Sin consenso → no operar, esperar setup |

### Dirección Consensuada

La dirección final (LONG/SHORT/NEUTRAL) se vota con pesos:
- **Técnico**: 2 votos
- **Correlación**: 3 votos

> El peso mayor de correlación en dirección (no en score) es intencional: evita trades contra-tendencia macro incluso si los indicadores técnicos lo sugieren.

---

## 📈 Score Técnico (75% del compuesto)

**Archivo**: `technical_scorer.py` + `indicators.py`

### Multi-Timeframe: Pesos por TF

Cada timeframe genera un score independiente (0-100). Se combinan así:

| TF | Peso | Rol | Barras M5 equivalentes |
|---|---|---|---|
| **M1** | 40% | Micro-momentum — ejecución inmediata | 0.2 velas |
| **M2** | 30% | Transición — confirma M1 o lo contradice | 0.4 velas |
| **M5** | 20% | Tendencia corta — dirección del movimiento | 1 vela |
| **M15** | 10% | Contexto — ancla dirección para el bias | 3 velas |

> **Normalización MACD**: En M1 y M2, el histograma MACD se normaliza por ATR (`h/ATR × 40 + 50`) para evitar saturación en instrumentos de precio alto como USDCLP (~940). M5/M15 usan la escala original.

### 5 Indicadores Técnicos

Cada indicador produce un **score** (0-100) y un **voto** (+1, 0, -1):

```
Score_TF = EMA×0.30 + RSI×0.20 + MACD×0.25 + BB×0.15 + PA×0.10
```

#### 1. EMA (30%) — Tendencia y Estructura

| Parámetros | Valores |
|---|---|
| EMA rápida | 9 períodos |
| EMA media | 21 períodos |
| EMA lenta | 50 períodos |
| EMA tendencia | 200 períodos |

| Patrón | Score | Voto | Interpretación |
|---|---|---|---|
| EMA 9 > 21 > 50 | 85 | +1 | Tendencia LONG establecida |
| EMA 9 < 21 < 50 | 15 | -1 | Tendencia SHORT establecida |
| Precio > 2 de 3 EMAs | 65 | +1 | Sesgo alcista |
| Precio < 2 de 3 EMAs | 35 | -1 | Sesgo bajista |
| Entrelazadas | 50 | 0 | Mercado lateral |

**Bonus cruce EMA 9/21**: +15 si cruce alcista, -15 si cruce bajista.

#### 2. RSI (20%) — Momentum

| Parámetros | Valores |
|---|---|
| Período | 14 |
| Sobrecompra | ≥ 70 |
| Sobreventa | ≤ 30 |

| Zona RSI | Score | Voto | Para el trader |
|---|---|---|---|
| ≥ 70 | 30 | -1 | **No entrar LONG** — agotamiento probable |
| 55-70 | 55-65 | +1 | Momentum comprador activo |
| 45-55 | 45-55 | ±0 | Zona neutral, esperar definición |
| 30-45 | 35-45 | -1 | Momentum vendedor activo |
| ≤ 30 | 70 | +1 | Sobreventa — buscar rebote LONG |

**Divergencias RSI entre TFs**: Si M1 RSI=75 (sobrecompra) pero M15 RSI=45 (neutral), se genera alerta `"RSI M1=75 vs M15=45 — probable retroceso"` con magnitud (leve/moderada/fuerte).

#### 3. MACD (25%) — Impulso

| Parámetros | Valores |
|---|---|
| Fast | 12 períodos |
| Slow | 26 períodos |
| Signal | 9 períodos |

**Para M1/M2** (normalizado por ATR):
```
score = 50 + (histogram / ATR) × 40    # Rango resultante: ~10-90
```

**Para M5/M15** (escala directa):
```
histogram > 0 → score = min(100, 60 + |h|×1000)
histogram < 0 → score = max(0,   40 - |h|×1000)
```

#### 4. Bollinger Bands (15%) — Volatilidad y Posición

| Parámetros | Valores |
|---|---|
| Período | 20 |
| Desviación std | 2.0 |

| Posición %B | Score | Interpretación |
|---|---|---|
| > 95% | 25 | Extremo superior → retroceso probable |
| 70-95% | 40 | Zona alta, precaución |
| 30-70% | 50 | Centro, equilibrio |
| 5-30% | 60 | Zona baja, posible rebote |
| < 5% | 75 | Extremo inferior → rebote probable |

#### 5. Price Action (10%) — Última Vela

Analiza el **body ratio** (|cuerpo| / rango total) de la última vela:

| Body Ratio | Score | Interpretación |
|---|---|---|
| > 70% + cuerpo alcista | 70 | Vela alcista fuerte — compradores dominan |
| > 70% + cuerpo bajista | 30 | Vela bajista fuerte — vendedores dominan |
| ≤ 70% + alcista | 55 | Vela normal alcista |
| ≤ 70% + bajista | 45 | Vela normal bajista |

### Cálculo de Dirección Técnica

La dirección del TF se determina por **votos acumulados** de los 5 indicadores:
- Votos > +1 → **LONG**
- Votos < -1 → **SHORT**
- Intermedio → **NEUTRAL**

La **dirección de M15** se usa como "ancla" (bias general) en el resultado final.

---

## 🌐 Score de Correlación (25% del compuesto)

**Archivo**: `correlation_engine.py`

### 8 Instrumentos Monitoreados

| Asset | Símbolo MT5 | Corr. Esperada | Peso | Lógica Fundamental |
|---|---|---|---|---|
| **DXY** | USDX_Jun26 | +0.75 | 3.0 | DXY sube → USDCLP sube (driver principal) |
| **Cobre** | Cobre_Jul26 | -0.70 | 2.5 | Cobre sube → CLP fuerte → USDCLP baja |
| **USD/MXN** | USDMXN | +0.60 | 1.5 | Risk-off LATAM → ambas monedas caen juntas |
| **USD/BRL** | USDBRL | +0.55 | 1.5 | Risk-off LATAM → BRL y CLP caen juntas |
| **AUD/USD** | AUDUSD | -0.50 | 1.0 | AUD proxy commodities → sube con cobre |
| **USD/CNH** | USDCNH | +0.45 | 1.0 | Yuan débil → menos demanda China → cobre baja |
| **WTI** | WTI | +0.40 | 1.0 | Chile importa energía → WTI sube → CLP baja |
| **S&P 500** | SP | -0.30 | 0.5 | Risk-on → EM se fortalecen → USDCLP baja |

### Cómo se calcula el Score de Correlación

1. **Datos**: Se cargan 200 barras H1 (horarias) de cada instrumento
2. **Retornos**: Se calculan log-returns alineados por timestamp (inner join)
3. **Correlación rolling**: Últimos 50 períodos → matriz de correlación Pearson
4. **Votación por consenso**:
   - Para cada asset: se mira su retorno reciente (últimas 5 velas)
   - Si corr. esperada es **directa** (+) y asset subió → **voto LONG** para USDCLP
   - Si corr. esperada es **inversa** (-) y asset subió → **voto SHORT** para USDCLP
   - Cada voto se pondera por el peso del asset (DXY pesa 3x, S&P pesa 0.5x)
5. **Score**: `50 + |consenso| × 50` → confluencia alta = score alto, señales divididas = 50

### Columna "HOY" — M1 Rolling Pearson (live)

La columna **HOY** en la tabla de correlaciones muestra la **confianza de correlación en los últimos 30 minutos**, calculada así:

```python
# 1. Obtener 30 barras M1 del USDCLP y del asset
# 2. Calcular log-returns de ambos
# 3. Pearson correlation entre ambas series
pearson_corr = np.corrcoef(returns_target, returns_asset)[0, 1]

# 4. Dirigir por signo esperado:
directed_corr = pearson_corr × sign(expected_correlation)
# Positivo = asset se comporta como se espera

# 5. Escalar a 0-100%:
HOY = clamp((directed_corr + 0.5) × 100, 0, 100)
```

| HOY | Color | Significado para el trader |
|---|---|---|
| **≥ 65%** | 🟢 Verde | Asset "enchufado" — sus señales son confiables ahora |
| **40-64%** | 🟡 Amarillo | Correlación moderada — usar con precaución |
| **< 40%** | 🔴 Rojo | Correlación débil o invertida — ignorar este asset |
| **--** | Gris | Sin datos M1 suficientes (< 10 barras) |

### Detección de Divergencias Cross-Asset

El sistema detecta cuando USDCLP **no se mueve** en la dirección que sugieren los otros assets:

> Ejemplo: Si cobre subió +2% (debería → USDCLP baja) pero USDCLP también subió → **DIVERGENCIA detectada**, se genera alerta.

Las divergencias se ordenan por magnitud. Las más fuertes aparecen primero en el panel de alertas.

### Flechas de Movimiento (tabla de correlaciones)

Cada asset muestra 3 flechas de movimiento reciente:
- **Flecha grande** (22px): Tick-to-tick (~2.5s) — movimiento instantáneo
- **Flecha mediana** (17px): 2 barras M1 = ~2 minutos
- **Flecha pequeña** (14px): 6 barras M1 = ~5 minutos

Los sparklines en tooltip muestran las últimas 6 barras M1 con cambio porcentual.

---

## ⚡ Panel de Señales v1 (Indicadores Técnicos Blended)

Las 3 celdas del panel representan **3 velocidades de señal**, cada una combinando TFs con diferentes proporciones:

| Celda | Icono | Blend | Reactividad | Uso |
|---|---|---|---|---|
| **Pulso** | ⚡ | 100% M1 | Instantánea | ¿Qué dicen los indicadores AHORA MISMO? |
| **Corto** | 🔄 | 60% M1 + 40% M2 | ~30s | Suaviza ruido, confirma o niega el pulso |
| **Medio** | 📊 | 40% M1 + 30% M2 + 30% M5 | ~1m | Incorpora tendencia corta |

Cada celda muestra: flecha (▲/▼/◆), dirección (COMPRAR/VENDER/ESPERAR) y % de confianza.

---

## 🧪 Panel de Señales v2 (Derivadas de Precio)

Estas señales añaden **velocidad** (1ª derivada) y **aceleración** (2ª derivada) del precio al score base de los indicadores técnicos.

### Cálculo de derivadas

```python
# Buffer de 24 precios bid (~2 min a 5s refresh)

# 1ª derivada: velocidad = ΔPrecio / ΔTiempo (pips/segundo)
vel_short  = (buf[-1] - buf[-2]) / dt   # últimos 2 ticks (~5s)
vel_medium = (buf[-1] - buf[-6]) / dt   # últimos 6 ticks (~30s)
vel_long   = (buf[-1] - buf[-12]) / dt  # últimos 12 ticks (~60s)

# 2ª derivada: aceleración = ΔVelocidad / ΔTiempo
acceleration = (vel_t - vel_t-1) / dt_avg
```

### Cómo se integran al score

```python
# Velocity boost: velocidad normalizada → ±25 puntos
vel_boost = clamp(velocity / 0.05 × 25, -25, +25)

# Acceleration boost: aceleración normalizada → ±10 puntos
accel_boost = clamp(acceleration / 0.01 × 10, -10, +10)

# Score final v2:
enhanced = base_score + (vel_boost × vel_weight × 2) + (accel_boost × accel_weight × 2)
```

| Celda v2 | Base score | Vel weight | Accel weight |
|---|---|---|---|
| ⚡ 5s | 100% M1 | 0.50 | 0.30 |
| 🔄 30s | 60% M1 + 40% M2 | 0.30 | 0.15 |
| 📊 1m | 40% M1 + 30% M2 + 30% M5 | 0.15 | 0.05 |

### Barra de Momentum

Debajo de las señales v2, una barra visual muestra el estado del momentum:

| Estado | Significado | Color |
|---|---|---|
| ⏫ Subiendo y acelerando | Impulso comprador fuerte | Verde |
| 🔼 Subiendo pero frenando | Posible techo pronto | Verde claro |
| ↗️ Subiendo suave | Movimiento lento al alza | Gris |
| ⏬ Bajando y acelerando | Impulso vendedor fuerte | Rojo |
| 🔽 Bajando pero frenando | Posible piso pronto | Rosa |
| ↘️ Bajando suave | Movimiento lento a la baja | Gris |
| ⏸️ Sin movimiento | Mercado quieto | Gris oscuro |

---

## 📐 Niveles de Price-Action (Soporte / Resistencia)

**Archivo**: `levels_engine.py`

### Camarilla Pivot Points (datos diarios)

Calculados con H/L/C del **día anterior** (fuente: babypips.com):

```
Range = High_ayer - Low_ayer
PP = (H + L + C) / 3
R1 = Close + Range × 1.1/12
R2 = Close + Range × 1.1/6
R3 = Close + Range × 1.1/4
S1 = Close - Range × 1.1/12
S2 = Close - Range × 1.1/6
S3 = Close - Range × 1.1/4
```

### Swing Levels (datos M15)

Detectados con `scipy.signal.argrelextrema(order=5)`:
- Un precio es **swing high** si es el máximo en 5 velas a cada lado (= 2.5 horas de contexto en M15)
- Un precio es **swing low** si es el mínimo en 5 velas a cada lado
- Filtro: solo niveles dentro de ±5% del precio actual

### Niveles Combinados

Se combinan Camarilla + Swings y se seleccionan los **3 más cercanos** por arriba y por abajo del precio actual. Si faltan niveles, se extrapolan sintéticos usando el rango diario.

La **interpretación de posición** indica si el precio está sobre/bajo el pivot, cerca de S1/R1, o ha roto el máximo/mínimo de ayer.

---

## 📊 Backtesting

Reproduce el motor de scoring sobre datos históricos y compara con trades reales del operador.

- **Configurable**: período (100-2000 velas M1), rango de trades (7-365 días), umbral de score
- **Gráfico dual**: precio vs score con zonas de señal coloreadas
- **Métricas**: % acierto, % pérdidas filtrables, señal activa
- **Tabla detallada**: cada trade del journal vs recomendación SENTINEL en ese momento

---

## 🤖 Asistente IA

Chat integrado con modelos de Anthropic. La IA recibe **todos los datos del dashboard** como contexto: scores, derivadas, correlaciones, niveles y alertas.

| Modo | Modelo | Tiempo | Costo/consulta |
|---|---|---|---|
| 🧠 Profundo | Claude Opus 4.7 | 3-5 min | ~$0.07 |
| ⚡ Rápido | Claude Sonnet 4.6 | 15-45s | ~$0.024 |

Tracking de costos en vivo: tokens, USD por consulta, total de sesión.

### Configurar API Key
1. Crear cuenta en [console.anthropic.com](https://console.anthropic.com)
2. Generar una API key
3. Ingresar directamente en el dashboard **o** como variable de entorno:
   ```bash
   set ANTHROPIC_API_KEY=sk-ant-xxxxx
   ```

---

## ⚙️ Configuración Detallada (`config.py`)

### Fuente de Datos
| Parámetro | Valor | Descripción |
|---|---|---|
| `DATA_MODE` | `"mt5"` | MT5 real-time (o `"api"` para Yahoo fallback) |
| `BARS_TO_FETCH` | 200 | Barras a descargar por timeframe |
| `DASHBOARD_REFRESH_SECONDS` | 2.5 | Ciclo de refresh del dashboard |

### Gestión de Riesgo
| Parámetro | Valor | Descripción |
|---|---|---|
| `risk_per_trade_pct` | 1% | Riesgo máximo por trade |
| `max_daily_loss_pct` | 3% | Pérdida máxima diaria |
| `max_trades_per_day` | 3 | Límite de trades |
| `min_rr_ratio` | 1.5:1 | Mínimo risk:reward |
| `atr_sl_multiplier` | 2.0 | ATR × 2.0 para stop loss |
| `atr_tp_multiplier` | 3.0 | ATR × 3.0 para take profit |

### Horario Operativo (Chile CLT = UTC-4)
| Parámetro | Valor |
|---|---|
| Apertura | 09:30 CLT |
| Cierre primario | 14:00 CLT |
| Cierre absoluto | 15:30 CLT |
| Buffer noticias | 30 min antes/después |

### Correlaciones
| Parámetro | Valor | Descripción |
|---|---|---|
| `CORRELATION_WINDOW` | 50 períodos | Ventana rolling para Pearson |
| `CORRELATION_BREAK_THRESHOLD` | 0.3 | Umbral de quiebre |
| `DIVERGENCE_THRESHOLD` | 2% | Umbral de divergencia |

---

## 🔄 Actualizaciones

**Automáticas**: `SENTINEL.bat` verifica la rama `release` de GitHub cada vez que se abre.
Si hay una nueva versión, la descarga, actualiza dependencias y relanza automáticamente.

### Flujo de ramas
```
master   ← desarrollo (nuevas features, experimentos)
release  ← estable (lo que reciben los traders)
```

Para promover cambios a los traders:
```bash
git checkout release
git merge master
git push origin release
```

---

## ⚠️ Disclaimer

SENTINEL es una herramienta de **análisis y apoyo a la decisión**.
NO ejecuta trades automáticamente. NO es asesoría financiera.
Toda decisión de trading es responsabilidad exclusiva del operador.
