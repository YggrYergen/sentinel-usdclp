"""
SENTINEL v3.4 — Chat IA para Análisis de Mercado
Conecta con Claude (Anthropic) para análisis asistido por IA.
Soporta Opus 4.7 (pensamiento profundo) y Sonnet 4.6 (respuesta rápida).

Mock mode cuando no hay API key configurada.

Referencia: https://docs.anthropic.com/en/docs/build-with-claude/overview
"""
import os
import time
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("sentinel.ai_chat")

# ══════════════════════════════════════════════════════════
# MODELOS DISPONIBLES
# ══════════════════════════════════════════════════════════

@dataclass
class ModelConfig:
    id: str
    name: str
    icon: str
    effort: str
    max_tokens: int
    input_cost_per_mtok: float  # USD per million tokens
    output_cost_per_mtok: float
    description: str

MODELS = {
    "opus": ModelConfig(
        id="claude-opus-4-7",
        name="🧠 Profundo (Opus 4.7)",
        icon="🧠",
        effort="xhigh",
        max_tokens=4096,
        input_cost_per_mtok=5.0,
        output_cost_per_mtok=25.0,
        description="Pensamiento profundo. 3-5 min. Máxima calidad de análisis."
    ),
    "sonnet": ModelConfig(
        id="claude-sonnet-4-6",
        name="⚡ Rápido (Sonnet 4.6)",
        icon="⚡",
        effort="high",
        max_tokens=2048,
        input_cost_per_mtok=3.0,
        output_cost_per_mtok=15.0,
        description="Respuesta rápida. 15-45s. Alta calidad."
    ),
}

# ══════════════════════════════════════════════════════════
# CONTEXT BUILDER
# ══════════════════════════════════════════════════════════

def build_market_context(result: dict, price_info: dict, 
                          derivative_data: dict = None) -> str:
    """
    Construye el system prompt con todos los datos del mercado actual.
    
    Args:
        result: Output de core.calculate_composite()
        price_info: Output de feed.get_current_price()
        derivative_data: Dict con velocity, acceleration, momentum_text, n_ticks
    """
    comp = result.get("components", {})
    tech = comp.get("technical", {})
    corr = comp.get("correlation", {})
    tech_details = tech.get("details", {})
    tf_scores = tech_details.get("tf_scores", {})
    
    # Build TF breakdown
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
            f"    macd_h={sigs.get('macd_histogram',0):.5f} bb_pct={sigs.get('bb_pct',0):.2f}"
        )
    
    # Build correlation breakdown
    corr_details = corr.get("details", {}).get("correlations", {})
    from sentinel.config import EXPECTED_CORRELATIONS
    corr_lines = []
    for k, v in corr_details.items():
        if v is None: continue
        exp = EXPECTED_CORRELATIONS.get(k, 0)
        delta = v - exp
        status = "OK" if abs(delta) < 0.2 else ("WARN" if abs(delta) < 0.4 else "BREAK")
        corr_lines.append(f"  {k}: real={v:+.2f} esperada={exp:+.2f} Δ={delta:+.2f} [{status}]")
    
    # Build levels
    levels = result.get("levels", {})
    combined = levels.get("combined", {})
    above = combined.get("above", [])
    below = combined.get("below", [])
    level_lines = []
    for lv in reversed(above):
        level_lines.append(f"  R: {lv['price']:.2f} ({lv['pct']:+.2f}%)")
    level_lines.append(f"  >>> PRECIO ACTUAL: {price_info.get('bid', 0):.2f} <<<")
    for lv in below:
        level_lines.append(f"  S: {lv['price']:.2f} ({lv['pct']:+.2f}%)")
    
    # Build derivatives
    deriv_text = "Sin datos de derivadas todavía."
    if derivative_data and derivative_data.get("n_ticks", 0) >= 2:
        deriv_text = (
            f"Velocidad (1ª derivada): {derivative_data.get('velocity', 0):+.4f}/s\n"
            f"Aceleración (2ª derivada): {derivative_data.get('acceleration', 0):+.5f}/s²\n"
            f"Momentum: {derivative_data.get('momentum_text', 'N/A')}\n"
            f"Buffer: {derivative_data.get('n_ticks', 0)} ticks"
        )
    
    # Build signals v1
    m1s = tf_scores.get("M1", {}).get("score", 50)
    m2s = tf_scores.get("M2", {}).get("score", 50)
    m5s = tf_scores.get("M5", {}).get("score", 50)
    sig_5s = m1s
    sig_30s = m1s * 0.6 + m2s * 0.4
    sig_1m = m1s * 0.4 + m2s * 0.3 + m5s * 0.3
    
    alerts = result.get("alerts", [])
    
    context = f"""Eres un analista de trading experto en USD/CLP y mercados emergentes.
Tienes acceso a datos en tiempo real del sistema SENTINEL. Tu rol es ayudar al trader
a tomar decisiones informadas, NUNCA recomendar posiciones directamente.

Contexto del trader: scalper de USDCLP, posiciones de 1-2 minutos típicamente,
máximo 30 min. Opera con Capitaria vía MetaTrader 5.

═══ DATOS EN TIEMPO REAL ═══

=== PRECIO ===
Bid: {price_info.get('bid', 0):.2f} | Ask: {price_info.get('ask', 0):.2f} | Spread: {price_info.get('spread', 0):.2f}

=== SCORE COMPUESTO ===
Final: {result.get('composite_score', 0)} | Dirección: {result.get('direction', 'N/A')}
Técnico: {tech.get('score', 0):.1f} ({tech.get('direction', '?')}) [peso: 75%]
Correlación: {corr.get('score', 0):.1f} ({corr.get('direction', '?')}) [peso: 25%]

=== TIMEFRAMES (M1=40%, M2=30%, M5=20%, M15=10%) ===
{chr(10).join(tf_lines)}

=== DERIVADAS ===
{deriv_text}

=== SEÑALES ===
Pulso 5s: {sig_5s:.0f} | Corto 30s: {sig_30s:.0f} | Medio 1m: {sig_1m:.0f}

=== CORRELACIONES CROSS-ASSET ===
{chr(10).join(corr_lines) if corr_lines else "No disponibles"}

=== NIVELES S/R ===
{chr(10).join(level_lines) if level_lines else "No disponibles"}

=== ALERTAS ===
{chr(10).join(alerts[:5]) if alerts else "Sin alertas activas"}

═══ REGLAS ═══
1. NUNCA digas "compra" o "vende" directamente. Analiza los datos y presenta escenarios.
2. Sé conciso. El trader necesita info rápida, no ensayos.
3. Si los datos sugieren NO operar, dilo claramente.
4. Menciona siempre los riesgos relevantes.
5. Responde en español.
"""
    return context


