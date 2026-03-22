"""
data/news_classifier.py — Classify news catalysts as one-time vs structural.

Layer 1: Keyword pattern matching (always runs, no API required).
Layer 2: Optional Groq LLM override (requires API key from user).
Layer 3: Manual user override (handled in UI).

Classification labels (from most bullish to most bearish):
  confirmed_one_time → likely_one_time → uncertain → likely_structural → structural_damage
"""

import requests
from config import (
    STRUCTURAL_KEYWORDS,
    ONE_TIME_KEYWORDS,
    GROQ_API_URL,
    GROQ_MODEL,
)

LABELS = [
    "confirmed_one_time",
    "likely_one_time",
    "uncertain",
    "likely_structural",
    "structural_damage",
]

LABEL_DISPLAY = {
    "confirmed_one_time": "Confirmed One-Time Event",
    "likely_one_time":    "Likely One-Time Event",
    "uncertain":          "Uncertain — Needs Research",
    "likely_structural":  "Likely Structural Damage",
    "structural_damage":  "Structural Damage",
}


def classify_keywords(headlines: list[str]) -> tuple[str, str]:
    """
    Layer 1: keyword-based classification.
    Returns (label, reason_string).
    """
    if not headlines:
        return "uncertain", "No recent news headlines available."

    combined = " ".join(headlines).lower()

    structural_hits = [kw for kw in STRUCTURAL_KEYWORDS if kw in combined]
    one_time_hits   = [kw for kw in ONE_TIME_KEYWORDS   if kw in combined]

    net_score = len(structural_hits) - len(one_time_hits)

    if net_score <= -3:
        label  = "confirmed_one_time"
        reason = f"Strong one-time signals detected: {', '.join(one_time_hits[:3])}."
    elif net_score <= -1:
        label  = "likely_one_time"
        reason = f"One-time signals ({', '.join(one_time_hits[:2])}) outweigh structural signals."
    elif net_score == 0:
        label  = "uncertain"
        if one_time_hits or structural_hits:
            reason = f"Mixed signals — one-time: {one_time_hits[:2]}, structural: {structural_hits[:2]}."
        else:
            reason = "No strong signals detected in headlines. Manual review recommended."
    elif net_score == 1:
        label  = "likely_structural"
        reason = f"Structural signals detected: {', '.join(structural_hits[:2])}."
    else:
        label  = "structural_damage"
        reason = f"Multiple structural signals: {', '.join(structural_hits[:3])}."

    return label, reason


def classify_with_groq(headlines: list[str], groq_api_key: str) -> tuple[str, str]:
    """
    Layer 2: Groq LLM classification.
    Returns (label, reason_string) or falls back to keyword classification on failure.
    """
    if not groq_api_key or not headlines:
        return classify_keywords(headlines)

    headline_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines[:3]))
    prompt = f"""Given these recent stock news headlines:
{headline_text}

Classify the primary investment catalyst as EXACTLY ONE of these labels:
- confirmed_one_time: clear temporary event, business model intact
- likely_one_time: probably temporary, no lasting competitive damage
- uncertain: ambiguous, need more information to judge
- likely_structural: possibly lasting damage to competitive position
- structural_damage: clear permanent impairment to business

Respond with ONLY the label on the first line, then a one-sentence explanation on the second line.
Example:
likely_one_time
Guidance cut appears driven by temporary macro headwinds, not market share loss."""

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.1,
            },
            timeout=10,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        lines   = content.split("\n", 1)
        label   = lines[0].strip().lower().replace(" ", "_")
        reason  = lines[1].strip() if len(lines) > 1 else "No explanation provided."

        if label not in LABELS:
            # LLM returned unexpected label — fall back to keyword
            return classify_keywords(headlines)

        return label, f"[AI] {reason}"
    except Exception:
        # Any failure → fall back to keyword classification silently
        return classify_keywords(headlines)


def classify(headlines: list[str], groq_api_key: str = None) -> dict:
    """
    Main classification entry point.
    Returns a dict with: label, display_label, reason, source
    """
    if groq_api_key:
        label, reason = classify_with_groq(headlines, groq_api_key)
        source = "AI (Groq)" if reason.startswith("[AI]") else "Keywords (AI fallback)"
        reason = reason.replace("[AI] ", "")
    else:
        label, reason = classify_keywords(headlines)
        source = "Keyword Analysis"

    return {
        "label":         label,
        "display_label": LABEL_DISPLAY.get(label, label),
        "reason":        reason,
        "source":        source,
        "headlines_used": headlines[:3],
    }
