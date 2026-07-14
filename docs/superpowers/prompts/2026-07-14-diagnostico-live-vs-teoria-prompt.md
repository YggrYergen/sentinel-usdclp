# PROMPT DE ARRANQUE — Diagnóstico profundo: qué hacen las estrategias EN VIVO vs qué deberían hacer EN TEORÍA

Eres un orquestador Fable 5 en `D:\FOREX`. Tu misión es SOLO diagnóstico: identificar, cuantificar y explicar
los gaps entre el comportamiento real de las 20 estrategias EMASAR en vivo y su comportamiento
teórico/proyectado, y explicar por qué la sesión live perdió dinero vs lo proyectado. Al final propondrás
correcciones rankeadas por $/esfuerzo, pero NO se implementa ninguna corrección de estrategia sin decisión
explícita del usuario.

## Reglas de orquestación (obligatorias)
- Tú orquestas y verificas; el trabajo lo hacen **subagentes Sonnet 5 high effort** con instrucciones
  cerradas, completas y detalladas (no deben razonar decisiones de diseño; tú decides, ellos ejecutan).
- **Investigadores = SOLO LECTURA**: prohibido modificar código/tests/configs; solo pueden escribir archivos
  NUEVOS de reporte bajo `docs/superpowers/research/` y JSONs bajo `scripts/report/`; prohibido borrar o
  sobrescribir información existente; MetaTrader5 solo lecturas (initialize/shutdown, account_info,
  positions_get, history_deals_get, copy_rates_*, symbol_info, symbol_info_tick). PROHIBIDO order_send/
  order_check/cierres/modificaciones de posiciones.
- **Nunca dos subagentes en paralelo cuyos archivos se solapen** (ni siquiera lectura de un archivo que otro
  esté escribiendo). Implementadores (si el usuario aprueba fixes) tampoco commitean; los commits los haces
  tú tras gate verde.
- Gate de tests: `python -m pytest -q tests/golden/test_parity.py tests/strategies tests/scripts tests/live`
  (180 al último corte). Parity gate del golden master es sagrado.
- Capa 4: DEMO 2883015767 = única operable; REAL 2883011573 = READ-ONLY SIEMPRE; ATTACH-ONLY (nadie lanza
  terminales MT5); `D:/FOREX/CUENTAS.md` es fuente única de cuentas.

## Estado del sistema al corte (2026-07-14 ~08:15 UTC)
- Ejecutor live ARMADO corriendo (proceso `python -m scripts.live.run_live_20 --arm`) con **código ANTERIOR
  al commit c93fcd0** (sin clamp de SL): los episodios retcode=10016 en MODIFY siguen ocurriendo. El código
  nuevo activa al reiniciar (el usuario tiene `INICIAR_TRADING_LIVE.bat`, watchdog que rearma vía
  `--arm --confirm-account 2883015767`, autorizado por el usuario).
- `run_deals_watcher` daemon poblando `deals_raw` (data/research.db) cada 5s.
- Alarma de piso: si balance/equity ≤ 30.000.000 CLP → crea `scripts/live/STOP` (kill-switch, congela
  aperturas). Balance al corte ~62,7M CLP.
- Kill-switch manual: `PAUSAR_TRADING.bat` / `REANUDAR_TRADING.bat` en `D:\FOREX`.
- Branch `alvaro`, últimos commits: 440331f (programa variantes + infra live) y c93fcd0 (endurecimiento +
  herramientas de paridad). Tree limpio al corte.

## Los hechos medidos de la sesión nocturna (01:06 → 07:57 UTC, informe overnight)
- PnL real: **−712.142 CLP ≈ −763 USD** (cuenta demo en CLP; ≈933,5 CLP/USD).
- **1.011 posiciones** en <7h; hold mediano **132 s**; 761 posiciones ≤5 min.
- **954/1011 (94%) salieron por SAME_BAR_EXIT_FALLBACK** (cierre a mercado al tick siguiente porque el sim
  salió DENTRO de la barra recién cerrada vía trail recalculado con el high/AC de esa misma barra).
  Costo by-design acumulado ≈ **−$1.033 USD**.
