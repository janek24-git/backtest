"""
Morning News Digest

Holt täglich Finanznews aus mehreren RSS-Feeds,
lässt Claude zusammenfassen + Handlungsempfehlung geben,
schickt 2 Telegram-Nachrichten:
  1. Top-News + Markteinschätzung
  2. Konkrete Handlungsempfehlung für Big5 + Watchlist
"""

import os
import re
import logging
import httpx
import anthropic
import numpy as np
import pandas as pd
import yfinance as yf
import xml.etree.ElementTree as ET
from datetime import date
from app.services.warrant_finder import build_warrant_message, build_warrant_buttons

logger = logging.getLogger(__name__)


def _ema(prices: np.ndarray, period: int) -> float:
    if len(prices) < period:
        return float("nan")
    k = 2.0 / (period + 1)
    val = prices[:period].mean()
    for p in prices[period:]:
        val = p * k + val * (1 - k)
    return round(val, 2)


def get_ema_status(ticker: str) -> dict:
    """EMA20/50/200 auf Tagesbasis für einen Ticker."""
    try:
        df = yf.download(ticker, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return {}
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        closes = df["Close"].dropna().values.astype(float)
        price  = round(float(closes[-1]), 2)
        e20    = _ema(closes, 20)
        e50    = _ema(closes, 50)
        e200   = _ema(closes, 200)

        def vs(ema_val: float) -> str:
            if np.isnan(ema_val):
                return "–"
            pct = (price - ema_val) / ema_val * 100
            return f"{'▲' if pct > 0 else '▼'} {abs(pct):.1f}%"

        return {
            "price": price,
            "ema20": e20,  "vs20":  vs(e20),
            "ema50": e50,  "vs50":  vs(e50),
            "ema200": e200, "vs200": vs(e200),
            "trend": (
                "bullish"  if price > e20 > e50 > e200 else
                "bearish"  if price < e20 < e50 < e200 else
                "mixed"
            ),
        }
    except Exception as e:
        logger.warning("EMA status failed for %s: %s", ticker, e)
        return {}

BIG5 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]

RSS_FEEDS = [
    ("Reuters Business",   "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC Markets",       "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135"),
    ("MarketWatch",        "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines"),
    ("Yahoo Finance",      "https://finance.yahoo.com/rss/topfinstories"),
    ("Seeking Alpha",      "https://seekingalpha.com/market_currents.xml"),
]


def _fetch_feed(name: str, url: str, max_items: int = 8) -> list[str]:
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, follow_redirects=True)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        items = root.findall(".//item")
        headlines = []
        for item in items[:max_items]:
            title = item.findtext("title", "").strip()
            if title:
                headlines.append(title)
        return headlines
    except Exception as e:
        logger.warning("Feed %s failed: %s", name, e)
        return []


def fetch_all_headlines() -> dict[str, list[str]]:
    result = {}
    for name, url in RSS_FEEDS:
        headlines = _fetch_feed(name, url)
        if headlines:
            result[name] = headlines
    return result


def _build_prompt(headlines: dict[str, list[str]]) -> str:
    today = date.today().strftime("%d.%m.%Y")
    lines = []
    for source, items in headlines.items():
        lines.append(f"\n### {source}")
        for h in items:
            lines.append(f"- {h}")
    news_block = "\n".join(lines)

    return f"""Du bist ein erfahrener Finanzanalyst. Heute ist der {today}.

Hier sind die aktuellen Finanznews aus mehreren Quellen:

{news_block}

---

Dein Auftrag — antworte auf Deutsch, direkt und präzise. Keine Floskeln.

## Teil 1 — Top 5 News
Wähle die 5 wichtigsten Meldungen. Für jede:
- 1 Satz was passiert ist
- 1 Satz Marktrelevanz (positiv / negativ / neutral)

Format:
1. [THEMA] Ereignis — Marktrelevanz

## Teil 2 — Handlungsempfehlung Big 5
Bezug auf: AAPL, MSFT, NVDA, AMZN, GOOGL
- Welche News betreffen direkt die Big 5?
- Sektor-Trends heute (KI, Chips, Cloud)?
- 1 konkrete Aktion mit 2-Satz-Begründung

## Teil 3 — Finance Research (5 Bereiche)
Analysiere die News aus exakt diesen 5 Perspektiven. Für jede genau 1 Finding:

Bereich 1: MARKT — Welche Aktie/Asset bewegt sich heute signifikant?
Bereich 2: MAKRO — Fed, EZB, Zinsen, Inflation, BIP-Daten heute?
Bereich 3: TECH/EARNINGS — Earnings-Überraschung oder Tech-Wachstum heute?
Bereich 4: CRYPTO — Bitcoin, Altcoins, Bewegung heute?
Bereich 5: DEALS — M&A, PE, VC, IPO-Deal heute relevant?

Format für jeden Bereich:
[NUMMER]. [TITEL (Asset/Sektor)]
[1-2 Sätze Finding]
Idee: [konkrete Trade-Idee oder Risiko-Hinweis]

Max 400 Wörter gesamt.

## Teil 4 — Trade-Idee des Tages
Synthetisiere ALLES aus Teil 1-3 zu EINER einzigen konkreten Trade-Idee.

Format exakt:
TICKER: [Symbol]
RICHTUNG: LONG / SHORT
EINSTIEG: [Kurs oder "bei Marktöffnung"]
ZIEL: [+X%]
STOP: [-X%]
POSITION (1000€): [Anzahl Aktien bei aktuellem Kurs]
GRUND: [2 Sätze — warum genau diese Aktie, warum heute]
KATALYSATOR: [Was triggert die Bewegung]"""


