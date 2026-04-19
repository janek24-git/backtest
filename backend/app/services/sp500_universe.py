SP500_TOP5_HISTORY: dict[int, list[str]] = {
    2000: ["GE", "XOM", "PFE", "CSCO", "MSFT"],
    2001: ["GE", "MSFT", "XOM", "WMT", "C"],
    2002: ["MSFT", "XOM", "WMT", "C", "PFE"],
    2003: ["MSFT", "XOM", "PFE", "C", "WMT"],
    2004: ["GE", "MSFT", "C", "XOM", "WMT"],
    2005: ["GE", "XOM", "MSFT", "C", "WMT"],
    2006: ["XOM", "MSFT", "C", "BAC", "GE"],
    2007: ["XOM", "MSFT", "PG", "GE", "GOOGL"],
    2008: ["XOM", "WMT", "PG", "MSFT", "JNJ"],
    2009: ["XOM", "MSFT", "WMT", "GOOGL", "AAPL"],
    2010: ["XOM", "AAPL", "MSFT", "BRK-B", "WMT"],
    2011: ["XOM", "AAPL", "MSFT", "CVX", "GOOGL"],
    2012: ["AAPL", "XOM", "GOOGL", "WMT", "MSFT"],
    2013: ["AAPL", "XOM", "GOOGL", "MSFT", "BRK-B"],
    2014: ["AAPL", "XOM", "MSFT", "BRK-B", "GOOGL"],
    2015: ["AAPL", "GOOGL", "MSFT", "BRK-B", "XOM"],
    2016: ["AAPL", "GOOGL", "MSFT", "BRK-B", "XOM"],
    2017: ["AAPL", "GOOGL", "MSFT", "AMZN", "META"],
    2018: ["MSFT", "AAPL", "AMZN", "GOOGL", "BRK-B"],
    2019: ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    2020: ["AAPL", "MSFT", "AMZN", "GOOGL", "META"],
    2021: ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
    2022: ["AAPL", "MSFT", "GOOGL", "AMZN", "BRK-B"],
    2023: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
    2024: ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN"],
    2025: ["NVDA", "AAPL", "GOOGL", "MSFT", "AMZN"],
}

ALL_TICKERS: list[str] = sorted(set(
    ticker
    for tickers in SP500_TOP5_HISTORY.values()
    for ticker in tickers
))


def get_top5(year: int) -> list[str]:
    if year not in SP500_TOP5_HISTORY:
        raise ValueError(f"No Top-5 data for year {year}. Supported: 2000–2025.")
    return SP500_TOP5_HISTORY[year]
