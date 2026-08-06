"""
File: data_fetcher.py

Purpose: Downloads OHLCV data for a list of tickers via yfinance and plots
closing prices. Provides helpers for standard (1-year) fetches and longer
refreshes (5-year, 10-year) used by the backtester.
"""
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt


def fetch_stock_data(ticker_list, period="1y"):
    """Fetch OHLCV data for each ticker and display a closing-price chart.

    Parameters
    ----------
    ticker_list : list of str — ticker symbols to fetch
    period      : str        — yfinance period string, e.g. '1y', '5y', '10y', 'max'

    Returns
    -------
    dict of {ticker: DataFrame}
        Each DataFrame has Date as the index and columns Open, High, Low,
        Close, Volume (column names preserved from yfinance).

    Raises
    ------
    ValueError
        If yfinance returns no data for a ticker (invalid symbol or no history
        available for the requested period).
    """
    result = {}
    plt.figure()
    for ticker in ticker_list:
        portfolio = yf.download(ticker, period=period, progress=False)
        if portfolio.empty:
            raise ValueError(
                f"No data returned for '{ticker}'. "
                "Check that the symbol is valid and that the requested period has data."
            )
        # yfinance v1.4+ returns a MultiIndex column (field, ticker). Flatten
        # to a simple index so the rest of the codebase can use plain names
        # like "Close" without caring about the yfinance version.
        if isinstance(portfolio.columns, pd.MultiIndex):
            portfolio.columns = portfolio.columns.get_level_values(0)
        plt.plot(portfolio["Close"], label=ticker)
        result[ticker] = portfolio
    plt.legend()
    plt.title(f"Closing Price — {period}")
    plt.show()
    return result


def refresh_stock_data(ticker_list):
    """Re-fetch the most recent 5 years of data for each ticker.

    Used to pull in new trading days since the last fetch. Only rows with a
    new (ticker, date) pair are inserted — INSERT OR IGNORE prevents duplicates.

    Returns
    -------
    dict of {ticker: DataFrame} — identical shape to fetch_stock_data().
    """
    return fetch_stock_data(ticker_list, period="5y")


def refresh_stock_data_backtest(ticker_list):
    """Re-fetch the most recent 10 years of data for each ticker.

    Used when refreshing from the backtester, which needs sufficient history
    for indicators like SMA 200 (requires ~200 trading days minimum).
    INSERT OR IGNORE prevents duplicates.

    Returns
    -------
    dict of {ticker: DataFrame} — identical shape to fetch_stock_data().
    """
    return fetch_stock_data(ticker_list, period="10y")


