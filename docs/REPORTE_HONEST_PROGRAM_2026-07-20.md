# Reporte matinal — Programa Honesto (noche 2026-07-19 → 2026-07-20)

> Rama `alvaro`. Fills honestos (`live_fill_mode=True`) + fricción plana 0.5 (Capitaria) +
> estadística deflactada (DSR). Objetivo: re-juzgar TODO lo que evaluó el motor clásico
> inflado y auditar los "gigantes" de la ventana W2. Stack live de producción intacto.

---

## 0. Titular (números primero)

- **NO sobrevive ningún ganador con significancia estadística honesta.** El barrido de
  102 pruebas da **DSR = 0.0000 → p-valor honesto = 1.0000**. El mejor config luce Sharpe
  2.42, pero bajo la búsqueda de 102 configs el azar produciría Sharpe ~11.1. **Cero edge probado.**
- **Los "gigantes" W2 de $44–146k eran humo.** De 17 celdas auditadas, **8 PASAN / 9 FALLAN**.
  Las 8 que pasan son **todas M15** y valen **+$3.9k a +$7.7k** honestos (no las cifras de 6 dígitos).
  Todo el bloque **M2 y M5 muere** (de −$2k hasta −$34k honestos).
- **La única señal real que queda:** una familia **M15** con un edge **pequeño pero positivo**
  (~+$6–8k en el mes W2 a 0.10 lote). Nada en M2/M5 sobrevive a fills honestos.
- **FIXED4 listo para machine-2** (shadow-only, D114) — gate local cumplido, pendiente solo el
  pull + evidencia de plataforma en machine-2.

---

## 1. Qué corrió (conteos)

| Ítem | Valor |
|---|---|
| Celdas honestas persistidas (mega-barrido B3) | **346** (`audit_log: honest_cell_persisted`) |
| Pruebas únicas en la liga (familia DSR) | **102** |
| Folds walk-forward | 7 |
| Celdas W2/OOW2 auditadas forensicamente (B4) | 17 |
| Filas `audit_log` del programa (actor `honest-program`) | 77 |
| Suite de tests (gate final) | **294 passed** |
| Proceso de barrido aún corriendo | ninguno (terminó ~00:16) |
| Proceso live en máquina | solo el stack de producción (`run_live_20 --arm`), intacto |

---

## 2. Liga honesta — ganadores DSR y quién murió

**Ganador nominal:** `HON-S6-V15-K1P5-AC1-M15` (J mediana de fold = 3259.8, dominancia 100%),
seleccionado por *minimum-change prior* dentro de un empate a 1-SE.

**Tie-pool (9 candidatos, TODOS M15):**
`S6-V15-K1P5-AC{0,1}`, `S6-V15-K2P0-AC{0,1}`, `S7-V15-TP{NONE,1P0,1P5}-BE{NONE,1P0}` — todos M15.

**Veredicto estadístico honesto (lo que importa):**

| Métrica | Valor |
|---|---|
| Sharpe observado | 2.4243 |
| Pruebas buscadas | 102 |
| Sharpe máximo esperado bajo el nulo (búsqueda sin skill) | 11.1358 |
| **Deflated Sharpe Ratio (DSR)** | **0.0000** |
| **p-valor honesto** | **1.0000** |

→ **Ningún config supera el umbral de significancia** una vez penalizada la búsqueda múltiple.
El ganador es "el mejor de un montón", no una señal probada.

**Quiénes murieron:** toda estructura es **M15-only**. **M5 y M2 son catastróficos** bajo fills
honestos (J mediana de −11k a −80k). Los viejos "ganadores" de 6 dígitos del motor clásico
(V11/V13/V15 en M2/M5) quedan en negativo.

---

## 3. Auditoría forense W2/OOW2 (B4) — APLICADA a la base

17 celdas `sim-report-emasar-oow2-*` (ventana W2 2026-03-02 → 04-03), antes marcadas
`REGIME_UNAUDITED`, ahora resueltas. **Escritura aplicada e idempotente** (reprodujo el dry-run al
byte; `run.validity`: 8 PASS / 9 FAIL, 0 `REGIME_UNAUDITED`).

| Timeframe | Neto clásico (papel) | Neto honesto | Veredicto |
|---|---|---|---|
| **M15** (8) | $44.8k – 92.1k | **+$3.9k → +$7.7k** | ✅ TODAS PASS |
| **M5** (5) | $116k – 129k | −$4.6k → −$6.0k | ❌ TODAS FAIL |
| **M2** (4) | $111k – 146k | −$27.6k → −$33.9k | ❌ TODAS FAIL |

Celdas más fuertes: `v06c/v06d-m15` **+$7.7k**, `v13-m15` +$7.0k, `ss-m15` +$6.9k, `ctrl-m15` +$5.1k.

