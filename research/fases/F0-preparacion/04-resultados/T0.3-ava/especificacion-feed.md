# T0.3-ava — Especificación del feed de oro (GOLD) del bróker AVA

**Tipo:** artefacto de datos — investigación report-only. Cero conclusiones, cero interpretación.

## Cabecera de lineage

| campo | valor |
|---|---|
| Fecha/hora de captura (hora del host = hora de servidor UTC−4, **sin conversión de zona horaria**) | `2026-08-11T21:04:09.584785` (corrida final, con Sección C completa). Corrida previa sin tick a las `2026-08-11T21:03:21.502709`. |
| Rama git | `equipo1` |
| SHA git al capturar | `89eebe4c833926124a941d35698bd04055d1429e` |
| Ruta del script usado | `C:\Users\tomas\AppData\Local\Temp\claude\D--FOREX\scratchpad-ava-spec\capture_ava_feed.py` (fuera del repo, temporal) |
| Salida cruda guardada en | `C:\Users\tomas\AppData\Local\Temp\claude\D--FOREX\scratchpad-ava-spec\run_output.txt` |
| Identidad verificada | `account_info().login = 101744074`, `account_info().server = 'Ava-Demo 1-MT5'`, `account_info().company = 'Ava Trade Ltd.'` — coincide con el login esperado (101744074) declarado en el brief. |
| Método de conexión | ATTACH-ONLY: `mt5.initialize()` sin argumento `path=`. Verificado con `tasklist`/`Get-Process` que ya existía un proceso `terminal64.exe` en ejecución antes de llamar a `initialize()`. No se lanzó ningún terminal. No se llamó a `order_send`, `order_check` ni `positions_modify`. `mt5.shutdown()` ejecutado al final en todos los caminos (`finally`). |

### Anomalía de nomenclatura de terminales (reportada, no resuelta por este agente)

El brief supone dos terminales corriendo simultáneamente, nombrados `MT5_Tester_1` (AVA, login 101744074) y `MT5_Tester_2` (cuenta "902" de Capitaria). Hechos observados en esta máquina en el momento de la captura:

- `Get-Process -Name terminal64` devolvió **un único** proceso: PID 9696, `Path = D:\FOREX\MT5_Tester\terminal64.exe` (sin sufijo `_1` ni `_2`).
- `Glob("MT5_Tester*", "D:\FOREX")` no encontró ninguna carpeta `MT5_Tester_1` ni `MT5_Tester_2`; solo existe `D:\FOREX\MT5_Tester`.
- `terminal_info().path` tras el attach = `'D:\\FOREX\\MT5_Tester'`.
- `D:\FOREX\CUENTAS.md` no menciona ninguna cuenta "902". Las cuentas documentadas ahí son: 2883015767 (DEMO Capitaria), 2883011573 (REAL Capitaria, titular "Quality Factor Servicios Financieros SpA"), y 101744074 (DEMO AVA).
- La verificación de identidad post-`initialize()` dio como resultado el login 101744074 (AVA) — coincide con el objetivo del brief — por lo que la captura procedió. No se intentó localizar ni tocar ningún segundo terminal ni la cuenta "902": está fuera de alcance de esta tarea y el brief la marca NO-R&D.

---

## Sección A — Identidad de la conexión

### `terminal_info()`

| campo | valor |
|---|---|
| path | `D:\FOREX\MT5_Tester` |
| data_path | `C:\Users\tomas\AppData\Roaming\MetaQuotes\Terminal\C09049E1712F47609377A8D30A1647B6` |
| commondata_path | `C:\Users\tomas\AppData\Roaming\MetaQuotes\Terminal\Common` |
| company | `MetaQuotes Ltd.` |
| name | `MetaTrader 5` |
| connected | `True` |
| trade_allowed | `False` |
| tradeapi_disabled | `False` |
| dlls_allowed | `False` |
| community_account | `False` |
| community_connection | `False` |
| email_enabled / ftp_enabled / notifications_enabled | `False` / `False` / `False` |
| mqid | `True` |
| build | `5836` |
| maxbars | `100000` |
| codepage | `1252` |
| ping_last | `209321` |
| community_balance | `0.0` |
| retransmission | `7.593559617058311` |
| language | `Spanish` |

### `account_info()`

| campo | valor |
|---|---|
| login | `101744074` |
| server | `Ava-Demo 1-MT5` |
| company | `Ava Trade Ltd.` |
| name | `18228627` |
| currency | `USD` |
| leverage | `400` |
| trade_mode (raw) | `0` → **`ACCOUNT_TRADE_MODE_DEMO`** |
| margin_mode (raw) | `2` |
| trade_allowed | `True` |
| trade_expert | `True` |
| balance | `10000.0` |
| equity | `10000.0` |
| credit | `0.0` |
| profit | `0.0` |
| margin | `0.0` |
| margin_free | `10000.0` |
| margin_level | `0.0` |
| margin_so_call / margin_so_so | `50.0` / `10.0` |
| margin_so_mode | `0` |
| currency_digits | `2` |
| fifo_close | `False` |
| limit_orders | `0` |

---

## Sección B — Especificación del símbolo `GOLD`

### Campo crítico, destacado

| campo | valor exacto |
|---|---|
| **`trade_contract_size`** | **`100.0`** |

