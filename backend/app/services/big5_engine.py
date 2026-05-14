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

COMBINATIONS = ["ACE", "ACF", "ADE", "ADF", "BCE", "BCF", "BDE", "BDF", "KCE", "KCF", "KDE", "KDF"]
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
    entry_threshold: float = 0.0,   # 0.005 = 0.5% buffer above EMA for entry
    min_hold_days: int = 0,          # minimum trading days before exit allowed
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
        "needs_reset": False,    # A-mode: entered top5 already above EMA → must dip below first
        "pending_buy": False,
        "pending_sell": False,
        "in_position": False,
        "entry_price": None,
        "entry_date": None,      # execution date
        "entry_idx": None,       # row index for hold-duration counting
    } for t in dfs}

    trades: list[dict] = []
    nr = 0           # sequential trade counter
    SLOT_START = 1000.0                              # €1.000 per slot
    slot_equity: dict[str, float] = {}              # per-ticker capital (initialised on first buy)

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
                    if ticker not in slot_equity:
                        slot_equity[ticker] = SLOT_START   # fresh slot: €1.000
                    nr += 1
                    trades.append({
                        "nr": nr,
                        "typ": "KAUF",
                        "ticker": ticker,
                        "datum": today_str,
                        "haltdauer": 0,
                        "open_preis": round(open_price, 4),
                        "perf_pct": 0.0,
                        "kum_perf_pct": round((slot_equity[ticker] / SLOT_START - 1) * 100, 4),
                        "kapital_eur": round(slot_equity[ticker], 2),
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
                    if ticker not in slot_equity:
                        slot_equity[ticker] = SLOT_START
                    slot_equity[ticker] *= (1 + perf / 100)
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
                        "kum_perf_pct": round((slot_equity[ticker] / SLOT_START - 1) * 100, 4),
                        "kapital_eur": round(slot_equity[ticker], 2),
                    })
                    s["in_position"] = False
                    s["entry_price"] = None
                    s["entry_date"] = None
                    s["entry_idx"] = None
                    s["needs_reset"] = False
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
            above_ind = close > ind_val                                        # for exit + reset detection
            above_ind_entry = close > ind_val * (1 + entry_threshold)         # threshold buffer for entry

            # A-mode reset logic: if stock entered top5 already above EMA,
            # it needs to dip below EMA first before a fresh crossover triggers entry
            if entry_mode == "A" and s["eligible"] and not s["in_position"]:
                if s["just_eligible"] and above_ind:
                    # Entered top5 while already above EMA → must reset first
                    s["needs_reset"] = True
                if s["needs_reset"] and not above_ind:
                    # Price has dipped below EMA → reset complete
                    s["needs_reset"] = False

            # EXIT signal
            if s["in_position"] and not s["pending_sell"]:
                hold_so_far = row_idx - s["entry_idx"] if s["entry_idx"] is not None else 0
                min_hold_ok = hold_so_far >= min_hold_days
                ema_exit = not above_ind  # close < EMA/SMA (no buffer on exit)
                top5_exit = (exit_mode == "D") and not in_top5
                if min_hold_ok and (ema_exit or top5_exit):
                    s["pending_sell"] = True

            # ENTRY signal
            if not s["in_position"] and not s["pending_buy"] and s["eligible"]:
                if entry_mode == "A":
                    # Fresh close > EMA + 0.5% buffer; if needs_reset, wait for dip first
                    if above_ind_entry and not s["needs_reset"]:
                        s["pending_buy"] = True
                elif entry_mode == "B":
                    # Buy only on the day of Top5 entry (just_eligible), even if already above EMA
                    if s["just_eligible"] and above_ind_entry:
                        s["pending_buy"] = True
                elif entry_mode == "K":
                    # Continuous EMA crossover while in Top5 — no reset, re-entry after every exit
                    if above_ind_entry:
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
            if ticker not in slot_equity:
                slot_equity[ticker] = SLOT_START
            slot_equity[ticker] *= (1 + perf / 100)
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
                "kum_perf_pct": round((slot_equity[ticker] / SLOT_START - 1) * 100, 4),
                "kapital_eur": round(slot_equity[ticker], 2),
            })

    # Sort by execution date, then nr
    trades.sort(key=lambda t: (t["datum"], t["nr"]))
    return trades


def _calc_metrics(trades: list[dict]) -> dict:
    sells = [t for t in trades if t["typ"] == "VERKAUF"]
    if not sells:
        return {"num_trades": 0, "win_rate": 0.0, "total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0,
                "portfolio_end_eur": 0.0, "slots_used": 0}

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

    # Portfolio end value: sum of last kapital_eur per slot
    last_by_ticker: dict[str, float] = {}
    for t in sells:
        if "kapital_eur" in t:
            last_by_ticker[t["ticker"]] = t["kapital_eur"]
    portfolio_end = sum(last_by_ticker.values())

    return {
        "num_trades": len(sells),
        "win_rate": round(win_rate, 2),
        "total_return": round(total_return, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(-max_dd, 4),
        "portfolio_end_eur": round(portfolio_end, 2),
        "slots_used": len(last_by_ticker),
    }


def run_all_combinations(
    price_data: dict[str, pd.DataFrame],
    top5_history: dict,
    indicator: str = "EMA",
    period: int = 200,
    entry_threshold: float = 0.0,
    min_hold_days: int = 0,
) -> list[dict]:
    """Run all 12 combinations and return list of results."""
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
                entry_threshold=entry_threshold,
                min_hold_days=min_hold_days,
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
