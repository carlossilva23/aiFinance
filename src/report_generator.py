"""
File: report_generator.py

Purpose: Formats and prints a structured terminal report for a single
ticker using the results dict returned by analyze_ticker(). Uses rich
for table and panel layout. Contains no analysis logic — formatting
and plain-language signal derivation only.
"""
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown

console = Console()


def generate_report(ticker, results):
    """Print a rich-formatted terminal report for *ticker*.

    Parameters
    ----------
    ticker  : str   — the stock ticker symbol
    results : dict  — dict returned by analyze_ticker()
    """
    df = results["df"]

    # ------------------------------------------------------------------ #
    # Shared values used across both sections                              #
    # ------------------------------------------------------------------ #
    last_close = df["close"].iloc[-1]
    starting_price = df["close"].iloc[0]
    ending_price = last_close
    pct_return = ((ending_price - starting_price) / starting_price) * 100
    date_range = f"{df['date'].iloc[0]}  →  {df['date'].iloc[-1]}"
    avg_volume = int(df["volume"].mean())
    volatility = results["volatility"].dropna().iloc[-1]
    highest = results["price_extremes"]["highest_close"]
    lowest = results["price_extremes"]["lowest_close"]
    largest_gain = results["price_extremes"]["largest_gain"] * 100
    largest_loss = results["price_extremes"]["largest_loss"] * 100

    # ------------------------------------------------------------------ #
    # Section 1 — Summary Metrics                                         #
    # ------------------------------------------------------------------ #
    summary_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value")

    summary_table.add_row("Date Range", date_range)
    summary_table.add_row("Starting Price", f"${starting_price:.2f}")
    summary_table.add_row("Ending Price", f"${ending_price:.2f}")
    summary_table.add_row("Percent Return", f"{pct_return:.2f}%")
    summary_table.add_row("Avg Daily Volume", f"{avg_volume:,}")
    summary_table.add_row("Volatility (20d)", f"{volatility:.4f}")
    summary_table.add_row("Highest Close", f"${highest:.2f}")
    summary_table.add_row("Lowest Close", f"${lowest:.2f}")
    summary_table.add_row("Largest 1-Day Gain", f"{largest_gain:.2f}%")
    summary_table.add_row("Largest 1-Day Loss", f"{largest_loss:.2f}%")

    # ------------------------------------------------------------------ #
    # Section 2 — Technical Indicators                                    #
    # ------------------------------------------------------------------ #
    ma = results["moving_averages"]
    sma20 = ma["sma_20"].dropna().iloc[-1]
    sma50 = ma["sma_50"].dropna().iloc[-1]
    ema20 = results["ema"].dropna().iloc[-1]
    rsi = results["rsi"].dropna().iloc[-1]
    macd_df = results["macd"]
    macd_val = macd_df["macd"].dropna().iloc[-1]
    signal_val = macd_df["signal"].dropna().iloc[-1]
    bb = results["bollinger_bands"]
    bb_upper = bb["bb_upper"].dropna().iloc[-1]
    bb_lower = bb["bb_lower"].dropna().iloc[-1]

    indicators_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    indicators_table.add_column("Indicator", style="bold")
    indicators_table.add_column("Value")
    indicators_table.add_column("Signal", style="dim")

    indicators_table.add_row("SMA 20", f"${sma20:.2f}", "Price above SMA 20" if last_close >= sma20 else "Price below SMA 20")
    indicators_table.add_row("SMA 50", f"${sma50:.2f}", "Price above SMA 50 — bullish" if last_close >= sma50 else "Price below SMA 50 — bearish")
    indicators_table.add_row("EMA 20", f"${ema20:.2f}", "Price above EMA 20" if last_close >= ema20 else "Price below EMA 20")
    indicators_table.add_row("RSI (14)", f"{rsi:.2f}", "Overbought" if rsi > 70 else ("Oversold" if rsi < 30 else "Neutral"))
    indicators_table.add_row("MACD", f"{macd_val:.4f}", "Bullish crossover" if macd_val > signal_val else "Bearish crossover")
    indicators_table.add_row("Signal Line", f"{signal_val:.4f}", "")
    indicators_table.add_row("BB Upper", f"${bb_upper:.2f}", "Near overbought" if last_close > bb_upper else "-")
    indicators_table.add_row("BB Lower", f"${bb_lower:.2f}", "Near oversold" if last_close < bb_lower else "-")

    # ------------------------------------------------------------------ #
    # Render inside a Panel                                                #
    # ------------------------------------------------------------------ #
    console.print()
    console.print(Panel(
        Columns([summary_table, indicators_table], equal=False, expand=False),
        title=f"[bold]{ticker} — Analysis Report[/bold]",
        border_style="blue",
        padding=(1, 2),
    ))


