"""
File: report_generator.py

Purpose: Formats and prints a structured terminal report for a single
ticker using the results dict returned by analyze_ticker(). Uses rich
for table and panel layout. Contains no analysis logic — formatting
and plain-language signal derivation only.
"""
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
