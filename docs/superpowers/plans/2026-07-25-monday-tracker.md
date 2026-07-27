# TRACKER — Entrega del lunes 2026-07-27 (campeón/retador)

> **Este archivo es la ÚNICA fuente de verdad del estado.** El plan dice QUÉ hacer; esto dice
> QUÉ SE HIZO. Cada subagente lo actualiza al terminar SU tarea (último paso de cada tarea) y
> commitea el cambio. No se edita a mitad de una tarea.
>
> - **Plan:** `docs/superpowers/plans/2026-07-25-monday-champion-challenger.md`
> - **Spec:** `docs/superpowers/specs/2026-07-25-monday-champion-challenger-design.md`
> - **Rama:** `equipo1`. **Nunca commitear a `alvaro`.**
> - **Deadline:** lunes 2026-07-27, primera hora.

Vocabulario: `[ ]` pendiente · `[~]` en curso · `[x]` hecho · `[!]` bloqueado/escalado.

---

## Rollback point

- **Tag:** `pre-challenger-2026-07-25` → SHA: `dfdc4d7cd34d473484ce20ca4d00f9e2ed52ba37`
- **Procedimiento de rollback:** _(Task 11 lo escribe aquí, 3 niveles)_

## Números que otras tareas necesitan

| Dato | Valor | Origen | Tarea que lo produce |
|---|---|---|---|
| `max_open_fichas` (cap B3) | **7** (pico observado de fichas simultáneas, 2347 posiciones / 7 meses). Sigue siendo 7 tras regenerar con el reloj corregido | `data/analysis/monday_audit/a2_overlap.json` | Task 8 |
| Correlación diaria de neto por par | **S6\|S7 +0,760 · S6\|ST +0,352 · S7\|ST +0,141** sobre **163** días de trading. 🔴 **Estos valores SUSTITUYEN a los de Task 8** (+0,730 / +0,295 / +0,047 sobre 161 días), medidos con el reloj roto | `data/analysis/monday_audit/a2_overlap.json` | Task 8, regenerado 2026-07-27 |
| maxDD @0.1 lot | **−28,57 %** del balance inicial (59,6 MM CLP) = −17 028 660 CLP; pico 2026-03-23 → valle 2026-04-28. **CONFIRMA** la estimación previa de −28,6 % (diferencia = redondeo; el CLP del pico-valle calculado, 17 028 660, coincide casi exacto con la regla de tres original, 114 092 025 × 0,1/0,67 = 17 028 660,45) | `data/analysis/monday_audit/a1_maxdd.json` | Task 7 |
| Cobertura del calendario B2 | 36 eventos, `2026-01-02T12:30:00Z`..`2028-12-01T12:30:00Z` (regla NFP: primer viernes del mes, 12:30 UTC; sin CPI/FOMC/PPI — ver limitación abajo) | `data/live/news_calendar.csv` | Task 2 |
| Veredictos de máscara B1–B4 | _pendiente_ | `b6_mask_verdicts.json` | Task 10 |

---

## Estado por tarea

