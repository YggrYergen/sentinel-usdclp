# 📋 INVESTIGACIÓN PROFUNDA #1 — Sistema de Trading USD/CLP

> **Fecha:** 2026-05-12
> **Búsquedas realizadas:** 100+
> **Estado:** 3 Rondas completadas — DOCUMENTO FINAL DE INVESTIGACIÓN

---

## 🚨 HALLAZGOS CRÍTICOS

### HALLAZGO #1: XTB NO SOPORTA METATRADER 5 NI TIENE API

- **XTB usa exclusivamente xStation 5.** MetaTrader 5 NO disponible.
- **La API de XTB fue eliminada permanentemente el 14 de marzo de 2025.**
- Sin forma de conectar Python, bots, ni nada programático a XTB.
- **Fuente:** xtb.com (oficial), github.com, intercom-help.eu | **Calidad:** ⭐⭐⭐⭐⭐

### HALLAZGO #2: CAPITARIA — EL GAME CHANGER 🟢

**Capitaria usa MetaTrader 5 y ofrece USD/CLP + Cobre + todos los instrumentos necesarios.**

| Atributo | Detalle |
|----------|---------|
| **Plataforma** | MetaTrader 5 (Desktop, Mobile, Web) ✅ |
| **USD/CLP** | Disponible ✅ |
| **Cobre** | Disponible ✅ |
| **WTI** | Disponible ✅ |
| **Otros instrumentos** | 500+ CFDs (forex, índices, acciones, commodities, crypto) ✅ |
| **Comisiones** | Sin comisiones — ganan por spread ⚠️ |
| **País** | Chile (Capitaria Latam SpA) ✅ |
| **Regulación** | UAF (prevención lavado), **NO regulada por CMF** ⚠️ |
| **API/Python** | Si MT5 está habilitado → `pip install MetaTrader5` funciona ✅ |

**Fuentes:** capitaria.com (oficial), rankia.cl, wikifx.com, fintechile.org
**Calidad:** ⭐⭐⭐⭐ (sitio oficial + reviews independientes)

#### ¿Cómo funciona Python + MT5 + Capitaria?

La librería `MetaTrader5` de Python (`pip install MetaTrader5`) se conecta al **terminal MT5 instalado en tu PC**. NO depende de una API del broker — se conecta al programa MT5 local. Esto significa:

1. Instalas MT5 de Capitaria en tu PC
2. Inicias sesión con tu cuenta Capitaria
3. Python se conecta al terminal MT5 local vía `mt5.initialize()`
4. Desde Python puedes: leer datos en tiempo real, calcular indicadores, generar señales
5. Opcionalmente: enviar órdenes vía `mt5.order_send()` (trading automatizado)

**Esto HABILITA toda la arquitectura SENTINEL que diseñamos originalmente.**

**Fuente:** mql5.com (documentación oficial MetaTrader), pypi.org, quantinsti.com
**Calidad:** ⭐⭐⭐⭐⭐ (documentación oficial)

#### ⚠️ ADVERTENCIAS SOBRE CAPITARIA

> **REGULACIÓN:** Capitaria NO está regulada por CMF ni por ningún regulador tier-1 internacional (FCA, ASIC, CySEC). Está bajo supervisión de UAF solo para anti-lavado.
> Múltiples reviews independientes la catalogan como "alto riesgo" por falta de regulación.
>
> **MITIGACIÓN:** Si ya están operando con un broker similar, el riesgo regulatorio no cambia. Lo importante: no dejar más capital del necesario en la cuenta, retirar ganancias regularmente.
>
> **Fuentes:** wikifx.com, reliableforexbroker.com, theforexreview.com, wikibit.com

#### Preguntas que deben hacer a Capitaria:

1. **¿Permiten trading algorítmico / Expert Advisors en MT5?** (Algunos brokers lo restringen)
2. **¿Cuál es el spread típico de USD/CLP?** (Si es muy ancho, erosiona ganancias)
3. **¿Ofrecen cuenta demo con datos reales de mercado?** (Para testear el sistema sin riesgo)
4. **¿Hay restricción de lote mínimo para USD/CLP?**
5. **¿Cobran swap/rollover por posiciones intraday?** (Como es day trading, debería ser mínimo)

---

## 📊 ARQUITECTURA SENTINEL v3 (Con Capitaria + MT5)

