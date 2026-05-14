"""
SENTINEL v3.4 — Dashboard Streamlit
Layout: [Score+Dir+Price | Niveles | Timeframes | Correlaciones] en 1 fila
Includes: Signal panels, backtesting, AI chat assistant
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sentinel.dashboard")

from sentinel.config import (SYMBOLS, WEIGHTS, SCORE_ALERT_THRESHOLD,
    SCORE_STRONG_THRESHOLD, DASHBOARD_REFRESH_SECONDS, EXPECTED_CORRELATIONS)
from sentinel.data_feed import DataFeed
from sentinel.sentinel_core import SentinelCore
from sentinel.version import VERSION, CODENAME

st.set_page_config(page_title=f"SENTINEL v{VERSION} — USD/CLP", page_icon="🛡️",
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
    /* Sparkline hover popup for cross-asset arrows */
    .spark-wrap { position: relative; cursor: crosshair; }
    .spark-wrap .spark-pop {
        visibility: hidden; opacity: 0; position: absolute;
        top: 110%; left: 50%; transform: translateX(-50%);
        z-index: 1000; background: #1a1d23; border: 1px solid #3a3f55;
        border-radius: 8px; padding: 6px 8px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.6);
        transition: opacity 0.15s; pointer-events: none; white-space: nowrap;
    }
    .spark-wrap:hover .spark-pop { visibility: visible; opacity: 1; }
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
    st.title(f"🛡️ SENTINEL v{VERSION}")
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

# ── Cross-asset technical scores + M1 price data (for enhanced corr table) ──
from sentinel.technical_scorer import calculate_multi_tf_score

_cross_asset_keys = ["dxy", "copper", "wti", "usdmxn", "usdbrl", "audusd", "usdcnh", "sp500"]
_cross_tech = {}
_cross_m1 = {}

# Session state: track tick prices between refreshes for instant arrow
if '_cross_last_prices' not in st.session_state:
    st.session_state._cross_last_prices = {}

for _cak in _cross_asset_keys:
    _ca_symbol = SYMBOLS.get(_cak, "")
    if _ca_symbol:
        try:
            _ca_result = calculate_multi_tf_score(feed, _ca_symbol)
            _tfs = _ca_result.get("tf_scores", {})
            # Fast score for arrow 2: 2/3 M1 + 1/3 M2 (reactive technicals)
            _fast = _tfs.get("M1", {}).get("score", 50) * 2/3 + _tfs.get("M2", {}).get("score", 50) * 1/3
            _cross_tech[_cak] = {
                "score": _ca_result.get("composite_score", 50),
                "fast_score": _fast,
                "direction": _ca_result.get("h4_direction", "NEUTRAL"),
            }
        except Exception:
            _cross_tech[_cak] = {"score": 50, "fast_score": 50, "direction": "NEUTRAL"}
        try:
            _ca_m1_data = feed.get_data(_ca_symbol, timeframe_minutes=1, bars=10)
            if _ca_m1_data is not None and len(_ca_m1_data) >= 6:
                _cls = _ca_m1_data['close'].values
                # 2min: last close vs close 2 bars ago
                _m2_bps = (_cls[-1] - _cls[-3]) / _cls[-3] * 10000
                # 5min: last close vs close 5 bars ago
                _m5_bps = (_cls[-1] - _cls[-6]) / _cls[-6] * 10000
                _cross_m1[_cak] = {
                    "m2": _m2_bps, "m5": _m5_bps,
                    "spark": list(_cls[-6:]),  # last 5 bars for sparkline
                }
        except Exception:
            pass
        # Tick delta: current price vs last refresh price (fastest possible)
        try:
            _ca_tick = feed.get_current_price(_ca_symbol)
            _curr_bid = _ca_tick.get("bid", 0) if _ca_tick else 0
            if _curr_bid > 0:
                _prev_bid = st.session_state._cross_last_prices.get(_cak, _curr_bid)
                _tick_bps = (_curr_bid - _prev_bid) / _prev_bid * 10000
                _cross_m1.setdefault(_cak, {})["tick"] = _tick_bps
                st.session_state._cross_last_prices[_cak] = _curr_bid
        except Exception:
            pass

def _bps_to_arrow(bps, sensitivity=9, threshold=2):
    angle = max(0, min(180, 90 - bps * sensitivity))
    if bps > threshold: clr = "#52b788"
    elif bps < -threshold: clr = "#ef476f"
    else: clr = "#555"
    return angle, clr

def _slider_bar(label, weight_pct, score, msg):
    """Generate an HTML bar slider for an indicator score."""
    if score >= 65: bar_clr = "#52b788"
    elif score >= 45: bar_clr = "#ffd166"
    else: bar_clr = "#ef476f"
    pct = max(0, min(100, score))
    return (
        f"<div style='margin:3px 0;'>"
        f"<div style='display:flex;justify-content:space-between;font-size:10px;margin-bottom:1px;'>"
        f"<span style='color:#aaa;'><b>{label}</b> ({weight_pct}%)</span>"
        f"<span style='color:{bar_clr};font-weight:bold;'>{score:.0f}</span></div>"
        f"<div style='background:#2a2d35;border-radius:3px;height:6px;width:100%;overflow:hidden;'>"
        f"<div style='background:{bar_clr};height:100%;width:{pct}%;border-radius:3px;"
        f"transition:width 0.3s;'></div></div>"
        f"<div style='font-size:11px;color:#777;margin-top:1px;'>{msg}</div>"
        f"</div>"
    )

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
        f"{sr}<br><br><b>Fórmula:</b> {tech_sc:.0f}×0.75 + {corr_sc:.0f}×0.25 = <b>{score}</b>",
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
            # Section 2: Live indicators with visual sliders
            rp.append(f"<br><div style='border-top:1px solid #444;padding-top:4px;margin-top:4px;'>"
                      f"<b>📋 Indicadores {tf}:</b></div>")

            # ── EMA slider ──
            ema_d = dets.get("ema", {}); ema_sc = ema_d.get("score", 50)
            price = sigs.get("price", 0)
            e9 = sigs.get("ema_9", 0); e21 = sigs.get("ema_21", 0); e50 = sigs.get("ema_50", 0)
            ema_cross = sigs.get("ema_cross", 0)
            if e9 > e21 > e50 > 0:
                ema_msg = "Tendencia LONG establecida — EMAs alineadas al alza (9>21>50)"
            elif e9 < e21 < e50 and e50 > 0:
                ema_msg = "Tendencia SHORT establecida — EMAs alineadas a la baja (9<21<50)"
            elif e9 > e21 and e21 < e50 and e50 > 0:
                ema_msg = "Posible giro alcista — EMA 9 cruzó sobre 21, confirmación pendiente"
            elif e9 < e21 and e21 > e50 and e50 > 0:
                ema_msg = "Posible giro bajista — EMA 9 cruzó bajo 21, precaución"
            else:
                ema_msg = "EMAs entrelazadas — sin tendencia clara, mercado lateral"
            if ema_cross == 1:
                ema_msg += " — ¡Cruce alcista!"
            elif ema_cross == -1:
                ema_msg += " — ¡Cruce bajista!"
            rp.append(_slider_bar("EMA", 30, ema_sc, ema_msg))

            # ── RSI slider ──
            rsi_d = dets.get("rsi", {}); rsi_sc2 = rsi_d.get("score", 50)
            if rsi >= 70:
                rsi_msg = f"Sobrecompra ({rsi:.0f}) — agotamiento probable, NO entrar LONG"
            elif rsi >= 55:
                rsi_msg = f"Momentum alcista ({rsi:.0f}) — presión compradora activa"
            elif rsi >= 45:
                rsi_msg = f"Zona neutral ({rsi:.0f}) — sin presión dominante, esperar"
            elif rsi >= 30:
                rsi_msg = f"Momentum bajista ({rsi:.0f}) — presión vendedora activa"
            else:
                rsi_msg = f"Sobreventa ({rsi:.0f}) — rebote probable, buscar LONG"
            rp.append(_slider_bar("RSI", 20, rsi_sc2, rsi_msg))

            # ── MACD slider ──
            macd_d = dets.get("macd", {}); macd_sc = macd_d.get("score", 50)
            macd_h = sigs.get("macd_histogram", 0)
            if macd_h > 0.005:
                macd_msg = f"Impulso alcista fuerte (H:{macd_h:+.4f}) — compradores dominan"
            elif macd_h > 0.001:
                macd_msg = f"Alcista moderado (H:{macd_h:+.4f}) — tendencia al alza presente"
            elif macd_h > -0.001:
                macd_msg = f"Transición (H:{macd_h:+.4f}) — posible cambio de dirección"
            elif macd_h > -0.005:
                macd_msg = f"Bajista moderado (H:{macd_h:+.4f}) — presión vendedora activa"
            else:
                macd_msg = f"Impulso bajista fuerte (H:{macd_h:+.4f}) — vendedores dominan"
            rp.append(_slider_bar("MACD", 25, macd_sc, macd_msg))

            # ── BB slider ──
            bb_d = dets.get("bb", {}); bb_sc = bb_d.get("score", 50)
            bb_pct = sigs.get("bb_pct", 0.5)
            if bb_pct > 0.95:
                bb_msg = f"Banda superior ({bb_pct:.0%}) — extremo alto, retroceso probable"
            elif bb_pct > 0.65:
                bb_msg = f"Mitad superior ({bb_pct:.0%}) — sesgo alcista, zona de precaución"
            elif bb_pct > 0.35:
                bb_msg = f"Centro ({bb_pct:.0%}) — precio en equilibrio, sin presión extrema"
            elif bb_pct > 0.05:
                bb_msg = f"Mitad inferior ({bb_pct:.0%}) — sesgo bajista, posible rebote"
            else:
                bb_msg = f"Banda inferior ({bb_pct:.0%}) — extremo bajo, rebote probable"
            rp.append(_slider_bar("BB", 15, bb_sc, bb_msg))

            # ── PA slider ──
            pa_d = dets.get("pa", {}); pa_sc = pa_d.get("score", 50)
            if pa_sc >= 70:
                pa_msg = "Vela alcista fuerte — cuerpo grande, compradores dominan"
            elif pa_sc >= 55:
                pa_msg = "Vela alcista moderada — compra presente pero sin convicción total"
            elif pa_sc >= 45:
                pa_msg = "Vela indecisa (doji/mecha) — mercado sin definición"
            elif pa_sc >= 30:
                pa_msg = "Vela bajista moderada — venta presente pero sin fuerza"
            else:
                pa_msg = "Vela bajista fuerte — cuerpo grande, vendedores dominan"
            rp.append(_slider_bar("PA", 10, pa_sc, pa_msg))
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
        # Full names and interpretation logic (kept for tooltips)
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

        # Build tooltip details (from old code)
        reliable = []; ignore_list = []; caution = []; inst_details = []
        for k, act in corr_data.items():
            if act is None or (isinstance(act, float) and np.isnan(act)): continue
            exp = EXPECTED_CORRELATIONS.get(k, 0)
            df = act - exp
            name, ex, rel_type, why = CORR_FULL.get(k, (k, 0, "?", ""))
            abs_diff = abs(df)
            if abs_diff < 0.2:
                status = "✅ Confiable"; reliable.append(CN.get(k, k))
                detail = f"Correlación {rel_type} funcionando normal. <b>Usar como confirmador.</b>"
            elif abs_diff < 0.4:
                status = "⚠️ Atención"; caution.append(CN.get(k, k))
                detail = f"Desalineado (Δ={df:+.2f}). Usar con <b>precaución</b>."
            else:
                status = "🔴 Desconectado"; ignore_list.append(CN.get(k, k))
                detail = f"<b>Quiebre</b> (Δ={df:+.2f}). <b>No usar</b> como referencia hoy."
            inst_details.append(
                f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
                f"border-radius:5px;padding:4px 7px;margin:3px 0;'>"
                f"<b>{name}</b> — {status}<br>"
                f"<span style='color:#888;'>{why}</span><br>{detail}</div>")

        cs = comp["correlation"]["score"]
        cd = comp["correlation"]["direction"]
        cc = "#52b788" if cs >= 65 else ("#ffd166" if cs >= 50 else "#ef476f")

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

        # ── Enhanced correlation table (arrows + sparklines) ──
        # Sort by abs(correlation) descending — most active/reliable on top
        _sorted_keys = sorted(
            [k for k in _cross_asset_keys if corr_data.get(k) is not None
             and not (isinstance(corr_data.get(k), float) and np.isnan(corr_data.get(k)))],
            key=lambda k: abs(corr_data.get(k, 0)), reverse=True
        )
        _hdr_rows = ""
        for _ek in _sorted_keys:
            _e_act = corr_data[_ek]
            _e_exp = EXPECTED_CORRELATIONS.get(_ek, 0)
            _e_df = _e_act - _e_exp
            _e_ic = "✅" if abs(_e_df) < 0.2 else ("⚠️" if abs(_e_df) < 0.4 else "🔴")

            _e_fs = 12 + max(0, (0.4 - abs(_e_df)) / 0.4) * 2
            _e_fw = "700" if abs(_e_df) < 0.15 else ("500" if abs(_e_df) < 0.25 else "400")
            _rs = f"font-size:{_e_fs:.1f}px;font-weight:{_e_fw};"

            _e_tech = _cross_tech.get(_ek, {"score": 50, "fast_score": 50, "direction": "NEUTRAL"})
            _e_fsc = _e_tech["fast_score"]
            _e_tclr = "#52b788" if _e_fsc >= 60 else ("#ffd166" if _e_fsc >= 45 else "#ef476f")
            _e_angle = (100 - _e_fsc) / 100 * 180

            _pm = _cross_m1.get(_ek, {"tick": 0, "m2": 0, "m5": 0})
            _a5, _c5 = _bps_to_arrow(_pm["m5"], sensitivity=3, threshold=2)
            _a2, _c2 = _bps_to_arrow(_pm["m2"], sensitivity=6, threshold=1)
            _at, _ct = _bps_to_arrow(_pm["tick"], sensitivity=25, threshold=0.3)

            # Sparkline SVG
            _spark_svg = ""
            _spark_pts = _pm.get("spark", [])
            if len(_spark_pts) >= 3:
                _sw, _sh = 160, 44
                _smin, _smax = min(_spark_pts), max(_spark_pts)
                _srng = _smax - _smin if _smax > _smin else 0.01
                _coords = []
                for _si, _sp in enumerate(_spark_pts):
                    _sx = _si / (len(_spark_pts) - 1) * _sw
                    _sy = _sh - 2 - (_sp - _smin) / _srng * (_sh - 6)
                    _coords.append(f"{_sx:.1f},{_sy:.1f}")
                _spoly = " ".join(_coords)
                _sclr = "#52b788" if _spark_pts[-1] >= _spark_pts[0] else "#ef476f"
                _sdelta = (_spark_pts[-1] - _spark_pts[0]) / _spark_pts[0] * 100
                _spark_svg = (
                    f"<div class='spark-pop'>"
                    f"<div style='font-size:11px;color:#aaa;margin-bottom:3px;'>"
                    f"<b style='color:#fff;'>{CN.get(_ek,_ek)}</b> "
                    f"<span style='color:{_sclr};'>{_spark_pts[-1]:.2f} ({_sdelta:+.3f}%)</span></div>"
                    f"<svg width='{_sw}' height='{_sh}'>"
                    f"<polyline points='{_spoly}' fill='none' stroke='{_sclr}' stroke-width='2' "
                    f"stroke-linecap='round' stroke-linejoin='round'/>"
                    f"<circle cx='{_sw}' cy='{_coords[-1].split(',')[1]}' r='3' fill='{_sclr}'/>"
                    f"</svg>"
                    f"<div style='font-size:9px;color:#555;text-align:center;'>últimos 5 min (M1)</div>"
                    f"</div>"
                )

            _hdr_rows += (
                f"<tr>"
                f"<td style='padding:1px 3px;color:#aaa;{_rs}'>{CN.get(_ek,_ek)}</td>"
                f"<td style='padding:1px 3px;text-align:right;{_rs}'>{_e_act:.2f}</td>"
                f"<td style='padding:1px 3px;text-align:right;color:#555;{_rs}'>{_e_exp}</td>"
                f"<td style='padding:1px 3px;text-align:right;{_rs}'>{_e_df:+.2f}</td>"
                f"<td style='padding:1px 2px;{_rs}'>{_e_ic}</td>"
                f"<td style='padding:1px 2px;'>"
                f"<div class='spark-wrap'>"
                f"<div style='display:flex;align-items:center;justify-content:center;gap:3px;'>"
                f"<span style='display:inline-block;font-size:22px;color:{_ct};line-height:1;"
                f"transform:rotate({_at:.0f}deg);'>▲</span>"
                f"<span style='display:inline-block;font-size:17px;color:{_e_tclr};line-height:1;"
                f"transform:rotate({_e_angle:.0f}deg);'>▲</span>"
                f"<span style='display:inline-block;font-size:14px;color:{_c2};line-height:1;"
                f"transform:rotate({_a2:.0f}deg);'>▲</span>"
                f"<span style='display:inline-block;font-size:12px;color:{_c5};line-height:1;"
                f"transform:rotate({_a5:.0f}deg);'>▲</span></div>"
                f"{_spark_svg}</div></td>"
                f"</tr>"
            )

        tbl = (f"<table style='width:100%;font-size:12px;font-family:monospace;"
               f"border-collapse:collapse;line-height:1.5;'>"
               f"{_hdr_rows}</table>"
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
# EXPERIMENTAL
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🧪 Experimental")

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

# ── Experimental: Direction Engine A vs B + Confirmation Score ──
exp_col_deriv, exp_col_dir, exp_col_conf = st.columns([0.55, 1.0, 1.0])

# The deriv column is already rendered above in sig2_col — leave exp_col_deriv empty
# to maintain alignment. The new widgets go in the next two columns.

# ── DATA for experimental widgets ──
# Direction Engine A: weights aligned with 75/25 (tech×3, corr×1)
dir_a_votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
for _d, _w in [(tech_dir, 3), (corr_dir, 1)]:
    if _d in dir_a_votes:
        dir_a_votes[_d] += _w
dir_a = max(dir_a_votes, key=dir_a_votes.get)
dir_a_conf = dir_a_votes[dir_a] / 4 * 100  # confidence 0-100%
dir_a_agree = tech_dir == corr_dir and tech_dir != "NEUTRAL"

# Direction Engine B: current weights (tech×2, corr×3) + conflict detection
dir_b_votes = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
for _d, _w in [(tech_dir, 2), (corr_dir, 3)]:
    if _d in dir_b_votes:
        dir_b_votes[_d] += _w
dir_b = max(dir_b_votes, key=dir_b_votes.get)
dir_b_conf = dir_b_votes[dir_b] / 5 * 100
dir_b_conflict = (tech_dir != corr_dir and tech_dir != "NEUTRAL" and corr_dir != "NEUTRAL")

# Confirmation Score: measures how much correlations confirm the technical direction
corr_details_exp = comp.get("correlation", {}).get("details", {}).get("correlations", {})
_conf_confirming = 0
_conf_opposing = 0
_conf_total_w = 0
for _ck, _cv in corr_details_exp.items():
    if _cv is None or (isinstance(_cv, float) and np.isnan(_cv)): continue
    _exp_corr = EXPECTED_CORRELATIONS.get(_ck, 0)
    _w_conf = abs(_exp_corr)  # weight by expected correlation strength
    _conf_total_w += _w_conf
    # Determine what this asset "votes" for USDCLP direction
    # If actual corr matches sign of expected → asset is behaving normally
    # Then check if asset's recent move implies USDCLP should go up or down
    if abs(_cv - _exp_corr) < 0.3:  # only use reliable correlations
        if tech_dir == "LONG":
            _conf_confirming += _w_conf if _cv * _exp_corr > 0 else 0
            _conf_opposing += _w_conf if _cv * _exp_corr < 0 else 0
        elif tech_dir == "SHORT":
            _conf_confirming += _w_conf if _cv * _exp_corr > 0 else 0
            _conf_opposing += _w_conf if _cv * _exp_corr < 0 else 0
if _conf_total_w > 0:
    _conf_ratio = (_conf_confirming - _conf_opposing) / _conf_total_w
    confirmation_score = round(50 + _conf_ratio * 50, 1)
else:
    confirmation_score = 50.0

# Current correlation score (consensus-based, direction-blind)
current_corr_score = corr_sc

# Composite with confirmation score
composite_confirmed = round(tech_sc * WEIGHTS.technical + confirmation_score * WEIGHTS.correlation, 1)

with exp_col_dir:
    # ── Direction Engine Comparison ──
    # Engine A
    _da_clr = "#52b788" if dir_a == "LONG" else ("#ef476f" if dir_a == "SHORT" else "#ffd166")
    _da_em = "📈" if dir_a == "LONG" else ("📉" if dir_a == "SHORT" else "➡️")
    _da_bg = f"rgba({82 if dir_a=='LONG' else (239 if dir_a=='SHORT' else 255)}," \
             f"{183 if dir_a=='LONG' else (71 if dir_a=='SHORT' else 209)}," \
             f"{136 if dir_a=='LONG' else (111 if dir_a=='SHORT' else 102)},0.10)"
    # Engine B
    _db_clr = "#52b788" if dir_b == "LONG" else ("#ef476f" if dir_b == "SHORT" else "#ffd166")
    _db_em = "📈" if dir_b == "LONG" else ("📉" if dir_b == "SHORT" else "➡️")
    if dir_b_conflict:
        _db_clr = "#ff6b6b"; _db_em = "⚠️"
    _db_bg = f"rgba(255,{100 if dir_b_conflict else (209 if dir_b=='NEUTRAL' else 183)}," \
             f"{100 if dir_b_conflict else (102 if dir_b=='NEUTRAL' else 136)},0.10)"

    dir_html = (
        f"<div style='background:#1a1d23;border-radius:8px;padding:6px 8px;'>"
        f"<div style='font-size:10px;color:#888;text-align:center;margin-bottom:4px;'>"
        f"🔬 Motor de Dirección A vs B</div>"
        f"<table style='width:100%;border-collapse:collapse;'><tr>"
        # Engine A
        f"<td style='width:50%;background:{_da_bg};padding:5px 6px;text-align:center;"
        f"border-right:1px solid #333;border-radius:6px 0 0 6px;'>"
        f"<div style='font-size:9px;color:#888;'>A: Téc×3 Corr×1</div>"
        f"<div style='font-size:16px;color:{_da_clr};font-weight:900;'>{_da_em} {dir_a}</div>"
        f"<div style='font-size:11px;color:{_da_clr};'>{dir_a_conf:.0f}%</div>"
        f"<div style='font-size:8px;color:#555;'>{'✅ Consenso' if dir_a_agree else 'Solo técnico'}</div></td>"
        # Engine B
        f"<td style='width:50%;background:{_db_bg};padding:5px 6px;text-align:center;"
        f"border-radius:0 6px 6px 0;'>"
        f"<div style='font-size:9px;color:#888;'>B: Téc×2 Corr×3</div>"
        f"<div style='font-size:16px;color:{_db_clr};font-weight:900;'>{_db_em} {dir_b}</div>"
        f"<div style='font-size:11px;color:{_db_clr};'>{dir_b_conf:.0f}%</div>"
        f"<div style='font-size:8px;color:#555;'>{'⚠️ CONFLICTO' if dir_b_conflict else ('✅ Consenso' if dir_a_agree else 'Solo corr')}</div></td>"
        f"</tr></table>"
    )

    # ── Sub-score breakdown (below direction) ──
    _t_clr = "#52b788" if tech_dir == "LONG" else ("#ef476f" if tech_dir == "SHORT" else "#ffd166")
    _t_em = "📈" if tech_dir == "LONG" else ("📉" if tech_dir == "SHORT" else "➡️")
    _c_clr = "#52b788" if corr_dir == "LONG" else ("#ef476f" if corr_dir == "SHORT" else "#ffd166")
    _c_em = "📈" if corr_dir == "LONG" else ("📉" if corr_dir == "SHORT" else "➡️")
    _t_pct = tech_sc  # 0-100 directional
    _c_pct = corr_sc  # 0-100 consensus
    _t_bar_w = min(100, abs(_t_pct - 50) * 2)
    _c_bar_w = min(100, abs(_c_pct - 50) * 2)

    dir_html += (
        f"<div style='margin-top:5px;padding-top:5px;border-top:1px solid #333;'>"
        f"<div style='font-size:10px;color:#888;text-align:center;margin-bottom:3px;'>Desglose Compuesto</div>"
        # Technical sub-score
        f"<div style='display:flex;align-items:center;gap:4px;margin:2px 0;'>"
        f"<span style='font-size:9px;color:#888;width:30px;'>TÉC</span>"
        f"<span style='font-size:12px;color:{_t_clr};font-weight:bold;width:35px;'>{_t_em}{tech_sc:.0f}</span>"
        f"<div style='flex:1;background:#111;border-radius:2px;height:6px;overflow:hidden;'>"
        f"<div style='width:{_t_bar_w:.0f}%;height:100%;background:{_t_clr};border-radius:2px;'></div></div>"
        f"<span style='font-size:9px;color:#555;'>75%</span></div>"
        # Correlation sub-score
        f"<div style='display:flex;align-items:center;gap:4px;margin:2px 0;'>"
        f"<span style='font-size:9px;color:#888;width:30px;'>CORR</span>"
        f"<span style='font-size:12px;color:{_c_clr};font-weight:bold;width:35px;'>{_c_em}{corr_sc:.0f}</span>"
        f"<div style='flex:1;background:#111;border-radius:2px;height:6px;overflow:hidden;'>"
        f"<div style='width:{_c_bar_w:.0f}%;height:100%;background:{_c_clr};border-radius:2px;'></div></div>"
        f"<span style='font-size:9px;color:#555;'>25%</span></div>"
        f"</div></div>"
    )

    # Tooltip for direction engines
    dir_tip = (
        f"<b>Motor A (Propuesto):</b> Téc×3 + Corr×1 → {dir_a} ({dir_a_conf:.0f}%)<br>"
        f"Alinea pesos de dirección con el score (75/25).<br><br>"
        f"<b>Motor B (Actual):</b> Téc×2 + Corr×3 → {dir_b} ({dir_b_conf:.0f}%)<br>"
        f"Pesos actuales — correlación domina dirección."
    )
    if dir_a != dir_b:
        dir_tip += f"<br><br>⚠️ <b>Los motores DISCREPAN:</b> A dice {dir_a}, B dice {dir_b}. "
        dir_tip += f"Esto significa que el peso de la correlación cambia la recomendación."
    if dir_b_conflict:
        dir_tip += f"<br><br>🔴 <b>CONFLICTO:</b> Téc dice {tech_dir}, Corr dice {corr_dir}. Ambos con convicción."

    st.markdown(tt(dir_html, "🔬 Comparativa Motores de Dirección", dir_tip, "down"),
                unsafe_allow_html=True)

with exp_col_conf:
    # ── Confirmation Score Comparison ──
    _cs_curr_clr = "#52b788" if current_corr_score >= 65 else ("#ffd166" if current_corr_score >= 50 else "#ef476f")
    _cs_conf_clr = "#52b788" if confirmation_score >= 55 else ("#ef476f" if confirmation_score < 45 else "#ffd166")
    _cs_conf_em = "✅" if confirmation_score >= 55 else ("❌" if confirmation_score < 45 else "➡️")
    _cs_conf_txt = "Confirma" if confirmation_score >= 55 else ("Contra" if confirmation_score < 45 else "Neutral")

    # Composite comparison
    _comp_curr = score  # current composite
    _comp_new = composite_confirmed
    _comp_diff = _comp_new - _comp_curr
    _comp_diff_clr = "#52b788" if _comp_diff >= 0 else "#ef476f"

    conf_html = (
        f"<div style='background:#1a1d23;border-radius:8px;padding:6px 8px;'>"
        f"<div style='font-size:10px;color:#888;text-align:center;margin-bottom:4px;'>"
        f"🔗 Score Correlación: Actual vs Confirmación</div>"
        f"<table style='width:100%;border-collapse:collapse;'><tr>"
        # Current (consensus)
        f"<td style='width:50%;background:rgba(255,209,102,0.08);padding:5px 6px;text-align:center;"
        f"border-right:1px solid #333;border-radius:6px 0 0 6px;'>"
        f"<div style='font-size:9px;color:#888;'>Actual (Consenso)</div>"
        f"<div style='font-size:20px;color:{_cs_curr_clr};font-weight:900;'>{current_corr_score:.0f}</div>"
        f"<div style='font-size:9px;color:#888;'>No distingue dirección</div></td>"
        # New (confirmation)
        f"<td style='width:50%;background:rgba({82 if confirmation_score>=55 else 239},"
        f"{183 if confirmation_score>=55 else 71},{136 if confirmation_score>=55 else 111},0.08);"
        f"padding:5px 6px;text-align:center;border-radius:0 6px 6px 0;'>"
        f"<div style='font-size:9px;color:#888;'>Propuesto (Confirma Téc)</div>"
        f"<div style='font-size:20px;color:{_cs_conf_clr};font-weight:900;'>"
        f"{_cs_conf_em} {confirmation_score:.0f}</div>"
        f"<div style='font-size:9px;color:{_cs_conf_clr};'>{_cs_conf_txt} al técnico</div></td>"
        f"</tr></table>"
    )

    # Composite impact
    _css_curr = "score-green" if _comp_curr >= 75 else ("score-yellow" if _comp_curr >= 65 else "score-red")
    _css_new = "score-green" if _comp_new >= 75 else ("score-yellow" if _comp_new >= 65 else "score-red")
    conf_html += (
        f"<div style='margin-top:5px;padding-top:5px;border-top:1px solid #333;'>"
        f"<div style='font-size:10px;color:#888;text-align:center;margin-bottom:3px;'>Impacto en Compuesto</div>"
        f"<div style='display:flex;justify-content:center;align-items:center;gap:8px;'>"
        f"<div style='text-align:center;'>"
        f"<div style='font-size:9px;color:#888;'>Actual</div>"
        f"<div style='font-size:18px;font-weight:bold;color:#fff;'>{_comp_curr}</div></div>"
        f"<div style='font-size:14px;color:#555;'>→</div>"
        f"<div style='text-align:center;'>"
        f"<div style='font-size:9px;color:#888;'>Propuesto</div>"
        f"<div style='font-size:18px;font-weight:bold;color:#fff;'>{_comp_new}</div></div>"
        f"<div style='font-size:11px;color:{_comp_diff_clr};font-weight:bold;'>"
        f"({_comp_diff:+.1f})</div>"
        f"</div></div></div>"
    )

    # Tooltip
    conf_tip = (
        f"<b>Score Actual (Consenso):</b> {current_corr_score:.1f}<br>"
        f"Mide cuántos assets concuerdan entre sí. <b>No importa si confirman o contradicen</b> al técnico.<br><br>"
        f"<b>Score Propuesto (Confirmación):</b> {confirmation_score:.1f}<br>"
        f"Mide cuánto las correlaciones <b>confirman la dirección técnica</b>.<br>"
        f"&gt;50 = confirman | &lt;50 = contradicen | 50 = neutral<br><br>"
        f"<b>Impacto:</b> Compuesto pasa de {_comp_curr} a {_comp_new} ({_comp_diff:+.1f})<br>"
    )
    if _comp_diff < -5:
        conf_tip += f"⚠️ <b>El score propuesto BAJA</b> porque las correlaciones no confirman al técnico. "
        conf_tip += f"El score actual escondía este desacuerdo."
    elif _comp_diff > 5:
        conf_tip += f"✅ <b>El score propuesto SUBE</b> porque las correlaciones confirman al técnico."

    st.markdown(tt(conf_html, "🔗 Comparativa Score de Correlación", conf_tip, "down"),
                unsafe_allow_html=True)

# ── [COMMENTED OUT] Enhanced Correlation Table — now active in header col_corr ──
# Full code preserved for rollback. See col_corr section above.

# ── Experimental: TF Cards with Visual Slider Tooltips ──
st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

_exp_tf_scores = tech_details.get("tf_scores", {})
_exp_tf_order = [t for t in ["M1", "M2", "M5", "M15"] if t in _exp_tf_scores]
if _exp_tf_scores:
    _exp_cards = ""
    for tf in _exp_tf_order:
        r = _exp_tf_scores[tf]
        sc = r.get("score", 50)
        dr3 = r.get("direction", "NEUTRAL")
        sigs = r.get("signals", {})
        dets = r.get("details", {})
        rsi = sigs.get("rsi", 50)
        clr = "#52b788" if sc >= 65 else ("#ffd166" if sc >= 50 else "#ef476f")
        em = "🟢" if sc >= 65 else ("🟡" if sc >= 50 else "🔴")
        tf_w = {"M1": "40%", "M2": "30%", "M5": "20%", "M15": "10%"}

        # Build indicator sliders
        sliders = ""

        # EMA — 5 interpretations
        ema_d = dets.get("ema", {}); ema_sc = ema_d.get("score", 50)
        e9 = sigs.get("ema_9", 0); e21 = sigs.get("ema_21", 0); e50 = sigs.get("ema_50", 0)
        ema_cross = sigs.get("ema_cross", 0)
        if e9 > e21 > e50 > 0:
            ema_msg = "Tendencia LONG establecida — EMAs alineadas al alza (9>21>50)"
        elif e9 < e21 < e50 and e50 > 0:
            ema_msg = "Tendencia SHORT establecida — EMAs alineadas a la baja (9<21<50)"
        elif e9 > e21 and e21 < e50 and e50 > 0:
            ema_msg = "Posible giro alcista — EMA 9 cruzó sobre 21, confirmación pendiente"
        elif e9 < e21 and e21 > e50 and e50 > 0:
            ema_msg = "Posible giro bajista — EMA 9 cruzó bajo 21, precaución"
        else:
            ema_msg = "EMAs entrelazadas — sin tendencia clara, mercado lateral"
        if ema_cross == 1:
            ema_msg += " — ¡Cruce alcista!"
        elif ema_cross == -1:
            ema_msg += " — ¡Cruce bajista!"
        sliders += _slider_bar("EMA", 30, ema_sc, ema_msg)

        # RSI — 5 interpretations
        rsi_d = dets.get("rsi", {}); rsi_sc2 = rsi_d.get("score", 50)
        if rsi >= 70:
            rsi_msg = f"Sobrecompra ({rsi:.0f}) — agotamiento probable, NO entrar LONG"
        elif rsi >= 55:
            rsi_msg = f"Momentum alcista ({rsi:.0f}) — presión compradora activa"
        elif rsi >= 45:
            rsi_msg = f"Zona neutral ({rsi:.0f}) — sin presión dominante, esperar"
        elif rsi >= 30:
            rsi_msg = f"Momentum bajista ({rsi:.0f}) — presión vendedora activa"
        else:
            rsi_msg = f"Sobreventa ({rsi:.0f}) — rebote probable, buscar LONG"
        sliders += _slider_bar("RSI", 20, rsi_sc2, rsi_msg)

        # MACD — 5 interpretations
        macd_d = dets.get("macd", {}); macd_sc = macd_d.get("score", 50)
        macd_h = sigs.get("macd_histogram", 0)
        if macd_h > 0.005:
            macd_msg = f"Impulso alcista fuerte (H:{macd_h:+.4f}) — compradores dominan"
        elif macd_h > 0.001:
            macd_msg = f"Alcista moderado (H:{macd_h:+.4f}) — tendencia al alza presente"
        elif macd_h > -0.001:
            macd_msg = f"Transición (H:{macd_h:+.4f}) — posible cambio de dirección"
        elif macd_h > -0.005:
            macd_msg = f"Bajista moderado (H:{macd_h:+.4f}) — presión vendedora activa"
        else:
            macd_msg = f"Impulso bajista fuerte (H:{macd_h:+.4f}) — vendedores dominan"
        sliders += _slider_bar("MACD", 25, macd_sc, macd_msg)

        # BB — 5 interpretations
        bb_d = dets.get("bb", {}); bb_sc = bb_d.get("score", 50)
        bb_pct = sigs.get("bb_pct", 0.5)
        if bb_pct > 0.95:
            bb_msg = f"Banda superior ({bb_pct:.0%}) — extremo alto, retroceso probable"
        elif bb_pct > 0.65:
            bb_msg = f"Mitad superior ({bb_pct:.0%}) — sesgo alcista, zona de precaución"
        elif bb_pct > 0.35:
            bb_msg = f"Centro ({bb_pct:.0%}) — precio en equilibrio, sin presión extrema"
        elif bb_pct > 0.05:
            bb_msg = f"Mitad inferior ({bb_pct:.0%}) — sesgo bajista, posible rebote"
        else:
            bb_msg = f"Banda inferior ({bb_pct:.0%}) — extremo bajo, rebote probable"
        sliders += _slider_bar("BB", 15, bb_sc, bb_msg)

        # PA — 5 interpretations
        pa_d = dets.get("pa", {}); pa_sc = pa_d.get("score", 50)
        if pa_sc >= 70:
            pa_msg = "Vela alcista fuerte — cuerpo grande, compradores dominan"
        elif pa_sc >= 55:
            pa_msg = "Vela alcista moderada — compra presente pero sin convicción total"
        elif pa_sc >= 45:
            pa_msg = "Vela indecisa (doji/mecha) — mercado sin definición"
        elif pa_sc >= 30:
            pa_msg = "Vela bajista moderada — venta presente pero sin fuerza"
        else:
            pa_msg = "Vela bajista fuerte — cuerpo grande, vendedores dominan"
        sliders += _slider_bar("PA", 10, pa_sc, pa_msg)

        # Direction summary
        if sc >= 65 and dr3 == "LONG":
            dir_txt = f"<span style='color:#52b788;'>▲ LONG {sc}</span>"
        elif sc >= 65 and dr3 == "SHORT":
            dir_txt = f"<span style='color:#ef476f;'>▼ SHORT {sc}</span>"
        elif sc >= 50:
            dir_txt = f"<span style='color:#ffd166;'>◆ ESPERAR {sc}</span>"
        else:
            dir_txt = f"<span style='color:#ef476f;'>● FUERA {sc}</span>"

        # Card
        card = (
            f"<div style='text-align:center;background:#1a1d23;padding:6px 3px;border-radius:8px;'>"
            f"<div style='font-size:10px;color:#888;'>{tf} ({tf_w.get(tf,'')})</div>"
            f"<div style='font-size:22px;color:{clr};font-weight:bold;'>{em} {sc}</div>"
            f"<div style='font-size:11px;color:{clr};font-weight:bold;'>{dr3}</div>"
            f"<div style='font-size:11px;color:{'#ef476f' if rsi >= 70 else ('#52b788' if rsi <= 30 else '#aaa')}'>"
            f"RSI: <b>{rsi:.0f}</b></div></div>"
        )

        # Tooltip with sliders
        tip = (
            f"<div style='min-width:200px;'>"
            f"<div style='text-align:center;margin-bottom:4px;'>{dir_txt}</div>"
            f"{sliders}</div>"
        )

        _exp_cards += (
            f"<td style='padding:2px;width:25%;vertical-align:top;'>"
            f"<div class='tt-wrap tt-down'>{card}"
            f"<div class='tt-pop'><div class='tt-title'>📊 {tf} ({tf_w.get(tf,'')})</div>{tip}</div>"
            f"</div></td>"
        )

    _exp_table = (
        f"<div style='margin-top:4px;'>"
        f"<div style='font-size:10px;color:#888;text-align:center;margin-bottom:2px;'>"
        f"📊 TF Scores (experimental — tooltips con sliders)</div>"
        f"<table style='width:100%;border-collapse:collapse;'><tr>{_exp_cards}</tr></table></div>"
    )
    st.markdown(_exp_table, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# BACKTESTING
# ══════════════════════════════════════════════════════════
st.markdown("---")

with st.expander("📊 **Backtesting** — Validar sistema contra historial", expanded=False):
    st.markdown("""
    <div style='background:rgba(76,201,240,0.08);border:1px solid #4cc9f033;border-radius:8px;
    padding:10px 14px;margin-bottom:12px;font-size:13px;color:#aaa;'>
    Reproduce el scoring SENTINEL sobre datos históricos y compara con trades reales del operador.
    Útil para calibrar pesos y validar señales.
    </div>""", unsafe_allow_html=True)

    bt_c1, bt_c2, bt_c3, bt_c4 = st.columns([1, 1, 1, 1])
    with bt_c1:
        bt_bars = st.selectbox("📏 Período (velas M1)", [100, 250, 500, 1000, 2000],
                               index=2, help="Más velas = más tiempo de cálculo")
    with bt_c2:
        bt_trade_days = st.selectbox("📅 Historial trades (días)", [7, 14, 30, 60, 90, 180, 365],
                                     index=3, help="Días hacia atrás para buscar trades reales")
    with bt_c3:
        bt_threshold = st.slider("🎯 Umbral score", 50, 80, 65,
                                 help="Score mínimo para considerar 'señal activa'")
    with bt_c4:
        st.write("")  # spacer
        bt_run = st.button("▶️ Ejecutar Backtest", use_container_width=True, type="primary")

    if bt_run:
        try:
            from sentinel.backtester import replay_scoring, fetch_historical_trades, compare_with_trades
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            progress_bar = st.progress(0, text="⏳ Calculando scores históricos...")
            def update_progress(pct):
                progress_bar.progress(min(pct, 1.0), text=f"🔄 Replay: {pct*100:.0f}%")

            replay_df = replay_scoring(bars_back=bt_bars, progress_callback=update_progress)
            progress_bar.progress(1.0, text="✅ Replay completado")

            if not replay_df.empty:
                # ── Gráfico principal ──
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                  vertical_spacing=0.06,
                                  row_heights=[0.55, 0.45],
                                  subplot_titles=("", ""))

                fig.add_trace(go.Scatter(
                    x=replay_df['timestamp'], y=replay_df['price'],
                    name='Precio', line=dict(color='#4cc9f0', width=1.5),
                    fill='tozeroy', fillcolor='rgba(76,201,240,0.05)'),
                    row=1, col=1)

                # Score colored by zones
                fig.add_trace(go.Scatter(
                    x=replay_df['timestamp'], y=replay_df['score'],
                    name='Score', line=dict(color='#ffd166', width=2)),
                    row=2, col=1)

                # Zone fills
                fig.add_hrect(y0=bt_threshold, y1=100, fillcolor="#52b788", opacity=0.06,
                             line_width=0, row=2, col=1)
                fig.add_hrect(y0=0, y1=100-bt_threshold, fillcolor="#ef476f", opacity=0.06,
                             line_width=0, row=2, col=1)
                fig.add_hline(y=bt_threshold, line_dash='dash', line_color='#52b788',
                             opacity=0.4, row=2, col=1,
                             annotation_text=f"LONG ≥{bt_threshold}", annotation_position="right")
                fig.add_hline(y=100-bt_threshold, line_dash='dash', line_color='#ef476f',
                             opacity=0.4, row=2, col=1,
                             annotation_text=f"SHORT ≤{100-bt_threshold}", annotation_position="right")
                fig.add_hline(y=50, line_dash='dot', line_color='#555', opacity=0.3, row=2, col=1)

                fig.update_layout(
                    height=380, template='plotly_dark',
                    margin=dict(l=40, r=10, t=10, b=10),
                    showlegend=False,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(title="USDCLP", gridcolor='#1a1d23'),
                    yaxis2=dict(title="Score", gridcolor='#1a1d23', range=[0, 100]),
                )
                st.plotly_chart(fig, use_container_width=True)

                # ── Métricas ──
                avg_score = replay_df['score'].mean()
                long_pct = (replay_df['direction'] == 'LONG').mean() * 100
                short_pct = (replay_df['direction'] == 'SHORT').mean() * 100
                neutral_pct = 100 - long_pct - short_pct
                active_pct = (replay_df['score'].apply(
                    lambda s: s >= bt_threshold or s <= (100 - bt_threshold))).mean() * 100

                mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                mc1.metric("📊 Puntos", f"{len(replay_df):,}")
                mc2.metric("📈 Score Prom.", f"{avg_score:.1f}")
                mc3.metric("🟢 LONG", f"{long_pct:.0f}%")
                mc4.metric("🔴 SHORT", f"{short_pct:.0f}%")
                mc5.metric("🎯 Señal Activa", f"{active_pct:.0f}%")

                # ── Comparación con trades ──
                st.markdown("---")
                st.markdown("**Comparación con Trades Reales**")
                trades_df = fetch_historical_trades(days_back=bt_trade_days)
                if not trades_df.empty:
                    comparison = compare_with_trades(replay_df, trades_df)
                    tc1, tc2, tc3, tc4 = st.columns(4)

                    tc1.markdown(f"""<div style='background:#1a1d23;border-radius:8px;padding:12px;text-align:center;'>
                        <div style='color:#888;font-size:11px;'>Trades Analizados</div>
                        <div style='font-size:28px;font-weight:bold;color:#4cc9f0;'>{comparison['total_trades']}</div>
                        </div>""", unsafe_allow_html=True)
                    tc2.markdown(f"""<div style='background:#1a1d23;border-radius:8px;padding:12px;text-align:center;'>
                        <div style='color:#888;font-size:11px;'>SENTINEL Acertó</div>
                        <div style='font-size:28px;font-weight:bold;color:#52b788;'>{comparison['accuracy_pct']}%</div>
                        </div>""", unsafe_allow_html=True)
                    tc3.markdown(f"""<div style='background:#1a1d23;border-radius:8px;padding:12px;text-align:center;'>
                        <div style='color:#888;font-size:11px;'>Pérdidas Filtrables</div>
                        <div style='font-size:28px;font-weight:bold;color:#ef476f;'>{comparison['filter_rate_pct']}%</div>
                        </div>""", unsafe_allow_html=True)
                    tc4.markdown(f"""<div style='background:#1a1d23;border-radius:8px;padding:12px;text-align:center;'>
                        <div style='color:#888;font-size:11px;'>Total Perdedores</div>
                        <div style='font-size:28px;font-weight:bold;color:#ffd166;'>{comparison['total_losing']}</div>
                        </div>""", unsafe_allow_html=True)

                    if comparison['trade_details']:
                        st.dataframe(
                            pd.DataFrame(comparison['trade_details']),
                            use_container_width=True, hide_index=True,
                            column_config={
                                "profit": st.column_config.NumberColumn("Profit", format="%.2f"),
                                "sentinel_score": st.column_config.NumberColumn("Score", format="%.1f"),
                            })
                else:
                    st.info("💡 No se encontraron trades de USDCLP en MT5. "
                           "Conecta con la cuenta del operador para comparar.")
            else:
                st.warning("⚠️ Datos históricos insuficientes.")
        except Exception as e:
            logger.error(f"Error en backtest: {e}")
            st.error(f"❌ Error en backtest: {e}")

# ══════════════════════════════════════════════════════════
# CHAT IA
# ══════════════════════════════════════════════════════════
st.markdown("---")

with st.expander("🤖 **Asistente IA** — Análisis asistido por Claude", expanded=False):
    # Initialize AI state
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []
    if "ai_client" not in st.session_state:
        from sentinel.ai_chat import SentinelAI
        st.session_state.ai_client = SentinelAI()

    ai = st.session_state.ai_client
    from sentinel.ai_chat import MODELS

    # Header row: model + status + clear
    ai_h1, ai_h2, ai_h3 = st.columns([1.2, 2.5, 0.8])
    with ai_h1:
        ai_model = st.selectbox("Modelo", list(MODELS.keys()),
                               format_func=lambda k: MODELS[k].name, label_visibility="collapsed")
    with ai_h2:
        if not ai.is_available:
            ai_key_input = st.text_input("🔑 API Key", type="password",
                                         placeholder="sk-ant-... (obtener en console.anthropic.com)",
                                         label_visibility="collapsed")
            if ai_key_input:
                ai.set_api_key(ai_key_input)
                st.rerun()
        else:
            st.markdown(f"""<div style='background:rgba(82,183,136,0.1);border:1px solid #52b78844;
            border-radius:6px;padding:6px 12px;font-size:12px;color:#52b788;'>
            ✅ Conectado — {ai.tracker.get_summary()}</div>""", unsafe_allow_html=True)
    with ai_h3:
        if st.button("🗑️ Limpiar", use_container_width=True):
            st.session_state.ai_messages = []
            st.rerun()

    # Model description
    sel_model = MODELS[ai_model]
    st.markdown(f"""<div style='background:#1a1d23;border-radius:6px;padding:6px 10px;
    font-size:11px;color:#888;margin-bottom:8px;'>
    {sel_model.icon} <b>{sel_model.id}</b> — {sel_model.description}
    &nbsp;|&nbsp; 💰 ${sel_model.input_cost_per_mtok}/M in, ${sel_model.output_cost_per_mtok}/M out
    </div>""", unsafe_allow_html=True)

    # Chat messages container (scrollable)
    chat_container = st.container(height=350)
    with chat_container:
        if not st.session_state.ai_messages:
            st.markdown("""<div style='text-align:center;padding:60px 20px;color:#555;'>
            <div style='font-size:40px;'>🤖</div>
            <div style='font-size:14px;margin-top:8px;'>Pregunta sobre el mercado actual</div>
            <div style='font-size:11px;color:#444;margin-top:4px;'>
            La IA recibe todos los datos del dashboard en tiempo real:<br>
            scores, derivadas, correlaciones, niveles y alertas.
            </div></div>""", unsafe_allow_html=True)
        else:
            for msg in st.session_state.ai_messages:
                is_user = msg["role"] == "user"
                align = "flex-end" if is_user else "flex-start"
                bg = "rgba(76,201,240,0.12)" if is_user else "rgba(255,255,255,0.04)"
                border = "#4cc9f044" if is_user else "#33333366"
                icon = "🧑‍💻" if is_user else "🤖"

                meta_html = ""
                if msg.get("meta") and msg["meta"].get("duration_s"):
                    m = msg["meta"]
                    meta_html = (f"<div style='font-size:10px;color:#555;margin-top:4px;'>"
                                f"⏱️ {m.get('duration_s',0)}s · "
                                f"📊 {m.get('input_tokens',0):,}→{m.get('output_tokens',0):,} · "
                                f"💰 ${m.get('cost_usd',0):.4f}</div>")

                st.markdown(f"""<div style='display:flex;justify-content:{align};margin:4px 0;'>
                <div style='background:{bg};border:1px solid {border};border-radius:10px;
                padding:8px 12px;max-width:85%;font-size:13px;'>
                <span style='font-size:11px;'>{icon}</span> {msg['content']}
                {meta_html}
                </div></div>""", unsafe_allow_html=True)

    # Input area (contained, not pinned to bottom)
    ai_input_col, ai_send_col = st.columns([5, 1])
    with ai_input_col:
        ai_prompt = st.text_input("Mensaje", placeholder="Ej: ¿Debería preocuparme por el RSI de M1?",
                                  label_visibility="collapsed", key="ai_input")
    with ai_send_col:
        ai_send = st.button(f"{sel_model.icon} Enviar", use_container_width=True, type="primary")

    if ai_send and ai_prompt:
        st.session_state.ai_messages.append({"role": "user", "content": ai_prompt})

        from sentinel.ai_chat import build_market_context
        deriv_data = {
            "velocity": vel_short if 'vel_short' in dir() else 0,
            "acceleration": acceleration if 'acceleration' in dir() else 0,
            "momentum_text": mom_txt if 'mom_txt' in dir() else "N/A",
            "n_ticks": n_ticks if 'n_ticks' in dir() else 0,
        }
        system_ctx = build_market_context(result, price_info, deriv_data)
        api_msgs = [{"role": m["role"], "content": m["content"]}
                    for m in st.session_state.ai_messages[:-1]]

        with st.spinner(f"{'🧠 Pensando profundamente' if ai_model == 'opus' else '⚡ Analizando'}..."):
            response = ai.chat(ai_prompt, ai_model, system_ctx, api_msgs)

        st.session_state.ai_messages.append({
            "role": "assistant",
            "content": response["content"],
            "meta": response
        })
        st.rerun()

# ══════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.caption(f"SENTINEL v{VERSION} \"{CODENAME}\" | "
           f"Última actualización: {datetime.now().strftime('%H:%M:%S')} | "
           f"Fuente: {'🟢 MT5 Real-Time' if feed.mt5_connected else '🟡 Yahoo Finance (delay)'} | "
           f"Score: Técnico {WEIGHTS.technical*100:.0f}% + Correlación {WEIGHTS.correlation*100:.0f}%")

if auto_refresh:
    time.sleep(DASHBOARD_REFRESH_SECONDS)
    st.rerun()
