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

    Thin wrapper over `sentinel_engine.ai_context._build_context_text` — the
    SINGLE producer of AI context, shared with the headless-engine path
    (`sentinel_engine.ai_context.render_ai_context`). This kills prompt drift
    by construction: the body lives in exactly one place. Weights are sourced
    (not literals) from `sentinel.config.WEIGHTS` / `sentinel.technical_scorer.TF_WEIGHTS`
    and expected-correlation baselines from `sentinel.config.EXPECTED_CORRELATIONS`
    — matching the pre-existing Defect-3 regression contract.

    Args:
        result: Output de core.calculate_composite()
        price_info: Output de feed.get_current_price()
        derivative_data: Dict con velocity, acceleration, momentum_text, n_ticks
        cross_asset_data: Dict con {asset_key: {m2_bps, m5_bps, fast_score, direction}}
        cross_corr_hoy: Dict con {asset_key: confianza_0_100}
        web_search_enabled: Si True, instruye a la IA a buscar noticias
    """
    from sentinel_engine.ai_context import _build_context_text
    from sentinel.config import WEIGHTS, EXPECTED_CORRELATIONS
    from sentinel.technical_scorer import TF_WEIGHTS

    w_tech = WEIGHTS.technical
    w_corr = WEIGHTS.correlation
    tf_w_pct = {tf: TF_WEIGHTS.get(tf, 0) * 100 for tf in ["M1", "M2", "M5", "M15"]}

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
        expected_correlations=EXPECTED_CORRELATIONS,
    )


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
