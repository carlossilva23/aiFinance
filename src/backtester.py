"""
File: backtester.py

Purpose: Implements three trading strategy back-tests (Buy & Hold,
MA Crossover, RSI Momentum) on historical OHLCV data retrieved from
the database. Each strategy returns a standardised result dict.
"""
import pandas as pd

from database import get_stock_data_range
from ai_summary import get_summary


# ------------------------------------------------------------------ #
# Private helpers                                                      #
# ------------------------------------------------------------------ #

def _calc_drawdown(portfolio_values):
    """Return the maximum drawdown as a positive decimal.

    Tracks the running peak and computes (current - peak) / peak for
    each value. Returns abs(min of all those ratios).
    """
    peak = portfolio_values[0]
    max_dd = 0.0
    for v in portfolio_values:
        if v > peak:
            peak = v
        if peak != 0:
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return abs(max_dd)


def _calc_volatility(portfolio_values):
    """Return the std deviation of daily % changes in portfolio value."""
    if len(portfolio_values) < 2:
        return 0.0
    changes = []
    for i in range(1, len(portfolio_values)):
        prev = portfolio_values[i - 1]
        if prev != 0:
            changes.append((portfolio_values[i] - prev) / prev)
    if not changes:
        return 0.0
    mean = sum(changes) / len(changes)
    variance = sum((c - mean) ** 2 for c in changes) / len(changes)
    return variance ** 0.5


# ------------------------------------------------------------------ #
# Strategy: Buy & Hold                                                 #
# ------------------------------------------------------------------ #

def run_buy_and_hold(df, initial_cash):
    """Buy all shares on day 0, sell on the last day.

    Parameters
    ----------
    df           : DataFrame with at least a 'close' column
    initial_cash : float — starting capital

    Returns the standard strategy result dict.
    """
    closes = df["close"].tolist()
    dates  = df["date"].tolist()

    buy_price  = closes[0]
    shares     = initial_cash / buy_price
    sell_price = closes[-1]
    final_value = shares * sell_price

    portfolio_values = [shares * c for c in closes]

    trades = [
        {"action": "BUY",  "date": dates[0],  "price": buy_price,
         "shares": shares,  "cash_after": 0.0},
        {"action": "SELL", "date": dates[-1], "price": sell_price,
         "shares": shares,  "cash_after": final_value},
    ]

    pl  = final_value - initial_cash
    pct = (pl / initial_cash) * 100 if initial_cash else 0.0

    return {
        "strategy_name":   "Buy & Hold",
        "initial_cash":    initial_cash,
        "final_value":     final_value,
        "profit_loss":     pl,
        "percent_return":  pct,
        "trade_count":     1,
        "max_drawdown":    _calc_drawdown(portfolio_values),
        "volatility":      _calc_volatility(portfolio_values),
        "trades":          trades,
    }


# ------------------------------------------------------------------ #
# Strategy: MA Crossover                                              #
# ------------------------------------------------------------------ #

def run_ma_crossover(df, initial_cash, fast_window=50, slow_window=200):
    """SMA fast/slow crossover strategy (golden cross / death cross).

    Parameters
    ----------
    df           : DataFrame with 'close' and 'date' columns
    initial_cash : float
    fast_window  : int — default 50
    slow_window  : int — default 200
    """
    close = df["close"]
    sma_fast = close.rolling(fast_window).mean()
    sma_slow = close.rolling(slow_window).mean()

    dates  = df["date"].tolist()
    closes = close.tolist()

    cash   = initial_cash
    shares = 0.0
    trades = []
    portfolio_values = []

    for i in range(len(closes)):
        fast_now  = sma_fast.iloc[i]
        slow_now  = sma_slow.iloc[i]

        # Portfolio value before any trade today
        pv = shares * closes[i] if shares > 0 else cash

        # Only evaluate signals once both SMAs are available
        if i > 0 and pd.notna(fast_now) and pd.notna(slow_now):
            fast_prev = sma_fast.iloc[i - 1]
            slow_prev = sma_slow.iloc[i - 1]

            if pd.notna(fast_prev) and pd.notna(slow_prev):
                # Golden cross — buy
                if fast_prev < slow_prev and fast_now >= slow_now and shares == 0:
                    shares = cash / closes[i]
                    trades.append({
                        "action": "BUY", "date": dates[i],
                        "price": closes[i], "shares": shares, "cash_after": 0.0,
                    })
                    cash = 0.0
                    pv   = shares * closes[i]

                # Death cross — sell
                elif fast_prev >= slow_prev and fast_now < slow_now and shares > 0:
                    cash = shares * closes[i]
                    trades.append({
                        "action": "SELL", "date": dates[i],
                        "price": closes[i], "shares": shares, "cash_after": cash,
                    })
                    shares = 0.0
                    pv     = cash

        portfolio_values.append(shares * closes[i] if shares > 0 else cash)

    # Liquidate at end if still holding
    if shares > 0:
        cash = shares * closes[-1]
        trades.append({
            "action": "SELL", "date": dates[-1],
            "price": closes[-1], "shares": shares, "cash_after": cash,
        })
        portfolio_values[-1] = cash
        shares = 0.0

    final_value  = cash
    trade_count  = sum(1 for t in trades if t["action"] == "SELL")
    pl           = final_value - initial_cash
    pct          = (pl / initial_cash) * 100 if initial_cash else 0.0

    return {
        "strategy_name":  "MA Crossover (50/200)",
        "initial_cash":   initial_cash,
        "final_value":    final_value,
        "profit_loss":    pl,
        "percent_return": pct,
        "trade_count":    trade_count,
        "max_drawdown":   _calc_drawdown(portfolio_values),
        "volatility":     _calc_volatility(portfolio_values),
        "trades":         trades,
    }


