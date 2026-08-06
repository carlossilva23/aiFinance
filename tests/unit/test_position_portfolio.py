"""
Unit Tests — position-based portfolio simulation (run_position_based_portfolio)

Tests per-lot math, ticker merging, and portfolio totals using in-memory SQLite.
No network calls or Ollama invocations are made.
"""
import sys
import os
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from database import create_stock_table
from simulator import run_position_based_portfolio


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def make_connection():
    conn = sqlite3.connect(":memory:")
    create_stock_table(conn)
    return conn


def insert_rows(conn, ticker, rows):
    cursor = conn.cursor()
    for date, open_, high, low, close, volume in rows:
        cursor.execute(
            "INSERT OR IGNORE INTO portfolio "
            "(ticker, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
            (ticker, date, open_, high, low, close, volume),
        )
    conn.commit()


# IBM: Jan close=100, Feb close=110, Mar close=120  (steady rise)
IBM_ROWS = [
    ("2023-01-02", 99.0, 102.0, 98.0,  100.0, 1_000_000),
    ("2023-02-01", 109.0, 112.0, 108.0, 110.0, 1_100_000),
    ("2023-03-01", 119.0, 122.0, 118.0, 120.0, 1_200_000),
]
# NVDA: Jan close=200, Mar close=180  (-10%)
NVDA_ROWS = [
    ("2023-01-02", 199.0, 205.0, 195.0, 200.0, 500_000),
    ("2023-03-01", 179.0, 185.0, 175.0, 180.0, 600_000),
]


# ------------------------------------------------------------------ #
# Basic behaviour                                                      #
# ------------------------------------------------------------------ #

class TestBasicBehaviour:
    def test_returns_none_when_no_lots_have_data(self):
        """Returns None when all positions fall outside stored date range."""
        conn = make_connection()
        insert_rows(conn, "IBM", IBM_ROWS)
        result = run_position_based_portfolio(conn, [
            {"ticker": "IBM", "entry_date": "2099-01-01", "exit_date": "2099-12-31",
             "shares": 10.0, "investment_amount": None},
        ])
        assert result is None
        conn.close()

    def test_returns_dict_with_correct_keys(self):
        """Result has all expected top-level keys."""
        conn = make_connection()
        insert_rows(conn, "IBM", IBM_ROWS)
        result = run_position_based_portfolio(conn, [
            {"ticker": "IBM", "entry_date": "2023-01-02", "exit_date": "2023-03-01",
             "shares": 10.0, "investment_amount": None},
        ])
        expected = {
            "lots", "ticker_summaries", "total_invested", "total_final_value",
            "total_profit_loss", "total_percent_return", "best_performer", "worst_performer",
        }
        assert expected == set(result.keys())
        conn.close()

    def test_single_lot_math(self):
        """Single IBM lot: 10 shares at $100 sold at $120 → +$200 (+20%)."""
        conn = make_connection()
        insert_rows(conn, "IBM", IBM_ROWS)
        result = run_position_based_portfolio(conn, [
            {"ticker": "IBM", "entry_date": "2023-01-02", "exit_date": "2023-03-01",
             "shares": 10.0, "investment_amount": None},
        ])
        lot = result["lots"][0]
        assert lot["shares_purchased"]  == pytest.approx(10.0,   rel=1e-6)
        assert lot["investment_amount"] == pytest.approx(1000.0, rel=1e-6)
        assert lot["final_value"]       == pytest.approx(1200.0, rel=1e-6)
        assert lot["profit_loss"]       == pytest.approx(200.0,  rel=1e-6)
        assert lot["percent_return"]    == pytest.approx(20.0,   rel=1e-4)
        conn.close()


# ------------------------------------------------------------------ #
# Exit date defaulting                                                 #
# ------------------------------------------------------------------ #

class TestExitDateDefaulting:
    def test_exit_date_defaults_to_latest_stored_date(self):
        """When exit_date is None the lot uses the latest available date."""
        conn = make_connection()
        insert_rows(conn, "IBM", IBM_ROWS)
        result = run_position_based_portfolio(conn, [
            {"ticker": "IBM", "entry_date": "2023-01-02", "exit_date": None,
             "shares": 5.0, "investment_amount": None},
        ])
        # Latest stored IBM date is 2023-03-01, close=120
        lot = result["lots"][0]
        assert lot["exit_date"]   == "2023-03-01"
        assert lot["sell_price"]  == pytest.approx(120.0, rel=1e-6)
        conn.close()


# ------------------------------------------------------------------ #
# Multiple lots of the same ticker                                     #
# ------------------------------------------------------------------ #

