# PROTOCOLO 06 — RUNNERS: LA EJECUCIÓN NO LA HACE UN LLM

> **Principio (decisión D-15 del user):** donde un script Python pueda ejecutar el trabajo, el
> script lo ejecuta. El LLM planifica e interpreta; no corre colas.
>
> **Por qué:** un subagente que "corre un backtest, mira el resultado, corre el siguiente" es
> caro en tokens, lento, y —lo grave— introduce tres modos de fallo que un script no tiene:
> alucinar un número que no leyó bien, interpretar sin que se le pida, y simplificar la cola
> cuando se hace larga. Un runner no se cansa ni se convence a sí mismo.

---

## Separación de planos

| Plano | Quién | Qué hace |
|---|---|---|
| **Razonamiento** | LLM (Opus diseña, Sonnet implementa) | Escribe el manifiesto, lee el registro consolidado, interpreta |
| **Ejecución** | Runner Python | Corre la cola, escribe artefactos con tags, actualiza el LEDGER |

El LLM **nunca** ve la salida cruda de cada corrida individual: ve el **registro consolidado**
que el runner produjo. Menos tokens, cero alucinación en la capa de ejecución.

## Manifiesto de corridas (declarativo)

Cada bloque de experimentos se describe en un manifiesto en `fases/<ID>/03-runs/`, no en prosa:

```yaml
# fases/GR-grillas/03-runs/B1-breakeven.yaml
experimento: B1-be-grid
area: B
hipotesis: 01-hipotesis/B1-breakeven.md      # pre-registro OBLIGATORIO, escrito ANTES
substrate_id: capitaria-ticks-2026H1
engine_sha: <sha del motor congelado>
paralelismo: 4                                # procesos, no agentes
modo: paired                                  # harness pareado: K salidas sobre 1 stream de entradas
base:
  estrategia: S6-K2P0-copia                   # SIEMPRE copia (R1-bis)
  lote: 0.10
grilla:
  be_at_r:   [off, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
  be_offset: [0.5, 2, 5]
salidas:
  resultados: 04-resultados/B1-be-grid/
  ledger: append
```

## Requisitos que todo runner debe cumplir

1. **Idempotente**: re-ejecutar no duplica ni corrompe; las corridas ya completas se saltan.
2. **Reanudable**: si se corta (o se corta la sesión), continúa donde quedó.
3. **Etiquetador**: escribe los tags de lineage (protocolo 04, parte 3) en cada artefacto.
4. **Append-only al LEDGER**: una línea por corrida, al terminarla.
5. **Registro consolidado**: emite un único fichero resumen que el LLM leerá.
6. **Fail-loud**: ante anomalía (dato faltante, assert violado, config inválida) **aborta y lo
   reporta**; jamás continúa en silencio ni rellena con un valor por defecto.
7. **Sin decisiones**: un runner ejecuta lo que dice el manifiesto. No elige, no poda, no ajusta.

## Qué se automatiza (lista viva)

- Colas de backtests (paralelas y secuenciales) sobre grillas declaradas
- Regeneración de sustratos y artefactos derivados
- Descargas e ingesta de datos, con validación de integridad
- Conteos, agregaciones y estadística descriptiva
- Cálculo de los tests de la puerta estadística (bootstrap, DSR, FDR)
- Escritura y validación del LEDGER

## Qué NO se automatiza

- El diseño de la grilla y la hipótesis (Opus, y se pre-registra ANTES de correr)
- La interpretación de los resultados (Opus, memo aparte)
- La decisión de promover, descartar o enmendar (user + Opus)

## Nota de disciplina operativa

Los procesos lanzados desde una herramienta de agente **no sobreviven** al fin de sesión. Las
colas largas se lanzan de forma que persistan (el user las arranca, o quedan bajo supervisión
durable). Lo mismo aplica a la ingesta continua de ticks: es un activo del programa —el histórico
de Capitaria solo crece hacia adelante y lo que no se captura se pierde— y por tanto necesita
supervisión durable, no un proceso ad-hoc de sesión.
