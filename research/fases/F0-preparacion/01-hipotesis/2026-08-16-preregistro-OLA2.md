# PRE-REGISTRO -- OLA2 (BLOCK B de OLA2-reporte.md)

**Escrito y COMMITEADO antes de correr un solo brazo** (charter SS10, D-58 regla 1). Rama
`equipo1`. `engine_sha` de esta ola = el commit exacto en que las tres piezas de plumbing
del BLOCK B (htf_mask en `run_supertrend`, gate de regimen en `ola1_paired`, task-type
`ola1_sizing`) quedaron verdes con la puerta de paridad en 4 passed -- ver OLA2-reporte.md
SS0 para el SHA real de la corrida, no el de este commit de pre-registro.

Ninguna grilla, regla de decision o hipotesis de este documento se toca despues de ver un
resultado (charter SS A.10). Los diseños curados de abajo (P-09 OFAT, P-15/16/17/18
convenciones de unidades) son decisiones de MI implementacion, tomadas ANTES de correr
nada y declaradas explicitamente como tales -- no del brief del controlador, que dejaba
esos detalles finales en manos del implementador.

Las palancas P-10/P-11/P-12/P-14/P-22/P-23/P-29/P-30/P-31 y la variante Awesome-Oscillator
de P-21 estan **GATED** (SS7) y NO se corren en esta ola.

---

## 0 · Que corre y por que (resumen)

| # | Palanca | sid(s) | Mecanismo | Arms | Confirmatorios | Pareado-por-entrada |
|---|---|---|---|---:|---:|---|
| (a) | P-19 | S6-K2P0, S7-TPNONE | H4 EMA filtro de tendencia | 5+5 | 4+4 | NO |
| (b) | P-28 | S6-K2P0, S7-TPNONE | H1 EMA filtro de tendencia (mismo mecanismo, H1) | 5+5 | 4+4 | NO |
| (c) | P-21 | S6-K2P0 | H1 gate de momentum | 3 | 2 | NO |
| (d) | P-20 | SuperTrend-p14x3-M15 | H4 SuperTrend gatea el flip M15 | 2 | 1 | NO |
| (e) | P-09 | S6-K2P0 | Gate compuesto de regimen k-de-4 | 13 | 12 | NO |
| (f) | P-13 | ALL (S6+S7+ST) | Kelly fraccional | 4 | 3 | SI (trivial) |
| (g) | P-15 | ALL | Descuento por correlacion | 4 | 3 | SI (trivial) |
| (h) | P-16 | ALL | Throttle por tramo de drawdown | 3 | 2 | SI (trivial) |
| (i) | P-17 | ALL | Ponderacion asimetrica de ficha | 3 | 2 | SI (trivial) |
| (j) | P-18 | ALL | Throttle por Sharpe rodante | 10 | 9 | SI (trivial) |

Total: **62 brazos** (50 confirmatorios) en **12 corridas**. (a)-(e) usan el task-type
`ola1_paired` ya existente (WP-1+2/BLOCK-1/BLOCK-2), vía plumbing nuevo de este bloque:
`htf_mask` en `run_supertrend` (commit `ea57198`) para (d), y `_regime` overlay -> harness
post-filtro para (e) (commit `8de6480`). (f)-(j) usan el task-type nuevo `ola1_sizing`
(commit `490d1bf`), arquitectura mas simple: pareado 100% trivial por construccion (misma
posicion, mismo indice, la SOLA baseline congelada T0.6), sin `entry_identity`.

---

## 1 · (a) P-19 -- H4 EMA trend filter, S6 y S7

### Hipotesis
Exigir que el M15 opere en la direccion de la pendiente de la EMA-H4 puede mejorar la
expectancy condicional (filtra entradas contra-tendencia de marco superior) o empeorarla
(P-29 en el catalogo mide, en otro mercado/TF, que el sesgo de TF superior EMPEORA el
score) -- se mide, no se asume (charter SS A.3).

