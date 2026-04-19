import pandas as pd
import numpy as np
from datetime import date


def calculate_ema(prices: pd.Series, period: int = 200) -> pd.Series:
    return prices.ewm(span=period, adjust=False).mean()


def generate_signals(df: pd.DataFrame, ema_period: int = 200) -> pd.DataFrame:
    df = df.copy()
    df["ema200"] = calculate_ema(df["close"], period=ema_period)
    df["signal"] = (df["close"] > df["ema200"]).astype(int)
    return df


def extract_trades(df: pd.DataFrame) -> list[dict]:
    trades = []
    in_trade = False
    entry_date = None
    entry_price = None

    for i in range(1, len(df)):
        prev_signal = df["signal"].iloc[i - 1]
        curr_open = df["open"].iloc[i]
        curr_date = df.index[i]

        if prev_signal == 1 and not in_trade:
            in_trade = True
            entry_date = curr_date
            entry_price = curr_open

        elif prev_signal == 0 and in_trade:
            exit_price = curr_open
            return_pct = (exit_price - entry_price) / entry_price * 100
            hold_days = (curr_date - entry_date).days
            trades.append({
                "entry_date": entry_date.date().isoformat(),
                "exit_date": curr_date.date().isoformat(),
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "return_pct": round(return_pct, 4),
                "hold_days": hold_days,
            })
            in_trade = False

    return trades
