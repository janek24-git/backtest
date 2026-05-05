"""
Episodic Pivot Backtest Engine — 2016–2026
==========================================
Datenquellen:
- yfinance daily OHLCV (10 Jahre, kein API-Limit)
- S&P500-Constituents (aktuelle Liste als Proxy)
- Finnhub earnings history für Katalysator-Check

Entry: Tages-Open + 0.1% Slippage (ORB-Proxy)
Stop:  Tages-Low
Exit:  Nach 20 Handelstagen ODER Stop getroffen
"""

import logging
import os
import httpx
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

logger = logging.getLogger(__name__)

HOLD_DAYS  = 20     # Maximale Haltedauer Handelstage
SLIPPAGE   = 0.001  # 0.1% Slippage auf Entry


def _get_sp500_tickers() -> list[str]:
    """Holt aktuelle S&P500-Ticker von Wikipedia."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        )
        return tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception as e:
        logger.warning("SP500 fetch failed: %s", e)
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
                "JPM", "V", "UNH", "XOM", "MA", "AVGO", "PG", "HD"]


def _fetch_ohlcv(ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
    try:
        df = yf.download(ticker, start=from_date, end=to_date,
                         progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.rename(columns={
            "Open": "open", "High": "high",
            "Low": "low",   "Close": "close", "Volume": "volume"
        })
        df.index = pd.to_datetime(df.index).date
        return df.dropna()
    except Exception:
        return pd.DataFrame()


def _check_finnhub_earnings_history(ticker: str, event_date: date) -> bool:
    """Prüft ob Earnings ±2 Tage um event_date."""
    token = os.environ.get("FINNHUB_API_KEY", "")
    from_d = (event_date - timedelta(days=2)).isoformat()
    to_d   = (event_date + timedelta(days=2)).isoformat()
    try:
        r = httpx.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"symbol": ticker, "from": from_d, "to": to_d, "token": token},
            timeout=8,
        )
        r.raise_for_status()
        return len(r.json().get("earningsCalendar", [])) > 0
    except Exception:
        return False


def _find_gap_events(df: pd.DataFrame, min_gap: float) -> list[dict]:
    """Findet alle Gap-up > min_gap im DataFrame."""
    events = []
    closes = df["close"].values
    opens  = df["open"].values
    dates  = list(df.index)
    for i in range(1, len(df)):
        if closes[i-1] <= 0:
            continue
        gap = (opens[i] - closes[i-1]) / closes[i-1]
        if gap >= min_gap:
            events.append({
                "idx":        i,
                "date":       dates[i],
                "gap_pct":    round(gap * 100, 2),
                "open":       opens[i],
                "low":        df["low"].values[i],
                "prev_close": closes[i-1],
            })
    return events


def _calc_rel_vol(df: pd.DataFrame, idx: int) -> float:
    if idx < 21:
        return 0.0
    vol_today = float(df["volume"].values[idx])
    vol_avg   = float(np.mean(df["volume"].values[idx-20:idx]))
    return round(vol_today / vol_avg, 2) if vol_avg > 0 else 0.0


def _simulate_trade(df: pd.DataFrame, entry_idx: int) -> dict:
    """
    Entry: open[entry_idx] * (1 + SLIPPAGE)
    Stop:  low[entry_idx]
    Exit:  nach HOLD_DAYS oder Stop getroffen

    Logic:
    - Iterate j = 1..HOLD_DAYS
    - If idx >= n (ran out of data): exit at last available close, break
    - If low[idx] <= stop: exit at stop price (stop hit), break
    - If j == HOLD_DAYS: exit at close on that day (time exit), break
    """
    closes = df["close"].values
    lows   = df["low"].values
    dates  = list(df.index)

    entry_price = float(df["open"].values[entry_idx]) * (1 + SLIPPAGE)
    stop_price  = float(lows[entry_idx])
    n = len(df)

    # Defaults — will always be overwritten in the loop
    exit_price = float(closes[n - 1])
    exit_date  = dates[n - 1]
    hit_stop   = False

    for j in range(1, HOLD_DAYS + 1):
        idx = entry_idx + j
        if idx >= n:
            # Ran out of data: exit at last available close
            exit_price = float(closes[n - 1])
            exit_date  = dates[n - 1]
            hit_stop   = False
            break
        if lows[idx] <= stop_price:
            # Stop hit
            exit_price = stop_price
            exit_date  = dates[idx]
            hit_stop   = True
            break
        if j == HOLD_DAYS:
            # Time exit after full hold period
            exit_price = float(closes[idx])
            exit_date  = dates[idx]
            hit_stop   = False

    perf_pct  = round((exit_price - entry_price) / entry_price * 100, 4)
    hold_days = (exit_date - dates[entry_idx]).days

    return {
        "entry_price": round(entry_price, 4),
        "exit_price":  round(exit_price, 4),
        "stop_price":  round(stop_price, 4),
        "exit_date":   str(exit_date),
        "hold_days":   hold_days,
        "perf_pct":    perf_pct,
        "hit_stop":    hit_stop,
    }


def _pead_avg(df: pd.DataFrame, entry_idx: int, days: int) -> float | None:
    closes = df["close"].values
    entry  = float(df["open"].values[entry_idx]) * (1 + SLIPPAGE)
    target_idx = entry_idx + days
    if target_idx >= len(closes):
        return None
    return round((float(closes[target_idx]) - entry) / entry * 100, 4)


def _calc_metrics(trades: list[dict]) -> dict:
    if not trades:
        return {
            "num_trades": 0, "win_rate": 0.0,
            "avg_win": 0.0,  "avg_loss": 0.0,
            "expectancy": 0.0, "sharpe": 0.0,
            "max_drawdown": 0.0, "total_return": 0.0,
            "pead_5d": 0.0, "pead_10d": 0.0, "pead_20d": 0.0, "pead_60d": 0.0,
        }

    returns   = [t["perf_pct"] for t in trades]
    winners   = [r for r in returns if r > 0]
    losers    = [r for r in returns if r <= 0]
    win_rate  = len(winners) / len(returns) * 100
    avg_win   = float(np.mean(winners)) if winners else 0.0
    avg_loss  = float(np.mean(losers))  if losers  else 0.0
    expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)

    arr    = np.array(returns) / 100
    excess = arr - 0.02 / 252
    sharpe = float(np.sqrt(252) * excess.mean() / excess.std()) if len(excess) > 1 and excess.std() > 0 else 0.0

    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = max(max_dd, (peak - v) / peak * 100)

    pead5  = [t.get("pead_5d")  for t in trades if t.get("pead_5d")  is not None]
    pead10 = [t.get("pead_10d") for t in trades if t.get("pead_10d") is not None]
    pead20 = [t.get("pead_20d") for t in trades if t.get("pead_20d") is not None]
    pead60 = [t.get("pead_60d") for t in trades if t.get("pead_60d") is not None]

    return {
        "num_trades":    len(trades),
        "win_rate":      round(win_rate, 2),
        "avg_win":       round(avg_win, 4),
        "avg_loss":      round(avg_loss, 4),
        "expectancy":    round(expectancy, 4),
        "sharpe":        round(sharpe, 4),
        "max_drawdown":  round(-max_dd, 4),
        "total_return":  round(sum(returns), 4),
        "pead_5d":       round(float(np.mean(pead5)),  4) if pead5  else 0.0,
        "pead_10d":      round(float(np.mean(pead10)), 4) if pead10 else 0.0,
        "pead_20d":      round(float(np.mean(pead20)), 4) if pead20 else 0.0,
        "pead_60d":      round(float(np.mean(pead60)), 4) if pead60 else 0.0,
    }


def run_ep_backtest(
    from_date: str = "2016-01-01",
    to_date: str   = "2026-01-01",
    min_gap_pct: float = 0.10,
    min_rel_vol: float = 2.0,
    require_earnings: bool = False,
    max_tickers: int = 100,
) -> dict:
    tickers = _get_sp500_tickers()[:max_tickers]
    all_trades: list[dict] = []

    for ticker in tickers:
        df = _fetch_ohlcv(ticker, from_date, to_date)
        if df.empty or len(df) < 25:
            continue

        # min_gap_pct comes in as decimal (0.10) from EPBacktestRequest default
        gap_threshold = min_gap_pct if min_gap_pct < 1 else min_gap_pct / 100
        events = _find_gap_events(df, gap_threshold)

        for ev in events:
            idx = ev["idx"]
            rel_vol = _calc_rel_vol(df, idx)
            if rel_vol < min_rel_vol:
                continue

            catalyst = "Unknown"
            if require_earnings:
                has_earnings = _check_finnhub_earnings_history(ticker, ev["date"])
                if not has_earnings:
                    continue
                catalyst = "Earnings"

            trade = _simulate_trade(df, idx)
            trade.update({
                "ticker":     ticker,
                "entry_date": str(ev["date"]),
                "gap_pct":    ev["gap_pct"],
                "rel_vol":    rel_vol,
                "catalyst":   catalyst,
                "pead_5d":    _pead_avg(df, idx, 5),
                "pead_10d":   _pead_avg(df, idx, 10),
                "pead_20d":   _pead_avg(df, idx, 20),
                "pead_60d":   _pead_avg(df, idx, 60),
            })
            all_trades.append(trade)

        logger.info("EP backtest %s: %d gap events", ticker, len(events))

    metrics = _calc_metrics(all_trades)
    return {
        "trades":    all_trades,
        "metrics":   metrics,
        "from_date": from_date,
        "to_date":   to_date,
    }
