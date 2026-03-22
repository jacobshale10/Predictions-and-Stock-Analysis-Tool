# config.py — All tunable constants for the Mean Reversion Stock Screener
# Edit these values to adjust the scoring weights, thresholds, and DCF defaults.

# ---------------------------------------------------------------------------
# SCORING WEIGHTS (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "price_decline":        0.20,   # % drop from 52-week high
    "pe_vs_sector":         0.15,   # Forward PE discount vs sector average
    "revenue_growth":       0.12,   # QoQ revenue growth
    "earnings_growth":      0.12,   # QoQ EPS growth
    "analyst_consensus":    0.13,   # Buy/Hold/Sell rating + price target gap
    "news_catalyst":        0.13,   # One-time vs structural damage classification
    "dcf_margin_of_safety": 0.15,   # DCF intrinsic value margin of safety (AI or quant)
}

# ---------------------------------------------------------------------------
# PRICE DECLINE THRESHOLDS
# ---------------------------------------------------------------------------
DECLINE_MIN       = 0.10   # Below this — no meaningful dislocation
DECLINE_SWEET_LOW = 0.15   # Sweet spot lower bound
DECLINE_SWEET_MID = 0.25   # Score = 0.7 zone
DECLINE_SWEET_HIGH= 0.35   # Score = 1.0 zone (peak — UPS/UNH zone)
DECLINE_UPPER     = 0.40   # Score = 0.9 — large but manageable
DECLINE_DANGER    = 0.55   # Above this — potential structural damage

# ---------------------------------------------------------------------------
# SETUP GRADE THRESHOLDS
# ---------------------------------------------------------------------------
STRONG_SETUP_THRESHOLD   = 0.72   # Green — clear mean reversion setup
MODERATE_SETUP_THRESHOLD = 0.50   # Yellow — some signals, proceed with caution

# ---------------------------------------------------------------------------
# DCF DEFAULTS
# ---------------------------------------------------------------------------
DEFAULT_TERMINAL_GROWTH = 0.025   # 2.5% — long-run GDP growth proxy
DCF_STAGE1_YEARS        = 5       # Years of analyst-informed growth
DCF_STAGE2_YEARS        = 5       # Years of decay to terminal (total = 10)
DCF_MAX_GROWTH_CAP      = 0.25    # Cap analyst growth estimates at 25%

# Kept for backward compatibility (auto-WACC replaces this in the UI)
DEFAULT_WACC            = 0.09

# Bull/Bear terminal growth adjustments for scenario analysis
DCF_BULL_GROWTH_DELTA   = +0.005  # Bull case: terminal growth +0.5%
DCF_BEAR_GROWTH_DELTA   = -0.005  # Bear case: terminal growth -0.5%

# ---------------------------------------------------------------------------
# WACC AUTO-CALCULATION
# ---------------------------------------------------------------------------
WACC_EQUITY_RISK_PREMIUM = 0.055   # Damodaran US long-run ERP
WACC_DEFAULT_BETA        = 1.0     # Fallback beta if unavailable
WACC_DEFAULT_TAX_RATE    = 0.21    # US federal statutory rate fallback
WACC_RF_FALLBACK         = 0.043   # ~4.3% if live Treasury fetch fails
WACC_MIN                 = 0.06    # Floor
WACC_MAX                 = 0.16    # Ceiling

# ---------------------------------------------------------------------------
# AI MODEL CONFIG
# ---------------------------------------------------------------------------
AI_MODEL             = "claude-sonnet-4-6"
AI_DCF_TOP_N         = 15          # Run AI DCF on top N candidates in batch scan
AI_MAX_TOKENS        = 512         # Response length limit for DCF JSON

# ---------------------------------------------------------------------------
# BATCH SCAN CONFIG
# ---------------------------------------------------------------------------
SCAN_PASS1_WORKERS   = 8           # Threads for fast_info filter pass
SCAN_PASS2_WORKERS   = 4           # Threads for full analysis pass
SCAN_PASS1_DELAY     = 0.05        # Seconds between pass-1 requests
SCAN_PASS2_DELAY     = 0.3         # Seconds between pass-2 requests
SCAN_MIN_MARKET_CAP  = 2e9         # $2B minimum market cap
SCAN_MIN_DECLINE     = 0.12        # 12% decline from 52W high required
SCAN_CACHE_TTL_HOURS = 6           # Cache scan results for 6 hours

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

# Groq API endpoint for optional LLM news classification
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.1-8b-instant"

# ---------------------------------------------------------------------------
# ANALYST RATING SCORE MAP
# ---------------------------------------------------------------------------
RATING_SCORE_MAP = {
    "strong buy":     1.00,
    "buy":            0.80,
    "overweight":     0.80,
    "outperform":     0.80,
    "hold":           0.50,
    "neutral":        0.50,
    "market perform": 0.50,
    "underweight":    0.20,
    "underperform":   0.20,
    "sell":           0.00,
    "strong sell":    0.00,
}
