"""
sentinel_engine.ai_context — the ONE-AND-ONLY producer of AI system-prompt context.

`render_ai_context(snapshot, cfg)` builds the AI system prompt from a headless
`sentinel_engine.engine.Snapshot`, deriving EVERY weight/number from the
`InstrumentConfig` (`cfg`) and the snapshot's already-config-sourced component
weights — NEVER from literals. This is the structural, permanent fix for
Defect 3 (prompt drift): the live dashboard's `sentinel.ai_chat.build_market_context`
is now a thin wrapper over the same shared body (`_build_context_text`), so the
context text can no longer drift between the two call sites by construction.

DETERMINISM: `render_ai_context` is a pure function of `(snapshot, cfg)` plus
optional live-UI extras (price/derivatives/cross-asset) that default to None.
It contains NO `datetime.now()`, no wall-clock, no randomness, and no
dict-ordering nondeterminism. Given a fixed `(feed, config)`, `Engine.step()`
produces a byte-stable `ai_context`.

This module is purely additive to the scoring path: it reads a Snapshot, never
mutates one.
"""
from __future__ import annotations

from typing import Any

# Per-timeframe technical sub-score weights shown in the prompt header. GLOBAL
# (not per-instrument) — identical to `sentinel_engine.technical._SUBWEIGHTS`
# and the inline dict in `sentinel.technical_scorer`. Displayed only, not used
# for any scoring here.
_TF_ORDER = ["M1", "M2", "M5", "M15"]


