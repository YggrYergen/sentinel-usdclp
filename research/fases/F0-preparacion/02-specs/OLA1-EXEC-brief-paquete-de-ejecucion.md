# OLA1-EXEC — BRIEF CERRADO (implementador)

**Rol:** IMPLEMENTADOR (Sonnet 5 high effort). **Rama:** `equipo1`. **Fecha:** 2026-08-16.
**Controlador:** Opus 5.

**Qué se construye:** el paquete que corre **la Ola 1 entera de una sola pasada, por script, sin
intervención de ningún agente**, y que deja los resultados registrados con trazabilidad completa.
**Tú construyes y pruebas el instrumento. TÚ NO CORRES LA OLA.** La corrida completa la lanza el
controlador. Está dicho explícitamente en §9.

**Documentos que mandan (léelos completos antes de escribir código):**
1. `research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-ola1.md` — el pre-registro
   (`22ee9fb`, escrito antes de correr nada).
2. `research/fases/F0-preparacion/01-hipotesis/2026-08-16-ampliacion-E04-ola1.md` — **la
   ampliación E-04 (`1c7279d`), que contiene LAS GRILLAS EXACTAS, las unidades, la definición de
   R, el bootstrap y las métricas secundarias.** Es tu especificación de datos. Si este brief y
   E-04 difieren, **manda E-04**.
3. `research/fases/F0-preparacion/02-specs/WP-1-2-reporte.md` — la API exacta del harness pareado.
4. `research/protocolos/06-runners.md` — el contrato del runner.
5. `research/fases/F0-preparacion/02-specs/T0.9-B-reporte.md` — `--on-error` / `--workers`.

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

## Normas específicas de ESTE brief

1. **R1-bis, repetido:** S6 / S7 / SuperTrend **vivos se preservan byte-idénticos**. Este paquete
   **no modifica ninguna estrategia ni el motor**: sólo los LEE y aplica overlays sobre **copias**
   (`overlay.overlay_kwargs` ya hace `deepcopy`). Si concluyes que hay que tocar un original,
   **estás equivocado sobre la tarea: PARA y escala.**
2. 🔴 **PROHIBIDO** editar `tests/research/test_baseline_parity.py`,
   `research/fases/F0-preparacion/04-resultados/T0.6-baseline/**`, `research/LEDGER.jsonl`,
   `research/TRACKER.md`, `research/DECISIONES.md`, los dos ficheros de `01-hipotesis/` y
   `sentinel_engine/**`. Los de `01-hipotesis/` son tu spec: se leen, no se editan.
3. 🔴 **NO CORRAS LA OLA COMPLETA.** Ver §9. Tus pruebas usan manifiestos de humo diminutos, un
   directorio de resultados temporal y **un LEDGER temporal** (`--ledger-path`), nunca el real.
4. Todos los timestamps son **hora de servidor del bróker (UTC−4)**. **Cualquier conversión de
   zona horaria está PROHIBIDA.** `datetime.utcfromtimestamp`, jamás `fromtimestamp`.
5. La verdad de terreno tiene resolución de **segundo entero** (D-46).
6. `pandas` convierte `None` en `NaN`; `is not None` no lo detecta — usa `pd.isna()`.
7. **Pytest SIEMPRE foreground**, suites dirigidas. **Nunca** la suite completa del repo.
8. **Commit por bloque verde, inmediatamente.** Cinco sesiones han muerto aquí por límite de
   sesión perdiendo trabajo sin commitear. **Bitácora de UNA línea por bloque** en
   `02-specs/OLA1-EXEC-progreso.md`, escrita al cerrar cada bloque, antes de empezar el siguiente.
9. **Donde este brief y el código difieran, gana el CÓDIGO.** Decirlo es lo esperado.
10. **D-48:** trabajas, no redactas ensayos. UN reporte (`02-specs/OLA1-EXEC-reporte.md`), mensaje
    final = estado + SHAs + una línea de tests + sólo preguntas que exijan decisión.
11. **No lances subagentes.** Haz el trabajo tú.

## TUS RUTAS (las únicas que puedes tocar)

