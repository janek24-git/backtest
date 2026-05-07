"""
Momentum Squeeze Scanner

Signal-Quellen (kein Reddit-Auth nötig):
  1. Yahoo Finance: Trending, Most Actives, Gainers, Losers
  2. Finnhub News: Katalysator-Erkennung via Headline-Tickers
  Velocity = Ticker auf mehreren Listen gleichzeitig
  Score = Quellen-Score × Short-Float% × Short-Ratio
"""

import os
import re
import logging
import httpx
import yfinance as yf
from datetime import datetime, timezone
from app.services.warrant_finder import build_warrant_message, build_warrant_buttons

logger = logging.getLogger(__name__)

# Quellen + Gewichtung
SOURCES = {
    "trending": 3,  # Yahoo Trending — stärkstes Hype-Signal
    "actives":  2,  # Most Actives — höchstes Volumen
    "gainers":  2,  # Top Gewinner — Momentum
    "losers":   1,  # Top Verlierer — potenzielle Squeeze-Setups
}
NUM_SOURCES = len(SOURCES)

TICKER_RE = re.compile(r'\b([A-Z]{2,5})\b')
BLACKLIST = {
    "THE","FOR","AND","NOT","ARE","BUT","YOU","THIS","THAT","WITH","HAVE",
    "FROM","WILL","THEY","BEEN","MORE","WHEN","YOUR","WHAT","ALL","HOW",
    "GET","ITS","NOW","CAN","USD","ATH","ATM","OTM","ITM","ETF","IPO",
    "SEC","CEO","EMA","RSI","SPY","QQQ","PUT","CALL","BUY","SELL","HOLD",
    "US","EU","UK","GDP","CPI","FED","EPS","AI","ML","GO","UP","IV","PE",
    "DC","SPX","CPU","API","NFT","ETH","BTC","NYSE","NASDAQ","CNBC","NEWS",
    "STOCK","TRADE","CASH","BANK","FUND","TAX","IRA","AI","ET","IT","AT",
}

MIN_SHORT_FLOAT = 0.10
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _fetch_yahoo_tickers(source: str) -> list[str]:
    try:
        if source == "trending":
            r = httpx.get(
                "https://query1.finance.yahoo.com/v1/finance/trending/US?count=25",
                headers=YAHOO_HEADERS, timeout=10,
            )
            r.raise_for_status()
            return [q["symbol"] for q in r.json()["finance"]["result"][0]["quotes"]]
        scr_map = {"actives": "most_actives", "gainers": "day_gainers", "losers": "day_losers"}
        r = httpx.get(
            f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds={scr_map[source]}&count=25",
            headers=YAHOO_HEADERS, timeout=10,
        )
        r.raise_for_status()
        return [q["symbol"] for q in r.json()["finance"]["result"][0].get("quotes", [])]
    except Exception as e:
        logger.warning("Yahoo %s: %s", source, e)
        return []


def _fetch_news_tickers() -> dict[str, str]:
    """Holt Finnhub-News und extrahiert Ticker → Headline."""
    token = os.environ.get("FINNHUB_API_KEY", "")
    if not token:
        return {}
    try:
        r = httpx.get(
            f"https://finnhub.io/api/v1/news?category=general&token={token}",
            timeout=10,
        )
        r.raise_for_status()
        result: dict[str, str] = {}
        for item in r.json()[:50]:
            headline = item.get("headline", "")
            for t in TICKER_RE.findall(headline):
                if t not in BLACKLIST and len(t) >= 2 and t not in result:
                    result[t] = headline[:80]
        return result
    except Exception as e:
        logger.warning("Finnhub news: %s", e)
        return {}


