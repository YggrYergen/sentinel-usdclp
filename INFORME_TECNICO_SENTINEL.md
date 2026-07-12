# Informe Técnico — SENTINEL (USD/CLP Trading Intelligence Panel)

> Documento descriptivo y neutro sobre el estado, arquitectura y componentes del proyecto SENTINEL, ubicado en `/mnt/d/FOREX/sentinel/`. Generado a partir de lectura directa del código fuente. Versión de referencia: `3.7.1` ("AI Advisor"), rama `release`, commit más reciente `6ee5310`.

---

## 1. Propósito general

SENTINEL es un panel de análisis en tiempo real para el par USD/CLP orientado a *scalping* (operaciones de 1 a 30 minutos), construido como una aplicación web local con Streamlit. Se conecta a MetaTrader 5 (broker Capitaria) para obtener precios y velas en vivo, con una fuente alternativa (Yahoo Finance) cuando MT5 no está disponible. El sistema no ejecuta operaciones — es de solo lectura/análisis; las llamadas a MT5 están limitadas a lectura de precios y velas (`symbol_info_tick`, `copy_rates_from_pos`, `symbol_select`, `history_deals_get`).

El sistema combina:
- Un **score técnico multi-timeframe** (indicadores clásicos: EMA, RSI, MACD, Bandas de Bollinger, price action).
- Un **score macro/cross-asset** (correlación de USD/CLP con 8 instrumentos relacionados: DXY, cobre, WTI, USD/MXN, USD/BRL, AUD/USD, USD/CNH, S&P 500).
- Niveles de soporte/resistencia (pivots Camarilla + detección de swings).
- Un motor de backtesting que reproduce el scoring sobre datos históricos y lo compara con operaciones reales del trader.
- Un asistente conversacional basado en modelos Claude (Anthropic) que recibe un snapshot completo del dashboard.

A partir de los últimos commits, el proyecto se ha extendido más allá de USD/CLP: existe una segunda versión de dashboard (`dashboard_v2.py`) que añade paneles equivalentes para **NASDAQ100** y **Oro (XAUUSD)**, reutilizando la misma arquitectura de scoring con tablas de correlación y pesos propias por instrumento.

---

## 2. Arquitectura general y flujo de datos

```
SENTINEL.bat (Windows, doble clic)
   └─▶ sentinel/launcher.py   (bootstrap/actualizador autocontenido)
          └─▶ streamlit run sentinel/app.py
                 ├─ "/"   → dashboard.py       (v1 — USD/CLP, producción)
                 └─ "/v2" → dashboard_v2.py    (v2 — USD/CLP + NASDAQ100 + Gold)

Flujo de datos (macro → micro):
MT5 / Yahoo Finance
   │
   ▼
DataFeed (data_feed.py)        ← abstrae la fuente, cachea, normaliza OHLCV
   │
   ├──▶ SentinelCore            ← orquesta el score compuesto (v1, USD/CLP)
   │       ├── TechnicalScorer      → score técnico multi-TF
   │       ├── MacroScorer          → score macro EWMA cross-asset
   │       ├── CorrelationEngine    → score de correlación "legacy" + detección de divergencias
   │       └── LevelsEngine         → niveles S/R
   │
   ├──▶ MacroScorer (instancias adicionales) + instrument_panel.render_panel
   │       → paneles NASDAQ100 y Gold en dashboard_v2.py
   │
   ▼
Dashboard (dashboard.py / dashboard_v2.py)   ← renderiza la UI, refresco periódico
```

Cada página Streamlit se ejecuta como un script completo en cada refresco (patrón estándar de Streamlit): al final del script, si el auto-refresh está activo, se hace `time.sleep(DASHBOARD_REFRESH_SECONDS)` seguido de `st.rerun()`, reiniciando la ejecución del script entero. `DASHBOARD_REFRESH_SECONDS` está fijado en `1.5` segundos en `config.py`.

---

## 3. Punto de entrada y arranque (`SENTINEL.bat`, `launcher.py`, `app.py`)

### 3.1 `launcher.py` (820 líneas)

Es un bootstrap "autocontenido" (no modifica el sistema host — sin cambios de PATH ni registro) que ejecuta una secuencia de 8 pasos, cada uno registrado con logging verboso a un archivo (`sentinel_log.txt`) y a consola:

