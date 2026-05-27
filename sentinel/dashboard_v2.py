"""
SENTINEL v2 — Dashboard (New Layout)
This is a scaffold that will be filled with the redesigned UI.
It shares DataFeed and SentinelCore with v1 via st.cache_resource in app.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
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
    pass  # Already set by app.py when running in multipage mode

# ── Shared system (initialized in app.py, or standalone fallback) ──
@st.cache_resource
def init_system():
    feed = DataFeed(mode="auto")
    return feed, SentinelCore(feed)

feed, core = init_system()

# ── Data Calculation (same as v1) ──
result = core.calculate_composite()
score = result["composite_score"]
direction = result["direction"]
price_info = feed.get_current_price(SYMBOLS["target"])
levels = result.get("levels", {})
combined = levels.get("combined", {})
curr_price = levels.get("current_price", 0)
comp = result["components"]
tech_details = comp["technical"].get("details", {})

# ══════════════════════════════════════════════════════════
# V2 LAYOUT — SCAFFOLD (to be designed)
# ══════════════════════════════════════════════════════════

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .stApp > header { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    div[data-testid="stToolbar"] { display: none !important; }
    div[data-testid="stDecoration"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    div[data-testid="stStatusWidget"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── Placeholder: Version indicator ──
dir_emoji = {"LONG": "📈", "SHORT": "📉", "NEUTRAL": "➡️"}
dir_color = {"LONG": "#52b788", "SHORT": "#ef476f", "NEUTRAL": "#ffd166"}

st.markdown(f"""
<div style='text-align:center;padding:40px 20px;'>
    <div style='font-size:48px;'>⚡</div>
    <div style='font-size:24px;font-weight:bold;color:#4cc9f0;margin-top:8px;'>
        SENTINEL v2 — En Desarrollo
    </div>
    <div style='font-size:14px;color:#888;margin-top:4px;'>
        Dashboard v{VERSION} "{CODENAME}" · Layout nuevo
    </div>
    <div style='margin-top:24px;padding:16px;background:#1a1d23;border-radius:12px;
         display:inline-block;border:1px solid #333;'>
        <div style='font-size:13px;color:#888;'>Score actual (datos compartidos con v1)</div>
        <div style='font-size:42px;font-weight:900;color:{dir_color[direction]};'>{score}</div>
        <div style='font-size:18px;color:{dir_color[direction]};'>
            {dir_emoji[direction]} {direction}
        </div>
        <div style='font-size:12px;color:#555;margin-top:4px;'>
            USDCLP: {curr_price:.2f} · {result['signal']}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Footer ──
st.markdown("---")
st.caption(f"SENTINEL v2 (dev) | v{VERSION} \"{CODENAME}\" | "
           f"{datetime.now().strftime('%H:%M:%S')} | "
           f"{'🟢 MT5' if feed.mt5_connected else '🟡 Yahoo'}")

# ── Auto-refresh (same as v1) ──
with st.sidebar:
    auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)
    st.caption(f"Refresh: {DASHBOARD_REFRESH_SECONDS}s")

if auto_refresh:
    time.sleep(DASHBOARD_REFRESH_SECONDS)
    st.rerun()
