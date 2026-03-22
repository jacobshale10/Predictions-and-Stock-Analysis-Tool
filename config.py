# config.py — All tunable constants for the Mean Reversion Stock Screener
# Edit these values to adjust the scoring weights, thresholds, and DCF defaults.

# ---------------------------------------------------------------------------
# SCORING WEIGHTS (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "price_decline":      0.20,  # % drop from 52-week high
    "pe_vs_sector":       0.20,  # Forward PE discount vs sector average
    "revenue_growth":     0.15,  # QoQ revenue growth
    "earnings_growth":    0.15,  # QoQ EPS growth
    "analyst_consensus":  0.15,  # Buy/Hold/Sell rating + price target gap
    "news_catalyst":      0.15,  # One-time vs structural damage classification
}

# ---------------------------------------------------------------------------
# PRICE DECLINE THRESHOLDS
# ---------------------------------------------------------------------------
DECLINE_MIN = 0.10        # Below this — no meaningful dislocation
DECLINE_SWEET_LOW = 0.15  # Sweet spot lower bound
DECLINE_SWEET_MID = 0.25  # Score = 0.7 zone
DECLINE_SWEET_HIGH = 0.35 # Score = 1.0 zone (peak — UPS/UNH zone)
DECLINE_UPPER = 0.40      # Score = 0.9 — large but manageable
DECLINE_DANGER = 0.55     # Above this — potential structural damage

# ---------------------------------------------------------------------------
# SETUP GRADE THRESHOLDS
# ---------------------------------------------------------------------------
STRONG_SETUP_THRESHOLD   = 0.72  # Green — clear mean reversion setup
MODERATE_SETUP_THRESHOLD = 0.50  # Yellow — some signals, proceed with caution

# ---------------------------------------------------------------------------
# DCF DEFAULTS
# ---------------------------------------------------------------------------
DEFAULT_WACC            = 0.09   # 9% — appropriate for large-cap investment grade
DEFAULT_TERMINAL_GROWTH = 0.025  # 2.5% — long-run GDP growth proxy
DCF_STAGE1_YEARS        = 5      # Years of analyst-informed growth
DCF_STAGE2_YEARS        = 5      # Years of decay to terminal (total = 10)
DCF_MAX_GROWTH_CAP      = 0.25   # Cap analyst growth estimates at 25%

# Bull/Bear WACC adjustments for scenario analysis
DCF_BULL_WACC_DELTA     = -0.01  # Bull case: WACC -1%
DCF_BEAR_WACC_DELTA     = +0.01  # Bear case: WACC +1%
DCF_BULL_GROWTH_DELTA   = +0.005 # Bull case: terminal growth +0.5%
DCF_BEAR_GROWTH_DELTA   = -0.005 # Bear case: terminal growth -0.5%

# ---------------------------------------------------------------------------
# NEWS CLASSIFIER
# ---------------------------------------------------------------------------
STRUCTURAL_KEYWORDS = [
    "market share loss", "losing customers to", "competitor gaining",
    "disruption", "secular decline", "obsolete", "replaced by",
    "fraud", "accounting restatement", "going concern",
    "covenant breach", "credit downgrade to junk", "class action",
    "sec investigation", "doj investigation",
]

ONE_TIME_KEYWORDS = [
    "one-time charge", "restructuring charge", "weather impact",
    "supply chain disruption", "temporary", "settlement",
    "one-time item", "guidance cut", "macro headwinds",
    "interest rate", "strike impact", "work stoppage",
    "cyber incident", "recall", "hurricane", "wildfire",
    "tariff", "foreign exchange", "fx headwind",
]

# Groq API endpoint for optional LLM classification
GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL     = "llama-3.1-8b-instant"

# ---------------------------------------------------------------------------
# ANALYST RATING SCORE MAP
# ---------------------------------------------------------------------------
RATING_SCORE_MAP = {
    "strong buy":   1.00,
    "buy":          0.80,
    "overweight":   0.80,
    "outperform":   0.80,
    "hold":         0.50,
    "neutral":      0.50,
    "market perform": 0.50,
    "underweight":  0.20,
    "underperform": 0.20,
    "sell":         0.00,
    "strong sell":  0.00,
}
