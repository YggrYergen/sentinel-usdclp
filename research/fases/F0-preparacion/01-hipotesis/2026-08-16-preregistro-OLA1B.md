# PRE-REGISTRO -- OLA1B (BLOCK-3 de OLA1B-reporte.md)

**Escrito y COMMITEADO antes de correr un solo brazo** (charter SS10, D-58 regla 1). Rama
`equipo1`. `engine_sha` de esta ola = el commit exacto en que BLOCK-1/BLOCK-2 quedaron
verdes con la puerta de paridad en 4 passed (ver OLA1B-reporte.md SS0 para el SHA real
de la corrida, no el de este commit de pre-registro).

Ninguna grilla, regla de decision o hipotesis de este documento se toca despues de ver un
resultado (charter SS A.10). Las tres piezas de abajo son independientes entre si y se
reportan por separado; ninguna revierte ni rescata a otra.

---

## 0 · Que corre y por que (resumen)

| # | Palanca | Que mide | Sustrato | `sid` | Clase |
|---|---|---|---|---|---|
| (a) | P-02 (re-corrida) | igual que 1c7279d, sobre el sustrato RECORTADO de D-60 | recortado (D-60) | S6-K2P0, S7-TPNONE | 1-A |
| (b) | P-03-floor (NUEVO) | `ac_modulate_floor_relief_k` x `ac_decel_umbral` | pre-holdout completo | S6-K2P0 | 1-A |
| (c) | P-34 (NUEVO) | `trail_atr_floor_k`, barrido completo con control=2.0 en la grilla | pre-holdout completo | S6-K2P0 | 1-A |

(a) no es una hipotesis nueva -- es la MISMA grilla y las MISMAS reglas de decision del
pre-registro `1c7279d` (P-02), re-corrida sobre el sustrato que D-60 exige para que no
choque con el borde del holdout. No se re-litiga aqui: se documenta que el sustrato
cambia y por que (SS1).

(b) y (c) son las dos hipotesis nuevas de este bloque, derivadas directamente de la
medicion cerrada de DIAG-P03 (`research/fases/F0-preparacion/02-specs/DIAG-P03-reporte.md`,
commit `7c4ea92`): el piso ATR (`trail_atr_floor_k=2.0`, minimo medido 8.67) domina al
trail modulado por AC (maximo posible en la grilla, 1.00) en el **100% de las 8.321
barras** con ATR14 valido -- la razon mecanica exacta por la que los 95 brazos de P-03
dieron el mismo numero.

---

## 1 · (a) P-02 re-corrida -- sustrato recortado (D-60), grilla sin cambios

**Grilla** (identica a `1c7279d` / `manifiesto._grid_p02`, sin tocar):
`max_hold_bars` in `{None(=default), 4, 6, 8, 10, 12, 15, 20, 25, 30, 40, 48, 56, 64, 80,
96, 128}` -- 17 brazos por `sid`, 7 confirmatorios cada uno (`{None,10,15,20,30,48,64}`).
`sid` in `{S6-K2P0, S7-TPNONE}` -- 34 brazos totales, 14 confirmatorios.

**Cambio, y SOLO este cambio:** el sustrato de ESTAS DOS corridas usa
`sustrato.cargar_barras(margen_extra_s=sustrato.MARGEN_P02_S)` en vez de
`cargar_barras()` -- recorta el pre-holdout en `(128+1)*900 = 116.100 s` adicionales
(D-60), aplicado **por igual al control y a los 17 brazos**, en ambos `sid`. Verificado
por codigo (`tests/research/test_ola1.py::test_margen_p02_ningun_max_hold_bars...`) que
ningun valor de la grilla puede producir un `t_exit >= HOLDOUT_INI`.

**Consecuencia declarada de antemano (D-60):** `n` de P-02 sera MENOR que el de
P-03-floor/P-34/P-05/P-08 -- distinto sustrato, comparacion valida solo DENTRO de P-02
(pareada, intra-palanca). Se cita el `n` recortado en cada tabla, nunca el de la linea
base sin recortar.

**Regla de decision:** identica a `1c7279d` -- diferencia pareada de `net1` por posicion
(brazo - control) sobre el subconjunto casado por identidad de entrada, bootstrap por
bloques de dia de servidor (B=10.000, semilla `20260816`), IC 95% que excluye 0, BH-FDR a
alfa=0.05 sobre los confirmatorios y sobre el total. Si `tasa_emparejamiento < 0.90`,
degrada a 1-B (D-56) y se declara asi.

**Secundaria:** `secundaria_p02` (poda de perdedoras vs. amputacion de ganadoras),
identica a antes.

---

## 2 · (b) P-03-floor -- NUEVO: `ac_modulate_floor_relief_k` x `ac_decel_umbral`

### Hipotesis

