"""
Dynamic index constituent fetching.
- S&P 500: Wikipedia scrape → ranked by market cap via yfinance
- NAS100:  Wikipedia scrape → ranked by market cap via yfinance
- Results cached 24h in cache/
"""

import json
import logging
import concurrent.futures
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

SP500_CACHE = CACHE_DIR / "sp500_dynamic.json"
NAS100_CACHE = CACHE_DIR / "nas100_dynamic.json"
CACHE_MAX_AGE_HOURS = 24

WIKIPEDIA_SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
WIKIPEDIA_NAS100 = "https://en.wikipedia.org/wiki/Nasdaq-100"

# Fallback hardcoded lists (used when Wikipedia/yfinance unavailable)
_FALLBACK: dict[str, dict[int, list[str]]] = {
    "SP500": {
        5:  ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"],
        10: ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "BRK-B", "JPM"],
        20: ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "BRK-B", "JPM",
             "LLY", "V", "UNH", "XOM", "WMT", "JPM", "MA", "ORCL", "COST", "HD"],
    },
    "NAS100": {
        5:  ["AAPL", "MSFT", "NVDA", "AMZN", "META"],
        10: ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AVGO", "TSLA", "COST", "NFLX"],
        20: ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AVGO", "TSLA", "COST", "NFLX",
             "AMD", "ADBE", "PEP", "CSCO", "INTC", "CMCSA", "TMUS", "QCOM", "TXN", "GOOG"],
    },
}


def _is_fresh(cache_file: Path) -> bool:
    if not cache_file.exists():
        return False
    mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
    return datetime.now(tz=timezone.utc) - mtime < timedelta(hours=CACHE_MAX_AGE_HOURS)


def _fetch_market_cap(ticker: str) -> tuple[str, float]:
    try:
        mc = yf.Ticker(ticker).fast_info.market_cap
        return ticker, float(mc) if mc else 0.0
    except Exception:
        return ticker, 0.0


def _rank_by_market_cap(tickers: list[str], max_workers: int = 20) -> list[str]:
    """Fetch market caps concurrently and return tickers sorted desc."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_fetch_market_cap, tickers))
    ranked = sorted(results, key=lambda x: x[1], reverse=True)
    return [t for t, cap in ranked if cap > 0]


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BacktestBot/1.0; "
        "+https://github.com/janek24-git/backtest)"
    )
}


def _read_html_with_headers(url: str) -> list[pd.DataFrame]:
    import requests
    from io import StringIO
    r = requests.get(url, headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return pd.read_html(StringIO(r.text))


def _fetch_sp500_constituents() -> list[str] | None:
    try:
        tables = _read_html_with_headers(WIKIPEDIA_SP500)
        for table in tables:
            if "Symbol" in table.columns:
                return [str(t).strip().replace(".", "-") for t in table["Symbol"].tolist()]
        return None
    except Exception as e:
        logger.warning("SP500 Wikipedia fetch failed: %s", e)
        return None


def _fetch_nas100_constituents() -> list[str] | None:
    try:
        tables = _read_html_with_headers(WIKIPEDIA_NAS100)
        for table in tables:
            cols = [str(c).lower() for c in table.columns]
            if "ticker" in cols:
                col = table.columns[cols.index("ticker")]
                return [str(t).strip().replace(".", "-") for t in table[col].tolist()]
        return None
    except Exception as e:
        logger.warning("NAS100 Wikipedia fetch failed: %s", e)
        return None


def _load_cache(cache_file: Path) -> list[str] | None:
    try:
        data = json.loads(cache_file.read_text())
        return data.get("ranked")
    except Exception:
        return None


def _save_cache(cache_file: Path, ranked: list[str]) -> None:
    try:
        cache_file.write_text(json.dumps({
            "ranked": ranked,
            "updated": datetime.now(tz=timezone.utc).isoformat(),
        }))
    except Exception as e:
        logger.warning("Cache write failed: %s", e)


def get_dynamic_tickers(universe_type: str, n: int) -> list[str]:
    """
    Returns top-n tickers from SP500 or NAS100, ranked by current market cap.
    Falls back to hardcoded lists on any failure.
    """
    utype = universe_type.upper()
    if utype not in _FALLBACK:
        raise ValueError(f"universe_type must be SP500 or NAS100, got {universe_type}")

    cache_file = SP500_CACHE if utype == "SP500" else NAS100_CACHE

    # Cache hit
    if _is_fresh(cache_file):
        ranked = _load_cache(cache_file)
        if ranked and len(ranked) >= n:
            logger.info("%s dynamic universe from cache (%d tickers)", utype, len(ranked))
            return ranked[:n]

    # Fetch Wikipedia constituents
    fetch_fn = _fetch_sp500_constituents if utype == "SP500" else _fetch_nas100_constituents
    constituents = fetch_fn()

    if not constituents:
        logger.warning("%s: Wikipedia fetch failed, using hardcoded fallback", utype)
        return _get_fallback(utype, n)

    logger.info("%s: fetched %d constituents from Wikipedia, ranking by market cap...", utype, len(constituents))
    ranked = _rank_by_market_cap(constituents)

    if not ranked:
        logger.warning("%s: market cap fetch failed, using hardcoded fallback", utype)
        return _get_fallback(utype, n)

    _save_cache(cache_file, ranked)
    logger.info("%s: dynamic universe ready (%d ranked tickers)", utype, len(ranked))
    return ranked[:n]


def _get_fallback(utype: str, n: int) -> list[str]:
    fb = _FALLBACK[utype]
    best = max((k for k in fb if k <= n), default=min(fb.keys()))
    return fb[best][:n]
