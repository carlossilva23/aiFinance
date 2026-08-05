# aiFinance — Test Suite

## Structure

```
tests/
├── unit/
│   ├── test_database.py   — tests each database.py function in isolation (in-memory SQLite, no network)
│   └── test_analysis.py   — tests each indicator calculation with synthetic DataFrames (no DB, no network)
├── integration/
│   └── test_pipeline.py   — tests the store → retrieve → analyze chain together (in-memory SQLite, no network)
└── e2e/
    └── test_smoke.py      — full pipeline smoke tests with live yfinance data (network required)
```

## Running the tests

Make sure you are in the project root and the virtual environment is active (or use `venv/bin/python`).

```bash
# Run all tests
venv/bin/python -m pytest tests/ -v

# Run only unit tests (fast, no network)
venv/bin/python -m pytest tests/unit/ -v

# Run only integration tests (fast, no network)
venv/bin/python -m pytest tests/integration/ -v

# Run end-to-end smoke tests (slower, requires internet)
venv/bin/python -m pytest tests/e2e/ -v

# Run a single test file
venv/bin/python -m pytest tests/unit/test_analysis.py -v

# Run a single test class
venv/bin/python -m pytest tests/unit/test_analysis.py::TestCalcRsi -v
```

## Test categories

| Category | Speed | Network | What it covers |
|---|---|---|---|
| **Unit** | Fast | No | Each function in `database.py` and `analysis.py` in complete isolation |
| **Integration** | Fast | No | `database.py` + `analysis.py` working together with synthetic data |
| **E2E / Smoke** | Slow | Yes | Full fetch → store → analyze → report pipeline with real market data |

## Notes

- Unit and integration tests use in-memory SQLite (`:memory:`) — no files are written to disk.
- E2E tests use `tmp_path` (pytest fixture) to write temporary `.db` files that are cleaned up automatically.
- The Ollama AI summary is **not** tested here — it requires a running Ollama server and is covered by manual testing.
