"""
analysis/ai_dcf.py — AI-powered DCF valuation using Claude API.

If a Claude API key is provided:
  - Sends financial data to Claude claude-sonnet-4-6
  - Claude selects growth rates, validates WACC, computes intrinsic value
  - Returns structured JSON with qualitative assessment

If no API key (or Claude call fails):
  - Falls back to the existing quantitative DCF in analysis/dcf.py
  - Uses auto-calculated WACC from analysis/wacc.py

The output AIDCFResult is display-compatible with the existing DCF UI.
"""

import json
from dataclasses import dataclass
from typing import Optional

from analysis.dcf import DCFResult, DCFScenario, _compute_intrinsic_value
from analysis.wacc import WACCResult
from config import DEFAULT_TERMINAL_GROWTH, DCF_MAX_GROWTH_CAP
from data import fetcher


@dataclass
class AIDCFResult:
    """Extended DCF result that may include AI-generated analysis."""
    ticker:          str
    current_price:   float

    # Scenarios (same as DCFResult for display compatibility)
    base:  DCFScenario
    bull:  DCFScenario
    bear:  DCFScenario

    # Raw inputs
    fcf_ttm:           Optional[float]
    growth_rate_used:  float
    shares_outstanding: Optional[float]
    net_debt:          float
    growth_source:     str

    # WACC info
    wacc_result:  WACCResult

    # AI-specific fields
    ai_powered:       bool     # True if Claude provided the analysis
    ai_assessment:    str      # Claude's qualitative 1-sentence summary
    ai_confidence:    str      # "high" | "medium" | "low"
    ai_growth_note:   str      # Why Claude chose this growth rate

    # Error / warning
    error:  Optional[str] = None


def _build_prompt(
    company_name:   str,
    sector:         str,
    current_price:  float,
    fcf_ttm:        float,
    revenue_ttm:    Optional[float],
    net_income_ttm: Optional[float],
    rev_growth:     Optional[float],
    analyst_growth: Optional[float],
    wacc_result:    WACCResult,
    shares:         float,
    net_debt:       float,
    headlines:      list[str],
) -> str:
    headlines_text = "\n".join(f"  - {h}" for h in headlines[:3]) if headlines else "  None available"

    return f"""You are a professional equity analyst performing a DCF valuation.

Company: {company_name} ({sector})
Current Price: ${current_price:.2f}

Financial Data:
- Free Cash Flow (TTM): ${fcf_ttm/1e9:.2f}B
- Revenue (TTM): {f"${revenue_ttm/1e9:.2f}B" if revenue_ttm else "N/A"}
- Net Income (TTM): {f"${net_income_ttm/1e9:.2f}B" if net_income_ttm else "N/A"}
- Revenue Growth (trailing YoY): {f"{rev_growth*100:.1f}%" if rev_growth else "N/A"}
- Analyst Consensus Growth Estimate: {f"{analyst_growth*100:.1f}%" if analyst_growth else "N/A"}

Capital Structure:
- Shares Outstanding: {shares/1e9:.3f}B
- Net Debt: ${net_debt/1e9:.2f}B (negative = net cash)

Auto-Calculated WACC Range:
- Base WACC: {wacc_result.wacc*100:.2f}%
- Low WACC: {wacc_result.wacc_low*100:.2f}%
- High WACC: {wacc_result.wacc_high*100:.2f}%
- Beta: {wacc_result.beta}
- Risk-Free Rate: {wacc_result.risk_free_rate*100:.2f}%

Recent Headlines:
{headlines_text}

Task: Perform a 10-year two-stage DCF valuation.
- Stage 1 (Years 1-5): Use the growth rate you select
- Stage 2 (Years 6-10): Linearly decay to terminal growth rate
- Terminal Value: Gordon Growth Model

Instructions:
1. Assess whether the FCF growth rate should be conservative/base/optimistic based on fundamentals
2. Select a realistic growth rate for years 1-5 (cap at 25%)
3. Select a terminal growth rate between 2.0% and 3.5%
4. From the WACC range, pick the most appropriate value
5. Compute the 10-year two-stage DCF intrinsic value per share
6. Calculate margin of safety vs current price of ${current_price:.2f}
7. Write a 1-sentence qualitative assessment

IMPORTANT: Return ONLY valid JSON with no extra text or markdown:
{{"growth_rate": 0.08, "terminal_growth": 0.025, "wacc_used": 0.091, "intrinsic_value": 145.20, "margin_of_safety": 0.23, "assessment": "Strong FCF generator trading at a meaningful discount after temporary operational headwinds.", "confidence": "high", "growth_note": "Using analyst estimate of 8% given stable revenue trajectory and margin recovery"}}"""


