"""
ui/styles.py — Premium dark-theme CSS injection + HTML component helpers.

Call inject() once from app.py after st.set_page_config().
Use the helper functions to render custom HTML components anywhere in the UI.
"""

import streamlit as st

# ── Accent palette ──────────────────────────────────────────────────────────
ACCENT      = "#00d4aa"   # teal-green — primary accent
ACCENT_DIM  = "#00a885"   # darker teal for hover
BLUE        = "#4dabf7"
RED         = "#ff6b6b"
YELLOW      = "#ffd93d"
GREEN       = "#51cf66"
SURFACE     = "#161b22"   # card background
BORDER      = "rgba(255,255,255,0.08)"
TEXT_MUTED  = "rgba(255,255,255,0.45)"


def inject() -> None:
    """Inject all custom CSS into the Streamlit app."""
    st.markdown(
        f"""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

/* ── Base ── */
html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

/* ── Hide default Streamlit chrome ── */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    background: #0d1117 !important;
    border-right: 1px solid {BORDER};
}}
[data-testid="stSidebar"] > div:first-child {{
    padding-top: 0 !important;
}}

/* Brand header inside sidebar */
.brand-header {{
    padding: 20px 16px 12px;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 8px;
}}
.brand-name {{
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: {ACCENT};
    text-transform: uppercase;
}}
.brand-tagline {{
    font-size: 11px;
    color: {TEXT_MUTED};
    margin-top: 2px;
    letter-spacing: 0.3px;
}}

/* Nav radio group — make it look like nav links, not a form */
[data-testid="stSidebar"] [role="radiogroup"] {{
    gap: 2px !important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: {TEXT_MUTED};
    margin: 16px 0 8px 16px;
}}

/* Style each radio as a nav item */
[data-testid="stSidebar"] label {{
    border-radius: 8px;
    padding: 8px 14px !important;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
    margin: 1px 8px;
    font-size: 13.5px;
    font-weight: 500;
    color: rgba(255,255,255,0.75) !important;
}}
[data-testid="stSidebar"] label:hover {{
    background: rgba(255,255,255,0.06) !important;
    color: rgba(255,255,255,0.95) !important;
}}
[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {{
    display: none !important;  /* hide radio circle */
}}
/* Active nav item (checked radio) */
[data-testid="stSidebar"] [aria-checked="true"] {{
    background: {ACCENT}18 !important;
    color: {ACCENT} !important;
    border-left: 3px solid {ACCENT};
    padding-left: 11px !important;
}}

/* Sidebar Settings header */
[data-testid="stSidebar"] h2 {{
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: {TEXT_MUTED} !important;
}}

/* ── Main content area ── */
[data-testid="stAppViewContainer"] > .main {{
    background: #0e1117;
}}
.block-container {{
    max-width: 1200px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}}

/* ── Page title ── */
h1 {{
    font-size: 2rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px;
    line-height: 1.2;
    margin-bottom: 4px !important;
}}

/* ── Dividers ── */
hr {{
    border-color: {BORDER} !important;
    margin: 1.5rem 0 !important;
}}

/* ── Buttons ── */
[data-testid="baseButton-primary"] {{
    background: {ACCENT} !important;
    border: none !important;
    color: #0e1117 !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px;
    border-radius: 8px !important;
    transition: background 0.15s, box-shadow 0.15s !important;
}}
[data-testid="baseButton-primary"]:hover {{
    background: {ACCENT_DIM} !important;
    box-shadow: 0 0 16px {ACCENT}55 !important;
}}
[data-testid="baseButton-secondary"] {{
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: border-color 0.15s, background 0.15s !important;
}}
[data-testid="baseButton-secondary"]:hover {{
    border-color: {ACCENT}88 !important;
    background: {ACCENT}0f !important;
}}

/* ── Inputs ── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
textarea {{
    background: {SURFACE} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    color: rgba(255,255,255,0.9) !important;
    transition: border-color 0.15s !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
textarea:focus {{
    border-color: {ACCENT}88 !important;
    box-shadow: 0 0 0 3px {ACCENT}18 !important;
}}

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {{
    background: {SURFACE} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}

/* ── Date input ── */
[data-testid="stDateInput"] input {{
    background: {SURFACE} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
}}

/* ── Expanders ── */
[data-testid="stExpander"] {{
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    background: {SURFACE} !important;
}}
[data-testid="stExpander"] summary {{
    font-weight: 500;
    font-size: 13.5px;
}}

/* ── Metric cards (native st.metric) ── */
[data-testid="stMetric"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 20px;
}}
[data-testid="stMetricLabel"] {{
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: {TEXT_MUTED} !important;
}}
[data-testid="stMetricValue"] {{
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    font-family: 'Inter', sans-serif !important;
    letter-spacing: -0.5px;
}}

/* ── Dataframe table ── */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    overflow: hidden;
}}

/* ── Alerts / info boxes ── */
[data-testid="stAlert"] {{
    border-radius: 10px !important;
    border-left-width: 4px !important;
}}

/* ── Spinner ── */
[data-testid="stSpinner"] {{
    color: {ACCENT} !important;
}}

/* ── Slider ── */
[data-testid="stSlider"] [role="slider"] {{
    background: {ACCENT} !important;
}}
[data-testid="stSlider"] [data-baseweb="slider"] div[style*="background"] {{
    background: {ACCENT} !important;
}}

/* ── Form container ── */
[data-testid="stForm"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 24px;
}}

/* ── Progress bar (scoring breakdown) ── */
[data-testid="stProgress"] > div > div {{
    background: {ACCENT} !important;
    border-radius: 4px !important;
}}
[data-testid="stProgress"] > div {{
    background: rgba(255,255,255,0.08) !important;
    border-radius: 4px !important;
}}

/* ── Caption / muted text ── */
[data-testid="stCaptionContainer"] {{
    color: {TEXT_MUTED} !important;
    font-size: 12.5px !important;
}}

/* ── Subheader ── */
h2, h3 {{
    font-weight: 600 !important;
    letter-spacing: -0.3px;
}}
</style>
""",
        unsafe_allow_html=True,
    )