```
┌──────────────────────────────────────────────────────────────┐
│                 SENTINEL v3 — Con Capitaria MT5               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  MetaTrader 5 (Capitaria)          Python (tu PC, 16GB)      │
│  ────────────────────────          ─────────────────────     │
│  • Cuenta real/demo                • pip install MetaTrader5 │
│  • 9 instrumentos en Market Watch  • mt5.initialize()        │
│  • Ejecución de órdenes            • Datos en tiempo real    │
│  • Gráficos como respaldo          • Motor de correlaciones  │
│                                    • Sistema de scoring      │
│  DOM Bancario (Zoom)               • Dashboard Streamlit     │
│  (Input visual manual)             • Trading Journal         │
│                                    • Calculadora ATR sizing  │
│  TradingView (complemento)         • Alertas sonoras         │
│  (Charting adicional si quieren)                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Flujo de Operación

```
1. MT5 Capitaria corriendo → conectado a cuenta
2. Python lee datos de 9 instrumentos cada 5-15 segundos
3. Python calcula: indicadores técnicos + correlaciones + scoring
4. Dashboard Streamlit muestra score compuesto en tiempo real
5. Cuando score > umbral → ALERTA sonora + visual
6. Trader revisa confluencia + DOM bancario
7. Si todo alineado → ejecuta manualmente en MT5 (o semi-auto)
8. Python registra trade en journal automáticamente
```

---

## 🏆 ESTRATEGIAS: RANKING POR EVIDENCIA

### Tier 1: ALTA EVIDENCIA + ALTA APLICABILIDAD

#### 1. Price Action + Confluence Multi-Timeframe
**Evidencia:** ⭐⭐⭐⭐⭐ | **Aplicabilidad USD/CLP:** ⭐⭐⭐⭐⭐

Consenso universal entre prop firms, traders verificados, y fuentes educativas.

**Reglas:**
1. Contexto H4/D1: tendencia con EMA 50/200 o estructura HH/HL vs LH/LL
2. Esperar precio en zona clave: S/R horizontal + Fibonacci 38.2%/50%/61.8%
3. Confirmar con vela de rechazo: Pin Bar (wick ≥ 2/3) o Engulfing
4. Confluencia mínima: 3+ factores alineados
5. Stop detrás de estructura, TP mínimo 1.5:1

**Fuentes:** dailypriceaction.com, audacity.capital, brightfunded.com, xs.com

#### 2. Cross-Asset Divergence Trading (NUESTRA VENTAJA)
**Evidencia:** ⭐⭐⭐⭐ | **Aplicabilidad USD/CLP:** ⭐⭐⭐⭐⭐

| Relación | Dirección | Fuerza |
|----------|-----------|--------|
| Cobre ↔ USDCLP | INVERSA (Cobre↑ → USDCLP↓) | 🟢 FUERTE |
| DXY ↔ USDCLP | DIRECTA (DXY↑ → USDCLP↑) | 🟢 FUERTE |
| WTI ↔ USDCLP | DIRECTA (WTI↑ → USDCLP↑) | 🟡 MODERADA |
| USDMXN/BRL ↔ USDCLP | DIRECTA (co-movimiento LATAM) | 🟡 MODERADA |
| USDCNH → Cobre | CNH débil → Cobre↓ | 🟡 MODERADA |

**Señal:** Cuando USDCLP diverge de lo que DXY + Cobre sugieren → reversión probable.

**Fuentes:** tradingeconomics.com, xtransfer.com, fynsa.com, mining.com

#### 3. Supply & Demand Zones + DOM Confirmation
**Evidencia:** ⭐⭐⭐⭐ | **Aplicabilidad USD/CLP:** ⭐⭐⭐⭐

El DOM bancario da ventaja ÚNICA para confirmar absorción en zonas.

**Fuentes:** purefinancialacademy.com, dukascopy.com, citytradersimperium.com

### Tier 2: BUENA EVIDENCIA

#### 4. EMA 9/21/50 + RSI(14) + ATR — Framework técnico estándar
#### 5. Wyckoff Accumulation/Distribution — Requiere experiencia, ideal con DOM
#### 6. Fibonacci + Confluencia — Subjetivo pero efectivo como complemento

### Tier 3: EVIDENCIA LIMITADA

#### 7. ICT/SMC — Sin verificación independiente. Solo 1-10% de prop firm traders ganan consistentemente con CUALQUIER estrategia.
#### 8. Bots automatizados — No existe bot "mágico" open-source rentable verificado.

---

## 🛡️ GESTIÓN DE RIESGO

### Datos de prop firms sobre lo que funciona:

| Parámetro | Agresivo (MÁXIMO) | Conservador (RECOMENDADO) |
|-----------|-------------------|---------------------------|
| Riesgo/trade | 2% (30,000 CLP) | 1% (15,000 CLP) |
| Máx diario | 5% (75,000 CLP) | 3% (45,000 CLP) |
| Máx trades/día | 4 | 2-3 |
| R:R mínimo | 1.5:1 | 2:1 |
| Stop Loss | ATR × 2.0 | ATR × 2.0 |

**⚠️ El 10% diario que mencionaste es EXTREMADAMENTE agresivo. Con prop firm rules serían eliminados.**

### Fórmula de Expectancy

```
Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss)

