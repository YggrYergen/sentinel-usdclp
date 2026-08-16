# WP-2b — BRIEF CERRADO (implementador)

**Rol:** IMPLEMENTADOR (Sonnet 5 high effort). **Rama:** `equipo1`. **Fecha:** 2026-08-16.
**Controlador:** Opus 5. **Manda:** D-52 (instrumentación de un viaje), D-55 (no re-congelar
paridad), pre-registro Ola 1 (`01-hipotesis/2026-08-16-preregistro-ola1.md`, palanca P-03).

Dos bloques independientes, en este orden. **Un commit por bloque verde.** Bitácora de UNA
línea por bloque en `02-specs/WP-2b-progreso.md`.

---

## §B · ROUTING (verbatim del charter)

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

## §C · NORMAS DE PROCESO (verbatim del charter)

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

---

## Normas específicas de ESTE brief (leer antes de tocar nada)

1. **R1-bis, repetido:** S6 / S7 / SuperTrend **vivos se preservan byte-idénticos**. El Bloque 2
   toca `sentinel_engine/strategies/emasar_variant.py`, que **es** el motor de S6/S7 vivos: el
   cambio es **estrictamente aditivo con default que reproduce hoy exactamente**. Si en algún
   momento concluyes que hay que cambiar el comportamiento por defecto, **estás equivocado sobre
   la tarea: PARA y escala al controlador.**
2. 🔴 **PROHIBIDO editar, regenerar o re-congelar `tests/research/test_baseline_parity.py` y
   `research/fases/F0-preparacion/04-resultados/T0.6-baseline/*`.** Son del controlador. Si la
   puerta de paridad se pone roja, **PARA y escala** — no la "arregles".