DIAG-P03 midio que el piso ATR absorbe el 100% del apriete de AC-modulate bajo los
kwargs vivos de S6-K2P0. `ac_modulate_floor_relief_k` (BLOCK-2, este task) deja que el
trail modulado por AC gane sobre el piso, SOLO durante una ventana de apriete activo.
Hipotesis: activar el relief (bajar `relief_k` de 1.0 hacia 0.0) cambia el neto pareado
respecto del control (relief=1.0, comportamiento de hoy) -- de signo no predicho a
priori (podria mejorar o empeorar; P-08 midio que ensanchar el stop de ST cuesta dinero
casi linealmente, lo que sugiere -pero no implica para S6- que ESTRECHAR el trail podria
ayudar. Se mide, no se asume, charter SS A.3).

### Grilla (factorial completo, TODOS confirmatorios -- grilla pequena y deliberada)

`ac_modulate_floor_relief_k` in `{1.00, 0.75, 0.50, 0.25, 0.00}` (5 valores; 1.00 = hoy,
0.00 = bypass total del piso durante el apriete).

`ac_decel_umbral_pips` in `{0, 25, 50, 75}` (4 valores; 0 = el default VIVO de S6-K2P0 --
`ac_decel_umbral=0.0` en unidades AC, cualquier desaceleracion dispara; 25/50/75 = el
subconjunto confirmatorio de umbrales de P-03 en `1c7279d`). Conversion identica a E-04
SS2.1: `ac_decel_umbral = umbral_pips * 0.01` (pip_size XAUUSD).

`ac_decel_lookback=1`, `ac_modulate_hold_bars=1` FIJOS en ambos (los defaults vivos) --
no se re-barren aqui: el objetivo de esta grilla es aislar el efecto del relief del piso,
no repetir el barrido de lookback/hold que ya corrio (sin efecto observable, por la
misma razon mecanica) en la Ola 1 original. Pendiente declarado: cruzar relief_k con
lookback/hold es un refinamiento posible de una ola futura, no de esta.

5 x 4 = **20 brazos**, TODOS confirmatorios. Brazo control = `relief1.00-u0`
(`ac_modulate_floor_relief_k=1.0, ac_decel_umbral=0.0`) -- byte-identico a la config viva
de S6-K2P0 (== el brazo `default` de P-03 en `1c7279d`, verificable por construccion:
`ac_modulate_floor_relief_k=1.0` es un no-op garantizado por el guard de
`emasar_variant.py`).

`sid = S6-K2P0` unicamente (mismo alcance que P-03 en la Ola 1 original: DIAG-P03 SS7 lo
declara explicito, "P-03 en Ola 1 solo corre sobre S6-K2P0"; no se extiende a S7 ni a ST
sin decision aparte -- `trail_atr_floor_k`/`ac_modulate` no son parte de la config viva
de S7-TPNONE en absoluto, ver `live_configs_20.py`).

**Coordinador (clarificacion recibida durante la ejecucion de este bloque):** "off by
default" protege la paridad y a las demas palancas -- NO es licencia para dejar el
parametro sin medir. Este pre-registro cumple: control (relief=1.0) y variante
(relief<1.0) corren en la MISMA llamada pareada (`run_paired_arms`/`ola1_paired`, brazo
`brazo_control="relief1.00-u0"`), y se reportan lado a lado (BLOCK-4).

**Regla de decision:** identica en forma a P-02/P-03/P-08 de `1c7279d` -- diferencia
pareada de `net1` (brazo - control) sobre el subconjunto casado, bootstrap por bloques de
dia de servidor (B=10.000, semilla `20260816`), IC 95% que excluye 0, BH-FDR a alfa=0.05
sobre los 20 (todos confirmatorios). `tasa_emparejamiento < 0.90` degrada a 1-B (D-56).

**Secundaria:** ninguna nueva -- se reutiliza `secundaria_p03` (coste de whipsaw/reflip)
sobre cada brazo, mismo criterio (ventana 2700 s = 3 barras M15).

---

## 3 · (c) P-34 -- NUEVO LEVER: barrido de `trail_atr_floor_k`

**Identificador:** siguiente libre despues de P-33 (catalogo
`05-analisis/2026-08-15-catalogo-palancas-y-requisitos-motor.md`, 33 palancas
P-01..P-33) = **P-34**. Entrada de catalogo completa en OLA1B-reporte.md SS-catalogo
(NO se edita el fichero del catalogo -- es artefacto del controlador).

### Hipotesis

`trail_atr_floor_k` gobierna la distancia de trailing de S6 el **100% del tiempo**
(DIAG-P03 SS5.4: domina al trail sin modular y al modulado en 8.321/8.321 barras) y
**nunca se ha barrido** -- su valor vivo (2.0, piso minimo medido 8.67) fue elegido sin
grilla. P-08 midio, sobre SuperTrend, que ensanchar el stop cuesta dinero casi
linealmente (−3.090/−7.347/−10.666/−15.047 USD en offsets 0.05/0.10/0.15/0.20, D-56,
`517aa63`) -- evidencia (no transferible directamente por R1-bis/mezcla de estrategias,
pero SI un prior razonable a explorar) de que un piso ancho puede ser la fuente del
problema tambien en S6. Se mide, no se asume.