def print_simulation_report(sim_result, ai_explanation):
    """Print a rich-formatted simulation report inside a green-bordered Panel.

    Parameters
    ----------
    sim_result      : dict — result dict returned by run_simulation()
    ai_explanation  : str  — plain-English text returned by get_simulation_summary()
    """
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    profit = sim_result["profit_loss"] >= 0
    pl_colour = "green" if profit else "red"
    pl_sign   = "+" if profit else ""
    ret_sign  = "+" if sim_result["percent_return"] >= 0 else ""

    table.add_row("Date Range",        f"{sim_result['start_date']} → {sim_result['end_date']}")
    table.add_row("Investment Amount", f"${sim_result['investment_amount']:,.2f}")
    table.add_row("Buy Price (entry)", f"${sim_result['buy_price']:.2f}")
    table.add_row("Sell Price (exit)", f"${sim_result['sell_price']:.2f}")
    table.add_row("Shares Purchased",  f"{sim_result['shares_purchased']:.4f}")
    table.add_row("Final Value",       f"${sim_result['final_value']:,.2f}")
    table.add_row(
        "Profit / Loss",
        f"[{pl_colour}]{pl_sign}${abs(sim_result['profit_loss']):,.2f}[/{pl_colour}]",
    )
    table.add_row(
        "Return",
        f"[{pl_colour}]{ret_sign}{sim_result['percent_return']:.2f}%[/{pl_colour}]",
    )

    separator = Text("─" * 40, style="dim")

    panel_content = Group(table, Text(""), separator, Text(ai_explanation))

    console.print()
    console.print(Panel(
        panel_content,
        title=f"[bold]{sim_result['ticker']} — Investment Simulator[/bold]",
        border_style="green",
        padding=(1, 2),
    ))


def print_ai_summary(summary_text, tickers):
    """Print the AI-generated summary inside a rich Panel matching the report style.

    Parameters
    ----------
    summary_text : str  — plain-English text returned by get_summary()
    tickers      : list — list of ticker symbols included in the summary
    """
    title = "[bold]AI Summary — " + ", ".join(tickers) + "[/bold]"
    console.print()
    console.print(Panel(
        Markdown(summary_text),
        title=title,
        border_style="purple",
        padding=(1, 3),
    ))


def print_portfolio_report(portfolio_result, ai_explanation):
    """Print a rich-formatted portfolio simulation report inside a yellow-bordered Panel.

    Parameters
    ----------
    portfolio_result : dict — result dict returned by run_portfolio_simulation()
    ai_explanation   : str  — plain-English text returned by get_portfolio_summary()
    """
    profit = portfolio_result["total_profit_loss"] >= 0
    pl_colour = "green" if profit else "red"
    pl_sign   = "+" if profit else ""
    ret_sign  = "+" if portfolio_result["total_percent_return"] >= 0 else ""

    # ------------------------------------------------------------------ #
    # Section 1 — Portfolio Summary                                        #
    # ------------------------------------------------------------------ #
    summary_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value")

    summary_table.add_row(
        "Date Range",
        f"{portfolio_result['start_date']} → {portfolio_result['end_date']}",
    )
    summary_table.add_row("Total Invested",    f"${portfolio_result['total_investment']:,.2f}")
    summary_table.add_row("Total Final Value", f"${portfolio_result['total_final_value']:,.2f}")
    summary_table.add_row(
        "Total Profit / Loss",
        f"[{pl_colour}]{pl_sign}${portfolio_result['total_profit_loss']:,.2f}[/{pl_colour}]",
    )
    summary_table.add_row(
        "Total Return",
        f"[{pl_colour}]{ret_sign}{portfolio_result['total_percent_return']:.2f}%[/{pl_colour}]",
    )
    summary_table.add_row("Best Performer",  f"[green]{portfolio_result['best_performer']}[/green]")
    summary_table.add_row("Worst Performer", f"[red]{portfolio_result['worst_performer']}[/red]")

    # ------------------------------------------------------------------ #
    # Section 2 — Per-Position Breakdown                                   #
    # ------------------------------------------------------------------ #
    positions_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    positions_table.add_column("Ticker",   style="bold")
    positions_table.add_column("Weight")
    positions_table.add_column("Invested")
    positions_table.add_column("Final Value")
    positions_table.add_column("Return")

    ranked = sorted(portfolio_result["positions"],
                    key=lambda p: p["percent_return"], reverse=True)
    for p in ranked:
        pos_profit  = p["percent_return"] >= 0
        pos_colour  = "green" if pos_profit else "red"
        pos_sign    = "+" if pos_profit else ""
        positions_table.add_row(
            p["ticker"],
            f"{p['weight']*100:.1f}%",
            f"${p['investment_amount']:,.2f}",
            f"${p['final_value']:,.2f}",
            f"[{pos_colour}]{pos_sign}{p['percent_return']:.2f}%[/{pos_colour}]",
        )

    separator = Text("─" * 40, style="dim")
    panel_content = Group(
        Columns([summary_table, positions_table], equal=False, expand=False),
        Text(""),
        separator,
        Text(ai_explanation),
    )

    tickers_str = ", ".join(portfolio_result["tickers"])
    console.print()
    console.print(Panel(
        panel_content,
        title=f"[bold]Portfolio Simulator — {tickers_str}[/bold]",
        border_style="yellow",
        padding=(1, 2),
    ))