- `scripts/research/ola1/**` (paquete nuevo)
- `scripts/research/runner/tasks_ola1.py` (fichero nuevo)
- `scripts/research/runner/runner.py` (**una sola línea**: el import que registra el task-type)
- `scripts/analysis/realtick_bt/paired_harness.py` (**sólo la adición aditiva del Bloque 2**)
- `tests/research/test_ola1.py` (fichero nuevo)
- `research/fases/F0-preparacion/03-runs/2026-08-16-ola1.yaml` (generado, commiteado)
- `research/fases/F0-preparacion/02-specs/OLA1-EXEC-progreso.md` y `OLA1-EXEC-reporte.md`

---

## BLOQUE 0 — línea de partida

Corre y anota la salida real:
```
python -m pytest tests/research/test_baseline_parity.py -m slow -q
python -m pytest tests/research -q
python -m pytest tests/analysis -q
git rev-parse HEAD
```
La puerta de paridad **tiene que decir `4 passed`** antes de que construyas nada. Si no, PARA y
escala. (Sin `-m slow` dice `4 deselected`: un verde que no probó nada. Nunca cites esa forma.)

Comprueba también, y anota, los datos de partida del sustrato:
```
python -c "import sys; sys.path.insert(0,'.'); from scripts.analysis.realtick_bt import backtest as bt; from scripts.research.baseline_golden import HOLDOUT_INI; bars=[b for b in bt.load_bars() if b['t']<HOLDOUT_INI]; print(len(bars)); r=bt.build_all(bt.Ticks(),bars); print({k:len(v) for k,v in r.items()})"
```
Esperado (medido por el controlador sobre `659a121`): **8334** barras y
`{'S6-K2P0': 624, 'S7-TPNONE': 708, 'SuperTrend-p14x3-M15': 153}`. Si difiere, **PARA y escala**:
significa que la línea base y el sustrato no están donde el pre-registro dice.

---

## BLOQUE 1 — `scripts/research/ola1/sustrato.py` y `riesgo.py`

### `sustrato.py`

```python
def cargar_barras() -> list[dict]
```
Barras M15 pre-holdout: `bt.load_bars()` filtrado por `b["t"] < HOLDOUT_INI`
(`from scripts.research.baseline_golden import HOLDOUT_INI`). **Reutiliza esa constante; no la
redefinas.**

```python
def verificar_holdout(posiciones: list[dict]) -> None
```
🔴 **Guarda dura del charter §A.14.** Si alguna posición resuelta tiene
`t_exit >= HOLDOUT_INI` o `t_in_exec >= HOLDOUT_INI`, lanza `HoldoutVioladoError` nombrando la
primera intrusa. Mismo criterio, literalmente, que `scripts/research/baseline_golden.py:75-85`.

```python
def verificar_control_contra_linea_base(sid: str, posiciones_control: list[dict]) -> dict
```
🔴 **La regla 5 del pre-registro: el instrumento se valida antes de leer nada más.** Compara el
brazo de control contra el congelado
`research/fases/F0-preparacion/04-resultados/T0.6-baseline/posiciones_<sid>.json`, con la **misma
normalización** que usa `tests/research/test_baseline_parity.py` (floats redondeados a 10
decimales, claves ordenadas, filas ordenadas por `(t_in_exec, t_exit)`). Compara **sólo las claves
que trae el congelado** (el brazo puede traer claves extra que tú añadas, como `R1`). Si hay
cualquier diferencia → `ControlNoReproduceLineaBaseError` nombrando la primera posición que
difiere, la clave y los dos valores. Devuelve `{"n_congelado": ..., "n_control": ..., "identico": True}`.

### `riesgo.py` — R por posición (E-04 §2.3)

```python
def r_por_posicion(sid, arm_overlay, posiciones, bars) -> list[float | None]
```
Devuelve, en el mismo orden, `R1_i` en **CLP por 1,0 lote**:
`R1_i = abs(entry_fill_i - SL_inicial_i) * bt.CONTRACT * bt.USDCLP`.

