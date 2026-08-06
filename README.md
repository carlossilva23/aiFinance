# aiFinance

A Python command-line finance tool that fetches, stores, and analyzes stock market data. Supports technical analysis, investment simulation, portfolio simulation, and strategy backtesting — all powered by a local AI explanation layer via Ollama.

---

## Tech Stack

| Library | Purpose |
|---|---|
| **Python 3** | Core language |
| **pandas** | DataFrame manipulation for all indicator and strategy calculations |
| **yfinance** | Fetches historical OHLCV data from Yahoo Finance |
| **matplotlib** | Renders a closing-price chart for fetched tickers |
| **SQLite (sqlite3)** | Persists raw OHLCV data locally between sessions |
| **rich** | Formats terminal reports with tables, panels, and colour |
| **ollama** | Sends calculated metrics to a local LLM for plain-English AI summaries |

---

## Project Structure

```
aiFinance/
├── run.sh                  # Convenience launcher — runs the tool using the venv Python
├── requirements.txt
└── src/
    ├── main.py             # Entry point — menu-driven CLI, orchestrates all modes
    ├── data_fetcher.py     # Downloads OHLCV data via yfinance; handles standard and backtest refresh periods
    ├── database.py         # SQLite connection, schema, insert, query, and date-range query functions
    ├── analysis.py         # Computes all technical indicators and summary metrics on-the-fly
    ├── simulator.py        # Single-stock, weighted portfolio, and position-based portfolio simulation
    ├── backtester.py       # Buy & Hold, MA Crossover (50/200), and RSI Momentum (30/70) strategies
    ├── report_generator.py # Formats and prints all rich terminal reports
    └── ai_summary.py       # Builds structured prompts and calls the local Ollama LLM
```

---

## Setup

```bash
git clone <repo-url>
cd aiFinance
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Ollama must be installed and running locally for AI summaries. Install from [ollama.com](https://ollama.com) and pull a model:

```bash
ollama pull qwen2.5:7b
```

The model used is configured in [`src/ai_summary.py`](src/ai_summary.py) via the `MODEL` constant.

---

## Running the Tool

```bash
./run.sh
```

Or directly:

```bash
venv/bin/python src/main.py
```

---

## Modes

The tool presents a menu on startup:

```
What would you like to do?
  1. Analysis & AI summary
  2. Single-stock simulator
  3. Portfolio simulator (weighted)
  4. Position-based portfolio (per-lot entry)
  5. Strategy backtester
  6. Analysis + all simulators + backtester