### Grilla

`trail_atr_floor_k` in `{2.00 (control/vivo), 1.75, 1.50, 1.25, 1.00, 0.75, 0.50, 0.25,
0.00 (piso desactivado)}` -- **9 valores**, TODOS confirmatorios (grilla pequena y
deliberada; cubre "bien por debajo de 2.0" como pide el brief, e incluye el control
explicitamente en la grilla, clarificacion del coordinador SS1). `ac_modulate_floor_relief_k`
NO se toca aqui (queda en su default 1.0 = sin relief) -- esta grilla aisla el efecto del
piso SIEMPRE-ACTIVO, ortogonal a (b) que aisla el efecto del piso SOLO-DURANTE-el-apriete.
Las dos grillas son independientes: ninguna presupone el resultado de la otra
(no-aditividad, D-58 regla 5).

`sid = S6-K2P0` unicamente -- mismo razonamiento de alcance que (b): `trail_atr_floor_k`
no forma parte de la config viva de S7-TPNONE (`live_configs_20.py`), y extenderlo ahi
es una decision de diseno fuera de este pre-registro (pendiente declarado si el user lo
pide).

**Metrica/criterio:** diferencia pareada de `net1` (brazo - control=2.0) sobre el
subconjunto casado, bootstrap por bloques de dia de servidor (B=10.000, semilla
`20260816`), IC 95% que excluye 0, BH-FDR a alfa=0.05 sobre los 9 (todos
confirmatorios, incluye el control como brazo con diferencia identicamente 0 -- no entra
al conteo de comparaciones, ver BLOCK-4).

**Pareado-por-entrada:** SI, sujeto a verificacion (D-56) -- `trail_atr_floor_k` es una
palanca de SALIDA pura (afecta solo la distancia del trailing, nunca el gate de
entrada), asi que en ausencia de `stop_and_reverse` cambiando el conjunto de entradas
posteriores se espera tasa alta; se MIDE, no se asume (mismo caveat que P-02/P-03/P-08
en D-56: S6 corre con `stop_and_reverse=True`, una salida distinta puede generar una
entrada distinta aguas abajo).

**Conflictos:** con (b) -- ambas tocan el mismo `max(...)` de `trail_efectivo` en
`emasar_variant.py:1050-1058`, por rutas distintas (piso base vs. piso durante el
apriete). No se corren combinadas en esta ola (grillas ortogonales, ver arriba); una
grilla cruzada relief_k x floor_k queda como pendiente declarado de una ola futura si
(b) y/o (c) muestran senal.

**Secundaria:** ninguna dedicada. `n_por_reason` (ya en `metricas_de_brazo`) sirve de
descriptor de que salida domina en cada celda (EXIT_TRAIL vs EXIT_INITSL vs otras).

---

## 4 · Reglas comunes a (a)+(b)+(c)

- Sustrato: pre-holdout Capitaria, `substrate_id=capitaria-ticks-2026-preholdout`, SALVO
  (a) que usa el recorte de D-60 (SS1). Holdout excluido siempre (`sustrato.verificar_holdout`,
  fail-loud).
- El brazo de control de CADA corrida debe reproducir la linea base congelada T0.6 (o su
  prefijo recortado para (a), `verificar_control_contra_linea_base_recortada`) --
  fail-loud, la corrida entera es invalida si no.
- BH-FDR: (b) y (c) se corrigen JUNTAS como un solo lote de 29 comparaciones (20+9,
  todas confirmatorias) al consolidar (BLOCK-4), separado del lote de (a) (34
  comparaciones, sustrato distinto) y separado del lote de Ola 1 original (`1c7279d`,
  ya corrido y consolidado en `48fe8d5`/`517aa63`) -- no se re-mezclan lotes de corridas
  distintas salvo que el user pida una correccion global unica.
- `estado_investigacion`: `piloto-instrumento` (D-57 sigue vigente -- el motor no esta
  congelado formalmente). Todo artefacto nace PRE-INTERPRETACION (D-58 regla 4):
  ningun numero de este lote es veredicto.
- **Runner:** `python -m scripts.research.runner.runner <manifiesto> --on-error continue
  --workers N`, foreground, con `python -m scripts.research.runner.progress <dir>` entre
  llamadas (brief SS3). Manifiesto: `research/fases/F0-preparacion/03-runs/2026-08-16-ola1b.yaml`,
  generado por `python -m scripts.research.ola1.manifiesto_ola1b` (nuevo script, grillas
  HARDCODEADAS de este documento, mismo patron que `manifiesto.py`).
- **Ledger:** filas nuevas en `research/LEDGER.jsonl` con el `git_sha` REAL de la corrida
  (no el de este commit de pre-registro).
