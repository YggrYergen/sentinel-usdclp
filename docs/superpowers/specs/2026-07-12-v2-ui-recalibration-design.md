# Diseño — Recalibración V2 (specs por-pestaña + restricción 4-8GB + AI-trader)

Status: **APROBADO por usuario 2026-07-12** (decisiones D1–D12 resueltas en sesión).
Capa-3 (rationale). Adenda a `FABLE5_RESPONSE_V2_SENTINEL_TOKATA.md`.
Investigación LLM: `docs/superpowers/specs/2026-07-12-llm-timeseries-context-research.md`.
Plan cerrado (Capa-1 normativa): `docs/superpowers/plans/2026-07-12-v2-recalibration-plan.md`.
Reglas de ejecución (Capa-4): `docs/superpowers/specs/2026-07-12-agentic-workflow-rules.md`.

---

## 1. Decisiones resueltas (registro con rationale)

| # | Decisión | Resolución del usuario |
|---|---|---|
| D1 | Topología | **ALL-LOCAL v1** (Opción A). Razón: traders NUNCA backtestean con mercado abierto/posiciones vivas — la lentitud durante backtest es aceptable; simplicidad de implementación. B/C/cloud se evalúan cuando el sistema demuestre resultados positivos. Máquina del usuario (16GB) puede hacer de always-on 1-2 semanas si hace falta. ≥4 laptops futuras. **Cada trader tiene su propia cuenta MT5.** Arquitectura queda service-shaped ⇒ migrar a B/C = cambio de deployment, no de código. |
| D2 | Catálogo chat | 3 últimos por familia: `claude-opus-4-8` (GATED `abc123`), `claude-sonnet-5` (default), `claude-haiku-4-5`. Gate = guardarraíl de costo + discreción, NO seguridad; validación server-side siempre. |
| D3 | Lab | v1 = **Expert + tooltips exhaustivos por palanca** (traders no técnicos pero ansiosos de aprender). Arquitectura deja hooks para Guided y Assistant-first (la vía realista para traders = asistente potente). Contenido de tooltips = tarea ORC con revisión de usuario. |
| D4 | Regime | Diferido a S2/S3 con placeholder honesto — pero entendido como "en el momento correcto, ASAP con calidad completa", no abandonado. |
| D5 | News | RSS×2-3 (ForexLive/FXStreet/Investing) + FairEconomy/FF calendar JSON; SSE; frescura etiquetada honestamente (minutos, no segundos). |
| D6 | Learning-mode | Nueva sección **TRAINING** (nombre final; misma spec que "PRÁCTICA"). Motor paper compartido. **Positions gana 4º selector `TRAINING`** que imita HUMANO pero solo posiciones ficticias de training. |
| D7 | Contrato de métricas | v1: R-multiples + normalización por día; teórico = run baseline PRE-REGISTRADO (anti cherry-picking), nunca "mejor run". |
| D8 | Posiciones IA | v1 paper-AI; v2 demo-exec vía gateway. **Ampliado por el usuario** → arquitectura AI-trader §4 de este doc (activators + revisor Opus + DSL). |
| D9 | Auditoría TOKATA R1-R36 | Plegada al authoring del plan (tarea ORC-1: mapear cada R → hecho/backlog/gap como apéndice del plan). |
| D10 | Workflow | Confirmado: 3 lanes Sonnet-5-high, refactor habilitador primero, contratos congelados, orquestador commitea, reviews batched. + **regla de tiempo: tarea >12min problema / >20min grave / >35min trabajo descartable**. |
| D11 | Métricas card posición | Por-posición: MAE/MFE (+ per-portfolio/subset nice-to-have en header agregado). **Las cards soportan GRUPOS multi-lote** (estrategias que abren p.ej. 3 lotes con SL/TP distintos = 1 card grupo → hijos), mismo patrón 3-fichas EMASAR V1. |
| D12 | Modelo asistente | Sonnet 5 default; Opus 4.8 tras gate; medidor de presupuesto por sesión. |

Nota Runs (2.8): componentes de UI dedicados e intuitivos para lanzar backtest (TF + período custom); **el form NO permite pedir períodos sin datos** (restricción por `/api/coverage`).
Nota Study (2.5): requiere **sesión de frontend-design dedicada** (ORC-2) antes de implementar su UI (pre-registro, sweeps R24, lentes, ladder — mucha responsabilidad, debe ser intuitiva/accionable).
Meta de sesión declarada por usuario: **e2e test del sistema HOY** → Waves 0+A+B priorizan el camino e2e.

## 2. Determinismo multi-laptop (guardarraíles ALL-LOCAL)

Barras del mismo broker = canónicas server-side; la divergencia entra por acumulación-live, barra en formación, history-depth del terminal, y ticks (no deterministas entre terminales). Reglas duras:
1. Lake SIEMPRE construido/backfilleado desde historia del broker (`copy_rates_range`); NUNCA acumulación del stream vivo.
2. La barra en formación NUNCA se persiste al lake.
3. `manifest.json` por lake con content-hash; **cada run registra el hash del manifest** → comparabilidad entre laptops verificable.
4. Sims tick-level SOLO desde `copy_ticks_range` (o no se hacen; bars-only por defecto).

