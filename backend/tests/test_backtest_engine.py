import pandas as pd
import numpy as np
import pytest
from app.services.backtest_engine import calculate_ema, generate_signals, extract_trades

def make_df(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=len(closes), freq="B")
    opens = [c * 0.999 for c in closes]
    return pd.DataFrame({"open": opens, "close": closes}, index=dates)


def test_ema_length_matches_input():
    df = make_df([100.0] * 250)
    ema = calculate_ema(df["close"], period=200)
    assert len(ema) == 250


def test_ema_constant_series_equals_constant():
    df = make_df([100.0] * 300)
    ema = calculate_ema(df["close"], period=200)
    assert abs(ema.iloc[-1] - 100.0) < 0.01


def test_generate_signals_columns():
    df = make_df([100.0] * 300)
    result = generate_signals(df.copy())
    assert "ema200" in result.columns
    assert "signal" in result.columns


def test_signal_long_when_close_above_ema():
    closes = [90.0] * 200 + [110.0] * 50
    df = make_df(closes)
    result = generate_signals(df.copy())
    assert result["signal"].iloc[-1] == 1


def test_signal_flat_when_close_below_ema():
    closes = [110.0] * 200 + [90.0] * 50
    df = make_df(closes)
    result = generate_signals(df.copy())
    assert result["signal"].iloc[-1] == 0


def test_extract_trades_returns_list():
    closes = [90.0] * 200 + [110.0] * 50 + [90.0] * 50
    df = make_df(closes)
    df_signals = generate_signals(df.copy())
    trades = extract_trades(df_signals)
    assert isinstance(trades, list)
    assert len(trades) >= 1


def test_trade_has_required_keys():
    closes = [90.0] * 200 + [110.0] * 50 + [90.0] * 50
    df = make_df(closes)
    df_signals = generate_signals(df.copy())
    trades = extract_trades(df_signals)
    trade = trades[0]
    for key in ["entry_date", "exit_date", "entry_price", "exit_price", "return_pct", "hold_days"]:
        assert key in trade, f"Missing key: {key}"


def test_metrics_keys():
    from app.services.backtest_engine import calculate_metrics
    trades = [
        {"return_pct": 10.0, "hold_days": 20, "entry_date": "2021-01-01",
         "exit_date": "2021-01-21", "entry_price": 100, "exit_price": 110},
        {"return_pct": -5.0, "hold_days": 10, "entry_date": "2021-02-01",
         "exit_date": "2021-02-11", "entry_price": 110, "exit_price": 104.5},
    ]
    metrics = calculate_metrics(trades)
    for key in ["win_rate", "total_return", "max_drawdown", "sharpe_ratio",
                "num_trades", "avg_hold_days", "best_trade", "worst_trade"]:
        assert key in metrics, f"Missing metric: {key}"


def test_win_rate_calculation():
    from app.services.backtest_engine import calculate_metrics
    trades = [
        {"return_pct": 10.0, "hold_days": 5, "entry_date": "2021-01-01",
         "exit_date": "2021-01-06", "entry_price": 100, "exit_price": 110},
        {"return_pct": -5.0, "hold_days": 5, "entry_date": "2021-02-01",
         "exit_date": "2021-02-06", "entry_price": 100, "exit_price": 95},
        {"return_pct": 8.0, "hold_days": 5, "entry_date": "2021-03-01",
         "exit_date": "2021-03-06", "entry_price": 100, "exit_price": 108},
    ]
    metrics = calculate_metrics(trades)
    assert abs(metrics["win_rate"] - 66.67) < 0.1


def test_empty_trades_returns_none():
    from app.services.backtest_engine import calculate_metrics
    metrics = calculate_metrics([])
    assert metrics is None


def test_run_backtest_returns_result():
    from app.services.backtest_engine import run_backtest
    closes = [90.0] * 210 + [110.0] * 60 + [90.0] * 60
    opens = [c * 0.999 for c in closes]
    dates = pd.date_range("2020-01-01", periods=len(closes), freq="B")
    df = pd.DataFrame({"open": opens, "close": closes}, index=dates)
    result = run_backtest(df, ema_period=200)
    assert "trades" in result
    assert "metrics" in result
    assert "signals" in result
