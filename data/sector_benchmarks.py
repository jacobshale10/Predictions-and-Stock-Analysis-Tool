"""
data/sector_benchmarks.py — Static sector PE and revenue growth benchmarks.
yfinance does not provide live sector averages, so these are hardcoded.
Update quarterly by looking up sector ETF (XLK, XLV, XLI, etc.) average PE ratios.
"""

SECTOR_BENCHMARKS: dict[str, dict] = {
    "Technology":             {"avg_pe": 28.0, "avg_rev_growth": 0.12},
    "Healthcare":             {"avg_pe": 22.0, "avg_rev_growth": 0.08},
    "Industrials":            {"avg_pe": 20.0, "avg_rev_growth": 0.06},
    "Consumer Discretionary": {"avg_pe": 23.0, "avg_rev_growth": 0.07},
    "Financials":             {"avg_pe": 14.0, "avg_rev_growth": 0.05},
    "Communication Services": {"avg_pe": 19.0, "avg_rev_growth": 0.09},
    "Consumer Staples":       {"avg_pe": 21.0, "avg_rev_growth": 0.04},
    "Energy":                 {"avg_pe": 12.0, "avg_rev_growth": 0.03},
    "Utilities":              {"avg_pe": 17.0, "avg_rev_growth": 0.03},
    "Real Estate":            {"avg_pe": 35.0, "avg_rev_growth": 0.05},
    "Materials":              {"avg_pe": 16.0, "avg_rev_growth": 0.04},
    "Unknown":                {"avg_pe": 20.0, "avg_rev_growth": 0.06},  # fallback
}


def get_sector_pe(sector: str) -> float:
    benchmark = SECTOR_BENCHMARKS.get(sector, SECTOR_BENCHMARKS["Unknown"])
    return benchmark["avg_pe"]


def get_sector_rev_growth(sector: str) -> float:
    benchmark = SECTOR_BENCHMARKS.get(sector, SECTOR_BENCHMARKS["Unknown"])
    return benchmark["avg_rev_growth"]
