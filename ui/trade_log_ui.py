"""
ui/trade_log_ui.py — Trade log CRUD interface.

Two sections:
  1. Add new trade form (pre-populated from dashboard if "Log This Trade" was clicked)
  2. Trade history table with live P&L
"""

import streamlit as st
import pandas as pd
from datetime import date

from database import db
from data import fetcher
from ui import styles


def render():
    st.markdown('<h1 style="margin-bottom:0;">Trade Log</h1>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:13.5px;color:rgba(255,255,255,0.45);margin-bottom:24px;">'
        f'Track entries, exits, and performance for your mean reversion setups.'
        f'</div>',
        unsafe_allow_html=True,
    )

    db.init_db()

    _render_add_form()
    st.divider()
    _render_trade_history()


def _render_add_form():
    st.markdown(styles.section_header("Log New Trade"), unsafe_allow_html=True)

    # Pre-fill from dashboard "Log This Trade" button
    prefill = st.session_state.pop("prefill_trade", {})

    with st.form("add_trade_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            ticker = st.text_input(
                "Ticker *",
                value=prefill.get("ticker", ""),
                placeholder="e.g. UPS, SPY, AAPL",
            ).upper().strip()
            company_name = st.text_input(
                "Company Name",
                value=prefill.get("company_name", ""),
            )
            entry_date = st.date_input(
                "Entry Date *",
                value=date.today(),
            )
            entry_price = st.number_input(
                "Entry Price (USD) *",
                value=max(0.01, float(prefill.get("entry_price", 0.01))),
                min_value=0.01,
                format="%.2f",
            )

        with col2:
            position_size = st.number_input(
                "Position Size (USD, optional)",
                value=0.0,
                min_value=0.0,
                format="%.0f",
                help="Dollar amount invested. Leave at 0 to skip.",
            )
            catalyst_options = [
                "confirmed_one_time",
                "likely_one_time",
                "uncertain",
                "likely_structural",
                "structural_damage",
            ]
            catalyst_prefill = prefill.get("catalyst_type", "uncertain")
            catalyst_idx = catalyst_options.index(catalyst_prefill) if catalyst_prefill in catalyst_options else 2
            catalyst_type = st.selectbox(
                "Catalyst Classification",
                options=catalyst_options,
                index=catalyst_idx,
                help="Override the automatic news classification with your own judgment.",
            )
            score_at_entry = st.number_input(
                "Setup Score at Entry",
                value=float(prefill.get("score_at_entry", 0.0)),
                min_value=0.0,
                max_value=1.0,
                format="%.3f",
                help="Pulled automatically from the Screener page.",
            )
            grade_options = ["STRONG", "MODERATE", "WEAK", ""]
            grade_prefill = prefill.get("grade_at_entry", "")
            grade_idx = grade_options.index(grade_prefill) if grade_prefill in grade_options else 3
            grade_at_entry = st.selectbox("Grade at Entry", options=grade_options, index=grade_idx)

        thesis_notes = st.text_area(
            "Thesis Notes",
            placeholder="Why are you entering this trade? What is the catalyst type? What is your exit thesis?",
            height=100,
        )

        submitted = st.form_submit_button("Save Trade →", type="primary")

        if submitted:
            if not ticker:
                st.error("Ticker is required.")
            elif entry_price <= 0:
                st.error("Entry price must be greater than zero.")
            else:
                db.insert_trade(
                    ticker=ticker,
                    entry_date=str(entry_date),
                    entry_price=entry_price,
                    company_name=company_name or None,
                    position_size_usd=position_size if position_size > 0 else None,
                    score_at_entry=score_at_entry if score_at_entry > 0 else None,
                    grade_at_entry=grade_at_entry or None,
                    dcf_margin_at_entry=prefill.get("dcf_margin_at_entry"),
                    decline_at_entry=prefill.get("decline_at_entry"),
                    catalyst_type=catalyst_type,
                    thesis_notes=thesis_notes or None,
                )
                st.success(f"Trade logged: **{ticker}** @ ${entry_price:.2f}")
                st.rerun()