1. **`check_running()`** — intenta conectarse a `http://localhost:8501`; si responde, asume que ya está corriendo y abre el navegador.
2. **`check_python()`** — valida que la versión de Python del intérprete activo esté en el rango `3.11`–`3.13`. Si no lo está, busca un Python compatible instalado en el sistema (`py -3.12`, `py -3.13`, `py -3.11`, o rutas comunes de instalación) y, si no encuentra ninguno, descarga e instala un **Python portable embebido** (`_python/`, versión `3.12.8`) dentro de la carpeta del proyecto, habilita `pip` editando el archivo `._pth` y lo instala vía `get-pip.py`. Si cambia de intérprete, relanza el script con el nuevo Python (`_relaunch`).
3. **`check_git()`** — busca `git` en el sistema o en una instalación portable (`_git/`, MinGit `2.47.1`); si no existe, la descarga y extrae. Si tampoco está disponible, continúa sin bloquear (usará actualización por ZIP).
4. **`check_updates()`** — limpia directorios temporales de ejecuciones previas interrumpidas (`_cleanup_stale_temps`) y aplica, en orden de preferencia: `git pull` sobre la rama `release` (si existe `.git`), `git clone` a un directorio temporal seguido de copia de archivos (si no existe `.git` pero git está disponible), o descarga de un ZIP del repositorio desde GitHub como última opción. En cualquier caso preserva `chat_history/` y `__pycache__/` sin sobrescribir. Tras actualizar, si el propio `launcher.py` cambió (comparación de hash MD5 antes/después), se relanza a sí mismo para cargar el código nuevo.
5. **`check_deps()`** — lee `requirements.txt`, calcula un hash MD5 del contenido + versión, y usa un archivo marcador (`_deps_ok_<hash>`) para saltar la reinstalación si ya se verificó. Si no hay marcador, intenta importar los paquetes clave (`streamlit, MetaTrader5, pandas, numpy, plotly, ta, scipy, anthropic, yfinance`); si falla, purga la caché de pip e instala con `pip install -r requirements.txt` (timeout de 900s).
6. **`verify_imports()`** — importa cada paquete individualmente y reporta versión.
7. **`verify_dashboard()`** — verificación no bloqueante de que `dashboard.py` puede cargarse como módulo.
8. **`launch()`** — lanza `streamlit run sentinel/app.py` como subproceso, con el navegador abriéndose automáticamente tras 8 segundos en un hilo separado, y transmite la salida del proceso tanto a consola como al archivo de log.

### 3.2 `app.py` (43 líneas) — enrutador

Punto de entrada real que usa la API nativa de multipágina de Streamlit (`st.navigation`):
- Define `init_system()` (cacheada con `@st.cache_resource`) que crea una única instancia compartida de `DataFeed` y `SentinelCore`, evitando abrir dos conexiones MT5 para v1 y v2.
- Registra dos páginas: `dashboard.py` en la ruta raíz (`url_path=""`) y `dashboard_v2.py` en `url_path="v2"`.
- Ejecuta la navegación con `pg.run()`.

### 3.3 `SENTINEL.bat`

Script de Windows de doble clic que invoca al launcher; según el README, delega en él la verificación de si ya está corriendo, la comprobación de actualizaciones en la rama `release`, la instalación/actualización de dependencias y el lanzamiento final con apertura de navegador.

---

## 4. Configuración central (`config.py`, 220 líneas de contenido)

Archivo de constantes y dataclasses, sin lógica de negocio, organizado en secciones:

- **`DATA_MODE`**: `"mt5"` por defecto (alternativa `"api"` para fallback Yahoo).
- **`SYMBOLS`**: mapeo de 9 claves internas a símbolos MT5 para USD/CLP y su set de correlación (target, dxy→`USDX_Jun26`, copper→`Cobre_Jul26`, wti→`WTI`, usdmxn, usdbrl, audusd, usdcnh, sp500→`SP`).
- **`SYMBOLS_YAHOO`**: mapeo equivalente a tickers de Yahoo Finance para el modo fallback.
- **`EXPECTED_CORRELATIONS`**: correlaciones esperadas de cada activo con USD/CLP (ej. dxy +0.75, copper −0.70, wti +0.40, usdmxn +0.60, usdbrl +0.55, audusd −0.50, usdcnh +0.45, sp500 −0.30).
- **`SYMBOLS_GOLD`** / **`EXPECTED_CORRELATIONS_GOLD`** / **`ASSET_WEIGHTS_GOLD`**: configuración paralela para el panel de Oro (target `XAUUSD`), con activos dxy, silver (`XAGUSD`), vix (`VIX_Jun26`), eurusd, sp500, usdjpy (documentado como "proxy real-time de yields US10Y") y copper. El comentario indica que el peso de `usdjpy` se subió a 2.5 "absorbiendo el canal WTI eliminado", y el de `vix` se bajó a 1.0 por "correlación débil (+0.35)".
- **`SYMBOLS_NASDAQ`** / **`EXPECTED_CORRELATIONS_NASDAQ`** / **`ASSET_WEIGHTS_NASDAQ`**: configuración paralela para el panel NASDAQ100 (target `NQ100`), con activos sp500, vix, dxy, usdjpy, bitcoin (`BTCUSD`), wti, eurusd y gold. El peso de `wti` se documenta como bajado a 0.7 ("señal indirecta vía inflación, débil intraday").
- **`TIMEFRAMES`**: M1(1), M2(2), M5(5), M15(15) minutos. `BARS_TO_FETCH = 200`.
- **`RiskConfig`** (dataclass, instancia `RISK`): capital 1.500.000 CLP, riesgo por operación 1%, pérdida diaria máxima 3%, máximo 3 operaciones/día, ratio riesgo:beneficio mínimo 1.5, multiplicadores ATR para SL (2.0) y TP (3.0), pausa tras 2 pérdidas consecutivas durante 120 minutos.
- **`ScoreWeights`** (dataclass, instancia `WEIGHTS`): `technical=0.50`, `correlation=0.50` (nota: el README describe una fórmula 75%/25% que corresponde a una versión anterior; el valor efectivo en el código actual es 50/50, ver sección 12).
- **`SCORE_ALERT_THRESHOLD = 65`**, **`SCORE_STRONG_THRESHOLD = 75`**.
- **`IndicatorParams`** (dataclass, instancia `INDICATORS`): EMA 9/21/50/200, RSI período 14 (70/30 sobrecompra/sobreventa), MACD 12/26/9, Bandas de Bollinger período 20 desviación 2.0, ATR período 14.
- **`CORRELATION_WINDOW = 50`**, **`CORRELATION_BREAK_THRESHOLD = 0.3`**, **`DIVERGENCE_THRESHOLD = 0.02`** (2%).
- **Horario operativo** (CLT/UTC-4): apertura 09:30, cierre primario 14:00, cierre absoluto 15:30, buffer de noticias 30 minutos.
- **`DASHBOARD_REFRESH_SECONDS = 1.5`**, `DASHBOARD_LANGUAGE = "es"`.
- **Rutas**: `BASE_DIR`, `DATA_DIR`, `JOURNAL_PATH` (`data/trades_journal.csv`).

---

## 5. Fuente de datos (`data_feed.py`, 307 líneas)

Clase `DataFeed(mode="auto")`: capa unificada de acceso a datos de mercado, documentada explícitamente como de solo lectura.

- Al inicializarse, intenta `_try_connect_mt5()`: inicializa la librería `MetaTrader5`, valida `account_info()`/`terminal_info()`, puebla el mapeo de timeframes MT5 (M1 a D1) y llama a `_enable_symbols()` para asegurar que todos los símbolos usados por USD/CLP, Gold y NASDAQ estén visibles en el Market Watch del terminal.
- Si MT5 no está disponible, opera en modo `"yfinance"`.
- **`get_data(symbol, timeframe_minutes, bars)`**: devuelve un DataFrame OHLCV, con caché por símbolo/timeframe/cantidad de barras (TTL de 5s para MT5, 30s para Yahoo). Intenta MT5 primero (`_get_data_mt5`, vía `mt5.copy_rates_from_pos`), y si no hay datos cae a `_get_data_yfinance` (vía `yfinance`, mapeando símbolo→ticker Yahoo e intervalo/periodo apropiados).
- **`get_current_price(symbol)`**: bid/ask/spread en vivo desde `mt5.symbol_info_tick` si está conectado; si no, sintetiza un spread aproximado (0.1% del precio) a partir de la última vela de 5 minutos.
- **`get_symbol_info(symbol)`**, **`get_all_data(timeframe_minutes, bars)`** (trae datos de todos los símbolos de `config.SYMBOLS`), **`get_status()`** (modo, conexión, tamaño de caché, datos de cuenta si está conectado), **`shutdown()`**.

---

## 6. Indicadores técnicos (`indicators.py`, 127 líneas)

Funciones sobre un DataFrame OHLCV (usa la librería `ta`):

- **`calculate_all(df)`**: agrega columnas EMA (9/21/50/200), RSI(14), MACD (línea, señal, histograma), Bandas de Bollinger (superior/media/inferior/%B) y ATR(14); además columnas derivadas: `ema_trend_signal`, `ema_cross` (detección de cruce 9/21), `rsi_signal` (zonas de sobrecompra/sobreventa/momentum) y `macd_trade_signal` (signo del histograma). Requiere un mínimo de 50 filas.
- **`get_latest_signals(df)`**: extrae la última fila de indicadores calculados como un diccionario plano.

---

## 7. Score técnico multi-timeframe (`technical_scorer.py`, 198 líneas)