| # | Tarea | Lane | Modelo | Estado | Evidencia / notas |
|---|---|---|---|---|---|
| 0 | Tag de seguridad + punto de revert | — | Sonnet 5 high | `[x]` | tag `pre-challenger-2026-07-25` → `dfdc4d7cd34d473484ce20ca4d00f9e2ed52ba37` |
| 1 | `risk_gates.py` — B1–B4 como lógica pura | B | Sonnet 5 high | `[x]` | 12/12 tests verdes en `tests/live/test_risk_gates.py`; suite completa de `tests/live` (189/189) también verde. Commit `e065fca`. Gate completa (full-suite) del repo eximida por el controller esta vez por un test lento patológico bajo investigación aparte; ver bitácora. |
| 2 | `news_calendar.py` + calendario commiteado | B | Sonnet 5 high | `[x]` | 9/9 tests verdes en `tests/live/test_news_calendar.py`; suite `tests/live` completa 198/198 verde (5.17 s). Commit `3a62b61`. Calendario: no existía `data/live/news_calendar_source.md`, así que se sembró con la regla NFP (primer viernes del mes, 12:30 UTC), fija y no re-tuneada (R3) — 36 filas, `2026-01-02`..`2028-12-01`. **Limitación declarada:** solo cubre NFP; CPI/FOMC/PPI (irregulares, no derivables por regla) quedan pendientes de que el user las añada — ver `data/live/news_calendar.README.md`. Gate completa (full-suite) del repo eximida por el controller (waiver explícito, mismo motivo que Task 1/6); sustituida por `python -m pytest tests/live -q`. |
| 3 | `gap_wait.py` — máquina de estado de B1 | B | Sonnet 5 high | `[x]` | 9/9 tests verdes en `tests/live/test_gap_wait.py`; suite `tests/live` completa 207/207 verde (4.92 s). Commit `70ab421`. |
| 4 | `CONFIGS_CHALLENGER` — roster espejo 726xxx | B | Sonnet 5 high | `[x]` | `CONFIGS_CHALLENGER` (3 configs, magics 726010/726020/726070, volume 0.02, `risk_gates` con `max_open_fichas=7` leído de `data/analysis/monday_audit/a2_overlap.json` vía Step 3 del brief). 7/7 tests nuevos verdes en `tests/scripts/test_run_live_20.py -k challenger`; suite dirigida `tests/scripts/test_run_live_20.py tests/live` → 244/244 verde (con `SUPERVISOR_MAX_SPREAD_OPEN`/`SUPERVISOR_STALE_AUTORESTART` despojados del entorno; con ellos puestos, los 7 fallos pre-existentes de `test_supervisor_env_*` reaparecen, no introducidos por esta tarea). `CONFIGS_LOCAL` verificado byte-idéntico (primeras 606 líneas del archivo idénticas al blob de HEAD; `git diff` solo agrega 92 líneas, cero eliminaciones). Commit `36979a3`. · **CORRECCIÓN 2026-07-26 APLICADA:** `CHALLENGER_VOLUME` 0.02 → **0.1** (paridad de tamaño con el campeón; duplica la exposición, aceptado por el user). Se tocaron solo el comentario de motivo, la constante, el mensaje del assert y la aserción del test; diff = 6 inserciones / 4 borrados, **todos por debajo de la línea 606** (ningún hunk toca `CONFIGS_LOCAL`, R1-bis intacto). Re-verificado `tests/scripts/test_run_live_20.py tests/live` → **244/244 verde** (11,83 s). |
| 5 | Plumbing del executor (gates en el OPEN) | B | **Opus 5 medium** | `[ ]` | la más compleja |
| 6 | Loader de auditoría (2.347 posiciones) | A | Sonnet 5 high | `[x]` | 4/4 tests verdes en `tests/analysis/test_monday_audit.py`. Smoke check contra datos reales: `2347 Counter({'S7-TPNONE': 1167, 'S6-K2P0': 912, 'SuperTrend-p14x3-M15': 268})` — coincide exacto con lo esperado en el brief. Commit `54355b9`. Gate completa (full-suite) del repo eximida por el controller por el mismo test lento patológico bajo investigación aparte (ver Task 1 y bitácora); se sustituyó por `python -m pytest tests/analysis -q` → `4 passed in 0.07s`. |
| 7 | A1 — verificar el maxDD | A | Sonnet 5 high | `[x]` | `max_drawdown()` en `scripts/analysis/monday_audit/a1_maxdd.py`. TDD seguido: rojo confirmado (`ModuleNotFoundError: ... a1_maxdd`) antes de implementar; 3/3 tests nuevos verdes, 11/11 en `tests/analysis/test_monday_audit.py` (0.07 s). Real-data run sobre las 2347 posiciones (ordenadas por `t_out`, equity acumulada @0.1 lot, empates por `(t_out, strategy, t_in)`): **maxDD = −17 028 660,47 CLP = −28,57 % del balance inicial** (59,6 MM CLP), pico 23 949 863,73 CLP el 2026-03-23T02:32:53 → valle 6 921 203,26 CLP el 2026-04-28T21:57:52. **CONFIRMA** la estimación previa de −28,6 % — la diferencia (28,57 vs 28,6) es solo redondeo; el CLP del drawdown calculado coincide casi al peso con la regla de tres original (114 092 025 × 0,1/0,67 = 17 028 660,45 ≈ 17 028 660,47 calculado). Como fracción del pico de equity en vez del balance inicial, el DD es −20,38 %. Artefacto: `data/analysis/monday_audit/a1_maxdd.json`. Se agregó excepción de `.gitignore` para este archivo, mismo patrón que `a2_overlap.json` (Task 8). Solo se tocaron `scripts/analysis/monday_audit/a1_maxdd.py`, `tests/analysis/test_monday_audit.py` y `.gitignore` (Lane A); no se tocó `a2_overlap.py` (edición concurrente de Task 8, ya mergeada). · commit `ff86d97` (feat), commit de este tracker a continuación. |
| 8 | A2 — solape, correlación y cap B3 | A | Sonnet 5 high | `[x]` | `max_concurrency()` + `pearson()` en `scripts/analysis/monday_audit/a2_overlap.py`. TDD seguido: rojo confirmado (`ModuleNotFoundError: ... a2_overlap`) antes de implementar; 4/4 tests nuevos verdes, 8/8 en el paquete completo `tests/analysis/test_monday_audit.py`. Real-data run sobre las 2347 posiciones: **cap B3 = 7** (pico de fichas simultáneas, dentro del rango de cordura 1–9; sanity-checked: alcanzado en 104/161 días de trading, no es un episodio aislado). Correlación diaria de neto por par: S6\|S7 +0.730, S6\|ST +0.295, S7\|ST +0.047 (S6/S7 comparten buena parte de la misma apuesta; ST es casi independiente). Artefacto: `data/analysis/monday_audit/a2_overlap.json`. Suite completa del repo corrida una vez (foreground, ~8m50s): `13 failed, 1914 passed, 2 skipped` — los 13 fallos coinciden exactamente con la lista pre-existente conocida (`test_run_live_20.py` ×7, `test_supervisor_live.py` ×2, `test_chat.py` ×1, `test_web_positions.py` ×2, `test_search.py` ×1); ninguno introducido por esta tarea. Se abrió excepción de `.gitignore` para `data/analysis/monday_audit/a2_overlap.json` (artefacto de auditoría commiteado, no dato de mercado regenerable — mismo patrón que `data/live/news_calendar.csv` en Task 2). · commit `cc70453` (feat), commit de este tracker a continuación. **Desbloquea Task 4.** |
| 9 | A3+A4+A5 — atribución, serial, gate 0.5 | A | Sonnet 5 high | `[x]` | `scripts/analysis/monday_audit/a3_a4_a5_stats.py`. 16/16 tests verdes en `tests/analysis/test_monday_audit.py`. **A3** (atribución por `(estrategia, reason)`): S6-K2P0 EXIT_INITSL n=891 net=89,68MM CLP (WR 36,0%) + EXIT_TRAIL n=21 net=3,95MM (WR 57,1%); S7-TPNONE EXIT_INITSL n=1104 net=24,56MM (WR 34,8%) + EXIT_TRAIL n=63 net=8,61MM (WR 47,6%); SuperTrend EXIT_STLINE n=268 net=20,98MM (WR 22,8%, único reason — no tiene trailing). **A4** (autocorrelación lag-1..5 en orden de `t_out`): S6 lag1=+0,635, S7 lag1=+0,655 (positiva y decayendo a ~0 en lag3+ — los resultados sí se agrupan en rachas de corto plazo, consistente con régimen); SuperTrend lag1=−0,063 (prácticamente independiente). Rachas más largas: pérdidas S6=27, S7=42, ST=13; ganancias S6=15, S7=15, ST=4. **A5 — NO EVALUABLE como comparación 0,5 vs 0,6**: las 2347 posiciones reales tienen spread=0,5 en el 100% de las filas (`at_0.6.n = 0` en las 4 vistas — por estrategia y COMBINED); no hay ni una fila a 0,6 en los CSV de reconstrucción real-tick de 7 meses. El filtro sigue validado únicamente por las cinco sesiones live citadas en el brief; esta auditoría NO lo corrobora ni lo refuta por falta de evidencia en el dato (regla "lo no evaluable se declara no evaluable"). A5 COMBINED (línea impresa por el script): `@0.5 net=147.780.084 (n=2347) \| @0.6 net=0 (n=0) \| unfiltered=147.780.084`. **Desviación documentada del brief:** el código Step-3 del brief para `autocorrelation` (media/varianza globales de la serie) da −0,8 en el propio fixture verbatim del brief (`[1,-1,1,-1,1]`, lag=1) y **no pasa** el test verbatim del propio brief (`< -0.9`); se implementó en su lugar la correlación de Pearson entre las dos subseries desplazadas por el lag (cada una normalizada por su propia media/varianza), que da exactamente −1,0 en ese fixture y sí satisface el test. Ambas fórmulas son válidas en la literatura; se documentó la discrepancia in-line en el código y en el reporte de la tarea. Artefactos: `data/analysis/monday_audit/{a3_exit_reason,a4_serial,a5_spread_gate}.json`, excepción de `.gitignore` una línea por archivo (mismo patrón que Task 7/8). `python -m pytest tests/analysis -q` → `16 passed in 0.06s`. Solo se tocaron `scripts/analysis/monday_audit/a3_a4_a5_stats.py`, `tests/analysis/test_monday_audit.py`, `data/analysis/monday_audit/{a3,a4,a5}*.json` y `.gitignore` (Lane A); no se tocó `a1_maxdd.py`, `a2_overlap.py` ni `loader.py`. · commit `d02e187` (feat), commit de este tracker a continuación. |
| 10 | Máscaras retrospectivas — veredictos | A/B | Sonnet 5 high | `[ ]` | necesita 6, 8, 2 |
| 11 | Ensayo de revert | B | Sonnet 5 high | `[ ]` | |
| 12 | Despliegue máq1 | B | Sonnet 5 high | `[ ]` | 🙋 **pasos 5-6 = manos del user** |
| 13 | Documento del lunes | — | Opus 5 medium | `[ ]` | |
| 14 | Track C — entrada aleatoria | A | Sonnet 5 high | `[ ]` | **NO bloquea el lunes** |
| 15 | Escalera de distancia de SL — **solo backtest** | A | Sonnet 5 high | `[ ]` | **NO bloquea el lunes.** Añadida 2026-07-26 por decisión del user |
| 16 | Curva del codo de la espera post-apertura (B1) — **solo backtest** | A | Sonnet 5 high | `[ ]` | **NO bloquea el lunes.** Añadida 2026-07-27. Ver §Task 16 abajo. Depende del substrato con el reloj corregido |

