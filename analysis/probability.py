"""
analysis/probability.py — Estimate probability of a strong recovery.

This is a calibrated rule-based estimate, NOT a statistically trained model.
Once 30+ trades are in the log, upgrade this to logistic regression.

Formula: P = score * 0.85 + dcf_margin * 0.15
(The 0.85 weight reflects that the setup score is more information-dense
than the DCF alone, given yfinance FCF data gaps.)
"""

from analysis.scorer import SetupScore


def estimate(setup_score: SetupScore, dcf_result) -> dict:
    """
    Returns:
        probability (float, 0.0–1.0)
        label (str): "High", "Moderate", "Low"
        color (str): "green", "orange", "red"
        description (str): plain-English explanation
    """
    score = setup_score.total_score

    # Use base DCF margin of safety if available and positive
    mos = dcf_result.base.margin_of_safety if dcf_result else None
    if mos is None or mos < 0:
        mos_contribution = 0.0
    else:
        mos_contribution = min(mos, 0.60)  # cap at 60% MoS for formula stability

    probability = score * 0.85 + mos_contribution * 0.15
    probability = round(min(max(probability, 0.0), 1.0), 3)

    if probability >= 0.68:
        label = "High"
        color = "green"
        description = (
            f"Strong fundamental setup with {probability*100:.0f}% estimated probability "
            "of recovery. Multiple dimensions confirm dislocation over deterioration."
        )
    elif probability >= 0.45:
        label = "Moderate"
        color = "orange"
        description = (
            f"Moderate setup ({probability*100:.0f}%). Some signals are positive but "
            "one or more dimensions show caution. Additional research recommended."
        )
    else:
        label = "Low"
        color = "red"
        description = (
            f"Weak setup ({probability*100:.0f}%). Multiple dimensions suggest this may be "
            "deterioration rather than temporary dislocation."
        )

    return {
        "probability": probability,
        "label":       label,
        "color":       color,
        "description": description,
        "score_contribution":    round(score * 0.85, 3),
        "dcf_contribution":      round(mos_contribution * 0.15, 3),
    }
