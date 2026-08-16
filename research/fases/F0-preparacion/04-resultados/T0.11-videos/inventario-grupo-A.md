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

## 11. nkMzaQqpFbw

- **Título (inferido):** Estrategia de "supply and demand" en 3 pasos + "6 claves" para zonas
  válidas; aplicable a forex/cripto/futuros/oro; incluye 3 recreaciones de trades y una trade en
  vivo con opening range breakout como filtro adicional.
- **URL:** https://www.youtube.com/watch?v=nkMzaQqpFbw
- **Duración/extensión:** 458 líneas, transcripción media, muy alta densidad de reglas mecánicas
  explícitas (posiblemente el video más operacionalizable del grupo A).
- **Qué cubre realmente:** metodología discrecional pero muy bien especificada de "supply and
  demand" (zonas de oferta/demanda institucionales) con reglas de construcción de zona, filtro de
  tendencia, condiciones de entrada, y — en la parte final — combina la estrategia con un **opening
  range breakout de 3 velas de 5 minutos** y un **indicador de trailing stop** para gestión de
  salida. Declara aplicabilidad explícita a oro. Presenta un backtest propio (121 trades, 79% win
  rate, +2.100% P&L, sin metodología mostrada) y 4 trades narrados (3 recreados + 1 en vivo).
- **Reglas/parámetros específicos y testeables:**
  - **Paso 1 — Construcción de zona de demanda/oferta institucional:** requiere un movimiento
    impulsivo de ≥3-4 velas grandes consecutivas en la misma dirección (ejemplo: "más de 60 pips",
    sin definir umbral universal). La zona se dibuja sobre el **cuerpo** de la última vela antes del
    impulso (no la mecha) si la vela es grande; si la vela es pequeña usa **mecha a mecha**; si hay
    varias velas pequeñas, las agrupa. Exige un **fair value gap** (gap de no-solapamiento entre
    velas) como confirmación de momentum/desequilibrio.
  - **Paso 2 — Confirmación de tendencia (3 métodos alternativos, cualquiera sirve):**
    (a) estructura de swings + rupturas de estructura (break of structure); (b) precio por encima/
    debajo de una **EMA** con separación clara (si el precio solo cruza la EMA sin separación,
    descarta el trade); (c) repetir el análisis de estructura en un timeframe superior (ej. H1→H4).
  - **Paso 3 — Condiciones de entrada (checklist estricto):**
    1. **Momentum lento de aproximación a la zona** (velas mixtas, no una sola vela grande) —
       rechaza explícitamente zonas alcanzadas por una única vela grande de impulso.
    2. La vela debe **cerrar dentro de la zona o mecharla, nunca cerrar por debajo/encima** — un
       cierre fuera de la zona invalida el setup.
    3. Entrada en la primera vela de reacción positiva tras el toque de zona.
    4. **Stop loss:** ajustado al borde de la zona, o más allá de la mecha más cercana (a menudo
       coincidiendo con el nivel de la EMA).
    5. **Take profit:** por defecto sugiere 1:1 pero él usa 1:1.5 o 1:1.83 apuntando a niveles de
       precio reciente (no ATR ni R fijo rígido).
  - **"6 claves" adicionales de validez de zona (filtros de calidad, cada uno testeable):**
    (1) **zona no usada previamente** (fresh, no tocada) — zonas ya "gastadas" no sostienen precio;
    (2) cierre-o-mecha dentro de zona (repite regla del paso 3.2); (3) **stack de confluencias**
    (nivel usado antes como soporte/resistencia opuesto = mayor probabilidad); (4) **"la demanda más
    baja es la más fuerte"** — de varias zonas apiladas, preferir la más reciente/más baja en un
    tramo alcista; (5) **descuento de Fibonacci**: la entrada debe estar **por debajo del 50%** del
    retroceso fibonacci del swing (regla de "comprar barato dentro del rango"); (6) exigir **break
    of structure confirmado** en la zona — su ausencia predice que la zona no sostendrá precio
    (ejemplo mostrado explícitamente de zona sin BOS que efectivamente falla).
  - **Gestión de salida alternativa con trailing stop (trade en vivo, M5):** usa un indicador de
    trailing stop configurado en **timeframe de 5 minutos**, no cierra hasta que una vela **cierra**
    por debajo de la línea de trailing (no solo mecha) — deja correr la ganancia de $474 hasta
    $1.428 en el ejemplo mostrado.
  - **Filtro adicional — Opening Range Breakout:** usa las **primeras 3 velas de 5 minutos** del
    día (desde 9:30am ET) para definir un rango; solo confirma dirección cuando el precio rompe y
    **cierra** fuera del rango (arriba o abajo), y luego espera el retroceso a la zona de demanda/
    oferta ya marcada antes de entrar — combina ORB (dirección/filtro de sesgo del día) con S/D
    (punto de entrada de precisión).