### Otros campos pedidos explícitamente

| campo | valor |
|---|---|
| digits | `2` |
| point | `0.01` |
| trade_tick_size | `0.01` |
| trade_tick_value | `1.0` |
| trade_tick_value_profit | `1.0` |
| trade_tick_value_loss | `1.0` |
| volume_min | `0.01` |
| volume_max | `150.0` |
| volume_step | `0.01` |
| filling_mode (raw) | `1` → bit activo: `SYMBOL_FILLING_FOK` |
| trade_mode del símbolo (raw) | `4` → `SYMBOL_TRADE_MODE_FULL` |
| spread (snapshot `symbol_info`, ver nota) | `0` |
| spread_float | `True` |
| currency_base | `USD` |
| currency_profit | `USD` |
| currency_margin | `USD` |
| swap_mode (raw) | `6` → `SYMBOL_SWAP_MODE_INTEREST_OPEN` |
| swap_long | `-9.5` |
| swap_short | `0.5` |
| swap_rollover3days (raw) | `3` → `WEDNESDAY` |
| session_deals | `0` |
| start_time | `0` |
| expiration_time | `0` |
| description | `1 Lot= 100 Troy Oz` |
| path | `CFD-Metals\GOLD` |

**Nota de secuencia (dato, no interpretación):** en el momento del primer `symbol_info("GOLD")`, el símbolo tenía `select=False` / `visible=False` (no estaba en Market Watch); en ese estado, `bid/ask/last/time/spread` del snapshot estático son `0` / `0.0`. Solo después de llamar a `symbol_select("GOLD", True)` (operación no destructiva, sin órdenes) el feed de tick quedó disponible — ver Sección C. `symbol_info("GOLD")` devolvió datos completos (no `None`) desde el primer intento; no fue necesario el fallback de enumerar `symbols_get()`.

### Resto de campos capturados (`symbol_info` completo)

Ver Anexo de evidencia para el volcado íntegro campo-por-campo (más de 80 campos, incluye los de opciones/greeks que son `0.0` porque `GOLD` no es una opción: `option_mode`, `price_greeks_*`, etc.).

---

## Sección C — Tick actual y spread

Capturado tras `symbol_select("GOLD", True)`:

| campo | valor |
|---|---|
| time (epoch, s) | `1786496651` |
| time_msc (epoch, ms) | `1786496651148` |
| bid | `4382.83` |
| ask | `4383.28` |
| last | `0.0` |
| volume | `0` |
| volume_real | `0.0` |
| flags | `6` |
| **spread calculado (ask − bid)** | **`0.4499999999998181`** (≈ 0.45 en unidades de precio, con el residuo de punto flotante propio del float64) |

---

## Sección D — Comparación de especificaciones (solo captura, sin juicio)

No se conectó a Capitaria; no se leyó ningún dato en vivo de esa cuenta. Se buscó en el repo documentación previa de la especificación de `XAUUSD` de Capitaria.

### Encontrado en el repo

`D:\FOREX\docs\superpowers\research\2026-07-14-diag-h3h5-spread-slip.md:108`:

> "Taken 2026-07-14T13:20:42 UTC on DEMO 2883015767: `symbol_info("XAUUSD").spread` = **60 points** × point 0.01 = **0.60 USD/oz**; `symbol_info_tick`: bid 4075.51 / ask 4076.11 → ask−bid = **0.60**; `spread_float` = **False**; `trade_contract_size` = **100**."

Campos equivalentes de esa cita, en tabla:

| campo | XAUUSD — Capitaria (según cita, 2026-07-14T13:20:42 UTC, DEMO 2883015767) | GOLD — AVA (esta captura, 2026-08-11T21:04:09) |
|---|---|---|
| trade_contract_size | 100 | 100.0 |
| point | 0.01 | 0.01 |
| spread (símbolo, en puntos) | 60 | 0 (snapshot sin suscribir, ver nota Sección B) |
| spread (USD/oz, ask−bid del tick) | 0.60 | 0.4499999999998181 |
| spread_float | False | True |
| bid (tick, momento de cita) | 4075.51 | 4382.83 |
| ask (tick, momento de cita) | 4076.11 | 4383.28 |

Corroboración adicional del `trade_contract_size=100` de Capitaria (mismo valor, sin campos nuevos) en:
- `D:\FOREX\docs\superpowers\plans\2026-07-21-tk-bw-backtest.md:78` — "1 ficha = 0.01 lote = 1 oz (contract_size 100 ⇒ $1 por $1/oz de movimiento)."
- `D:\FOREX\docs\superpowers\research\2026-07-14-overnight-live-vs-backtest.md:6` — "Símbolo/lote: XAUUSD, 0,01 lot = 1 oz por ficha, 3 fichas/config, contract_size=100"

