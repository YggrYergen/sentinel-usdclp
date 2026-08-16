# OLA1B -- reporte final (BLOCK A de esta tarea)

**Rol:** IMPLEMENTADOR (Sonnet 5 high effort). **Rama:** `equipo1`. **Fecha:** 2026-08-16.
Documento de ENSAMBLAJE puro -- todo numero citado aqui ya existe en disco, producido por
sesiones/commits anteriores. Ningun computo nuevo se hizo para escribir este reporte.
🔴 **PRE-INTERPRETACION.** Datos, rutas y comandos -- ningun veredicto, ranking ni
recomendacion (charter §A.4/§B).

---

## 0 · Commits de esta ola, en orden

| Commit | Contenido |
|---|---|
| `a6a6979` | BLOCK-1+2: punto de inyeccion `htf_mask` (wiring WP-3) + `ac_modulate_floor_relief_k` (correccion del piso P-03), ambos aditivos/off-by-default |
| `877e5cd` | BLOCK-1: `backtest.build_htf_mask` -- el punto de inyeccion que pedia WP-3, cableado al loop de decision via `htf_mask` |
| `bac393e` | BLOCK-1 addendum: `apply_regime_gate_by_entry_bar` -- post-filtro a nivel de harness que conecta `regime.py` (WP-5) con la mitad de gate-de-entrada de P-09 |
| `ad2ef41` | BLOCK-3a (D-60): recorte de sustrato para P-02 -- `ola1_paired` gana `margen_extra_s`, verificado que ningun valor de `max_hold_bars` de la grilla toca el holdout |
| `8e9d708` | **preregistro(OLA1B)**: P-02 re-corrida (sustrato D-60) + P-03-floor (NUEVO) + P-34 (NUEVO LEVER) -- ESCRITO ANTES DE CORRER |
| `fe6ffca` | BLOCK-3: `manifiesto_ola1b.py` -- genera el manifiesto de las 4 corridas de la pre-registro OLA1B |
| `cae0475` | BLOCK-4: `consolidar.py` gana `net_positivo`/`diff_positivo` + banner de unidad/fiabilidad (clarificacion del coordinador a mitad de tarea) |
| `78e8225` | feat(next-run hook): `ola1_paired._expandir_htf_en_brazos` -- deja que un overlay de manifiesto declare `htf_mask` via parametros LOGICOS (`_htf: {tf_sec, field, ...}`) en vez de un array literal de 8.334 floats |
| `69bad91` | resultados(OLA1B): 63 brazos en 4 corridas + 4 filas de LEDGER; unidad de `net_lote1` confirmada CLP |

**`git_sha` REAL de la corrida (el que llevan las 4 filas del LEDGER y `metricas.json` de
cada corrida):** `fe6ffca`. **No** el de este commit de pre-registro ni el de commits
posteriores -- verificado leyendo `research/LEDGER.jsonl` directamente (los 4 `run_id`
`P34-S6`/`P02-S6`/`P02-S7`/`P03FLOOR-S6` de `experimento=OLA1B-palancas-de-salida` traen
`"git_sha": "fe6ffca", "engine_sha": "fe6ffca"`).

⚠️ **Nota de trazabilidad, declarada, no un error de dato:** `research/fases/F0-preparacion/04-resultados/OLA1B/_ESTADO.md`
(generado por `correr_ola1.py`, reusado con `--manifiesto` apuntando al YAML de OLA1B)
imprime `git_sha (momento de correr): cae0475b6bc813d2dbe86c14e2a13e0c9eea5235` -- un commit
POSTERIOR a `fe6ffca` en el log (`cae0475` = BLOCK-4, que solo anadio columnas derivadas a
`consolidar.py`). Consistente con que `correr_ola1.py` se re-invoco sobre el mismo
manifiesto tras `cae0475` para regenerar `_consolidado.md`/`.json` con las columnas nuevas;
`run_manifest` es idempotente por `_runner_state.json` y no re-ejecuto ninguna de las 4
corridas (ya `ok`), asi que su `lineage.git_sha()` propio -- capturado dentro de cada tarea,
en el momento en que SI corrio -- se quedo en `fe6ffca`. La fuente de verdad por posicion es
el `git_sha` de cada corrida individual (`fe6ffca`), no el de `_ESTADO.md`, que solo fecha
la ultima vez que el WRAPPER se ejecuto.

---

## 1 · Que corrio (resumen ejecutivo del pre-registro `8e9d708`)

Pre-registro completo: `research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-OLA1B.md`.