def _get_short_data(ticker: str) -> dict:
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
    # Quellen abrufen
    by_source: dict[str, list[str]] = {s: _fetch_yahoo_tickers(s) for s in SOURCES}
    news_tickers = _fetch_news_tickers()

    # Score pro Ticker berechnen
    ticker_score: dict[str, int] = {}
    ticker_sources: dict[str, list[str]] = {}
    for source, weight in SOURCES.items():
        for ticker in by_source[source]:
            if any(c.isdigit() for c in ticker):
                continue
            ticker_score[ticker] = ticker_score.get(ticker, 0) + weight
            ticker_sources.setdefault(ticker, []).append(source)

    # Mindest-Score 2, sortiert nach Score
    velocity = [
        (t, score, len(srcs))
        for t, score in ticker_score.items()
        if score >= 2
        for srcs in [ticker_sources[t]]
    ]
    velocity.sort(key=lambda x: (x[2], x[1]), reverse=True)

    # Short-Daten für Top-Kandidaten
    squeeze_candidates = []
    for ticker, mentions, sources_count in velocity[:15]:
        sd = _get_short_data(ticker)
        score = round(mentions * (sd["short_float"] * 100) * max(sd["short_ratio"], 0.1), 1)
        signals = ticker_sources[ticker]
        catalyst = news_tickers.get(ticker)
        posts = [{"title": f"📰 {catalyst}", "score": 1}] if catalyst else \
                [{"title": f"Quellen: {', '.join(signals)}", "score": 0}]
        squeeze_candidates.append({
            "ticker":          ticker,
            "name":            sd["name"],
            "mentions":        mentions,
            "sorts":           sources_count,
            "short_float":     sd["short_float"],
            "short_float_pct": round(sd["short_float"] * 100, 1),
            "short_ratio":     sd["short_ratio"],
            "price":           sd["price"],
            "score":           score,
            "posts":           posts,
            "signals":         signals,
            "catalyst":        catalyst,
        })

    squeeze_candidates.sort(key=lambda x: x["score"], reverse=True)
    high_short  = [c for c in squeeze_candidates if c["short_float"] >= MIN_SHORT_FLOAT]
    explosions  = [c for c in squeeze_candidates if c["sorts"] >= 3 and c["short_float"] >= 0.15]

    return {
        "squeeze_candidates": squeeze_candidates[:10],
        "high_short":         high_short[:5],
        "explosions":         explosions[:3],
        "timestamp":          datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
    }


TV_BASE = "https://www.tradingview.com/chart/?symbol="


def _tv(ticker: str) -> str:
    return f'<a href="{TV_BASE}{ticker}">{ticker}</a>'


def _build_squeeze_buttons(candidates: list[dict]) -> dict:
    keyboard = []
    for c in candidates[:5]:
        t = c["ticker"]
        keyboard.append([
            {"text": f"📈 {t}", "url": f"https://www.tradingview.com/chart/?symbol={t}"},
            {"text": "📰 News", "url": f"https://finance.yahoo.com/quote/{t}/news/"},
        ])
    return {"inline_keyboard": keyboard}


def _build_mentions_buttons(candidates: list[dict]) -> dict:
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
    lines = [f"📋 <b>Market Signals</b>  —  {data['timestamp']}", ""]
    by_mentions = sorted(data["squeeze_candidates"], key=lambda x: x["mentions"], reverse=True)
    for i, c in enumerate(by_mentions, 1):
        icon = "🔥" if c["sorts"] >= 3 else "📈" if c["sorts"] == 2 else "·"
        lines.append(
            f"{i:>2}. {icon} <b>{_tv(c['ticker'])}</b>"
            f"  Score:{c['mentions']}"
            f"  {c['sorts']}/{NUM_SOURCES} Quellen"
            f"  Short: {c['short_float_pct']:.1f}%"
        )
    lines.append("")
    lines.append("Ticker = Link zu TradingView Chart")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def _build_wsb_message(data: dict) -> str:
    lines = [f"🎯 <b>Momentum Scanner</b>  —  {data['timestamp']}", ""]

    explosions = data.get("explosions", [])
    if explosions:
        lines.append("🚨 <b>EXPLOSIONS-ALARM</b>  ·  3+ Quellen + Short≥15%")
        for c in explosions:
            lines.append(
                f"   💥 <b>{_tv(c['ticker'])}</b>"
                f"  Short: {c['short_float_pct']:.1f}%"
                f"  Ratio: {c['short_ratio']:.1f}d"
                f"  Score:{c['mentions']}  Squeeze:{c['score']:.0f}"
            )
            if c["posts"]:
                lines.append(f"      └ {c['posts'][0]['title'][:65]}")
        lines.append("")

    candidates = data["squeeze_candidates"]
    if candidates:
        lines.append("<b>🏆 Top Squeeze-Kandidaten</b>")
        lines.append("")
        for c in candidates[:7]:
            icon = "🔥" if c["sorts"] >= 3 else "📈" if c["sorts"] == 2 else "·"
            lines.append(
                f"{icon} <b>{_tv(c['ticker'])}</b>"
                f"  Short: {c['short_float_pct']:.1f}%"
                f"  {c['short_ratio']:.1f}d"
                f"  Quellen:{c['sorts']}/{NUM_SOURCES}"
                f"  Score {c['score']:.0f}"
            )
            if c["posts"]:
                lines.append(f"   └ {c['posts'][0]['title'][:65]}")

    lines.append("")
    lines.append("Quellen: Trending · Aktiv · Gewinner · Verlierer · News")
    lines.append("Ticker anklicken → TradingView Chart")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def send_wsb_alert() -> dict:
    data = scan_wsb()

    top_score  = data["squeeze_candidates"][0]["score"] if data["squeeze_candidates"] else 0
    high_short = data["high_short"]
    explosions = data.get("explosions", [])

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
