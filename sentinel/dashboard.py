"""
SENTINEL v3.2 — Dashboard Streamlit
Layout: [Score+Dir+Price | Niveles | Timeframes | Correlaciones] en 1 fila
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time

from sentinel.config import (SYMBOLS, WEIGHTS, SCORE_ALERT_THRESHOLD,
    SCORE_STRONG_THRESHOLD, DASHBOARD_REFRESH_SECONDS, EXPECTED_CORRELATIONS)
from sentinel.data_feed import DataFeed
from sentinel.sentinel_core import SentinelCore

st.set_page_config(page_title="SENTINEL v3.2 — USD/CLP", page_icon="🛡️",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .score-box { font-size: 44px; font-weight: bold; text-align: center;
        padding: 6px 14px; border-radius: 10px; line-height: 1.2; }
    .score-green { background: linear-gradient(135deg, #1a472a, #2d6a4f); color: #52b788; border: 2px solid #52b788; }
    .score-yellow { background: linear-gradient(135deg, #5c4b1f, #8a6d3b); color: #ffd166; border: 2px solid #ffd166; }
    .score-red { background: linear-gradient(135deg, #4a1a1a, #8b2c2c); color: #ef476f; border: 2px solid #ef476f; }
    .tt-wrap { position: relative; cursor: help; }
    .tt-wrap .tt-pop {
        visibility: hidden; opacity: 0; position: absolute; z-index: 9999;
        bottom: 105%; left: 50%; transform: translateX(-50%); width: 380px;
        padding: 12px 14px; background: #1e2130; color: #c8ccd4;
        border: 1px solid #3a3f55; border-radius: 10px; font-size: 13px;
        line-height: 1.45; font-family: -apple-system, sans-serif;
        font-style: normal; font-weight: 400;
        max-height: 500px; overflow-y: auto;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        transition: opacity 0.2s; pointer-events: none;
    }
    .tt-wrap .tt-pop::after {
        content: ''; position: absolute; top: 100%; left: 50%;
        transform: translateX(-50%); border: 7px solid transparent;
        border-top-color: #3a3f55;
    }
    .tt-wrap:hover .tt-pop { visibility: visible; opacity: 1; pointer-events: auto; }
    .tt-pop b { color: #fff; }
    .tt-pop .tt-title { font-size: 14px; font-weight: 700; color: #fff;
        margin-bottom: 5px; padding-bottom: 4px; border-bottom: 1px solid #333850; }
    .tt-down .tt-pop { bottom: auto; top: 105%; }
    .tt-down .tt-pop::after { top: auto; bottom: 100%;
        border-color: transparent transparent #3a3f55 transparent; }
    section.main div[data-testid="stHorizontalBlock"]:first-of-type {
        align-items: stretch !important;
    }
    section.main div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="stColumn"] > div {
        height: 100%; display: flex; flex-direction: column; justify-content: flex-start;
    }
</style>
""", unsafe_allow_html=True)

def tt(content, title, body, direction="up"):
    cls = "tt-wrap" if direction == "up" else "tt-wrap tt-down"
    return (f'<div class="{cls}">{content}'
            f'<div class="tt-pop"><div class="tt-title">{title}</div>{body}</div></div>')

# ══════════════════════════════════════════════════════════
# INIT
# ══════════════════════════════════════════════════════════
@st.cache_resource
def init_system():
    feed = DataFeed(mode="auto")
    return feed, SentinelCore(feed)

feed, core = init_system()

with st.sidebar:
    st.title("🛡️ SENTINEL v3.2")
    st.caption("USD/CLP Trading System")
    st.divider()
    status = feed.get_status()
    if status['mt5_connected']:
        st.success("📡 MT5 REAL-TIME")
        st.caption(f"Login: {status.get('login', '?')}")
        st.caption(f"Server: {status.get('server', '?')}")
    else:
        st.warning("📡 Yahoo Finance (delay ~15 min)")
    st.caption(f"Cache: {status['cache_size']} items")
    auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)
    st.caption(f"Refresh: {DASHBOARD_REFRESH_SECONDS}s")

# ══════════════════════════════════════════════════════════
# CÁLCULO
# ══════════════════════════════════════════════════════════
result = core.calculate_composite()
score = result["composite_score"]
direction = result["direction"]
price_info = feed.get_current_price(SYMBOLS["target"])
levels = result.get("levels", {})
combined = levels.get("combined", {})
curr_price = levels.get("current_price", 0)
comp = result["components"]
tech_details = comp["technical"].get("details", {})
dir_emoji = {"LONG": "📈", "SHORT": "📉", "NEUTRAL": "➡️"}
dir_color = {"LONG": "#52b788", "SHORT": "#ef476f", "NEUTRAL": "#ffd166"}
CN = {"dxy":"DXY","copper":"Cu","wti":"WTI","usdmxn":"MXN",
      "usdbrl":"BRL","audusd":"AUD","usdcnh":"CNH","sp500":"S&P"}
css = "score-green" if score >= SCORE_STRONG_THRESHOLD else ("score-yellow" if score >= SCORE_ALERT_THRESHOLD else "score-red")
tech_sc = comp["technical"]["score"]
corr_sc = comp["correlation"]["score"]
tech_dir = comp["technical"]["direction"]
corr_dir = comp["correlation"]["direction"]

# ══════════════════════════════════════════════════════════
# HEADER — 4 columnas en 1 fila
# ══════════════════════════════════════════════════════════
col_score, col_levels, col_tf, col_corr = st.columns([0.55, 0.85, 1.6, 1.0])

