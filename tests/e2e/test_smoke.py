"""
End-to-End Smoke Tests — full pipeline with real yfinance data

These tests make live network calls to the yfinance API and write to a
temporary on-disk database. They verify the full path:
  fetch → flatten MultiIndex → insert → retrieve → analyze → report

Run selectively — these are slower than unit/integration tests.
Mark with: pytest tests/e2e/
"""
import sys
import os
import sqlite3
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from database import create_stock_table, insert_stock_data, get_stock_data, ticker_exists
from analysis import analyze_ticker
from report_generator import generate_report


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def fetch_and_flatten(ticker, period="1y"):
    """Fetch data from yfinance and flatten the MultiIndex if present."""
    import yfinance as yf
    df = yf.download(ticker, period=period, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def make_temp_connection(tmp_path, name="stocks_test.db"):
    path = str(tmp_path / name)
    conn = sqlite3.connect(path)
    create_stock_table(conn)
    return conn


# ------------------------------------------------------------------ #
# Smoke Test 1 — Fresh fetch and store                                 #
# ------------------------------------------------------------------ #

class TestFreshFetchAndStore:
    def test_aapl_fetches_non_empty_data(self):
        """yfinance returns non-empty data for AAPL over 1 year."""
        df = fetch_and_flatten("AAPL", period="1y")
        assert not df.empty

    def test_fetched_data_has_expected_columns(self):
        """Fetched DataFrame has Open, High, Low, Close, Volume after flattening."""
        df = fetch_and_flatten("AAPL", period="1y")
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            assert col in df.columns, f"Missing column: {col}"

    def test_fetched_data_has_sufficient_rows(self, tmp_path):
        """A 1-year fetch returns at least 200 trading days."""
        df = fetch_and_flatten("AAPL", period="1y")
        assert len(df) >= 200

    def test_data_inserts_without_error(self, tmp_path):
        """Fetched data inserts into SQLite without raising an exception."""
        df = fetch_and_flatten("AAPL", period="1y")
        conn = make_temp_connection(tmp_path)
        insert_stock_data(conn, "AAPL", df)  # should not raise
        conn.close()

    def test_row_count_matches_after_insert(self, tmp_path):
        """Row count in the database matches the number of rows fetched."""
        df = fetch_and_flatten("AAPL", period="1y")
        conn = make_temp_connection(tmp_path)
        insert_stock_data(conn, "AAPL", df)
        stored = get_stock_data(conn, "AAPL")
        assert len(stored) == len(df)
        conn.close()


# ------------------------------------------------------------------ #
# Smoke Test 2 — Cached run (ticker already in database)              #
# ------------------------------------------------------------------ #

class TestCachedRun:
    def test_ticker_exists_after_first_insert(self, tmp_path):
        """ticker_exists() returns True after the first fetch and store."""
        df = fetch_and_flatten("AAPL", period="1y")
        conn = make_temp_connection(tmp_path)
        insert_stock_data(conn, "AAPL", df)
        assert ticker_exists(conn, "AAPL") is True
        conn.close()

    def test_reinserting_same_data_does_not_duplicate_rows(self, tmp_path):
        """Inserting the same data twice leaves the row count unchanged."""
        df = fetch_and_flatten("AAPL", period="1y")
        conn = make_temp_connection(tmp_path)
        insert_stock_data(conn, "AAPL", df)
        count_before = len(get_stock_data(conn, "AAPL"))
        insert_stock_data(conn, "AAPL", df)
        count_after = len(get_stock_data(conn, "AAPL"))
        assert count_before == count_after
        conn.close()


# ------------------------------------------------------------------ #
# Smoke Test 3 — Mixed run (one cached, one new ticker)               #
# ------------------------------------------------------------------ #

class TestMixedRun:
    def test_two_tickers_stored_independently(self, tmp_path):
        """AAPL and MSFT can be stored and retrieved independently."""
        conn = make_temp_connection(tmp_path)
        for ticker in ["AAPL", "MSFT"]:
            df = fetch_and_flatten(ticker, period="1y")
            insert_stock_data(conn, ticker, df)
        assert ticker_exists(conn, "AAPL") is True
        assert ticker_exists(conn, "MSFT") is True
        aapl_rows = get_stock_data(conn, "AAPL")
        msft_rows = get_stock_data(conn, "MSFT")
        assert len(aapl_rows) > 0
        assert len(msft_rows) > 0
        conn.close()


# ------------------------------------------------------------------ #
# Smoke Test 4 — Bad ticker handling                                   #
# ------------------------------------------------------------------ #

class TestBadTicker:
    def test_invalid_ticker_returns_empty_dataframe(self):
        """yfinance returns an empty DataFrame for a non-existent ticker."""
        import yfinance as yf
        df = yf.download("ZZZZ_INVALID", period="1y", progress=False)
        assert df.empty

    def test_analyze_returns_none_for_missing_ticker(self, tmp_path):
        """analyze_ticker() returns None if the ticker was never stored."""
        conn = make_temp_connection(tmp_path)
        result = analyze_ticker(conn, "ZZZZ_INVALID")
        assert result is None
        conn.close()


# ------------------------------------------------------------------ #
# Smoke Test 5 — Full pipeline with report generation                  #
# ------------------------------------------------------------------ #

class TestFullPipeline:
    def test_full_pipeline_produces_analysis_results(self, tmp_path):
        """Fetch → insert → analyze returns a complete results dict."""
        df = fetch_and_flatten("AAPL", period="1y")
        conn = make_temp_connection(tmp_path)
        insert_stock_data(conn, "AAPL", df)
        results = analyze_ticker(conn, "AAPL")
        assert results is not None
        assert results["ticker"] == "AAPL"
        assert not results["df"].empty
        conn.close()

    def test_report_generates_without_error(self, tmp_path, capsys):
        """generate_report() runs without raising an exception."""
        df = fetch_and_flatten("AAPL", period="1y")
        conn = make_temp_connection(tmp_path)
        insert_stock_data(conn, "AAPL", df)
        results = analyze_ticker(conn, "AAPL")
        generate_report("AAPL", results)  # should not raise
        conn.close()

    def test_price_extremes_are_within_data_range(self, tmp_path):
        """Highest and lowest close prices fall within the fetched data range."""
        df = fetch_and_flatten("AAPL", period="1y")
        conn = make_temp_connection(tmp_path)
        insert_stock_data(conn, "AAPL", df)
        results = analyze_ticker(conn, "AAPL")
        pe = results["price_extremes"]
        stored = get_stock_data(conn, "AAPL")
        assert pe["highest_close"] == pytest.approx(stored["close"].max(), rel=1e-4)
        assert pe["lowest_close"]  == pytest.approx(stored["close"].min(), rel=1e-4)
        conn.close()
