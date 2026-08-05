"""
Integration Tests — fetch → store → analyze pipeline

Tests that the database layer and analysis layer work correctly together
using synthetic data. No network calls are made — yfinance is not invoked.
"""
import sys
import os
import sqlite3
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from database import create_stock_table, insert_stock_data, get_stock_data, ticker_exists
from analysis import analyze_ticker


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def make_connection():
    conn = sqlite3.connect(":memory:")
    create_stock_table(conn)
    return conn


def make_sample_df(rows=60, start_price=100.0, step=0.5):
    """Synthetic OHLCV DataFrame with enough rows for all indicators."""
    import datetime
    dates = pd.date_range(end=datetime.date.today(), periods=rows, freq="B")
    close = [start_price + i * step for i in range(rows)]
    return pd.DataFrame(
        {
            "Open":   [c - 0.5 for c in close],
            "High":   [c + 1.0 for c in close],
            "Low":    [c - 1.0 for c in close],
            "Close":  close,
            "Volume": [1_000_000] * rows,
        },
        index=dates,
    )


# ------------------------------------------------------------------ #
# Store → Retrieve                                                     #
# ------------------------------------------------------------------ #

class TestStoreAndRetrieve:
    def test_inserted_data_is_retrievable(self):
        """Data inserted via insert_stock_data() can be retrieved via get_stock_data()."""
        conn = make_connection()
        df = make_sample_df(rows=30)
        insert_stock_data(conn, "AAPL", df)
        result = get_stock_data(conn, "AAPL")
        assert len(result) == 30
        conn.close()

    def test_close_prices_round_trip_correctly(self):
        """Close prices survive the insert → retrieve cycle without distortion."""
        conn = make_connection()
        df = make_sample_df(rows=10)
        insert_stock_data(conn, "AAPL", df)
        result = get_stock_data(conn, "AAPL")
        original_closes = [round(c, 4) for c in df["Close"].tolist()]
        stored_closes   = [round(c, 4) for c in result["close"].tolist()]
        assert original_closes == stored_closes
        conn.close()

    def test_ticker_exists_after_insert(self):
        """ticker_exists() returns True immediately after insertion."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=5))
        assert ticker_exists(conn, "AAPL") is True
        conn.close()

    def test_ticker_not_exists_before_insert(self):
        """ticker_exists() returns False when no data has been inserted."""
        conn = make_connection()
        assert ticker_exists(conn, "AAPL") is False
        conn.close()


# ------------------------------------------------------------------ #
# Store → Analyze                                                      #
# ------------------------------------------------------------------ #

class TestStoreAndAnalyze:
    def test_analyze_ticker_returns_dict(self):
        """analyze_ticker() returns a dict after data is stored."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=60))
        result = analyze_ticker(conn, "AAPL")
        assert isinstance(result, dict)
        conn.close()

    def test_analyze_ticker_returns_none_for_missing_ticker(self):
        """analyze_ticker() returns None when no data exists for the ticker."""
        conn = make_connection()
        result = analyze_ticker(conn, "ZZZZ")
        assert result is None
        conn.close()

    def test_analyze_ticker_has_all_expected_keys(self):
        """Results dict contains all expected top-level keys."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=60))
        result = analyze_ticker(conn, "AAPL")
        expected_keys = {
            "ticker", "df", "daily_returns", "moving_averages",
            "ema", "volatility", "rsi", "macd", "bollinger_bands", "price_extremes",
        }
        assert expected_keys.issubset(set(result.keys()))
        conn.close()

    def test_ticker_key_matches_input(self):
        """results['ticker'] equals the ticker string passed in."""
        conn = make_connection()
        insert_stock_data(conn, "NVDA", make_sample_df(rows=60))
        result = analyze_ticker(conn, "NVDA")
        assert result["ticker"] == "NVDA"
        conn.close()

    def test_rsi_values_in_valid_range(self):
        """RSI values are between 0 and 100 after a store + analyze cycle."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=60))
        result = analyze_ticker(conn, "AAPL")
        rsi = result["rsi"].dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()
        conn.close()

    def test_bollinger_bands_upper_above_lower(self):
        """Upper Bollinger Band is always above the lower band."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=60))
        result = analyze_ticker(conn, "AAPL")
        bb = result["bollinger_bands"].dropna()
        assert (bb["bb_upper"] >= bb["bb_lower"]).all()
        conn.close()

    def test_macd_columns_present(self):
        """MACD result contains ema_12, ema_26, macd, and signal columns."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=60))
        result = analyze_ticker(conn, "AAPL")
        assert list(result["macd"].columns) == ["ema_12", "ema_26", "macd", "signal"]
        conn.close()


# ------------------------------------------------------------------ #
# Duplicate insert protection                                          #
# ------------------------------------------------------------------ #

class TestDuplicateProtection:
    def test_second_insert_does_not_double_row_count(self):
        """Inserting the same DataFrame twice keeps the row count unchanged."""
        conn = make_connection()
        df = make_sample_df(rows=40)
        insert_stock_data(conn, "AAPL", df)
        insert_stock_data(conn, "AAPL", df)
        result = get_stock_data(conn, "AAPL")
        assert len(result) == 40
        conn.close()

    def test_analysis_unaffected_by_duplicate_insert(self):
        """Analysis results are identical whether data was inserted once or twice."""
        conn = make_connection()
        df = make_sample_df(rows=60)
        insert_stock_data(conn, "AAPL", df)
        result_once = analyze_ticker(conn, "AAPL")

        insert_stock_data(conn, "AAPL", df)  # duplicate — should be ignored
        result_twice = analyze_ticker(conn, "AAPL")

        assert result_once["price_extremes"] == result_twice["price_extremes"]
        conn.close()