### Mecanismo (engine)
`_htf: {tf_sec: 14400, field: "ema_slope", ema_period: N}` -> `backtest.build_htf_mask()`
-> `htf_mask` real, consumido por `emasar_variant.simular_variant` (WP-3 wiring, BLOCK-1,
ya verde antes de esta ola). Signo de la pendiente EMA-H4 bar-a-bar: positiva ->
long-only, negativa -> short-only.

### Grilla
`ema_period` in `{10, 15, 20, 30}` (filtro ON) + control (filtro OFF, overlay `{}`, ==
config viva). **5 arms por sid, 4 confirmatorios** (todos los `ema_period`; el control no
cuenta como confirmatorio, es la referencia). `sid` in `{S6-K2P0, S7-TPNONE}` -- **2
corridas separadas** (`P19-S6`, `P19-S7`), 10 arms totales, 8 confirmatorios.

### Regla de decision
Diferencia pareada de `net1` (brazo - control) sobre el subconjunto casado por
`entry_identity`, bootstrap por bloques de dia de servidor (B=10.000, semilla `20260816`),
IC 95% que excluye 0, BH-FDR a alfa=0.05 (lote conjunto con (b)-(e), SS "Reglas comunes").
**`tasa_emparejamiento < 0.90` degrada a 1-B (D-56)** -- se espera baja de por si: el gate
cambia el CONJUNTO de entradas, no solo la salida (catalogo: "Pareado-por-entrada: NO").
Se reporta la tasa igualmente, sin excepcion.

---

## 2 · (b) P-28 -- H1 alignment, mismo mecanismo que P-19 en H1

### Hipotesis
Identica a P-19, en el timeframe inmediatamente superior a M15 (H1 en vez de H4) --
version mas rapida/menos suave del mismo filtro.

### Mecanismo
`_htf: {tf_sec: 3600, field: "ema_slope", ema_period: N}`. Mismos periodos EMA que P-19
(instruccion del brief: "Same EMA periods as P-19").

### Grilla
`ema_period` in `{10, 15, 20, 30}` + control. **5 arms por sid, 4 confirmatorios**, `sid`
in `{S6-K2P0, S7-TPNONE}` -- corridas `P28-S6`, `P28-S7`, 10 arms, 8 confirmatorios.

### Regla de decision
Identica a P-19.

---

## 3 · (c) P-21 -- H1 momentum gate, S6 unicamente

### Hipotesis
Dos mecanismos de momentum-H1 alternativos como gate adicional de S6, sobre los gates
M15 ya existentes.

### Mecanismo y grilla
**Dos brazos unicamente** (brief SS explicito: "Two mechanisms only"), ambos ya
implementados en `higher_tf.py`:
- `momentum`: `_htf: {tf_sec: 3600, field: "momentum", momentum_lookback: 2}`.
- `emaslope`: `_htf: {tf_sec: 3600, field: "ema_slope"}` (periodo EMA default de
  `build_higher_series`, 20 -- el brief no da grilla de periodo para esta variante).

Mas control (overlay `{}`). **3 arms, 2 confirmatorios.** `sid = S6-K2P0` unicamente
(brief explicito). 🔴 **GATED explicitamente: la variante Awesome Oscillator** -- no
implementada en `higher_tf.py`, no se agrega motor para esta ola (instruccion directa
del brief, SS BLOCK B).

### Regla de decision
Identica a P-19/P-28.

---

## 4 · (d) P-20 -- H4 SuperTrend alignment antes de permitir un flip M15, brazo unico