Con R:R 2:1 → solo necesitas 34% win rate para ser rentable
Con R:R 1.5:1 → necesitas 40% win rate
Con R:R 1:1 → necesitas >50% win rate
```

### Regla Anti-Revenge Trading (NO NEGOCIABLE)

> "Si pierdes 2 trades seguidos → PARAS por 2 horas mínimo."
> "Si alcanzas max pérdida diaria → CIERRAS la plataforma. Punto."

**Fuentes:** goatfundedtrader.com, blueguardian.com, tradezella.com, FTMO rules

---

## 📅 CONTEXTO MACRO USD/CLP — MAYO 2026

| Factor | Estado | Impacto en USDCLP |
|--------|--------|-------------------|
| TPM BCCh | 4.5% estable | Neutral |
| Fed Rate | Expectativa recortes | Si recorta → USDCLP↓ |
| Cobre | Demanda fuerte (electrificación) | Soporte para CLP (USDCLP↓) |
| WTI | Prima riesgo por Medio Oriente | Presión USDCLP↑ |
| Catalizadores | IPC Chile, Minutas BCCh, NFP, FOMC | Volatilidad alta |

**Fuentes:** bcentral.cl, investing.com, forbes.cl | **Calidad:** ⭐⭐⭐⭐⭐

---

## ⏰ HORARIO ÓPTIMO

| Hora Chile | Sesión | Recomendación |
|------------|--------|---------------|
| 05:00-09:00 | Pre-mercado | ❌ NO OPERAR |
| **09:00-12:00** | **Apertura Chile** | ✅ **VENTANA PRIMARIA** |
| **12:00-14:00** | **Overlap con NY** | ✅ **VENTANA PRIMARIA** |
| 14:00-16:00 | Cierre Chile | ⚠️ Solo si hay setup |
| 16:00+ | Post-cierre | ❌ NO OPERAR |

---

## 📋 ROADMAP (Adaptado a Capitaria + MT5)

### Fase 0: Setup (Día 1-3) 🔥
- [ ] Confirmar con Capitaria: ¿permiten EAs/trading algorítmico? ¿spread USDCLP? ¿cuenta demo?
- [ ] Abrir cuenta demo Capitaria + instalar MT5
- [ ] Instalar Python + `pip install MetaTrader5 pandas numpy streamlit plotly`
- [ ] Verificar conexión Python ↔ MT5 con los 9 instrumentos
- [ ] Establecer reglas de riesgo POR ESCRITO
- [ ] Descargar CSV trades históricos de XTB

### Fase 1: Motor de Correlaciones (Semana 1-2) — ALTO VALOR
- [ ] Script Python que lee 9 instrumentos de MT5 cada N segundos
- [ ] Matriz de correlación rolling (50, 100, 200 periodos)
- [ ] Detector de divergencias (USDCLP vs DXY/Cobre)
- [ ] Dashboard Streamlit con heatmap
- [ ] Alertas cuando correlaciones se rompen

### Fase 2: Score Técnico Multi-Indicador (Semana 2-3)
- [ ] Calcular RSI, MACD, Bollinger, VWAP, Ichimoku, EMA para USDCLP
- [ ] Sistema de votación con pesos
- [ ] Score 0-100 visible en dashboard
- [ ] Multi-timeframe: M5, M15, H1, H4
- [ ] Alertas cuando score > 65

### Fase 3: Score Compuesto + Risk Management (Semana 3-4)
- [ ] Unificar scores (Técnico 30%, Correlación 45%, Riesgo 20%, DOM 5%)
- [ ] Calculadora position sizing ATR
- [ ] Stop/TP dinámicos
- [ ] Trading journal automático

### Fase 4: Optimización (Semana 5+)
- [ ] Detector régimen mercado
- [ ] Pesos adaptativos
- [ ] Journal analytics
- [ ] Backtesting del sistema

---

## 📚 FUENTES POR CALIDAD

### ⭐⭐⭐⭐⭐ Tier-1
- bcentral.cl, xtb.com, capitaria.com, mql5.com, tradingeconomics.com, pypi.org

### ⭐⭐⭐⭐ Tier-2
- babypips.com, dukascopy.com, pepperstone.com, FTMO/prop firms, mining.com, fynsa.com, rankia.cl

### ⭐⭐⭐ Tier-3
- reddit.com, medium.com, youtube.com (filtrar con cuidado)

### ⭐⭐ Tier-4 (precaución)
- "Gurús" de redes, vendedores de bots/señales, sitios con afiliación agresiva

---

# 🔬 RONDA 2: PROFUNDIZACIÓN (25 queries adicionales)

---

## 📊 LO QUE DICEN LOS DATOS DE FTMO (Evidencia más dura disponible)

FTMO es la prop firm más grande del mundo. Sus datos representan la mejor evidencia disponible sobre qué funciona realmente.

**Hallazgos clave de traders FTMO consistentemente rentables:**

| Factor | Lo que hacen los que GANAN | Lo que hacen los que PIERDEN |
|--------|---------------------------|------------------------------|
| Riesgo/trade | 0.1% - 1% del capital | >2% o sin límite |
| R:R ratio | Mínimo 1:2, muchos 1:3 | 1:1 o peor |
| Trades/día | 1-3 de alta calidad ("A+ setups") | 5-10+ (overtrading) |
| Win rate | 30-50% (compensado con alto R:R) | >60% pero con R:R malo |
| Timeframes | Multi-TF: D1/H4 contexto → M5/M15 ejecución | Solo un TF |
| Sesión | Especialistas en 1-2 sesiones | Todo el día sin filtro |
| Psicología | "Set and forget" — ponen SL/TP y se van | Micromanagean cada tick |
| Post-pérdida | Reducen tamaño o paran | Revenge trading |

**Fuente:** ftmo.com (múltiples artículos oficiales), goatfundedtrader.com
**Calidad:** ⭐⭐⭐⭐⭐ (datos de la prop firm más grande del mundo, miles de traders evaluados)

> **CONCLUSIÓN CLAVE:** Los traders exitosos ganan NO por tener mejor análisis técnico, sino por **gestión de riesgo superior + disciplina**. El 90% del edge está en la gestión, no en la predicción.

---

## 🧠 DETECCIÓN DE RÉGIMEN DE MERCADO (Hidden Markov Models)

**Concepto:** El mercado tiene "estados ocultos" (trending/ranging/volátil) que no se ven directamente pero afectan TODO. Un HMM puede detectarlos automáticamente.

**Implementación en Python:**
- Librería: `hmmlearn` (GaussianHMM)
- Inputs: log returns + volatilidad rolling del USDCLP
- Output: Probabilidad de estar en régimen Trending vs Ranging vs Crisis
- **Uso:** Solo operar cuando el HMM confirma que estamos en régimen favorable

**Resultados de investigación:**
- Reduce max drawdown significativamente vs estrategias estáticas
- Los regímenes son "persistentes" (duran días/semanas) → señal confiable
- **Limitación:** Requiere reentrenamiento periódico (cada 2-4 semanas)

**Fuentes:** pyquantlab.com, cuni.cz (académico), plainenglish.io, medium.com (varios)
**Calidad:** ⭐⭐⭐⭐ (respaldo académico + implementaciones documentadas)

**Aplicación para SENTINEL:** Añadir HMM como "filtro maestro". Si el régimen es "crisis/alta volatilidad" → reducir sizing 50% o no operar.

---

## 📉 KELLY CRITERION: POSITION SIZING ÓPTIMO

### Fórmula Kelly:
```
f* = (bp - q) / b

