# Divergencias entre nuestro motor de backtest y el motor faulty en vivo

**Qué es esto.** El catálogo exacto de en qué se comportan distinto
`scripts/analysis/realtick_bt/backtest.py` (el harness que veníamos construyendo para los
backtests) y el ejecutor que corrió las estrategias en la cuenta 902
(tag `engine-faulty-tomachine-902` → `b113eb7`). Cada entrada lleva el sitio de código de ambos
lados, el mecanismo por el que produce resultados distintos, y qué hace falta para cerrarla.

**Para qué.** Los dos hitos de paridad dependen de cerrar esta lista:

| Hito | Sustrato | Objetivo | Estado |
|---|---|---|---|
| **P-CAP** | ticks Capitaria, ventana 902 | **bit-idéntico** contra el historial de la 902 — requisito duro, sin él no se procede | ⏳ |
| **P-AVA** | ticks AVA, misma ventana | lo más par posible; bit-idéntico es la meta asintótica, no el criterio de paso | ⏳ |

Ambos se persisten y documentan **antes** de tocar el motor. Son el instrumento con el que se
medirá toda mejora posterior: sin ellos, cualquier ganancia atribuida a un cambio es indistinguible
de un artefacto del harness.

---

## Resumen

| # | Divergencia | Efecto | Muerde en |
|---|---|---|---|
| **D1** | Entrada emparejada con el SL inicial vs con el SL ya trailleado | salidas a −17,5 USD vs −1,00 USD | ambos |
| **D2** | Reintento de apertura: 2 barras vs ciclos de 15 s indefinidos | posiciones descartadas → infra-generación | ambos |
| **D3** | 3 fichas fijas vs `active_fichas=1` | ×3 en volumen y en cuenta de posiciones | ambos |
| **D4** | Sin re-entradas secuenciales | 49 señales → 49 posiciones vs → 152 | ambos |
| **D5** | Gate de spread: **banda** `[0,45 ; 0,55]` vs **cap** `≤ 0,50` | invisible en Capitaria; **aniquila 3 años de AVA** | 🔴 **AVA** |
| **D6** | Sin time-gate 18:00–18:45 | 4.790 `TIME_GATE_SKIP` no modelados | ambos |
| **D7** | Salida por barrido intra-barra vs SL server-side + trail a cierre de barra | 5,8 % ya medido | ambos |
| **D8** | Sin descarte por SL ya cruzado | 943 aperturas que el vivo NO hizo | ambos |
| **D9** | Sin cierres manuales | libera cupo → cambia toda la secuencia | ambos |
| **D10** | Constantes `LIVE` obsoletas en el reporte | falsa medición de fidelidad | ambos |

---

## D1 · La entrada se empareja con un SL distinto (D-39)

**Harness.** `backtest.py:344-364` — la entrada se fija en el **cierre de barra**
(`tc = bar_times[bi] + BAR_SEC`), con `entry_fill = eask if side_l=="L" else ebid`. El nivel de
salida que se le empareja es el que emitió `simular_variant`, y `run_ladder()` llega a
**reconstruir el SL genuino de la barra de entrada** (`_sl_inicial_genuine`, `backtest.py:162-219`)
para distinguir `EXIT_INITSL` de `EXIT_SL_RAISED`. Es decir: el harness se esfuerza activamente en
emparejar cada entrada con **su** SL inicial.

**Vivo.** `reconciler.py:296-299` emite `OPEN` con `sl=d["sl"]` — el SL **actual** del sim, ya
arrastrado por el trail — y `price_ref=d["entry"]`, declarado en `reconciler.py:60` como *«sim
entry/stop reference (for logs)»*. `run_live_20.py:786` manda la orden con `price = tick.ask/bid`.
**`price_ref` no se usa nunca.**

**Mecanismo.** El vivo abre a mercado *ahora* con un stop calculado para una entrada *de antes*. Si
el precio ya corrió a favor, la posición nace con el stop a un pelo. Salidas reales agrupadas en
**−1,00 USD** (= ancho exacto del trail plano) en vez de los ~17,5 USD del SL inicial; duración
mediana **169 s**; **41,7 %** bajo el minuto.

**Para cerrarla:** el harness debe emitir la apertura con el SL vigente en el instante de
reconciliación, no con el de la barra de señal.

## D2 · La ventana de reintento — y el comentario que revela el problema de raíz

**Harness.** `MAX_RETRY_BARS = 1` (`backtest.py:46`), aplicado en `resolve()` como
`hi = min(hi, lo + 1 + MAX_RETRY_BARS)`: se escanean **la barra de señal y una siguiente**. Si
ninguna admite fill, `resolve()` hace `return None` y **la posición se descarta**.

