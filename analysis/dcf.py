"""
analysis/dcf.py — Two-stage DCF valuation model.

Stage 1 (Years 1–5): Base FCF × analyst earnings growth (capped at 25%).
Stage 2 (Years 6–10): Growth decays linearly to terminal rate.
Terminal Value: Gordon Growth Model, discounted back to present.

Returns intrinsic value per share and margin of safety %.
Also runs Bull (WACC-1%) and Bear (WACC+1%) scenarios.
"""

from dataclasses import dataclass
from typing import Optional

from data import fetcher
from config import (
    DEFAULT_WACC, DEFAULT_TERMINAL_GROWTH,
    DCF_STAGE1_YEARS, DCF_STAGE2_YEARS, DCF_MAX_GROWTH_CAP,
    DCF_BULL_WACC_DELTA, DCF_BEAR_WACC_DELTA,
    DCF_BULL_GROWTH_DELTA, DCF_BEAR_GROWTH_DELTA,
)


@dataclass
class DCFScenario:
    label: str
    wacc: float
    terminal_growth: float
    intrinsic_value: Optional[float]
    margin_of_safety: Optional[float]  # positive = stock below intrinsic value


@dataclass
class DCFResult:
    ticker: str
    current_price: float
    base: DCFScenario
    bull: DCFScenario
    bear: DCFScenario

    # Inputs used (for transparency display)
    fcf_ttm: Optional[float]
    growth_rate_used: float
    shares_outstanding: Optional[float]
    net_debt: float

    # Data quality
    growth_source: str   # "analyst_estimate" | "trailing_revenue_growth" | "default"
    error: Optional[str] = None


def _compute_intrinsic_value(
    fcf_ttm: float,
    growth_rate: float,
    terminal_growth: float,
    wacc: float,
    shares_outstanding: float,
    net_debt: float,
) -> Optional[float]:
    """
    Core DCF engine. Returns intrinsic value per share or None on failure.
    """
    if shares_outstanding is None or shares_outstanding <= 0:
        return None
    if fcf_ttm is None or fcf_ttm <= 0:
        return None
    if wacc <= terminal_growth:
        return None  # Gordon Growth undefined

    total_years = DCF_STAGE1_YEARS + DCF_STAGE2_YEARS
    pv_sum = 0.0
    fcf = fcf_ttm

    for year in range(1, total_years + 1):
        if year <= DCF_STAGE1_YEARS:
            g = growth_rate
        else:
            # Linear decay from growth_rate to terminal_growth
            decay_years = DCF_STAGE2_YEARS
            decay_step  = year - DCF_STAGE1_YEARS
            g = growth_rate + (terminal_growth - growth_rate) * (decay_step / decay_years)

        fcf = fcf * (1 + g)
        pv  = fcf / ((1 + wacc) ** year)
        pv_sum += pv

    # Terminal value at end of year 10
    terminal_fcf = fcf * (1 + terminal_growth)
    tv = terminal_fcf / (wacc - terminal_growth)
    pv_tv = tv / ((1 + wacc) ** total_years)

    enterprise_value = pv_sum + pv_tv
    equity_value     = enterprise_value - net_debt
    intrinsic_per_share = equity_value / shares_outstanding

    return intrinsic_per_share


def _scenario(
    label: str,
    fcf_ttm: float,
    growth_rate: float,
    shares_outstanding: float,
    net_debt: float,
    current_price: float,
    wacc_delta: float = 0.0,
    growth_delta: float = 0.0,
    base_wacc: float = DEFAULT_WACC,
    base_terminal: float = DEFAULT_TERMINAL_GROWTH,
) -> DCFScenario:
    wacc = base_wacc + wacc_delta
    tg   = base_terminal + growth_delta

    iv = _compute_intrinsic_value(fcf_ttm, growth_rate, tg, wacc, shares_outstanding, net_debt)
    mos = None
    if iv is not None and iv > 0:
        mos = (iv - current_price) / iv

    return DCFScenario(
        label=label,
        wacc=wacc,
        terminal_growth=tg,
        intrinsic_value=iv,
        margin_of_safety=mos,
    )


def run(
    symbol: str,
    current_price: float,
    fundamentals: dict,
    wacc: float = DEFAULT_WACC,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
) -> DCFResult:
    """
    Compute Base, Bull, Bear DCF scenarios.
    `fundamentals` is the dict returned by fetcher.get_fundamentals().
    `wacc` may be overridden by the user via a UI slider.
    """
    ticker = symbol.upper()
    cf_data = fetcher.get_cash_flow_data(ticker)

    fcf_ttm = cf_data.get("free_cash_flow_ttm") if cf_data else None
    shares  = fundamentals.get("shares_outstanding")
    net_debt = (fundamentals.get("total_debt") or 0) - (fundamentals.get("total_cash") or 0)

    # --- Determine growth rate ---
    growth_source = "default"
    growth_rate = 0.07  # fallback: 7%

    analyst_eg = fundamentals.get("earnings_growth")
    rev_growth = fundamentals.get("revenue_growth")

    if analyst_eg is not None and 0 < analyst_eg <= DCF_MAX_GROWTH_CAP:
        growth_rate  = analyst_eg
        growth_source = "analyst_estimate"
    elif rev_growth is not None and 0 < rev_growth <= DCF_MAX_GROWTH_CAP:
        growth_rate  = rev_growth
        growth_source = "trailing_revenue_growth"

    # Guard against None FCF
    error = None
    if fcf_ttm is None or fcf_ttm <= 0:
        error = "Free cash flow data unavailable or negative — DCF not meaningful."
        empty = DCFScenario("N/A", wacc, terminal_growth, None, None)
        return DCFResult(
            ticker=ticker, current_price=current_price,
            base=empty, bull=empty, bear=empty,
            fcf_ttm=fcf_ttm, growth_rate_used=growth_rate,
            shares_outstanding=shares, net_debt=net_debt,
            growth_source=growth_source, error=error,
        )

    if shares is None or shares <= 0:
        error = "Shares outstanding data unavailable — cannot compute per-share value."
        empty = DCFScenario("N/A", wacc, terminal_growth, None, None)
        return DCFResult(
            ticker=ticker, current_price=current_price,
            base=empty, bull=empty, bear=empty,
            fcf_ttm=fcf_ttm, growth_rate_used=growth_rate,
            shares_outstanding=shares, net_debt=net_debt,
            growth_source=growth_source, error=error,
        )

    base = _scenario("Base", fcf_ttm, growth_rate, shares, net_debt, current_price,
                     base_wacc=wacc, base_terminal=terminal_growth)
    bull = _scenario("Bull", fcf_ttm, growth_rate, shares, net_debt, current_price,
                     wacc_delta=DCF_BULL_WACC_DELTA, growth_delta=DCF_BULL_GROWTH_DELTA,
                     base_wacc=wacc, base_terminal=terminal_growth)
    bear = _scenario("Bear", fcf_ttm, growth_rate, shares, net_debt, current_price,
                     wacc_delta=DCF_BEAR_WACC_DELTA, growth_delta=DCF_BEAR_GROWTH_DELTA,
                     base_wacc=wacc, base_terminal=terminal_growth)

    return DCFResult(
        ticker=ticker,
        current_price=current_price,
        base=base,
        bull=bull,
        bear=bear,
        fcf_ttm=fcf_ttm,
        growth_rate_used=growth_rate,
        shares_outstanding=shares,
        net_debt=net_debt,
        growth_source=growth_source,
    )