- **Escalera (S6/S7):** `SL_inicial` con `bt._sl_inicial_genuine(side_l, idx, bars, k_init,
  entry_bid, wait_mae_atr_k, atr14)` — **el mismo helper que usa `run_ladder`** (mira
  `backtest.py:239-303` para ver cómo lo llama y con qué defaults: `k_init =
  kwargs.get("init_sl_range_k", 1.0)`, `wait_mae_atr_k = kwargs.get("wait_mae_atr_k", 0.0)`,
  `atr14` sólo si `wait_mae_atr_k > 0`). Las kwargs efectivas del brazo se obtienen con
  `overlay.overlay_kwargs(sid, arm_overlay)`. `idx` = índice de la barra de **señal**:
  `int(np.searchsorted(bar_times, pos["t_in"], "left"))`, y **asserta**
  `bars[idx]["t"] == pos["t_in"]`.
- **SuperTrend:** recalcula la línea con los helpers que usa `run_supertrend`
  (`_atr_wilder(highs, lows, closes, atr_period)` y `supertrend(highs, lows, closes, atrf, mult)`),
  con el `atr_period`/`mult`/`sl_offset` **del propio brazo** (defaults 14 / 3.0 / 0.0). Para una
  posición que entra en la barra `j` (`bars[j]["t"] == pos["t_in"]`): `SL_inicial = line[j] -
  sl_offset` si LONG, `line[j] + sl_offset` si SHORT. Si `line[j] is None` → `R1_i = None`.
- Si `R1_i <= 0` o no computable → `None`. **Jamás rellenar con un default.** El número de `None`
  se cuenta y se publica.

---

## BLOQUE 2 — `paired_harness.run_paired_arms`: alineación sólo contra el control (aditivo)

**El problema, medido en el diseño:** P-03 corre **95 brazos**. `run_paired_arms` calcula hoy la
alineación de **todos los pares** — C(95,2) = **4.465** pares, cada uno con su lista `no_casadas`.
Es trabajo y memoria que nadie va a leer: la única alineación que las reglas de decisión usan es
la de **cada brazo contra el brazo de control**.

**Cambio (estrictamente aditivo, default = comportamiento de hoy):**
```python
def run_paired_arms(sid, arms, bars, ticks=None, *,
                    pares: str = "todos", brazo_control: str = "default") -> PairedResult
```
- `pares="todos"` (default) → exactamente el comportamiento actual. **Los 21 tests de
  `tests/research/test_harness_pareado.py` deben seguir verdes sin tocarlos.**
- `pares="contra_control"` → sólo calcula los pares `(brazo_control, otro)` para cada otro brazo.
  Si `brazo_control` no está en `arms`, `ValueError` nombrando las claves disponibles.

Actualiza el docstring. **No cambies nada más de ese fichero.**

Verificación: `python -m pytest tests/research/test_harness_pareado.py -q` → **21 passed**, más
un test tuyo nuevo (en `tests/research/test_ola1.py`) que compruebe que con `pares="contra_control"`
salen exactamente `K-1` entradas en `alignment_signal` y en `alignment_filled`, y que sus valores
**coinciden con los del modo `"todos"`** para esos mismos pares.

---

## BLOQUE 3 — `scripts/research/ola1/metricas.py`

```python
def metricas_de_brazo(sid, arm, overlay, posiciones, bars) -> dict
```
Todo en **CLP por 1,0 lote** salvo donde se diga. Claves exactas (respétalas: el consolidador y el
memo del controlador dependen de ellas):

| clave | definición |
|---|---|
| `n` | nº de posiciones resueltas |
| `net_lote1` | `sum(net1)` |
| `net_por_posicion_lote1` | `net_lote1 / n` (None si n=0) |
| `wr`, `pf`, `maxdd_lote1`, `rom`, `avg_win`, `avg_loss` | de `bt.metrics(posiciones, 1.0)` |
| `net_lote_grid` | `bt.metrics(posiciones, bt.LOT_GRID)["net"]` — comparabilidad con la línea base congelada (`LOT_GRID` = 0.67) |
| `R_mediana`, `R_p25`, `R_p75` | de los `R1_i` computables |
| `n_R_no_computable` | cuántos `R1_i` salieron `None` |
| `net_en_R_total`, `net_en_R_por_posicion` | `sum(net1_i / R1_i)` sobre los computables, y su media |
| `max_perdidas_consecutivas` | racha máxima de posiciones con `net1 < 0`, **ordenadas por `t_exit`** |
| `sharpe_por_posicion` | `media(net1) / desvío(net1)` con `ddof=1`; `None` si `n<2` o desvío 0 |
| `sharpe_diario_ann` | agrega `net1` por **día de servidor de `t_exit`** (`datetime.utcfromtimestamp`), luego `media/desvío × sqrt(252)`; `None` si <2 días |
| `n_por_reason` | `dict` de conteos por `reason` |
| `n_flips` | = `n` (SuperTrend es always-in: cada posición termina en un flip o un toque de línea). Se publica igual para la escalera, con la nota de que ahí no significa flip |
| `net_con_coste_lote1` | overlay E-04 §2.5 |
| `n_posiciones_con_coste` | cuántas recibieron el coste |

