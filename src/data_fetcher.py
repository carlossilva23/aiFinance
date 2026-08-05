"""
File: data_fetcher.py

Purpose: User is prompted to input tickers in order
to place them into their portfolio.
"""
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt


def fetch_stock_data(ticker_list):
    result = {}
    plt.figure()
    for ticker in ticker_list:
        portfolio = yf.download(ticker, period='1y')
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


