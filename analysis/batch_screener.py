"""
analysis/batch_screener.py — Two-pass batch screening engine.

Pass 1 (fast filter, ~0.3s/ticker via fast_info):
  - Price decline from 52W high >= 15%
  - Market cap >= $2B (avoid micro-caps with poor data)
  - Skip ETFs/funds (no PE data at all)

Pass 2 (full analysis, ~2-4s/ticker):
  - Runs screener.run() + scorer.score() + wacc.calculate()
  - Builds ScanResult for every ticker that passes Pass 1

Pass 3 (AI DCF, top N candidates only):
  - Runs ai_dcf.run() on top N by setup_score
  - Updates ScanResult with AI margin of safety

Results are cached per-universe per-day for 6 hours.
"""

import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import yfinance as yf

from analysis import screener, scorer, wacc as wacc_module
from analysis.ai_dcf import run as ai_dcf_run
from data.fetcher import get_fundamentals

# ── Cache ─────────────────────────────────────────────────────────────────────
_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
_CACHE_TTL = timedelta(hours=6)

# ── Batch settings ────────────────────────────────────────────────────────────
PASS1_WORKERS    = 8    # threads for fast_info pass
PASS2_WORKERS    = 4    # threads for full analysis (more yfinance calls)
PASS1_DELAY      = 0.05  # seconds between pass-1 requests
PASS2_DELAY      = 0.3   # seconds between pass-2 requests
MIN_MARKET_CAP   = 2e9   # $2B minimum
MIN_DECLINE      = 0.12  # 12% decline from 52W high to enter pass 2
AI_DCF_TOP_N     = 15    # run AI DCF on top N by score


@dataclass
class ScanResult:
    ticker:              str
    company_name:        str
    sector:              str
    current_price:       float
    decline_from_high:   float     # fraction, e.g. 0.27 = 27%
    setup_score:         float     # 0.0–1.0
    grade:               str       # "STRONG SETUP" | "MODERATE SETUP" | "WEAK SETUP"
    wacc:                float     # auto-calculated WACC
    wacc_range:          str       # e.g. "8.4%–9.8%"
    dcf_margin_of_safety: Optional[float]  # from AI or quant DCF
    dcf_intrinsic_value:  Optional[float]  # base intrinsic value per share
    ai_assessment:       str       # Claude's 1-sentence summary or ""
    ai_powered:          bool      # True if Claude computed the DCF
    flags:               list[str] = field(default_factory=list)
    analyst_upside:      Optional[float] = None
    consensus_rating:    str = ""
    forward_pe:          Optional[float] = None
    sector_avg_pe:       float = 0.0
    scan_timestamp:      datetime = field(default_factory=datetime.now)


def _cache_path(universe_name: str) -> Path:
    safe = universe_name.replace(" ", "_").replace("&", "and")
    date_str = datetime.now().strftime("%Y-%m-%d")
    return _CACHE_DIR / f"scan_{safe}_{date_str}.pkl"


def load_cache(universe_name: str) -> Optional[list[ScanResult]]:
    """Load cached scan results if they exist and are fresh."""
    try:
        path = _cache_path(universe_name)
        if not path.exists():
            return None
        with open(path, "rb") as f:
            data = pickle.load(f)
        if not data:
            return None
        age = datetime.now() - data[0].scan_timestamp
        if age > _CACHE_TTL:
            return None
        return data
    except Exception:
        return None


