# Plan Integral de Investigación v4 — Programa XAUUSD 2026-H2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) o superpowers:executing-plans para ejecutar fase a fase. Checkboxes (`- [ ]`)
> para tracking. **Este es el plan MAESTRO del programa**: cada fase ejecutable emite su propio
> plan detallado vía `superpowers:writing-plans` EN SU FRONTERA, escrito contra los docs fuente
> (anti-alucinación), nunca de memoria.

**Goal:** Programa exhaustivo de investigación para maximizar el desempeño real y sostenible de
las estrategias sobre XAUUSD — puliendo las ganadoras actuales (S6, ST) Y explorando familias
nuevas — bajo la filosofía de composición de mejoras marginales en todas las áreas, con evidencia
(literatura + experimental), ejecución agéntica sin drift, y trazabilidad absoluta.

**Architecture:** Fase 0 (preparación: datos AVA, fidelidad A6, motor congelado, Research OS,
literatura) → Fase A0 (autopsia de posiciones) → S0 (screening retrospectivo) → grillas B/C/D/F/G/H/LS
sobre harness pareado → puerta estadística → cola de backtest largo real-tick → checkpoint conversado
→ Familia E (gateada) → holdout sagrado (una pasada) → síntesis final.

**Tech Stack:** Python 3.x (pathlib, utf-8, Win10/11), pandas/pyarrow, motor de backtest propio
(`sentinel_engine` + `scripts/analysis/realtick_bt`), MT5 attach-only, pytest foreground, git rama `equipo1`.

**Estado: BORRADOR v4 — PARA REVISIÓN DEL USER. NO EJECUTAR NADA sin su OK explícito.**
**Registro aditivo:** este doc REEMPLAZA como vigente al catálogo v3
(`2026-07-27-strategy-improvement-catalog-v3.md`) y a la matriz FINAL
(`2026-07-22-FINAL-experiment-matrix.md`); esos ficheros NO se editan.
**Backup del plan previo:** `docs/superpowers/plans/backups/2026-08-10-programa-exploracion-artifact-PRE-INTEGRACION.html`.
**Fuente de las decisiones:** conversación 2026-08-09/10 (documento exhaustivo del user + respuesta integrada, 31 deltas).

---

## §0 · CHARTER — reglas doctrinales (obligatorias, van al frente de todo brief)

1. **Comparabilidad es la directiva #1.** Todo experimento corre a lote estandarizado idéntico
   (investigación: 0.10/ficha salvo indicación; la config VIVA es otra cosa y se etiqueta aparte).
   Resultados SIEMPRE en unidades por-lote Y en múltiplos de R. Toda regla monetaria se especifica
   **normalizada por lote** (p.ej. "4500 CLP @0.01 lot" ≡ 450.000 CLP/lote). La invarianza de
   escala se audita (rompedores conocidos: reglas cash, `trade_stops_level`, redondeo lot-step).
2. **"Ganadora" = neto positivo en backtest real-tick.** NO "mejor que S6/ST". La dependencia del
   top-K es **descriptor, no gate** (el trend-following es asimétrico-positivo por diseño; las top-K
   SON la estrategia). Anti-suerte = bootstrap por bloques a nivel de episodio + holdout, no amputación.
3. **No-contaminación del orquestador.** Rankings de valor esperado pueden EXTENDER profundidad;
   JAMÁS recortar amplitud de áreas pedidas. Toda área del listado se explora con grilla suficiente.
4. **Hipótesis-only.** Ningún hallazgo se comunica como veredicto fuera de memos de interpretación
   (Opus) separados de los datos. Prohibido "la evidencia apunta a" en artefactos de datos.
5. **Motor congelado.** Inventario de modificaciones (§4.T0.6) → implementación conjunta (TDD, sobre
   copias) → suite golden + **A6 empírico** tras CADA modificación → freeze por SHA → el programa
   entero corre anclado a ese SHA. Cambio posterior = enmienda formal + re-validación completa.
6. **Real-tick = sustrato de veredicto.** Barras solo para estadísticas de señal matemáticamente
   exactas sobre cierres (conteos de gate, correlaciones), etiquetadas `substrate=bars, non-verdict`,
   jamás deciden solas. Barras M15 como sustrato de veredicto: ELIMINADAS.
7. **Routing LLM 70/29/1.** Sonnet 5 high ≈70% (implementa con spec cerrada / investiga con reporte
   objetivo SIN interpretación; siempre despachado con información completa). Opus 5 high ≤29%
   (orquesta + TODA interpretación/ideación; **máx 2 subagentes en paralelo**; nunca 2 sobre los
   mismos ficheros). Fable 5 ≈1% — reservado a 3 momentos (§7.4).
8. **Automatización tradicional primero.** Colas de backtests, regeneraciones, descargas y conteos
   los ejecutan runners Python con manifiestos declarativos. El LLM planifica e interpreta; no
   "corre un backtest, mira, corre otro".
9. **Trazabilidad absoluta.** Todo artefacto lleva `{run_id, area, experimento, config_hash,
   substrate_id, engine_sha, git_sha, etapa, generador, timestamp}`. Ledger maestro append-only.
   Prueba de aceptación: cualquier número rastreable a su corrida en <1 minuto, a 2 meses vista.
10. **Enmiendas solo en fronteras de fase**, con causa escrita, jamás a mitad de experimento.
    Ideas nuevas → backlog de observaciones (NO crea tareas hasta frontera).
11. **R1-bis (verbatim, sin excepción):** los S6/ST (y S7 histórica) VIVOS se preservan
    byte-identical. Toda modificación va sobre copia independiente (cfg deep-copy, módulo nuevo,
    banda mágica nueva). Quien concluya que hay que tocar el original está equivocado: PARAR y escalar.
12. **MT5:** `CUENTAS.md` = fuente única. Cuenta **902 = NO-R&D**: solo lectura vía `MT5_Tester_2`,
    PROHIBIDO modificarla/agregarle nada, jamás corre posiciones desde este equipo, credenciales
    jamás persistidas. Attach-only global; toda orden (en la DEMO autorizada) requiere
    `guard_cuenta.assert_demo()`. Reales READ-ONLY.
13. **Anti-drift:** "hecho" = artefacto verificable (fichero en ruta esperada + fila en ledger +
    hash), jamás la palabra de un agente. Verificador ≠ implementador.
    `superpowers:verification-before-completion` obligatoria. Anomalía ⇒ **STOP + escalar al user**;
    prohibido "aceptar" errores de resultado/método o reducir alcance sin enmienda escrita.
