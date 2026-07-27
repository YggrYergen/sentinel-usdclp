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
- **Procedimiento de rollback (ENSAYADO 2026-07-27, Task 11, commit `f65ff02`):**

**Nivel 1 — segundos, sin código.** Poner `SUPERVISOR_CONFIGS=local` y reiniciar el supervisor.
El retador deja de abrir; el campeón queda intacto. Las posiciones 726xxx abiertas se gestionan
hasta su salida re-armando `local+challenger` brevemente, o se cierran a mano.
*Ensayado:* confirmado indirectamente — `test_supervisor_env_local` prueba que
`SUPERVISOR_CONFIGS=local` resuelve `EXECUTOR_ARGV[-2:] == ["--configs","local"]` en el árbol
pre-retador. **No** ensayado contra un supervisor corriendo de verdad.

**Nivel 2 — un comando.** En `equipo1`, del más nuevo al más viejo (orden obligatorio para que
`git revert` aplique sin conflictos):

```
git -C D:/FOREX revert --no-edit 13c4898 826de0f 36979a3
```

- `13c4898` — executor: roster `local+challenger` + puertas en el OPEN (`scripts/live/run_live_20.py`)
- `826de0f` — lote del retador 0.02 → 0.1
- `36979a3` — `CONFIGS_CHALLENGER`, banda 726xxx (`sentinel_engine/strategies/live_configs_20.py`)

🔴 **Ruling del controlador sobre la duda de Task 11** (¿incluir `e065fca`, el módulo
`risk_gates.py`?): **NO.** `risk_gates.py`, `news_calendar.py` y `gap_wait.py` son módulos de
adición pura. El bloque de puertas del executor está guardado por
`if a.kind == "OPEN" and risk_gates:`, y `risk_gates` solo llega desde un config que lo lleve —
es decir, solo desde `CONFIGS_CHALLENGER`. Revertidos el roster y el plumbing, esos tres módulos
quedan inalcanzables: código muerto inocuo, no código vivo. Incluirlos en el revert añade
superficie de conflicto sin reducir riesgo. Se quedan.
⚠️ Los tres commits del Nivel 2 se revierten **juntos o ninguno**: revertir el plumbing dejando
el roster haría que un config pasara `risk_gates` a una firma que ya no lo acepta.

