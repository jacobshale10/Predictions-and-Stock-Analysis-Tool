"""
ui/backtest_ui.py — Backtest summary page.

Shows aggregate performance statistics across all closed trades:
  - P&L scatter vs score at entry
  - Win rate by setup grade
  - Summary stats table
"""

import streamlit as st
import pandas as pd

from database import db
from ui import charts


def render():
    st.title("Backtest Summary")
    st.caption(
        "Aggregate performance across all closed trades. "
        "The more trades logged, the more statistically meaningful these results become. "
        "Target: 30+ trades for reliable signal."
    )

    db.init_db()
    trades = db.get_all_trades()

    if not trades:
        st.info(
            "No trades logged yet. Once you've entered and exited trades via the Trade Log, "
            "the backtest results will appear here."
        )
        return

    df = pd.DataFrame(trades)
    closed = df[df["exit_date"].notna()].copy()
    open_count = len(df) - len(closed)

    # --- Summary stats ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Trades Logged", len(df))
    with col2:
        st.metric("Open Positions", open_count)
    with col3:
        st.metric("Closed Trades", len(closed))
    with col4:
        if not closed.empty and "pnl_pct" in closed.columns:
            win_rate = (closed["pnl_pct"] > 0).mean() * 100
            st.metric("Win Rate (Closed)", f"{win_rate:.0f}%")
        else:
            st.metric("Win Rate (Closed)", "N/A")

    if closed.empty:
        st.info("No closed trades yet — exit trades in the Trade Log to see P&L analysis.")
        return

    st.divider()

    # --- Charts ---
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(charts.build_pnl_scatter(df), use_container_width=True)
    with chart_col2:
        st.plotly_chart(charts.build_win_rate_bar(df), use_container_width=True)

    st.divider()

    # --- Detailed stats by grade ---
    st.subheader("Performance by Setup Grade")
    if "grade_at_entry" in closed.columns and "pnl_pct" in closed.columns:
        summary = closed.groupby("grade_at_entry").agg(
            Count=("pnl_pct", "count"),
            Win_Rate=("pnl_pct", lambda x: f"{(x > 0).mean()*100:.0f}%"),
            Avg_PnL=("pnl_pct", lambda x: f"{x.mean()*100:+.1f}%"),
            Median_PnL=("pnl_pct", lambda x: f"{x.median()*100:+.1f}%"),
            Best=("pnl_pct", lambda x: f"{x.max()*100:+.1f}%"),
            Worst=("pnl_pct", lambda x: f"{x.min()*100:+.1f}%"),
        ).reset_index()
        st.dataframe(summary.rename(columns={
            "grade_at_entry": "Grade",
            "Win_Rate": "Win Rate",
            "Avg_PnL": "Avg P&L",
            "Median_PnL": "Median P&L",
        }), use_container_width=True, hide_index=True)

    # --- Holding period analysis ---
    st.subheader("Holding Period Analysis")
    if "holding_days" in closed.columns:
        hold_col1, hold_col2, hold_col3 = st.columns(3)
        valid_hold = closed["holding_days"].dropna()
        if not valid_hold.empty:
            with hold_col1:
                st.metric("Avg Holding Days", f"{valid_hold.mean():.0f}")
            with hold_col2:
                st.metric("Median Holding Days", f"{valid_hold.median():.0f}")
            with hold_col3:
                winners = closed[closed["pnl_pct"] > 0]["holding_days"].dropna()
                st.metric("Avg Winner Hold", f"{winners.mean():.0f}" if not winners.empty else "N/A")

    # --- Catalyst type breakdown ---
    st.subheader("Performance by Catalyst Type")
    if "catalyst_type" in closed.columns and "pnl_pct" in closed.columns:
        cat_summary = closed.groupby("catalyst_type").agg(
            Count=("pnl_pct", "count"),
            Win_Rate=("pnl_pct", lambda x: f"{(x > 0).mean()*100:.0f}%"),
            Avg_PnL=("pnl_pct", lambda x: f"{x.mean()*100:+.1f}%"),
        ).reset_index()
        st.dataframe(cat_summary.rename(columns={
            "catalyst_type": "Catalyst Type",
            "Win_Rate": "Win Rate",
            "Avg_PnL": "Avg P&L",
        }), use_container_width=True, hide_index=True)

    # --- All closed trades detail ---
    with st.expander("All closed trades — detailed view"):
        show_df = closed[[
            "ticker", "entry_date", "entry_price", "exit_date", "exit_price",
            "pnl_pct", "holding_days", "score_at_entry", "grade_at_entry",
            "catalyst_type", "exit_reason",
        ]].copy()
        show_df["pnl_pct"] = show_df["pnl_pct"].apply(lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "—")
        show_df["entry_price"] = show_df["entry_price"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "—")
        show_df["exit_price"]  = show_df["exit_price"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "—")
        st.dataframe(show_df, use_container_width=True, hide_index=True)
