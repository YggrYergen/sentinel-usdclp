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
    SCORE_STRONG_THRESHOLD, DASHBOARD_REFRESH_SECONDS, EXPECTED_CORRELATIONS,
    LOG_TICKS, LOG_SNAPSHOTS, LOGS_DIR)
from sentinel.data_feed import DataFeed
from sentinel.sentinel_core import SentinelCore
from sentinel.version import VERSION, CODENAME

if LOG_TICKS:
    from sentinel.logging.tick_logger import TickLogger

    @st.cache_resource
    def _init_tick_logger():
        return TickLogger(SYMBOLS["target"], LOGS_DIR)

if LOG_SNAPSHOTS:
    from sentinel.logging.snapshot_logger import SnapshotLogger

    @st.cache_resource
    def _init_snapshot_logger():
        # config_hash: P1's InstrumentConfig hashing is not wired yet —
        # "unversioned" is a placeholder until P1 lands (see task 0.7 report).
        return SnapshotLogger(LOGS_DIR, "unversioned", symbol=SYMBOLS["target"])

try:
    st.set_page_config(page_title=f"SENTINEL v{VERSION} — USD/CLP", page_icon="🛡️",
                       layout="wide", initial_sidebar_state="collapsed")
except st.errors.StreamlitAPIException:
    pass  # Already set by app.py when running in multipage mode

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
    /* Reduce default Streamlit vertical gaps in signal column */
    section.main div[data-testid="stColumn"]:first-child div[data-testid="stMarkdownContainer"] {
        margin-bottom: -12px;
    }
    section.main div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="stColumn"] > div {
        height: 100%; display: flex; flex-direction: column; justify-content: flex-start;
    }
    .macro-votes-wrap { display: flex; flex-direction: column; justify-content: space-between; }
    .macro-votes-wrap table { flex: 1; }
    /* Hide Streamlit toolbar (Deploy, menu, etc.) */
    .stApp > header { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    div[data-testid="stToolbar"] { display: none !important; }
    div[data-testid="stDecoration"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    div[data-testid="stStatusWidget"] { display: none !important; }
    .stApp [data-testid="stAppViewContainer"] {
        transition: none !important;
    }
    /* Prevent the white flash during rerun */
    .stApp iframe { display: none !important; }
    .stApp [data-testid="stAppViewBlockContainer"] {
        animation: fadeIn 0.15s ease-in;
    }
    @keyframes fadeIn {
        from { opacity: 0.85; }
        to { opacity: 1; }
    }
    /* Ensure tooltips always on top */
    .tt-wrap { z-index: 100; position: relative; }
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
if LOG_TICKS and price_info.get("time") and price_info.get("bid", 0) > 0:
    _init_tick_logger().on_tick(price_info["time"], price_info["bid"], price_info["ask"])
if LOG_SNAPSHOTS:
    _init_snapshot_logger().log(result)
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

# Fetch USDCLP M1 data for rolling correlation (30 bars = 30 min)
_target_m1_closes = None
try:
    _target_m1 = feed.get_data(SYMBOLS["target"], timeframe_minutes=1, bars=30)
    if _target_m1 is not None and len(_target_m1) >= 10:
        _target_m1_closes = _target_m1['close'].values
except Exception:
    pass
_cross_corr_hoy = {}  # key -> confidence 0-100

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
            _ca_m1_data = feed.get_data(_ca_symbol, timeframe_minutes=1, bars=30)
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
                # Rolling M1 correlation for HOY column
                if _target_m1_closes is not None:
                    _min_len = min(len(_target_m1_closes), len(_cls))
                    if _min_len >= 10:
                        _t_ret = np.diff(np.log(_target_m1_closes[-_min_len:]))
                        _a_ret = np.diff(np.log(_cls[-_min_len:]))
                        _rcorr = np.corrcoef(_t_ret, _a_ret)[0, 1]
                        if np.isfinite(_rcorr):
                            _exp_s = np.sign(EXPECTED_CORRELATIONS.get(_cak, 0))
                            # directed_corr: positive = behaving as expected
                            _dir_c = _rcorr * _exp_s
                            # Scale to 0-100%: [-0.5,+0.5] -> [0%,100%]
                            _hoy_pct = min(100, max(0, (_dir_c + 0.5) * 100))
                            _cross_corr_hoy[_cak] = round(_hoy_pct)
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
# PRE-CALC: MacroScorer (needed for header macro votes column)
# ══════════════════════════════════════════════════════════
if not hasattr(core, 'macro_scorer'):
    from sentinel.macro_scorer import MacroScorer
    core.macro_scorer = MacroScorer()
_ms = core.macro_scorer
_macro_result = comp.get("_macro", _ms.calculate_score(feed))
_macro_score = _macro_result["score"]
_macro_dir = _macro_result["direction"]

# ══════════════════════════════════════════════════════════
# HEADER — 5 columnas en 1 fila
# ══════════════════════════════════════════════════════════
col_score, col_macro, col_tf, col_corr, col_levels = st.columns([0.55, 1.1, 1.6, 1.0, 0.65])

with col_score:
    # Signal panel (compact, same width as score)
    _tf_sc = tech_details.get("tf_scores", {})
    _sc_map = {t: _tf_sc.get(t, {}).get("score", 50) for t in ("M1","M2","M5","M15")}
    _dir_map = {t: _tf_sc.get(t, {}).get("direction", "NEUTRAL") for t in ("M1","M2","M5","M15")}
    _sig_defs = [("⚡","5s",{"M1":1.0}),("🔄","30s",{"M1":0.6,"M2":0.4}),("📊","1m",{"M1":0.4,"M2":0.3,"M5":0.3}),("📈","5m",{"M5":0.6,"M15":0.4})]
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
        _cells += (f"<td style='background:{_bg};padding:2px 4px;text-align:center;"
                   f"border-right:1px solid #333;width:25%;'>"
                   f"<div style='font-size:9px;color:#888;line-height:1;'>{_ic} {_sp}</div>"
                   f"<div style='font-size:15px;color:{_tc};font-weight:900;line-height:1;'>{_ar}</div>"
                   f"<div style='font-size:9px;color:{_tc};font-weight:bold;line-height:1.1;'>{_ac}</div>"
                   f"<div style='font-size:12px;color:#fff;font-weight:bold;line-height:1.1;'>{_cv:.0f}%</div>"
                   f"{_ept}</td>")
        _det = " + ".join(f"{t}({_sc_map.get(t,50):.0f})" for t in _wt)
        _ttp.append(f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
                    f"border-radius:5px;padding:4px 7px;margin:3px 0;'>"
                    f"<b>{_ic} {_sp}</b> — <span style='color:{_tc};'><b>{_ac} {_cv:.0f}%</b></span><br>"
                    f"<span style='color:#888;'>Blend: {_det} = {_bl:.1f}</span></div>")
    _sig_html = (f"<div style='background:#1a1d23;border-radius:8px;overflow:hidden;'>"
                 f"<table style='width:100%;border-collapse:collapse;'><tr>{_cells}</tr></table></div>")
    st.markdown(tt(_sig_html, "🎯 Panel de Señales",
        f"{''.join(_ttp)}<br>⚡=M1 | 🔄=M1+M2 | 📊=M1+M2+M5 | 📈=M5+M15",
        "down"), unsafe_allow_html=True)

    # ── Derivative-enhanced signals (v2) ──
    # Price buffer in session_state
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
    velocity = 0.0; acceleration = 0.0; vel_short = 0.0; vel_medium = 0.0; vel_long = 0.0; vel_5m = 0.0
    acc_short = 0.0; acc_medium = 0.0; acc_long = 0.0; acc_5m = 0.0
    if n_ticks >= 2:
        dt = ts_buf[-1] - ts_buf[-2]
        if dt > 0: vel_short = (buf[-1] - buf[-2]) / dt
    # Per-window acceleration helper
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
        acceleration = acc_short  # backward compat
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

    def vel_to_boost(v, scale=0.05):
        return max(-25, min(25, (v / scale) * 25))
    def accel_to_boost(a, scale=0.01):
        return max(-10, min(10, (a / scale) * 10))

    _tf_sc2 = tech_details.get("tf_scores", {})
    _m1_sc2 = _tf_sc2.get("M1", {}).get("score", 50)
    _m2_sc2 = _tf_sc2.get("M2", {}).get("score", 50)
    _m5_sc2 = _tf_sc2.get("M5", {}).get("score", 50)
    _m15_sc2 = _tf_sc2.get("M15", {}).get("score", 50)
    v2_defs = [
        ("⚡", "5s", _m1_sc2, vel_short, acc_short, 0.50, 0.30),
        ("🔄", "30s", _m1_sc2 * 0.6 + _m2_sc2 * 0.4, vel_medium, acc_medium, 0.30, 0.15),
        ("📊", "1m", _m1_sc2 * 0.4 + _m2_sc2 * 0.3 + _m5_sc2 * 0.3, vel_long, acc_long, 0.15, 0.05),
        ("📈", "5m", _m5_sc2 * 0.6 + _m15_sc2 * 0.4, vel_5m, acc_5m, 0.10, 0.03),
    ]
    v2_cells = ""; v2_ttp = []
    for _ic, _sp, _base, _vel, _acc, _vw, _aw in v2_defs:
        v_boost = vel_to_boost(_vel); a_boost = accel_to_boost(_acc)
        enhanced = max(0, min(100, _base + (v_boost * _vw * 2) + (a_boost * _aw * 2)))
        _sd2 = "LONG" if enhanced >= 55 else ("SHORT" if enhanced <= 45 else "NEUTRAL")
        _cv2 = min(100, abs(enhanced - 50) * 2)
        if _sd2 == "LONG": _r,_g,_b = 82,183,136; _ar="▲"; _ac="COMPRAR"; _ep2=price_info.get("ask",0)
        elif _sd2 == "SHORT": _r,_g,_b = 239,71,111; _ar="▼"; _ac="VENDER"; _ep2=price_info.get("bid",0)
        else: _r,_g,_b = 255,209,102; _ar="◆"; _ac="ESPERAR"; _ep2=0
        _op2 = 0.10+(_cv2/100)*0.45
        _tc2 = f"rgb({_r},{_g},{_b})"; _bg2 = f"rgba({_r},{_g},{_b},{_op2:.2f})"
        if _acc > 0.002: acc_icon = "⏫"
        elif _acc > 0: acc_icon = "🔼"
        elif _acc > -0.002: acc_icon = "🔽"
        else: acc_icon = "⏬"
        v2_cells += (f"<td style='background:{_bg2};padding:2px 4px;text-align:center;"
                     f"border-right:1px solid #333;width:25%;'>"
                     f"<div style='font-size:9px;color:#888;line-height:1;'>{_ic} {_sp} {acc_icon}</div>"
                     f"<div style='font-size:15px;color:{_tc2};font-weight:900;line-height:1;'>{_ar}</div>"
                     f"<div style='font-size:9px;color:{_tc2};font-weight:bold;line-height:1.1;'>{_ac}</div>"
                     f"<div style='font-size:12px;color:#fff;font-weight:bold;line-height:1.1;'>{_cv2:.0f}%</div>"
                     f"</td>")
        v_dir = "↑" if _vel > 0 else ("↓" if _vel < 0 else "→")
        a_dir = "acelerando" if _acc > 0.001 else ("frenando" if _acc < -0.001 else "estable")
        v2_ttp.append(
            f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
            f"border-radius:5px;padding:4px 7px;margin:3px 0;'>"
            f"<b>{_ic} {_sp}</b> — <span style='color:{_tc2};'><b>{_ac} {_cv2:.0f}%</b></span><br>"
            f"Base: {_base:.1f} + Vel({v_boost:+.1f}×{_vw}) + Acc({a_boost:+.1f}×{_aw}) = <b>{enhanced:.1f}</b><br>"
            f"<span style='color:#888;'>Velocidad: {_vel:+.4f}/s {v_dir} | {a_dir}</span></div>")
    v2_html = (f"<div style='background:#1a1d23;border-radius:8px;overflow:hidden;margin-top:3px;'>"
               f"<table style='width:100%;border-collapse:collapse;'><tr>{v2_cells}</tr></table></div>")
    # Momentum bar
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

    if score >= 75:
        sr = f"🟢 <b>FUERTE ({score})</b><br>Téc({tech_sc:.0f})+Macro({corr_sc:.0f}) confluyen → {direction}."
    elif score >= 65:
        sr = f"🟡 <b>ALERTA ({score})</b><br>Téc={tech_sc:.0f}, Macro={corr_sc:.0f}. Buscar confirmación."
    else:
        sr = f"🔴 <b>ESPERAR ({score})</b><br>Téc={tech_sc:.0f}, Macro={corr_sc:.0f}. Sin consenso."
    d = direction
    if tech_dir == corr_dir and tech_dir != "NEUTRAL":
        dr = f"✅ Consenso → {tech_dir}."
    elif tech_dir != corr_dir and "NEUTRAL" not in (tech_dir, corr_dir):
        dr = f"⚠️ Téc={tech_dir} vs Macro={corr_dir}."
    elif corr_dir != "NEUTRAL":
        dr = f"Macro → {corr_dir}. Téc neutral."
    elif tech_dir != "NEUTRAL":
        dr = f"Téc → {tech_dir}. Sin respaldo Macro."
    else:
        dr = "Ambos neutrales — fuera."
    st.markdown(tt(
        f"<div style='display:flex;align-items:center;justify-content:center;gap:6px;padding:4px 0;'>"
        f"<span style='background:{dir_color[d]}22;border:1px solid {dir_color[d]};border-radius:4px;"
        f"padding:1px 6px;font-size:16px;font-weight:900;color:{dir_color[d]};line-height:1.3;'>{score}</span>"
        f"<span style='font-size:22px;'>{dir_emoji[d]}</span>"
        f"<span style='color:{dir_color[d]};font-size:18px;font-weight:bold;'>{d}</span>"
        f"<span style='font-size:11px;color:#888;'>{result['signal']}</span></div>",
        "📊 Score + Dirección",
        f"{sr}<br><br><b>Fórmula:</b> {tech_sc:.0f}×0.50 + {corr_sc:.0f}×0.50 = <b>{score}</b>"
        f"<br><br>{dr}<br><br>Téc: <b>{tech_dir}</b> (50%) | Macro: <b>{corr_dir}</b> (50%)",
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

        _sprd = price_info.get('spread', 0) if price_info else 0
        _src = 'MT5' if price_info.get('source')=='mt5' else 'Yahoo'
        st.markdown(tt(
            f"<div style='display:flex;justify-content:space-between;align-items:center;padding:3px 6px;"
            f"font-family:monospace;background:rgba(76,201,240,0.12);border:1px solid #4cc9f0;"
            f"border-radius:3px;margin:1px 0;line-height:1.3;'>"
            f"<span style='color:#4cc9f0;font-size:11px;font-weight:bold;'>USDCLP</span>"
            f"<span style='font-size:18px;font-weight:bold;color:#4cc9f0;'>{curr_price:.2f}</span>"
            f"<span style='color:#4cc9f0;font-size:11px;'>±{_sprd:.1f}</span></div>",
            "💲 Precio en Vivo",
            f"Bid: {price_info['bid']:.2f} | Ask: {price_info['ask']:.2f} | Spread: {_sprd:.2f}<br>"
            f"Fuente: <b>{_src}</b>",
            "down"), unsafe_allow_html=True)
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
        tf_w = {"M1": "35%", "M2": "35%", "M5": "20%", "M15": "10%"}
        tf_roles = {"M1": "Ejecución", "M2": "Confirmación", "M5": "Tendencia", "M15": "Contexto"}
        for col_idx, tf in enumerate(active_tfs):
            r = tf_scores[tf]
            sc = r.get("score", 50); dr3 = r.get("direction", "NEUTRAL")
            sigs = r.get("signals", {})
            dets = r.get("details", {})
            rsi = sigs.get("rsi", 0)
            # Color gradient based on score intensity (distance from 50)
            _intensity = min(1.0, abs(sc - 50) / 40)  # 0.0 at 50, 1.0 at 90+
            if sc >= 50:
                # Green gradient: gray(136,136,136) → green(82,183,136)
                _cr = int(136 - (136 - 82) * _intensity)
                _cg = int(136 + (183 - 136) * _intensity)
                _cb = int(136 + (136 - 136) * _intensity)
            else:
                # Red gradient: gray(136,136,136) → red(239,71,111)
                _cr = int(136 + (239 - 136) * _intensity)
                _cg = int(136 - (136 - 71) * _intensity)
                _cb = int(136 - (136 - 111) * _intensity)
            clr = f"rgb({_cr},{_cg},{_cb})"
            em = "🟢" if sc >= 65 else ("🟡" if sc >= 50 else "🔴")
            rc = "#ef476f" if rsi >= 70 else ("#52b788" if rsi <= 30 else "#aaa")
            rt = "OB" if rsi >= 70 else ("OS" if rsi <= 30 else "")
            rp = []
            # Direction-based action labels (traders requested COMPRAR/VENDER/ESPERAR)
            if dr3 == "LONG":
                action = "📈 COMPRAR"
                rp.append(f"✅ <b>Señal COMPRAR</b> ({sc}/100). Indicadores al alza.")
            elif dr3 == "SHORT":
                action = "📉 VENDER"
                rp.append(f"✅ <b>Señal VENDER</b> ({sc}/100). Indicadores a la baja.")
            else:
                action = "🟡 ESPERAR"
                rp.append(f"🟡 <b>Sin dirección clara</b> ({sc}/100). Esperar confirmación.")
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
                ema_raw = "9>21>50 ✓"
                ema_msg = f"<b>{ema_raw}</b> · Tendencia LONG establecida — EMAs alineadas al alza"
            elif e9 < e21 < e50 and e50 > 0:
                ema_raw = "9<21<50 ✓"
                ema_msg = f"<b>{ema_raw}</b> · Tendencia SHORT establecida — EMAs alineadas a la baja"
            elif e9 > e21 and e21 < e50 and e50 > 0:
                ema_raw = "9>21, 21<50"
                ema_msg = f"<b>{ema_raw}</b> · Posible giro alcista — EMA 9 cruzó sobre 21"
            elif e9 < e21 and e21 > e50 and e50 > 0:
                ema_raw = "9<21, 21>50"
                ema_msg = f"<b>{ema_raw}</b> · Posible giro bajista — EMA 9 cruzó bajo 21"
            else:
                ema_raw = "Entrelazadas"
                ema_msg = f"<b>{ema_raw}</b> · Sin tendencia clara — mercado lateral"
            if ema_cross == 1:
                ema_msg += " — <b>¡Cruce alcista!</b>"
            elif ema_cross == -1:
                ema_msg += " — <b>¡Cruce bajista!</b>"
            rp.append(_slider_bar("EMA", 30, ema_sc, ema_msg))

            # ── RSI slider ──
            rsi_d = dets.get("rsi", {}); rsi_sc2 = rsi_d.get("score", 50)
            if rsi >= 70:
                rsi_msg = f"<b>RSI: {rsi:.0f}</b> · Sobrecompra — agotamiento probable, NO entrar LONG"
            elif rsi >= 55:
                rsi_msg = f"<b>RSI: {rsi:.0f}</b> · Momentum alcista — presión compradora activa"
            elif rsi >= 45:
                rsi_msg = f"<b>RSI: {rsi:.0f}</b> · Zona neutral — sin presión dominante, esperar"
            elif rsi >= 30:
                rsi_msg = f"<b>RSI: {rsi:.0f}</b> · Momentum bajista — presión vendedora activa"
            else:
                rsi_msg = f"<b>RSI: {rsi:.0f}</b> · Sobreventa — rebote probable, buscar LONG"
            rp.append(_slider_bar("RSI", 20, rsi_sc2, rsi_msg))

            # ── MACD slider ──
            macd_d = dets.get("macd", {}); macd_sc = macd_d.get("score", 50)
            macd_h = sigs.get("macd_histogram", 0)
            if macd_h > 0.005:
                macd_msg = f"<b>H: {macd_h:+.4f}</b> · Impulso alcista fuerte — compradores dominan"
            elif macd_h > 0.001:
                macd_msg = f"<b>H: {macd_h:+.4f}</b> · Alcista moderado — tendencia al alza presente"
            elif macd_h > -0.001:
                macd_msg = f"<b>H: {macd_h:+.4f}</b> · Transición — posible cambio de dirección"
            elif macd_h > -0.005:
                macd_msg = f"<b>H: {macd_h:+.4f}</b> · Bajista moderado — presión vendedora activa"
            else:
                macd_msg = f"<b>H: {macd_h:+.4f}</b> · Impulso bajista fuerte — vendedores dominan"
            rp.append(_slider_bar("MACD", 25, macd_sc, macd_msg))

            # ── BB slider ──
            bb_d = dets.get("bb", {}); bb_sc = bb_d.get("score", 50)
            bb_pct = sigs.get("bb_pct", 0.5)
            if bb_pct > 0.95:
                bb_msg = f"<b>BB: {bb_pct:.0%}</b> · Banda superior — extremo alto, retroceso probable"
            elif bb_pct > 0.65:
                bb_msg = f"<b>BB: {bb_pct:.0%}</b> · Mitad superior — sesgo alcista, zona de precaución"
            elif bb_pct > 0.35:
                bb_msg = f"<b>BB: {bb_pct:.0%}</b> · Centro — precio en equilibrio, sin presión extrema"
            elif bb_pct > 0.05:
                bb_msg = f"<b>BB: {bb_pct:.0%}</b> · Mitad inferior — sesgo bajista, posible rebote"
            else:
                bb_msg = f"<b>BB: {bb_pct:.0%}</b> · Banda inferior — extremo bajo, rebote probable"
            rp.append(_slider_bar("BB", 15, bb_sc, bb_msg))

            # ── PA slider ──
            pa_d = dets.get("pa", {}); pa_sc = pa_d.get("score", 50)
            _last_body = abs(sigs.get("price", 0) - sigs.get("ema_9", 0))  # approx
            if pa_sc >= 70:
                pa_msg = "<b>Vela alcista fuerte</b> · Cuerpo grande, compradores dominan"
            elif pa_sc >= 55:
                pa_msg = "<b>Vela alcista moderada</b> · Compra presente pero sin convicción total"
            elif pa_sc >= 45:
                pa_msg = "<b>Vela indecisa</b> · Doji/mecha — mercado sin definición"
            elif pa_sc >= 30:
                pa_msg = "<b>Vela bajista moderada</b> · Venta presente pero sin fuerza"
            else:
                pa_msg = "<b>Vela bajista fuerte</b> · Cuerpo grande, vendedores dominan"
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
        # Sort by abs(actual - expected) ascending — most reliable/predictive on top
        _sorted_keys = sorted(
            [k for k in _cross_asset_keys if corr_data.get(k) is not None
             and not (isinstance(corr_data.get(k), float) and np.isnan(corr_data.get(k)))],
            key=lambda k: abs(corr_data.get(k, 0) - EXPECTED_CORRELATIONS.get(k, 0))
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

            # HOY column: M1 rolling correlation confidence %
            _hoy_v = _cross_corr_hoy.get(_ek, -1)
            if _hoy_v < 0:
                _cc_html = f"<td style='padding:1px 3px;text-align:center;color:#555;font-size:10px;'>--</td>"
            else:
                _ccclr = "#52b788" if _hoy_v >= 65 else ("#ffd166" if _hoy_v >= 40 else "#ef476f")
                _cc_html = f"<td style='padding:1px 3px;text-align:center;color:{_ccclr};font-size:11px;font-weight:bold;'>{_hoy_v}%</td>"
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
                f"{_cc_html}"
                f"</tr>"
            )

        tbl = (f"<div class='corr-table-wrap'>"
               f"<table style='width:100%;font-size:12px;font-family:monospace;"
               f"border-collapse:collapse;line-height:1.5;'>"
               f"{_hdr_rows}</table>"
               f"<div style='text-align:center;margin-top:3px;padding:2px;"
               f"border-top:1px solid #333;font-size:13px;'>"
               f"<span style='color:{cc};font-weight:bold;'>Corr: {cs}</span>"
               f" <span style='color:{cc};font-size:11px;'>{cd}</span></div>"
               f"</div>")
        st.markdown(tt(tbl, "🔗 Correlaciones Cross-Asset",
            corr_rec,
            "down"), unsafe_allow_html=True)

# ── COL 5: Macro Votes (copy of experimental breakdown) ──
with col_macro:
    _hdr_votes = _macro_result.get("votes", {})
    if _hdr_votes:
        _hdr_vote_rows = ""
        for _hvk, _hvv in sorted(_hdr_votes.items(), key=lambda x: abs(x[1]["weighted_vote"]), reverse=True):
            _hv_name = CN.get(_hvk, _hvk)
            _hv_ret = _hvv["return_bps"]
            _hv_wv = _hvv["weighted_vote"]
            _hv_conf = _hvv["confidence"]
            _hv_warm = _hvv["warmup"]
            if _hv_wv > 0.05: _hv_clr = "#52b788"; _hv_dir = "LONG"
            elif _hv_wv < -0.05: _hv_clr = "#ef476f"; _hv_dir = "SHORT"
            else: _hv_clr = "#555"; _hv_dir = "—"
            _hc_clr = "#52b788" if _hv_conf >= 0.6 else ("#ffd166" if _hv_conf >= 0.3 else "#ef476f")
            _hc_pct = _hv_conf * 100
            _hw_tag = " <span style='color:#ff6b6b;font-size:8px;'>⏳</span>" if _hv_warm else ""
            _is_cu = _hv_name == "Cu"
            _name_style = "color:#fff;font-weight:bold;font-size:13px;" if _is_cu else "color:#ccc;font-size:12px;"
            _row_border = "border-left:2px solid #ffd166;" if _is_cu else ""
            # Smooth gradient color for confidence bar: red(0%) → yellow(50%) → green(100%)
            _cf = max(0, min(1, _hv_conf))
            if _cf >= 0.5:
                _t = (_cf - 0.5) * 2  # 0→1 for yellow→green
                _bar_r = int(255 * (1 - _t) + 82 * _t)
                _bar_g = int(209 * (1 - _t) + 183 * _t)
                _bar_b = int(102 * (1 - _t) + 136 * _t)
            else:
                _t = _cf * 2  # 0→1 for red→yellow
                _bar_r = int(239 * (1 - _t) + 255 * _t)
                _bar_g = int(71 * (1 - _t) + 209 * _t)
                _bar_b = int(111 * (1 - _t) + 102 * _t)
            _bar_clr = f"rgb({_bar_r},{_bar_g},{_bar_b})"
            _hdr_vote_rows += (
                f"<tr style='border-bottom:1px solid #1a1d23;{_row_border}'>"
                f"<td title='Activo cross-asset: {_hv_name}. Correlación con USDCLP usada para ponderar su voto.' style='padding:3px 3px;{_name_style}'>{_hv_name}{_hw_tag}</td>"
                f"<td title='Δ3min: {_hv_ret:+.1f} bps. Retorno reciente del activo. Positivo = subió, Negativo = bajó.' style='padding:3px 3px;text-align:right;color:{'#52b788' if _hv_ret > 0 else '#ef476f' if _hv_ret < 0 else '#555'};font-size:12px;'>"
                f"{_hv_ret:+.1f}</td>"
                f"<td title='Dirección: {_hv_dir}. Basada en el retorno reciente del activo y su correlación con USDCLP.' style='padding:3px 3px;text-align:center;color:{_hv_clr};font-weight:bold;font-size:12px;'>{_hv_dir}</td>"
                f"<td title='Confianza EWMA: {_hv_conf:.0%}.' style='padding:3px 3px;text-align:center;white-space:nowrap;'>"
                f"<div style='display:inline-flex;align-items:center;gap:3px;'>"
                f"<div style='background:#2a2d35;border-radius:2px;height:4px;width:32px;display:inline-block;overflow:hidden;'>"
                f"<div style='background:{_bar_clr};height:100%;width:{_hc_pct:.0f}%;transition:width 1.5s;'></div></div>"
                f"<span style='color:{_bar_clr};font-size:10px;'>{_hc_pct:.0f}%</span></div></td>"
                f"</tr>"
            )
        # Macro direction color
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
            f"</div>"
        )
        st.markdown(tt(_hdr_macro_tbl, "🌍 Votos Macro por Activo",
            f"Consenso: <b>{_macro_result['consensus_raw']:+.4f}</b><br>"
            f"Confianza promedio: <b>{_macro_result['confidence_avg']:.0%}</b><br><br>"
            f"Cada activo vota LONG/SHORT según su retorno reciente,<br>"
            f"ponderado por confianza EWMA de correlación histórica.",
            "down"), unsafe_allow_html=True)
    else:
        st.caption("⏳ Macro...")

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
# EXPERIMENTAL v4.0 — Triple Signal System
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("""<div style='text-align:center;padding:4px 0;'>
<span style='background:linear-gradient(90deg,#4cc9f033,#4cc9f000);padding:4px 16px;
border-radius:4px;color:#4cc9f0;font-size:13px;font-weight:bold;
border:1px solid #4cc9f044;'>🧪 EXPERIMENTAL v4.0 — Triple Signal System</span></div>""",
unsafe_allow_html=True)

# MacroScorer already initialized and calculated in pre-calc section above
# _ms, _macro_result, _macro_score, _macro_dir are already available

# Technical score (already calculated above)
_tech_score_v4 = tech_sc  # from production calc
_tech_dir_v4 = tech_dir

# Fusion
_fusion = _ms.calculate_fusion(_tech_score_v4, _tech_dir_v4, _macro_score, _macro_dir)

# ── Triple Signal Cards ──
_exp_c1, _exp_c2, _exp_c3 = st.columns(3)

def _signal_card(label, icon, score, direction, detail_text=""):
    """Generate a signal card HTML."""
    if direction == "LONG":
        clr = "#52b788"; arrow = "▲"; action = "COMPRAR"
    elif direction == "SHORT":
        clr = "#ef476f"; arrow = "▼"; action = "VENDER"
    else:
        clr = "#ffd166"; arrow = "◆"; action = "ESPERAR"
    
    # Confidence bar
    bar_pct = abs(score - 50) * 2  # 0-100 based on distance from neutral
    bar_side = "left" if score >= 50 else "right"
    
    card = (
        f"<div style='background:#1a1d23;border-radius:10px;padding:10px 8px;"
        f"border:1px solid {clr}33;text-align:center;'>"
        f"<div style='font-size:11px;color:#888;margin-bottom:2px;'>{icon} {label}</div>"
        f"<div style='font-size:28px;color:{clr};font-weight:900;line-height:1.2;'>{arrow}</div>"
        f"<div style='font-size:20px;color:{clr};font-weight:bold;'>{score:.0f}</div>"
        f"<div style='font-size:12px;color:{clr};font-weight:bold;margin:2px 0;'>{action}</div>"
        f"<div style='background:#2a2d35;border-radius:3px;height:5px;width:100%;overflow:hidden;"
        f"margin-top:4px;'>"
        f"<div style='background:{clr};height:100%;width:{bar_pct:.0f}%;border-radius:3px;"
        f"float:{bar_side};transition:width 0.5s;'></div></div>"
        f"<div style='font-size:9px;color:#555;margin-top:3px;'>{detail_text}</div>"
        f"</div>"
    )
    return card

with _exp_c1:
    _t_detail = f"EMA+RSI+MACD+BB×4TF"
    st.markdown(_signal_card("TÉCNICO", "🔧", _tech_score_v4, _tech_dir_v4, _t_detail),
                unsafe_allow_html=True)

with _exp_c2:
    _warmed = _macro_result["assets_warmed_up"]
    _total = _macro_result["total_assets_tracked"]
    _conf_avg = _macro_result["confidence_avg"]
    _m_detail = f"{_warmed}/{_total} activos | conf {_conf_avg:.0%}"
    st.markdown(_signal_card("MACRO", "🌍", _macro_score, _macro_dir, _m_detail),
                unsafe_allow_html=True)

with _exp_c3:
    _f_detail = f"Confl: {_fusion['confluence_pct']:.0f}% | {_fusion['risk_emoji']} {_fusion['risk_mode']}"
    st.markdown(_signal_card("FUSIÓN", "⚡", _fusion["score"], _fusion["direction"], _f_detail),
                unsafe_allow_html=True)

# ── Confluence Meter ──
_conf_pct = _fusion["confluence_pct"]
_conf_clr = "#52b788" if _fusion["aligned"] else ("#ef476f" if _fusion["opposed"] else "#ffd166")
_conf_label = "✅ CONFLUENCIA" if _fusion["aligned"] else ("⚠️ DIVERGENCIA" if _fusion["opposed"] else "➡️ PARCIAL")
_risk = _fusion["risk_mode"]
_sl_m = _fusion["sl_multiplier"]
_tp_m = _fusion["tp_multiplier"]

st.markdown(
    f"<div style='background:#1a1d23;border-radius:8px;padding:8px 12px;margin-top:6px;"
    f"border:1px solid {_conf_clr}33;'>"
    f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;'>"
    f"<span style='color:{_conf_clr};font-weight:bold;font-size:13px;'>"
    f"{_conf_label} {_conf_pct:.0f}%</span>"
    f"<span style='color:#888;font-size:11px;'>"
    f"SL: {_sl_m:.1f}×ATR | TP: {_tp_m:.1f}×ATR | {_fusion['risk_emoji']} {_risk}</span></div>"
    f"<div style='background:#2a2d35;border-radius:4px;height:8px;width:100%;overflow:hidden;'>"
    f"<div style='background:linear-gradient(90deg,{_conf_clr},{_conf_clr}88);height:100%;"
    f"width:{_conf_pct:.0f}%;border-radius:4px;transition:width 0.5s;'></div></div>"
    f"</div>",
    unsafe_allow_html=True
)

# ── Experimental Signal Panel (4 signals: 5s / 30s / 1m / 5m) ──
st.markdown(
    "<div style='text-align:center;margin-top:8px;margin-bottom:4px;'>"
    "<span style='color:#888;font-size:11px;'>📡 Señales Experimentales (4 timeframes)</span></div>",
    unsafe_allow_html=True
)

# Get TF scores for experimental signals
_exp_tf = tech_details.get("tf_scores", {})
_exp_sc = {t: _exp_tf.get(t, {}).get("score", 50) for t in ("M1", "M2", "M5", "M15")}
_exp_dir = {t: _exp_tf.get(t, {}).get("direction", "NEUTRAL") for t in ("M1", "M2", "M5", "M15")}

# V1: Base signals (static TF blends)
_exp_sig_defs = [
    ("⚡", "5s",  {"M1": 1.0}),
    ("🔄", "30s", {"M1": 0.6, "M2": 0.4}),
    ("📊", "1m",  {"M1": 0.4, "M2": 0.3, "M5": 0.3}),
    ("🕐", "5m",  {"M1": 0.2, "M2": 0.2, "M5": 0.35, "M15": 0.25}),
]
_exp_cells_v1 = ""
_exp_ttp_v1 = []
for _eic, _esp, _ewt in _exp_sig_defs:
    _ebl = sum(_exp_sc.get(t, 50) * w for t, w in _ewt.items())
    _evl = sum(w for t, w in _ewt.items() if _exp_dir.get(t) == "LONG")
    _evs = sum(w for t, w in _ewt.items() if _exp_dir.get(t) == "SHORT")
    _esd = "LONG" if _evl > _evs and _evl > 0.3 else ("SHORT" if _evs > _evl and _evs > 0.3 else "NEUTRAL")
    _ecv = min(100, abs(_ebl - 50) * 2)
    if _esd == "LONG":    _er, _eg, _eb = 82, 183, 136; _ear = "▲"; _eac = "COMPRAR"
    elif _esd == "SHORT": _er, _eg, _eb = 239, 71, 111; _ear = "▼"; _eac = "VENDER"
    else:                 _er, _eg, _eb = 255, 209, 102; _ear = "◆"; _eac = "ESPERAR"
    _eop = 0.10 + (_ecv / 100) * 0.45
    _etc = f"rgb({_er},{_eg},{_eb})"; _ebg = f"rgba({_er},{_eg},{_eb},{_eop:.2f})"
    _exp_cells_v1 += (
        f"<td style='background:{_ebg};padding:2px 4px;text-align:center;"
        f"border-right:1px solid #333;width:25%;'>"
        f"<div style='font-size:9px;color:#888;line-height:1;'>{_eic} {_esp}</div>"
        f"<div style='font-size:15px;color:{_etc};font-weight:900;line-height:1;'>{_ear}</div>"
        f"<div style='font-size:9px;color:{_etc};font-weight:bold;line-height:1.1;'>{_eac}</div>"
        f"<div style='font-size:12px;color:#fff;font-weight:bold;line-height:1.1;'>{_ecv:.0f}%</div>"
        f"</td>"
    )
    _edet = " + ".join(f"{t}({_exp_sc.get(t,50):.0f})" for t in _ewt)
    _exp_ttp_v1.append(
        f"<div style='background:rgba(255,255,255,0.04);border:1px solid #333;"
        f"border-radius:5px;padding:4px 7px;margin:3px 0;'>"
        f"<b>{_eic} {_esp}</b> — <span style='color:{_etc};'><b>{_eac} {_ecv:.0f}%</b></span><br>"
        f"<span style='color:#888;'>Blend: {_edet} = {_ebl:.1f}</span></div>"
    )

_exp_sig_html_v1 = (
    f"<div style='background:#1a1d23;border-radius:8px;overflow:hidden;'>"
    f"<table style='width:100%;border-collapse:collapse;'><tr>{_exp_cells_v1}</tr></table></div>"
)
st.markdown(tt(_exp_sig_html_v1, "🎯 Señales Base (exp)",
    f"{''.join(_exp_ttp_v1)}<br>⚡=M1 | 🔄=M1+M2 | 📊=M1+M2+M5 | 🕐=M1+M2+M5+M15",
    "down"), unsafe_allow_html=True)

# V2: Tech + Derivatives + Macro-fused signals — per-card tooltips
_exp_m1v2 = _exp_sc.get("M1", 50)
_exp_m2v2 = _exp_sc.get("M2", 50)
_exp_m5v2 = _exp_sc.get("M5", 50)
_exp_m15v2 = _exp_sc.get("M15", 50)

# Calculate macro at each window (cached per refresh since data doesn't change within a cycle)
_macro_5s = _ms.calculate_score_at_window(feed, lookback_bars=1)
_macro_30s = _ms.calculate_score_at_window(feed, lookback_bars=3)
_macro_1m = _ms.calculate_score_at_window(feed, lookback_bars=5)
_macro_5m = _ms.calculate_score_at_window(feed, lookback_bars=15)

# (icon, label, role, tech_base, tf_blend, vel, accel, vel_weight, accel_weight,
#  macro_result, macro_weight, tech_weight, description)
_exp_v2_defs = [
    ("⚡", "5s", "Reacción instantánea",
     _exp_m1v2,
     {"M1": "100%"},
     vel_short, acceleration, 0.50, 0.30,
     _macro_5s, 0.20, 0.80,
     "Captura micro-movimientos del último tick + <b>pulso mundial</b>.<br>"
     "80% técnico (M1) + 20% macro (assets en ~1 min).<br>"
     "El mundo confirma o frena la señal instantánea."),
    ("🔄", "30s", "Confirmación corta",
     _exp_m1v2 * 0.6 + _exp_m2v2 * 0.4,
     {"M1": "60%", "M2": "40%"},
     vel_medium, acceleration, 0.30, 0.15,
     _macro_30s, 0.30, 0.70,
     "M1+M2 técnico + <b>mundo en 3 min</b>.<br>"
     "70% técnico + 30% macro (retornos 3-min de 8 assets).<br>"
     "Filtra señales falsas: si el mundo no acompaña → esperar."),
    ("📊", "1m", "Tendencia corta",
     _exp_m1v2 * 0.4 + _exp_m2v2 * 0.3 + _exp_m5v2 * 0.3,
     {"M1": "40%", "M2": "30%", "M5": "30%"},
     vel_long, acceleration, 0.15, 0.05,
     _macro_1m, 0.40, 0.60,
     "M1+M2+M5 técnico + <b>mundo en 5 min</b>.<br>"
     "60% técnico + 40% macro (retornos 5-min).<br>"
     "Equilibrio: si técnico Y mundo confluyen → <b>señal fuerte</b>."),
    ("🕐", "5m", "Contexto estratégico",
     _exp_m1v2 * 0.2 + _exp_m2v2 * 0.2 + _exp_m5v2 * 0.35 + _exp_m15v2 * 0.25,
     {"M1": "20%", "M2": "20%", "M5": "35%", "M15": "25%"},
     vel_long, acceleration, 0.10, 0.03,
     _macro_5m, 0.50, 0.50,
     "M1-M15 técnico + <b>mundo en 15 min</b>.<br>"
     "50% técnico + 50% macro (retornos 15-min).<br>"
     "Señal estratégica: indica la <b>dirección dominante global</b>."),
]

_exp_v2_cols = st.columns(4)
for _col_idx, (_eic2, _esp2, _erole, _ebase2, _eblend, _evel2, _eacc2, _evw2, _eaw2,
               _emacro, _emw, _etw, _edesc) in enumerate(_exp_v2_defs):
    # Layer 1: Technical base + derivatives
    _ev_boost = vel_to_boost(_evel2)
    _ea_boost = accel_to_boost(_eacc2)
    _tech_enhanced = max(0, min(100, _ebase2 + (_ev_boost * _evw2 * 2) + (_ea_boost * _eaw2 * 2)))

    # Layer 2: Macro at matching window
    _emacro_score = _emacro["score"]
    _emacro_dir = _emacro["direction"]
    _emacro_consensus = _emacro["consensus_raw"]

    # Layer 3: Fuse tech + macro
    _fused = _tech_enhanced * _etw + _emacro_score * _emw
    _fused = max(0, min(100, _fused))

    _esd2 = "LONG" if _fused >= 55 else ("SHORT" if _fused <= 45 else "NEUTRAL")
    _ecv2 = min(100, abs(_fused - 50) * 2)
    if _esd2 == "LONG":    _er2, _eg2, _eb2 = 82, 183, 136; _ear2 = "▲"; _eac2 = "COMPRAR"
    elif _esd2 == "SHORT": _er2, _eg2, _eb2 = 239, 71, 111; _ear2 = "▼"; _eac2 = "VENDER"
    else:                  _er2, _eg2, _eb2 = 255, 209, 102; _ear2 = "◆"; _eac2 = "ESPERAR"
    _eop2 = 0.10 + (_ecv2 / 100) * 0.45
    _etc2 = f"rgb({_er2},{_eg2},{_eb2})"; _ebg2 = f"rgba({_er2},{_eg2},{_eb2},{_eop2:.2f})"
    if _eacc2 > 0.002: _eacc_icon = "⏫"; _eacc_txt = "acelerando al alza"
    elif _eacc2 > 0: _eacc_icon = "🔼"; _eacc_txt = "subiendo pero frenando"
    elif _eacc2 > -0.002: _eacc_icon = "🔽"; _eacc_txt = "bajando pero frenando"
    else: _eacc_icon = "⏬"; _eacc_txt = "acelerando a la baja"

    if _evel2 > 0.01: _evel_txt = f"↑ subiendo ({_evel2:+.4f}/s)"
    elif _evel2 < -0.01: _evel_txt = f"↓ bajando ({_evel2:+.4f}/s)"
    else: _evel_txt = f"→ estable ({_evel2:+.4f}/s)"

    _blend_txt = " + ".join(f"{t}({p})" for t, p in _eblend.items())
    _blend_vals = " + ".join(f"{_exp_sc.get(t, 50):.0f}×{p}" for t, p in _eblend.items())

    # Macro direction indicator for the card
    if _emacro_dir == "LONG": _macro_icon = "🌍↑"
    elif _emacro_dir == "SHORT": _macro_icon = "🌍↓"
    else: _macro_icon = "🌍→"

    _card_html = (
        f"<div style='background:{_ebg2};padding:4px 4px;text-align:center;"
        f"border-radius:6px;'>"
        f"<div style='font-size:9px;color:#888;line-height:1;'>{_eic2} {_esp2} {_eacc_icon} {_macro_icon}</div>"
        f"<div style='font-size:15px;color:{_etc2};font-weight:900;line-height:1;'>{_ear2}</div>"
        f"<div style='font-size:9px;color:{_etc2};font-weight:bold;line-height:1.1;'>{_eac2}</div>"
        f"<div style='font-size:12px;color:#fff;font-weight:bold;line-height:1.1;'>{_ecv2:.0f}%</div>"
        f"</div>"
    )

    _tip_body = (
        f"<div style='margin-bottom:6px;'>{_edesc}</div>"
        f"<div style='background:rgba(255,255,255,0.06);border:1px solid #333;"
        f"border-radius:5px;padding:6px;margin:4px 0;'>"
        # Layer 1: Technical
        f"<span style='color:#4cc9f0;font-weight:bold;'>① Técnico ({_etw:.0%})</span><br>"
        f"Base = {_blend_txt}<br>"
        f"<span style='color:#888;'>{_blend_vals} = <b>{_ebase2:.1f}</b></span><br>"
        f"Vel: {_evel_txt} → boost {_ev_boost * _evw2 * 2:+.1f}<br>"
        f"Acc: {_eacc_txt} → boost {_ea_boost * _eaw2 * 2:+.1f}<br>"
        f"<b>Tech enhanced = {_tech_enhanced:.1f}</b><br><br>"
        # Layer 2: Macro
        f"<span style='color:#ffd166;font-weight:bold;'>② Macro ({_emw:.0%}) — ventana {_emacro['lookback_bars']}min</span><br>"
        f"Consenso mundo: <b>{_emacro_consensus:+.4f}</b> → score <b>{_emacro_score:.1f}</b><br>"
        f"Dirección mundo: <b>{_emacro_dir}</b><br><br>"
        # Layer 3: Fusion
        f"<span style='color:#52b788;font-weight:bold;'>③ Fusión</span><br>"
        f"{_tech_enhanced:.1f}×{_etw:.0%} + {_emacro_score:.1f}×{_emw:.0%} = "
        f"<b style='color:{_etc2};font-size:14px;'>{_fused:.1f}</b><br>"
        f"Confianza = |{_fused:.1f} - 50| × 2 = <b>{_ecv2:.0f}%</b>"
        f"</div>"
    )

    with _exp_v2_cols[_col_idx]:
        st.markdown(tt(_card_html, f"{_eic2} {_esp2} — {_erole}", _tip_body, "down"),
                    unsafe_allow_html=True)

# ── Per-Asset Vote Breakdown ──
with st.expander("📊 **Detalle votos por activo** — EWMA Confidence Weighted", expanded=False):
    _votes = _macro_result.get("votes", {})
    if _votes:
        _vote_rows = ""
        for _vk, _vv in sorted(_votes.items(), key=lambda x: abs(x[1]["weighted_vote"]), reverse=True):
            _v_name = CN.get(_vk, _vk)
            _v_ret = _vv["return_bps"]
            _v_raw = _vv["raw_vote"]
            _v_conf = _vv["confidence"]
            _v_ew = _vv["effective_weight"]
            _v_wv = _vv["weighted_vote"]
            _v_ewma = _vv["ewma_corr"]
            _v_conc = _vv["concordance"]
            _v_warm = _vv["warmup"]
            
            # Color based on vote direction
            if _v_wv > 0.05:
                _v_clr = "#52b788"
                _v_dir = "LONG"
            elif _v_wv < -0.05:
                _v_clr = "#ef476f"
                _v_dir = "SHORT"
            else:
                _v_clr = "#555"
                _v_dir = "—"
            
            # Confidence bar
            _c_clr = "#52b788" if _v_conf >= 0.6 else ("#ffd166" if _v_conf >= 0.3 else "#ef476f")
            _c_pct = _v_conf * 100
            _warmup_tag = " <span style='color:#ff6b6b;font-size:9px;'>⏳WARMUP</span>" if _v_warm else ""
            
            _vote_rows += (
                f"<tr style='border-bottom:1px solid #1a1d23;'>"
                f"<td style='padding:4px 6px;color:#ccc;font-weight:bold;'>{_v_name}{_warmup_tag}</td>"
                f"<td style='padding:4px 4px;text-align:right;color:{'#52b788' if _v_ret > 0 else '#ef476f' if _v_ret < 0 else '#555'};'>"
                f"{_v_ret:+.1f}bp</td>"
                f"<td style='padding:4px 4px;text-align:right;color:{_v_clr};font-weight:bold;'>{_v_dir}</td>"
                f"<td style='padding:4px 4px;text-align:center;'>"
                f"<div style='background:#2a2d35;border-radius:3px;height:4px;width:50px;display:inline-block;overflow:hidden;'>"
                f"<div style='background:{_c_clr};height:100%;width:{_c_pct:.0f}%;'></div></div>"
                f"<span style='color:{_c_clr};font-size:10px;margin-left:3px;'>{_v_conf:.0%}</span></td>"
                f"<td style='padding:4px 4px;text-align:right;color:{_v_clr};'>{_v_wv:+.3f}</td>"
                f"</tr>"
            )
        
        st.markdown(
            f"<table style='width:100%;font-size:12px;font-family:monospace;"
            f"border-collapse:collapse;background:#0e1117;'>"
            f"<tr style='border-bottom:1px solid #333;'>"
            f"<th style='padding:4px 6px;text-align:left;color:#888;font-size:10px;'>ACTIVO</th>"
            f"<th style='padding:4px 4px;text-align:right;color:#888;font-size:10px;'>Δ3min</th>"
            f"<th style='padding:4px 4px;text-align:right;color:#888;font-size:10px;'>VOTO</th>"
            f"<th style='padding:4px 4px;text-align:center;color:#888;font-size:10px;'>CONFIANZA</th>"
            f"<th style='padding:4px 4px;text-align:right;color:#888;font-size:10px;'>PESO</th>"
            f"</tr>{_vote_rows}</table>"
            f"<div style='text-align:center;margin-top:6px;font-size:11px;color:#666;'>"
            f"Consenso: <b style='color:#fff;'>{_macro_result['consensus_raw']:+.4f}</b> | "
            f"Confianza promedio: <b style='color:#fff;'>{_macro_result['confidence_avg']:.0%}</b></div>",
            unsafe_allow_html=True
        )
    else:
        st.caption("⏳ Esperando datos de cross-assets...")

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
    if "ai_web_search" not in st.session_state:
        st.session_state.ai_web_search = False

    ai = st.session_state.ai_client
    from sentinel.ai_chat import MODELS, THINKING_EFFORTS, save_conversation

    # Header row: model + options + status + clear
    ai_h1, ai_h2, ai_h3, ai_h4 = st.columns([1.2, 0.8, 2.0, 0.5])
    with ai_h1:
        ai_model = st.selectbox("Modelo", list(MODELS.keys()),
                               format_func=lambda k: MODELS[k].name, label_visibility="collapsed")
    with ai_h2:
        _ai_ws = st.checkbox("🔍 Web", value=st.session_state.ai_web_search,
                             help="Buscar noticias en Reuters, Bloomberg, Investing.com, etc.")
        st.session_state.ai_web_search = _ai_ws
    with ai_h3:
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
    with ai_h4:
        if st.button("🗑️", use_container_width=True, help="Limpiar conversación"):
            st.session_state.ai_messages = []
            st.rerun()

    # Model description + thinking effort selector
    sel_model = MODELS[ai_model]
    _ai_opt1, _ai_opt2 = st.columns([3, 1])
    with _ai_opt1:
        _ws_note = " · <span style='color:#ffd166;'>🔍 Web ON → sin thinking</span>" if _ai_ws else ""
        st.markdown(f"""<div style='background:#1a1d23;border-radius:6px;padding:6px 10px;
        font-size:11px;color:#888;margin-bottom:8px;'>
        {sel_model.icon} <b>{sel_model.id}</b> — {sel_model.description}
        &nbsp;|&nbsp; 💰 ${sel_model.input_cost_per_mtok}/M in, ${sel_model.output_cost_per_mtok}/M out
        {_ws_note}
        </div>""", unsafe_allow_html=True)
    with _ai_opt2:
        _ai_effort = None
        if sel_model.supports_thinking and not _ai_ws:
            _ai_effort = st.selectbox("Thinking", THINKING_EFFORTS,
                                      index=THINKING_EFFORTS.index(sel_model.thinking_effort)
                                      if sel_model.thinking_effort in THINKING_EFFORTS else 0,
                                      label_visibility="collapsed",
                                      help="Nivel de razonamiento extendido")

    # Chat messages container (scrollable)
    chat_container = st.container(height=350)
    with chat_container:
        if not st.session_state.ai_messages:
            st.markdown("""<div style='text-align:center;padding:50px 20px;color:#555;'>
            <div style='font-size:40px;'>🤖</div>
            <div style='font-size:14px;margin-top:8px;'>Pregunta sobre el mercado actual</div>
            <div style='font-size:11px;color:#444;margin-top:4px;'>
            La IA recibe un <b>snapshot completo</b> del dashboard: scores por TF,
            sub-scores (EMA/RSI/MACD/BB/PA), derivadas, correlaciones HOY,
            movimiento cross-asset, niveles S/R, divergencias y alertas.<br>
            <span style='color:#ffd166;'>🔍 Activa Web para buscar noticias financieras.</span>
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
                    ws_txt = f" · 🔍 {m.get('web_searches',0)}" if m.get("web_searches",0) > 0 else ""
                    meta_html = (f"<div style='font-size:10px;color:#555;margin-top:4px;'>"
                                f"⏱️ {m.get('duration_s',0)}s · "
                                f"📊 {m.get('input_tokens',0):,}→{m.get('output_tokens',0):,} · "
                                f"💰 ${m.get('cost_usd',0):.4f}{ws_txt}</div>")

                # Render citations
                cite_html = ""
                if msg.get("meta") and msg["meta"].get("citations"):
                    cites = msg["meta"]["citations"]
                    if cites:
                        cite_items = "".join(
                            f"<li><a href='{c['url']}' target='_blank' "
                            f"style='color:#4cc9f0;text-decoration:none;'>"
                            f"{c.get('title','') or c['url']}</a>"
                            f"<span style='color:#555;'> — {c.get('cited_text','')[:80]}</span></li>"
                            for c in cites[:5]
                        )
                        cite_html = (f"<div style='margin-top:6px;padding-top:4px;"
                                    f"border-top:1px solid #333;font-size:10px;'>"
                                    f"<b style='color:#aaa;'>📎 Fuentes:</b>"
                                    f"<ul style='margin:2px 0;padding-left:16px;'>"
                                    f"{cite_items}</ul></div>")

                st.markdown(f"""<div style='display:flex;justify-content:{align};margin:4px 0;'>
                <div style='background:{bg};border:1px solid {border};border-radius:10px;
                padding:8px 12px;max-width:85%;font-size:13px;'>
                <span style='font-size:11px;'>{icon}</span> {msg['content']}
                {cite_html}
                {meta_html}
                </div></div>""", unsafe_allow_html=True)

    # Input area
    ai_input_col, ai_send_col = st.columns([5, 1])
    with ai_input_col:
        _ph = ("Ej: ¿Qué noticias afectan USDCLP hoy?" if _ai_ws
               else "Ej: ¿Debería preocuparme por el RSI de M1?")
        ai_prompt = st.text_input("Mensaje", placeholder=_ph,
                                  label_visibility="collapsed", key="ai_input")
    with ai_send_col:
        _send_label = f"🔍 Buscar" if _ai_ws else f"{sel_model.icon} Enviar"
        ai_send = st.button(_send_label, use_container_width=True, type="primary")

    if ai_send and ai_prompt:
        st.session_state.ai_messages.append({"role": "user", "content": ai_prompt})

        from sentinel.ai_chat import build_market_context

        # Build complete derivative data
        deriv_data = {
            "velocity": vel_short if 'vel_short' in dir() else 0,
            "acceleration": acceleration if 'acceleration' in dir() else 0,
            "momentum_text": mom_txt if 'mom_txt' in dir() else "N/A",
            "n_ticks": n_ticks if 'n_ticks' in dir() else 0,
        }

        # Build cross-asset movement data for context
        _ca_data = {}
        for _cak2 in _cross_asset_keys:
            _ct2 = _cross_tech.get(_cak2, {})
            _cm2 = _cross_m1.get(_cak2, {})
            _ca_data[_cak2] = {
                "fast_score": _ct2.get("fast_score", 50),
                "direction": _ct2.get("direction", "NEUTRAL"),
                "m2_bps": _cm2.get("m2", 0),
                "m5_bps": _cm2.get("m5", 0),
            }

        system_ctx = build_market_context(
            result, price_info, deriv_data,
            cross_asset_data=_ca_data,
            cross_corr_hoy=_cross_corr_hoy,
            web_search_enabled=_ai_ws,
        )
        api_msgs = [{"role": m["role"], "content": m["content"]}
                    for m in st.session_state.ai_messages[:-1]]

        _spinner_txt = ("🔍 Buscando noticias y analizando..." if _ai_ws
                        else ('🧠 Pensando profundamente...' if ai_model == 'opus'
                              else '⚡ Analizando...'))
        with st.spinner(_spinner_txt):
            response = ai.chat(
                ai_prompt, ai_model, system_ctx, api_msgs,
                web_search_enabled=_ai_ws,
                thinking_effort_override=_ai_effort,
            )

        st.session_state.ai_messages.append({
            "role": "assistant",
            "content": response["content"],
            "meta": response,
        })

        # Auto-save conversation locally
        _session_id = st.session_state.get("_ai_session_id", "")
        if not _session_id:
            import uuid
            _session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
            st.session_state._ai_session_id = _session_id
        save_conversation(st.session_state.ai_messages, _session_id)

        st.rerun()

# ══════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.caption(f"SENTINEL v{VERSION} \"{CODENAME}\" | "
           f"Última actualización: {datetime.now().strftime('%H:%M:%S')} | "
           f"Fuente: {'🟢 MT5 Real-Time' if feed.mt5_connected else '🟡 Yahoo Finance (delay)'} | "
           f"Score: Técnico {WEIGHTS.technical*100:.0f}% + Macro {WEIGHTS.correlation*100:.0f}%")

if auto_refresh:
    time.sleep(DASHBOARD_REFRESH_SECONDS)
    st.rerun()
