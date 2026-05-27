"""
SENTINEL v2 — Dashboard (New Layout)
Starts as exact copy of v1 header, then will be modified for new aesthetic.
Shares DataFeed and SentinelCore with v1 via st.cache_resource.
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
logger = logging.getLogger("sentinel.dashboard_v2")

from sentinel.config import (SYMBOLS, WEIGHTS, SCORE_ALERT_THRESHOLD,
    SCORE_STRONG_THRESHOLD, DASHBOARD_REFRESH_SECONDS, EXPECTED_CORRELATIONS)
from sentinel.data_feed import DataFeed
from sentinel.sentinel_core import SentinelCore
from sentinel.version import VERSION, CODENAME

try:
    st.set_page_config(page_title=f"SENTINEL v2 — USD/CLP", page_icon="⚡",
                       layout="wide", initial_sidebar_state="collapsed")
except st.errors.StreamlitAPIException:
    pass

# ══════════════════════════════════════════════════════════
# CSS (identical to v1 for now)
# ══════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* ── Anti-flicker: lock background during rerun ── */
    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewBlockContainer"],
    section.main,
    .main .block-container {
        background-color: #0e1117 !important;
    }
    /* Kill ALL Streamlit transitions/animations that cause flash */
    .stApp * { transition: none !important; animation-duration: 0.01s !important; }
    /* Re-enable only our tooltip transitions */
    .tt-wrap .tt-pop { transition: opacity 0.2s !important; }
    .spark-wrap .spark-pop { transition: opacity 0.15s !important; }
    /* Hide rerun spinner/overlay */
    div[data-testid="stStatusWidget"] { display: none !important; }
    div[data-testid="stDecoration"] { display: none !important; }
    .stApp > header { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    div[data-testid="stToolbar"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    .stApp iframe { display: none !important; }
    /* Prevent the "skeleton" loading flash */
    [data-testid="stAppViewContainer"] > section > div {
        opacity: 1 !important;
    }
    /* KEY FIX: prevent Streamlit from dimming content during rerun */
    [data-stale="true"] {
        opacity: 1 !important;
    }
    .stApp .stMarkdown { min-height: 0 !important; }

    /* ── Layout styles ── */
    .score-box { font-size: 44px; font-weight: bold; text-align: center;
        padding: 6px 14px; border-radius: 10px; line-height: 1.2; }
    .score-green { background: linear-gradient(135deg, #1a472a, #2d6a4f); color: #52b788; border: 2px solid #52b788; }
    .score-yellow { background: linear-gradient(135deg, #5c4b1f, #8a6d3b); color: #ffd166; border: 2px solid #ffd166; }
    .score-red { background: linear-gradient(135deg, #4a1a1a, #8b2c2c); color: #ef476f; border: 2px solid #ef476f; }
    .tt-wrap { position: relative; cursor: help; z-index: 100; }
    .tt-wrap .tt-pop {
        visibility: hidden; opacity: 0; position: absolute; z-index: 9999;
        bottom: 105%; left: 50%; transform: translateX(-50%); width: 380px;
        padding: 12px 14px; background: #1e2130; color: #c8ccd4;
        border: 1px solid #3a3f55; border-radius: 10px; font-size: 13px;
        line-height: 1.45; font-family: -apple-system, sans-serif;
        font-style: normal; font-weight: 400;
        max-height: 500px; overflow-y: auto;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        pointer-events: none;
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
    .spark-wrap { position: relative; cursor: crosshair; }
    .spark-wrap .spark-pop {
        visibility: hidden; opacity: 0; position: absolute;
        top: 110%; left: 50%; transform: translateX(-50%);
        z-index: 1000; background: #1a1d23; border: 1px solid #3a3f55;
        border-radius: 8px; padding: 6px 8px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.6);
        pointer-events: none; white-space: nowrap;
    }
    .spark-wrap:hover .spark-pop { visibility: visible; opacity: 1; }
    section.main div[data-testid="stHorizontalBlock"]:first-of-type {
        align-items: stretch !important;
    }
    section.main div[data-testid="stColumn"]:first-child div[data-testid="stMarkdownContainer"] {
        margin-bottom: -12px;
    }
    section.main div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="stColumn"] > div {
        height: 100%; display: flex; flex-direction: column; justify-content: flex-start;
    }
    .macro-votes-wrap { display: flex; flex-direction: column; justify-content: space-between; }
    .macro-votes-wrap table { flex: 1; }
</style>
""", unsafe_allow_html=True)

def tt(content, title, body, direction="up"):
    cls = "tt-wrap" if direction == "up" else "tt-wrap tt-down"
    return (f'<div class="{cls}">{content}'
            f'<div class="tt-pop"><div class="tt-title">{title}</div>{body}</div></div>')

# ══════════════════════════════════════════════════════════
# INIT + CALCULATION
# ══════════════════════════════════════════════════════════
@st.cache_resource
def init_system():
    feed = DataFeed(mode="auto")
    return feed, SentinelCore(feed)

feed, core = init_system()

with st.sidebar:
    st.title(f"⚡ SENTINEL v2")
    st.caption("USD/CLP — New Layout")
    st.divider()
    status = feed.get_status()
    if status['mt5_connected']:
        st.success("📡 MT5 REAL-TIME")
    else:
        st.warning("📡 Yahoo Finance (delay)")
    auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)

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
# CROSS-ASSET DATA (for correlation table + macro votes)
# ══════════════════════════════════════════════════════════
from sentinel.technical_scorer import calculate_multi_tf_score

_cross_asset_keys = ["dxy", "copper", "wti", "usdmxn", "usdbrl", "audusd", "usdcnh", "sp500"]
_cross_tech = {}
_cross_m1 = {}

if '_cross_last_prices_v2' not in st.session_state:
    st.session_state._cross_last_prices_v2 = {}