# ------------------------------------------------------------------ #
# Strategy: RSI Momentum                                              #
# ------------------------------------------------------------------ #

def run_rsi_momentum(df, initial_cash, period=14, oversold=30, overbought=70):
    """RSI-based momentum strategy.

    Buy when RSI crosses below `oversold`; sell when RSI crosses above
    `overbought`. RSI is re-implemented inline (no import from analysis.py).

    Parameters
    ----------
    df           : DataFrame with 'close' and 'date' columns
    initial_cash : float
    period       : int — RSI look-back period (default 14)
    oversold     : int/float — buy threshold (default 30)
    overbought   : int/float — sell threshold (default 70)
    """
    delta    = df["close"].diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs       = avg_gain / avg_loss
    rsi      = 100 - (100 / (1 + rs))

    dates  = df["date"].tolist()
    closes = df["close"].tolist()

    cash   = initial_cash
    shares = 0.0
    trades = []
    portfolio_values = []

    for i in range(len(closes)):
        rsi_now = rsi.iloc[i]
        pv = shares * closes[i] if shares > 0 else cash

        if i > 0 and pd.notna(rsi_now):
            rsi_prev = rsi.iloc[i - 1]

            if pd.notna(rsi_prev):
                # RSI crosses below oversold — buy signal
                if rsi_prev >= oversold and rsi_now < oversold and shares == 0:
                    shares = cash / closes[i]
                    trades.append({
                        "action": "BUY", "date": dates[i],
                        "price": closes[i], "shares": shares, "cash_after": 0.0,
                    })
                    cash = 0.0
                    pv   = shares * closes[i]

                # RSI crosses above overbought — sell signal
                elif rsi_prev <= overbought and rsi_now > overbought and shares > 0:
                    cash = shares * closes[i]
                    trades.append({
                        "action": "SELL", "date": dates[i],
                        "price": closes[i], "shares": shares, "cash_after": cash,
                    })
                    shares = 0.0
                    pv     = cash

        portfolio_values.append(shares * closes[i] if shares > 0 else cash)

    # Liquidate at end if still holding
    if shares > 0:
        cash = shares * closes[-1]
        trades.append({
            "action": "SELL", "date": dates[-1],
            "price": closes[-1], "shares": shares, "cash_after": cash,
        })
        portfolio_values[-1] = cash
        shares = 0.0

    final_value  = cash
    trade_count  = sum(1 for t in trades if t["action"] == "SELL")
    pl           = final_value - initial_cash
    pct          = (pl / initial_cash) * 100 if initial_cash else 0.0

    return {
        "strategy_name":  "RSI Momentum (30/70)",
        "initial_cash":   initial_cash,
        "final_value":    final_value,
        "profit_loss":    pl,
        "percent_return": pct,
        "trade_count":    trade_count,
        "max_drawdown":   _calc_drawdown(portfolio_values),
        "volatility":     _calc_volatility(portfolio_values),
        "trades":         trades,
    }


# ------------------------------------------------------------------ #
# Main entry point                                                     #
# ------------------------------------------------------------------ #

def run_backtest(connection, ticker, start_date, end_date, initial_cash=10000.0):
    """Run all three strategies over the given date range for one ticker.

    Returns None if no data is found for the date range. Otherwise returns
    a dict with ticker metadata and a ranked list of strategy results.
    """
    df = get_stock_data_range(connection, ticker, start_date, end_date)
    if df.empty:
        return None

    results = [
        run_buy_and_hold(df, initial_cash),
        run_ma_crossover(df, initial_cash),
        run_rsi_momentum(df, initial_cash),
    ]

    ranked = sorted(results, key=lambda r: r["percent_return"], reverse=True)

    return {
        "ticker":         ticker,
        "start_date":     start_date,
        "end_date":       end_date,
        "initial_cash":   initial_cash,
        "results":        ranked,
        "best_strategy":  ranked[0]["strategy_name"],
        "worst_strategy": ranked[-1]["strategy_name"],
    }


# ------------------------------------------------------------------ #
# AI summary helpers                                                   #
# ------------------------------------------------------------------ #