def _build_context_text(
    result: dict,
    price_info: dict | None,
    derivative_data: dict | None,
    cross_asset_data: dict | None,
    cross_corr_hoy: dict | None,
    web_search_enabled: bool,
    *,
    w_tech: float,
    w_corr: float,
    tf_w_pct: dict,
    expected_correlations: dict,
) -> str:
    """Single source of truth for the AI system-prompt text.

    `result` is a snapshot-shaped dict (either `Snapshot.to_dict()` or the
    legacy `SentinelCore.calculate_composite()` dict — they share the same
    `components`/`levels`/`alerts`/`divergences` shape). All weights and
    expected-correlation baselines are INJECTED by the caller (sourced from
    config, never literals).
    """
    price_info = price_info or {}
    comp = result.get("components", {})
    tech = comp.get("technical", {})
    corr = comp.get("correlation", {})
    tech_details = tech.get("details", {})
    tf_scores = tech_details.get("tf_scores", {})

    # ── TF breakdown (score + sub-scores por indicador) ──
    tf_lines = []
    for tf in _TF_ORDER:
        d = tf_scores.get(tf, {})
        sigs = d.get("signals", {})
        dets = d.get("details", {})
        tf_lines.append(
            f"  {tf}: score={d.get('score',50):.0f} dir={d.get('direction','?')} "
            f"rsi={sigs.get('rsi',0):.1f}\n"
            f"    EMA={dets.get('ema',{}).get('score',0):.0f} "
            f"RSI={dets.get('rsi',{}).get('score',0):.0f} "
            f"MACD={dets.get('macd',{}).get('score',0):.0f} "
            f"BB={dets.get('bb',{}).get('score',0):.0f} "
            f"PA={dets.get('pa',{}).get('score',0):.0f}\n"
            f"    ema9={sigs.get('ema_9',0):.2f} ema21={sigs.get('ema_21',0):.2f} "
            f"ema50={sigs.get('ema_50',0):.2f}\n"
            f"    macd_h={sigs.get('macd_histogram',0):.5f} bb_pct={sigs.get('bb_pct',0):.2f} "
            f"ema_cross={sigs.get('ema_cross',0)}"
        )

    # ── Correlation breakdown ──
    corr_details = corr.get("details", {}).get("correlations", {})
    corr_lines = []
    for k, v in corr_details.items():
        if v is None:
            continue
        exp = expected_correlations.get(k, 0)
        delta = v - exp
        status = "OK" if abs(delta) < 0.2 else ("WARN" if abs(delta) < 0.4 else "BREAK")
        # Add HOY confidence if available
        hoy = cross_corr_hoy.get(k, -1) if cross_corr_hoy else -1
        hoy_txt = f" HOY={hoy}%" if hoy >= 0 else " HOY=--"
        corr_lines.append(
            f"  {k}: real={v:+.2f} esperada={exp:+.2f} Δ={delta:+.2f} [{status}]{hoy_txt}"
        )

    # ── Cross-asset movements ──
    cross_lines = []
    if cross_asset_data:
        CN = {"dxy": "DXY", "copper": "Cobre", "wti": "WTI", "usdmxn": "MXN",
              "usdbrl": "BRL", "audusd": "AUD", "usdcnh": "CNH", "sp500": "S&P"}
        for k, d in cross_asset_data.items():
            m2 = d.get("m2_bps", 0)
            m5 = d.get("m5_bps", 0)
            fsc = d.get("fast_score", 50)
            dr = d.get("direction", "?")
            cross_lines.append(
                f"  {CN.get(k,k)}: 2min={m2:+.1f}bps 5min={m5:+.1f}bps tech_fast={fsc:.0f} dir={dr}"
            )

    # ── Levels ──
    levels = result.get("levels", {})
    combined = levels.get("combined", {})
    above = combined.get("above", [])
    below = combined.get("below", [])
    position = levels.get("position", "")
    level_lines = []
    for lv in reversed(above):
        level_lines.append(f"  R: {lv['price']:.2f} ({lv['pct']:+.3f}%) {lv.get('label','')}")
    level_lines.append(f"  >>> PRECIO: {price_info.get('bid', 0):.2f} <<<")
    for lv in below:
        level_lines.append(f"  S: {lv['price']:.2f} ({lv['pct']:+.3f}%) {lv.get('label','')}")

    # ── Derivatives ──
    deriv_text = "Sin datos de derivadas todavía (buffer llenándose)."
    if derivative_data and derivative_data.get("n_ticks", 0) >= 2:
        deriv_text = (
            f"Velocidad (1ª derivada): {derivative_data.get('velocity', 0):+.4f}/s\n"
            f"Aceleración (2ª derivada): {derivative_data.get('acceleration', 0):+.5f}/s²\n"
            f"Momentum: {derivative_data.get('momentum_text', 'N/A')}\n"
            f"Buffer: {derivative_data.get('n_ticks', 0)} ticks"
        )

    # ── Signals v1 ──
    m1s = tf_scores.get("M1", {}).get("score", 50)
    m2s = tf_scores.get("M2", {}).get("score", 50)
    m5s = tf_scores.get("M5", {}).get("score", 50)
    sig_5s = m1s
    sig_30s = m1s * 0.6 + m2s * 0.4
    sig_1m = m1s * 0.4 + m2s * 0.3 + m5s * 0.3

    # ── RSI divergences ──
    rsi_divs = tech_details.get("rsi_divergences", [])
    rsi_div_lines = []
    for rd in rsi_divs[:3]:
        rsi_div_lines.append(f"  {rd.get('description', '')}")

    # ── Alerts ──
    alerts = result.get("alerts", [])
    divergences = result.get("divergences", [])
    div_lines = [d.get("description", "") for d in divergences[:3]]

    # ── Web search instruction ──
    web_instruction = ""
    if web_search_enabled:
        web_instruction = """
═══ BÚSQUEDA WEB ═══
Tienes acceso a búsqueda web en fuentes financieras oficiales.
ÚSALA PROACTIVAMENTE para:
- Buscar noticias que afecten USD, CLP, cobre, petróleo, LATAM
- Verificar eventos económicos programados (FOMC, NFP, decisión tasa BCCh)
- Contexto macro: inflación, aranceles, política monetaria
- Datos de commodities y flujos de capital
Cita SIEMPRE las fuentes con URL. Prioriza: Reuters, Bloomberg, Investing.com, BancoCentral.cl.
"""

    context = f"""Eres un analista de trading experto en USD/CLP, mercados emergentes y commodities.
Tienes acceso a un snapshot completo del sistema SENTINEL en tiempo real.

Tu rol: ayudar al operador a tomar decisiones informadas de scalping (1-30 min).
NUNCA recomiendes "compra" o "vende" directamente — presenta escenarios con probabilidades.

Contexto del operador: scalper de USDCLP vía MetaTrader 5 (broker Capitaria).
Posiciones típicas: 1-2 minutos, máximo 30 min. Capital ~$1.5M CLP.
{web_instruction}
═══ SNAPSHOT DEL DASHBOARD (en vivo) ═══

=== PRECIO ===
Bid: {price_info.get('bid', 0):.2f} | Ask: {price_info.get('ask', 0):.2f} | Spread: {price_info.get('spread', 0):.2f}

=== SCORE COMPUESTO (fórmula: Tech×{w_tech:.2f} + Corr×{w_corr:.2f}) ===
Final: {result.get('composite_score', 0)} | Dirección: {result.get('direction', 'N/A')} | Señal: {result.get('signal', '')}
Técnico: {tech.get('score', 0):.1f} ({tech.get('direction', '?')}) [peso: {w_tech*100:.0f}%]
Correlación: {corr.get('score', 0):.1f} ({corr.get('direction', '?')}) [peso: {w_corr*100:.0f}%]

=== TIMEFRAMES (M1={tf_w_pct['M1']:.0f}%, M2={tf_w_pct['M2']:.0f}%, M5={tf_w_pct['M5']:.0f}%, M15={tf_w_pct['M15']:.0f}%) ===
Cada TF: Score_TF = EMA×30% + RSI×20% + MACD×25% + BB×15% + PA×10%
{chr(10).join(tf_lines)}

=== SEÑALES v1 (indicadores técnicos blended) ===
⚡ Pulso 5s (100% M1): {sig_5s:.0f}
🔄 Corto 30s (60%M1+40%M2): {sig_30s:.0f}
📊 Medio 1m (40%M1+30%M2+30%M5): {sig_1m:.0f}

=== DERIVADAS DE PRECIO ===
{deriv_text}

=== CORRELACIONES CROSS-ASSET ===
Correlación rolling Pearson 50 períodos H1. HOY = M1 Pearson 30 barras dirigido.
{chr(10).join(corr_lines) if corr_lines else "No disponibles"}

=== MOVIMIENTO RECIENTE CROSS-ASSETS ===
{chr(10).join(cross_lines) if cross_lines else "No disponibles"}

=== NIVELES S/R (Camarilla + Swing Detection) ===
Posición: {position}
{chr(10).join(level_lines) if level_lines else "No disponibles"}

=== DIVERGENCIAS RSI ENTRE TIMEFRAMES ===
{chr(10).join(rsi_div_lines) if rsi_div_lines else "Sin divergencias RSI detectadas"}

=== DIVERGENCIAS CROSS-ASSET ===
{chr(10).join(div_lines) if div_lines else "Sin divergencias cross-asset"}

=== ALERTAS ACTIVAS ===
{chr(10).join(alerts[:5]) if alerts else "Sin alertas activas"}

═══ REGLAS ═══
1. NUNCA digas "compra" o "vende" directamente. Analiza escenarios.
2. Sé conciso y accionable. El operador necesita info rápida bajo presión.
3. Si los datos sugieren NO operar, dilo claramente y explica por qué.
4. Menciona siempre los riesgos y niveles clave (S/R) relevantes.
5. Si hay divergencias RSI o cross-asset, adviértelas prominentemente.
6. Responde en español.
"""
    return context


