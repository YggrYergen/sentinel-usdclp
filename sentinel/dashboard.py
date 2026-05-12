"""
SENTINEL v3.1 — Dashboard Streamlit
Panel compacto para USD/CLP — Score + Niveles + Correlaciones
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime
import time

from sentinel.config import (SYMBOLS, WEIGHTS, SCORE_ALERT_THRESHOLD,
    SCORE_STRONG_THRESHOLD, DASHBOARD_REFRESH_SECONDS)
from sentinel.data_feed import DataFeed
from sentinel.sentinel_core import SentinelCore

# ══════════════════════════════════════════════════════════
# CONFIGURACIÓN DE PÁGINA
# ══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SENTINEL v3.1 — USD/CLP",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .score-box {
        font-size: 48px; font-weight: bold; text-align: center;
        padding: 10px; border-radius: 12px; margin: 5px 0;
        line-height: 1.2;
    }
    .score-green { background: linear-gradient(135deg, #1a472a, #2d6a4f); color: #52b788; border: 2px solid #52b788; }
    .score-yellow { background: linear-gradient(135deg, #5c4b1f, #8a6d3b); color: #ffd166; border: 2px solid #ffd166; }
    .score-red { background: linear-gradient(135deg, #4a1a1a, #8b2c2c); color: #ef476f; border: 2px solid #ef476f; }
    .level-row { display: flex; justify-content: space-between; padding: 4px 12px;
        border-radius: 6px; margin: 2px 0; font-family: monospace; font-size: 14px; }
    .level-above { background: rgba(239, 71, 111, 0.1); border-left: 3px solid #ef476f; }
    .level-below { background: rgba(82, 183, 136, 0.1); border-left: 3px solid #52b788; }
    .level-current { background: rgba(76, 201, 240, 0.15); border: 1px solid #4cc9f0;
        padding: 6px 12px; border-radius: 6px; text-align: center; font-weight: bold;
        font-size: 16px; margin: 4px 0; }
    .hint { color: #666; font-size: 12px; font-style: italic; margin: 2px 0; padding: 4px 8px;
        background: rgba(255,255,255,0.03); border-radius: 4px; }
    div[data-testid="stMetric"] { background: #1a1d23; padding: 10px; border-radius: 8px; }
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
# SIDEBAR MÍNIMO
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.title("🛡️ SENTINEL v3.1")
    st.caption("USD/CLP Trading System")
    st.divider()
    status = feed.get_status()
    st.info(f"📡 {status['mode'].upper()} | Cache: {status['cache_size']}")
    auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)
    st.caption(f"Refresh: {DASHBOARD_REFRESH_SECONDS}s")

# ══════════════════════════════════════════════════════════
# CÁLCULO PRINCIPAL
# ══════════════════════════════════════════════════════════
result = core.calculate_composite()

# ══════════════════════════════════════════════════════════
# HEADER COMPACTO — Score + Dirección + Precio (1 fila)
# ══════════════════════════════════════════════════════════
score = result["composite_score"]
direction = result["direction"]
price_info = feed.get_current_price(SYMBOLS["target"])
levels = result.get("levels", {})
combined = levels.get("combined", {})
curr_price = levels.get("current_price", 0)

dir_emoji = {"LONG": "📈", "SHORT": "📉", "NEUTRAL": "➡️"}
dir_color = {"LONG": "#52b788", "SHORT": "#ef476f", "NEUTRAL": "#ffd166"}

if score >= SCORE_STRONG_THRESHOLD:
    css = "score-green"
elif score >= SCORE_ALERT_THRESHOLD:
    css = "score-yellow"
else:
    css = "score-red"

# Layout: [Score + Dir + Precio] | [Niveles compactos]
col_main, col_levels = st.columns([2.5, 1])

with col_main:
    mc1, mc2, mc3 = st.columns([1.2, 0.8, 1.5])
    with mc1:
        st.markdown(f'<div class="score-box {css}">{score}</div>', unsafe_allow_html=True)
        st.markdown(f"<p style='text-align:center;color:#888;font-size:11px;'>Score Compuesto</p>", unsafe_allow_html=True)
    with mc2:
        d = direction
        st.markdown(f"<div style='text-align:center;padding:8px;'>"
                    f"<span style='font-size:32px;'>{dir_emoji[d]}</span><br>"
                    f"<span style='color:{dir_color[d]};font-size:20px;font-weight:bold;'>{d}</span><br>"
                    f"<span style='font-size:13px;'>{result['signal']}</span></div>",
                    unsafe_allow_html=True)
    with mc3:
        if price_info["bid"] > 0:
            st.metric("💲 USDCLP", f"{price_info['bid']:.2f}",
                      delta=f"Spread: {price_info['spread']:.2f}")
        st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")

with col_levels:
    st.markdown("<div style='font-size:13px;font-weight:bold;color:#aaa;margin-bottom:2px;'>📍 Niveles</div>",
                unsafe_allow_html=True)
    if combined and curr_price > 0:
        above = combined.get("above", [])
        below = combined.get("below", [])
        
        # R3, R2, R1 (de lejos a cerca)
        for i, lv in enumerate(reversed(above)):
            label = f"R{len(above) - i}"
            st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center;padding:1px 4px;"
                        f"font-family:monospace;font-size:16px;background:rgba(239,71,111,0.08);"
                        f"border-left:2px solid #ef476f;border-radius:3px;margin:0;line-height:1.3;'>"
                        f"<span style='color:#ef476f;min-width:24px;'>{label}</span>"
                        f"<span style='font-weight:bold;font-size:19px;'>{lv['price']:.2f}</span>"
                        f"<span style='color:#ef476f;font-size:13px;'>+{lv['pct']:.2f}%</span></div>",
                        unsafe_allow_html=True)
        
        # Precio actual
        st.markdown(f"<div style='text-align:center;padding:2px;font-size:16px;font-weight:bold;"
                    f"background:rgba(76,201,240,0.12);border:1px solid #4cc9f0;border-radius:3px;"
                    f"margin:1px 0;color:#4cc9f0;line-height:1.3;'>▸ {curr_price:.2f}</div>",
                    unsafe_allow_html=True)
        
        # S1, S2, S3 (de cerca a lejos)
        for i, lv in enumerate(below):
            label = f"S{i + 1}"
            st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center;padding:1px 4px;"
                        f"font-family:monospace;font-size:16px;background:rgba(82,183,136,0.08);"
                        f"border-left:2px solid #52b788;border-radius:3px;margin:0;line-height:1.3;'>"
                        f"<span style='color:#52b788;min-width:24px;'>{label}</span>"
                        f"<span style='font-weight:bold;font-size:19px;'>{lv['price']:.2f}</span>"
                        f"<span style='color:#52b788;font-size:13px;'>{lv['pct']:.2f}%</span></div>",
                        unsafe_allow_html=True)
        
        # Interpretación compacta
        position = levels.get("position", "")
        if position:
            st.markdown(f"<div style='font-size:10px;color:#888;margin-top:2px;'>{position}</div>",
                        unsafe_allow_html=True)
    else:
        st.caption("Sin datos")

st.markdown('<div class="hint">ℹ️ Score = Técnico (40%) + Correlación (60%). '
            '≥75 🟢 Fuerte | ≥65 🟡 Alerta | <65 🔴 Esperar. '
            'R1-R3 resistencias, S1-S3 soportes (Camarilla + Swing).</div>', unsafe_allow_html=True)

# Alertas (si hay) — filtrar la de score redundante
filtered_alerts = [a for a in result["alerts"] if not a.startswith("📊 Score")]
if filtered_alerts:
    for alert in filtered_alerts[:3]:
        st.warning(alert)

# ══════════════════════════════════════════════════════════
# SECCIÓN 1: SCORE POR TIMEFRAME
# ══════════════════════════════════════════════════════════
st.markdown("---")
comp = result["components"]
tech_details = comp["technical"].get("details", {})

st.markdown("### ⏱️ Score por Timeframe")
st.markdown('<div class="hint">ℹ️ M15 es el ancla (50% del peso). M5 confirma ejecución (35%). '
            'M1 detecta micro-momentum (15%). Busca confluencia: 🟢 en los 3 = señal sólida.</div>',
            unsafe_allow_html=True)

tf_scores = tech_details.get("tf_scores", {})
if tf_scores:
    tf_cols = st.columns(len(tf_scores))
    tf_order = ["M1", "M5", "M15"]
    tf_weights = {"M1": "15%", "M5": "35%", "M15": "50%"}
    for i, tf_name in enumerate(tf_order):
        if tf_name in tf_scores:
            tf_r = tf_scores[tf_name]
            sc = tf_r.get("score", 50)
            dr = tf_r.get("direction", "NEUTRAL")
            rsi = tf_r.get("signals", {}).get("rsi", 0)
            color = "#52b788" if sc >= 65 else ("#ffd166" if sc >= 50 else "#ef476f")
            emoji = "🟢" if sc >= 65 else ("🟡" if sc >= 50 else "🔴")
            # RSI color
            if rsi >= 70:
                rsi_c = "#ef476f"
                rsi_tag = "OB"
            elif rsi <= 30:
                rsi_c = "#52b788"
                rsi_tag = "OS"
            else:
                rsi_c = "#aaa"
                rsi_tag = ""
            with tf_cols[i]:
                st.markdown(f"<div style='text-align:center;background:#1a1d23;padding:10px;border-radius:8px;'>"
                            f"<div style='font-size:12px;color:#888;'>{tf_name} ({tf_weights.get(tf_name,'')})</div>"
                            f"<div style='font-size:28px;color:{color};font-weight:bold;'>{emoji} {sc}</div>"
                            f"<div style='font-size:12px;color:{color};'>{dr}</div>"
                            f"<div style='font-size:13px;color:{rsi_c};margin-top:4px;border-top:1px solid #333;padding-top:4px;'>"
                            f"RSI: <b>{rsi:.0f}</b> {rsi_tag}</div></div>",
                            unsafe_allow_html=True)

# RSI Divergences — siempre mostrar estado
rsi_divs = tech_details.get("rsi_divergences", [])
if rsi_divs:
    for rd in rsi_divs:
        mag = rd["mag_score"]
        if mag >= 3:
            st.error(f"📊 {rd['description']}")
        elif mag >= 2:
            st.warning(f"📊 {rd['description']}")
        else:
            st.info(f"📊 {rd['description']}")
else:
    st.markdown("<div class='hint'>📊 RSI alineado entre timeframes — sin divergencias (Δ < 10 pts)</div>",
                unsafe_allow_html=True)




# ══════════════════════════════════════════════════════════
# SECCIÓN 3: CORRELACIONES CROSS-ASSET
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🔗 Correlaciones Cross-Asset")
st.markdown('<div class="hint">ℹ️ Correlación Real vs Esperada. Si la diferencia es grande = quiebre de correlación = '
            'posible divergencia. ✅ diff <0.2 = normal. ⚠️ <0.4 = atención. 🔴 >0.4 = quiebre. '
            'Score alto (>65) = todos los activos apuntan en la misma dirección.</div>',
            unsafe_allow_html=True)

corr_details = comp["correlation"].get("details", {})
corr_data = corr_details.get("correlations", {})

if corr_data:
    from sentinel.config import EXPECTED_CORRELATIONS
    corr_table = []
    for key, actual in corr_data.items():
        if actual is None or (isinstance(actual, float) and np.isnan(actual)):
            continue
        expected = EXPECTED_CORRELATIONS.get(key, 0)
        diff = actual - expected
        status = "✅" if abs(diff) < 0.2 else ("⚠️" if abs(diff) < 0.4 else "🔴")
        corr_table.append({
            "Instrumento": key.upper(),
            "Real": round(actual, 3),
            "Esperada": expected,
            "Δ Diff": round(diff, 3),
            "": status,
        })
    if corr_table:
        st.dataframe(pd.DataFrame(corr_table), use_container_width=True, hide_index=True)

    # Score y dirección de correlación
    cs = comp["correlation"]["score"]
    cd = comp["correlation"]["direction"]
    c_color = "#52b788" if cs >= 65 else ("#ffd166" if cs >= 50 else "#ef476f")
    st.markdown(f"<div style='text-align:center;'>"
                f"<span style='color:{c_color};font-size:18px;font-weight:bold;'>Score Correlación: {cs}</span>"
                f" | Dirección: <span style='color:{c_color};'>{cd}</span></div>",
                unsafe_allow_html=True)

# Cross-asset divergences
divs = result.get("divergences", [])
if divs:
    st.markdown("#### 🔍 Divergencias Cross-Asset")
    for d in divs[:5]:
        st.warning(d["description"])

# ══════════════════════════════════════════════════════════
# GRÁFICO DE PRECIOS
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 📈 USDCLP — M15")

target_data = feed.get_data(SYMBOLS["target"], 15, 200)
if not target_data.empty:
    fig = go.Figure(data=[go.Candlestick(
        x=target_data.index,
        open=target_data['open'], high=target_data['high'],
        low=target_data['low'], close=target_data['close'],
        increasing_line_color='#52b788', decreasing_line_color='#ef476f'
    )])
    
    # Agregar líneas de niveles al gráfico
    if combined and curr_price > 0:
        for lv in combined.get("above", []):
            fig.add_hline(y=lv["price"], line_dash="dash", line_color="#ef476f",
                         annotation_text=lv["label"], annotation_font_color="#ef476f",
                         annotation_font_size=10)
        for lv in combined.get("below", []):
            fig.add_hline(y=lv["price"], line_dash="dash", line_color="#52b788",
                         annotation_text=lv["label"], annotation_font_color="#52b788",
                         annotation_font_size=10)
        pp = combined.get("pp")
        if pp:
            fig.add_hline(y=pp, line_dash="dot", line_color="#4cc9f0",
                         annotation_text="PP", annotation_font_color="#4cc9f0")
    
    fig.update_layout(
        template="plotly_dark", height=450,
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=10, b=20),
        paper_bgcolor='#0e1117', plot_bgcolor='#0e1117',
    )
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.caption(f"Última actualización: {datetime.now().strftime('%H:%M:%S')} | "
           f"Modo: {feed.get_status()['mode'].upper()} | "
           f"Score: Técnico {WEIGHTS.technical*100:.0f}% + Correlación {WEIGHTS.correlation*100:.0f}%")

if auto_refresh:
    time.sleep(DASHBOARD_REFRESH_SECONDS)
    st.rerun()
