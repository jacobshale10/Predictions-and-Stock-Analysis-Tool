"""
data/universe.py — Ticker universe management.

Provides lists of tickers for batch scanning:
  - S&P 500:     ~503 tickers scraped from Wikipedia (cached 7 days)
  - NASDAQ 100:  ~101 tickers scraped from Wikipedia (cached 7 days)
  - Russell 1000: bundled static CSV (data/russell1000.csv)
  - All Large Cap: union of all three

Falls back gracefully if network is unavailable.
"""

import os
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Cache settings ────────────────────────────────────────────────────────────
_CACHE_DIR  = Path(__file__).parent / "cache"
_CACHE_FILE = _CACHE_DIR / "universe_cache.pkl"
_CACHE_TTL  = timedelta(days=7)

# ── Static CSV ────────────────────────────────────────────────────────────────
_RUSSELL_CSV = Path(__file__).parent / "russell1000.csv"

# ── Wikipedia URLs ────────────────────────────────────────────────────────────
_SP500_URL   = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NASDAQ_URL  = "https://en.wikipedia.org/wiki/Nasdaq-100"

# ── Minimal fallback S&P 500 tickers (used if Wikipedia is unreachable) ───────
_SP500_FALLBACK = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","BRK.B","JPM",
    "LLY","V","UNH","XOM","MA","COST","PG","JNJ","HD","ABBV","BAC","WFC",
    "MRK","ORCL","KO","NFLX","CVX","CRM","AMD","PEP","ADBE","TMO","ACN",
    "MCD","CSCO","NKE","TXN","IBM","VZ","DHR","AMGN","CAT","QCOM","NEE",
    "PM","SPGI","INTU","ISRG","AMAT","GE","HON","RTX","UPS","BA","NOW",
    "LOW","ETN","T","BLK","ELV","SYK","MDT","GS","DE","MS","BKNG","AXP",
    "C","REGN","BX","ADI","LRCX","MU","TJX","MMC","VRTX","KLAC","CI","CB",
    "PGR","PANW","MDLZ","ADP","GILD","SBUX","CME","ZTS","SNPS","EQIX",
    "CDNS","MAR","FI","WM","ITW","HUM","MSI","EW","APD","AON","DUK","SO",
    "PLD","AMT","CCI","PSA","WELL","CTAS","NSC","PH","GD","LMT","NOC",
    "HCA","DXCM","BIIB","IDXX","A","ROK","FICO","PPG","SHW","ECL","EMR",
    "FDX","EXC","PCG","SRE","AEP","XEL","D","CL","KMB","RSG","AWK","ROP",
    "EFX","MCO","ICE","MSCI","NUE","STLD","FCX","NEM","DOW","DD","LYB",
]

_NASDAQ100_FALLBACK = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","GOOG","META","TSLA","AVGO","COST",
    "NFLX","ADBE","AMD","QCOM","INTU","CSCO","TXN","PEP","HON","AMGN",
    "AMAT","ISRG","VRTX","BKNG","REGN","ADP","PANW","GILD","LRCX","KLAC",
    "CDNS","SNPS","ADI","MELI","MRNA","INTC","MDLZ","PYPL","CTAS","MAR",
    "MNST","CEG","ORLY","MRVL","PCAR","IDXX","ROST","FTNT","KDP","PAYX",
    "TTD","ABNB","DXCM","EA","VRSK","ODFL","GFS","GEHC","EXC","FAST",
    "MCHP","DDOG","DLTR","CPRT","BKR","CSGP","TEAM","ZS","WDAY","NXPI",
    "CHTR","ROP","WBD","SIRI","ON","FANG","ZM","CRWD","OKTA","SMCI",
]


def _load_cache() -> Optional[dict]:
    """Load cached universe data if it exists and is not expired."""
    try:
        if not _CACHE_FILE.exists():
            return None
        with open(_CACHE_FILE, "rb") as f:
            data = pickle.load(f)
        if datetime.now() - data.get("timestamp", datetime.min) > _CACHE_TTL:
            return None
        return data
    except Exception:
        return None


