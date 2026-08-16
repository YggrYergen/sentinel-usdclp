# Inventario de literatura informal — Grupo B (14 videos)

> T0.11b, decisión D-49 (2026-08-15). Pasada única de lectura + inventario, sin conteo de tokens
> ni routing por video. Un video = un contexto de análisis; procesados estrictamente uno a la vez,
> en el orden listado abajo. Objetivo de referencia: hacer ganar más / perder menos a S6 y
> SuperTrend en XAUUSD M15 (debilidades conocidas: gestión de salida, regímenes laterales).
>
> Fuente: `data/literature/youtube_transcripts/<id>.txt`. `urls.txt` no trae títulos, solo URLs;
> los títulos abajo están **inferidos del contenido** de la transcripción (marcado explícitamente).
> "Longitud" es un proxy por tamaño de fichero de la transcripción (no hay metadata de duración).

---

## 1. `m5zu_X-_51I` — "Cómo hice $1.000.000 en 51 días day trading" (título inferido) — Ross Cameron / Warrior Trading

- URL: https://www.youtube.com/watch?v=m5zu_X-_51I
- Longitud: transcripción de 118 KB / 2059 líneas — el video más largo del lote B, formato masterclass.

**Qué cubre:** Day trading discrecional de acciones US small-cap/low-float en marcos de 1-5 minutos.
No es trading algorítmico ni sistemático — el propio narrador aclara que decide manualmente cada
entrada/salida. Cubre: criterios de selección de acciones, patrón de entrada "bull flag", gestión
de riesgo por posición, escalado de tamaño de posición durante el día, y una rutina de arranque
para principiantes.

**Reglas/parámetros concretos y citables:**
- Selección de acción (5 criterios, TODOS deben cumplirse): volumen relativo ≥5× el promedio de 50
  días; subida pre-market ≥2% (idealmente ≥10%); catalizador de noticias; precio entre $2 y $20;
  float <10M acciones (float bajo).
- Patrón de entrada "bull flag": tras un impulso alcista fuerte (spike por noticia), esperar
  retroceso que sostenga ≥50% del movimiento inicial, entrar en la primera vela que hace nuevo
  máximo tras el retroceso.
- Stop: mínimo del retroceso (pullback). Target inicial: retest del máximo del día. Umbral mínimo
  de entrada: relación beneficio/pérdida ≥2:1 (declina el trade si no ve potencial de 2:1).
