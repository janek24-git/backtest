"""
Reddit WSB Scanner
Durchsucht r/wallstreetbets nach trending Tickers
Fokus: PLTR + alle weiteren Top-Mentions
Sendet Alert wenn PLTR erwähnt wird oder neuer Top-Ticker auftaucht
"""

import os
import re
import logging
import httpx
from collections import Counter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SUBREDDITS = ["wallstreetbets", "stocks", "investing", "options"]
WATCHLIST = ["PLTR", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "AMD", "GOOGL"]

# Regex: Ticker = 2-5 Großbuchstaben, nicht mitten in Wort
TICKER_RE = re.compile(r'\b([A-Z]{2,5})\b')

# Wörter die keine Tickers sind (häufige False Positives)
BLACKLIST = {
    "THE", "FOR", "AND", "NOT", "ARE", "BUT", "YOU", "THIS", "THAT",
    "WITH", "HAVE", "FROM", "WILL", "THEY", "BEEN", "MORE", "WHEN",
    "YOUR", "WHAT", "ALL", "HOW", "GET", "ITS", "NOW", "CAN", "USD",
    "WSB", "ATH", "ATM", "OTM", "ITM", "ETF", "IPO", "SEC", "CEO",
    "EMA", "RSI", "SPY", "QQQ", "GEX", "DEX", "PUT", "CALL", "BUY",
    "SELL", "HOLD", "YOLO", "FOMO", "DD", "TA", "GL", "OP", "US",
    "EU", "UK", "GDP", "CPI", "FED", "IMO", "EDIT", "TLDR", "EOD",
    "EOW", "YTD", "YOY", "MOM", "LOL", "WTF", "IMO", "FYI", "EPS",
    "PE", "DC", "AI", "ML", "GO", "UP", "DOWN",
}


def _fetch_reddit(subreddit: str, sort: str = "hot", limit: int = 25) -> list[dict]:
    try:
        r = httpx.get(
            f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}",
            headers={"User-Agent": "Mozilla/5.0 FinanceBot/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        posts = r.json()["data"]["children"]
        return [p["data"] for p in posts]
    except Exception as e:
        logger.warning("Reddit %s failed: %s", subreddit, e)
        return []


def _extract_tickers(text: str) -> list[str]:
    found = TICKER_RE.findall(text or "")
    return [t for t in found if t not in BLACKLIST and len(t) >= 2]


def scan_wsb() -> dict:
    """
    Scannt WSB + weitere Subreddits.
    Gibt zurück:
    - top_tickers: Liste nach Mentions sortiert
    - pltr_posts: Posts die PLTR erwähnen
    - watchlist_hits: Matches aus unserer Watchlist
    """
    all_tickers: Counter = Counter()
    pltr_posts = []
    watchlist_hits: dict[str, int] = {}

    for sub in SUBREDDITS:
        posts = _fetch_reddit(sub, "hot", 25)
        for post in posts:
            title = post.get("title", "")
            body = post.get("selftext", "")
            full_text = f"{title} {body}"
            tickers = _extract_tickers(full_text)
            all_tickers.update(tickers)

            if "PLTR" in tickers:
                pltr_posts.append({
                    "subreddit": sub,
                    "title": title[:120],
                    "score": post.get("score", 0),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "mentions": tickers.count("PLTR"),
                })

    # Top 15 Tickers (Schwelle ≥2, aber Watchlist immer rein wenn ≥1)
    top_raw = dict(all_tickers.most_common(50))
    top = [(t, c) for t, c in all_tickers.most_common(20) if c >= 2 or t in WATCHLIST]

    # Watchlist Hits
    for ticker in WATCHLIST:
        if all_tickers[ticker] > 0:
            watchlist_hits[ticker] = all_tickers[ticker]

    return {
        "top_tickers": top[:15],
        "pltr_posts": sorted(pltr_posts, key=lambda x: x["score"], reverse=True)[:5],
        "watchlist_hits": watchlist_hits,
        "scanned_subreddits": SUBREDDITS,
        "timestamp": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
    }


def _build_wsb_message(data: dict) -> str:
    lines = [f"🎰 <b>WSB Scanner</b>  —  {data['timestamp']}", ""]

    # PLTR highlight
    pltr_count = dict(data["top_tickers"]).get("PLTR", 0)
    if pltr_count > 0 or data["pltr_posts"]:
        lines.append(f"🔵 <b>PLTR</b>  —  {pltr_count} Mentions")
        for p in data["pltr_posts"][:3]:
            lines.append(f"   📌 {p['title']}")
            lines.append(f"   ⬆️ {p['score']} | r/{p['subreddit']}")
        lines.append("")

    # Top Tickers
    lines.append("<b>Top Mentions WSB + Stocks + Investing:</b>")
    for ticker, count in data["top_tickers"][:10]:
        bar = "█" * min(count, 10)
        lines.append(f"   <code>{ticker:<6}</code>  {bar}  {count}×")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def send_wsb_alert() -> dict:
    data = scan_wsb()

    # Nur senden wenn PLTR erwähnt oder Watchlist-Ticker mit hohen Mentions
    pltr_mentions = dict(data["top_tickers"]).get("PLTR", 0)
    high_watchlist = {k: v for k, v in data["watchlist_hits"].items() if v >= 3}

    if pltr_mentions == 0 and not high_watchlist and not data["pltr_posts"]:
        return {"sent": False, "reason": "No significant mentions", "data": data}

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError("Telegram credentials missing")

    text = _build_wsb_message(data)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()

    return {"sent": True, "pltr_mentions": pltr_mentions, "top": data["top_tickers"][:5]}
