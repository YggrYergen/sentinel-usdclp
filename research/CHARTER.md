# CHARTER — Constitución del Programa

> **Estos bloques son OBLIGATORIOS y van VERBATIM en todo brief de subagente.**
> Origen: directivas del user, rondas 2026-07-27 y 2026-08-09/10. No se editan sin enmienda
> firmada (`protocolos/04-enmiendas-trazabilidad.md`).

---

## §A · LAS 14 REGLAS DOCTRINALES

**1 · Comparabilidad es la directiva #1.**
Todo experimento corre a lote estandarizado idéntico (investigación: 0.10/ficha salvo indicación
explícita; la config VIVA es otra cosa y se etiqueta aparte). Resultados SIEMPRE en unidades
por-lote **Y** en múltiplos de R. Toda regla monetaria se especifica **normalizada por lote**
(p. ej. "4500 CLP @0.01 lot" ≡ 450.000 CLP/lote). La invarianza de escala se audita; rompedores
conocidos: reglas cash, `trade_stops_level` del bróker, redondeo de lot-step.
*Por qué:* si los resultados no son comparables entre sí, el programa entero no concluye nada.

**2 · "Ganadora" = neto positivo en backtest real-tick.**
NO "mejor que S6/ST". La dependencia del top-K es **descriptor, no gate** — el trend-following es
asimétrico-positivo por diseño y las top-K SON la estrategia; amputarlas y declarar fracaso es
malinterpretar la forma esperada de la distribución. Control anti-suerte = bootstrap por bloques
a nivel de episodio + holdout, **nunca** amputación.

**3 · No-contaminación del orquestador.**
Los rankings de valor esperado pueden **EXTENDER** profundidad en áreas prometedoras; **JAMÁS
recortar amplitud** de áreas pedidas. Toda área del listado se explora con grilla suficiente.
Una hipótesis del orquestador sobre "esto probablemente correlaciona / probablemente no sirve"
no poda nada: se mide.

**4 · Hipótesis-only.**
Ningún hallazgo se comunica como veredicto fuera de memos de interpretación (Opus), que viven en
ficheros separados de los datos. **Prohibida** la frase "la evidencia apunta a" (o equivalente) en
cualquier artefacto de datos, reporte de investigador o brief.

**5 · Motor congelado.**
Todas las modificaciones de motor se inventarían, implementan y validan **JUNTAS, ANTES** del
programa. Suite golden + fidelidad empírica A6 tras **CADA** modificación. Luego freeze por SHA;
el programa entero corre anclado a ese SHA. Cambio posterior = enmienda formal + re-validación
completa de paridad.
*Por qué:* modificar el motor a mitad de ejecución invalidaría silenciosamente todo lo corrido
antes, y en el peor caso costaría el capital.

**6 · Real-tick = sustrato de veredicto.**
Barras M15 **eliminadas** como sustrato de veredicto. Las barras solo sirven para estadísticas de
señal matemáticamente exactas sobre cierres (conteos de gate, correlaciones de indicadores),
etiquetadas `substrate=bars, non-verdict`, y jamás deciden solas.
*Por qué:* la investigación es mayormente de salidas, y las salidas son path-dependent — la
trayectoria intra-barra decide qué nivel se toca primero.

**7 · Routing LLM 70/29/1.** Ver §B.

**8 · Automatización tradicional primero.**
Colas de backtests, regeneraciones, descargas y conteos los ejecutan **runners Python** con
manifiestos declarativos. El LLM planifica e interpreta; **no** "corre un backtest, mira, corre
otro". Ver `protocolos/06-runners.md`.

**9 · Trazabilidad absoluta.**
Todo artefacto lleva `{run_id, area, experimento, config_hash, substrate_id, engine_sha, git_sha,
etapa, generador, timestamp}`. Ledger maestro append-only. **Prueba de aceptación:** cualquier
número de cualquier documento debe poder rastrearse a su corrida de origen en <1 minuto, dentro
de 2 meses.

**10 · Enmiendas solo en fronteras de fase**, con causa escrita, jamás a mitad de un experimento.
Las grillas quedan congeladas por fase. Ideas nuevas → `BACKLOG.md` (NO crea tareas hasta la
frontera). El programa PUEDE dejar pendientes declarados con recomendaciones por etapa.

**11 · R1-bis (verbatim, sin excepción).**
Los S6 / S7 / SuperTrend **VIVOS se preservan byte-identical** (engines, kwargs, config dicts,
code paths). Toda modificación va sobre **copia independiente** (cfg deep-copy, módulo nuevo,
banda mágica nueva), JAMÁS sobre el original. Un implementador que concluya que hay que tocar el
original **está equivocado sobre la tarea: debe PARAR y escalar**.

