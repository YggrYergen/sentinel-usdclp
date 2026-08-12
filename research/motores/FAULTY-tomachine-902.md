# MOTOR FAULTY — `engine-faulty-tomachine-902`

> **Este motor se preserva, no se arregla.** Es el ejemplar del código que generó dos semanas
> de operativa real. Su valor está en sus errores, no a pesar de ellos: es la línea base contra
> la que se mide qué aporta el motor corregido.
>
> Cualquier arreglo va sobre un motor **separado** (`engine=fixed`). Ningún commit debe apuntar
> a este ref con intención de corregirlo.

---

## 1 · Identidad

| | |
|---|---|
| Tag | `engine-faulty-tomachine-902` (anotado) |
| Commit | `b113eb7471c104f9178518c02365129818c203e8` |
| Ref preservado | `refs/m2/heads/alvaro-tomachine-s6st-config` |
| Rama de origen | `alvaro-tomachine-s6st-config` — local en máquina 2, **jamás pusheada** |
| Base | `f93e54a` (= `origin/alvaro`), 10 commits por encima |
| Cuenta que operó | DEMO **2883016902** (Capitaria), lote 0,67 |
| Ventana de operativa | 2026-07-27 18:52:29 → 2026-08-12 09:37:02 (hora de servidor, UTC−4) |

El namespace `refs/m2/*` es deliberado: no aparece en `git branch`, no se puede checkoutear ni
mergear por accidente. Para inspeccionarlo: `git show engine-faulty-tomachine-902:<ruta>`.

## 2 · Procedencia y verificación

Entrega `M2_ENTREGA` del 2026-08-12, generada en máquina 2 en modo estrictamente de solo lectura.

Verificado **por máquina 1**, no aceptado por reporte:

- `git bundle verify repo-completo.bundle` → *okay*, **complete history**, 8 refs.
- `b113eb7` alcanzable tras importar; `git rev-list --count f93e54a..b113eb7` = **10**.
- Los 6 ficheros sueltos de `config_efectiva/` son **byte-idénticos** (`git hash-object` ==
  `git rev-parse b113eb7:<ruta>`) a los del commit: `reconciler.py`, `run_live_20.py`,
  `live_configs_20.py`, `emasar_variant.py`, `guard_cuenta.py`, `supervisor_live.py`.

**Corrección de una premisa nuestra:** el brief pedía «el working tree sin commitear» suponiendo
que era el único ejemplar. Era falso — el working tree estaba limpio y el artefacto es una rama
git íntegra. Mejor de lo esperado: se preserva como historia, no como copia de ficheros.

Artefactos voluminosos **fuera de git** (no versionar):
`C:\Users\tomas\Downloads\M2_ENTREGA\M2_ENTREGA\` — `logs_ejecutor/` (70 MB, audit de la ventana),
`mt5_logs_capitaria/` (18 logs), `repo/` (352 MB), `repo-completo.bundle` (4,6 MB).

## 3 · Cómo se invocaba

Cadena: tarea programada `SENTINEL_LIVE_TOMACHINE` (AtLogOn) → `INICIAR_SENTINEL_LIVE_LOCAL.bat`
→ `watchdog_local.ps1` (oculto) → `python -m scripts.live.supervisor_live` → subproceso ejecutor.

```
python -m scripts.live.run_live_20 --arm --confirm-account 2883016902 \
       --configs tomachine --max-spread-open 0.5 \
       --blocked-open-window 18:00-18:45 --no-adaptive-spread