```

### 1 — Analysis & AI Summary

Enter one or more tickers. For each:
- Fetches 1 year of OHLCV data (or prompts to refresh with 5 years if already stored)
- Displays a matplotlib closing-price chart
- Stores data in `stocks.db`
- Computes all technical indicators
- Prints a **blue** analysis report per ticker
- Generates a comparative **purple** AI summary across all tickers

**Indicators computed:** SMA 7/20/30/50, EMA 20, RSI (14), MACD (12/26/9), Bollinger Bands (20), rolling volatility, daily returns, highest/lowest close, largest single-day gain/loss

**Signal hints:** RSI overbought/oversold, price vs SMA 50, MACD crossover, Bollinger Band extremes

---

### 2 — Single-Stock Simulator

Simulate a buy-and-hold investment in one stock over a chosen date range.

- Choose input mode: **dollar amount** or **number of shares**
- Shows available date range from stored data
- Calculates shares purchased, final value, profit/loss, and return %
- Prints a **green** simulation report
- Generates an AI explanation of the result

---

### 3 — Portfolio Simulator (Weighted)

Simulate a multi-stock portfolio with a single shared date range.

- Enter multiple tickers
- Choose **equal weights** or **custom weights** (auto-normalised if they don't sum to 1.0)
- Enter a total investment amount
- Shows the narrowest shared date range across all tickers
- Calculates per-position and portfolio-level results
- Ranks best and worst performers
- Prints a **yellow** portfolio report
- Generates an AI comparative summary

---

### 4 — Position-Based Portfolio (Per-Lot Entry)

Simulate a portfolio where each position has its own entry date, exit date, and size — supports multiple lots of the same ticker at different prices.

- Enter positions one at a time (ticker, shares or dollars, entry date)
- Exit date defaults to the latest stored date for that ticker, or can be overridden
- Multiple lots of the same ticker are merged into a blended per-ticker summary
- Prints an **orange** report with three sections: Portfolio Totals, Per-Ticker Summary, Individual Lots
- Generates an AI summary that comments on the impact of different entry dates

**Example:** 20 shares of IBM in January + 20 more in February + 10 NVDA — each lot tracked independently, IBM blended automatically.

---

### 5 — Strategy Backtester

Test rule-based trading strategies against historical data.

**Sub-menu:**
```
1. Single ticker — compare all 3 strategies
2. Multiple tickers — one strategy across all tickers
```

**Single ticker mode:**
- Prompts to refresh with 10 years of history (needed for SMA 200)
- Runs all three strategies over the chosen date range
- Prints a **cyan** report comparing strategies side by side

**Multi-ticker mode:**
- Enter multiple tickers, pick one strategy, apply it to all
- Prints a **cyan** comparison table ranked best-to-worst ticker

**Strategies implemented:**

| Strategy | Logic |
|---|---|
| **Buy & Hold** | Buy on day 1, hold, sell on the last day — the baseline |
| **MA Crossover (50/200)** | Buy on golden cross (SMA 50 crosses above SMA 200), sell on death cross |
| **RSI Momentum (30/70)** | Buy when RSI crosses below 30 (oversold), sell when RSI crosses above 70 (overbought) |

**Metrics per strategy:** Final value, return %, max drawdown, volatility, trade count, full trade log

**Data refresh periods:**

| Context | Period fetched |
|---|---|
| First fetch (all modes) | 1 year |
| Refresh (analysis/simulator modes) | 5 years |
| Refresh (backtester modes) | 10 years |

---

## Example Output

**Analysis Report (blue):**
```
╭──────────────────────── AAPL — Analysis Report ────────────────────────╮
│  Metric                Value          Indicator     Value     Signal    │
│  Date Range            2024-08-06 →   SMA 20        $211.40   Above     │
│                        2025-08-05     SMA 50        $204.75   Bullish   │
│  Starting Price        $207.23        EMA 20        $209.90   Above     │
│  Ending Price          $311.00        RSI (14)      35.64     Neutral   │
│  Percent Return        +46.42%        MACD          2.0917    Bearish ↓ │
│  Avg Daily Volume      50,854,103     BB Upper      $345.80   -         │
│  Volatility (20d)      0.0236         BB Lower      $301.64   -         │
│  Highest Close         $340.08                                          │
│  Lowest Close          $212.41                                          │
│  Largest 1-Day Gain    +4.84%                                           │
│  Largest 1-Day Loss    -7.35%                                           │
╰─────────────────────────────────────────────────────────────────────────╯
```

**Strategy Backtest (cyan):**
```
╭────────── AAPL — Strategy Backtest (2023-01-01 to 2025-01-01) ──────────╮
│  Strategy               Final Value   Return    Drawdown   Vol    Trades │
│  Buy & Hold             $14,821       +48.2%    12.4%      0.019  1      │
│  RSI Momentum (30/70)   $13,204       +32.0%    8.1%       0.021  4      │
│  MA Crossover (50/200)  $11,890       +18.9%    6.2%       0.015  2      │
╰─────────────────────────────────────────────────────────────────────────╯
```

---

## Features

- Fetches 1 year of OHLCV data on first run; refreshes with 5 or 10 years depending on context
- Persists data locally in SQLite — no data lost between sessions; duplicates automatically skipped
- All indicators hand-built with pandas — no external TA libraries (demonstrates understanding)
- Three strategy backtests with drawdown, volatility, and trade-log tracking
- Position-based portfolio simulation with per-lot cost basis and blended returns
- Local AI explanations via Ollama — LLM only receives pre-calculated numbers, minimising hallucination
- 133 unit and integration tests covering all core logic

---

## Testing

```bash
# Unit and integration tests (fast, no network)
venv/bin/python -m pytest tests/unit/ tests/integration/ -q

# End-to-end smoke tests (slower, requires internet)
venv/bin/python -m pytest tests/e2e/ -v
```

See [`tests/README.md`](tests/README.md) for the full test inventory.

