"""
File: data_fetcher.py

Purpose: User is prompted to input tickers in order
to place them into their portfolio.
"""
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt


def fetch_stock_data(ticker_list, period="1y"):
    """Fetch OHLCV data for each ticker and plot closing prices.

    Parameters
    ----------
    ticker_list : list of str — ticker symbols to fetch
    period      : str        — yfinance period string, e.g. '1y', '2y', 'max'

    Returns a dict of {ticker: DataFrame}.
    """
    result = {}
    plt.figure()
    for ticker in ticker_list:
        portfolio = yf.download(ticker, period=period)
        if portfolio.empty:
            print(f"'{ticker}' does not exist.\n")
            exit()
        else:
            # yfinance returns a MultiIndex column (field, ticker) in newer
            # versions. Flatten to a simple column index so the rest of the
            # codebase can access columns by plain name (e.g. "Close").
            if isinstance(portfolio.columns, pd.MultiIndex):
                portfolio.columns = portfolio.columns.get_level_values(0)
            close_port = portfolio['Close']
            plt.plot(close_port, label=f"{ticker}")
            result[ticker] = portfolio
    plt.legend()
    plt.title("Closing Price Past Year")
    plt.show()
    return result


def refresh_stock_data(ticker_list):
    """Re-fetch the most recent 5 years of data for each ticker.

    Used to pull in new trading days since the last fetch. Only rows with a
    new (ticker, date) pair are inserted — INSERT OR IGNORE prevents duplicates.
    Returns a dict of {ticker: DataFrame} — identical shape to fetch_stock_data().
    """
    return fetch_stock_data(ticker_list, period="5y")


def refresh_stock_data_backtest(ticker_list):
    """Re-fetch the most recent 10 years of data for each ticker.

    Used when refreshing from the backtester, which needs sufficient history
    for indicators like SMA 200 (requires ~200 trading days minimum).
    INSERT OR IGNORE prevents duplicates.
    Returns a dict of {ticker: DataFrame} — identical shape to fetch_stock_data().
    """
    return fetch_stock_data(ticker_list, period="10y")


