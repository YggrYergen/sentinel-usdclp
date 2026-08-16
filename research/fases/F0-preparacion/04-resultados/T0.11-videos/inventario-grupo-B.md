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

---