```

`--window` y `--interval` **no se pasan** → defaults `--window 10000` y **`--interval 15.0`**.
Confirmado por el propio audit log en el arranque (`window=10000`, ciclos cada ~15 s).

> El intervalo de 15 s es **parte del motor faulty**, no un detalle de despliegue: la ruta de
> apertura (§4, F-1) toma el precio de mercado *en el instante del ciclo de reconciliación*.
> Cualquier réplica en harness que no modele esa cadencia no reproduce este motor.

## 4 · Fallos conocidos — PRESERVAR, no corregir

### F-1 · Herencia del SL trailleado en la apertura (D-39) — el fallo principal

El ejecutor **abre a precio de mercado pero hereda el SL ya trailleado del sim.**

- `reconciler.py:296-299` — la acción `OPEN` lleva `sl=d.get("sl")` (el SL **actual** del sim, ya
  arrastrado por el trail) y `price_ref=d.get("entry")` (la entrada del sim, declarada en
  `reconciler.py:60` como *«sim entry/stop reference (for logs)»*).
- `run_live_20.py:786` — `price = tick.ask if a.side == "L" else tick.bid`. La orden se manda al
  precio de mercado del momento. **`price_ref` no se usa nunca.**

Consecuencia: si la señal del sim es de hace varias barras y el precio ya corrió a favor, la
posición viva **nace con el stop a un pelo** (≈ el ancho del trail) en vez de a los ~17,5 USD del
SL inicial del backtest. De ahí las salidas agrupadas en −1,00 USD y las duraciones de segundos.

Verificado **independientemente en el repo de máquina 1**: la ruta está en la base compartida
`origin/alvaro` y los 10 commits locales no la tocan. No es divergencia máquina-1-vs-máquina-2,
es divergencia **ejecutor-vs-backtest**.

Huella en el audit log de la ventana:

| Evento | Cuenta |
|---|---|
| `OPEN_SKIPPED_SL_CROSSED` (SL del sim ya cruzado por el precio vivo → apertura descartada) | **943** |
| `SL_CLAMPED` | 35 |
| `FALLBACK_CLOSE_INVALID_SL` | 9 |
| `MODIFY/F1` (trail operando en vivo, SL arrastrándose monótonamente) | 441 |
| `CLOSE/F1` | **3** |

Solo 3 CLOSE en toda la ventana ⇒ **prácticamente todas las salidas las hizo el bróker por SL**,
no el reconciliador. Salidas reales por `reason` de MT5: 118 SL · 21 expert · 11 manuales · 1 TP.

Y esas salidas por SL son ruinosas: **−16.290.173 CLP** en la ventana. El motor faulty, dejado a
su propia gestión de salidas, **pierde dinero** (ver §7 y D-43).

El descarte por SL ya cruzado (las 943) es **parte del motor**: modela pérdida de entradas, y
cualquier réplica debe incluirlo.

### F-2 · Gate de spread con cap duro contra un spread degenerado

`--no-adaptive-spread` desde el arranque (2026-07-27 18:52) ⇒ el running-min adaptativo está
**apagado**; queda solo el cap estático duro de 0,50. El spread de XAUUSD en Capitaria es
bimodal degenerado (p25=p50=0,500 · p75=p99=0,600), así que el cap corta **justo en la moda**.

⚠️ **No es una divergencia harness-vs-vivo.** El gate del harness y el del vivo son el mismo gate:
el running-min converge a 0,500001 y admite exactamente los mismos 1.817.188 ticks que la banda
fija de 0,50. Confirmado por dos vías. Se documenta aquí porque **es un parámetro del motor
faulty** que hay que replicar, no porque explique el déficit de recall — no lo explica
(ver §6).

### F-3 · El ejecutor murió sin que nada lo detectara

Terminó el 2026-08-12 09:37:02 con
`[GUARD] REFUSING TO OPERATE: account_info() returned None (not connected / attach failed)`.
El watchdog reporta `watcher up · supervisor up · dashboard up` cada 20 s — **no vigila el
ejecutor** (de eso responde el supervisor), así que el fallo no disparó alarma.

### F-4 · Cierres por SL/TP con `magic=0`

Los deals de cierre por stop/TP llegan con `magic=0` y se mis-etiquetan como humanos, rompiendo
el conteo abierto/cerrado y el neto. La atribución correcta exige heredar la estrategia por
`position_id`. (Ver memoria `mt5-sltp-close-magic-zero`.)

## 5 · Config efectiva (rutas relativas a la raíz del repo, en `b113eb7`)

| Parámetro | Valor | `fichero:línea` |
|---|---|---|
| `active_fichas` S6-K2P0 | **1** | `sentinel_engine/strategies/live_configs_20.py:568` (assert `:597`) |
| `active_fichas` SuperTrend | ausente a propósito — motor `supertrend_always_in`, ya mono-ficha | `live_configs_20.py:569`, assert `:599`; motor `run_live_20.py:356` |
| `trail_atr_floor_k` | **2.0, y SÍ se aplica** | `live_configs_20.py:256`; aplicación `emasar_variant.py:967-971` |
| `f1_trail_pips` (y F2/F3) | 100.0 (pip 0,01 ⇒ 1,00 USD) | `live_configs_20.py:51` |
| `init_sl_range_k` M15 | 2.5 | `live_configs_20.py:60` (`_K_BY_TF`), aplicado `:234` |
| `be_at_r` en S6-K2P0 | ausente (default motor 0.0 = desactivado) | `live_configs_20.py:256-257`; default `emasar_variant.py:105` |
| volumen / lote | **0.67 fijo por config** (copia profunda del dict go-live) | `live_configs_20.py:568-569` (`_tomachine_copy`), assert `:591` |
| `MAX_VOLUME` | global 0.10, **override por config `max_volume=0.67`** — sin el override todo OPEN sería `REJECT_VOLUME` | `reconciler.py:45`; override `live_configs_20.py:560`; lectura `run_live_20.py:406` |
| `stop_and_reverse` | True | `live_configs_20.py:236` |
| gate de spread | no adaptativo, cap duro 0,50 | `supervisor_live.py:140`, `:189+` |

Esqueleto S6-K2P0 (`_GOLIVE_BASE_M15`, `live_configs_20.py:43-69`, `:232-252`):
`ema_fast=8`, `ema_slow=20`, `sar_step=0.3`, `sar_max=0.3`, `sar_adaptive=True`,
`sar_fast=(0.3,0.3)`, `sar_slow=(0.005,0.05)`, `vol_regime_window=200`, `confirm_mode=1`,
`confirm_count=2`, `require_ema_order=False`, `ac_modulate=True`, `ac_modulate_factor=0.25`,
`live_fill_mode=True`, `symbol="XAUUSD"`.

Magics: S6-K2P0 base 724010 → F1 = **724011** (84 aperturas); SuperTrend base 724070 →
F1 = **724071** (68 aperturas). `724012`/`724013` **no aparecen jamás** — solo existe F1.

Perfil de máquina (`scripts/live/machine_local.json`, gitignored, incluido en la entrega):
terminal `C:\Program Files\Capitaria MT5 Terminal\terminal64.exe`, **`portable: false`**,
`demo_login: 2883016902`.

**No hay gestor de SL alternativo.** Barrido de `MQL5\Experts`: 390 ficheros, todos ejemplos de
stock de MetaQuotes. `SENTINEL_TrailGuard` no existe en esa máquina en ninguna forma, y
`MQL5\Logs` está vacío ⇒ ningún EA se adjuntó ni ejecutó nunca. **El único gestor de SL es el
ejecutor Python.**

## 6 · Lo que NO es un fallo de este motor — confusores muertos con número

No re-medir. Cada uno se cerró con una cifra:

1. **Servidor distinto** — falso. `server='Capitaria-All'`, `company='Capitaria Latam SpA'`. La
   celda de `CUENTAS.md` llevaba la razón social donde las demás filas llevan el servidor; ya
   corregida. El sustrato es válido.
2. **Gate de spread como divergencia** — mismo gate por dos vías (§F-2). Y su contador
   `SPREAD_GATE_SKIP` = 92.461 es **por ciclo** (~89.900 ciclos a 15 s ≈ 1/ciclo), no un censo
   de señales bloqueadas: contra 49 + 42 barras-señal hay tres órdenes de magnitud de diferencia.
   Además la dirección no cierra — un gate más restrictivo en vivo daría **menos** entradas
   reales, y el déficit es que el harness genera **menos** que la realidad. Mismo caveat para
   `OPEN/F1` 98.365 y `NOOP/F1` 50.484: son acciones deseadas por ciclo, no órdenes.
3. ~~**Mod #12 / cierres manuales** — atacan el 7%.~~ 🔴 **REVOCADO — ver D-43.** El «7 %» era
   11 de 151 **por cuenta**, no participación en el neto. Medido: los 11 cierres manuales aportan
   **+28.416.355,78 CLP** sobre un neto total de **+15.203.111,33** — sin ellos la cuenta pierde
   **13,2 M**. `SuperTrend` sin manuales hace **−16.223.085**. No es un confusor menor: es la
   totalidad de la rentabilidad de la ventana.
4. **Granularidad del trail (barra vs tick)** — explica el 5,8%. Forzoso: `sl_check` se actualiza
   al cierre de barra en ambos modos.
5. **`trail_atr_floor_k` ausente** — **refutada**. Existe en ambos lados con el mismo valor (2.0)
   y se aplica. El −1,00 lo explica F-1 en solitario, sin necesidad de que el floor falte.

**Vivos:** F-1 (D-39) y `active_fichas` (harness 3, realidad 1).

## 7 · Comportamiento observado, para contrastar contra la réplica

La réplica en harness es fiel sólo si reproduce esto:

- **152 posiciones** en la ventana (84 `S6-K2P0`, 68 `SuperTrend-p14x3-M15`), todas ficha F1.
- Duración **mediana 169 s**; **41,7%** cerradas en menos de un minuto.
- Cuenta **plana el 68% del tiempo**, re-entrando sin parar.
- Salidas agrupadas en **−1,00 USD** (= ancho del trail plano), no en el SL inicial (~17,5 USD).
- Concurrencia máxima verificada: **1 posición por estrategia**. Las hasta 8 posiciones por barra
  son **re-entradas secuenciales de una sola señal**, siempre en la misma dirección.

### Neto objetivo — y por qué hay que declarar cuál se persigue

Medido sobre `deals_raw` de la entrega (ventana canónica; reproduce 118 SL · 21 expert · 11 manual
· 1 TP = 151 cierres y cuadra al peso con la LEDGER F0-INFRA-0025):

| | NETO (= LEDGER) | Sin cierres manuales | Aporte manual |
|---|---:|---:|---:|
| `SAR::S6-K2P0` | +9.272.144,35 | **+3.009.841,01** | +6.262.303,34 (3 cierres) |
| `SuperTrend::SuperTrend-p14x3-M15` | +5.930.966,98 | **−16.223.085,46** | +22.154.052,44 (8 cierres) |
| **Cuenta** | **+15.203.111,33** | **−13.213.244,45** | **+28.416.355,78** |

🔴 **Las cifras de la LEDGER incluyen los cierres manuales**, así que no miden a las estrategias.
El motor faulty **con sus propias salidas pierde 13,2 M CLP**; lo que lo pone en positivo es un
humano cerrando a mano 11 veces. Una réplica que persiga el neto de la LEDGER está persiguiendo el
desempeño de un operador, no del motor. Declarar el objetivo antes de medir:

- **Neto de estrategia** (sólo salidas automáticas) → +3,01 M / −16,22 M. Es lo que el harness
  puede reproducir por sí solo.
- **Neto de operación** (incluye discrecionales) → +9,27 M / +5,93 M. Exige **replay por marca
  temporal** de los 11 cierres; no es modelable.

## 8 · Reglas de uso

1. **No corregir sobre este ref.** Los arreglos (SL re-anclado al abrir, cadencia de refresco más
   rápida) van sobre un motor separado que se registrará como `engine=fixed`.
2. **Todo resultado de backtest se etiqueta con el motor**: `engine=faulty@b113eb7` o
   `engine=fixed@<sha>`. Un resultado sin etiqueta de motor no es comparable y no vale.
3. **R1-bis sigue vigente**: los S6/S7/ST vivos se preservan byte-idénticos; toda modificación va
   sobre copia independiente (cfg deep-copy, módulo nuevo, banda mágica nueva).
4. **La réplica en harness no es el motor.** Antes de proyectar años con ella hay que certificarla
   contra A6 Pata A a nivel barra-señal (denominadores 49/42, tolerancia 0 y ±1, desplazamiento
   estructural de +1 barra). Sin ese certificado, el backtest largo faulty es una proyección de un
   motor que sólo *creemos* haber replicado.
5. **Restricción de datos, abierta:** los ticks de Capitaria cubren sólo 2026-01 → 2026-08. Una
   proyección plurianual sólo existe sobre AVA, cuyo spread tiene distribución real mientras que
   el de Capitaria es un escalón. El mismo cap de 0,50 es un gate distinto en cada feed. Esto es
   la premisa rota de D-21/D-38 y **está pendiente de decisión del usuario** — no se resuelve
   aquí.