# ══════════════════════════════════════════════════════════
# TRACKING DE COSTOS
# ══════════════════════════════════════════════════════════

@dataclass
class UsageTracker:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    query_count: int = 0
    history: list = field(default_factory=list)
    
    def add_usage(self, input_tokens: int, output_tokens: int, model_key: str):
        model = MODELS.get(model_key)
        if not model:
            return
        
        cost = (input_tokens * model.input_cost_per_mtok / 1_000_000 +
                output_tokens * model.output_cost_per_mtok / 1_000_000)
        
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost
        self.query_count += 1
        self.history.append({
            "time": time.strftime("%H:%M:%S"),
            "model": model_key,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 4),
        })
        
        logger.info(f"AI query #{self.query_count}: {model_key} "
                     f"{input_tokens}→{output_tokens} tokens, ${cost:.4f}")
        
        return cost
    
    def get_summary(self) -> str:
        return (f"💰 ${self.total_cost_usd:.3f} | "
                f"📊 {self.query_count} consultas | "
                f"📥 {self.total_input_tokens:,}→📤 {self.total_output_tokens:,} tokens")


# ══════════════════════════════════════════════════════════
# CLIENTE PRINCIPAL
# ══════════════════════════════════════════════════════════

class SentinelAI:
    """Cliente de IA para SENTINEL. Soporta mock mode."""
    
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
             system_prompt: str, conversation: list) -> dict:
        """
        Envía mensaje al modelo seleccionado.
        
        Returns dict:
            content: str (respuesta)
            input_tokens: int
            output_tokens: int
            cost_usd: float
            duration_s: float
            model: str
            error: str or None
        """
        model = MODELS.get(model_key)
        if not model:
            return {"content": f"Modelo '{model_key}' no reconocido.", "error": "invalid_model"}
        
        # Mock mode
        if not self.is_available:
            return self._mock_response(user_message, model_key)
        
        # Build messages
        messages = list(conversation)
        messages.append({"role": "user", "content": user_message})
        
        start = time.time()
        try:
            response = self.client.messages.create(
                model=model.id,
                max_tokens=model.max_tokens,
                thinking={"type": "enabled", "effort": model.effort},
                system=system_prompt,
                messages=messages,
            )
            
            duration = time.time() - start
            
            # Extract text content (skip thinking blocks)
            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
            
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = self.tracker.add_usage(input_tokens, output_tokens, model_key)
            
            logger.info(f"Respuesta de {model.id} en {duration:.1f}s")
            
            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
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
                "input_tokens": 0,
                "output_tokens": 0,
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
            f"todos los datos del dashboard en tiempo real."
        )
        
        return {
            "content": mock_content,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0,
            "duration_s": 1.0,
            "model": model_key,
            "error": None,
        }
