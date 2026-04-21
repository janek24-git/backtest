"""
Big 5 Swing Backtest Engine
===========================
Implements 8 combinations: ACE, ACF, ADE, ADF, BCE, BCF, BDE, BDF

Entry modes:
  A: buy on first close > EMA/SMA AFTER company entered top5 (any subsequent day)
  B: buy ONLY on the specific day eligibility is gained, IF close > EMA/SMA

Exit modes:
  C: if company leaves top5, keep holding until close < EMA/SMA
  D: if company leaves top5, sell on next trading day regardless of EMA/SMA

Top5 filter:
  E: 1 day in top5 triggers eligibility
  F: 5 consecutive days in top5 required

Signal timing:
  - Signal detected at day D close
  - Execution at day D+1 open (= 9:30 ET ≈ 9:00 MESZ per spec)
  - Holiday handling: yfinance data already excludes non-trading days
"""

import logging
import pandas as pd
import numpy as np
from datetime import date

logger = logging.getLogger(__name__)

COMBINATIONS = ["ACE", "ACF", "ADE", "ADF", "BCE", "BCF", "BDE", "BDF"]
FILTER_DAYS = {"E": 1, "F": 5}


def _calc_indicator(closes: pd.Series, indicator: str, period: int) -> pd.Series:
    if indicator == "SMA":
        return closes.rolling(window=period, min_periods=period).mean()
    # TradingView-compatible EMA: seed with SMA of first `period` bars
    k = 2.0 / (period + 1)
    result = np.full(len(closes), np.nan)
    vals = closes.values
    # find first index where we have enough data for SMA seed
    if len(vals) < period:
        return pd.Series(result, index=closes.index)
    result[period - 1] = vals[:period].mean()
    for i in range(period, len(vals)):
        result[i] = vals[i] * k + result[i - 1] * (1 - k)
    return pd.Series(result, index=closes.index)


def _run_one_combination(
    price_data: dict[str, pd.DataFrame],
    top5_history: dict,
    entry_mode: str,  # "A" or "B"
    exit_mode: str,   # "C" or "D"
    filter_mode: str, # "E" or "F"
    indicator: str,
    period: int,
) -> list[dict]:
    """Run backtest for one combination. Returns list of trade dicts."""

    required_days = FILTER_DAYS[filter_mode]

    # Prepare price + indicator for each candidate
    dfs: dict[str, pd.DataFrame] = {}
    for ticker, df in price_data.items():
        d = df[["open", "close"]].copy()
        d.index = pd.to_datetime(d.index)
        d = d.sort_index()
        d.loc[:, "ind"] = _calc_indicator(d["close"], indicator, period)
        d.loc[:, "signal"] = (d["close"] > d["ind"]).astype(int)
        dfs[ticker] = d

    # Pre-compute per-ticker index maps for O(1) row lookup
    idx_maps: dict[str, dict] = {
        t: {dt: i for i, dt in enumerate(df.index)}
        for t, df in dfs.items()
    }

    # Build unified trading day index
    all_dates = sorted(set().union(*[set(df.index) for df in dfs.values()]))

    # Per-ticker state
    state: dict[str, dict] = {t: {
        "consecutive": 0,       # consecutive days in top5
        "eligible": False,       # eligible for entry
        "just_eligible": False,  # became eligible today (for B mode)
        "pending_buy": False,
        "pending_sell": False,
        "in_position": False,
        "entry_price": None,
        "entry_date": None,      # execution date
        "entry_idx": None,       # row index for hold-duration counting
    } for t in dfs}

    trades: list[dict] = []
    nr = 0          # sequential trade counter
    kum_perf = 0.0  # cumulative performance (simple sum of closed trades)

    def next_trading_day_open(ticker: str, current_idx: int) -> tuple[str, float] | None:
        """Returns (date_str, open_price) for the next trading day."""
        df = dfs[ticker]
        dates = list(df.index)
        if current_idx + 1 >= len(dates):
            return None
        next_date = dates[current_idx + 1]
        next_open = df.iloc[current_idx + 1]["open"]
        if pd.isna(next_open):
            return None
        return str(next_date.date()), float(next_open)

    def get_row_idx(ticker: str, dt) -> int | None:
        df = dfs[ticker]
        dates = list(df.index)
        try:
            return dates.index(dt)
        except ValueError:
            return None

    for dt in all_dates:
        today_str = str(dt.date())
        top5_today = top5_history.get(dt.date(), [])

        for ticker in list(dfs.keys()):
            df = dfs[ticker]
            if dt not in idx_maps[ticker]:
                continue

            row_idx = idx_maps[ticker][dt]
            row = df.iloc[row_idx]

            if pd.isna(row["close"]) or pd.isna(row["ind"]):
                continue

            s = state[ticker]
            close = float(row["close"])
            ind_val = float(row["ind"])
            in_top5 = ticker in top5_today

            # ── 1. Execute pending orders at today's open ──────────────────
            if s["pending_buy"] and not s["in_position"]:
                open_price = float(row["open"])
                if not pd.isna(open_price):
                    nr += 1
                    trades.append({
                        "nr": nr,
                        "typ": "KAUF",
                        "ticker": ticker,
                        "datum": today_str,
                        "haltdauer": 0,
                        "open_preis": round(open_price, 4),
                        "perf_pct": 0.0,
                        "kum_perf_pct": round(kum_perf, 4),
                    })
                    s["in_position"] = True
                    s["entry_price"] = open_price
                    s["entry_date"] = today_str
                    s["entry_idx"] = row_idx
                s["pending_buy"] = False

            if s["pending_sell"] and s["in_position"]:
                open_price = float(row["open"])
                if not pd.isna(open_price) and s["entry_price"] is not None:
                    perf = (open_price - s["entry_price"]) / s["entry_price"] * 100
                    kum_perf += perf
                    hold_days = row_idx - s["entry_idx"] if s["entry_idx"] is not None else 0
                    nr += 1
                    trades.append({
                        "nr": nr,
                        "typ": "VERKAUF",
                        "ticker": ticker,
                        "datum": today_str,
                        "haltdauer": hold_days,
                        "open_preis": round(open_price, 4),
                        "perf_pct": round(perf, 4),
                        "kum_perf_pct": round(kum_perf, 4),
                    })
                    s["in_position"] = False
                    s["entry_price"] = None
                    s["entry_date"] = None
                    s["entry_idx"] = None
                s["pending_sell"] = False

            # ── 2. Update top5 membership and eligibility ──────────────────
            was_eligible = s["eligible"]
            s["just_eligible"] = False

            if in_top5:
                s["consecutive"] += 1
            else:
                s["consecutive"] = 0
                if not s["in_position"]:
                    s["eligible"] = False

            # Determine new eligibility
            if s["consecutive"] >= required_days and not s["eligible"]:
                s["eligible"] = True
                s["just_eligible"] = True  # transition day

            # ── 3. Generate signals for TOMORROW ──────────────────────────
            above_ind = close > ind_val

            # EXIT signal
            if s["in_position"] and not s["pending_sell"]:
                ema_exit = not above_ind  # close < EMA/SMA
                top5_exit = (exit_mode == "D") and not in_top5
                if ema_exit or top5_exit:
                    s["pending_sell"] = True

            # ENTRY signal
            if not s["in_position"] and not s["pending_buy"] and s["eligible"]:
                if entry_mode == "A":
                    # Any day while eligible and close > EMA
                    if above_ind:
                        s["pending_buy"] = True
                elif entry_mode == "B":
                    # Only on the day eligibility is gained
                    if s["just_eligible"] and above_ind:
                        s["pending_buy"] = True

    # ── 4. Close open positions at end of period ──────────────────────────
    for ticker, s in state.items():
        if s["in_position"] and s["entry_price"] is not None:
            df = dfs[ticker]
            if df.empty:
                continue
            last_row = df.iloc[-1]
            exit_price = float(last_row["close"])
            perf = (exit_price - s["entry_price"]) / s["entry_price"] * 100
            kum_perf += perf
            hold_days = len(df) - 1 - (s["entry_idx"] or 0)
            nr += 1
            trades.append({
                "nr": nr,
                "typ": "VERKAUF",
                "ticker": ticker,
                "datum": str(last_row.name.date()),
                "haltdauer": hold_days,
                "open_preis": round(exit_price, 4),
                "perf_pct": round(perf, 4),
                "kum_perf_pct": round(kum_perf, 4),
            })

    # Sort by execution date, then nr
    trades.sort(key=lambda t: (t["datum"], t["nr"]))
    return trades