**Overlay de coste (E-04 §2.5), exacto:** `COSTE_USD = 0.225`;
`COSTE_CLP = 0.225 * bt.CONTRACT * bt.USDCLP` (= 21071.25). Una posición recibe el coste si
`reason in {"EXIT_INITSL", "EXIT_SL_RAISED", "EXIT_TRAIL", "EXIT_STLINE"}`. `EXIT_TP`,
`EXIT_STFLIP`, `time_stop`, `reverse` y cualquier salida a cierre de barra **no lo reciben**.
`net_con_coste_lote1 = sum(net1_i - COSTE_CLP si aplica else net1_i)`. Define las constantes como
módulo-nivel con un comentario citando **D-54** y **T0.7-M-H** como su origen.

---

## BLOQUE 4 — `scripts/research/ola1/pareado.py`

```python
def pareado_vs_control(sid, posiciones_brazo, posiciones_control, r_control) -> dict
```

1. **Identidad de entrada:** `paired_harness.entry_identity(sid, pos)`. Construye el mapa
   identidad → posición para ambos brazos. 🔴 **Si una identidad aparece dos veces dentro del
   mismo brazo, NO la descartes en silencio:** cuenta las duplicadas, quédate con la primera por
   `t_exit`, y publica `n_identidades_duplicadas`. Un emparejamiento silenciosamente ambiguo
   falsearía todo lo demás.
2. **Subconjunto casado** = intersección de identidades. Claves:
   `n_control`, `n_brazo`, `n_casadas`,
   `tasa_emparejamiento = n_casadas / n_control` (**denominador declarado: las posiciones
   rellenadas del brazo de control**), `n_solo_control`, `n_solo_brazo`.
3. **Degradación automática (D-56, regla dura del pre-registro):**
   `degradado_a_1B = (tasa_emparejamiento < 0.90)`. Es un booleano en el JSON. **Tú lo calculas;
   no lo interpretas ni lo comentas.**
4. **Diferencias pareadas:** `diff_i = net1_brazo_i - net1_control_i` sobre las casadas.
   `media_diff`, `mediana_diff`, `suma_diff`, `desvio_diff`.
   `media_diff_en_R` usando **`R1_i` del control** (E-04 §2.3); excluye las de R no computable y
   publica `n_excluidas_por_R`.
5. **Bootstrap por bloques (E-04 §2.4), exacto y reproducible:**
   - bloque = **día de servidor de `t_in_exec` del control** (`datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")`).
   - `B = 10000`, `numpy.random.default_rng(20260816)`.
   - Se remuestrean **días con reemplazo**, tantos como días observados.
   - 🔴 **Implementación obligatoria por eficiencia y exactitud** (157 brazos × 10.000 no puede
     hacerse concatenando arrays): precalcula por día `suma_dia[d]` y `n_dia[d]`; la media de un
     remuestreo es entonces `sum(suma_dia[muestra]) / sum(n_dia[muestra])`. Es **exactamente** la
     media del pool remuestreado, y cuesta `O(B × n_dias)`. Añade un test que lo compruebe contra
     una implementación ingenua por concatenación sobre un caso pequeño.
   - Salidas: `ic95_bajo`, `ic95_alto` (percentiles 2,5 / 97,5), `ic_excluye_0` (bool),
     `p_bootstrap` = `2 * min(frac(stat <= 0), frac(stat >= 0))` recortado a [0,1],
     `n_dias_bloque`.
   - Si `n_casadas == 0` o `n_dias_bloque < 2`: todo a `None` y `motivo_no_evaluable` con el
     porqué. **Nunca un número inventado.**