def render_ai_context(
    snapshot: Any,
    cfg: Any,
    *,
    price_info: dict | None = None,
    derivative_data: dict | None = None,
    cross_asset_data: dict | None = None,
    cross_corr_hoy: dict | None = None,
    web_search_enabled: bool = False,
) -> str:
    """Render the AI system-prompt context from a headless `Snapshot` + `cfg`.

    This is the single producer of AI context for the engine path. EVERY
    weight/number is derived from config, never a literal:
      - composite weights come from the snapshot's config-sourced component
        weights (`components[...]["weight"]`, set from `cfg.composite.weights`),
      - per-timeframe weights come from `cfg.technical.tf_weights`,
      - expected-correlation baselines come from `cfg.expected_correlations`.

    Live-UI extras (price/derivatives/cross-asset/HOY confidence/web-search)
    default to None and are NOT part of the deterministic scoring snapshot; the
    engine/golden path passes none of them, so the output is byte-stable given
    `(feed, config)`. NO wall-clock or randomness is used.
    """
    result = snapshot.to_dict()
    comp = result.get("components", {})
    w_tech = comp.get("technical", {}).get("weight", cfg.composite.weights["technical"])
    w_corr = comp.get("correlation", {}).get("weight", cfg.composite.weights["correlation"])
    tf_weights = cfg.technical.tf_weights
    tf_w_pct = {tf: tf_weights.get(tf, 0) * 100 for tf in _TF_ORDER}

    return _build_context_text(
        result,
        price_info,
        derivative_data,
        cross_asset_data,
        cross_corr_hoy,
        web_search_enabled,
        w_tech=w_tech,
        w_corr=w_corr,
        tf_w_pct=tf_w_pct,
        expected_correlations=cfg.expected_correlations,
    )