## 3. Presupuestos de recursos (ALL-LOCAL)

- Servicio idle ≤400MB RSS; request-path sin cargas pandas de archivo completo (pyarrow row-groups, row_group_size≈8192, particiones mensuales — span de partición NO gobierna memoria, el row-group sí).
- Backtests: worker pool = 1 (all-local), solo out-of-market por práctica operativa (aviso UI si hay posiciones abiertas = v2 nice-to-have).
- Frontend: heap ≤60MB por tab con chart (§6.2 diseño); payload /api/bars ≤5000 pts / ~1.5MB con fallback a tier más grueso (`served_tf`); primer render ≤2s; listas >200 filas virtualizadas; markers solo en ventana.

## 4. Arquitectura AI-trader (Wave E — GATED por discusión E0)

**Principio rector (decidido): la LLM CONFIGURA, el CÓDIGO MONITOREA.** Ninguna LLM en el loop de monitoreo de precio; la LLM emite intents declarativos que un rules-engine del servicio evalúa por tick/barra.

### 4.1 Order-Intent DSL (sketch, se congela en E0/E1)
```json
{
  "intent_id": "uuid", "symbol": "XAUUSD", "side": "long", "volume": 0.01,
  "entry": {"type": "band_bounce", "price": 4670.0, "tolerance_pips": 15,
             "confirm_bars": 1, "expires_at": "ISO"},
  "sl": {"type": "trailing", "fulfillment": "first_of",
          "rules": [{"kind": "pip_distance", "pips": 120},
                     {"kind": "indicator_cross", "fast": "EMA8", "slow": "EMA20", "direction": "against"},
                     {"kind": "indicator_reversal", "indicator": "SAR"}]},
  "tp": {"type": "static", "price": 4695.0},
  "monitor": {"model": "haiku", "watch": ["news_high_impact", "spread_spike"]},
  "provenance": {"origin": "ia", "activator": "strategy_id", "reviewer_model": "claude-opus-4-8", "chat_session": "id"}
}
```
- `entry.type ∈ {market, band_bounce, cross}`; `fulfillment ∈ {first_of, two_of}` (1–3 reglas simultáneas; cierra al cumplirse la primera o las dos primeras — pedido literal del usuario).
- Estado del intent: `pending → armed → active → closed|cancelled|expired`, con audit-trail por transición.

### 4.2 Flujo activador (brainstorm del usuario, a refinar en E0)
1. **Activators** = set pequeño de estrategias ganadoras. Trigger: proximidad %-al-umbral de activación O disparo efectivo.
2. Trigger → **agente revisor Opus 4.8 (effort medium)** recibe dossier snapshot (formato según investigación LLM) → veredicto `seconds | veto | modify` (puede ajustar SL/TP/umbrales, aportar contexto).
3. Si seconds → intent al rules-engine → v1 ejecuta en PAPER; v2 en demo vía gateway §4.4 + `guard_cuenta.assert_demo()`.
4. Opcional: **subagente monitor barato (Haiku)** por posición, chequeos acotados de un solo asunto, cadencia configurable.
5. Desde chat: custom tool `propose_position` → intent draft → confirmación del usuario → mismo pipeline. Máxima libertad de configuración de comportamientos, empezando simple para iterar.
6. E0 cierra: qué estrategias activan, umbrales exactos, presupuesto/frecuencia de invocaciones Opus, kill-switch, y qué info adicional lleva el dossier del revisor.

## 5. Asistente (B8) — resoluciones de la investigación adoptadas
1. Dossiers en **tablas Markdown** (no CSV pelado) hasta que el mini-eval (§6 del reporte) decida con datos propios.
2. **La LLM nunca agrega**: stats server-side (endpoint scorecard compartido UI/IA); el modelo interpreta y cita.
3. Layout de contexto: sistema estable+tools (prefijo cacheado) → documentos XML → pregunta AL FINAL (+30% first-party).
4. Precisión decimal fija por columna/instrumento; sin trucos de dígitos estilo GPT.
5. Posición = dossier 3-8K tok en contexto, 1 llamada; estrategia = híbrido stats+log compacto + tools con tope 25K tok/respuesta.

## 6. Assumptions etiquetadas
- ASSUMPTION: lightweight-charts custom primitives bastan para marcador intrabar fraccional; fallback especificado en plan (A5b) = anclaje a barra + hairline + hora exacta en tooltip.
- ASSUMPTION: Capitaria expone `copy_ticks_range` suficiente para replays tick; si no, replays bars-only.
- ASSUMPTION: agrupación multi-lote por (symbol+direction+magic idénticos y entradas ≤90s) — validar contra deals reales en B1.
