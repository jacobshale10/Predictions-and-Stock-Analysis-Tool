"""
analysis/scorer.py — Weighted scoring engine.

Takes a ScreenerResult and produces a SetupScore with:
  - 7 sub-scores (each 0.0–1.0), including DCF margin of safety
  - weighted total score (0.0–1.0)
  - grade: STRONG SETUP / MODERATE SETUP / WEAK SETUP

Sub-scoring functions are calibrated so that UPS (2023), UNH (2024),
and INTU (2024) all score in the 0.72–0.85 range (STRONG SETUP).
"""

from dataclasses import dataclass
from typing import Optional

from analysis.screener import ScreenerResult
from config import (
    WEIGHTS,
    DECLINE_MIN, DECLINE_SWEET_LOW, DECLINE_SWEET_MID,
    DECLINE_SWEET_HIGH, DECLINE_UPPER, DECLINE_DANGER,
    STRONG_SETUP_THRESHOLD, MODERATE_SETUP_THRESHOLD,
    RATING_SCORE_MAP,
)


@dataclass
class SetupScore:
    # Raw sub-scores (0.0–1.0)
    price_decline_score:      float
    pe_vs_sector_score:       float
    revenue_growth_score:     float
    earnings_growth_score:    float
    analyst_consensus_score:  float
    news_catalyst_score:      float
    dcf_mos_score:            float   # DCF margin of safety (0.4 neutral if unavailable)

    # Weighted total
    total_score: float

    # Grade
    grade: str          # "STRONG SETUP" | "MODERATE SETUP" | "WEAK SETUP"
    grade_color: str    # "green" | "yellow" | "red"

    # Flags for UI warnings
    pe_negative: bool = False
    eps_negative: bool = False
    missing_data: list[str] = None

    def sub_scores_dict(self) -> dict:
        return {
            "Price Decline":       self.price_decline_score,
            "PE vs Sector":        self.pe_vs_sector_score,
            "Revenue Growth":      self.revenue_growth_score,
            "Earnings Growth":     self.earnings_growth_score,
            "Analyst Consensus":   self.analyst_consensus_score,
            "News Catalyst":       self.news_catalyst_score,
            "DCF Margin of Safety": self.dcf_mos_score,
        }


# ---------------------------------------------------------------------------
# Individual sub-scoring functions
# ---------------------------------------------------------------------------

def _score_price_decline(decline: float) -> float:
    """
    Sweet spot: 25–35% from 52w high = score 1.0
    < 10%: no meaningful dislocation
    > 55%: potential structural damage
    """
    d = decline
    if d < DECLINE_MIN:
        return max(0.0, d / DECLINE_MIN * 0.3)
    if d < DECLINE_SWEET_LOW:
        # 10–15%: linear 0.3 → 0.5
        return 0.3 + (d - DECLINE_MIN) / (DECLINE_SWEET_LOW - DECLINE_MIN) * 0.2
    if d < DECLINE_SWEET_MID:
        # 15–25%: linear 0.5 → 0.7
        return 0.5 + (d - DECLINE_SWEET_LOW) / (DECLINE_SWEET_MID - DECLINE_SWEET_LOW) * 0.2
    if d < DECLINE_SWEET_HIGH:
        # 25–35%: peak zone 0.7 → 1.0
        return 0.7 + (d - DECLINE_SWEET_MID) / (DECLINE_SWEET_HIGH - DECLINE_SWEET_MID) * 0.3
    if d < DECLINE_UPPER:
        # 35–40%: 1.0 → 0.9
        return 1.0 - (d - DECLINE_SWEET_HIGH) / (DECLINE_UPPER - DECLINE_SWEET_HIGH) * 0.1
    if d < DECLINE_DANGER:
        # 40–55%: 0.9 → 0.3
        return 0.9 - (d - DECLINE_UPPER) / (DECLINE_DANGER - DECLINE_UPPER) * 0.6
    # > 55%: potential structural damage
    return 0.1


def _score_pe_vs_sector(pe_discount: Optional[float], pe_negative: bool) -> float:
    """
    pe_discount > 0 means stock is cheaper than sector average.
    15–30% discount = score 1.0
    Premium to sector = score 0.2
    Negative PE = score 0.0
    """
    if pe_negative:
        return 0.0
    if pe_discount is None:
        return 0.4  # neutral when data unavailable
    d = pe_discount
    if d < 0:
        return 0.2  # premium to sector
    if d < 0.05:
        return 0.4
    if d < 0.15:
        return 0.4 + (d - 0.05) / 0.10 * 0.3   # 0.4 → 0.7
    if d < 0.30:
        return 0.7 + (d - 0.15) / 0.15 * 0.3   # 0.7 → 1.0
    # > 30% discount: slightly penalized (uncertainty)
    return 0.8


def _score_growth(growth: Optional[float], eps_positive: bool = True) -> float:
    """
    Used for both revenue QoQ and earnings QoQ.
    eps_positive=False hard-caps score at 0.3 (company losing money).
    """
    if growth is None:
        return 0.4  # neutral when data unavailable

    if growth < -0.05:
        score = 0.0
    elif growth < 0:
        score = 0.0 + (growth + 0.05) / 0.05 * 0.2  # -5% to 0% → 0.0 to 0.2
    elif growth < 0.03:
        score = 0.2 + growth / 0.03 * 0.3   # 0 to 3% → 0.2 to 0.5
    elif growth < 0.08:
        score = 0.5 + (growth - 0.03) / 0.05 * 0.3  # 3% to 8% → 0.5 to 0.8
    else:
        score = min(1.0, 0.8 + (growth - 0.08) / 0.12 * 0.2)  # 8%+ → 0.8 to 1.0

    if not eps_positive:
        score = min(score, 0.3)

    return round(score, 4)


