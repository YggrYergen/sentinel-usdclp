"""
SENTINEL v3.7 — Chat IA para Análisis de Mercado
Conecta con Claude (Anthropic) para análisis asistido por IA.

Modelos disponibles:
  - Opus 4.7:  Pensamiento profundo (extended thinking xhigh)
  - Sonnet 4.6: Respuesta rápida con thinking high
  - Haiku 4.5:  Veloz y económico, sin extended thinking

Capacidades:
  - Snapshot completo del dashboard (todos los valores visibles al operador)
  - Web search nativo (Anthropic server tool) con fuentes financieras
  - Historial de conversaciones persistente en disco local

Referencia: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool
"""
import os
import sys
import time
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict

logger = logging.getLogger("sentinel.ai_chat")

# ══════════════════════════════════════════════════════════
# MODELOS DISPONIBLES
# ══════════════════════════════════════════════════════════

@dataclass
class ModelConfig:
    id: str
    name: str
    icon: str
    max_tokens: int
    input_cost_per_mtok: float   # USD per million tokens
    output_cost_per_mtok: float
    supports_thinking: bool
    thinking_effort: str         # "xhigh", "high", "medium", "low" (only if supports_thinking)
    description: str

MODELS = {
    "opus": ModelConfig(
        id="claude-opus-4-7",
        name="🧠 Profundo (Opus 4.7)",
        icon="🧠",
        max_tokens=16384,
        input_cost_per_mtok=5.0,
        output_cost_per_mtok=25.0,
        supports_thinking=True,
        thinking_effort="xhigh",
        description="Pensamiento profundo xhigh. 3-5 min. Máxima calidad de análisis."
    ),
    "sonnet": ModelConfig(
        id="claude-sonnet-4-6",
        name="⚡ Rápido (Sonnet 4.6)",
        icon="⚡",
        max_tokens=8192,
        input_cost_per_mtok=3.0,
        output_cost_per_mtok=15.0,
        supports_thinking=True,
        thinking_effort="high",
        description="Respuesta rápida con thinking high. 15-45s."
    ),
    "haiku": ModelConfig(
        id="claude-haiku-4-5-20250315",
        name="💨 Veloz (Haiku 4.5)",
        icon="💨",
        max_tokens=8192,
        input_cost_per_mtok=0.80,
        output_cost_per_mtok=4.0,
        supports_thinking=False,
        thinking_effort="",
        description="Ultra-rápido y económico. ~5-10s. Sin extended thinking."
    ),
}

# Thinking effort levels available for manual override
THINKING_EFFORTS = ["xhigh", "high", "medium", "low"]

# ══════════════════════════════════════════════════════════
# WEB SEARCH CONFIGURATION
# ══════════════════════════════════════════════════════════

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,
    "allowed_domains": [
        "reuters.com", "bloomberg.com", "investing.com",
        "forexfactory.com", "bcentral.cl", "dailyfx.com",
        "tradingview.com", "cnbc.com", "marketwatch.com",
        "fxstreet.com", "kitco.com", "economiaynegocios.cl",
        "df.cl", "emol.com", "cooperativa.cl",
    ],
    "user_location": {
        "type": "approximate",
        "city": "Santiago",
        "region": "Metropolitana",
        "country": "CL",
        "timezone": "America/Santiago"
    }
}

# Cost per 1000 web searches (USD)
WEB_SEARCH_COST_PER_1K = 10.0

# ══════════════════════════════════════════════════════════
# CONTEXT BUILDER — Complete Dashboard Snapshot
# ══════════════════════════════════════════════════════════

def build_market_context(result: dict, price_info: dict,
                          derivative_data: dict = None,
                          cross_asset_data: dict = None,
                          cross_corr_hoy: dict = None,
                          web_search_enabled: bool = False) -> str:
    """
    Construye el system prompt con TODOS los datos del dashboard.

    Args:
        result: Output de core.calculate_composite()
        price_info: Output de feed.get_current_price()
        derivative_data: Dict con velocity, acceleration, momentum_text, n_ticks
        cross_asset_data: Dict con {asset_key: {m2_bps, m5_bps, fast_score, direction}}
        cross_corr_hoy: Dict con {asset_key: confianza_0_100}
        web_search_enabled: Si True, instruye a la IA a buscar noticias
    """
    comp = result.get("components", {})
    tech = comp.get("technical", {})
    corr = comp.get("correlation", {})
    tech_details = tech.get("details", {})
    tf_scores = tech_details.get("tf_scores", {})

    # ── TF breakdown (score + sub-scores por indicador) ──
    tf_lines = []
    for tf in ["M1", "M2", "M5", "M15"]:
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
    from sentinel.config import EXPECTED_CORRELATIONS
    corr_lines = []
    for k, v in corr_details.items():
        if v is None: continue
        exp = EXPECTED_CORRELATIONS.get(k, 0)
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
        CN = {"dxy":"DXY","copper":"Cobre","wti":"WTI","usdmxn":"MXN",
              "usdbrl":"BRL","audusd":"AUD","usdcnh":"CNH","sp500":"S&P"}
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

