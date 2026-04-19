import os
import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from massive import RESTClient

CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY", "")
CACHE_MAX_AGE_HOURS = 23


def get_cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}.parquet"


def is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(tz=timezone.utc) - mtime
    return age < timedelta(hours=CACHE_MAX_AGE_HOURS)


def parse_massive_response(raw: dict) -> pd.DataFrame:
    results = raw.get("results", [])
    if not results:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    rows = []
    for r in results:
        rows.append({
            "date": pd.to_datetime(r["t"], unit="ms", utc=True).date(),
            "open": r["o"],
            "high": r["h"],
            "low": r["l"],
            "close": r["c"],
            "volume": r["v"],
        })
    df = pd.DataFrame(rows).set_index("date")
    df.index.name = "date"
    return df


def _fetch_ticker_sync(ticker: str, from_date: str) -> pd.DataFrame:
    client = RESTClient(api_key=MASSIVE_API_KEY)
    aggs = []
    for a in client.list_aggs(
        ticker=ticker,
        multiplier=1,
        timespan="day",
        from_=from_date,
        to=datetime.now().strftime("%Y-%m-%d"),
        adjusted=True,
        sort="asc",
        limit=50000,
    ):
        aggs.append(a)

    if not aggs:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    rows = []
    for a in aggs:
        rows.append({
            "date": pd.to_datetime(a.timestamp, unit="ms", utc=True).date(),
            "open": a.open,
            "high": a.high,
            "low": a.low,
            "close": a.close,
            "volume": a.volume,
        })

    df = pd.DataFrame(rows).set_index("date")
    df.index.name = "date"
    return df


async def fetch_ticker_data(ticker: str, from_date: str = "2010-01-01") -> pd.DataFrame:
    cache_path = get_cache_path(ticker)

    if is_cache_fresh(cache_path):
        return pd.read_parquet(cache_path)

    df = await asyncio.get_event_loop().run_in_executor(
        None, _fetch_ticker_sync, ticker, from_date
    )

    if len(df) > 0:
        df.to_parquet(cache_path)

    return df


async def fetch_universe_data(tickers: list[str]) -> dict[str, pd.DataFrame]:
    results = await asyncio.gather(
        *[fetch_ticker_data(t) for t in tickers],
        return_exceptions=True
    )
    out = {}
    for ticker, result in zip(tickers, results):
        if isinstance(result, Exception):
            print(f"[WARN] Failed to fetch {ticker}: {result}")
        else:
            out[ticker] = result
    return out