def build_backtest_prompt(backtest_result):
    """Build a structured anti-hallucination prompt for the backtest result."""
    ticker     = backtest_result["ticker"]
    start_date = backtest_result["start_date"]
    end_date   = backtest_result["end_date"]
    initial    = backtest_result["initial_cash"]

    lines = [
        "You are a financial analyst assistant.",
        "Only reference the numbers provided below — do not add any external "
        "knowledge, predictions, or information not present in this data.",
        "",
        f"Backtest results for {ticker} ({start_date} to {end_date})",
        f"Initial capital: ${initial:,.2f}",
        "",
    ]

    for r in backtest_result["results"]:
        lines += [
            f"Strategy: {r['strategy_name']}",
            f"  Final Value:     ${r['final_value']:,.2f}",
            f"  Profit / Loss:   ${r['profit_loss']:,.2f}",
            f"  Return:          {r['percent_return']:.2f}%",
            f"  Max Drawdown:    {r['max_drawdown'] * 100:.2f}%",
            f"  Volatility:      {r['volatility'] * 100:.4f}%",
            f"  Trade Count:     {r['trade_count']}",
            "",
        ]

    lines += [
        f"Best strategy:  {backtest_result['best_strategy']}",
        f"Worst strategy: {backtest_result['worst_strategy']}",
        "",
        "In 4-5 sentences, compare these strategies based only on the numbers above. "
        "Note which performed best, comment on trade-offs between return and risk, "
        "and explain what the results suggest about this stock's price behaviour "
        "during this period.",
    ]

    return "\n".join(lines)


def get_backtest_summary(backtest_result):
    """Build prompt and send to the local LLM; return the response string."""
    prompt = build_backtest_prompt(backtest_result)
    return get_summary(prompt)


# ------------------------------------------------------------------ #
# Multi-ticker: one strategy across many tickers                       #
# ------------------------------------------------------------------ #

STRATEGY_MAP = {
    "1": ("Buy & Hold",          run_buy_and_hold),
    "2": ("MA Crossover (50/200)", run_ma_crossover),
    "3": ("RSI Momentum (30/70)", run_rsi_momentum),
}


def run_multi_ticker_backtest(connection, tickers, start_date, end_date,
                               strategy_key, initial_cash=10000.0):
    """Run one chosen strategy across multiple tickers over the same date range.

    Parameters
    ----------
    connection   : sqlite3 connection
    tickers      : list of str
    start_date   : str YYYY-MM-DD
    end_date     : str YYYY-MM-DD
    strategy_key : str — "1" (Buy & Hold), "2" (MA Crossover), "3" (RSI Momentum)
    initial_cash : float

    Returns
    -------
    dict or None (if no ticker produced data).

    Keys
    ----
    strategy_name, start_date, end_date, initial_cash,
    results       — list of per-ticker dicts (ticker + strategy result), ranked by return
    best_ticker, worst_ticker
    """
    if strategy_key not in STRATEGY_MAP:
        raise ValueError(f"strategy_key must be one of {list(STRATEGY_MAP.keys())}")

    strategy_name, strategy_fn = STRATEGY_MAP[strategy_key]

    ticker_results = []
    for ticker in tickers:
        df = get_stock_data_range(connection, ticker, start_date, end_date)
        if df.empty:
            continue
        result = strategy_fn(df, initial_cash)
        result["ticker"] = ticker
        ticker_results.append(result)

    if not ticker_results:
        return None

    ranked = sorted(ticker_results, key=lambda r: r["percent_return"], reverse=True)

    return {
        "strategy_name": strategy_name,
        "start_date":    start_date,
        "end_date":      end_date,
        "initial_cash":  initial_cash,
        "results":       ranked,
        "best_ticker":   ranked[0]["ticker"],
        "worst_ticker":  ranked[-1]["ticker"],
    }


def build_multi_backtest_prompt(multi_result):
    """Build a structured anti-hallucination prompt for the multi-ticker backtest."""
    lines = [
        "You are a financial analyst assistant.",
        "Only reference the numbers provided below — do not add any external "
        "knowledge, predictions, or information not present in this data.",
        "",
        f"Strategy: {multi_result['strategy_name']}",
        f"Date Range: {multi_result['start_date']} to {multi_result['end_date']}",
        f"Initial Capital per Ticker: ${multi_result['initial_cash']:,.2f}",
        "",
        "Results by ticker (ranked best to worst):",
    ]
    for r in multi_result["results"]:
        sign = "+" if r["percent_return"] >= 0 else ""
        lines += [
            f"  {r['ticker']}:",
            f"    Final Value:  ${r['final_value']:,.2f}",
            f"    Return:       {sign}{r['percent_return']:.2f}%",
            f"    Max Drawdown: {r['max_drawdown']*100:.2f}%",
            f"    Volatility:   {r['volatility']*100:.4f}%",
            f"    Trades:       {r['trade_count']}",
            "",
        ]
    lines += [
        f"Best ticker:  {multi_result['best_ticker']}",
        f"Worst ticker: {multi_result['worst_ticker']}",
        "",
        "In 4-5 sentences, compare these tickers under this strategy based only on "
        "the numbers above. Highlight which ticker performed best and worst, comment "
        "on any notable differences in drawdown or trade count, and describe what "
        "the results suggest about each stock's behaviour during this period.",
    ]
    return "\n".join(lines)


def get_multi_backtest_summary(multi_result):
    """Build prompt and send to the local LLM; return the response string."""
    prompt = build_multi_backtest_prompt(multi_result)
    return get_summary(prompt)