Donde:
f* = Fracción del capital a arriesgar
p = Probabilidad de ganar
q = Probabilidad de perder (1 - p)
b = Payoff ratio (avg win / avg loss)
```

### ¿Por qué NO usar Full Kelly?
- Full Kelly puede causar drawdowns de 50%+ incluso con edge positivo
- Psicológicamente insostenible
- Pequeños errores en la estimación de win rate → ruina

### Recomendación: Half-Kelly o Quarter-Kelly
- **Half-Kelly:** Retiene ~75% de la tasa de crecimiento con mucho menos volatilidad
- **Quarter-Kelly:** Ultra conservador, ideal durante recuperación de drawdown

### Framework de Recuperación de Drawdown:
1. **PARAR** — Diagnosticar: ¿fallo de mercado o fallo de ejecución?
2. **Reducir tamaño 50-75%** (si normalmente arriesgas 2%, baja a 0.5-1%)
3. **10-20 trades "limpios"** antes de considerar subir tamaño
4. **Graduación escalonada:** 50% → 75% → 100% del sizing normal

**Fuentes:** quantvps.com, journalplus.co, backtestbase.com, wikipedia.org (Kelly)
**Calidad:** ⭐⭐⭐⭐⭐ (matemática establecida + aplicación práctica documentada)

---

## 🇨🇱 PATRONES INTRADAY ESPECÍFICOS DEL USDCLP

**Hallazgo académico (University of Texas):** El USDCLP NO sigue un random walk perfecto. Existen patrones periódicos intraday y semanales ligados a:
- Flujos corporativos de exportadores/importadores (especialmente cobre)
- AFPs (fondos de pensiones) rebalanceando
- Bancos comerciales ejecutando grandes órdenes en ventanas de liquidez

### Picos de Liquidez USDCLP:
1. **~11:00-12:00 CLT** — Pico mid-day (institucionales locales)
2. **~14:00-15:00 CLT** — Overlap con NY + cierre local
3. **Mínima liquidez:** Pre-apertura (antes de 09:00) y post-cierre (después de 16:00)

**Fuentes:** utexas.edu (académico), investing.com, fpmarkets.com
**Calidad:** ⭐⭐⭐⭐⭐ (investigación académica tier-1)

> **APLICACIÓN:** Concentrar operaciones en 09:30-14:00 CLT. Evitar las primeras y últimas medias horas del mercado (spreads anchos, liquidez baja).

---

## ⚠️ RIESGO DE QUIEBRE DE CORRELACIONES

**Cuándo las correlaciones históricas FALLAN:**
- Crisis sistémicas → TODAS las EM currencies caen juntas (correlación → 1.0)
- Intervención del BCCh → USDCLP se mueve independiente del DXY/Cobre
- Shock político local → Idiosincratic risk domina
- Cambio de régimen de tasas → Carry trade unwind

**Cómo detectarlo:**
1. **Rolling correlation** (ventana 20 periodos) cae por debajo de umbral → ALERTA
2. **HMM** detecta cambio de régimen → reducir sizing
3. **Volatilidad implícita** sube bruscamente → modo defensivo

**Implicación para SENTINEL:** El score de correlación debe incluir un "circuit breaker" — si la correlación histórica se rompe, el score de correlación se neutraliza (50) en vez de dar señal falsa.

**Fuentes:** collinseow.com, ieee.org, diva-portal.org, lombardodier.com
**Calidad:** ⭐⭐⭐⭐ (académico + institucional)

---

## ✅ CHECKLIST PRE-TRADE (Estándar Institucional)

### Fase 1: Contexto
- [ ] ¿Hay noticias high-impact en las próximas 2h? (Si sí → NO operar)
- [ ] ¿Cuál es el régimen? (Trending/Ranging/Crisis)
- [ ] ¿Estamos en horario de liquidez? (09:30-14:00 CLT)
- [ ] ¿La tendencia H4/D1 está clara? ¿En qué dirección?

### Fase 2: Riesgo (REGLAS DURAS)
- [ ] ¿El trade arriesga ≤ 1-2% del capital?
- [ ] ¿El SL está definido por estructura, no por un número arbitrario?
- [ ] ¿El R:R es ≥ 1.5:1?
- [ ] ¿Tengo posiciones correlacionadas abiertas? (Si sí → ¿exposición total dentro de límites?)

### Fase 3: Señal
- [ ] ¿El score compuesto SENTINEL es ≥ 65?
- [ ] ¿Hay confluencia de AL MENOS 3 factores?
- [ ] ¿El patrón de vela confirma?
- [ ] ¿Las correlaciones cross-asset confirman?

### Fase 4: Disciplina
- [ ] ¿Estoy operando por SEÑAL o por emoción/aburrimiento/FOMO/revenge?
- [ ] ¿He alcanzado mi máximo de trades diarios?
- [ ] ¿He alcanzado mi máximo de pérdida diaria?

> **REGLA DE ORO: Si cualquier checkbox de Fase 1 o Fase 2 falla → NO OPERAR. Sin excepciones.**

---

## 🛠️ HERRAMIENTAS DE IMPLEMENTACIÓN

### Backtesting (Python)
- **vectorbt:** Ultra rápido, procesa miles de parámetros en paralelo
- **Walk-Forward Optimization:** Gold standard — entrenar en ventana A, validar en ventana B, avanzar
- **Métricas:** Sharpe, Sortino, Profit Factor, Max Drawdown, Win Rate
- **Regla:** Mínimo 100+ trades en backtest para significancia estadística

### Trading Journal
| Tool | Gratis | Mejor Para |
|------|--------|------------|
| **TradesViz** | 3,000 trades/mes | Más completo gratis |
| **Stonk Journal** | Ilimitado | Totalmente gratis, manual |
| **FX Replay** | Sí | Forex específico |
| **Custom (Python)** | Sí | Integración con SENTINEL |

**Recomendación:** Construir journal custom en Python integrado con SENTINEL para log automático. Complementar con TradesViz para analytics avanzados.

### Dashboard en Tiempo Real (Streamlit)
- `st.empty()` + `while True` loop para actualización continua
- Plotly para charts interactivos
- Actualización cada 5-15 segundos via MT5
- `@st.cache_data(ttl=60)` para eficiencia

### ATR Stop Loss — Multiplicador Óptimo

| Multiplicador | Uso | Para USDCLP |
|---------------|-----|-------------|
| 1.5× | Scalping, muy ajustado | ❌ Demasiado tight para un exótico |
| **2.0×** | **Day trading estándar** | ✅ **RECOMENDADO** |
| 3.0× | Swing, movimientos grandes | ⚠️ Solo si buscan capturar todo el día |

**Fuentes:** avatrade.com, acy.com, quantifiedstrategies.com
**Calidad:** ⭐⭐⭐⭐

---

## 🔮 OUTLOOK MACRO (Lo que afecta al USDCLP a mediano plazo)

### Cobre
- **Déficit estructural de oferta** proyectado por demanda de EVs + electrificación
- Precios con sesgo alcista a mediano plazo → POSITIVO para CLP → USDCLP tendería a bajar
- **Riesgo:** Recesión global → demanda China cae → Cobre baja → CLP se debilita

### DXY / Fed
- Mercado anticipa recortes graduales de tasas en 2026
- Si Fed recorta → DXY↓ → USDCLP↓
- **Riesgo:** Inflación persistente → Fed no recorta → DXY↑ → USDCLP↑

### Spreads en Pares Exóticos
- USDCLP tendrá spreads 20-100× más anchos que EUR/USD
- **Esto hace que el scalping sea INVIABLE** — necesitan capturar movimientos de al menos 3-5× el spread para ser rentables
- Calcular costo de spread ANTES de cada trade

> **Implicación:** Con spreads anchos, la estrategia debe ser de **pocos trades de alta calidad y alta R:R**, no muchos trades pequeños. Esto refuerza la filosofía FTMO de "A+ setups only".

---

# 🎯 RONDA 3: VERDAD INCÓMODA + IMPLEMENTACIÓN FINAL (25 queries adicionales)

---

## 💰 EXPECTATIVAS REALISTAS — La verdad que nadie quiere escuchar

### ¿Cuánto puede ganar realmente un day trader?

| Nivel | Retorno mensual | % de traders que lo logran |
|-------|----------------|---------------------------|
| Principiante | Negativo (pierde dinero) | 70-90% de retail |
| Competente | 0-2% mensual | 5-15% |
| Profesional | 1-3% mensual consistente | 1-5% |
| Elite | 3-5% mensual consistente | <1% |
| "Gurú de Instagram" | 20-50% mensual | 0% sostenible |

**Fuentes:** defcofx.com, mondfx.com, thinkcapital.com, quantifiedstrategies.com, a1trading.com, myfxbook.com
**Calidad:** ⭐⭐⭐⭐⭐ (consenso de la industria + datos de plataformas verificadas)

### Proyección realista con 1.5M CLP:

| Escenario | Retorno/mes | Mes 6 | Mes 12 | Notas |
|-----------|-------------|-------|--------|-------|
| **Conservador (1%)** | 15,000 CLP | 1,592,000 | 1,690,000 | Sostenible |
| **Realista-bueno (3%)** | ~45,000 CLP | 1,791,000 | 2,137,000 | Excelente si es consistente |
| **Optimista (5%)** | ~75,000 CLP | 2,010,000 | 2,693,000 | Top 1% del mundo |
| **Fantasía (10%)** | ~150,000 CLP | 2,657,000 | 4,709,000 | Estadísticamente insostenible |

> **REALIDAD:** Un retorno de 3% mensual consistente = **42.6% anual compuesto**. Eso SUPERA a la mayoría de hedge funds del mundo. Es un resultado excepcional, no el mínimo.

---

## 🧠 PSICOLOGÍA: TRADING BAJO PRESIÓN FINANCIERA — La trampa más peligrosa

> **⚠️ ESTA SECCIÓN ES LA MÁS IMPORTANTE DE TODO EL DOCUMENTO.**

### El problema:

Cuando la estabilidad financiera de la familia depende de los resultados del trading, ocurre un efecto documentado:

1. **Reducción cognitiva:** El estrés financiero ocupa "ancho de banda mental" → decisiones impulsivas, no analíticas
2. **Aversión a la pérdida amplificada:** Las pérdidas se sienten 2.5× más que las ganancias equivalentes → mantener trades perdedores demasiado tiempo, cortar ganadores prematuramente
3. **Identidad atada al P&L:** Día ganador = validación personal. Día perdedor = fracaso personal. → Ciclo destructivo
4. **Mentalidad de supervivencia:** "Necesito ganar HOY" → romper reglas, overtrading, revenge trading

**Fuentes:** fundingpips.com, fortraders.com, forexclub.pl, gomarkets.com, scottcoop.com
**Calidad:** ⭐⭐⭐⭐⭐ (psicología financiera documentada, investigación conductual)

### Mitigación (NO opcional):

1. **Separar "dinero de trading" de "dinero de vida"** — Lo que está en la cuenta de trading NO es dinero de gastos
2. **Metas de PROCESO, no de dinero** — "Ejecuté mi plan" > "Gané X pesos"
3. **Circuit breakers automáticos** — Si pierdes 3% en el día, la plataforma se cierra. Sin negociación.
4. **Journal emocional** — Anotar estado emocional junto con cada trade. Los trades con tag "ansioso" probablemente tienen peor win rate.
5. **Pausas obligatorias** — Desconectarse de la pantalla cada 2 horas. El sistema nervioso necesita recuperarse.

---

## 🏦 BANCO CENTRAL DE CHILE — Mecanismo de Intervención

**Hallazgos clave (fuentes: bcentral.cl, bis.org):**

- **Régimen de tipo de cambio flexible:** El BCCh NO defiende un nivel específico del dólar
- **Intervención excepcional y discrecional:** NO hay triggers automáticos ni niveles publicados
- **Criterios para intervenir:**
  - Depreciación/apreciación "excesiva" que amenace estabilidad financiera
  - Estrés de mercado extremo
  - Desalineación con fundamentales
- **Reservas internacionales:** USD 44-51 mil millones (2024-2025)
- **En 2024-2025:** No hubo programas de intervención sistemática

**Implicación para trading:** La intervención del BCCh es un "cisne gris" — raro pero devastador. Si USDCLP se mueve de forma extrema (>2-3% en un día), considerar que BCCh PODRÍA actuar. Reducir posiciones.

---

## 🏗️ FLUJOS AFP — El "monstruo oculto" del USDCLP

**Hallazgo académico (Notre Dame University, NBER, BCCh):**

Los fondos de pensión (AFP) mueven volúmenes MASIVOS de USDCLP cuando los afiliados cambian entre fondos (A↔E).

### Datos cuantificados:
- **Elasticidad del precio:** ~0.81-0.83 (baja) → los flujos AFP mueven el tipo de cambio significativamente
- **Impacto medido:** Un rebalanceo grande puede mover USDCLP ~0.59% en pocos días
- **Mecanismo:** AFP compra/vende USD → bancos locales intermedian → forwards con contrapartes internacionales

### Cómo aprovechar:
- Monitorear noticias de cambios masivos entre fondos AFP (ahora regulados, pero aún existen)
- Si hay flujo AFP vendiendo USD → presión bajista en USDCLP (CLP se fortalece)
- Si hay flujo AFP comprando USD → presión alcista en USDCLP (CLP se debilita)
- **Fuente de datos:** Superintendencia de Pensiones publica estadísticas de traspasos

**Fuentes:** wpmucdn.com (paper académico), nd.edu, nber.org, bcentral.cl, ese.cl
**Calidad:** ⭐⭐⭐⭐⭐ (investigación académica de universidades tier-1)

---

## 👁️ CÓMO LEER EL DOM BANCARIO (Guía para la ventana de Zoom)

### Qué buscar:

| Señal | Significado | Acción |
|-------|------------|--------|
| **Absorción en el Bid** | Alto volumen de venta golpea el bid PERO el precio no baja → compradores fuertes absorbiendo | Posible soporte, buscar LONG |
| **Absorción en el Ask** | Alto volumen de compra golpea el ask PERO precio no sube → vendedores absorbiendo | Posible resistencia, buscar SHORT |
| **Stacking** (acumulación de órdenes) | Grandes órdenes aparecen en un nivel → intención real de defender ese precio | Nivel significativo |
| **Pulling** (retiro de órdenes) | Órdenes grandes desaparecen antes de ser ejecutadas → posible spoofing/manipulación | DESCONFIAR del nivel |
| **Exhaustión** | Volumen de agresores se seca → el movimiento se queda sin fuerza | Posible reversión |

### ⚠️ LIMITACIÓN CRÍTICA del DOM en Forex:
- Forex spot es **descentralizado** — NO hay order book global único
- El DOM que ven via el banco es **su liquidez específica**, no todo el mercado
- Para DOM "real" → usar futures (CME) si es posible
- **Usar como CONTEXTO, no como señal directa**

---

## 🔄 WORKFLOW MULTI-TIMEFRAME EXACTO PARA USDCLP

### H4 → M15 → M5 (El "Zoom-Lens")

```
PASO 1: H4 (El Ancla) — ¿Para dónde va el mercado?
├── Identificar tendencia: ¿HH/HL (alcista) o LH/LL (bajista)?
├── Marcar zonas S/R clave + EMA 50/200
├── REGLA: NUNCA operar contra la dirección H4
│
PASO 2: M15 (El Táctico) — ¿Hay un setup formándose?
├── ¿El precio está en una zona H4 de interés?
├── ¿Hay quiebre de estructura (BMS/CHoCH) que confirme?
├── ¿Las correlaciones (DXY/Cobre) confirman dirección?
│
PASO 3: M5 (La Ejecución) — ¿Cuál es el entry exacto?
├── Buscar: Pin bar, engulfing, liquidity sweep
├── SL detrás de la estructura M5 (tight)
├── TP en próxima zona M15/H4
├── R:R debe ser ≥ 1.5:1 ANTES de entrar
│
RESULTADO: SL ajustado + dirección correcta = Alto R:R
```

---

## 📐 CÁLCULO DE PIPS Y SIZING PARA USDCLP

### Fórmula:
```
Pip Value = (0.0001 / Exchange Rate) × Position Size