14. **Holdout sagrado** sellado en Fase 0 (§4.T0.12): tramo intocado + hipótesis pre-registradas +
    UNA sola evaluación final. Quien lo lee dos veces, lo quema.

## §1 · Objetivo y filosofía

- **Composición de mejoras marginales → retornos exponenciales.** No se busca una única gran
  palanca: se busca al menos una mejora pequeña en CADA área, compuestas como grilla de variantes
  tratadas como hipótesis experimentales. Mejoras modestas son EXACTAMENTE lo que se busca.
- **Gemas en bruto:** S6/ST logran neto positivo consistente en live-test y backtests SIN tocar las
  áreas que la literatura señala como de mayor beneficio. El programa simultáneamente (a) pule
  estas estrategias incompletas y (b) busca edge estructural. El techo está inexplorado por construcción.
- **Todo respaldado en evidencia** — de literatura (formal e informal) o experimental propia. Que
  no se escape absolutamente nada.

## §2 · Estado de partida (verificado 2026-08-10)

| Ítem | Estado |
|---|---|
| Roster vivo (live-test, otro equipo) | **S6 + ST**, cuenta Capitaria **902** (50M CLP inicial), **1 ficha de 0.67 c/u, UNA posición abierta a la vez**, ~2 semanas corriendo. **S7 murió** (consistentemente peor que S6 en live). |
| Substrato reparado | 7 meses, 2.542 posiciones, CSVs regenerados (R1-R3 hechas) |
| Ticks Capitaria locales | 2026-01-01→07-24 (52,6M); servidor sirve ~7 meses RODANTES |
| Lake barras | M1 4,3 meses · M2 8m · M5 1,5a · M15 4,3a · H1 4,6a (tope por barras, ventana desliza) |
| Ticks AVA | **NUEVO**: cuenta creada; encargada regional confirmó viabilidad de descarga ≥2 años (objetivo 4). Instrucciones pendientes de entrega del user. Spread AVA < Capitaria (máx y mín). |
| Disco | C: 25 GB libres (95%, crítico) · D: 154 GB libres → AVA (~8-15 GB parquet) cabe en D: |
| Fidelidad A6 | **NO medida post-reparación** (lo más cercano: docs 07-14/07-18, pre-reparación) |
| Task 12 / challengers | CONGELADO: nada sube a live-demo hasta terminar la investigación completa y revisar juntos la grilla de netas positivas |
| Backup del plan | Hecho (ver header) |

### §2.1 · CUARENTENA (números bajo hipótesis de reconciliación — NO usar como veredicto)

`PF 1,03 / neto 39,5MM / maxDD 129MM / patas reverse ≈ −108MM` describen **UNA configuración**
(3 estrategias incl. S7 muerta, 3 fichas clonadas, gates de la época) sobre un sustrato cuya
validez es justo lo que A6 confirmará o refutará. El sistema vivo (S6+ST, 1 ficha, 1 posición,
spread-gated) es OTRO sistema, con registro live consistentemente positivo. Hipótesis
pre-registradas, ninguna privilegiada:
- **H-A** El backtest mide otra config que la viva → ambos correctos a la vez.
- **H-B** La ventana live aún no alcanza significancia → compatible con cualquier PF subyacente.
- **H-C** Error residual de medición → A6 lo detectará.
Resuelven: A6 (§4.T0.7) + Autopsia (§5) + A3 (§7.A). ⚠️ Tres docs con prosa obsoleta
(b1-wait-curve, b1-robustness, long-backtest-queue): leer SIEMPRE el JSON, no la prosa.

## §3 · AL INICIO DE CADA SESIÓN FRESCA

🔴 **Protocolo canónico y obligatorio: `research/protocolos/00-inicio-de-sesion.md`.**
Resumen: (1) pinned del brain → (2) leer `research/README.md`, `CHARTER.md`, `TRACKER.md`,
`DECISIONES.md` y este plan → (3) invocar las skills de `research/protocolos/01-skills.md`
(mínimo: `dispatching-parallel-agents` antes del primer paralelo, `subagent-driven-development`
para el ciclo por tarea) → (4) verificar que la fase previa esté `[x]` → (5) revisar bloqueos
activos → (6) ningún número sin confirmar su lineage en el LEDGER; ninguna prosa vieja sin
re-leer su JSON.

**Antes de actuar debes poder responder:** en qué fase estamos y cuál es su criterio de cierre ·
cuál es la siguiente tarea ejecutable y si está desbloqueada · qué modelo la ejecuta y en qué rol ·
qué artefacto exacto debe existir para declararla hecha · qué decisiones del user la restringen.

## §ROUTING (va VERBATIM en cada brief)

> El subagente principal es **Sonnet 5 high effort** (~70% del trabajo): implementa con spec
> técnico cerrado y detallado (con cuidados, pointers, contexto) o investiga reportando
> objetivamente números/rutas SIN interpretaciones, recomendaciones ni decisiones. **Opus 5 high**
> (≤29%): orquesta (máx 2 paralelos, jamás 2 sobre mismos ficheros) e interpreta resultados,
> propone mejoras, genera ideas — todo lo que requiere razonamiento complejo. **Fable 5** (~1%):
> exclusivo para los 3 momentos de §7.4. A Sonnet NUNCA se le pide interpretar.

## §NORMAS (bloque copy-paste para TODO brief)

> R1-bis verbatim (§0.11). Paralelismo máx 2, nunca mismos ficheros; ficheros compartidos
> (tracker, planes, ledger) son del CONTROLADOR. Git: commit scoped `git add -- <rutas>`;
> ni `git add .` ni `-A` ni rebase ni push. Pytest FOREGROUND siempre, suites dirigidas
> (13 rojos conocidos por env-leak del host; lentos en cuarentena `slow`). MT5: §0.12.
> Honestidad: todo número lo calcula código; lo no evaluable se declara no evaluable; registro
> aditivo. Anomalía ⇒ STOP + escalar. "Hecho" = artefacto verificable (§0.13).

---

# §4 · FASE 0 — PREPARACIÓN (bloqueante; nada de investigación corre antes)

