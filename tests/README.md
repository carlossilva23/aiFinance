# aiFinance — Test Suite

## Structure

```
tests/
├── unit/
│   ├── test_analysis.py           — every indicator function in analysis.py (synthetic DataFrames, no DB, no network)
│   ├── test_database.py           — every function in database.py (in-memory SQLite, no network)
│   ├── test_simulator.py          — run_simulation() — single-stock math, dollar and share modes
│   ├── test_portfolio_simulator.py— run_portfolio_simulation() — weighted portfolio math and ranking
│   ├── test_position_portfolio.py — run_position_based_portfolio() — per-lot math, ticker merging, blended returns
│   └── test_backtester.py         — all three strategy engines, drawdown/volatility helpers, run_backtest()
├── integration/
│   └── test_pipeline.py           — store → retrieve → analyze chain (in-memory SQLite, no network)
└── e2e/
    └── test_smoke.py              — full fetch → store → analyze → report pipeline (live network, real yfinance data)
```

## Running the tests

Run from the project root. No activation needed — use `venv/bin/python` directly.

```bash
# Run all unit and integration tests (fast, no network — recommended for regular use)
venv/bin/python -m pytest tests/unit/ tests/integration/ -v

# Run only unit tests
venv/bin/python -m pytest tests/unit/ -v

# Run only integration tests
venv/bin/python -m pytest tests/integration/ -v

# Run end-to-end smoke tests (slower, requires internet + live yfinance data)
venv/bin/python -m pytest tests/e2e/ -v

# Run all tests including e2e
venv/bin/python -m pytest tests/ -v

# Run a single test file
venv/bin/python -m pytest tests/unit/test_backtester.py -v

# Run a single test class
venv/bin/python -m pytest tests/unit/test_analysis.py::TestCalcRsi -v

# Quiet summary (just pass/fail counts)
venv/bin/python -m pytest tests/unit/ tests/integration/ -q
```

## Test categories

| Category | Speed | Network | What it covers |
|---|---|---|---|
| **Unit** | Fast (<1s) | No | Every function in `analysis.py`, `database.py`, `simulator.py`, `backtester.py` in isolation |
| **Integration** | Fast (<1s) | No | `database.py` + `analysis.py` + `simulator.py` working together end-to-end with synthetic data |
| **E2E / Smoke** | Slow (~30s) | Yes | Full fetch → store → analyze → report pipeline with real market data from Yahoo Finance |

## Test count

| File | Tests | What it verifies |
|---|---|---|
| `test_analysis.py` | 34 | SMA/EMA/RSI/MACD/Bollinger/volatility/returns/price extremes — output types, NaN behaviour, correct math |
| `test_database.py` | 18 | Schema creation, insert, query, date ordering, duplicate protection, ticker existence check |
| `test_simulator.py` | 15 | Dollar-amount and share-count modes, math correctness, mutual-exclusion validation |
| `test_portfolio_simulator.py` | 18 | Equal/custom weights, allocation math, best/worst ranking, net-zero scenario |
| `test_position_portfolio.py` | 19 | Multi-lot merging, blended returns, exit date defaulting, dollar vs share modes |
| `test_backtester.py` | 13 | Drawdown helper, volatility helper, buy-and-hold correctness, MA flat-data no-trade, RSI flat-data no-trade, run_backtest None/keys/ranking |
| `test_pipeline.py` | 13 | Store → retrieve → analyze integration, duplicate protection, RSI range, MACD columns |
| `test_smoke.py` | 14 | Live yfinance fetch, MultiIndex flatten, row count, full pipeline, report generation |

**Total: 133 unit + integration tests** (plus 14 e2e smoke tests run separately)

## Notes

- Unit and integration tests use in-memory SQLite (`:memory:`) — no files are written to disk.
- E2E tests use pytest's `tmp_path` fixture — temporary `.db` files are cleaned up automatically after each test.
- The Ollama AI summary layer is **not** covered by automated tests — it requires a running Ollama server and is validated manually.
- The `backtester.py` MA Crossover strategy requires at least 200 rows of data for SMA 200 to produce valid signals. Tests use synthetic DataFrames with 210+ rows to cover this.