_target_m1_closes = None
try:
    _target_m1 = feed.get_data(SYMBOLS["target"], timeframe_minutes=1, bars=30)
    if _target_m1 is not None and len(_target_m1) >= 10:
        _target_m1_closes = _target_m1['close'].values
except Exception:
    pass
_cross_corr_hoy = {}

for _cak in _cross_asset_keys:
    _ca_symbol = SYMBOLS.get(_cak, "")
    if _ca_symbol:
        try:
            _ca_result = calculate_multi_tf_score(feed, _ca_symbol)
            _tfs = _ca_result.get("tf_scores", {})
            _fast = _tfs.get("M1", {}).get("score", 50) * 2/3 + _tfs.get("M2", {}).get("score", 50) * 1/3
            _cross_tech[_cak] = {
                "score": _ca_result.get("composite_score", 50),
                "fast_score": _fast,
                "direction": _ca_result.get("h4_direction", "NEUTRAL"),
            }
        except Exception:
            _cross_tech[_cak] = {"score": 50, "fast_score": 50, "direction": "NEUTRAL"}
        try:
            _ca_m1_data = feed.get_data(_ca_symbol, timeframe_minutes=1, bars=30)
            if _ca_m1_data is not None and len(_ca_m1_data) >= 6:
                _cls = _ca_m1_data['close'].values
                _m2_bps = (_cls[-1] - _cls[-3]) / _cls[-3] * 10000
                _m5_bps = (_cls[-1] - _cls[-6]) / _cls[-6] * 10000
                _cross_m1[_cak] = {"m2": _m2_bps, "m5": _m5_bps, "spark": list(_cls[-6:])}
                if _target_m1_closes is not None:
                    _min_len = min(len(_target_m1_closes), len(_cls))
                    if _min_len >= 10:
                        _t_ret = np.diff(np.log(_target_m1_closes[-_min_len:]))
                        _a_ret = np.diff(np.log(_cls[-_min_len:]))
                        _rcorr = np.corrcoef(_t_ret, _a_ret)[0, 1]
                        if np.isfinite(_rcorr):
                            _exp_s = np.sign(EXPECTED_CORRELATIONS.get(_cak, 0))
                            _dir_c = _rcorr * _exp_s
                            _hoy_pct = min(100, max(0, (_dir_c + 0.5) * 100))
                            _cross_corr_hoy[_cak] = round(_hoy_pct)
        except Exception:
            pass
        try:
            _ca_tick = feed.get_current_price(_ca_symbol)
            _curr_bid = _ca_tick.get("bid", 0) if _ca_tick else 0
            if _curr_bid > 0:
                _prev_bid = st.session_state._cross_last_prices_v2.get(_cak, _curr_bid)
                _tick_bps = (_curr_bid - _prev_bid) / _prev_bid * 10000
                _cross_m1.setdefault(_cak, {})["tick"] = _tick_bps
                st.session_state._cross_last_prices_v2[_cak] = _curr_bid
        except Exception:
            pass

def _bps_to_arrow(bps, sensitivity=9, threshold=2):
    angle = max(0, min(180, 90 - bps * sensitivity))
    if bps > threshold: clr = "#52b788"
    elif bps < -threshold: clr = "#ef476f"
    else: clr = "#555"
    return angle, clr

def _slider_bar(label, weight_pct, score, msg):
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

# MacroScorer pre-calc
if not hasattr(core, 'macro_scorer'):
    from sentinel.macro_scorer import MacroScorer
    core.macro_scorer = MacroScorer()
_ms = core.macro_scorer
_macro_result = comp.get("_macro", _ms.calculate_score(feed))
_macro_score = _macro_result["score"]
_macro_dir = _macro_result["direction"]

# ══════════════════════════════════════════════════════════
# HEADER — 5 columnas en 1 fila (exact copy from v1)
# ══════════════════════════════════════════════════════════
col_score, col_macro, col_tf, col_corr, col_levels = st.columns([0.55, 1.1, 1.6, 1.0, 0.35])

