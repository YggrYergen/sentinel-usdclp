# WP-2b — Reporte final

## (a) Rutas producidas y SHA de cada commit

- `tests/analysis/test_borde_del_dia.py` (modificado, Bloque 1) — commit `7ae06db`
  "fix(WP-2b B1): la cita del gate de spread se localiza por contenido, no
  por numero de linea (tercera rotura del mismo tipo)"
- `sentinel_engine/strategies/emasar_variant.py` (modificado, Bloque 2) — commit `323af83`
  "feat(WP-2b B2): ac_modulate_hold_bars aditivo (P-03, duracion del apriete
  de AC), default=1 byte-identico"
- `tests/research/test_ac_modulate_hold.py` (nuevo, Bloque 2) — commit `323af83`
- `research/fases/F0-preparacion/02-specs/WP-2b-progreso.md` (nuevo) — commit
  `7ae06db` (Bloque 0+1), actualizado en `323af83` (Bloque 2)
- `research/fases/F0-preparacion/02-specs/WP-2b-reporte.md` (este fichero, sin commitear)

`git status --short` tras el último commit no muestra ninguna de las rutas
propias pendiente; los ficheros `??` restantes en el árbol son preexistentes,
ajenos a este brief (no tocados).

## (b) Comandos ejecutados y salida real

### Bloque 0 — línea de partida

```
python -m pytest tests/research/test_baseline_parity.py -m slow -q
```
```
4 passed in 2.42s
```

```
python -m pytest tests/analysis -q
```
```
1 failed, 306 passed in 56.96s
```
(fallo: `test_cita_gate_spread_harness_verificada_contra_el_fichero_real`,
exactamente el que arregla el Bloque 1)

```
python -m pytest tests/research -q
```
```
300 passed, 4 deselected in 25.02s
```

```
python -m pytest tests/strategies -q
```
```
272 passed in 3.59s
```

Coincide con la línea de partida esperada del brief (medida en `659a121`).

### Bloque 1 — cita por contenido

Diseño: `_localizar_cita_gate_spread(texto)` (función auxiliar nueva en el
propio fichero de test, parametrizada por texto — no lee el fichero
directamente) busca `"abs(sp - 0.5) <= 0.05"` sobre todas las líneas de
`texto`, exige exactamente una ocurrencia, y verifica que esa línea cae entre
`def resolve(` y el siguiente `def ` de módulo. `backtest.py` real la cita
hoy en la línea 400 (índice 399), dentro de `resolve()` (366-474).

```
python -m pytest tests/analysis/test_borde_del_dia.py -q
```
```
31 passed in 0.58s
```

```
python -m pytest tests/analysis -q
```
```
307 passed in 53.12s
```

```
python -m pytest tests/research/test_baseline_parity.py -m slow -q
```
```
4 passed in 2.58s
```

**Verificación por mutación** (sobre el CONTENIDO en memoria del fichero
real, sin escribir ni modificar `backtest.py` en ningún momento; se
comprobó `texto_despues == texto_original` tras el experimento):

- Mutación (a), borrar la cadena (`replace` sobre el texto en memoria):
  ```
  MUTACION (a) OK, excepcion: la constante del gate de spread desaparecio de backtest.py
  ```
- Mutación (b), duplicar la línea que la contiene:
  ```
  MUTACION (b) OK, excepcion: la cadena 'abs(sp - 0.5) <= 0.05' aparece en mas de una linea, ambiguedad -- lineas encontradas: [400, 401]
  ```
- Confirmación: `backtest.py sin modificar: True`

### Bloque 2 — `ac_modulate_hold_bars`

Sitio: `sentinel_engine/strategies/emasar_variant.py`. Kwarg nuevo al final
de la firma de `simular_variant` (`ac_modulate_hold_bars: int = 1`); guard
`ValueError` junto al guard de `wait_mae_atr_k`; contador
`ac_modulate_hold_by_tag: dict[str, int] = {}` inicializado junto a
`ac_decel_consec_by_tag`; bloque AC-modulated trailing (antes en
963-969, verificado en el código actual sin desplazamiento) sustituido por
la semántica de contador con re-arme; reset `ac_modulate_hold_by_tag = {}`
añadido en los tres sitios de apertura de ficha (junto a
`ac_decel_consec_by_tag = {}`, líneas 1238/1452/1468 verificadas en el
código actual).