**Nivel 3 — nuclear.** `git -C D:/FOREX checkout pre-challenger-2026-07-25 -- sentinel_engine scripts`
y luego commit. Devuelve el código al estado pre-retador exactamente.
*Ensayado:* no ejecutado literalmente; sí se confirmó que el tag resuelve a un commit real,
checkout-able y con árbol funcional (el worktree del ensayo ES ese árbol y sus tests `local` pasan).

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
| 5 | Plumbing del executor (gates en el OPEN) | B | Opus 5 | `[x]` | commit `13c4898`. `GateCycleContext` + bloque de puertas en `execute_action` (guardado por `if a.kind == "OPEN" and risk_gates:`) + `_build_gate_ctx` + roster `local+challenger`. TDD: rojo confirmado antes de implementar (`AttributeError: ... GateCycleContext`, `TypeError: execute_action() got an unexpected keyword argument 'risk_gates'`). **251 passed** en `test_run_live_20.py + tests/live` (baseline 244, +7 = exactamente los tests nuevos); 760 passed en `tests/scripts + tests/live + tests/strategies`. Verificado por el controller tras integrar con Task 4 y el substrato regenerado: **271 passed** en `test_run_live_20.py + tests/live + tests/analysis`. Prueba de no-regresión del campeón: selección `-k "local or tomachine or golive"` 17→19, el diff son SOLO los dos tests nuevos, ningún test pre-existente cambió de resultado. Línea real emitida en dry-run: `[risk-gates] now=... spread=0.20000 spread_ok_since=... open_fichas=0 news_windows=36`, y `[RISK_GATE_SKIP] gate=B1 config=S6-K2P0-R ... only 1.3 of 50 min elapsed`; los configs campeón (sin `-R`) tomaron la ruta sin puertas, sin ninguna línea `[RISK_GATE_*]`. **Desviación declarada:** el brief usaba `sl=3900.0` pero el tick de `MockMT5` es bid 2000,0 / ask 2000,2, así que 3900 está atravesado para un LONG y disparaba la rama pre-existente `OPEN_SKIPPED_SL_CROSSED` antes de la línea de dry-run; se cambió a `sl=1990.0` en los 4 sitios y se documentó en el docstring del helper. Las aserciones no se tocaron. **No verificado:** nada contra un terminal MT5 real — todo mockeado, cero órdenes enviadas. |
| 6 | Loader de auditoría (2.347 posiciones) | A | Sonnet 5 high | `[x]` | 4/4 tests verdes en `tests/analysis/test_monday_audit.py`. Smoke check contra datos reales: `2347 Counter({'S7-TPNONE': 1167, 'S6-K2P0': 912, 'SuperTrend-p14x3-M15': 268})` — coincide exacto con lo esperado en el brief. Commit `54355b9`. Gate completa (full-suite) del repo eximida por el controller por el mismo test lento patológico bajo investigación aparte (ver Task 1 y bitácora); se sustituyó por `python -m pytest tests/analysis -q` → `4 passed in 0.07s`. |
| 7 | A1 — verificar el maxDD | A | Sonnet 5 high | `[x]` | `max_drawdown()` en `scripts/analysis/monday_audit/a1_maxdd.py`. TDD seguido: rojo confirmado (`ModuleNotFoundError: ... a1_maxdd`) antes de implementar; 3/3 tests nuevos verdes, 11/11 en `tests/analysis/test_monday_audit.py` (0.07 s). Real-data run sobre las 2347 posiciones (ordenadas por `t_out`, equity acumulada @0.1 lot, empates por `(t_out, strategy, t_in)`): **maxDD = −17 028 660,47 CLP = −28,57 % del balance inicial** (59,6 MM CLP), pico 23 949 863,73 CLP el 2026-03-23T02:32:53 → valle 6 921 203,26 CLP el 2026-04-28T21:57:52. **CONFIRMA** la estimación previa de −28,6 % — la diferencia (28,57 vs 28,6) es solo redondeo; el CLP del drawdown calculado coincide casi al peso con la regla de tres original (114 092 025 × 0,1/0,67 = 17 028 660,45 ≈ 17 028 660,47 calculado). Como fracción del pico de equity en vez del balance inicial, el DD es −20,38 %. Artefacto: `data/analysis/monday_audit/a1_maxdd.json`. Se agregó excepción de `.gitignore` para este archivo, mismo patrón que `a2_overlap.json` (Task 8). Solo se tocaron `scripts/analysis/monday_audit/a1_maxdd.py`, `tests/analysis/test_monday_audit.py` y `.gitignore` (Lane A); no se tocó `a2_overlap.py` (edición concurrente de Task 8, ya mergeada). · commit `ff86d97` (feat), commit de este tracker a continuación. |
| 8 | A2 — solape, correlación y cap B3 | A | Sonnet 5 high | `[x]` | `max_concurrency()` + `pearson()` en `scripts/analysis/monday_audit/a2_overlap.py`. TDD seguido: rojo confirmado (`ModuleNotFoundError: ... a2_overlap`) antes de implementar; 4/4 tests nuevos verdes, 8/8 en el paquete completo `tests/analysis/test_monday_audit.py`. Real-data run sobre las 2347 posiciones: **cap B3 = 7** (pico de fichas simultáneas, dentro del rango de cordura 1–9; sanity-checked: alcanzado en 104/161 días de trading, no es un episodio aislado). Correlación diaria de neto por par: S6\|S7 +0.730, S6\|ST +0.295, S7\|ST +0.047 (S6/S7 comparten buena parte de la misma apuesta; ST es casi independiente). Artefacto: `data/analysis/monday_audit/a2_overlap.json`. Suite completa del repo corrida una vez (foreground, ~8m50s): `13 failed, 1914 passed, 2 skipped` — los 13 fallos coinciden exactamente con la lista pre-existente conocida (`test_run_live_20.py` ×7, `test_supervisor_live.py` ×2, `test_chat.py` ×1, `test_web_positions.py` ×2, `test_search.py` ×1); ninguno introducido por esta tarea. Se abrió excepción de `.gitignore` para `data/analysis/monday_audit/a2_overlap.json` (artefacto de auditoría commiteado, no dato de mercado regenerable — mismo patrón que `data/live/news_calendar.csv` en Task 2). · commit `cc70453` (feat), commit de este tracker a continuación. **Desbloquea Task 4.** |
| 9 | A3+A4+A5 — atribución, serial, gate 0.5 | A | Sonnet 5 high | `[x]` | `scripts/analysis/monday_audit/a3_a4_a5_stats.py`. 16/16 tests verdes en `tests/analysis/test_monday_audit.py`. **A3** (atribución por `(estrategia, reason)`): S6-K2P0 EXIT_INITSL n=891 net=89,68MM CLP (WR 36,0%) + EXIT_TRAIL n=21 net=3,95MM (WR 57,1%); S7-TPNONE EXIT_INITSL n=1104 net=24,56MM (WR 34,8%) + EXIT_TRAIL n=63 net=8,61MM (WR 47,6%); SuperTrend EXIT_STLINE n=268 net=20,98MM (WR 22,8%, único reason — no tiene trailing). **A4** (autocorrelación lag-1..5 en orden de `t_out`): S6 lag1=+0,635, S7 lag1=+0,655 (positiva y decayendo a ~0 en lag3+ — los resultados sí se agrupan en rachas de corto plazo, consistente con régimen); SuperTrend lag1=−0,063 (prácticamente independiente). Rachas más largas: pérdidas S6=27, S7=42, ST=13; ganancias S6=15, S7=15, ST=4. **A5 — NO EVALUABLE como comparación 0,5 vs 0,6**: las 2347 posiciones reales tienen spread=0,5 en el 100% de las filas (`at_0.6.n = 0` en las 4 vistas — por estrategia y COMBINED); no hay ni una fila a 0,6 en los CSV de reconstrucción real-tick de 7 meses. El filtro sigue validado únicamente por las cinco sesiones live citadas en el brief; esta auditoría NO lo corrobora ni lo refuta por falta de evidencia en el dato (regla "lo no evaluable se declara no evaluable"). A5 COMBINED (línea impresa por el script): `@0.5 net=147.780.084 (n=2347) \| @0.6 net=0 (n=0) \| unfiltered=147.780.084`. **Desviación documentada del brief:** el código Step-3 del brief para `autocorrelation` (media/varianza globales de la serie) da −0,8 en el propio fixture verbatim del brief (`[1,-1,1,-1,1]`, lag=1) y **no pasa** el test verbatim del propio brief (`< -0.9`); se implementó en su lugar la correlación de Pearson entre las dos subseries desplazadas por el lag (cada una normalizada por su propia media/varianza), que da exactamente −1,0 en ese fixture y sí satisface el test. Ambas fórmulas son válidas en la literatura; se documentó la discrepancia in-line en el código y en el reporte de la tarea. Artefactos: `data/analysis/monday_audit/{a3_exit_reason,a4_serial,a5_spread_gate}.json`, excepción de `.gitignore` una línea por archivo (mismo patrón que Task 7/8). `python -m pytest tests/analysis -q` → `16 passed in 0.06s`. Solo se tocaron `scripts/analysis/monday_audit/a3_a4_a5_stats.py`, `tests/analysis/test_monday_audit.py`, `data/analysis/monday_audit/{a3,a4,a5}*.json` y `.gitignore` (Lane A); no se tocó `a1_maxdd.py`, `a2_overlap.py` ni `loader.py`. · commit `d02e187` (feat), commit de este tracker a continuación. |
| 10 | Máscaras retrospectivas — veredictos | A/B | Sonnet 5 high | `[x]` | commit `2827524` (+ `3a241c0` session_clock del controller). B1 reescrito sobre reaperturas MEDIDAS (145, del stream de barras; el proxy de entradas inventaba 415). Veredictos: B1 NO-VETO (209 vetadas, +20,01%), B2 0 descartes (calendario solo NFP), B3 0 descartes, B4 NO EVALUABLE (CSV sin columna SL). ⚠️ Sujeto a re-run por reparación de substrato (ver §Extensión 2026-07-27) |
| 11 | Ensayo de revert | B | Sonnet 5 high | `[x]` | commit `f65ff02`. `tests/scripts/test_challenger_rollback.py` 2/2 verde. Ensayo real en worktree scratch sobre el tag `pre-challenger-2026-07-25` (`dfdc4d7`): `test_run_live_20.py -k "local"` **5/5 passed** — el tag es un punto de rollback genuinamente ejecutable, no una etiqueta. Hubo que despojar `SUPERVISOR_MAX_SPREAD_OPEN`/`SUPERVISOR_STALE_AUTORESTART` del proceso pytest (fuga conocida del host vivo, deuda pre-existente, no introducida aquí). Worktree eliminado y verificado (`git worktree list` limpio). Procedimiento de 3 niveles + ruling sobre `e065fca` → §Rollback point. **Desviación del plan:** los Steps 5-6 originales escribían y commiteaban el tracker; reasignados al CONTROLADOR (fichero compartido), el agente commiteó solo su test |
| 12 | Despliegue máq1 | B | Sonnet 5 high | `[ ]` | 🙋 **pasos 5-6 = manos del user**. Recomendado tras R4 (el cap B3=7 se calibró sobre substrato incompleto y podría moverse); timing = decisión del user |
| 13 | Documento del lunes | — | **Opus 5 high** | `[ ]` | 🔴 **GATEADA por R3+R4** (plan 2026-07-27-substrate-repair). CUATRO correcciones narrativas obligatorias: corr ST ya no "casi independiente" (0,35); grilla mensual regenerada; reporte mensual sin snapshot previo; 🆕 disclosure bug reverse+fills con números del re-run |
| 14 | Track C — entrada aleatoria | A | Sonnet 5 high | `[ ]` | **NO bloquea el lunes** |
| 15 | Escalera de distancia de SL — **solo backtest** | A | Sonnet 5 high | `[ ]` | **NO bloquea el lunes.** Añadida 2026-07-26 por decisión del user. Correr sobre substrato REPARADO |
| 16 | Curva del codo de la espera post-apertura (B1) — **solo backtest** | A | Sonnet 5 high | `[x]` | commit `c402976`. Curva N=2..6 en BARRAS: N3 +32,67% > N4 +20,01% > N2 +13,27% > N5 +9,72% > N6 −15,24%. Joroba, no codo; S7 se desploma −93,3% en N6. Robustez follow-up commit `059a5a2`: la mejora NO sobrevive consistencia mensual (sin 2026-02 los 5 peldaños negativos); ranking SÍ sobrevive top-K; lo vetado ES peor (mediana/WR/PF) en N2-N5. ⚠️ Sujeto a re-run por reparación de substrato |

