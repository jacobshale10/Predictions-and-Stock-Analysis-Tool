"""
ui/charts.py — All Plotly figure builders.
No business logic lives here — only rendering.
Every function accepts plain data and returns a plotly.graph_objects.Figure.
"""

import plotly.graph_objects as go
import pandas as pd
from typing import Optional

# ── Consistent palette (mirrors styles.py) ──────────────────────────────────
ACCENT   = "#00d4aa"
BLUE     = "#4dabf7"
RED      = "#ff6b6b"
YELLOW   = "#ffd93d"
GREEN    = "#51cf66"
ORANGE   = "#fd7e14"
SURFACE  = "rgba(22, 27, 34, 0.8)"
GRID     = "rgba(255,255,255,0.06)"
FONT     = "Inter, -apple-system, sans-serif"


def _base_layout(**kwargs) -> dict:
    """Shared layout defaults for all charts."""
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, color="rgba(255,255,255,0.82)", size=12),
        margin=dict(l=60, r=30, t=50, b=40),
        **kwargs,
    )


def build_radar_chart(sub_scores: dict) -> go.Figure:
    """Spider/radar chart of the 6 scoring dimensions."""
    categories = list(sub_scores.keys())
    values     = [round(v * 100, 1) for v in sub_scores.values()]
    categories_closed = categories + [categories[0]]
    values_closed     = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=categories_closed,
        fill="toself",
        fillcolor=f"{ACCENT}1a",
        line=dict(color=ACCENT, width=2.5),
        marker=dict(size=5, color=ACCENT),
        name="Setup Score",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                ticksuffix="%",
                gridcolor=GRID,
                tickcolor="rgba(255,255,255,0.3)",
                tickfont=dict(size=10, color="rgba(255,255,255,0.4)"),
                linecolor=GRID,
            ),
            angularaxis=dict(
                gridcolor=GRID,
                tickfont=dict(size=11, family=FONT, color="rgba(255,255,255,0.75)"),
                linecolor=GRID,
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        title=dict(text="Setup Score Breakdown", font=dict(size=13, color="rgba(255,255,255,0.5)"), x=0.5),
        margin=dict(l=60, r=60, t=50, b=40),
        height=360,
        font=dict(family=FONT),
    )
    return fig


def build_price_history(
    history: pd.DataFrame,
    ticker: str,
    price_52w_high: float,
    entry_price: Optional[float] = None,
) -> go.Figure:
    """1-year price chart with 52-week high line and optional entry marker."""
    fig = go.Figure()

    # Fill area under price line
    fig.add_trace(go.Scatter(
        x=history.index,
        y=history["Close"],
        mode="lines",
        name=ticker,
        line=dict(color=ACCENT, width=2),
        fill="tozeroy",
        fillcolor=f"{ACCENT}0d",
    ))

    # 52-week high horizontal line
    fig.add_hline(
        y=price_52w_high,
        line_dash="dash",
        line_color=f"{YELLOW}88",
        line_width=1.5,
        annotation_text=f"52W High  ${price_52w_high:.2f}",
        annotation_position="top left",
        annotation_font=dict(color=YELLOW, size=11),
    )

    if entry_price:
        fig.add_hline(
            y=entry_price,
            line_dash="dot",
            line_color=f"{GREEN}99",
            line_width=1.5,
            annotation_text=f"Entry  ${entry_price:.2f}",
            annotation_position="bottom right",
            annotation_font=dict(color=GREEN, size=11),
        )

    fig.update_layout(
        **_base_layout(
            title=dict(text=f"{ticker} · 1-Year Price History", font=dict(size=13), x=0),
            xaxis=dict(gridcolor=GRID, showline=False, zeroline=False),
            yaxis=dict(gridcolor=GRID, tickprefix="$", showline=False, zeroline=False),
            height=300,
            margin=dict(l=70, r=20, t=50, b=30),
            hovermode="x unified",
        )
    )
    return fig


def build_probability_gauge(probability: float, label: str, color: str) -> go.Figure:
    """Gauge chart for the setup probability (0–100%)."""
    palette = {"green": GREEN, "orange": YELLOW, "red": RED}
    gauge_color = palette.get(color, ACCENT)
    pct = round(probability * 100, 1)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number=dict(suffix="%", font=dict(size=40, color=gauge_color, family=FONT)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor="rgba(255,255,255,0.3)", tickfont=dict(size=10)),
            bar=dict(color=gauge_color, thickness=0.28),
            bgcolor="rgba(255,255,255,0.04)",
            borderwidth=0,
            steps=[
                dict(range=[0,  45],  color=f"{RED}22"),
                dict(range=[45, 68],  color=f"{YELLOW}22"),
                dict(range=[68, 100], color=f"{GREEN}22"),
            ],
            threshold=dict(
                line=dict(color=gauge_color, width=3),
                thickness=0.8,
                value=pct,
            ),
        ),
        title=dict(
            text=f"Recovery Probability<br><span style='font-size:12px;color:rgba(255,255,255,0.5)'>{label}</span>",
            font=dict(size=13, color="rgba(255,255,255,0.7)", family=FONT),
        ),
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white", family=FONT),
        height=260,
        margin=dict(l=20, r=20, t=30, b=10),
    )
    return fig


