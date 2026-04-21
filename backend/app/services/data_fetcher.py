import asyncio
import logging
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

CACHE_MAX_AGE_HOURS = 23


def get_cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}.parquet"


def is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(tz=timezone.utc) - mtime < timedelta(hours=CACHE_MAX_AGE_HOURS)


def _fetch_ticker_sync(ticker: str, from_date: str) -> pd.DataFrame:
    raw = yf.download(ticker, start=from_date, progress=False, auto_adjust=False)
    if raw.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    # Use split-adjusted Close (not dividend-adjusted) to match TradingView default
    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    return df


async def fetch_ticker_data(ticker: str, from_date: str = "2000-01-01") -> pd.DataFrame:
    cache_path = get_cache_path(ticker)

    if is_cache_fresh(cache_path):
        return pd.read_parquet(cache_path)

    df = await asyncio.get_running_loop().run_in_executor(
        None, _fetch_ticker_sync, ticker, from_date
    )

    if len(df) > 0:
        df.to_parquet(cache_path)

    return df


async def fetch_universe_data(tickers: list[str]) -> dict[str, pd.DataFrame]:
    results = await asyncio.gather(
        *[fetch_ticker_data(t) for t in tickers],
        return_exceptions=True,
    )
    out = {}
    for ticker, result in zip(tickers, results):
        if isinstance(result, Exception):
            logger.warning("Failed to fetch %s: %s", ticker, result)
        else:
            out[ticker] = result
    return out