| Corrida | Palanca | `sid` | Brazos | Confirmatorios | Control |
|---|---|---|---|---|---|
| `P02-S6` | P-02 (re-corrida, sustrato D-60) | S6-K2P0 | 17 | 7 | `default` |
| `P02-S7` | P-02 (re-corrida, sustrato D-60) | S7-TPNONE | 17 | 7 | `default` |
| `P03FLOOR-S6` | P-03-floor (NUEVO: `ac_modulate_floor_relief_k` × `ac_decel_umbral`) | S6-K2P0 | 20 | 20 | `relief1.00-u0` |
| `P34-S6` | P-34 (NUEVO LEVER: barrido de `trail_atr_floor_k`) | S6-K2P0 | 9 | 9 | `default` (= `floork2.00`) |

**Total: 63 brazos en 4 corridas, 43 confirmatorios.** Comando de ejecucion (una sola
orden, D-58 punto 3, sin intervencion agentica entre el inicio y el fin):
```
python -m scripts.research.ola1.correr_ola1 --manifiesto research/fases/F0-preparacion/03-runs/2026-08-16-ola1b.yaml --workers N
```
Manifiesto generado por: `python -m scripts.research.ola1.manifiesto_ola1b` (commit `fe6ffca`).

---

## 2 · La correccion de wiring de WP-5 -- desviacion documentada

**El BLOCK 1 del brief anterior pedia** cablear el regimen "en el loop de decision" del
motor. **Lo que en cambio se hizo, y por que es correcto:** `apply_regime_gate_by_entry_bar`
(commit `bac393e`) es un **post-filtro a nivel de harness**, aplicado DESPUES de
`run_ladder()`/`run_supertrend()` sobre las posiciones de senal, ANTES de `resolve()` --
`sentinel_engine` (el motor real, `emasar_ref.py`/`emasar_variant.py`/
`live_configs_20.py`) **no se toca en absoluto**.

**Justificacion, verbatim de las dos fuentes que obligan la desviacion:**
- La fila de WP-5 en la spec de instrumentacion de motor
  (`research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md`,
  §2, tabla) dice literalmente: *"modulo nuevo, SIN TOCAR el nucleo"*.
- El docstring del propio `regime.py` (cabecera del modulo, WP-345-reporte.md §1)
  confirma: *"Does not touch `backtest.py` at all... este modulo es un add-on puro,
  standalone, consumido (si acaso) por levers de estrategia futuros, no cableado al motor
  aqui"*.

El brief del BLOCK 1 estaba en tension directa con esas dos fuentes cerradas (spec +
docstring del propio codigo). El predecesor aplico correctamente **"el codigo gana"**
(charter §4, y ver tambien la regla identica que este mismo reporte aplica en §4 mas abajo
para `run_supertrend`/P-20): el gate de regimen vive en el harness, no en el motor. Esto
NO es una relajacion del alcance de P-09 -- P-09 se corre igual (ver OLA2-reporte.md, ya
que P-09 en si no formaba parte de la grilla de OLA1B), solo cambia DONDE vive el gate.
**Queda como desviacion documentada, no como incumplimiento silencioso.**

---

## 3 · La entrada de catalogo de P-34 (formato exacto de la Parte 1 del catalogo)

**No se edita** `research/fases/F0-preparacion/05-analisis/2026-08-15-catalogo-palancas-y-requisitos-motor.md`
(artefacto del controlador). La entrada completa, en el MISMO formato que las 33 palancas
existentes (P-01..P-33), vive AQUI:

### P-34 — Barrido del piso ATR del trailing de S6 (`trail_atr_floor_k`)
- **Mecanismo:** `trail_atr_floor_k` gobierna la distancia de trailing de S6 el **100 % del
  tiempo** bajo los kwargs vivos (DIAG-P03, `7c4ea92`: el piso `2.0×ATR14` domina al trail
  sin modular Y al trail modulado por AC en las **8.321/8.321** barras con ATR14 valido,
  minimo medido del piso `8.67`); su valor vivo (`2.0`) fue elegido **sin grilla**.
- **Estrategia:** S6-K2P0 unicamente (mismo alcance que P-03 en la Ola 1 original --
  `trail_atr_floor_k` no forma parte de la config viva de S7-TPNONE, verificado en
  `live_configs_20.py`).
- **Origen:** hallazgo propio de la sesion (DIAG-P03, no de la literatura T0.10/T0.11) --
  el barrido nunca existio porque el propio piso nunca se habia expuesto como parametro
  antes de esta ola.
- **Evidencia:** N/A (no es una palanca de literatura, es un parametro vivo sin grilla
  previa, motivado por una medicion propia del programa, no por una fuente externa).
- **Estatus vs. plan:** EXTENSION -- ningun mod de los 12 originales ni del catalogo de 33
  cubria el piso ATR como eje de barrido; P-03 (AC-modulate) lo asumia constante.
