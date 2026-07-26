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
| `max_open_fichas` (cap B3) | **7** (pico observado de fichas simultáneas, 2347 posiciones / 7 meses; alcanzado en 104 de 161 días de trading — no es un episodio único) | `data/analysis/monday_audit/a2_overlap.json` | Task 8 |
| maxDD @0.1 lot | _pendiente_ (estimación previa: −28,6 %) | `a1_maxdd.json` | Task 7 |
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
| 4 | `CONFIGS_CHALLENGER` — roster espejo 726xxx | B | Sonnet 5 high | `[ ]` | **desbloqueada por Task 8** — cap B3 = 7 ya disponible en `data/analysis/monday_audit/a2_overlap.json` |
| 5 | Plumbing del executor (gates en el OPEN) | B | **Opus 5 medium** | `[ ]` | la más compleja |
| 6 | Loader de auditoría (2.347 posiciones) | A | Sonnet 5 high | `[x]` | 4/4 tests verdes en `tests/analysis/test_monday_audit.py`. Smoke check contra datos reales: `2347 Counter({'S7-TPNONE': 1167, 'S6-K2P0': 912, 'SuperTrend-p14x3-M15': 268})` — coincide exacto con lo esperado en el brief. Commit `54355b9`. Gate completa (full-suite) del repo eximida por el controller por el mismo test lento patológico bajo investigación aparte (ver Task 1 y bitácora); se sustituyó por `python -m pytest tests/analysis -q` → `4 passed in 0.07s`. |
| 7 | A1 — verificar el maxDD | A | Sonnet 5 high | `[ ]` | |
| 8 | A2 — solape, correlación y cap B3 | A | Sonnet 5 high | `[x]` | `max_concurrency()` + `pearson()` en `scripts/analysis/monday_audit/a2_overlap.py`. TDD seguido: rojo confirmado (`ModuleNotFoundError: ... a2_overlap`) antes de implementar; 4/4 tests nuevos verdes, 8/8 en el paquete completo `tests/analysis/test_monday_audit.py`. Real-data run sobre las 2347 posiciones: **cap B3 = 7** (pico de fichas simultáneas, dentro del rango de cordura 1–9; sanity-checked: alcanzado en 104/161 días de trading, no es un episodio aislado). Correlación diaria de neto por par: S6\|S7 +0.730, S6\|ST +0.295, S7\|ST +0.047 (S6/S7 comparten buena parte de la misma apuesta; ST es casi independiente). Artefacto: `data/analysis/monday_audit/a2_overlap.json`. Suite completa del repo corrida una vez (foreground, ~8m50s): `13 failed, 1914 passed, 2 skipped` — los 13 fallos coinciden exactamente con la lista pre-existente conocida (`test_run_live_20.py` ×7, `test_supervisor_live.py` ×2, `test_chat.py` ×1, `test_web_positions.py` ×2, `test_search.py` ×1); ninguno introducido por esta tarea. Se abrió excepción de `.gitignore` para `data/analysis/monday_audit/a2_overlap.json` (artefacto de auditoría commiteado, no dato de mercado regenerable — mismo patrón que `data/live/news_calendar.csv` en Task 2). · commit `cc70453` (feat), commit de este tracker a continuación. **Desbloquea Task 4.** |
| 9 | A3+A4+A5 — atribución, serial, gate 0.5 | A | Sonnet 5 high | `[ ]` | |
| 10 | Máscaras retrospectivas — veredictos | A/B | Sonnet 5 high | `[ ]` | necesita 6, 8, 2 |
| 11 | Ensayo de revert | B | Sonnet 5 high | `[ ]` | |
| 12 | Despliegue máq1 | B | Sonnet 5 high | `[ ]` | 🙋 **pasos 5-6 = manos del user** |
| 13 | Documento del lunes | — | Opus 5 medium | `[ ]` | |
| 14 | Track C — entrada aleatoria | A | Sonnet 5 high | `[ ]` | **NO bloquea el lunes** |