## 🔴 EXTENSIÓN 2026-07-27 — reparación de substrato (BLOQUEA Task 13)

**Plan:** `docs/superpowers/plans/2026-07-27-substrate-repair-and-program-extension.md` (leer sus
§ROUTING/§SKILLS/§NORMAS antes de despachar — van verbatim en cada brief).
**Motivo:** dos bugs del instrumento hallados 2026-07-27, verificados: (1) `backtest.py:164` no
empareja los cierres `"reverse"` — ~504 S6 + ~240 S7 ausentes de las CSV (~24% de los cierres);
(2) `resolve()` inventa fills cuando ningún tick cruza el nivel — 36% de los EXIT_INITSL de S6
con exit_fill en dirección de ganancia. Todo Track A queda sujeto a re-run; el veredicto vivo de
50 min y el código vivo NO están afectados.

| # | Tarea | Modelo | Estado | Notas |
|---|---|---|---|---|
| R1 | Pairing "reverse" en `run_ladder` | Sonnet 5 high | `[x]` | commit `fadf1ec`. Evento `reverse` MEDIDO antes de implementar: es **uno por ficha** (504/504 traen clave `ficha`; 168 barras × 3 fichas), forma idéntica a `EXIT*`/`time_stop`, ninguno con `same_bar_fallback`. Por eso la implementación mínima fue ampliar la CONDICIÓN de la rama existente (1 línea), sin duplicar el bloque de emparejamiento. TDD: rojo confirmado (3 failed / 1 passed) antes de tocar `backtest.py`. 4 tests nuevos en `tests/analysis/test_realtick_pairing.py`; `tests/analysis -q` → **61 passed** (baseline medido 57 + 4). Impacto in-memory: **504** filas `reason="reverse"` en S6-K2P0, **240** en S7-TPNONE (coincide 1:1 con los eventos crudos: ningún reverse se perdió) |
| R3a | 🆕 Snapshot inmutable pre-reparación | Sonnet 5 high | `[x]` | commit `b3c53e2` (commiteado por el CONTROLADOR: requería excepción en `.gitignore`). `data/analysis/pre_repair_snapshot/` con los **12** artefactos que Track A usó como base (3 CSV + 8 JSON + el reporte mensual markdown, que `backtest.py` sobrescribe al correr) + `MANIFEST.json` (sha256/bytes/mtime + resúmenes calculados por código) + `baseline_rows.csv` (multiset `(strategy,t_in,ficha,reason,net)` de las 2.347 filas, contra el que R3 hará el diff). Contraste con el tracker: **912 / 1167 / 268 = 2347** filas y neto **147.780.084,05** CLP — coincidencia exacta, diff 0,00. Integridad de los orígenes re-verificada por hash tras copiar. Tarea creada en esta sesión: es el Step 1 de R3, extraído para que el "antes" quedara preservado ANTES de que nada regenerara (el fallo del 2026-07-26 no se repite) |
| R2 | Jerarquía de fills + `fill_source` + asserts | Sonnet 5 high | `[!]` **NO SE IMPLEMENTA** | 🔴 **Cerrada por REFUTACIÓN, decisión del user 2026-07-27.** R2 escaló BLOCKED en su Step 1 sin tocar ningún fichero (`backtest.py` intacto, 61 passed). La población que iba a instrumentar (`level_uncrossed`) es de **0 filas medidas**: 891/891 y 1104/1104 cruzan dentro de su barra. Implementarla sería código sin objeto. Ver §H3 y la §"Remedio archivado" abajo, que deja escrito QUÉ implementar si algún día aparece el problema |
| R2-bis | 🆕 Separar stop GENUINO vs stop YA LEVANTADO | Sonnet 5 high | `[~]` | Creada por decisión del user 2026-07-27 tras H3. Corrige la atribución **en la capa de análisis** (`backtest.py`), NO en el motor: recalcula el stop inicial genuino desde la barra de entrada (importando la función del motor, no re-implementándola) y separa `EXIT_INITSL` en `EXIT_INITSL` (genuino) vs `EXIT_SL_RAISED`. Esperado según medición de R2: S6 12 genuinas / 879 levantadas; S7 3 / 1101 |
| R3 | Regenerar + re-correr Track A + diff | Sonnet 5 high | `[ ]` | Step 1 (snapshot) YA HECHO por R3a. 🔴 **Corrección del controlador a la expectativa del plan:** el plan decía "las 2.347 filas viejas deben seguir existiendo con su mismo net, si una cambió → PARAR". Eso es previsiblemente FALSO: el test de R1 demostró que antes del fix las fichas huérfanas de una señal revertida eran emparejadas por eventos de salida POSTERIORES (una fila salía con el `entry_bid` de la señal revertida). Es decir R1 no solo AÑADE filas: **re-atribuye** algunas existentes. La verificación correcta es CUANTIFICAR (cuántas idénticas / cuántas re-atribuidas / por qué), no un gate pass-fail que daría falsa alarma |
| R4 | Veredictos sobre el diff | **Opus 5 high** | `[ ]` | análisis de resultados = Opus SIEMPRE; puede mover cap B3 del retador |

