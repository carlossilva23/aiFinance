"""
Unit Tests — portfolio simulation (run_portfolio_simulation)

Tests the portfolio math using an in-memory SQLite database.
No network calls or Ollama invocations are made.
"""
import sys
import os
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from database import create_stock_table
from simulator import run_portfolio_simulation


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def make_connection():
    conn = sqlite3.connect(":memory:")
    create_stock_table(conn)
    return conn


def insert_rows(conn, ticker, rows):
    """Insert (date, open, high, low, close, volume) tuples directly."""
    cursor = conn.cursor()
    for date, open_, high, low, close, volume in rows:
        cursor.execute(
            "INSERT OR IGNORE INTO portfolio "
            "(ticker, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
            (ticker, date, open_, high, low, close, volume),
        )
    conn.commit()


# Two tickers with simple, predictable prices
AAPL_ROWS = [
    ("2023-01-02", 100.0, 105.0, 99.0,  100.0, 1_000_000),
    ("2023-01-03", 100.0, 110.0, 99.0,  110.0, 1_100_000),  # +10%
]
NVDA_ROWS = [
    ("2023-01-02", 200.0, 210.0, 195.0, 200.0, 500_000),
    ("2023-01-03", 200.0, 220.0, 195.0, 180.0, 600_000),  # -10%
]

START = "2023-01-02"
END   = "2023-01-03"


# ------------------------------------------------------------------ #
# Input validation                                                     #
# ------------------------------------------------------------------ #

class TestPortfolioInputValidation:
    def test_raises_if_tickers_and_weights_length_mismatch(self):
        """ValueError when tickers and weights lists have different lengths."""
        conn = make_connection()
        with pytest.raises(ValueError, match="same length"):
            run_portfolio_simulation(conn, ["AAPL", "NVDA"], [0.5], 1000.0, START, END)
        conn.close()

    def test_raises_if_weights_do_not_sum_to_one(self):
        """ValueError when weights do not sum to 1.0."""
        conn = make_connection()
        insert_rows(conn, "AAPL", AAPL_ROWS)
        insert_rows(conn, "NVDA", NVDA_ROWS)
        with pytest.raises(ValueError, match="sum to 1.0"):
            run_portfolio_simulation(conn, ["AAPL", "NVDA"], [0.4, 0.4], 1000.0, START, END)
        conn.close()

    def test_returns_none_when_no_positions_have_data(self):
        """Returns None when no ticker has data in the requested date range."""
        conn = make_connection()
        insert_rows(conn, "AAPL", AAPL_ROWS)
        insert_rows(conn, "NVDA", NVDA_ROWS)
        result = run_portfolio_simulation(
            conn, ["AAPL", "NVDA"], [0.5, 0.5], 1000.0,
            "2099-01-01", "2099-12-31"
        )
        assert result is None
        conn.close()


# ------------------------------------------------------------------ #
# Equal weights                                                        #
# ------------------------------------------------------------------ #

