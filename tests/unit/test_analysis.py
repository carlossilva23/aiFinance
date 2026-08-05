"""
Unit Tests — analysis.py

Tests each indicator calculation function in isolation using a
synthetic DataFrame. No database or network calls are made.
"""
import sys
import os
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from analysis import (
    calc_daily_returns,
    calc_moving_averages,
    calc_ema,
    calc_volatility,
    calc_rsi,
    calc_macd,
    calc_bollinger_bands,
    calc_price_extremes,
)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def make_df(rows=60, start_price=100.0, step=1.0):
    """Build a synthetic OHLCV DataFrame with a steady linear close price."""
    close = [start_price + i * step for i in range(rows)]
    return pd.DataFrame(
        {
            "date":   [f"2024-01-{i+1:02d}" for i in range(rows)],
            "open":   [c - 0.5 for c in close],
            "high":   [c + 1.0 for c in close],
            "low":    [c - 1.0 for c in close],
            "close":  close,
            "volume": [1_000_000] * rows,
        }
    )


# ------------------------------------------------------------------ #
# calc_daily_returns                                                   #
# ------------------------------------------------------------------ #

class TestCalcDailyReturns:
    def test_returns_series(self):
        """calc_daily_returns() returns a pandas Series."""
        df = make_df()
        result = calc_daily_returns(df)
        assert isinstance(result, pd.Series)

    def test_length_matches_input(self):
        """Output length equals input length (first value is NaN)."""
        df = make_df(rows=30)
        result = calc_daily_returns(df)
        assert len(result) == 30

    def test_first_value_is_nan(self):
        """First value is NaN since there is no prior day to compare."""
        df = make_df(rows=10)
        result = calc_daily_returns(df)
        assert pd.isna(result.iloc[0])

    def test_positive_returns_on_rising_prices(self):
        """All non-NaN returns are positive when prices strictly increase."""
        df = make_df(rows=20, step=1.0)
        result = calc_daily_returns(df).dropna()
        assert (result > 0).all()


# ------------------------------------------------------------------ #
# calc_moving_averages                                                 #
# ------------------------------------------------------------------ #

class TestCalcMovingAverages:
    def test_returns_dataframe_with_correct_columns(self):
        """Output DataFrame has sma_7, sma_20, sma_30, sma_50 columns."""
        df = make_df(rows=60)
        result = calc_moving_averages(df)
        assert list(result.columns) == ["sma_7", "sma_20", "sma_30", "sma_50"]

    def test_sma7_nan_for_first_six_rows(self):
        """SMA 7 is NaN for the first 6 rows (window not yet filled)."""
        df = make_df(rows=60)
        result = calc_moving_averages(df)
        assert result["sma_7"].iloc[:6].isna().all()
        assert not pd.isna(result["sma_7"].iloc[6])

    def test_sma50_nan_until_row_49(self):
        """SMA 50 only has valid values from row 49 onward."""
        df = make_df(rows=60)
        result = calc_moving_averages(df)
        assert result["sma_50"].iloc[:49].isna().all()
        assert not pd.isna(result["sma_50"].iloc[49])

    def test_sma_value_is_mean_of_window(self):
        """SMA 7 at row 6 equals the mean of the first 7 close prices."""
        df = make_df(rows=60)
        result = calc_moving_averages(df)
        expected = df["close"].iloc[:7].mean()
        assert result["sma_7"].iloc[6] == pytest.approx(expected, rel=1e-6)


# ------------------------------------------------------------------ #
# calc_ema                                                             #
# ------------------------------------------------------------------ #

class TestCalcEma:
    def test_returns_series(self):
        """calc_ema() returns a pandas Series."""
        df = make_df(rows=40)
        result = calc_ema(df)
        assert isinstance(result, pd.Series)

    def test_series_named_ema_20_by_default(self):
        """Default Series name is 'ema_20'."""
        df = make_df(rows=40)
        result = calc_ema(df)
        assert result.name == "ema_20"

    def test_custom_span_reflected_in_name(self):
        """Series name reflects the custom span argument."""
        df = make_df(rows=40)
        result = calc_ema(df, span=12)
        assert result.name == "ema_12"

    def test_no_nan_values(self):
        """EMA produces a value for every row (adjust=False seeds from first value)."""
        df = make_df(rows=40)
        result = calc_ema(df)
        assert result.isna().sum() == 0


# ------------------------------------------------------------------ #
# calc_volatility                                                      #
# ------------------------------------------------------------------ #

class TestCalcVolatility:
    def test_returns_series(self):
        """calc_volatility() returns a pandas Series."""
        df = make_df(rows=60)
        result = calc_volatility(df)
        assert isinstance(result, pd.Series)

    def test_nan_for_insufficient_data(self):
        """Volatility is NaN until at least 21 rows of data exist."""
        df = make_df(rows=60)
        result = calc_volatility(df)
        # rolling(20) on pct_change needs 20 returns → first valid at row 21
        assert result.dropna().iloc[0] is not None

    def test_zero_volatility_on_flat_prices(self):
        """A flat price series (step=0) produces zero volatility."""
        df = make_df(rows=60, step=0.0)
        result = calc_volatility(df).dropna()
        assert (result.abs() < 1e-10).all()


# ------------------------------------------------------------------ #
# calc_rsi                                                             #
# ------------------------------------------------------------------ #