- **`calculate_technical_score(df, normalize_macd=False)`**: combina 5 sub-scores en un score 0-100 con pesos EMA 30%, RSI 20%, MACD 25%, BB 15%, PA 10%. La dirección se determina por la suma de votos (+1/0/−1) de cada indicador.
  - `_score_ema`: alineación de EMAs 9/21/50 (85 si alineación alcista completa, 15 si bajista completa, 65/35 para alineación parcial, 50 si entrelazadas; bonus ±15 en cruce 9/21).
  - `_score_rsi`: 30 si RSI≥70 (sobrecompra), 70 si RSI≤30 (sobreventa), escala lineal en zonas intermedias.
  - `_score_macd`: si se pasa ATR, normaliza el histograma por ATR (`50 + (h/ATR)×40`); si no, usa escala directa del histograma (`60 + |h|×1000` / `40 − |h|×1000`).
  - `_score_bb`: posición %B dentro de las bandas (25 en extremo superior >95%, 75 en extremo inferior <5%, 50 en el centro).
  - `_score_pa`: ratio cuerpo/rango de la última vela (70/30 para velas fuertes, 55/45 para velas moderadas).
- **`calculate_multi_tf_score(data_feed, symbol)`**: obtiene datos por timeframe (M1 40%/35%, M2 35%, M5 20%, M15 10%, según el punto de llamada — ver nota de pesos duplicados en la sección 15), computa `calculate_technical_score` por TF con normalización ATR del MACD activada para M1/M2, calcula el score compuesto ponderado, la dirección ancla de M15 (`h4_direction`, nombre de clave heredado), el `confluence` (máximo de TFs que coinciden en una misma dirección) y las divergencias RSI entre TFs.
- **`detect_rsi_divergences(tf_scores)`**: compara el RSI de TFs adyacentes (orden M1→M15); diferencias ≥10 puntos se clasifican por magnitud (LEVE ≥10, MODERADA ≥15, FUERTE ≥25) y generan una descripción textual con contexto de sobrecompra/sobreventa.

---

## 8. Motor de correlación cross-asset "legacy" (`correlation_engine.py`, 486 líneas)

Contiene dos capas independientes:

### 8.1 Funciones basadas en ventana rolling (H1, usadas por `SentinelCore`)

- **`calculate_correlation_matrix(all_data, window)`**: normaliza timestamps de cada instrumento (a UTC naive, redondeado a la hora, deduplicado), alinea cierres por *inner join*, calcula log-retornos y la matriz de correlación de Pearson sobre los últimos `window` periodos (por defecto `CORRELATION_WINDOW=50`).
- **`calculate_target_correlations(all_data, target_key)`**: para cada instrumento en `EXPECTED_CORRELATIONS`, registra la correlación real, la divergencia frente a la esperada, y marca una "ruptura" (`break`) si la correlación real cae por debajo de `CORRELATION_BREAK_THRESHOLD` mientras la esperada era fuerte (>0.4). Calcula `score` (vía `_calculate_correlation_score`) y `direction` (vía `_determine_correlation_direction`).
- **`_calculate_correlation_score`**: vota LONG/SHORT por instrumento según el signo de su retorno reciente (5 velas) combinado con el signo de la correlación esperada, pondera cada voto por un peso fijo por activo (dxy 3.0, copper 2.5, usdmxn/usdbrl 1.5, wti/audusd/usdcnh 1.0, sp500 0.5) y escala el consenso a `50 + |consenso|×50`.
- **`_determine_correlation_direction`**: lógica de votación equivalente pero con umbral de divergencia (`DIVERGENCE_THRESHOLD`) para decidir la dirección final LONG/SHORT/NEUTRAL.
- **`detect_divergence(all_data, target_key)`**: para cada instrumento, calcula el movimiento que "debería" tener USD/CLP según su retorno y el signo de correlación esperado; si el movimiento real de USD/CLP contradice esa expectativa por encima de `DIVERGENCE_THRESHOLD`, registra una divergencia con magnitud y descripción, ordenadas de mayor a menor.

### 8.2 `RealtimeCorrelationTracker` (clase, para uso tick-a-tick)

Tracker de confianza de correlación en tiempo real, calibrado para refrescos de 2.5s, con tres componentes:
- Correlación EWMA de doble lambda (varianza rápida `lambda_var=0.85`, covarianza lenta `lambda_cov=0.97`).
- Concordancia de signo entre retornos (ventana de 60 actualizaciones).
- Z-score de ruptura sobre el spread `ret_target − expected_sign×ret_asset` (ventana de 50, umbral de ruptura 2.0).

Métodos: `update(asset_key, ret_target, ret_asset, expected_sign)` (alimenta un tick), `get_confidence(asset_key)` (retorna confianza compuesta = 35% concordancia EWMA + 45% concordancia de signo + 20% penalización por ruptura, con bandera de calentamiento si hay menos de 30 actualizaciones), `get_all_confidence()`.

---

## 9. Motor macro EWMA (`macro_scorer.py`, 362 líneas)