## 🔴 Correcciones del user 2026-07-26 (1 aplicada, resto vigentes)

1. **Lote del retador: 0.02 → 0.1.** ✅ **APLICADA 2026-07-26** — `CHALLENGER_VOLUME = 0.1`,
   igual que el campeón. Motivo: paridad de tamaño hace el A/B directamente comparable en vez de
   normalizado por operación. El user acepta explícitamente que duplica la exposición de la cuenta
   (DEMO 2883015767, 59,6 MM CLP). Roster + tests + R2 del plan, los tres al día.
2. **B4 se queda como está** (piso de legalidad a 0.50). La escalera de distancias de SL que el user
   quiere probar **no es B4**: es una mutación de la estrategia y vive en la nueva **Task 15**,
   backtest primero, sin desplegar nada hasta discutir resultados.
3. **Spread 0,5 y solo 0,5.** Las estrategias por diseño solo operan a 0,5; 0,6 es técnicamente
   operable pero **no lo haremos**. Esto confirma que A5 quedara declarada «no evaluable» era
   correcto, no un fallo.
4. **Task 12: el terminal MT5 correcto YA ESTÁ ABIERTO** (el que usan las estrategias vivas).
5. **Task 5 se puede validar en caliente**: las estrategias están tomando posiciones ahora mismo,
   así que se verá si algo se rompe.

---

## 🔴 Bug de reloj en el substrato (hallado 2026-07-27) — arreglado en origen

`scripts/analysis/realtick_bt/backtest.py` convertía los epochs de MT5 con
`datetime.fromtimestamp()`. Los epochs de MT5 **ya vienen en reloj de servidor** (UTC−4), así que esa
llamada les restaba **además** el offset local del PC. Y como Chile cambia de horario, **el desfase
cambia a mitad del dataset**: 3 h del 1-ene al 4-abr, 4 h del 5-abr en adelante.

Prueba: `_bars_M15.parquet` leído con `utcfromtimestamp` da la semana forex de manual (domingo 18:00
→ viernes 17:00, sábado vacío); leído con `fromtimestamp` da el mismo patrón deforme que tenían las
CSV de posiciones. Además el piso de hora mínima de los domingos baja de 15:00 a 14:00 justo en la
semana ISO 14, que es cuando Chile sale del horario de verano.

**Alcance medido — ningún número commiteado estaba mal:**

- cap B3 = **7** antes y después. Idéntico.
- **0 de 2347** posiciones cambian de duración (ninguna cruza la frontera de horario, así que `t_in`
  y `t_out` se desplazan lo mismo y la resta se cancela).
- Todo Track A es de orden o de ratio: neto, WR, PF, A1 drawdown, A3 exit reason, A4 serial,
  A5 spread. El emparejamiento barra↔tick↔posición se hizo por epoch, que siempre estuvo bien.
- Lo único inutilizado era cualquier lectura de **hora del día**. O sea, exactamente B1.

### 🔴 Lo que SÍ cambió al regenerar (corrige la expectativa «no cambia nada»)

