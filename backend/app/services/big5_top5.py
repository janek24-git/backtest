"""
S&P 500 Top-5 Tracker (daily, by market cap)

Two-tier market cap calculation:
  1. Companies with complex corporate histories (GE, XOM, CSCO, INTC, WMT, C …)
     → hardcoded annual market caps (billion USD) from historical records
  2. All other companies
     → close_price × shares_outstanding (yfinance fast_info, current value)

Constituency validation:
  → fja05680/sp500 dataset ensures only actual S&P 500 members are considered.
"""

import asyncio
import logging
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta, timezone

from app.services.sp500_constituents import load_constituents as sp500_load_constituents, get_members_on_date as sp500_get_members_on_date
from app.services.nas100_constituents import load_constituents as nas100_load_constituents, get_members_on_date as nas100_get_members_on_date

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_MAX_AGE_HOURS = 23

# ── Candidate universes ───────────────────────────────────────────────────────
# All stocks that have historically appeared in the S&P 500 Top 5 (2000–2025)
SP500_CANDIDATES = [
    "MSFT",   "AAPL",  "AMZN",  "GOOGL", "META",
    "NVDA",   "XOM",   "GE",    "BRK-B", "WMT",
    "CSCO",   "JNJ",   "JPM",   "CVX",   "INTC",
    "PG",     "C",     "BAC",   "HD",    "PFE",
]

# All stocks that have historically appeared in the Nasdaq-100 Top 5 (2000–2025)
NAS100_CANDIDATES = [
    "MSFT", "AAPL", "AMZN", "GOOGL", "META",
    "NVDA", "INTC", "CSCO", "ORCL",  "QCOM",
    "TSLA", "NFLX", "ADBE", "PYPL",  "CMCSA",
    "AVGO", "COST", "TXN",  "AMGN",  "GOOG",
]

# ── Historical market cap corrections (billion USD, approximate annual) ───────
# Used for companies whose price × current_shares gives wrong historical results
# due to reverse splits, spin-offs, or massive share-count changes.
# Source: public records, Wikipedia, annual reports.
HIST_MCAP_B: dict[str, dict[int, float]] = {
    "GE": {
        2000: 450, 2001: 350, 2002: 230, 2003: 290, 2004: 365,
        2005: 375, 2006: 380, 2007: 390, 2008: 180, 2009: 160,
        2010: 195, 2011: 165, 2012: 240, 2013: 280, 2014: 260,
        2015: 285, 2016: 255, 2017: 145, 2018: 65,
    },
    "XOM": {
        2000: 265, 2001: 255, 2002: 235, 2003: 265, 2004: 325,
        2005: 370, 2006: 445, 2007: 510, 2008: 405, 2009: 310,
        2010: 370, 2011: 405, 2012: 400, 2013: 445, 2014: 385,
        2015: 325, 2016: 370,
    },
    "CSCO": {
        2000: 465, 2001: 105, 2002: 75, 2003: 110, 2004: 115,
        2005: 105, 2006: 135, 2007: 190, 2008: 95,
    },
    "INTC": {
        2000: 215, 2001: 120, 2002: 90,  2003: 125, 2004: 165,
        2005: 145, 2006: 120, 2007: 150, 2008: 75,
    },
    "WMT": {
        2000: 265, 2001: 252, 2002: 235, 2003: 240, 2004: 215,
        2005: 200, 2006: 195, 2007: 195, 2008: 220, 2009: 210,
        2010: 210, 2011: 195, 2012: 245,
    },
    "C": {
        2000: 235, 2001: 265, 2002: 155, 2003: 235, 2004: 255,
        2005: 240, 2006: 270, 2007: 225, 2008: 35,  2009: 80,
        2010: 130,
    },
    "PG": {
        2000: 90,  2001: 85,  2002: 115, 2003: 130, 2004: 135,
        2005: 200, 2006: 200, 2007: 215, 2008: 185,
    },
    "JNJ": {
        2000: 110, 2001: 165, 2002: 175, 2003: 145, 2004: 170,
        2005: 180, 2006: 175, 2007: 180, 2008: 170,
    },
    "BAC": {
        2000: 75,  2001: 65,  2002: 60,  2003: 105, 2004: 175,
        2005: 185, 2006: 220, 2007: 180, 2008: 55,  2009: 120,
        2010: 130,
    },
    "ORCL": {
        2000: 230, 2001: 50, 2002: 30, 2003: 55, 2004: 65,
        2005: 60,  2006: 80, 2007: 95, 2008: 60,
    },
    "QCOM": {
        2000: 130, 2001: 30, 2002: 20, 2003: 30, 2004: 50,
        2005: 65,  2006: 75, 2007: 100, 2008: 55,
    },
}


def _hist_mcap_for_year(ticker: str, year: int) -> float | None:
    """
    Returns approximate market cap (billion USD) for a ticker in a given year.
    Interpolates linearly between known annual values.
    Returns None if no historical data available (use price × shares fallback).
    """
    data = HIST_MCAP_B.get(ticker)
    if not data:
        return None
    years = sorted(data.keys())
    if year < years[0]:
        return data[years[0]]
    if year > years[-1]:
        return None  # Modern era: use yfinance approximation
    if year in data:
        return data[year]
    # Linear interpolation
    for i in range(len(years) - 1):
        y0, y1 = years[i], years[i + 1]
        if y0 < year < y1:
            t = (year - y0) / (y1 - y0)
            return data[y0] + t * (data[y1] - data[y0])
    return None


