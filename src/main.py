"""
File: main.py

Purpose: Main program direction.
"""
from data_fetcher import fetch_stock_data, refresh_stock_data, refresh_stock_data_backtest
from database import create_database, create_stock_table, insert_stock_data, ticker_exists, get_stock_data, get_stock_data_range
from analysis import analyze_ticker
from report_generator import (generate_report, print_ai_summary, print_simulation_report,
                               print_portfolio_report, print_position_portfolio_report,
                               print_backtest_report, print_multi_backtest_report)
from ai_summary import build_prompt, get_summary
from simulator import (run_simulation, get_simulation_summary,
                       run_portfolio_simulation, get_portfolio_summary,
                       run_position_based_portfolio, get_position_portfolio_summary)
from backtester import (run_backtest, get_backtest_summary,
                        run_multi_ticker_backtest, get_multi_backtest_summary)


# ------------------------------------------------------------------ #
# Shared helpers                                                       #
# ------------------------------------------------------------------ #

def _fetch_and_store(connection, ticker_list):
    """Fetch or refresh data for each ticker and persist to the database."""
    tickers_to_fetch = []
    tickers_to_refresh = []

    for ticker in ticker_list:
        if ticker_exists(connection, ticker):
            refresh = input(f"{ticker}: already in database. Refresh to latest data? (y/n): ").strip().lower()
            if refresh == "y":
                tickers_to_refresh.append(ticker)
            else:
                print(f"{ticker}: using stored data.")
        else:
            tickers_to_fetch.append(ticker)

    if tickers_to_fetch:
        try:
            stock_data = fetch_stock_data(tickers_to_fetch)
        except ValueError as exc:
            print(f"Error fetching data: {exc}")
            return
        for ticker, df in stock_data.items():
            insert_stock_data(connection, ticker, df)
            print(f"{ticker}: {len(df)} rows saved to database.")

    if tickers_to_refresh:
        print("\nRefreshing data (fetching 5 years of history)...")
        try:
            refreshed = refresh_stock_data(tickers_to_refresh)
        except ValueError as exc:
            print(f"Error refreshing data: {exc}")
            return
        for ticker, df in refreshed.items():
            insert_stock_data(connection, ticker, df)
            stored = get_stock_data(connection, ticker)
            print(f"{ticker}: refreshed — {len(stored)} total rows now in database.")


def _fetch_and_store_backtest(connection, ticker_list):
    """Fetch or refresh data for backtesting — uses 10-year history on refresh."""
    tickers_to_fetch = []
    tickers_to_refresh = []

    for ticker in ticker_list:
        if ticker_exists(connection, ticker):
            refresh = input(f"{ticker}: already in database. Refresh with 10 years of history? (y/n): ").strip().lower()
            if refresh == "y":
                tickers_to_refresh.append(ticker)
            else:
                print(f"{ticker}: using stored data.")
        else:
            tickers_to_fetch.append(ticker)

    if tickers_to_fetch:
        try:
            stock_data = fetch_stock_data(tickers_to_fetch, period="10y")
        except ValueError as exc:
            print(f"Error fetching data: {exc}")
            return
        for ticker, df in stock_data.items():
            insert_stock_data(connection, ticker, df)
            print(f"{ticker}: {len(df)} rows saved to database.")

    if tickers_to_refresh:
        print("\nRefreshing data (fetching 10 years of history)...")
        try:
            refreshed = refresh_stock_data_backtest(tickers_to_refresh)
        except ValueError as exc:
            print(f"Error refreshing data: {exc}")
            return
        for ticker, df in refreshed.items():
            insert_stock_data(connection, ticker, df)
            stored = get_stock_data(connection, ticker)
            print(f"{ticker}: refreshed — {len(stored)} total rows now in database.")


def _collect_tickers():
    """Prompt the user to enter tickers until an empty line is entered."""
    ticker_list = []
    while True:
        ticker = input("Please type in a stock (press Enter to finish): ").strip()
        if ticker == "":
            break
        ticker_list.append(ticker.upper())
    return ticker_list


# ------------------------------------------------------------------ #
# Mode: Analysis + AI summary                                          #
# ------------------------------------------------------------------ #

def _run_analysis(connection):
    """Collect tickers, fetch/store data, run analysis, print reports."""
    ticker_list = _collect_tickers()
    if not ticker_list:
        print("No tickers entered.")
        return

    _fetch_and_store(connection, ticker_list)

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


# ------------------------------------------------------------------ #
# Mode: Investment simulator                                           #
# ------------------------------------------------------------------ #