- Incidentes de ejecución: 21× retcode 10027 (Algo Trading OFF, 01:03-01:05), 12× 10016 en OPEN, ≥33× 10016
  en MODIFY (SL dentro de stops_level=50 pts; algunos episodios persistentes de minutos). Costo directo
  estimado de incidentes: solo ≈ −$10…−25 USD → **los incidentes NO explican la pérdida; el churn sí**.
- Paridad de señal validada: audit log del sim in-process reconcilia 1:1 con deals reales; checker oficial
  (ventana 01:06→02:57): 13/20 MATCH y divergencias trazables a incidentes.
- Informes previos (leer primero): `docs/superpowers/research/2026-07-14-overnight-live-vs-backtest.md`,
  `docs/REPORTE_PARIDAD_LIVE_2026-07-14.md`, `docs/superpowers/research/2026-07-13-livefill-bound.md` (D90),
  `docs/superpowers/research/2026-07-13-live-executor.md` (semántica del ejecutor, addendum de stops
  intra-barra), `scripts/live/fill_parity_20260714_v2.json`, `scripts/report/parity_overnight.json`.

## Hipótesis-candidatas a investigar (rankeadas; asigna un subagente por línea, archivos disjuntos)

**H1 — El churn same-bar: ¿es fiel al backtest o es un artefacto del ejecutor? (LA CENTRAL)**
Pregunta decisiva: si corres `simular_variant` offline sobre las mismas barras/ventana, ¿también hace ~1.000
trades con hold de ~2 min? 
- Si SÍ: el diseño de la estrategia churnea igual en backtest, pero el backtest "gana" porque llena las
  salidas AL NIVEL del trail sin spread/slippage → el optimismo del modelo de fills es estructural
  (cota D90) y la corrección es de ESTRATEGIA (alejar trailing / ac_modulate_factor / retirar configs 0.01).
- Si NO: el ejecutor recomputa distinto que el backtest (ventana 10.000 barras vs historia completa, barra
  en formación, direction_mask en vivo, blocked_hours, semántica return_state) → bug de ejecutor.
Dónde mirar: `sentinel_engine/strategies/emasar_variant.py` (trailing ladder: cómo se recalcula el stop con
el high/AC de la barra actual; motivos EXIT_TRAIL/EXIT_INITSL/EXIT_TP/EXIT_ACDECEL), `run_live_20.run_cycle`
(fetch_bars descarta barra en formación; window=10000), `last_bar_exits` en return_state. Comparar trade por
trade: eventos del sim offline vs audit log vs deals_raw en una ventana con lake completo (01:06→02:54).

**H2 — SL/TP server-side: ¿replican la semántica del sim? (sospecha explícita del usuario)**
- Verificar si el ejecutor instala TP server-side. Si el sim tiene EXIT_TP intra-barra y el live NO tiene TP
  en el broker, el live se pierde los take-profits entre barras → pérdida sistemática vs proyectado.
  Mirar: construcción de la orden OPEN en `execute_action` (¿campo tp?), reconciler (¿acción MODIFY para TP?).
- Verificar la semántica del SL: sim comprueba `low <= sl` (¿sobre bid o mid?); broker ejecuta SL sobre bid
  (long) — con spread nocturno ancho el SL live salta ANTES que el del sim. Cuantificar: distribución del
  spread real de la noche (ticks o symbol_info_tick histórico no disponible → usar deals: |fill − close de
  barra| como proxy) vs el modelo flat 0.5 del sim.
- Verificar que el SL enviado = SL del sim (auditar MODIFYs exitosos vs trail del sim en la misma barra).

**H3 — Spread/sesión: el modelo flat 0.5 vs la madrugada real**
La sesión fue 01:06-07:57 UTC (madrugada, spread XAUUSD real probablemente 2-5× el modelo). Con trails de
~1 pip (configs 0.01) el spread nocturno convierte cada micro-trade en pérdida casi segura. Cuantificar
spread efectivo por hora desde los pares entrada/salida de deals vs el 0.5 asumido; recalcular el PnL
proyectado con spread realista; ¿cuánto de los −$763 explica esto solo?