with col_score:
    # Signal panel (compact, same width as score)
    _tf_sc = tech_details.get("tf_scores", {})
    _sc_map = {t: _tf_sc.get(t, {}).get("score", 50) for t in ("M1","M2","M5")}
    _dir_map = {t: _tf_sc.get(t, {}).get("direction", "NEUTRAL") for t in ("M1","M2","M5")}
    _sig_defs = [("⚡","5s",{"M1":1.0}),("🔄","30s",{"M1":0.6,"M2":0.4}),("📊","1m",{"M1":0.4,"M2":0.3,"M5":0.3})]
    _cells = ""
    _ttp = []
    for _ic, _sp, _wt in _sig_defs:
        _bl = sum(_sc_map.get(t,50)*w for t,w in _wt.items())
        _vl = sum(w for t,w in _wt.items() if _dir_map.get(t)=="LONG")
        _vs = sum(w for t,w in _wt.items() if _dir_map.get(t)=="SHORT")
        _sd = "LONG" if _vl>_vs and _vl>0.3 else ("SHORT" if _vs>_vl and _vs>0.3 else "NEUTRAL")
        _cv = min(100, abs(_bl-50)*2)
        if _sd=="LONG":    _r,_g,_b=82,183,136; _ar="▲"; _ac="COMPRAR"; _ep=price_info.get("ask",0)
        elif _sd=="SHORT": _r,_g,_b=239,71,111; _ar="▼"; _ac="VENDER"; _ep=price_info.get("bid",0)
        else:              _r,_g,_b=255,209,102; _ar="◆"; _ac="ESPERAR"; _ep=0
        _op = 0.10+(_cv/100)*0.45
        _tc = f"rgb({_r},{_g},{_b})"; _bg = f"rgba({_r},{_g},{_b},{_op:.2f})"
        _ept = f"<div style='font-size:9px;color:#666;'>{_ep:.1f}</div>" if _ep>0 else ""
        _cells += (f"<td style='background:{_bg};padding:4px 6px;text-align:center;"
                   f"border-right:1px solid #333;width:33%;'>"
                   f"<div style='font-size:9px;color:#888;'>{_ic} {_sp}</div>"
                   f"<div style='font-size:18px;color:{_tc};font-weight:900;line-height:1;'>{_ar}</div>"
                   f"<div style='font-size:10px;color:{_tc};font-weight:bold;'>{_ac}</div>"
                   f"<div style='font-size:14px;color:#fff;font-weight:bold;'>{_cv:.0f}%</div>"
                   f"{_ept}</td>")
        _det = " + ".join(f"{t}({_sc_map.get(t,50):.0f})" for t in _wt)
        _ttp.append(f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
                    f"border-radius:5px;padding:4px 7px;margin:3px 0;'>"
                    f"<b>{_ic} {_sp}</b> — <span style='color:{_tc};'><b>{_ac} {_cv:.0f}%</b></span><br>"
                    f"<span style='color:#888;'>Blend: {_det} = {_bl:.1f}</span></div>")
    _sig_html = (f"<div style='background:#1a1d23;border-radius:8px;overflow:hidden;'>"
                 f"<table style='width:100%;border-collapse:collapse;'><tr>{_cells}</tr></table></div>")
    st.markdown(tt(_sig_html, "🎯 Panel de Señales",
        f"{''.join(_ttp)}<br>⚡=M1 | 🔄=M1+M2 | 📊=M1+M2+M5",
        "down"), unsafe_allow_html=True)
    if score >= 75:
        sr = f"🟢 <b>FUERTE ({score})</b><br>Téc({tech_sc:.0f})+Corr({corr_sc:.0f}) confluyen → {direction}."
    elif score >= 65:
        sr = f"🟡 <b>ALERTA ({score})</b><br>Téc={tech_sc:.0f}, Corr={corr_sc:.0f}. Buscar confirmación."
    else:
        sr = f"🔴 <b>ESPERAR ({score})</b><br>Téc={tech_sc:.0f}, Corr={corr_sc:.0f}. Sin consenso."
    st.markdown(tt(f'<div class="score-box {css}">{score}</div>', "📊 Score Compuesto",
        f"{sr}<br><br><b>Fórmula:</b> {tech_sc:.0f}×0.4 + {corr_sc:.0f}×0.6 = <b>{score}</b>",
        "down"), unsafe_allow_html=True)

    d = direction
    if tech_dir == corr_dir and tech_dir != "NEUTRAL":
        dr = f"✅ Consenso → {tech_dir}."
    elif tech_dir != corr_dir and "NEUTRAL" not in (tech_dir, corr_dir):
        dr = f"⚠️ Téc={tech_dir} vs Corr={corr_dir}."
    elif corr_dir != "NEUTRAL":
        dr = f"Corr → {corr_dir}. Téc neutral."
    elif tech_dir != "NEUTRAL":
        dr = f"Téc → {tech_dir}. Sin respaldo Corr."
    else:
        dr = "Ambos neutrales — fuera."
    st.markdown(tt(
        f"<div style='text-align:center;padding:4px 0;'>"
        f"<span style='font-size:22px;'>{dir_emoji[d]}</span> "
        f"<span style='color:{dir_color[d]};font-size:18px;font-weight:bold;'>{d}</span>"
        f" <span style='font-size:11px;color:#888;'>{result['signal']}</span></div>",
        "🧭 Dirección", f"{dr}<br><br>Téc: <b>{tech_dir}</b> (x2) | Corr: <b>{corr_dir}</b> (x3)",
        "down"), unsafe_allow_html=True)

    if price_info["bid"] > 0:
        st.markdown(tt(
            f"<div style='background:#1a1d23;padding:6px 10px;border-radius:6px;text-align:center;'>"
            f"<span style='color:#888;font-size:11px;'>USDCLP</span> "
            f"<span style='font-size:22px;font-weight:bold;color:#fff;'>{price_info['bid']:.2f}</span>"
            f" <span style='color:#52b788;font-size:11px;'>±{price_info['spread']:.2f}</span></div>",
            "💲 Precio", f"Bid: {price_info['bid']:.2f} | Ask: {price_info['ask']:.2f} | Spread: {price_info['spread']:.2f}<br>"
            f"Fuente: <b>{'MT5' if price_info.get('source')=='mt5' else 'Yahoo'}</b>",
            "down"), unsafe_allow_html=True)