Clase **`MacroScorer`**, motor de scoring por consenso ponderado de activos correlacionados, instanciable por instrumento (una instancia para USD/CLP con los pesos por defecto del módulo, e instancias adicionales para Gold y NASDAQ con `ASSET_WEIGHTS_GOLD`/`ASSET_WEIGHTS_NASDAQ`).

- **`update_tick(data_feed)`**: alimenta el tracker EWMA interno con el tick más reciente de cada activo correlacionado.
- **`calculate_score(data_feed)`**: calcula un score 0-100 y dirección a partir del consenso ponderado por confianza (EWMA) de todos los activos monitoreados; retorna también el detalle de votos por activo (`votes`), activos "calentados" (`assets_warmed_up`) y confianza promedio (`confidence_avg`).
- **`calculate_score_at_window(data_feed, lookback_bars=3)`**: variante del cálculo de score usando una ventana de barras históricas específica en lugar del estado tick-a-tick en vivo (usado para el detalle de votos/replay).
- **`calculate_fusion(tech_score, tech_direction, macro_score, macro_direction)`**: combina el score técnico y el macro en una señal de "fusión" con nivel de confluencia (`confluence_pct`), banderas `aligned`/`opposed`, un `risk_mode` (con emoji) y multiplicadores sugeridos de stop-loss/take-profit sobre ATR (`sl_multiplier`, `tp_multiplier`).

Este motor reemplaza, para el cálculo del score compuesto en `sentinel_core.py`, al score de correlación "legacy" descrito en la sección 8.1 (que se mantiene disponible bajo la clave `_correlation_legacy` del resultado).

---

## 10. Niveles de soporte/resistencia (`levels_engine.py`, 259 líneas)

- **`calculate_levels(data_feed, symbol)`**: función de entrada que obtiene velas diarias (10 barras), M15 (200 barras) y M5 (50 barras); determina el precio actual y combina pivots + swings.
- **`_calculate_camarilla(df_daily)`**: pivots Camarilla clásicos a partir de H/L/C del día anterior — `PP=(H+L+C)/3`, R1-R3 = `Close + Range×1.1/{12,6,4}`, S1-S3 = `Close − Range×1.1/{12,6,4}`.
- **`_detect_swing_levels(df, current_price, order=5)`**: usa `scipy.signal.argrelextrema` con ventana de 5 velas a cada lado sobre datos M15 para detectar máximos/mínimos locales (swing highs/lows), filtrando a niveles dentro de ±5% del precio actual.
- **`_combine_levels(pivot, swings, current_price)`**: fusiona niveles Camarilla y swings, deduplica los cercanos entre sí (<0.1%), selecciona los 3 más próximos por encima y por debajo del precio, y rellena con niveles sintéticos extrapolados si faltan.
- **`_interpret_position(combined, current_price, pivot)`**: genera una interpretación textual en español de la posición del precio respecto al pivot y a los máximos/mínimos del día anterior.

---

## 11. Orquestador central (`sentinel_core.py`, 102 líneas)

Clase **`SentinelCore(data_feed)`**, el "cerebro" que en cada refresco:
1. Calcula el score técnico multi-TF (`technical_scorer.calculate_multi_tf_score`).
2. Actualiza y calcula el score macro EWMA (`MacroScorer.update_tick` + `calculate_score`).
3. Calcula el score de correlación "legacy" y sus divergencias (`correlation_engine`), sobre datos H1 de 200 barras.
4. Calcula los niveles S/R (`levels_engine.calculate_levels`).
5. Combina técnico y macro en el **score compuesto** (`tech_score×WEIGHTS.technical + macro_score×WEIGHTS.correlation`, actualmente 50%/50% según `config.py`), clampado a [0,100].
6. Determina la **dirección de consenso** por voto ponderado (técnico peso 2, macro peso 3) entre LONG/SHORT/NEUTRAL.
7. Asigna la señal de semáforo (`FUERTE` ≥75, `ALERTA` ≥65, `ESPERAR` <65, según `SCORE_STRONG_THRESHOLD`/`SCORE_ALERT_THRESHOLD`).
8. Compila una lista de alertas (alerta de score, top-3 divergencias) y retorna un diccionario único con todos los componentes (`composite_score`, `direction`, `signal`, `components`, `levels`, `divergences`, `alerts`, `meta.timestamp`).

---

## 12. Dashboard v1 (`dashboard.py`, 1658 líneas)

Interfaz principal en Streamlit, servida en la ruta raíz vía `app.py`. Estructura por secciones (líneas aproximadas):