def print_position_portfolio_report(portfolio_result, ai_explanation):
    """Print a rich-formatted position-based portfolio report in an orange-bordered Panel.

    Shows individual lots per ticker, a merged per-ticker summary, and portfolio totals.

    Parameters
    ----------
    portfolio_result : dict — result from run_position_based_portfolio()
    ai_explanation   : str  — plain-English text from get_position_portfolio_summary()
    """
    profit    = portfolio_result["total_profit_loss"] >= 0
    pl_colour = "green" if profit else "red"
    pl_sign   = "+" if profit else ""
    ret_sign  = "+" if portfolio_result["total_percent_return"] >= 0 else ""

    # ------------------------------------------------------------------ #
    # Section 1 — Portfolio Totals                                         #
    # ------------------------------------------------------------------ #
    totals_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    totals_table.add_column("Metric", style="bold")
    totals_table.add_column("Value")

    totals_table.add_row("Total Invested",    f"${portfolio_result['total_invested']:,.2f}")
    totals_table.add_row("Total Final Value", f"${portfolio_result['total_final_value']:,.2f}")
    totals_table.add_row(
        "Total Profit / Loss",
        f"[{pl_colour}]{pl_sign}${portfolio_result['total_profit_loss']:,.2f}[/{pl_colour}]",
    )
    totals_table.add_row(
        "Total Return",
        f"[{pl_colour}]{ret_sign}{portfolio_result['total_percent_return']:.2f}%[/{pl_colour}]",
    )
    totals_table.add_row("Best Performer",  f"[green]{portfolio_result['best_performer']}[/green]")
    totals_table.add_row("Worst Performer", f"[red]{portfolio_result['worst_performer']}[/red]")

    # ------------------------------------------------------------------ #
    # Section 2 — Per-Ticker Summary (blended across lots)                 #
    # ------------------------------------------------------------------ #
    ticker_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    ticker_table.add_column("Ticker",        style="bold")
    ticker_table.add_column("Shares")
    ticker_table.add_column("Invested")
    ticker_table.add_column("Final Value")
    ticker_table.add_column("Blended Return")

    ranked_summaries = sorted(
        portfolio_result["ticker_summaries"].values(),
        key=lambda s: s["blended_return"], reverse=True,
    )
    for s in ranked_summaries:
        pos_colour = "green" if s["blended_return"] >= 0 else "red"
        pos_sign   = "+" if s["blended_return"] >= 0 else ""
        ticker_table.add_row(
            s["ticker"],
            f"{s['total_shares']:.4f}",
            f"${s['total_invested']:,.2f}",
            f"${s['total_final_value']:,.2f}",
            f"[{pos_colour}]{pos_sign}{s['blended_return']:.2f}%[/{pos_colour}]",
        )

    # ------------------------------------------------------------------ #
    # Section 3 — Individual Lots                                          #
    # ------------------------------------------------------------------ #
    lots_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    lots_table.add_column("Ticker",     style="bold")
    lots_table.add_column("Entry")
    lots_table.add_column("Exit")
    lots_table.add_column("Shares")
    lots_table.add_column("Buy $")
    lots_table.add_column("Sell $")
    lots_table.add_column("Return")

    for lot in portfolio_result["lots"]:
        lot_colour = "green" if lot["percent_return"] >= 0 else "red"
        lot_sign   = "+" if lot["percent_return"] >= 0 else ""
        lots_table.add_row(
            lot["ticker"],
            lot["entry_date"],
            lot["exit_date"],
            f"{lot['shares_purchased']:.4f}",
            f"${lot['buy_price']:.2f}",
            f"${lot['sell_price']:.2f}",
            f"[{lot_colour}]{lot_sign}{lot['percent_return']:.2f}%[/{lot_colour}]",
        )

    separator = Text("─" * 40, style="dim")
    panel_content = Group(
        Text("Portfolio Totals", style="bold underline"),
        totals_table,
        Text(""),
        Text("Per-Ticker Summary", style="bold underline"),
        ticker_table,
        Text(""),
        Text("Individual Lots", style="bold underline"),
        lots_table,
        Text(""),
        separator,
        Text(ai_explanation),
    )

    console.print()
    console.print(Panel(
        panel_content,
        title="[bold]Position-Based Portfolio Simulator[/bold]",
        border_style="dark_orange",
        padding=(1, 2),
    ))


