"""
File: main.py

Purpose: Main program direction.
"""
from data_fetcher import fetch_stock_data
from database import create_database, create_stock_table, insert_stock_data
from analysis import analyze_ticker
from report_generator import generate_report


def main():
    connection = create_database()
    create_stock_table(connection)

    ticker_list = []
    while True:
        ticker = input("Please type in a stock: ")
        if ticker == "":
            break
        else:
            ticker_list.append(ticker.upper())

    stock_data = fetch_stock_data(ticker_list)

    for ticker, df in stock_data.items():
        insert_stock_data(connection, ticker, df)
        print(f"{ticker}: {len(df)} rows saved to database.")

    for ticker in ticker_list:
        results = analyze_ticker(connection, ticker)
        if results is not None:
            generate_report(ticker, results)
        else:
            print(f"Warning: no data found for {ticker}.")

    connection.close()


if __name__ == "__main__":
    main()