| # | Tarea | Routing | Notas |
|---|---|---|---|
| T0.1 | Backup del plan previo | — | ✅ HECHO 2026-08-10 |
| T0.2 | Propuesta limpieza disco C: (95%) | Sonnet | SOLO propuesta; cero borrado sin aprobación del user |
| T0.3 | **R6-AVA**: descarga real-tick ≥2 años (objetivo 4) | Sonnet (spec cerrada tras instrucciones del user) | Registrar en ledger con lineage; validar integridad (huecos, duplicados, calendario); destino `data/lake_ticks_ava/XAUUSD/` en D: |
| T0.4 | **Top-up ticks Capitaria** (ventana 902 completa) | Sonnet | ⚠️ VENTANA RODANTE (~7 meses): descargar YA la ventana jul-ago antes de que ruede fuera. Mismo servidor `Capitaria-All` — 🔴 **JUSTIFICACIÓN SUPERADA: ver ENMIENDA E-01 (§15).** El motivo real es que A6 Pata A necesita esa ventana |
| T0.5 | **Export historial 902** vía `MT5_Tester_2` | Sonnet | Deals+órdenes+balance. SOLO LECTURA (§0.12) |
| T0.6 | **Inventario + implementación de modificaciones de motor** (12 ítems, abajo) | Specs: Opus · Implementación: Sonnet (TDD) | TODAS JUNTAS antes del freeze; sobre copias (R1-bis) |
| T0.7 | **A6 — Fidelidad** (diseño de dos patas, abajo) | Implementación Sonnet · Análisis Opus | GATE de todo el programa |
| T0.8 | **Freeze del motor** (tag SHA) | Controlador | Tras T0.6+T0.7 verdes |
| T0.9 | **Research OS** (estructura §10: carpetas, ledger, runners, plantillas, tracker, protocolo) | Sonnet con spec de Opus | Incluye supervisión durable de watcher/ingesta |
| T0.10 | **Literatura formal** (7 áreas, abajo) | Recolección Sonnet · Memos Opus | Cada área ANTES de cerrar su grilla |
| T0.11 | **Pipeline YouTube** (3 etapas, abajo) | Sonnet (descarga+conteo) · decisión con user | Lista de 25-27 videos pendiente de entrega |
| T0.12 | **Holdout**: definir partición (decisión user) + SELLAR | Controlador | Propuesta en §13.1 |
| T0.13 | **Modelado hora muerta** (desplazante) | Sonnet · análisis Opus | 3 fuentes: ticks AVA, ticks Capitaria 7m, historiales MT5 (~3 meses reales en suma) |

### §4.1 · T0.6 — Inventario de modificaciones de motor (cerrar con el user ANTES de implementar)

1. **Harness de replay pareado**: K políticas de salida sobre UN stream de entradas; cada entrada
   recibe K resultados (estadística pareada). Base: mecanismo wrapper/masks existente.
2. **Ratchet como schedule**: `lock_frac = f(percentil de ganancia | covariables)`; escalones
   configurables; NUNCA extiende el SL inicial (assert, no convención).
3. **Maquinaria familia C**: cooldowns, event-ificación, condiciones de re-entrada. El
   `reentry_enable` existente tiene semántica INVERTIDA (solo tras trail-out): se construye la
   nueva AL LADO, sin tocar la vieja.
4. **Pipeline de features de zona** (D2): todos los métodos de marcado + firmeza + distancias.
5. **Feed multi-TF a decisiones**: indicadores de TF inferior disponibles en entrada (D1) y salida (B8).
6. **Condicionamiento por sesión/ventana-de-spread** (D3/A4).
7. **Knob de concurrencia/dirección**: máx posiciones simultáneas + restricción direccional
   (para familia LS). Hoy no existe.
8. **TP cash normalizado por lote** (§0.1).
9. **Módulo familia F**: momentum M10/M1 + variantes; modos de evaluación closed-bar E intrabar
   (ambos honestos sobre ticks).
10. **Adaptador de datos AVA** + **overlay de costos por bróker** (spread empírico Capitaria
    condicionado a hora, aplicable sobre ticks AVA; y viceversa).
11. **Instrumentación de camino de posición**: grabar la matriz de indicadores (§5.2) en apertura,
    durante (por barra/tick) y cierre de cada posición. Sin esto no hay autopsia.
12. **Replay con inyección de eventos**: cierres manuales inyectados como salidas forzadas en su
    timestamp (sin esto, A6 diverge en cascada tras el primer cierre manual).

Protocolo por modificación: spec cerrada (Opus) → test rojo → implementación mínima → verde →
suite golden → commit scoped. Tras la ÚLTIMA: A6 completo → freeze.

### §4.2 · T0.7 — A6: Fidelidad del motor (diseño cerrado)

**Objetivos:** señal **100% bit-idéntica**; fills por bandas; neto por ventana: tracking error
≤0,3% (≡99,7%) / ideal ≤0,15% (≡99,85%).