### 🔴🔴 H3 — El "bug 2" NO EXISTE, y lo que hay en su lugar es una ETIQUETA ENGAÑOSA (R2, 2026-07-27)

R2 se detuvo en su Step 1 y escaló (BLOCKED), tal como el brief le ordenaba ante un tercer bug.
No tocó ningún fichero: `backtest.py` intacto, `tests/analysis -q` sigue en 61 passed.

**Lo que se creía (plan) y queda REFUTADO:** «`resolve()` inventa fills cuando ningún tick cruza
el nivel del stop». **Falso en este dataset.** Sobre el conjunto resuelto:
`EXIT_INITSL` de S6-K2P0 **891/891 cruzan (100 %)**; de S7-TPNONE **1104/1104 cruzan (100 %)**.
El fallback de barra-siguiente **no se dispara nunca**. En la población CRUDA (pre-gate) hay solo
**3** filas no-cruzadas en total (S7), con gap de 0,0155 USD, y las 3 cruzan en la ventana
siguiente. La población `level_uncrossed` que R2 iba a instrumentar es, medida, de **0 filas**.

**Lo que SÍ explica el 36 %:** el motor etiqueta `EXIT_INITSL` a cierres cuyo nivel **ya había
sido levantado** por trailing o por breakeven-at-R en una barra ANTERIOR. El bloque de
`EXIT_INITSL` (`emasar_variant.py:784-793`) se ejecuta antes del trailing de SU barra, pero
compara contra `sl_check`, que viene de `server_sl_by_tag[tag] = f.sl` (línea 1093) — es decir,
`f.sl` **tal como quedó tras los ajustes de barras previas**. No distingue "stop intacto" de
"stop ya subido".

