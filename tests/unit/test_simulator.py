"""
Unit Tests — simulator.py

Tests run_simulation() in isolation using an in-memory SQLite database.
No network calls are made. Ollama is not invoked.
"""
import sys
import os
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from database import create_stock_table, insert_stock_data
from simulator import run_simulation

import pandas as pd


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def make_connection():
    """Return an in-memory SQLite connection with the stock table created."""
    conn = sqlite3.connect(":memory:")
    create_stock_table(conn)
    return conn


def insert_rows(conn, ticker, rows):
    """Insert a list of (date, open, high, low, close, volume) tuples directly."""
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


# Fixed test data: 3 trading days
ROWS = [
    ("2023-01-02", 100.0, 105.0, 99.0, 102.0, 1_000_000),
    ("2023-01-03", 102.0, 107.0, 101.0, 108.0, 1_100_000),
    ("2023-01-04", 108.0, 112.0, 106.0, 110.0, 1_200_000),
]
BUY_PRICE  = 102.0   # close on 2023-01-02
SELL_PRICE = 110.0   # close on 2023-01-04
INVESTMENT = 1000.0
SHARES     = INVESTMENT / BUY_PRICE
FINAL      = SHARES * SELL_PRICE
PL         = FINAL - INVESTMENT
PCT        = (PL / INVESTMENT) * 100


# ------------------------------------------------------------------ #
# run_simulation                                                       #
# ------------------------------------------------------------------ #

class TestRunSimulationByAmount:
    """Tests for dollar-amount input mode."""

    def test_returns_none_for_empty_date_range(self):
        """Returns None when no rows exist in the requested date range."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2025-01-01", "2025-12-31",
                                investment_amount=INVESTMENT)
        assert result is None
        conn.close()

    def test_returns_none_for_unknown_ticker(self):
        """Returns None when the ticker has no data at all."""
        conn = make_connection()
        result = run_simulation(conn, "ZZZZ", "2023-01-02", "2023-01-04",
                                investment_amount=INVESTMENT)
        assert result is None
        conn.close()

    def test_returns_dict_with_correct_keys(self):
        """Result dict contains all expected keys."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                investment_amount=INVESTMENT)
        expected_keys = {
            "ticker", "start_date", "end_date",
            "investment_amount", "buy_price", "sell_price",
            "shares_purchased", "final_value", "profit_loss",
            "percent_return", "df",
        }
        assert expected_keys == set(result.keys())
        conn.close()

    def test_shares_purchased_equals_investment_divided_by_buy_price(self):
        """shares_purchased = investment_amount / buy_price."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                investment_amount=INVESTMENT)
        assert result["shares_purchased"] == pytest.approx(SHARES, rel=1e-6)
        conn.close()

    def test_final_value_equals_shares_times_sell_price(self):
        """final_value = shares_purchased * sell_price."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                investment_amount=INVESTMENT)
        assert result["final_value"] == pytest.approx(FINAL, rel=1e-6)
        conn.close()

    def test_profit_loss_equals_final_value_minus_investment(self):
        """profit_loss = final_value - investment_amount."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                investment_amount=INVESTMENT)
        assert result["profit_loss"] == pytest.approx(PL, rel=1e-6)
        conn.close()

    def test_percent_return_calculated_correctly(self):
        """percent_return = (profit_loss / investment_amount) * 100."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                investment_amount=INVESTMENT)
        assert result["percent_return"] == pytest.approx(PCT, rel=1e-6)
        conn.close()

    def test_buy_price_is_close_on_first_date(self):
        """buy_price is the close price on the earliest date in the range."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                investment_amount=INVESTMENT)
        assert result["buy_price"] == pytest.approx(BUY_PRICE, rel=1e-6)
        conn.close()

    def test_sell_price_is_close_on_last_date(self):
        """sell_price is the close price on the latest date in the range."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                investment_amount=INVESTMENT)
        assert result["sell_price"] == pytest.approx(SELL_PRICE, rel=1e-6)
        conn.close()

    def test_df_is_dataframe(self):
        """Result contains a non-empty DataFrame under key 'df'."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                investment_amount=INVESTMENT)
        assert isinstance(result["df"], pd.DataFrame)
        assert not result["df"].empty
        conn.close()

    def test_partial_date_range(self):
        """Simulation correctly uses only rows within the requested sub-range."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-03",
                                investment_amount=INVESTMENT)
        assert result["buy_price"]  == pytest.approx(102.0, rel=1e-6)
        assert result["sell_price"] == pytest.approx(108.0, rel=1e-6)
        conn.close()


class TestRunSimulationByShares:
    """Tests for share-count input mode."""

    def test_investment_amount_derived_from_shares_times_buy_price(self):
        """When shares provided, investment_amount = shares * buy_price."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        num_shares = 10.0
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                shares=num_shares)
        expected_amount = num_shares * BUY_PRICE
        assert result["investment_amount"] == pytest.approx(expected_amount, rel=1e-6)
        conn.close()

    def test_shares_purchased_matches_input(self):
        """shares_purchased equals the shares value that was passed in."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        num_shares = 7.5
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                shares=num_shares)
        assert result["shares_purchased"] == pytest.approx(num_shares, rel=1e-6)
        conn.close()

    def test_final_value_equals_shares_times_sell_price(self):
        """final_value = shares * sell_price regardless of input mode."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        num_shares = 5.0
        result = run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                                shares=num_shares)
        assert result["final_value"] == pytest.approx(num_shares * SELL_PRICE, rel=1e-6)
        conn.close()

    def test_raises_if_both_provided(self):
        """ValueError is raised when both investment_amount and shares are supplied."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        with pytest.raises(ValueError):
            run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04",
                           investment_amount=1000.0, shares=10.0)
        conn.close()

    def test_raises_if_neither_provided(self):
        """ValueError is raised when neither investment_amount nor shares is supplied."""
        conn = make_connection()
        insert_rows(conn, "AAPL", ROWS)
        with pytest.raises(ValueError):
            run_simulation(conn, "AAPL", "2023-01-02", "2023-01-04")
        conn.close()