- **Pata A — fidelidad del motor** (la que da el 99,7%): replay de S6+ST con la config viva EXACTA
  (1 ficha 0.67, una posición a la vez, roster S6+ST, gates activos) sobre los ticks de
  **Capitaria misma** (T0.4) para la ventana de la 902; comparar contra el historial real (T0.5).
  - Cierres por estrategia: ≥99,7% idénticos (entrada+salida+precios dentro de tolerancia).
  - Cierres manuales: SOLO la apertura debe ser idéntica; el cierre se INYECTA (motor mod #12).
  - Medir por estrategia y por motivo de salida; reportar distribución de desviación de fill y
    asimetría direccional (stops de largos en caídas rápidas).
- **Pata B — transferencia de feed**: misma estrategia sobre ticks AVA vs ticks Capitaria en el
  solape → cuantifica divergencia de feed y calibra el overlay de costos (motor mod #10). Ninguna
  cifra AVA-cruda se compara contra cifras Capitaria sin declarar el ajuste.
- Sin Pata A verde no corre NADA del programa. Sin Pata B, los 4 años AVA no son sustrato de veredicto.

### §4.3 · T0.10 — Literatura formal (una revisión por área, compartimentada)

(1) Salidas/trade-management y optimal stopping — incluye métodos modernos para MFE/MAE:
triple-barrier + meta-labeling, análisis de supervivencia/hazard sobre excursiones (responde
"¿cuántas veces se recuperó desde X?"), regresión cuantílica de MFE condicional; (2) régimen y
lateralidad; (3) S/R, zonas, números redondos, microestructura de barreras; (4) sizing/riesgo/
gestión de equity-curve; (5) validación estadística de backtests (DSR/PBO/CPCV, actualizaciones
recientes); (6) riesgo de eventos/noticias en oro; (7) momentum multi-TF.
**Entregable por área:** bibliografía anotada + memo de integración ("qué cambia en nuestra
grilla y por qué") ANTES de cerrar la grilla de esa área.

### §4.4 · T0.11 — Pipeline literatura informal (YouTube)

Etapa 1: descargar transcripciones de los 25-27 videos (skill `yt-transcripts`, batch, a disco,
SIN leerlas). Etapa 2: reporte tokens/video + costo estimado por modelo (Anthropic vs Vertex AI
Gemini — ~USD 100/mes en créditos disponibles; verificar costo-eficiencia con números al decidir).
Etapa 3: decidir routing CON el user. **Regla de hierro: un video = un contexto de análisis;
JAMÁS mezclar videos en una misma pregunta** (compartimentación anti-contaminación).

---

# §5 · FASE A0 — AUTOPSIA DE POSICIONES (antes de cerrar el diseño de salidas)

**Fuentes:** historial 902 (T0.5) · historiales MT5 demás cuentas (~3 meses en suma) · ~2.542
posiciones del backtest reparado · ticks Capitaria de las ventanas (reconstrucción de camino).

### §5.1 · Dossier por posición (4 capas)
1. **Contexto de entrada** — snapshot completo de la matriz de indicadores (§5.2) al abrir.
2. **Camino** — curva de excursión MFE/MAE en el tiempo (tick/M1) + evolución de indicadores
   durante la vida (motor mod #11).
3. **Contexto de salida** — qué cerró, estado de indicadores, y qué hizo el precio DESPUÉS
   (¿la salida fue buena ex-post?).
4. **Contrafactuales** — qué habrían hecho K salidas alternativas sobre esa entrada (harness pareado).

### §5.2 · Matriz de indicadores (cerrar con el user antes de correr)
RSI · momentum(n) varios n/TF · ATR multi-TF + percentil + pendiente · **distancia a S/R y zonas
por múltiples métodos y horizontes: intradía, día anterior, 2-3 días, semana** · estados/steps SAR ·
pendientes EMAs · CHOP + pendiente · ADX · **posición del precio en el rango de k días**
(operacionaliza lateralidad) · tick-volume · hora/día/sesión · spread vigente · proximidad a hora
muerta · ventana de noticias (§7.D3-news).

### §5.3 · Análisis y productos
- Expectancy condicional por covariable con **split de muestra** (descubrir en mitad A, confirmar
  en B) y **corrección FDR** por comparaciones múltiples. Todo hallazgo → hipótesis pre-registrada.
- **Reconstrucción de episodios de re-entrada** (C0): cadenas cierre→reapertura; P&L por episodio;
  **procedencia de las grandes ganadoras** (¿re-aperturas tras reversión pequeña?); condicionado
  por régimen. PREVIO a la grilla C.
- **Hipótesis de lateralidad** (Familia H): definición empírica de "suficientemente lateral"
  (candidatos: contención en rango 1/2/3 días, ancho de rango vs ATR, eficiencia direccional);
  test de la hipótesis sobre S6/ST.
- **Análisis de recuperación:** curvas de supervivencia — P(recuperar | profundidad MAE, tiempo
  bajo agua, régimen). Insumo directo de salidas por hazard (B9).
- Productos: parquet de dossiers (capa máquina) + estadística + **inventario escrito en formato
  tesis** (cuantitativo y cualitativo) + backlog de ideas. Consumidores: B, C, D2, H, A6, §2.1.

---

# §6 · FASE S0 — SCREENING RETROSPECTIVO DE FEATURES (costo ~0, reglas pre-fijadas)

Features candidatas se evalúan sobre posiciones/señales YA registradas (expectancy condicional,
sin backtests nuevos): cruces de ATR multi-TF · sumas/combinaciones de momentum (1m+10m, etc.) ·
pendiente de CHOP · Crystal Heiken Ashi · zonas del indicador Supply&Demand (vs las nuestras) ·
score D1b (nº TFs alineados) · índice de coherencia D1f · frecuencia y costo de señales de la
familia F (kill-criteria de costos: señales/día × spread vs envolvente de edge — pre-registrado).
**Regla de decisión pre-fijada:** separación con IC que excluye 0 → su grilla entra a la cola;
si no → registro de negativos (y NO se corre). Así el plan queda cerrado aunque las respuestas no.

---

# §7 · CATÁLOGO DE FAMILIAS (grillas exactas)

> Reglas transversales: sin priors direccionales (toda grilla incluye `off` y ambas direcciones);
> exhaustividad por estrategia donde sea mecánicamente posible; regla de meseta (meseta → refinar
> paso ≤0.25); re-litigar quemados solo con causa; harness pareado siempre que aplique.

## Familia A — Instrumento y medición
- **A2 Mapa MFE/MAE** por posición: % de perdedoras que tocó ≥{0.25,0.5,1,1.5,2}R en verde, por
  estrategia + los métodos de literatura de §4.3(1). Calibra B. (Se absorbe en §5 Autopsia.)
- **A3 Economía de la reversa** (HIPÓTESIS, plan pre-registrado): ¿las patas de `stop_and_reverse`
  suman o restan? ¿cuánto spread quema el ciclo? Decide E3. En cuarentena §2.1 hasta A6.
- **A4 Expectancy condicional al spread** {0.50, 0.60} + comportamiento intra-ventana-0.5 vs general.
- **A5 Experimento natural S6-vs-S7** (misma señal, salidas distintas; datos históricos; S7 muerta
  en live pero su historia sirve): valor del BE-1R neto del churn.
- **A6** → §4.2 (Fase 0).

## Familia B — Salidas y protección de utilidad (área de mayor presupuesto)
- **B1 Breakeven, las tres:** `be_at_r ∈ {off,0.25,0.5,0.75,1.0,1.25,1.5,2.0}` ×
  `be_offset ∈ {0.5,2,5}` pips (off en S7 = testear remover el vivo; ST vía wrapper B7c).
- **B2 Ratchet fijo:** `lock_frac ∈ {0.25,0.4,0.5,0.6,0.7,0.8}` + chandelier
  `ratchet_atr_k ∈ {2.0,2.5,3.0}` (excluyentes).
- **B2-P Ratchet percentílico (schedule):** `lock_frac = f(percentil de ganancia)` calibrado de la
  distribución EMPÍRICA (sustrato reparado + 902; §5). Grilla: armado {BE, BE+spread, +0.5R, +1R} ×
  curvas de devolución {90%→…→5% del peak por tramos} × búsqueda de meseta × variantes con
  covariables (régimen, distancia a zona — regresión cuantílica). Calibrar meses 1-4, validar 5-7,
  re-validar en largo. Entregable: frontera media↔varianza (configs conservadora/agresiva).
- **B3 Piso ATR del trail:** `trail_atr_floor_k ∈ {1.0,1.5,2.0,2.5,3.0}`.
- **B4 Trailing trifásico (diseño user):** F1 supervivencia→BE; F2 apretar hasta
  `W* = L̄·(1−WR)/WR` (computado del sustrato reparado, por estrategia); F3 runner con apriete POR
  INDICADOR {agotamiento momentum, desaceleración AC, proximidad a zona opuesta (D2)}.
  Transiciones R ∈ {(1,2),(1,2.5),(1,3),(0.75,2)}.
- **B5 TP re-exploración:** `tp_r ∈ {0.5,0.75,1.0,1.5,2.0,3.0}` × por-ficha {F1, F1+F2} ×
  cuantizado a zona (D2) × con/sin política C acoplada + **TP cash normalizado** (450.000 CLP/lote
  = la hipótesis 4500@0.01 del trader, una entre decenas). Nota doctrinal: el quemado viejo cubría
  SOLO TP fijo a-priori; un trailing en positivo es un TP a-posteriori — familia
  "salidas condicionadas a utilidad" ABIERTA.
- **B6 Time-stop:** `max_hold_bars` derivado de curva expectancy-vs-barras (y ver §12: re-correr
  PX sin max_hold).
- **B7 SuperTrend programa propio:** (a) romper always-in con multi-definición de plano:
  {flip-count K barras, ADX(14), |precio−línea|/ATR, CHOP(14), **pendiente de CHOP**, pendiente
  LR(20)} × 3 umbrales c/u; (b) cierre-a-través + buffer (SL desastre línea±k·ATR; salida solo por
  CIERRE cruzando banda); (c) wrapper BE/ratchet (ST no tiene nada; WR≈23%); (d) `mult {2.0..3.5}`,
  ATR period {7,10,14,21}, supresión flip cerca de zona.
- **B8 Salidas multi-TF:** trailing/salida modificados por indicadores de TF inferior (momentum
  rápido, SAR inferior); implementado como extensión del aparato B4-F3; SIEMPRE acoplado a política
  C (churn). Grilla de TF inferior {1m,2m,5m} × indicador × umbral.
- **B9 Familias nuevas de salida:** hazard-exit (salir si P(recuperación|estado) < umbral, de §5.3) ·
  stop tiempo-bajo-agua (percentil τ de recuperaciones históricas) · stall multi-TF (sin nuevo
  máximo en K barras ×ATR) · salidas conscientes de zona (apretar/parcial cerca de zona opuesta) ·
  sets conmutados por régimen de vol · session/spread-aware (no salir voluntariamente en spread
  ancho salvo desastre) · flatten pre-noticias (D3-news) · clasificador de forma de excursión
  (prefijo del camino como predictor) · gestión de equity-curve a nivel estrategia (caps diarios,
  trailing sobre equity).
- **B★ Núcleo heredado:** `init_sl_range_k ∈ {1.0,1.5,2.0,2.25,2.5,3.0,3.5}` (guiado por MAE) ·
  trail base {50,75,100,125,150,250} pips + 2-3 derivados de percentiles MFE · esquema SL
  {range-SL, ATR-SL, estructural-swing} · AC-modulate {off,0.25,0.5} · asimetría de salida L/S.

## Familia C — Políticas de re-entrada (companion obligatorio de B)
- **C0 (PRIMERO): análisis de episodios** — §5.3. La "propiedad anti-trampa" del BE es hipótesis
  NO confirmada; procedencia de grandes ganadoras; regímenes. Recién después, la grilla:
- C1 cooldown K∈{1,2,3,5,8} barras · C2 event-ificación (gate pasa por FALSO) on/off × {1,2} ·
  C3 solo a mejor precio, margen {0,0.5,1}·ATR · C4 confirmación reforzada on/off · C5 tamaño
  reducido {0.5,0.33} restaura tras win · C6 máx re-entradas/episodio {1,2,3,∞} · C7 condicional a
  MFE de la pata cerrada X∈{0.25,0.5,1.0}R · C8 SAR-reset on/off × TF · C9 bloqueo por zona
  consumida (D2) · C10 tiempo-O-distancia (C1×C3) · C11 asimétrica por tipo de cierre (post-BE
  libre, post-pérdida gateada) · C12 presupuesto por episodio Z∈{1.5,2,3}R.
- **C13 (nueva) condicionada a dirección** (política distinta para re-entrar long vs short) ·
  **C14 (nueva) condicionada a régimen/condiciones de mercado** (lateral vs tendencia, spread).
- ST dialecto: C2 ≡ exigir cierre-confirmación tras stop-out (cruce B7b).

## Familia D — Entradas, contexto y calidad de señal
- **D1 Multi-TF INFERIOR:** D1a gate binario SAR {1m,2m,5m} × k-de-m {1/3,2/3,3/3} × **step SAR
  ampliado: {0.001,0.002,0.005,0.01,0.02,0.05} ∪ {0.02,0.1,0.3} existentes** (TOKATA nunca
  encontró el codo hacia abajo; sus resultados = direccionales, motor faulty; tarea de auditoría
  documental: qué TFs, qué insights quedaron anotados) · D1b score graduado (nº TFs = nota, no
  veto; validación retrospectiva S0, costo 0) · D1c micro-timing (M15 arma, 1m/5m confirma; SL
  anclado a estructura del TF inferior ⇒ más R ⇒ arma antes BE/ratchet/fases) · D1d frescura del
  flip (reciente vs maduro, ambas direcciones) · D1e variantes de indicador (SuperTrend inferior,
  AO/AC 5m) · D1f índice de coherencia 1m→H1 (gate + score sizing + feature meta-label).
- **D2 Zonas — máximo depth (FOCO):** métodos {swings fractales · pivotes S1-S3/R1-R3 · H/L
  día/semana/sesión previos · números redondos oro 00/50/25 · perfil volumen-tick HVN/LVN ·
  opening range/initial balance · bordes de gaps de reapertura · extremos Donchian · score de
  confluencia · **zonas del indicador Supply&Demand de tienda** (S0 primero: ¿agregan sobre las
  nuestras?)} × firmeza {toques ≥1/2/3 × decay recencia × mechas de rechazo × edad} × usos {permiso
  de entrada espacio ≥α·R, α∈{1,1.5,2} ACOPLADO al armado del BE · ancla del SL · cuantización TP
  (B5) · supresión flip ST (B7) · apriete F3 (B4) · bloqueo re-entrada (C9)} × unidad de distancia
  {R, ATR, múltiplos de spread} (cuál es la correcta = hallazgo) × **condicionamiento intra-ventana-
  spread-0.5 vs general** (operamos solo en la ventana de mayor volumen; las zonas pueden
  comportarse distinto dentro).
- **D3 Contexto temporal y régimen:** espera post-apertura EN BARRAS {0,2,3,4,5,6} (N3=45min vs
  N4=60min: **test de significancia pareado pendiente**; verificado in-sample N3 93,9MM > N4
  80,3MM) · hora/día/sesión · asimetría L/S · spread-regime (A4) · **familias de régimen COMPLETAS,
  SIN representante único** (grilla por familia; la colinealidad ADX≈CHOP≈ER se MIDE primero como
  resultado, no se asume): ADX {umbrales×períodos} · CHOP {nivel × **pendiente**} · Variance-Ratio ·
  Hurst · HMM · **ATR re-exploración con causa registrada** (solo se quemó ATR14-percentil-como-
  probado): períodos {7,14,21,50} × múltiplos × ventanas de percentil × pendiente × **cruces de ATR
  multi-TF** (2-3+ TFs) · **Crystal Heiken Ashi** (screening S0; método fiel: export de buffers
  desde terminal del user o reimplementación + chequeo de equivalencia; sin poda por correlación —
  medir valor incremental Y standalone) · **noticias**: gate de blackout retro-testeable (calendario
  de eventos de alto impacto × resultados de posiciones; ±X min como palanca); estrategias
  news-driven = plan dedicado (backlog).

## Familia LS — Concurrencia direccional (variantes directas de las vivas; NO gateada)
- **LS1:** permitir segunda posición SOLO si es de dirección opuesta (jamás dos iguales). Cuenta
  hedging confirmada. Requiere motor mod #7.
- **LS2 (refinada con resultados de LS1):** política de alternancia — cuándo re-permitir short
  tras pasar a long y viceversa, máx alternancias por episodio, condiciones {señal, zona, P&L,
  cooldown}. Grilla derivada de LS1 + C.

## Familia E — Estructura y recombinación (🔒 gateada)
- **E0 CHECKPOINT CONVERSADO (obligatorio antes de E):** revisión conjunta con el user de TODAS
  las configs netas positivas + S6/ST, con datos live-demo Y backtest real-tick. "Ganadora" =
  neto positivo (§0.2), NO "supera a S6/ST".
- E1 escalera de fichas diferenciada (plantilla TOKATA F1-patrón/F2-flip/F3-runner, ~206 celdas
  diseñadas jamás corridas, re-correr honesto; números viejos descartados). Nota: NO hay ladder
  clonado en el live (1 ficha); esto es diseño de investigación. Costo del ladder: al final.
- E2 S6+S7 como una estrategia de 6 fichas (histórico; S7 muerta en live — evaluar si conserva
  sentido tras A0). · E3 `stop_and_reverse` {on,off} (decidido por A3). · E4 piramidación (último).
- **E5 Ensambles por perfil de riesgo:** solo con configs que pasaron gates + holdout; pesos NO
  optimizados (equal-weight / inversa-vol). Curva tamaño↔drawdown: explorar como hipótesis y
  CONVERSAR puntos tolerados/pros/contras con el user. **Vol-targeting: AL FINAL del programa**
  (rompería comparabilidad antes).

## Familia F — Momentum del trader (nueva; spec literal + familia completa)
- **F1 (spec LITERAL del trader, preservada para mostrar/discutir):** tendencia = MOM(2) en M10
  (>100 alcista, <100 bajista); entradas = MOM(2) en M1 cruzando 100 (compra >100, venta <100);
  salida = monto fijo (450.000 CLP/lote ≡ 4500@0.01 — hipótesis normalizada). ⚠️ La spec no define
  salida perdedora: F1 se corre fiel PERO acompañada de brazos con envolvente de riesgo
  obligatorios {SL desastre grid, salida por flip del M10}; reportar SIEMPRE MAE máx, colas,
  exposición a swap (posiciones multi-día con TP de ~$4,7/oz).
- **F2 Variantes:** `mom_period ∈ {2,3,5,8}` × TF señal {M1,M2,M5,M6,M10,M15} × TF tendencia
  {M10,M15,M30,H1} × umbral {línea 100 · franja 100±δ · histéresis n barras · aceleración ΔMOM} ×
  salidas {cash-TP grid, top-3 salidas existentes FOREX+TOKATA, grilla B} × **modo de evaluación
  {closed-bar, intrabar} como DIMENSIÓN de grilla** (ambos honestos sobre ticks; conclusiones TK
  previas = direccionales, motor faulty — no restringen el diseño).
- **F0 kill-criteria S0 (pre-registrado):** contar sobre ticks señales/día del gate literal ×
  costo de spread vs envolvente de edge (ancla: campeones actuales ≈ +$0,24/oz/trade neto; spread
  0,50-0,60 = 10,5-12,8% del TP de $4,7). Si el costo domina, la spec literal se documenta y la
  exploración vive en variantes lentas — con números, no con prior.
- **TK:** TK-Momentum entra como pariente de F. **TK-BW: gated por rediseño de entrada con
  MÚLTIPLES alternativas** (hoy geométricamente incapaz); gate de éxito = neto positivo, no
  "toma posiciones". Observación histórica registrada COMO HIPÓTESIS a testear (no como regla):
  "TFs más rápidos han terminado siempre peor".

## Familia G — Composición multivariable (embudo, no búsqueda libre)
- Solo entran a composición features que INDIVIDUALMENTE sobrevivieron S0 (IC excluye 0).
- Formas pre-registradas de baja dimensión: k-de-m condicional (≡D1a extendido) y combinaciones
  lineales con pesos fijos/monótonos. PROHIBIDO el ajuste libre de superficie. Cap dimensional.
- El haircut DSR cuenta TODO lo intentado. Destino: features validadas → meta-labeling (techo).
- La investigación PUEDE dejar pendientes declarados aquí (etapas con recomendaciones; §0.10).

## Familia H — Lateralidad / mean-reversion (condicional al test de §5.3)
- Si la hipótesis se confirma: gate on/off para las vivas en lateral · **familia dedicada de
  range-trading** (fade de extremos del rango con lógica de zonas — white space: todo el roster
  actual es tendencia) · conmutación por régimen · indicador propio/adoptado · ideas innovadoras
  (backlog abierto). Si no se confirma: registro de negativos con la evidencia.

---

# §8 · SECUENCIACIÓN Y DEPENDENCIAS (DAG)

```
FASE 0 (T0.1..T0.13) ── freeze motor + A6 verde + Research OS + holdout sellado
   └─► FASE A0 Autopsia (requiere T0.5, mod #11, ticks)
         └─► S0 Screening (reglas pre-fijadas)
               └─► Ola de grillas: B, C (tras C0), D, LS, F, G, H   [harness pareado; runners]
                     └─► Puerta estadística §9 (gates: neto>0 + consistencia; descriptores: top-K)
                           └─► Cola de backtest largo real-tick (AVA 2-4a, con overlay validado B)
                                 └─► E0 CHECKPOINT CONVERSADO con el user
                                       └─► Familia E (🔒) → HOLDOUT (una pasada) → SÍNTESIS FINAL
```
Dependencias duras: R6→(F largo, sustrato largo) · T0.5+mod#11→A0 · A0→(B2-P, B9-hazard, C-grilla, H) ·
A3→E3 · A6→TODO · S0→G y F0. Challengers a live-demo: SOLO tras E0/holdout y decisión explícita del user.

# §9 · ESTADÍSTICA Y VALIDACIÓN

- **Diseño pareado por entrada** para TODA comparación de salidas (misma entrada, K políticas):
  elimina la varianza común; máxima potencia.
- **Bootstrap por bloques a nivel de EPISODIO** para IC de expectancy/PF/maxDD (reemplaza la
  amputación top-K como control anti-suerte).
- **DSR/PBO/White-SPA** contando TODO lo intentado; **walk-forward purgado+embargado / CPCV**.
- **FDR** en la autopsia (comparaciones múltiples masivas); split descubrimiento/confirmación.
- **Regla de meseta** (meseta → refinar paso ≤0.25; picos aislados = sospecha de overfit).
- **Puerta D170'** (enmendada §0.2): gates = neto>0 real-tick + consistencia mensual; descriptores
  informativos = recorte top-K, concentración. Significancia pre-fijada por A/B ANTES de correr.
- **Test pendiente registrado:** N3 vs N4 pareado (45 vs 60 min).
- **Holdout:** una sola evaluación final, hipótesis pre-registradas (§0.14).

# §10 · RESEARCH OS — trazabilidad y formato tesis

- **Corpus (formato tesis):** índice general vivo · una sección por área con sub-índice ·
  por área: `01-hipotesis/` (pre-registros) · `02-specs/` · `03-runs/` (manifiestos) ·
  `04-resultados/` (capa máquina, JSON/parquet) · `05-analisis/` (memos Opus, interpretación EN
  CUARENTENA de los datos) · `06-observaciones-backlog.md` (ideas nuevas; NO crea tareas) ·
  síntesis final del programa ("el libro"). Árbol exacto se emite en T0.9.
- **Ledger maestro** append-only (una fila por experimento): id, hipótesis, grilla, métrica,
  regla de decisión, estado, substrate_id, engine_sha, artefactos. Cualquier sesión fresca
  reconstruye el estado sin leer 50 docs.
- **Tags obligatorios** en todo artefacto (§0.9). **Plano de ejecución** (runners Python,
  manifiestos declarativos de colas paralelas/secuenciales) separado del **plano de razonamiento**
  (LLM). **Supervisión durable** de watcher/ingesta = activo del programa (la captura continua de
  ticks Capitaria solo crece hacia adelante).
- **Plantillas de brief** (implementador / investigador-objetivo) con §ROUTING y §NORMAS verbatim.
- **Tracker de programa** = única fuente de estado (patrón monday-tracker, probado).

# §11 · PROTOCOLO DE ENMIENDAS Y BACKLOG

Enmiendas SOLO en fronteras de fase, con causa escrita y firma en el tracker; jamás a mitad de un
experimento; grillas congeladas por fase. Ideas nuevas de cualquier agente/sesión → backlog de
observaciones del área (no crean tareas). El programa PUEDE dejar pendientes declarados con
recomendaciones por etapa (directiva user 2026-08-10; especialmente G).

# §12 · REGISTRO DE CUARENTENAS Y QUEMADOS (alcances EXACTOS)

| Ítem | Estado | Alcance exacto |
|---|---|---|
| PF 1,03 / neto 39,5MM / reverse −108MM | 🟡 CUARENTENA | Hipótesis H-A/H-B/H-C (§2.1); resuelven A6+A0+A3 |
| Régimen ATR14-percentil | ❌ quemado / 🔓 re-abierto acotado | Solo la forma probada; grilla nueva D3-ATR con causa registrada |
| Take-profit fijo a-priori | ❌ quemado / 🔓 re-abierto B5 | Veredicto pre-fixes y sin control de re-entradas; trailing-en-positivo ≡ TP a-posteriori (familia abierta) |
| Fills same-bar | 🔒 resuelto | `live_fill_mode=True` obligatorio en todo backtest |
| Netting | ✅ cerrado | Cuenta HEDGING confirmada |
| Cross-instrumento | ❌ eliminado | Directiva user: solo oro |
| Spread como barrido | ❌ eliminado | Se opera solo ≤0.5; A4 mide DENTRO de la condición |
| max_hold_bars=64 confound | 🟡 tarea | Re-correr suite PX SIN max_hold + controles 64/48 solos |
| Base S7 del programa PX | 🟡 tarea | No transplantable; re-correr y documentar diferencias; al final contrastar con lo que corre el equipo live |
| Resultados TOKATA (SAR steps, etc.) | 🟡 direccionales | Motor faulty; re-correr todo bajo motor honesto |
| Prosa de 3 docs (b1-wait, b1-rob, lbt-queue) | ⚠️ obsoleta | Leer SIEMPRE el JSON |

# §13 · DECISIONES DEL USER (resueltas 2026-08-10) Y BLOQUEOS VIGENTES

> Registro canónico y vinculante: `research/DECISIONES.md` (D-01 … D-15). Resumen:

| # | Decisión | Estado |
|---|---|---|
| 1 | **Holdout** — trimestre más reciente del sustrato combinado + un año completo NO adyacente de AVA (p.ej. 2023 entero + may-jul 2026) | ✅ **APROBADO** (D-01). Falta sellarlo (T0.12) con las fechas exactas contra el rango real descargado |
| 2 | **Método de descarga AVA** — GUI: clic derecho en el listado de instrumentos → Symbols → Ticks → instrumento + ticks + fechas → Exportar. Evaluar `copy_ticks_range` programático | ✅ Método conocido (D-02) · 🔴 **BLOQUEADO: faltan credenciales AVA** (el user tiene la clave, falta el login) |
| 3 | **Lista de videos** — 28 entregados | ✅ **T0.11a HECHA**: 28/28 descargados, ~233.723 tokens, NINGUNO leído. Protocolo de análisis: `research/fases/F0-preparacion/PROTOCOLO-REVISION-VIDEOS.md` (D-03) |
| 4 | **Sign-off del inventario de motor** (§4.1, 12 mods) | 🔴 **PENDIENTE del user** — bloquea T0.6 → T0.7 → T0.8 → todo |
| 5 | **Limpieza disco C:** — cruzar tamaño × antigüedad | ✅ Aprobada **SOLO como propuesta** (D-04). 🔴 PROHIBIDO BORRAR: el user borra a mano |

**Bloqueos vigentes** (ver `research/TRACKER.md` §BLOQUEOS): B1 credenciales AVA · B2 sign-off del
motor · B3 cierre de la matriz de indicadores de la autopsia (§5.2, antes de instrumentar el motor
mod #11) · B4 umbrales operacionales de la puerta estadística (§9).

# §13-bis · RESEARCH OS (construido 2026-08-10)

El sistema de trabajo vive en `research/` y es de cumplimiento obligatorio:

| Fichero | Rol |
|---|---|
| `research/README.md` | **Punto de entrada único** de toda sesión/handoff/subagente |
| `research/CHARTER.md` | 14 reglas + §ROUTING + §NORMAS — **bloques VERBATIM en todo brief** |
| `research/TRACKER.md` | **Única fuente de verdad del estado** |
| `research/DECISIONES.md` | Decisiones del user, fechadas y vinculantes |
| `research/LEDGER.jsonl` + `.schema.md` | Append-only, lineage completo por experimento |
| `research/BACKLOG.md` · `NEGATIVOS.md` | Ideas que NO crean tareas · lo que no funcionó, con evidencia |
| `research/protocolos/00..06` | Inicio de sesión · skills obligatorias · plantillas de brief · verificación/anti-drift · enmiendas y trazabilidad · runners |
| `research/fases/<ID>/` | Una carpeta por fase con estructura estándar (hipótesis/specs/runs/resultados/análisis/observaciones) |

# §14 · DELIVERABLES DEL PROGRAMA

1. **El "libro"** (formato tesis §10): corpus completo con resultados por área, observaciones,
   backlog y síntesis final.
2. **Grilla de configs netas positivas** con evidencia completa (real-tick + holdout + IC), para
   la conversación E0 y la decisión de despliegue (del user, siempre).
3. **Ledger + artefactos** con trazabilidad total.
4. **Mejores prácticas por área** respaldadas en evidencia (literatura + experimental), incluso
   donde la mejora sea marginal — se componen.

# §15 · ENMIENDAS (aditivo — el texto original nunca se borra)

### ENMIENDA E-01 · 2026-08-10 · Justificación de la prioridad de T0.4
**Fase / frontera:** Fase 0, antes del primer despacho del programa.
**Causa:** la justificación original de T0.4 ("ventana rodante de ~7 meses: cada semana que pasa
se pierde una semana por atrás") **está mal planteada**. Lo que rueda fuera de la ventana es el
histórico viejo, y ese **ya está capturado en disco**: `data/lake_ticks/XAUUSD/202601..202607.parquet`
(7 ficheros, ~444 MB, escritos 2026-07-25). El hueco jul-ago es **reciente** y seguirá disponible
en el servidor durante meses. La urgencia declarada no existía.
**Cambio exacto:** la prioridad de T0.4 se re-funda sobre su dependencia real —
**A6 Pata A (§4.2) necesita exactamente la ventana en que la 902 operó en vivo**. Sin esos ticks
no se puede medir la fidelidad del motor contra el historial real (T0.5), y esa medición es el
**gate de todo el programa**. T0.4 no compite contra el calendario: compite contra la fecha en que
queremos poder correr A6. Se añade además la interacción con el holdout: la ventana jul-ago es
candidata al *"trimestre más reciente"* de D-01 ⇒ **descargar sí, mirar no**, y T0.12 (sellado) va
inmediatamente después de T0.4.
**Afecta a:** ninguna corrida, ninguna grilla, ningún resultado. **Sin cambio de alcance**: T0.4
descarga exactamente lo mismo, por otra razón y con otra secuenciación aguas abajo.
**Re-validación requerida:** no.
**Firmada por:** user (2026-08-10) · redactada por el controlador (Opus 5).
**Propagada a:** `research/fases/F0-preparacion/00-README.md` (orden de ejecución + riesgos),
`research/TRACKER.md` (fila T0.4 + bitácora).

---

## Self-Review (hecho al escribir)

- **Cobertura:** 31/31 deltas de la conversación 2026-08-09/10 mapeados (charter 1-14; Fase 0
  T0.1-13; A0; S0; familias A/B/C/D/LS/E/F/G/H; §9-§12; decisiones 1-5). Los puntos del user:
  prefacio (objetivos, filosofía, routing, anti-drift, formato tesis) → §0/§1/§7.4/§10; sección 1
  (1.1-1.17) → T0.1, §4.2, §2.3-nota, §0.14, B, §5, C0, D1a-SAR, D2-spread, D3-45/60+familias,
  E0+LS, §0.1-2+E5, §0.6, T0.13, D3-ATR+B5-nota, §12-confounds; sección 2 (2.1-2.22) → T0.2-3,
  A6, DAG-challengers, §0.12, F1/F2, D2-S&D, §11, respuestas 4 preguntas (B5-cash, 902, tienda,
  TK-BW), §2.1-cuarentena, §0.3, §4.1+§0.5, B8/D3-cruces, B2-P, §11, §10, §0.3; sección 3 (A-F)
  → §5, §4.3, §4.4, D3-news, C13-14, §0.8+§10; sección 4 → §5.
- **Sin placeholders:** las grillas llevan valores exactos; lo pendiente de decisión está en §13
  como decisión, no como TBD; los planes por fase se emiten en frontera POR DISEÑO (§11), no por omisión.
- **Consistencia:** nombres de familias/tareas/mods referenciados de forma única; cifras
  verificadas en esta sesión (disco, lake, N3/N4, backup) o citadas de artefactos con ruta.
