# PROTOCOLO 02 — PLANTILLAS DE BRIEF

> Un subagente **no hereda nada**: llega frío. Todo lo que necesita debe estar en el brief.
> Un brief incompleto es la causa raíz de la mayoría de los fallos agénticos: el agente rellena
> los huecos inventando, y lo inventado entra al registro como si fuera dato.
>
> **Regla:** los bloques §ROUTING y §NORMAS de `research/CHARTER.md` van **VERBATIM** en todo
> brief. No se resumen, no se parafrasean, no se "adaptan".

---

## Plantilla A · IMPLEMENTADOR (Sonnet 5 high)

```markdown
# TAREA <ID> — <título>

## Contexto del programa (lee esto primero)
Trabajas en el Programa de Investigación XAUUSD 2026-H2. Antes de tocar nada, lee:
- research/CHARTER.md   (reglas: son obligatorias, no orientativas)
- research/TRACKER.md   (estado real del programa)
Tu tarea es la <ID> de la fase <FASE>. No hagas nada fuera de este alcance.

## Tu rol
Eres IMPLEMENTADOR. Recibes un spec cerrado. Implementas exactamente eso.
NO tomas decisiones de diseño. NO interpretas resultados. NO propones mejoras.
Si el spec te parece incorrecto o incompleto: PARA y escala. No lo "arregles".

## Qué hay que construir (spec cerrado)
<descripción exacta: comportamiento, entradas, salidas, casos borde>

## Ficheros
- Crear:    <ruta exacta>
- Modificar:<ruta exacta:líneas>
- Test:     <ruta exacta>

## Interfaces
- Consume: <firmas exactas que ya existen, con file:line>
- Produce: <nombres de funciones, tipos de parámetros y retorno que otras tareas usarán>

## Cuidados específicos de esta tarea
<los gotchas reales: p.ej. "el lake NO tiene _bars_M1.parquet (verificado)",
 "los timestamps son hora de servidor UTC−4: PROHIBIDA toda conversión de zona",
 "reentry_enable existente tiene semántica INVERTIDA: no lo toques, construye al lado">

## Pointers útiles
<ficheros de referencia, patrones existentes a imitar, tests similares ya escritos>

## Método OBLIGATORIO
Usa superpowers:test-driven-development — rojo → mínimo → verde → commit. Sin excepción.
Usa superpowers:verification-before-completion antes de declarar nada terminado.
Pytest SIEMPRE en foreground, suite dirigida.

## Definición de HECHO
- [ ] Test escrito y visto FALLAR primero (pega la salida real)
- [ ] Implementación mínima; test en verde (pega la salida real)
- [ ] Suite dirigida sin regresiones (pega la salida real)
- [ ] Commit scoped SOLO a tus rutas
- [ ] Fila actualizada en research/TRACKER.md (solo TU fila)

## Reporte final (formato exacto)
1. Rutas de los artefactos producidos
2. Comandos ejecutados + su salida REAL (no parafraseada)
3. Lo que NO pudiste hacer y por qué
Sin adjetivos, sin conclusiones, sin recomendaciones.

<<< PEGAR AQUÍ VERBATIM: CHARTER §B (ROUTING) >>>
<<< PEGAR AQUÍ VERBATIM: CHARTER §C (NORMAS) >>>
```

---

## Plantilla B · INVESTIGADOR REPORT-ONLY (Sonnet 5 high)

```markdown
# INVESTIGACIÓN <ID> — <pregunta exacta a responder>

## Contexto del programa
<igual que plantilla A>

## Tu rol
Eres INVESTIGADOR REPORT-ONLY. Recopilas y reportas hechos: números, rutas, conteos,
citas file:line, salidas de comandos.
🔴 PROHIBIDO: interpretar, concluir, recomendar, priorizar, opinar sobre qué es importante,
o escribir frases del tipo "esto sugiere que…" / "la evidencia apunta a…".
Si crees haber encontrado algo relevante, REPÓRTALO COMO DATO, no como hallazgo.

## Preguntas exactas a responder
1. <pregunta cerrada, verificable>
2. <...>

## Dónde buscar
<rutas, ficheros, comandos sugeridos>

## Restricciones
- SOLO LECTURA. No modificas ningún fichero fuera de tu artefacto de reporte.
- No corres backtests ni tareas pesadas salvo que el brief lo pida explícitamente.
- Si un dato no es evaluable con lo disponible: dilo. "No evaluable" es una respuesta válida
  y correcta; inventar o estimar NO lo es.

## Entregable
Fichero en <ruta exacta> con: una sección por pregunta, la respuesta factual, y la evidencia
(comando + salida, o file:line). Nada más.

<<< PEGAR AQUÍ VERBATIM: CHARTER §B (ROUTING) >>>
<<< PEGAR AQUÍ VERBATIM: CHARTER §C (NORMAS) >>>
```

---

## Plantilla C · ANALISTA (Opus 5 high) — interpretación

```markdown
# ANÁLISIS <ID> — <qué hay que interpretar>

## Contexto del programa
<igual que plantilla A> + lee también las hipótesis pre-registradas en
fases/<FASE>/01-hipotesis/ ANTES de mirar los resultados.

## Tu rol
Eres ANALISTA. Interpretas resultados y emites juicio. Este es el único rol autorizado a
concluir. Tu salida es un MEMO, que vive en fases/<FASE>/05-analisis/ — separado de los datos.

## Insumos
<rutas exactas de los artefactos de datos a analizar>

## Qué se te pide
1. Qué dice el dato, número por número.
2. Qué hipótesis pre-registrada se sostiene, cuál cambia, cuál queda INDETERMINADA.
   "Indeterminado" es una conclusión legítima y frecuentemente la correcta.
3. Qué NO se puede concluir con estos datos (explícito).
4. Backlog: qué ideas nuevas genera esto → fases/<FASE>/06-observaciones.md
   (recordar: el backlog NO crea tareas; se revisa en la frontera de fase).

## Restricciones duras
- No cambies grillas ni alcance: eso requiere enmienda (protocolos/04).
- No declares ganadores fuera de la puerta estadística del plan §9.
- Distingue SIEMPRE: hipótesis vs resultado vs decisión.
- Si el dato contradice una decisión del user: NO la reinterpretes. Escala.

<<< PEGAR AQUÍ VERBATIM: CHARTER §B (ROUTING) >>>
<<< PEGAR AQUÍ VERBATIM: CHARTER §C (NORMAS) >>>
```

---

## Checklist del despachador (antes de enviar cualquier brief)

- [ ] ¿Lleva §ROUTING y §NORMAS verbatim?
- [ ] ¿El rol está declarado sin ambigüedad (implementador / investigador / analista)?
- [ ] ¿Un agente frío podría ejecutarlo sin preguntar nada?
- [ ] ¿Están las rutas exactas, no descripciones vagas?
- [ ] ¿Está la definición de HECHO con artefacto verificable?
- [ ] ¿Los gotchas reales están escritos (no asumidos)?
- [ ] ¿Hay otro agente tocando alguno de esos ficheros? (si sí: **serializar**)
- [ ] ¿Son ≤2 agentes en paralelo?