Búsqueda realizada en: `D:\FOREX\CUENTAS.md` (sin resultados para "XAUUSD"), `D:\FOREX\docs\` (81 ficheros con coincidencias de "XAUUSD"; grep dirigido a `contract_size|trade_tick_value|volume_step|digits`), `D:\FOREX\research\` (10 ficheros con "XAUUSD", ninguno con `contract_size` ni `symbol_info`).

### No documentado en el repo

Los siguientes campos de la especificación de `XAUUSD` de Capitaria, pedidos para `GOLD` en la Sección B de este brief, **no se encontraron documentados en ningún fichero del repo** tras la búsqueda anterior: `digits`, `trade_tick_size`, `trade_tick_value` / `_profit` / `_loss`, `volume_min` / `volume_max` / `volume_step`, `filling_mode`, `trade_mode` del símbolo, `currency_base` / `currency_profit` / `currency_margin`, `swap_mode`, `swap_long`, `swap_short`, `swap_rollover3days`, `session_deals`, `start_time`, `expiration_time`, `description`, `path`.

---

## Sección E — Disco

| campo | valor |
|---|---|
| `terminal_info().data_path` | `C:\Users\tomas\AppData\Roaming\MetaQuotes\Terminal\C09049E1712F47609377A8D30A1647B6` |
| Unidad | `C:` |
| disk_usage.total | `484659499008` bytes |
| disk_usage.used | `404628738048` bytes |
| disk_usage.free | `80030760960` bytes (`74.534` GB) |

Motivo del dato (no interpretado aquí, solo capturado): la caché de histórico del terminal crece en `data_path`.

---

## Sección F — Calendario de sesión (ADDENDUM)

**Añadido tras entrega inicial. Mismo terminal, mismo login verificado, misma sesión de captura del brief original — no se reabrió el terminal.**

| campo | valor |
|---|---|
| Fecha/hora de captura del addendum | `2026-08-11T21:09:41.624560` (hora del host = hora de servidor UTC−4, sin conversión) |
| Ruta del script usado | `C:\Users\tomas\AppData\Local\Temp\claude\D--FOREX\scratchpad-ava-spec\capture_ava_sessions.py` (fuera del repo, temporal) |
| Salida cruda guardada en | `C:\Users\tomas\AppData\Local\Temp\claude\D--FOREX\scratchpad-ava-spec\sessions_output.txt` |
| Identidad verificada antes de leer nada | `account_info().login = 101744074`, `server = 'Ava-Demo 1-MT5'`, `company = 'Ava Trade Ltd.'` — coincide con el login esperado. |
| Operación previa a la lectura | `symbol_select('GOLD', True)` (no destructiva, sin órdenes) para asegurar disponibilidad de datos del símbolo, igual que en la Sección C. |

### Resultado: función no disponible en el paquete instalado

`mt5.symbol_info_session_quote("GOLD", weekday, session_index)` y `mt5.symbol_info_session_trade("GOLD", weekday, session_index)` lanzan `AttributeError` en los 7 días de la semana (weekday 0..6), índice 0:

```
AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_quote'")
AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_trade'")
```

Enumeración de verificación (`dir(mt5)`) sobre el paquete `MetaTrader5` **versión `5.0.5735`** (la misma versión usada en toda esta captura, ver cabecera de lineage): **269 atributos públicos**, **ninguno contiene la subcadena `"session"`** (comprobado con `[a for a in dir(mt5) if 'session' in a.lower()]` → `[]`). La lista completa de los 269 atributos está en el Anexo de evidencia de esta sección.

Las funciones expuestas por este paquete relacionadas con símbolos son únicamente: `symbol_info`, `symbol_info_tick`, `symbol_select`, `symbols_get`, `symbols_total` — ninguna de nombre `symbol_info_session_*`.

### Tabla de sesiones — `symbol_info_session_quote`

| weekday | nombre | resultado |
|---|---|---|
| 0 | SUNDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 1 | MONDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 2 | TUESDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 3 | WEDNESDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 4 | THURSDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 5 | FRIDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 6 | SATURDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |

### Tabla de sesiones — `symbol_info_session_trade`

| weekday | nombre | resultado |
|---|---|---|
| 0 | SUNDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 1 | MONDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 2 | TUESDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 3 | WEDNESDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 4 | THURSDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 5 | FRIDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |
| 6 | SATURDAY | no evaluable — `AttributeError`, función ausente en el paquete instalado |

### Formato en que la API entregaría las horas

No determinable: al no existir la función en el paquete instalado, no se pudo observar el tipo de retorno real (`datetime.time`, segundos desde medianoche, u otro). No se estima ni se infiere del código fuente del paquete — fuera de alcance de este script de captura read-only.

No se intentó ninguna vía alternativa (reinstalar/actualizar el paquete `MetaTrader5`, invocar `SymbolInfoSessionQuote`/`SymbolInfoSessionTrade` desde MQL5, u otro mecanismo fuera de la API Python ya en uso): el brief pide específicamente `mt5.symbol_info_session_quote(...)` / `mt5.symbol_info_session_trade(...)`, y modificar el entorno Python o escribir/ejecutar código MQL5 está fuera del alcance read-only de esta tarea.

---

## Anexo de evidencia — salida cruda del script, literal

Script: `C:\Users\tomas\AppData\Local\Temp\claude\D--FOREX\scratchpad-ava-spec\capture_ava_feed.py`
Comando ejecutado: `python capture_ava_feed.py > run_output.txt 2>&1` (corrida final, incluye fallback de tick)

```
=== CAPTURA FEED AVA GOLD ===
Timestamp host (hora servidor UTC-4, sin conversion): 2026-08-11T21:04:09.584785
MetaTrader5 package version: 5.0.5735