### Hipotesis
Igual que P-19/28 pero sobre el mecanismo de SuperTrend (ST es always-in: la pregunta no
es "permitir la entrada" sino "permitir el FLIP" -- ver SS "plumbing nuevo" abajo).
🔴 **Sin grilla inventada** (instruccion explicita del brief: la fuente no da valores
numericos para este parametro): un unico arm con la configuracion VIVA de SuperTrend en
H4 (`st_atr_period=14, st_mult=3.0`), mas control. Justificacion registrada por el brief:
Ola 1's P-05 ya midio que ningun multiplicador supera a 3.0 en M15, asi que un unico valor
defendible es la eleccion honesta frente a inventar una grilla sin respaldo.

### Plumbing nuevo (commit `ea57198`, ANTES de este pre-registro)
`run_supertrend()` no aceptaba `htf_mask` -- el WP-3 wiring original (BLOCK-1) solo
alcanzaba `simular_variant` (S6/S7). Se anadio `htf_mask: list[int|None]|None=None`
(default `None` -> byte-identico, verificado por 5 tests nuevos + puerta de paridad) que
gatea el FLIP del M15 (no las entradas: ST no tiene "entradas" discretas, es always-in):
cuando el trend M15 quiere flipear en bar `j` y `htf_mask[j]` desacuerda con el nuevo
lado, el flip se SUPRIME solo para esa barra (no se enclava -- se re-evalua cada barra); un
toque de linea (`EXIT_STLINE`) jamas se ve afectado por la mascara. **Esta es la
correccion del predecessor's handoff** que decia "P-19, P-20, P-21 y P-28 corren por el
pipeline `ola1_paired` existente sin plumbing adicional" -- para P-20 eso era FALSO antes
de este commit: `run_supertrend` no tenia ningun hook de TF superior. El codigo gana
(charter SS4): se corrigio anadiendo el hook minimo, aditivo, bajo la puerta de paridad,
mismo patron que `sl_offset` (P-08, WP-1+2 Bloque 5).

### Mecanismo
`_htf: {tf_sec: 14400, field: "st_dir", st_atr_period: 14, st_mult: 3.0}` -> `htf_mask`
real -> pasado como kwarg literal a `run_supertrend(bars, ticks, **overlay)` (la
expansion `_expandir_htf_en_brazos` es agnostica de `sid`, ya funcionaba para esto sin
cambios).

### Grilla
Brazos: `default` (control, sin `_htf`) y `h4st` (con `_htf` de arriba). **2 arms, 1
confirmatorio.** `sid = SuperTrend-p14x3-M15` unicamente. Corrida `P20-ST`.

### Regla de decision
Identica a P-19/28/21. `entry_identity` para ST es `(t_in, side)` (ya existente en
`paired_harness.py`, sin cambios).

---

## 5 · (e) P-09 -- Gate compuesto de regimen k-de-4, S6 unicamente

### Hipotesis
Un gate compuesto ADX/Variance-Ratio/Efficiency-Ratio/Choppiness, exigiendo `k` de 4
criterios de "tendencial" antes de tomar una entrada de S6, puede mejorar la expectancy
condicional filtrando regimen no-tendencial -- se mide, no se asume.

### Curacion del brief (verbatim del BLOCK B)
> ADX(14) threshold {20, 25} · Variance Ratio (lag 5, window 100) threshold
> {0.95, 1.00, 1.05} · Efficiency Ratio(20) threshold {0.35, 0.50} · Choppiness(14)
> threshold {38, 61.8} · composite k-of-4 con k in {2, 3}. Doce brazos mas control.
> Racional: la literatura grada ADX y Choppiness como debiles y Variance Ratio como el
> unico con respaldo real, por eso VR recibe el conjunto de umbrales mas denso.

El brief fija los **conjuntos de valores por dimension** y el **conteo final** (doce +
control) pero no enumera los doce tuplos exactos -- esa curacion final es mia, tomada
ANTES de correr nada, siguiendo la logica explicita del brief (VR "denso" = 3 valores
frente a 2 de los demas) con un diseno **OFAT (un factor a la vez)** desde una linea base
compartida, cruzado con `k in {2,3}`:

- **Linea base por k** (el umbral MAS PERMISIVO en cada dimension, coherente entre las
  4): `adx_min=20.0` (looser), `vr_low=1.00` (frontera clasica random-walk, sin
  `vr_high` -- ver nota de direccion abajo), `er_min=0.35` (looser), `chop_max=61.8`
  (looser -- Choppiness alto=choppy, un tope alto deja pasar mas barras como
  "tendenciales").
- **Barrido de un factor a la vez** desde esa linea base: `adx_min=25.0` (1 variante);
  `vr_low in {0.95, 1.05}` (2 variantes, VR es la dimension "densa"); `er_min=0.50` (1
  variante); `chop_max=38.0` (1 variante). Total por `k`: 1 (linea base) + 1+2+1+1 (5
  variantes de 1 factor) = **6 arms**. Cruzado con `k in {2,3}`: **12 arms**. Mas
  **control** (`_regime` ausente del overlay = gate apagado del todo, == config viva de
  S6) = **13 arms, 12 confirmatorios**.
- **Direccion de VR**: solo `vr_low` se fija (nunca `vr_high`) -- Variance Ratio >1 =
  tendencial, <1 = mean-reverting (mecanismo del catalogo); para un gate que busca
  regimen TENDENCIAL, la condicion natural es "VR por encima de un umbral", no una banda
  simetrica. `vr_low` sube (0.95->1.00->1.05) hace el gate mas estricto (exige mas
  evidencia de tendencia).

### Nombres de arm y `_regime` exacto

| arm | adx_min | vr_low | er_min | chop_max | k_of_m |
|---|---:|---:|---:|---:|---:|
| k2-baseline | 20.0 | 1.00 | 0.35 | 61.8 | 2 |
| k2-adx25 | 25.0 | 1.00 | 0.35 | 61.8 | 2 |
| k2-vr095 | 20.0 | 0.95 | 0.35 | 61.8 | 2 |
| k2-vr105 | 20.0 | 1.05 | 0.35 | 61.8 | 2 |
| k2-er050 | 20.0 | 1.00 | 0.50 | 61.8 | 2 |
| k2-chop38 | 20.0 | 1.00 | 0.35 | 38.0 | 2 |
| k3-baseline | 20.0 | 1.00 | 0.35 | 61.8 | 3 |
| k3-adx25 | 25.0 | 1.00 | 0.35 | 61.8 | 3 |
| k3-vr095 | 20.0 | 0.95 | 0.35 | 61.8 | 3 |
| k3-vr105 | 20.0 | 1.05 | 0.35 | 61.8 | 3 |
| k3-er050 | 20.0 | 1.00 | 0.50 | 61.8 | 3 |
| k3-chop38 | 20.0 | 1.00 | 0.35 | 38.0 | 3 |
| control | (gate apagado, sin `_regime`) | | | | |

Los 4 periodos de las series (ADX 14, VR lag=5/ventana=100, ER 20, CHOP 14) son **FIJOS
en toda la grilla** (nunca barridos) -- solo umbrales y `k_of_m` varian, tal como pide el
brief. Computados UNA vez por corrida (`regime.compute_regime_series(bars, adx_period=14,
vr_window=100, vr_q=5, er_period=20, chop_period=14)`), no por arm.

### Plumbing nuevo (commit `8de6480`, ANTES de este pre-registro)
`_extraer_regime_de_brazos()` en `tasks_ola1.py`, mismo patron que
`_expandir_htf_en_brazos`: `_regime` (kwargs logicos de `regime.RegimeGateConfig`, sin
`enabled`) se extrae del overlay ANTES de `overlay_kwargs`/`run_ladder` (ninguno de los
dos acepta un `regime_cfg`), y se aplica DESPUES de `run_ladder` -- sobre las posiciones
de SENAL, antes de `resolve()` -- via `backtest.apply_regime_gate_by_entry_bar` (WP-5,
harness-level, `sentinel_engine` sin tocar, ya existente antes de esta ola).