Recalculando el stop inicial genuino con la fórmula real de `_sl_inicial` (líneas 621-624,
`k=init_sl_range_k=2.5`) desde la barra de entrada y comparándolo con el nivel emitido:

| | filas `EXIT_INITSL` | stop GENUINO | stop YA LEVANTADO | rentables |
|---|---:|---:|---:|---|
| S6-K2P0 | 891 | **12** | **879 (98,7 %)** | 321, **100 % del grupo levantado** |
| S7-TPNONE | 1104 | **3** | **1101 (99,7 %)** | 384, **100 % del grupo levantado** |

**0 de las 12 y 0 de las 3 filas genuinas son rentables** — coherente: un stop inicial intacto
siempre debe ser pérdida. Dos casos extremos verificados contra barras crudas: el precio se movió
241 USD (S6) y 144 USD (S7) A FAVOR y luego revirtió hasta tocar exactamente el nivel reportado —
patrón inequívoco de stop trailing ya desplazado, no de stop inicial.

🟢 **NO es un bug de código vivo.** El motor sale al nivel correcto y los fills son reales: neto,
PF, WR global, maxDD **no cambian por esto**. Lo que está mal es la ETIQUETA `motivo`, que es
demasiado gruesa.

🔴 **Consecuencia para la entrega del lunes — A3 está mal narrado.** El tracker (Task 9) dice
«S6-K2P0 EXIT_INITSL n=891 net=89,68MM (WR 36,0 %) + EXIT_TRAIL n=21 (WR 57,1 %)», leído como
"el grueso son stop-outs iniciales". Realmente **879 de esos 891 son salidas por stop levantado**
(trailing/BE), y `EXIT_TRAIL` sale con solo 21 filas porque el motor solo usa ese motivo cuando
la subida y el toque ocurren en la MISMA barra (21/21 y 63/63 son `same_bar`). La atribución por
motivo de salida del documento del lunes, tal como está, **induce a error**.