- **1–109**: configuración de página (`st.set_page_config`, con manejo de excepción si `app.py` ya la configuró) e inyección de CSS (paleta oscura, tooltips flotantes con hover, ocultamiento de la barra de herramientas de Streamlit, animación de transición entre refrescos).
- **111–124**: función auxiliar `tt()` para construir tooltips HTML; `init_system()` cacheado que crea `DataFeed` + `SentinelCore`.
- **126–140** (sidebar): título/versión, estado de conexión (MT5 en vivo vs Yahoo con delay), tamaño de caché, checkbox de auto-refresh, intervalo de refresco.
- **141–238**: cálculo del score compuesto (`core.calculate_composite()`); cálculo adicional de scores técnicos rápidos por activo cross-asset (para la tabla de correlaciones enriquecida) y de la correlación rolling "HOY" (Pearson de 30 barras M1, dirigida por el signo esperado, escalada a 0-100%); registro de precios tick a tick en `session_state` para flechas instantáneas.
- **239–274**: helpers de renderizado (`_bps_to_arrow`, `_slider_bar`) e inicialización de `MacroScorer` para la columna de votos macro del header.
- **Header de 5 columnas (líneas 278–948)**, en una sola fila:
  - **`col_score`**: panel de señales v1 (⚡5s / 🔄30s / 📊1m / 📈5m, blends ponderados de scores por TF), panel de señales v2 con derivadas de precio (velocidad y aceleración calculadas sobre un buffer de hasta 200 ticks de bid, con boost de hasta ±25 puntos por velocidad y ±10 por aceleración), barra de momentum, y el bloque final de Score + Dirección con semáforo.
  - **`col_levels`**: lista de resistencias (R1-R3) y soportes (S1-S3) con tooltips explicativos según la distancia al precio actual, y el precio en vivo (bid/ask/spread, fuente MT5/Yahoo).
  - **`col_tf`**: una tarjeta por timeframe activo (M1/M2/M5/M15) con score, dirección (COMPRAR/VENDER/ESPERAR), RSI, y tooltip con el detalle de los 5 sub-indicadores (barras deslizantes de EMA/RSI/MACD/BB/PA) más contexto de confirmación M15 y de activos cross-asset confiables.
  - **`col_corr`**: tabla de correlaciones cross-asset con 3 flechas de movimiento (tick, ~2min, ~5min), sparkline SVG en hover, columna "HOY" de confianza rolling M1, y clasificación ✅/⚠️/🔴 según la desviación de la correlación esperada.
  - **`col_macro`**: desglose de votos del `MacroScorer` por activo (retorno en bps, voto ponderado, confianza, bandera de calentamiento ⏳).
- **949–975**: sección de Alertas — divergencias RSI entre TFs, alertas generales del `SentinelCore`, divergencias cross-asset.
- **976–1068**: bloque marcado "EXPERIMENTAL v4.0 — Triple Signal System": tres tarjetas (Técnico/Macro/Fusión) usando `MacroScorer.calculate_fusion`, y un medidor de confluencia con multiplicadores de SL/TP sugeridos según el `risk_mode`.
- **1069–1253**: panel experimental adicional de 4 señales (5s/30s/1m/5m) sobre los mismos scores por TF.
- **1253–1317**: expander "Detalle de votos por activo" (desglose EWMA Confidence Weighted).
- **1317–1456**: expander de "Backtesting" — controles para configurar el periodo (barras M1, rango de días de trades) y disparar `backtester.replay_scoring`/`compare_with_trades`, con gráfico dual precio/score y tabla de resultados por trade.
- **1456–1645**: expander de "Asistente IA" — selector de modelo (Opus/Sonnet/Haiku), checkbox de Web Search, campo de API key si no está configurada, selector de "thinking effort" (deshabilitado si Web Search está activo), contenedor de chat con historial persistido, renderizado de citas de búsqueda web, contador de costo/tokens acumulado (`UsageTracker.get_summary()`), y guardado automático de la conversación tras cada respuesta (`ai_chat.save_conversation`).
- **1647–1658**: pie de página con versión/codename/hora/fuente de datos, y el bucle de refresco (`time.sleep(DASHBOARD_REFRESH_SECONDS)` + `st.rerun()` si `auto_refresh` está activo).

**Nota sobre la fórmula del score**: el README documenta una fórmula histórica `Score = TechScore×0.75 + CorrScore×0.25`; el código actual (`config.py` `ScoreWeights`, usado por `sentinel_core.py`) aplica `0.50/0.50` entre técnico y macro. El dashboard, en los mensajes de tooltip del bloque Score+Dirección, ya refleja la proporción 50/50 vigente en el código.

---

## 13. Dashboard v2 y paneles multi-instrumento (`dashboard_v2.py`, `instrument_panel.py`)

