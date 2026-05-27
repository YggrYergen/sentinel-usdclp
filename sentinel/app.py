"""
SENTINEL — Multi-Page Router
Entry point that serves both v1 (production dashboard) and v2 (new layout).
Uses st.navigation for clean URL routing:
  /           → v1 (dashboard.py — untouched production)
  /v2         → v2 (dashboard_v2.py — new layout in development)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

# Must be the FIRST Streamlit command (before any other st.* calls)
st.set_page_config(page_title="SENTINEL — USD/CLP", page_icon="🛡️",
                   layout="wide", initial_sidebar_state="collapsed")

from sentinel.version import VERSION

# ── Shared resources (single MT5 connection, shared across both pages) ──
from sentinel.data_feed import DataFeed
from sentinel.sentinel_core import SentinelCore

@st.cache_resource
def init_system():
    feed = DataFeed(mode="auto")
    return feed, SentinelCore(feed)

# Pre-initialize so both pages share the same instances
feed, core = init_system()

# ── Page definitions ──
v1 = st.Page("dashboard.py", title="SENTINEL v1", icon="🛡️", default=True)
v2 = st.Page("dashboard_v2.py", title="SENTINEL v2", icon="⚡")

# ── Navigation ──
pg = st.navigation(
    {
        "Dashboard": [v1, v2],
    },
    position="sidebar",
)

pg.run()
