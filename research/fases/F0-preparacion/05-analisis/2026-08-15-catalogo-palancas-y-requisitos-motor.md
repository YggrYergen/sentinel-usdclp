# Catálogo de palancas y requisitos de motor — T0.10/T0.11 → grilla del programa

**Etapa:** F0 · **Fecha:** 2026-08-15 · **Branch:** `equipo1` · **Autor:** controlador:opus5 (documento único, no código)

## Cómo leer este documento

Insumo de entrada para el controlador; no crea tareas ni modifica `TRACKER.md`/`LEDGER.jsonl`/
`DECISIONES.md`. Cada palanca (`P-01`…`P-33`) trae su origen exacto, su grado de evidencia **tal
como lo asignó la fuente** (nunca subido de grado aquí), su estatus frente al plan
`docs/superpowers/plans/2026-08-10-plan-investigacion-integral-v4.md` (en adelante "el plan"), y
el requisito de motor concreto que la hace medible. Ninguna palanca fue inventada: toda idea propia
del redactor que no traza a una fuente en disco vive en la Parte 4, marcada explícitamente como
inferencia.

**Distinción importante que se sostiene en todo el documento:** los 26 videos de YouTube
procesados (12 del Grupo A, 9 del Grupo B — 5 videos de A/B quedaron sin leer por corte de
presupuesto del user, D-49) traen una etiqueta de **relevancia** (HIGH/MEDIUM/LOW) asignada por el
agente que los revisó, NO un **grado de evidencia** académico. Salvo un caso (`KML09tRtHM8`, un
backtest de 25.000 configuraciones con walk-forward y holdout, metodológicamente serio aunque no
arbitrado), el resto de los videos son testimonios de traders discrecionales sin backtest auditado,
con red flags de sesgo de selección/supervivencia declarados en el propio inventario. Por eso **toda
palanca de origen exclusivamente-video se grada LOW (folklore/practitioner no auditado)** aunque su
relevancia haya sido marcada HIGH — relevancia y rigor son ejes distintos, y el Charter §A.4
prohíbe convertir un hallazgo en veredicto.

---

# Parte 1 — Catálogo de palancas

## Bloque Salidas / trade-management (Área 1 de literatura formal)

### P-01 — SL adaptativo por ficha vía meta-labeling (confianza de entrada)
- **Mecanismo:** entrenar un clasificador sobre features de contexto de entrada (pendiente EMA8,
  nivel AC, nº de osciladores favorables, percentil ATR14, hora) para predecir `p_profit`; usar
  `p_profit` para modular el ancho del SL por ficha (F1 más ajustado si `p_profit` bajo, F3 siempre
  más suelto).
- **Estrategia:** S6 (y por extensión S7, mismo gate).
- **Origen:** `T0.10-literatura/area-1-exits-optimal-stopping.md` Rule Set A, citando López de Prado
  (2018) triple-barrier/meta-labeling y Pardo (2008) MFE/MAE.
- **Evidencia:** HIGH (practitioner-grade, sin RCT formal — grado asignado por la fuente).
- **Estatus:** EXTENSION. No hay meta-labeling en el plan hoy; Familia G (§7) declara el meta-labeling
  como **techo** del embudo ("features validadas → meta-labeling"), es decir, el plan ya lo prevé
  como destino final, pero condicionado a que features individuales sobrevivan S0 primero (Familia G,
  regla: "solo entran a composición features que INDIVIDUALMENTE sobrevivieron S0").
- **Requisito de motor:** requiere el snapshot de contexto de entrada por posición (mod #11,
  instrumentación de camino) YA especificado en el plan §4.1; requiere además un hook de SL
  parametrizado por `p_profit` (no existe hoy — SL es una fórmula fija de rango×k). Nuevo: **decisión
  hook de SL condicional a un score externo**.
- **Grid:** SL_F1 = `2.5×rango × (0.8 + 0.4×p_profit)`; SL_F2 = `×(1.0+0.2×p_profit)`; SL_F3 =
  `×(1.2+0.0×p_profit)` (valores de ejemplo de la fuente, no fijos — el score y los coeficientes se
  calibran contra el sustrato reparado).
- **Métrica/criterio:** Sharpe out-of-sample mejora Y max-DD no empeora, sobre la MISMA malla de
  entradas (ver paridad abajo).
- **Pareado-por-entrada:** YES (solo cambia el ancho de SL por ficha, no la señal de entrada).
- **Conflictos:** depende de que Familia G y S0 (screening de features) ya hayan corrido; depende de
  mod #11.

### P-02 — Time-stop por edad de la señal (decaimiento de alfa)
- **Mecanismo:** medir la correlación entre la señal de entrada y el retorno a 5 barras, estratificado
  por barras-desde-entrada; si decae significativamente tras N barras, forzar cierre a mercado a esa
  edad.
- **Estrategia:** S6, S7 (Rule Set B); análogo para SuperTrend (Rule Set F, ver P-06).
- **Origen:** `area-1-exits-optimal-stopping.md` Rule Set B, citando Campbell/Lo/MacKinlay (1997) y
  Chernoff (1972).
- **Evidencia:** MEDIUM (teoría rigurosa, aplicación práctica sin ensayo previo).
- **Estatus:** YA-EN-PLAN. Plan §7 Familia B6 "Time-stop: `max_hold_bars` derivado de curva
  expectancy-vs-barras" — mecanismo idéntico, ★ campeón de granularidad extendida (§6 del
  matrix histórico, y §7 del plan). **Cuidado de reconciliación:** §12 del plan trae un ítem 🟡 TAREA
  "`max_hold_bars=64` confound — re-correr suite PX SIN max_hold + controles 64/48 solos" —
  cualquier corrida de P-02 debe controlar por ese confound conocido, no asumir que 64 es neutral.
- **Requisito de motor:** ya cubierto — `max_hold_bars` existe como parámetro (`emasar_variant.py`,
  hoy `None`/deshabilitado para S6/S7). No requiere mod nuevo más allá de exponerlo en el harness
  pareado (mod #1).
- **Grid:** {10, 15, 20, 30} barras (fuente); reconciliar con la grilla ya declarada del plan
  (`{off, N1, N2, N3}` guiada por la curva expectancy-vs-barras, §6 del matrix histórico).
- **Métrica/criterio:** ¿las posiciones cerradas por time-stop son predominantemente perdedoras
  (buena poda) o ganadoras (upside perdido)? Decide por expectancy condicional, no solo P&L agregado.
- **Pareado-por-entrada:** YES.
- **Conflictos:** P-04 (hazard-exit) puede subsumir esto si el hazard ya captura la decadencia de
  recuperación; correr ambos y comparar, no asumir dominancia.

### P-03 — Barrido de umbral/lookback del apriete por desaceleración de AC
- **Mecanismo:** el S6 vivo YA tiene AC-modulate (aprieta trail a 0.25× cuando AC desacelera contra la
  dirección favorable); la fuente pide validar el TRIGGER en sí — barrer el umbral de "desaceleración"
  en pips y el lookback de 1 vs 2 barras, y cuánto tiempo mantener el apriete.
- **Estrategia:** S6.
- **Origen:** `area-1-exits-optimal-stopping.md` Rule Set C, citando Sweeney (1986).
- **Evidencia:** MEDIUM (mixta — empírico general, no validado sobre esta forma exacta).
- **Estatus:** YA-EN-PLAN parcial. Plan §7 Familia B★ ya trae `AC-modulate {off, 0.25, 0.5}` como
  factor de grilla — pero eso es el FACTOR de apriete, no el UMBRAL/lookback del trigger de
  desaceleración en sí, que hoy es fijo en código. La parte del umbral/lookback es EXTENSION sobre
  una familia ya abierta.
- **Requisito de motor:** exponer el umbral de desaceleración AC y su lookback como parámetros
  (hoy hardcoded en `emasar_ref.py` — `ac_desacelerando`). Nuevo parámetro sweepable, effort LOW.
- **Grid:** umbral tightening {25, 50, 75} pips × lookback {1, 2} barras × duración del apriete {3,
  5, 10} barras (fuente).
- **Métrica/criterio:** % de re-flips falsos tras el apriete (costo de whipsaw) vs. P&L medio por
  trade.
- **Pareado-por-entrada:** YES.
- **Conflictos:** ninguno directo; complementa B★.

### P-04 — SL condicionado a hazard de recuperación desde MAE
- **Mecanismo:** para cada ficha abierta, calcular la tasa histórica de recuperación desde la
  profundidad MAE actual (¿qué fracción de posiciones que tocaron X pips en contra recuperó en N
  barras?); si la tasa es alta, ensanchar el SL; si es baja, forzar salida.
- **Estrategia:** S6, S7 (y aplicable conceptualmente a ST si se define "recuperación" sobre el flip).
- **Origen:** `area-1-exits-optimal-stopping.md` Rule Set D, citando Cox (1972) y Kiefer (1988)
  (supervivencia/hazard, competing risks).
- **Evidencia:** MEDIUM (teoría rigurosa + practitioner MFE/MAE de Pardo).
- **Estatus:** YA-EN-PLAN. Plan §5.3 "Análisis de recuperación: curvas de supervivencia — P(recuperar
  | profundidad MAE, tiempo bajo agua, régimen). Insumo directo de salidas por hazard (B9)" y Familia
  B9 "hazard-exit (salir si P(recuperación|estado) < umbral, de §5.3)". Coincide exactamente.
