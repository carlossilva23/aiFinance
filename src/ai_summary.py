"""
File: ai_summary.py

Purpose: Sends calculated stock metrics to a local Ollama LLM and returns
a plain-English comparative summary. The LLM only receives data that Python
has already computed — it is never asked to recall or invent financial facts.
"""
import ollama

MODEL = "qwen2.5:7b"


def build_prompt(all_results):
    """Format a list of analyze_ticker() result dicts into a structured prompt.

    Each ticker's key metrics are written out explicitly so the LLM has
    nothing to infer or fabricate. The instruction explicitly forbids the
    model from referencing anything outside the provided data.
    """
    lines = [
        "You are a financial analyst assistant.",
        "Summarize the following stock data in plain English.",
        "Only reference the numbers provided below — do not add any external "
        "knowledge, predictions, or information not present in this data.",
        "",
    ]

    for results in all_results:
        ticker = results["ticker"]
        df = results["df"]
        pe = results["price_extremes"]
        ma = results["moving_averages"]

        last_close   = df["close"].iloc[-1]
        start_price  = df["close"].iloc[0]
        end_price    = last_close
        pct_return   = ((end_price - start_price) / start_price) * 100
        date_start   = df["date"].iloc[0]
        date_end     = df["date"].iloc[-1]
        volatility   = results["volatility"].dropna().iloc[-1]
        rsi          = results["rsi"].dropna().iloc[-1]
        macd_val     = results["macd"]["macd"].dropna().iloc[-1]
        signal_val   = results["macd"]["signal"].dropna().iloc[-1]
        sma50        = ma["sma_50"].dropna().iloc[-1]
        bb_upper     = results["bollinger_bands"]["bb_upper"].dropna().iloc[-1]
        bb_lower     = results["bollinger_bands"]["bb_lower"].dropna().iloc[-1]

        rsi_signal   = "Overbought" if rsi > 70 else ("Oversold" if rsi < 30 else "Neutral")
        macd_signal  = "Bullish crossover" if macd_val > signal_val else "Bearish crossover"
        sma50_signal = "Above SMA 50 (bullish)" if last_close >= sma50 else "Below SMA 50 (bearish)"
        bb_signal    = (
            "Near overbought (above upper band)" if last_close > bb_upper
            else "Near oversold (below lower band)" if last_close < bb_lower
            else "Within normal range"
        )

        lines += [
            f"--- {ticker} ({date_start} to {date_end}) ---",
            f"  Starting Price:      ${start_price:.2f}",
            f"  Ending Price:        ${end_price:.2f}",
            f"  Percent Return:      {pct_return:.2f}%",
            f"  Volatility (20d):    {volatility:.4f}",
            f"  Highest Close:       ${pe['highest_close']:.2f}",
            f"  Lowest Close:        ${pe['lowest_close']:.2f}",
            f"  Largest 1-Day Gain:  {pe['largest_gain'] * 100:.2f}%",
            f"  Largest 1-Day Loss:  {pe['largest_loss'] * 100:.2f}%",
            f"  RSI (14):            {rsi:.2f} — {rsi_signal}",
            f"  MACD:                {macd_signal}",
            f"  Price vs SMA 50:     {sma50_signal}",
            f"  Bollinger Bands:     {bb_signal}",
            "",
        ]

    lines += [
        "Based only on the data above, write a 4-6 sentence plain-English summary.",
        "If multiple stocks are provided, compare them.",
        "Highlight which stock performed better, note any momentum or risk signals, "
        "and flag anything that stands out. Do not speculate beyond the data.",
    ]

    return "\n".join(lines)


def get_summary(prompt, model=MODEL):
    """Send the prompt to the local Ollama model and return the response text."""
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]