class TestMultipleLotsPerTicker:
    def setup_method(self):
        self.conn = make_connection()
        insert_rows(self.conn, "IBM", IBM_ROWS)
        # Lot 1: 20 shares bought Jan, sold Mar  → buy=100, sell=120 (+20%)
        # Lot 2: 20 shares bought Feb, sold Mar  → buy=110, sell=120 (+9.09%)
        self.result = run_position_based_portfolio(self.conn, [
            {"ticker": "IBM", "entry_date": "2023-01-02", "exit_date": "2023-03-01",
             "shares": 20.0, "investment_amount": None},
            {"ticker": "IBM", "entry_date": "2023-02-01", "exit_date": "2023-03-01",
             "shares": 20.0, "investment_amount": None},
        ])

    def teardown_method(self):
        self.conn.close()

    def test_two_lots_created(self):
        """Two input positions produce two lots."""
        assert len(self.result["lots"]) == 2

    def test_only_one_ticker_summary(self):
        """Two IBM lots merge into a single IBM ticker summary."""
        assert "IBM" in self.result["ticker_summaries"]
        assert len(self.result["ticker_summaries"]) == 1

    def test_total_shares_combined(self):
        """Ticker summary total_shares = 20 + 20 = 40."""
        summary = self.result["ticker_summaries"]["IBM"]
        assert summary["total_shares"] == pytest.approx(40.0, rel=1e-6)

    def test_cost_basis_combined(self):
        """Total invested = (20 × $100) + (20 × $110) = $4,200."""
        summary = self.result["ticker_summaries"]["IBM"]
        assert summary["total_invested"] == pytest.approx(4200.0, rel=1e-6)

    def test_final_value_combined(self):
        """Total final value = 40 shares × $120 = $4,800."""
        summary = self.result["ticker_summaries"]["IBM"]
        assert summary["total_final_value"] == pytest.approx(4800.0, rel=1e-6)

    def test_blended_return_between_individual_returns(self):
        """Blended return is between the two individual lot returns (9.09% and 20%)."""
        summary = self.result["ticker_summaries"]["IBM"]
        assert 9.0 < summary["blended_return"] < 20.0

    def test_portfolio_total_matches_sum_of_lots(self):
        """Portfolio total_invested equals sum of both lot cost bases."""
        expected = sum(l["investment_amount"] for l in self.result["lots"])
        assert self.result["total_invested"] == pytest.approx(expected, rel=1e-6)


# ------------------------------------------------------------------ #
# Multiple tickers                                                     #
# ------------------------------------------------------------------ #

class TestMultipleTickers:
    def setup_method(self):
        self.conn = make_connection()
        insert_rows(self.conn, "IBM",  IBM_ROWS)
        insert_rows(self.conn, "NVDA", NVDA_ROWS)
        # IBM: 10 shares Jan→Mar  (+20%)
        # NVDA: 5 shares Jan→Mar  (-10%)
        self.result = run_position_based_portfolio(self.conn, [
            {"ticker": "IBM",  "entry_date": "2023-01-02", "exit_date": "2023-03-01",
             "shares": 10.0, "investment_amount": None},
            {"ticker": "NVDA", "entry_date": "2023-01-02", "exit_date": "2023-03-01",
             "shares": 5.0,  "investment_amount": None},
        ])

    def teardown_method(self):
        self.conn.close()

    def test_two_ticker_summaries(self):
        """One summary per ticker."""
        assert set(self.result["ticker_summaries"].keys()) == {"IBM", "NVDA"}

    def test_best_performer_is_ibm(self):
        """IBM (+20%) is the best performer."""
        assert self.result["best_performer"] == "IBM"

    def test_worst_performer_is_nvda(self):
        """NVDA (-10%) is the worst performer."""
        assert self.result["worst_performer"] == "NVDA"

    def test_total_invested_is_sum_of_positions(self):
        """Total invested = (10×100) + (5×200) = $2,000."""
        assert self.result["total_invested"] == pytest.approx(2000.0, rel=1e-6)

    def test_total_final_value_is_sum_of_positions(self):
        """Total final value = (10×120) + (5×180) = $2,100."""
        assert self.result["total_final_value"] == pytest.approx(2100.0, rel=1e-6)

    def test_total_profit_loss(self):
        """Total P&L = $2,100 - $2,000 = +$100."""
        assert self.result["total_profit_loss"] == pytest.approx(100.0, rel=1e-6)

    def test_total_percent_return(self):
        """Total return = $100 / $2,000 = +5%."""
        assert self.result["total_percent_return"] == pytest.approx(5.0, rel=1e-4)


# ------------------------------------------------------------------ #
# Dollar-amount input mode                                             #
# ------------------------------------------------------------------ #

class TestDollarAmountMode:
    def test_dollar_amount_lot_math(self):
        """$1000 in IBM at Jan close=$100 → 10 shares, sold Mar at $120 → $1200."""
        conn = make_connection()
        insert_rows(conn, "IBM", IBM_ROWS)
        result = run_position_based_portfolio(conn, [
            {"ticker": "IBM", "entry_date": "2023-01-02", "exit_date": "2023-03-01",
             "shares": None, "investment_amount": 1000.0},
        ])
        lot = result["lots"][0]
        assert lot["shares_purchased"]  == pytest.approx(10.0,   rel=1e-6)
        assert lot["final_value"]       == pytest.approx(1200.0, rel=1e-6)
        assert lot["percent_return"]    == pytest.approx(20.0,   rel=1e-4)
        conn.close()
