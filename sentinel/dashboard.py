"""
SENTINEL v3 — Dashboard Streamlit
Panel de control en tiempo real para USD/CLP
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime
import time

from sentinel.config import (SYMBOLS, RISK, WEIGHTS, SCORE_ALERT_THRESHOLD,
    SCORE_STRONG_THRESHOLD, DASHBOARD_REFRESH_SECONDS, MARKET_OPEN, MARKET_CLOSE)
from sentinel.data_feed import DataFeed
from sentinel.sentinel_core import SentinelCore
from sentinel.risk_manager import calculate_position_size, check_daily_limits
from sentinel.indicators import calculate_all

# ══════════════════════════════════════════════════════════
# CONFIGURACIÓN DE PÁGINA
# ══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SENTINEL v3 — USD/CLP",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .big-score { font-size: 72px; font-weight: bold; text-align: center; padding: 20px; border-radius: 15px; margin: 10px 0; }
    .score-green { background: linear-gradient(135deg, #1a472a, #2d6a4f); color: #52b788; border: 2px solid #52b788; }
    .score-yellow { background: linear-gradient(135deg, #5c4b1f, #8a6d3b); color: #ffd166; border: 2px solid #ffd166; }
    .score-red { background: linear-gradient(135deg, #4a1a1a, #8b2c2c); color: #ef476f; border: 2px solid #ef476f; }
    .metric-card { background: #1a1d23; border-radius: 10px; padding: 15px; margin: 5px 0; border-left: 4px solid #4cc9f0; }
    .alert-box { background: #2d1f1f; border-left: 4px solid #ef476f; padding: 10px; margin: 5px 0; border-radius: 5px; }
    div[data-testid="stMetric"] { background: #1a1d23; padding: 15px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# INICIALIZACIÓN
# ══════════════════════════════════════════════════════════
@st.cache_resource
def init_system():
    feed = DataFeed(mode="auto")
    core = SentinelCore(feed)
    return feed, core

feed, core = init_system()

# ══════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=60)
    st.title("SENTINEL v3")
    st.caption("Sistema de Trading USD/CLP")
    st.divider()
    
    # Estado de conexión
    status = feed.get_status()
    if status["mt5_connected"]:
        st.success("🟢 MT5 Conectado")
    else:
        st.warning(f"🟡 Modo: {status['mode'].upper()}")
    
    now = datetime.now().time()
    if MARKET_OPEN <= now <= MARKET_CLOSE:
        st.success("🟢 Mercado ABIERTO")
    else:
        st.error("🔴 Fuera de horario operativo")
    
    st.divider()
    st.subheader("📊 Input DOM Manual")
    dom_score = st.slider("Score DOM (0-100)", 0, 100, 50, key="dom_s")
    dom_dir = st.selectbox("Dirección DOM", ["NEUTRAL", "LONG", "SHORT"], key="dom_d")
    core.set_dom_input(dom_score, dom_dir)
    
    st.divider()
    st.subheader("⚙️ Configuración")
    st.metric("Capital", f"${RISK.capital_clp:,.0f} CLP")
    st.metric("Riesgo/Trade", f"{RISK.risk_per_trade_pct*100}%")
    st.metric("Max Pérdida Diaria", f"{RISK.max_daily_loss_pct*100}%")
    st.metric("Max Trades/Día", RISK.max_trades_per_day)
    
    st.divider()
    auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)

# ══════════════════════════════════════════════════════════
# CÁLCULO PRINCIPAL
# ══════════════════════════════════════════════════════════
result = core.calculate_composite()

# ══════════════════════════════════════════════════════════
# HEADER - SCORE PRINCIPAL
# ══════════════════════════════════════════════════════════
st.markdown("---")
col_score, col_dir, col_signal = st.columns([2, 1, 1])

with col_score:
    score = result["composite_score"]
    if score >= SCORE_STRONG_THRESHOLD:
        css_class = "score-green"
    elif score >= SCORE_ALERT_THRESHOLD:
        css_class = "score-yellow"
    else:
        css_class = "score-red"
    st.markdown(f'<div class="big-score {css_class}">{score}</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center; color: #888;'>Score Compuesto SENTINEL</p>", unsafe_allow_html=True)

with col_dir:
    dir_emoji = {"LONG": "📈", "SHORT": "📉", "NEUTRAL": "➡️"}
    dir_color = {"LONG": "#52b788", "SHORT": "#ef476f", "NEUTRAL": "#ffd166"}
    d = result["direction"]
    st.markdown(f"<h1 style='text-align:center; color:{dir_color[d]};'>{dir_emoji[d]}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align:center; color:{dir_color[d]};'>{d}</h2>", unsafe_allow_html=True)

with col_signal:
    st.markdown(f"<h2 style='text-align:center;'>{result['signal']}</h2>", unsafe_allow_html=True)
    if result["blocked"]:
        st.error(f"🚫 {result['block_reason']}")

# Precio actual
price_info = feed.get_current_price(SYMBOLS["target"])
if price_info["bid"] > 0:
    pcol1, pcol2, pcol3, pcol4 = st.columns(4)
    pcol1.metric("💲 Bid", f"{price_info['bid']:.2f}")
    pcol2.metric("💲 Ask", f"{price_info['ask']:.2f}")
    pcol3.metric("📏 Spread", f"{price_info['spread']:.2f}")
    pcol4.metric("🕐 Hora", datetime.now().strftime("%H:%M:%S"))

# ══════════════════════════════════════════════════════════
# ALERTAS
# ══════════════════════════════════════════════════════════
if result["alerts"]:
    st.markdown("### 🚨 Alertas Activas")
    for alert in result["alerts"]:
        st.markdown(f'<div class="alert-box">{alert}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# COMPONENTES DEL SCORE
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 📊 Componentes del Score")

comp = result["components"]
c1, c2, c3, c4 = st.columns(4)

def score_color(s):
    if s >= 65: return "#52b788"
    elif s >= 50: return "#ffd166"
    else: return "#ef476f"

with c1:
    ts = comp["technical"]["score"]
    st.markdown(f"**📈 Técnico** ({WEIGHTS.technical*100:.0f}%)")
    st.markdown(f"<h2 style='color:{score_color(ts)}'>{ts}</h2>", unsafe_allow_html=True)
    st.caption(f"Dirección: {comp['technical']['direction']}")

with c2:
    cs = comp["correlation"]["score"]
    st.markdown(f"**🔗 Correlación** ({WEIGHTS.correlation*100:.0f}%)")
    st.markdown(f"<h2 style='color:{score_color(cs)}'>{cs}</h2>", unsafe_allow_html=True)
    st.caption(f"Dirección: {comp['correlation']['direction']}")

with c3:
    rs = comp["risk"]["score"]
    st.markdown(f"**🛡️ Riesgo** ({WEIGHTS.risk*100:.0f}%)")
    st.markdown(f"<h2 style='color:{score_color(rs)}'>{rs}</h2>", unsafe_allow_html=True)

with c4:
    ds = comp["dom"]["score"]
    st.markdown(f"**👁️ DOM** ({WEIGHTS.dom*100:.0f}%)")
    st.markdown(f"<h2 style='color:{score_color(ds)}'>{ds}</h2>", unsafe_allow_html=True)
    st.caption(f"Dirección: {comp['dom']['direction']}")

# ══════════════════════════════════════════════════════════
# SCORES POR TIMEFRAME
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### ⏱️ Score por Timeframe")

tech_details = comp["technical"].get("details", {})
tf_scores = tech_details.get("tf_scores", {})

if tf_scores:
    tf_data = []
    for tf_name, tf_result in tf_scores.items():
        sc = tf_result.get("score", 50)
        dr = tf_result.get("direction", "NEUTRAL")
        emoji = "🟢" if sc >= 65 else ("🟡" if sc >= 50 else "🔴")
        tf_data.append({"Timeframe": tf_name, "Score": sc, "Dirección": dr, "Señal": emoji})
    
    tf_df = pd.DataFrame(tf_data)
    st.dataframe(tf_df, use_container_width=True, hide_index=True)

# RSI Divergences between timeframes
rsi_divs = tech_details.get("rsi_divergences", [])
if rsi_divs:
    st.markdown("#### 📊 Divergencias RSI entre Timeframes")
    for rd in rsi_divs:
        mag = rd["mag_score"]
        if mag >= 3:
            st.error(rd["description"])
        elif mag >= 2:
            st.warning(rd["description"])
        else:
            st.info(rd["description"])
else:
    st.caption("✅ Sin divergencias RSI significativas entre timeframes")

# ══════════════════════════════════════════════════════════
# MATRIZ DE CORRELACIONES
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🔗 Correlaciones Cross-Asset")

corr_details = comp["correlation"].get("details", {})
corr_data = corr_details.get("correlations", {})

if corr_data:
    from sentinel.config import EXPECTED_CORRELATIONS
    corr_table = []
    for key, actual in corr_data.items():
        expected = EXPECTED_CORRELATIONS.get(key, 0)
        diff = actual - expected
        status = "✅" if abs(diff) < 0.2 else ("⚠️" if abs(diff) < 0.4 else "🔴")
        corr_table.append({
            "Instrumento": key.upper(),
            "Correlación Actual": round(actual, 3),
            "Esperada": expected,
            "Diferencia": round(diff, 3),
            "Estado": status,
        })
    st.dataframe(pd.DataFrame(corr_table), use_container_width=True, hide_index=True)

# Divergencias
divs = result.get("divergences", [])
if divs:
    st.markdown("### 🔍 Divergencias Detectadas")
    for d in divs[:5]:
        st.warning(d["description"])

# ══════════════════════════════════════════════════════════
# CALCULADORA DE POSICIÓN
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🧮 Calculadora de Posición")

target_data = feed.get_data(SYMBOLS["target"], 60, 200)
if not target_data.empty:
    target_ind = calculate_all(target_data)
    if 'atr' in target_ind.columns:
        current_atr = target_ind['atr'].iloc[-1]
        current_price = target_data['close'].iloc[-1]
        
        pos = calculate_position_size(RISK.capital_clp, current_atr, current_price)
        
        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("ATR(14)", f"{pos['atr']:.4f}")
        pc2.metric("Stop Loss", f"{pos['sl_distance']:.4f}", f"ATR × {pos['sl_multiplier']}")
        pc3.metric("Take Profit", f"{pos['tp_distance']:.4f}", f"ATR × {pos['tp_multiplier']}")
        pc4.metric("R:R Ratio", f"1:{pos['rr_ratio']}")
        
        pc5, pc6, pc7, _ = st.columns(4)
        pc5.metric("Riesgo CLP", f"${pos['risk_amount_clp']:,.0f}")
        pc6.metric("Lots", f"{pos['lots']}")
        pc7.metric("Riesgo %", f"{pos['risk_pct']}%")

# ══════════════════════════════════════════════════════════
# ESTADO DEL DÍA
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 📋 Estado del Día")

meta = result["meta"]
limits = check_daily_limits(meta["daily_pnl"], meta["trades_today"], meta["consecutive_losses"])

mc1, mc2, mc3, mc4 = st.columns(4)
mc1.metric("Trades Hoy", f"{limits['trades_used']}/{limits['max_trades']}")
mc2.metric("P&L Diario", f"${meta['daily_pnl']:,.0f} CLP")
mc3.metric("Pérdida Usada", f"{limits['loss_pct_used']}%")
mc4.metric("Pérdidas Seguidas", f"{limits['consecutive_losses']}/{limits['max_consecutive']}")

if not limits["can_trade"]:
    st.error("🚫 NO SE PUEDE OPERAR — Límites diarios alcanzados")
else:
    st.success("✅ Dentro de límites de riesgo")

# ══════════════════════════════════════════════════════════
# GRÁFICO DE PRECIOS
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"### 📈 USDCLP — Últimas 200 velas (H1)")

if not target_data.empty:
    fig = go.Figure(data=[go.Candlestick(
        x=target_data.index,
        open=target_data['open'], high=target_data['high'],
        low=target_data['low'], close=target_data['close'],
        increasing_line_color='#52b788', decreasing_line_color='#ef476f'
    )])
    fig.update_layout(
        template="plotly_dark",
        height=500,
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117',
    )
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════
# CHECKLIST PRE-TRADE
# ══════════════════════════════════════════════════════════
with st.expander("✅ Checklist Pre-Trade (expandir antes de operar)"):
    st.checkbox("¿Hay noticias high-impact en las próximas 2h?", key="ck1")
    st.checkbox("¿Estamos en horario de liquidez? (09:30-14:00 CLT)", key="ck2")
    st.checkbox("¿El trade arriesga ≤ 1-2% del capital?", key="ck3")
    st.checkbox("¿El SL está definido por estructura?", key="ck4")
    st.checkbox("¿El R:R es ≥ 1.5:1?", key="ck5")
    st.checkbox("¿Score SENTINEL ≥ 65?", key="ck6")
    st.checkbox("¿Hay confluencia de AL MENOS 3 factores?", key="ck7")
    st.checkbox("¿Estoy operando por SEÑAL, no por emoción?", key="ck8")

# ══════════════════════════════════════════════════════════
# AUTO-REFRESH
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.caption(f"Última actualización: {datetime.now().strftime('%H:%M:%S')} | Modo: {feed.get_status()['mode'].upper()}")

if auto_refresh:
    time.sleep(DASHBOARD_REFRESH_SECONDS)
    st.rerun()