# ── COL 2: Niveles ──
def _level_tooltip(lb, lv, curr_price, is_resistance):
    pct = lv['pct']
    dist = abs(pct)
    price = lv['price']
    if is_resistance:
        if dist < 0.10:
            rec = f"⚠️ <b>Resistencia inminente</b> a solo {dist:.2f}%.<br>Cuidado con LONGs — posible rechazo en {price:.2f}."
        elif dist < 0.30:
            rec = f"Resistencia cercana ({dist:.2f}%). Si el precio llega a <b>{price:.2f}</b>, buscar señal de rechazo para SHORT."
        else:
            rec = f"Resistencia lejana ({dist:.2f}%). Espacio al alza hasta <b>{price:.2f}</b>.<br>LONG viable si hay momentum."
        if lb == 'R3':
            rec += "<br><br>🔺 <b>R3 = resistencia extrema.</b> Romper R3 con volumen → breakout alcista fuerte."
    else:
        if dist < 0.10:
            rec = f"⚠️ <b>Soporte inminente</b> a solo {dist:.2f}%.<br>Posible rebote en {price:.2f} — buscar LONG."
        elif dist < 0.30:
            rec = f"Soporte cercano ({dist:.2f}%). Si llega a <b>{price:.2f}</b>, buscar rebote para LONG."
        else:
            rec = f"Soporte lejano ({dist:.2f}%). Si rompe niveles previos, target bajista en <b>{price:.2f}</b>."
        if lb == 'S3':
            rec += "<br><br>🔻 <b>S3 = soporte extremo.</b> Romper S3 → presión bajista severa."
    return rec

with col_levels:
    if combined and curr_price > 0:
        above = combined.get("above", [])
        below = combined.get("below", [])

        for i, lv in enumerate(reversed(above)):
            lb = f"R{len(above) - i}"
            rh = (f"<div style='display:flex;justify-content:space-between;align-items:center;padding:2px 4px;"
                  f"font-family:monospace;font-size:16px;background:rgba(239,71,111,0.08);"
                  f"border-left:2px solid #ef476f;border-radius:3px;margin:0;line-height:1.3;'>"
                  f"<span style='color:#ef476f;'>{lb}</span>"
                  f"<span style='font-weight:bold;font-size:18px;'>{lv['price']:.2f}</span>"
                  f"<span style='color:#ef476f;font-size:13px;'>{lv['pct']:+.1f}%</span></div>")
            tip = _level_tooltip(lb, lv, curr_price, True)
            st.markdown(tt(rh, f"🔴 {lb} — Resistencia ({lv['price']:.2f})", tip, "down"), unsafe_allow_html=True)

        st.markdown(f"<div style='text-align:center;padding:2px;font-size:18px;font-weight:bold;"
                    f"background:rgba(76,201,240,0.12);border:1px solid #4cc9f0;border-radius:3px;"
                    f"margin:1px 0;color:#4cc9f0;line-height:1.3;'>▸ {curr_price:.2f}</div>",
                    unsafe_allow_html=True)
        for i, lv in enumerate(below):
            lb = f"S{i+1}"
            rh = (f"<div style='display:flex;justify-content:space-between;align-items:center;padding:2px 4px;"
                  f"font-family:monospace;font-size:16px;background:rgba(82,183,136,0.08);"
                  f"border-left:2px solid #52b788;border-radius:3px;margin:0;line-height:1.3;'>"
                  f"<span style='color:#52b788;'>{lb}</span>"
                  f"<span style='font-weight:bold;font-size:18px;'>{lv['price']:.2f}</span>"
                  f"<span style='color:#52b788;font-size:13px;'>{lv['pct']:+.1f}%</span></div>")
            tip = _level_tooltip(lb, lv, curr_price, False)
            st.markdown(tt(rh, f"🟢 {lb} — Soporte ({lv['price']:.2f})", tip, "down"), unsafe_allow_html=True)
    else:
        st.caption("Sin datos")

