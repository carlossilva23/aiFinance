"""
File: data_fetcher.py

Purpose: User is prompted to input tickers in order
to place them into their portfolio.
"""
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
            close_port = portfolio['Close']
            plt.plot(close_port, label=f"{ticker}")
            result[ticker] = portfolio
    plt.legend()
    plt.title("Closing Price Past Year")
    plt.show()
    return result