with col_score:
    # ── Price derivative buffer ──
    if "price_buffer" not in st.session_state:
        st.session_state.price_buffer = []
        st.session_state.price_timestamps = []
    curr_bid = price_info.get("bid", 0)
    now_ts = time.time()
    if curr_bid > 0:
        st.session_state.price_buffer.append(curr_bid)
        st.session_state.price_timestamps.append(now_ts)
        if len(st.session_state.price_buffer) > 200:
            st.session_state.price_buffer = st.session_state.price_buffer[-200:]
            st.session_state.price_timestamps = st.session_state.price_timestamps[-200:]
    buf = st.session_state.price_buffer
    ts_buf = st.session_state.price_timestamps
    n_ticks = len(buf)

    # Velocity & acceleration at different windows
    vel_short = 0.0; vel_medium = 0.0; vel_long = 0.0; vel_5m = 0.0
    acc_short = 0.0; acc_medium = 0.0; acc_long = 0.0; acc_5m = 0.0
    velocity = 0.0; acceleration = 0.0
    if n_ticks >= 2:
        dt = ts_buf[-1] - ts_buf[-2]
        if dt > 0: vel_short = (buf[-1] - buf[-2]) / dt
        velocity = vel_short
    def _accel_window(b, tb, w):
        if len(b) < w + 1: return 0.0
        mid = w // 2
        dt1 = tb[-1] - tb[-mid] if tb[-1] != tb[-mid] else 1
        dt2 = tb[-mid] - tb[-w] if tb[-mid] != tb[-w] else 1
        v1 = (b[-1] - b[-mid]) / dt1
        v2 = (b[-mid] - b[-w]) / dt2
        dt_a = (dt1 + dt2) / 2
        return (v1 - v2) / dt_a if dt_a > 0 else 0.0
    if n_ticks >= 3:
        acc_short = _accel_window(buf, ts_buf, 3)
        acceleration = acc_short
    if n_ticks >= 6:
        dt_m = ts_buf[-1] - ts_buf[-6]
        if dt_m > 0: vel_medium = (buf[-1] - buf[-6]) / dt_m
        acc_medium = _accel_window(buf, ts_buf, 6)
    if n_ticks >= 12:
        dt_l = ts_buf[-1] - ts_buf[-12]
        if dt_l > 0: vel_long = (buf[-1] - buf[-12]) / dt_l
        acc_long = _accel_window(buf, ts_buf, 12)
    if n_ticks >= 24:
        dt_5 = ts_buf[-1] - ts_buf[-24]
        if dt_5 > 0: vel_5m = (buf[-1] - buf[-24]) / dt_5
        acc_5m = _accel_window(buf, ts_buf, 24)

    def vel_to_boost(v, scale=0.05): return max(-25, min(25, (v / scale) * 25))
    def accel_to_boost(a, scale=0.01): return max(-10, min(10, (a / scale) * 10))

    # ── Fused signal cards (A+C): direction from engine, confidence from enhanced ──
    _tf_sc = tech_details.get("tf_scores", {})
    _sc_map = {t: _tf_sc.get(t, {}).get("score", 50) for t in ("M1","M2","M5","M15")}
    _dir_map = {t: _tf_sc.get(t, {}).get("direction", "NEUTRAL") for t in ("M1","M2","M5","M15")}

    _fused_defs = [
        ("\u26a1", "5s",  {"M1":1.0},                         vel_short,  acc_short,  0.50, 0.30),
        ("\U0001f504", "30s", {"M1":0.6,"M2":0.4},                vel_medium, acc_medium, 0.30, 0.15),
        ("\U0001f4ca", "1m",  {"M1":0.4,"M2":0.3,"M5":0.3},       vel_long,   acc_long,   0.15, 0.05),
        ("\U0001f4c8", "5m",  {"M5":0.6,"M15":0.4},               vel_5m,     acc_5m,     0.10, 0.03),
    ]
    _cells = ""; _ttp = []
    for _ic, _sp, _wt, _vel, _acc, _vw, _aw in _fused_defs:
        # Direction from engine voting (Row 1 logic)
        _vl = sum(w for t,w in _wt.items() if _dir_map.get(t)=="LONG")
        _vs = sum(w for t,w in _wt.items() if _dir_map.get(t)=="SHORT")
        _sd = "LONG" if _vl>_vs and _vl>0.3 else ("SHORT" if _vs>_vl and _vs>0.3 else "NEUTRAL")

        # Enhanced score for confidence (Row 2 logic)
        _bl = sum(_sc_map.get(t,50)*w for t,w in _wt.items())
        _vb = vel_to_boost(_vel); _ab = accel_to_boost(_acc)
        _enh = max(0, min(100, _bl + (_vb * _vw * 2) + (_ab * _aw * 2)))
        _cv = min(100, abs(_enh - 50) * 2)

        # Disagreement detection
        _sd2 = "LONG" if _enh >= 55 else ("SHORT" if _enh <= 45 else "NEUTRAL")
        _disagree = (_sd != _sd2) and _sd != "NEUTRAL" and _sd2 != "NEUTRAL"

        # Colors
        if _sd=="LONG":    _r,_g,_b=82,183,136; _ar="\u25b2"; _ac="COMPRAR"; _ep=price_info.get("ask",0)
        elif _sd=="SHORT": _r,_g,_b=239,71,111; _ar="\u25bc"; _ac="VENDER"; _ep=price_info.get("bid",0)
        else:              _r,_g,_b=255,209,102; _ar="\u25c6"; _ac="ESPERAR"; _ep=0
        _op = 0.10+(_cv/100)*0.45
        _tc = f"rgb({_r},{_g},{_b})"; _bg = f"rgba({_r},{_g},{_b},{_op:.2f})"

        # Acceleration icon
        if _acc > 0.002: _aic = "\u23eb"
        elif _acc > 0: _aic = "\U0001f53c"
        elif _acc > -0.002: _aic = "\U0001f53d"
        else: _aic = "\u23ec"

        # Disagreement dot
        _dot = (f"<span style='position:absolute;top:1px;right:2px;font-size:7px;"
                f"color:#ff9f1c;' title='T\u00e9c\u2260Deriv'>\u25cf</span>") if _disagree else ""

        _ept = f"<div style='font-size:9px;color:#666;'>{_ep:.1f}</div>" if _ep>0 else ""
        _cells += (f"<td style='background:{_bg};padding:4px 4px;text-align:center;"
                   f"border-right:1px solid #333;width:25%;position:relative;'>"
                   f"{_dot}"
                   f"<div style='font-size:18px;color:{_tc};font-weight:900;line-height:1.2;'>{_ar}</div>"
                   f"<div style='font-size:10px;color:{_tc};font-weight:bold;line-height:1.2;'>{_ac}</div>"
                   f"<div style='font-size:13px;color:#fff;font-weight:bold;line-height:1.2;'>{_cv:.0f}%</div>"
                   f"{_ept}</td>")

        # Tooltip
        _det = " + ".join(f"{t}({_sc_map.get(t,50):.0f})" for t in _wt)
        v_dir = "\u2191" if _vel > 0 else ("\u2193" if _vel < 0 else "\u2192")
        a_dir = "acelerando" if _acc > 0.001 else ("frenando" if _acc < -0.001 else "estable")
        _disag_txt = f"<br><span style='color:#ff9f1c;'>\u26a0\ufe0f Derivadas dicen: {_sd2}</span>" if _disagree else ""
        _ttp.append(
            f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
            f"border-radius:5px;padding:4px 7px;margin:3px 0;'>"
            f"<b>{_ic} {_sp}</b> \u2014 <span style='color:{_tc};'><b>{_ac} {_cv:.0f}%</b></span><br>"
            f"<span style='color:#888;'>T\u00e9c: {_det} = {_bl:.1f}</span><br>"
            f"<span style='color:#888;'>+ Vel({_vb:+.1f}\u00d7{_vw}) + Acc({_ab:+.1f}\u00d7{_aw}) = <b>{_enh:.1f}</b></span><br>"
            f"<span style='color:#888;'>Velocidad: {_vel:+.4f}/s {v_dir} | {_aic} {a_dir}</span>"
            f"{_disag_txt}</div>")

    _sig_html = (f"<div style='background:#151820;border-radius:8px;overflow:hidden;'>"
                 f"<table style='width:100%;border-collapse:collapse;table-layout:fixed;margin:0;'><tr>{_cells}</tr></table>"
                 f"<div style='text-align:center;font-size:7px;color:#555;letter-spacing:2px;padding:1px 0;'"
                 f">TÉCNICO</div></div>")
    st.markdown(tt(_sig_html, "\U0001f3af Se\u00f1ales Fusionadas (T\u00e9c + Derivadas)",
        f"{''.join(_ttp)}<br>"
        f"<b>Direcci\u00f3n:</b> del engine t\u00e9cnico (votaci\u00f3n por TF)<br>"
        f"<b>Confianza %:</b> score t\u00e9cnico + derivadas de precio<br>"
        f"<b>{_aic}:</b> aceleraci\u00f3n del precio<br>"
        f"<b style='color:#ff9f1c;'>\u25cf</b> punto naranja = derivadas discrepan del t\u00e9cnico<br><br>"
        f"\u26a1=M1 | \U0001f504=M1+M2 | \U0001f4ca=M1+M2+M5 | \U0001f4c8=M5+M15",
        "down"), unsafe_allow_html=True)

    # \u2500\u2500 Momentum slider bar \u2500\u2500
    if vel_short > 0.01 and acceleration > 0.001:
        mom_txt = "\U0001f4c8 Subiendo y acelerando"; mom_clr = "#52b788"; mom_ic = "\u23eb"
    elif vel_short > 0.01 and acceleration < -0.001:
        mom_txt = "\U0001f4c8 Subiendo pero frenando"; mom_clr = "#a8d5a2"; mom_ic = "\U0001f53c"
    elif vel_short > 0:
        mom_txt = "\u2197\ufe0f Subiendo suave"; mom_clr = "#888"; mom_ic = "\U0001f53c"
    elif vel_short < -0.01 and acceleration < -0.001:
        mom_txt = "\U0001f4c9 Bajando y acelerando"; mom_clr = "#ef476f"; mom_ic = "\u23ec"
    elif vel_short < -0.01 and acceleration > 0.001:
        mom_txt = "\U0001f4c9 Bajando pero frenando"; mom_clr = "#f4a0b0"; mom_ic = "\U0001f53d"
    elif vel_short < 0:
        mom_txt = "\u2198\ufe0f Bajando suave"; mom_clr = "#888"; mom_ic = "\U0001f53d"
    else:
        mom_txt = "\u27a1\ufe0f Sin movimiento"; mom_clr = "#555"; mom_ic = "\u23f8\ufe0f"
    mom_pct = min(100, abs(vel_short) / 0.05 * 100)
    bar_clr = "#52b788" if vel_short > 0 else "#ef476f"
    fill_dir = "right" if vel_short > 0 else "left"
    deriv_info = (
        f"<div style='background:#1a1d23;border-radius:8px;padding:3px 8px;margin-top:2px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;font-size:11px;'>"
        f"<span style='color:{mom_clr};font-weight:bold;'>{mom_ic} {mom_txt}</span>"
        f"<span style='color:#555;font-size:9px;'>{n_ticks} ticks</span></div>"
        f"<div style='background:#111;border-radius:3px;height:4px;margin-top:2px;overflow:hidden;'>"
        f"<div style='width:{mom_pct:.0f}%;height:100%;background:{bar_clr};"
        f"border-radius:3px;float:{fill_dir};'></div></div></div>")
    st.markdown(tt(deriv_info, "\U0001f4c8 Momentum del Precio",
        f"<b>{mom_txt}</b><br>"
        f"Vel: {vel_short:+.4f}/s | Acc: {acceleration:+.6f}/s\u00b2<br>"
        f"Buffer: {n_ticks} ticks (~{n_ticks*5}s)",
        "down"), unsafe_allow_html=True)


    # ── Macro Derivative Signal Cards ──
    # Buffer the macro score over time to compute its velocity & acceleration
    if "macro_score_buffer" not in st.session_state:
        st.session_state.macro_score_buffer = []
        st.session_state.macro_score_ts = []
    _ms_val = _macro_score  # current macro score (0-100)
    _ms_now = time.time()
    st.session_state.macro_score_buffer.append(_ms_val)
    st.session_state.macro_score_ts.append(_ms_now)
    if len(st.session_state.macro_score_buffer) > 200:
        st.session_state.macro_score_buffer = st.session_state.macro_score_buffer[-200:]
        st.session_state.macro_score_ts = st.session_state.macro_score_ts[-200:]
    _mb = st.session_state.macro_score_buffer
    _mt = st.session_state.macro_score_ts
    _mn = len(_mb)

    # Macro velocities at different windows
    def _macro_vel(b, t, w):
        if len(b) < w + 1: return 0.0
        dt = t[-1] - t[-w]
        return (b[-1] - b[-w]) / dt if dt > 0 else 0.0

    def _macro_acc(b, t, w):
        if len(b) < w + 1: return 0.0
        mid = w // 2
        dt1 = t[-1] - t[-mid] if t[-1] != t[-mid] else 1
        dt2 = t[-mid] - t[-w] if t[-mid] != t[-w] else 1
        v1 = (b[-1] - b[-mid]) / dt1
        v2 = (b[-mid] - b[-w]) / dt2
        dt_a = (dt1 + dt2) / 2
        return (v1 - v2) / dt_a if dt_a > 0 else 0.0

    _mv_s = _macro_vel(_mb, _mt, 2) if _mn >= 3 else 0.0   # ~5s
    _mv_m = _macro_vel(_mb, _mt, 6) if _mn >= 7 else 0.0   # ~30s
    _mv_l = _macro_vel(_mb, _mt, 12) if _mn >= 13 else 0.0  # ~1m
    _mv_5 = _macro_vel(_mb, _mt, 24) if _mn >= 25 else 0.0  # ~5m
    _ma_s = _macro_acc(_mb, _mt, 3) if _mn >= 4 else 0.0
    _ma_m = _macro_acc(_mb, _mt, 6) if _mn >= 7 else 0.0
    _ma_l = _macro_acc(_mb, _mt, 12) if _mn >= 13 else 0.0
    _ma_5 = _macro_acc(_mb, _mt, 24) if _mn >= 25 else 0.0

    # Macro signal cards: base = macro_score, boosted by macro velocity/acceleration
    def _m_vel_boost(v, scale=2.0): return max(-25, min(25, (v / scale) * 25))
    def _m_acc_boost(a, scale=0.5): return max(-10, min(10, (a / scale) * 10))

    _macro_card_defs = [
        ("⚡", "5s",  _ms_val, _mv_s, _ma_s, 0.50, 0.30),
        ("🔄", "30s", _ms_val, _mv_m, _ma_m, 0.30, 0.15),
        ("📊", "1m",  _ms_val, _mv_l, _ma_l, 0.15, 0.05),
        ("📈", "5m",  _ms_val, _mv_5, _ma_5, 0.10, 0.03),
    ]
    _mc_cells = ""; _mc_ttp = []
    for _ic, _sp, _base, _vel, _acc, _vw, _aw in _macro_card_defs:
        _vb = _m_vel_boost(_vel); _ab = _m_acc_boost(_acc)
        _enh = max(0, min(100, _base + (_vb * _vw * 2) + (_ab * _aw * 2)))
        _sd = "LONG" if _enh >= 55 else ("SHORT" if _enh <= 45 else "NEUTRAL")
        _cv = min(100, abs(_enh - 50) * 2)
        if _sd == "LONG":    _r,_g,_b = 82,183,136; _ar="▲"; _ac="COMPRAR"
        elif _sd == "SHORT": _r,_g,_b = 239,71,111; _ar="▼"; _ac="VENDER"
        else:                _r,_g,_b = 255,209,102; _ar="◆"; _ac="ESPERAR"
        _op = 0.10 + (_cv / 100) * 0.45
        _tc = f"rgb({_r},{_g},{_b})"; _bg = f"rgba({_r},{_g},{_b},{_op:.2f})"
        if _acc > 0.1: _aic = "⏫"
        elif _acc > 0: _aic = "🔼"
        elif _acc > -0.1: _aic = "🔽"
        else: _aic = "⏬"
        _mc_cells += (f"<td style='background:{_bg};padding:4px 4px;text-align:center;"
                      f"border-right:1px solid #333;width:25%;'>"
                      f"<div style='font-size:18px;color:{_tc};font-weight:900;line-height:1.2;'>{_ar}</div>"
                      f"<div style='font-size:10px;color:{_tc};font-weight:bold;line-height:1.2;'>{_ac}</div>"
                      f"<div style='font-size:13px;color:#fff;font-weight:bold;line-height:1.2;'>{_cv:.0f}%</div>"
                      f"</td>")
        _vd = "↑" if _vel > 0 else ("↓" if _vel < 0 else "→")
        _ad = "acelerando" if _acc > 0.05 else ("frenando" if _acc < -0.05 else "estable")
        _mc_ttp.append(
            f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
            f"border-radius:5px;padding:4px 7px;margin:3px 0;'>"
            f"<b>{_ic} {_sp}</b> — <span style='color:{_tc};'><b>{_ac} {_cv:.0f}%</b></span><br>"
            f"Macro base: {_base:.1f} + Vel({_vb:+.1f}×{_vw}) + Acc({_ab:+.1f}×{_aw}) = <b>{_enh:.1f}</b><br>"
            f"<span style='color:#888;'>Vel: {_vel:+.2f}/s {_vd} | {_ad}</span></div>")
    _mc_html = (f"<div style='background:#151820;border-radius:8px;overflow:hidden;margin-top:3px;'>"
                f"<table style='width:100%;border-collapse:collapse;table-layout:fixed;margin:0;'><tr>{_mc_cells}</tr></table>"
                f"<div style='text-align:center;font-size:7px;color:#555;letter-spacing:2px;padding:1px 0;'"
                f">MACRO</div></div>")
    st.markdown(tt(_mc_html, "🌍 Señales Macro (derivadas)",
        f"{''.join(_mc_ttp)}<br>"
        f"<b>Lógica:</b> Macro score puro ({_ms_val:.1f}) + derivadas de velocidad/aceleración<br>"
        f"del propio score macro en ventanas de 5s a 5m.<br><br>"
        f"Buffer: {_mn} muestras (~{_mn*5}s)",
        "down"), unsafe_allow_html=True)

    # ── Triple Signal Cards (Técnico / Macro / Fusión) ──
    _fusion = _ms.calculate_fusion(tech_sc, tech_dir, _macro_score, _macro_dir)
    def _mini_card(label, sc, dr):
        if dr == 'LONG':    clr='#52b788'; ar='▲'; ac='COMPRAR'
        elif dr == 'SHORT': clr='#ef476f'; ar='▼'; ac='VENDER'
        else:               clr='#ffd166'; ar='◆'; ac='ESPERAR'
        bp = min(100, abs(sc - 50) * 2)
        bs = 'left' if sc >= 50 else 'right'
        return (
            f"<td style='width:33.3%;padding:0 2px;vertical-align:top;'>"
            f"<div style='background:#1a1d23;border-radius:6px;padding:3px 4px;"
            f"text-align:center;border:1px solid {clr}22;'>"
            f"<div style='font-size:8px;color:#888;line-height:1;'>{label}</div>"
            f"<div style='font-size:16px;color:{clr};font-weight:900;line-height:1.1;'>{ar}</div>"
            f"<div style='font-size:13px;color:{clr};font-weight:bold;line-height:1.1;'>{sc:.0f}</div>"
            f"<div style='font-size:8px;color:{clr};font-weight:bold;line-height:1.1;'>{ac}</div>"
            f"<div style='background:#2a2d35;border-radius:2px;height:3px;margin-top:2px;overflow:hidden;'>"
            f"<div style='background:{clr};height:100%;width:{bp:.0f}%;border-radius:2px;"
            f"float:{bs};'></div></div>"
            f"</div></td>")

    _tc1 = _mini_card('\U0001f527 T\u00e9cnico', tech_sc, tech_dir)
    _tc2 = _mini_card('\U0001f30d Macro', _macro_score, _macro_dir)
    _tc3 = _mini_card('\u26a1 Fusi\u00f3n', _fusion['score'], _fusion['direction'])
    _triple_html = (
        f"<table style='width:100%;border-collapse:collapse;table-layout:fixed;margin-top:3px;'>"
        f"<tr>{_tc1}{_tc2}{_tc3}</tr></table>")
    _warmed = _macro_result['assets_warmed_up']
    _total = _macro_result['total_assets_tracked']
    _conf_avg = _macro_result['confidence_avg']
    st.markdown(tt(_triple_html, '\U0001f9ea Triple Signal System',
        f"T\u00e9cnico: <b>{tech_sc:.0f}</b> ({tech_dir}) \u2014 EMA+RSI+MACD+BB\u00d74TF<br>"
        f"Macro: <b>{_macro_score:.0f}</b> ({_macro_dir}) \u2014 {_warmed}/{_total} activos, conf {_conf_avg:.0%}<br>"
        f"Fusi\u00f3n: <b>{_fusion['score']:.0f}</b> ({_fusion['direction']}) \u2014 Confl {_fusion['confluence_pct']:.0f}%",
        'down'), unsafe_allow_html=True)

    # Confluence slider
    _conf_pct = _fusion['confluence_pct']
    _conf_clr = '#52b788' if _fusion['aligned'] else ('#ef476f' if _fusion['opposed'] else '#ffd166')
    _conf_label = '\u2705 CONFL' if _fusion['aligned'] else ('\u26a0\ufe0f DIVER' if _fusion['opposed'] else '\u27a1\ufe0f PARCIAL')
    _risk = _fusion['risk_mode']
    st.markdown(
        f"<div style='background:#1a1d23;border-radius:6px;padding:2px 6px;margin-top:2px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;font-size:9px;'>"
        f"<span style='color:{_conf_clr};font-weight:bold;'>{_conf_label} {_conf_pct:.0f}%</span>"
        f"<span style='color:#555;'>{_fusion['risk_emoji']} {_risk}</span></div>"
        f"<div style='background:#2a2d35;border-radius:3px;height:4px;margin-top:2px;overflow:hidden;'>"
        f"<div style='background:{_conf_clr};height:100%;width:{_conf_pct:.0f}%;"
        f"border-radius:3px;'></div></div></div>",
        unsafe_allow_html=True)


