"""
File: database.py

Purpose: Manages the SQLite database for aiFinance. Provides functions to
create the schema, insert OHLCV rows, query all rows for a ticker, query a
date-bounded slice, and check whether a ticker is already stored.
"""
import sqlite3
import pandas as pd


def create_database():
    """Create and return a connection to stocks.db."""
    connection = sqlite3.connect("stocks.db")
    return connection


def create_stock_table(connection):
    """Create the portfolio table if it does not already exist."""
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INT NOT NULL,
            UNIQUE(ticker, date)
            )
        """)
    connection.commit()


def insert_stock_data(connection, ticker, df):
    """Insert OHLCV rows for a ticker into the portfolio table.

    Accepts a connection, a ticker string, and a pandas DataFrame
    with Date as the index and columns Open, High, Low, Close, Volume.
    Uses INSERT OR IGNORE to skip duplicate (ticker, date) pairs.
    """
    cursor = connection.cursor()
    for date, row in df.iterrows():
        cursor.execute(
            """
            INSERT OR IGNORE INTO portfolio
                (ticker, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                str(date)[:10],
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
                int(row["Volume"]),
            ),
        )
    connection.commit()


def get_stock_data(connection, ticker):
    """Retrieve all rows for a ticker ordered by date.

    Returns a pandas DataFrame with columns:
    date, open, high, low, close, volume.
    """
    query = """
        SELECT date, open, high, low, close, volume
        FROM portfolio
        WHERE ticker = ?
        ORDER BY date ASC
    """
    return pd.read_sql_query(query, connection, params=(ticker,))


def get_stock_data_range(connection, ticker, start_date, end_date):
    """Retrieve rows for a ticker within an inclusive date range.

    Returns a pandas DataFrame with columns:
    date, open, high, low, close, volume ordered by date ASC.
    Returns an empty DataFrame if no rows match.
    """
    query = """
        SELECT date, open, high, low, close, volume
        FROM portfolio
        WHERE ticker = ?
          AND date >= ?
          AND date <= ?
        ORDER BY date ASC
    """
    return pd.read_sql_query(query, connection, params=(ticker, start_date, end_date))


def ticker_exists(connection, ticker):
    """Return True if any rows exist for ticker in the database."""
    cursor = connection.cursor()
    cursor.execute(
        "SELECT 1 FROM portfolio WHERE ticker = ? LIMIT 1",
        (ticker,),
    )
    return cursor.fetchone() is not None


