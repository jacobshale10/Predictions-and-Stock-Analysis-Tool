"""
ui/charts.py — All Plotly figure builders.
No business logic lives here — only rendering.
Every function accepts plain data and returns a plotly.graph_objects.Figure.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Optional


def build_radar_chart(sub_scores: dict) -> go.Figure:
    """
    Spider/radar chart of the 6 scoring dimensions.
    sub_scores: dict of {dimension_name: score_0_to_1}
    """
    categories = list(sub_scores.keys())
    values     = [round(v * 100, 1) for v in sub_scores.values()]
    # Close the polygon
    categories_closed = categories + [categories[0]]
    values_closed     = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=categories_closed,
        fill="toself",
        fillcolor="rgba(0, 150, 255, 0.15)",
        line=dict(color="rgba(0, 150, 255, 0.9)", width=2),
        name="Setup Score",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                ticksuffix="%",
                gridcolor="rgba(255,255,255,0.15)",
                tickcolor="rgba(255,255,255,0.5)",
            ),
            angularaxis=dict(
                gridcolor="rgba(255,255,255,0.15)",
                tickcolor="rgba(255,255,255,0.5)",
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(l=60, r=60, t=40, b=40),
        height=350,
    )
    return fig


def build_price_history(
    history: pd.DataFrame,
    ticker: str,
    price_52w_high: float,
    entry_price: Optional[float] = None,
) -> go.Figure:
    """
    1-year price chart with 52-week high line and optional entry marker.
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=history.index,
        y=history["Close"],
        mode="lines",
        name="Price",
        line=dict(color="#4dabf7", width=2),
    ))

    # 52-week high horizontal line
    fig.add_hline(
        y=price_52w_high,
        line_dash="dash",
        line_color="rgba(255,200,100,0.6)",
        annotation_text=f"52W High ${price_52w_high:.2f}",
        annotation_position="top left",
        annotation_font_color="rgba(255,200,100,0.9)",
    )

    # Entry price marker
    if entry_price:
        fig.add_hline(
            y=entry_price,
            line_dash="dot",
            line_color="rgba(100,255,150,0.7)",
            annotation_text=f"Entry ${entry_price:.2f}",
            annotation_position="bottom right",
            annotation_font_color="rgba(100,255,150,0.9)",
        )

    fig.update_layout(
        title=f"{ticker} — 1 Year Price History",
        xaxis_title=None,
        yaxis_title="Price (USD)",
        yaxis_tickprefix="$",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,20,30,0.6)",
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        height=320,
        margin=dict(l=60, r=20, t=50, b=40),
    )
    return fig


def build_probability_gauge(probability: float, label: str, color: str) -> go.Figure:
    """
    Gauge chart for the setup probability (0–100%).
    """
    color_map = {"green": "#2ecc71", "orange": "#f39c12", "red": "#e74c3c"}
    gauge_color = color_map.get(color, "#4dabf7")
    pct = round(probability * 100, 1)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": "%", "font": {"size": 32, "color": gauge_color}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "white"},
            "bar":  {"color": gauge_color, "thickness": 0.3},
            "bgcolor": "rgba(255,255,255,0.05)",
            "borderwidth": 0,
            "steps": [
                {"range": [0,   45],  "color": "rgba(231, 76, 60, 0.2)"},
                {"range": [45,  68],  "color": "rgba(243, 156, 18, 0.2)"},
                {"range": [68, 100],  "color": "rgba(46, 204, 113, 0.2)"},
            ],
            "threshold": {
                "line": {"color": gauge_color, "width": 3},
                "thickness": 0.75,
                "value": pct,
            },
        },
        title={"text": f"Recovery Probability — {label}", "font": {"size": 14}},
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
        height=250,
        margin=dict(l=30, r=30, t=30, b=10),
    )
    return fig