### 📦 Remedio ARCHIVADO — qué implementar si el problema de fills llegara a aparecer

Decisión explícita del user (2026-07-27): **no se implementa**, porque la población medida es de
0 filas. Se deja escrito para que, si alguna vez aparece, no haya que re-diagnosticar nada.

**Síntoma que lo activaría:** que `resolve()` (`scripts/analysis/realtick_bt/backtest.py`) empiece
a caer en su rama de fallback — para `reason in LEVEL_EXITS`, ningún tick de la ventana
`[t_out, t_out+900)` cruza el nivel, y entonces cierra en silencio al primer tick de la barra
SIGUIENTE. Eso produce un fill que ningún tick respalda. **Cómo detectarlo:** contar filas de
salida de nivel cuyo `exit_fill` quede en dirección de GANANCIA respecto de la entrada siendo un
stop. Hoy ese conteo es 0 tras descontar el fenómeno de la etiqueta (H3).

**Qué implementar entonces (diseño ya cerrado, no hay que volver a pensarlo):**

1. **Columna `fill_source`** en cada fila del CSV, con vocabulario `tick` (un tick real cruzó el
   nivel; `exit_fill` = precio de ese tick) · `level_uncrossed` (la ventana tiene ticks pero
   ninguno cruzó; se conserva el cierre a barra siguiente **pero la fila queda MARCADA**, con lo
   que deja de ser un fill inventado en silencio y pasa a ser una discrepancia declarada) ·
   `bar_close` (salidas que no son de nivel: `reverse`, `time_stop`, `EXIT_STFLIP`, `same_bar`).
2. **Assert aritmético** que ABORTA la corrida (no un warning, no saltarse la fila): para
   `fill_source == "tick"` y reason de stop (`EXIT_INITSL`, `EXIT_SL_RAISED`, `EXIT_TRAIL`,
   `EXIT_STLINE` — **no** `EXIT_TP`, que es lo contrario): long ⇒ `exit_fill <= level + SLIP_TOL`;
   short ⇒ `exit_fill >= level - SLIP_TOL`. `SLIP_TOL = 0.05`.
3. **Sensibilidad** a reportar junto al resultado: neto con la política vigente vs neto
   contrafactual si las filas `level_uncrossed` se cerraran EN el nivel.

**Lo que NO hay que implementar nunca en este lake:** la rama "hueco de cobertura → reconstruir
bucket M1 al vuelo" ni los valores `m1` / `level_assumed`. H1 lo mide: **0 ventanas vacías de
13.236**, mínimo 441 ticks por barra. No hay `_bars_M1.parquet` en el lake y no hace falta.
Sería código muerto por construcción.

### 📌 Item abierto para el programa post-lunes (decisión del user 2026-07-27)

