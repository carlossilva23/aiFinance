"""
Unit Tests — backtester.py

Tests each strategy function and the run_backtest() entry point using an
in-memory SQLite database with synthetic data. No network calls are made.
"""
import sys
import os
import sqlite3

import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from database import create_stock_table
from backtester import (
    _calc_drawdown,
    _calc_volatility,
    run_buy_and_hold,
    run_ma_crossover,
    run_rsi_momentum,
    run_backtest,
)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

EXPECTED_KEYS = {
    "strategy_name", "initial_cash", "final_value", "profit_loss",
    "percent_return", "trade_count", "max_drawdown", "volatility", "trades",
}

BACKTEST_KEYS = {
    "ticker", "start_date", "end_date", "initial_cash",
    "results", "best_strategy", "worst_strategy",
}


def make_connection():
    """Return an in-memory SQLite connection with the stock table created."""
    conn = sqlite3.connect(":memory:")
    create_stock_table(conn)
    return conn


def insert_rows(conn, ticker, rows):
    """Insert a list of (date, open, high, low, close, volume) tuples."""
    cursor = conn.cursor()
    for date, open_, high, low, close, volume in rows:
        cursor.execute(
            """
            INSERT OR IGNORE INTO portfolio
                (ticker, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ticker, date, open_, high, low, close, volume),
        )
    conn.commit()


def make_rising_df(n=210):
    """Return a DataFrame with n rows of steadily rising close prices."""
    dates  = pd.date_range("2020-01-01", periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    closes = [100.0 + i * 0.5 for i in range(n)]
    return pd.DataFrame({
        "date":   dates,
        "open":   closes,
        "high":   [c + 1 for c in closes],
        "low":    [c - 1 for c in closes],
        "close":  closes,
        "volume": [1_000_000] * n,
    })


def make_flat_df(n=210, price=100.0):
    """Return a DataFrame with n rows of a constant close price."""
    dates = pd.date_range("2020-01-01", periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    return pd.DataFrame({
        "date":   dates,
        "open":   [price] * n,
        "high":   [price] * n,
        "low":    [price] * n,
        "close":  [price] * n,
        "volume": [1_000_000] * n,
    })


def make_db_with_rising(n=210):
    """Return a connection populated with n rising-price rows for AAPL."""
    conn = make_connection()
    df   = make_rising_df(n)
    rows = list(zip(df["date"], df["open"], df["high"], df["low"], df["close"], df["volume"]))
    insert_rows(conn, "AAPL", rows)
    return conn, df


# ------------------------------------------------------------------ #
# _calc_drawdown                                                       #
# ------------------------------------------------------------------ #

class TestCalcDrawdown:
    def test_zero_drawdown_for_monotonically_increasing(self):
        """No drawdown when values only go up."""
        values = [100.0, 110.0, 120.0, 130.0]
        assert _calc_drawdown(values) == pytest.approx(0.0)

    def test_known_drawdown(self):
        """Peak=200 then trough=100 → drawdown = 50%."""
        values = [100.0, 200.0, 100.0]
        assert _calc_drawdown(values) == pytest.approx(0.5)


# ------------------------------------------------------------------ #
# run_buy_and_hold                                                     #
# ------------------------------------------------------------------ #

class TestRunBuyAndHold:
    def test_returns_correct_keys(self):
        """Result dict contains all expected keys."""
        df = make_rising_df(10)
        result = run_buy_and_hold(df, 10000.0)
        assert set(result.keys()) == EXPECTED_KEYS

    def test_trade_count_is_one(self):
        """Buy & Hold always completes exactly one round trip."""
        df = make_rising_df(10)
        result = run_buy_and_hold(df, 10000.0)
        assert result["trade_count"] == 1

    def test_final_value_equals_shares_times_last_close(self):
        """final_value = (initial_cash / first_close) * last_close."""
        df         = make_rising_df(10)
        initial    = 10000.0
        shares     = initial / df["close"].iloc[0]
        expected   = shares * df["close"].iloc[-1]
        result     = run_buy_and_hold(df, initial)
        assert result["final_value"] == pytest.approx(expected, rel=1e-9)

    def test_profit_loss_equals_final_minus_initial(self):
        """profit_loss = final_value - initial_cash."""
        df     = make_rising_df(10)
        result = run_buy_and_hold(df, 10000.0)
        assert result["profit_loss"] == pytest.approx(
            result["final_value"] - result["initial_cash"], rel=1e-9
        )

    def test_zero_return_on_flat_prices(self):
        """percent_return is 0 when the price never changes."""
        df     = make_flat_df(5)
        result = run_buy_and_hold(df, 10000.0)
        assert result["percent_return"] == pytest.approx(0.0, abs=1e-9)


# ------------------------------------------------------------------ #
# run_ma_crossover                                                     #
# ------------------------------------------------------------------ #

class TestRunMaCrossover:
    def test_returns_correct_keys(self):
        """Result dict contains all expected keys."""
        df = make_rising_df()
        result = run_ma_crossover(df, 10000.0)
        assert set(result.keys()) == EXPECTED_KEYS

    def test_no_trades_on_flat_prices(self):
        """No crossover ever fires on a flat price series → 0 trades, cash unchanged."""
        df     = make_flat_df()
        result = run_ma_crossover(df, 10000.0)
        assert result["trade_count"] == 0
        assert result["final_value"] == pytest.approx(10000.0, rel=1e-9)


# ------------------------------------------------------------------ #
# run_rsi_momentum                                                     #
# ------------------------------------------------------------------ #

class TestRunRsiMomentum:
    def test_returns_correct_keys(self):
        """Result dict contains all expected keys."""
        df = make_rising_df()
        result = run_rsi_momentum(df, 10000.0)
        assert set(result.keys()) == EXPECTED_KEYS

    def test_no_trades_on_flat_prices(self):
        """RSI is undefined/NaN on flat prices — no signal fires, cash unchanged."""
        df     = make_flat_df()
        result = run_rsi_momentum(df, 10000.0)
        assert result["trade_count"] == 0
        assert result["final_value"] == pytest.approx(10000.0, rel=1e-9)


# ------------------------------------------------------------------ #
# run_backtest                                                         #
# ------------------------------------------------------------------ #

class TestRunBacktest:
    def test_returns_none_for_empty_date_range(self):
        """Returns None when no rows match the requested date range."""
        conn, _ = make_db_with_rising()
        result  = run_backtest(conn, "AAPL", "2099-01-01", "2099-12-31")
        assert result is None
        conn.close()

    def test_returns_dict_with_correct_top_level_keys(self):
        """Returned dict contains all required top-level keys."""
        conn, df = make_db_with_rising()
        start    = df["date"].iloc[0]
        end      = df["date"].iloc[-1]
        result   = run_backtest(conn, "AAPL", start, end)
        assert set(result.keys()) == BACKTEST_KEYS
        conn.close()

    def test_results_list_has_three_entries(self):
        """Exactly three strategy results are returned."""
        conn, df = make_db_with_rising()
        start    = df["date"].iloc[0]
        end      = df["date"].iloc[-1]
        result   = run_backtest(conn, "AAPL", start, end)
        assert len(result["results"]) == 3
        conn.close()

    def test_results_ranked_by_percent_return_descending(self):
        """results list is sorted best-to-worst by percent_return."""
        conn, df = make_db_with_rising()
        start    = df["date"].iloc[0]
        end      = df["date"].iloc[-1]
        result   = run_backtest(conn, "AAPL", start, end)
        returns  = [r["percent_return"] for r in result["results"]]
        assert returns == sorted(returns, reverse=True)
        conn.close()