# ── HTML helper components ───────────────────────────────────────────────────

def metric_card(label: str, value: str, delta: str = "", delta_up: bool = True, width: str = "100%") -> str:
    """
    Returns an HTML string for a custom metric card.
    Render with st.markdown(..., unsafe_allow_html=True).
    """
    delta_color = GREEN if delta_up else RED
    delta_html = (
        f'<div style="font-size:12px;font-weight:500;color:{delta_color};margin-top:4px;">'
        f'{delta}</div>'
        if delta else ""
    )
    return f"""
<div style="
    background:{SURFACE};
    border:1px solid {BORDER};
    border-radius:12px;
    padding:18px 22px;
    width:{width};
    box-sizing:border-box;
    transition:border-color 0.2s;
">
  <div style="font-size:10.5px;font-weight:600;text-transform:uppercase;
              letter-spacing:0.9px;color:{TEXT_MUTED};margin-bottom:8px;">
    {label}
  </div>
  <div style="font-size:1.55rem;font-weight:700;letter-spacing:-0.4px;
              color:rgba(255,255,255,0.95);line-height:1.1;">
    {value}
  </div>
  {delta_html}
</div>"""


def grade_badge(grade: str, color_name: str) -> str:
    """Premium grade badge with glow effect."""
    palette = {
        "green":  (GREEN,  "#51cf6622"),
        "orange": (YELLOW, "#ffd93d22"),
        "red":    (RED,    "#ff6b6b22"),
    }
    fg, bg = palette.get(color_name, (ACCENT, f"{ACCENT}22"))
    return f"""
<div style="
    display:inline-flex;align-items:center;gap:8px;
    padding:10px 24px;
    border-radius:100px;
    background:{bg};
    border:1.5px solid {fg};
    color:{fg};
    font-size:13px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;
    box-shadow:0 0 20px {fg}33;
">{grade}</div>"""


def section_header(title: str, subtitle: str = "") -> str:
    """Styled section header with accent underline and optional subtitle."""
    sub_html = (
        f'<div style="font-size:13px;color:{TEXT_MUTED};margin-top:4px;font-weight:400;">'
        f'{subtitle}</div>'
        if subtitle else ""
    )
    return f"""
<div style="margin:8px 0 16px;">
  <div style="font-size:16px;font-weight:700;letter-spacing:-0.3px;
              color:rgba(255,255,255,0.95);padding-bottom:10px;
              border-bottom:1px solid {BORDER};">
    {title}
  </div>
  {sub_html}
</div>"""


def pill_tag(text: str, color: str = ACCENT) -> str:
    """Small pill badge for tags/labels."""
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:100px;'
        f'background:{color}22;border:1px solid {color}66;'
        f'color:{color};font-size:11px;font-weight:600;letter-spacing:0.5px;">'
        f'{text}</span>'
    )


def catalyst_box(label: str, reason: str, source: str, color: str) -> str:
    """Styled catalyst assessment box."""
    return f"""
<div style="
    padding:16px 20px;
    border-left:3px solid {color};
    background:{color}12;
    border-radius:0 10px 10px 0;
    margin:4px 0;
">
  <div style="font-size:14px;font-weight:700;color:{color};margin-bottom:6px;">{label}</div>
  <div style="font-size:13px;color:rgba(255,255,255,0.78);line-height:1.5;">{reason}</div>
  <div style="font-size:11px;color:{TEXT_MUTED};margin-top:8px;font-weight:500;text-transform:uppercase;
              letter-spacing:0.5px;">Source: {source}</div>
</div>"""