def _run_simulator(connection):
    """Collect a ticker, fetch/store if needed, run the investment simulator."""
    ticker_list = _collect_tickers()
    if not ticker_list:
        print("No tickers entered.")
        return

    _fetch_and_store(connection, ticker_list)

    # Allow simulating one ticker per run (user can re-run for more)
    sim_ticker = ticker_list[0] if len(ticker_list) == 1 else \
        input("Enter ticker to simulate: ").strip().upper()

    if not ticker_exists(connection, sim_ticker):
        print(f"{sim_ticker} is not in the database. Please fetch it first.")
        return

    mode = input("Simulate by (1) Dollar amount  or  (2) Number of shares? [1/2]: ").strip()

    date_df = get_stock_data(connection, sim_ticker)
    print(f"Available dates: {date_df['date'].iloc[0]} to {date_df['date'].iloc[-1]}")

    start_date = input("Enter start date (YYYY-MM-DD): ").strip()
    end_date   = input("Enter end date (YYYY-MM-DD): ").strip()

    if mode == "2":
        shares_input = float(input("Enter number of shares purchased: "))
        result = run_simulation(connection, sim_ticker, start_date, end_date,
                                shares=shares_input)
    else:
        amount = float(input("Enter investment amount (e.g. 1000): $"))
        result = run_simulation(connection, sim_ticker, start_date, end_date,
                                investment_amount=amount)

    if result is None:
        print("No data found for that date range.")
    else:
        print("\nGenerating AI explanation (this may take a moment)...")
        sim_summary = get_simulation_summary(result)
        print_simulation_report(result, sim_summary)


# ------------------------------------------------------------------ #
# Mode: Portfolio simulator                                            #
# ------------------------------------------------------------------ #

def _run_portfolio_simulator(connection):
    """Collect multiple tickers, assign weights, run portfolio simulation."""
    ticker_list = _collect_tickers()
    if len(ticker_list) < 2:
        print("Please enter at least 2 tickers for a portfolio simulation.")
        return

    _fetch_and_store(connection, ticker_list)

    # Weights
    weight_choice = input(
        "\nWeighting — (1) Equal weights  or  (2) Custom weights? [1/2]: "
    ).strip()

    if weight_choice == "2":
        weights = []
        print("Enter each ticker's weight as a decimal (e.g. 0.5 for 50%).")
        for ticker in ticker_list:
            w = float(input(f"  Weight for {ticker}: "))
            weights.append(w)
        total_w = sum(weights)
        if abs(total_w - 1.0) > 1e-6:
            print(f"Weights sum to {total_w:.4f}, not 1.0 — normalising automatically.")
            weights = [w / total_w for w in weights]
    else:
        equal = 1.0 / len(ticker_list)
        weights = [equal] * len(ticker_list)
        print("Using equal weights: " +
              ", ".join(f"{t} {equal*100:.1f}%" for t in ticker_list))

    total_investment = float(input("\nEnter total investment amount (e.g. 10000): $"))

    # Date range — use the narrowest overlap across all tickers
    earliest_start = ""
    latest_end = ""
    for ticker in ticker_list:
        df = get_stock_data(connection, ticker)
        t_start = df["date"].iloc[0]
        t_end   = df["date"].iloc[-1]
        if not earliest_start or t_start > earliest_start:
            earliest_start = t_start
        if not latest_end or t_end < latest_end:
            latest_end = t_end

    print(f"\nShared date range across all tickers: {earliest_start} to {latest_end}")
    start_date = input("Enter start date (YYYY-MM-DD): ").strip()
    end_date   = input("Enter end date (YYYY-MM-DD): ").strip()

    result = run_portfolio_simulation(
        connection, ticker_list, weights, total_investment, start_date, end_date
    )

    if result is None:
        print("No data found for that date range across any ticker.")
    else:
        print("\nGenerating AI portfolio summary (this may take a moment)...")
        summary = get_portfolio_summary(result)
        print_portfolio_report(result, summary)


# ------------------------------------------------------------------ #
# Mode: Position-based portfolio                                       #
# ------------------------------------------------------------------ #

def _run_position_portfolio(connection):
    """Build a portfolio lot-by-lot, each with its own ticker, dates and size."""
    print("\nEnter each position one at a time. Press Enter with no ticker to finish.")
    positions_input = []
    tickers_needed  = []

    while True:
        ticker = input("\nTicker (or Enter to finish): ").strip().upper()
        if ticker == "":
            break

        if ticker not in tickers_needed:
            tickers_needed.append(ticker)

        mode = input("  Enter by (1) Shares  or  (2) Dollar amount? [1/2]: ").strip()
        if mode == "2":
            amount = float(input("  Investment amount: $"))
            size   = {"investment_amount": amount, "shares": None}
        else:
            shares = float(input("  Number of shares: "))
            size   = {"shares": shares, "investment_amount": None}

        entry_date = input("  Entry date (YYYY-MM-DD): ").strip()

        # Offer to override the exit date
        override = input("  Use latest stored date as exit? (y/n): ").strip().lower()
        if override == "n":
            exit_date = input("  Exit date (YYYY-MM-DD): ").strip()
        else:
            exit_date = None

        positions_input.append({
            "ticker":           ticker,
            "entry_date":       entry_date,
            "exit_date":        exit_date,
            **size,
        })

    if not positions_input:
        print("No positions entered.")
        return

    # Fetch/store any tickers not yet in the database
    _fetch_and_store(connection, tickers_needed)

    result = run_position_based_portfolio(connection, positions_input)
    if result is None:
        print("No data found for any of the positions entered.")
    else:
        print("\nGenerating AI portfolio summary (this may take a moment)...")
        summary = get_position_portfolio_summary(result)
        print_position_portfolio_report(result, summary)