La regeneración confirmó las cinco pruebas duras —2347 posiciones, neto exacto 147.780.084,05
comparado con `Decimal` sobre el texto crudo, multiset de duraciones idéntico (939 valores
distintos), desplazamiento exacto +3 h ×1716 / +4 h ×2978 sin una sola violación, y cap B3 = 7—.
`a3_exit_reason`, `a4_serial` y `a5_spread_gate` salieron **byte-idénticos**. `a1_maxdd` cambió solo
las etiquetas `t_peak`/`t_trough` (mismos números).

**Pero `a2_overlap` movió dos cosas reales, porque agrupa por `p.t_out.date()` y el corte de día
pasa a ser medianoche de SERVIDOR en vez de medianoche de Chile:**

- `n_trading_days` **161 → 163**
- correlación diaria de neto: S6\|S7 **0,7301 → 0,7596**, S6\|ST **0,2950 → 0,3520**,
  S7\|ST **0,0468 → 0,1409**

Los nuevos son los correctos. 🔴 **Consecuencia narrativa para el documento del lunes:** la frase de
Task 8 «SuperTrend es casi independiente de ambas» ya **no se sostiene igual** — S6\|ST sube a 0,35 y
S7\|ST triplica. Sigue siendo baja, pero hay que suavizar la afirmación, no repetirla.

También se re-agrupó la columna `month` (Mar 298→297, Abr 440→435, Jun 419→425), lo que cambia la
**grilla mensual** del reporte. Los totales no se mueven.

⚠️ `docs/REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md` fue reescrito como efecto colateral de
regenerar, **sin snapshot previo**, así que no hay diff viejo-contra-nuevo. Es regenerable.

Decisión del user: **arreglar en origen Y regenerar el substrato** (no la opción barata).
Se versionaron además `data/analysis/realtick_bt/positions_*.csv`, que estaban **fuera de git**
pese a ser la base de todo Track A (requisito R5), y `scripts/analysis/realtick_bt/`, que tampoco
estaba commiteado.

## Task 16 — curva del codo de la espera post-apertura (solo backtest)

**Motivación.** Con el reloj corregido, la máscara de B1 a los 50 min pre-fijados veta 209 de 2347
posiciones y el neto sube de 147.780.084 a 177.357.685 CLP (**+20,01 %**). Las 209 vetadas valían
−29,6 MM entre todas: −141 k de media cada una contra +63 k del promedio general. Confirma la
hipótesis del user: los indicadores contaminados por el hueco de apertura producen entradas malas.

**Pero el número no es estable**: 30 min → +13,3 %, 50 y 60 → +20,0 %, 90 min → **−15,2 %**. El signo
se da vuelta entre 60 y 90.

**Grilla en BARRAS, no en minutos.** Las entradas solo ocurren en múltiplos de 15 min tras la
reapertura (barras M15, reapertura en punto); nunca hay una entrada a +0. Por eso una espera de 50 y
una de 60 son **el mismo experimento** (ambas bloquean {15,30,45} = 209 posiciones). La grilla
correcta es «bloquear las primeras N barras M15». **N = 2..6** (30/45/60/75/90 min) — el user
descartó explícitamente N=1 (15 min).

**Contrato del entregable (igual que Task 15, decisión del user):**

- El entregable es una **comparación contra la baseline**, no un campeón. El implementador **no elige
  ganador**; el user decide con los números delante. Nada se despliega sin otra decisión suya.
- 🔴 **PERO el ranking SÍ se registra**, explícitamente y por escrito. Razón del user: aunque sea
  sobreajuste sobre 7 meses, no es tan grave, y si no queda documentado cuál salió mejor, alguien más
  adelante puede reintentar 15 o 90 minutos sin entender por qué le va peor. El documento debe dejar
  el orden de los peldaños Y el caveat de que es in-sample.
- Buscar el codo **es tunear**, así que este resultado va **declarado aparte** del veredicto de
  máscara — mismo razonamiento que separó B4 de Task 15. El veredicto de B1 para el lunes sigue
  siendo el de los **50 min fijados de antemano** por diagnóstico, no el que salga de esta curva.

**Reaperturas: medidas, no supuestas.** Primera barra tras una interrupción ≥60 min en el stream de
barras M15 → **145 reaperturas**. La pausa diaria dura exactamente 1:15:00 (115 casos) y reabre a las
18:00 (n=64), 20:00 (n=36) o 19:00 (n=15); el fin de semana cierra el viernes y reabre domingo 18:00.
La moda de 18:00 coincide con el «abre a las 6 de la tarde» del user.

---

## Criterio de aceptación (spec §9)

- [ ] Sleeve A corriendo, verificablemente idéntico a hoy (snapshot verde).
- [ ] Sleeve B corriendo a **0.1** (paridad con el campeón) con B1–B4 activos, en la banda 726xxx.
- [ ] Máscara retrospectiva corrida para cada wrapper, veredicto registrado (veto / no-veto /
      no-evaluable), **sin haberla usado para seleccionar**.
- [ ] Tag de git sobre el commit vivo + revert de un paso probado.
- [ ] Pista A completa, con el maxDD confirmado o corregido.
- [ ] Documento entregado (= emitido; "entregado" de verdad solo tras revisión del user).
- [ ] Pista C corriendo o entregada (no bloquea el lunes).

---

## Reglas de ejecución (doctrina D152 — leer antes de despachar)

- **Implementadores e investigadores = Sonnet 5 high.** Solo Task 5 y Task 13 = **Opus 5 medium**.
- **Máximo 2 subagentes en paralelo**, y nunca dos que escriban archivos que se solapen.
  Lane A (`scripts/analysis/**`, `data/analysis/**`) y Lane B (`sentinel_engine/**`,
  `scripts/live/**`) son disjuntas por diseño: esas dos sí pueden ir juntas.
- **Briefs exhaustivos.** El subagente recibe la tarea COMPLETA copiada del plan + este tracker +
  las Global Constraints. Si tiene que inferir algo, el brief está mal escrito.
- **TDD obligatorio** (`superpowers:test-driven-development`): test rojo → mínimo código → verde →
  commit. Los pasos del plan ya vienen en ese orden.