---

## BLOQUE 5 — `scripts/research/ola1/secundarias.py`

Las tres definiciones están **cerradas en E-04 §4**. Impleméntalas literalmente.

```python
def secundaria_p02(sid, posiciones_brazo, posiciones_control) -> dict
```
Sobre las casadas, mirando las posiciones que el **brazo** cerró con `reason == "time_stop"`:
`n_cerradas_por_time_stop`, y la descomposición `podadas_perdedoras` / `amputadas_ganadoras`
(cada una con `n` y `suma_delta`), más `net_medio_time_stop_lote1` y `wr_time_stop` sobre las
propias posiciones del brazo.

```python
def secundaria_p03(sid, posiciones_brazo) -> dict
```
Re-flip = par de posiciones consecutivas en el tiempo donde la segunda abre en **sentido
contrario** dentro de **3 barras M15 (2700 s)** desde el cierre de la primera
(`0 <= t_in_exec_2 - t_exit_1 <= 2700` y `side_2 != side_1`). Es **falso** si esa segunda termina
con `net1 < 0`. Publica `n_reflips`, `n_reflips_falsos`, `pct_reflip_falso` (`None` si
`n_reflips == 0` — **no 0,0**: son cosas distintas y confundirlas mentiría).
Ordena por `t_exit`; para la escalera, aplica la definición **por ficha** (`ficha` igual), porque
tres fichas de la misma señal se solapan en el tiempo y sin separarlas el conteo es ruido.

```python
def secundaria_p08(sid, posiciones_brazo, posiciones_control) -> dict
```
Descomposición **exhaustiva** sobre las casadas, en tres cubos: `salvadas` (control salió por
`EXIT_STLINE` y el brazo no), `mismo_stop_peor_fill` (ambos por `EXIT_STLINE`), `otros`. Cada cubo
con `n` y `suma_delta`. 🔴 **`assert` de que las tres sumas dan exactamente `suma_diff`**
(tolerancia 1e-6). Si el assert salta, es un bug tuyo, no un dato.

---

## BLOQUE 6 — `scripts/research/runner/tasks_ola1.py` (el task-type)

```python
def ola1_paired(params: dict, out_dir: Path) -> dict
register("ola1_paired", ola1_paired, parallelizable=True)
```
Y **una sola línea nueva** en `runner.py`, junto a los otros imports de side-effect:
```python
from scripts.research.runner import tasks_ola1  # noqa: F401 -- side effect: registers ola1_paired
```

**`params` (viene del manifiesto; todo lo que no sea `run_key`/`tipo`):**
```yaml
palanca: P-02
sid: S6-K2P0
clase: "1-A"
brazo_control: default
secundaria: p02          # p02 | p03 | p08 | none
brazos:
  default: {}
  mhb10:   {max_hold_bars: 10}
  ...
```
Cada valor de `brazos` es el **overlay** que se pasa al harness. Para la escalera son kwargs de
`simular_variant` (vía `overlay_kwargs`); para SuperTrend son kwargs de `run_supertrend`
(`atr_period`, `mult`, `sl_offset`) — así lo define WP-1+2.

**Qué hace, en orden:**
1. `bars = sustrato.cargar_barras()`.
2. `run_paired_arms(sid, brazos, bars, pares="contra_control", brazo_control=params["brazo_control"])`.
3. Por cada brazo, **según lo va terminando**, escribe una línea en `<out_dir>/_brazos.txt`
   (append atómico, `flush`) con `brazo  n  net_lote1  segundos` y la imprime por stdout. Es la
   visibilidad de progreso **dentro** de la corrida: con 95 brazos en una sola corrida, el
   `_progreso.txt` del runner sólo se mueve al final, y el humano necesita ver el avance.
   ⚠️ Para poder emitir esa línea por brazo tienes que resolver brazo a brazo: si `run_paired_arms`
   no te lo permite tal cual, **llama tú a los mismos componentes en el mismo orden** y construye
   el `PairedResult` — pero entonces **añade un test** que compruebe que tu camino produce
   posiciones **idénticas** a `run_paired_arms` para un caso de 2 brazos. No divergencia silenciosa.
