"""
File: simulator.py

Purpose: Simulates hypothetical buy-and-hold investments using closing prices
from the database. Supports single-stock simulation (run_simulation),
weighted portfolio simulation (run_portfolio_simulation), and per-lot
position-based simulation (run_position_based_portfolio). Delegates AI
explanations to the local Ollama model via ai_summary.get_summary().
"""
from collections import defaultdict

from database import get_stock_data, get_stock_data_range
from ai_summary import get_summary


def run_simulation(connection, ticker, start_date, end_date,
                   investment_amount=None, shares=None):
    """Simulate a buy-and-hold investment using close prices from the database.

    Exactly one of investment_amount or shares must be provided.

    Parameters
    ----------
    connection        : sqlite3 connection
    ticker            : str   — stock ticker symbol, e.g. "AAPL"
    start_date        : str   — YYYY-MM-DD buy date (inclusive)
    end_date          : str   — YYYY-MM-DD sell date (inclusive)
    investment_amount : float — dollars invested, e.g. 1000.0  (mutually exclusive with shares)
    shares            : float — number of shares purchased, e.g. 10.0 (mutually exclusive with investment_amount)

    Returns
    -------
    dict with simulation results, or None if no data exists for the range.
    """
    if (investment_amount is None) == (shares is None):
        raise ValueError("Provide exactly one of investment_amount or shares.")

    df = get_stock_data_range(connection, ticker, start_date, end_date)
    if df.empty:
        return None

    buy_price  = df["close"].iloc[0]
    sell_price = df["close"].iloc[-1]

    if investment_amount is not None:
        shares_purchased  = investment_amount / buy_price
        amount_invested   = investment_amount
    else:
        shares_purchased  = shares
        amount_invested   = shares * buy_price

    final_value    = shares_purchased * sell_price
    profit_loss    = final_value - amount_invested
    percent_return = (profit_loss / amount_invested) * 100

    return {
        "ticker":            ticker,
        "start_date":        df["date"].iloc[0],
        "end_date":          df["date"].iloc[-1],
        "investment_amount": amount_invested,
        "buy_price":         buy_price,
        "sell_price":        sell_price,
        "shares_purchased":  shares_purchased,
        "final_value":       final_value,
        "profit_loss":       profit_loss,
        "percent_return":    percent_return,
        "df":                df,
    }


def build_simulation_prompt(sim_result):
    """Build a structured prompt for the AI explanation of a simulation result.

    Only passes computed values — the LLM is never asked to recall facts.
    """
    profitable = sim_result["profit_loss"] >= 0
    lines = [
        "You are a financial analyst assistant.",
        "A hypothetical investment simulation produced the following results.",
        "Only reference the numbers provided below — do not add any external "
        "knowledge, predictions, or information not present in this data.",
        "",
        f"Ticker:            {sim_result['ticker']}",
        f"Date Range:        {sim_result['start_date']} to {sim_result['end_date']}",
        f"Investment Amount: ${sim_result['investment_amount']:,.2f}",
        f"Buy Price:         ${sim_result['buy_price']:.2f}",
        f"Sell Price:        ${sim_result['sell_price']:.2f}",
        f"Shares Purchased:  {sim_result['shares_purchased']:.4f}",
        f"Final Value:       ${sim_result['final_value']:,.2f}",
        f"Profit / Loss:     ${sim_result['profit_loss']:+,.2f}",
        f"Percent Return:    {sim_result['percent_return']:+.2f}%",
        f"Outcome:           {'Profitable' if profitable else 'Unprofitable'}",
        "",
        "In 3-4 sentences, explain what happened to this investment based only on "
        "the numbers above. Do not add any information not provided.",
    ]
    return "\n".join(lines)


def get_simulation_summary(sim_result):
    """Return an AI-generated plain-English explanation of the simulation result."""
    prompt = build_simulation_prompt(sim_result)
    return get_summary(prompt)


# ------------------------------------------------------------------ #
# Portfolio simulation                                                 #
# ------------------------------------------------------------------ #