- **Requisito de motor:** ya cubierto -- `trail_atr_floor_k` ya era un kwarg existente de
  `emasar_variant.simular_variant` (agregado en un mod anterior para permitir el piso
  mismo); solo faltaba exponerlo al harness pareado, que ya existe (mod #1).
- **Grid:** `{2.00 (control/vivo), 1.75, 1.50, 1.25, 1.00, 0.75, 0.50, 0.25, 0.00
  (piso desactivado)}` -- 9 valores, todos confirmatorios, grilla pequena y deliberada;
  incluye el control explicitamente EN la grilla (clarificacion del coordinador).
- **Metrica/criterio:** diferencia pareada de `net1` (brazo − control=2.0) sobre el
  subconjunto casado, bootstrap por bloques de dia de servidor (B=10.000, semilla
  `20260816`), IC 95 % que excluye 0, BH-FDR α=0.05 sobre los 9 (junto con P-03-floor, un
  solo lote de 29 comparaciones).
- **Pareado-por-entrada:** SI, sujeto a verificacion (D-56) -- `trail_atr_floor_k` es una
  palanca de SALIDA pura; en ausencia de que `stop_and_reverse` cambie el conjunto de
  entradas posteriores se espera tasa alta, pero se MIDE, no se asume (ver §5 tabla de
  tasas -- de hecho la tasa cae con fuerza segun el brazo, 0.97-1.00, y `n` varia mucho por
  brazo, 678-1074, evidencia directa de que el "pareado por entrada" de esta palanca NO es
  trivial: `stop_and_reverse=True` en S6 hace que una salida distinta por trailing cambie
  cuando se re-entra).
- **Conflictos:** con P-03-floor (`ac_modulate_floor_relief_k`) -- ambas tocan el mismo
  `max(...)` de `trail_efectivo` en `emasar_variant.py:1050-1058`, por rutas distintas
  (piso base vs. piso durante el apriete de AC). No se corren combinadas en esta ola
  (grillas ortogonales); grilla cruzada queda como pendiente declarado de una ola futura.

---

## 4 · La discrepancia de formula de P-15 -- reportada, NO relitigada

El pre-registro OLA1B no ejecuta P-15 (es un lever de OLA2, ver `OLA2-reporte.md`), pero el
predecesor de esta tarea dejo la discrepancia marcada para que se reportara aqui, y se
repite en el pre-registro OLA2 (§6(g)) porque OLA2 es quien la EJECUTA por primera vez:

- **Formula de la fuente** (`area-3-sizing-riesgo-equity.md` §2.3, catalogo P-15):
  `size_adjusted = base_size / sqrt(1 + overlap)`, con `overlap ∈ {0.60, 0.70, 0.80}` (de
  donde salen los factores ≈0.79/0.77/0.75 -- cerca pero no identicos a los
  `{0.70, 0.77, 0.85}` que el catalogo tabula como grid).
- **Formula IMPLEMENTADA en `sizing.py`** (WP-4, `lot_multiplier`, linea del modulo):
  `mult *= 1.0 / (1.0 + cfg.correlation_discount_per_extra * n_extra)` -- un mecanismo
  DISTINTO: descuento multiplicativo por CADA estrategia extra concurrente detectada en
  tiempo de ejecucion (`_concurrency_at_open`), no una funcion cerrada de una fraccion de
  overlap fija medida offline.
- **No se relitiga aqui.** Se reporta como hecho verificado leyendo ambas fuentes
  (`area-3-sizing-riesgo-equity.md` y `sizing.py`); la decision de que hacer con la
  discrepancia (implementar la formula original, aceptar la sustitucion, o correr ambas)
  es de interpretacion (Opus), no de este reporte.

---

## 5 · Tabla completa de tasas de emparejamiento (los 63 brazos, sin excepcion)

Fuente: `research/fases/F0-preparacion/04-resultados/OLA1B/_consolidado.md` (commit
`69bad91`), columna `tasa_emparejamiento`. `n/a` = brazo de control (no tiene pareado
contra si mismo).

### P02-S6 (control `default`, n=615)
| brazo | n | tasa_emparejamiento |
|---|---:|---:|
| mhb4 | 849 | 1.00 |
| mhb6 | 774 | 0.99 |
| mhb8 | 723 | 1.00 |
| mhb10 | 693 | 1.00 |
| mhb12 | 666 | 1.00 |
| mhb15 | 636 | 1.00 |
| mhb20 | 630 | 1.00 |
| mhb25 | 621 | 1.00 |
| mhb30 | 618 | 1.00 |
| mhb40 | 615 | 1.00 |
| mhb48 | 615 | 1.00 |
| mhb56 | 615 | 1.00 |
| mhb64 | 615 | 1.00 |
| mhb80 | 615 | 1.00 |
| mhb96 | 615 | 1.00 |
| mhb128 | 615 | 1.00 |

### P02-S7 (control `default`, n=696)
| brazo | n | tasa_emparejamiento |
|---|---:|---:|
| mhb4 | 858 | 1.00 |
| mhb6 | 795 | 0.99 |
| mhb8 | 750 | 1.00 |
| mhb10 | 735 | 1.00 |
| mhb12 | 720 | 1.00 |
| mhb15 | 705 | 1.00 |
| mhb20 | 702 | 1.00 |
| mhb25 | 699 | 1.00 |
| mhb30 | 696 | 1.00 |
| mhb40 | 696 | 1.00 |
| mhb48 | 696 | 1.00 |
| mhb56 | 696 | 1.00 |
| mhb64 | 696 | 1.00 |
| mhb80 | 696 | 1.00 |
| mhb96 | 696 | 1.00 |
| mhb128 | 696 | 1.00 |

### P03FLOOR-S6 (control `relief1.00-u0`, n=624)
| brazo | n | tasa_emparejamiento |
|---|---:|---:|
| relief0.00-u0 | 891 | 1.00 |
| relief0.00-u25 | 855 | 1.00 |
| relief0.00-u50 | 834 | 1.00 |
| relief0.00-u75 | 813 | 1.00 |
| relief0.25-u0 | 846 | 1.00 |
| relief0.25-u25 | 828 | 1.00 |
| relief0.25-u50 | 813 | 1.00 |
| relief0.25-u75 | 786 | 1.00 |
| relief0.50-u0 | 780 | 1.00 |
| relief0.50-u25 | 765 | 1.00 |
| relief0.50-u50 | 756 | 1.00 |
| relief0.50-u75 | 738 | 1.00 |
| relief0.75-u0 | 678 | 1.00 |
| relief0.75-u25 | 675 | 1.00 |
| relief0.75-u50 | 675 | 1.00 |
| relief0.75-u75 | 672 | 1.00 |
| relief1.00-u25 | 624 | 1.00 |
| relief1.00-u50 | 624 | 1.00 |
| relief1.00-u75 | 624 | 1.00 |

### P34-S6 (control `default`=`floork2.00`, n=624)
| brazo | n | tasa_emparejamiento |
|---|---:|---:|
| floork0.00 | 1074 | 0.97 |
| floork0.25 | 1020 | 0.97 |
| floork0.50 | 999 | 0.99 |
| floork0.75 | 936 | 1.00 |
| floork1.00 | 876 | 1.00 |
| floork1.25 | 783 | 1.00 |
| floork1.50 | 708 | 1.00 |
| floork1.75 | 678 | 1.00 |

**Lectura estructural (dato, no interpretacion):** la tasa de emparejamiento es alta
(0.97-1.00) en las 4 corridas de esta ola -- ninguna se acerca al umbral de degradacion a
1-B de D-56 (`< 0.90`). Contraste con P-05 de la Ola 1 original (tasa 0.02-0.25, ya
documentado en el handoff) o con varias corridas de OLA2 (P-09, tasas hasta 0.07 -- ver
`OLA2-reporte.md`): esta ola SI mide palancas casi-puramente-de-salida sobre S6/S7 con
`stop_and_reverse=True`, y el emparejamiento sobrevive razonablemente bien pese a eso.

---

## 6 · Rutas de artefactos

- Pre-registro: `research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-OLA1B.md`
- Manifiesto: `research/fases/F0-preparacion/03-runs/2026-08-16-ola1b.yaml`
- Resultados por corrida: `research/fases/F0-preparacion/04-resultados/OLA1B/{P02-S6,P02-S7,P03FLOOR-S6,P34-S6}/{metricas.json,posiciones.csv,alineacion.json,_brazos.txt}`
- Consolidado: `research/fases/F0-preparacion/04-resultados/OLA1B/_consolidado.{json,md}`
- Estado de la corrida: `research/fases/F0-preparacion/04-resultados/OLA1B/_ESTADO.md`
- LEDGER: 4 filas, `research/LEDGER.jsonl`, `experimento=OLA1B-palancas-de-salida`,
  `git_sha=fe6ffca` en las 4.

## 7 · Reservas heredadas del predecesor (sin resolver aqui, sin relitigar)

1. **P-15**: discrepancia de formula (§4 arriba) -- decision pendiente de Opus.
2. **P-34 × P-03-floor**: conflicto de mecanismo declarado, no medido combinado (§3 arriba,
   "Conflictos").
3. **Extension de P-34/P-03-floor a S7/ST**: fuera de alcance de esta ola por diseno (mismo
   razonamiento de alcance que P-03 en Ola 1 original); pendiente declarado si el user lo
   pide.