async def _send_telegram(text: str, reply_markup: dict | None = None) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup and reply_markup.get("inline_keyboard"):
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()


def _format_msg1(part1: str, today: str) -> str:
    return (
        f"📰 <b>Morning Briefing — {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{part1}"
    )


def _format_msg2(part2: str, today: str) -> str:
    return (
        f"🎯 <b>Handlungsempfehlung — {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{part2}"
    )


def _format_msg3(part3: str, today: str) -> str:
    return (
        f"🔬 <b>Finance Research — {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{part3}\n\n"
        f"<i>Research by 5-Bereich System</i>"
    )


def _format_msg4(part4: str, today: str) -> str:
    return (
        f"⚡️ <b>Trade-Idee des Tages — {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<code>{part4.strip()}</code>"
    )


async def send_news_digest() -> dict:
    headlines = fetch_all_headlines()
    if not headlines:
        return {"sent": False, "message": "No feeds available"}

    total = sum(len(v) for v in headlines.values())
    logger.info("Fetched %d headlines from %d sources", total, len(headlines))

    prompt = _build_prompt(headlines)
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text

    # Split in Teil 1–4
    parts = {"1": "", "2": "", "3": "", "4": ""}
    current = "1"
    for line in raw.splitlines():
        if "## Teil 2" in line:
            current = "2"; continue
        if "## Teil 3" in line:
            current = "3"; continue
        if "## Teil 4" in line:
            current = "4"; continue
        if "## Teil 1" in line:
            continue
        parts[current] += line + "\n"

    today = date.today().strftime("%d.%m.%Y")
    await _send_telegram(_format_msg1(parts["1"].strip(), today))
    if parts["2"].strip():
        await _send_telegram(_format_msg2(parts["2"].strip(), today))
    if parts["3"].strip():
        await _send_telegram(_format_msg3(parts["3"].strip(), today))
    if parts["4"].strip():
        trade_text  = parts["4"].strip()
        ticker_m    = re.search(r"TICKER:\s*([A-Z]{1,6})", trade_text)
        direction_m = re.search(r"RICHTUNG:\s*(LONG|SHORT)", trade_text)
        ziel_m      = re.search(r"ZIEL:\s*\+?(\d+)", trade_text)

        # EMA-Status für den vorgeschlagenen Ticker holen
        ema_block = ""
        conflict  = ""
        if ticker_m:
            ema = get_ema_status(ticker_m.group(1))
            if ema:
                trend_icon = "🟢" if ema["trend"] == "bullish" else "🔴" if ema["trend"] == "bearish" else "🟡"
                ema_block = (
                    f"\n\n<b>Technischer Check ({ticker_m.group(1)})</b>\n"
                    f"Kurs: {ema['price']}  {trend_icon} Trend: {ema['trend'].upper()}\n"
                    f"EMA20:  {ema['ema20']}  ({ema['vs20']})\n"
                    f"EMA50:  {ema['ema50']}  ({ema['vs50']})\n"
                    f"EMA200: {ema['ema200']}  ({ema['vs200']})"
                )
                if direction_m:
                    d = direction_m.group(1)
                    if (d == "LONG" and ema["trend"] == "bearish") or \
                       (d == "SHORT" and ema["trend"] == "bullish"):
                        conflict = "\n\n⚠️ <b>ACHTUNG:</b> News-Signal widerspricht EMA-Trend — erhöhtes Risiko!"

        await _send_telegram(_format_msg4(trade_text + ema_block + conflict, today))

        # Optionsschein-Finder
        if ticker_m and direction_m:
            ticker    = ticker_m.group(1)
            direction = direction_m.group(1)
            target    = float(ziel_m.group(1)) if ziel_m else 10.0
            warrant_msg     = build_warrant_message(ticker, direction, target)
            warrant_buttons = build_warrant_buttons(ticker, direction)
            await _send_telegram(warrant_msg, reply_markup=warrant_buttons)

    return {
        "sent": True,
        "sources": list(headlines.keys()),
        "headlines_total": total,
    }