```
python -m pytest tests/research/test_ac_modulate_hold.py -q
```
```
6 passed in 0.65s
```

```
python -m pytest tests/research/test_baseline_parity.py -m slow -q
```
```
4 passed in 2.21s
```

```
python -m pytest tests/strategies -q
```
```
272 passed in 3.67s
```

```
python -m pytest tests/research -q
```
```
306 passed, 4 deselected in 15.90s
```
(300 de la línea de partida + 6 de `test_ac_modulate_hold.py`)

```
python -m pytest tests/analysis -q
```
```
307 passed in 53.27s
```

### Diseño de los 5 tests de `tests/research/test_ac_modulate_hold.py`

- `test_default_hold_1_es_byte_identico_al_motor_de_hoy`: S6-K2P0 (kwargs
  vivos, `copy.deepcopy`), 400 primeras barras reales
  (`scripts.analysis.realtick_bt.backtest.load_bars()`), sin el kwarg vs.
  `ac_modulate_hold_bars=1` explícito — eventos `==` exactos. Verificado
  aparte con script ad-hoc: `True`, 105 eventos.
- `test_hold_mayor_que_1_persiste_el_apriete` y
  `test_rearme_dentro_de_la_ventana`: fixture sintética determinista
  (`random.Random(seed)`, mismo patrón que
  `tests/strategies/test_emasar_variant.py::_synthetic_bars`) con gate
  relajado (`confirm_mode=1, require_ema_order=False`) para forzar una
  entrada LONG temprana con F1 (`active_fichas=1`) que permanece abierta.
  Los bares de disparo/no-disparo de `ac_desacelerando` se localizaron
  offline (script de exploración, no incluido en el repo) computando
  `ac_series`/`ac_desacelerando` directamente sobre la fixture: semilla 1,
  disparo en barra 60 y no en 61 (hold=1 vs hold=3, comparados vía
  `return_state=True` truncando bars a `[:62]`); semilla 11, disparos en
  146 y 148 con no-disparo en 147 (hold=1 vs hold=2, truncando a `[:150]`).
  El efecto observable comparado es el `sl` de F1 reportado por
  `return_state=True` (no variables internas): estrictamente más alto
  (trail más apretado) en el hold que debe seguir apretando. Verificado
  offline que las barras previas al punto de comparación producen el mismo
  `sl` en ambas corridas (misma línea histórica), así que la diferencia solo
  puede venir del manejo del contador en la barra comparada.
- `test_hold_bars_invalido_falla_ruidoso` (parametrizado 0 y -1): `ValueError`
  cuyo mensaje contiene el valor recibido. Verificado aparte: mensaje
  `"ac_modulate_hold_bars must be >= 1 (...); got ac_modulate_hold_bars=0"`
  (y análogo para -1).
- `test_ac_modulate_false_ignora_el_parametro`: S7-TPNONE (kwargs vivos,
  `copy.deepcopy`, `ac_modulate=False`), 400 primeras barras reales,
  `hold_bars=1` vs `hold_bars=10` — eventos `==` exactos. Verificado aparte:
  `True`, 117 eventos.

## (c) Lo que NO pude hacer y por qué

Nada. Los dos bloques quedaron verdes, con puerta de paridad `4 passed` en
ambos casos, y se commitearon inmediatamente cada uno.

## (d) Diferencias código vs. brief (informativas, no bloqueantes)

- El bloque AC-modulated trailing citado por el brief como "líneas 963-969"
  está, en el código verificado al empezar, exactamente en esas mismas
  líneas (963-969) — no se había desplazado. Sin cambios de ubicación que
  reportar.
- Añadí un párrafo a la docstring de `simular_variant` documentando
  `ac_modulate_hold_bars` (no lo pide explícitamente el diseño cerrado del
  Bloque 2, pero sigue la convención existente del fichero de documentar
  cada palanca V-XX/P-XX en la docstring). Es aditivo, no cambia
  comportamiento.

## Preguntas que exigen decisión del controlador

Ninguna.