3. **La puerta de paridad se invoca SIEMPRE con `-m slow`:**
   `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → debe decir **`4 passed`**.
   Sin `-m slow` dice `4 deselected` — un verde que no probó nada. **Nunca cites esa forma.**
4. Todos los timestamps del repo son **hora de servidor del bróker (UTC−4)**. **Cualquier
   conversión de zona horaria está PROHIBIDA.** `datetime.utcfromtimestamp`, nunca
   `fromtimestamp`.
5. `pandas` convierte `None` en `NaN`; `is not None` no lo detecta — usar `pd.isna()`.
6. **Commit por bloque verde**, inmediatamente. Sesiones anteriores murieron por límite de sesión
   y perdieron trabajo no commiteado: si el Bloque 1 está verde, se commitea antes de empezar el
   Bloque 2. **Bitácora de una línea por bloque** en `02-specs/WP-2b-progreso.md`, escrita al
   cerrar cada bloque.
7. **Donde este brief y el código difieran, gana el CÓDIGO.** Decirlo en el reporte es lo
   esperado, no una falta.
8. **D-48:** los agentes trabajan, no redactan ensayos. UN fichero de reporte
   (`02-specs/WP-2b-reporte.md`), la bitácora de una línea por bloque, y el mensaje final =
   estado + SHAs + una línea de tests + solo las preguntas que exigen decisión.

## TUS RUTAS (las únicas que puedes tocar)

- `tests/analysis/test_borde_del_dia.py` (Bloque 1)
- `sentinel_engine/strategies/emasar_variant.py` (Bloque 2, **solo aditivo**)
- `tests/research/test_ac_modulate_hold.py` (Bloque 2, fichero nuevo)
- `research/fases/F0-preparacion/02-specs/WP-2b-progreso.md` y `WP-2b-reporte.md`

**Fuera de tus rutas, no tocar:** `scripts/analysis/realtick_bt/**`, `scripts/research/**`,
`tests/research/test_baseline_parity.py`, `research/LEDGER.jsonl`, `research/TRACKER.md`,
`research/DECISIONES.md`, y `research/fases/F0-preparacion/04-resultados/**`.

---

## BLOQUE 0 — línea de partida (obligatorio, antes de editar nada)

Corre y anota la salida real de:

```
python -m pytest tests/research/test_baseline_parity.py -m slow -q
python -m pytest tests/analysis -q
python -m pytest tests/research -q
python -m pytest tests/strategies -q
```

Línea de partida conocida y esperada (medida por el controlador en `659a121`):
paridad **4 passed**; `tests/analysis` **1 failed, 306 passed** (el rojo es exactamente el que
arregla el Bloque 1); `tests/research` **300 passed, 4 deselected`; `tests/strategies` **272
passed**. Si tu medición difiere, **anótalo y sigue** — la línea de partida es la tuya.

---

## BLOQUE 1 — la cita `file:line` frágil pasa a ser cita POR CONTENIDO

**El hecho.** `tests/analysis/test_borde_del_dia.py::test_cita_gate_spread_harness_verificada_contra_el_fichero_real`
lee `scripts/analysis/realtick_bt/backtest.py` de verdad y afirma que la cadena
`"abs(sp - 0.5) <= 0.05"` está en `lineas[375]` (índice hardcodeado). Hoy esa cadena está en la
**línea 400** (índice 399) porque WP-1+2 añadió docstrings arriba. **Es la TERCERA vez que esta
misma prueba se rompe por lo mismo** (el propio test documenta en un comentario que T0.7-M-E ya
la desplazó de 358 → 376, y WP-1+2 la desplazó de 376 → 400).

**Qué hay que hacer — las dos cosas, no solo la primera:**

1. **Arreglarla.** Que vuelva a verde.
2. **Quitarle el impuesto para siempre:** la prueba debe **localizar la línea citada por
   CONTENIDO, no por número**. El número de línea deja de ser un dato de entrada y pasa a ser un
   dato de salida (si acaso, se reporta en el mensaje de fallo).

**Diseño CERRADO de la nueva prueba** (impleméntalo así; el nombre del test **no cambia**, para
no romper referencias externas):

- Lee el fichero completo y busca la cadena literal `abs(sp - 0.5) <= 0.05` sobre **todas** las
  líneas.
- Asserta que aparece en **exactamente una** línea. Si aparece 0 veces: fallo con mensaje
  «la constante del gate de spread desapareció de backtest.py» — eso SÍ es una regresión real y
  la prueba debe seguir atrapándola. Si aparece >1 vez: fallo nombrando todos los números de
  línea encontrados (ambigüedad = la prueba ya no sabe qué está citando).
- Asserta que esa única línea está **dentro del cuerpo de la función `resolve`** — localiza el
  `def resolve(` y el siguiente `def ` a nivel de módulo (columna 0) y comprueba que el índice
  cae entre ambos. Esto conserva la intención original (verificar QUÉ código implementa el gate,
  no solo que la cadena existe en algún sitio del fichero).
- El mensaje de fallo debe imprimir el número de línea **encontrado** para que el humano lo vea.
- **Actualiza el comentario de rango** que hoy dice `# linea 376, indice 375` (y el comentario de
  histórico de líneas 308-313) para que explique que la cita es por contenido y que **por eso ya
  no hay número que mantener**.

**Verificación del Bloque 1 (las tres, con salida real en el reporte):**
```
python -m pytest tests/analysis/test_borde_del_dia.py -q
python -m pytest tests/analysis -q            # debe pasar a 307 passed, 0 failed
python -m pytest tests/research/test_baseline_parity.py -m slow -q   # 4 passed
```
**Verificación por mutación (obligatoria, y se revierte inmediatamente):** comprueba que la
prueba nueva sigue teniendo dientes. Hazlo **sin editar `backtest.py`**: copia el fichero a un
temporal, aplica la mutación sobre la COPIA y ejecuta la lógica de localización contra la copia
(o parametriza la función auxiliar de búsqueda para que acepte un texto). Dos mutaciones:
(a) borrar la cadena → debe fallar con el mensaje de "desapareció"; (b) duplicarla → debe fallar
por ambigüedad. Reporta la salida real de ambas. **`scripts/analysis/realtick_bt/backtest.py` no
se modifica en ningún momento, ni siquiera temporalmente.**

**Commit del Bloque 1** (solo tus rutas):
```
git add -- tests/analysis/test_borde_del_dia.py research/fases/F0-preparacion/02-specs/WP-2b-progreso.md
git commit -m "fix(WP-2b B1): la cita del gate de spread se localiza por contenido, no por numero de linea (tercera rotura del mismo tipo)" -- tests/analysis/test_borde_del_dia.py research/fases/F0-preparacion/02-specs/WP-2b-progreso.md
```

---

## BLOQUE 2 — `ac_modulate_hold_bars`: duración del apriete de AC (palanca P-03)

**Por qué existe.** El pre-registro de la Ola 1 (fijado ANTES de correr nada) declara para P-03
la grilla `umbral {25,50,75} pips × lookback {1,2} barras × duración del apriete {3,5,10}
barras` = 18 brazos. WP-1+2 (Bloque 4) expuso `ac_decel_lookback` y `ac_decel_umbral`, pero **la
tercera dimensión —cuánto tiempo se MANTIENE el apriete— no tiene parámetro en el motor**: hoy el
apriete dura exactamente la barra en la que la condición se cumple. Sin este parámetro, 12 de los
44 brazos pre-registrados serían duplicados exactos de otros 6 y la palanca se mediría a un tercio
de su grilla. Es una adición **LOW effort** y aditiva; el controlador la autoriza bajo D-52.

**El sitio exacto.** `sentinel_engine/strategies/emasar_variant.py`, bloque «AC-modulated
trailing (V-06)», hoy en las líneas **963-969**:

```python
            # AC-modulated trailing (V-06; ac_modulate=False disables this
            # block entirely, preserving current behavior byte-for-byte):
            # when AC is decelerating against this ficha's favorable
            # direction on the current bar, tighten the trail distance.
            if ac_modulate and ac_desacelerando(ac, i, f.lado, lookback=ac_decel_lookback,
                                                 umbral=ac_decel_umbral):
                trail_efectivo = trail_efectivo * ac_modulate_factor
```

(Verifica el número de línea al empezar: puede haberse movido. **Gana el código.**)

**Diseño CERRADO — impleméntalo exactamente así:**

1. **Kwarg nuevo, al FINAL de la firma de `simular_variant`**, junto a `ac_decel_lookback` /
   `ac_decel_umbral`:
   ```python
   ac_modulate_hold_bars: int = 1,
   ```
   `1` = comportamiento de hoy **exacto**.

2. **Contador por ficha**, inicializado junto a los demás diccionarios por-tag del cuerpo de la
   función (mismo sitio donde vive `ac_decel_consec_by_tag`, hoy ~línea 666):
   ```python
   ac_modulate_hold_by_tag: dict[str, int] = {}
   ```

3. **Sustituye el bloque de 963-969 por esta semántica** (misma indentación, mismo lugar,
   comentario actualizado):
   ```python
   if ac_modulate:
       if ac_desacelerando(ac, i, f.lado, lookback=ac_decel_lookback,
                            umbral=ac_decel_umbral):
           ac_modulate_hold_by_tag[tag] = ac_modulate_hold_bars
       if ac_modulate_hold_by_tag.get(tag, 0) > 0:
           trail_efectivo = trail_efectivo * ac_modulate_factor
           ac_modulate_hold_by_tag[tag] -= 1
   ```
   Lee la equivalencia con `ac_modulate_hold_bars=1`: si la condición se cumple → contador=1 →
   se aplica el factor → contador=0. Si no se cumple → contador 0 → no se aplica. **Idéntico bit
   a bit al bloque de hoy.** Con `hold_bars=N`, el apriete persiste N barras desde el disparo y se
   **re-arma** (vuelve a N) si vuelve a dispararse dentro de la ventana.

4. **Reset en cada apertura de ficha.** Donde hoy se hace `ac_decel_consec_by_tag = {}` al abrir
   una señal nueva (hay tres sitios: ~líneas 1209, 1422, 1438 — **verifícalos**), añade
   `ac_modulate_hold_by_tag = {}` en el MISMO sitio y con la MISMA forma. Razón: el apriete no
   puede heredarse de una posición cerrada a la siguiente.

5. **Nada más cambia.** `ac_modulate=False` (S7) sigue saltándose el bloque entero. Ningún otro
   comportamiento, ninguna otra firma, ningún default.

6. **Guard de validez:** si `ac_modulate_hold_bars < 1`, `raise ValueError` con mensaje que
   nombre el valor recibido (mismo estilo fail-loud que el guard de `wait_mae_atr_k` en
   ~línea 550). Un 0 silencioso desactivaría el apriete sin decirlo.

**Tests (fichero nuevo `tests/research/test_ac_modulate_hold.py`), TDD — rojo primero:**

- `test_default_hold_1_es_byte_identico_al_motor_de_hoy`: corre `simular_variant` sobre las
  **400 primeras barras reales** del sustrato (mismo patrón que usó WP-1+2 Bloque 4; carga las
  barras con `scripts.analysis.realtick_bt.backtest.load_bars()`) con las kwargs vivas de
  **S6-K2P0** (`from sentinel_engine.strategies.live_configs_20 import _GOLIVE_M15`; toma
  `c["kwargs"]` del que tiene `id == "S6-K2P0"`, con `copy.deepcopy` — **jamás mutes el dict
  vivo**), una vez sin el kwarg y otra con `ac_modulate_hold_bars=1`, y compara la lista de
  eventos **completa y exacta** (`==`).
- `test_hold_mayor_que_1_persiste_el_apriete`: caso sintético mínimo y determinista
  (construye tú las barras) donde la condición de desaceleración se cumple en una barra y NO en
  la siguiente; con `hold_bars=1` el trail de la barra siguiente NO está apretado y con
  `hold_bars=3` SÍ. Verifícalo por su **efecto observable** (el nivel de SL emitido / el evento de
  salida), no leyendo variables internas.
- `test_rearme_dentro_de_la_ventana`: si la condición se vuelve a cumplir mientras el contador
  está vivo, el contador vuelve a `hold_bars` (comprobable con una secuencia de 2 disparos
  separados por 1 barra y `hold_bars=2`).
- `test_hold_bars_invalido_falla_ruidoso`: `ac_modulate_hold_bars=0` y `-1` → `ValueError` cuyo
  mensaje contiene el valor recibido.
- `test_ac_modulate_false_ignora_el_parametro`: con las kwargs vivas de **S7-TPNONE**
  (`ac_modulate=False`), `hold_bars=1` y `hold_bars=10` producen eventos **idénticos**.

**Verificación del Bloque 2 (con salida real en el reporte):**
```
python -m pytest tests/research/test_ac_modulate_hold.py -q
python -m pytest tests/research/test_baseline_parity.py -m slow -q   # 4 passed OBLIGATORIO
python -m pytest tests/strategies -q                                  # 272 passed
python -m pytest tests/research -q
python -m pytest tests/analysis -q                                    # 307 passed
```
🔴 **Si la puerta de paridad NO dice `4 passed`, el cambio NO es aditivo: PARA, revierte tu
edición de `emasar_variant.py`, y escala al controlador con la salida real.** No re-congeles nada.

**Commit del Bloque 2** (solo tus rutas).

---

## Reporte final (UN fichero: `02-specs/WP-2b-reporte.md`)

Contenido mínimo, sin adjetivos: (a) rutas exactas de lo producido y SHA de cada commit;
(b) los comandos ejecutados y su **salida real** (incluida la de mutación del Bloque 1 y la
puerta de paridad tras el Bloque 2); (c) lo que NO pudiste hacer y por qué; (d) solo las
preguntas que exigen decisión del controlador.

**Mensaje final al controlador:** estado, SHAs, una línea de tests, y preguntas que exijan
decisión. Nada más.