- **Relevancia a S6/SuperTrend:** HIGH. Aporta el conjunto más grande de reglas de filtro de calidad
  de zona/señal directamente testeables como grid para reducir falsas señales de entrada en S6/ST:
  "zona fresca vs. usada", "descuento Fibonacci <50%", "confluencia con nivel S/R histórico",
  "confirmación de break of structure", y "momentum de aproximación lento vs. impulsivo" son todos
  filtros binarios computables sobre una serie de precios sin ambigüedad excesiva. La combinación
  ORB (3 velas M5) + zona de reacción es directamente análoga a un filtro de sesgo diario que podría
  aplicarse antes de las señales M15 de S6/ST. La regla de trailing-stop-por-cierre-de-vela (no por
  mecha) en el timeframe de ejecución es una alternativa de gestión de salida trasladable y
  fácilmente implementable (equivalente a un SuperTrend con confirmación de cierre). Limitación: no
  hay un ATR ni volatilidad explícita en la definición de zona/stop, y varios umbrales ("60 pips",
  "más o menos 3-4 velas") son ilustrativos, no reglas universales — requerirían calibración propia
  para XAUUSD M15.
- **Red flags:** backtest propio citado (121 trades, 79% win rate, +2.100% P&L) sin mostrar
  metodología, rango de fechas, ni costos de transacción — no verificable ni reproducible desde el
  video; los 3 "trades recreados" se presentan reproduciendo el chart histórico conociendo ya el
  resultado (riesgo de selección/hindsight, aunque el autor incluye honestamente 1 de 4 trades como
  perdedor); fuerte venta cruzada (bróker afiliado "TripleA AFX", sala VIP de pago, sala gratuita
  como funnel); la elección de qué zonas "sí cuentan" entre las docenas visibles en cualquier chart
  sigue siendo discrecional pese a presentarse como sistemática.

## 10. uGMen58jwxE

- **Título (inferido):** "Haddy" — episodio 1 de una serie de recap semanal de trading discrecional
  en una cuenta de $100k (US30 principalmente, una mención de oro), objetivo declarado "$100k a
  $100 millones".
- **URL:** https://www.youtube.com/watch?v=uGMen58jwxE
- **Duración/extensión:** 616 líneas, transcripción media, en formato de vlog/diario semanal, no
  de tutorial de estrategia.
