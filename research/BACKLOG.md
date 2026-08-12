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

- **2026-08-11** · User · 🟢 Explorar una política de ratchet **restringida al régimen de spread
  estrecho**: solo permitir abrir posición cuando el spread esté en el modo bajo de su
  distribución. Sin tarea asociada por ahora · idea, sin origen documental
- **2026-08-11** · Opus5 (verificación guard de identidad `ticks_mt5`) · 🟡 Dos chequeos de
  identidad solapados: el manifiesto ya traía `logins_sancionados` (lista) y ahora además
  `expected_login` (exacto) — semánticas distintas para lo mismo. No es defecto: si el operador
  está logueado en la otra demo sancionada, la corrida aborta con mensaje claro y se edita el
  manifiesto. Resolver en la revisión de código de fin de fase: decidir si `expected_login`
  supersede a `logins_sancionados` o si pasa a ser lista ·
  `research/fases/F0-preparacion/03-runs/T0.4-topup-capitaria.yaml`
- **2026-08-11** · Opus5 (verificación T0.3-ava) · 🟡 Falta la especificación del símbolo `XAUUSD`
  de Capitaria. El repo solo documenta `trade_contract_size` (100), `point` (0.01), `spread`
  (0,60) y `spread_float` (False) — fuente
  `docs/superpowers/research/2026-07-14-diag-h3h5-spread-slip.md:108`. Faltan `digits`, valores de
  tick, volúmenes mín/máx/paso, `filling_mode`, monedas y swaps. **Tiene ventana**: debe capturarse
  durante el mismo login de Capitaria en que se corra T0.4, o costará otro cambio manual de sesión
  al user · `docs/superpowers/research/2026-07-14-diag-h3h5-spread-slip.md:108`
- **2026-08-11** · Opus5 · 🔴 `CUENTAS.md` no documenta la 902 ni el login `2883016567`. Ya anotado
  previamente (ver entrada 2026-08-10 arriba); se reitera porque ahora tiene consecuencia directa
  sobre A6 Pata A. Ver bloqueo **B8** en `TRACKER.md` · `CUENTAS.md` + `extract_ticks.py:34`

- **2026-08-11** · Opus5 (verificación T0.3-ingest-ava-gold-csv) · 🟡 `<LAST>` y `<VOLUME>` del CSV
  de AVA se descartan. El lago tiene esquema `[t_msc, bid, ask]` y esas columnas vienen vacías en
  el feed spot. Si alguna vez hiciera falta volumen real, habría que reingerir ·
  `scripts/research/runner/tasks_ticks_csv.py`
- **2026-08-11** · Opus5 (verificación T0.3-ingest-ava-gold-csv) · 🟡 Criterio de "mes completo" en
  `ticks_csv_mt5` = el parquet final existe. Es correcto para un CSV estático, pero si el fichero
  de origen se sustituyera alguna vez por uno más largo, los meses ya escritos se saltarían en
  silencio. El checksum del origen queda en las métricas, así que la detección es posible pero
  **no automática** · `scripts/research/runner/tasks_ticks_csv.py`
- **2026-08-11** · Opus5 (verificación T0.3-ingest-ava-gold-csv) · 🟡 Divergencia de comportamiento
  entre task-types ante aborto: `ticks_mt5` deja los `.tmp` para inspección; `ticks_csv_mt5` los
  borra. Unificar el criterio en la revisión de código de fin de fase ·
  `scripts/research/runner/tasks_ticks.py` + `scripts/research/runner/tasks_ticks_csv.py`

## Promovidas a tarea (con enmienda)

_(ninguna todavía)_

## Cerradas sin promover

_(ninguna todavía)_