def run_portfolio_simulation(connection, tickers, weights, total_investment,
                              start_date, end_date):
    """Simulate a weighted multi-stock portfolio over a date range.

    Parameters
    ----------
    connection       : sqlite3 connection
    tickers          : list of str   — e.g. ["AAPL", "NVDA", "MSFT"]
    weights          : list of float — must sum to 1.0, e.g. [0.5, 0.3, 0.2]
    total_investment : float         — total dollars to invest across all positions
    start_date       : str           — YYYY-MM-DD buy date (inclusive)
    end_date         : str           — YYYY-MM-DD sell date (inclusive)

    Returns
    -------
    dict with portfolio-level results, or None if no position has data.

    Keys
    ----
    tickers, weights, total_investment, start_date, end_date,
    positions        — list of per-position dicts (see below),
    total_final_value, total_profit_loss, total_percent_return,
    best_performer   — ticker string,
    worst_performer  — ticker string
    """
    if len(tickers) != len(weights):
        raise ValueError("tickers and weights must have the same length.")
    if abs(sum(weights) - 1.0) > 1e-6:
        raise ValueError(f"Weights must sum to 1.0 (got {sum(weights):.6f}).")

    positions = []
    for ticker, weight in zip(tickers, weights):
        alloc = total_investment * weight
        result = run_simulation(connection, ticker, start_date, end_date,
                                investment_amount=alloc)
        if result is None:
            continue
        result["weight"] = weight
        positions.append(result)

    if not positions:
        return None

    total_final_value  = sum(p["final_value"]    for p in positions)
    total_profit_loss  = sum(p["profit_loss"]     for p in positions)
    invested           = sum(p["investment_amount"] for p in positions)
    total_pct_return   = (total_profit_loss / invested) * 100

    ranked = sorted(positions, key=lambda p: p["percent_return"], reverse=True)

    return {
        "tickers":             tickers,
        "weights":             weights,
        "total_investment":    total_investment,
        "start_date":          positions[0]["start_date"],
        "end_date":            positions[0]["end_date"],
        "positions":           positions,
        "total_final_value":   total_final_value,
        "total_profit_loss":   total_profit_loss,
        "total_percent_return": total_pct_return,
        "best_performer":      ranked[0]["ticker"],
        "worst_performer":     ranked[-1]["ticker"],
    }


def build_portfolio_prompt(portfolio_result):
    """Build a structured anti-hallucination prompt for the portfolio AI summary."""
    lines = [
        "You are a financial analyst assistant.",
        "A hypothetical portfolio simulation produced the following results.",
        "Only reference the numbers provided below — do not add any external "
        "knowledge, predictions, or information not present in this data.",
        "",
        f"Date Range:          {portfolio_result['start_date']} to {portfolio_result['end_date']}",
        f"Total Invested:      ${portfolio_result['total_investment']:,.2f}",
        f"Total Final Value:   ${portfolio_result['total_final_value']:,.2f}",
        f"Total Profit / Loss: ${portfolio_result['total_profit_loss']:+,.2f}",
        f"Total Return:        {portfolio_result['total_percent_return']:+.2f}%",
        f"Best Performer:      {portfolio_result['best_performer']}",
        f"Worst Performer:     {portfolio_result['worst_performer']}",
        "",
        "Individual positions:",
    ]
    for p in portfolio_result["positions"]:
        lines += [
            f"  {p['ticker']}:",
            f"    Weight:          {p['weight']*100:.1f}%",
            f"    Amount Invested: ${p['investment_amount']:,.2f}",
            f"    Buy Price:       ${p['buy_price']:.2f}",
            f"    Sell Price:      ${p['sell_price']:.2f}",
            f"    Shares:          {p['shares_purchased']:.4f}",
            f"    Final Value:     ${p['final_value']:,.2f}",
            f"    Profit / Loss:   ${p['profit_loss']:+,.2f}",
            f"    Return:          {p['percent_return']:+.2f}%",
            "",
        ]
    lines += [
        "In 4-5 sentences, summarise how this portfolio performed. Highlight the best "
        "and worst performers, comment on the overall return, and note any position "
        "that stood out. Base your response only on the numbers above.",
    ]
    return "\n".join(lines)


def get_portfolio_summary(portfolio_result):
    """Return an AI-generated plain-English summary of the portfolio simulation."""
    prompt = build_portfolio_prompt(portfolio_result)
    return get_summary(prompt)


# ------------------------------------------------------------------ #
# Position-based portfolio simulation                                  #
# ------------------------------------------------------------------ #