def _save_cache(data: dict) -> None:
    """Save universe data to cache."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data["timestamp"] = datetime.now()
        with open(_CACHE_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception:
        pass


def _scrape_sp500() -> list[str]:
    """Scrape S&P 500 tickers from Wikipedia."""
    try:
        tables = pd.read_html(_SP500_URL)
        # First table on the page has the constituents
        df = tables[0]
        # Column is "Symbol" on the Wikipedia S&P 500 page
        col = next((c for c in df.columns if "symbol" in c.lower() or "ticker" in c.lower()), None)
        if col is None:
            col = df.columns[0]
        tickers = df[col].dropna().astype(str).str.strip().str.upper().tolist()
        # Clean: remove entries that aren't valid tickers (some rows have notes)
        tickers = [t.replace(".", "-") for t in tickers if 1 <= len(t) <= 6 and t.isalpha() or "." in t or "-" in t]
        return [t for t in tickers if t]
    except Exception:
        return []


def _scrape_nasdaq100() -> list[str]:
    """Scrape NASDAQ 100 tickers from Wikipedia."""
    try:
        tables = pd.read_html(_NASDAQ_URL)
        # Find the table that has a ticker/symbol column
        for table in tables:
            for col in table.columns:
                if "ticker" in str(col).lower() or "symbol" in str(col).lower():
                    tickers = table[col].dropna().astype(str).str.strip().str.upper().tolist()
                    tickers = [t for t in tickers if 1 <= len(t) <= 6]
                    if len(tickers) > 50:
                        return tickers
        return []
    except Exception:
        return []


def _load_russell1000() -> list[str]:
    """Load Russell 1000 tickers from the bundled CSV."""
    try:
        df = pd.read_csv(_RUSSELL_CSV)
        col = df.columns[0]
        tickers = df[col].dropna().astype(str).str.strip().str.upper().tolist()
        return [t for t in tickers if 1 <= len(t) <= 6]
    except Exception:
        return list(_SP500_FALLBACK)


def _dedupe(tickers: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    seen = set()
    result = []
    for t in tickers:
        if t not in seen and t:
            seen.add(t)
            result.append(t)
    return result


def get_universe(name: str) -> list[str]:
    """
    Return a list of ticker symbols for the requested universe.

    Args:
        name: "S&P 500" | "NASDAQ 100" | "Russell 1000" | "All Large Cap"

    Returns:
        List of ticker strings (deduplicated, uppercase).
    """
    cache = _load_cache()

    if name == "S&P 500":
        if cache and "sp500" in cache:
            return cache["sp500"]
        tickers = _scrape_sp500() or list(_SP500_FALLBACK)
        tickers = _dedupe(tickers)
        _save_cache({"sp500": tickers, **(cache or {})})
        return tickers

    if name == "NASDAQ 100":
        if cache and "nasdaq100" in cache:
            return cache["nasdaq100"]
        tickers = _scrape_nasdaq100() or list(_NASDAQ100_FALLBACK)
        tickers = _dedupe(tickers)
        _save_cache({"nasdaq100": tickers, **(cache or {})})
        return tickers

    if name == "Russell 1000":
        return _dedupe(_load_russell1000())

    if name == "All Large Cap":
        sp500   = get_universe("S&P 500")
        nasdaq  = get_universe("NASDAQ 100")
        russell = get_universe("Russell 1000")
        return _dedupe(sp500 + nasdaq + russell)

    raise ValueError(f"Unknown universe: {name!r}. Valid options: 'S&P 500', 'NASDAQ 100', 'Russell 1000', 'All Large Cap'")


def get_universe_size(name: str) -> int:
    """Return approximate size of a universe without fully loading it."""
    sizes = {"S&P 500": 503, "NASDAQ 100": 101, "Russell 1000": 1000, "All Large Cap": 1200}
    return sizes.get(name, 500)