- **Qué cubre realmente:** recap narrativo de la semana de trading del autor: 29 trades, 27
  ganadores, 2 perdedores (93% win rate declarado), +55% de la cuenta en una semana. Repasa
  discrecionalmente algunos trades (incluyendo uno en oro y varios en US30), su entrada ("point of
  interest", "internal change of character", timeframe de 5 minutos), y se enfoca casi
  exclusivamente en la lección de gestión emocional/paciencia: haber cerrado posiciones demasiado
  pronto le habría costado ganar $100-150k en vez de $55k esa semana. No es un tutorial de mecánica
  replicable; es contenido de mindset y diario personal.
- **Reglas/parámetros específicos y testeables:**
  - Referencias vagas a conceptos de estructura (estilo ICT): "point of interest", "internal
    change of character", "rejection" en niveles clave, en gráfico de **5 minutos** con contexto de
    timeframe superior para targets — sin especificar reglas mecánicas de construcción (a diferencia
    de los videos 5 y 7 del grupo, aquí no se define swing/estructura con precisión).
  - **Gestión de riesgo declarada:** mueve el stop a break-even (o ligeramente por encima) tan
    pronto como es posible tras entrar en ganancia ("tomar el riesgo de la mesa lo antes posible") —
    identifica esto como la causa de varias de sus "pérdidas pequeñas" (trades que llegaron a
    break-even y luego revirtieron).
  - Toma múltiples posiciones simultáneas al construir una cuenta pequeña, explícitamente para
    generar un "colchón de ganancia" psicológico.
  - No hay stop/entry/exit cuantificado en pips, ATR, ni R múltiplo consistente; los ejemplos de
    R:R mencionados son post-hoc ("esa pérdida de $500 podría haber sido una ganancia de $25.000 si
    hubiera aguantado" — hindsight, no regla).
- **Relevancia a S6/SuperTrend:** LOW. No aporta ninguna regla mecánica, parámetro numérico ni
  filtro de régimen implementable. El único tema tangencialmente relevante es la lección de
  "salir demasiado pronto / mover a break-even demasiado agresivo cuesta ganancias" — que apunta en
  la misma dirección que la debilidad de gestión de salida de S6/ST, pero sin ninguna regla
  operacionalizable (es una reflexión post-hoc sobre 2 trades específicos, no un patrón
  sistemático).
- **Red flags:** win rate de 93% sobre solo 29 trades (muestra pequeña, alta varianza, no
  estadísticamente significativo); afirmación repetida de "sabía hacia dónde iba a ir el precio"
  presentada como habilidad predictiva, clásico sesgo de hindsight/confirmación; ninguna evidencia
  auditada de resultados más allá de capturas de pantalla de su propia plataforma; formato de vlog
  orientado a construir marca personal/seguidores más que a enseñar método; el propio video es
  "episodio 1" de una serie promocional de una cuenta de $100k → $100M sin submitir a validación
  externa.

## 9. KML09tRtHM8

- **Título (inferido):** "Brendan" (mismo autor del video 8) — 25.000 backtests con Claude del
  "ICT Silver Bullet" sobre 16 años de datos de futuros NQ/ES en 1 minuto, con holdout de 2 años,
  para determinar qué reglas ICT concretas aportan edge real.
- **URL:** https://www.youtube.com/watch?v=KML09tRtHM8
- **Duración/extensión:** 555 líneas, transcripción media, extremadamente denso en metodología y
  resultados cuantitativos citados con precisión.
- **Qué cubre realmente:** el video cuantitativamente más riguroso del grupo A hasta ahora. Testea
  el setup ICT "Silver Bullet" (barrido de liquidez → desplazamiento → fair value gap → entrada en
  el retroceso al FVG → objetivo en la liquidez opuesta, restringido a 3 ventanas horarias
  específicas) descomponiendo cada regla discrecional en un "dial" parametrizable, muestrea 25.000
  configuraciones de un espacio de ~258 millones de combinaciones posibles, aplica walk-forward,
  filtro de Sharpe, filtro de drawdown, corrección por múltiples comparaciones ("luck correction"),
  validación cruzada en ES sin retuning, y finalmente un **holdout de 2 años nunca tocado** evaluado
  una sola vez. Metodológicamente es un espejo casi exacto de las prácticas de este programa (walk-
  forward, holdout sagrado, corrección por comparaciones múltiples, out-of-sample).
  - **No cubre forex ni oro** (lo declara explícitamente como fuera de alcance) ni timeframe M15 —
    todo en 1 minuto/5 minutos sobre futuros de índice (NQ/ES).
- **Reglas/parámetros específicos y testeables:**
  - **Definición completa del setup Silver Bullet:** (1) nivel de liquidez (swing obvio con stops
    acumulados) → (2) barrido (mecha que toma el nivel) → (3) desplazamiento (movimiento fuerte en
    dirección opuesta) → (4) fair value gap (zona de velas no solapadas dejada por el
    desplazamiento) → (5) entrada en el retroceso al FVG → (6) objetivo = liquidez del lado
    contrario. Ventanas horarias "signature": **3-4am y 10-11am hora Londres; 2-3pm hora NY**.
  - **Resultado del embudo de validación:** de 25.000 configuraciones, solo 9.481 producen ≥100
    trades (mínimo evaluable); 6.190 son rentables tras costos; 2.191 superan el umbral risk-
    adjusted; 1.614 sobreviven la corrección por suerte; **solo 420 (1.7%) sobreviven la validación
    cruzada en ES**.
  - **Win rate real vs. reclamado:** el marketing de ICT cita 70-80% de win rate; las mejores
    configuraciones reales rondan **34-48%** (supervivientes ~52% en promedio). Solo 5 de 25.000
    configuraciones alcanzaron 70%, todas mediante toma de profit rápida ~20 veces al año (no
    escalable como "ingreso diario").
  - **Hallazgo regla por regla (el resultado más accionable del video):** partiendo solo de "entrar
    en el FVG" (score 0.33), **añadir la exigencia de barrido de liquidez es la ÚNICA regla que
    mejora el resultado** (score sube a 0.69). Todo lo demás lo empeora: exigir desplazamiento
    (baja el score), restringir a las 3 ventanas horarias "especiales" (baja el score — se probó
    explícitamente cada hora del día y las horas ICT "famosas" quedaron **en medio de la
    distribución**, la ventana de las 10am incluso salió ligeramente negativa), y sobre todo
    **añadir el sesgo direccional de estructura M15 hunde el score a 0.16** (peor regla de todas).
    La versión que sobrevive todo el embudo es la más simple: sin sesgo direccional, sin restricción
    horaria, solo barrido + FVG de 1 minuto, operado con alta frecuencia (~1.996 veces/año en la
    versión "as traded" que la mayoría de traders ICT usan de facto).
  - **Discreción necesaria para "salvar" la versión textbook:** habría que saltarse correctamente
    por adelantado el **17.2%** de los trades perdedores para convertir la versión de libro en una
    estrategia sólida — algo no demostrable por backtest y que el autor señala como el mito de
    "solo necesitas experiencia de pantalla".
  - **Resultado en holdout (2 años nunca tocados, evaluados una sola vez):** la mejor configuración
    hizo $455k en un solo contrato (Sharpe 13, 24/24 meses positivos) — pero con el caveat explícito
    de que esos 2 años fueron un mercado fuertemente alcista, tratarlo como techo no como
    expectativa, y que los fills asumidos son óptimos (en la realidad se pierden más perdedoras de
    las que se llenan ganadoras por delante en la cola de órdenes).
  - **Conclusión explícita del autor:** "barrido + rebote" en 1 minuto es esencialmente
    **mean-reversion con vocabulario ICT distinto** — conecta directamente con el hallazgo del
    video 8 del mismo autor.
- **Relevancia a S6/SuperTrend:** HIGH (como evidencia metodológica y como advertencia, no como
  regla de grid directa). Aporta un contraste directo y con datos contra el video 7 (lYmmBoYQvWM) y
  el video 5 (en8RMFRqSME) de este mismo grupo A, que sí dependen de sesgo direccional M15/H1 y de
  ventanas horarias de sesión como reglas centrales — este video muestra evidencia cuantitativa
  (aunque en otro instrumento/timeframe) de que exactamente ese tipo de filtro (sesgo direccional
  de timeframe superior, restricción a horas "especiales") puede **destruir** el edge en vez de
  mejorarlo, mientras que exigir un barrido de liquidez previo sí añade valor. Esto es una hipótesis
  de alto valor para testear explícitamente en la grilla de S6/ST: ¿el filtro de tendencia M15/H1
  que ya usan ayuda o perjudica, controlando por lo demás igual? El video también es una plantilla
  metodológica directamente aplicable (embudo de validación, corrección por comparaciones
  múltiples, holdout único) que refuerza (no contradice) las normas ya adoptadas por este programa.
- **Red flags:** ninguna afirmación de PnL personal del autor (a diferencia de casi todos los otros
  videos); el propio autor declara las limitaciones (fills perfectos asumidos, 2 años alcistas como
  techo no expectativa, imposibilidad de backtest de discreción); venta cruzada de su comunidad de
  pago y datos premium de futuros, pero secundaria al contenido técnico. Limitación real: instrumento
  y timeframe distintos a los de S6/ST (NQ/ES en 1 minuto vs XAUUSD en M15), por lo que el resultado
  cuantitativo específico no es transferible directamente — solo la metodología y la hipótesis de
  "el sesgo de timeframe superior puede perjudicar" son trasladables, sujetas a validación propia.

## 8. nLQhKkjkuWI

- **Título (inferido):** "Brendan" — 9.000 backtests con Claude sobre 30 activos y 15 años de
  datos diarios para determinar qué familias de estrategias (trend, mean-reversion, momentum,
  breakout, volumen, volatilidad, patrones) sobreviven validación rigurosa.
- **URL:** https://www.youtube.com/watch?v=nLQhKkjkuWI
- **Duración/extensión:** 617 líneas, transcripción media.
- **Qué cubre realmente:** NO es un video de estrategia de trading manual sino de **metodología de
  investigación cuantitativa** (meta-nivel): construye con Claude Code un pipeline de backtesting
  masivo sobre **barras diarias** de 30 activos líquidos (incluye oro como uno de los 30, pero sin
  tratamiento especial) durante 15 años, con walk-forward, filtros de robustez y bootstrap. El
  hallazgo central: de las familias de estrategias probadas "desnudas" (sin filtros de régimen ni
  capas adicionales), **solo mean-reversion sobrevive de forma consistente**; trend-following y
  momentum en su forma básica fallan en agregado, pero funcionan "situacionalmente" — en activos
  específicos con tendencia fuerte (ej. Apple, Nvidia) o cuando se activan solo en régimen de
  mercado detectado como tendencial. Propone un framework de capas: señal base con edge real → 
  gestión de riesgo/sizing → señales no correlacionadas combinadas → filtro de régimen de mercado
  (vía Hidden Markov Model) que decide cuándo usar momentum vs. mean-reversion.
  - **NO trata timeframes intradía ni M15** — todo el testing es en barras diarias, explícitamente
    fuera del alcance intradía/futuros/opciones (lo declara el propio autor).
- **Reglas/parámetros específicos y testeables (de metodología, no de estrategia de mercado):**
  - **Embudo de validación (6 filtros) aplicado a cada backtest:** (1) walk-forward obligatorio
    (tune en datos antiguos, testear en datos nuevos no vistos); (2) filtro de **Sharpe
    out-of-sample > 0.5**; (3) filtro de **drawdown máximo < 35%**; (4) filtro de sobreajuste
    (descarta estrategias con desempeño in-sample muy superior al out-of-sample); (5) número mínimo
    de trades para considerar viable la estrategia; (6) tras estos filtros, exige un histórico de
    activo de **≥10 años** para el ranking final. De 9.000 backtests, sobreviven 524 → 478 tras el
    filtro de historia larga.
  - **Prueba de robustez por reshuffle (bootstrap):** cada estrategia superviviente se somete a
    **500 reordenamientos aleatorios de sus propios trades** para verificar que el resultado no
    dependa de la secuencia específica en que ocurrieron (ejemplo dado: una estrategia de momentum
    dual en Nvidia mostraba drawdowns de 61%/51% al reordenar, pese a verse "limpia" en el
    backtest original — señal de que el resultado dependía de una única trayectoria afortunada).
  - **Hallazgo de generalización:** una estrategia se considera robusta si funciona en **múltiples
    activos no relacionados** (ejemplo: RSI mean-reversion funcionó en 20 tickers distintos, Keltner
    reversion en 18) — un patrón que solo funciona en un instrumento se trata como sospechoso de
    suerte/sobreajuste.
  - **Propuesta de arquitectura de estrategia en capas:** señal base con edge demostrado + gestión
    de riesgo/sizing + combinación de señales no correlacionadas + **filtro de régimen de mercado**
    (HMM: detecta bear/tendencial/lateral-choppy/bull) que decide cuándo activar momentum
    (mercados tendenciales) vs. mean-reversion (mercados en rango/choppy) — en vez de correr
    cualquiera de las dos "a piloto automático" todo el tiempo.
  - **Momentum cross-sectional > momentum de un solo activo:** rankear una cesta de activos entre
    sí y solo ir largo en los más fuertes / corto en los más débiles mejoró sustancialmente el
    resultado de momentum frente a aplicarlo aisladamente a un solo activo.
- **Relevancia a S6/SuperTrend:** MEDIUM. No aporta ningún parámetro de entrada/salida/stop
  específico de oro ni de M15 — es barras diarias, multi-activo, sin especificidad de instrumento.
  Pero el **hallazgo central es directamente relevante como hipótesis de programa, no como regla
  de grid**: refuerza con evidencia (aunque en otro mercado/timeframe) la premisa de que
  trend-following como S6/ST necesita un **filtro de régimen explícito** (detectar tendencial vs.
  lateral/choppy) para no operar "a piloto automático" en todas las condiciones — coincide
  exactamente con la debilidad declarada de S6/ST en regímenes de rango. También es relevante
  metodológicamente: el uso de walk-forward + bootstrap de reshuffle + exigencia de generalización
  cross-activo son prácticas de validación ya adoptadas por este programa (Charter §A.2 bootstrap
  por bloques, holdout) — este video es una confirmación externa independiente de que esas
  prácticas son las correctas, no un hallazgo nuevo de mecánica.
- **Red flags:** ninguna cifra de PnL personal ni afirmación de rentabilidad propia (a diferencia
  de la mayoría de otros videos del grupo) — el video es inusualmente honesto en admitir que los
  resultados de mean-reversion "desnuda" son modestos y que esto es "el piso, no el techo"; sí hay
  venta cruzada de su comunidad de pago ("school", enlace en descripción) y los prompts exactos
  usados con Claude no se muestran con suficiente detalle como para auditar la metodología
  (p. ej. qué contó exactamente como "estrategia de trend" vs "mean reversion" en cada una de las
  9.000 corridas, o cómo se corrigió por comparaciones múltiples más allá de mencionarlo de pasada).

## 7. lYmmBoYQvWM

- **Título (inferido):** Estrategia "London Sweep / Frankfurt" — sistema ICT/SMC de 5 pasos
  (bias M15 → localización de sesión → confirmación M1 → punto de interés → toma de beneficio) con
  recap de un trade real de junio.
- **URL:** https://www.youtube.com/watch?v=lYmmBoYQvWM
- **Duración/extensión:** 662 líneas, transcripción media, muy densa en reglas concretas
  (posiblemente el video más "spec-like" del grupo A hasta ahora).
- **Qué cubre realmente:** sistema discrecional (pero declarado "mecánico y basado en reglas
  repetibles") de 5 pasos para operar durante la sesión de Londres/Frankfurt en forex, vendiendo
  además un indicador propio que automatiza cada paso. No es específicamente sobre oro, pero es
  agnóstico de par y estructuralmente idéntico a lo que otros videos ICT aplican a XAUUSD. Explica
  con mucho detalle el problema de ambigüedad en la definición de "swing high/low" (afirma que la
  mayoría de traders usan reglas no reproducibles) y ofrece una regla mecánica fija para resolverla
  (aunque no la especifica completamente en el audio — remite a su indicador propietario).
- **Reglas/parámetros específicos y testeables:**
  - **Paso 1 — Sesgo direccional M15 vía estructura de mercado:** operar solo en dirección de la
    secuencia de higher-highs/higher-lows (alcista) o lower-highs/lower-lows (bajista) en M15,
    usando puntos de swing "externos". Regla explícita: si el rango M1 es demasiado grande, usar
    estructura "interna" en lugar de externa (declarado pero sin definir el umbral numérico exacto
    de "demasiado grande").
  - **Paso 2 — Localización por sesión (rangos horarios en hora de Nueva York/EST):**
    - Sesión Asia: **20:00–00:00 EST**.
    - Sesión Londres: **02:00–05:00 EST**.
    - Sesión Nueva York: **07:00–10:00 EST**.
    Regla de ubicación: en sesión de Londres, operar únicamente en relación al rango
    (máximo/mínimo) de la sesión Asia — si el sesgo es bajista, buscar cortos **por encima del
    máximo de Asia**; si es alcista, buscar largos **por debajo del mínimo de Asia**. En sesión
    Nueva York, la referencia pasa a ser el rango de Londres (mismo patrón: NY toma el extremo de
    Londres y luego opera en dirección opuesta) — afirma esto como observación estadística repetida
    ("Londres suele tomar el rango de Asia y luego tendencia en la dirección opuesta").
  - **Paso 3 — Confirmación por cambio de estructura en M1:** tras el precio tomar el nivel de
    localización, esperar un "change of character" (cambio de estructura) en el timeframe de 1
    minuto en la dirección del sesgo M15 antes de confirmar la entrada — evita entrar apenas se
    toca el nivel (explícitamente muestra cómo vender inmediatamente al tocar el máximo de Asia sin
    confirmación produce 3 stops seguidos antes de 1 ganador, break-even neto tras comisiones).
  - **Paso 4 — Punto de interés (entrada de precisión):** dentro del leg de M1 que confirma el
    shift, entrar en un **order block** o **fair value gap** alineado con el sesgo (no en el
    breakout directo) para mejorar el R:R de ~1:1 a **1:4/1:5**. Stop loss: por encima/debajo del
    swing high/low que invalidaría el sesgo M1 (si se rompe, el sesgo M1 cambia y el trade queda
    invalidado).
  - **Paso 5 — Toma de beneficios (regla dual, la más operacionalizable del video):**
    - Objetivo 1 (parcial): **cerrar 50% de la posición en 5R fijo**, declarado explícitamente como
      corrección a un patrón repetido de "llegar a 1:4, 1:5, 1:6, 1:7 y volver a break-even" antes
      de tocar el target de estructura.
    - Objetivo 2 (resto de la posición): dejar correr hasta el **siguiente swing estructural**
      (o niveles de liquidez: máximo/mínimo del día previo, máximo/mínimo de la semana previa).
    - Ratio medio de resultado declarado por el autor: **win:loss promedio de 6.14** con
      **win rate ~33%**, presentado explícitamente como el trade-off esperado (a mayor R:R buscado,
      menor win rate).
    - Afirma (sin mostrar la metodología) tener **"10 años de datos"** que dan **75% de probabilidad
      de que se tome el mínimo/máximo del día previo** en los días siguientes — cifra no verificable
      desde el video, pero es un patrón de "toma de liquidez del extremo previo" replicable
      empíricamente con datos propios.
- **Relevancia a S6/SuperTrend:** HIGH. Aporta tres piezas testeables y trasladables a M15 XAUUSD:
  (a) un **filtro de régimen basado en rango de sesión** (Asia/Londres/NY) que podría probarse como
  filtro adicional para S6/ST — no operar señales de tendencia contra el rango de la sesión previa;
  (b) una **regla dual de toma de beneficios** (parcial fijo a 5R + resto trailing a estructura) que
  ataca directamente la debilidad declarada de gestión de salida — el patrón "corre a 5-7R y vuelve
  a break-even" descrito es exactamente el tipo de fuga de ganancias que un backtest de S6/ST podría
  estar sufriendo silenciosamente; (c) la idea de exigir confirmación de cambio de estructura en un
  timeframe menor antes de entrar, como filtro anti-falso-breakout. Limitación: la estrategia base
  es de reversión en rango de sesión (contra-extremo), no de continuación pura, y varias
  definiciones clave (umbral de "M1 range demasiado grande", regla exacta de swing) se delegan al
  indicador propietario sin especificarse completamente en el audio.
- **Red flags:** cifras de rentabilidad ("22.79R en junio", win:loss 6.14, 75% con "10 años de
  datos") presentadas sin mostrar metodología de cálculo ni auditoría externa — solo capturas de su
  propio panel; producto vinculado directamente (indicador propietario + paquete de "5 setups" de
  pago, enlace en descripción); el video reconoce explícitamente la ambigüedad/subjetividad del
  concepto central (definición de swing high/low) como problema de toda la industria, pero resuelve
  venciendo esa ambigüedad con un producto propio no auditable en vez de una regla pública
  verificable.

## 6. FbuYWdwA_wU

- **Título (inferido):** "David Tech" — tutorial de construcción de un "AI hedge fund" usando
  Claude Code + servidores MCP (TradingKit, TradingView, TriggerTrade) para descubrir, backtest,
  forward-test y desplegar automáticamente estrategias.
- **URL:** https://www.youtube.com/watch?v=FbuYWdwA_wU
- **Duración/extensión:** 774 líneas, transcripción media.
- **Qué cubre realmente:** NO es un video de estrategia de trading. Es un tutorial de
  infraestructura/tooling: cómo conectar Claude Code a MCP servers de terceros para automatizar el
  ciclo completo "generar idea → backtest → forward-test 20 trades / ~3 meses → validar
  robustez/juez → desplegar en TradingView → conectar a exchange/broker vía webhooks → monitoreo y
  apagado automático de estrategias que pierden edge". Todo el contenido es sobre criptomonedas
  (BTC/USDT) y trading multi-activo genérico vía TradingView/Pine Script; no discute mecánica de
  entrada/salida de ninguna estrategia concreta más allá de un ejemplo trivial de cruce de SMA
  (-22%, mencionado solo como prueba de que el sistema de backtest funciona, no como estrategia
  recomendada).
- **Reglas/parámetros específicos y testeables:**
  - **Regla de circuit-breaker de drawdown a nivel de portafolio (meta-regla, no de trading):**
    pausar automáticamente una estrategia si toca **4% de drawdown máximo en un solo día**.
  - **Alternativa mencionada:** bandas de Bollinger sobre la curva de equity (no sobre precio); si
    la equity toca la banda inferior (1 desviación estándar), apagar los bots asociados.
  - **Ventana de forward-testing recomendada antes de confiar en una estrategia:** mínimo **20
    trades**, o aproximadamente **3 meses**, dependiendo del timeframe de optimización.
  - Ningún parámetro de entrada, stop, trailing o filtro de régimen específico de mercado.
- **Relevancia a S6/SuperTrend:** NONE. No aporta mecánica de trading aplicable a S6/ST ni menciona
  oro/XAUUSD en ningún momento. Las únicas reglas concretas (4% drawdown diario como apagador, 20
  trades/3 meses de forward-test antes de confiar en una estrategia) son ideas de **gobernanza de
  portafolio de estrategias**, no de la estrategia individual — conceptualmente cercanas a lo que
  ya hace este programa de investigación (holdout, gates estadísticos) pero sin aportar nada nuevo
  o específico al problema de exits/regímenes de rango de S6/ST.
- **Red flags:** el video es esencialmente un anuncio/tutorial de producto propio (su comunidad de
  pago "school.com/davidtech", su plataforma "Strategy Factory AI" con 400+ estrategias, su
  colección de repos de GitHub); afirma "he backtesteado más de 2.000 estrategias en 5 años" y
  "actualmente corro 7 bots" sin mostrar ningún resultado auditado agregado; el ejemplo de backtest
  mostrado en vivo fue en realidad una pérdida (-22%), usado solo para demostrar que la herramienta
  "funciona", no que el enfoque genera edge — irónicamente el propio video no aporta evidencia de
  que el método de descubrimiento automatizado de estrategias sea rentable.

## 5. en8RMFRqSME

- **Título (inferido):** "Brad Gold" (canal "Brad Trades") — estrategia de scalping en oro (XAUUSD)
  basada en estructura de mercado y liquidez (estilo ICT/SMC), con recap de dos trades reales que
  sumaron $566k.
- **URL:** https://www.youtube.com/watch?v=en8RMFRqSME
- **Duración/extensión:** 815 líneas, transcripción media.
- **Qué cubre realmente:** único video del corpus grupo A hasta ahora **explícitamente sobre oro**,
  con timeframes explícitos de **15 minutos y 1 hora** (coincide exactamente con el timeframe de
  S6/ST). Estrategia de scalping direccional (no trend-following puro ni contra-tendencia clásico):
  alinear tendencia 1H+15M, esperar a que el precio llegue a una zona de oferta/demanda, esperar un
  barrido de liquidez (stop hunt) en esa zona como disparador, entrar en la dirección de la
  tendencia mayor tras el barrido, con objetivo en el siguiente swing/zona de liquidez. Incluye
  advertencia explícita: el oro se mueve muy rápido, respeta liquidez fuertemente (barre máximos y
  mínimos antes de moverse con fuerza), y castiga a quien intenta "capturar todo el movimiento" o
  usa stops demasiado ajustados. Fuerte venta cruzada de su app "Edge Flow" (planificación,
  guardrails, journaling).
- **Reglas/parámetros específicos y testeables:**
  - **Paso 1 — Alineación de tendencia:** exige que la tendencia de **15M y 1H estén alineadas**
    (ambas alcistas o ambas bajistas) antes de buscar cualquier entrada; si hay desalineación,
    declara el setup de baja probabilidad (lo confirma él mismo: el trade "5/10" del video fue
    justamente uno donde operó pese a desalineación 15M/1H, y casi lo pierde).
  - **Paso 2 — Marcar zonas de liquidez y puntos de interés:** identificar zonas de oferta/demanda
    (u order blocks / fair value gaps) en dirección de la tendencia mayor, y los "swing
    lows/highs" internos como liquidez (donde se agrupan stops).
  - **Paso 3 — Esperar (no operar) hasta que el precio llegue a un punto de interés en 15M.**
  - **Paso 4 — Modelo de entrada, DOS variantes explícitas y comparadas:**
    - *Agresiva:* entrar inmediatamente tras el **barrido de liquidez** (mecha que toma un swing
      low/high previo) dentro/cerca de la zona de interés — mayor tasa de falsos breakouts pero
      menor probabilidad de perderse el movimiento.
    - *Conservadora:* esperar además una confirmación de **"market shift"** — que el precio rompa
      el último swing interno opuesto tras el barrido — y esperar un **pullback a la zona que
      generó ese shift** antes de entrar. Menos falsos positivos, más probabilidad de perder el
      trade si no hay pullback.
  - **Stop loss:** siempre bajo/sobre la vela de entrada, específicamente bajo/sobre el
    máximo/mínimo que generó el barrido de liquidez ("protected low/high" — hay menor probabilidad
    de que se vuelva a barrer ese nivel).
  - **Take profit:** el siguiente swing high/low o zona de oferta/demanda en 15M — **no** usa
    múltiplos R fijos grandes; ejemplo dado fue 1:3 R:R, con filosofía explícita de "capturar la
    parte más limpia del movimiento", no todo el rango del día.
  - **Anécdota de gestión discrecional (trade "5/10"):** durante ese trade quitó el stop loss
    manualmente por "corazonada" al ver que el precio iba en contra, apostando a que era otro
    barrido de liquidez — funcionó, pero él mismo lo señala como mala práctica para principiantes
    ("si estás en tu primer año, no muevas tu stop; sé lo más mecánico posible").
- **Relevancia a S6/SuperTrend:** HIGH. Es el video más directamente aplicable del grupo A hasta
  ahora: mismo instrumento (XAUUSD/oro), mismos timeframes de referencia (15M/1H) que S6/ST, y
  aborda exactamente la debilidad declarada de "regímenes de rango" mediante un filtro de
  alineación multi-timeframe (no operar si 15M y 1H no coinciden) — esto es un candidato directo
  de grid/filtro testeable para reducir falsas señales de S6/ST en lateral. El concepto de "esperar
  el barrido de liquidez antes de la entrada" es una idea de timing de entrada potencialmente
  aplicable a filtrar entradas de breakout prematuras. El uso de "protected high/low" como base del
  stop (en vez de ATR fijo) es una alternativa de stop testeable. Limitación: la identificación de
  zonas de oferta/demanda y "barrido de liquidez" es discrecional/visual (estilo ICT), sin
  definición algorítmica precisa en el video — traducirlo a regla de código exacta requeriría
  operacionalizar qué cuenta como swing y qué distancia de mecha cuenta como "sweep".
- **Red flags:** cifra de resultado de altísimo impacto ($566k en un mes, con un trade de $292k en
  1h20m) presentada sin contexto de tamaño de cuenta ni apalancamiento, lo que hace la cifra
  absoluta no evaluable (podría ser cualquier % de retorno según el capital); no hay evidencia de
  auditoría externa, solo capturas de su propio "trading journal"; venta cruzada activa de su app
  Edge Flow y de una mentoría de 33 días; la anécdota de remover el stop loss por "gut feeling" es
  presentada como válida por experiencia (7 años) pero es exactamente el tipo de manejo de riesgo
  discrecional que el propio Charter de este programa prohíbe reproducir sin evidencia sistemática.

## 4. PnIkSLm2yRk

- **Título (inferido):** "Tori Trades" — sistema completo de trading basado únicamente en líneas
  de tendencia (trend lines) multi-timeframe ("top-down analysis"), aplicable a cualquier
  instrumento.
- **URL:** https://www.youtube.com/watch?v=PnIkSLm2yRk
- **Duración/extensión:** 955 líneas, transcripción media-larga, contenido denso y bien
  estructurado (sin relleno de anécdotas de PnL como otros videos del grupo).
- **Qué cubre realmente:** metodología discrecional completa de análisis técnico basada
  exclusivamente en **líneas de tendencia** (sin indicadores), demostrada paso a paso sobre Bitcoin
  en TradingView. Define un proceso reproducible: análisis top-down multi-timeframe → identificar
  "action line" (línea rota = señal de entrada) → "safety line" (línea opuesta = stop/trailing) →
  gestión de posición → mantenimiento diario de las líneas. Es agnóstico de instrumento y timeframe
  (afirma poder aplicarse igual a oro, crudo, Nasdaq, Tesla, forex).
- **Reglas/parámetros específicos y testeables:**
  - **Top-down analysis:** dibujar trend lines en secuencia descendente de timeframes (mensual →
    semanal → diario → 4H → 1H → [timeframe de ejecución]) usando la herramienta "ray" (dos puntos,
    extensión indefinida). Reglas de construcción de la línea:
    1. La primera trendline alcista debe iniciar en el **mínimo más bajo visible** en el timeframe,
       con ángulo estrictamente positivo (nunca horizontal). Simétrico para la primera bajista
       (máximo más alto).
    2. Cada trendline nueva debe conectar con el punto B de la anterior (point A nuevo = point B
       anterior) — construcción encadenada.
    3. Maximizar el número de toques (touch points) por línea.
    4. **Regla dura: el precio nunca puede haber perforado/cruzado la línea** — si lo hizo, la línea
       es inválida y se debe ajustar.
    5. Bajar de timeframe repitiendo el proceso hasta llegar al timeframe de ejecución elegido.
  - **Entrada ("action line"):** se opera en la dirección de la ruptura de una trend line — ruptura
    de una alcista → entrada en corto; ruptura de una bajista → entrada en largo. Es puramente
    reactiva al quiebre de estructura, no anticipatoria.
  - **Salida/stop/trailing ("safety line" = SL):** el stop inicial se coloca justo al otro lado de
    la trend line opuesta a la que originó la entrada (la "safety line"). A medida que el precio
    avanza y sigue respetando la safety line, el trader **desplaza manualmente el stop a lo largo de
    esa línea** (trailing stop dinámico, no un ATR ni un múltiplo fijo). La salida ocurre única y
    exclusivamente cuando el precio **viola/cruza la safety line** — no hay take-profit fijo ni
    objetivo de R múltiplo.
  - **Position sizing:** regla genérica de principiante — **arriesgar 1-2% del capital por
    operación**, stop siempre determinado por la distancia a la safety line (no al revés).
  - **Mantenimiento diario:** las líneas deben re-trazarse/ajustarse a diario conforme aparecen
    nuevos máximos/mínimos, siguiendo las mismas 3 reglas de construcción.
- **Relevancia a S6/SuperTrend:** MEDIUM-HIGH. La mecánica "safety line" es, en esencia, un
  **trailing stop estructural basado en pendiente de tendencia** (equivalente conceptual a un
  SuperTrend/Parabolic dibujado a mano con reglas de no-intersección) — es la pieza más
  directamente comparable con el mecanismo de SuperTrend que se ha visto en el grupo hasta ahora, y
  toca exactamente la debilidad declarada de exit/trailing management. Es completamente
  implementable como regla algorítmica: la "safety line" puede formalizarse como la trendline de
  regresión/pivotes conectados sin intersección de precio, y el trailing = mover el stop al valor
  de esa línea en cada barra. La entrada por ruptura de trendline también es una idea de filtro de
  régimen (invalidación de tendencia) potencialmente útil para decidir cuándo S6/ST deben cerrar o
  no abrir posiciones. No es específico de oro ni M15, pero se declara explícitamente agnóstico de
  instrumento/timeframe, lo cual reduce el riesgo de que la mecánica no traduzca.
- **Red flags:** afirmación de resultado personal no verificable ("$5.000 → más de medio millón en
  11 años" con "el mismo sistema exacto") sin mostrar track record auditado ni estadísticas
  (win rate, drawdown, número de trades); ningún backtest cuantitativo, todo es demostración visual
  cualitativa sobre un solo activo (Bitcoin) sin medir resultados; venta cruzada de prop firm
  (Alpha Futures/Alpha Capital, código de descuento "Tory"); el trazado de trend lines es
  inherentemente subjetivo/discrecional pese a presentarse como "sin ambigüedad" — dos traders
  distintos trazarían líneas distintas, lo cual complica la traducción 1:1 a regla de código sin
  definir un algoritmo determinista de pivotes.

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