- **Requisito de motor:** las curvas de supervivencia son un PRODUCTO de la Autopsia §5 (necesita
  mod #11 de instrumentación de camino, YA especificado); el hook de salida condicional al hazard es
  un decision-hook nuevo (no existe hoy ninguna forma de "consultar una tabla de recuperación" en
  runtime del backtest).
- **Grid:** buckets de MAE {10, 20, 30 pips} × ventana de recuperación {5, 10, 15, 20 barras} ×
  umbral de tasa {50%, 60%, 70%} (fuente).
- **Métrica/criterio:** reducción de la pérdida máxima por trade sin recortar el tamaño medio de
  ganadora recuperable.
- **Pareado-por-entrada:** YES.
- **Conflictos:** depende de §5 Autopsia completa (bloqueante, per plan §8 DAG); comparte insumo con
  P-02.

### P-05 — Barrido del multiplicador ATR de SuperTrend
- **Mecanismo:** el multiplicador 3.0 de SuperTrend no tiene derivación en literatura ("probablemente
  ajustado en un solo mercado" — flag explícito de folklore de la propia fuente); barrer el
  multiplicador y medir el trade-off whipsaw↔give-back.
- **Estrategia:** ST.
- **Origen:** `area-1-exits-optimal-stopping.md` Rule Set E, folklore explícitamente marcado en §3.2
  ítem 6 ("ATR multiplier de 3.0 es óptimo" → Folklore).
- **Evidencia:** MEDIUM (práctica común, sin derivación).
- **Estatus:** YA-EN-PLAN. Plan §7 Familia B7d: `mult {2.0..3.5}` ★ óptimo interior — idéntico.
- **Requisito de motor:** ya soportado (parámetro existente `_ST_MULT`, solo falta exponerlo al
  harness de barrido).
- **Grid:** {2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0} (fuente) vs. {2.0, 2.5, 3.0, 3.5} extensible a paso
  0.25 (plan) — usar la unión, con regla de meseta (Charter §9) para decidir si extender más allá de
  3.5.
- **Métrica/criterio:** Sharpe, nº de flips, max pérdidas consecutivas.
- **Pareado-por-entrada:** NO — el multiplicador determina la línea SuperTrend, que ES la señal de
  flip (entrada); cambia el conjunto de entradas, no solo la salida.
- **Conflictos:** interactúa con P-07 (ATR period adaptativo) — no correr ambos como "on" simultáneo
  sin sondeo de interacción explícito.

### P-06 — Time-stop de whipsaw tras flip de SuperTrend
- **Mecanismo:** si ocurre un segundo flip dentro de N barras del anterior, cerrar la segunda posición
  a mercado sin esperar el SL (los flips consecutivos sugieren régimen choppy de baja convicción).
- **Estrategia:** ST.
- **Origen:** `area-1-exits-optimal-stopping.md` Rule Set F, citando Campbell et al. (1997).
- **Evidencia:** LOW ("not validated on ST" — grado asignado explícitamente por la fuente, el más
  bajo de las 8 rule-sets del área).
- **Estatus:** YA-EN-PLAN. Plan §7 Familia B7a: "romper always-in con multi-definición de plano:
  {flip-count K barras, ...} × 3 umbrales c/u" — el "flip-count K barras" es exactamente esto.
- **Requisito de motor:** decision-hook nuevo para ST (hoy no existe ningún mecanismo de suprimir/
  forzar cierre post-flip fuera de la línea SuperTrend misma).
- **Grid:** N ∈ {2, 3, 5} barras (fuente) × 3 umbrales (plan, sin fijar).
- **Métrica/criterio:** reducción de drawdown por ciclos de whipsaw.
- **Pareado-por-entrada:** YES (cierra posiciones ya abiertas antes de tiempo; no cambia el flip que
  las originó).
- **Conflictos:** relacionado con P-22 (detección de crash de momentum) — ambos actúan sobre
  secuencias de flips, definir precedencia si se combinan.

### P-07 — Período ATR adaptativo por régimen de volatilidad (SuperTrend)
- **Mecanismo:** en vez de ATR(14) fijo, usar ATR(p) donde p varía con el percentil de volatilidad
  reciente (p.ej. p=20 en vol baja, p=10 en vol alta).
- **Estrategia:** ST.
- **Origen:** `area-1-exits-optimal-stopping.md` Rule Set G, citando Sweeney (1986) y Kaufman (2013).
  La propia fuente estima "ganancia marginal probablemente < 2% Sharpe".
- **Evidencia:** MEDIUM (practitioner).
- **Estatus:** EXTENSION sobre una familia YA-EN-PLAN parcial. El plan solo trae el período ATR como
  factor ESTÁTICO (Familia B7d: `ATR period {7,10,14,21}`); la variante donde el período CAMBIA
  dinámicamente por régimen dentro de la misma corrida es nueva.
- **Requisito de motor:** requiere que el cálculo de ATR de ST pueda leer un período variable por
  barra desde un detector de régimen — depende de que P-09/P-10 (regime filter) ya calculen ese
  estado. Nuevo: parámetro compuesto (función de régimen → período), no solo un escalar.
- **Grid:** período base {12, 14, 16} × período lo-vol {base+4, base+6} × período hi-vol {base−2,
  base−4} (fuente).
- **Métrica/criterio:** Sharpe, con umbral mínimo de mejora dado el propio caveat de bajo impacto
  esperado de la fuente — no gastar presupuesto de grilla fina aquí sin señal previa positiva.
- **Pareado-por-entrada:** NO (el período ATR determina la línea/flip, igual que P-05).
- **Conflictos:** P-05 (no correr ambos simultáneamente sin sondeo de interacción); depende de P-09.

### P-08 — Offset de SL consciente de calidad de fill (compensación de spread del bróker)
- **Mecanismo:** sumar un buffer al nivel de SL de SuperTrend para compensar el slippage esperado del
  bróker en el fill del stop.
- **Estrategia:** ST.
- **Origen:** `area-1-exits-optimal-stopping.md` Rule Set H, citando Hasbrouck (2007). La propia fuente
  lo marca como "band-aid; mejor arreglo es lógica de entrada, no de salida".
- **Evidencia:** MEDIUM (teoría + dato de slippage propio).
- **Estatus:** EXTENSION. No hay ningún factor de "offset de SL por slippage esperado" en el plan; lo
  más cercano es A4 (expectancy condicional al spread) y el overlay de costos por bróker (mod #10),
  que mide el efecto pero no ofrece un lever de compensación activa.
- **Requisito de motor:** parámetro nuevo (offset constante o función del spread vigente) aplicado al
  SL antes de enviarlo al reconciler.
- **Grid:** {0.00, 0.10, 0.20, 0.30} USD (fuente).
- **Métrica/criterio:** reducción de "casi-tocados-no-rellenados" vs. aumento de falsos triggers por
  SL más ancho — medir ambos lados.
- **Pareado-por-entrada:** YES.
- **Conflictos:** depende de A6/A4 (medición de slippage real) para calibrar el offset con datos
  propios en vez de valores arbitrarios de la fuente.

## Bloque Régimen / lateralidad (Área 2 de literatura formal)

### P-09 — Filtro de régimen compuesto k-de-m {ADX, Variance Ratio, Efficiency Ratio, Choppiness Index}
- **Mecanismo:** puntuar 4 indicadores de régimen (cada uno con su umbral) y exigir que ≥3 de 4
  coincidan en "tendencial" antes de permitir entradas de S6 o flips de ST.
- **Estrategia:** S6 (gate de entrada), ST (supresión de flip).
- **Origen:** `area-2-regime-lateralidad.md` §2.4, citando Wilder (1978, ADX), Lo & MacKinlay (1988,
  VR), Kaufman (1995+, ER), Hutson (Choppiness).
- **Evidencia:** MIXTA POR COMPONENTE, no promediable — el propio documento fuente separa: VR = HIGH
  (rigurosa, revisada por pares); ER = MEDIUM (metódica, sin revisión por pares); ADX = LOW
  (heurística, "usar con cautela, NO depender solo de ella"); Choppiness = LOW ("folklore/no
  verificado, evitar como filtro primario"). El compuesto hereda la evidencia de su componente más
  débil salvo que se pese explícitamente — no se sube de grado por combinarlos.
- **Estatus:** YA-EN-PLAN. Plan §7 Familia D3: "familias de régimen COMPLETAS, SIN representante
  único... ADX {umbrales×períodos} · CHOP {nivel × pendiente} · Variance-Ratio · Hurst · HMM"; y
  explícitamente: "la colinealidad ADX≈CHOP≈ER se MIDE primero como resultado, no se asume" — ER
  también está nombrado. Coincide con los 4 componentes de esta palanca.
- **Requisito de motor:** las 4 series de indicador (ADX, VR, ER, CI) deben calcularse por barra y
  quedar disponibles como gate — ninguna existe hoy en el motor. Nuevo cómputo × nuevo hook de
  entrada condicional (S6) y de supresión de flip (ST).
- **Grid:** ADX período {14,21,28}×umbrales{15,20,25}/{25,30,35}; VR lag{3,5,7,10}×ventana{60,100,
  150,200}×umbrales{0.90-1.15}; ER N{10,15,20,30}×umbrales{0.30-0.70}; CI N{10,14,20,30}×umbrales
  {35-40}/{60-65}; compuesto: umbral de acuerdo {2,3} de 4 (todos de la fuente).
- **Métrica/criterio:** expectancy condicional por bucket de régimen con IC que excluye 0 (regla de
  decisión del plan §6 S0), antes de comprometerse a la grilla completa.
- **Pareado-por-entrada:** NO — es un gate de entrada, cambia qué señales se toman.
- **Conflictos:** con P-10/P-11/P-12 — la colinealidad entre indicadores de régimen se mide primero
  (mandato explícito del plan), no se asume redundancia ni complementariedad a priori.

### P-10 — Régimen por Hidden Markov Model (2-4 estados)
- **Mecanismo:** entrenar un HMM sobre {retorno, volatilidad GARCH, ADX} para inferir probabilidad de
  estado "tendencial" en cada barra; gatear entradas si P(tendencial) > 0.7.
- **Estrategia:** S6, ST.
- **Origen:** `area-2-regime-lateralidad.md` §1.4, §2.3, citando Hamilton (1989) y Guidolin & Timmermann
  (2007).
- **Evidencia:** HIGH (rigurosa, revisada por pares, con aplicación empírica documentada en la fuente).
- **Estatus:** YA-EN-PLAN. Plan §7 Familia D3 nombra HMM explícitamente junto a ADX/CHOP/VR/Hurst.
- **Requisito de motor:** requiere entrenamiento de un modelo estadístico (no solo una fórmula
  cerrada como los demás indicadores) — dependencia externa (`hmmlearn` o equivalente), complejidad
  MEDIA per la fuente. Nuevo cómputo, el más costoso de implementar del bloque régimen.
- **Grid:** nº de estados {2,3,4}; features de observación {retorno, GARCH-vol, ADX}; umbral de
  gate {0.6, 0.7, 0.8} (umbral no fijado por la fuente, inferido de la regla dada, marcar a definir).
- **Métrica/criterio:** igual regla que P-09 (expectancy condicional + IC).
- **Pareado-por-entrada:** NO.
- **Conflictos:** ver P-09.

### P-11 — Régimen por exponente de Hurst (R/S rescalado)
- **Mecanismo:** clasificar tendencial (H>0.6) vs. mean-reverting (H<0.4) vs. random-walk (H≈0.5) vía
  análisis R/S.
- **Estrategia:** S6, ST.
- **Origen:** `area-2-regime-lateralidad.md` §1.2, citando Hurst (1951)/Peters (1991), con la crítica
  peer-reviewed de Lo (1991) que demuestra sesgo severo en muestras finitas.
- **Evidencia:** LOW/controversial — la propia fuente lo marca "Avoid. R/S analysis is biased for
  finite samples... not recommended for real-time trading" salvo con estimadores corregidos por sesgo
  (Anis & Lloyd).
- **Estatus:** YA-EN-PLAN, con esta MISMA reserva ya presente en el plan. Familia D3 nombra Hurst
  explícitamente en la grilla de régimen; el plan no descarta probarlo, pero esta palanca documenta
  que la fuente académica recomienda NO usarlo sin corrección de sesgo — si se corre, debe ser con
  el estimador Anis & Lloyd, no el R/S ingenuo.
- **Requisito de motor:** cómputo de Hurst por ventana rodante con estimador corregido por sesgo
  (más caro que el R/S naive que muchas librerías ofrecen por defecto — riesgo de implementación
  incorrecta si se usa la fórmula ingenua).
- **Grid:** ventana rodante {no especificada por la fuente — a definir con causa}; umbrales {H<0.4,
  H≈0.5, H>0.6} (fuente).
- **Métrica/criterio:** igual que P-09; además, comparar el estimador corregido vs. el naive para
  cuantificar el sesgo denunciado por Lo (1991) sobre el propio sustrato de XAUUSD M15 antes de
  confiar en el resultado.
- **Pareado-por-entrada:** NO.
- **Conflictos:** ver P-09; alta probabilidad de resultar descartado en el screening S0 (§6 del plan)
  dado el bias conocido — no es candidato de grilla fina.

### P-12 — Marcador de régimen de volatilidad GARCH(1,1)
- **Mecanismo:** ajustar GARCH(1,1) en ventana rodante; volatilidad en expansión = probable
  tendencial, en contracción = probable choppy.
- **Estrategia:** S6, ST (marcador secundario, no gate primario).
- **Origen:** `area-2-regime-lateralidad.md` §1.5, citando Engle (1982).
- **Evidencia:** HIGH (rigurosa, revisada por pares — teoría fundacional de econometría financiera),
  pero la propia fuente la posiciona como "marcador SECUNDARIO", no primario.
- **Estatus:** EXTENSION. El plan usa ATR (no GARCH) como proxy de volatilidad en toda la Familia D3
  ("ATR re-exploración... multi-TF"); GARCH no está nombrado en ningún punto del catálogo de
  familias §7. Es un cómputo estadístico distinto (varianza condicional autorregresiva) del ATR
  (rango verdadero suavizado), con propiedades diferentes de reacción a clusters de volatilidad.
- **Requisito de motor:** ajuste GARCH(1,1) por ventana — dependencia de librería estadística (no
  trivial en el motor actual, que es aritmética directa sobre barras). Nuevo cómputo, effort MEDIO.
- **Grid:** no fijada por la fuente más allá del concepto (ventana de ajuste, umbral de expansión/
  contracción) — a definir con causa antes de correr.
- **Métrica/criterio:** correlación entre el marcador GARCH y el régimen detectado por VR/HMM
  (validación cruzada de régimen, no solo P&L) antes de usarlo como gate.
- **Pareado-por-entrada:** NO (si se usa como gate); YES si se usa solo como covariable de sizing.
- **Conflictos:** con P-09/P-10 — mismo rol (detección de régimen), medir colinealidad antes de sumar
  al compuesto.

## Bloque Sizing / riesgo / equity-curve (Área 3 de literatura formal)

### P-13 — Kelly fraccional (0.25×–0.5×) obligatorio dado DSR≈0
- **Mecanismo:** estimar Kelly teórico `f* = (w·W − (1−w)·L)/W` de los últimos ~100 trades; aplicar
  solo una fracción (0.25× para S6 dado DSR≈0, 0.5× para ST) como tamaño práctico.
- **Estrategia:** S6, ST (fracciones distintas).
- **Origen:** `area-3-sizing-riesgo-equity.md` §2.1, citando Kelly (1956), MacLean/Thorp/Ziemba (2011),
  Ziemba & MacLean (2017).
- **Evidencia:** HIGH ("Strong. Peer-reviewed, multiple case studies, simulation-backed" — grado de la
  fuente).
- **Estatus:** EXTENSION. Ningún factor de sizing por Kelly aparece en el catálogo §7 del plan (las
  únicas menciones de sizing son "Vol-targeting" en S6/S7 factor 12 y ST factor 5, y E5 "pesos NO
  optimizados equal-weight/inversa-vol" para ensambles — ninguna es Kelly). Genuino hueco del plan
  actual: no hay familia de sizing por criterio de crecimiento óptimo.
- **Requisito de motor:** hook de sizing nuevo — hoy el motor no tiene ningún mecanismo para escalar
  el volumen de una orden en función de estadística histórica de la propia estrategia. Nuevo decision
  hook: "position-size multiplier", parametrizado.
- **Grid:** fracción α ∈ {0.25, 0.5, 1.0 como baseline full-Kelly} (fuente).
- **Métrica/criterio:** reducción de max-DD y de episodios de ruina simulados vs. Kelly completo,
  sobre el MISMO stream de entradas/salidas ya decidido.
- **Pareado-por-entrada:** YES (multiplica el tamaño, no cambia qué se abre ni cuándo se cierra).
- **Conflictos:** con P-15 (descuento por correlación de portafolio) — orden de aplicación importa
  (Kelly individual primero, descuento de correlación después, según la fuente).

### P-14 — Sizing inverso al ATR14 (volatility targeting)
- **Mecanismo:** `lot_scaled = base_lot × (ATR14_mediano_histórico / ATR14_actual)`, con cap
  {0.67–1.5} o {0.50–2.0}.
- **Estrategia:** S6, S7, ST.
- **Origen:** `area-3-sizing-riesgo-equity.md` §2.2, citando Blitz et al. (2021) y Turnbull (2012).
- **Evidencia:** HIGH ("Strong. Multi-asset empirical study; ~15–25% DD reduction documented").
- **Estatus:** YA-EN-PLAN, en cuarentena temporal por diseño. Plan §7 factor 12 (S6/S7) y factor 5
  (ST): "Vol-targeting {fijo, vol-target} + vol-objetivo {baja,media,alta}". Familia E5 declara
  explícitamente: "**Vol-targeting: AL FINAL del programa** (rompería comparabilidad antes)" — es
  decir, el plan YA decidió diferir esta palanca a propósito, no por omisión.
  **No ejecutar antes de lo que el plan indica** sin enmienda.
- **Requisito de motor:** hook de sizing (mismo tipo que P-13) — comparten la misma infraestructura
  nueva.
- **Grid:** cap {0.67–1.5} vs {0.50–2.0} (fuente) — reconciliar con "vol-objetivo {baja,media,alta}"
  del plan.
- **Métrica/criterio:** reducción de max-DD y mejora de Sharpe, medida DESPUÉS de que el resto del
  programa esté comparable (por diseño del plan).
- **Pareado-por-entrada:** YES.
- **Conflictos:** explícitamente pospuesta por el plan — cualquier ejecución anticipada requiere
  enmienda formal (Charter §A.10).

### P-15 — Kelly de portafolio con descuento por correlación (60-77% overlap S6/S7/ST)
- **Mecanismo:** en vez de Kelly por estrategia independiente, descontar el tamaño por el solapamiento
  de señal medido (60-77% documentado): `size_adjusted = base_size / sqrt(1+overlap)`.
- **Estrategia:** S6+S7+ST tratados como portafolio conjunto.
- **Origen:** `area-3-sizing-riesgo-equity.md` §2.3, citando Vince (2009), Ziemba & MacLean (2017).
- **Evidencia:** MEDIUM ("Moderate. Sound logic; limited independent empirical validation" — grado de
  la fuente).
- **Estatus:** EXTENSION relacionada a una familia YA-EN-PLAN. Plan Familia E2 ("S6+S7 como una
  estrategia de 6 fichas") y E5 (ensambles con pesos inversa-vol) tocan el mismo problema de
  solapamiento, pero ninguna aplica la matemática de Kelly-de-portafolio específicamente — es una
  extensión metodológica de E2/E5, no una familia nueva de cero.
- **Requisito de motor:** requiere el mismo hook de sizing de P-13/P-14 MÁS acceso al overlap medido
  entre estrategias en tiempo de decisión (hoy el overlap se mide offline, no está disponible como
  input runtime del motor).
- **Grid:** descuento por overlap {0.70, 0.77, 0.85} correspondiente a {60%, 70%, 80%} de overlap
  asumido (fuente).
- **Métrica/criterio:** Sharpe de portafolio conjunto vs. suma de Sharpes individuales sin descuento.
- **Pareado-por-entrada:** YES.
- **Conflictos:** con P-13 (orden de aplicación); con E2/E3 (¿tiene sentido S7 en absoluto si murió en
  vivo? — pregunta ya abierta en el plan, no resuelta aquí).

### P-16 — Throttle de exposición por tramos de drawdown
- **Mecanismo:** reducir tamaño de posición escalonadamente según drawdown corriente desde el pico de
  equity (p.ej. 75% del tamaño en DD 5-10%, 50% en 10-15%, 25% en >15%), con regla de recuperación.
- **Estrategia:** S6, S7, ST (a nivel cuenta/portafolio).
- **Origen:** `area-3-sizing-riesgo-equity.md` §2.4, citando Grossman & Zhou (1993).
- **Evidencia:** HIGH ("Strong. Rigorous theoretical derivation + empirical validation").
- **Estatus:** EXTENSION. No hay ningún factor de throttle por drawdown en el catálogo §7 — el
  concepto más cercano es Familia B9 "gestión de equity-curve a nivel estrategia (caps diarios,
  trailing sobre equity)", que es de la misma familia conceptual pero no idéntico (B9 es ROLLING-
  SHARPE/caps, esta palanca es DRAWDOWN-DESDE-PICO específicamente — mecanismos relacionados, no el
  mismo). Se mantiene como palanca separada por tener grid y trigger propios.
- **Requisito de motor:** hook de sizing (comparte infraestructura con P-13/P-14) MÁS seguimiento de
  equity-peak corriente a nivel de cuenta/portafolio (nuevo estado agregado, no por-posición).
- **Grid:** tiers {5%,10%,15%} × reducción {75%,50%,25%} (fuente); alternativa continua `factor = 1 −
  (DD_actual/20%)`, piso 25%.
- **Métrica/criterio:** reducción de probabilidad de DD catastrófico (>30%) vs. Sharpe de largo plazo.
- **Pareado-por-entrada:** YES.
- **Conflictos:** con P-18 (equity-curve por Sharpe rodante) — ambos actúan sobre el mismo problema
  (protección de la curva de equity) con triggers distintos; no combinar sin sondeo de interacción.

### P-17 — Ponderación asimétrica de fichas S6 (escalera de confianza)
- **Mecanismo:** en vez de F1=F2=F3 con igual tamaño, ponderar F1 40%/F2 35%/F3 25% (mimetiza una
  escalera de convicción: apuesta ligera temprano, más pesada tarde).
- **Estrategia:** S6.
- **Origen:** `area-3-sizing-riesgo-equity.md` §2.5, citando Lempérière et al. (2014) sobre
  ponderación por fuerza de señal en trend-following.
- **Evidencia:** MEDIUM — la fuente es explícita: "direct evidence on '3-tier exit ladder with
  asymmetric sizes' is limited. Test carefully before committing" (el hallazgo de Lempérière es
  general sobre peso-por-señal, no sobre esta estructura de 3 tramos específica).
- **Estatus:** YA-EN-PLAN. Plan Familia E1 "escalera de fichas diferenciada (plantilla TOKATA
  F1-patrón/F2-flip/F3-runner, ~206 celdas diseñadas jamás corridas, re-correr honesto)" — mismo
  concepto de diferenciación de fichas, aunque la plantilla TOKATA diferencia por LÓGICA de entrada/
  salida, no solo por TAMAÑO; esta palanca aporta el eje de tamaño puro como complemento.
- **Requisito de motor:** hook de sizing por índice de ficha (F1/F2/F3) — parte del mismo mecanismo
  de sizing nuevo, aplicado por ficha en vez de por estrategia.
- **Grid:** pesos {(40,35,25), (33,33,33) baseline, (30,30,40)} (fuente).
- **Métrica/criterio:** Sharpe vs. baseline equal-weight, sobre el MISMO conjunto de entradas.
- **Pareado-por-entrada:** YES.
- **Conflictos:** con Familia E1 completa — coordinar para no duplicar presupuesto de grilla.

### P-18 — Throttle por curva de equity / Sharpe rodante
- **Mecanismo:** si el Sharpe rodante de las últimas 50 operaciones cae bajo 0.5, reducir tamaño 20%;
  si cae bajo 0, reducir 50%; recuperar gradualmente.
- **Estrategia:** S6, ST.
- **Origen:** `area-3-sizing-riesgo-equity.md` §2.6, citando Pardo (2008) y Corcoran & Corcoran (2016),
  con caveat explícito de la fuente: "For S6 (DSR~0), this filter may accelerate exit from an already
  marginal strategy. Use cautiously."
- **Evidencia:** MEDIUM (practitioner, con evidencia empírica de trade-off retorno/DD documentada por
  Corcoran & Corcoran).
- **Estatus:** YA-EN-PLAN. Plan Familia B9: "gestión de equity-curve a nivel estrategia (caps
  diarios, trailing sobre equity)" — mismo mecanismo.
- **Requisito de motor:** hook de sizing (comparte infraestructura P-13/14/16) MÁS cómputo de Sharpe
  rodante por estrategia en runtime.
- **Grid:** umbral Sharpe {0.3, 0.5, 0.7} × reducción {20%, 30%, 50%} (fuente).
- **Métrica/criterio:** el propio caveat de la fuente ES el criterio de aceptación: verificar primero
  si el filtro acelera la salida de una estrategia marginal (dato negativo) antes de aceptar la
  reducción de DD como ganancia neta.
- **Pareado-por-entrada:** YES.
- **Conflictos:** con P-16 (mismo espacio de problema, trigger distinto).

## Bloque Momentum multi-timeframe (Área 4 de literatura formal)

### P-19 — Filtro de tendencia H4 (EMA20) que gatea entradas M15
- **Mecanismo:** solo permitir entradas M15 en la dirección del cierre H4 vs. EMA20-H4.
- **Estrategia:** S6, ST.
- **Origen:** `area-4-momentum-multi-tf.md` Parameter Set 1, citando Neely, Weller & Dittmar (1997,
  JFQA, backtest riguroso en FX) y Elder (1987)/Lhabitant (2006) como consenso de practicantes.
- **Evidencia:** HIGH (Neely et al. es backtest riguroso revisado por pares específico de FX).
- **Estatus:** EXTENSION — hueco genuino del plan. Familia D1 del catálogo §7 se titula explícitamente
  "Multi-TF **INFERIOR**" (1m/2m/5m, para confirmación/micro-timing) — es la dirección OPUESTA
  (timeframe MENOR, no mayor). Ningún factor del catálogo §7 usa H4/H1 como filtro de sesgo direccional
  de timeframe SUPERIOR sobre M15. La única alusión indirecta es D3 "cruces de ATR multi-TF (2-3+
  TFs)", que es sobre volatilidad, no sobre dirección/tendencia.