=== SCORE COMPUESTO (fórmula: Tech×0.75 + Corr×0.25) ===
Final: {result.get('composite_score', 0)} | Dirección: {result.get('direction', 'N/A')} | Señal: {result.get('signal', '')}
Técnico: {tech.get('score', 0):.1f} ({tech.get('direction', '?')}) [peso: 75%]
Correlación: {corr.get('score', 0):.1f} ({corr.get('direction', '?')}) [peso: 25%]

=== TIMEFRAMES (M1=40%, M2=30%, M5=20%, M15=10%) ===
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


# ══════════════════════════════════════════════════════════
# CHAT HISTORY PERSISTENCE
# ══════════════════════════════════════════════════════════

def _get_history_dir() -> Path:
    """Returns the chat history directory (inside sentinel folder)."""
    sentinel_dir = Path(__file__).parent
    history_dir = sentinel_dir / "chat_history"
    history_dir.mkdir(exist_ok=True)
    return history_dir


def save_conversation(messages: list, session_id: str):
    """Save conversation messages to a local JSON file."""
    try:
        history_dir = _get_history_dir()
        filepath = history_dir / f"chat_{session_id}.json"
        data = {
            "session_id": session_id,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "messages": messages,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving conversation: {e}")


def load_conversation(session_id: str) -> list:
    """Load conversation messages from a local JSON file."""
    try:
        filepath = _get_history_dir() / f"chat_{session_id}.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("messages", [])
    except Exception as e:
        logger.error(f"Error loading conversation: {e}")
    return []


def list_conversations() -> list:
    """List all saved conversations, newest first."""
    try:
        history_dir = _get_history_dir()
        files = sorted(history_dir.glob("chat_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        result = []
        for f in files[:20]:  # Last 20 conversations
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                result.append({
                    "session_id": data.get("session_id", f.stem),
                    "saved_at": data.get("saved_at", ""),
                    "n_messages": len(data.get("messages", [])),
                    "filepath": str(f),
                })
            except Exception:
                pass
        return result
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
    return []


# ══════════════════════════════════════════════════════════
# TRACKING DE COSTOS
# ══════════════════════════════════════════════════════════

@dataclass
class UsageTracker:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_web_searches: int = 0
    query_count: int = 0
    history: list = field(default_factory=list)

    def add_usage(self, input_tokens: int, output_tokens: int, model_key: str,
                  web_searches: int = 0):
        model = MODELS.get(model_key)
        if not model:
            return 0

        cost = (input_tokens * model.input_cost_per_mtok / 1_000_000 +
                output_tokens * model.output_cost_per_mtok / 1_000_000)

        # Add web search cost
        if web_searches > 0:
            cost += web_searches * WEB_SEARCH_COST_PER_1K / 1000
            self.total_web_searches += web_searches

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost
        self.query_count += 1
        self.history.append({
            "time": time.strftime("%H:%M:%S"),
            "model": model_key,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "web_searches": web_searches,
            "cost_usd": round(cost, 4),
        })

        logger.info(f"AI query #{self.query_count}: {model_key} "
                     f"{input_tokens}→{output_tokens} tokens, "
                     f"{web_searches} searches, ${cost:.4f}")

        return cost

    def get_summary(self) -> str:
        ws = f" | 🔍 {self.total_web_searches} búsquedas" if self.total_web_searches > 0 else ""
        return (f"💰 ${self.total_cost_usd:.3f} | "
                f"📊 {self.query_count} consultas | "
                f"📥 {self.total_input_tokens:,}→📤 {self.total_output_tokens:,} tokens{ws}")


# ══════════════════════════════════════════════════════════
# CLIENTE PRINCIPAL
# ══════════════════════════════════════════════════════════

class SentinelAI:
    """Cliente de IA para SENTINEL. Soporta web search y extended thinking."""

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = None
        self.tracker = UsageTracker()
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            logger.info("ANTHROPIC_API_KEY no configurada — modo mock activado")
            return

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
            logger.info("Cliente Anthropic inicializado correctamente")
        except ImportError:
            logger.error("pip install anthropic requerido")
            self.client = None
        except Exception as e:
            logger.error(f"Error inicializando Anthropic: {e}")
            self.client = None

    def set_api_key(self, key: str):
        """Configura API key en runtime (desde UI)."""
        self.api_key = key
        os.environ["ANTHROPIC_API_KEY"] = key
        self._init_client()

    @property
    def is_available(self) -> bool:
        return self.client is not None

    def chat(self, user_message: str, model_key: str,
             system_prompt: str, conversation: list,
             web_search_enabled: bool = False,
             thinking_effort_override: str = None) -> dict:
        """
        Envía mensaje al modelo seleccionado.

        Args:
            user_message: Pregunta del usuario
            model_key: "opus", "sonnet", "haiku"
            system_prompt: System prompt con datos del dashboard
            conversation: Historial de mensajes previos
            web_search_enabled: Si True, habilita web search (deshabilita thinking)
            thinking_effort_override: Override manual del effort ("xhigh","high","medium","low")

        Returns dict:
            content: str (respuesta)
            citations: list of {url, title, cited_text}
            input_tokens: int
            output_tokens: int
            web_searches: int
            cost_usd: float
            duration_s: float
            model: str
            error: str or None
        """
        model = MODELS.get(model_key)
        if not model:
            return {"content": f"Modelo '{model_key}' no reconocido.", "error": "invalid_model",
                    "citations": [], "input_tokens": 0, "output_tokens": 0,
                    "web_searches": 0, "cost_usd": 0, "duration_s": 0, "model": model_key}

        # Mock mode
        if not self.is_available:
            return self._mock_response(user_message, model_key)

        # Build messages
        messages = list(conversation)
        messages.append({"role": "user", "content": user_message})

        # Build request kwargs
        kwargs = {
            "model": model.id,
            "max_tokens": model.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }

        # Web search and thinking are mutually exclusive in the API
        if web_search_enabled:
            # Web search mode: tools enabled, NO extended thinking
            kwargs["tools"] = [WEB_SEARCH_TOOL]
        elif model.supports_thinking:
            # Thinking mode: extended thinking enabled, NO tools
            effort = thinking_effort_override or model.thinking_effort
            if effort and effort in THINKING_EFFORTS:
                kwargs["thinking"] = {"type": "enabled", "effort": effort}

        start = time.time()
        try:
            response = self.client.messages.create(**kwargs)
            duration = time.time() - start

            # Extract text content and citations
            content = ""
            citations = []
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
                    # Extract citations from text blocks
                    if hasattr(block, 'citations') and block.citations:
                        for cite in block.citations:
                            if hasattr(cite, 'url'):
                                citations.append({
                                    "url": getattr(cite, 'url', ''),
                                    "title": getattr(cite, 'title', ''),
                                    "cited_text": getattr(cite, 'cited_text', ''),
                                })

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Count web searches
            web_searches = 0
            if hasattr(response.usage, 'server_tool_use') and response.usage.server_tool_use:
                web_searches = getattr(response.usage.server_tool_use,
                                       'web_search_requests', 0)

            cost = self.tracker.add_usage(input_tokens, output_tokens, model_key,
                                          web_searches=web_searches)

            # Deduplicate citations
            seen_urls = set()
            unique_citations = []
            for c in citations:
                if c["url"] not in seen_urls:
                    seen_urls.add(c["url"])
                    unique_citations.append(c)

            logger.info(f"Respuesta de {model.id} en {duration:.1f}s, "
                        f"{web_searches} web searches")

            return {
                "content": content,
                "citations": unique_citations,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "web_searches": web_searches,
                "cost_usd": cost,
                "duration_s": round(duration, 1),
                "model": model_key,
                "error": None,
            }

        except Exception as e:
            duration = time.time() - start
            error_msg = str(e)
            logger.error(f"Error en chat: {error_msg}")

            return {
                "content": f"⚠️ Error: {error_msg}",
                "citations": [],
                "input_tokens": 0,
                "output_tokens": 0,
                "web_searches": 0,
                "cost_usd": 0,
                "duration_s": round(duration, 1),
                "model": model_key,
                "error": error_msg,
            }

    def _mock_response(self, user_message: str, model_key: str) -> dict:
        """Respuesta simulada cuando no hay API key."""
        model = MODELS[model_key]
        time.sleep(1)  # Simular latencia

        mock_content = (
            f"🔒 **Modo Demo** — API key no configurada.\n\n"
            f"Para activar el asistente IA ({model.name}):\n\n"
            f"1. Crear cuenta en [console.anthropic.com](https://console.anthropic.com)\n"
            f"2. Generar una API key\n"
            f"3. Configurar en el campo de abajo o como variable de entorno:\n"
            f"   `set ANTHROPIC_API_KEY=sk-ant-xxxxx`\n\n"
            f"**Tu pregunta fue:** {user_message}\n\n"
            f"Con la API activa, recibirías un análisis completo usando "
            f"todos los datos del dashboard en tiempo real, con capacidad de "
            f"búsqueda web en fuentes financieras oficiales."
        )

        return {
            "content": mock_content,
            "citations": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "web_searches": 0,
            "cost_usd": 0,
            "duration_s": 1.0,
            "model": model_key,
            "error": None,
        }