--- VERIFICACION DE IDENTIDAD (previa a cualquier otra lectura) ---
account_info().login = 101744074
account_info().server = Ava-Demo 1-MT5
account_info().company = Ava Trade Ltd.
IDENTIDAD VERIFICADA: login 101744074 == esperado 101744074. Continuando.

=== SECCION A: terminal_info() ===
terminal_info.community_account = False
terminal_info.community_connection = False
terminal_info.connected = True
terminal_info.dlls_allowed = False
terminal_info.trade_allowed = False
terminal_info.tradeapi_disabled = False
terminal_info.email_enabled = False
terminal_info.ftp_enabled = False
terminal_info.notifications_enabled = False
terminal_info.mqid = True
terminal_info.build = 5836
terminal_info.maxbars = 100000
terminal_info.codepage = 1252
terminal_info.ping_last = 209321
terminal_info.community_balance = 0.0
terminal_info.retransmission = 7.593559617058311
terminal_info.company = 'MetaQuotes Ltd.'
terminal_info.name = 'MetaTrader 5'
terminal_info.language = 'Spanish'
terminal_info.path = 'D:\\FOREX\\MT5_Tester'
terminal_info.data_path = 'C:\\Users\\tomas\\AppData\\Roaming\\MetaQuotes\\Terminal\\C09049E1712F47609377A8D30A1647B6'
terminal_info.commondata_path = 'C:\\Users\\tomas\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common'

=== SECCION A: account_info() ===
account_info.login = 101744074
account_info.trade_mode = 0
account_info.leverage = 400
account_info.limit_orders = 0
account_info.margin_so_mode = 0
account_info.trade_allowed = True
account_info.trade_expert = True
account_info.margin_mode = 2
account_info.currency_digits = 2
account_info.fifo_close = False
account_info.balance = 10000.0
account_info.credit = 0.0
account_info.profit = 0.0
account_info.equity = 10000.0
account_info.margin = 0.0
account_info.margin_free = 10000.0
account_info.margin_level = 0.0
account_info.margin_so_call = 50.0
account_info.margin_so_so = 10.0
account_info.margin_initial = 0.0
account_info.margin_maintenance = 0.0
account_info.assets = 0.0
account_info.liabilities = 0.0
account_info.commission_blocked = 0.0
account_info.name = '18228627'
account_info.server = 'Ava-Demo 1-MT5'
account_info.currency = 'USD'
account_info.company = 'Ava Trade Ltd.'
account_info.trade_mode traducido = ACCOUNT_TRADE_MODE_DEMO

=== SECCION B: symbol_info('GOLD') ===
--- symbol_info('GOLD') COMPLETO ---
symbol_info.GOLD.custom = False
symbol_info.GOLD.chart_mode = 0
symbol_info.GOLD.select = False
symbol_info.GOLD.visible = False
symbol_info.GOLD.session_deals = 0
symbol_info.GOLD.session_buy_orders = 0
symbol_info.GOLD.session_sell_orders = 0
symbol_info.GOLD.volume = 0
symbol_info.GOLD.volumehigh = 0
symbol_info.GOLD.volumelow = 0
symbol_info.GOLD.time = 0
symbol_info.GOLD.digits = 2
symbol_info.GOLD.spread = 0
symbol_info.GOLD.spread_float = True
symbol_info.GOLD.ticks_bookdepth = 0
symbol_info.GOLD.trade_calc_mode = 2
symbol_info.GOLD.trade_mode = 4
symbol_info.GOLD.start_time = 0
symbol_info.GOLD.expiration_time = 0
symbol_info.GOLD.trade_stops_level = 50
symbol_info.GOLD.trade_freeze_level = 0
symbol_info.GOLD.trade_exemode = 2
symbol_info.GOLD.swap_mode = 6
symbol_info.GOLD.swap_rollover3days = 3
symbol_info.GOLD.margin_hedged_use_leg = False
symbol_info.GOLD.expiration_mode = 15
symbol_info.GOLD.filling_mode = 1
symbol_info.GOLD.order_mode = 55
symbol_info.GOLD.order_gtc_mode = 0
symbol_info.GOLD.option_mode = 0
symbol_info.GOLD.option_right = 0
symbol_info.GOLD.bid = 0.0
symbol_info.GOLD.bidhigh = 0.0
symbol_info.GOLD.bidlow = 0.0
symbol_info.GOLD.ask = 0.0
symbol_info.GOLD.askhigh = 0.0
symbol_info.GOLD.asklow = 0.0
symbol_info.GOLD.last = 0.0
symbol_info.GOLD.lasthigh = 0.0
symbol_info.GOLD.lastlow = 0.0
symbol_info.GOLD.volume_real = 0.0
symbol_info.GOLD.volumehigh_real = 0.0
symbol_info.GOLD.volumelow_real = 0.0
symbol_info.GOLD.option_strike = 0.0
symbol_info.GOLD.point = 0.01
symbol_info.GOLD.trade_tick_value = 1.0
symbol_info.GOLD.trade_tick_value_profit = 1.0
symbol_info.GOLD.trade_tick_value_loss = 1.0
symbol_info.GOLD.trade_tick_size = 0.01
symbol_info.GOLD.trade_contract_size = 100.0
symbol_info.GOLD.trade_accrued_interest = 0.0
symbol_info.GOLD.trade_face_value = 0.0
symbol_info.GOLD.trade_liquidity_rate = 0.0
symbol_info.GOLD.volume_min = 0.01
symbol_info.GOLD.volume_max = 150.0
symbol_info.GOLD.volume_step = 0.01
symbol_info.GOLD.volume_limit = 319.0
symbol_info.GOLD.swap_long = -9.5
symbol_info.GOLD.swap_short = 0.5
symbol_info.GOLD.margin_initial = 0.0
symbol_info.GOLD.margin_maintenance = 0.0
symbol_info.GOLD.session_volume = 0.0
symbol_info.GOLD.session_turnover = 0.0
symbol_info.GOLD.session_interest = 0.0
symbol_info.GOLD.session_buy_orders_volume = 0.0
symbol_info.GOLD.session_sell_orders_volume = 0.0
symbol_info.GOLD.session_open = 0.0
symbol_info.GOLD.session_close = 0.0
symbol_info.GOLD.session_aw = 0.0
symbol_info.GOLD.session_price_settlement = 0.0
symbol_info.GOLD.session_price_limit_min = 0.0
symbol_info.GOLD.session_price_limit_max = 0.0
symbol_info.GOLD.margin_hedged = 100.0
symbol_info.GOLD.price_change = 0.0
symbol_info.GOLD.price_volatility = 0.0
symbol_info.GOLD.price_theoretical = 0.0
symbol_info.GOLD.price_greeks_delta = 0.0
symbol_info.GOLD.price_greeks_theta = 0.0
symbol_info.GOLD.price_greeks_gamma = 0.0
symbol_info.GOLD.price_greeks_vega = 0.0
symbol_info.GOLD.price_greeks_rho = 0.0
symbol_info.GOLD.price_greeks_omega = 0.0
symbol_info.GOLD.price_sensitivity = 0.0
symbol_info.GOLD.basis = ''
symbol_info.GOLD.category = 'Commodities'
symbol_info.GOLD.currency_base = 'USD'
symbol_info.GOLD.currency_profit = 'USD'
symbol_info.GOLD.currency_margin = 'USD'
symbol_info.GOLD.bank = ''
symbol_info.GOLD.description = '1 Lot= 100 Troy Oz'
symbol_info.GOLD.exchange = 'XNYS'
symbol_info.GOLD.formula = ''
symbol_info.GOLD.isin = 'US00181T1079'
symbol_info.GOLD.name = 'GOLD'
symbol_info.GOLD.page = ''
symbol_info.GOLD.path = 'CFD-Metals\\GOLD'

