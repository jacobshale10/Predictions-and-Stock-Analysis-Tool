"""
app.py — Streamlit entry point.

Run with:
    streamlit run app.py

Navigation:
    Screener    → Main analysis dashboard
    Trade Log   → Enter and exit trades
    Backtest    → Aggregate performance review
"""

import streamlit as st

# Page config must be the very first Streamlit call
st.set_page_config(
    page_title="Mean Reversion Stock Screener",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)

from database import db
from ui import dashboard, trade_log_ui, backtest_ui

# Initialize database on every startup (idempotent — CREATE TABLE IF NOT EXISTS)
db.init_db()

# --- Navigation ---
PAGES = {
    "📉 Screener":    dashboard,
    "📋 Trade Log":   trade_log_ui,
    "📊 Backtest":    backtest_ui,
}

with st.sidebar:
    st.markdown("## Navigation")
    # Support nav from dashboard "Log This Trade" button
    default_page = st.session_state.pop("nav_page", None)
    page_keys    = list(PAGES.keys())

    if default_page:
        # Map short name to full key
        for k in page_keys:
            if default_page.lower() in k.lower():
                default_page = k
                break

    selected = st.radio(
        "Go to",
        options=page_keys,
        index=page_keys.index(default_page) if default_page in page_keys else 0,
        label_visibility="collapsed",
    )

PAGES[selected].render()