# ── Price data fetching ───────────────────────────────────────────────────────

def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}.parquet"


def _is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(tz=timezone.utc) - mtime < timedelta(hours=CACHE_MAX_AGE_HOURS)


def _fetch_price_sync(ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
    raw = yf.download(ticker, start=from_date, end=to_date, progress=False, auto_adjust=True)
    if raw.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)
    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    return df


def _fetch_shares_sync(ticker: str) -> float | None:
    """Current shares outstanding (used as fallback for companies without hist data)."""
    try:
        info = yf.Ticker(ticker).fast_info
        val = getattr(info, "shares", None)
        if val:
            return float(val)
    except Exception:
        pass
    try:
        info = yf.Ticker(ticker).info
        val = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        if val:
            return float(val)
    except Exception:
        pass
    return None


async def fetch_candidate_data(from_date: str = "2000-01-01", to_date: str = "2025-12-31", universe: str = "SP500") -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for all candidates (cached per ticker)."""
    candidates = SP500_CANDIDATES if universe == "SP500" else NAS100_CANDIDATES
    loop = asyncio.get_running_loop()

    async def fetch_one(ticker: str) -> tuple[str, pd.DataFrame]:
        path = _cache_path(ticker)
        needs_fetch = True
        if _is_fresh(path):
            df = pd.read_parquet(path)
            # Check if cached data covers the requested from_date
            if not df.empty:
                import datetime as _dt
                cached_start = pd.to_datetime(df.index[0]).date()
                requested_start = _dt.date.fromisoformat(from_date)
                if cached_start <= requested_start:
                    needs_fetch = False
        if needs_fetch:
            df = await loop.run_in_executor(None, _fetch_price_sync, ticker, from_date, to_date)
            if len(df) > 0:
                df.to_parquet(path)
        return ticker, df

    results = await asyncio.gather(*[fetch_one(t) for t in candidates], return_exceptions=True)
    out = {}
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Fetch error: %s", r)
        else:
            ticker, df = r
            if not df.empty:
                out[ticker] = df
    return out


# ── Top5 history computation ──────────────────────────────────────────────────

def compute_top5_history(price_data: dict[str, pd.DataFrame], universe: str = "SP500") -> dict:
    """
    For each trading day, determine the Top 5 by approximate market cap.

    Priority:
      1. Constituency data → only real index members considered
         SP500: fja05680/sp500 dataset (1996–present)
         NAS100: no historical dataset available — candidate-only mode
      2. HIST_MCAP_B lookup → accurate for complex-history tickers (GE, XOM, CSCO…)
      3. price × shares_outstanding → fallback for modern tickers
    """
    # Load constituency data (may be None if download failed or not available)
    if universe == "SP500":
        constituents_df = sp500_load_constituents()
        _get_members = sp500_get_members_on_date
        if constituents_df is not None:
            logger.info("Using real S&P 500 constituency data (%d snapshots)", len(constituents_df))
        else:
            logger.warning("S&P 500 constituency data unavailable — using candidate list only")
    else:
        constituents_df = nas100_load_constituents()
        _get_members = nas100_get_members_on_date
        logger.info("NAS100 mode: no historical constituency data — using NAS100_CANDIDATES only")

    # Fetch current shares for fallback tickers
    shares_map: dict[str, float] = {}
    for ticker in price_data:
        if ticker not in HIST_MCAP_B:
            s = _fetch_shares_sync(ticker)
            if s:
                shares_map[ticker] = s

    # Build close price DataFrame
    close_df = pd.DataFrame({t: df["close"] for t, df in price_data.items()})
    close_df.index = pd.to_datetime(close_df.index)
    close_df = close_df.sort_index()

    # Precompute constituency sets per unique snapshot date for speed
    constituents_cache: dict = {}

    top5_history: dict = {}

    for dt, row in close_df.iterrows():
        year = dt.year

        # Get index members on this date
        if constituents_df is not None:
            # Cache by snapshot (constituency changes ~monthly)
            month_key = (dt.year, dt.month)
            if month_key not in constituents_cache:
                constituents_cache[month_key] = _get_members(constituents_df, dt)
            members = constituents_cache[month_key]
        else:
            members = None  # No filter: use all candidates

        market_caps: dict[str, float] = {}
        for ticker, price in row.items():
            if pd.isna(price):
                continue
            # Filter to S&P 500 members
            if members is not None and ticker not in members:
                continue

            # Compute market cap
            hist = _hist_mcap_for_year(ticker, year)
            if hist is not None:
                # Use historical correction (in comparable units: billions)
                market_caps[ticker] = hist * 1e9
            else:
                # Fallback: price × current shares
                shares = shares_map.get(ticker)
                if shares:
                    market_caps[ticker] = float(price) * shares

        # Top 5 by market cap
        top5 = sorted(market_caps, key=market_caps.get, reverse=True)[:5]
        top5_history[dt.date()] = top5

    return top5_history