def _render_trade_history():
    st.markdown(styles.section_header("Trade History"), unsafe_allow_html=True)

    trades = db.get_all_trades()
    if not trades:
        st.info("No trades logged yet. Use the form above to add your first trade.")
        return

    df = pd.DataFrame(trades)

    # Live P&L for open trades
    open_mask = df["exit_date"].isna()
    if open_mask.any():
        with st.spinner("Fetching live prices for open trades…"):
            for idx, row in df[open_mask].iterrows():
                live_price = fetcher.get_current_price(row["ticker"])
                if live_price and row["entry_price"]:
                    df.at[idx, "live_pnl_pct"] = (live_price - row["entry_price"]) / row["entry_price"]
                    df.at[idx, "live_price"]    = live_price

    # Display columns
    display_cols = [
        "id", "ticker", "company_name", "entry_date", "entry_price",
        "score_at_entry", "grade_at_entry", "catalyst_type",
        "exit_date", "exit_price", "exit_reason", "pnl_pct",
    ]
    if "live_pnl_pct" in df.columns:
        display_cols.append("live_pnl_pct")

    display_df = df[[c for c in display_cols if c in df.columns]].copy()

    for pct_col in ["pnl_pct", "live_pnl_pct"]:
        if pct_col in display_df.columns:
            display_df[pct_col] = display_df[pct_col].apply(
                lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "—"
            )

    for price_col in ["entry_price", "exit_price"]:
        if price_col in display_df.columns:
            display_df[price_col] = display_df[price_col].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else "—"
            )

    if "score_at_entry" in display_df.columns:
        display_df["score_at_entry"] = display_df["score_at_entry"].apply(
            lambda x: f"{x:.3f}" if pd.notna(x) else "—"
        )

    st.dataframe(
        display_df.rename(columns={
            "id":             "ID",
            "ticker":         "Ticker",
            "company_name":   "Company",
            "entry_date":     "Entry Date",
            "entry_price":    "Entry Price",
            "score_at_entry": "Score",
            "grade_at_entry": "Grade",
            "catalyst_type":  "Catalyst",
            "exit_date":      "Exit Date",
            "exit_price":     "Exit Price",
            "exit_reason":    "Exit Reason",
            "pnl_pct":        "P&L %",
            "live_pnl_pct":   "Live P&L %",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # Close a trade
    open_trades = [t for t in trades if not t.get("exit_date")]
    if open_trades:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(styles.section_header("Close a Trade"), unsafe_allow_html=True)
        with st.form("close_trade_form"):
            trade_options = {
                f"#{t['id']} {t['ticker']} @ ${t['entry_price']:.2f} ({t['entry_date']})": t["id"]
                for t in open_trades
            }
            selected_label = st.selectbox("Select open trade to close", options=list(trade_options.keys()))
            trade_id = trade_options[selected_label]

            col1, col2 = st.columns(2)
            with col1:
                exit_date  = st.date_input("Exit Date", value=date.today())
                exit_price = st.number_input("Exit Price (USD)", min_value=0.01, value=1.0, format="%.2f")
            with col2:
                exit_reason = st.selectbox(
                    "Exit Reason",
                    ["target_hit", "stop_loss", "thesis_broken", "other"],
                )
                review_notes = st.text_area("Post-Trade Review Notes", height=80)

            close_submitted = st.form_submit_button("Record Exit →", type="primary")
            if close_submitted:
                db.update_trade_exit(
                    trade_id=trade_id,
                    exit_date=str(exit_date),
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    review_notes=review_notes or None,
                )
                st.success("Trade exit recorded.")
                st.rerun()

    # Delete a trade
    with st.expander("Delete a trade (permanent)"):
        all_options = {
            f"#{t['id']} {t['ticker']} ({t['entry_date']})": t["id"]
            for t in trades
        }
        del_label = st.selectbox("Select trade to delete", options=list(all_options.keys()), key="del_sel")
        if st.button("Delete permanently", type="secondary"):
            db.delete_trade(all_options[del_label])
            st.warning("Trade deleted.")
            st.rerun()
