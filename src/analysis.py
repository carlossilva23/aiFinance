"""
File: analysis.py

Purpose: Computes technical indicators and financial metrics from raw
OHLCV data retrieved from the database. All calculations are performed
on-the-fly using pandas — nothing is stored back to SQLite.
"""
import pandas as pd

from database import get_stock_data


def calc_daily_returns(df):
    """Return a Series of day-over-day percent changes on the close column."""
    return df["close"].pct_change()


def calc_moving_averages(df):
    """Return a DataFrame with SMA 7, SMA 20, SMA 30, and SMA 50 columns."""
    close = df["close"]
    return pd.DataFrame({
        "sma_7":  close.rolling(7).mean(),
        "sma_20": close.rolling(20).mean(),
        "sma_30": close.rolling(30).mean(),
        "sma_50": close.rolling(50).mean(),
    })


def calc_ema(df, span=20):
    """Return a Series containing the exponential moving average of close.

    The Series is named 'ema_{span}'. Uses adjust=False so each value
    is a true running EMA rather than a weighted average of all history.
    """
    series = df["close"].ewm(span=span, adjust=False).mean()
    series.name = f"ema_{span}"
    return series


def calc_volatility(df):
    """Return a Series of rolling 20-day standard deviation of daily returns."""
    daily_returns = calc_daily_returns(df)
    return daily_returns.rolling(20).std()


def calc_rsi(df, period=14):
    """Return a Series of RSI values on a 0–100 scale.

    Steps:
    1. Compute daily price changes via close.diff().
    2. Separate gains (positive deltas, others zeroed) from losses
       (negative deltas made positive, others zeroed).
    3. Compute rolling mean of gains and losses over `period` days.
    4. RSI = 100 - (100 / (1 + avg_gain / avg_loss)).
    """
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_macd(df):
    """Return a DataFrame with EMA 12, EMA 26, MACD line, and Signal line.

    Columns returned:
    - ema_12  : 12-period EMA of close
    - ema_26  : 26-period EMA of close
    - macd    : ema_12 - ema_26
    - signal  : 9-period EMA of the MACD line
    """
    close = df["close"]
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9, adjust=False).mean()
    return pd.DataFrame({
        "ema_12": ema_12,
        "ema_26": ema_26,
        "macd":   macd,
        "signal": signal,
    })


def calc_bollinger_bands(df, window=20):
    """Return a DataFrame with upper, middle, and lower Bollinger Band columns.

    Middle band = SMA of close over `window` periods.
    Upper band  = middle + 2 * rolling std.
    Lower band  = middle - 2 * rolling std.
    """
    close = df["close"]
    middle = close.rolling(window).mean()
    std = close.rolling(window).std()
    return pd.DataFrame({
        "bb_upper":  middle + 2 * std,
        "bb_middle": middle,
        "bb_lower":  middle - 2 * std,
    })


def calc_price_extremes(df):
    """Return a dict with highest/lowest close and largest single-day gain/loss.

    Keys:
    - highest_close : maximum closing price over the stored period
    - lowest_close  : minimum closing price over the stored period
    - largest_gain  : maximum daily return as a decimal (e.g. 0.045 = 4.5%)
    - largest_loss  : minimum daily return as a decimal (e.g. -0.032 = -3.2%)
    """
    daily_returns = calc_daily_returns(df)
    return {
        "highest_close": df["close"].max(),
        "lowest_close":  df["close"].min(),
        "largest_gain":  daily_returns.max(),
        "largest_loss":  daily_returns.min(),
    }


def analyze_ticker(connection, ticker):
    """Load data for ticker and run all technical analysis functions.

    Returns None if no data exists for the ticker.

    Returns a dict with keys:
    ticker, df, daily_returns, moving_averages, ema, volatility,
    rsi, macd, bollinger_bands, price_extremes.
    """
    df = get_stock_data(connection, ticker)
    if df.empty:
        return None

    return {
        "ticker":         ticker,
        "df":             df,
        "daily_returns":  calc_daily_returns(df),
        "moving_averages": calc_moving_averages(df),
        "ema":            calc_ema(df),
        "volatility":     calc_volatility(df),
        "rsi":            calc_rsi(df),
        "macd":           calc_macd(df),
        "bollinger_bands": calc_bollinger_bands(df),
        "price_extremes": calc_price_extremes(df),
    }
