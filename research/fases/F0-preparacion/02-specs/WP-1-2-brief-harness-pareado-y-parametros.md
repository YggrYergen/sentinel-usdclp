# BRIEF — WP-1+2 · Harness pareado, parámetros expuestos e instrumentación de camino

**Rol:** IMPLEMENTADOR (Sonnet 5 high effort). **Rama:** `equipo1`. **Fecha:** 2026-08-16
**Spec padre:** `research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md` (§WP-1+2)
**Manda:** D-52 (instrumentación de un solo viaje) · D-55 + ENMIENDA E-03 (la puerta de paridad está
verde otra vez, commit `35fdde2`, y es tu red de seguridad)
**Bitácora obligatoria:** `research/fases/F0-preparacion/02-specs/WP-1-2-progreso.md` — UNA línea por
bloque, escrita al terminar el bloque, antes del commit.
**Reporte final (uno solo):** `research/fases/F0-preparacion/02-specs/WP-1-2-reporte.md`.

---

## 0 · Lo que tienes que entender antes de tocar nada

El objetivo del programa ahora mismo es **obtener resultados de la Ola 1** (seis palancas de salida
sobre S6/S7/SuperTrend). Tú construyes el instrumento que las hace medibles. No mides nada tú.

El simulador tiene hoy una **divergencia de neto del 16,7 %** contra la realidad, con sesgo de
**signo opuesto** por estrategia (S6 −5,13 USD/posición · SuperTrend +45,22 USD/posición). Por eso
lo único que se puede concluir con rigor es una comparación **dentro de la misma estrategia sobre el
mismo conjunto de entradas**: el sesgo compartido se cancela en la resta. **Tu harness es lo que
hace posible esa resta.** Si el harness no puede demostrar que dos brazos corrieron sobre las mismas
entradas, el programa no puede concluir nada. Ése es el valor de este paquete, y de ahí sale el
requisito duro del Bloque 3.

**Invariante que gobierna todo el paquete:** toda la instrumentación es **aditiva y apagada por
defecto**. Con los parámetros nuevos sin especificar, el motor debe producir resultados
**byte-idénticos** a los de hoy. Quien lo demuestra es
`tests/research/test_baseline_parity.py -m slow` (hoy **4 passed**). Lo corres **antes de empezar y
después de cada bloque**. Si se pone rojo: **PARA y escala**; no lo arregles, no lo re-congeles, no
lo edites. Ese fichero es del controlador (D-55).

⚠️ **Sin `-m slow` ese test devuelve `4 deselected` — un verde que no probó NADA.** No lo cites nunca
sin el flag.

---

## 1 · Recon obligatorio (Bloque 0)

Antes de escribir código, produce en la bitácora **diez líneas** confirmando dónde vive de verdad
cada cosa que vas a tocar. Este brief fija **contratos**, no números de línea. **Donde el brief y el
código difieran, gana el código** — corregir al controlador es lo esperado, no una molestia; anótalo
en el reporte.

Lo que el controlador ya verificó en disco el 2026-08-16 (úsalo como punto de partida, confírmalo):

- `scripts/analysis/realtick_bt/backtest.py` (718 líneas) es el harness real-tick. Piezas:
  - `run_ladder(kwargs, bars)` — llama `simular_variant(bars, **kwargs)` (el motor S6/S7 vivo) y
    empareja eventos → posiciones. Ya acepta **kwargs arbitrarios**.
  - `run_supertrend(bars, ticks)` — SuperTrend "always-in". 🔴 **Tiene `14` y `3.0` HARDCODEADOS**
    (`_atr_wilder(..., 14)` y `supertrend(..., 3.0)`), y usa la línea como SL server-side
    (`sl = line[j-1]`).
  - `resolve(pos, ticks, bar_times)` — fill real-tick; **descarta** posiciones que nunca abrieron
    (retry de cierre de barra con gate de spread ≤0,5, `MAX_RETRY_BARS = 1`).
  - `build_all(ticks, bars)` — orquesta las tres estrategias. `_GL = {c["id"]: c["kwargs"] for c in
    _GOLIVE_M15}` son las kwargs VIVAS.
- `sentinel_engine/strategies/emasar_variant.py` — `simular_variant`. **`max_hold_bars` YA es kwarg**
  (línea ~130, default `None` = deshabilitado). `ac_modulate` / `ac_modulate_factor` ya son kwargs
  (~113-114).
- `sentinel_engine/strategies/emasar_ref.py:291` — `ac_desacelerando(ac, idx, direccion)`: **aquí
  vive el umbral/lookback hardcodeado** que el Bloque 4 tiene que sacar a parámetro.
- `sentinel_engine/strategies/_supertrend_ref.py` — `supertrend(highs, lows, closes, atr, mult)`.

---

## 2 · Los bloques, en este orden exacto

