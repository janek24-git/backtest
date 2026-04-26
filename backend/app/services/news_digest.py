"""
Morning News Digest

Holt täglich Finanznews aus mehreren RSS-Feeds,
lässt Claude zusammenfassen + Handlungsempfehlung geben,
schickt 2 Telegram-Nachrichten:
  1. Top-News + Markteinschätzung
  2. Konkrete Handlungsempfehlung für Big5 + Watchlist
"""

import os
import logging
import httpx
import anthropic
import xml.etree.ElementTree as ET
from datetime import date

logger = logging.getLogger(__name__)

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

Dein Auftrag — antworte auf Deutsch, direkt und präzise:

## Teil 1 — Top 5 News (Telegram-Nachricht 1)
Wähle die 5 wichtigsten Meldungen aus. Für jede:
- 1 Satz was passiert ist
- 1 Satz Marktrelevanz (positiv / negativ / neutral für Aktien)

Format exakt so:
1. [THEMA] Ereignis — Marktrelevanz
2. ...

## Teil 2 — Handlungsempfehlung (Telegram-Nachricht 2)
Bezug auf Big 5: AAPL, MSFT, NVDA, AMZN, GOOGL

Beantworte:
- Welche Nachrichten betreffen direkt die Big 5?
- Gibt es Sektor-Trends (KI, Chips, Cloud, Konsum) die heute relevant sind?
- 1 konkrete Aktion: kaufen / halten / vorsichtig sein — mit Begründung in 2 Sätzen

Max 300 Wörter gesamt. Keine Floskeln."""


async def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
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
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text

    # Split in Teil 1 und Teil 2
    if "## Teil 2" in raw:
        part1, part2 = raw.split("## Teil 2", 1)
        part1 = part1.replace("## Teil 1 — Top 5 News (Telegram-Nachricht 1)", "").strip()
        part2 = part2.replace("— Handlungsempfehlung (Telegram-Nachricht 2)", "").strip()
    else:
        part1 = raw
        part2 = ""

    today = date.today().strftime("%d.%m.%Y")
    msg1 = _format_msg1(part1, today)
    await _send_telegram(msg1)

    if part2:
        msg2 = _format_msg2(part2, today)
        await _send_telegram(msg2)

    return {
        "sent": True,
        "sources": list(headlines.keys()),
        "headlines_total": total,
    }