**Afinar la etiqueta de salida del MOTOR.** `emasar_variant.py` marca `EXIT_INITSL` sin distinguir
un stop intacto de uno ya levantado por trailing/BE (ver §H3). R2-bis lo corrige en la capa de
análisis, que es lo que la entrega del lunes necesita, pero el motor sigue emitiendo la etiqueta
gruesa. Arreglarlo en el motor **va sobre COPIA independiente (R1-bis), jamás sobre el original**,
y por tanto pertenece al programa del catálogo v3, no a la entrega del lunes.

### 🔴 Hallazgos del pre-flight scan 2026-07-27 (medidos por el controlador, modifican la spec)

**H1 — NO existen huecos de cobertura de ticks.** Sobre las 13.236 barras M15 del dataset
contrastadas contra los 52.599.197 ticks del lake: ventanas `[t, t+900)` con CERO ticks =
**0 de 13.236**; mínimo de ticks en una ventana = **441**; mediana 3.262; ventanas con <10 ticks = 0.
→ La rama «hueco de cobertura → reconstruir bucket M1 al vuelo» que el plan de R2 describía
**no puede dispararse nunca en este dataset**. Implementarla sería código muerto. El vocabulario
de `fill_source` se reduce a `tick` / `level_uncrossed` / `bar_close`.

