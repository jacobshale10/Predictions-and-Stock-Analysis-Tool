"""
analysis/wacc.py — Automatic WACC calculation from company fundamentals.

Replaces the manual WACC slider. Derives all inputs from yfinance data:
  - Beta                   → Cost of Equity via CAPM
  - 10-yr Treasury (^TNX)  → Risk-free rate (live)
  - Equity Risk Premium    → 5.5% (Damodaran long-run historical)
  - Interest expense / total debt → Cost of Debt (pre-tax)
  - Tax provision / pretax income  → Effective tax rate (fallback: 21%)
  - Market cap + total debt        → Capital structure weights

Returns WACCResult with base WACC plus a low/high range.
Falls back gracefully on any data failure — never crashes the caller.
"""

from dataclasses import dataclass
from typing import Optional

import yfinance as yf

# ── Constants ─────────────────────────────────────────────────────────────────
EQUITY_RISK_PREMIUM = 0.055   # Damodaran US market long-run ERP
DEFAULT_TAX_RATE    = 0.21    # US federal statutory corporate rate
DEFAULT_BETA        = 1.0     # Market beta fallback
BETA_RANGE_DELTA    = 0.20    # ±0.2 beta for low/high WACC range
MIN_WACC            = 0.06    # Floor: prevents nonsensical DCF outputs
MAX_WACC            = 0.16    # Ceiling
RF_FALLBACK         = 0.043   # ~4.3% if live Treasury fetch fails
DEFAULT_WACC_BASE   = 0.09    # 9% — used when all data fetching fails


@dataclass
class WACCResult:
    wacc:             float   # Base WACC estimate
    wacc_low:         float   # Optimistic (lower beta)
    wacc_high:        float   # Pessimistic (higher beta)
    cost_of_equity:   float   # CAPM: Rf + β × ERP
    cost_of_debt_at:  float   # After-tax cost of debt
    beta:             float   # Beta used
    risk_free_rate:   float   # 10-yr Treasury yield
    tax_rate:         float   # Effective or statutory
    equity_weight:    float   # Market cap / (market cap + debt)
    debt_weight:      float   # Debt / (market cap + debt)
    source_notes:     str     # Transparency string for UI display


def default_wacc() -> WACCResult:
    """
    Return a conservative default WACCResult when live data is unavailable.
    Uses 9% base WACC with ±0.7% range.
    """
    rf = RF_FALLBACK
    ke = rf + DEFAULT_BETA * EQUITY_RISK_PREMIUM
    return WACCResult(
        wacc=DEFAULT_WACC_BASE,
        wacc_low=round(DEFAULT_WACC_BASE - 0.007, 4),
        wacc_high=round(DEFAULT_WACC_BASE + 0.007, 4),
        cost_of_equity=round(ke, 4),
        cost_of_debt_at=round((rf + 0.015) * (1 - DEFAULT_TAX_RATE), 4),
        beta=DEFAULT_BETA,
        risk_free_rate=rf,
        tax_rate=DEFAULT_TAX_RATE,
        equity_weight=1.0,
        debt_weight=0.0,
        source_notes="Default estimates (data unavailable)",
    )


def _get_risk_free_rate() -> float:
    """Fetch the current 10-year US Treasury yield from yfinance (^TNX)."""
    try:
        t = yf.Ticker("^TNX")
        fi = t.fast_info
        price = getattr(fi, "last_price", None)
        if price and price > 0:
            return float(price) / 100  # ^TNX quotes in percentage points
    except Exception:
        pass
    return RF_FALLBACK


def _get_income_stmt(t: yf.Ticker):
    """
    Safely fetch the annual income statement, trying multiple attribute names
    that differ across yfinance versions (0.2.x vs 1.x).
    Returns a DataFrame or None.
    """
    for attr in ("income_stmt", "income_statement", "financials"):
        try:
            df = getattr(t, attr, None)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
    return None


def _clamp(w: float) -> float:
    return max(MIN_WACC, min(MAX_WACC, w))


def calculate(symbol: str, fundamentals: dict) -> WACCResult:
    """
    Compute WACC for a stock.

    Args:
        symbol:       Ticker symbol (e.g. "AAPL")
        fundamentals: Dict from fetcher.get_fundamentals() — used for market_cap,
                      total_debt, etc. We fetch income statement separately here.

    Returns:
        WACCResult dataclass with base + range.
        Never raises — falls back to default_wacc() on any failure.
    """
    try:
        return _calculate_inner(symbol, fundamentals)
    except Exception:
        return default_wacc()