**12 · MT5 y cuentas.**
`D:/FOREX/CUENTAS.md` = fuente única. **ATTACH-ONLY**: ningún script lanza terminales; los abre el
user a mano. Cuentas REALES = READ-ONLY, jamás operar. Toda orden (solo en la DEMO autorizada)
requiere `guard_cuenta.assert_demo()` verificado en ESA sesión.
**Cuenta 902 = NO-R&D:** es la cuenta live-test en otro equipo. Aquí es **SOLO LECTURA** vía
`MT5_Tester_2`; PROHIBIDO modificarla o agregarle nada; jamás corre posiciones desde este equipo;
sus credenciales no se persisten nunca en este equipo.

**13 · Anti-drift.**
"Hecho" = **artefacto verificable** (fichero en la ruta esperada + fila en el ledger + hash),
jamás la palabra de un agente. Verificador ≠ implementador. Ante cualquier anomalía: **STOP +
escalar al user**. Prohibido "aceptar" un error de resultado o de método, y prohibido simplificar
o reducir el alcance de una tarea sin enmienda escrita. Ver `protocolos/03-verificacion.md`.

**14 · Holdout sagrado.**
Sellado en Fase 0. Tramo intocado + hipótesis pre-registradas + **UNA sola** evaluación final.
Quien lo lee dos veces, lo quema. Está prohibido abrir, muestrear o "echarle un vistazo" al
holdout por cualquier motivo antes de la evaluación final autorizada por el user.

---

## §B · ROUTING (bloque VERBATIM en cada brief)

> **Routing de modelos del programa (70 / 29 / 1):**
>
> **Sonnet 5 high effort ≈ 70 %** — el caballo de batalla. Dos roles, nunca mezclados:
> · **IMPLEMENTADOR**: recibe un spec técnico CERRADO y detallado (qué implementar, dónde,
>   con qué cuidados, pointers a ficheros y contexto relevante). Implementa. No decide diseño.
> · **INVESTIGADOR**: recopila y reporta **objetivamente** — números, rutas, conteos, citas
>   `file:line`. **REPORT-ONLY: prohibido interpretar, recomendar, concluir o priorizar.**
> A Sonnet **NUNCA** se le pide interpretar resultados, hacer recomendaciones ni tomar decisiones.
> Siempre se le despacha con **información completa** (no hereda contexto).
>
> **Opus 5 high effort ≤ 29 %** — orquestación e inteligencia. **Máximo 2 subagentes en paralelo**,
> y NUNCA dos sobre los mismos ficheros. Opus hace: toda interpretación de resultados, propuesta
> de mejoras, generación de ideas, redacción de specs y memos, decisiones de diseño.
> **Toda etapa de ANÁLISIS DE RESULTADOS usa Opus, siempre.**
>
> **Fable 5 ≈ 1 %** — reservado a 3 momentos de máximo apalancamiento:
> (1) cierre e integración del plan + charter; (2) auditoría pre-vuelo del motor congelado y de
> los resultados de A6, antes de autorizar la ejecución; (3) síntesis final del programa.
>
> Ficheros compartidos (TRACKER, LEDGER, planes, `.gitignore`) son del **CONTROLADOR**,
> jamás de un agente.

---

## §C · NORMAS DE PROCESO (bloque VERBATIM en cada brief)

> **R1-bis:** ver §A.11 — vivos byte-idénticos, todo sobre copias, PARAR y escalar si crees que
> hay que tocar el original.
>
> **Paralelismo:** máximo **2** subagentes simultáneos. NUNCA dos sobre los mismos ficheros —
> ni siquiera lectura de un fichero que otro está editando.
>
> **Git:** commitear SOLO las rutas propias: `git add -- <rutas>` y
> `git commit -m "<msg>" -- <rutas>` (el `-m` va ANTES del `--`). Verificar `git status --short`
> antes y después. Ni `git add .`, ni `-A`, ni rebase, ni push, ni tags.
>
> **Pytest:** PROHIBIDO en background. Foreground con timeout largo. Suites dirigidas
> (`tests/analysis`, `tests/live`), no la suite completa: hay 13 rojos conocidos por fuga de
> variables de entorno del host vivo (deuda de test, no bugs), y los lentos están en cuarentena
> con marca `slow`.
>
> **MT5:** ver §A.12 — attach-only, reales read-only, 902 solo lectura, `assert_demo()`.
>
> **Honestidad:** todo número lo calcula código; lo no evaluable se declara no evaluable; registro
> aditivo (jamás borrar ni mutar filas de resultados); veredictos solo bajo la puerta estadística
> del plan (§9). Ningún artefacto de datos lleva conclusiones.
>
> **Reporte:** al terminar, entrega (a) rutas exactas de los artefactos producidos, (b) los
> comandos ejecutados y su salida real, (c) lo que NO pudiste hacer y por qué. Sin adjetivos.
