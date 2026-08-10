# FASE F0 — PREPARACIÓN

> **Fase actual.** Bloqueante: ninguna tarea de investigación puede correr antes de que esta fase
> cierre. Aquí no se produce ningún resultado de trading — aquí se compra la **validez** de todo
> lo que vendrá después.

## Objetivo

Dejar el programa en condiciones de producir evidencia confiable: datos real-tick suficientes,
un motor cuya fidelidad contra el mercado real esté **medida** (no supuesta) y congelado, un
sistema de trabajo que no derive a lo largo de decenas de sesiones, y el holdout sellado antes
de que nadie mire nada.

## Gate de entrada

Ninguno — es la primera fase. Requiere el plan v4 cerrado y firmado por el user.

## Entradas

- Plan maestro: `docs/superpowers/plans/2026-08-10-plan-investigacion-integral-v4.md`
- Decisiones del user: `research/DECISIONES.md`
- Sustrato existente: ticks Capitaria 2026-01→07 (52,6M), sustrato reparado de 7 meses
- Historial live de la cuenta 902 (solo lectura, vía `MT5_Tester_2`)
- Transcripciones descargadas: `data/literature/youtube_transcripts/` (28 videos, ~233.723 tokens)

## Salidas (esto es lo que se verifica al cerrar)

| Salida | Ruta / artefacto |
|---|---|
| Ticks AVA 2–4 años, validados | `data/lake_ticks_ava/XAUUSD/` + fila en LEDGER |
| Ticks Capitaria al día (ventana 902 completa) | `data/lake_ticks/XAUUSD/` |
| Historial 902 exportado | `data/live_history/902/` |
| 12 modificaciones de motor implementadas y testeadas | `sentinel_engine/**` (sobre copias) + tests |
| **A6 — fidelidad medida y firmada** | `04-resultados/A6/` + memo en `05-analisis/A6-veredicto.md` |
| Motor congelado | SHA registrado en `research/TRACKER.md` |
| Research OS operativo (runners + ledger) | `research/**` + `scripts/research/**` |
| Literatura formal, 7 áreas | `05-analisis/literatura-<area>.md` |
| Literatura informal analizada | `04-resultados/videos/` + `05-analisis/videos-*.md` |
| Holdout sellado | Constancia fechada en `research/DECISIONES.md` (D-01) |
| Modelo de la hora muerta desplazante | `04-resultados/hora-muerta/` |

## Criterio de cierre (verificable)

- [ ] T0.2 … T0.13 en `[x]` **verificado** en el TRACKER (artefacto + ledger + evidencia)
- [ ] **A6 en verde y firmada por Opus**: señal bit-idéntica; neto ≤0,3 % (99,7 %) o mejor
- [ ] Motor congelado, SHA escrito en el TRACKER
- [ ] Holdout sellado, con las fechas exactas registradas en `DECISIONES.md`
- [ ] Revisión de código batcheada de la fase (`superpowers:requesting-code-review`)
- [ ] Memo de análisis de la fase escrito (Opus)
- [ ] Backlog de la fase revisado: qué se promueve (con enmienda) y qué queda
- [ ] TRACKER y LEDGER actualizados

## Orden de ejecución (AUTORIZADO por el user 2026-08-10)

| # | Tarea | Quién | Nota |
|---|---|---|---|
| 0 | Commit del Research OS (D-16) + filas de lineage (D-17) | Controlador | Antes de despachar nada |
| 1 | **T0.2** — propuesta de limpieza de disco C: | Sonnet · INVESTIGADOR report-only | 🔴 Primera entrega: el user la quiere leer PRIMERO |
| 2 | **T0.9-min** — scaffold mínimo de runner (D-18) | Sonnet · implementador · TDD | Paralelizable con T0.2 (ficheros disjuntos) |
| 3 | **T0.4** — top-up Capitaria, primer cliente del runner | Sonnet impl. + runner | Requiere `MT5_Tester` abierto por el user |
| 4 | **T0.12** — sellar el holdout | Controlador | **Inmediatamente después de T0.4** |
| 5 | **T0.3** — AVA (D-19) | Sonnet | Tras terminal AVA abierto + autorización del guard |
| 6 | **T0.5** — export historial 902 | Sonnet | Desbloquea la autopsia |
| 7 | **T0.11b** — análisis de los 28 videos | Ver `PROTOCOLO-REVISION-VIDEOS.md` al pie de la letra | No se reinterpreta |

Máximo **2 en paralelo**, nunca sobre los mismos ficheros. Solo el par (1,2) es paralelizable de
entrada. T0.6 (motor) sigue esperando el sign-off del user (B2) → T0.7 (A6) → T0.8 (freeze).

### Por qué T0.4 es prioritaria (corregido — ver ENMIENDA E-01)

**No es por la ventana rodante.** Lo que rueda fuera de los ~7 meses es el histórico viejo, que
**ya está capturado en disco** (`data/lake_ticks/XAUUSD/202601..202607.parquet`); el hueco
jul-ago es reciente y seguirá disponible meses.

La razón real es que **A6 Pata A necesita exactamente esa ventana**: es el período en que la 902
operó en vivo, y sin esos ticks no se puede medir la fidelidad del motor contra el historial real
— que es el **gate de todo el programa** (§4.2 del plan). T0.4 no compite contra el calendario:
compite contra la fecha en que queremos poder correr A6.

🔴 **T0.4 × holdout:** la ventana jul-ago es candidata directa al *"trimestre más reciente del
sustrato combinado"* que D-01 manda sellar. **Descargarla sí; mirarla no.** Por eso T0.12 va
inmediatamente después de T0.4 (charter §A.14: quien lo lee dos veces, lo quema).

## Riesgos conocidos de esta fase

| Riesgo | Cómo se detecta / mitiga |
|---|---|
| A6 Pata A no se puede correr porque falta la ventana de ticks jul-ago en que operó la 902 | T0.4 antes que el motor; es su insumo directo (no es urgencia de calendario — ver ENMIENDA E-01) |
| Alguien explora la ventana jul-ago que después queda sellada como holdout | T0.12 inmediatamente después de T0.4; descargar ≠ mirar (D-01, charter §A.14) |
| A6 falla y no sabemos qué capa falló (motor vs feed) | Diseño de **dos patas**: Pata A sobre ticks Capitaria (motor), Pata B AVA-vs-Capitaria (feed) |
| A6 diverge en cascada tras el primer cierre manual | Motor mod #12: inyección de eventos — los cierres manuales se fuerzan en su timestamp |
| Se implementa el motor y luego falta una modificación | Sign-off del inventario **antes** de implementar; después del freeze cuesta re-validación completa |
| El spread de AVA (menor que Capitaria) hace optimistas los backtests | Overlay de costos obligatorio; ninguna cifra AVA-cruda se compara con cifras Capitaria |
| Alguien mira el holdout "solo un poco" | Sellado antes de explorar; charter §A.14 — leerlo dos veces lo quema |
