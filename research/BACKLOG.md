# BACKLOG GLOBAL — observaciones que NO crean tareas

> Aquí van las ideas, dudas y "esto habría que mirarlo" que surgen mientras se ejecuta.
> **Escribir aquí es obligatorio** cuando detectas algo interesante fuera de tu alcance: así no
> se pierde, y así tampoco descarrilas la tarea en curso.
>
> 🔴 **Una entrada en el backlog NO es una tarea.** Se revisa **solo en la frontera de fase**, y
> ahí el user y el controlador deciden qué se promueve (vía enmienda, protocolo 04) y qué queda
> anotado. Nadie ejecuta nada de aquí por iniciativa propia.

Formato: `<fecha> · <quién> · <observación> · <origen: ruta o experimento>`

---

## Abiertas

- **2026-08-10** · Opus5 (verificación T0.9-min) · 🟠 **`run_id` del runner = `run_key` literal**,
  no el formato `<FASE>-<AREA><n>-<seq>` de `LEDGER.schema.md`. El implementador hizo lo correcto
  al **no** inventar la convención (es decisión de diseño, fuera de su rol). **Ruling del
  controlador:** el manifiesto de T0.4 debe llevar el `run_id` explícito por corrida; si aparece
  una tercera tarea con el mismo problema, se promueve a enmienda y el runner genera la secuencia ·
  `scripts/research/runner/runner.py`
- **2026-08-10** · Opus5 (verificación T0.9-min) · 🟠 `ledger.append_row()` escribe `line + "\n"`
  asumiendo que el fichero **termina** en salto de línea. Si alguna vez no lo hace, la fila nueva
  se fusiona con la última y **corrompe un artefacto append-only**. Endurecer al construir T0.4
  (comprobar el último byte antes de escribir) · `scripts/research/runner/ledger.py:42`
- **2026-08-10** · Opus5 (verificación T0.9-min) · 🟡 El test `test_lineage_completo_13_campos`
  afirma cubrir "sin conversión de zona" pero solo comprueba que el timestamp no contenga `Z` ni
  `+00:00`. **`datetime.utcnow()` pasaría ese test** desplazando 4 horas en silencio. La
  implementación es correcta (`datetime.now()`), así que no hay defecto vivo — pero el test no
  guarda lo que dice guardar · `tests/research/test_runner_scaffold.py:163-165`
- **2026-08-10** · Opus5 (verificación T0.9-min) · 🟡 `test_fail_loud_corrida_aborta...` llama a
  `tasks.register()` sobre el registro global sin limpiarlo después: contaminación de estado entre
  tests · `tests/research/test_runner_scaffold.py:118`

- **2026-08-10** · Opus5 · 🔴 `CUENTAS.md` es la **fuente única** de cuentas MT5 según charter
  §A.12, pero está **incompleta respecto del código**: no menciona el login `2883016567`, que
  `scripts/analysis/realtick_bt/extract_ticks.py:34` sí sanciona como demo operable
  (`SANCTIONED_DEMO = {2883015767, 2883016567}`), ni la cuenta **902**, ni la instancia
  `MT5_Tester_2` que el charter nombra para leerla. El código autoriza una cuenta que la fuente
  única no conoce. El user decidió (2026-08-10) **solo anotarlo aquí**, sin tocar `CUENTAS.md`
  por este motivo; se resuelve en la frontera de fase · `CUENTAS.md` + `extract_ticks.py:34`
- **2026-08-10** · Opus5 · Tres de los ocho JSON de `data/analysis/monday_audit/` están
  **gitignored** (`b1_robustness`, `b1_wait_window`, `b6_mask_verdicts`), igual que los
  `positions_*.csv`. Sus filas de LEDGER (D-17) apuntan a artefactos que viven **solo en este
  disco**: si el disco se pierde, el lineage queda colgando · `.gitignore:46-54`

- **2026-08-10** · Fable5 · El reparto del Bloque 2 de videos no cuadra con la instrucción literal
  ("los 8 restantes sobre 15k"): la medición real da 5 videos ≥15k y 1 de 12,8k. Confirmar con el
  user si el Bloque 2 son 6 videos (3+3) u otra partición · `fases/F0-preparacion/PROTOCOLO-REVISION-VIDEOS.md`
- **2026-08-10** · Fable5 · Evaluar si la descarga de ticks de AVA es replicable con
  `copy_ticks_range` en vez del export manual por GUI — permitiría trocear 2–4 años y registrar
  lineage automáticamente · `DECISIONES.md` D-02
- **2026-08-10** · Fable5 · La ingesta continua de ticks de Capitaria es un activo que solo crece
  hacia adelante (el servidor sirve ~7 meses rodantes). Merece supervisión durable propia, no un
  proceso ad-hoc de sesión · `protocolos/06-runners.md`
- **2026-08-10** · Fable5 · Los umbrales operacionales de la puerta estadística (§9 del plan) están
  definidos cualitativamente pero no numéricamente: cuántos meses positivos de N para
  "consistencia", nivel de confianza, q del FDR. Fijar con el user antes de la fase GR · plan §9
- **2026-08-10** · Fable5 · La matriz de indicadores de la autopsia (plan §5.2) debe cerrarse ANTES
  de implementar la instrumentación de camino (motor mod #11): añadir un indicador después obliga
  a re-correr la autopsia completa · plan §5.2

## Promovidas a tarea (con enmienda)

_(ninguna todavía)_

## Cerradas sin promover

_(ninguna todavía)_