### `sid` y alcance
`S6-K2P0` unicamente -- mismo alcance que P-03-floor/P-34 en OLA1B (S6 es donde vive
`ac_modulate`/el trailing por AC; el gate de regimen en el catalogo tambien nombra "S6
(gate de entrada)" como su primera mitad, la unica implementada por WP-5/BLOCK-1). La
mitad "supresion de flip" de ST queda **fuera de esta ola** (no pedida por el brief para
P-09; P-20 ya cubre el mecanismo analogo de H4-alignment sobre ST).

### Regla de decision
Identica a (a)-(d). `apply_regime_gate_by_entry_bar` puede reducir drasticamente `n`
(hasta 0 si el gate es imposible de satisfacer, como en el smoke test de
`test_ola2.py::TestOla1PairedConRegimeOverlay`) -- la tasa de emparejamiento se mide, no
se asume, y una tasa baja o `n_casadas=0` degrada automaticamente a 1-B / a
"no evaluable" (mismo criterio que `pareado.py` ya aplica).

---

## 6 · Sizing -- P-13, P-15, P-16, P-17, P-18 (task-type `ola1_sizing`)

### Diseno comun
Todas operan sobre la MISMA baseline congelada T0.6 (`posiciones_<sid>.json` para
`S6-K2P0`, `S7-TPNONE`, `SuperTrend-p14x3-M15`), pasada intacta a
`sizing.apply_sizing(baseline, cfg)`. `apply_sizing` preserva el orden/cardinalidad
ORIGINAL por `sid` (contrato de `sizing.py`, WP-4) -- el pareado es **100% trivial por
construccion**: mismo indice, misma posicion, brazo contra control, verificado con
`assert` fail-loud en `_pareado_trivial` (no se asume, se comprueba en cada corrida).
`tasa_emparejamiento = 1.0` siempre, por diseno del mecanismo (no del sustrato).

Control **compartido en las 5 corridas**: `SizingConfig()` neutra (todos los knobs en su
default `None`/vacio) -> `lot_mult=1.0` en cada posicion, byte-identico a la config viva
sin sizing (WP-4 test `test_apply_sizing_neutral_config_adds_only_lot_mult_equal_to_one`,
ya verde antes de esta ola). Arm name `neutral` en las 5 corridas.

**Unidad de la comparacion:** `net1 * lot_mult`, sumado en TODAS las posiciones de las 3
estrategias juntas (pool de cuenta) para la metrica agregada, y desglosado por `sid` en
`metricas.net_lote1_por_sid`. `net1` sigue siendo CLP por 1.0 lote (banner del
consolidado); `lot_mult` es un escalar adimensional, asi que la unidad de
`net_lote1`/`media_diff` de estas 5 corridas **sigue siendo CLP por 1.0 lote**, igual que
el resto de la ola -- no se introduce una unidad nueva.

**R1 (riesgo por posicion):** NO se computa para las 5 corridas de sizing. `sizing` no
toca la entrada ni el SL inicial de ninguna posicion (por diseno: es un multiplicador de
lote sobre posiciones YA resueltas) asi que `R1_i` de cada posicion es literalmente
identico al de la config viva -- normalizar por R aqui no aporta senal nueva sobre la que
ya aporta `net1` bruto, y el coste de recomputar R para las 3 estrategias juntas sin
alinear con `overlay` real (sizing no tiene un "overlay del motor" del que derivar SL) no
se justifica. Declarado como alcance reducido de este task-type, no como omision
accidental.

### (f) P-13 -- Kelly fraccional
`SizingConfig(kelly_mult=alpha)`. Grilla `alpha in {0.25, 0.50, 1.00}` (el brief da estos
3 valores; 1.00 = "Kelly completo", **no** es el control -- el control es `neutral`,
`kelly_mult=None` = sin ajuste por Kelly en absoluto, la config viva). **4 arms
(`neutral`, `alpha0.25`, `alpha0.50`, `alpha1.00`), 3 confirmatorios.** Corrida
`SIZING-P13`.

### (g) P-15 -- Descuento por correlacion
`SizingConfig(correlation_discount_per_extra=d)`. Grilla `d in {0.70, 0.77, 0.85}` (los 3
valores del brief). **4 arms (`neutral`, `disc0.70`, `disc0.77`, `disc0.85`), 3
confirmatorios.** Corrida `SIZING-P15`.

🔴 **Discrepancia de formula, reportada, NO relitigada** (BLOCK-A ya la documenta para
OLA1B/P-15; se repite aqui porque esta ola la EJECUTA por primera vez): la fuente
original describe `size_adjusted = base_size / sqrt(1+overlap)` con `overlap in {0.60,
0.70, 0.80}` (de donde salen los factores ~0.79/0.77/0.75, cerca pero no identicos a
`{0.70,0.77,0.85}`); `sizing.py` (WP-4) implementa en cambio
`mult *= 1 / (1 + discount * n_extra)`, un mecanismo DISTINTO (descuento multiplicativo
por CADA estrategia extra concurrente, no una funcion de una fraccion de overlap fija).
Los 3 valores `{0.70, 0.77, 0.85}` del brief se usan aqui **literalmente como el
parametro `correlation_discount_per_extra` de la formula YA IMPLEMENTADA**, no
re-derivados de una fraccion de overlap -- es la unica lectura que no exige inventar una
conversion no pedida por el brief. Queda expresamente para el memo de interpretacion
(Opus) decidir si esta sustitucion es aceptable o si P-15 necesita una implementacion de
formula nueva en una ola futura.

### (h) P-16 -- Throttle por tramo de drawdown
Dos mecanismos, cada uno UN arm (mas el continuo, que es explicitamente "la alternativa"
en el brief, no un punto de grilla adicional):
- **`ladder`**: `SizingConfig(dd_bands=[(5.0,1.0),(10.0,0.75),(15.0,0.50),(1e9,0.25)])`.
  Interpretacion de "tiers {5%,10%,15%} x reduccion {75%,50%,25%}" como una ESCALERA
  ordenada (no un cruce 3x3 -- `dd_bands` es mecanicamente una escalera, nunca puntos
  independientes): **sin drawdown, sin reduccion** (`factor=1.0` hasta 5% de DD, tier
  anadido por mi criterio de diseno porque `_dd_band_factor` aplica el primer umbral que
  cumple `dd_pct <= umbral` -- sin un primer tramo a `1.0`, CUALQUIER drawdown por
  pequeno que sea heredaria el primer factor de la lista, contradiciendo la semantica de
  "throttle" del propio nombre de la palanca); 5-10% -> 0.75; 10-15% -> 0.50; >15% ->
  0.25 (ultimo tramo, cota superior 1e9 como "infinito" practico).
- **`continuous`**: `SizingConfig(dd_continuous=(20.0, 0.25))` -- "factor = 1 - DD/20%",
  piso 25% (kwarg nuevo de este bloque, commit `816c962`).

Mas `neutral` (control). **3 arms, 2 confirmatorios.** Corrida `SIZING-P16`.

### (i) P-17 -- Ponderacion asimetrica de ficha
`SizingConfig(ficha_factors={...})`. El brief da PESOS `{(40,35,25), (33,33,33)=control,
(30,30,40)}` sobre 100 (proporcion del tamano por ficha); `ficha_factors` en `sizing.py`
es un MULTIPLICADOR relativo al tamano neutro (no una proporcion absoluta), asi que se
normalizan dividiendo por el peso equal-weight (100/3 = 33,33): `factor_Fi = peso_i * 3 /
100`.
- `(40,35,25)` -> `factor_F1=1.20, factor_F2=1.05, factor_F3=0.75` (arm `asym-front`).
- `(30,30,40)` -> `factor_F1=0.90, factor_F2=0.90, factor_F3=1.20` (arm `asym-back`).
- `(33,33,33)` == control por construccion (factor=1.0 en las 3, identico a `neutral`) --
  **no se corre como arm aparte**, es literalmente la config `neutral` compartida.

**3 arms (`neutral`, `asym-front`, `asym-back`), 2 confirmatorios.** Corrida `SIZING-P17`.
`ficha_factors` se aplica a las 3 estrategias del pool (S6/S7 tienen F1/F2/F3 reales; ST
opera siempre con `ficha="F1"` -- el factor F1 le aplica igual, F2/F3 nunca se ejercen
para ST, declarado, no oculto).

### (j) P-18 -- Throttle por Sharpe rodante
`SizingConfig(sharpe_floor=umbral, sharpe_floor_factor=reduccion)`. A diferencia de P-16
(escalera), aqui el mecanismo es un UNICO par (umbral, factor) -- no hay una nocion de
"tramos" ordenados, asi que el "x" del brief ("umbral {0.3,0.5,0.7} x reduccion
{20%,30%,50%}") se lee como **cruce cartesiano genuino**: cada combinacion es una config
standalone valida. Convencion de unidades (misma que P-16): "reduccion X%" = el
multiplicador resultante ES `X/100` (no "se reduce EN X%") -- consistente con como se
leyo P-16 arriba (75%/50%/25% son los factores finales, no reducciones-de).

`sharpe_floor in {0.3, 0.5, 0.7}` x `sharpe_floor_factor in {0.20, 0.30, 0.50}` = **9
combinaciones**, arm `sh<T>-r<R>` (p.ej. `sh0.3-r20`). Mas `neutral`. **10 arms, 9
confirmatorios.** Corrida `SIZING-P18`.

### Regla de decision (comun a f-j)
Diferencia pareada de `net1*lot_mult` (brazo - control) sobre TODAS las posiciones (pool
de las 3 estrategias, pareado trivial 1:1 por indice), bootstrap por bloques de dia de
servidor (B=10.000, semilla `20260816`), IC 95% que excluye 0, BH-FDR a alfa=0.05 (lote
separado de (a)-(e), ver SS "Reglas comunes"). `tasa_emparejamiento` siempre 1.0 -- no
hay degradacion a 1-B posible por diseno del mecanismo (nunca cambia que posiciones
existen).

---

## 7 · GATED -- NO se implementan ni se corren en esta ola

Cada una con su pieza faltante exacta (ninguna existe hoy en el motor/harness):

| # | Palanca | Pieza faltante |
|---|---|---|
| P-10 | Regimen por HMM (2-4 estados) | Requiere dependencia externa (`hmmlearn`/equiv.) y entrenamiento de modelo estadistico -- ningun codigo existe |
| P-11 | Regimen por exponente de Hurst (R/S corregido por sesgo) | Requiere estimador Anis & Lloyd corregido por sesgo -- ningun codigo existe; el R/S ingenuo esta explicitamente desaconsejado por la propia fuente academica |
| P-12 | Marcador de volatilidad GARCH(1,1) | Requiere ajuste GARCH en ventana rodante, dependencia estadistica -- ningun codigo existe |
| P-14 | Sizing inverso a ATR14 (`atr_target`) | **Cuarentena explicita del plan** ("AL FINAL del programa... no ejecutar antes sin enmienda", D-52/catalogo) -- el hook (`atr_target`/`atr_fn`) YA EXISTE en `sizing.py` (WP-4) pero esta ola NO lo activa por mandato del brief, no por falta de codigo |
| P-22 | Overlay de deteccion de "momentum crash" (H4) | Requiere un indice compuesto (spike ATR-H4 + divergencia de momentum) -- ningun codigo existe, aunque el feed H4 subyacente (`higher_tf.py`) si existe |
| P-23 | Regimen de "opening range" (dia tendencia vs. rango) | Requiere confirmacion multi-TF por cierre de vela en TF distinto de la barra de origen -- ningun codigo existe |
| P-29 | Precondicion de barrido de liquidez antes de honrar breakout/tendencia | Requiere deteccion de swing/pivote determinista + regla "mecha-supera-y-cierra-dentro" -- ningun codigo existe |
| P-30 | Trailing-stop estructural por trendline sin interseccion | Requiere algoritmo de busqueda combinatoria sobre pivotes -- ningun codigo existe (el mas caro de implementar del catalogo, marcado HIGH effort) |
| P-31 | Filtro de regimen VWAP-3-condiciones | Requiere computo de VWAP anclado (sesion/dia) -- ningun codigo existe |
| P-21 (parcial) | Variante Awesome Oscillator del gate de momentum H1 | No implementada en `higher_tf.py` -- **instruccion explicita del brief de NO anadirla** en esta ola |

---

## 8 · Reglas comunes a (a)-(j)

- Sustrato: pre-holdout Capitaria, `substrate_id=capitaria-ticks-2026-preholdout` para
  (a)-(e) (`ola1_paired`, sin recorte D-60 -- ninguna de estas palancas usa
  `max_hold_bars`, asi que no hay riesgo de tocar el holdout por esa via; `verificar_holdout`
  sigue corriendo igual, fail-loud); `substrate_id=t06-baseline-frozen-golden` para (f)-(j)
  (`ola1_sizing`, la baseline YA congelada de T0.6, pre-holdout por construccion).
- El brazo de control de CADA corrida `ola1_paired` debe reproducir la linea base
  congelada T0.6 (`verificar_control_contra_linea_base`) -- fail-loud, la corrida entera
  es invalida si no. Las corridas `ola1_sizing` verifican en cambio que `apply_sizing`
  preserva orden/cardinalidad (`SizingBaselineDivergedError`, fail-loud).
- **BH-FDR en DOS lotes separados** (mismo criterio que OLA1B SS4): lote
  "htf/regimen" = las 50 comparaciones confirmatorias de (a)-(e) (8+8+2+1+12+... nota:
  ver conteo exacto en SS0, 31 confirmatorios de (a)-(e)); lote "sizing" = las 19
  comparaciones confirmatorias de (f)-(j). Ninguno se mezcla con el lote de OLA1/OLA1B ya
  consolidado (`48fe8d5`/`517aa63`/`69bad91`).
- `estado_investigacion`: `piloto-instrumento` (D-57 sigue vigente -- el motor no esta
  congelado formalmente). Todo artefacto nace PRE-INTERPRETACION (D-58 regla 4): ningun
  numero de este lote es veredicto.
- **Runner:** `python -m scripts.research.runner.runner <manifiesto> --on-error continue
  --workers N`, foreground, con `python -m scripts.research.runner.progress <dir>` entre
  llamadas. Manifiesto:
  `research/fases/F0-preparacion/03-runs/2026-08-16-ola2.yaml`, generado por
  `python -m scripts.research.ola1.manifiesto_ola2` (nuevo script, grillas HARDCODEADAS
  de este documento, mismo patron que `manifiesto_ola1b.py`).
- **Ledger:** filas nuevas en `research/LEDGER.jsonl` con el `git_sha` REAL de la corrida
  (no el de este commit de pre-registro).
- R1-bis (charter SS A.11) sigue intacto: ningun cambio de este bloque toca
  `sentinel_engine/strategies/live_configs_20.py`; los tres cambios de motor
  (`run_supertrend.htf_mask`, `_extraer_regime_de_brazos`, `sizing.dd_continuous`) son
  aditivos, off-by-default, verificados bajo la puerta de paridad tras cada uno (SS0).