- **`dashboard_v2.py`** (820 líneas), servido en la ruta `/v2`: reproduce la estructura de v1 (header de score, señales, niveles, timeframes, tabla de correlaciones, votos macro) añadiendo el bloque "Triple Signal System" (Técnico/Macro/Fusión vía `MacroScorer.calculate_fusion`) de forma más integrada, y agrega, en la parte inferior del layout, dos paneles adicionales para instrumentos distintos de USD/CLP: **NASDAQ100** y **Gold (XAUUSD)**, cada uno renderizado mediante `instrument_panel.render_panel(...)`.
- **`instrument_panel.py`** (455 líneas): módulo con la función parametrizada `render_panel(feed, symbols_cfg, expected_corrs, asset_weights, panel_key, label, emoji)`, que reconstruye para el instrumento dado el mismo tipo de panel que usa USD/CLP (señales fusionadas, barra de momentum, tarjetas por timeframe, niveles S/R, tabla de votos macro), instanciando su propio `MacroScorer` identificado por `panel_key` en `session_state`.

---

## 14. Backtesting (`backtester.py`, 302 líneas)

- **`fetch_historical_trades(days_back=30)`**: obtiene el historial de operaciones reales del trader desde MT5 (`mt5.history_deals_get`), filtrado a símbolos que contienen "USDCLP" o "CLP".
- **`fetch_historical_candles(symbol, timeframe_minutes, bars=500)`**: helper que instancia un `DataFeed` y delega en `get_data`.
- **`replay_scoring(bars_back=500, progress_callback=None)`**: reproduce el sistema de scoring sobre velas M1 históricas. Para cada punto en el tiempo, calcula el score técnico por TF (pesos M15 10%/M5 20%/M2 35%/M1 35%), un score de correlación fijo obtenido una sola vez al inicio del replay (vía `CorrelationEngine.calculate()`), el score compuesto (`WEIGHTS.technical`/`WEIGHTS.correlation`), la dirección por voto ponderado, y las señales v1 blended (5s/30s/1m). Retorna un DataFrame con una fila por timestamp.
- **`compare_with_trades(replay_df, trades_df)`**: empareja entradas y salidas de operaciones reales (por `position_id`/`order`), localiza el score de SENTINEL vigente en el momento de cada entrada, y calcula métricas: porcentaje de acierto direccional (`accuracy_pct`), porcentaje de pérdidas que SENTINEL habría filtrado (`filter_rate_pct`), y el detalle fila por fila de cada operación con su comparación.

---

## 15. Asistente IA (`ai_chat.py`, 620 líneas)

- **`ModelConfig`** (dataclass) y diccionario **`MODELS`**: tres modelos configurados —
  - `opus`: `claude-opus-4-7`, thinking `xhigh`, hasta 16384 tokens de salida, $5/$25 por millón de tokens entrada/salida.
  - `sonnet`: `claude-sonnet-4-6`, thinking `high`, hasta 8192 tokens, $3/$15 por millón.
  - `haiku`: `claude-haiku-4-5-20250315`, sin thinking extendido, hasta 8192 tokens, $0.80/$4 por millón.
- **`WEB_SEARCH_TOOL`**: configuración de la herramienta de servidor `web_search_20250305` de Anthropic, limitada a un dominio permitido de fuentes financieras (Reuters, Bloomberg, Investing.com, ForexFactory, BancoCentral.cl, DailyFX, TradingView, CNBC, MarketWatch, FXStreet, Kitco, EconomíayNegocios.cl, DF.cl, Emol.com, Cooperativa.cl), máximo 5 búsquedas por consulta, geolocalizada a Santiago, Chile. Costo declarado: $10 por 1000 búsquedas.
- **`build_market_context(...)`**: construye el *system prompt* completo enviado al modelo en cada consulta, incluyendo precio bid/ask/spread, score compuesto y su fórmula, desglose por timeframe con sub-scores de cada indicador, señales v1, derivadas de precio (velocidad/aceleración/momentum), correlaciones cross-asset con estado OK/WARN/BREAK y confianza "HOY", movimiento reciente cross-asset en bps, niveles S/R con posición, divergencias RSI y cross-asset, y alertas activas. Incluye instrucciones de rol fijas: no recomendar "compra"/"venta" directamente, presentar escenarios con probabilidades, responder en español, ser conciso, advertir riesgos y divergencias.
- **Persistencia de historial**: `save_conversation`/`load_conversation`/`list_conversations` almacenan cada sesión como un archivo JSON en `sentinel/chat_history/` (excluido de git y preservado por el launcher entre actualizaciones).
- **`UsageTracker`** (dataclass): acumula tokens de entrada/salida, número de búsquedas web y costo estimado en USD por consulta, con un resumen formateado para la UI.
- **`SentinelAI`** (clase cliente): inicializa el cliente `anthropic.Anthropic` con la API key de la variable de entorno `ANTHROPIC_API_KEY` (o configurable en runtime desde la UI); si no hay API key, opera en "modo mock" devolviendo una respuesta de demostración. El método `chat(...)` arma la solicitud a la API — activando o bien la herramienta de búsqueda web, o bien el *thinking* extendido, nunca ambos simultáneamente (limitación de la API señalada explícitamente en el código) — extrae el contenido de la respuesta, las citas de fuentes web, y registra el uso/costo en el `UsageTracker`.