class TestEqualWeights:
    def setup_method(self):
        self.conn = make_connection()
        insert_rows(self.conn, "AAPL", AAPL_ROWS)
        insert_rows(self.conn, "NVDA", NVDA_ROWS)
        self.result = run_portfolio_simulation(
            self.conn, ["AAPL", "NVDA"], [0.5, 0.5], 10_000.0, START, END
        )

    def teardown_method(self):
        self.conn.close()

    def test_returns_dict(self):
        """Result is a non-None dict."""
        assert isinstance(self.result, dict)

    def test_correct_top_level_keys(self):
        """Result has all expected top-level keys."""
        expected = {
            "tickers", "weights", "total_investment", "start_date", "end_date",
            "positions", "total_final_value", "total_profit_loss",
            "total_percent_return", "best_performer", "worst_performer",
        }
        assert expected == set(self.result.keys())

    def test_position_count_matches_tickers(self):
        """One position dict per ticker."""
        assert len(self.result["positions"]) == 2

    def test_each_position_allocated_half(self):
        """Each position receives half the total investment."""
        for pos in self.result["positions"]:
            assert pos["investment_amount"] == pytest.approx(5_000.0, rel=1e-6)

    def test_aapl_position_gained(self):
        """AAPL position shows a positive return (+10%)."""
        aapl = next(p for p in self.result["positions"] if p["ticker"] == "AAPL")
        assert aapl["percent_return"] == pytest.approx(10.0, rel=1e-4)

    def test_nvda_position_lost(self):
        """NVDA position shows a negative return (-10%)."""
        nvda = next(p for p in self.result["positions"] if p["ticker"] == "NVDA")
        assert nvda["percent_return"] == pytest.approx(-10.0, rel=1e-4)

    def test_best_performer_is_aapl(self):
        """AAPL (+10%) is ranked as the best performer."""
        assert self.result["best_performer"] == "AAPL"

    def test_worst_performer_is_nvda(self):
        """NVDA (-10%) is ranked as the worst performer."""
        assert self.result["worst_performer"] == "NVDA"

    def test_total_profit_loss_is_zero_net(self):
        """Equal +10% and -10% positions cancel out: net P&L ≈ 0."""
        assert self.result["total_profit_loss"] == pytest.approx(0.0, abs=1e-4)

    def test_total_final_value_equals_total_investment(self):
        """Net-zero portfolio: final value ≈ original investment."""
        assert self.result["total_final_value"] == pytest.approx(10_000.0, rel=1e-4)

    def test_total_percent_return_is_zero(self):
        """Net return is 0% when gains and losses exactly cancel."""
        assert self.result["total_percent_return"] == pytest.approx(0.0, abs=1e-4)


# ------------------------------------------------------------------ #
# Custom weights                                                       #
# ------------------------------------------------------------------ #

class TestCustomWeights:
    def setup_method(self):
        self.conn = make_connection()
        insert_rows(self.conn, "AAPL", AAPL_ROWS)
        insert_rows(self.conn, "NVDA", NVDA_ROWS)

    def teardown_method(self):
        self.conn.close()

    def test_custom_weight_allocations_are_correct(self):
        """70/30 split allocates the right dollar amounts per position."""
        result = run_portfolio_simulation(
            self.conn, ["AAPL", "NVDA"], [0.7, 0.3], 10_000.0, START, END
        )
        aapl = next(p for p in result["positions"] if p["ticker"] == "AAPL")
        nvda = next(p for p in result["positions"] if p["ticker"] == "NVDA")
        assert aapl["investment_amount"] == pytest.approx(7_000.0, rel=1e-6)
        assert nvda["investment_amount"] == pytest.approx(3_000.0, rel=1e-6)

    def test_heavy_weight_on_winner_produces_positive_return(self):
        """90% in AAPL (+10%) and 10% in NVDA (-10%) produces net positive return."""
        result = run_portfolio_simulation(
            self.conn, ["AAPL", "NVDA"], [0.9, 0.1], 10_000.0, START, END
        )
        assert result["total_percent_return"] > 0

    def test_heavy_weight_on_loser_produces_negative_return(self):
        """10% in AAPL (+10%) and 90% in NVDA (-10%) produces net negative return."""
        result = run_portfolio_simulation(
            self.conn, ["AAPL", "NVDA"], [0.1, 0.9], 10_000.0, START, END
        )
        assert result["total_percent_return"] < 0

    def test_total_invested_matches_sum_of_positions(self):
        """Sum of per-position investment amounts equals total_investment."""
        result = run_portfolio_simulation(
            self.conn, ["AAPL", "NVDA"], [0.6, 0.4], 10_000.0, START, END
        )
        total_from_positions = sum(p["investment_amount"] for p in result["positions"])
        assert total_from_positions == pytest.approx(result["total_investment"], rel=1e-6)