**Vivo.** El reconciliador re-desea la ficha **en cada ciclo de 15 s**, indefinidamente, mientras el
sim la mantenga abierta. De ahí las hasta 8 aperturas secuenciales por barra-señal.

🔴 **El comentario de `backtest.py:47` dice literalmente:**

> `(>1-bar delays pair a late entry with the sim's stale SL -> artifact.)`

El harness **conoce el comportamiento de D1 y lo suprime a propósito**, clasificándolo como
artefacto. Es decir: la divergencia central no es un olvido, es una decisión de diseño tomada
cuando se creía que el emparejamiento tardío era un defecto del harness — y resulta ser
exactamente lo que hace el motor de producción. **Cerrar D1 exige revertir esta decisión, no sólo
subir la constante.**

## D3 · Fichas: 3 fijas contra 1

**Harness.** `run_ladder()` (`backtest.py:258`) abre siempre
`"fichas": {"F1", "F2", "F3"}`, sin leer `active_fichas`.

**Vivo.** `active_fichas=1` (`live_configs_20.py:568`, assert `:597`). Magics de apertura
observados: `724011` (84) y `724071` (68); **`724012` y `724013` no aparecen jamás**.

## D4 · No existen las re-entradas secuenciales

**Harness.** Una señal produce una posición por ficha, y se cierra cuando su nivel se cruza. No hay
mecanismo de re-apertura.

**Vivo.** Tras cada salida por SL, si el sim sigue deseando la ficha, el siguiente ciclo la vuelve a
abrir. Por eso **49 barras-señal de S6 y 42 de SuperTrend produjeron 152 posiciones**, con
concurrencia máxima 1 por estrategia y siempre en la misma dirección.

Esta es la razón estructural de que el denominador de A6 sean **barras-señal (49/42)** y no
posiciones (152): son re-entradas de una misma señal, no señales distintas.

## D5 · 🔴 El gate de spread: banda contra cap — invisible en Capitaria, letal en AVA

**Harness.** `backtest.py:358` → `if abs(sp - 0.5) <= 0.05:` — una **banda** que admite
spread ∈ [0,45 ; 0,55].

**Vivo.** `--max-spread-open 0.5` con `--no-adaptive-spread` → un **cap duro**: admite spread ≤ 0,50.

**En Capitaria son indistinguibles**, y por eso nadie lo detectó: el spread es un escalón
degenerado en 0,50/0,60, así que ambos criterios aceptan exactamente el mismo conjunto de ticks.
Medido sobre 2026-07 (10.855.025 ticks): banda 37,4 % · cap 37,4 % · **discrepancia 0,0 % en ambos
sentidos**.

**En AVA no se parecen en nada.** Admisión de ticks por mes:

| Mes | p50 spread | banda `[0,45;0,55]` | cap `≤0,50` |
|---|---:|---:|---:|
| 2022-01 | 0,340 | **0,0 %** | 100,0 % |
| 2023-01 | 0,290 | **0,0 %** | 100,0 % |
| 2024-07 | 0,270 | **0,0 %** | 99,9 % |
| 2024-12 | 0,270 | 4,5 % | 94,7 % |
| 2025-10 | 0,370 | 12,9 % | 75,0 % |
| 2026-07 | 0,460 | 46,4 % | 65,2 % |

Desde **2022-01 hasta 2024-11 la banda admite entre 0,0 % y 0,2 % de los ticks** — unos **35 de los
56 meses** del sustrato largo. El spread nativo de AVA vivió en 0,27–0,34 durante tres años, muy
por debajo del borde inferior de la banda.

**Consecuencia:** un backtest largo sobre AVA con este gate **abre prácticamente cero posiciones
antes de 2025**. No es un sesgo: es un silencio total. Y explica por qué las réplicas previas
fallaban de forma inconsistente — funcionaban en los meses recientes, donde el spread de AVA se
había desplazado hacia la banda, y no producían nada en los antiguos.

**Para cerrarla:** el gate debe ser un cap `≤ umbral`, no una banda centrada. Nótese que esto es
independiente de la decisión pendiente de D-21/D-38 sobre qué anchura usar para el **coste**: aquí
se trata de la **condición de apertura**, y el vivo usa un cap.

## D6 · Falta el time-gate de aperturas

**Vivo.** `--blocked-open-window 18:00-18:45` (OPEN únicamente) → **4.790 `TIME_GATE_SKIP`** en la
ventana.

**Harness.** No existe. Grep de `blocked|time_gate|18:0` sobre `backtest.py` no devuelve ninguna
implementación — sólo una mención en el comentario de zona horaria.

