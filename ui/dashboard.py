"""
ui/dashboard.py — Stock Detail page (full analysis for a single ticker).

Renders the full analysis:
  1. Ticker input + Run button
  2. Custom metric cards (price, decline, analyst upside, score)
  3. Grade badge + probability gauge
  4. Radar chart (7 sub-scores including DCF MoS)
  5. Price history chart
  6. Auto-WACC display (replaces manual WACC slider)
  7. AI-powered DCF (or quantitative fallback)
  8. News catalyst assessment
  9. Raw data expander
  10. "Log This Trade" button
"""

import streamlit as st

from analysis import screener, scorer, probability
from analysis import wacc as wacc_module
from analysis.ai_dcf import run as ai_dcf_run
from data import fetcher
from ui import charts, styles


def render():
    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown(
        '<h1 style="margin-bottom:0;">Stock Detail Analysis</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:13.5px;color:rgba(255,255,255,0.45);margin-bottom:24px;">'
        'Identify stocks with temporary price dislocations — down 15–40% on news while fundamentals remain intact.'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Sidebar settings ──────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            '<div style="font-size:11px;font-weight:600;text-transform:uppercase;'
            'letter-spacing:1.2px;color:rgba(255,255,255,0.35);margin:16px 0 8px 16px;">AI Settings</div>',
            unsafe_allow_html=True,
        )
        claude_api_key = st.text_input(
            "Claude API Key (optional)",
            type="password",
            help=(
                "Anthropic API key enables AI-powered DCF. Claude claude-sonnet-4-6 reads the "
                "financials and selects growth rates autonomously. Get a key at console.anthropic.com."
            ),
            key="detail_claude_key",
        )
        groq_api_key = st.text_input(
            "Groq API Key (optional)",
            type="password",
            help="Free API key from console.groq.com — enables AI-powered news classification.",
            key="detail_groq_key",
        )
        st.divider()
        st.caption("WACC is auto-calculated from company fundamentals. No manual input needed.")
        st.caption("Sector PE benchmarks last updated: Q1 2025")

    # ── Ticker input ──────────────────────────────────────────────────────────
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        ticker_input = st.text_input(
            "ticker",
            value=st.session_state.get("prefill_ticker", ""),
            placeholder="Enter ticker symbol — e.g. SPY, UPS, UNH",
            label_visibility="collapsed",
        ).upper().strip()
    with col_btn:
        run_clicked = st.button("Analyze →", type="primary", use_container_width=True)

    if not ticker_input:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.info("Enter a ticker symbol above and click **Analyze →** to run the full setup screen.")
        _render_reference_examples()
        return

    if not run_clicked and "last_result" not in st.session_state:
        st.info("Click **Analyze →** to run the screen.")
        return

    # ── Run analysis ──────────────────────────────────────────────────────────
    if run_clicked or st.session_state.get("last_ticker") != ticker_input:
        with st.spinner(f"Fetching data for {ticker_input}…"):
            result = screener.run(ticker_input, groq_api_key=groq_api_key or None)

        if result is None:
            st.error(
                f"**Could not retrieve data for {ticker_input}.**\n\n"
                "Possible causes:\n"
                "- Invalid ticker symbol — double-check spelling (e.g. AAPL, MSFT, UPS)\n"
                "- Yahoo Finance rate limit — wait 30 seconds and click **Analyze →** again\n"
                "- No price history available for this symbol\n\n"
                "Try a well-known ticker like **AAPL** to confirm connectivity."
            )
            return

        with st.spinner("Calculating WACC and running DCF…"):
            fund_data = fetcher.get_fundamentals(ticker_input)
            try:
                wacc_result = wacc_module.calculate(ticker_input, fund_data or {})
            except Exception:
                wacc_result = wacc_module.default_wacc()
            try:
                dcf_result = ai_dcf_run(
                    symbol=ticker_input,
                    current_price=result.current_price,
                    fundamentals=fund_data or {},
                    wacc_result=wacc_result,
                    claude_api_key=claude_api_key or None,
                )
            except Exception:
                dcf_result = None

        # Score includes DCF MoS
        dcf_mos = (
            dcf_result.base.margin_of_safety
            if dcf_result and not dcf_result.error and dcf_result.base.margin_of_safety is not None
            else None
        )
        setup_score = scorer.score(result, dcf_margin_of_safety=dcf_mos)
        prob_result = probability.estimate(setup_score, dcf_result)

        st.session_state["last_result"]     = result
        st.session_state["last_score"]      = setup_score
        st.session_state["last_dcf"]        = dcf_result
        st.session_state["last_wacc"]       = wacc_result
        st.session_state["last_prob"]       = prob_result
        st.session_state["last_ticker"]     = ticker_input
        st.session_state["last_fund_data"]  = fund_data
    else:
        result      = st.session_state["last_result"]
        setup_score = st.session_state["last_score"]
        dcf_result  = st.session_state["last_dcf"]
        wacc_result = st.session_state["last_wacc"]
        prob_result = st.session_state["last_prob"]
        fund_data   = st.session_state.get("last_fund_data", {})

    # ── Company header ────────────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col_name, col_badge = st.columns([3, 1])
    with col_name:
        st.markdown(
            f'<div style="font-size:1.4rem;font-weight:700;letter-spacing:-0.3px;margin-bottom:2px;">'
            f'{result.company_name}'
            f'<span style="font-size:1rem;color:rgba(255,255,255,0.4);margin-left:10px;font-weight:400;">'
            f'{result.ticker}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-size:12.5px;color:rgba(255,255,255,0.4);margin-bottom:16px;">'
            f'{result.sector} · {result.industry}</div>',
            unsafe_allow_html=True,
        )
    with col_badge:
        st.markdown(
            styles.grade_badge(setup_score.grade, setup_score.grade_color),
            unsafe_allow_html=True,
        )

    if result.missing_fields:
        st.warning(
            f"Some data fields unavailable from Yahoo Finance: "
            f"{', '.join(result.missing_fields)}. "
            "Affected dimensions show a neutral score."
        )

    # ── Metric cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            styles.metric_card("Current Price", f"${result.current_price:,.2f}"),
            unsafe_allow_html=True,
        )
    with c2:
        decline_pct = result.decline_from_52w_high * 100
        st.markdown(
            styles.metric_card(
                "Decline from 52W High",
                f"{decline_pct:.1f}%",
                delta=f"Peak ${result.price_52w_high:,.2f}",
                delta_up=False,
            ),
            unsafe_allow_html=True,
        )
    with c3:
        if result.analyst_upside is not None:
            st.markdown(
                styles.metric_card(
                    "Analyst Upside",
                    f"{result.analyst_upside * 100:.1f}%",
                    delta=f"Target ${result.mean_target:,.2f}" if result.mean_target else "",
                    delta_up=result.analyst_upside > 0,
                ),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(styles.metric_card("Analyst Upside", "N/A"), unsafe_allow_html=True)
    with c4:
        st.markdown(
            styles.metric_card(
                "Setup Score",
                f"{setup_score.total_score:.2f}",
                delta=f"/ 1.00 · {setup_score.grade.split()[0]}",
                delta_up=setup_score.total_score >= 0.72,
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.divider()

    # ── Charts row ────────────────────────────────────────────────────────────
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

    # ── Price history ─────────────────────────────────────────────────────────
    if result.price_history is not None:
        st.plotly_chart(
            charts.build_price_history(result.price_history, result.ticker, result.price_52w_high),
            use_container_width=True,
        )

    st.divider()

    # ── Auto-WACC section ─────────────────────────────────────────────────────
    st.markdown(
        styles.section_header("Discount Rate (WACC)", "Auto-calculated from company fundamentals"),
        unsafe_allow_html=True,
    )

    w = wacc_result
    wacc_col1, wacc_col2, wacc_col3, wacc_col4 = st.columns(4)
    with wacc_col1:
        st.markdown(
            styles.metric_card("Base WACC", f"{w.wacc*100:.2f}%",
                               delta=f"Range: {w.wacc_low*100:.1f}%–{w.wacc_high*100:.1f}%"),
            unsafe_allow_html=True,
        )
    with wacc_col2:
        st.markdown(
            styles.metric_card("Beta", f"{w.beta:.2f}",
                               delta=f"Rf {w.risk_free_rate*100:.2f}% · ERP 5.5%"),
            unsafe_allow_html=True,
        )
    with wacc_col3:
        st.markdown(
            styles.metric_card("Cost of Equity", f"{w.cost_of_equity*100:.2f}%",
                               delta=f"Weight {w.equity_weight*100:.0f}%"),
            unsafe_allow_html=True,
        )
    with wacc_col4:
        st.markdown(
            styles.metric_card("After-tax CoD", f"{w.cost_of_debt_at*100:.2f}%",
                               delta=f"Tax rate {w.tax_rate*100:.0f}% · Weight {w.debt_weight*100:.0f}%"),
            unsafe_allow_html=True,
        )
    st.caption(f"Sources: {w.source_notes}")

    st.divider()

    # ── DCF section ───────────────────────────────────────────────────────────
    ai_badge = (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'background:{styles.ACCENT}22;border:1px solid {styles.ACCENT}66;'
        f'color:{styles.ACCENT};font-size:11px;font-weight:600;margin-left:10px;">'
        f'Powered by Claude claude-sonnet-4-6</span>'
        if dcf_result.ai_powered else
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);'
        f'color:rgba(255,255,255,0.4);font-size:11px;margin-left:10px;">'
        f'Quantitative (no AI key)</span>'
    )
    st.markdown(
        f'<div style="margin:8px 0 16px;">'
        f'<div style="font-size:16px;font-weight:700;padding-bottom:10px;'
        f'border-bottom:1px solid {styles.BORDER};color:rgba(255,255,255,0.95);">'
        f'DCF Valuation{ai_badge}</div>'
        f'<div style="font-size:13px;color:{styles.TEXT_MUTED};margin-top:4px;">'
        f'Two-stage discounted cash flow model · Base, Bull, Bear scenarios</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if dcf_result is None:
        st.warning("DCF unavailable: valuation model encountered an error. Screener results above are still valid.")
    elif dcf_result.error:
        st.warning(f"DCF unavailable: {dcf_result.error}")
    else:
        dcf_col1, dcf_col2 = st.columns([2, 1])
        with dcf_col1:
            scenarios = []
            for sc in [dcf_result.base, dcf_result.bull, dcf_result.bear]:
                if sc.intrinsic_value:
                    scenarios.append({
                        "label":            sc.label,
                        "intrinsic_value":  sc.intrinsic_value,
                        "margin_of_safety": sc.margin_of_safety,
                    })
            if scenarios:
                st.plotly_chart(charts.build_dcf_bar(scenarios), use_container_width=True)

        with dcf_col2:
            mos = dcf_result.base.margin_of_safety if dcf_result else None
            mos_color = styles.GREEN if mos and mos > 0 else styles.RED
            growth_label = (
                "Claude-selected" if dcf_result and dcf_result.ai_powered
                else (dcf_result.growth_source.replace("_", " ") if dcf_result else "N/A")
            )
            st.markdown(
                f'<div style="background:{styles.SURFACE};border:1px solid {styles.BORDER};'
                f'border-radius:12px;padding:20px 22px;margin-top:8px;">'
                f'<div style="font-size:11px;font-weight:600;text-transform:uppercase;'
                f'letter-spacing:0.8px;color:{styles.TEXT_MUTED};margin-bottom:14px;">Assumptions</div>'
                f'<div style="font-size:13px;line-height:2;color:rgba(255,255,255,0.85);">'
                f'WACC &nbsp;<b>{wacc_result.wacc*100:.2f}%</b> '
                f'<span style="color:{styles.TEXT_MUTED};font-size:11px;">[{wacc_result.wacc_low*100:.1f}%–{wacc_result.wacc_high*100:.1f}%]</span><br>'
                f'Growth &nbsp;<b>{dcf_result.growth_rate_used*100:.1f}%</b>'
                f'<span style="color:{styles.TEXT_MUTED};font-size:11px;"> ({growth_label})</span><br>'
                f'Terminal &nbsp;<b>{dcf_result.base.terminal_growth*100:.1f}%</b><br>'
                + (
                    f'Base MoS &nbsp;<b style="color:{mos_color};">'
                    f'{mos*100:+.1f}%</b>'
                    if mos is not None else ""
                )
                + f'</div></div>',
                unsafe_allow_html=True,
            )

        # AI assessment block
        if dcf_result and dcf_result.ai_powered and dcf_result.ai_assessment:
            conf_color = {
                "high":   styles.GREEN,
                "medium": styles.YELLOW,
                "low":    styles.RED,
            }.get(dcf_result.ai_confidence, styles.ACCENT)
            st.markdown(
                f'<div style="margin-top:16px;padding:14px 18px;'
                f'background:{styles.ACCENT}0d;border-left:3px solid {styles.ACCENT};'
                f'border-radius:0 10px 10px 0;">'
                f'<div style="font-size:11px;font-weight:600;text-transform:uppercase;'
                f'letter-spacing:0.8px;color:{styles.ACCENT};margin-bottom:8px;">'
                f'Claude Assessment · Confidence: <span style="color:{conf_color};">'
                f'{dcf_result.ai_confidence.upper()}</span></div>'
                f'<div style="font-size:13px;color:rgba(255,255,255,0.85);line-height:1.6;">'
                f'{dcf_result.ai_assessment}</div>'
                + (
                    f'<div style="font-size:11.5px;color:{styles.TEXT_MUTED};margin-top:8px;">'
                    f'Growth rationale: {dcf_result.ai_growth_note}</div>'
                    if dcf_result.ai_growth_note else ""
                )
                + f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── News catalyst ─────────────────────────────────────────────────────────
    st.markdown(styles.section_header("News Catalyst Assessment"), unsafe_allow_html=True)

    catalyst_colors = {
        "confirmed_one_time":  styles.GREEN,
        "likely_one_time":     "#40c057",
        "uncertain":           styles.YELLOW,
        "likely_structural":   "#fd7e14",
        "structural_damage":   styles.RED,
    }
    c = catalyst_colors.get(result.news_label, styles.ACCENT)
    st.markdown(
        styles.catalyst_box(result.news_display, result.news_reason, result.news_source, c),
        unsafe_allow_html=True,
    )

    if result.headlines:
        with st.expander("Recent headlines used for classification"):
            for h in result.headlines[:5]:
                st.markdown(f"- {h}")

    st.divider()

    # ── Scoring breakdown ─────────────────────────────────────────────────────
    with st.expander("Scoring Breakdown — click to expand"):
        sub = setup_score.sub_scores_dict()
        weight_map = {
            "Price Decline":        0.20,
            "PE vs Sector":         0.15,
            "Revenue Growth":       0.12,
            "Earnings Growth":      0.12,
            "Analyst Consensus":    0.13,
            "News Catalyst":        0.13,
            "DCF Margin of Safety": 0.15,
        }
        for dim, score_val in sub.items():
            w = weight_map.get(dim, 0)
            col_a, col_b, col_c = st.columns([2, 4, 1])
            with col_a:
                st.markdown(
                    f'<div style="font-size:13px;font-weight:600;padding-top:6px;">{dim}</div>'
                    f'<div style="font-size:11px;color:{styles.TEXT_MUTED};">weight ×{w:.0%}</div>',
                    unsafe_allow_html=True,
                )
            with col_b:
                st.progress(score_val)
            with col_c:
                st.markdown(
                    f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;'
                    f'padding-top:6px;text-align:right;">{score_val:.2f}</div>',
                    unsafe_allow_html=True,
                )

        if setup_score.pe_negative:
            st.warning("PE ratio is negative — company is currently unprofitable.")
        if setup_score.eps_negative:
            st.warning("Latest EPS is negative — earnings score capped at 0.30.")

    # ── Raw data ──────────────────────────────────────────────────────────────
    with st.expander("Raw data (verify inputs)"):
        mos_val = (
            dcf_result.base.margin_of_safety
            if dcf_result and not dcf_result.error and dcf_result.base.margin_of_safety is not None
            else None
        )
        st.json({
            "current_price":         result.current_price,
            "price_52w_high":        result.price_52w_high,
            "decline_from_52w_high": f"{result.decline_from_52w_high*100:.2f}%",
            "forward_pe":            result.forward_pe,
            "trailing_pe":           result.trailing_pe,
            "sector_avg_pe":         result.sector_avg_pe,
            "pe_discount_to_sector": (
                f"{result.pe_discount_to_sector*100:.2f}%"
                if result.pe_discount_to_sector is not None else None
            ),
            "revenue_qoq":  f"{result.revenue_qoq*100:.2f}%" if result.revenue_qoq is not None else None,
            "earnings_qoq": f"{result.earnings_qoq*100:.2f}%" if result.earnings_qoq is not None else None,
            "consensus_rating": result.consensus_rating,
            "mean_target":      result.mean_target,
            "analyst_upside":   (
                f"{result.analyst_upside*100:.2f}%"
                if result.analyst_upside is not None else None
            ),
            "news_label":     result.news_label,
            "missing_fields": result.missing_fields,
            "auto_wacc":      f"{wacc_result.wacc*100:.2f}%",
            "wacc_range":     f"{wacc_result.wacc_low*100:.2f}%–{wacc_result.wacc_high*100:.2f}%",
            "wacc_sources":   wacc_result.source_notes,
            "dcf_margin_of_safety": f"{mos_val*100:.2f}%" if mos_val else None,
            "dcf_ai_powered": dcf_result.ai_powered if dcf_result else False,
        })

    # ── Log This Trade ────────────────────────────────────────────────────────
    st.divider()
    col_log, _ = st.columns([1, 3])
    with col_log:
        if st.button("Log This Trade →", type="secondary", use_container_width=True):
            mos_val = (
                dcf_result.base.margin_of_safety
                if dcf_result and not dcf_result.error and dcf_result.base.margin_of_safety is not None
                else None
            )
            st.session_state["prefill_trade"] = {
                "ticker":              result.ticker,
                "company_name":        result.company_name,
                "score_at_entry":      setup_score.total_score,
                "grade_at_entry":      setup_score.grade.split()[0],
                "dcf_margin_at_entry": mos_val,
                "decline_at_entry":    result.decline_from_52w_high,
                "catalyst_type":       result.news_label,
                "entry_price":         result.current_price,
            }
            st.session_state["nav_page"] = "Trade Log"
            st.rerun()


def _render_reference_examples():
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown(
        styles.section_header(
            "Reference Examples",
            "Prototypical setups this tool is designed to identify. Try running them through the screener.",
        ),
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    examples = [
        ("UPS",  "2023 Guidance Cut",        "Volume outlook reset · 25% decline · One-time noise",    styles.GREEN),
        ("UNH",  "2024 Regulatory Overhang", "Legal/political pressure · 30% decline · Core intact",   styles.YELLOW),
        ("INTU", "2024 Macro Reset",         "Guidance cut · 20% decline · Platform still growing",    styles.ACCENT),
    ]
    for col, (ticker, event, summary, color) in zip(cols, examples):
        with col:
            st.markdown(
                f'<div style="background:{styles.SURFACE};border:1px solid {styles.BORDER};'
                f'border-radius:12px;padding:18px 20px;height:100%;">'
                f'<div style="font-size:1.3rem;font-weight:700;letter-spacing:-0.5px;margin-bottom:4px;'
                f'color:{color};">{ticker}</div>'
                f'<div style="font-size:13px;font-weight:600;color:rgba(255,255,255,0.85);margin-bottom:8px;">{event}</div>'
                f'<div style="font-size:12px;color:{styles.TEXT_MUTED};line-height:1.5;">{summary}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