def _calculate_inner(symbol: str, fundamentals: dict) -> WACCResult:
    """Inner calculation — may raise; wrapped by calculate()."""
    ticker = symbol.upper()
    t = yf.Ticker(ticker)

    try:
        info = t.info or {}
    except Exception:
        info = {}

    # ── Risk-free rate ──────────────────────────────────────────────────────
    rf = _get_risk_free_rate()

    # ── Beta ────────────────────────────────────────────────────────────────
    beta_raw = info.get("beta")
    try:
        beta_raw_f = float(beta_raw) if beta_raw is not None else None
    except (TypeError, ValueError):
        beta_raw_f = None

    if beta_raw_f is None or beta_raw_f <= 0:
        beta = DEFAULT_BETA
        beta_note = "default 1.0"
    else:
        beta = beta_raw_f
        beta_note = f"{beta:.2f}"

    # ── Cost of Equity (CAPM) ────────────────────────────────────────────────
    ke = rf + beta * EQUITY_RISK_PREMIUM

    # ── Income statement (needed for tax rate + cost of debt) ────────────────
    inc = _get_income_stmt(t)

    # ── Effective Tax Rate ───────────────────────────────────────────────────
    tax_rate = DEFAULT_TAX_RATE
    tax_note = "statutory 21%"
    try:
        if inc is not None and not inc.empty:
            tax_prov = None
            pretax   = None
            for row_label in inc.index:
                lab = str(row_label).lower()
                if tax_prov is None and ("tax provision" in lab or "income tax" in lab):
                    val = inc.loc[row_label].iloc[0]
                    if val is not None:
                        try:
                            tax_prov = float(val)
                        except (TypeError, ValueError):
                            pass
                if pretax is None and ("pretax income" in lab or "income before tax" in lab):
                    val = inc.loc[row_label].iloc[0]
                    if val is not None:
                        try:
                            pretax = float(val)
                        except (TypeError, ValueError):
                            pass
            if tax_prov is not None and pretax is not None and pretax > 0:
                eff = tax_prov / pretax
                if 0.05 <= eff <= 0.48:
                    tax_rate = eff
                    tax_note = f"effective {tax_rate*100:.1f}%"
    except Exception:
        pass

    # ── Cost of Debt (pre-tax) ───────────────────────────────────────────────
    try:
        total_debt = float(fundamentals.get("total_debt") or info.get("totalDebt") or 0)
    except (TypeError, ValueError):
        total_debt = 0.0

    kd = rf + 0.015   # fallback: risk-free + 150 bps spread
    kd_note = "estimated (Rf+1.5%)"
    try:
        if inc is not None and not inc.empty and total_debt > 0:
            for row_label in inc.index:
                lab = str(row_label).lower()
                if "interest expense" in lab:
                    ie = inc.loc[row_label].iloc[0]
                    if ie is not None:
                        try:
                            kd_raw = abs(float(ie)) / total_debt
                            if 0.005 <= kd_raw <= 0.20:
                                kd = kd_raw
                                kd_note = f"actual {kd*100:.1f}%"
                        except (TypeError, ValueError):
                            pass
                    break
    except Exception:
        pass

    kd_at = kd * (1 - tax_rate)   # after-tax cost of debt

    # ── Capital structure weights ────────────────────────────────────────────
    try:
        market_cap = float(fundamentals.get("market_cap") or info.get("marketCap") or 0)
    except (TypeError, ValueError):
        market_cap = 0.0

    total_cap = market_cap + total_debt
    if total_cap > 0:
        we = market_cap / total_cap
        wd = total_debt / total_cap
    else:
        we = 1.0
        wd = 0.0

    # ── Base WACC ────────────────────────────────────────────────────────────
    wacc_base = _clamp(we * ke + wd * kd_at)

    # ── WACC range (beta ±0.20) ──────────────────────────────────────────────
    beta_low  = max(0.4, beta - BETA_RANGE_DELTA)
    beta_high = beta + BETA_RANGE_DELTA
    ke_low    = rf + beta_low  * EQUITY_RISK_PREMIUM
    ke_high   = rf + beta_high * EQUITY_RISK_PREMIUM
    wacc_low  = _clamp(we * ke_low  + wd * kd_at)
    wacc_high = _clamp(we * ke_high + wd * kd_at)

    source_notes = (
        f"β={beta_note} · Rf={rf*100:.2f}% · ERP=5.5% · "
        f"Kd={kd_note} · Tax={tax_note}"
    )

    return WACCResult(
        wacc           = round(wacc_base, 4),
        wacc_low       = round(wacc_low,  4),
        wacc_high      = round(wacc_high, 4),
        cost_of_equity = round(ke,        4),
        cost_of_debt_at= round(kd_at,     4),
        beta           = round(beta,       3),
        risk_free_rate = round(rf,         4),
        tax_rate       = round(tax_rate,   4),
        equity_weight  = round(we,         3),
        debt_weight    = round(wd,         3),
        source_notes   = source_notes,
    )