Ejemplo con USDCLP @ 950:
- 1 micro lot (1,000 units): pip value = 0.1 CLP = ~0.000105 USD
- 1 mini lot (10,000 units): pip value = 1.0 CLP = ~0.00105 USD  
- 1 standard lot (100,000 units): pip value = 10 CLP = ~0.0105 USD
```

> **IMPORTANTE:** Verificar en MT5 Capitaria el contract size y point value específicos. Cada broker puede diferir para pares exóticos.

### Position Sizing con ATR:
```
ATR(14) del USDCLP = X pips (verificar en MT5)
Stop Loss = ATR × 2.0
Risk Amount = Capital × 1% = 1,500,000 × 0.01 = 15,000 CLP
Position Size = Risk Amount / (SL pips × pip value)
```

---

## 🕯️ HERRAMIENTAS COMPLEMENTARIAS VALIDADAS

### Heikin Ashi
- ✅ Excelente para filtrar ruido en USDCLP (par volátil)
- ✅ Usar en H4 para identificar tendencia
- ❌ NO usar para entries precisos (son lagging)
- **Combo:** H4 con Heikin Ashi (tendencia) + M15/M5 con velas normales (entry)

### Ichimoku Cloud
- ✅ Sistema "todo-en-uno": tendencia + momentum + S/R
- ✅ Kumo twist = warning de cambio de tendencia
- ❌ Falla en mercados laterales (muchas señales falsas)
- **Uso:** H4 con Ichimoku como filtro de tendencia. Solo operar cuando precio está claramente arriba/abajo de la nube.

### Mean Reversion (Bollinger + RSI)
- ⚠️ PELIGROSO en pares exóticos — pueden quedar overbought/oversold por SEMANAS
- ⚠️ Los fundamentales (inflación, tasa BCCh) pueden causar trends que NO revierten
- **Uso limitado:** Solo como filtro adicional, NUNCA como señal principal
- **Regla:** Solo considerar mean reversion si la tendencia H4 es LATERAL, no en tendencia

---

## 📱 CALENDARIO ECONÓMICO — Setup Recomendado

| Herramienta | Mejor Para | Push Notifications |
|-------------|-----------|-------------------|
| **Forex Factory** | Gold standard, comunidad | ❌ Solo email/browser |
| **Investing.com** | App mobile + alertas | ✅ Push móvil |
| **Tradays** (MetaQuotes) | Integración con MT5 | ✅ Push móvil |

**Recomendación:** Usar **Investing.com** para alertas móviles + **Forex Factory** como referencia de fondo.

---

## 🎖️ OPCIÓN ALTERNATIVA: PROP FIRMS DESDE CHILE

Si quieren escalar capital sin arriesgar más dinero propio:

- **FTMO, Goat Funded Trader, Blue Guardian** aceptan traders de Chile
- **Capital virtual:** Pueden manejar cuentas de $10K-$200K USD sin poner ese capital
- **Pago:** Via Wise, transferencia bancaria, o crypto
- **Requisito:** Pasar evaluación con reglas de riesgo estrictas
- **Tributación:** Las ganancias tributan en Chile (consultar SII)

> **Estrategia paralela:** Tu padre y su socio operan USDCLP con Capitaria (capital real 1.5M CLP). TÚ podrías intentar una prop firm challenge con la misma estrategia SENTINEL (capital virtual). Si pasas, multiplicas el capital operado sin arriesgar más dinero propio.

---

## 📋 MANUAL DE OPERACIÓN SENTINEL — Día Típico

```
07:30 — Preparación
├── Revisar calendario económico (Investing.com/Forex Factory)
├── ¿Hay noticias high-impact hoy? Marcar horarios
├── Abrir MT5 Capitaria, verificar conexión
├── Abrir Python dashboard (Streamlit)

08:00 — Análisis Pre-Mercado
├── H4 de USDCLP: ¿tendencia? ¿zonas clave?
├── Revisar DXY, Cobre, WTI en TradingView/MT5
├── Dashboard: ¿correlaciones normales o divergentes?
├── Score SENTINEL: ¿cómo está antes de apertura?

09:00 — Mercado Abre (Chile)
├── Observar primeros 30 min sin operar (dejar que se forme rango)
├── DOM bancario: ¿absorción en algún nivel?

09:30-14:00 — Ventana Operativa
├── SOLO operar si score SENTINEL ≥ 65
├── Checklist pre-trade COMPLETO antes de cada entry
├── Máximo 3 trades en el día
├── Si 2 pérdidas seguidas → PAUSA 2 horas
├── Si 3% de pérdida diaria → STOP. Cerrar todo.

14:00-15:30 — Wind Down
├── Cerrar posiciones abiertas (day trading, no overnight)
├── Registrar trades en journal (automático + notas manuales)
├── Anotar estado emocional post-sesión

15:30 — Post-Mercado
├── Dashboard: revisar métricas del día
├── ¿El sistema funcionó? ¿Los scores predijeron bien?
├── Anotar ajustes para mañana
├── DESCONECTARSE de las pantallas
```