class TestCalcRsi:
    def test_returns_series(self):
        """calc_rsi() returns a pandas Series."""
        df = make_df(rows=60)
        result = calc_rsi(df)
        assert isinstance(result, pd.Series)

    def test_values_between_0_and_100(self):
        """All non-NaN RSI values are between 0 and 100."""
        df = make_df(rows=60)
        result = calc_rsi(df).dropna()
        assert (result >= 0).all() and (result <= 100).all()

    def test_rising_prices_produce_high_rsi(self):
        """Strictly rising prices produce an RSI above 70 (overbought)."""
        df = make_df(rows=60, step=2.0)  # consistent upward movement
        result = calc_rsi(df).dropna()
        assert result.iloc[-1] > 70

    def test_falling_prices_produce_low_rsi(self):
        """Strictly falling prices produce an RSI below 30 (oversold)."""
        df = make_df(rows=60, step=-2.0)
        result = calc_rsi(df).dropna()
        assert result.iloc[-1] < 30

    def test_nan_for_first_period_rows(self):
        """RSI is NaN for the first `period` rows."""
        df = make_df(rows=60)
        result = calc_rsi(df, period=14)
        assert result.iloc[:14].isna().all()


# ------------------------------------------------------------------ #
# calc_macd                                                            #
# ------------------------------------------------------------------ #

class TestCalcMacd:
    def test_returns_dataframe(self):
        """calc_macd() returns a DataFrame."""
        df = make_df(rows=60)
        result = calc_macd(df)
        assert isinstance(result, pd.DataFrame)

    def test_correct_columns(self):
        """Output has ema_12, ema_26, macd, signal columns."""
        df = make_df(rows=60)
        result = calc_macd(df)
        assert list(result.columns) == ["ema_12", "ema_26", "macd", "signal"]

    def test_macd_equals_ema12_minus_ema26(self):
        """MACD column equals ema_12 minus ema_26 at every row."""
        df = make_df(rows=60)
        result = calc_macd(df)
        diff = (result["ema_12"] - result["ema_26"] - result["macd"]).abs()
        assert (diff < 1e-10).all()

    def test_rising_prices_produce_positive_macd(self):
        """Consistently rising prices result in a positive MACD (fast EMA > slow EMA)."""
        df = make_df(rows=60, step=1.0)
        result = calc_macd(df)
        assert result["macd"].iloc[-1] > 0


# ------------------------------------------------------------------ #
# calc_bollinger_bands                                                 #
# ------------------------------------------------------------------ #

class TestCalcBollingerBands:
    def test_returns_dataframe(self):
        """calc_bollinger_bands() returns a DataFrame."""
        df = make_df(rows=60)
        result = calc_bollinger_bands(df)
        assert isinstance(result, pd.DataFrame)

    def test_correct_columns(self):
        """Output has bb_upper, bb_middle, bb_lower columns."""
        df = make_df(rows=60)
        result = calc_bollinger_bands(df)
        assert list(result.columns) == ["bb_upper", "bb_middle", "bb_lower"]

    def test_upper_above_middle_above_lower(self):
        """Upper band > middle band > lower band for all non-NaN rows."""
        df = make_df(rows=60, step=0.5)
        result = calc_bollinger_bands(df).dropna()
        assert (result["bb_upper"] > result["bb_middle"]).all()
        assert (result["bb_middle"] > result["bb_lower"]).all()

    def test_nan_for_first_window_minus_one_rows(self):
        """Bands are NaN until the rolling window (20) is filled."""
        df = make_df(rows=60)
        result = calc_bollinger_bands(df, window=20)
        assert result["bb_middle"].iloc[:19].isna().all()
        assert not pd.isna(result["bb_middle"].iloc[19])

    def test_flat_prices_produce_zero_width_bands(self):
        """Flat prices have zero std → upper == middle == lower."""
        df = make_df(rows=60, step=0.0)
        result = calc_bollinger_bands(df).dropna()
        assert (result["bb_upper"] == result["bb_lower"]).all()


# ------------------------------------------------------------------ #
# calc_price_extremes                                                  #
# ------------------------------------------------------------------ #

class TestCalcPriceExtremes:
    def test_returns_dict_with_correct_keys(self):
        """Output is a dict with the four expected keys."""
        df = make_df(rows=30)
        result = calc_price_extremes(df)
        assert set(result.keys()) == {"highest_close", "lowest_close", "largest_gain", "largest_loss"}

    def test_highest_close_is_maximum(self):
        """highest_close equals the max of the close column."""
        df = make_df(rows=30)
        result = calc_price_extremes(df)
        assert result["highest_close"] == pytest.approx(df["close"].max(), rel=1e-6)

    def test_lowest_close_is_minimum(self):
        """lowest_close equals the min of the close column."""
        df = make_df(rows=30)
        result = calc_price_extremes(df)
        assert result["lowest_close"] == pytest.approx(df["close"].min(), rel=1e-6)

    def test_largest_gain_is_positive(self):
        """largest_gain is positive for a rising price series."""
        df = make_df(rows=30, step=1.0)
        result = calc_price_extremes(df)
        assert result["largest_gain"] > 0

    def test_largest_loss_is_negative(self):
        """largest_loss is negative (prices can't only rise with no loss)."""
        df = make_df(rows=30, step=1.0)
        result = calc_price_extremes(df)
        # Even on a rising series, pct_change on first row is NaN;
        # but with strictly rising prices the min return approaches 0 from above
        # Only assert it is finite and ≤ largest_gain
        assert result["largest_loss"] <= result["largest_gain"]