4. `sustrato.verificar_holdout(...)` sobre **todas** las posiciones de **todos** los brazos.
5. `sustrato.verificar_control_contra_linea_base(sid, brazos[control])` — 🔴 **si falla, la corrida
   entera falla**, ruidosamente. Es la regla 5 del pre-registro: si el control no reproduce la
   línea base, ningún otro brazo es interpretable.
6. `riesgo.r_por_posicion` para cada brazo → añade la clave `R1` a cada posición.
7. `metricas.metricas_de_brazo` para cada brazo.
8. `pareado.pareado_vs_control` para cada brazo ≠ control.
9. La secundaria que diga `params["secundaria"]`, para cada brazo ≠ control.
10. Escribe en `out_dir`:
    - `posiciones.csv` — todas las posiciones de todos los brazos (`PairedResult.rows()` +
      columnas `R1` y `net1_con_coste`). Es el dato crudo; nada se deriva de otro sitio.
    - `metricas.json` — el objeto completo (ver §7).
    - `alineacion.json` — `alignment_signal` y `alignment_filled` contra el control. Guarda los
      **conteos completos** y, de `no_casadas`, **como mucho las 50 primeras** identidades por par
      (más el total). Serializa las tuplas como listas.
    - `_brazos.txt` — la bitácora de progreso.
11. **Devuelve** un dict compacto (va a `_resumen.json` y al LEDGER): `palanca`, `sid`, `clase`,
    `n_brazos`, `n_confirmatorios`, `estado_investigacion: "piloto-instrumento"` (D-57),
    `control_reproduce_linea_base: True`, y por brazo `{n, net_lote1, net_por_posicion_lote1,
    tasa_emparejamiento, media_diff, ic95_bajo, ic95_alto, ic_excluye_0, p_bootstrap}`.

**Fail-loud (charter, protocolo 06 §6):** cualquier anomalía —holdout tocado, control que no
reproduce, identidad duplicada inesperada, R no computable en más del 50 % de un brazo— **lanza**.
El runner en `--on-error continue` la registrará con traceback y seguirá con las demás corridas.
**Jamás rellenes con un default ni sigas en silencio.**

---

## BLOQUE 7 — forma exacta de `metricas.json`

```json
{
  "lineage": {"run_id","palanca","sid","clase","substrate_id","engine_sha","git_sha",
              "etapa","generador","timestamp","estado_investigacion","preregistro","ampliacion"},
  "sustrato": {"n_barras", "t0", "t1", "holdout_excluido"},
  "control": {"brazo","n_congelado","n_control","identico"},
  "brazos": {
    "<nombre>": {
      "overlay": {...},
      "confirmatorio": true,
      "metricas": { ...Bloque 3... },
      "pareado": { ...Bloque 4... },      // ausente en el propio control
      "secundaria": { ...Bloque 5... }    // ausente en el control o si secundaria == none
    }
  }
}
```
`substrate_id` = `"capitaria-ticks-2026-preholdout"`. `etapa` = `"F0"`. `preregistro` =
`"research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-ola1.md"`. `ampliacion` =
`".../2026-08-16-ampliacion-E04-ola1.md"`. `git_sha`/`engine_sha`: `git rev-parse HEAD` **en el
momento de correr** (usa `lineage.git_sha()` del runner, que ya existe).
🔴 **Ningún fichero de datos lleva conclusiones, lecturas ni adjetivos** (charter §A.4).

---

## BLOQUE 8 — `manifiesto.py`, `consolidar.py` y `correr_ola1.py`

### `scripts/research/ola1/manifiesto.py`
CLI: `python -m scripts.research.ola1.manifiesto [--salida <ruta>] [--engine-sha <sha>]`.
Genera `research/fases/F0-preparacion/03-runs/2026-08-16-ola1.yaml` a partir de las grillas de
**E-04 §3, hardcodeadas aquí** (son el pre-registro; no se leen de ningún sitio configurable).
Cinco corridas:

| run_key | palanca | sid | clase | secundaria | brazos |
|---|---|---|---|---|---:|
| `P02-S6` | P-02 | S6-K2P0 | 1-A | p02 | 17 |
| `P02-S7` | P-02 | S7-TPNONE | 1-A | p02 | 17 |
| `P03-S6` | P-03 | S6-K2P0 | 1-A | p03 | 95 |
| `P05-ST` | P-05 | SuperTrend-p14x3-M15 | 1-B | none | 17 |
| `P08-ST` | P-08 | SuperTrend-p14x3-M15 | 1-A | p08 | 11 |

**Total 157 brazos.** Nombres de brazo (fíjalos así, el memo los va a citar):
`default`; P-02 `mhb<N>`; P-03 `u<pips>-lb<L>-h<H>` más `ac_off` y `factor<F>` (p.ej. `factor0.10`);
P-05 `mult<M>` (p.ej. `mult2.25`); P-08 `slo<O>` (p.ej. `slo0.05`).
`ac_decel_umbral = umbral_pips * 0.01` (E-04 §2.1) y el YAML guarda **las dos**: el nombre lleva
los pips y el overlay lleva el valor en unidades AC, con un comentario en la cabecera del YAML
explicando la conversión.
Cabecera del manifiesto con los campos que el runner exige: `experimento: OLA1-palancas-de-salida`,
`area: B`, `etapa: F0`, `hipotesis: <ruta al pre-registro>`, `substrate_id:
capitaria-ticks-2026-preholdout`, `engine_sha`, `salidas: {resultados:
research/fases/F0-preparacion/04-resultados/OLA1/, ledger: append}`.

🔴 **Test obligatorio `test_los_44_preregistrados_son_subconjunto_exacto`:** codifica en el test
los **44 brazos confirmatorios tal como los lista el pre-registro** y comprueba, contra el YAML
generado, que los 44 están presentes con su overlay exacto y que hay 157 brazos en total. Si el
generador se desviara del pre-registro, este test es lo único que lo atrapa.

### `scripts/research/ola1/consolidar.py`
CLI: `python -m scripts.research.ola1.consolidar <resultados_dir>`. Lee todos los
`<run_key>/metricas.json` y produce:
- `_consolidado.json` — **una fila plana por brazo** (157) con palanca, sid, clase,
  confirmatorio, overlay, todas las métricas y todo lo pareado.
- `_consolidado.md` — tablas markdown, **una por corrida, con TODOS sus brazos** (nunca sólo el
  mejor), ordenadas por el valor del parámetro barrido, no por resultado. Cabecera con el banner de
  §8-bis. Sin una sola conclusión.
- **BH-FDR al 5 %** sobre `p_bootstrap`, calculado **dos veces** (E-04 §2.4): `p_bh_confirmatorio`
  (sólo brazos confirmatorios no-control) y `p_bh_total` (todos los no-control), cada uno con su
  booleano de rechazo. Documenta el procedimiento en el docstring.
- Brazos sin `p_bootstrap` (no evaluables) quedan **fuera del denominador de BH** y se cuentan
  aparte, declarados.

### `scripts/research/ola1/correr_ola1.py` — **UNA sola orden para toda la ola**
CLI: `python -m scripts.research.ola1.correr_ola1 [--workers N] [--manifiesto <ruta>]
[--ledger-path <ruta>]`. Hace, en orden y sin preguntar nada:
1. imprime `git rev-parse HEAD` y la hora de inicio;
2. `run_manifest(manifiesto, on_error="continue", workers=N)` — **`continue` siempre**, para que
   una corrida mala no mate la noche (D-53);
3. `consolidar` sobre el directorio de resultados;
4. escribe `_ESTADO.md` (§8-bis);
5. imprime un resumen final de dos líneas: corridas ok/fallidas y rutas de los tres ficheros que
   el humano va a abrir.
Código de salida ≠ 0 si alguna corrida falló. **No debe requerir ninguna intervención entre el
paso 1 y el 5.**

### §8-bis — el banner, literal, en `_ESTADO.md` y en la cabecera de `_consolidado.md`

```
🔴 PRE-INTERPRETACIÓN — DATOS SIN LEER
Este fichero contiene resultados crudos de la Ola 1. NO contiene interpretación, ni lectura,
ni veredicto, ni recomendación (charter §A.4).
Ninguna interpretación de estos datos es válida hasta haber sido discutida en profundidad con
el humano y aprobada por él (directiva del user, 2026-08-16). Lo que el controlador escriba
antes de esa conversación es PROPUESTA DE LECTURA y vive en un fichero aparte.
Estado del resultado: piloto-instrumento (D-57) — el congelado del motor no está firmado.
```

