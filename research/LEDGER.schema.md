# LEDGER — esquema

`research/LEDGER.jsonl` — **append-only**, un objeto JSON por línea, una línea por experimento
o artefacto de datos relevante. Nunca se edita una línea existente.

## Campos obligatorios

| Campo | Tipo | Descripción |
|---|---|---|
| `run_id` | string | Identificador único. Formato `<FASE>-<AREA><n>-<seq>`, p. ej. `GR-B1-0007` |
| `timestamp` | string | ISO 8601, **hora de servidor del bróker (UTC−4)**. Nunca convertir zonas |
| `etapa` | string | `F0` · `A0` · `S0` · `GR` · `LBT` · `E` · `HO` |
| `area` | string | Familia del catálogo: `A`…`H`, `LS`, o `INFRA` |
| `experimento` | string | ID del pre-registro correspondiente |
| `hipotesis_ref` | string | Ruta al pre-registro (`fases/<ID>/01-hipotesis/<exp>.md`) |
| `substrate_id` | string | Vocabulario controlado — ver `protocolos/04`, parte 3 |
| `engine_sha` | string | SHA del motor congelado bajo el que corrió |
| `git_sha` | string | SHA del repo al momento de correr |
| `config_hash` | string | Hash de la configuración exacta |
| `generador` | string | `runner:<script>` · `agent:<modelo>-<rol>` · `human` |
| `artefactos` | array | Rutas de los ficheros producidos |
| `estado` | string | `ok` · `abortado` · `superseded` |

## Campos opcionales

| Campo | Cuándo |
|---|---|
| `supersedes` | `run_id` al que reemplaza (correcciones — nunca se edita el original) |
| `reason` | Por qué reemplaza / por qué abortó |
| `notas` | Hechos objetivos. 🔴 **Nunca conclusiones ni interpretación** |
| `metricas` | Objeto con las métricas principales, para búsqueda rápida |

## Ejemplo

```json
{"run_id":"F0-INFRA-0001","timestamp":"2026-08-10T05:03:00","etapa":"F0","area":"INFRA","experimento":"T0.11a-descarga-transcripciones","hipotesis_ref":"n/a","substrate_id":"n/a","engine_sha":"n/a","git_sha":"41fdb25","config_hash":"n/a","generador":"agent:fable5-controller","artefactos":["data/literature/youtube_transcripts/"],"estado":"ok","metricas":{"videos":28,"tokens_totales":233723},"notas":"28/28 descargados. Ninguna transcripcion leida."}
```

## Reglas

1. Se escribe **al terminar** el experimento, preferentemente por el runner (protocolo 06).
2. Ninguna línea sin `substrate_id`. Ningún veredicto sobre `bars-*` o `pre-repair`.
3. Para corregir: nueva línea con `supersedes` + `reason`. **Jamás** editar ni borrar.
4. `notas` es para hechos. La interpretación vive en `fases/<ID>/05-analisis/`.
