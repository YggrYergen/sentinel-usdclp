# Inventario de transcripciones YouTube — Grupo A (T0.11b)

> Ejecutado bajo decisión D-49 (2026-08-15): pasada única, sin conteo de tokens, sin
> estimación de costo, sin model-routing. Un video = un contexto de análisis, procesados
> estrictamente uno por uno, entrada escrita y persistida antes de abrir el siguiente.
> Objetivo rector: qué sirve para que S6 y SuperTrend (trend/breakout M15, XAUUSD) ganen
> más y pierdan menos — debilidades conocidas: gestión de salida/trailing y regímenes
> de rango. Corpus: 14 archivos en `data/literature/youtube_transcripts/`.

---

## 1. znSRU984kc8

- **Título (inferido):** Podcast "Words of Wisdom" con Andrea Timi — orden de flujo, mentalidad
  profesional, y por qué la mayoría de retail (incl. ICT/SMC) no gana.
- **URL:** https://www.youtube.com/watch?v=znSRU984kc8
- **Duración/extensión:** transcripción muy larga, ~3.790 líneas (el archivo más grande del grupo).
- **Qué cubre realmente:** entrevista/podcast de mentalidad y crítica a la industria, NO un video de
  estrategia. Argumenta que el trading discrecional de patrones de velas tiene baja tasa de éxito
  frente al trading profesional (order flow, macro global, algorítmico); ataca el "culto ICT/SMC"
  con el argumento de sesgo de supervivencia (analogía de los aviones de la WWII) y sesgo de
  popularidad; crítica extensa a las prop firms (trailing drawdowns, conflicto de interés,
  resultados no replicables en cuenta real); consejos de gestión de vida financiera (ahorro antes
  que especulación, no tradear sin colchón financiero). Fuerte carga publicitaria: 3 cortes de
  sponsor (Chart Academy, Alpha Futures, TradeZella/Market Journal) y venta indirecta de su propia
  plataforma de "order flow bubbles".
- **Reglas/parámetros específicos y testeables:**
  - Menciona **opening range breakout (ORB)** y **gap fill** como los dos patrones "simples y
    validados" que recomienda como punto de partida (atribuye el ORB a Toby Crabel, años 90, sobre
    S&P500/Nasdaq). No da ventana de apertura, umbral de rango ni distancia de stop — solo el
    concepto y una afirmación de que "supera al S&P500 en Sharpe" (sin cifras, sin fuente
    verificable).
    Cita literal: *"a very simple rule-based stupidly pattern like the opening range breakout or
    the gap fill... start from a simple strategy that you know works."*
  - Filtro cualitativo de volumen/order-flow sobre el ORB: exige operaciones grandes (da un umbral
    ilustrativo de "**at least 150 contracts**" en futuros) como confirmación de que el breakout va
    a sostenerse — sin backtest mostrado, sin regla de traducción a forex/oro.
  - Manejo de trade real que cuenta el propio entrevistado: movió el stop a **break-even** en un
    setup ORB ganador y fue barrido justo antes del gran movimiento (anécdota, no regla — de hecho
    la usa como ejemplo de gestión imperfecta, no de método a replicar).
- **Relevancia a S6/SuperTrend:** LOW. El ORB y el filtro de order-flow tocan tangencialmente el
  problema de "cuándo confiar en un breakout", pero el video nunca aterriza en parámetros
  implementables, no menciona oro ni M15, y el filtro de volumen de futuros (contratos) no tiene
  traducción directa a spread/tick de FX/XAU. Es contenido de mentalidad/marketing, no de mecánica.