---

## 16. Utilidad de diagnóstico (`check_state.py`, 52 líneas)

Script standalone (no parte de la app Streamlit) que instancia `DataFeed` + `SentinelCore`, ejecuta `calculate_composite()` una vez, e imprime por consola un resumen de precio, score compuesto, detalle por timeframe, correlaciones (real vs. esperada, con clasificación OK/WARN/BREAK), niveles S/R y las primeras 5 alertas activas. Sirve como verificación rápida del pipeline completo sin levantar el dashboard.

---

## 17. Versión (`version.py`)

Dos constantes: `VERSION = "3.7.1"`, `CODENAME = "AI Advisor"`.

---

## 18. Estructura de archivos del repositorio y entornos auxiliares

- **`sentinel/`**: todo el código Python descrito arriba, más `chat_history/` (historial de conversaciones IA, no versionado) y `__pycache__/`.
- **`data/`**: destino de `JOURNAL_PATH` (`trades_journal.csv`), usado por el backtester para comparar contra operaciones reales.
- **`MT5_Portable/`**: instalación portable de MetaTrader 5 (terminal, perfiles, configuración, logs).
- **`MT5_Tester/`, `MT5_Tester_2/`**: instancias adicionales de MT5 (con `MetaEditor64.exe` y capturas de pantalla de pruebas, ej. `SMOKE_T10_magic-holding.png`), aparentemente usadas para pruebas/tester headless.
- **`_python/`**: directorio de instalación del Python portable embebido descargado por `launcher.py` cuando el Python del sistema no es compatible.
- **`temp/`**: contiene logs de ejecución del launcher en distintos sistemas (`sentinel_win10_log.txt`, `sentinel_win11_log.txt`).
- **`CUENTAS.md`** (no versionado en git): registro de las dos cuentas MT5 utilizadas — una cuenta DEMO (única donde se permite operar) y una cuenta REAL de solo lectura vía contraseña de inversor — junto con las reglas operativas del proyecto (verificación de modo demo antes de cualquier orden, prohibición de lanzar terminales MT5 desde scripts, protocolo de nombres de los `.bat` de lanzamiento de cada terminal).
- **`MT5_DEMO_TOMAS.bat`, `MT5_REAL_PAPA_SOLO_LECTURA.bat`** (no versionados): lanzadores manuales de cada instancia de MT5 (demo y real de solo lectura respectivamente), según lo documentado en `CUENTAS.md`.
- **`SENTINEL.bat`**: lanzador de un clic del dashboard (raíz del repositorio).
- **`README.md`**: documentación de arquitectura y fórmulas de scoring; describe la estructura de módulos y la fórmula de composición de una versión anterior del sistema (no incluye `app.py`, `dashboard_v2.py`, `macro_scorer.py` ni `instrument_panel.py`, y documenta el score compuesto como 75%/25% técnico/correlación en vez del 50%/50% vigente en `config.py`).

---

## 19. Estado del control de versiones al momento de este informe

- Rama activa: `release`. Historial reciente (5 commits más recientes): ajustes de pesos de correlación para el panel de Gold y NASDAQ (`6ee5310`), incorporación del dashboard multi-activo con paneles NASDAQ+Gold (`d1bf9cc`), corrección de dependencia faltante de `yfinance` y relanzamiento autocurativo del launcher (`5e8ab4f`), mejoras de robustez SSL/timeout/copiado recursivo del launcher (`68929e3`), introducción del enrutador `app.py` (`e56cea8`).
- El árbol de trabajo actual tiene diferencias reportadas por `git diff` en prácticamente todos los archivos `.py` del proyecto, con un número de líneas insertadas igual al de líneas eliminadas en cada archivo. La inspección de `config.py` confirma que el contenido del working tree usa terminadores de línea CRLF, mientras que la versión almacenada en el commit usa LF — es decir, el diff reportado corresponde a una conversión de terminadores de línea, no a cambios de contenido.
- Existen varios archivos y directorios no rastreados por git en el momento de este informe: `CUENTAS.md`, `MT5_DEMO_TOMAS.bat`, `MT5_REAL_PAPA_SOLO_LECTURA.bat`, `MT5_Tester/`, `MT5_Tester_2/`, `temp/`.

---

*Fin del informe. Generado por inspección directa de todos los módulos Python del proyecto (`sentinel/*.py`), `README.md`, `config.py`, el historial de git y el estado del árbol de trabajo.*
