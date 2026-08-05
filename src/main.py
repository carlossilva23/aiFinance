"""
File: main.py

Purpose: Main program direction.
"""
from data_fetcher import fetch_stock_data
from database import create_database, create_stock_table, insert_stock_data, ticker_exists
from analysis import analyze_ticker
from report_generator import generate_report, print_ai_summary
from ai_summary import build_prompt, get_summary


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

    tickers_to_fetch = []
    for ticker in ticker_list:
        if ticker_exists(connection, ticker):
            print(f"{ticker}: already in database, skipping fetch.")
        else:
            tickers_to_fetch.append(ticker)

    if tickers_to_fetch:
        stock_data = fetch_stock_data(tickers_to_fetch)
        for ticker, df in stock_data.items():
            insert_stock_data(connection, ticker, df)
            print(f"{ticker}: {len(df)} rows saved to database.")

    all_results = []
    for ticker in ticker_list:
        results = analyze_ticker(connection, ticker)
        if results is not None:
            generate_report(ticker, results)
            all_results.append(results)
        else:
            print(f"Warning: no data found for {ticker}.")

    if all_results:
        print("\nGenerating AI summary (this may take a moment)...")
        prompt = build_prompt(all_results)
        summary = get_summary(prompt)
        tickers = [r["ticker"] for r in all_results]
        print_ai_summary(summary, tickers)

    connection.close()


if __name__ == "__main__":
    main()
