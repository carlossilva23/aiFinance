# aiFinance

A Python finance tool that fetches, stores, and analyzes stock market data from the command line.

---

## Tech Stack

| Library | Purpose |
|---------|---------|
| **Python 3** | Core language |
| **pandas** | DataFrame manipulation for all indicator calculations |
| **yfinance** | Fetches historical OHLCV data from Yahoo Finance |
| **matplotlib** | Renders a closing-price chart for the requested tickers |
| **SQLite (sqlite3)** | Persists raw OHLCV data locally between sessions |
| **rich** | Formats the terminal analysis report with tables and panels |

---

## Project Structure

```
aiFinance/
└── src/
    ├── main.py             # Entry point — orchestrates input, fetch, store, and report
    ├── data_fetcher.py     # Prompts for tickers, downloads 1-year OHLCV data via yfinance
    ├── database.py         # SQLite connection, schema creation, insert and query functions
    ├── analysis.py         # Computes all technical indicators and summary metrics
    └── report_generator.py # Formats and prints the rich terminal report per ticker
```

---

## Setup

```bash
git clone <repo-url>
cd aiFinance
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Usage

Run the tool from the project root:

```bash
python src/main.py
```

You will be prompted to enter stock tickers one at a time. Press **Enter** on an empty line when you are done:

```
Please type in a stock: AAPL
Please type in a stock: NVDA
Please type in a stock:
```

After you finish entering tickers the tool will:

1. Fetch 1 year of historical OHLCV data for each ticker via yfinance
2. Display a closing-price chart with all tickers overlaid (matplotlib window)
3. Store the data in a local SQLite database (`stocks.db`)
4. Compute technical indicators on-the-fly for each ticker
5. Print a formatted analysis report in the terminal

---

## Example Output

```
╭─────────────────────────────── AAPL — Analysis Report ────────────────────────────────╮
│                                                                                        │
│  Metric                  Value          Indicator     Value       Signal               │
│  ──────────────────────  ─────────────  ────────────  ──────────  ──────────────────── │
│  Date Range              2024-01-02  →  SMA 20        $186.40     Price above SMA 20   │
│                          2025-01-02     SMA 50        $181.75     Price above SMA 50   │
│  Starting Price          $185.20                                  — bullish            │
│  Ending Price            $192.35        EMA 20        $187.90     Price above EMA 20   │
│  Percent Return          3.86%          RSI (14)      58.42       Neutral              │
│  Avg Daily Volume        55,234,100     MACD          0.8821      Bullish crossover     │
│  Volatility (20d)        0.0124         Signal Line   0.4103                           │
│  Highest Close           $199.62        BB Upper      $196.88     -                    │
│  Lowest Close            $164.08        BB Lower      $175.92     -                    │
│  Largest 1-Day Gain      4.33%                                                         │
│  Largest 1-Day Loss      -3.88%                                                        │
│                                                                                        │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

---

## Features

- Fetches 1 year of historical OHLCV data for any valid ticker via yfinance
- Persists data locally in SQLite — no data lost between sessions
- Computes SMA (7/20/30/50-day), EMA (20-day), RSI (14-period), MACD (12/26/9), Bollinger Bands (20-day), volatility, daily returns, and price extremes
- Displays a formatted terminal report with plain-language signal hints (overbought/oversold, bullish/bearish crossovers)
- No external TA libraries — all indicators hand-built with pandas


