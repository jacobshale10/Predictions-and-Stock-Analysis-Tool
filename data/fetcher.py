"""
data/fetcher.py — All yfinance data retrieval.
Every method returns None (never raises) when data is unavailable.
This is the ONLY file in the project that talks to yfinance.
"""

import yfinance as yf
import pandas as pd
from typing import Optional


def _ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol.upper())


def get_price_data(symbol: str) -> Optional[dict]:
    """
    Returns:
        current_price, price_52w_high, price_52w_low,
        price_1m_ago, price_3m_ago, price_6m_ago,
        volume, avg_volume
    """
    try:
        t = _ticker(symbol)
        info = t.info or {}

        # fast_info.last_price is reliable for stocks and ETFs in modern yfinance
        current_price = None
        try:
            fi = t.fast_info
            lp = fi.last_price if hasattr(fi, "last_price") else None
            if lp and lp > 0:
                current_price = float(lp)
        except Exception:
            pass

        if current_price is None:
            current_price = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("navPrice")
                or info.get("previousClose")
            )

        if current_price is None:
            return None

        hist = t.history(period="1y")
        if hist.empty:
            return None

        price_52w_high = float(hist["Close"].max())
        price_52w_low  = float(hist["Close"].min())

        def price_n_days_ago(n: int) -> Optional[float]:
            if len(hist) < n:
                return None
            return float(hist["Close"].iloc[-(n)])

        return {
            "current_price":  float(current_price),
            "price_52w_high": price_52w_high,
            "price_52w_low":  price_52w_low,
            "price_1m_ago":   price_n_days_ago(21),
            "price_3m_ago":   price_n_days_ago(63),
            "price_6m_ago":   price_n_days_ago(126),
            "volume":         info.get("volume"),
            "avg_volume":     info.get("averageVolume"),
            "history":        hist,  # full DataFrame for charting
        }
    except Exception:
        return None


def get_fundamentals(symbol: str) -> Optional[dict]:
    """
    Returns:
        sector, industry, company_name,
        forward_pe, trailing_pe, peg_ratio,
        revenue_quarterly (list, newest first),
        eps_quarterly (list, newest first),
        market_cap, shares_outstanding,
        total_debt, total_cash
    """
    try:
        t = _ticker(symbol)
        info = t.info or {}

        company_name = info.get("longName") or info.get("shortName") or symbol.upper()
        sector       = info.get("sector")
        industry     = info.get("industry")

        forward_pe  = info.get("forwardPE")
        trailing_pe = info.get("trailingPE")
        peg_ratio   = info.get("pegRatio")

        # Quarterly financials — income statement
        try:
            quarterly = t.quarterly_income_stmt
            if quarterly is not None and not quarterly.empty:
                # Rows = metrics, columns = quarters (newest first)
                rev_row = None
                eps_row = None

                for row_label in quarterly.index:
                    label_lower = str(row_label).lower()
                    if "total revenue" in label_lower:
                        rev_row = quarterly.loc[row_label].tolist()
                    if "basic eps" in label_lower or "diluted eps" in label_lower:
                        if eps_row is None:
                            eps_row = quarterly.loc[row_label].tolist()
            else:
                rev_row = None
                eps_row = None
        except Exception:
            rev_row = None
            eps_row = None

        market_cap       = info.get("marketCap")
        shares_out       = info.get("sharesOutstanding")
        total_debt       = info.get("totalDebt", 0) or 0
        total_cash       = info.get("totalCash", 0) or 0
        earnings_growth  = info.get("earningsGrowth")   # analyst fwd estimate
        revenue_growth   = info.get("revenueGrowth")    # trailing YoY

        return {
            "company_name":      company_name,
            "sector":            sector,
            "industry":          industry,
            "forward_pe":        forward_pe,
            "trailing_pe":       trailing_pe,
            "peg_ratio":         peg_ratio,
            "revenue_quarterly": rev_row,   # list newest first, or None
            "eps_quarterly":     eps_row,   # list newest first, or None
            "market_cap":        market_cap,
            "shares_outstanding": shares_out,
            "total_debt":        total_debt,
            "total_cash":        total_cash,
            "earnings_growth":   earnings_growth,
            "revenue_growth":    revenue_growth,
        }
    except Exception:
        return None