- Gestión de tamaño intradía: arranca el día con 1/4 del tamaño de posición completo; solo pasa a
  tamaño completo tras acumular un "cushion" de beneficio = 1/4 del objetivo diario (típicamente en
  1-2 trades ganadores). Si no toma ningún trade en 30 minutos, corta la sesión ("it's not
  happening today").
- Piramidación en ganadores: si la posición va a favor, duplica el tamaño y mueve el stop a
  breakeven (nunca añade a perdedoras — "cut my losers ruthlessly").
- Pérdida máxima diaria = objetivo de ganancia diaria (simetría declarada, sin cifra fija general).
- Clasificación de calidad de setup: A = cumple 5/5 criterios, B = 4/5, C = 3/5; declara que solo
  opera A y ocasionalmente B.
- Progresión de escalado recomendada para principiantes: primeras 1000 operaciones con ~160
  acciones/posición, luego 1600, luego 16000 (factor ×10 en cada etapa, ligado a su propio caso).

**Indicadores:** ninguno técnico formal (RSI/MACD/EMA no aparecen); todo es lectura de velas
(patrones nombrados: "bull flag", "dragonfly doji", mecha inferior = señal alcista) y volumen
relativo en tiempo real vía software de escaneo propietario ("Day Trade Dash").

**Riesgo/sizing:** ver arriba — basado en distancia entrada-stop, no en % de cuenta fijo declarado
explícitamente (aunque menciona cuentas de $25k-$100k con 4× leverage). No hay regla de riesgo por
operación en % de capital.

**Afirmaciones de resultados:** $1M en 51 días, 936 operaciones, 71.4% aciertos, ganador medio
$1800/perdedor medio $761 (~2.4:1). Reclama auditoría externa de un CPA de sus resultados
acumulados ("independently audited"), pero no se muestra el informe ni metodología de auditoría en
el video — es una afirmación verbal sin evidencia mostrada en pantalla.

**Menciones de zonas S/R, régimen, trailing, XAUUSD:** ninguna mención de oro/XAUUSD, ni de forex.
"Régimen" se menciona solo como "mercado caliente vs. frío" (heurística subjetiva de sizing, no
una regla de detección medible). No hay ATR, no hay trailing stop técnico (el "trailing" es mover
el stop a breakeven tras duplicar posición, no un trailing dinámico). Sin mención de noticias
macro, sesiones, ni spread.

**Qué NO cubre:** cualquier instrumento fuera de acciones US de baja capitalización; timeframes
M15+; trading de tendencia/breakout tipo swing; gestión de posición para instrumentos sin opción
de "doblar" tamaño ilimitadamente; backtesting o validación estadística fuera de sus propias
métricas de trading real.

**Relevancia a S6/SuperTrend: LOW.** El instrumento (acciones de bajísimo float, movidas por
catalizadores de noticias y manipulación de liquidez) y el timeframe (1-5 min, holds de 2-3
minutos) son estructuralmente distintos de XAUUSD M15 trend-following. Las ideas de "piramidar en
ganadores moviendo el stop a breakeven" y "cortar sin piedad las perdedoras" son principios
genéricos de gestión de salida potencialmente transferibles como HIPÓTESIS a probar, pero ningún
parámetro numérico es aplicable directamente (dependen de float, volumen relativo y estructura de
velas de 1 minuto que no existen en forex).

**Red flags:** fuerte tono de venta (upsell a "Warrior Trading" community, venta de libro propio,
trial de $20); afirmación de resultados auditados sin mostrar evidencia; ejemplos tipo "pop quiz"
seleccionados a posteriori sobre gráficos ya resueltos (razonamiento con sesgo de retrospectiva
clásico de contenido educativo de trading); disclaimer verbal de "mis resultados no son típicos"
que reconoce el propio sesgo de supervivencia/habilidad del narrador.

---

## 2. `ksVXut9bSSg` — "The Forever Model: Complete Trading System Revealed" (título inferido) — "Justin", Trade School ep. final

- URL: https://www.youtube.com/watch?v=ksVXut9bSSg
- Longitud: transcripción de 63 KB / 1640 líneas — video largo, mitad estrategia / mitad psicología.

**Qué cubre:** Estrategia ICT/Smart-Money-Concepts ("forever model") en futuros NASDAQ (NQ) y
S&P (ES) intradía, multi-timeframe (15m/5m/1m). Segunda mitad del video: gestión de riesgo para
cuentas fondeadas (prop firms), psicología de trading, plan de implementación de 30 días.

**Reglas/parámetros concretos y citables:**
- Setup de entrada ("forever model") requiere 4 elementos simultáneos: (1) barrida de liquidez
  ("liquidity sweep") o rechazo de un Fair Value Gap (FVG) de timeframe superior; (2) "SMT"
  (divergencia entre NQ y ES: un activo hace máximo/mínimo más alto/bajo que el otro, señal de
  debilidad relativa); (3) "CISD" (Change in State of Delivery) = cierre por encima/debajo de una
  serie de velas de un mismo color, a favor del liquidity draw; (4) objetivo = liquidez opuesta,
  equilibrio, un FVG, o basado en R:R.
- FVG definido con precisión: hueco de ineficiencia creado por una formación de 3 velas
  consecutivas (patrón ICT estándar).
- Entrada: en la ruptura del CISD (cierre por debajo/encima de la última vela de color contrario)
  o en el "rebalance" (retroceso) hacia ese nivel.
- Stop: en el "protected low/high" (el extremo donde se formó la divergencia SMT) o en el mínimo/
  máximo reciente de la señal de entrada.
- Ratio riesgo:beneficio objetivo declarado: mínimo 1:2 ("risking one to make two"); por debajo de
  eso solo si hay convicción muy alta.
- Riesgo por operación — **dos cifras inconsistentes en el mismo video**: (a) para cuentas
  fondeadas/prop firm dice explícitamente "risk 10% of an account per trade" ("give your room for
  10 losses before account destruction"); (b) más adelante, en el plan de 30 días, dice "Maximum
  one to two risk per trade" (sin unidad explícita, probablemente 1-2%). No reconcilia la
  contradicción.
- Regla de circuito: "Stop trading after two losses in a day" (semana 2 del plan de 30 días).
- Sesiones: opera solo la sesión de Nueva York; usa máximos/mínimos de sesión de Londres, Asia y
  NY como zonas de liquidez de alta probabilidad.
- Principio fractal explícito: el mismo patrón de 4 elementos se busca en cada timeframe (1H →
  15m → 5m → 1m), alineando sesgo de timeframe superior con gatillo de timeframe inferior.

**Indicadores:** ninguno tradicional (sin EMA/RSI/ATR); todo basado en estructura de precio
(order flow / ICT: FVG, liquidez de sesión, CISD) y en la divergencia entre dos activos
correlacionados (NQ vs ES) para el filtro SMT.

**Gestión de riesgo/sizing:** posición dimensionada por distancia al stop, no por P&L fijo
("distance to stop determines your position size"). Progresión de tamaño en 30 días: semana 1
solo paper trading; semana 2 tamaño mínimo (micros, $5-10 de riesgo); semanas 3-4 incremento
gradual condicionado a disciplina. Sin cifra de % de cuenta estándar fuera de la mencionada arriba.

**Afirmaciones de resultados:** "casi un millón de dólares" en la carrera, "primer año de
$300.000" a partir del año 3 de trading, un trade de "$8.000 en 20 minutos" mostrado sin
verificación en pantalla (no se exhibe broker statement ni cuenta verificada). Menciona haber
"quebrado cuentas constantemente" antes de encontrar el modelo — sin cifras de drawdown.

**Menciones de zonas S/R, régimen, trailing, XAUUSD:** liquidez de sesión (Londres/Asia/NY) actúa
como S/R implícito; "equilibrium" (50% de un rango) como nivel de reacción — concepto de régimen
propio (aunque no formalizado como "lateral vs. tendencial", es "choppy/no clarity" vs. "clear
draw"); menciona explícitamente "if the market is choppy... there's nothing to see... wait for
clarity" como regla de no-operar en lateralidad, pero sin definición medible de choppy. No hay
ATR, no hay trailing stop dinámico (solo mover stop tras confirmación de displacement adicional).
Ninguna mención de oro/XAUUSD ni de forex; instrumento es exclusivamente futuros de índices US.

**Qué NO cubre:** cualquier instrumento fuera de NQ/ES; backtesting cuantitativo o estadísticas de
sistema (pide al espectador que backtestee él mismo, no muestra resultados agregados de su propio
backtest); gestión de exits parciales con reglas numéricas fijas (solo "take partials at internal
lows/highs", sin fracciones); definición operacional de "choppy".

**Relevancia a S6/SuperTrend: MEDIUM.** El instrumento y el filtro SMT (requiere un segundo activo
correlacionado) no son transferibles directamente a XAUUSD sin sustituto (podría explorarse
divergencia XAUUSD vs. DXY o XAGUSD, pero el video no lo sugiere). Sin embargo, hay ideas
estructuralmente relevantes como HIPÓTESIS a probar en S6/SuperTrend: (a) exigir R:R mínimo 1:2
antes de tomar la señal de entrada de tendencia; (b) circuit breaker "detener tras N pérdidas
consecutivas en el día"; (c) filtro de "no operar si no hay contexto claro / condición choppy"
como proxy de filtro de régimen lateral, que es justamente la debilidad conocida de S6/ST — pero
el video no aporta un umbral medible, solo discreción subjetiva.

**Red flags:** contradicción interna en el % de riesgo por operación (10% vs 1-2%) sin resolver;
resultados no verificados en pantalla; fuerte funnel de venta (comunidad "Tactical Traders",
software de journaling "Trade Path" propio, prop firm afiliada "Apex"); gran proporción del video
es contenido motivacional/psicológico genérico no específico de mercado ni testeable; conceptos
ICT (liquidez, "smart money") son narrativa no falsable tal como se presentan, sin backtest
mostrado en pantalla.

---

## 3. `hC4g7qY6UcQ` — "Risk Management Masterclass" (título inferido, canal orientado a trader de acciones US)

- URL: https://www.youtube.com/watch?v=hC4g7qY6UcQ
- Longitud: transcripción de 58 KB / 1547 líneas — monólogo largo, sin instrumento específico
  (agnóstico de mercado; ejemplos con acciones US, pero el marco es general).

**Qué cubre:** Filosofía y marco conceptual de gestión de riesgo, no una estrategia de entrada.
Cubre stop-losses (duro vs. mental vs. temporal), position sizing como herramienta de riesgo
superior al stop, jerarquía de reglas (flexibles vs. rígidas/inquebrantables), sizing dinámico
según calidad de oportunidad, reconocimiento de régimen ("cuándo no operar"), psicología (tilt,
FOMO, anclaje, overconfidence tras rachas ganadoras), y retiro de ganancias ("wiring out profits").

**Reglas/parámetros concretos y citables (el propio narrador los presenta como EJEMPLO ilustrativo
personal, no como receta universal — lo declara explícitamente varias veces):**
- Límite de pérdida diaria de ejemplo: nunca perder más del 10% de la cuenta en un día.
- Límite mensual: drawdown >20% del mes → pausa obligatoria de 3 días + reducir tamaño de posición
  al 50%; drawdown acumulado adicional del 10% (≈30% total) → pausa de 1 semana.
- Límite duro de cuenta: nunca perder más del 50% de la cuenta (umbral de "ruina" personal).
- Tamaño máximo por posición: nunca >50% de la cuenta en un solo trade ni >50% en un mismo "tema"
  correlacionado; posiciones cortas limitadas a 25% de cuenta; nunca mantener overnight una
  posición corta en microcap por más del 2% de la cuenta.
- "Daily report card" (autoevaluación subjetiva pre-mercado): calificación C → reducir riesgo 50%;
  D → reducir riesgo 80%; F → no operar ese día, solo trabajo productivo/recuperación.
- Retiro de ganancias: ejemplo de regla — retirar 50% de las ganancias por encima del máximo
  histórico de la cuenta ("high water mark") cada mes.
- Concepto de "time stop": salir de una operación si la tesis no empieza a funcionar dentro de una
  ventana de tiempo esperada, independientemente de si tocó el stop de precio — útil especialmente
  en trades basados en catalizadores de noticias.
- Regla explícita de jerarquía: reglas a nivel de trade (stop individual, gestión táctica) son
  flexibles y pueden romperse si el EV lo justifica; reglas a nivel de cuenta (drawdown máximo,
  ruina) son casi inquebrantables.
- Sizing dinámico ligado a calidad de oportunidad: declara haber arriesgado hasta "10x, en casos
  raros 100x" su tamaño base en días de oportunidad excepcional vs. días lentos — sin fórmula, por
  juicio subjetivo diario.
- Rechaza explícitamente el criterio de Kelly como impracticable en trading real (inputs
  imposibles de estimar con precisión, no personalizable, genera drawdowns que rompen la
  disciplina del propio trader) — lo usa solo como intuición direccional ("mayor edge → mayor
  apuesta"), no como fórmula.

**Indicadores:** ninguno técnico. El "edge" se define por el propio trader/estrategia, no por
indicador.

**Riesgo/sizing:** ver arriba — el pilar central del video es que el position sizing (no el stop)
es la herramienta de riesgo más poderosa, porque determina si un evento de cola (gap, halt) es
sobrevivible. Distingue riesgo asimétrico de cortos (pérdida teóricamente ilimitada) vs. largos
(pérdida acotada al 100%) — no aplica directamente a XAUUSD (sin equivalente de "float" o halt).

**Afirmaciones de resultados:** ninguna cifra propia de P&L o track record verificable se da en
este video; solo referencias de terceros (menciona drawdowns públicos de 50-70% de otros traders
conocidos, sin verificar cifras ni dar las suyas). Esto reduce el riesgo de sesgo de venta directa
respecto a los otros dos videos del lote.

**Menciones de zonas S/R, régimen, trailing, XAUUSD:** régimen se trata explícitamente como
concepto de "condiciones de mercado" (favorables/limpias vs. "choppy, movimientos random y
lentos... simplemente incompatible con tu estrategia") — recomienda no forzar operaciones y pasar
a modo "R&D" (revisar journal, backtestear, descansar) en vez de operar en condiciones adversas;
es un principio, no una regla medible con umbral. No hay ATR, S/R técnico, ni trailing dinámico
formalizado (solo "a veces muevo el stop" como discreción). Ninguna mención de oro/XAUUSD, forex,
ni sesiones de mercado específicas.

**Qué NO cubre:** ninguna señal de entrada, ningún indicador técnico, ningún instrumento
específico, ninguna cifra respaldada por backtest o dato agregado propio — es 100% marco
conceptual y ejemplos ilustrativos declarados como no-universales.

**Relevancia a S6/SuperTrend: MEDIUM.** No aporta reglas de entrada ni de mercado específicas a
XAUUSD/M15, pero el contenido apunta directamente al área declarada débil del programa (gestión de
salida/riesgo y detección de régimen). Ideas testeables como HIPÓTESIS de investigación: (a)
circuit breaker de pérdida diaria/semanal con reducción de tamaño escalonada tras drawdown; (b)
"time stop" — cerrar si el trade no muestra progreso direccional dentro de N barras, aplicable
directamente a S6/ST en M15; (c) jerarquía de reglas rígidas (nivel cuenta) vs. flexibles (nivel
trade) como principio de diseño de sistema de risk-gating; (d) "mejor trade es no operar" como
justificación conceptual — aunque no operacional — para el filtro de régimen lateral que el
programa ya busca. Ninguno de estos viene con un umbral numérico ligado a ATR/volatilidad de
XAUUSD; habría que derivarlo empíricamente.

**Red flags:** bajo nivel de red flags relativo a los otros dos videos del lote — no hace
afirmaciones de resultados propios verificables ni vende un producto/comunidad de forma agresiva
(solo referencias a otros videos del mismo canal). Riesgo principal: es contenido puramente
cualitativo/motivacional sin ningún dato ni backtest mostrado en pantalla; los ejemplos numéricos
(10%/20%/50%) se presentan explícitamente como ilustrativos y personales, no como recomendación
generalizable — el propio narrador lo advierte, lo cual es honesto pero limita su valor operativo
directo.

---

## 4. `wm4A6qo0g3I` — "Drift VWAP Pullback: prop firm golden ticket" (título inferido) — entrevista a Matteo Conti (SQR Capital)

- URL: https://www.youtube.com/watch?v=wm4A6qo0g3I
- Longitud: transcripción de 34 KB / 1039 líneas — entrevista con demo en gráfico, formato podcast.

**Qué cubre:** Estrategia sistemática de reversión-a-VWAP en futuros Nasdaq-100 (NQ), diseñada
específicamente para maximizar la probabilidad de aprobar "prop firm challenges" (no
necesariamente para operar capital propio — el propio entrevistado lo advierte). Incluye
metodología de validación cuantitativa (in-sample/out-of-sample, simulación Monte Carlo) más
rigurosa que el resto del lote.

**Reglas/parámetros concretos y citables (el más preciso y mecánico del lote B):**
- Instrumento/timeframes: NQ futuros, filtro de tendencia en velas de 15 min, gatillo de entrada
  en velas de 5 min. VWAP calculado en base 15 min, ancla en apertura de mercado (9:30 ET),
  desplegado sobre el gráfico de 5 min.
- Filtro de tendencia ("drift"), evaluado cada 15 min, requiere las 3 condiciones simultáneamente:
  **Largo:** (1) precio por encima del VWAP; (2) VWAP en ascenso en los últimos 15 min; (3) precio
  del subyacente subió ≥0.1% en la última hora (4 barras de 15 min). **Corto:** condiciones
  espejo (precio bajo VWAP, VWAP descendente, caída ≥0.1% en la última hora).
- Bloqueo horario: no operar entre 9:30-10:30 ET (primera hora, para que el VWAP tome nivel).
- Gatillo de entrada: primera vela en contra de la tendencia que retrocede hacia el VWAP (para
  largos: primera vela roja hacia el VWAP; para cortos: primera vela verde) → entrada a mercado en
  la apertura de la siguiente vela.
- Gestión de riesgo por operación — **ratio riesgo:beneficio negativo, declarado explícitamente**:
  largos arriesgan 80 puntos para ganar 40 (2:1 en contra); cortos arriesgan 80 puntos para ganar
  50. Compensado por una tasa de acierto declarada del 64-65%.
- Guardrails de sistema: una sola posición a la vez; máximo 4 operaciones/día; **máximo 2 pérdidas
  consecutivas por día → detener el sistema por el resto del día**; no abrir nuevas operaciones
  después de las 15:30 ET; cerrar todas las posiciones a las 15:55 ET (antes del cierre regular).
- Metodología de validación: desarrollo/optimización in-sample 2020-2024; el parámetro de 0.1% de
  momentum se fijó por optimización in-sample "minimizando el riesgo de overfitting"; período
  out-of-sample declarado 2024 hasta agosto 2026 (validación forward real, no solo walk-forward
  histórico).
- Estadísticas declaradas: ganador medio ~$866, perdedor medio ~$1.300 (por contrato/unidad no
  precisada con exactitud), tasa de acierto 64-65%. Simulación Monte Carlo de 20.000 corridas sobre
  el histórico de trades → probabilidad de aprobar un desafío de prop firm: 49.8% en el primer
  intento, 74.8% acumulado en 2 intentos, 87.3% en 3, 93.6% en 4; tiempo medio para aprobar ≈3.4
  días.
- Uso de Monte Carlo como "vara de medir" para monitoreo en vivo: umbral de ejemplo dado — "solo
  5% de probabilidad de drawdown >$10.000 en 10 trades"; si el drawdown real excede ese percentil,
  regla es detener el sistema y revisar (kill-switch estadístico, no discrecional).

**Indicadores:** VWAP (anchored, 15 min) — único indicador. Pendiente del VWAP y posición del
precio respecto a él son las señales de régimen; momentum de 1h (%) es el tercer filtro.

**Gestión de riesgo/sizing:** dimensionado explícito en puntos de NQ, no en % de cuenta; el diseño
completo está optimizado para superar el reglamento de drawdown de firmas de fondeo (prop firms),
no para retorno compuesto de capital propio — dato relevante declarado por el propio entrevistado
("unlikely que esta estrategia haga dinero con tu propio capital").

**Afirmaciones de resultados:** narración inicial del host afirma "over 300% across more than
4.000 trades in historical testing" — no verificado en pantalla ni desglosado con métricas
estándar (Sharpe, max DD) más allá de lo mencionado arriba. Las cifras de win rate/avg win/avg
loss y las probabilidades Monte Carlo sí se muestran como salida de un backtest codeado (Python),
con separación in/out-of-sample declarada — el nivel de rigor metodológico es notablemente más
alto que el resto del lote, aunque sigue sin auditoría externa independiente.

**Menciones de zonas S/R, régimen, trailing, XAUUSD:** el VWAP funciona como zona dinámica de
reacción (S/R "viva"); "régimen" se detecta con las 3 condiciones de tendencia (posición vs VWAP,
pendiente VWAP, momentum 1h) — es la aproximación MÁS medible y replicable a un filtro de régimen
de todo el lote B hasta ahora. Sin trailing stop (TP/SL fijos en puntos). Ninguna mención de
oro/XAUUSD ni forex; instrumento exclusivamente NQ.

**Qué NO cubre:** gestión de salidas parciales, trailing o breakeven; cualquier instrumento fuera
de NQ; operar con capital propio (el video es explícito en que el objetivo es pasar el desafío de
fondeo, no maximizar EV de largo plazo); detalles del código o de los datos crudos usados en el
backtest (no se entrega el dataset ni el script).

**Relevancia a S6/SuperTrend: MEDIUM.** El instrumento, timeframe y mecánica de entrada (reversión
a VWAP dentro de una tendencia de 15 min, penalizada por RR negativo) no transfieren directamente
a XAUUSD M15 trend-following/breakout. Pero el video aporta tres elementos metodológicos con alto
valor de HIPÓTESIS testeable independientemente de la estrategia de entrada: (a) un filtro de
régimen de 3 condiciones cuantificado (posición vs. VWAP, pendiente de VWAP, momentum sobre
lookback fijo) como plantilla replicable para detectar tendencia/lateralidad en XAUUSD; (b)
circuit breaker "detener tras 2 pérdidas consecutivas en el día" y bloqueo de horario de apertura
(análogo al "wait after market-open gap" ya documentado para XAUUSD en la memoria del programa);
(c) uso de Monte Carlo sobre el histórico de trades para fijar umbrales de drawdown como
kill-switch de monitoreo en vivo — directamente aplicable a la vigilancia de S6/ST en producción,
independientemente de la estrategia de entrada.

**Red flags:** fuerte impulso comercial de prop firms (anuncio insertado a mitad del video con
oferta "$9 challenge", cierre con afiliado "IQ Capital... $1"); la cifra "300% en 4.000+ trades"
la dice el host en la introducción sin que Matteo la reconfirme ni se muestre en pantalla — trátese
con cautela como no verificada; el objetivo declarado de la estrategia (pasar un challenge, no ser
rentable con capital propio) es un incentivo estructural distinto al de un trader/fondo real y
debe tenerse en cuenta al evaluar la seriedad de las cifras de "aprobación" mostradas.

---

## 5. `C_R4sLaM0eo` — vlog de day trading en vivo, cripto (BTC/SOL/ETH), semana de $21.500 (título inferido)

- URL: https://www.youtube.com/watch?v=C_R4sLaM0eo
- Longitud: transcripción de 29 KB / 790 líneas — vlog narrado en tiempo real de una sesión
  completa de trading (crypto spot/futuros), estilo ICT/smart-money discrecional.

**Qué cubre:** Día completo de trading discrecional en criptomonedas (Bitcoin principalmente,
también Solana y Ethereum), combinando sesgo macro de timeframe superior (4h/diario) con entradas
en "fair value gaps" (FVG) y "change of character" (ruptura de estructura de tendencia, concepto
ICT), gestión de parciales y trailing manual del stop siguiendo la estructura de ondas del
mercado. Es un log narrado de 9 operaciones reales de un solo día, no una guía sistemática.

**Reglas/parámetros concretos y citables:**
- Sesgo direccional del día definido por estructura de timeframe superior (4h en BTC) antes de
  buscar entradas en timeframes menores.
- Entradas en niveles de "fair value gap" (hueco de ineficiencia) combinados con "change of
  character" (ruptura de estructura que indica cambio de tendencia) como confirmación.
- Sizing objetivo: arriesgar aproximadamente $1.000 por posición, buscando $3.500-$7.000+ de
  potencial por posición (R:R objetivo >3:1), reconociendo que "solo necesito que esto ocurra
  unas pocas veces" para ser rentable.
- **Regla de gestión de parciales explícita:** al alcanzar 1R de beneficio (1:1 riesgo:recompensa),
  toma 50% de la posición fuera de mercado para asegurar el "risk factor", mueve el stop a
  breakeven en el resto, y deja correr la posición restante siguiendo ("trailing") la estructura de
  ondas de la tendencia — sin fórmula ATR, es discrecional ("wave structure").
- Principio declarado de asimetría: "mantener las pérdidas muy pequeñas y dejar que los ganadores
  corran sin límite" — justifica que incluso 5 pérdidas seguidas después de un ganador grande deja
  la cuenta en zona de rentabilidad.
- Práctica de reducir tamaño de posición cuando entra con incertidumbre ("fui un poco liviano") y
  de añadir a la posición cuando el momentum confirma la dirección.
- No declara ningún límite diario de pérdida ni circuito de parada tras N pérdidas (a diferencia
  de otros videos del lote) — puramente discrecional, incluye admisión explícita de incertidumbre
  ("I don't know how to read these markets, honestly").

**Indicadores:** "diamond indicator" — indicador propietario no divulgado (solo se menciona que da
señales de "switch de sesgo"), sin definición de sus reglas internas; herramienta de position
sizing también propietaria, promocionada vía Instagram, sin especificación técnica. FVG y "change
of character" son los únicos conceptos técnicos explicados con algo de detalle (aunque sin
definición formal de umbral).

**Gestión de riesgo/sizing:** en dólares fijos por posición (~$1.000 de riesgo), no en % de
cuenta declarado. Toma de parciales en múltiplos de R (50% en 1R) es la única regla de salida
cuantificada del video.

**Afirmaciones de resultados:** semana de $21.500 de profit (día mostrado: +$8.592), win rate del
64% que el propio narrador señala como "25% más alto que mi win rate normal" — reconoce
explícitamente que es una semana atípica ("not a normal circumstance"). No se muestra ningún
agregado multi-semana ni broker statement; son cifras narradas sobre la plataforma en pantalla.

**Menciones de zonas S/R, régimen, trailing, XAUUSD:** S/R mencionado explícitamente vía niveles de
"previous day low/high" y zonas de rechazo repetidas; "régimen" no se trata como concepto
formalizado, aunque el narrador comenta cuando el mercado está "choppy" (lateral, sin dirección
clara) y ajusta selectividad. Trailing sí aparece, pero es 100% discrecional ("walk my stop down
into the trend"), sin regla ATR ni multiplicador definido. Ninguna mención de oro/XAUUSD ni forex;
instrumento exclusivamente cripto.

**Qué NO cubre:** definición formal/reproducible del indicador propietario o de "fair value gap"
con umbrales precisos; backtest o estadística agregada fuera de la semana narrada; cualquier regla
de circuito de parada por pérdidas; instrumento fuera de cripto.

**Relevancia a S6/SuperTrend: MEDIUM.** El instrumento (cripto) y el estilo (discrecional, sin
reglas cuantificadas ni backtest) limitan la transferencia directa. Sin embargo, la regla de
gestión de parciales — tomar 50% en 1R, mover a breakeven, dejar correr el resto siguiendo la
estructura de tendencia — es una HIPÓTESIS concreta y testeable de gestión de salida, exactamente
el área de debilidad declarada de S6/SuperTrend. También es relevante como ejemplo cualitativo de
"dejar correr ganadores, cortar rápido perdedores" con métrica de R explícita (1R como punto de
decisión), aunque sin definición ATR-based que sea directamente portable sin adaptación.

**Red flags:** contenido de una sola sesión (n=9 trades) presentada como "semana insana" — sesgo
de selección temporal clásico de contenido de YouTube (se publica la semana buena, no el promedio);
el propio narrador admite la anormalidad del resultado, lo cual mitiga parcialmente el red flag
pero no lo elimina; indicador y herramienta de sizing propietarios no divulgados, con funnel de
marketing hacia Instagram DM; sin verificación externa de cuenta ni de P&L acumulado.

---

## 6. `Fb7G5SNpaes` — "How to Find Profitable Trading Strategies with Claude" (título inferido) — Brendan

- URL: https://www.youtube.com/watch?v=Fb7G5SNpaes
- Longitud: transcripción de 25 KB / 660 líneas — tutorial de metodología, no una estrategia única.

**Qué cubre:** No es una estrategia de trading sino una METODOLOGÍA de investigación: usar Claude
(vía web y Claude Code) para generar, testear, filtrar y combinar en portafolio candidatos de
estrategias de trading multi-activo (ETFs, gold, futuros NQ, cripto), con disciplina de
validación fuera de muestra. Es el video más metodológicamente afín al propio programa (out-of-
sample, costos, anti-look-ahead, stress test, anti-overfitting), aunque genérico y multi-activo,
no específico de XAUUSD M15.

**Reglas/parámetros concretos y citables:**
- Metodología de testing en 3 reglas obligatorias declaradas en el prompt: (1) **split de datos**
  in-sample (en su caso 2010-2022, usado para construir/elegir estrategias) vs. out-of-sample
  sellado (2023-hoy, usado SOLO para puntuar al final); (2) **costos siempre activos** — comisiones,
  financiamiento de apalancamiento, dividendos, slippage modelado según volumen de operaciones;
  (3) **prohibido ver el futuro** — decisión se toma con el cierre de ayer, se opera en la apertura
  siguiente (elimina look-ahead bias).
- Proceso de filtrado en cascada: de 155 ideas candidatas generadas por el LLM, tasa de
  supervivencia tras el test out-of-sample sellado fue ~3% (5 estrategias sobrevivientes).
- Filtros adicionales de robustez tras la supervivencia inicial (3 checks): (a) **stress test en la
  peor década histórica** disponible (2000-2009: dot-com + crisis financiera) — eliminó casi todas
  las estrategias que solo funcionaban en regímenes fáciles (ejemplo dado: un QQQ apalancado tuvo
  85% de drawdown en esa década); (b) **consistencia de familia** — el vecindario de parámetros
  cercanos también debe funcionar, no solo la combinación puntual óptima; (c) **plateau test** —
  solo confiar en un parámetro optimizado si el desempeño es suave en el entorno de configuraciones
  vecinas Y el ranking en datos de entrenamiento coincide aproximadamente con el ranking en datos
  de test (chequeo directo anti-overfitting/anti-curve-fitting).
- 5 estrategias finales sobrevivientes (ejemplos concretos con reglas y cifras exactas):
  1. **Trend core (gold/QQQ switch):** si QQQ > su media móvil de 200 días, mantener QQQ; si no,
     mantener oro. ~5 operaciones/año. Resultado en ventana de test: 33.8%/año, Sharpe 1.66
     (validado sobre 50 años de historia dado el bajo número de operaciones/año).
  2. **Momentum rotation:** mensualmente, mantener las 5 ETFs de un universo de 50 más cercanas a
     su máximo de 52 semanas; ir a cash cuando SPY < su media móvil de 200 días.
  3. **Dip buyer en SPY:** comprar cuando el cierre cae en el 10% inferior del rango del día Y el
     índice sigue por encima de su media de 200 días; salir en un cierre fuerte o tras 3 días
     (time stop explícito).
  4. **NQ opening range breakout:** operar la ruptura del rango de los primeros 30 minutos de
     sesión.
  5. **Capa de sizing a nivel de portafolio:** escalar posiciones para mantener el portafolio en
     ~20% de volatilidad objetivo.
- Combinación en portafolio: no añade señal nueva — pondera las estrategias sobrevivientes según su
  correlación cruzada para suavizar la curva de equity conjunta (diversificación, no alpha
  adicional).
- Reglas de apagado ("shutoff rules") antes de operar en vivo: detener nuevas entradas y alertar si
  el desempeño rodante cae por debajo de lo que produciría entrada aleatoria, o si el drawdown
  supera el peor drawdown visto en backtest — chequeo diario.
- Afirmación específica sobre el comportamiento del activo oro: **"Gold trends, it barely mean
  reverts"** (declarado como premisa de diseño para elegir qué tipo de estrategia aplicar a cada
  activo — SPY/QQQ sí revierten a la media en pocos días, oro no).

**Indicadores:** ninguno propio de la estrategia de gold/QQQ (solo media móvil de 200 días);
"opening range breakout" de 30 min para NQ; percentil de rango diario para el dip-buyer de SPY.

**Gestión de riesgo/sizing:** capa de volatilidad objetivo (~20%) a nivel de portafolio; límites
duros recomendados para el bot en vivo — cap de tamaño de posición, cap de posiciones concurrentes,
kill switch automático; recomienda paper trading 1-2 meses antes de capital real.

**Afirmaciones de resultados:** 33.8%/año y Sharpe 1.66 para la estrategia gold/QQQ en ventana de
test (no se muestra la curva de equity cruda ni el desglose de drawdown en la transcripción,
aunque el proceso declarado de validación —split OOS + stress test en década difícil + plateau
test— es notablemente más riguroso que el resto del lote).

**Menciones de zonas S/R, régimen, trailing, XAUUSD:** menciona XAUUSD (gold) explícitamente como
activo con comportamiento de tendencia dominante y reversión a la media mínima — dato de contexto
relevante y coherente con el diseño de S6/SuperTrend como estrategias de tendencia sobre oro. No
hay ATR ni trailing técnico definido; "régimen" se trata a nivel de década/macro-periodo (stress
test en 2000-2009) más que de régimen intradía/lateral. Menciona explícitamente que "el trend
strategy struggles cuando el mercado está choppy" y que el dip-buyer rinde mejor en esas
condiciones — reconoce el problema de régimen lateral sin dar un umbral medible para detectarlo en
tiempo real.

**Qué NO cubre:** cualquier regla de entrada/salida específica para M15 o intradía en oro; gestión
de trailing stop; consideración explícita del problema de comparaciones múltiples/data snooping al
testear 155 candidatos simultáneamente (mitigado parcialmente por el split OOS y el plateau test,
pero no discutido como tal); spread o costos específicos de FX/CFD.

**Relevancia a S6/SuperTrend: MEDIUM — pero ALTA relevancia metodológica para el programa.** No
aporta reglas de entrada/salida de oro M15, pero sí: (a) confirma la premisa de que oro es un
activo de tendencia con reversión a la media mínima, coherente con el enfoque de S6/ST; (b) el
protocolo de validación (split IS/OOS sellado, stress test en el peor régimen histórico disponible,
plateau test anti-overfitting, kill-switch de monitoreo en vivo) es directamente análogo a los
principios ya adoptados en el CHARTER del programa (holdout sagrado, motor congelado, anti-drift) y
puede usarse como referencia cruzada al validar hallazgos de S6/ST; (c) el concepto de portafolio
de estrategias no correlacionadas (mezclar S6/ST tendencial con algo que rinda en lateral) es
coherente con la brecha de régimen que el programa ya identificó como debilidad.

**Red flags:** fuerte autopromoción (comunidad propia de pago en Skool); las cifras de desempeño
(33.8%/año, Sharpe 1.66) no se muestran con curva de equity ni tabla cruda en la transcripción, solo
narradas sobre un dashboard no verificable desde el texto; el problema de comparaciones múltiples al
generar 155 candidatos y filtrar a 5 no se aborda explícitamente como riesgo de data snooping,
aunque el proceso descrito (OOS + stress test + plateau) mitiga parcialmente ese riesgo.

---

## 7. `fV02FcLmFpA` — "10 Brutal Truths of Trading" — Doug, 26 años como trader (título inferido)

- URL: https://www.youtube.com/watch?v=fV02FcLmFpA
- Longitud: transcripción de 24 KB / 639 líneas — monólogo motivacional, sin gráficos ni datos.

**Qué cubre:** Contenido puramente de mentalidad/disciplina, sin estrategia de entrada/salida, sin
instrumento definido (implícitamente acciones, "shares"), sin backtest ni cifras verificables.
Once "lecciones" genéricas: simplicidad, especializarse en un solo activo, horas de pantalla,
tamaño de posición ligado a ansiedad, no mirar el P&L intradía, aceptar pérdidas "buenas" vs.
"malas", sistema de ranking de calidad de setup, journaling, reglas de circuito, mentoría.

**Reglas/parámetros concretos y citables (escasas, y todas subjetivas/sin umbral medible salvo
las marcadas):**
- Sistema de ranking de convicción en 3 niveles (subjetivo, sin criterio objetivo de clasificación):
  Tier 1 = setup con ~85%+ de win rate estimado por el propio trader → "debe tomarse", máximo
  riesgo permitido; Tier 2 = ~70-75% de win rate estimado → se toma pero sin sobre-apalancar; Tier
  3 = ~50/50 → se descarta, "ya no pierdo tiempo con esas".
- Sizing de posición ajustado hasta el punto donde deja de generar ansiedad ("si tienes ansiedad
  con 100 acciones, baja a 70, 50, 40, 30, 10, 5... hasta que no te preocupe") — regla puramente
  subjetiva, sin fórmula.
- **Circuit breaker declarado: tras 3 operaciones perdedoras seguidas, reducir actividad o tomarse
  el día libre.**
- "GTFO number" — umbral personal de pérdida máxima (diaria o de cuenta, no especifica cuál) al
  cual se detiene toda operación sin excepción — el propio autor no da la cifra, solo el principio.
- Distingue pérdida "aceptable" (siguió el plan, setup A+, fue detenido por azar del mercado) de
  "inaceptable" (revenge trading, trading emocional) — sin criterio objetivo de clasificación más
  allá del auto-reporte.
- Recomienda journaling exhaustivo de cada operación y revisión semanal con un objetivo de mejora
  puntual (entradas, paciencia en salidas, tamaño).

**Indicadores:** ninguno. Recomienda explícitamente empezar SIN indicadores — solo price action,
soporte/resistencia genérico y "box theory" (sin definir esta última).

**Gestión de riesgo/sizing:** ver arriba — sin ninguna cifra objetiva de % de cuenta o unidades;
todo el marco es cualitativo/introspectivo.

**Afirmaciones de resultados:** "he hecho millones y millones de dólares... haciendo un solo trade
sencillo cada día" — sin ninguna cifra, cuenta, ni evidencia mostrada; anécdota de que su esposa
"empezó con 7 euros y lo logró" — sin verificación ni detalle.

**Menciones de zonas S/R, régimen, trailing, XAUUSD:** soporte/resistencia mencionado solo como
concepto genérico de nivel de entrada para principiantes, sin definición operacional. Sin ATR, sin
trailing, sin régimen formalizado, sin mención de oro/XAUUSD ni forex.

**Qué NO cubre:** absolutamente ninguna regla de entrada, salida, indicador o instrumento
específico; ningún dato de backtest o track record verificable.

**Relevancia a S6/SuperTrend: LOW.** Es el video de menor contenido técnico del lote — pura
mentalidad y disciplina sin ninguna regla de mercado aplicable. Lo único mínimamente testeable
como HIPÓTESIS genérica de gestión de riesgo es el circuit breaker de "3 pérdidas consecutivas →
pausa", que ya aparece de forma más precisa y con más contexto cuantitativo en otros videos del
lote (`ksVXut9bSSg`, `wm4A6qo0g3I`).

**Red flags:** cero datos, cero backtest, cero cifra verificable; afirmaciones de resultados
("millones y millones de dólares", esposa con €7) sin ninguna evidencia; cierre del video con
autopromoción de su propio "live trading room" de pago ("Rumors Squad"); estructura y tono de
contenido motivacional/venta de comunidad, no de educación técnica.

---

---
