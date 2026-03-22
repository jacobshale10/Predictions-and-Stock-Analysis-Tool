# Mean Reversion Stock Screener

A stock analysis tool for identifying **temporary price dislocations** — stocks that dropped 15–40% on negative news while their fundamentals remain intact.

Inspired by setups like UPS (2023 guidance cut), UNH (2024 regulatory overhang), and INTU (2024 macro guidance reset). All three recovered strongly within 6–18 months.

---

## What It Does

- **Scores stocks across 6 dimensions**: price decline, PE vs sector, revenue growth, earnings growth, analyst consensus, and news catalyst type
- **Grades setups**: Strong (≥0.72), Moderate (≥0.50), or Weak
- **DCF valuation**: two-stage model with Base/Bull/Bear scenarios and WACC slider
- **News catalyst classifier**: keyword-based (always works) + optional AI (Groq API key)
- **Trade log**: track entries, exits, and P&L in a local SQLite database
- **Backtest summary**: correlate setup scores with actual trade outcomes over time

---

## Setup (do this once — takes 5–10 minutes)

### Step 1: Install Python

- Go to **python.org/downloads**
- Download Python **3.11 or newer**
- **Windows**: check "Add Python to PATH" during installation
- **Mac**: Python may already be installed — open Terminal and type: `python3 --version`

### Step 2: Download this project

- Click the green **Code** button on GitHub → **Download ZIP**
- Unzip to your Desktop or Documents folder

### Step 3: Open a terminal in the project folder

- **Mac**: right-click the folder in Finder → "New Terminal at Folder"
- **Windows**: hold **Shift + right-click** the folder → "Open PowerShell window here"

### Step 4: Install the required libraries (copy-paste exactly)

```
pip install -r requirements.txt
```

### Step 5: Run the app

```
streamlit run app.py
```

The app will open in your browser automatically at **http://localhost:8501**

To stop the app: go back to the terminal and press **Ctrl+C**

---

## Daily Use

1. Open terminal in the project folder
2. Type: `streamlit run app.py`
3. Browser opens automatically
4. Type a ticker in the search box and click **Analyze**

---

## Optional: AI-Powered News Classification

The tool classifies news catalysts automatically using keyword matching. For smarter classification:

1. Go to **console.groq.com** and create a free account (no credit card needed for basic usage)
2. Create an API key
3. Paste the key into the **Groq API Key** field in the sidebar
4. News will be classified using `llama-3.1-8b-instant` (free model)

---

## Tuning the Scoring Weights

All scoring weights and thresholds are in **`config.py`** — this is the only file you need to edit to customize the tool's behavior.

Key settings:
- `WEIGHTS` — how much each dimension contributes to the total score
- `STRONG_SETUP_THRESHOLD` — currently 0.72 (scores above this = green)
- `DEFAULT_WACC` — default discount rate for the DCF model (9%)

---

## Project Structure

```
app.py                  ← Run this to start the app
requirements.txt        ← Python packages needed
config.py               ← All tunable settings (weights, thresholds)
data/                   ← Yahoo Finance data fetching
analysis/               ← Scoring, DCF, and probability models
ui/                     ← All screens and charts
database/               ← Trade log (SQLite)
trades.db               ← Your trade data (created automatically)
```

---

## Data Source

All market data comes from **Yahoo Finance** via the [yfinance](https://github.com/ranaroussi/yfinance) library (free, no API key required). Data includes prices, fundamentals, analyst targets, and recent news headlines.

**Limitations:**
- Quarterly revenue/EPS data may be missing for recent filings
- Analyst data is not always available for all tickers
- Free cash flow data varies by company — the DCF will display a warning when unavailable

---

## Disclaimer

This tool is for **personal research and educational purposes only**. Nothing here is financial advice. Always do your own due diligence before making investment decisions.