# ── COL 5: Niveles ──
def _level_tooltip(lb, lv, curr_price, is_resistance):
    pct = lv['pct']; dist = abs(pct); price = lv['price']
    if is_resistance:
        if dist < 0.10: rec = f"⚠️ <b>Resistencia inminente</b> a solo {dist:.2f}%.<br>Cuidado con LONGs."
        elif dist < 0.30: rec = f"Resistencia cercana ({dist:.2f}%). Buscar señal de rechazo."
        else: rec = f"Resistencia lejana ({dist:.2f}%). Espacio al alza hasta <b>{price:.2f}</b>."
        if lb == 'R3': rec += "<br><br>🔺 <b>R3 = resistencia extrema.</b>"
    else:
        if dist < 0.10: rec = f"⚠️ <b>Soporte inminente</b> a solo {dist:.2f}%.<br>Posible rebote."
        elif dist < 0.30: rec = f"Soporte cercano ({dist:.2f}%). Buscar rebote para LONG."
        else: rec = f"Soporte lejano ({dist:.2f}%). Target bajista en <b>{price:.2f}</b>."
        if lb == 'S3': rec += "<br><br>🔻 <b>S3 = soporte extremo.</b>"
    return rec

with col_levels:
    if combined and curr_price > 0:
        above = combined.get("above", [])
        below = combined.get("below", [])
        for i, lv in enumerate(reversed(above)):
            lb = f"R{len(above) - i}"
            rh = (f"<div style='display:flex;justify-content:space-between;align-items:center;padding:4px 3px;"
                  f"font-family:monospace;background:rgba(239,71,111,0.08);"
                  f"border-left:2px solid #ef476f;border-radius:2px;margin:0;line-height:1.3;'>"
                  f"<span style='color:#ef476f;font-size:9px;'>{lb}</span>"
                  f"<span style='font-weight:bold;font-size:16px;'>{lv['price']:.1f}</span>"
                  f"<span style='color:#ef476f;font-size:9px;'>{lv['pct']:+.1f}%</span></div>")
            tip = _level_tooltip(lb, lv, curr_price, True)
            st.markdown(tt(rh, f"🔴 {lb} — Resistencia ({lv['price']:.2f})", tip, "down"), unsafe_allow_html=True)
        _sprd = price_info.get('spread', 0) if price_info else 0
        _src = 'MT5' if price_info.get('source')=='mt5' else 'Yahoo'
        st.markdown(tt(
            f"<div style='display:flex;justify-content:space-between;align-items:center;padding:5px 3px;"
            f"font-family:monospace;background:rgba(76,201,240,0.12);border:1px solid #4cc9f0;"
            f"border-radius:2px;margin:1px 0;line-height:1.3;'>"
            f"<span style='color:#4cc9f0;font-size:9px;font-weight:bold;'>USD</span>"
            f"<span style='font-size:17px;font-weight:bold;color:#4cc9f0;'>{curr_price:.1f}</span>"
            f"<span style='color:#4cc9f0;font-size:9px;'>±{_sprd:.0f}</span></div>",
            "💲 Precio en Vivo",
            f"Bid: {price_info['bid']:.2f} | Ask: {price_info['ask']:.2f} | Spread: {_sprd:.2f}<br>"
            f"Fuente: <b>{_src}</b>",
            "down"), unsafe_allow_html=True)
        for i, lv in enumerate(below):
            lb = f"S{i+1}"
            rh = (f"<div style='display:flex;justify-content:space-between;align-items:center;padding:4px 3px;"
                  f"font-family:monospace;background:rgba(82,183,136,0.08);"
                  f"border-left:2px solid #52b788;border-radius:2px;margin:0;line-height:1.3;'>"
                  f"<span style='color:#52b788;font-size:9px;'>{lb}</span>"
                  f"<span style='font-weight:bold;font-size:16px;'>{lv['price']:.1f}</span>"
                  f"<span style='color:#52b788;font-size:9px;'>{lv['pct']:+.1f}%</span></div>")
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
        tf_cols = st.columns(len(active_tfs), gap="small")
        tf_w = {"M1": "35%", "M2": "35%", "M5": "20%", "M15": "10%"}
        tf_roles = {"M1": "Ejecución", "M2": "Confirmación", "M5": "Tendencia", "M15": "Contexto"}
        for col_idx, tf in enumerate(active_tfs):
            r = tf_scores[tf]
            sc = r.get("score", 50); dr3 = r.get("direction", "NEUTRAL")
            sigs = r.get("signals", {}); dets = r.get("details", {})
            rsi = sigs.get("rsi", 0)
            _intensity = min(1.0, abs(sc - 50) / 40)
            if sc >= 50:
                _cr = int(136 - (136 - 82) * _intensity)
                _cg = int(136 + (183 - 136) * _intensity)
                _cb = int(136 + (136 - 136) * _intensity)
            else:
                _cr = int(136 + (239 - 136) * _intensity)
                _cg = int(136 - (136 - 71) * _intensity)
                _cb = int(136 - (136 - 111) * _intensity)
            clr = f"rgb({_cr},{_cg},{_cb})"
            em = "🟢" if sc >= 65 else ("🟡" if sc >= 50 else "🔴")
            rc = "#ef476f" if rsi >= 70 else ("#52b788" if rsi <= 30 else "#aaa")
            rt = "OB" if rsi >= 70 else ("OS" if rsi <= 30 else "")
            rp = []
            if dr3 == "LONG":
                action = "📈 COMPRAR"
                rp.append(f"✅ <b>Señal COMPRAR</b> ({sc}/100).")
            elif dr3 == "SHORT":
                action = "📉 VENDER"
                rp.append(f"✅ <b>Señal VENDER</b> ({sc}/100).")
            else:
                action = "🟡 ESPERAR"
                rp.append(f"🟡 <b>Sin dirección clara</b> ({sc}/100).")
            if rsi >= 70: rp.append(f"<br>⚠️ RSI <b>{rsi:.0f}</b> SOBRECOMPRA.")
            elif rsi <= 30: rp.append(f"<br>⚠️ RSI <b>{rsi:.0f}</b> SOBREVENTA.")
            elif rsi > 55: rp.append(f"<br>RSI <b>{rsi:.0f}</b> — alcista.")
            elif rsi < 45: rp.append(f"<br>RSI <b>{rsi:.0f}</b> — bajista.")
            else: rp.append(f"<br>RSI <b>{rsi:.0f}</b> — neutral.")
            # Indicator sliders in tooltip
            rp.append(f"<br><div style='border-top:1px solid #444;padding-top:4px;margin-top:4px;'>"
                      f"<b>📋 Indicadores {tf}:</b></div>")
            ema_d = dets.get("ema", {}); ema_sc = ema_d.get("score", 50)
            e9 = sigs.get("ema_9", 0); e21 = sigs.get("ema_21", 0); e50 = sigs.get("ema_50", 0)
            if e9 > e21 > e50 > 0: ema_msg = "<b>9>21>50 ✓</b> · Tendencia LONG"
            elif e9 < e21 < e50 and e50 > 0: ema_msg = "<b>9<21<50 ✓</b> · Tendencia SHORT"
            else: ema_msg = "<b>Entrelazadas</b> · Sin tendencia clara"
            rp.append(_slider_bar("EMA", 30, ema_sc, ema_msg))
            rsi_d = dets.get("rsi", {}); rsi_sc2 = rsi_d.get("score", 50)
            rsi_msg = f"<b>RSI: {rsi:.0f}</b>"
            rp.append(_slider_bar("RSI", 20, rsi_sc2, rsi_msg))
            macd_d = dets.get("macd", {}); macd_sc = macd_d.get("score", 50)
            macd_h = sigs.get("macd_histogram", 0)
            rp.append(_slider_bar("MACD", 25, macd_sc, f"<b>H: {macd_h:+.4f}</b>"))
            bb_d = dets.get("bb", {}); bb_sc = bb_d.get("score", 50)
            bb_pct = sigs.get("bb_pct", 0.5)
            rp.append(_slider_bar("BB", 15, bb_sc, f"<b>BB: {bb_pct:.0%}</b>"))
            pa_d = dets.get("pa", {}); pa_sc = pa_d.get("score", 50)
            rp.append(_slider_bar("PA", 10, pa_sc, "Price Action"))
            card = (f"<div style='text-align:center;background:#1a1d23;padding:2px 2px;border-radius:5px;'>"
                    f"<div style='font-size:10px;color:#888;line-height:1.1;'>{tf} ({tf_w.get(tf,'')})</div>"
                    f"<div style='font-size:22px;color:{clr};font-weight:bold;line-height:1.1;'>{em} {sc}</div>"
                    f"<div style='font-size:11px;color:{clr};font-weight:bold;line-height:1.1;'>{action}</div>"
                    f"<div style='font-size:11px;color:{rc};margin-top:1px;border-top:1px solid #333;padding-top:1px;line-height:1.2;'>"
                    f"RSI: <b>{rsi:.0f}</b> {rt}</div></div>")
            with tf_cols[col_idx]:
                st.markdown(tt(card, f"{tf_roles[tf]} — {tf} ({tf_w.get(tf,'')})", "".join(rp), "down"), unsafe_allow_html=True)

