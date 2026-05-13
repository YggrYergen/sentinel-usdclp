# 🛡️ SENTINEL — USD/CLP Trading Intelligence

> Sistema de análisis en tiempo real para scalping de USD/CLP.
> Conecta con MetaTrader 5 para datos en vivo, calcula scores técnicos multi-timeframe,
> correlaciones cross-asset, y señales con derivadas de precio.

## ⚡ Inicio Rápido

```bash
# 1. Clonar repositorio
git clone https://github.com/YggrYergen/sentinel-usdclp.git
cd sentinel-usdclp

# 2. Instalar dependencias
pip install -r sentinel/requirements.txt

# 3. Ejecutar dashboard
streamlit run sentinel/dashboard.py
```

O simplemente ejecuta `INICIAR_SENTINEL.bat` en Windows.

## 📋 Requisitos

- **Python 3.11+**
- **MetaTrader 5** instalado con cuenta Capitaria activa
- **Windows** (MT5 no soporta Linux nativamente)
- **Anthropic API Key** (opcional, para asistente IA)

## 🏗️ Arquitectura

```
sentinel/
├── dashboard.py          # UI principal (Streamlit)
├── sentinel_core.py      # Motor de scoring compuesto
├── technical_scorer.py   # Score técnico (EMA, RSI, MACD, BB, PA)
├── correlation_engine.py # Correlaciones cross-asset
├── levels_engine.py      # Niveles S/R (Camarilla + swing)
├── data_feed.py          # Fuente de datos (MT5 + Yahoo fallback)
├── indicators.py         # Indicadores técnicos
├── backtester.py         # Motor de backtesting
├── ai_chat.py            # Asistente IA (Claude)
├── config.py             # Configuración y pesos
├── version.py            # Versión actual
└── requirements.txt      # Dependencias
```

## 📊 Características

### Score Compuesto
- **Técnico (75%)**: EMA, RSI, MACD, Bollinger Bands, Price Action
- **Correlación (25%)**: DXY, Cobre, WTI, USDMXN, USDBRL, AUDUSD, USDCNH, SP500

### Timeframes
| TF | Peso | Uso |
|---|---|---|
| M1 | 40% | Ejecución inmediata |
| M2 | 30% | Confirmación |
| M5 | 20% | Tendencia corta |
| M15 | 10% | Contexto |

### Panel de Señales
- **Pulso (5s)**: 100% M1 — reacción instantánea
- **Corto (30s)**: 60% M1 + 40% M2 — suaviza ruido
- **Medio (1m)**: 40% M1 + 30% M2 + 30% M5 — incorpora tendencia

### Señales v2 (Derivadas)
- **1ª derivada (velocidad)**: ¿El precio sube o baja ahora?
- **2ª derivada (aceleración)**: ¿El movimiento se acelera o frena?

### Backtesting
- Replay de scoring sobre datos históricos
- Comparación con trades reales del operador
- Umbral configurable, métricas de filtrado

### Asistente IA
- **🧠 Profundo (Claude Opus 4.7)**: Análisis completo, 3-5 min
- **⚡ Rápido (Claude Sonnet 4.6)**: Respuesta en 15-45s
- Recibe todos los datos del dashboard como contexto
- Tracking de costos por consulta

## 🔑 Configuración API

Para activar el asistente IA:
1. Crear cuenta en [console.anthropic.com](https://console.anthropic.com)
2. Generar API key
3. Configurar como variable de entorno:
   ```bash
   set ANTHROPIC_API_KEY=sk-ant-xxxxx
   ```
   O ingresar directamente en el dashboard.

## 🔄 Actualizar

Ejecuta `ACTUALIZAR_SENTINEL.bat` o:
```bash
git pull origin master
pip install -r sentinel/requirements.txt
```

## ⚠️ Disclaimer

SENTINEL es una herramienta de **análisis y apoyo a la decisión**. 
NO ejecuta trades automáticamente. NO es asesoría financiera.
Toda decisión de trading es responsabilidad exclusiva del operador.