def _save_cache(universe_name: str, results: list[ScanResult]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(universe_name)
        with open(path, "wb") as f:
            pickle.dump(results, f)
    except Exception:
        pass


def _pass1_check(ticker: str) -> Optional[dict]:
    """
    Fast pre-filter using yfinance fast_info.
    Returns a dict with basic metrics if the ticker passes, else None.
    """
    try:
        time.sleep(PASS1_DELAY)
        t = yf.Ticker(ticker)
        fi = t.fast_info

        price = getattr(fi, "last_price", None)
        if not price or price <= 0:
            return None

        year_high = getattr(fi, "year_high", None)
        if not year_high or year_high <= 0:
            return None

        decline = (year_high - price) / year_high
        if decline < MIN_DECLINE:
            return None  # not dislocated enough

        market_cap = getattr(fi, "market_cap", None)
        if market_cap and market_cap < MIN_MARKET_CAP:
            return None  # too small

        return {
            "ticker":      ticker,
            "price":       float(price),
            "year_high":   float(year_high),
            "decline":     float(decline),
            "market_cap":  float(market_cap) if market_cap else None,
        }
    except Exception:
        return None


def _build_flags(result, setup_score) -> list[str]:
    """Generate human-readable flag strings for a screener result."""
    flags = []
    d = result.decline_from_52w_high * 100
    flags.append(f"↓{d:.0f}% from 52W high")

    if result.pe_discount_to_sector is not None and result.pe_discount_to_sector > 0.15:
        flags.append(f"PE disc {result.pe_discount_to_sector*100:.0f}%")

    if result.analyst_upside is not None and result.analyst_upside > 0.20:
        flags.append(f"Analyst ↑{result.analyst_upside*100:.0f}%")

    if result.news_label in ("confirmed_one_time", "likely_one_time"):
        flags.append("One-time catalyst")

    if result.revenue_qoq is not None and result.revenue_qoq > 0.03:
        flags.append(f"Rev +{result.revenue_qoq*100:.0f}% QoQ")

    if result.earnings_qoq is not None and result.earnings_qoq > 0.05:
        flags.append(f"EPS +{result.earnings_qoq*100:.0f}% QoQ")

    return flags[:4]  # cap at 4 flags to keep UI clean


def _pass2_analyze(ticker: str) -> Optional[ScanResult]:
    """Full analysis for a single ticker that passed the fast filter."""
    try:
        time.sleep(PASS2_DELAY)

        result = screener.run(ticker, groq_api_key=None)
        if result is None:
            return None

        setup_score = scorer.score(result)

        fund = get_fundamentals(ticker)
        if fund is None:
            fund = {}

        wacc_result = wacc_module.calculate(ticker, fund)

        flags = _build_flags(result, setup_score)

        return ScanResult(
            ticker=ticker,
            company_name=result.company_name,
            sector=result.sector,
            current_price=result.current_price,
            decline_from_high=result.decline_from_52w_high,
            setup_score=setup_score.total_score,
            grade=setup_score.grade,
            wacc=wacc_result.wacc,
            wacc_range=f"{wacc_result.wacc_low*100:.1f}%–{wacc_result.wacc_high*100:.1f}%",
            dcf_margin_of_safety=None,   # filled in pass 3
            dcf_intrinsic_value=None,
            ai_assessment="",
            ai_powered=False,
            flags=flags,
            analyst_upside=result.analyst_upside,
            consensus_rating=result.consensus_rating,
            forward_pe=result.forward_pe,
            sector_avg_pe=result.sector_avg_pe,
            scan_timestamp=datetime.now(),
        )
    except Exception:
        return None


def _pass3_ai_dcf(scan_result: ScanResult, fund: dict, wacc_result, claude_api_key: str) -> ScanResult:
    """Enrich a ScanResult with AI DCF analysis."""
    try:
        from analysis.wacc import WACCResult
        dcf_result = ai_dcf_run(
            symbol=scan_result.ticker,
            current_price=scan_result.current_price,
            fundamentals=fund,
            wacc_result=wacc_result,
            claude_api_key=claude_api_key,
        )
        if dcf_result.base.intrinsic_value:
            scan_result.dcf_intrinsic_value  = dcf_result.base.intrinsic_value
            scan_result.dcf_margin_of_safety = dcf_result.base.margin_of_safety
        scan_result.ai_assessment = dcf_result.ai_assessment
        scan_result.ai_powered    = dcf_result.ai_powered
    except Exception:
        pass
    return scan_result


def scan(
    universe_name: str,
    tickers:       list[str],
    min_score:     float = 0.50,
    max_results:   int   = 50,
    claude_api_key: Optional[str] = None,
    progress_cb:   Optional[Callable[[int, int, str], None]] = None,
    force_refresh: bool  = False,
) -> list[ScanResult]:
    """
    Run a full market scan over a list of tickers.

    Args:
        universe_name:  Display name (used for cache key)
        tickers:        List of ticker symbols to scan
        min_score:      Minimum setup score to include in results (0.0–1.0)
        max_results:    Maximum number of results to return
        claude_api_key: Optional Anthropic API key for AI DCF
        progress_cb:    Optional callback(current, total, status_msg)
        force_refresh:  If True, bypass cache

    Returns:
        List of ScanResult sorted by setup_score descending.
    """
    # ── Check cache ────────────────────────────────────────────────────────
    if not force_refresh:
        cached = load_cache(universe_name)
        if cached is not None:
            return [r for r in cached if r.setup_score >= min_score][:max_results]

    total = len(tickers)

    # ── PASS 1: Fast filter ────────────────────────────────────────────────
    pass1_results = []
    completed = 0

    def _p1_worker(t):
        nonlocal completed
        r = _pass1_check(t)
        completed += 1
        if progress_cb:
            progress_cb(completed, total, f"Pass 1: filtering {t}…")
        return r

    with ThreadPoolExecutor(max_workers=PASS1_WORKERS) as ex:
        futures = {ex.submit(_p1_worker, t): t for t in tickers}
        for fut in as_completed(futures):
            r = fut.result()
            if r:
                pass1_results.append(r["ticker"])

    # Sort by decline desc for more interesting candidates first
    pass1_results = list(dict.fromkeys(pass1_results))  # dedupe

    if progress_cb:
        progress_cb(total, total, f"Pass 1 complete — {len(pass1_results)}/{total} candidates")

    if not pass1_results:
        return []

    # ── PASS 2: Full scoring ───────────────────────────────────────────────
    scan_results = []
    completed_p2 = 0

    def _p2_worker(t):
        nonlocal completed_p2
        r = _pass2_analyze(t)
        completed_p2 += 1
        if progress_cb:
            progress_cb(completed_p2, len(pass1_results), f"Pass 2: analyzing {t}…")
        return r

    with ThreadPoolExecutor(max_workers=PASS2_WORKERS) as ex:
        futures = {ex.submit(_p2_worker, t): t for t in pass1_results}
        for fut in as_completed(futures):
            r = fut.result()
            if r and r.setup_score >= min_score:
                scan_results.append(r)

    # Sort by score
    scan_results.sort(key=lambda x: x.setup_score, reverse=True)

    # ── PASS 3: AI DCF on top N ────────────────────────────────────────────
    if claude_api_key and scan_results:
        top_n = scan_results[:AI_DCF_TOP_N]
        if progress_cb:
            progress_cb(0, len(top_n), f"AI DCF: analyzing top {len(top_n)} candidates…")

        for i, sr in enumerate(top_n):
            if progress_cb:
                progress_cb(i + 1, len(top_n), f"AI DCF: {sr.ticker}…")
            fund = get_fundamentals(sr.ticker) or {}
            from analysis.wacc import calculate as wacc_calc
            wacc_res = wacc_calc(sr.ticker, fund)
            sr = _pass3_ai_dcf(sr, fund, wacc_res, claude_api_key)
            scan_results[i] = sr

    # ── Trim and cache ─────────────────────────────────────────────────────
    final = scan_results[:max_results]
    _save_cache(universe_name, scan_results)  # cache full list (before max_results trim)

    return final