def _calc_metrics(trades: list[dict]) -> dict:
    sells = [t for t in trades if t["typ"] == "VERKAUF"]
    if not sells:
        return {"num_trades": 0, "win_rate": 0.0, "total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}

    returns = [t["perf_pct"] for t in sells]
    winners = [r for r in returns if r > 0]
    win_rate = len(winners) / len(returns) * 100
    total_return = sum(returns)

    # Sharpe (annualized, risk-free 2%)
    arr = np.array(returns) / 100
    excess = arr - 0.02 / 252
    sharpe = 0.0
    if len(excess) > 1 and excess.std() > 0:
        sharpe = float(np.sqrt(252) * excess.mean() / excess.std())

    # Max drawdown on equity curve
    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        dd = (peak - v) / peak * 100
        max_dd = max(max_dd, dd)

    return {
        "num_trades": len(sells),
        "win_rate": round(win_rate, 2),
        "total_return": round(total_return, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(-max_dd, 4),
    }


def run_all_combinations(
    price_data: dict[str, pd.DataFrame],
    top5_history: dict,
    indicator: str = "EMA",
    period: int = 200,
) -> list[dict]:
    """Run all 8 combinations and return list of results."""
    results = []
    for combo in COMBINATIONS:
        entry_mode = combo[0]   # A or B
        exit_mode = combo[1]    # C or D
        filter_mode = combo[2]  # E or F
        logger.info("Running combination %s ...", combo)
        try:
            trades = _run_one_combination(
                price_data, top5_history,
                entry_mode, exit_mode, filter_mode,
                indicator, period,
            )
            metrics = _calc_metrics(trades)
            results.append({
                "kombination": combo,
                "trades": trades,
                "metrics": metrics,
            })
        except Exception as e:
            logger.error("Combination %s failed: %s", combo, e)
            results.append({
                "kombination": combo,
                "trades": [],
                "metrics": {"num_trades": 0, "win_rate": 0.0, "total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0},
            })
    return results