# ------------------------------------------------------------------ #
# Mode: Strategy backtester                                            #
# ------------------------------------------------------------------ #

def _run_backtester(connection):
    """Backtest mode: single ticker (all 3 strategies) or multi-ticker (one strategy)."""
    print("\nBacktest mode:")
    print("  1. Single ticker — compare all 3 strategies")
    print("  2. Multiple tickers — one strategy across all tickers")
    mode = input("\nEnter mode [1/2]: ").strip()

    if mode == "2":
        _run_multi_ticker_backtest(connection)
    else:
        _run_single_ticker_backtest(connection)


def _run_single_ticker_backtest(connection):
    """Run all three strategies on one ticker over a chosen date range."""
    print("\nEnter the ticker to backtest (only the first will be used):")
    ticker_list = _collect_tickers()
    if not ticker_list:
        print("No ticker entered.")
        return

    ticker = ticker_list[0]
    _fetch_and_store_backtest(connection, [ticker])

    date_df = get_stock_data(connection, ticker)
    if date_df.empty:
        print(f"No data found for {ticker}.")
        return
    print(f"Available dates: {date_df['date'].iloc[0]} to {date_df['date'].iloc[-1]}")

    start_date   = input("Enter start date (YYYY-MM-DD): ").strip()
    end_date     = input("Enter end date (YYYY-MM-DD): ").strip()
    cash_input   = input("Enter initial cash amount (default 10000): $").strip()
    initial_cash = float(cash_input) if cash_input else 10000.0

    result = run_backtest(connection, ticker, start_date, end_date, initial_cash)
    if result is None:
        print("No data found for that date range.")
        return

    print("\nGenerating AI backtest summary (this may take a moment)...")
    summary = get_backtest_summary(result)
    print_backtest_report(result, summary)


def _run_multi_ticker_backtest(connection):
    """Run one chosen strategy across multiple tickers over the same date range."""
    ticker_list = _collect_tickers()
    if len(ticker_list) < 2:
        print("Please enter at least 2 tickers.")
        return

    _fetch_and_store_backtest(connection, ticker_list)

    # Show the narrowest shared date range
    earliest_start, latest_end = "", ""
    for ticker in ticker_list:
        df = get_stock_data(connection, ticker)
        if df.empty:
            continue
        t_start, t_end = df["date"].iloc[0], df["date"].iloc[-1]
        if not earliest_start or t_start > earliest_start:
            earliest_start = t_start
        if not latest_end or t_end < latest_end:
            latest_end = t_end

    print(f"\nShared date range across all tickers: {earliest_start} to {latest_end}")
    start_date   = input("Enter start date (YYYY-MM-DD): ").strip()
    end_date     = input("Enter end date (YYYY-MM-DD): ").strip()
    cash_input   = input("Enter initial cash per ticker (default 10000): $").strip()
    initial_cash = float(cash_input) if cash_input else 10000.0

    print("\nChoose a strategy to run across all tickers:")
    print("  1. Buy & Hold")
    print("  2. MA Crossover (50/200)")
    print("  3. RSI Momentum (30/70)")
    strategy_key = input("Strategy [1/2/3]: ").strip()

    result = run_multi_ticker_backtest(
        connection, ticker_list, start_date, end_date, strategy_key, initial_cash
    )
    if result is None:
        print("No data found for that date range across any ticker.")
        return

    print("\nGenerating AI backtest summary (this may take a moment)...")
    summary = get_multi_backtest_summary(result)
    print_multi_backtest_report(result, summary)


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #

def main():
    connection = create_database()
    create_stock_table(connection)

    print("\nWhat would you like to do?")
    print("  1. Analysis & AI summary")
    print("  2. Single-stock simulator")
    print("  3. Portfolio simulator (weighted)")
    print("  4. Position-based portfolio (per-lot entry)")
    print("  5. Strategy backtester")
    print("  6. Run all modes in sequence")
    choice = input("\nEnter choice [1/2/3/4/5/6]: ").strip()

    if choice == "1":
        _run_analysis(connection)
    elif choice == "2":
        _run_simulator(connection)
    elif choice == "3":
        _run_portfolio_simulator(connection)
    elif choice == "4":
        _run_position_portfolio(connection)
    elif choice == "5":
        _run_backtester(connection)
    elif choice == "6":
        _run_analysis(connection)
        _run_simulator(connection)
        _run_portfolio_simulator(connection)
        _run_position_portfolio(connection)
        _run_backtester(connection)
    else:
        print(f"'{choice}' is not a valid option. Please enter 1–6.")

    connection.close()


if __name__ == "__main__":
    main()
