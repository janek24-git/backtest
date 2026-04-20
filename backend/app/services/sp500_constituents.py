"""
Historical S&P 500 constituency data from fja05680/sp500 (1996–2026, daily).
Source: https://github.com/fja05680/sp500
"""

import logging
import pandas as pd
import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_FILE = CACHE_DIR / "sp500_constituents.parquet"
CSV_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes(01-17-2026).csv"
)
CACHE_MAX_AGE_DAYS = 7


def _is_fresh() -> bool:
    if not CACHE_FILE.exists():
        return False
    mtime = datetime.fromtimestamp(CACHE_FILE.stat().st_mtime, tz=timezone.utc)
    return datetime.now(tz=timezone.utc) - mtime < timedelta(days=CACHE_MAX_AGE_DAYS)


def _normalize_ticker(t: str) -> str:
    """Normalize ticker for cross-source comparison (e.g. BRK.B → BRK-B)."""
    return t.strip().replace(".", "-")


def load_constituents() -> pd.DataFrame | None:
    """
    Returns DataFrame with DatetimeIndex and single column 'tickers' (comma-separated).
    Returns None if download fails.
    """
    if _is_fresh():
        return pd.read_parquet(CACHE_FILE)

    try:
        r = requests.get(CSV_URL, verify=False, timeout=20)
        r.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(r.text), index_col=0)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df.to_parquet(CACHE_FILE)
        logger.info("S&P 500 constituents downloaded: %d snapshots", len(df))
        return df
    except Exception as e:
        logger.warning("Failed to load S&P 500 constituents: %s", e)
        return None


def get_members_on_date(df: pd.DataFrame, dt) -> set[str]:
    """Return set of normalized tickers in S&P 500 on the given date."""
    dt = pd.to_datetime(dt)
    subset = df.loc[:dt]
    if subset.empty:
        return set()
    raw = subset.iloc[-1]["tickers"]
    return {_normalize_ticker(t) for t in raw.split(",")}
