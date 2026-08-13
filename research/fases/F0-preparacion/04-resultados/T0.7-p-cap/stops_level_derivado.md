# T0.7-P-CAP -- stops_level derivado de eventos de clamp (b113eb7)

INVESTIGADOR REPORT-ONLY. Sin conclusiones ni recomendaciones: numeros, rutas y conteos.

## Lineage

- run_id: `T0.7-p-cap-stops-level-20260813T192101Z`
- area: `F0`
- experimento: `T0.7-P-CAP-stops-level`
- git_sha: `be106a5ec3f1bb3363dc812d43b11185eea40989`
- engine_sha: `b113eb7`
- etapa: `F0`
- generador: `scripts/analysis/p_cap/derivar_stops_level.py`
- timestamp: `2026-08-13T19:21:01.888205+00:00`

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