**El orden importa y no es negociable:** está ordenado por camino crítico de la Ola 1. Si te quedas
sin sesión a mitad, lo que quede hecho tiene que ser lo que más desbloquea. **Commit al final de
cada bloque verde.** Cuatro agentes han muerto por límite de sesión en este programa; el commit por
incremento verde y la bitácora de una línea por bloque son lo que permite que un agente frío retome
sin rehacer trabajo.

### Bloque 1 — Parámetros de SuperTrend expuestos (palanca P-05)
`run_supertrend(bars, ticks, *, atr_period: int = 14, mult: float = 3.0)`.
Los defaults son **exactamente** los valores hardcodeados de hoy, y `build_all` sigue llamándola
**sin argumentos nuevos**. Criterio: paridad verde ⇒ byte-idéntico.
Añade un test que corra `run_supertrend(bars, ticks)` y `run_supertrend(bars, ticks, atr_period=14,
mult=3.0)` y exija resultados **idénticos**.

### Bloque 2 — Overlay de kwargs sobre las estrategias de escalera (palancas P-02, P-03)
Función que, dado un `sid` (`"S6-K2P0"` / `"S7-TPNONE"`) y un dict de overlay, produzca las kwargs
efectivas como **deep-copy** de `_GL[sid]` con el overlay aplicado encima.
🔴 **`_GL` y `_GOLIVE_M15` NO se mutan JAMÁS** (R1-bis: `copy.deepcopy`, nunca `dict.update` sobre el
original). Test que lo demuestre: correr un overlay y verificar después que `_GL[sid]` sigue igual.
Con overlay vacío, el resultado tiene que ser el de hoy.
Esto ya deja `max_hold_bars` (P-02) barrible **sin tocar el motor**.

### Bloque 3 — Harness pareado y **tabla de alineación de entradas** (el corazón del paquete)
Contrato:

> Dado un conjunto de brazos (cada brazo = estrategia + overlay de parámetros), ejecutar los K brazos
> y devolver K resultados **alineados posición a posición por identidad de entrada**, más una tabla
> explícita de qué entradas casan y cuáles no.

Requisitos duros:
- Identidad de entrada: `(sid_estrategia, ficha, t_in, side)`. Para SuperTrend, `(t_in, side)`.
- 🔴 **PROHIBIDO ASUMIR QUE LOS BRAZOS COMPARTEN ENTRADAS.** S6/S7 corren con
  `stop_and_reverse=True`: una salida distinta puede generar una **entrada** distinta aguas abajo, y
  `resolve()` además descarta posiciones que no pasaron el gate de spread. El harness **mide** el
  solape, no lo presupone. Emite, por par de brazos: `n_casadas`, `n_solo_A`, `n_solo_B`, y la lista
  de identidades no casadas. Emítelo en **dos niveles**: (a) entradas de señal, antes de `resolve()`;
  (b) entradas rellenadas, después de `resolve()`. Los dos números importan y son distintos.
- El brazo por defecto (la salida actual de cada estrategia) es **un brazo más**, y correrlo solo
  tiene que reproducir el resultado de hoy exactamente. Ése es el test de no-regresión.
- Las entradas se calculan una sola vez por brazo; no re-simular por política dentro de un brazo.
- Salida columnar, unible por identificador de posición sin ambigüedad.

### Bloque 4 — Umbral y lookback de desaceleración de AC (palanca P-03)
Sacar a parámetro lo que hoy está fijo dentro de `ac_desacelerando` (`emasar_ref.py:291`) y
enhebrarlo desde `simular_variant`. **Los defaults tienen que reproducir el comportamiento de hoy
exactamente**; la paridad verde es la prueba.
🔴 **Kwargs nuevos aditivos, con default = comportamiento actual. No cambies ningún default
existente. NO toques `live_configs_20.py` ni ningún dict de configuración viva.** R1-bis se hace
cumplir aquí **por comportamiento**, verificado por la puerta de paridad — que es exactamente para
lo que existe esa puerta (lee su docstring). Si crees que hay que cambiar un default o tocar una
config viva: **PARA y escala**.
Rango que la grilla va a barrer (para que dimensiones bien los parámetros, no para que lo corras tú):
umbral {25, 50, 75} pips × lookback {1, 2} barras × duración del apriete {3, 5, 10} barras.

### Bloque 5 — Offset de SL consciente del fill (palanca P-08)
Parámetro nuevo `sl_offset: float = 0.0` (USD) que **ensancha** el nivel de stop antes de evaluarlo:
para LONG el nivel baja `sl_offset`, para SHORT sube. Aplícalo en SuperTrend (`sl = line[j-1]`) de
forma que **tanto el test de toque como el precio de salida** usen el nivel desplazado — si sólo
desplazas uno de los dos, el resultado es incoherente.
Grilla prevista: {0.00, 0.10, 0.20, 0.30} USD. Default `0.0` ⇒ byte-idéntico.

