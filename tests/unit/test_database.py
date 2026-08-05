"""
Unit Tests — database.py

Tests each database function in isolation using an in-memory SQLite
database. No files are written to disk and no network calls are made.
"""
import sys
import os
import sqlite3
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from database import (
    create_database,
    create_stock_table,
    insert_stock_data,
    get_stock_data,
    ticker_exists,
)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def make_connection():
    """Return an in-memory SQLite connection with the stock table created."""
    conn = sqlite3.connect(":memory:")
    create_stock_table(conn)
    return conn


def make_sample_df(ticker="AAPL", rows=60):
    """Build a minimal OHLCV DataFrame that mimics a yfinance download."""
    import datetime
    dates = pd.date_range(end=datetime.date.today(), periods=rows, freq="B")
    return pd.DataFrame(
        {
            "Open":   [150.0 + i * 0.1 for i in range(rows)],
            "High":   [152.0 + i * 0.1 for i in range(rows)],
            "Low":    [148.0 + i * 0.1 for i in range(rows)],
            "Close":  [151.0 + i * 0.1 for i in range(rows)],
            "Volume": [1_000_000 + i * 1000 for i in range(rows)],
        },
        index=dates,
    )


# ------------------------------------------------------------------ #
# create_database                                                      #
# ------------------------------------------------------------------ #

class TestCreateDatabase:
    def test_returns_connection(self, tmp_path):
        """create_database() returns a live sqlite3 connection."""
        db_path = str(tmp_path / "test.db")
        import database as db_module
        _real_connect = sqlite3.connect          # capture the real function first
        original = db_module.sqlite3.connect
        db_module.sqlite3.connect = lambda _: _real_connect(db_path)
        try:
            conn = create_database()
            assert conn is not None
            conn.close()
        finally:
            db_module.sqlite3.connect = original  # always restore, even on failure


# ------------------------------------------------------------------ #
# create_stock_table                                                   #
# ------------------------------------------------------------------ #