**Causa raíz de la inflación:** las 17 celdas son **causal-limpias en la entrada** (mejora de
entrada media firmada = 0.0; fracción de salida same-bar = 0.0 → entran exactamente al cierre de
barra). Todo el gap de 6 dígitos es el **trail-raise same-bar del motor clásico** (el look-ahead D90
que el modo live-fill honesto neutraliza). No es timing de entrada — es la subida intrabar del stop.

**Veredicto de familia:** la región W2-M15 se sostiene, pero **a magnitud deflactada** — el titular
"+$9.3–9.6k" era optimista; lo honesto y causal está en **+$6–8k** para los configs fuertes. El lado
M2/M5 está **muerto**: de ~$68–146k de papel, **~$0 sobrevive**.

---

## 4. FIXED4 para machine-2 (notas de comportamiento esperado)

FIXED4 = los 4 configs live (V11-M2, V13-M2, V15-M2, V15-M15) con las correcciones de honestidad
(`ac_modulate=False`, `live_fill_mode=True`, `trail_atr_floor_k=1.5`), IDs sufijo `-F`,
**magics 721011–721043** (banda disjunta de los live 7200xx/7201xx).

- **Directiva D114:** machine-2 opera **SOLO** FIXED4 (`--configs shadow`). Prohibido `live` y
  `live+shadow` en machine-2.
- **Gate local cumplido en machine-1:** backtest A1-V 5/5 PASS (idempotencia, byte-identidad clásica,
  open_state honesto); ciclo live real (2026-07-20T02:20Z, DEMO 2883015767) — los 4 `-F` ciclaron sin
  errores, magics shadow espejando la señal live con el mismo SL, ciclo 1.6 s; suite 265→294 passed.
- **Pendiente en machine-2:** `git pull origin alvaro` (ver `75ad350` FIXED4 + `056bdef` sim honesto)
  → correr kit de evidencia zero-positions (AutoTrading ON, `machine_local.json`, sin STOP, preflight
  verde, terminal DEMO 2883015767 attach-only) → recién ahí armar shadow. Rollback = parar.
- Detalle completo: `docs/MACHINE2_FIXED4_DEPLOY_2026-07-19.md`.

---

## 5. Resumen de marcado del registro (aditivo, con audit trail)

| Etiqueta `validity` | Filas | Significado |
|---|---:|---|
| `DUPLICATE_INGEST` | 39 | pares TOKATA duplicados (se conserva el primer `run_id`) |
| `LOOKAHEAD_CONFIRMED` | 4 | familia V-12 (`m1/m2/m5/m15`), look-ahead confirmado |
| `W2_AUDIT_PASS` | 8 | oow2 M15 con edge honesto real (+$3.9–7.7k) |
| `W2_AUDIT_FAIL(…)` | 9 | oow2 M2/M5 — inflación por look-ahead, negativo honesto |
| `REGIME_UNAUDITED` | 0 | todas las 17 oow2 fueron resueltas por B4 |
| `INEXECUTABLE_STOP` | 0 | ninguna fila casó la familia de stop de 3 pips |
| (sin marcar) | 718 | resto del registro |

Política: **ADITIVA-ONLY** — ninguna fila original borrada ni mutada; todo vía columna nueva +
`audit_log` (actor `honest-program`, acción `validity-mark`, 77 filas totales).

---

## 6. Desviaciones del plan

- **Holdout single-touch NO corrido** para el ganador del barrido (diferido a propósito; reportado
  honestamente, no falseado). Sin holdout, el ganador M15 no tiene confirmación fuera de muestra final.
- **DSR p=1.0:** el plan esperaba destilar "sobrevivientes DSR"; el resultado honesto es que **no hay
  sobreviviente significativo** — es un hallazgo válido, no un fallo de ejecución.
- Track C (telemetría P3 de spread, presupuesto de pérdida P30) **no iniciado** (era "si sobra tiempo").
- `2026-07-20-honest-league.trials.db` queda **untracked** en git (artefacto derivado, regenerable).

---

## 7. Recomendación para la próxima ola

1. **Correr el holdout single-touch** sobre la familia M15 (`v06c/v06d/v13-m15`) — es la única con
   edge honesto positivo; sin holdout no es desplegable.
2. **No desplegar nada nuevo por DSR** — con p=1.0 no hay señal probada; el barrido dice "para de
   buscar en este espacio", no "aquí está el ganador".
3. **Enterrar M2/M5** como fuente de configs: bajo fills honestos su edge es negativo en todos lados
   (barrido y auditoría W2 coinciden).
4. **Cerrar FIXED4 en machine-2** (shadow-only) para observar el gap sim↔live real con magics
   disjuntos, antes de cualquier decisión de capital.
5. **Ola siguiente de barrido:** más ventanas (habilitar W1/W3 donde el lake lo permita) y niveles de
   fricción reales (P3) — el 0.5 plano es conservador pero no capturado; validar con spread medido.

---

*Generado por el orquestador del programa honesto. Stack de producción y assets originales intactos.*