### Bloque 6 — Instrumentación de camino (mod #11) — **sólo si 1-5 están verdes y commiteados**
Por posición y a lo largo de su vida: **MFE y MAE en el tiempo** (no sólo su valor final), **barras
transcurridas** desde la entrada, **snapshot del contexto de entrada** (estado de los indicadores al
abrir) y 🔴 **el spread vigente en el instante de decisión** — hoy no se registra por operación y es
un agujero conocido: el spread de Capitaria es **bimodal 0,50 / 0,60**, no fijo, y sin ese dato no se
puede separar coste de ejecución de calidad de señal.
Apagado por defecto, artefacto columnar aparte, unible por identificador de posición.
**Criterio duro:** correr con y sin instrumentación da **el mismo resultado**. La instrumentación no
decide nada.

---

## 3 · Fuera de alcance (no lo hagas, no lo empieces)

- **P-27 (SL estructural por swing/pivote)**: NO entra en este paquete. Requiere detección de swings
  y tiene una trampa de look-ahead propia (un pivote fractal en la barra `i` sólo se conoce `k`
  barras después). Va en un paquete aparte, después.
- Régimen (WP-5), feed H1/H4 (WP-3), sizing (WP-4): otros paquetes, otros agentes, otros ficheros.
- **Correr grillas o barridos.** Tú entregas el instrumento. Las corridas las lanza el controlador
  con un manifiesto y el runner.
- Escribir en `research/LEDGER.jsonl`, `research/TRACKER.md`, `research/DECISIONES.md` o el plan
  maestro: **son del CONTROLADOR**. Deja en tu reporte los datos de linaje (comandos, SHAs, conteos)
  y el controlador escribe las filas.

---

## 4 · Criterios de aceptación (definición de HECHO)

1. `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed**, después de
   **cada** bloque. Con los parámetros nuevos sin especificar, byte-idéntico.
2. `python -m pytest tests/analysis -q` y `python -m pytest tests/research -q` sin regresiones
   respecto de la línea de partida que midas tú mismo en el Bloque 0 (mídela y anótala).
3. Tests nuevos propios en **fichero propio** (p. ej. `tests/research/test_harness_pareado.py`), que
   cubran: defaults idénticos (B1), no-mutación de `_GL` (B2), tabla de alineación con un caso donde
   los brazos **no** comparten todas las entradas (B3), defaults de AC idénticos (B4), coherencia
   toque/precio del offset (B5), instrumentación inerte (B6).
4. El reporte documenta **la API exacta** que dejas (firmas, tipos, rutas de artefactos), porque el
   controlador escribe el manifiesto de la Ola 1 contra ella.

---

## 5 · §B ROUTING — bloque VERBATIM del charter

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

## 6 · §C NORMAS DE PROCESO — bloque VERBATIM del charter

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

## 7 · Normas específicas de este programa (van además de las anteriores)

- Rama `equipo1`. **NUNCA** `master` ni `alvaro`. Sin force-push, rebase, amend, push ni tags.
- Todos los timestamps son **hora de servidor del bróker (UTC−4)**. **Prohibida toda conversión de
  zona.** Esta regla ya costó dinero real.
- La verdad de terreno tiene **resolución de segundo entero** (D-46).
- `pandas` convierte `None` en `NaN` y `is not None` no lo ve — usa `pd.isna()`.
- El spread de Capitaria es **bimodal 0,50 / 0,60**, no fijo.
- La cadencia de 15,77 s es **medida, no elegida**: con 15,0 el total pasa de 157 a 167 posiciones.
- `scripts/analysis/a6_pata_a/` está **sin trackear**: `git add` sobre el directorio lo incorpora
  entero. Añade por ruta explícita, siempre.
- Respaldo `<nombre>.bak-<timestamp UTC>` antes de regenerar cualquier artefacto.
- Método: TDD (rojo → mínimo → verde → commit).
- **D-48, disciplina de salida:** los agentes trabajan, no redactan ensayos. UN fichero de reporte,
  bitácora de una línea por bloque, y mensaje final corto: estado, SHAs, una línea de tests, y sólo
  las dudas que exijan decisión humana.
- 🔴 **Hay otro agente trabajando en paralelo** sobre `scripts/analysis/realtick_bt/faulty/
  divergencia_neto.py` y `research/fases/F0-preparacion/04-resultados/T0.7-p-cap/`. **No leas ni
  toques esas rutas.** Las tuyas son: `scripts/analysis/realtick_bt/backtest.py`, módulos nuevos que
  crees, `sentinel_engine/strategies/emasar_ref.py`, `sentinel_engine/strategies/emasar_variant.py`,
  `tests/research/test_harness_pareado.py` y tus dos ficheros de `02-specs/`.