**H2 — barras y ticks son fuentes MT5 distintas y casi coinciden.** Las barras salen de
`copy_rates_range` y los ticks de `copy_ticks_range`. Contraste bar-a-bar: coincidencia EXACTA
low 12.682/13.236 (95,8 %), high 12.657/13.236 (95,6 %). Donde discrepan, el gap mediano es
**0,02 USD** (p95 0,06; máx 0,43 en el low). → **Demasiado pequeño y demasiado poco frecuente
para explicar el 36 % de `EXIT_INITSL` de S6 con fill en dirección de ganancia.** La hipótesis
del plan («hueco de cobertura») queda REFUTADA por H1, y el desajuste de fuentes es insuficiente:
**la causa raíz del bug 2 sigue SIN establecerse** y R2 debe diagnosticarla, no asumirla.

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
- 2026-07-27 · Task R1 · `run_ladder` ahora empareja los cierres `"reverse"`. Medición previa obligatoria (Step 1 del plan) ejecutada y pegada en el reporte: el evento `reverse` que emite `emasar_variant.py:1140-1151` es **uno por ficha** (504/504 con clave `ficha`, 168 barras × 3 fichas, `precio` = cierre de la barra, ninguno con `same_bar_fallback`) — forma idéntica a los `EXIT*` que la rama ya procesaba. Por eso la implementación mínima resultó ser ampliar la condición existente (`... or motivo == "reverse"`), una sola línea, reutilizando la maquinaria de emparejamiento (`open_pos.get(last)` + barrido de fallback + `pop`) en vez de duplicar el bloque. TDD estricto: rojo verificado antes de tocar el fichero (3 failed / 1 passed; el test que no depende del fix ya pasaba). Verde: 4/4 en `tests/analysis/test_realtick_pairing.py`, `tests/analysis -q` → 61 passed contra baseline medido de 57. Impacto in-memory (sin regenerar CSV, prohibido — es R3): 504 filas `reverse` en S6-K2P0, 240 en S7-TPNONE. `resolve()` no se tocó: `"reverse"` ∉ `LEVEL_EXITS`, aserción explícita en el test. · commit `fadf1ec`
- 2026-07-27 · Task 11 · Ensayo de revert. `tests/scripts/test_challenger_rollback.py` (2 tests: el roster campeón coincide con lo que se desplegó el 2026-07-22, y campeón/retador no comparten identidad de objeto ni `risk_gates`) → 2/2 verde. Ensayo real: worktree scratch sobre el tag `pre-challenger-2026-07-25` (`dfdc4d7`) y `pytest tests/scripts/test_run_live_20.py -k "local"` → **5/5 passed**, es decir el tag no es una etiqueta sino un árbol ejecutable y verde. Para lograrlo hubo que despojar del entorno del proceso pytest `SUPERVISOR_MAX_SPREAD_OPEN` y `SUPERVISOR_STALE_AUTORESTART` (fuga de variables `setx`-eadas del host vivo — deuda pre-existente conocida, documentada, NO introducida por esta tarea). Worktree eliminado y verificado con `git worktree list`. Procedimiento de 3 niveles registrado en §Rollback point con los SHA reales del Nivel 2 (`13c4898 826de0f 36979a3`, del más nuevo al más viejo). **Duda del agente resuelta por el controlador:** `e065fca` (`risk_gates.py`) NO entra en el Nivel 2 — es adición pura e inalcanzable una vez revertidos roster y plumbing, porque el bloque de puertas está guardado por `if a.kind == "OPEN" and risk_gates:` y `risk_gates` solo llega desde `CONFIGS_CHALLENGER`. **Desviación del plan declarada:** los Steps 5-6 escribían y commiteaban el tracker; el controlador los reasignó a sí mismo (fichero compartido, §NORMAS) y el agente commiteó solo su test. · commit `f65ff02`
- 2026-07-27 · Task R3a (nueva) · Snapshot inmutable del substrato PRE-reparación, extraído del Step 1 de R3 y adelantado para que el "antes" quedara preservado antes de que cualquier cosa regenerara. `data/analysis/pre_repair_snapshot/` con los 12 artefactos base de Track A: los 3 `positions_*.csv`, los 8 JSON de `monday_audit/`, y `docs/REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md` — este último es el que `backtest.py` sobrescribe como efecto colateral de correr, y cuya pérdida sin snapshot el 2026-07-26 dejó la entrega sin diff viejo-contra-nuevo. Cada copia verificada por sha256 origen-vs-destino, y los orígenes re-hasheados al final para probar que nadie los tocó (12/12, verificación independiente con `sha256sum` del sistema además del hashing del propio script). `MANIFEST.json` lleva sha256/bytes/mtime por fichero más resúmenes calculados por código (n_rows, suma de `net_067lot_clp`, histogramas por `reason` y por `month`). `baseline_rows.csv` (2347 filas + cabecera) fija el multiset `(strategy, t_in, ficha, reason, net_067lot_clp)` con los valores copiados como TEXTO verbatim, sin round-trip por float ni datetime, para que el diff de R3 sea byte-a-byte. Contraste contra el tracker: 912 / 1167 / 268 = 2347 filas y neto 147.780.084,05 CLP, diff 0,00. No commiteó (requería excepción de `.gitignore`, fichero del controlador); commiteado por el controlador junto con la excepción, más una excepción faltante para `b1_robustness.json`, que estaba trackeado pero sin regla que lo protegiera. · commit `b3c53e2`
- 2026-07-27 · Task R2 · **CERRADA SIN IMPLEMENTAR, por refutación.** El agente ejecutó el Step 1 (diagnóstico) y escaló BLOCKED sin tocar un solo fichero, exactamente como el brief le ordenaba ante el hallazgo de un tercer bug — `backtest.py` intacto, `tests/analysis -q` sigue en 61 passed, ningún commit. Lo medido: el fallback de nivel-no-cruzado de `resolve()` **no se dispara nunca** (`EXIT_INITSL` cruza 891/891 en S6-K2P0 y 1104/1104 en S7-TPNONE dentro de su propia barra; en la población cruda pre-gate hay 3 filas no-cruzadas en total, gap 0,0155 USD, y las 3 cruzan en la ventana siguiente). La premisa del plan («`resolve()` inventa fills») queda REFUTADA para este dataset. El 36 % de `EXIT_INITSL` rentables se explica al 98,7 % (S6) y 99,7 % (S7) por un fenómeno distinto: el motor etiqueta `EXIT_INITSL` a stops ya levantados por trailing/BE en barras anteriores, porque compara contra `sl_check` ← `server_sl_by_tag[tag] = f.sl` (línea 1093), que arrastra los ajustes previos. 0 de las 12 (S6) y 0 de las 3 (S7) filas de stop genuino son rentables; el 100 % de las rentables está en el grupo levantado. **Decisión del user:** no implementar la instrumentación (`fill_source`, assert direccional) por población inexistente, y dejar archivado en el tracker el diseño exacto a implementar si el problema llegara a aparecer → §"Remedio archivado". No es bug de código vivo: los fills son reales y neto/PF/WR/maxDD no cambian por esto. · sin commit (por diseño)
- 2026-07-27 · Task R2-bis (nueva) · Creada por decisión del user tras H3, para corregir la atribución por motivo de salida **en la capa de análisis** y que la entrega del lunes no induzca a error. Separa `EXIT_INITSL` en `EXIT_INITSL` (stop inicial genuino, recalculado desde la barra de entrada con la función del propio motor, importada y no re-implementada, con `k=init_sl_range_k` leído de los kwargs vivos) y `EXIT_SL_RAISED` (stop ya levantado y tocado después). El motor NO se toca: afinar su etiqueta se registró como item del programa post-lunes, sobre copia independiente (R1-bis). · despachada
