import pandas as pd
import numpy as np
from datetime import date


def calculate_ema(prices: pd.Series, period: int = 200) -> pd.Series:
    # TradingView-compatible EMA: seed with SMA of first `period` bars
    k = 2.0 / (period + 1)
    vals = prices.values
    result = np.full(len(vals), np.nan)
    if len(vals) < period:
        return pd.Series(result, index=prices.index)
    result[period - 1] = vals[:period].mean()
    for i in range(period, len(vals)):
        result[i] = vals[i] * k + result[i - 1] * (1 - k)
    return pd.Series(result, index=prices.index)


def generate_signals(df: pd.DataFrame, ema_period: int = 200) -> pd.DataFrame:
    df = df.copy()
    df.loc[:, "ema200"] = calculate_ema(df["close"], period=ema_period)
    df.loc[:, "signal"] = (df["close"] > df["ema200"]).astype(int)
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
                "entry_date": entry_date.isoformat() if isinstance(entry_date, date) else entry_date.date().isoformat(),
                "exit_date": curr_date.isoformat() if isinstance(curr_date, date) else curr_date.date().isoformat(),
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "return_pct": round(return_pct, 4),
                "hold_days": hold_days,
            })
            in_trade = False

    return trades


def calculate_metrics(trades: list[dict]) -> dict | None:
    if not trades:
        return None

    returns = [t["return_pct"] for t in trades]
    winning = [r for r in returns if r > 0]

    win_rate = round(len(winning) / len(trades) * 100, 2)
    total_return = round(sum(returns), 4)
    best_trade = round(max(returns), 4)
    worst_trade = round(min(returns), 4)
    avg_hold_days = round(sum(t["hold_days"] for t in trades) / len(trades), 1)

    # Max drawdown on equity curve
    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))
    peak = equity[0]
    max_dd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd
    max_drawdown = round(-max_dd, 4)

    # Sharpe ratio (annualised, risk-free = 2%)
    returns_arr = np.array(returns) / 100
    excess = returns_arr - 0.02 / 252
    sharpe = 0.0
    if len(excess) > 1 and excess.std() > 0:
        sharpe = round(float(np.sqrt(252) * excess.mean() / excess.std()), 4)

    return {
        "win_rate": win_rate,
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe,
        "num_trades": len(trades),
        "avg_hold_days": avg_hold_days,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
    }


def run_backtest(df: pd.DataFrame, ema_period: int = 200, from_date=None) -> dict:
    # Calculate EMA on full history for TradingView-compatible values
    df_signals = generate_signals(df, ema_period=ema_period)

    # Filter to requested date range AFTER EMA calculation
    if from_date is not None:
        df_signals = df_signals[df_signals.index >= from_date]

    trades = extract_trades(df_signals)
    metrics = calculate_metrics(trades)

    signals_out = df_signals[["open", "close", "ema200", "signal"]].copy()
    signals_out = signals_out.dropna(subset=["ema200"])
    signals_out.index = [d.isoformat() if isinstance(d, date) else d.strftime("%Y-%m-%d") for d in signals_out.index]

    return {
        "trades": trades,
        "metrics": metrics,
        "signals": signals_out.reset_index().rename(columns={"index": "date"}).to_dict(orient="records"),
    }