def build_dcf_bar(scenarios: list[dict]) -> go.Figure:
    """Horizontal bar chart — Base/Bull/Bear intrinsic values."""
    labels = [s["label"] for s in scenarios]
    values = [s["intrinsic_value"] for s in scenarios]
    palette = [BLUE, GREEN, RED]

    fig = go.Figure()
    for i, (lbl, val, col) in enumerate(zip(labels, values, palette)):
        mos = scenarios[i].get("margin_of_safety", 0) or 0
        mos_pct = f"{mos*100:+.1f}%"
        fig.add_trace(go.Bar(
            name=lbl,
            x=[val],
            y=[lbl],
            orientation="h",
            marker=dict(
                color=f"{col}bb",
                line=dict(color=col, width=1.5),
            ),
            text=f"${val:,.0f}  ({mos_pct} MoS)",
            textposition="outside",
            textfont=dict(color="rgba(255,255,255,0.85)", size=12, family=FONT),
        ))

    fig.update_layout(
        **_base_layout(
            title=dict(text="DCF Intrinsic Value — Scenarios", font=dict(size=13), x=0),
            xaxis=dict(tickprefix="$", gridcolor=GRID, zeroline=False),
            yaxis=dict(gridcolor=GRID, tickfont=dict(size=13)),
            barmode="group",
            showlegend=False,
            height=210,
            margin=dict(l=80, r=130, t=50, b=30),
        )
    )
    return fig


def build_pnl_scatter(trades_df: pd.DataFrame) -> go.Figure:
    """Scatter of P&L % vs score_at_entry for closed trades."""
    closed = trades_df[trades_df["exit_date"].notna()].copy()

    if closed.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No closed trades yet — P&L data will appear after your first exit.",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=13, color="rgba(255,255,255,0.35)", family=FONT),
        )
        fig.update_layout(**_base_layout(height=300))
        return fig

    closed["pnl_pct_display"] = closed["pnl_pct"] * 100

    fig = go.Figure(go.Scatter(
        x=closed["score_at_entry"].tolist(),
        y=closed["pnl_pct_display"].tolist(),
        mode="markers+text",
        text=closed["ticker"].tolist(),
        textposition="top center",
        textfont=dict(size=11, family=FONT, color="rgba(255,255,255,0.7)"),
        marker=dict(
            color=closed["pnl_pct_display"].tolist(),
            colorscale=[[0, RED], [0.5, YELLOW], [1, GREEN]],
            size=13,
            line=dict(color="rgba(255,255,255,0.2)", width=1),
            showscale=True,
            colorbar=dict(
                title=dict(text="P&L %", font=dict(size=11)),
                ticksuffix="%",
                tickfont=dict(size=10),
            ),
        ),
    ))

    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)", line_width=1)
    fig.add_vline(
        x=0.72, line_dash="dot", line_color=f"{GREEN}55", line_width=1.5,
        annotation_text="Strong threshold",
        annotation_font=dict(color=GREEN, size=10),
        annotation_position="top right",
    )

    fig.update_layout(
        **_base_layout(
            title=dict(text="P&L % vs Score at Entry", font=dict(size=13), x=0),
            xaxis=dict(title="Score at Entry", range=[0, 1], gridcolor=GRID),
            yaxis=dict(title="P&L %", ticksuffix="%", gridcolor=GRID),
            height=350,
        )
    )
    return fig


def build_win_rate_bar(trades_df: pd.DataFrame) -> go.Figure:
    """Win rate % by grade at entry."""
    closed = trades_df[trades_df["exit_date"].notna()].copy()

    if closed.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No closed trades yet.",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=13, color="rgba(255,255,255,0.35)", family=FONT),
        )
        fig.update_layout(**_base_layout(height=250))
        return fig

    closed["win"] = closed["pnl_pct"] > 0
    summary = closed.groupby("grade_at_entry").agg(
        win_rate=("win", "mean"),
        count=("win", "count"),
    ).reset_index()

    palette = {"STRONG SETUP": GREEN, "MODERATE SETUP": YELLOW, "WEAK SETUP": RED}
    bar_colors = [palette.get(g, ACCENT) for g in summary["grade_at_entry"]]

    fig = go.Figure(go.Bar(
        x=summary["grade_at_entry"].tolist(),
        y=(summary["win_rate"] * 100).tolist(),
        text=[f"{wr*100:.0f}% ({c})" for wr, c in zip(summary["win_rate"], summary["count"])],
        textposition="outside",
        textfont=dict(size=12, family=FONT),
        marker=dict(
            color=[f"{c}bb" for c in bar_colors],
            line=dict(color=bar_colors, width=1.5),
        ),
    ))

    fig.add_hline(
        y=50, line_dash="dash", line_color="rgba(255,255,255,0.2)", line_width=1,
        annotation_text="50% breakeven",
        annotation_font=dict(size=10, color="rgba(255,255,255,0.4)"),
        annotation_position="right",
    )

    fig.update_layout(
        **_base_layout(
            title=dict(text="Win Rate by Setup Grade", font=dict(size=13), x=0),
            yaxis=dict(title="Win Rate %", range=[0, 115], ticksuffix="%", gridcolor=GRID),
            xaxis=dict(gridcolor=GRID),
            showlegend=False,
            height=280,
        )
    )
    return fig