--- CAMPOS DESTACADOS ---
trade_contract_size (EXACTO, sin redondear) = 100.0
digits = 2
point = 0.01
trade_tick_size = 0.01
trade_tick_value = 1.0
trade_tick_value_profit = 1.0
trade_tick_value_loss = 1.0
volume_min = 0.01
volume_max = 150.0
volume_step = 0.01
filling_mode (raw) = 1 -> bits activos: ['SYMBOL_FILLING_FOK']
trade_mode (simbolo) = 4 -> SYMBOL_TRADE_MODE_FULL
spread = 0
spread_float = True
currency_base = 'USD'
currency_profit = 'USD'
currency_margin = 'USD'
swap_mode = 6 -> SYMBOL_SWAP_MODE_INTEREST_OPEN
swap_long = -9.5
swap_short = 0.5
swap_rollover3days = 3 -> dia: WEDNESDAY
session_deals = 0
start_time = 0
expiration_time = 0
description = '1 Lot= 100 Troy Oz'
path = 'CFD-Metals\\GOLD'

=== SECCION C: symbol_info_tick('GOLD') ===
symbol_info_tick('GOLD') devolvio None en primer intento. last_error=(-4, 'Terminal: Not found')
Simbolo no suscrito (symbol_info.select=False). Intentando symbol_select('GOLD', True) para habilitar el feed de ticks (no destructivo, no coloca ordenes)...
symbol_select('GOLD', True) = True
tick.time = 1786496651
tick.bid = 4382.83
tick.ask = 4383.28
tick.last = 0.0
tick.volume = 0
tick.time_msc = 1786496651148
tick.flags = 6
tick.volume_real = 0.0
spread calculado (ask - bid) = 0.4499999999998181

=== SECCION E: disco de data_path ===
terminal_info.data_path = 'C:\\Users\\tomas\\AppData\\Roaming\\MetaQuotes\\Terminal\\C09049E1712F47609377A8D30A1647B6'
Unidad analizada: 'C:'
disk_usage.total = 484659499008 bytes
disk_usage.used = 404628738048 bytes
disk_usage.free = 80030760960 bytes
disk_usage.free (GB) = 74.534

=== FIN CAPTURA (sin ordenes colocadas, solo lectura) ===
mt5.shutdown() ejecutado.
```

### Corrida previa (sin fallback de tick, referencia solo)

La primera corrida (`2026-08-11T21:03:21.502709`) produjo la misma identidad, `terminal_info`, `account_info` y `symbol_info('GOLD')`, pero `symbol_info_tick('GOLD')` devolvió `None` con `last_error=(-4, 'Terminal: Not found')` porque el símbolo aún no estaba suscrito (`select=False`). Se descartó como fuente de la Sección C a favor de la corrida final, que sí capturó el tick.

### Addendum — salida cruda de `capture_ava_sessions.py`

Script: `C:\Users\tomas\AppData\Local\Temp\claude\D--FOREX\scratchpad-ava-spec\capture_ava_sessions.py`
Comando ejecutado: `python capture_ava_sessions.py > sessions_output.txt 2>&1`

```
=== ADDENDUM: CALENDARIO DE SESION GOLD (AVA) ===
Timestamp host (hora servidor UTC-4, sin conversion): 2026-08-11T21:09:41.624560
MetaTrader5 package version: 5.0.5735