---

## Criterio de aceptación (spec §9)

- [ ] Sleeve A corriendo, verificablemente idéntico a hoy (snapshot verde).
- [ ] Sleeve B corriendo a 0.02 con B1–B4 activos, en la banda 726xxx.
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
- 2026-07-26 · Task 8 · `scripts/analysis/monday_audit/a2_overlap.py` creado: `max_concurrency(intervals) -> (peak, hist)` barre el stream de posiciones fundidas como eventos ±1 en `t_in`/`t_out`, procesando salidas ANTES que entradas en un empate exacto de timestamp (un cierre-y-apertura al mismo instante es secuencial, no solapado) — orden `(t, delta)` con `-1` antes de `+1` por construcción del sort. `pearson(xs, ys)` correlación de Pearson pura (sin numpy), 0.0 si alguna serie tiene varianza cero. TDD seguido: rojo confirmado (`ModuleNotFoundError: No module named 'scripts.analysis.monday_audit.a2_overlap'`) antes de implementar; 4/4 tests nuevos verdes tras implementar, 8/8 en el paquete completo (`tests/analysis/test_monday_audit.py`, 0.07 s). Real-data run sobre las 2347 posiciones reales (S6 912 / S7 1167 / ST 268, vía `loader.load_positions`, sin re-simular nada): **cap B3 (`max_simultaneous_fichas`) = 7** — dentro de la cota de cordura del brief (1–9, dado que cada config corre a lo sumo 3 fichas). Verificado con un barrido adicional (no commiteado, solo diagnóstico) que el pico de 7 se alcanza en 104 de los 161 días de trading — no es un evento raro producido por un único episodio anómalo, es un nivel de solape rutinario en la práctica de las tres estrategias corriendo juntas. `p95_simultaneous` = `p99_simultaneous` = 7 (la métrica cuenta momentos-evento, no tiempo ponderado — así vino especificada en el brief). Correlación diaria de neto @0.67 lot (lot-invariante) por par: S6-K2P0\|S7-TPNONE +0.730, S6-K2P0\|SuperTrend-p14x3-M15 +0.295, S7-TPNONE\|SuperTrend-p14x3-M15 +0.047 — S6 y S7 comparten una porción sustancial de la misma apuesta direccional; SuperTrend es casi independiente de ambas. `pct_time_with_any_position` = 92.8 %. Artefacto escrito en `data/analysis/monday_audit/a2_overlap.json` vía `loader.write_artifact` (R5: cifra trazable a archivo, no a mano). Se abrió una excepción de `.gitignore` (bloque `data/*`) para `data/analysis/monday_audit/a2_overlap.json`, mismo patrón que la excepción de `data/live/news_calendar.csv` en Task 2 (artefacto de auditoría commiteado, no dato de mercado regenerable). Suite COMPLETA del repo corrida una vez en foreground (529.92 s ≈ 8m50s, sin waiver — instrucción explícita del controller esta vez): `13 failed, 1914 passed, 2 skipped, 20 deselected` — los 13 fallos coinciden uno a uno con la lista pre-existente conocida y verificada en el tag de rollback (`tests/scripts/test_run_live_20.py` ×7, `tests/scripts/test_supervisor_live.py` ×2, `tests/service/test_chat.py` ×1, `tests/service/test_web_positions.py` ×2, `tests/opt/test_search.py` ×1); ninguno introducido por esta tarea. Solo se tocaron `scripts/analysis/monday_audit/a2_overlap.py`, `tests/analysis/test_monday_audit.py`, `data/analysis/monday_audit/a2_overlap.json` y `.gitignore` (Lane A + la excepción puntual de gitignore); no se tocó `sentinel_engine/**` ni `scripts/live/**`; `loader.py` de Task 6 no se modificó, solo se importó (`load_positions`, `write_artifact`). **Task 4 queda desbloqueada: cap B3 = 7.** · commit `cc70453` (feat), commit de este tracker a continuación.