def get_analyst_data(symbol: str) -> Optional[dict]:
    """
    Returns:
        consensus_rating (str), num_analysts (int),
        mean_target, low_target, high_target
    """
    try:
        t = _ticker(symbol)
        info = t.info or {}

        mean_target = info.get("targetMeanPrice")
        low_target  = info.get("targetLowPrice")
        high_target = info.get("targetHighPrice")
        num_analysts = info.get("numberOfAnalystOpinions")
        rec = info.get("recommendationKey", "")  # e.g. "buy", "hold", "strong_buy"

        # Normalize to human-readable
        rating_map = {
            "strong_buy":  "Strong Buy",
            "buy":         "Buy",
            "hold":        "Hold",
            "underperform":"Underperform",
            "sell":        "Sell",
            "":            "N/A",
        }
        consensus_rating = rating_map.get(rec, rec.replace("_", " ").title())

        return {
            "consensus_rating": consensus_rating,
            "num_analysts":     num_analysts,
            "mean_target":      mean_target,
            "low_target":       low_target,
            "high_target":      high_target,
        }
    except Exception:
        return None


def get_cash_flow_data(symbol: str) -> Optional[dict]:
    """
    Returns:
        free_cash_flow_ttm (float) — trailing twelve months FCF
        free_cash_flow_history (list) — quarterly FCF newest first
    """
    try:
        t = _ticker(symbol)

        # Try quarterly cash flow statement
        try:
            cf = t.quarterly_cashflow
            fcf_history = None
            if cf is not None and not cf.empty:
                for row_label in cf.index:
                    if "free cash flow" in str(row_label).lower():
                        fcf_history = cf.loc[row_label].tolist()
                        break

            # If not found directly, compute OCF - CapEx
            if fcf_history is None:
                ocf_row = None
                capex_row = None
                for row_label in cf.index:
                    label = str(row_label).lower()
                    if "operating cash flow" in label or "cash from operations" in label:
                        ocf_row = cf.loc[row_label].tolist()
                    if "capital expenditure" in label or "capex" in label:
                        capex_row = cf.loc[row_label].tolist()
                if ocf_row and capex_row:
                    fcf_history = [
                        (o or 0) + (c or 0)  # capex is usually negative
                        for o, c in zip(ocf_row, capex_row)
                    ]
        except Exception:
            fcf_history = None

        info = t.info or {}
        fcf_ttm = info.get("freeCashflow")

        if fcf_ttm is None and fcf_history:
            valid = [v for v in fcf_history[:4] if v is not None]
            fcf_ttm = sum(valid) if valid else None

        return {
            "free_cash_flow_ttm":     fcf_ttm,
            "free_cash_flow_history": fcf_history,
        }
    except Exception:
        return None


def get_news(symbol: str) -> list[str]:
    """Returns a list of recent news headline strings (up to 10)."""
    try:
        t = _ticker(symbol)
        news = t.news or []
        headlines = []
        for item in news[:10]:
            title = item.get("content", {}).get("title") or item.get("title", "")
            if title:
                headlines.append(title)
        return headlines
    except Exception:
        return []


def get_current_price(symbol: str) -> Optional[float]:
    """Fast single-price fetch for live P&L in the trade log."""
    try:
        t = _ticker(symbol)
        # fast_info is the fastest path and works for ETFs + stocks
        try:
            fi = t.fast_info
            lp = fi.last_price if hasattr(fi, "last_price") else None
            if lp and lp > 0:
                return float(lp)
        except Exception:
            pass
        info = t.info or {}
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("navPrice")
            or info.get("previousClose")
        )
        return float(price) if price else None
    except Exception:
        return None