def print_backtest_report(backtest_result, ai_explanation):
    """Print a rich-formatted backtest report inside a cyan-bordered Panel.

    Parameters
    ----------
    backtest_result : dict — result dict returned by run_backtest()
    ai_explanation  : str  — plain-English text returned by get_backtest_summary()
    """
    ticker     = backtest_result["ticker"]
    start_date = backtest_result["start_date"]
    end_date   = backtest_result["end_date"]
    best       = backtest_result["best_strategy"]

    # ------------------------------------------------------------------ #
    # Section 1 — Strategy Comparison table                                #
    # ------------------------------------------------------------------ #
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Strategy",     style="bold")
    table.add_column("Final Value")
    table.add_column("Return")
    table.add_column("Max Drawdown")
    table.add_column("Volatility")
    table.add_column("Trades")

    for r in backtest_result["results"]:
        is_best   = r["strategy_name"] == best
        name_text = f"[bold]{r['strategy_name']}[/bold]" if is_best else r["strategy_name"]
        ret_colour = "green" if r["percent_return"] >= 0 else "red"
        ret_sign   = "+" if r["percent_return"] >= 0 else ""
        table.add_row(
            name_text,
            f"${r['final_value']:,.2f}",
            f"[{ret_colour}]{ret_sign}{r['percent_return']:.2f}%[/{ret_colour}]",
            f"{r['max_drawdown'] * 100:.2f}%",
            f"{r['volatility'] * 100:.4f}%",
            str(r["trade_count"]),
        )

    separator = Text("─" * 40, style="dim")
    panel_content = Group(
        table,
        Text(""),
        separator,
        Text(""),
        Markdown(ai_explanation),
    )

    console.print()
    console.print(Panel(
        panel_content,
        title=f"[bold]{ticker} — Strategy Backtest ({start_date} to {end_date})[/bold]",
        border_style="cyan",
        padding=(1, 2),
    ))


def print_multi_backtest_report(multi_result, ai_explanation):
    """Print a multi-ticker backtest comparison inside a cyan-bordered Panel.

    Parameters
    ----------
    multi_result    : dict — result from run_multi_ticker_backtest()
    ai_explanation  : str  — plain-English text from get_multi_backtest_summary()
    """
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Ticker",       style="bold")
    table.add_column("Final Value")
    table.add_column("Return")
    table.add_column("Max Drawdown")
    table.add_column("Volatility")
    table.add_column("Trades")

    for r in multi_result["results"]:
        ret_profit = r["percent_return"] >= 0
        colour     = "green" if ret_profit else "red"
        sign       = "+" if ret_profit else ""
        is_best    = r["ticker"] == multi_result["best_ticker"]
        ticker_str = f"[bold]{r['ticker']}[/bold]" if is_best else r["ticker"]
        table.add_row(
            ticker_str,
            f"${r['final_value']:,.2f}",
            f"[{colour}]{sign}{r['percent_return']:.2f}%[/{colour}]",
            f"{r['max_drawdown']*100:.2f}%",
            f"{r['volatility']*100:.4f}%",
            str(r["trade_count"]),
        )

    separator = Text("─" * 40, style="dim")
    panel_content = Group(
        table,
        Text(""),
        separator,
        Markdown(ai_explanation),
    )

    console.print()
    console.print(Panel(
        panel_content,
        title=(f"[bold]Multi-Ticker Backtest — {multi_result['strategy_name']} "
               f"({multi_result['start_date']} to {multi_result['end_date']})[/bold]"),
        border_style="cyan",
        padding=(1, 2),
    ))