# ── COL 4: Reserved space (correlation table removed) ──
with col_corr:
    st.markdown(
        "<div style='min-height:300px;background:#0e1117;'>&nbsp;</div>",
        unsafe_allow_html=True)

# ── COL 2: Macro Votes (merged: + ✅/⚠️ + HOY% from corr, - slider, fixed order) ──
_FIXED_ORDER = ["copper", "dxy", "wti", "sp500", "usdmxn", "usdbrl", "audusd", "usdcnh"]
with col_macro:
    _hdr_votes = _macro_result.get("votes", {})
    corr_data_m = comp["correlation"].get("details", {}).get("correlations", {})
    if _hdr_votes:
        _hdr_vote_rows = ""
        for _hvk in _FIXED_ORDER:
            _hvv = _hdr_votes.get(_hvk)
            if not _hvv:
                continue
            _hv_name = CN.get(_hvk, _hvk)
            _hv_ret = _hvv["return_bps"]
            _hv_wv = _hvv["weighted_vote"]
            _hv_warm = _hvv["warmup"]
            if _hv_wv > 0.05: _hv_clr = "#52b788"; _hv_dir = "LONG"
            elif _hv_wv < -0.05: _hv_clr = "#ef476f"; _hv_dir = "SHORT"
            else: _hv_clr = "#555"; _hv_dir = "—"
            _hw_tag = " <span style='color:#ff6b6b;font-size:8px;'>⏳</span>" if _hv_warm else ""
            _is_cu = _hv_name == "Cu"
            _name_style = "color:#fff;font-weight:bold;font-size:13px;" if _is_cu else "color:#ccc;font-size:12px;"
            _row_border = "border-left:2px solid #ffd166;" if _is_cu else ""
            # ✅/⚠️/🔴 from correlation data
            _e_act_m = corr_data_m.get(_hvk)
            if _e_act_m is not None and not (isinstance(_e_act_m, float) and np.isnan(_e_act_m)):
                _e_exp_m = EXPECTED_CORRELATIONS.get(_hvk, 0)
                _e_df_m = abs(_e_act_m - _e_exp_m)
                _status_ic = "✅" if _e_df_m < 0.2 else ("⚠️" if _e_df_m < 0.4 else "🔴")
            else:
                _status_ic = "—"
            # HOY% from M1 rolling correlation
            _hoy_v = _cross_corr_hoy.get(_hvk, -1)
            if _hoy_v < 0:
                _hoy_html = "<span style='color:#555;font-size:10px;'>--</span>"
            else:
                _hoy_clr = "#52b788" if _hoy_v >= 65 else ("#ffd166" if _hoy_v >= 40 else "#ef476f")
                _hoy_html = f"<span style='color:{_hoy_clr};font-size:11px;font-weight:bold;'>{_hoy_v}%</span>"
            _hdr_vote_rows += (
                f"<tr style='border-bottom:1px solid #1a1d23;{_row_border}'>"
                f"<td style='padding:3px 3px;{_name_style}'>{_hv_name}{_hw_tag}</td>"
                f"<td style='padding:3px 3px;text-align:right;color:{'#52b788' if _hv_ret > 0 else '#ef476f' if _hv_ret < 0 else '#555'};font-size:12px;'>"
                f"{_hv_ret:+.1f}</td>"
                f"<td style='padding:3px 3px;text-align:center;color:{_hv_clr};font-weight:bold;font-size:12px;'>{_hv_dir}</td>"
                f"<td style='padding:3px 2px;text-align:center;'>{_status_ic}</td>"
                f"<td style='padding:3px 3px;text-align:center;'>{_hoy_html}</td>"
                f"</tr>")
        _hm_clr = "#52b788" if _macro_score >= 65 else ("#ffd166" if _macro_score >= 50 else "#ef476f")
        _hdr_macro_tbl = (
            f"<div class='macro-votes-wrap'>"
            f"<table style='width:100%;font-size:12px;font-family:monospace;"
            f"border-collapse:collapse;line-height:1.5;'>"
            f"{_hdr_vote_rows}</table>"
            f"<div style='text-align:center;margin-top:auto;padding:2px;"
            f"border-top:1px solid #333;font-size:13px;'>"
            f"<span style='color:{_hm_clr};font-weight:bold;'>Macro: {_macro_score:.0f}</span>"
            f" <span style='color:{_hm_clr};font-size:11px;'>{_macro_dir}</span></div>"
            f"</div>")
        st.markdown(tt(_hdr_macro_tbl, "🌍 Votos Macro por Activo",
            f"Consenso: <b>{_macro_result['consensus_raw']:+.4f}</b><br>"
            f"Confianza promedio: <b>{_macro_result['confidence_avg']:.0%}</b>",
        "down"), unsafe_allow_html=True)
    else:
            st.caption("⏳ Macro...")

# ══════════════════════════════════════════════════════════
# AUTO-REFRESH
# ══════════════════════════════════════════════════════════
if auto_refresh:
    time.sleep(DASHBOARD_REFRESH_SECONDS)
    st.rerun()