def _score_analyst_consensus(
    consensus_rating: str,
    analyst_upside: Optional[float],
) -> float:
    """
    Combines:
      - Rating label → 0.0–1.0
      - Target gap (analyst upside) → 0.0–1.0
    Returns weighted average (50/50).
    """
    # Rating component
    rating_lower = consensus_rating.lower()
    rating_score = RATING_SCORE_MAP.get(rating_lower, 0.5)
    # Partial match fallback
    if rating_score == 0.5 and rating_lower not in RATING_SCORE_MAP:
        for key, val in RATING_SCORE_MAP.items():
            if key in rating_lower:
                rating_score = val
                break

    # Target gap component
    if analyst_upside is None:
        target_score = 0.4  # neutral
    elif analyst_upside < 0:
        target_score = 0.0
    elif analyst_upside < 0.10:
        target_score = 0.3
    elif analyst_upside < 0.20:
        target_score = 0.6
    elif analyst_upside < 0.35:
        target_score = 0.9
    else:
        target_score = 1.0

    return round((rating_score + target_score) / 2, 4)


def _score_news_catalyst(label: str) -> float:
    catalyst_scores = {
        "confirmed_one_time":  1.0,
        "likely_one_time":     0.8,
        "uncertain":           0.5,
        "likely_structural":   0.2,
        "structural_damage":   0.0,
    }
    return catalyst_scores.get(label, 0.5)


def _score_dcf_mos(margin_of_safety: Optional[float]) -> float:
    """
    Score the DCF margin of safety.
    Positive MoS = stock trading below intrinsic value (good).
    """
    if margin_of_safety is None:
        return 0.4  # neutral when data unavailable
    m = margin_of_safety
    if m < -0.30:
        return 0.0   # >30% overvalued
    if m < 0:
        return 0.0 + (m + 0.30) / 0.30 * 0.30   # -30% to 0%: 0.0 → 0.3
    if m < 0.10:
        return 0.30 + m / 0.10 * 0.20            # 0–10% MoS: 0.3 → 0.5
    if m < 0.25:
        return 0.50 + (m - 0.10) / 0.15 * 0.30  # 10–25% MoS: 0.5 → 0.8
    if m < 0.40:
        return 0.80 + (m - 0.25) / 0.15 * 0.20  # 25–40% MoS: 0.8 → 1.0
    return 1.0   # >40% MoS: fully undervalued


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score(result: ScreenerResult, dcf_margin_of_safety: Optional[float] = None) -> SetupScore:
    """
    Compute the weighted setup score from a ScreenerResult.

    Args:
        result:                ScreenerResult from screener.run()
        dcf_margin_of_safety:  Optional DCF margin of safety (from ai_dcf or dcf module).
                               If None, the DCF dimension uses a neutral score (0.4).
    """
    pe_negative = (
        result.forward_pe is not None and result.forward_pe < 0
    ) or (
        result.trailing_pe is not None and result.trailing_pe < 0
    )

    s_decline   = _score_price_decline(result.decline_from_52w_high)
    s_pe        = _score_pe_vs_sector(result.pe_discount_to_sector, pe_negative)
    s_revenue   = _score_growth(result.revenue_qoq)
    s_earnings  = _score_growth(result.earnings_qoq, eps_positive=result.eps_positive)
    s_analyst   = _score_analyst_consensus(result.consensus_rating, result.analyst_upside)
    s_catalyst  = _score_news_catalyst(result.news_label)
    s_dcf       = _score_dcf_mos(dcf_margin_of_safety)

    total = (
        WEIGHTS["price_decline"]        * s_decline  +
        WEIGHTS["pe_vs_sector"]         * s_pe       +
        WEIGHTS["revenue_growth"]       * s_revenue  +
        WEIGHTS["earnings_growth"]      * s_earnings +
        WEIGHTS["analyst_consensus"]    * s_analyst  +
        WEIGHTS["news_catalyst"]        * s_catalyst +
        WEIGHTS["dcf_margin_of_safety"] * s_dcf
    )
    total = round(total, 4)

    if total >= STRONG_SETUP_THRESHOLD:
        grade = "STRONG SETUP"
        color = "green"
    elif total >= MODERATE_SETUP_THRESHOLD:
        grade = "MODERATE SETUP"
        color = "orange"
    else:
        grade = "WEAK SETUP"
        color = "red"

    return SetupScore(
        price_decline_score=round(s_decline, 4),
        pe_vs_sector_score=round(s_pe, 4),
        revenue_growth_score=round(s_revenue, 4),
        earnings_growth_score=round(s_earnings, 4),
        analyst_consensus_score=round(s_analyst, 4),
        news_catalyst_score=round(s_catalyst, 4),
        dcf_mos_score=round(s_dcf, 4),
        total_score=total,
        grade=grade,
        grade_color=color,
        pe_negative=pe_negative,
        eps_negative=not result.eps_positive,
        missing_data=result.missing_fields,
    )