--- VERIFICACION DE IDENTIDAD (previa a cualquier otra lectura) ---
account_info().login = 101744074
account_info().server = Ava-Demo 1-MT5
account_info().company = Ava Trade Ltd.
IDENTIDAD VERIFICADA: login 101744074 == esperado 101744074. Continuando.

symbol_select('GOLD', True) = True (asegurando disponibilidad de datos de sesion)

=== CALENDARIO symbol_info_session_quote('GOLD', weekday, idx) ===
weekday=0 (SUNDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_quote'")
weekday=0 (SUNDAY): SIN SESIONES (quote)

weekday=1 (MONDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_quote'")
weekday=1 (MONDAY): SIN SESIONES (quote)

weekday=2 (TUESDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_quote'")
weekday=2 (TUESDAY): SIN SESIONES (quote)

weekday=3 (WEDNESDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_quote'")
weekday=3 (WEDNESDAY): SIN SESIONES (quote)

weekday=4 (THURSDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_quote'")
weekday=4 (THURSDAY): SIN SESIONES (quote)

weekday=5 (FRIDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_quote'")
weekday=5 (FRIDAY): SIN SESIONES (quote)

weekday=6 (SATURDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_quote'")
weekday=6 (SATURDAY): SIN SESIONES (quote)

=== CALENDARIO symbol_info_session_trade('GOLD', weekday, idx) ===
weekday=0 (SUNDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_trade'")
weekday=0 (SUNDAY): SIN SESIONES (trade)

weekday=1 (MONDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_trade'")
weekday=1 (MONDAY): SIN SESIONES (trade)

weekday=2 (TUESDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_trade'")
weekday=2 (TUESDAY): SIN SESIONES (trade)

weekday=3 (WEDNESDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_trade'")
weekday=3 (WEDNESDAY): SIN SESIONES (trade)

weekday=4 (THURSDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_trade'")
weekday=4 (THURSDAY): SIN SESIONES (trade)

weekday=5 (FRIDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_trade'")
weekday=5 (FRIDAY): SIN SESIONES (trade)

weekday=6 (SATURDAY) idx=0: EXCEPTION AttributeError("module 'MetaTrader5' has no attribute 'symbol_info_session_trade'")
weekday=6 (SATURDAY): SIN SESIONES (trade)

=== FIN ADDENDUM (sin ordenes colocadas, solo lectura) ===
mt5.shutdown() ejecutado.
```

### Addendum — verificación independiente: enumeración `dir(mt5)`

Comando ejecutado (fuera del script anterior, verificación puntual read-only, mismo intérprete Python, sin `mt5.initialize()`):

```
python -c "
import MetaTrader5 as mt5
print('version:', mt5.__version__)
attrs = [a for a in dir(mt5) if 'session' in a.lower()]
print('atributos con session:', attrs)
all_attrs = [a for a in dir(mt5) if not a.startswith('_')]
print('TOTAL atributos publicos:', len(all_attrs))
for a in sorted(all_attrs):
    print(' -', a)
"
```

Salida:

```
version: 5.0.5735
atributos con session: []
TOTAL atributos publicos: 269
 - ACCOUNT_MARGIN_MODE_EXCHANGE
 - ACCOUNT_MARGIN_MODE_RETAIL_HEDGING
 - ACCOUNT_MARGIN_MODE_RETAIL_NETTING
 - ACCOUNT_STOPOUT_MODE_MONEY
 - ACCOUNT_STOPOUT_MODE_PERCENT
 - ACCOUNT_TRADE_MODE_CONTEST
 - ACCOUNT_TRADE_MODE_DEMO
 - ACCOUNT_TRADE_MODE_REAL
 - AccountInfo
 - BOOK_TYPE_BUY
 - BOOK_TYPE_BUY_MARKET
 - BOOK_TYPE_SELL
 - BOOK_TYPE_SELL_MARKET
 - BookInfo
 - Buy
 - COPY_TICKS_ALL
 - COPY_TICKS_INFO
 - COPY_TICKS_TRADE
 - Close
 - DAY_OF_WEEK_FRIDAY
 - DAY_OF_WEEK_MONDAY
 - DAY_OF_WEEK_SATURDAY
 - DAY_OF_WEEK_SUNDAY
 - DAY_OF_WEEK_THURSDAY
 - DAY_OF_WEEK_TUESDAY
 - DAY_OF_WEEK_WEDNESDAY
 - DEAL_DIVIDEND
 - DEAL_DIVIDEND_FRANKED
 - DEAL_ENTRY_IN
 - DEAL_ENTRY_INOUT
 - DEAL_ENTRY_OUT
 - DEAL_ENTRY_OUT_BY
 - DEAL_REASON_CLIENT
 - DEAL_REASON_EXPERT
 - DEAL_REASON_MOBILE
 - DEAL_REASON_ROLLOVER
 - DEAL_REASON_SL
 - DEAL_REASON_SO
 - DEAL_REASON_SPLIT
 - DEAL_REASON_TP
 - DEAL_REASON_VMARGIN
 - DEAL_REASON_WEB
 - DEAL_TAX
 - DEAL_TYPE_BALANCE
 - DEAL_TYPE_BONUS
 - DEAL_TYPE_BUY
 - DEAL_TYPE_BUY_CANCELED
 - DEAL_TYPE_CHARGE
 - DEAL_TYPE_COMMISSION
 - DEAL_TYPE_COMMISSION_AGENT_DAILY
 - DEAL_TYPE_COMMISSION_AGENT_MONTHLY
 - DEAL_TYPE_COMMISSION_DAILY
 - DEAL_TYPE_COMMISSION_MONTHLY
 - DEAL_TYPE_CORRECTION
 - DEAL_TYPE_CREDIT
 - DEAL_TYPE_INTEREST
 - DEAL_TYPE_SELL
 - DEAL_TYPE_SELL_CANCELED
 - ORDER_FILLING_BOC
 - ORDER_FILLING_FOK
 - ORDER_FILLING_IOC
 - ORDER_FILLING_RETURN
 - ORDER_REASON_CLIENT
 - ORDER_REASON_EXPERT
 - ORDER_REASON_MOBILE
 - ORDER_REASON_SL
 - ORDER_REASON_SO
 - ORDER_REASON_TP
 - ORDER_REASON_WEB
 - ORDER_STATE_CANCELED
 - ORDER_STATE_EXPIRED
 - ORDER_STATE_FILLED
 - ORDER_STATE_PARTIAL
 - ORDER_STATE_PLACED
 - ORDER_STATE_REJECTED
 - ORDER_STATE_REQUEST_ADD
 - ORDER_STATE_REQUEST_CANCEL
 - ORDER_STATE_REQUEST_MODIFY
 - ORDER_STATE_STARTED
 - ORDER_TIME_DAY
 - ORDER_TIME_GTC
 - ORDER_TIME_SPECIFIED
 - ORDER_TIME_SPECIFIED_DAY
 - ORDER_TYPE_BUY
 - ORDER_TYPE_BUY_LIMIT
 - ORDER_TYPE_BUY_STOP
 - ORDER_TYPE_BUY_STOP_LIMIT
 - ORDER_TYPE_CLOSE_BY
 - ORDER_TYPE_SELL
 - ORDER_TYPE_SELL_LIMIT
 - ORDER_TYPE_SELL_STOP
 - ORDER_TYPE_SELL_STOP_LIMIT
 - OrderCheckResult
 - OrderSendResult
 - POSITION_REASON_CLIENT
 - POSITION_REASON_EXPERT
 - POSITION_REASON_MOBILE
 - POSITION_REASON_WEB
 - POSITION_TYPE_BUY
 - POSITION_TYPE_SELL
 - RES_E_AUTH_FAILED
 - RES_E_AUTO_TRADING_DISABLED
 - RES_E_FAIL
 - RES_E_INTERNAL_FAIL
 - RES_E_INTERNAL_FAIL_CONNECT
 - RES_E_INTERNAL_FAIL_INIT
 - RES_E_INTERNAL_FAIL_RECEIVE
 - RES_E_INTERNAL_FAIL_SEND
 - RES_E_INTERNAL_FAIL_TIMEOUT
 - RES_E_INVALID_PARAMS
 - RES_E_INVALID_VERSION
 - RES_E_NOT_FOUND
 - RES_E_NO_MEMORY
 - RES_E_UNSUPPORTED
 - RES_S_OK
 - SYMBOL_CALC_MODE_CFD
 - SYMBOL_CALC_MODE_CFDINDEX
 - SYMBOL_CALC_MODE_CFDLEVERAGE
 - SYMBOL_CALC_MODE_EXCH_BONDS
 - SYMBOL_CALC_MODE_EXCH_BONDS_MOEX
 - SYMBOL_CALC_MODE_EXCH_FUTURES
 - SYMBOL_CALC_MODE_EXCH_OPTIONS
 - SYMBOL_CALC_MODE_EXCH_OPTIONS_MARGIN
 - SYMBOL_CALC_MODE_EXCH_STOCKS
 - SYMBOL_CALC_MODE_EXCH_STOCKS_MOEX
 - SYMBOL_CALC_MODE_FOREX
 - SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE
 - SYMBOL_CALC_MODE_FUTURES
 - SYMBOL_CALC_MODE_SERV_COLLATERAL
 - SYMBOL_CHART_MODE_BID
 - SYMBOL_CHART_MODE_LAST
 - SYMBOL_OPTION_MODE_AMERICAN
 - SYMBOL_OPTION_MODE_EUROPEAN
 - SYMBOL_OPTION_RIGHT_CALL
 - SYMBOL_OPTION_RIGHT_PUT
 - SYMBOL_ORDERS_DAILY
 - SYMBOL_ORDERS_DAILY_NO_STOPS
 - SYMBOL_ORDERS_GTC
 - SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT
 - SYMBOL_SWAP_MODE_CURRENCY_MARGIN
 - SYMBOL_SWAP_MODE_CURRENCY_SYMBOL
 - SYMBOL_SWAP_MODE_DISABLED
 - SYMBOL_SWAP_MODE_INTEREST_CURRENT
 - SYMBOL_SWAP_MODE_INTEREST_OPEN
 - SYMBOL_SWAP_MODE_POINTS
 - SYMBOL_SWAP_MODE_REOPEN_BID
 - SYMBOL_SWAP_MODE_REOPEN_CURRENT
 - SYMBOL_TRADE_EXECUTION_EXCHANGE
 - SYMBOL_TRADE_EXECUTION_INSTANT
 - SYMBOL_TRADE_EXECUTION_MARKET
 - SYMBOL_TRADE_EXECUTION_REQUEST
 - SYMBOL_TRADE_MODE_CLOSEONLY
 - SYMBOL_TRADE_MODE_DISABLED
 - SYMBOL_TRADE_MODE_FULL
 - SYMBOL_TRADE_MODE_LONGONLY
 - SYMBOL_TRADE_MODE_SHORTONLY
 - Sell
 - SymbolInfo
 - TICK_FLAG_ASK
 - TICK_FLAG_BID
 - TICK_FLAG_BUY
 - TICK_FLAG_LAST
 - TICK_FLAG_SELL
 - TICK_FLAG_VOLUME
 - TIMEFRAME_D1
 - TIMEFRAME_H1
 - TIMEFRAME_H12
 - TIMEFRAME_H2
 - TIMEFRAME_H3
 - TIMEFRAME_H4
 - TIMEFRAME_H6
 - TIMEFRAME_H8
 - TIMEFRAME_M1
 - TIMEFRAME_M10
 - TIMEFRAME_M12
 - TIMEFRAME_M15
 - TIMEFRAME_M2
 - TIMEFRAME_M20
 - TIMEFRAME_M3
 - TIMEFRAME_M30
 - TIMEFRAME_M4
 - TIMEFRAME_M5
 - TIMEFRAME_M6
 - TIMEFRAME_MN1
 - TIMEFRAME_W1
 - TRADE_ACTION_CLOSE_BY
 - TRADE_ACTION_DEAL
 - TRADE_ACTION_MODIFY
 - TRADE_ACTION_PENDING
 - TRADE_ACTION_REMOVE
 - TRADE_ACTION_SLTP
 - TRADE_RETCODE_CANCEL
 - TRADE_RETCODE_CLIENT_DISABLES_AT
 - TRADE_RETCODE_CLOSE_ONLY
 - TRADE_RETCODE_CLOSE_ORDER_EXIST
 - TRADE_RETCODE_CONNECTION
 - TRADE_RETCODE_DONE
 - TRADE_RETCODE_DONE_PARTIAL
 - TRADE_RETCODE_ERROR
 - TRADE_RETCODE_FIFO_CLOSE
 - TRADE_RETCODE_FROZEN
 - TRADE_RETCODE_INVALID
 - TRADE_RETCODE_INVALID_CLOSE_VOLUME
 - TRADE_RETCODE_INVALID_EXPIRATION
 - TRADE_RETCODE_INVALID_FILL
 - TRADE_RETCODE_INVALID_ORDER
 - TRADE_RETCODE_INVALID_PRICE
 - TRADE_RETCODE_INVALID_STOPS
 - TRADE_RETCODE_INVALID_VOLUME
 - TRADE_RETCODE_LIMIT_ORDERS
 - TRADE_RETCODE_LIMIT_POSITIONS
 - TRADE_RETCODE_LIMIT_VOLUME
 - TRADE_RETCODE_LOCKED
 - TRADE_RETCODE_LONG_ONLY
 - TRADE_RETCODE_MARKET_CLOSED
 - TRADE_RETCODE_NO_CHANGES
 - TRADE_RETCODE_NO_MONEY
 - TRADE_RETCODE_ONLY_REAL
 - TRADE_RETCODE_ORDER_CHANGED
 - TRADE_RETCODE_PLACED
 - TRADE_RETCODE_POSITION_CLOSED
 - TRADE_RETCODE_PRICE_CHANGED
 - TRADE_RETCODE_PRICE_OFF
 - TRADE_RETCODE_REJECT
 - TRADE_RETCODE_REJECT_CANCEL
 - TRADE_RETCODE_REQUOTE
 - TRADE_RETCODE_SERVER_DISABLES_AT
 - TRADE_RETCODE_SHORT_ONLY
 - TRADE_RETCODE_TIMEOUT
 - TRADE_RETCODE_TOO_MANY_REQUESTS
 - TRADE_RETCODE_TRADE_DISABLED
 - TerminalInfo
 - Tick
 - TradeDeal
 - TradeOrder
 - TradePosition
 - TradeRequest
 - account_info
 - copy_rates_from
 - copy_rates_from_pos
 - copy_rates_range
 - copy_ticks_from
 - copy_ticks_range
 - history_deals_get
 - history_deals_total
 - history_orders_get
 - history_orders_total
 - initialize
 - last_error
 - login
 - market_book_add
 - market_book_get
 - market_book_release
 - order_calc_margin
 - order_calc_profit
 - order_check
 - order_send
 - orders_get
 - orders_total
 - positions_get
 - positions_total
 - shutdown
 - symbol_info
 - symbol_info_tick
 - symbol_select
 - symbols_get
 - symbols_total
 - terminal_info
 - version
```