## D7 · Semántica de la salida

**Harness.** `resolve()` (`backtest.py:369-387`) barre los ticks **dentro de la barra de salida**
buscando el primer cruce del nivel; si no cruza, usa fill a cierre de barra.

**Vivo.** El SL vive **en el servidor del bróker** y se ejecuta en cualquier tick; el trail sólo lo
mueve al cierre de barra (**441 `MODIFY`** en la ventana, arrastrándose monótonamente). Sólo hubo
**3 `CLOSE`** del reconciliador ⇒ prácticamente todas las salidas las hizo el bróker.

Diferencia ya cuantificada en sesión previa: la granularidad barra-vs-tick del trail explica el
**5,8 %**. Es un residuo forzoso, no un bug: `sl_check` se actualiza al cierre de barra en ambos
modos.

## D8 · El descarte por SL ya cruzado no está modelado

**Vivo.** Cuando el SL heredado del sim ya está cruzado por el precio vivo, la apertura se
**descarta**: **943 `OPEN_SKIPPED_SL_CROSSED`** en la ventana (más 35 `SL_CLAMPED` y 9
`FALLBACK_CLOSE_INVALID_SL`).

**Harness.** No tiene el concepto. Abriría esas 943.

Es consecuencia directa de D1 y **hay que modelarlo**: es pérdida de entradas, y sin él el harness
sobre-genera justo donde el vivo callaba.

## D9 · Los cierres manuales y el cupo

**Vivo.** 11 cierres manuales en la ventana canónica. Con `active_fichas=1` y concurrencia 1, una
posición abierta **bloquea toda señal posterior**; cada cierre manual libera el cupo antes de tiempo
y abre una ventana de entrada que el sim nunca tiene.

**Harness.** No los tiene.

⚠️ **Por eso el resultado autónomo real no es derivable de los datos.** Restar los deals manuales del
historial (+3,01 M / −16,22 M, ver D-43) **no es el contrafactual autónomo**: es aritmética sobre
una secuencia que esos mismos cierres causaron. Sin ellos las posiciones habrían seguido abiertas
ocupando el cupo y toda la secuencia posterior sería otra. **El desempeño 100 % autónomo sólo se
obtiene re-simulando** — de ahí la corrida dedicada sin manuales.

Para **P-CAP** (bit-idéntico contra el historial) los 11 cierres deben reproducirse por **replay de
marca temporal**; no son modelables.

## D10 · Constantes `LIVE` obsoletas

`backtest.py:465-467` fija
`LIVE = {"combined": (116, 282372.88), "S6-K2P0": (69, 114348.06), "S7-TPNONE": (42, 45775.52),
"SuperTrend-p14x3-M15": (5, 122249.30)}` — de un informe del 2026-07-25 con otro alcance. **No son
las cifras de la 902**, que son 84 y 68 posiciones con +9.272.144 y +5.930.966 CLP (LEDGER
F0-INFRA-0025) — y esas, a su vez, **incluyen los cierres manuales** (D-43).

Además `MONTHS = [f"2026-{m:02d}" for m in range(1, 8)]` (`backtest.py:460`) fija el sustrato a los
7 meses de Capitaria.

Nadie debe leer esas constantes como medición de fidelidad.

---

## Qué hace falta para P-CAP (bit-idéntico)

Cerrar D1, D2, D3, D4, D6, D8 y reproducir D9 por replay. D5 es no-op sobre Capitaria (banda y cap
coinciden) pero conviene arreglarlo igual, porque es el mismo código que correrá P-AVA. D7 deja un
residuo del 5,8 % que hay que declarar como techo de paridad alcanzable, o demostrar que se
compensa. D10 es higiene.

## Qué hace falta además para P-AVA

D5 es **bloqueante**: con la banda actual, tres años del sustrato no producen ninguna posición. Y la
anchura de coste sigue sujeta a la decisión pendiente de D-21/D-38, que —según la adenda 2— **no
debería fijarse antes de tener P-CAP**, porque el overlay se calibró contra una brecha que en buena
parte era D1.

## Verificación pendiente antes de dar por buena cualquier cifra

- La puerta de paridad exige `-m slow`: sin ese flag
  `pytest tests/research/test_baseline_parity.py -q` devuelve **4 deselected** — un verde que no
  ejecutó nada.
- El denominador de A6 son **barras-señal (49 S6 / 42 ST)**, nunca posiciones. Tolerancia 0 y ±1,
  jamás ±8. Aplicar el desplazamiento estructural de **+1 barra**.
- `deals_raw` da **150 aperturas / 151 cierres** en la ventana canónica, no 152: re-derivar el
  denominador, no heredarlo.
