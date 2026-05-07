"""
Short Squeeze Scanner — WSB Momentum Detektor

GME-Formel:
  1. Mention-Velocity: Tickers die auf hot + new + rising gleichzeitig auftauchen
  2. Short Interest: shortPercentOfFloat + shortRatio via yfinance
  3. Score = Mentions × Short-Float% × Short-Ratio
  4. Alert wenn Score hoch ODER einzelne Metrik extrem

Quellen: r/wallstreetbets, r/stocks, r/options, r/shortsqueeze
"""

import os
import re
import logging
import httpx
import yfinance as yf
from collections import Counter
from datetime import datetime, timezone
from app.services.warrant_finder import build_warrant_message, build_warrant_buttons

logger = logging.getLogger(__name__)

SUBREDDITS   = ["wallstreetbets", "stocks", "options", "shortsqueeze", "investing"]
SORTS        = ["hot", "new", "rising"]
WATCHLIST    = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "AMD", "GOOGL", "GME", "AMC"]

TICKER_RE    = re.compile(r'\b([A-Z]{2,6})\b')
BLACKLIST    = {
    "THE","FOR","AND","NOT","ARE","BUT","YOU","THIS","THAT","WITH","HAVE",
    "FROM","WILL","THEY","BEEN","MORE","WHEN","YOUR","WHAT","ALL","HOW",
    "GET","ITS","NOW","CAN","USD","WSB","ATH","ATM","OTM","ITM","ETF",
    "IPO","SEC","CEO","EMA","RSI","SPY","QQQ","PUT","CALL","BUY","SELL",
    "HOLD","YOLO","FOMO","DD","TA","GL","OP","US","EU","UK","GDP","CPI",
    "FED","IMO","EDIT","TLDR","EOD","YTD","LOL","WTF","FYI","EPS","AI",
    "ML","GO","UP","IV","PE","DC","GEX","DEX","SPX","CPU","ARPU","RDDT",
    "API","NFT","ETH","BTC","DRS","MOASS","APES","SHORT","LONG","CALLS",
    "PUTS","YOLO","MOON","BULL","BEAR","GREEN","RED","LOSS","GAIN","OPEN",
    "HIGH","LOW","CLOSE","NYSE","NASDAQ","CNBC","NEWS","STOCK","TRADE",
    "LOSS","GAIN","CASH","BANK","FUND","TAX","IRA","ROTH",
}

# Mindest-Short-Float für Squeeze-Kandidaten
MIN_SHORT_FLOAT = 0.10   # 10%
MIN_SHORT_RATIO = 3.0    # 3 Tage zum Covern


def _fetch_reddit(subreddit: str, sort: str, limit: int = 30) -> list[dict]:
    try:
        r = httpx.get(
            f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}",
            headers={"User-Agent": "Mozilla/5.0 SqueezeBot/2.0"},
            timeout=10,
        )
        r.raise_for_status()
        return [p["data"] for p in r.json()["data"]["children"]]
    except Exception as e:
        logger.warning("Reddit %s/%s: %s", subreddit, sort, e)
        return []


def _extract_tickers(text: str) -> list[str]:
    found = TICKER_RE.findall(text or "")
    return [t for t in found if t not in BLACKLIST and len(t) >= 2]


def _get_short_data(ticker: str) -> dict:
    """Holt Short-Float% und Short-Ratio via yfinance."""
    try:
        info = yf.Ticker(ticker).info
        short_float = info.get("shortPercentOfFloat") or 0.0
        short_ratio = info.get("shortRatio") or 0.0
        price       = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
        name        = info.get("shortName") or ticker
        return {
            "short_float": round(float(short_float), 4),
            "short_ratio": round(float(short_ratio), 2),
            "price":       round(float(price), 2),
            "name":        name,
        }
    except Exception:
        return {"short_float": 0.0, "short_ratio": 0.0, "price": 0.0, "name": ticker}