class TestCreateStockTable:
    def test_table_exists_after_creation(self):
        """portfolio table is present after create_stock_table()."""
        conn = sqlite3.connect(":memory:")
        create_stock_table(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_idempotent(self):
        """Calling create_stock_table() twice does not raise an error."""
        conn = sqlite3.connect(":memory:")
        create_stock_table(conn)
        create_stock_table(conn)  # should not raise
        conn.close()

    def test_correct_columns(self):
        """portfolio table has the expected columns with correct types."""
        conn = sqlite3.connect(":memory:")
        create_stock_table(conn)
        cursor = conn.execute("PRAGMA table_info(portfolio)")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        assert cols["ticker"] == "TEXT"
        assert cols["date"] == "TEXT"
        assert cols["open"] == "REAL"
        assert cols["high"] == "REAL"
        assert cols["low"] == "REAL"
        assert cols["close"] == "REAL"
        assert cols["volume"] == "INT"
        conn.close()


# ------------------------------------------------------------------ #
# insert_stock_data                                                    #
# ------------------------------------------------------------------ #

class TestInsertStockData:
    def test_inserts_all_rows(self):
        """All rows from the DataFrame are inserted into the database."""
        conn = make_connection()
        df = make_sample_df(rows=60)
        insert_stock_data(conn, "AAPL", df)
        count = conn.execute("SELECT COUNT(*) FROM portfolio WHERE ticker='AAPL'").fetchone()[0]
        assert count == 60
        conn.close()

    def test_no_duplicates_on_reinsertion(self):
        """Re-inserting the same data does not create duplicate rows."""
        conn = make_connection()
        df = make_sample_df(rows=60)
        insert_stock_data(conn, "AAPL", df)
        insert_stock_data(conn, "AAPL", df)  # second insert — all should be ignored
        count = conn.execute("SELECT COUNT(*) FROM portfolio WHERE ticker='AAPL'").fetchone()[0]
        assert count == 60
        conn.close()

    def test_prices_stored_as_floats(self):
        """Close price is stored as a float, not truncated to int."""
        conn = make_connection()
        df = make_sample_df(rows=1)
        insert_stock_data(conn, "AAPL", df)
        row = conn.execute("SELECT close FROM portfolio").fetchone()
        assert isinstance(row[0], float)
        assert row[0] == pytest.approx(151.0, rel=1e-3)
        conn.close()

    def test_date_format_is_yyyy_mm_dd(self):
        """Dates are stored in YYYY-MM-DD string format."""
        conn = make_connection()
        df = make_sample_df(rows=1)
        insert_stock_data(conn, "AAPL", df)
        row = conn.execute("SELECT date FROM portfolio").fetchone()
        date_str = row[0]
        assert len(date_str) == 10
        assert date_str[4] == "-" and date_str[7] == "-"
        conn.close()

    def test_multiple_tickers_stored_independently(self):
        """Two tickers can coexist in the database without interfering."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=30))
        insert_stock_data(conn, "NVDA", make_sample_df(rows=30))
        aapl_count = conn.execute("SELECT COUNT(*) FROM portfolio WHERE ticker='AAPL'").fetchone()[0]
        nvda_count = conn.execute("SELECT COUNT(*) FROM portfolio WHERE ticker='NVDA'").fetchone()[0]
        assert aapl_count == 30
        assert nvda_count == 30
        conn.close()


# ------------------------------------------------------------------ #
# get_stock_data                                                       #
# ------------------------------------------------------------------ #

class TestGetStockData:
    def test_returns_dataframe(self):
        """get_stock_data() returns a pandas DataFrame."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=10))
        result = get_stock_data(conn, "AAPL")
        assert isinstance(result, pd.DataFrame)
        conn.close()

    def test_correct_columns(self):
        """Returned DataFrame has exactly the expected columns."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=10))
        result = get_stock_data(conn, "AAPL")
        assert list(result.columns) == ["date", "open", "high", "low", "close", "volume"]
        conn.close()

    def test_correct_row_count(self):
        """Returned DataFrame has one row per inserted trading day."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=50))
        result = get_stock_data(conn, "AAPL")
        assert len(result) == 50
        conn.close()

    def test_ordered_by_date_ascending(self):
        """Rows are returned in ascending date order."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=20))
        result = get_stock_data(conn, "AAPL")
        dates = result["date"].tolist()
        assert dates == sorted(dates)
        conn.close()

    def test_returns_empty_dataframe_for_unknown_ticker(self):
        """Querying a ticker with no data returns an empty DataFrame."""
        conn = make_connection()
        result = get_stock_data(conn, "ZZZZ")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        conn.close()

    def test_only_returns_requested_ticker(self):
        """get_stock_data() filters to only the requested ticker."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=20))
        insert_stock_data(conn, "NVDA", make_sample_df(rows=20))
        result = get_stock_data(conn, "AAPL")
        assert len(result) == 20          # NVDA's rows must not bleed in
        assert result["close"].notna().all()
        conn.close()


# ------------------------------------------------------------------ #
# ticker_exists                                                        #
# ------------------------------------------------------------------ #

class TestTickerExists:
    def test_returns_true_when_ticker_present(self):
        """ticker_exists() returns True after data has been inserted."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=5))
        assert ticker_exists(conn, "AAPL") is True
        conn.close()

    def test_returns_false_when_ticker_absent(self):
        """ticker_exists() returns False for a ticker with no rows."""
        conn = make_connection()
        assert ticker_exists(conn, "ZZZZ") is False
        conn.close()

    def test_case_sensitive(self):
        """ticker_exists() treats 'aapl' and 'AAPL' as different tickers."""
        conn = make_connection()
        insert_stock_data(conn, "AAPL", make_sample_df(rows=5))
        assert ticker_exists(conn, "aapl") is False
        conn.close()
