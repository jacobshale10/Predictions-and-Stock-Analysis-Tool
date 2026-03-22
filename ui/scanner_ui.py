"""
ui/scanner_ui.py — Market Scanner page.

Scans an entire ticker universe (S&P 500 / NASDAQ 100 / Russell 1000 / All Large Cap),
flags equities that meet the investment criteria, and presents a ranked table with:
  - Setup score, grade, decline from 52W high
  - Auto-calculated WACC
  - DCF margin of safety (AI-powered if Claude key provided)
  - Key flags (PE discount, analyst upside, catalyst type)

Clicking a row pre-populates the Stock Detail page.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from analysis import batch_screener
from data import universe as universe_module
from ui import styles


# ── Grade color helpers ───────────────────────────────────────────────────────

_GRADE_COLORS = {
    "STRONG SETUP":   styles.GREEN,
    "MODERATE SETUP": styles.YELLOW,
    "WEAK SETUP":     styles.RED,
}


def _grade_pill(grade: str) -> str:
    short = grade.split()[0]  # "STRONG" | "MODERATE" | "WEAK"
    color = _GRADE_COLORS.get(grade, styles.ACCENT)
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:100px;'
        f'background:{color}22;border:1px solid {color}66;'
        f'color:{color};font-size:11px;font-weight:700;letter-spacing:0.8px;">'
        f'{short}</span>'
    )


def _mos_color(mos: float | None) -> str:
    if mos is None:
        return styles.TEXT_MUTED
    if mos >= 0.20:
        return styles.GREEN
    if mos >= 0.05:
        return styles.YELLOW
    if mos >= -0.10:
        return styles.TEXT_MUTED
    return styles.RED


def _cache_age_str(universe_name: str) -> str:
    """Returns human-readable cache age string."""
    try:
        safe = universe_name.replace(" ", "_").replace("&", "and")
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = Path(__file__).parent.parent / "data" / "cache" / f"scan_{safe}_{date_str}.pkl"
        if not path.exists():
            return ""
        import pickle
        with open(path, "rb") as f:
            data = pickle.load(f)
        if not data:
            return ""
        ts = data[0].scan_timestamp
        age = datetime.now() - ts
        if age.total_seconds() < 60:
            return "just now"
        if age.total_seconds() < 3600:
            mins = int(age.total_seconds() / 60)
            return f"{mins}m ago"
        hours = age.total_seconds() / 3600
        fresh_for = max(0, 6 - hours)
        return f"{hours:.1f}h ago · cache valid {fresh_for:.1f}h more"
    except Exception:
        return ""


def render():
    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown(
        '<h1 style="margin-bottom:0;">Market Scanner</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:13.5px;color:rgba(255,255,255,0.45);margin-bottom:24px;">'
        'Automatically scan entire market universes and flag equities with mean-reversion setups — '
        'ranked by composite score including AI-powered DCF valuation.'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Sidebar controls ─────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            '<div style="font-size:11px;font-weight:600;text-transform:uppercase;'
            'letter-spacing:1.2px;color:rgba(255,255,255,0.35);margin:16px 0 8px 16px;">Scan Settings</div>',
            unsafe_allow_html=True,
        )

        universe_name = st.selectbox(
            "Universe",
            options=["S&P 500", "NASDAQ 100", "Russell 1000", "All Large Cap"],
            index=0,
            help="S&P 500 is the fastest (~5 min). All Large Cap is the most comprehensive (~20 min).",
        )

        min_score = st.select_slider(
            "Min Setup Score",
            options=[0.40, 0.50, 0.60, 0.72],
            value=0.50,
            format_func=lambda x: f"{x:.2f}  ({'STRONG' if x >= 0.72 else 'MODERATE+' if x >= 0.50 else 'ALL'})",
            help="0.72+ = STRONG setups only. 0.50+ includes MODERATE.",
        )

        max_results = st.selectbox(
            "Max Results",
            options=[10, 25, 50, 100],
            index=1,
            help="Number of top-ranked results to display.",
        )

        st.divider()
        st.markdown(
            '<div style="font-size:11px;font-weight:600;text-transform:uppercase;'
            'letter-spacing:1.2px;color:rgba(255,255,255,0.35);margin:8px 0 8px 16px;">AI Settings</div>',
            unsafe_allow_html=True,
        )

        claude_api_key = st.text_input(
            "Claude API Key (optional)",
            type="password",
            help=(
                "Your Anthropic API key enables AI-powered DCF analysis on top candidates. "
                "Get one at console.anthropic.com. Without a key, quantitative DCF is used."
            ),
            key="scanner_claude_key",
        )

        groq_api_key = st.text_input(
            "Groq API Key (optional)",
            type="password",
            help="Free key from console.groq.com — enables AI news classification.",
            key="scanner_groq_key",
        )

        st.divider()

        col_run, col_refresh = st.columns([2, 1])
        with col_run:
            run_scan = st.button("Run Market Scan", type="primary", use_container_width=True)
        with col_refresh:
            force_refresh = st.button("↺ Refresh", help="Force re-scan, bypass cache", use_container_width=True)

    # ── Check for prefill from scanner (clicking a row) ───────────────────────
    if "scanner_select_ticker" in st.session_state:
        ticker_to_view = st.session_state.pop("scanner_select_ticker")
        st.session_state["prefill_ticker"] = ticker_to_view
        st.session_state["nav_page"] = "Stock Detail"
        st.rerun()

    # ── Load or run scan ──────────────────────────────────────────────────────
    results = None
    scan_ran = False

    if run_scan or force_refresh or st.session_state.get("scanner_results_universe") == universe_name:
        if run_scan or force_refresh:
            # Run a fresh scan with progress UI
            tickers = universe_module.get_universe(universe_name)
            approx  = len(tickers)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            progress_bar   = st.progress(0.0)
            status_text    = st.empty()
            elapsed_text   = st.empty()
            start_time     = time.time()

            status_text.markdown(
                f'<div style="font-size:13px;color:{styles.TEXT_MUTED};">'
                f'Initializing scan of {approx} tickers in <b>{universe_name}</b>…</div>',
                unsafe_allow_html=True,
            )

            def progress_cb(current: int, total: int, msg: str):
                frac = min(1.0, current / max(total, 1))
                progress_bar.progress(frac)
                elapsed = time.time() - start_time
                eta_s   = (elapsed / max(current, 1)) * max(total - current, 0)
                eta_str = f"{eta_s/60:.1f} min" if eta_s > 60 else f"{eta_s:.0f}s"
                status_text.markdown(
                    f'<div style="font-size:13px;color:{styles.TEXT_MUTED};">{msg}</div>',
                    unsafe_allow_html=True,
                )
                elapsed_text.markdown(
                    f'<div style="font-size:12px;color:{styles.TEXT_MUTED};">'
                    f'Elapsed: {elapsed:.0f}s · ETA: {eta_str}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with st.spinner(""):
                results = batch_screener.scan(
                    universe_name=universe_name,
                    tickers=tickers,
                    min_score=min_score,
                    max_results=max_results,
                    claude_api_key=claude_api_key or None,
                    progress_cb=progress_cb,
                    force_refresh=force_refresh,
                )

            progress_bar.progress(1.0)
            status_text.empty()
            elapsed_text.empty()

            st.session_state["scanner_results"]         = results
            st.session_state["scanner_results_universe"]= universe_name
            scan_ran = True

        else:
            # Use cached results from session state
            results = st.session_state.get("scanner_results")

    # ── No results yet ─────────────────────────────────────────────────────────
    if not results:
        if not run_scan and not force_refresh:
            _render_how_it_works()
        return

    # ── Summary banner ─────────────────────────────────────────────────────────
    strong_count   = sum(1 for r in results if "STRONG" in r.grade)
    moderate_count = sum(1 for r in results if "MODERATE" in r.grade)
    cache_str      = _cache_age_str(universe_name)

    st.markdown(
        f'<div style="background:{styles.SURFACE};border:1px solid {styles.BORDER};'
        f'border-radius:12px;padding:16px 24px;margin-bottom:20px;'
        f'display:flex;align-items:center;justify-content:space-between;">'
        f'<div>'
        f'<span style="font-size:15px;font-weight:700;color:{styles.GREEN};">{strong_count} STRONG</span>'
        f'<span style="color:{styles.TEXT_MUTED};margin:0 8px;">+</span>'
        f'<span style="font-size:15px;font-weight:700;color:{styles.YELLOW};">{moderate_count} MODERATE</span>'
        f'<span style="font-size:13px;color:{styles.TEXT_MUTED};margin-left:12px;">setups flagged in {universe_name}</span>'
        f'</div>'
        f'<div style="font-size:12px;color:{styles.TEXT_MUTED};">{cache_str}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not results:
        st.info(f"No setups found with score ≥ {min_score:.2f} in {universe_name}. Try lowering the Min Setup Score.")
        return

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown(
        styles.section_header(
            "Flagged Opportunities",
            "Sorted by composite setup score · Click a ticker to open full analysis"
        ),
        unsafe_allow_html=True,
    )

    # Build display DataFrame
    rows = []
    for r in results:
        mos_str = f"{r.dcf_margin_of_safety*100:+.1f}%" if r.dcf_margin_of_safety is not None else "N/A"
        ai_badge = " ✦" if r.ai_powered else ""
        upside_str = f"{r.analyst_upside*100:.1f}%" if r.analyst_upside is not None else "N/A"
        rows.append({
            "Ticker":     r.ticker,
            "Company":    r.company_name[:28] + ("…" if len(r.company_name) > 28 else ""),
            "Sector":     r.sector[:16] + ("…" if r.sector and len(r.sector) > 16 else ""),
            "Score":      f"{r.setup_score:.3f}",
            "Grade":      r.grade.split()[0],
            "Decline":    f"{r.decline_from_high*100:.1f}%",
            "WACC":       f"{r.wacc*100:.1f}% [{r.wacc_range}]",
            "DCF MoS":    mos_str + ai_badge,
            "Analyst ↑":  upside_str,
            "Flags":      " · ".join(r.flags[:3]),
        })

    df = pd.DataFrame(rows)

    # Color-coded score column via styling
    def _style_grade(val):
        if val == "STRONG":
            return f"color: {styles.GREEN}; font-weight: 700;"
        if val == "MODERATE":
            return f"color: {styles.YELLOW}; font-weight: 600;"
        return f"color: {styles.RED};"

    styled = df.style.applymap(_style_grade, subset=["Grade"])

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=min(600, 50 + len(df) * 38),
    )

    # ── Click-to-detail row selection ─────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col_select, col_export = st.columns([2, 1])

    with col_select:
        ticker_options = [r.ticker for r in results]
        selected_ticker = st.selectbox(
            "Open full analysis →",
            options=["— select a ticker —"] + ticker_options,
            label_visibility="collapsed",
        )
        if selected_ticker and selected_ticker != "— select a ticker —":
            if st.button(f"Analyze {selected_ticker} in detail →", type="primary"):
                st.session_state["prefill_ticker"] = selected_ticker
                st.session_state["nav_page"] = "Stock Detail"
                st.rerun()

    with col_export:
        csv = df.to_csv(index=False)
        st.download_button(
            "Export CSV",
            data=csv,
            file_name=f"scan_{universe_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # ── AI note ───────────────────────────────────────────────────────────────
    ai_count = sum(1 for r in results if r.ai_powered)
    if ai_count > 0:
        st.markdown(
            f'<div style="font-size:12px;color:{styles.TEXT_MUTED};margin-top:8px;">'
            f'✦ {ai_count} stocks analyzed by Claude claude-sonnet-4-6 · '
            f'DCF MoS marked with ✦</div>',
            unsafe_allow_html=True,
        )
    elif not claude_api_key:
        st.markdown(
            f'<div style="font-size:12px;color:{styles.TEXT_MUTED};margin-top:8px;">'
            f'Add a Claude API key in the sidebar to enable AI-powered DCF analysis on top candidates.'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Top candidate detail cards ────────────────────────────────────────────
    if results:
        st.divider()
        st.markdown(styles.section_header("Top Candidates", "Highest-scoring setups at a glance"), unsafe_allow_html=True)
        top3 = results[:3]
        cols = st.columns(len(top3))
        for col, r in zip(cols, top3):
            grade_color = _GRADE_COLORS.get(r.grade, styles.ACCENT)
            mos_str   = (
                f'{r.dcf_margin_of_safety*100:+.1f}%{"✦" if r.ai_powered else ""}'
                if r.dcf_margin_of_safety is not None else "N/A"
            )
            mos_color = _mos_color(r.dcf_margin_of_safety)
            with col:
                st.markdown(
                    f'<div style="background:{styles.SURFACE};border:1px solid {grade_color}44;'
                    f'border-radius:12px;padding:18px 20px;">'
                    f'<div style="font-size:1.3rem;font-weight:700;color:{grade_color};margin-bottom:2px;">'
                    f'{r.ticker}</div>'
                    f'<div style="font-size:12.5px;color:rgba(255,255,255,0.55);margin-bottom:12px;">'
                    f'{r.company_name}</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">'
                    f'<div><div style="font-size:10px;color:{styles.TEXT_MUTED};text-transform:uppercase;'
                    f'letter-spacing:0.7px;">Score</div>'
                    f'<div style="font-size:1.1rem;font-weight:700;color:{grade_color};">{r.setup_score:.3f}</div></div>'
                    f'<div><div style="font-size:10px;color:{styles.TEXT_MUTED};text-transform:uppercase;'
                    f'letter-spacing:0.7px;">Decline</div>'
                    f'<div style="font-size:1.1rem;font-weight:700;">↓{r.decline_from_high*100:.0f}%</div></div>'
                    f'<div><div style="font-size:10px;color:{styles.TEXT_MUTED};text-transform:uppercase;'
                    f'letter-spacing:0.7px;">DCF MoS</div>'
                    f'<div style="font-size:1.1rem;font-weight:700;color:{mos_color};">{mos_str}</div></div>'
                    f'<div><div style="font-size:10px;color:{styles.TEXT_MUTED};text-transform:uppercase;'
                    f'letter-spacing:0.7px;">WACC</div>'
                    f'<div style="font-size:1.1rem;font-weight:700;">{r.wacc*100:.1f}%</div></div>'
                    f'</div>'
                    + (
                        f'<div style="font-size:11.5px;color:rgba(255,255,255,0.65);font-style:italic;'
                        f'border-top:1px solid {styles.BORDER};padding-top:10px;margin-top:4px;">'
                        f'"{r.ai_assessment}"</div>'
                        if r.ai_assessment else ""
                    )
                    + f'</div>',
                    unsafe_allow_html=True,
                )


def _render_how_it_works():
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown(
        styles.section_header(
            "How the Scanner Works",
            "Identifies market inefficiencies across hundreds of stocks automatically",
        ),
        unsafe_allow_html=True,
    )

    steps = [
        ("1 · Universe Selection",
         "Choose S&P 500 (503 stocks), NASDAQ 100, Russell 1000, or All Large Cap. "
         "The scanner fetches live data for every equity in the universe."),
        ("2 · Two-Pass Filter",
         "Pass 1 quickly eliminates stocks without meaningful dislocations (< 12% decline, "
         "market cap < $2B). Only ~15–30% proceed to full analysis."),
        ("3 · Composite Scoring",
         "7-dimension weighted score: Price Decline, PE vs Sector, Revenue Growth, "
         "EPS Growth, Analyst Consensus, News Catalyst, and DCF Margin of Safety."),
        ("4 · Auto-WACC Calculation",
         "WACC is calculated automatically using CAPM (beta from yfinance + live 10-yr Treasury), "
         "actual cost of debt, effective tax rate, and capital structure weights."),
        ("5 · AI-Powered DCF",
         "With a Claude API key, the top 15 candidates are analyzed by Claude claude-sonnet-4-6 — "
         "which reads the financials, selects appropriate growth rates, and computes intrinsic value."),
        ("6 · Ranked Flags",
         "Results are ranked by composite score. Click any ticker to open the full "
         "detail analysis. Export the full table as CSV."),
    ]

    cols = st.columns(3)
    for i, (title, desc) in enumerate(steps):
        with cols[i % 3]:
            st.markdown(
                f'<div style="background:{styles.SURFACE};border:1px solid {styles.BORDER};'
                f'border-radius:12px;padding:18px 20px;margin-bottom:16px;">'
                f'<div style="font-size:12.5px;font-weight:700;color:{styles.ACCENT};'
                f'margin-bottom:8px;letter-spacing:0.3px;">{title}</div>'
                f'<div style="font-size:12.5px;color:rgba(255,255,255,0.6);line-height:1.6;">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