def run_position_based_portfolio(connection, positions_input):
    """Simulate a portfolio where each position has its own dates and size.

    Supports multiple lots of the same ticker bought at different dates.
    The exit date defaults to the latest stored date for that ticker when
    not supplied.

    Parameters
    ----------
    connection      : sqlite3 connection
    positions_input : list of dicts, each with keys:
        ticker          (str)
        entry_date      (str, YYYY-MM-DD)
        exit_date       (str, YYYY-MM-DD) or None — defaults to latest stored date
        shares          (float) or None
        investment_amount (float) or None   — exactly one of shares/investment_amount

    Returns
    -------
    dict with portfolio results, or None if no lot produced data.

    Keys
    ----
    lots             — list of individual lot result dicts (one per input position)
    ticker_summaries — dict keyed by ticker with combined cost basis / value / return
    total_invested, total_final_value, total_profit_loss, total_percent_return,
    best_performer, worst_performer
    """
    lots = []
    for pos in positions_input:
        ticker     = pos["ticker"]
        entry_date = pos["entry_date"]

        # Resolve exit date: default to latest stored date for this ticker
        if pos.get("exit_date"):
            exit_date = pos["exit_date"]
        else:
            full_df = get_stock_data(connection, ticker)
            if full_df.empty:
                continue
            exit_date = full_df["date"].iloc[-1]

        lot = run_simulation(
            connection, ticker, entry_date, exit_date,
            investment_amount=pos.get("investment_amount"),
            shares=pos.get("shares"),
        )
        if lot is None:
            continue
        lot["entry_date"] = lot["start_date"]   # alias for clarity
        lot["exit_date"]  = lot["end_date"]
        lots.append(lot)

    if not lots:
        return None

    # ── Per-ticker summaries (merge lots of the same ticker) ────────────── #
    by_ticker = defaultdict(list)
    for lot in lots:
        by_ticker[lot["ticker"]].append(lot)

    ticker_summaries = {}
    for ticker, ticker_lots in by_ticker.items():
        total_inv   = sum(l["investment_amount"] for l in ticker_lots)
        total_final = sum(l["final_value"]       for l in ticker_lots)
        total_pl    = sum(l["profit_loss"]        for l in ticker_lots)
        total_shares = sum(l["shares_purchased"]  for l in ticker_lots)
        blended_return = (total_pl / total_inv) * 100 if total_inv else 0.0
        ticker_summaries[ticker] = {
            "ticker":            ticker,
            "lots":              ticker_lots,
            "total_invested":    total_inv,
            "total_final_value": total_final,
            "total_profit_loss": total_pl,
            "total_shares":      total_shares,
            "blended_return":    blended_return,
        }

    # ── Portfolio totals ─────────────────────────────────────────────────── #
    total_invested   = sum(s["total_invested"]    for s in ticker_summaries.values())
    total_final      = sum(s["total_final_value"] for s in ticker_summaries.values())
    total_pl         = sum(s["total_profit_loss"] for s in ticker_summaries.values())
    total_pct_return = (total_pl / total_invested) * 100 if total_invested else 0.0

    ranked = sorted(ticker_summaries.values(),
                    key=lambda s: s["blended_return"], reverse=True)

    return {
        "lots":               lots,
        "ticker_summaries":   ticker_summaries,
        "total_invested":     total_invested,
        "total_final_value":  total_final,
        "total_profit_loss":  total_pl,
        "total_percent_return": total_pct_return,
        "best_performer":     ranked[0]["ticker"],
        "worst_performer":    ranked[-1]["ticker"],
    }


def build_position_portfolio_prompt(portfolio_result):
    """Build a structured anti-hallucination prompt for the position-based portfolio."""
    lines = [
        "You are a financial analyst assistant.",
        "A hypothetical position-based portfolio simulation produced the following results.",
        "Only reference the numbers provided below — do not add any external "
        "knowledge, predictions, or information not present in this data.",
        "",
        f"Total Invested:      ${portfolio_result['total_invested']:,.2f}",
        f"Total Final Value:   ${portfolio_result['total_final_value']:,.2f}",
        f"Total Profit / Loss: ${portfolio_result['total_profit_loss']:+,.2f}",
        f"Total Return:        {portfolio_result['total_percent_return']:+.2f}%",
        f"Best Performer:      {portfolio_result['best_performer']}",
        f"Worst Performer:     {portfolio_result['worst_performer']}",
        "",
        "Per-ticker summary (blended across all lots):",
    ]
    for summary in portfolio_result["ticker_summaries"].values():
        lines += [
            f"  {summary['ticker']}:",
            f"    Total Invested:  ${summary['total_invested']:,.2f}",
            f"    Total Shares:    {summary['total_shares']:.4f}",
            f"    Final Value:     ${summary['total_final_value']:,.2f}",
            f"    Profit / Loss:   ${summary['total_profit_loss']:+,.2f}",
            f"    Blended Return:  {summary['blended_return']:+.2f}%",
            "",
        ]
    lines += [
        "Individual lots:",
    ]
    for lot in portfolio_result["lots"]:
        lines += [
            f"  {lot['ticker']} lot ({lot['entry_date']} → {lot['exit_date']}):",
            f"    Shares:        {lot['shares_purchased']:.4f}",
            f"    Buy Price:     ${lot['buy_price']:.2f}",
            f"    Sell Price:    ${lot['sell_price']:.2f}",
            f"    Cost Basis:    ${lot['investment_amount']:,.2f}",
            f"    Final Value:   ${lot['final_value']:,.2f}",
            f"    Return:        {lot['percent_return']:+.2f}%",
            "",
        ]
    lines += [
        "In 4-5 sentences, summarise how this portfolio performed. Note the best and "
        "worst performers, comment on the impact of different entry dates, and describe "
        "the overall outcome. Base your response only on the numbers above.",
    ]
    return "\n".join(lines)


def get_position_portfolio_summary(portfolio_result):
    """Return an AI-generated plain-English summary of the position-based portfolio."""
    prompt = build_position_portfolio_prompt(portfolio_result)
    return get_summary(prompt)
