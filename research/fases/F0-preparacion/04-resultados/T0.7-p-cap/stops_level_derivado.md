# T0.7-P-CAP -- stops_level derivado de eventos de clamp (b113eb7)

INVESTIGADOR REPORT-ONLY. Sin conclusiones ni recomendaciones: numeros, rutas y conteos.

## Lineage

- run_id: `T0.7-p-cap-stops-level-20260813T193202Z`
- area: `F0`
- experimento: `T0.7-P-CAP-stops-level`
- git_sha: `6cb394965fe0f3984d830aba66f34edfa062b50a`
- engine_sha: `b113eb7`
- etapa: `F0`
- generador: `scripts/analysis/p_cap/derivar_stops_level.py`
- timestamp: `2026-08-13T19:32:02.881005+00:00`

## Fuentes

- eventos_csv: `data/analysis/p_cap/eventos_ejecutor_902.csv`
- sl_clamped_open_json: `data/analysis/p_cap/sl_clamped_open_events.json`
- verdad_terreno_csv: `data/analysis/p_cap/verdad_terreno_902.csv`

## Cuadre contra la fuente secundaria (87 eventos SL_CLAMPED OPEN)

- n en JSON: 87
- n en CSV (event=SL_CLAMPED OPEN): 87
- coincide: True

## Familia `SL_CLAMPED OPEN`

- n eventos: 87
- n usables (ref y clamped presentes): 0
- n descartados: 87
  - ref_ausente: 87
- side emparejado: 85 / no emparejado: 2

### Distribucion de `level_i`

Sin eventos usables -- no hay `level_i` que reportar.

### Desglose por side

(sin eventos con side emparejado y usable)

### Desglose por config

(sin eventos con config y usable)

### Verificacion de signo

- ok: 0 · fail: 0

### Verificacion de necesidad

- ok: 0 · fail: 0 · no evaluable (sin desired_sl): 0

## Familia `SL_CLAMPED`

- n eventos: 35
- n usables (ref y clamped presentes): 0
- n descartados: 35
  - ref_ausente: 35
- side emparejado: 33 / no emparejado: 2

### Distribucion de `level_i`

Sin eventos usables -- no hay `level_i` que reportar.

### Desglose por side

(sin eventos con side emparejado y usable)

### Desglose por config

(sin eventos con config y usable)

### Verificacion de signo

- ok: 0 · fail: 0

### Verificacion de necesidad

- ok: 0 · fail: 0 · no evaluable (sin desired_sl): 0

## Familia `TOTAL`

- n eventos: 122
- n usables (ref y clamped presentes): 0
- n descartados: 122
  - ref_ausente: 122
- side emparejado: n/a / no emparejado: n/a

### Distribucion de `level_i`

Sin eventos usables -- no hay `level_i` que reportar.

### Desglose por side

(sin eventos con side emparejado y usable)

### Desglose por config

(sin eventos con config y usable)

### Verificacion de signo

- ok: 0 · fail: 0

### Verificacion de necesidad

- ok: 0 · fail: 0 · no evaluable (sin desired_sl): 0


## Via ticks (ronda de correccion 1 -- inversion contra ticks reales)

- fuente de ticks: data/lake_ticks/XAUUSD/<YYYYMM>.parquet (t_msc, bid, ask), leido directamente con pandas.read_parquet en TickWindowLoader (reimplementacion propia, no reutiliza scripts/analysis/realtick_bt/backtest.py:Ticks).
- rejilla de L: [0.0, 2.0], paso 0.01

### Familia `SL_CLAMPED OPEN`

### Ventana +/-0.25s

- eventos fuente: 87
- sin side emparejado: 2
- sin ticks en la ventana: 9
- evaluables: 76

- max_n consistentes: 34 de 76 (fraccion: 0.44737)
- L ganador unico: 0.50
- L empatados en el maximo: ['0.50']

Top-5 puntos de la curva (L, n_consistentes):

| L | n_consistentes |
|---|---|
| 0.50 | 34 |
| 0.51 | 24 |
| 0.52 | 24 |
| 0.48 | 22 |
| 0.49 | 22 |

Curva completa `L -> n_consistentes` (rejilla 0.00-2.00, paso 0.01): ver capa maquina (`stops_level_derivado.json`, `via_ticks.'SL_CLAMPED OPEN'.ventanas['0.25'].curva`).

### Ventana +/-1.0s

- eventos fuente: 87
- sin side emparejado: 2
- sin ticks en la ventana: 0
- evaluables: 85

- max_n consistentes: 83 de 85 (fraccion: 0.97647)
- L ganador unico: 0.50
- L empatados en el maximo: ['0.50']

Top-5 puntos de la curva (L, n_consistentes):

| L | n_consistentes |
|---|---|
| 0.50 | 83 |
| 0.49 | 72 |
| 0.48 | 71 |
| 0.51 | 70 |
| 0.47 | 66 |

Curva completa `L -> n_consistentes` (rejilla 0.00-2.00, paso 0.01): ver capa maquina (`stops_level_derivado.json`, `via_ticks.'SL_CLAMPED OPEN'.ventanas['1.00'].curva`).

### Ventana +/-3.0s

- eventos fuente: 87
- sin side emparejado: 2
- sin ticks en la ventana: 0
- evaluables: 85

- max_n consistentes: 85 de 85 (fraccion: 1.00000)
- L ganador unico: 0.50
- L empatados en el maximo: ['0.50']

Top-5 puntos de la curva (L, n_consistentes):

| L | n_consistentes |
|---|---|
| 0.50 | 85 |
| 0.48 | 84 |
| 0.49 | 84 |
| 0.47 | 82 |
| 0.51 | 82 |

Curva completa `L -> n_consistentes` (rejilla 0.00-2.00, paso 0.01): ver capa maquina (`stops_level_derivado.json`, `via_ticks.'SL_CLAMPED OPEN'.ventanas['3.00'].curva`).

### Familia `SL_CLAMPED`

### Ventana +/-1.0s

- eventos fuente: 35
- sin side emparejado: 2
- sin ticks en la ventana: 2
- evaluables: 31
- nota de resolucion: epoch entero, sin ms (menor resolucion temporal que la familia SL_CLAMPED OPEN); ventana minima declarada +/-1s, sin barrido de sensibilidad adicional.

- max_n consistentes: 27 de 31 (fraccion: 0.87097)
- L ganador unico: 0.50
- L empatados en el maximo: ['0.50']

Top-5 puntos de la curva (L, n_consistentes):

| L | n_consistentes |
|---|---|
| 0.50 | 27 |
| 0.48 | 20 |
| 0.49 | 20 |
| 0.51 | 18 |
| 0.52 | 16 |

Curva completa `L -> n_consistentes` (rejilla 0.00-2.00, paso 0.01): ver capa maquina (`stops_level_derivado.json`, `via_ticks.'SL_CLAMPED'.ventanas['1.00'].curva`).