# ── COL 3: Timeframes ──
with col_tf:
    tf_scores = tech_details.get("tf_scores", {})
    if tf_scores:
        tf_order = ["M1", "M2", "M5", "M15"]
        active_tfs = [t for t in tf_order if t in tf_scores]
        tf_cols = st.columns(len(active_tfs))
        tf_w = {"M1": "40%", "M2": "30%", "M5": "20%", "M15": "10%"}
        tf_roles = {"M1": "Ejecución", "M2": "Confirmación", "M5": "Tendencia", "M15": "Contexto"}
        for col_idx, tf in enumerate(active_tfs):
            r = tf_scores[tf]
            sc = r.get("score", 50); dr3 = r.get("direction", "NEUTRAL")
            sigs = r.get("signals", {})
            dets = r.get("details", {})
            rsi = sigs.get("rsi", 0)
            clr = "#52b788" if sc >= 65 else ("#ffd166" if sc >= 50 else "#ef476f")
            em = "🟢" if sc >= 65 else ("🟡" if sc >= 50 else "🔴")
            rc = "#ef476f" if rsi >= 70 else ("#52b788" if rsi <= 30 else "#aaa")
            rt = "OB" if rsi >= 70 else ("OS" if rsi <= 30 else "")
            rp = []
            if sc >= 65 and dr3 == "LONG":
                action = "📈 LONG"
                rp.append(f"✅ <b>Señal LONG</b> ({sc}/100). Indicadores al alza.")
            elif sc >= 65 and dr3 == "SHORT":
                action = "📉 SHORT"
                rp.append(f"✅ <b>Señal SHORT</b> ({sc}/100). Indicadores a la baja.")
            elif sc >= 50:
                action = "🟡 ESPERAR"
                rp.append(f"🟡 <b>Débil</b> ({sc}/100). Esperar confirmación.")
            else:
                action = "🔴 FUERA"
                rp.append(f"🔴 <b>Sin señal</b> ({sc}/100). No operar.")
            if rsi >= 70:
                rp.append(f"<br>⚠️ RSI <b>{rsi:.0f}</b> SOBRECOMPRA.")
            elif rsi <= 30:
                rp.append(f"<br>⚠️ RSI <b>{rsi:.0f}</b> SOBREVENTA — posible rebote.")
            elif rsi > 55: rp.append(f"<br>RSI <b>{rsi:.0f}</b> — alcista.")
            elif rsi < 45: rp.append(f"<br>RSI <b>{rsi:.0f}</b> — bajista.")
            else: rp.append(f"<br>RSI <b>{rsi:.0f}</b> — neutral.")
            # M15 context (kept for reference)
            m15d = tf_scores.get("M15",{}).get("direction","NEUTRAL")
            if tf != "M15":
                if dr3 != m15d and m15d != "NEUTRAL" and dr3 != "NEUTRAL":
                    rp.append(f"<br>⚠️ M15 apunta {m15d}.")
                elif dr3 == m15d and dr3 != "NEUTRAL":
                    rp.append(f"<br>✅ M15 confirma {m15d}.")
            # Cross-asset context from reliable correlations
            corr_details = comp.get("correlation", {}).get("details", {}).get("correlations", {})
            corr_dir = comp.get("correlation", {}).get("direction", "NEUTRAL")
            if corr_details:
                ok_assets = []
                for ck, cv in corr_details.items():
                    if cv is None or (isinstance(cv, float) and np.isnan(cv)): continue
                    exp = EXPECTED_CORRELATIONS.get(ck, 0)
                    if abs(cv - exp) < 0.2:
                        ok_assets.append(CN.get(ck, ck))
                if ok_assets:
                    ca_clr = "#52b788" if corr_dir == dr3 else ("#ef476f" if corr_dir != "NEUTRAL" and dr3 != "NEUTRAL" else "#888")
                    if corr_dir == dr3 and dr3 != "NEUTRAL":
                        ca_txt = f"✅ <b>Assets confirman {corr_dir}</b> — {', '.join(ok_assets)} alineados."
                    elif corr_dir != "NEUTRAL" and dr3 != "NEUTRAL" and corr_dir != dr3:
                        ca_txt = f"⚠️ <b>Assets dicen {corr_dir}</b> pero {tf} dice {dr3}. Cuidado."
                    else:
                        ca_txt = f"Assets confiables: {', '.join(ok_assets)}. Consenso: {corr_dir}."
                    rp.append(f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
                              f"border-radius:5px;padding:4px 7px;margin:4px 0;'>"
                              f"<b>🔗 Contexto Cross-Asset</b><br>"
                              f"<span style='color:{ca_clr};'>{ca_txt}</span></div>")
            # Section 2: Live indicators with dynamic interpretation
            rp.append(f"<br><div style='border-top:1px solid #444;padding-top:4px;margin-top:4px;'>"
                      f"<b>📋 Indicadores {tf}:</b></div>")

            # ── EMA ──
            ema_d = dets.get("ema", {}); ema_sc = ema_d.get("score", 50); ema_v = ema_d.get("vote", 0)
            price = sigs.get("price", 0)
            e9 = sigs.get("ema_9", 0); e21 = sigs.get("ema_21", 0); e50 = sigs.get("ema_50", 0)
            ema_cross = sigs.get("ema_cross", 0)
            if e9 > e21 > e50 > 0:
                ema_txt = "📈 <b>Tendencia LONG establecida</b> — EMAs alineadas al alza (9&gt;21&gt;50). Precio sostenido."
            elif e9 < e21 < e50 and e50 > 0:
                ema_txt = "📉 <b>Tendencia SHORT establecida</b> — EMAs alineadas a la baja (9&lt;21&lt;50)."
            elif e9 > e21 and e21 < e50 and e50 > 0:
                ema_txt = "🔄 <b>Posible giro alcista incipiente</b> — EMA 9 cruzó sobre 21, pero 21 aún bajo 50. Confirmación pendiente."
            elif e9 < e21 and e21 > e50 and e50 > 0:
                ema_txt = "🔄 <b>Posible giro bajista incipiente</b> — EMA 9 cruzó bajo 21, pero 21 aún sobre 50. Precaución."
            elif price > 0 and e50 > 0 and price > e50:
                ema_txt = "🟢 Precio sobre EMA 50 — sesgo alcista de fondo, pero sin alineación completa."
            elif price > 0 and e50 > 0 and price < e50:
                ema_txt = "🔴 Precio bajo EMA 50 — sesgo bajista de fondo."
            else:
                ema_txt = "⚪ EMAs entrelazadas — sin tendencia clara. Mercado lateral."
            if ema_cross == 1:
                ema_txt += "<br>⚡ <b>¡Cruce alcista reciente!</b> EMA 9 cruzó sobre 21 → señal de compra."
            elif ema_cross == -1:
                ema_txt += "<br>⚡ <b>¡Cruce bajista reciente!</b> EMA 9 cruzó bajo 21 → señal de venta."
            rp.append(f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;border-radius:6px;padding:6px 8px;margin:4px 0;'>"
                      f"<b>EMA</b> (30%) — {ema_sc:.0f}pts<br>{ema_txt}"
                      f"<br><span style='color:#555;'>9={e9:.1f} | 21={e21:.1f} | 50={e50:.1f}</span></div>")

            # ── RSI ──
            rsi_d = dets.get("rsi", {}); rsi_sc2 = rsi_d.get("score", 50)
            if rsi >= 80:
                rsi_txt = "🔴 <b>Sobrecompra extrema</b> — agotamiento casi seguro. Corrección inminente. NO entrar LONG."
            elif rsi >= 70:
                rsi_txt = "🟠 <b>Sobrecompra</b> — la subida pierde fuerza. Longs riesgosos. Buscar señal SHORT si retrocede."
            elif rsi >= 60:
                rsi_txt = "🟢 Momentum alcista saludable — tendencia al alza activa. LONG viable."
            elif rsi >= 55:
                rsi_txt = "🟢 Ligeramente alcista — incipiente presión compradora. Observar si se sostiene >60."
            elif rsi >= 45:
                rsi_txt = "⚪ Zona neutral — sin presión dominante. Esperar definición."
            elif rsi >= 40:
                rsi_txt = "🔴 Ligeramente bajista — incipiente presión vendedora. Observar si cae <40."
            elif rsi >= 30:
                rsi_txt = "🔴 Momentum bajista — tendencia a la baja activa. SHORT viable."
            elif rsi >= 20:
                rsi_txt = "🟠 <b>Sobreventa</b> — la caída pierde fuerza. Shorts riesgosos. Buscar rebote LONG."
            else:
                rsi_txt = "🟢 <b>Sobreventa extrema</b> — rebote técnico muy probable. Buscar entrada LONG con confirmación."
            rp.append(f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;border-radius:6px;padding:6px 8px;margin:4px 0;'>"
                      f"<b>RSI</b> (20%) — {rsi_sc2:.0f}pts | RSI={rsi:.0f}<br>{rsi_txt}</div>")

            # ── MACD ──
            macd_d = dets.get("macd", {}); macd_sc = macd_d.get("score", 50); macd_v = macd_d.get("vote", 0)
            macd_h = sigs.get("macd_histogram", 0)
            if macd_h > 0.005:
                macd_txt = "📈 <b>Momentum alcista fuerte</b> — histograma positivo y creciente. Impulso comprador claro."
            elif macd_h > 0.001:
                macd_txt = "🟢 Momentum alcista moderado — histograma positivo pero débil. Tendencia al alza presente."
            elif macd_h > 0:
                macd_txt = "🔄 <b>Momentum alcista incipiente</b> — histograma apenas positivo. Posible inicio de giro al alza."
            elif macd_h > -0.001:
                macd_txt = "🔄 <b>Momentum bajista incipiente</b> — histograma apenas negativo. Posible inicio de giro a la baja."
            elif macd_h > -0.005:
                macd_txt = "🔴 Momentum bajista moderado — histograma negativo. Presión vendedora activa."
            else:
                macd_txt = "📉 <b>Momentum bajista fuerte</b> — histograma muy negativo. Impulso vendedor dominante."
            rp.append(f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;border-radius:6px;padding:6px 8px;margin:4px 0;'>"
                      f"<b>MACD</b> (25%) — {macd_sc:.0f}pts | H:{macd_h:+.4f}<br>{macd_txt}</div>")

            # ── Bollinger Bands ──
            bb_d = dets.get("bb", {}); bb_sc = bb_d.get("score", 50)
            bb_pct = sigs.get("bb_pct", 0.5)
            if bb_pct > 0.95:
                bb_txt = "🔴 <b>Tocando banda superior</b> — precio en el extremo alto de volatilidad. Probable retroceso a la media."
            elif bb_pct > 0.80:
                bb_txt = "🟠 Cerca de banda superior — presión alcista pero acercándose a zona de reversión."
            elif bb_pct > 0.60:
                bb_txt = "🟢 Mitad superior — sesgo alcista dentro del rango normal de volatilidad."
            elif bb_pct > 0.40:
                bb_txt = "⚪ Centro de las bandas — precio en equilibrio. Sin presión extrema."
            elif bb_pct > 0.20:
                bb_txt = "🔴 Mitad inferior — sesgo bajista dentro del rango de volatilidad."
            elif bb_pct > 0.05:
                bb_txt = "🟠 Cerca de banda inferior — presión bajista pero acercándose a zona de rebote."
            else:
                bb_txt = "🟢 <b>Tocando banda inferior</b> — precio en el extremo bajo. Probable rebote al alza."
            rp.append(f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;border-radius:6px;padding:6px 8px;margin:4px 0;'>"
                      f"<b>BB</b> (15%) — {bb_sc:.0f}pts | Pos: {bb_pct:.0%}<br>{bb_txt}</div>")

            # ── Price Action ──
            pa_d = dets.get("pa", {}); pa_sc = pa_d.get("score", 50); pa_det = pa_d.get("detail", "")
            if pa_sc >= 70:
                pa_txt = f"📈 <b>Vela alcista fuerte</b> — cuerpo grande, compradores dominan. Confirma momentum LONG."
            elif pa_sc >= 55:
                pa_txt = f"🟢 Vela alcista moderada — cuerpo pequeño al alza. Compra tímida, sin convicción total."
            elif pa_sc >= 45:
                pa_txt = f"⚪ Vela indecisa (doji/mecha) — mercado sin definición. Esperar próxima vela."
            elif pa_sc >= 30:
                pa_txt = f"🔴 Vela bajista moderada — cuerpo pequeño a la baja. Venta tímida."
            else:
                pa_txt = f"📉 <b>Vela bajista fuerte</b> — cuerpo grande, vendedores dominan. Confirma momentum SHORT."
            rp.append(f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;border-radius:6px;padding:6px 8px;margin:4px 0;'>"
                      f"<b>PA</b> (10%) — {pa_sc:.0f}pts<br>{pa_txt}</div>")
            card = (f"<div style='text-align:center;background:#1a1d23;padding:6px 3px;border-radius:8px;'>"
                    f"<div style='font-size:10px;color:#888;'>{tf} ({tf_w.get(tf,'')})</div>"
                    f"<div style='font-size:22px;color:{clr};font-weight:bold;'>{em} {sc}</div>"
                    f"<div style='font-size:11px;color:{clr};font-weight:bold;'>{action}</div>"
                    f"<div style='font-size:11px;color:{rc};margin-top:2px;border-top:1px solid #333;padding-top:2px;'>"
                    f"RSI: <b>{rsi:.0f}</b> {rt}</div></div>")
            with tf_cols[col_idx]:
                st.markdown(tt(card, f"{tf_roles[tf]} — {tf} ({tf_w.get(tf,'')})", "".join(rp), "down"), unsafe_allow_html=True)