- **Requisito de motor:** el motor no tiene NINGÚN feed de barras H4/H1 disponible en el momento de
  decisión (mod #5 del plan §4.1 dice explícitamente "indicadores de TF inferior disponibles en
  entrada" — solo inferior). Nuevo: extender el feed multi-TF para incluir TF SUPERIOR también.
- **Grid:** EMA H4 período {10, 15, 20, 30}, con/sin filtro (fuente).
- **Métrica/criterio:** Sharpe y max-DD, con la advertencia metodológica de P-29/KML09tRtHM8 de que
  este TIPO de filtro puede perjudicar en vez de ayudar (medir, no asumir).
- **Pareado-por-entrada:** NO (gate de entrada).
- **Conflictos:** ver P-29 (evidencia contraria de que el sesgo de TF superior puede hundir el score);
  correr ambos lados de la hipótesis, no solo el lado "ayuda".

### P-20 — Alineación H4-SuperTrend antes de permitir flip M15
- **Mecanismo:** calcular SuperTrend también en H4; solo permitir el flip M15 si el SuperTrend-H4 ya
  apunta (o flipea el mismo día) en la misma dirección.
- **Estrategia:** ST.
- **Origen:** `area-4-momentum-multi-tf.md` Parameter Set 2, citando Moskowitz, Ooi & Pedersen (2012,
  JFE, persistencia de momentum multi-frecuencia) y motivado por el riesgo de "momentum crash" de
  Blitz et al. (2013)/Arnott et al. (2016) (white papers, no journal arbitrado).
- **Evidencia:** MEDIUM (Moskowitz es rigurosa para el concepto general de persistencia multi-TF; la
  aplicación específica "exigir acuerdo de dos SuperTrends" no está validada en la fuente misma).
- **Estatus:** EXTENSION, mismo hueco que P-19 (Familia D1 es solo TF inferior).
- **Requisito de motor:** mismo requisito que P-19 (feed H4) MÁS cómputo de un segundo SuperTrend
  sobre esa serie H4.
- **Grid:** multiplicador SuperTrend-H4 {2.0, 2.5, 3.0, 3.5}, ATR period H4 fijo en 14 (fuente).
- **Métrica/criterio:** reducción de flips whipsaw / drawdown en periodos de crash de momentum.
- **Pareado-por-entrada:** NO (cambia qué flips se honran, i.e. cambia el conjunto de entradas de ST).
- **Conflictos:** con P-05/P-07 (todas tocan el mecanismo de flip de ST) — sondeo de interacción
  obligatorio antes de combinar.

### P-21 — Gate intermedio de momentum H1 para S6
- **Mecanismo:** exigir que un indicador de momentum en H1 (AO o momentum-2) esté del lado correcto
  ADEMÁS de los gates M15 existentes de S6.
- **Estrategia:** S6.
- **Origen:** `area-4-momentum-multi-tf.md` Parameter Set 3, citando Baltas & Kosowski (2012, EDHEC,
  persistencia de momentum en futuros de commodities a distintos horizontes).
- **Evidencia:** MEDIUM/LOW ("less direct literature support" — la propia integración lo marca como
  el más débil de los 4 parameter sets del área, prioridad de implementación #3 de 4).
- **Estatus:** EXTENSION, mismo hueco de Familia D1 (solo TF inferior) — aquí H1 es una capa
  intermedia entre M15 y H4, tampoco cubierta.
- **Requisito de motor:** feed H1 (parte del mismo requisito de P-19/P-20, generalizado a "cualquier
  TF superior a M15").
- **Grid:** indicador H1 {Awesome Oscillator, momentum simple close[0]/close[2], pendiente EMA} como
  gate binario (fuente).
- **Métrica/criterio:** selectividad (menos entradas) vs. precisión (mayor expectancy por entrada
  tomada).
- **Pareado-por-entrada:** NO.
- **Conflictos:** con P-19 (ambos añaden capas de confirmación a S6 — evaluar aisladas antes de
  apilar, la propia área 4 advierte contra asumir que "más confluencia siempre ayuda" sin medir).

### P-22 — Overlay de detección de "momentum crash" (protección)
- **Mecanismo:** si (a) ATR-H4 actual > 1.5× su media de 20 barras H4 Y (b) diverge el momentum H4
  vs. M15, suspender flips de ST / suspender el stop-and-reverse de S6 hasta que la señal de alerta
  se apague.
- **Estrategia:** S6, ST.
- **Origen:** `area-4-momentum-multi-tf.md` Parameter Set 4, citando Sornette et al. (2012) y Blitz et
  al. (2013)/Arnott et al. (2016).
- **Evidencia:** MEDIUM, con una reserva EXPLÍCITA del controlador de T0.10 (no del agente): "Blitz...
  y Sornette et al. ... yo no pude cotejarlas contra la fuente primaria en esta pasada. Recomendación:
  spot-check antes de citarlas fuera de este programa" (`T0.10-reporte.md` §Reservas ítem 1). Esta
  palanca hereda esa reserva sin resolverla.
- **Estatus:** EXTENSION, mismo hueco de feed multi-TF superior que P-19/P-20/P-21.
- **Requisito de motor:** feed H4 (compartido) + cómputo de un "índice de crash" derivado (spike de
  ATR + divergencia de momentum) — nuevo cómputo compuesto, no solo un indicador simple.
- **Grid:** umbral de spike de volatilidad {1.2×, 1.5×, 2.0×}; umbral de divergencia de momentum
  {10%, 20%, 30%} (fuente).
- **Métrica/criterio:** reducción de exposición a colas (peor percentil de pérdida por episodio) sin
  recortar demasiadas entradas legítimas — la propia fuente advierte que los spikes de volatilidad
  son frecuentes en XAUUSD y un gate ingenuo podría saltarse trades rentables.
- **Pareado-por-entrada:** NO (suspende entradas/flips).
- **Conflictos:** con P-06 (ambos suspenden actividad de ST tras eventos anómalos, mecanismos
  distintos); citas de baja verificación — no usar como única motivación de una decisión de diseño
  sin spot-check previo (mandato del propio T0.10-reporte.md).

## Bloque literatura informal (videos Grupo A/B, solo relevancia HIGH/MEDIUM)

### P-23 — Rango de apertura multi-TF como sesgo del día (M15 range + confirmación de cierre M5)
- **Mecanismo:** marcar máx/mín de la primera vela M15 de la sesión; exigir cierre de M5 fuera del
  rango como confirmación direccional; tres modelos de entrada según si el día es de continuación o
  de rango (video declara explícitamente que FX tiende más a mean-reversion que las acciones que él
  opera).
- **Estrategia:** S6, ST (como pre-filtro de sesgo diario).
- **Origen:** video Grupo A `bITIVwysCzM` (relevancia HIGH); NO evidencia académica, es contenido de
  trader discrecional con red flags declarados (resultado no auditado, sin trade perdedor mostrado).
- **Evidencia:** LOW (folklore/practitioner no auditado — grado propio, distinto de la relevancia
  HIGH que el inventario le asignó).
- **Estatus:** YA-EN-PLAN. Plan §7 Familia D2 lista "opening range/initial balance" explícitamente
  entre los métodos de marcado de zona — coincide con el concepto central de esta palanca (el rango
  de la vela/velas de apertura como zona de referencia).
- **Requisito de motor:** pipeline de features de zona (mod #4 del plan §4.1, YA especificado) debe
  incluir el método "opening range/initial balance" con su confirmación multi-TF por cierre — hoy
  el mod #4 lista el método pero no la variante de confirmación en TF distinto de la barra de origen.
- **Grid:** ventana de apertura {M5, M15} (video); umbral de "el precio recorrió todo el rango sin
  romper" como señal de "día de rango" — regla cualitativa a operacionalizar con datos de barras.
- **Métrica/criterio:** expectancy condicional al régimen de día (tendencia vs. rango) detectado por
  esta regla, con split descubrimiento/confirmación (Charter §9).
- **Pareado-por-entrada:** NO (gate de entrada/sesgo del día).
- **Conflictos:** con D3 (familias de régimen ya existentes) — medir si el "opening range regime" es
  redundante con VR/ADX/HMM antes de sumarlo como filtro independiente.

### P-24 — Filtros de calidad de zona oferta/demanda (freshness, descuento Fibonacci, confluencia, BOS)
- **Mecanismo:** checklist de 6 "claves" de validez de una zona de oferta/demanda antes de honrarla:
  zona no usada previamente, cierre-o-mecha dentro de zona, confluencia con S/R previo, "la zona más
  reciente es la más fuerte", entrada bajo el 50% del retroceso Fibonacci, y confirmación de ruptura
  de estructura (BOS) — más un trailing-stop que solo cierra en cierre de vela (no mecha) bajo la
  línea.
- **Estrategia:** S6, ST (como filtro de calidad de zona ya presente en D2; el trailing por cierre es
  aplicable a ambas como esquema de salida).
- **Origen:** video Grupo A `nkMzaQqpFbw` (relevancia HIGH); backtest propio no auditado (121 trades,
  79% win rate, sin metodología mostrada — red flag explícito del inventario).
- **Evidencia:** LOW (folklore/practitioner no auditado).
- **Estatus:** YA-EN-PLAN. Plan Familia D2 nombra explícitamente "zonas del indicador Supply&Demand
  de tienda (S0 primero: ¿agregan sobre las nuestras?)" y ya trae el eje de "firmeza {toques ≥1/2/3 ×
  decay recencia × mechas de rechazo × edad}" que cubre freshness/confluencia. El descuento Fibonacci
  <50% y la regla BOS son sub-reglas NUEVAS dentro de esa familia ya abierta, no una familia nueva.
- **Requisito de motor:** mod #4 (pipeline de zona) debe soportar el método Supply&Demand con sus
  6 sub-filtros como flags independientes, más el nivel de retroceso Fibonacci como covariable de
  distancia. El trailing-por-cierre-no-mecha es una variante del hook B7b (cierre-a-través, ya
  especificado para ST) generalizable a S6.
- **Grid:** ninguna fija numéricamente por la fuente salvo "descuento <50% Fibonacci"; el resto son
  flags binarios (fresh/no-fresh, BOS-confirmado/no) — construir grilla categórica de combinaciones,
  screening S0 primero (mandato Familia D2: "S0 primero").
- **Métrica/criterio:** igual regla D2 general — expectancy condicional con IC excluye 0.
- **Pareado-por-entrada:** MIXTO — si se usa como filtro de ENTRADA (permiso de tomar la señal), NO
  pareado; si se usa solo para apretar F3/cuantizar TP cerca de zona (usos ya listados en D2), SÍ
  pareado. Documentar cuál uso se corre en cada experimento.
- **Conflictos:** con toda la Familia D2 — coordinar presupuesto, no duplicar el screening S0.

### P-25 — Rango de sesión previa como referencia de liquidez (Asia→Londres→NY)
- **Mecanismo:** usar el rango (máx/mín) de la sesión anterior como zona de referencia: en Londres,
  operar en relación al rango de Asia; en NY, en relación al rango de Londres.
- **Estrategia:** S6, ST.
- **Origen:** video Grupo A `lYmmBoYQvWM` (relevancia HIGH); testimonio con cifras no auditadas
  ("22.79R en junio" sin metodología mostrada).
- **Evidencia:** LOW (folklore/practitioner no auditado).
- **Estatus:** YA-EN-PLAN. Plan Familia D2 lista "H/L día/semana/sesión previos" como método de zona
  explícito — coincide.
- **Requisito de motor:** mod #4 (zona) + mod #6 (condicionamiento por sesión/ventana, YA
  especificado en plan §4.1) deben poder cruzar ambos: "rango de la sesión previa" como zona
  requiere saber los límites horarios de sesión (Asia/Londres/NY en hora de bróker) — mod #6 ya
  cubre la ventana horaria, falta conectar el rango de esa ventana como zona de D2.
- **Grid:** sesiones {Asia 20:00-00:00, Londres 02:00-05:00, NY 07:00-10:00 EST — convertir a hora de
  bróker UTC-4} (fuente); sin ventana numérica adicional más allá de las 3 sesiones.
- **Métrica/criterio:** igual regla D2.
- **Pareado-por-entrada:** NO si se usa como filtro de sesgo; el TP dual asociado (ver P-27) es
  aparte.
- **Conflictos:** con D3 (ya trae "hora/día/sesión" como factor genérico) — esta palanca aporta la
  regla ESPECÍFICA de "usar el rango de la sesión anterior como zona", más concreta que el factor
  genérico ya listado.

### P-26 — TP dual: parcial fijo a 5R + resto en trailing a estructura
- **Mecanismo:** cerrar 50% de la posición en un R fijo (la fuente usa 5R, en respuesta a un patrón
  observado de "corre a 5-7R y vuelve a breakeven"); dejar correr el resto con trailing hasta el
  siguiente swing estructural o nivel de liquidez.
- **Estrategia:** S6, S7 (ya tienen ladder de fichas; esto es una variante del reparto entre TP fijo y
  runner).
- **Origen:** video Grupo A `lYmmBoYQvWM` (relevancia HIGH, mismo video que P-25); también reforzado
  por Grupo B `C_R4sLaM0eo` (relevancia MEDIUM, misma estructura: 50% en 1R + BE + resto en trailing
  de estructura).
- **Evidencia:** LOW (ambas fuentes son video sin backtest auditado — reforzado por dos fuentes
  independientes del corpus informal, pero ninguna es rigurosa).
- **Estatus:** YA-EN-PLAN, PERO CON UNA ADVERTENCIA DE REAPERTURA QUE DEBE CITARSE. Plan Familia B5
  "TP re-exploración: `tp_r ∈ {0.5,0.75,1.0,1.5,2.0,3.0}` × por-ficha {F1, F1+F2}" cubre el TP
  parcial fijo; Familia B4 "Trailing trifásico" cubre el runner con apriete por indicador. **PERO**
  `NEGATIVOS.md` registra: "Take-profit fijo a-priori (`tp_min`), todos los valores → Activamente
  perjudicial" — 🔓 **reabierto en B5 con causa** ("el veredicto precede a los fixes de reloj/
  `reverse`/fills y nunca controló re-entradas. Además, un trailing en positivo es un TP a-posteriori:
  esa familia nunca estuvo quemada"). Es decir: la componente de TP-parcial-fijo-a-priori de esta
  palanca ES la forma previamente quemada, reabierta con causa ya registrada — **no re-litigar el
  veredicto viejo, correr bajo la causa de reapertura ya escrita, no una nueva**.
- **Requisito de motor:** ya cubierto por B5/B4 (parámetros `tp_r`, reparto por ficha, apriete por
  indicador) — no requiere mod nuevo más allá del harness pareado (mod #1).
- **Grid:** parcial en R fijo {1.0, 1.5, 2.0, 3.0, 5.0} (unir grilla B5 con el 5R del video) × resto
  en trailing a estructura (requiere D2 zona para definir "estructura").
- **Métrica/criterio:** igual regla B5/B4; comparar explícitamente contra el veredicto quemado
  original para entender qué cambió (reloj/reverse/fills), no solo contra "sin TP".
- **Pareado-por-entrada:** YES.
- **Conflictos:** depende de D2 (zona/estructura) para el tramo runner; ver la nota de reapertura de
  NEGATIVOS.md arriba — obligatorio citarla en cualquier spec que ejecute esto.

### P-27 — SL inicial estructural ("protected high/low") en vez de rango×k
- **Mecanismo:** anclar el SL inicial al extremo que generó el barrido de liquidez / swing que invalida
  el sesgo, en vez de una fórmula de rango de vela × multiplicador.
- **Estrategia:** S6, S7.
- **Origen:** video Grupo A `en8RMFRqSME` (relevancia HIGH, único video del corpus explícitamente sobre
  XAUUSD en M15/H1 — mismo timeframe que S6/ST).
- **Evidencia:** LOW (folklore/practitioner, cifras de resultado no auditadas — "$566k en un mes" sin
  contexto de cuenta).
- **Estatus:** YA-EN-PLAN. Plan Familia B★ ya trae "esquema SL {range-SL (actual), ATR-SL,
  **estructural-swing**}" — la opción "estructural-swing" es exactamente esto.
- **Requisito de motor:** requiere detección de swing/pivote (mod #4, pipeline de zona, método M2
  "swing pivots/fractales" ya especificado en el plan histórico y presente en D2) conectada al cálculo
  de SL inicial — hoy el SL inicial solo lee el rango de la vela de señal, no una serie de swings.
- **Grid:** lookback de swing {5, 10, 20} barras; tamaño mínimo de swing {0.5, 1.0}×ATR (tomado de la
  sub-matriz M2 histórica, ya que el video no da parámetros numéricos).
- **Métrica/criterio:** comparar contra el esquema range-SL actual sobre el MISMO conjunto de
  entradas (paridad de simulador).
- **Pareado-por-entrada:** YES (cambia solo dónde se ancla el SL inicial, no la señal de entrada).
- **Conflictos:** ninguno directo; es un nivel más de la grilla B★ ya existente.

### P-28 — Filtro de alineación de tendencia H1+M15 obligatoria antes de entrar (específico XAUUSD)
- **Mecanismo:** exigir que la tendencia de 15M y 1H estén alineadas antes de buscar cualquier
  entrada; si hay desalineación, el setup es de baja probabilidad (el propio autor casi pierde el
  trade que operó pese a desalineación).
- **Estrategia:** S6, ST.
- **Origen:** video Grupo A `en8RMFRqSME` (mismo video que P-27; relevancia HIGH).
- **Evidencia:** LOW (folklore/practitioner, mismo video que P-27).
- **Estatus:** EXTENSION — mismo hueco de Familia D1 (solo TF inferior) que P-19/P-20/P-21. Esta
  palanca es la versión H1 (en vez de H4) del mismo mecanismo; se agrupa aquí por venir de fuente de
  video en vez de literatura formal, pero comparte el requisito de motor con P-19/P-21.
- **Requisito de motor:** feed H1 — MISMO requisito consolidado que P-19/P-20/P-21/P-22 (ver Parte 2).
- **Grid:** sin parámetro numérico específico en la fuente (alineación binaria sí/no) — combinar con
  la definición de "tendencia H1" que ya exista en el motor (EMA order o SAR).
- **Métrica/criterio:** igual regla que P-19; correr como réplica del mismo experimento en H1 en vez
  de H4, comparar cuál horizonte superior aporta más.
- **Pareado-por-entrada:** NO.
- **Conflictos:** con P-19/P-21 — literalmente el mismo tipo de filtro en un TF distinto; NO correr
  como palancas independientes sin coordinar la grilla (riesgo de inflar el conteo de comparaciones
  múltiples del haircut DSR sobre la misma idea repetida en 3 TFs).

### P-29 — Precondición de barrido de liquidez antes de honrar breakout/tendencia (con advertencia metodológica)
- **Mecanismo:** solo tomar una señal de breakout/tendencia si fue precedida por un "barrido de
  liquidez" (mecha que toma un swing previo) — y, CRÍTICAMENTE, el video fuente es un backtest
  riguroso (25.000 configuraciones, walk-forward, holdout de 2 años, otro instrumento/TF) que
  encontró que exigir el barrido es la ÚNICA regla que MEJORA el score (0.33→0.69), mientras que
  añadir sesgo direccional de TF superior o restringir a horas "especiales" EMPEORA el resultado
  (sesgo M15 hunde el score a 0.16, la peor regla probada).
- **Estrategia:** S6, ST (como precondición de entrada) — pero también como ADVERTENCIA sobre P-19/
  P-20/P-21/P-28 (filtros de sesgo de TF superior).
- **Origen:** video Grupo A `KML09tRtHM8` (relevancia HIGH, "como evidencia metodológica y como
  advertencia, no como regla de grid directa" — cita literal del propio inventario). Instrumento/TF
  distinto (NQ/ES en 1 minuto, no XAUUSD M15) — resultado cuantitativo NO transferible directamente,
  solo la metodología y la hipótesis de que "el sesgo de TF superior puede perjudicar" son
  trasladables, sujetas a validación propia.
- **Evidencia:** MEDIUM — es el único video del corpus con metodología cuantitativa rigurosa
  (walk-forward, corrección por comparaciones múltiples, holdout único nunca tocado), aunque no
  arbitrado y en otro mercado; se grada por encima del resto de la literatura informal por ese
  motivo, sin llegar a HIGH porque el resultado no es directamente transferible a oro/M15.
- **Estatus:** EXTENSION (la precondición de barrido de liquidez en sí no está en el catálogo §7,
  aunque D2 zona/S/R cubre swings y podría extenderse). **Uso principal de esta entrada: la
  advertencia.** Debe citarse explícitamente como contrapeso al ejecutar P-19/P-20/P-21/P-28 — el
  propio programa corre el riesgo de asumir que "más filtro de TF superior siempre ayuda" cuando la
  evidencia cuantitativa más rigurosa del corpus informal (aunque de otro mercado) dice lo contrario.
- **Requisito de motor:** detección de "barrido de liquidez" = mecha que supera un swing previo y
  cierra de vuelta dentro — requiere la misma detección de swings de P-27 (mod #4, método M2) más una
  regla de "mecha-supera-y-cierra-dentro" (nuevo cómputo simple sobre datos de barras ya
  disponibles).
- **Grid:** definición del swing (lookback, tamaño mínimo — compartir con P-27); sin parámetro
  numérico adicional de la fuente para el barrido en sí.
- **Métrica/criterio:** correr P-19/20/21/28 (bias de TF superior) Y P-29 (precondición de barrido)
  como hipótesis EXPLÍCITAMENTE EN COMPETENCIA, no asumidas complementarias — exactamente el diseño
  que el video demuestra que hace falta (probar cada regla aislada, no solo la combinación completa).
- **Pareado-por-entrada:** NO.
- **Conflictos:** directo con P-19/P-20/P-21/P-28 — ver arriba. Es la palanca con más valor
  metodológico del bloque video (ratifica el mandato del Charter §A.3: "una hipótesis del
  orquestador sobre 'esto probablemente correlaciona' no poda nada: se mide").

### P-30 — Trailing-stop estructural por línea de tendencia sin intersección ("safety line")
- **Mecanismo:** el stop se ancla a una trendline construida por reglas mecánicas (nunca perforada por
  el precio, conecta máximos/mínimos sucesivos, se desplaza manualmente/algorítmicamente a lo largo
  de esa línea); la posición se cierra únicamente cuando el precio cruza esa línea. Conceptualmente
  es un SuperTrend "dibujado a mano" con reglas de no-intersección en vez de banda ATR.
- **Estrategia:** ST (mecanismo trailing alternativo), S6 (como esquema de trailing alternativo al
  ladder de pips).
- **Origen:** video Grupo A `PnIkSLm2yRk` (relevancia MEDIUM-HIGH, agnóstico de instrumento/TF —
  declarado explícitamente aplicable a oro por el propio video, aunque demostrado sobre Bitcoin).
- **Evidencia:** LOW (folklore/practitioner, "$5.000 → medio millón en 11 años" sin track record
  auditado; el propio inventario nota que el trazado de trendlines es inherentemente subjetivo salvo
  que se defina un algoritmo determinista de pivotes).
- **Estatus:** EXTENSION. No hay ningún esquema de trailing basado en trendline de pivotes conectados
  en el catálogo §7 — B★ trae {range-SL, ATR-SL, estructural-swing} para el SL INICIAL (no trailing
  continuo), y B7 (SuperTrend) trae bandas ATR, no trendlines de pivotes. Es un mecanismo de trailing
  genuinamente distinto.
- **Requisito de motor:** requiere un algoritmo determinista de construcción de trendline (conectar
  swings sin que el precio los perfore, regla de "point A nuevo = point B anterior") — cómputo nuevo,
  no trivial (a diferencia de una banda ATR, una trendline válida requiere buscar sobre combinaciones
  de pivotes que no violen la regla de no-intersección). Nuevo decision hook de trailing.
- **Grid:** sin parámetros numéricos de la fuente (regla puramente geométrica) — a definir: mínimo de
  toques por línea, tolerancia de "casi-toque" antes de invalidar.
- **Métrica/criterio:** comparar contra SuperTrend/trail-pips actual sobre el MISMO conjunto de
  entradas.
- **Pareado-por-entrada:** YES (solo cambia el mecanismo de trailing).
- **Conflictos:** con B7 (mecanismo de trailing alternativo para ST) — evaluar como alternativa, no
  como suma.

### P-31 — Filtro de régimen de 3 condiciones basado en VWAP (posición/pendiente/momentum)
- **Mecanismo:** tendencia válida solo si simultáneamente (1) precio por encima/debajo del VWAP
  anclado a la apertura, (2) VWAP en pendiente a favor, (3) momentum de la última hora ≥ umbral —
  aplicado en el video como filtro de 15 min sobre gatillo de 5 min en NQ.
- **Estrategia:** S6, ST (como plantilla de filtro de régimen a adaptar).
- **Origen:** video Grupo B `wm4A6qo0g3I` (relevancia MEDIUM), único video del lote B con metodología
  IS/OOS declarada y simulación Monte Carlo sobre el propio histórico de trades — más riguroso que el
  resto del lote B pero el propio entrevistado declara que la estrategia está diseñada para pasar
  desafíos de prop firm, no para maximizar EV de capital propio, y "300% en 4.000+ trades" no se
  reconfirma en pantalla.
- **Evidencia:** LOW (no auditado externamente, pese a mayor rigor relativo que el resto del corpus
  informal — se mantiene LOW porque sigue siendo YouTube sin dataset/código entregado).
- **Estatus:** EXTENSION. VWAP no aparece en ningún método de zona de la Familia D2 del plan v4
  (fractales, pivotes, H/L, redondos, volumen HVN/LVN, opening range, gaps, Donchian, confluencia,
  Supply&Demand — VWAP ausente). Genuino hueco: ni como zona ni como filtro de régimen está el VWAP
  en el catálogo actual.
- **Requisito de motor:** cómputo de VWAP anclado (a la apertura de sesión o de día) — no existe hoy
  en el motor. Nuevo cómputo, effort BAJO-MEDIO (fórmula cerrada, no requiere ajuste estadístico como
  GARCH/HMM).
- **Grid:** ninguna grilla numérica dada por la fuente más allá del concepto de 3 condiciones — a
  definir umbral de pendiente VWAP y umbral de momentum de 1h con causa propia sobre XAUUSD M15.
- **Métrica/criterio:** expectancy condicional, igual regla D3/S0.
- **Pareado-por-entrada:** NO (gate de régimen).
- **Conflictos:** con P-09 (compuesto ADX/VR/ER/CI) — evaluar si VWAP añade señal incremental sobre
  el compuesto ya existente antes de sumarlo (regla de no-duplicación de Familia D2/D3).

### P-32 — Circuit breaker de pérdidas consecutivas / reducción escalonada diaria
- **Mecanismo:** pausar nuevas entradas tras N pérdidas consecutivas en el día (2 en un video, 3 en
  otro), o reducir tamaño escalonadamente según drawdown diario/mensual con umbrales declarados
  (10%/20%/50% en un video, con pausas de 3 días / 1 semana).
- **Estrategia:** S6, S7, ST (a nivel cuenta/portafolio, no por-estrategia individual).
- **Origen:** reforzado por CUATRO fuentes independientes del corpus informal: Grupo B `ksVXut9bSSg`
  (relevancia MEDIUM, "stop trading after two losses in a day"), `wm4A6qo0g3I` (relevancia MEDIUM,
  "máximo 2 pérdidas consecutivas por día → detener el sistema"), `hC4g7qY6UcQ` (relevancia MEDIUM,
  tiers de drawdown 10%/20%/50% con pausas escalonadas), `fV02FcLmFpA` (relevancia LOW, "3 pérdidas
  seguidas → reducir actividad", el más débil de los 4 pero consistente en dirección).
- **Evidencia:** LOW (todas las fuentes son practitioner/folklore no auditado; la CONVERGENCIA entre
  4 fuentes independientes es una señal de consenso de práctica, no de rigor — no se sube de grado
  por repetición, per Charter §A.4/regla de no-laundering de este encargo).
- **Estatus:** EXTENSION relacionada con una familia YA-EN-PLAN. Se solapa conceptualmente con
  Familia B9 ("gestión de equity-curve a nivel estrategia, caps diarios") y con P-16/P-18 (throttle
  por drawdown / Sharpe rodante) — pero el TRIGGER aquí es "N pérdidas consecutivas" (conteo discreto
  de eventos), un mecanismo distinto de "% de drawdown" o "Sharpe rodante". Se mantiene como palanca
  separada por tener su propio trigger y grid.
- **Requisito de motor:** hook de gobernanza a nivel de CUENTA/PORTAFOLIO que pueda SUPRIMIR nuevas
  aperturas de TODAS las estrategias tras un evento — esto es distinto de los hooks de sizing por
  posición de P-13..P-18 y distinto del kill-switch STOP-file ya existente (que es manual, no
  automático por conteo de pérdidas). Nuevo: decision hook a nivel cuenta, no por-estrategia.
- **Grid:** N pérdidas consecutivas {2, 3}; tiers de DD {10%,20%,50%} con pausas {3 días, 1 semana}
  (fuentes, sin reconciliar entre sí — el propio corpus trae cifras inconsistentes, p.ej.
  `ksVXut9bSSg` da 10% Y 1-2% de riesgo por trade en el MISMO video sin resolverlo, red flag ya
  declarado en el inventario).
- **Métrica/criterio:** reducción de max-DD vs. costo de oportunidad de días sin operar.
- **Pareado-por-entrada:** NO (suprime entradas futuras tras el trigger).
- **Conflictos:** con P-16/P-18 (mismo espacio de protección de equity, triggers distintos) — no
  combinar sin sondeo de interacción; con el kill-switch STOP-file manual ya existente en el
  reconciler (§2.5 de `strategy-mechanics-reference.md`) — coordinar semántica (automático vs.
  manual) antes de implementar.

### P-33 — Confirmación literaria de "cierre inmediato en señal opuesta" como folklore sin validar
- **Mecanismo:** ninguno nuevo — esta entrada documenta que la propia literatura formal marca
  explícitamente `stop_and_reverse` (cierre y apertura inmediata en dirección opuesta, tal como S6/S7
  lo hacen hoy) como una práctica NO validada por ningún estudio publicado, y propone contrastarla
  contra una salida por reglas dedicadas (SL/TP/time-stop) en vez de por señal de entrada reciclada.
- **Estrategia:** S6, S7 (`stop_and_reverse=True` en ambas, per `strategy-mechanics-reference.md`
  §2.3/§3.3).
- **Origen:** `area-1-exits-optimal-stopping.md` §3.2 ítem 5 ("Close on opposite signal, immediately" →
  Folklore/assumption. "Recommended: A/B test vs. a threshold-based exit... to measure the cost of
  true signal-based exits").
- **Evidencia:** LOW (folklore, marcado explícitamente como tal por la fuente académica).
- **Estatus:** YA-EN-PLAN. Coincide exactamente con Familia A3 ("Economía de la reversa (HIPÓTESIS,
  plan pre-registrado): ¿las patas de `stop_and_reverse` suman o restan?... Decide E3") y Familia E3
  ("`stop_and_reverse` {on,off} (decidido por A3)"), ambas YA en cuarentena §2.1 del plan hasta que
  A6 cierre. Esta entrada no agrega grilla nueva — es CITACIÓN de respaldo literario para un
  experimento que el programa ya tenía planeado, documentada aquí porque el encargo exige trazar
  toda idea de la literatura al plan, incluso cuando el plan ya la cubre.
- **Requisito de motor:** ninguno adicional — A3/E3 ya están en el DAG del plan (§8), condicionadas a
  A6.
- **Grid:** {on, off} de `stop_and_reverse` (ya definida en Familia E3).
- **Métrica/criterio:** ya definida por A3/E3 — no se agrega criterio nuevo.
- **Pareado-por-entrada:** NO (cambiar `stop_and_reverse` cambia si se reabre o no tras un cierre, lo
  que altera el conjunto de entradas subsecuentes).
- **Conflictos:** ninguno nuevo; referencia cruzada a A3/E3.

---

# Parte 2 — Requisitos de motor consolidados

De-duplicados contra los **12 mods ya inventariados** en el plan §4.1 (spec cerrada, implementación
vía-rápida D-47 pendiente de ejecución). Donde una palanca solo necesita un mod ya listado, se marca
**YA CUBIERTO**; donde extiende un mod existente en un eje que ese mod no contemplaba, se marca
**EXTIENDE mod #N**; donde no hay mod que lo cubra, se marca **NUEVO**.

## Instrumentación (grabar algo que el motor no graba hoy)

| Ítem | Palancas | Cubierto por | Effort |
|---|---|---|---|
| Snapshot de contexto de entrada (features de indicadores al abrir) | P-01, P-04, P-24 | YA CUBIERTO — mod #11 (instrumentación de camino de posición), ya especificado en plan §4.1 | — |
| MFE/MAE por posición a lo largo del tiempo | P-01, P-04 | YA CUBIERTO — mod #11 | — |
| Overlap de señal entre estrategias disponible en runtime (no solo offline) | P-15 | NUEVO — hoy el 60-77% de overlap se mide offline (Wave-4 histórico); el motor no expone esta métrica como input de decisión en tiempo de backtest | MEDIUM |
| Estado de equity-peak / drawdown corriente a nivel cuenta | P-16, P-32 | NUEVO — no existe seguimiento de equity-peak agregado por cuenta/portafolio en el motor de backtest (solo por posición) | MEDIUM |
| Sharpe rodante por estrategia en runtime | P-18 | NUEVO — requiere ventana rodante de últimas 50 operaciones cerradas, disponible como estado consultable | LOW-MEDIUM |
| Conteo de pérdidas consecutivas / día a nivel cuenta | P-32 | NUEVO — estado agregado distinto del anterior (evento discreto, no continuo) | LOW |

## Nuevos parámetros (cosas hoy hardcoded que deben volverse barribles)

| Ítem | Palancas | Cubierto por | Effort |
|---|---|---|---|
| Multiplicador ATR SuperTrend (ya parametrizado, falta exponer al harness) | P-05 | YA CUBIERTO — parámetro existente `_ST_MULT`, falta solo el harness pareado (mod #1) | LOW |
| Período ATR SuperTrend (ya parametrizado) | P-05, P-07 (base) | YA CUBIERTO — `_ST_ATR_PERIOD`, falta harness | LOW |
| Umbral y lookback de desaceleración AC (hoy hardcoded en `emasar_ref.py`) | P-03 | NUEVO — no está expuesto como kwarg | LOW |
| `max_hold_bars` (ya existe como parámetro, deshabilitado en S6/S7) | P-02 | YA CUBIERTO — solo falta exponerlo al harness pareado (mod #1) | LOW |
| Offset de SL por slippage esperado (ST) | P-08 | NUEVO | LOW |
| TP parcial en R fijo + reparto por ficha (ya en grilla B5) | P-26 | YA CUBIERTO — `tp_r`, reparto por ficha, ya en Familia B5/B4 | — |

## Nuevos cómputos (series/indicadores que el motor no calcula hoy)

| Ítem | Palancas | Cubierto por | Effort |
|---|---|---|---|
| ADX, Variance Ratio, Efficiency Ratio, Choppiness Index (4 series) | P-09 | NUEVO — ninguna existe hoy en el motor | MEDIUM (4 fórmulas cerradas, sin dependencia estadística externa) |
| HMM de régimen (2-4 estados, entrenado) | P-10 | NUEVO — requiere dependencia externa (`hmmlearn` o equiv.) | HIGH |
| Hurst exponent con estimador corregido por sesgo (Anis & Lloyd) | P-11 | NUEVO — riesgo de implementación incorrecta si se usa R/S ingenuo | MEDIUM |
| GARCH(1,1) en ventana rodante | P-12 | NUEVO — dependencia estadística, no trivial en el motor actual | MEDIUM |
| VWAP anclado (sesión/día) | P-31 | NUEVO — fórmula cerrada, sin dependencia estadística | LOW-MEDIUM |
| Detección de swing/pivote determinista (para SL estructural y barrido de liquidez) | P-27, P-29, P-30 (parcial) | PARCIALMENTE CUBIERTO — mod #4 (pipeline de zona) ya incluye método M2 "swing pivots/fractales" en la sub-matriz histórica de zonas; falta conectarlo al cálculo de SL inicial y a la regla de "mecha-supera-y-cierra-dentro" | MEDIUM |
| Algoritmo de trendline de pivotes sin intersección ("safety line") | P-30 | NUEVO — búsqueda combinatoria sobre pivotes, más caro que una banda ATR | HIGH |
| Feed de barras TF SUPERIOR (H1/H4) disponible en decisión | P-19, P-20, P-21, P-22, P-28, P-29(parcial) | **EXTIENDE mod #5** — el mod #5 del plan dice literalmente "indicadores de TF inferior disponibles en entrada (D1) y salida (B8)"; NINGÚN mod de los 12 cubre TF SUPERIOR. Es el hueco más repetido de este catálogo (6 palancas lo necesitan) | MEDIUM |
| Índice compuesto de "momentum crash" (spike ATR-H4 + divergencia momentum H4/M15) | P-22 | NUEVO, depende del feed H4 de arriba | MEDIUM |
| "Índice de crash" / detección de "opening range regime" (día tendencia vs. rango) | P-23 | PARCIALMENTE CUBIERTO — mod #4 ya lista "opening range/initial balance" como método de zona; falta la confirmación multi-TF por cierre de vela en TF distinto | LOW-MEDIUM |

## Nuevos hooks de decisión (pluggable, para que K políticas corran sobre las MISMAS entradas)

| Ítem | Palancas | Cubierto por | Effort |
|---|---|---|---|
| Harness de replay pareado (K políticas de salida, una entrada) | TODAS las de exits (P-01 a P-08, P-24 parcial, P-26, P-27, P-30) | YA CUBIERTO — mod #1, ya especificado, vía rápida (triaje "aditiva") | — |
| SL condicionado a score externo (meta-label `p_profit`) | P-01 | NUEVO | MEDIUM |
| SL condicionado a tabla de hazard/recuperación | P-04 | NUEVO | MEDIUM |
| Suspensión de flip/reversa tras evento (whipsaw, crash) | P-06, P-22 | NUEVO — no existe ningún mecanismo de suprimir flip fuera de la línea SuperTrend misma o el gate de S6 | MEDIUM |
| **Hook de sizing por posición (multiplicador de lote)** parametrizado por: Kelly fraccional, ATR inverso, tramo de drawdown, índice de ficha, Sharpe rodante | P-13, P-14, P-15, P-16, P-17, P-18 | **NUEVO — el hueco más grande y más repetido del catálogo (6 palancas comparten la misma pieza faltante).** Hoy el motor no tiene NINGÚN mecanismo para escalar el volumen de una orden en función de estadística — es puramente `base_lot` fijo o vol-target ya previsto (factor 12/factor 5 del plan) pero diferido a "AL FINAL del programa" | HIGH (una sola pieza de infraestructura sirve a 6 palancas — máxima prioridad de diseño, ejecución diferida por el plan) |
| Circuit breaker de cuenta (suprimir aperturas tras N pérdidas o tramo de DD) | P-32 | NUEVO — distinto del STOP-file manual ya existente (reconciler); este es automático, gatillado por conteo de eventos | MEDIUM |
| Filtro de régimen como gate de entrada (compuesto k-de-m, HMM, VWAP-3-condiciones) | P-09, P-10, P-31 | NUEVO — ninguna forma de gate de régimen existe hoy en el motor (S6 no tiene `direction_filter`/regime gate activo, confirmado en `strategy-mechanics-reference.md` §2.5) | MEDIUM (una vez que los cómputos de arriba existen, el gate en sí es una condición booleana) |
| Trailing por cierre de vela (no mecha) generalizado a S6 | P-24 (parcial) | **EXTIENDE mod B7b** (ya especificado para ST, "cierre-a-través + buffer") — falta generalizar a S6/S7 | LOW |

**Lectura de prioridad de la Parte 2:** dos huecos dominan por repetición — (a) **feed de TF
SUPERIOR** (6 palancas: P-19/20/21/22/28/29) y (b) **hook de sizing por posición** (6 palancas:
P-13 a P-18). Ninguno de los 12 mods ya especificados en el plan §4.1 los cubre. Si el motor se
modifica UNA sola vez (mandato del Charter §A.5), estos dos son candidatos obligatorios a sumarse a
la lista de 12, no opcionales — de lo contrario dos bloques completos de este catálogo (momentum
multi-TF y sizing) quedan sin poder medirse en absoluto.

---

# Parte 3 — Ordenamiento de ejecución

**Contexto que condiciona todo lo demás:** A6 midió una divergencia neta simulador-vs-real del
**17,6%** con sesgo de **signo opuesto** entre estrategias — el simulador penaliza a S6 en
−10,39 USD/posición y favorece a ST en +54,44 USD/posición (`NEGATIVOS.md`, entrada 2026-08-15,
`F0-A6-NETO-0001`). Esto ya fue explícitamente refutado como "inocuo para la comparación": el
propio controlador intentó ese argumento y quedó cerrado como **no válido**. Consecuencia dura para
cualquier ola de este catálogo: **ninguna cifra absoluta de dinero, y ninguna comparación
S6-vs-ST, sobrevive al simulador tal como está hoy.** Solo sobreviven preguntas **comparativas
dentro de la MISMA estrategia sobre el MISMO conjunto de entradas** (diseño pareado, Charter §9) —
exactamente el motivo por el que el campo "Pareado-por-entrada" de cada palanca es el filtro real de
qué se puede concluir, no solo un detalle metodológico.

## Ola 1 — Alto valor / bajo esfuerzo, todo pareado-por-entrada

P-05 (mult ST, YA CUBIERTO), P-02 (time-stop, YA CUBIERTO salvo confound conocido de 64 barras),
P-03 (umbral AC, LOW effort), P-27 (SL estructural, extiende D2/B★ ya abierta), P-08 (offset SL
fill-aware, LOW effort), P-33 (cita de respaldo a A3/E3, sin costo — ya en el DAG).
**Qué se puede concluir:** todas son pareadas-por-entrada → comparaciones DENTRO de cada estrategia
son válidas pese al 17,6% de divergencia (el sesgo afecta el nivel absoluto, no la comparación entre
K políticas sobre el mismo stream). **Qué NO se puede concluir:** ninguna cifra de USD/oz absoluta,
ni si S6 "gana más" que ST tras aplicar la palanca — eso exige el simulador reparado o la ventana
902 real.

## Ola 2 — Alto valor / esfuerzo medio, mezcla pareado/no-pareado

P-09/P-10/P-11/P-12 (régimen, requiere nuevo cómputo pero fórmulas cerradas salvo HMM), P-01/P-04
(meta-labeling/hazard, requieren mod #11 + hooks nuevos pero ya especificados), P-24/P-25/P-26
(zonas, extienden D2 ya abierta), P-06/P-07 (ST whipsaw/ATR adaptativo, requieren hooks nuevos
pequeños), P-30 (trendline safety-line, cómputo nuevo pero acotado).
**Qué se puede concluir:** las de régimen (P-09..P-12) NO son pareadas — cambian el conjunto de
entradas — así que su resultado es válido solo como comparación de expectancy CONDICIONAL (regla S0
del plan: IC que excluye 0), nunca como veredicto de "neto mejora". Las de exits (P-01, P-04, P-24
parcial, P-26, P-27, P-30) SÍ son pareadas y heredan la garantía de Ola 1.

## Ola 3 — Esfuerzo alto o dependencias externas al catálogo, no arrancar sin Ola 1-2 verdes

P-13 a P-18 (todo el bloque sizing, bloqueado por el hook de sizing NUEVO más grande del catálogo —
Parte 2), P-19/P-20/P-21/P-22/P-28/P-29 (todo el bloque momentum multi-TF superior, bloqueado por el
feed H4/H1 NUEVO), P-31 (VWAP, cómputo nuevo + sin grilla numérica fuente, requiere calibración
propia), P-32 (circuit breaker de cuenta, requiere estado agregado nuevo + coordinación con
kill-switch manual existente).
**Qué se puede concluir:** el bloque sizing (P-13..P-18) es TODO pareado-por-entrada, así que en
principio podría ir a Ola 1 por diseño — se pospone a Ola 3 exclusivamente por el COSTO de
infraestructura (el hook de sizing no existe), no por valor esperado bajo. El bloque momentum
multi-TF (P-19..P-22, P-28, P-29) es TODO no-pareado (cambia entradas) y además compite
internamente (P-29 es evidencia metodológica CONTRA P-19/20/21/28) — su resultado más valioso de
esta ola puede terminar siendo "esto no ayuda", que es un hallazgo legítimo y económico de reportar,
no un fracaso del programa (Charter §A.2).

---

# Parte 4 — Vacíos (gaps)

1. **S/R + zonas + números redondos + microestructura de barreras** (área 3 declarada pendiente de
   T0.10, `T0.10-reporte.md` "Declarado pendiente ... por elección explícita de D-50, no omisión
   silenciosa"). Costo: el catálogo de zonas D2 del plan sigue operando sin el respaldo de literatura
   formal específico de microestructura de barreras (solo tiene la evidencia que ya traía el matrix
   histórico de 2026-07-22 — Osler 2000/2003 — que este documento no volvió a revisar por estar fuera
   del encargo de T0.10). Ninguna palanca de este catálogo depende bloqueantemente de este gap, pero
   D2 (la familia de mayor presupuesto declarado, "FOCO") queda con menos respaldo académico fresco
   que régimen/exits/sizing/momentum.
2. **Validación estadística de backtests: DSR/PBO/CPCV, actualizaciones recientes** (área 5
   declarada pendiente). Costo: el plan §9 ya tiene un diseño estadístico (bootstrap por bloques,
   DSR/PBO/White-SPA, walk-forward purgado+embargado) fijado en 2026-08-10, pero sin la revisión de
   literatura formal que confirme si esos son los métodos más actuales o si hay refinamientos
   posteriores (el video `KML09tRtHM8` del corpus informal, aunque no es literatura formal, ya
   demuestra en la práctica un embudo de validación afín — walk-forward, corrección por suerte,
   holdout único — que podría servir de referencia cruzada, pero no sustituye la revisión formal
   pendiente).
3. **Riesgo de eventos/noticias en oro** (área 6 declarada pendiente). Costo: Familia D3 ya lista
   "noticias: gate de blackout retro-testeable" como palanca planeada, y §5.2 de la autopsia incluye
   "ventana de noticias" en la matriz de indicadores — pero sin literatura formal de respaldo, el
   diseño exacto del gate (±X min, qué calendario de eventos, qué umbral de impacto) queda sin
   evidencia académica que lo guíe; el video Grupo A `oDK0hbAMWbU` menciona Forex Factory como fuente
   práctica pero sin metodología cuantitativa.
4. **(Inferencia propia, no de fuente — marcada como tal por mandato del encargo.)** Ninguna de las
   fuentes leídas trata el problema de **qué hacer cuando dos palancas de este catálogo compiten por
   el mismo mecanismo** (p.ej. P-19 vs. P-29, o P-16 vs. P-18 vs. P-32, todas descritas arriba con
   "Conflictos" pero sin una regla de arbitraje declarada en el plan). El plan §7 dice "sondeos de
   interacción dirigidos en pares acoplados" mas no da una regla general de precedencia entre
   familias que tocan el mismo estado (equity-curve, régimen, TF superior). Costo: sin esa regla,
   hay riesgo de que la Ola 3 termine corriendo combinaciones no coordinadas y gastando presupuesto
   de comparaciones múltiples en preguntas redundantes — un ítem a resolver por el controlador antes
   de secuenciar Ola 3 en detalle, no algo que este catálogo pueda resolver por sí solo.

---

**Trazabilidad de este documento:** no crea entradas de `LEDGER.jsonl` (documento de controlador,
no de agente ejecutor de experimento) — el controlador que lo consuma debe registrar su propia
lectura/uso en el research OS si corresponde. Todas las citas de literatura son `file:line`-
equivalentes a nivel de sección de los 7 ficheros fuente listados en el encargo; ningún número de
este documento fue calculado por código — es síntesis de prosa ya escrita y commiteada.