- **Red flags:** fuerte carga de venta (3 sponsors + producto propio de "bubbles"/order flow);
  afirmación de rendimiento no verificable ("ha superado al S&P 500 en Sharpe... lo hemos
  investigado cuantitativamente") sin mostrar ni un número, ni una curva, ni una fuente; anécdotas
  personales de PnL ($15k día bueno, $10k pérdida) sin contexto de cuenta ni tamaño de posición;
  gran parte del video es autopromoción de la plataforma del entrevistado.

## 2. oDK0hbAMWbU

- **Título (inferido):** "$50 → $21,873 en 10 trades" — progresión de escalado de tamaño operando
  reversiones en soporte/resistencia con futuros micro (NASDAQ, ES, oro).
- **URL:** https://www.youtube.com/watch?v=oDK0hbAMWbU
- **Duración/extensión:** transcripción larga, 1.568 líneas; recorre ~9-10 trades reales con
  screen-recording narrado.
- **Qué cubre realmente:** estrategia discrecional de **reversión en zonas de soporte/resistencia**
  (NO estrategia de continuación/breakout) en futuros de índices (micro NASDAQ, ES) y futuros de oro
  (micro gold), operando principalmente en 1 minuto con contexto de 15 minutos, escalando el tamaño
  de posición ($50 de riesgo inicial hasta $1.500) a medida que gana confianza. Explica un checklist
  de reversión y cómo gestiona el trade (mover a break-even, trailing de stop bajo swings,
  scale-out parcial). El ejemplo de oro (líneas 820-904) es el más directamente relevante del grupo
  A hasta ahora.
- **Reglas/parámetros específicos y testeables:**
  - **Contexto diario:** cada mañana traza soporte/resistencia en gráfico de **15 minutos** desde
    swings clave; luego baja a 1 minuto para gestionar la entrada.
  - **Checklist de entrada en reversión (los 4 elementos deben alinearse):**
    1. Ruptura de la tendencia previa (rotura de una trendline de 1 min hacia el nivel).
    2. Movimiento fuerte y rápido hacia el nivel ("unhealthy move": p. ej. 3 velas grandes bajando
       en ~15 minutos) — cuanto más "insano"/parabólico el movimiento de entrada al nivel, mayor
       probabilidad de reversión rápida.
    3. Patrón de velas de reversión (head-and-shoulders o doble suelo/techo) confirmándose en el
       nivel de S/R.
    4. **Ventana horaria**: reversiones tienden a ocurrir **15 y 30 minutos después de la apertura**
       del mercado (7:30/9:30 hora local del trader); trata esas ventanas como zonas temporales de
       mayor probabilidad, no como gatillo exacto.
    Entrada: stop-order de ruptura de la vela de reversión (no entra en el mínimo/máximo exacto,
    espera confirmación de "fuerza" rompiendo el swing).
  - **Stop:** debajo/encima del mínimo/máximo de la vela grande de reversión, o del swing que
    confirma la reversión — nunca un ATR ni distancia fija; el criterio es estructural (bajo el
    swing relevante).
  - **Gestión de salida (regla explícita, repetida en cada trade):**
    - Mover el stop a **break-even cuando el precio avanza ~1x a 1.5x el riesgo inicial** ("depende
      del mercado, mejora con experiencia").
    - Objetivo simple sugerido para quien quiera reglas fijas: **relación riesgo:beneficio 2:1**,
      con stop fijo y mover a break-even al acercarse — declarado explícitamente como alternativa
      "sin pensar tanto" a su gestión más discrecional.
    - Su propia gestión real: deja correr hasta 2-3x el riesgo con trailing bajo swings sucesivos;
      hace **scale-out parcial** (ej. cierra 2 de 3 contratos en un salto fuerte, deja correr el
      resto) cuando el movimiento es "demasiado" rápido/grande en relación al tamaño operado.
    - Objetivo inicial de referencia declarado en varios trades: **retorno al precio de apertura
      del mercado** (mean-reversion hacia el open) como primer target táctico, con niveles de
      resistencia/soporte superiores como extensiones.
    - Filtro anti-lateral: evita entrar durante rangos claramente "choppy" (dice explícitamente que
      un rango lateral puede durar más de lo esperado y da señales falsas/trampas).
  - **Calendario de noticias:** revisa Forex Factory cada mañana, filtra a EE.UU., presta atención
    especial a impacto medio/alto cerca de sus ventanas de 15/30 min, y a veces coloca limit orders
    anticipando el spike de una noticia.
  - **Ejemplo de oro (líneas 820-904):** mismo checklist pero en 5 minutos en vez de 1 minuto (más
    lento, dice que tarda 45min-1h en desarrollarse un movimiento equivalente); mismo manejo de
    stop a break-even tras impulso, salida cuando revierte el pullback en vez de sostener target
    fijo.
- **Relevancia a S6/SuperTrend:** MEDIUM. Es una estrategia de **reversión en rango**, no de
  tendencia/breakout — la mecánica de entrada (contra-tendencia en S/R) no es transplantable
  directamente a S6/ST, que son trend-following. Pero el bloque de **gestión de salida** es
  relevante y testeable: regla de break-even a 1-1.5R, trailing estructural bajo swings, R:R base
  2:1 con opción de dejar correr por señal en vez de target fijo, y filtro explícito de "no entrar
  en rango lateral / choppy". El concepto de ventana horaria de reversión (15/30 min post-apertura)
  también es una idea de timing operacionalizable y testeable en M15 XAUUSD si se traduce a la
  apertura de la sesión relevante (Londres/NY). Sin evidencia cuantitativa de que estas reglas
  generalicen fuera de futuros de índice.
- **Red flags:** la narrativa es "$50 → $21.873 en 10 trades" pero la mayoría de trades mostrados
  ya usan tamaño creciente ($100-$1.500 de riesgo) — la progresión geométrica de tamaño infla el
  resultado headline más que el "edge" en sí; no hay conteo de trades perdedores mostrado (solo se
  narran ganadores, sesgo de selección clásico); ningún backtest ni estadística de tasa de acierto;
  "hindsight" explícito reconocido por el propio autor en al menos un trade ("that's hindsight
  talking"); producto vinculado (plataforma Ninja Trader, PDF de venta/lead-magnet).

## 3. xGIa8Vg0PWM

- **Título (inferido):** "How to Day Trade" — Ross Cameron (Warrior Trading), clase de "momentum
  day trading" sobre acciones de bajo float; recap de un reto de cuenta pequeña $2.000→$65.000 en
  30 días.
- **URL:** https://www.youtube.com/watch?v=xGIa8Vg0PWM
- **Duración/extensión:** transcripción larga, 1.221 líneas.
- **Qué cubre realmente:** metodología completa de day trading intradía en acciones de bajo float
  (penny/small-cap, timeframe de 1 minuto), NO forex ni oro. Cinco pasos: (1) selección de acción
  por "5 pilares" (volumen relativo, volumen total, gap %, precio, float); (2) patrón de entrada
  "first pullback" con reglas de velas; (3) ejecución con datos Level 2 (order book de acciones,
  no existe en FX retail); (4) indicadores de salida discrecionales; (5) registro/journaling de
  métricas. Fuerte marketing de su plataforma "Day Trade Dash" y del reto benéfico.
- **Reglas/parámetros específicos y testeables:**
  - **Selección de instrumento (5 pilares):** volumen relativo ≥5x el promedio de 50 días (ideal
    entre 5x-10x, "sweet spot"); volumen total alto (ejemplo: prefiere >1M acciones); gap de
    apertura ≥2% vs cierre previo; precio entre $2 y $20; float <20M acciones (mejor cuanto menor).
    Requiere cumplir "al menos 4 de 5" pilares.
  - **Patrón de entrada "first pullback":** tras un impulso alcista, esperar un retroceso que (a)
    **no retraceda más del 50%** del movimiento inicial; (b) tenga **volumen mayor en velas verdes
    que en rojas**; (c) **no rompa el VWAP**; (d) **no rompa la EMA de 9** (llamada también "90 EMA"
    en el audio, probablemente error de transcripción de "9 EMA"); evitar "topping tails" (mechas
    superiores) en el pullback. Entrada = la primera vela que hace un nuevo máximo sobre la vela
    previa ("crossing candle").
  - **Stop/riesgo:** stop = mínimo del pullback (no un ATR ni distancia fija). Ejemplo concreto del
    propio trade: entrada $7.60, stop $7.45 (15 centavos de riesgo), tamaño 5.000 acciones ($750 de
    riesgo), objetivo optimista $8.50 (90 centavos, ~R:R 6:1). Regla general: apunta a **mínimo
    2:1 profit/loss** (con eso el breakeven matemático baja a 33% de aciertos).
  - **Salida (discrecional, 6 señales):** gran orden de venta visible en Level 2; "vendedor oculto"
    (iceberg absorbiendo compras sin que suba el precio); ráfaga fuerte de ventas en el time & sales;
    reversión brusca formando vela de mecha superior ("topping tail"); desaceleración de la compra;
    formación de vela roja/topping tail. No fija objetivo de profit — deja correr hasta que aparezca
    una señal de salida.
  - **Reglas de "cuándo parar de operar" (day-level circuit breakers):** (a) parar si se pierde el
    **50% de la ganancia del día**; (b) pérdida máxima diaria = **ganancia diaria promedio** (en su
    caso ~$10-20k, la cifra es específica de su cuenta, no un ratio transferible); (c) parar si la
    "ventana horaria" donde suele rendir bien ya pasó (para él, corte duro a las 10:00 a.m. hora de
    mercado EEUU); (d) parar si ya no hay candidatos que cumplan los 5 pilares; (e) parar si el
    sesgo del día es claramente bajista/con muchos falsos breakouts. Regla dura declarada: "no
    volver a mirar después de haberse ido" (evitar FOMO de reentrada).
- **Relevancia a S6/SuperTrend:** LOW. El mercado (acciones de bajo float, datos Level 2, velas de
  1 minuto) y el objetivo (explotar desequilibrios de oferta/demanda extremos en un solo día) no
  tienen equivalente estructural en FX/XAU M15 — no hay float, no hay Level 2 público en XAUUSD, y
  el edge depende de catalizadores de noticias en acciones individuales. El único elemento
  potencialmente portable es genérico y ya conocido: (a) el principio de "no capar ganadores, salir
  por señal de reversión en vez de por objetivo fijo" es filosóficamente relevante a la debilidad de
  gestión de salida de S6/ST, pero las señales concretas (Level 2, tape) no existen en nuestro
  instrumento; (b) el criterio de "circuit breaker" diario (parar tras perder 50% de la ganancia,
  o tras una ventana horaria de bajo rendimiento) es una idea de gestión de sesión trasladable en
  principio, pero sin ninguna especificidad de gold/M15.
- **Red flags:** cifras de resultado no auditables de forma independiente por el espectador (solo
  se muestran capturas de su propio software); resultado "típico" explícitamente negado por el
  propio presentador ("no asuman que mis resultados son típicos") pero igual usado como gancho de
  título; superviviencia implícita (18+ años de trading, primer millón recién en 2019, se omite el
  período de pérdidas); fuerte impulso de venta cruzada (curso, software, broadcast en vivo).