# ── COL 4: Correlaciones (compact HTML) ──
with col_corr:
    corr_data = comp["correlation"].get("details", {}).get("correlations", {})
    if corr_data:
        # Full names and interpretation logic
        CORR_FULL = {
            "dxy": ("DXY (Dólar global)", +0.75, "directa", "DXY sube → USDCLP sube"),
            "copper": ("Cobre", -0.70, "inversa", "Cobre sube → CLP fuerte → USDCLP baja"),
            "wti": ("WTI (Petróleo)", +0.40, "directa", "WTI sube → Chile importa caro → USDCLP sube"),
            "usdmxn": ("USD/MXN", +0.60, "directa", "Risk-off LATAM → ambas monedas caen juntas"),
            "usdbrl": ("USD/BRL", +0.55, "directa", "Risk-off LATAM → BRL y CLP caen juntas"),
            "audusd": ("AUD/USD", -0.50, "inversa", "AUD proxy commodities → sube con Cobre"),
            "usdcnh": ("USD/CNH", +0.45, "directa", "Yuan débil → menos demanda China → Cobre baja"),
            "sp500": ("S&P 500", -0.30, "inversa", "Risk-on → EM se fortalecen → USDCLP baja"),
        }
        rows = ""
        reliable = []
        ignore_list = []
        caution = []
        inst_details = []

        for k, act in corr_data.items():
            if act is None or (isinstance(act, float) and np.isnan(act)): continue
            exp = EXPECTED_CORRELATIONS.get(k, 0)
            df = act - exp
            ic = "✅" if abs(df) < 0.2 else ("⚠️" if abs(df) < 0.4 else "🔴")
            rows += (f"<tr><td style='padding:1px 3px;color:#aaa;'>{CN.get(k,k)}</td>"
                     f"<td style='padding:1px 3px;text-align:right;'>{act:.2f}</td>"
                     f"<td style='padding:1px 3px;text-align:right;color:#555;'>{exp}</td>"
                     f"<td style='padding:1px 3px;text-align:right;'>{df:+.2f}</td>"
                     f"<td style='padding:1px 2px;'>{ic}</td></tr>")

            name, ex, rel_type, why = CORR_FULL.get(k, (k, 0, "?", ""))
            abs_diff = abs(df)

            if abs_diff < 0.2:
                status = "✅ Confiable"
                reliable.append(CN.get(k, k))
                detail = f"Correlación {rel_type} funcionando normal. <b>Usar como confirmador.</b>"
            elif abs_diff < 0.4:
                status = "⚠️ Atención"
                caution.append(CN.get(k, k))
                detail = f"Desalineado (Δ={df:+.2f}). Usar con <b>precaución</b>."
            else:
                status = "🔴 Desconectado"
                ignore_list.append(CN.get(k, k))
                detail = f"<b>Quiebre</b> (Δ={df:+.2f}). <b>No usar</b> como referencia hoy."

            inst_details.append(
                f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
                f"border-radius:5px;padding:4px 7px;margin:3px 0;'>"
                f"<b>{name}</b> — {status}<br>"
                f"<span style='color:#888;'>{why}</span><br>"
                f"{detail}</div>")

        cs = comp["correlation"]["score"]
        cd = comp["correlation"]["direction"]
        cc = "#52b788" if cs >= 65 else ("#ffd166" if cs >= 50 else "#ef476f")

        # Summary recommendation
        corr_rec = ""
        if reliable:
            corr_rec += f"✅ <b>Confirmadores activos:</b> {', '.join(reliable)}<br>Estos se mueven como se espera — <b>pesar sus señales</b>.<br><br>"
        if ignore_list:
            corr_rec += f"🔴 <b>Ignorar hoy:</b> {', '.join(ignore_list)}<br>Correlación rota — <b>no usar</b> para decidir.<br><br>"
        if caution:
            corr_rec += f"⚠️ <b>Con precaución:</b> {', '.join(caution)}<br>Parcialmente desalineados.<br><br>"

        if cd == "LONG":
            corr_rec += f"📈 Consenso: <b>LONG</b> — mayoría de confirmadores apuntan al alza."
        elif cd == "SHORT":
            corr_rec += f"📉 Consenso: <b>SHORT</b> — mayoría de confirmadores apuntan a la baja."
        else:
            corr_rec += f"➡️ Sin consenso — instrumentos divididos."

        corr_rec += "<br><br>" + "".join(inst_details)

        tbl = (f"<table style='width:100%;font-size:12px;font-family:monospace;"
               f"border-collapse:collapse;line-height:1.5;'>"
               f"{rows}</table>"
               f"<div style='text-align:center;margin-top:3px;padding:2px;"
               f"border-top:1px solid #333;font-size:13px;'>"
               f"<span style='color:{cc};font-weight:bold;'>Corr: {cs}</span>"
               f" <span style='color:{cc};font-size:11px;'>{cd}</span></div>")
        st.markdown(tt(tbl, "🔗 Correlaciones Cross-Asset",
            corr_rec,
            "down"), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# ALERTAS Y DIVERGENCIAS
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### ⚠️ Alertas")

rsi_divs = tech_details.get("rsi_divergences", [])
if rsi_divs:
    for rd in rsi_divs:
        mag = rd["mag_score"]
        if mag >= 3: st.error(f"📊 {rd['description']}")
        elif mag >= 2: st.warning(f"📊 {rd['description']}")
        else: st.info(f"📊 {rd['description']}")

filtered_alerts = [a for a in result["alerts"] if not a.startswith("📊 Score")]
if filtered_alerts:
    for alert in filtered_alerts[:3]:
        st.warning(alert)

divs = result.get("divergences", [])
if divs:
    for d_item in divs[:5]:
        st.warning(d_item["description"])

if not rsi_divs and not filtered_alerts and not divs:
    st.caption("✅ Sin alertas activas")

# ══════════════════════════════════════════════════════════
# SEÑALES v2 — EXPERIMENTAL (con derivadas)
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🧪 Señales v2 (derivadas)")

# Price buffer in session_state
if "price_buffer" not in st.session_state:
    st.session_state.price_buffer = []
    st.session_state.price_timestamps = []

curr_bid = price_info.get("bid", 0)
now_ts = time.time()
if curr_bid > 0:
    st.session_state.price_buffer.append(curr_bid)
    st.session_state.price_timestamps.append(now_ts)
    # Keep last 24 ticks (~2 min at 5s refresh)
    if len(st.session_state.price_buffer) > 24:
        st.session_state.price_buffer = st.session_state.price_buffer[-24:]
        st.session_state.price_timestamps = st.session_state.price_timestamps[-24:]

buf = st.session_state.price_buffer
ts_buf = st.session_state.price_timestamps
n_ticks = len(buf)

# Calculate derivatives
velocity = 0.0      # 1st derivative: price change per second (pips/s)
acceleration = 0.0  # 2nd derivative: change in velocity
vel_short = 0.0     # velocity over last 2 ticks (~10s)
vel_medium = 0.0    # velocity over last 6 ticks (~30s)
vel_long = 0.0      # velocity over last 12 ticks (~60s)

if n_ticks >= 2:
    dt = ts_buf[-1] - ts_buf[-2]
    if dt > 0:
        vel_short = (buf[-1] - buf[-2]) / dt
if n_ticks >= 3:
    dt1 = ts_buf[-1] - ts_buf[-2]
    dt2 = ts_buf[-2] - ts_buf[-3]
    v1 = (buf[-1] - buf[-2]) / dt1 if dt1 > 0 else 0
    v2 = (buf[-2] - buf[-3]) / dt2 if dt2 > 0 else 0
    dt_avg = (dt1 + dt2) / 2
    acceleration = (v1 - v2) / dt_avg if dt_avg > 0 else 0
if n_ticks >= 6:
    dt_m = ts_buf[-1] - ts_buf[-6]
    if dt_m > 0:
        vel_medium = (buf[-1] - buf[-6]) / dt_m
if n_ticks >= 12:
    dt_l = ts_buf[-1] - ts_buf[-12]
    if dt_l > 0:
        vel_long = (buf[-1] - buf[-12]) / dt_l

# Derivative-enhanced scores for 3 speeds
_tf_sc2 = tech_details.get("tf_scores", {})
_m1_sc2 = _tf_sc2.get("M1", {}).get("score", 50)
_m2_sc2 = _tf_sc2.get("M2", {}).get("score", 50)
_m5_sc2 = _tf_sc2.get("M5", {}).get("score", 50)

# Normalize velocity to a -25 to +25 score boost
# Typical USDCLP velocity: ±0.1 per second = ±0.5 pips/5s
def vel_to_boost(v, scale=0.05):
    """Convert velocity to score boost, capped at ±25"""
    return max(-25, min(25, (v / scale) * 25))

def accel_to_boost(a, scale=0.01):
    """Convert acceleration to score boost, capped at ±10"""
    return max(-10, min(10, (a / scale) * 10))

# Build 3 v2 signals
v2_defs = [
    ("⚡", "5s", _m1_sc2, vel_short, acceleration, 0.50, 0.30),
    ("🔄", "30s", _m1_sc2 * 0.6 + _m2_sc2 * 0.4, vel_medium, acceleration, 0.30, 0.15),
    ("📊", "1m", _m1_sc2 * 0.4 + _m2_sc2 * 0.3 + _m5_sc2 * 0.3, vel_long, acceleration, 0.15, 0.05),
]
# weights: (icon, speed, base_score, velocity, accel, vel_weight, accel_weight)

v2_cells = ""
v2_ttp = []
for _ic, _sp, _base, _vel, _acc, _vw, _aw in v2_defs:
    # Blend: base score + velocity boost + acceleration boost
    v_boost = vel_to_boost(_vel)
    a_boost = accel_to_boost(_acc)
    enhanced = _base + (v_boost * _vw * 2) + (a_boost * _aw * 2)
    enhanced = max(0, min(100, enhanced))

    # Direction from enhanced score
    if enhanced >= 55:
        _sd2 = "LONG"
    elif enhanced <= 45:
        _sd2 = "SHORT"
    else:
        _sd2 = "NEUTRAL"

    _cv2 = min(100, abs(enhanced - 50) * 2)

    if _sd2 == "LONG":
        _r, _g, _b = 82, 183, 136; _ar = "▲"; _ac = "COMPRAR"
        _ep2 = price_info.get("ask", 0)
    elif _sd2 == "SHORT":
        _r, _g, _b = 239, 71, 111; _ar = "▼"; _ac = "VENDER"
        _ep2 = price_info.get("bid", 0)
    else:
        _r, _g, _b = 255, 209, 102; _ar = "◆"; _ac = "ESPERAR"
        _ep2 = 0

    _op2 = 0.10 + (_cv2 / 100) * 0.45
    _tc2 = f"rgb({_r},{_g},{_b})"; _bg2 = f"rgba({_r},{_g},{_b},{_op2:.2f})"
    _ept2 = f"<div style='font-size:9px;color:#666;'>{_ep2:.1f}</div>" if _ep2 > 0 else ""

    # Acceleration arrow indicator
    if _acc > 0.002:
        acc_icon = "⏫"  # accelerating up
    elif _acc > 0:
        acc_icon = "🔼"  # gently accelerating up
    elif _acc > -0.002:
        acc_icon = "🔽"  # gently decelerating
    else:
        acc_icon = "⏬"  # accelerating down

    v2_cells += (f"<td style='background:{_bg2};padding:4px 6px;text-align:center;"
                 f"border-right:1px solid #333;width:33%;'>"
                 f"<div style='font-size:9px;color:#888;'>{_ic} {_sp} {acc_icon}</div>"
                 f"<div style='font-size:18px;color:{_tc2};font-weight:900;line-height:1;'>{_ar}</div>"
                 f"<div style='font-size:10px;color:{_tc2};font-weight:bold;'>{_ac}</div>"
                 f"<div style='font-size:14px;color:#fff;font-weight:bold;'>{_cv2:.0f}%</div>"
                 f"{_ept2}</td>")

    # Tooltip detail
    v_dir = "↑" if _vel > 0 else ("↓" if _vel < 0 else "→")
    a_dir = "acelerando" if _acc > 0.001 else ("frenando" if _acc < -0.001 else "estable")
    v2_ttp.append(
        f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
        f"border-radius:5px;padding:4px 7px;margin:3px 0;'>"
        f"<b>{_ic} {_sp}</b> — <span style='color:{_tc2};'><b>{_ac} {_cv2:.0f}%</b></span><br>"
        f"Base: {_base:.1f} + Vel({v_boost:+.1f}×{_vw}) + Acc({a_boost:+.1f}×{_aw}) = <b>{enhanced:.1f}</b><br>"
        f"<span style='color:#888;'>Velocidad: {_vel:+.4f}/s {v_dir} | {a_dir}</span></div>")

v2_html = (f"<div style='background:#1a1d23;border-radius:8px;overflow:hidden;'>"
           f"<table style='width:100%;border-collapse:collapse;'><tr>{v2_cells}</tr></table></div>")

# Momentum summary bar (human readable, no raw numbers)
if vel_short > 0.01 and acceleration > 0.001:
    mom_txt = "📈 Subiendo y acelerando"; mom_clr = "#52b788"; mom_ic = "⏫"
elif vel_short > 0.01 and acceleration < -0.001:
    mom_txt = "📈 Subiendo pero frenando"; mom_clr = "#a8d5a2"; mom_ic = "🔼"
elif vel_short > 0:
    mom_txt = "↗️ Subiendo suave"; mom_clr = "#888"; mom_ic = "🔼"
elif vel_short < -0.01 and acceleration < -0.001:
    mom_txt = "📉 Bajando y acelerando"; mom_clr = "#ef476f"; mom_ic = "⏬"
elif vel_short < -0.01 and acceleration > 0.001:
    mom_txt = "📉 Bajando pero frenando"; mom_clr = "#f4a0b0"; mom_ic = "🔽"
elif vel_short < 0:
    mom_txt = "↘️ Bajando suave"; mom_clr = "#888"; mom_ic = "🔽"
else:
    mom_txt = "➡️ Sin movimiento"; mom_clr = "#555"; mom_ic = "⏸️"

# Momentum bar with visual fill
mom_pct = min(100, abs(vel_short) / 0.05 * 100)  # normalize to 0-100%
bar_clr = "#52b788" if vel_short > 0 else "#ef476f"
fill_dir = "right" if vel_short > 0 else "left"
deriv_info = (
    f"<div style='background:#1a1d23;border-radius:8px;padding:5px 8px;margin-top:4px;'>"
    f"<div style='display:flex;justify-content:space-between;align-items:center;font-size:11px;'>"
    f"<span style='color:{mom_clr};font-weight:bold;'>{mom_ic} {mom_txt}</span>"
    f"<span style='color:#555;font-size:9px;'>{n_ticks} ticks</span></div>"
    f"<div style='background:#111;border-radius:3px;height:4px;margin-top:3px;overflow:hidden;'>"
    f"<div style='width:{mom_pct:.0f}%;height:100%;background:{bar_clr};"
    f"border-radius:3px;float:{fill_dir};'></div></div></div>")

sig2_col, _ = st.columns([0.55, 3.45])
with sig2_col:
    st.markdown(tt(v2_html, "🧪 Señales v2 (derivadas)",
        f"{''.join(v2_ttp)}<br>"
        f"<b>Momentum:</b> {mom_txt}<br><br>"
        f"<b>Interpretación:</b><br>"
        f"⏫ Precio sube cada vez más rápido → impulso comprador fuerte<br>"
        f"🔼 Precio sube pero pierde fuerza → posible techo pronto<br>"
        f"⏬ Precio baja cada vez más rápido → impulso vendedor fuerte<br>"
        f"🔽 Precio baja pero pierde fuerza → posible piso pronto<br><br>"
        f"Buffer: {n_ticks} ticks (~{n_ticks*5}s)",
        "down"), unsafe_allow_html=True)
    st.markdown(deriv_info, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.caption(f"Última actualización: {datetime.now().strftime('%H:%M:%S')} | "
           f"Fuente: {'🟢 MT5 Real-Time' if feed.mt5_connected else '🟡 Yahoo Finance (delay)'} | "
           f"Score: Técnico {WEIGHTS.technical*100:.0f}% + Correlación {WEIGHTS.correlation*100:.0f}%")

if auto_refresh:
    time.sleep(DASHBOARD_REFRESH_SECONDS)
    st.rerun()
