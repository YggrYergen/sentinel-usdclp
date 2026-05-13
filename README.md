# 🛡️ SENTINEL v3.4 "Scalper Pro" — USD/CLP Trading Intelligence

> Sistema de análisis en tiempo real para scalping de USD/CLP.
> Conecta con MetaTrader 5 para datos en vivo, calcula scores técnicos multi-timeframe,
> correlaciones cross-asset, señales con derivadas de precio, backtesting y chat con IA.

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

## 🏗️ Arquitectura

```
SENTINEL.bat                  ← Un click para todo
sentinel/
├── dashboard.py              # UI principal (Streamlit)
├── sentinel_core.py          # Motor de scoring compuesto
├── technical_scorer.py       # Score técnico (EMA, RSI, MACD, BB, PA)
├── correlation_engine.py     # Correlaciones cross-asset (8 assets)
├── levels_engine.py          # Niveles S/R (Camarilla + swing detection)
├── data_feed.py              # Fuente de datos (MT5 real-time + Yahoo fallback)
├── indicators.py             # Cálculo de indicadores técnicos
├── backtester.py             # Motor de backtesting + replay de scores
├── ai_chat.py                # Asistente IA (Claude Opus 4.7 / Sonnet 4.6)
├── config.py                 # Pesos, umbrales, símbolos MT5
├── version.py                # Versión actual del sistema
├── check_state.py            # Diagnóstico programático
└── requirements.txt          # Dependencias Python
```

## 📊 Sistema de Scoring

### Score Compuesto (0-100)
| Componente | Peso | Fuente |
|---|---|---|
| Técnico | 75% | EMA, RSI, MACD, Bollinger Bands, Price Action |
| Correlación | 25% | DXY, Cobre, WTI, USDMXN, USDBRL, AUDUSD, USDCNH, SP500 |

### Timeframes
| TF | Peso | Uso |
|---|---|---|
| M1 | 40% | Ejecución inmediata |
| M2 | 30% | Confirmación |
| M5 | 20% | Tendencia corta |
| M15 | 10% | Contexto |

### Panel de Señales v1
- **Pulso (5s)**: 100% M1 — reacción instantánea
- **Corto (30s)**: 60% M1 + 40% M2 — suaviza ruido
- **Medio (1m)**: 40% M1 + 30% M2 + 30% M5 — incorpora tendencia

### Señales v2 (Derivadas)
- **1ª derivada (velocidad)**: ¿El precio sube o baja ahora?
- **2ª derivada (aceleración)**: ¿El movimiento se acelera o frena?
- Visualización: barra de momentum + texto interpretativo

## 📊 Backtesting

Reproduce el motor de scoring sobre datos históricos y compara con trades reales.

- Configurable: período (100-2000 velas M1), rango de trades (7-365 días), umbral de score
- Gráfico dual: precio vs score con zonas de señal
- Métricas: % acierto, % pérdidas filtrables, señal activa
- Tabla detallada de cada trade vs recomendación SENTINEL

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

## ⚠️ Disclaimer

SENTINEL es una herramienta de **análisis y apoyo a la decisión**.
NO ejecuta trades automáticamente. NO es asesoría financiera.
Toda decisión de trading es responsabilidad exclusiva del operador.