def _call_claude(prompt: str, api_key: str) -> Optional[dict]:
    """Call Claude API and parse JSON response. Returns None on failure."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        # Validate required fields
        required = {"growth_rate", "terminal_growth", "wacc_used", "intrinsic_value", "margin_of_safety", "assessment", "confidence"}
        if not required.issubset(data.keys()):
            return None

        # Sanity-check numeric ranges
        if not (0 < data["growth_rate"] <= 0.30):
            return None
        if not (0.015 <= data["terminal_growth"] <= 0.04):
            return None
        if not (0.04 <= data["wacc_used"] <= 0.20):
            return None

        return data

    except Exception:
        return None


def _quant_fallback(
    fcf_ttm:     float,
    growth_rate: float,
    growth_source: str,
    shares:      float,
    net_debt:    float,
    current_price: float,
    wacc_result: WACCResult,
    ticker:      str,
) -> AIDCFResult:
    """Compute DCF using pure quantitative approach with auto-WACC."""

    def _scenario(label, wacc, tg):
        iv = _compute_intrinsic_value(fcf_ttm, growth_rate, tg, wacc, shares, net_debt)
        mos = None
        if iv is not None and iv > 0:
            mos = (iv - current_price) / iv
        return DCFScenario(label=label, wacc=wacc, terminal_growth=tg, intrinsic_value=iv, margin_of_safety=mos)

    tg_base = DEFAULT_TERMINAL_GROWTH
    base = _scenario("Base", wacc_result.wacc,      tg_base)
    bull = _scenario("Bull", wacc_result.wacc_low,  tg_base + 0.005)
    bear = _scenario("Bear", wacc_result.wacc_high, tg_base - 0.005)

    return AIDCFResult(
        ticker=ticker, current_price=current_price,
        base=base, bull=bull, bear=bear,
        fcf_ttm=fcf_ttm, growth_rate_used=growth_rate,
        shares_outstanding=shares, net_debt=net_debt,
        growth_source=growth_source,
        wacc_result=wacc_result,
        ai_powered=False,
        ai_assessment="",
        ai_confidence="",
        ai_growth_note="",
    )


def run(
    symbol:        str,
    current_price: float,
    fundamentals:  dict,
    wacc_result:   WACCResult,
    claude_api_key: Optional[str] = None,
) -> AIDCFResult:
    """
    Compute AI-powered (or quantitative fallback) DCF for a stock.

    Args:
        symbol:          Ticker symbol
        current_price:   Current market price per share
        fundamentals:    Dict from fetcher.get_fundamentals()
        wacc_result:     WACCResult from wacc.calculate()
        claude_api_key:  Optional Anthropic API key for AI mode

    Returns:
        AIDCFResult with Base/Bull/Bear scenarios plus optional AI assessment.
    """
    ticker = symbol.upper()

    # ── Fetch cash flow data ───────────────────────────────────────────────
    cf_data = fetcher.get_cash_flow_data(ticker)
    fcf_ttm  = cf_data.get("free_cash_flow_ttm") if cf_data else None
    shares   = fundamentals.get("shares_outstanding")
    net_debt = float((fundamentals.get("total_debt") or 0) - (fundamentals.get("total_cash") or 0))

    # ── Determine growth rate ──────────────────────────────────────────────
    growth_source = "default"
    growth_rate   = 0.07
    analyst_eg    = fundamentals.get("earnings_growth")
    rev_growth    = fundamentals.get("revenue_growth")

    if analyst_eg is not None and 0 < analyst_eg <= DCF_MAX_GROWTH_CAP:
        growth_rate   = analyst_eg
        growth_source = "analyst_estimate"
    elif rev_growth is not None and 0 < rev_growth <= DCF_MAX_GROWTH_CAP:
        growth_rate   = rev_growth
        growth_source = "trailing_revenue_growth"

    # ── Guard missing data ─────────────────────────────────────────────────
    empty = DCFScenario("N/A", wacc_result.wacc, DEFAULT_TERMINAL_GROWTH, None, None)
    if fcf_ttm is None or fcf_ttm <= 0:
        return AIDCFResult(
            ticker=ticker, current_price=current_price,
            base=empty, bull=empty, bear=empty,
            fcf_ttm=fcf_ttm, growth_rate_used=growth_rate,
            shares_outstanding=shares, net_debt=net_debt,
            growth_source=growth_source, wacc_result=wacc_result,
            ai_powered=False, ai_assessment="", ai_confidence="", ai_growth_note="",
            error="Free cash flow data unavailable or negative — DCF not meaningful.",
        )
    if shares is None or shares <= 0:
        return AIDCFResult(
            ticker=ticker, current_price=current_price,
            base=empty, bull=empty, bear=empty,
            fcf_ttm=fcf_ttm, growth_rate_used=growth_rate,
            shares_outstanding=shares, net_debt=net_debt,
            growth_source=growth_source, wacc_result=wacc_result,
            ai_powered=False, ai_assessment="", ai_confidence="", ai_growth_note="",
            error="Shares outstanding data unavailable — cannot compute per-share value.",
        )

    # ── Try AI-powered DCF ─────────────────────────────────────────────────
    if claude_api_key:
        company_name = fundamentals.get("company_name") or ticker
        sector       = fundamentals.get("sector") or "Unknown"
        rev_q        = fundamentals.get("revenue_quarterly") or []
        rev_ttm      = sum(v for v in rev_q[:4] if v) if rev_q else None
        ni_ttm       = None  # net income TTM not directly in fundamentals

        headlines = fetcher.get_news(ticker)

        prompt = _build_prompt(
            company_name=company_name,
            sector=sector,
            current_price=current_price,
            fcf_ttm=fcf_ttm,
            revenue_ttm=rev_ttm,
            net_income_ttm=ni_ttm,
            rev_growth=rev_growth,
            analyst_growth=analyst_eg,
            wacc_result=wacc_result,
            shares=shares,
            net_debt=net_debt,
            headlines=headlines,
        )

        ai_data = _call_claude(prompt, claude_api_key)

        if ai_data:
            ai_growth    = float(ai_data["growth_rate"])
            ai_tg        = float(ai_data["terminal_growth"])
            ai_wacc      = float(ai_data["wacc_used"])
            ai_iv        = float(ai_data["intrinsic_value"])
            ai_mos       = float(ai_data["margin_of_safety"])
            ai_assess    = str(ai_data.get("assessment", ""))
            ai_conf      = str(ai_data.get("confidence", "medium"))
            ai_gnote     = str(ai_data.get("growth_note", ""))

            base = DCFScenario("Base (AI)",   ai_wacc,                  ai_tg,         ai_iv,  ai_mos)
            bull = DCFScenario("Bull (AI)",   wacc_result.wacc_low,     ai_tg + 0.005,
                               _compute_intrinsic_value(fcf_ttm, ai_growth, ai_tg + 0.005, wacc_result.wacc_low, shares, net_debt), None)
            bear = DCFScenario("Bear (AI)",   wacc_result.wacc_high,    ai_tg - 0.005,
                               _compute_intrinsic_value(fcf_ttm, ai_growth, ai_tg - 0.005, wacc_result.wacc_high, shares, net_debt), None)

            # Fill MoS for bull/bear
            for sc in [bull, bear]:
                if sc.intrinsic_value is not None and sc.intrinsic_value > 0:
                    sc.margin_of_safety = (sc.intrinsic_value - current_price) / sc.intrinsic_value

            return AIDCFResult(
                ticker=ticker, current_price=current_price,
                base=base, bull=bull, bear=bear,
                fcf_ttm=fcf_ttm, growth_rate_used=ai_growth,
                shares_outstanding=shares, net_debt=net_debt,
                growth_source="claude_ai",
                wacc_result=wacc_result,
                ai_powered=True,
                ai_assessment=ai_assess,
                ai_confidence=ai_conf,
                ai_growth_note=ai_gnote,
            )

    # ── Quantitative fallback ──────────────────────────────────────────────
    return _quant_fallback(fcf_ttm, growth_rate, growth_source, shares, net_debt,
                           current_price, wacc_result, ticker)