**H4 — Bug de persistencia del lake (bloquea todo backtest completo; arreglar PRIMERO si el usuario aprueba)**
`scripts/mt5_dump_history.py` corrió ≥2 veces después de las 02:54 y el lake (monolítico
`data/lake/XAUUSD/<tf>.parquet` y/o tiers `data/lake/XAUUSD/<TF>/2026-07.parquet`) sigue terminando en
02:54 UTC pese a que MT5 tiene las barras. Candidatos: `ingest_mt5_csv`/`store.py` (¿dedupe/merge que
descarta lo nuevo?, ¿escritura de mes parcial?), `drop_forming_bar` (commit c93fcd0, ¿demasiado agresivo?,
¿now_epoch capturado una vez y reutilizado?), tiers (`build_tiers` lee vía store.read_bars). Reproducir con
un dump de prueba y aislar qué capa pierde las barras. Este es el ÚNICO fix técnico pre-aprobado como
implementación si el diagnóstico lo confirma (con tests, gate verde, sin tocar estrategia).

**H5 — Slippage de entrada (fill N+1) y asimetría bid/ask**
Ya cuantificado parcial (~$13.9 en 2h, clase ENTRY_NEXT_BAR del checker). Extender a toda la noche vía
deals_raw: distribución del slip por config/hora; ¿es simétrico o sesgado contra? El sim entra al close de
la barra de señal; el live al ask (long)/bid (short) del tick siguiente.

**H6 — Estado encadenado tras misses**
Cuando un incidente saltó una entrada, el estado del ejecutor y el del sim divergen durante un rato
(posiciones que uno tiene y el otro no). Cuantificar cuánto PnL de la noche vino de tramos "desincronizados"
(ya hay lógica de cascada visible en el checker: MISSED → EXTRA subsiguientes).

## Herramientas ya construidas (reutilizar, no reconstruir)
- `scripts/live/check_live_sim_parity.py` — paridad de fills (warmup 10k, ENTRY_NEXT_BAR, SAME_BAR_OPTIMISM,
  same_bar_cost/entry_slip_cost, --json). Uso: `python -m scripts.live.check_live_sim_parity --config all
  --start <iso> --end <iso> --json out.json`.
- `scripts/live/check_dryrun_intent_parity.py` — paridad de intents audit-log vs lake (BAR_EDGE_LAG).
- `scripts/live/run_deals_watcher.py` — captura deals → deals_raw (corriendo).
- `scripts/mt5_dump_history.py` + `scripts/build_tiers.py --symbol XAUUSD` — refresco del lake (¡ver H4!).
- Audit log: `scripts/live/run_live_20.audit.log` (líneas [SAME_BAR_EXIT_FALLBACK] con sim_fill/live_fill/
  gap$/motivo; líneas "SAME_BAR cumulative" firmadas por config; incidentes con retcodes).
- `deals_raw` (data/research.db, sqlite): ticket, position_id, side, volume, price, profit (en CLP), magic,
  time (epoch), entry_type IN/OUT. Magics: base por config en CONFIGS_20; fichas = base+1..base+3.
- Sim: `simular_variant(bars, **kwargs)` → eventos con motivo/idx/precio/lado/ficha; `return_state=True`
  para estado de fichas abiertas; kwargs por config en `sentinel_engine/strategies/live_configs_20.py`.
  V10-* necesita `direction_mask` (compute_direction_mask de scripts.report.gen_variant_batch5 sobre las
  MISMAS barras); V11-* lleva blocked_hours dentro de kwargs.

## Entregable final de la sesión de diagnóstico
`docs/REPORTE_DIAGNOSTICO_LIVE_VS_TEORIA_2026-07-14.md` (español, para el usuario): resumen ejecutivo;
respuesta binaria y evidenciada a H1 (¿estrategia o ejecutor?); veredicto SL/TP (H2) con evidencia
trade-por-trade; tabla de descomposición de los −$763 por causa con % explicado (el residuo no explicado
debe quedar <10% o justificado); correcciones propuestas rankeadas por impacto $/esfuerzo con su riesgo,
SIN implementar (salvo H4-lake si se confirma bug, pre-aprobado); y qué configs recomendarías pausar ya
(PAUSAR_TRADING.bat congela TODAS las aperturas; retirar configs individuales requiere cambio de código →
decisión del usuario). Presenta al usuario las decisiones al final, no durante.