def scan_wsb() -> dict:
    """
    Scannt alle Subreddits auf hot/new/rising.
    Berechnet Mention-Velocity und Short-Squeeze-Score.
    """
    # Mentions pro Sort sammeln
    by_sort: dict[str, Counter] = {s: Counter() for s in SORTS}
    post_details: dict[str, list] = {}  # ticker → posts

    for sub in SUBREDDITS:
        for sort in SORTS:
            posts = _fetch_reddit(sub, sort, 30)
            for post in posts:
                title  = post.get("title", "")
                body   = post.get("selftext", "")
                score  = post.get("score", 0)
                tickers = _extract_tickers(f"{title} {body}")

                by_sort[sort].update(tickers)

                for t in set(tickers):
                    if t not in post_details:
                        post_details[t] = []
                    post_details[t].append({
                        "title":     title[:100],
                        "score":     score,
                        "subreddit": sub,
                        "sort":      sort,
                        "url":       f"https://reddit.com{post.get('permalink','')}",
                    })

    # Velocity-Score: Ticker auf allen 3 Sorts präsent = starkes Signal
    all_tickers = by_sort["hot"] + by_sort["new"] + by_sort["rising"]
    velocity: list[tuple[str, int, int]] = []
    for ticker in set(all_tickers.keys()):
        total   = all_tickers[ticker]
        on_sorts = sum(1 for s in SORTS if by_sort[s][ticker] > 0)
        if total >= 2:
            velocity.append((ticker, total, on_sorts))

    # Sortiert: erst nach Sorts-Coverage, dann nach Mentions
    velocity.sort(key=lambda x: (x[2], x[1]), reverse=True)
    top_velocity = velocity[:20]

    # Short-Interest für Top-Kandidaten holen
    squeeze_candidates = []
    for ticker, mentions, sorts_count in top_velocity[:12]:
        sd = _get_short_data(ticker)
        score = round(mentions * (sd["short_float"] * 100) * max(sd["short_ratio"], 0.1), 1)
        squeeze_candidates.append({
            "ticker":       ticker,
            "name":         sd["name"],
            "mentions":     mentions,
            "sorts":        sorts_count,
            "short_float":  sd["short_float"],
            "short_float_pct": round(sd["short_float"] * 100, 1),
            "short_ratio":  sd["short_ratio"],
            "price":        sd["price"],
            "score":        score,
            "posts":        sorted(post_details.get(ticker, []), key=lambda x: x["score"], reverse=True)[:2],
        })

    # Sortiert nach Squeeze-Score
    squeeze_candidates.sort(key=lambda x: x["score"], reverse=True)

    # Extreme Shorts (auch ohne viele Mentions)
    high_short = [c for c in squeeze_candidates if c["short_float"] >= MIN_SHORT_FLOAT]

    # Explosions-Kandidaten: auf allen 3 Sorts + Short-Float >= 15%
    explosions = [
        c for c in squeeze_candidates
        if c["sorts"] == 3 and c["short_float"] >= 0.15
    ]

    return {
        "squeeze_candidates": squeeze_candidates[:10],
        "high_short":         high_short[:5],
        "explosions":         explosions[:3],
        "timestamp": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
    }


TV_BASE = "https://www.tradingview.com/chart/?symbol="


def _tv(ticker: str) -> str:
    return f'<a href="{TV_BASE}{ticker}">{ticker}</a>'


def _build_squeeze_buttons(candidates: list[dict]) -> dict:
    """Inline keyboard: TradingView + WSB Reddit search per top candidate."""
    keyboard = []
    for c in candidates[:5]:
        t = c["ticker"]
        keyboard.append([
            {"text": f"📈 {t}", "url": f"https://www.tradingview.com/chart/?symbol={t}"},
            {"text": "🔍 WSB", "url": f"https://www.reddit.com/r/wallstreetbets/search/?q={t}&sort=new&restrict_sr=1"},
        ])
    return {"inline_keyboard": keyboard}


def _build_mentions_buttons(candidates: list[dict]) -> dict:
    """Inline keyboard for mention-sorted list — Yahoo Finance + Finviz."""
    keyboard = []
    by_mentions = sorted(candidates, key=lambda x: x["mentions"], reverse=True)
    for c in by_mentions[:5]:
        t = c["ticker"]
        keyboard.append([
            {"text": f"💹 {t} YF", "url": f"https://finance.yahoo.com/quote/{t}"},
            {"text": f"📊 Finviz", "url": f"https://finviz.com/quote.ashx?t={t}"},
        ])
    return {"inline_keyboard": keyboard}