---

## BLOQUE 9 — tests (`tests/research/test_ola1.py`)

Como mínimo, y todos con datos reales del sustrato salvo donde se diga sintético:
1. `test_los_44_preregistrados_son_subconjunto_exacto` (§8) — **el más importante del fichero**.
2. `test_manifiesto_valida_contra_el_runner` — `load_manifest()` sobre el YAML generado no lanza y
   ve 5 corridas con `tipo` registrado.
3. `test_control_reproduce_linea_base_para_las_tres_estrategias` — `verificar_control_contra_linea_base`
   pasa con el brazo `{}` para S6, S7 y ST. (Marca `slow` si tarda más de ~10 s.)
4. `test_guarda_de_holdout_dispara` — posición sintética con `t_exit` dentro del sello → lanza.
5. `test_bootstrap_vectorizado_igual_al_ingenuo` (§4.5) — mismo `rng`, caso pequeño.
6. `test_bootstrap_es_reproducible` — dos llamadas con la misma semilla dan bit a bit lo mismo.
7. `test_ic_de_diferencia_cero_contiene_cero` — brazo idéntico al control ⇒ `media_diff == 0`,
   `ic_excluye_0 == False`, `tasa_emparejamiento == 1.0`.
8. `test_pares_contra_control_coincide_con_todos` (§2).
9. `test_overlay_de_coste_solo_toca_salidas_por_nivel` — sintético, las 4 razones que sí y al menos
   3 que no.
10. `test_r_por_posicion_escalera_y_supertrend` — R > 0 y computable para ≥95 % de las posiciones
    del brazo por defecto de cada estrategia; publica el conteo.
11. `test_secundaria_p08_suma_exactamente_la_diferencia` (§5).
12. `test_reflip_definicion` — sintético con un caso dentro de 3 barras y otro fuera.
13. `test_task_type_registrado_y_manifiesto_de_humo_corre` — manifiesto **diminuto** (1 corrida,
    2 brazos de P-08) con `tmp_path` como `resultados` y `--ledger-path` a un fichero temporal;
    comprueba que se escriben `metricas.json`, `posiciones.csv`, `alineacion.json`, `_brazos.txt`.
    🔴 **Nunca contra `research/LEDGER.jsonl` ni contra `04-resultados/OLA1/`.**

---

## §9 · LO QUE NO DEBES HACER — leer dos veces

🔴 **NO corras la Ola 1 completa.** Ni «para probar», ni «una corrida corta», ni con `--workers 1`,
ni contra `research/fases/F0-preparacion/04-resultados/OLA1/`. La corrida real la lanza el
CONTROLADOR, una sola vez, y sus filas del LEDGER y su `git_sha` tienen que corresponder a esa
corrida. Una corrida tuya «de prueba» contra las rutas reales **contamina el registro** y obliga a
repetir todo con `supersedes`.
Tus pruebas: manifiestos de humo de 1-2 brazos, `tmp_path`, LEDGER temporal. Punto.

🔴 **NO escribas en** `research/LEDGER.jsonl`, `research/TRACKER.md`, `research/DECISIONES.md`, ni
en los ficheros de `01-hipotesis/`.

🔴 **NO toques** `sentinel_engine/**`, `tests/research/test_baseline_parity.py`, ni
`04-resultados/T0.6-baseline/**`.

---

## Reporte final (UN fichero: `02-specs/OLA1-EXEC-reporte.md`)

(a) rutas exactas y SHA de cada commit; (b) comandos ejecutados y **salida real** (incluida la
puerta de paridad al principio y al final, y el conteo de brazos del YAML generado); (c) lo que NO
pudiste hacer y por qué; (d) el **tiempo medido** de la corrida de humo, para que el controlador
pueda estimar la corrida completa; (e) sólo las preguntas que exijan decisión.

**Mensaje final:** estado, SHAs, una línea de tests, tiempo de humo medido, preguntas de decisión.
Nada más.