def build_dcf_bar(scenarios: list[dict]) -> go.Figure:
    """
    Horizontal bar chart showing Base/Bull/Bear intrinsic values vs current price.
    scenarios: list of {'label': str, 'intrinsic_value': float, 'margin_of_safety': float}
    current_price: shown as a vertical reference line
    """
    labels = [s["label"] for s in scenarios]
    values = [s["intrinsic_value"] for s in scenarios]
    colors = ["#4dabf7", "#2ecc71", "#e74c3c"]  # Base, Bull, Bear

    fig = go.Figure()
    for i, (lbl, val, col) in enumerate(zip(labels, values, colors)):
        mos = scenarios[i].get("margin_of_safety", 0) or 0
        mos_pct = f"{mos*100:+.1f}%"
        fig.add_trace(go.Bar(
            name=lbl,
            x=[val],
            y=[lbl],
            orientation="h",
            marker_color=col,
            text=f"${val:,.0f}  ({mos_pct} MoS)",
            textposition="outside",
            textfont=dict(color="white"),
        ))

    fig.update_layout(
        title="DCF Intrinsic Value — Base / Bull / Bear",
        xaxis_title="Intrinsic Value Per Share (USD)",
        xaxis_tickprefix="$",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,20,30,0.6)",
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        barmode="group",
        showlegend=False,
        height=220,
        margin=dict(l=80, r=120, t=50, b=40),
    )
    return fig


def build_pnl_scatter(trades_df: pd.DataFrame) -> go.Figure:
    """
    Scatter of P&L % vs score_at_entry for closed trades.
    """
    closed = trades_df[trades_df["exit_date"].notna()].copy()

    if closed.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No closed trades yet — P&L data will appear after your first exit.",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=14, color="gray"),
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(20,20,30,0.6)",
            height=300,
        )
        return fig

    closed["pnl_pct_display"] = closed["pnl_pct"] * 100

    color_vals = closed["pnl_pct_display"].tolist()
    fig = go.Figure(go.Scatter(
        x=closed["score_at_entry"].tolist(),
        y=closed["pnl_pct_display"].tolist(),
        mode="markers+text",
        text=closed["ticker"].tolist(),
        textposition="top center",
        marker=dict(
            color=color_vals,
            colorscale=[[0, "#e74c3c"], [0.5, "#f39c12"], [1, "#2ecc71"]],
            size=12,
            showscale=True,
            colorbar=dict(title="P&L %", ticksuffix="%"),
        ),
    ))

    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    fig.add_vline(x=0.72, line_dash="dot", line_color="rgba(100,200,100,0.4)",
                  annotation_text="Strong Setup threshold", annotation_position="top right")

    fig.update_layout(
        title="P&L % vs Score at Entry (Closed Trades)",
        xaxis_title="Score at Entry",
        yaxis_title="P&L %",
        yaxis_ticksuffix="%",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,20,30,0.6)",
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)", range=[0, 1]),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        height=350,
        margin=dict(l=60, r=20, t=50, b=40),
    )
    return fig


def build_win_rate_bar(trades_df: pd.DataFrame) -> go.Figure:
    """
    Win rate % by grade at entry (STRONG / MODERATE / WEAK).
    """
    closed = trades_df[trades_df["exit_date"].notna()].copy()
    if closed.empty:
        fig = go.Figure()
        fig.add_annotation(text="No closed trades yet.", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=14, color="gray"))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=250)
        return fig

    closed["win"] = closed["pnl_pct"] > 0
    summary = closed.groupby("grade_at_entry").agg(
        win_rate=("win", "mean"),
        count=("win", "count"),
    ).reset_index()

    colors = {"STRONG SETUP": "#2ecc71", "MODERATE SETUP": "#f39c12", "WEAK SETUP": "#e74c3c"}
    bar_colors = [colors.get(g, "#4dabf7") for g in summary["grade_at_entry"]]

    fig = go.Figure(go.Bar(
        x=summary["grade_at_entry"].tolist(),
        y=(summary["win_rate"] * 100).tolist(),
        text=[f"{wr*100:.0f}% ({c} trades)" for wr, c in zip(summary["win_rate"], summary["count"])],
        textposition="outside",
        marker_color=bar_colors,
    ))

    fig.add_hline(y=50, line_dash="dash", line_color="rgba(255,255,255,0.3)",
                  annotation_text="50% breakeven", annotation_position="right")

    fig.update_layout(
        title="Win Rate by Setup Grade",
        yaxis_title="Win Rate %",
        yaxis_range=[0, 110],
        yaxis_ticksuffix="%",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,20,30,0.6)",
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        showlegend=False,
        height=280,
        margin=dict(l=60, r=20, t=50, b=40),
    )
    return fig