def _build_mentions_message(data: dict) -> str:
    """Ranked mention list — sauber, klickbare Ticker."""
    lines = [f"📋 <b>Top Mentions Reddit</b>  —  {data['timestamp']}", ""]
    by_mentions = sorted(data["squeeze_candidates"], key=lambda x: x["mentions"], reverse=True)
    for i, c in enumerate(by_mentions, 1):
        icon = "🔥" if c["sorts"] == 3 else "📈" if c["sorts"] == 2 else "·"
        lines.append(
            f"{i:>2}. {icon} <b>{_tv(c['ticker'])}</b>"
            f"  {c['mentions']}×"
            f"  {c['sorts']}/3 sorts"
            f"  Short: {c['short_float_pct']:.1f}%"
        )
    lines.append("")
    lines.append("Ticker = Link zu TradingView Chart")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def _build_wsb_message(data: dict) -> str:
    lines = [f"🎯 <b>WSB Squeeze Scanner</b>  —  {data['timestamp']}", ""]

    # Explosions-Alert (hot+new+rising + Short ≥15%) — GME-Setup
    explosions = data.get("explosions", [])
    if explosions:
        lines.append("🚨 <b>EXPLOSIONS-ALARM</b>  ·  hot+new+rising + Short≥15%")
        for c in explosions:
            lines.append(
                f"   💥 <b>{_tv(c['ticker'])}</b>"
                f"  Short: {c['short_float_pct']:.1f}%"
                f"  Ratio: {c['short_ratio']:.1f}d"
                f"  {c['mentions']}×  Score: {c['score']:.0f}"
            )
            if c["posts"]:
                lines.append(f"      └ {c['posts'][0]['title'][:65]}")
        lines.append("")

    # Top Squeeze Kandidaten
    candidates = data["squeeze_candidates"]
    if candidates:
        lines.append("<b>🏆 Top Squeeze-Kandidaten</b>")
        lines.append("")
        for c in candidates[:7]:
            icon = "🔥" if c["sorts"] == 3 else "📈" if c["sorts"] == 2 else "·"
            lines.append(
                f"{icon} <b>{_tv(c['ticker'])}</b>"
                f"  {c['mentions']}×"
                f"  Short: {c['short_float_pct']:.1f}%"
                f"  {c['short_ratio']:.1f}d"
                f"  Score {c['score']:.0f}"
            )
            if c["posts"]:
                lines.append(f"   └ {c['posts'][0]['title'][:65]}")

    lines.append("")
    lines.append("🔥 hot+new+rising  ·  Score = Mentions × Short%")
    lines.append("Ticker anklicken → TradingView Chart")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def send_wsb_alert() -> dict:
    data = scan_wsb()

    top_score  = data["squeeze_candidates"][0]["score"] if data["squeeze_candidates"] else 0
    high_short = data["high_short"]
    explosions = data.get("explosions", [])

    # Senden wenn: Explosions-Kandidat ODER hoher Score ODER extreme Short-Interest
    should_send = (
        len(explosions) >= 1
        or top_score >= 50
        or len(high_short) >= 2
    )

    if not should_send:
        return {"sent": False, "reason": "No squeeze signal", "top_score": top_score}

    token   = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    candidates = data["squeeze_candidates"]
    text1      = _build_wsb_message(data)
    text2      = _build_mentions_message(data)
    buttons1   = _build_squeeze_buttons(candidates)
    buttons2   = _build_mentions_buttons(candidates)

    async with httpx.AsyncClient() as client:
        for text, markup in ((text1, buttons1), (text2, buttons2)):
            payload: dict = {
                "chat_id":    chat_id,
                "text":       text,
                "parse_mode": "HTML",
            }
            if markup.get("inline_keyboard"):
                payload["reply_markup"] = markup
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()

    # Optionsschein für Top-Kandidaten — Explosions zuerst, sonst #1 Squeeze
    warrant_ticker = (
        explosions[0]["ticker"] if explosions
        else candidates[0]["ticker"] if candidates
        else None
    )
    if warrant_ticker:
        warrant_text    = build_warrant_message(warrant_ticker, "LONG", target_pct=20.0)
        warrant_buttons = build_warrant_buttons(warrant_ticker, "LONG")
        async with httpx.AsyncClient() as client:
            payload: dict = {
                "chat_id":    chat_id,
                "text":       warrant_text,
                "parse_mode": "HTML",
            }
            if warrant_buttons.get("inline_keyboard"):
                payload["reply_markup"] = warrant_buttons
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=30,
            )

    # Auto-save warrant_ticker to forward testing
    if warrant_ticker:
        from app.services.forward_db import add_trade as _add_forward
        warrant_candidate = (
            next((c for c in explosions if c["ticker"] == warrant_ticker), None)
            or next((c for c in candidates if c["ticker"] == warrant_ticker), None)
        )
        if warrant_candidate and warrant_candidate.get("price", 0) > 0:
            try:
                _add_forward(
                    ticker=warrant_ticker,
                    signal_date=date.today().isoformat(),
                    entry_price=warrant_candidate["price"],
                    ema200=warrant_candidate["price"],
                    tp_pct=20.0,
                    sl_pct=10.0,
                    source="WSB",
                    rel_vol=warrant_candidate.get("mentions"),
                    pct_above_ema=warrant_candidate.get("short_float", 0) * 100,
                )
            except Exception:
                pass

    return {
        "sent":           True,
        "explosions":     [c["ticker"] for c in explosions],
        "top_score":      top_score,
        "warrant_ticker": warrant_ticker,
        "candidates":     [(c["ticker"], c["score"]) for c in candidates[:5]],
    }
