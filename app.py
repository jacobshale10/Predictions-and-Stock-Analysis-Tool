"""
app.py — Streamlit entry point.

Run with:
    streamlit run app.py
"""

import streamlit as st

# Page config must be the very first Streamlit call
st.set_page_config(
    page_title="MR Screener",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)

from database import db
from ui import scanner_ui, dashboard, trade_log_ui, backtest_ui
from ui import styles

# Inject premium CSS theme
styles.inject()

# Initialize database on every startup (idempotent)
db.init_db()

# ── Navigation ────────────────────────────────────────────────────────────────
PAGES = {
    "Market Scanner": scanner_ui,
    "Stock Detail":   dashboard,
    "Trade Log":      trade_log_ui,
    "Backtest":       backtest_ui,
}

NAV_ICONS = {
    "Market Scanner": "⬡",
    "Stock Detail":   "◎",
    "Trade Log":      "◈",
    "Backtest":       "◉",
}

with st.sidebar:
    # Brand header
    st.markdown(
        """
<div class="brand-header">
  <div class="brand-name">MR Screener</div>
  <div class="brand-tagline">Mean Reversion · AI-Powered · Market Inefficiencies</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="font-size:11px;font-weight:600;text-transform:uppercase;'
        'letter-spacing:1.2px;color:rgba(255,255,255,0.35);margin:16px 0 8px 16px;">Navigation</div>',
        unsafe_allow_html=True,
    )

    # Support nav redirect from scanner → detail and dashboard → trade log
    default_page = st.session_state.pop("nav_page", None)
    page_keys = list(PAGES.keys())

    if default_page:
        for k in page_keys:
            if default_page.lower() in k.lower():
                default_page = k
                break

    selected = st.radio(
        "nav",
        options=page_keys,
        index=page_keys.index(default_page) if default_page in page_keys else 0,
        label_visibility="collapsed",
        format_func=lambda k: f"{NAV_ICONS.get(k, '·')}  {k}",
    )

PAGES[selected].render()