- **Techo por subagente: ~30 min / ~300k tokens.** Al tocarlo: actualizar este tracker, hacer
  `/brain update` y pasar a un subagente NUEVO de la misma categoría con el estado en la mano.
- **Al terminar cada tarea: actualizar este tracker y commitearlo.** Sin excepción.

## Reglas de honestidad (no negociables)

- **Prohibido re-tunear cualquier parámetro** (R3). Ni un barrido, ni un "probé y este va mejor".
- **Las máscaras VETAN, nunca SELECCIONAN** (spec §4.4). Si te sorprendes comparando variantes de
  un wrapper por su resultado retrospectivo, para: eso es exactamente el error que esta entrega
  existe para no repetir.
- **Todo número lo calcula código** (R5). Ninguna cifra escrita a mano en ningún artefacto.
- **Lo no evaluable se declara no evaluable.** B2 fuera del rango del calendario y B4 sin columna
  de SL no son "sin problema": son "sin evidencia", y así van al documento.

---

## Bitácora

_(cada subagente añade una línea al terminar: fecha ISO · tarea · qué quedó · commit)_

- 2026-07-25 · Task 0 · Tag anotado `pre-challenger-2026-07-25` creado sobre HEAD (`dfdc4d7`, resuelto por `git rev-parse` sin editar a mano); working tree confirmado limpio (`git status --porcelain -uno` vacío) y `git diff 496fecf..HEAD --stat` verificado solo-docs antes de taguear. Punto de revert registrado arriba. · commit `chore(tracker): rollback tag pre-challenger-2026-07-25 recorded`
- 2026-07-26 · Task 1 · `sentinel_engine/live/risk_gates.py` creado: `GateInput`/`GateDecision` (dataclasses frozen) + `evaluate_open_gates()` puro (sin MT5, sin reloj, sin filesystem) implementando B1 `gap_wait_minutes`, B2 `news_blackout_minutes` (fail-closed sin calendario), B3 `max_open_fichas`, B4 `min_sl_distance` (fail-closed, hit = BUG), en ese orden fijo. TDD seguido: rojo confirmado (`ModuleNotFoundError`) antes de implementar. 12/12 tests verdes en `tests/live/test_risk_gates.py`; suite `tests/live` completa 189/189 verde (5.75 s). La suite COMPLETA del repo fue eximida para esta tarea por el controller (waiver explícito): hay un test lento patológico en investigación aparte que hace que una corrida completa tome ~1 hora; se sustituyó por la corrida dirigida de `tests/live`. `CONFIGS_LOCAL` no tocado (R1); módulo nuevo, aditivo, sin mutar objetos compartidos (R4). · commit `e065fca` (feat), commit de este tracker a continuación.
- 2026-07-26 · Task 6 · `scripts/analysis/monday_audit/loader.py` creado: `Position` (dataclass frozen, 12 campos tipados) + `load_positions(root=REALTICK_DIR) -> list[Position]` que funde los 3 CSV (`positions_S6-K2P0.csv`, `positions_S7-TPNONE.csv`, `positions_SuperTrend-p14x3-M15.csv`), etiqueta cada fila con su `strategy` y ordena por `(t_in, strategy)` — orden total y determinista. `net_at_lot(lot)` reescala linealmente desde `SOURCE_LOT=0.67`. TDD seguido: rojo confirmado (`ModuleNotFoundError: No module named 'scripts.analysis.monday_audit'`) antes de implementar. 4/4 tests verdes en `tests/analysis/test_monday_audit.py` (0.07 s). Smoke check contra los CSV reales: `2347 Counter({'S7-TPNONE': 1167, 'S6-K2P0': 912, 'SuperTrend-p14x3-M15': 268})` — coincide exacto con los conteos del brief, sin necesidad de reconciliar nada. La suite COMPLETA del repo fue eximida para esta tarea por el mismo waiver del controller que Task 1 (test lento patológico bajo investigación aparte, ~1 hora); se sustituyó por `python -m pytest tests/analysis -q` → `4 passed in 0.07s`. Solo se tocaron `scripts/analysis/monday_audit/**` y `tests/analysis/**` (Lane A); nada bajo `sentinel_engine/` ni `scripts/live/`. · commit `54355b9` (feat), commit de este tracker a continuación.
- 2026-07-26 · Task 2 · `sentinel_engine/live/news_calendar.py` creado: `load_windows(path=CALENDAR_PATH, *, minutes_before, minutes_after) -> tuple[tuple[datetime,datetime],...] | None`, fail-closed (`None`) ante archivo ausente/ilegible, header sin `utc_datetime`, o timestamp no parseable; header válido con 0 filas devuelve `()` (legible, sin eventos). Reloj: `utc_datetime` es UTC real (no hora de servidor MT5); un timestamp naive se lee como UTC. TDD seguido: rojo confirmado (`ImportError: cannot import name 'news_calendar'`) antes de implementar. 9/9 tests verdes en `tests/live/test_news_calendar.py`; suite `tests/live` completa 198/198 verde (5.17 s) — el intento inicial de correr la suite COMPLETA del repo en foreground se salió del control (superó el timeout de la herramienta y quedó en background pese a la prohibición explícita del controller); el controller intervino, la corrida en background fue abortada sin esperar su resultado, y se declaró el waiver explícito documentado abajo. Calendario `data/live/news_calendar.csv`: no existía `data/live/news_calendar_source.md` (ningún export del user), así que se sembró con la regla fija NFP (primer viernes del mes, 12:30 UTC / 08:30 ET) — 36 filas generadas por código (no a mano, R5), rango `2026-01-02T12:30:00Z`..`2028-12-01T12:30:00Z`. **Limitación honesta:** solo cubre NFP; CPI/FOMC/PPI son irregulares (no derivables por regla) y quedan pendientes de que el user las añada a mano — documentado en `data/live/news_calendar.README.md`. `data/` está en `.gitignore` en bloque (lake de mercado regenerable); se abrió una excepción explícita para `data/live/{news_calendar.csv,news_calendar.README.md}` usando `data/*` en vez de `data/` (una exclusión de directorio con `/` final impide que git recorra el árbol y la negación de hijos no tiene efecto — trampa clásica de gitignore, documentada en el propio archivo). Gate completa (full-suite) del repo eximida por el controller (waiver explícito, mismo motivo que Task 1/6: test lento patológico bajo investigación aparte, ~1h); sustituida por `python -m pytest tests/live -q` → `198 passed in 5.17s`. Solo se tocaron `sentinel_engine/live/news_calendar.py`, `tests/live/test_news_calendar.py`, `data/live/news_calendar.csv`, `data/live/news_calendar.README.md` y `.gitignore` (Lane B); no se tocó `tests/analysis/test_monday_audit.py` (edición concurrente de Task 8, dejada intacta). · commit `3a62b61` (feat), commit de este tracker a continuación.
- 2026-07-26 · Task 3 · `sentinel_engine/live/gap_wait.py` creado: `GapWaitState(last_seen, spread_ok_since)` (dataclass frozen) + `advance(state, *, now, spread, thin_spread=THIN_SPREAD, session_gap_minutes=SESSION_GAP_MINUTES)` pura, + `load(path=STATE_PATH)`/`save(state, path=STATE_PATH)` para persistir a `data/live/gap_wait_state.json`, siguiendo el mismo patrón fail-closed de `news_calendar.py` (Task 2). Semántica implementada verbatim del brief: un gap ≥`SESSION_GAP_MINUTES` (60) desde la última observación es un reinicio de sesión y resetea `spread_ok_since` a `None`; el reloj arranca en la primera observación con `spread <= THIN_SPREAD` (0.5) tras el reset; el reloj NO se reinicia si el spread vuelve a ensancharse (regla: "≥50 min desde que el spread bajó", no "50 min consecutivos"); archivo de estado ausente o corrupto ⇒ estado fresco (`spread_ok_since=None`), que niega aperturas — dirección conservadora, nunca permisiva. Reloj: tanto `last_seen` como `spread_ok_since` son UTC real (mismo reloj que `datetime.now(timezone.utc)`), nunca hora de servidor MT5 — documentado explícito en el docstring del módulo para que Task 5 no mezcle relojes. TDD seguido: rojo confirmado (`ImportError: cannot import name 'gap_wait' from 'sentinel_engine.live'`) antes de implementar. 9/9 tests verdes en `tests/live/test_gap_wait.py` (incluye roundtrip a disco, archivo ausente y archivo corrupto `"{not json"`); suite `tests/live` completa 207/207 verde (4.92 s). No se creó `data/live/gap_wait_state.json` en disco (ningún test usa el `STATE_PATH` por defecto; el `.gitignore` ya excluye `data/live/*` salvo las excepciones explícitas de Task 2, así que un futuro archivo de estado real quedará ignorado automáticamente — no se tocó `.gitignore`). Solo se tocaron `sentinel_engine/live/gap_wait.py` y `tests/live/test_gap_wait.py` (Lane B); no se tocó `tests/analysis/test_monday_audit.py` ni `scripts/analysis/monday_audit/a2_overlap.py`, ambos con cambios concurrentes de Task 8 ya en stage, dejados intactos. · commit `70ab421` (feat), commit de este tracker a continuación.
- 2026-07-26 · Task 7 · `scripts/analysis/monday_audit/a1_maxdd.py` creado: `max_drawdown(deltas) -> Drawdown` (dataclass frozen: `max_dd`, `peak_equity`, `trough_equity`, `peak_index`, `trough_index`) barre la suma acumulada de `deltas` una sola vez llevando el pico corriente y la caída máxima pico-valle. `main()` carga las 2347 posiciones vía `loader.load_positions`, las ordena por `(t_out, strategy, t_in)` (equity se mueve al CERRAR, no al abrir — empates deterministas), reescala a 0,1 lot con `net_at_lot`, corre `max_drawdown` y escribe el artefacto vía `loader.write_artifact`. TDD seguido: rojo confirmado (`ModuleNotFoundError: No module named 'scripts.analysis.monday_audit.a1_maxdd'`) antes de implementar; 3/3 tests nuevos verdes (curva sintética de 4 puntos verificada a mano: 0→100→60→160→10, DD=150; curva monótona, DD=0; serie vacía, DD=0), 11/11 en el paquete completo `tests/analysis/test_monday_audit.py` (0.07 s). Real-data run: **maxDD @0,1 lot = −17 028 660,47 CLP = −28,57 % del balance inicial (59,6 MM CLP)** — pico 23 949 863,73 CLP el 2026-03-23T02:32:53 (server time), valle 6 921 203,26 CLP el 2026-04-28T21:57:52; como fracción del pico de equity (en vez del balance inicial) el DD es −20,38 %. **Veredicto: CONFIRMA la estimación previa de −28,6 %** — no es una coincidencia de redondeo superficial: el CLP del drawdown calculado (17 028 660,47) reproduce casi al peso la regla de tres original (114 092 025 CLP @0,67 lot × 0,1/0,67 = 17 028 660,45 CLP), es decir la ventana pico-valle que produjo la cifra de 2026 en circulación es la misma que produce el código sobre el stream real de 2347 posiciones. Artefacto: `data/analysis/monday_audit/a1_maxdd.json` (claves: `max_dd_clp`, `max_dd_pct_of_initial`, `max_dd_pct_of_peak_equity`, `peak_equity_clp`, `trough_equity_clp`, `t_peak`, `t_trough`, `final_net_clp`, `lot`, `account_balance_clp`, `n_positions`). Se agregó `!data/analysis/monday_audit/a1_maxdd.json` a `.gitignore`, mismo patrón que la excepción de `a2_overlap.json` en Task 8. Gate completa (full-suite) del repo eximida por el mismo waiver del controller (test lento patológico bajo investigación aparte); se sustituyó por `python -m pytest tests/analysis -q` → `11 passed in 0.07s`. Solo se tocaron `scripts/analysis/monday_audit/a1_maxdd.py`, `tests/analysis/test_monday_audit.py` y `.gitignore` (Lane A); no se tocó `a2_overlap.py` ni `loader.py` (solo importados), ambos de Task 6/8. · commit `ff86d97` (feat), commit de este tracker a continuación.
- 2026-07-26 · Task 8 · `scripts/analysis/monday_audit/a2_overlap.py` creado: `max_concurrency(intervals) -> (peak, hist)` barre el stream de posiciones fundidas como eventos ±1 en `t_in`/`t_out`, procesando salidas ANTES que entradas en un empate exacto de timestamp (un cierre-y-apertura al mismo instante es secuencial, no solapado) — orden `(t, delta)` con `-1` antes de `+1` por construcción del sort. `pearson(xs, ys)` correlación de Pearson pura (sin numpy), 0.0 si alguna serie tiene varianza cero. TDD seguido: rojo confirmado (`ModuleNotFoundError: No module named 'scripts.analysis.monday_audit.a2_overlap'`) antes de implementar; 4/4 tests nuevos verdes tras implementar, 8/8 en el paquete completo (`tests/analysis/test_monday_audit.py`, 0.07 s). Real-data run sobre las 2347 posiciones reales (S6 912 / S7 1167 / ST 268, vía `loader.load_positions`, sin re-simular nada): **cap B3 (`max_simultaneous_fichas`) = 7** — dentro de la cota de cordura del brief (1–9, dado que cada config corre a lo sumo 3 fichas). Verificado con un barrido adicional (no commiteado, solo diagnóstico) que el pico de 7 se alcanza en 104 de los 161 días de trading — no es un evento raro producido por un único episodio anómalo, es un nivel de solape rutinario en la práctica de las tres estrategias corriendo juntas. `p95_simultaneous` = `p99_simultaneous` = 7 (la métrica cuenta momentos-evento, no tiempo ponderado — así vino especificada en el brief). Correlación diaria de neto @0.67 lot (lot-invariante) por par: S6-K2P0\|S7-TPNONE +0.730, S6-K2P0\|SuperTrend-p14x3-M15 +0.295, S7-TPNONE\|SuperTrend-p14x3-M15 +0.047 — S6 y S7 comparten una porción sustancial de la misma apuesta direccional; SuperTrend es casi independiente de ambas. `pct_time_with_any_position` = 92.8 %. Artefacto escrito en `data/analysis/monday_audit/a2_overlap.json` vía `loader.write_artifact` (R5: cifra trazable a archivo, no a mano). Se abrió una excepción de `.gitignore` (bloque `data/*`) para `data/analysis/monday_audit/a2_overlap.json`, mismo patrón que la excepción de `data/live/news_calendar.csv` en Task 2 (artefacto de auditoría commiteado, no dato de mercado regenerable). Suite COMPLETA del repo corrida una vez en foreground (529.92 s ≈ 8m50s, sin waiver — instrucción explícita del controller esta vez): `13 failed, 1914 passed, 2 skipped, 20 deselected` — los 13 fallos coinciden uno a uno con la lista pre-existente conocida y verificada en el tag de rollback (`tests/scripts/test_run_live_20.py` ×7, `tests/scripts/test_supervisor_live.py` ×2, `tests/service/test_chat.py` ×1, `tests/service/test_web_positions.py` ×2, `tests/opt/test_search.py` ×1); ninguno introducido por esta tarea. Solo se tocaron `scripts/analysis/monday_audit/a2_overlap.py`, `tests/analysis/test_monday_audit.py`, `data/analysis/monday_audit/a2_overlap.json` y `.gitignore` (Lane A + la excepción puntual de gitignore); no se tocó `sentinel_engine/**` ni `scripts/live/**`; `loader.py` de Task 6 no se modificó, solo se importó (`load_positions`, `write_artifact`). **Task 4 queda desbloqueada: cap B3 = 7.** · commit `cc70453` (feat), commit de este tracker a continuación.
- 2026-07-26 · Task 4 · `CONFIGS_CHALLENGER` añadido al final de `sentinel_engine/strategies/live_configs_20.py` (después de la línea 606, fin del bloque `CONFIGS_LOCAL` — nada por encima de esa línea se tocó): 3 configs `_challenger_copy(cid)` para `S6-K2P0`/`S7-TPNONE`/`SuperTrend-p14x3-M15`, cada uno una `copy.deepcopy` INDEPENDIENTE del dict compartido de `CONFIGS_GOLIVE` (nunca alias), re-etiquetado `<id>-R`, magic remapeado a la banda fresca 726010/726020/726070 (`CHALLENGER_MAGIC_BASE=726000`), `volume=0.02` (`CHALLENGER_VOLUME`), y un `risk_gates` propio (dict nuevo por config, nunca compartido) con las 4 puertas: B1 `gap_wait_minutes=50` (diagnóstico previo, no barrido este fin de semana), B2 `news_blackout_minutes=30` (convención §4.3, no tuneado desde backtest), B3 `max_open_fichas=7` (leído en código de `data/analysis/monday_audit/a2_overlap.json['max_simultaneous_fichas']`, artefacto de Task 8, commit `cc70453` — NO escrito a mano, R5), B4 `min_sl_distance=0.50` (mínimo del broker; su incumplimiento es un BUG). TK-Momentum deliberadamente NO espejado: 3 configs, no 4. El brief (`task-4-brief.md`) se transcribió verbatim, incluidos los asserts de inmutabilidad (los dicts compartidos de `CONFIGS_GOLIVE` NO ganan `risk_gates` ni `volume`) y los de disjunción de banda (726xxx vs live/shadow/go-live/TK/TK-BW2, y fuera de los bloques reservados 722xxx/723xxx). TDD seguido: rojo confirmado (`ImportError: cannot import name 'CONFIGS_CHALLENGER'`) antes de implementar. 7/7 tests nuevos verdes (`pytest tests/scripts/test_run_live_20.py -k challenger`); suite dirigida `tests/scripts/test_run_live_20.py tests/live` → **244/244 verde** (9.91 s) con `SUPERVISOR_MAX_SPREAD_OPEN`/`SUPERVISOR_STALE_AUTORESTART` despojados del entorno (deuda técnica pre-existente documentada en el brief de Task 4, no introducida aquí); sin despojar esas dos variables reaparecen los mismos 7 fallos pre-existentes de `test_supervisor_env_*` ya conocidos desde el tag de rollback — verificado explícitamente que son los mismos, ninguno nuevo. **Prueba (a) `CONFIGS_LOCAL` byte-idéntico:** `git diff HEAD -- sentinel_engine/strategies/live_configs_20.py` muestra únicamente 92 líneas insertadas, CERO líneas eliminadas en todo el archivo (`grep -c '^-'` en el diff = 0); las primeras 606 líneas del archivo tras el cambio, normalizadas a LF, son byte-idénticas al blob de `HEAD` (comparación explícita en Python). **Prueba (b) copias independientes:** se mutó en vivo `CONFIGS_CHALLENGER[0]["kwargs"]`, `["risk_gates"]` y `["notes"]` tras importar el módulo y se verificó que `CONFIGS_GOLIVE['S6-K2P0']`, `CONFIGS_LOCAL['S6-K2P0']` y `CONFIGS_TOMACHINE['S6-K2P0']` permanecen sin `risk_gates`/`volume` y sin cambios — cero fuga. **Prueba (c) banda disjunta:** banda calculada en código = `{726010..726013, 726020..726023, 726070..726073}`, min/max = 726010/726073, disjunta de LIVE/SHADOW/GOLIVE/TK/LOCAL/TOMACHINE y fuera de 722000–723999 (todo verificado por script, no a mano). Archivo `tests/analysis/test_monday_audit.py` visto modificado en el working tree (edición concurrente de otra tarea, probablemente Task 9) — NO tocado, no incluido en el commit. Solo se tocaron `sentinel_engine/strategies/live_configs_20.py` y `tests/scripts/test_run_live_20.py` (Lane B). · commit `36979a3` (feat), commit de este tracker a continuación. Informe completo: `.superpowers/sdd/2026-07-25-monday-champion-challenger/task-4-report.md`.
- 2026-07-26 · Task 9 · `scripts/analysis/monday_audit/a3_a4_a5_stats.py` creado: `win_rate`, `profit_factor`, `autocorrelation`, `longest_streak`, `_summary` puras + `main()` que produce tres artefactos vía `loader.write_artifact`. TDD seguido: rojo confirmado (`ModuleNotFoundError: ... a3_a4_a5_stats`) antes de implementar; 16/16 tests verdes en el paquete completo `tests/analysis/test_monday_audit.py` (0.06–0.08 s). **Desviación documentada del brief:** el código Step-3 propuesto por el propio brief para `autocorrelation` (normalización con media/varianza ÚNICA de toda la serie) da −0,8 sobre el fixture verbatim del propio brief (`[1,-1,1,-1,1]`, lag=1) y por tanto NO pasa el test verbatim del mismo brief (`< -0.9`) — verificado a mano y con Python antes de tocar el código. Se implementó en su lugar la correlación de Pearson entre las dos subseries desplazadas por el lag, cada una normalizada por su propia media/varianza, que da exactamente −1,0 en ese fixture y sí satisface el test; ambas son definiciones válidas de autocorrelación muestral, se documentó la elección in-line en el docstring de la función. Real-data run sobre las 2347 posiciones reales: **A3** (atribución por exit reason) — el grueso del volumen de trades cae en EXIT_INITSL para S6/S7 (891 y 1104 respectivamente) pero EXIT_TRAIL tiene mejor WR y mejor mean_clp en ambas (S6: WR 57,1% vs 36,0%; S7: WR 47,6% vs 34,8%); SuperTrend solo tiene EXIT_STLINE (268, WR 22,8%, net 20,98MM). **A4** (autocorrelación lag-1..5 en orden de `t_out`) — S6 y S7 muestran autocorrelación lag-1 positiva y notable (+0,635 y +0,655) que decae a ~0 hacia lag-3+ (resultados se agrupan en rachas cortas, consistente con régimen de mercado); SuperTrend prácticamente independiente (lag-1 = −0,063). Rachas más largas de pérdidas: S6=27, S7=42, ST=13; de ganancias: S6=15, S7=15, ST=4. **A5 — declarado NO EVALUABLE como comparación 0,5 vs 0,6:** confirmado con código (no a mano) que el 100% de las 2347 filas de los tres CSV de reconstrucción real-tick de 7 meses tiene `spread=0.5`; CERO filas a 0,6 en cualquier estrategia o COMBINED (`at_0.6.n = 0` en las 4 vistas del artefacto). El filtro de spread 0,5 sigue validado ÚNICAMENTE por las cinco sesiones live citadas en el brief — esta auditoría de 7 meses no lo corrobora ni lo refuta, por ausencia total de evidencia en el dato (regla "lo no evaluable se declara no evaluable", no se manufacturó ninguna conclusión). Línea impresa por el script (A5 COMBINED): `@0.5 net=147.780.084 (n=2347) | @0.6 net=0 (n=0) | unfiltered=147.780.084`. Artefactos: `data/analysis/monday_audit/{a3_exit_reason,a4_serial,a5_spread_gate}.json`, tres líneas de excepción en `.gitignore` (una por archivo, mismo patrón que Task 7/8). `python -m pytest tests/analysis -q` → `16 passed in 0.06s`. Solo se tocaron `scripts/analysis/monday_audit/a3_a4_a5_stats.py`, `tests/analysis/test_monday_audit.py`, los tres JSON nuevos y `.gitignore` (Lane A); no se tocó `a1_maxdd.py`, `a2_overlap.py` ni `loader.py` (solo importados); no se tocó `sentinel_engine/strategies/live_configs_20.py` ni `tests/scripts/test_run_live_20.py` (edición concurrente de Task 4, vista modificada en el working tree y dejada intacta). · commit `d02e187` (feat), commit de este tracker a continuación. Informe completo: `.superpowers/sdd/2026-07-25-monday-champion-challenger/task-9-report.md`.
