"""
analysis/screener.py — Compute all 6 screening metrics from raw yfinance data.
This module has no UI concerns — it returns a plain dataclass.
"""

from dataclasses import dataclass, field
from typing import Optional

from data import fetcher
from data import sector_benchmarks
from data import news_classifier


@dataclass
class ScreenerResult:
    ticker: str
    company_name: str
    sector: str
    industry: str

    # --- Price ---
    current_price: float
    price_52w_high: float
    price_52w_low: float
    decline_from_52w_high: float  # e.g. 0.27 = 27% below peak

    # --- Valuation ---
    forward_pe: Optional[float]
    trailing_pe: Optional[float]
    sector_avg_pe: float
    pe_discount_to_sector: Optional[float]  # positive = cheaper than sector

    # --- Growth ---
    revenue_qoq: Optional[float]   # QoQ change, e.g. 0.05 = +5%
    earnings_qoq: Optional[float]  # QoQ EPS change
    eps_positive: bool              # True if latest EPS > 0

    # --- Analyst ---
    consensus_rating: str
    num_analysts: Optional[int]
    mean_target: Optional[float]
    analyst_upside: Optional[float]  # (target - price) / price

    # --- News ---
    news_label: str
    news_display: str
    news_reason: str
    news_source: str
    headlines: list[str] = field(default_factory=list)

    # --- Data quality flags ---
    missing_fields: list[str] = field(default_factory=list)

    # --- Raw history for charting ---
    price_history: object = None  # pandas DataFrame


def run(symbol: str, groq_api_key: str = None) -> Optional[ScreenerResult]:
    """
    Fetch all data and compute screening metrics for a given ticker.
    Returns None if the ticker cannot be found or is missing critical price data.
    """
    symbol = symbol.upper().strip()
    missing = []

    # --- Price ---
    price_data = fetcher.get_price_data(symbol)
    if not price_data or price_data["current_price"] is None:
        return None

    current_price  = price_data["current_price"]
    price_52w_high = price_data["price_52w_high"]
    price_52w_low  = price_data["price_52w_low"]
    decline = (price_52w_high - current_price) / price_52w_high if price_52w_high else 0.0

    # --- Fundamentals ---
    fund = fetcher.get_fundamentals(symbol)
    if not fund:
        fund = {}
        missing.append("fundamentals")

    company_name = fund.get("company_name") or symbol
    sector       = fund.get("sector") or "Unknown"
    industry     = fund.get("industry") or "Unknown"
    forward_pe   = fund.get("forward_pe")
    trailing_pe  = fund.get("trailing_pe")
    sector_avg_pe = sector_benchmarks.get_sector_pe(sector)

    # Use forward PE preferentially, fall back to trailing
    pe_to_use = forward_pe or trailing_pe
    if pe_to_use and pe_to_use > 0:
        pe_discount = (sector_avg_pe - pe_to_use) / sector_avg_pe
    else:
        pe_discount = None
        if pe_to_use is None:
            missing.append("pe_ratio")

    # --- Revenue QoQ ---
    rev_q = fund.get("revenue_quarterly")
    revenue_qoq = None
    if rev_q and len(rev_q) >= 2:
        q_now  = rev_q[0]
        q_prev = rev_q[1]
        if q_now is not None and q_prev and q_prev != 0:
            revenue_qoq = (q_now - q_prev) / abs(q_prev)
    if revenue_qoq is None:
        missing.append("revenue_qoq")

    # --- EPS QoQ ---
    eps_q = fund.get("eps_quarterly")
    earnings_qoq = None
    eps_positive = True
    if eps_q and len(eps_q) >= 2:
        e_now  = eps_q[0]
        e_prev = eps_q[1]
        if e_now is not None and e_prev and e_prev != 0:
            earnings_qoq = (e_now - e_prev) / abs(e_prev)
        if e_now is not None:
            eps_positive = e_now > 0
    if earnings_qoq is None:
        missing.append("earnings_qoq")

    # --- Analyst ---
    analyst = fetcher.get_analyst_data(symbol)
    if not analyst:
        analyst = {}
        missing.append("analyst_data")

    consensus_rating = analyst.get("consensus_rating") or "N/A"
    num_analysts     = analyst.get("num_analysts")
    mean_target      = analyst.get("mean_target")
    analyst_upside   = None
    if mean_target and current_price:
        analyst_upside = (mean_target - current_price) / current_price

    # --- News ---
    headlines = fetcher.get_news(symbol)
    news_result = news_classifier.classify(headlines, groq_api_key=groq_api_key)

    return ScreenerResult(
        ticker=symbol,
        company_name=company_name,
        sector=sector,
        industry=industry,
        current_price=current_price,
        price_52w_high=price_52w_high,
        price_52w_low=price_52w_low,
        decline_from_52w_high=decline,
        forward_pe=forward_pe,
        trailing_pe=trailing_pe,
        sector_avg_pe=sector_avg_pe,
        pe_discount_to_sector=pe_discount,
        revenue_qoq=revenue_qoq,
        earnings_qoq=earnings_qoq,
        eps_positive=eps_positive,
        consensus_rating=consensus_rating,
        num_analysts=num_analysts,
        mean_target=mean_target,
        analyst_upside=analyst_upside,
        news_label=news_result["label"],
        news_display=news_result["display_label"],
        news_reason=news_result["reason"],
        news_source=news_result["source"],
        headlines=headlines,
        missing_fields=missing,
        price_history=price_data.get("history"),
    )
