"""
ui/dashboard.py — Main analysis results page.

Renders the full analysis for a single ticker:
  1. Ticker input + Run button
  2. Metric cards (price, decline, analyst upside)
  3. Grade badge + probability gauge
  4. Radar chart (6 sub-scores)
  5. Price history chart
  6. DCF valuation
  7. News catalyst assessment
  8. Raw data expander
  9. "Log This Trade" button → pre-populates trade log form via session_state
"""

import streamlit as st

from analysis import screener, scorer, dcf, probability
from data import fetcher
from ui import charts


def _grade_badge(grade: str, color: str) -> str:
    colors = {"green": "#2ecc71", "orange": "#f39c12", "red": "#e74c3c"}
    hex_color = colors.get(color, "#4dabf7")
    return (
        f'<div style="display:inline-block;padding:8px 20px;border-radius:8px;'
        f'background-color:{hex_color}22;border:2px solid {hex_color};'
        f'color:{hex_color};font-size:1.3rem;font-weight:700;letter-spacing:1px;">'
        f'{grade}</div>'
    )


def render():
    st.title("Mean Reversion Stock Screener")
    st.caption(
        "Identify stocks with temporary price dislocations — "
        "down 15–40% on news while fundamentals remain intact."
    )

    # --- Sidebar settings ---
    with st.sidebar:
        st.header("Settings")
        wacc = st.slider(
            "DCF Discount Rate (WACC)",
            min_value=0.07, max_value=0.13, value=0.09, step=0.005,
            format="%.1f%%",
            help="9% is appropriate for large-cap investment-grade companies. "
                 "Use 11–13% for smaller or higher-risk stocks.",
        )
        wacc_display = wacc  # already decimal

        groq_api_key = st.text_input(
            "Groq API Key (optional)",
            type="password",
            help="Free API key from console.groq.com — enables AI-powered news classification.",
        )

        st.divider()
        st.caption("Sector PE benchmarks last updated: Q1 2025")

    # --- Ticker input ---
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        ticker_input = st.text_input(
            "Enter ticker symbol",
            value=st.session_state.get("prefill_ticker", ""),
            placeholder="e.g. UPS, UNH, INTU",
            label_visibility="collapsed",
        ).upper().strip()
    with col_btn:
        run_clicked = st.button("Analyze", type="primary", use_container_width=True)

    if not ticker_input:
        st.info("Enter a ticker symbol above and click **Analyze** to run the full setup screen.")
        _render_reference_examples()
        return

    if not run_clicked and "last_result" not in st.session_state:
        st.info("Click **Analyze** to run the screen.")
        return

    # --- Run analysis ---
    if run_clicked or st.session_state.get("last_ticker") != ticker_input:
        with st.spinner(f"Fetching data for **{ticker_input}**..."):
            result = screener.run(ticker_input, groq_api_key=groq_api_key or None)

        if result is None:
            st.error(
                f"Could not retrieve data for **{ticker_input}**. "
                "Please check the ticker symbol and try again."
            )
            return

        setup_score = scorer.score(result)
        fund_data   = fetcher.get_fundamentals(ticker_input)
        dcf_result  = dcf.run(
            ticker_input, result.current_price, fund_data or {},
            wacc=wacc_display,
        )
        prob_result = probability.estimate(setup_score, dcf_result)

        st.session_state["last_result"]     = result
        st.session_state["last_score"]      = setup_score
        st.session_state["last_dcf"]        = dcf_result
        st.session_state["last_prob"]       = prob_result
        st.session_state["last_ticker"]     = ticker_input
    else:
        result      = st.session_state["last_result"]
        setup_score = st.session_state["last_score"]
        dcf_result  = st.session_state["last_dcf"]
        prob_result = st.session_state["last_prob"]

    # --- Company header ---
    st.subheader(f"{result.company_name} ({result.ticker})")
    st.caption(f"{result.sector} · {result.industry}")

    if result.missing_fields:
        st.warning(
            f"Some data fields unavailable from Yahoo Finance: "
            f"{', '.join(result.missing_fields)}. "
            "Affected dimensions show a neutral score."
        )

    # --- Grade badge ---
    st.markdown(
        _grade_badge(setup_score.grade, setup_score.grade_color),
        unsafe_allow_html=True,
    )
    st.write("")  # spacer

    # --- Top metric cards ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Current Price", f"${result.current_price:,.2f}")
    with c2:
        decline_pct = result.decline_from_52w_high * 100
        st.metric(
            "Decline from 52W High",
            f"{decline_pct:.1f}%",
            delta=f"High: ${result.price_52w_high:,.2f}",
            delta_color="off",
        )
    with c3:
        if result.analyst_upside is not None:
            st.metric(
                "Analyst Upside",
                f"{result.analyst_upside * 100:.1f}%",
                delta=f"Target: ${result.mean_target:,.2f}" if result.mean_target else None,
                delta_color="normal",
            )
        else:
            st.metric("Analyst Upside", "N/A")
    with c4:
        st.metric("Setup Score", f"{setup_score.total_score:.2f} / 1.00")

    st.divider()

    # --- Charts row ---
    col_radar, col_gauge = st.columns([1, 1])

    with col_radar:
        st.plotly_chart(
            charts.build_radar_chart(setup_score.sub_scores_dict()),
            use_container_width=True,
        )

    with col_gauge:
        st.plotly_chart(
            charts.build_probability_gauge(
                prob_result["probability"],
                prob_result["label"],
                prob_result["color"],
            ),
            use_container_width=True,
        )
        st.caption(prob_result["description"])

    # --- Price history chart ---
    if result.price_history is not None:
        st.plotly_chart(
            charts.build_price_history(
                result.price_history,
                result.ticker,
                result.price_52w_high,
            ),
            use_container_width=True,
        )

    st.divider()

    # --- DCF section ---
    st.subheader("DCF Valuation")
    if dcf_result.error:
        st.warning(f"DCF unavailable: {dcf_result.error}")
    else:
        dcf_col1, dcf_col2 = st.columns([2, 1])
        with dcf_col1:
            scenarios = []
            for sc in [dcf_result.base, dcf_result.bull, dcf_result.bear]:
                if sc.intrinsic_value:
                    scenarios.append({
                        "label": sc.label,
                        "intrinsic_value": sc.intrinsic_value,
                        "margin_of_safety": sc.margin_of_safety,
                    })
            if scenarios:
                st.plotly_chart(
                    charts.build_dcf_bar(scenarios),
                    use_container_width=True,
                )
        with dcf_col2:
            st.markdown("**Assumptions**")
            st.markdown(f"- WACC: **{wacc_display*100:.1f}%**")
            st.markdown(f"- Growth rate: **{dcf_result.growth_rate_used*100:.1f}%** ({dcf_result.growth_source})")
            st.markdown(f"- Terminal growth: **{dcf_result.base.terminal_growth*100:.1f}%**")
            if dcf_result.base.margin_of_safety is not None:
                mos = dcf_result.base.margin_of_safety * 100
                color = "green" if mos > 0 else "red"
                st.markdown(
                    f"- Base margin of safety: "
                    f"<span style='color:{'#2ecc71' if mos>0 else '#e74c3c'}'>"
                    f"**{mos:+.1f}%**</span>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # --- News catalyst ---
    st.subheader("News Catalyst Assessment")
    catalyst_colors = {
        "confirmed_one_time":  "#2ecc71",
        "likely_one_time":     "#27ae60",
        "uncertain":           "#f39c12",
        "likely_structural":   "#e67e22",
        "structural_damage":   "#e74c3c",
    }
    c = catalyst_colors.get(result.news_label, "#4dabf7")
    st.markdown(
        f'<div style="padding:12px 16px;border-left:4px solid {c};'
        f'background:{c}18;border-radius:4px;">'
        f'<b style="color:{c}">{result.news_display}</b><br/>'
        f'<span style="color:rgba(255,255,255,0.75)">{result.news_reason}</span><br/>'
        f'<small style="color:rgba(255,255,255,0.4)">Source: {result.news_source}</small>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if result.headlines:
        with st.expander("Recent headlines used"):
            for h in result.headlines[:5]:
                st.markdown(f"- {h}")

    st.divider()

    # --- Scoring breakdown ---
    with st.expander("Scoring breakdown — click to expand"):
        sub = setup_score.sub_scores_dict()
        weight_map = {
            "Price Decline":     0.20,
            "PE vs Sector":      0.20,
            "Revenue Growth":    0.15,
            "Earnings Growth":   0.15,
            "Analyst Consensus": 0.15,
            "News Catalyst":     0.15,
        }
        for dim, score_val in sub.items():
            w = weight_map.get(dim, 0)
            col_a, col_b, col_c = st.columns([2, 4, 1])
            with col_a:
                st.markdown(f"**{dim}** (×{w:.0%})")
            with col_b:
                st.progress(score_val)
            with col_c:
                st.markdown(f"`{score_val:.2f}`")

        if setup_score.pe_negative:
            st.warning("PE ratio is negative — company is currently unprofitable.")
        if setup_score.eps_negative:
            st.warning("Latest EPS is negative — earnings score capped at 0.30.")

    # --- Raw data ---
    with st.expander("Raw data (verify inputs)"):
        st.json({
            "current_price":        result.current_price,
            "price_52w_high":       result.price_52w_high,
            "decline_from_52w_high": f"{result.decline_from_52w_high*100:.2f}%",
            "forward_pe":           result.forward_pe,
            "trailing_pe":          result.trailing_pe,
            "sector_avg_pe":        result.sector_avg_pe,
            "pe_discount_to_sector": (
                f"{result.pe_discount_to_sector*100:.2f}%"
                if result.pe_discount_to_sector is not None else None
            ),
            "revenue_qoq":          (
                f"{result.revenue_qoq*100:.2f}%"
                if result.revenue_qoq is not None else None
            ),
            "earnings_qoq":         (
                f"{result.earnings_qoq*100:.2f}%"
                if result.earnings_qoq is not None else None
            ),
            "consensus_rating":     result.consensus_rating,
            "mean_target":          result.mean_target,
            "analyst_upside":       (
                f"{result.analyst_upside*100:.2f}%"
                if result.analyst_upside is not None else None
            ),
            "news_label":           result.news_label,
            "missing_fields":       result.missing_fields,
        })

    # --- Log This Trade button ---
    st.divider()
    if st.button("Log This Trade →", type="secondary"):
        st.session_state["prefill_trade"] = {
            "ticker":              result.ticker,
            "company_name":        result.company_name,
            "score_at_entry":      setup_score.total_score,
            "grade_at_entry":      setup_score.grade.split()[0],  # STRONG / MODERATE / WEAK
            "dcf_margin_at_entry": (
                dcf_result.base.margin_of_safety
                if dcf_result and dcf_result.base.margin_of_safety else None
            ),
            "decline_at_entry":    result.decline_from_52w_high,
            "catalyst_type":       result.news_label,
            "entry_price":         result.current_price,
        }
        st.session_state["nav_page"] = "Trade Log"
        st.rerun()


def _render_reference_examples():
    st.divider()
    st.subheader("Reference Examples")
    st.caption(
        "These are the prototypical setups this tool is designed to identify. "
        "Try running them through the screener to see current scoring."
    )
    cols = st.columns(3)
    examples = [
        ("UPS", "2023 — Guidance cut on volume outlook", "25% decline, one-time guidance noise"),
        ("UNH", "2024 — Legal/regulatory overhang", "30% decline, core business intact"),
        ("INTU", "2024 — Macro guidance reset", "20% decline, platform still growing"),
    ]
    for col, (ticker, event, summary) in zip(cols, examples):
        with col:
            st.markdown(f"**{ticker}**")
            st.markdown(f"*{event}*")
            st.caption(summary)
