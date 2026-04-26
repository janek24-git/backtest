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

Aktuelle Finanznews:

{news_block}

---

Antworte auf Deutsch. Halte dich EXAKT an die Formate — kein Abweichen.

## Teil 1 — Top 5 News
Wähle die 5 wichtigsten Meldungen. Format exakt so (Nummerierung + Thema in Klammern):
1. [THEMA] Was passiert ist. Marktrelevanz: positiv/negativ/neutral für Aktien.
2. [THEMA] ...
(bis 5)

## Teil 2 — Handlungsempfehlung Big 5
Exakt diese 3 Abschnitte mit exakt diesen Labels:

DIREKTE BETROFFENHEIT:
[Welche Big5 (AAPL/MSFT/NVDA/AMZN/GOOGL) sind heute direkt betroffen und warum — 2 Sätze]

SEKTOR-TRENDS:
[KI / Chips / Cloud / Konsum — was ist heute relevant — 2 Sätze]

KONKRETE AKTION:
[KAUFEN / HALTEN / VORSICHT — Ticker — 2-Satz-Begründung]

## Teil 3 — Finance Research
Exakt 5 Findings, exakt dieses Format:

MARKT: [Titel]
[1-2 Sätze was passiert]
Idee: [konkrete Trade-Idee]

MAKRO: [Titel]
[1-2 Sätze]
Idee: [Idee]

TECH: [Titel]
[1-2 Sätze]
Idee: [Idee]

CRYPTO: [Titel]
[1-2 Sätze]
Idee: [Idee]

DEALS: [Titel]
[1-2 Sätze]
Idee: [Idee]

## Teil 4 — Trade-Idee des Tages
Exakt dieses Format, jede Zeile beginnt mit dem Label:

TICKER: [Symbol]
RICHTUNG: LONG oder SHORT
EINSTIEG: [Kurs oder "Marktöffnung"]
ZIEL: [+X%]
STOP: [-X%]
POSITION: [Anzahl Aktien für 1000 Euro]
GRUND: [2 Sätze warum diese Aktie heute]
KATALYSATOR: [Was löst die Bewegung aus]"""


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


_NUM_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]


def _format_msg1(part1: str, today: str) -> str:
    lines = [f"📰 <b>Morning Briefing — {today}</b>", "━━━━━━━━━━━━━━━━━━━━", ""]
    for raw in part1.strip().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        # "1. [TECH] Text" → "1️⃣ [TECH] Text"
        m = re.match(r"^(\d)\.\s*(.*)", raw)
        if m:
            idx = int(m.group(1)) - 1
            emoji = _NUM_EMOJI[idx] if 0 <= idx < len(_NUM_EMOJI) else f"{m.group(1)}."
            lines.append(f"{emoji} {m.group(2)}")
        else:
            lines.append(raw)
    return "\n".join(lines)


def _format_msg2(part2: str, today: str) -> str:
    section_map = {
        "DIREKTE BETROFFENHEIT:": "📌 <b>Direkte Betroffenheit</b>",
        "SEKTOR-TRENDS:":         "📊 <b>Sektor-Trends</b>",
        "KONKRETE AKTION:":       "✅ <b>Konkrete Aktion</b>",
    }
    lines = [f"🎯 <b>Handlungsempfehlung Big 5 — {today}</b>", "━━━━━━━━━━━━━━━━━━━━", ""]
    for raw in part2.strip().splitlines():
        stripped = raw.strip()
        replaced = False
        for label, replacement in section_map.items():
            if stripped.upper().startswith(label):
                lines += ["", replacement]
                rest = stripped[len(label):].strip()
                if rest:
                    lines.append(rest)
                replaced = True
                break
        if not replaced and stripped:
            lines.append(stripped)
    return "\n".join(lines)


def _format_msg3(part3: str, today: str) -> str:
    area_map = {
        "MARKT:":  "📈 <b>Markt</b>",
        "MAKRO:":  "🏦 <b>Makro</b>",
        "TECH:":   "💻 <b>Tech / Earnings</b>",
        "CRYPTO:": "₿ <b>Crypto</b>",
        "DEALS:":  "🤝 <b>Deals / M&A</b>",
        "IDEE:":   "💡 <i>Idee:</i>",
    }
    lines = [f"🔬 <b>Finance Research — {today}</b>", "━━━━━━━━━━━━━━━━━━━━", ""]
    for raw in part3.strip().splitlines():
        stripped = raw.strip()
        replaced = False
        for label, replacement in area_map.items():
            if stripped.upper().startswith(label):
                title = stripped[len(label):].strip()
                lines += ["", f"{replacement}  {title}" if title else replacement]
                replaced = True
                break
        if not replaced and stripped:
            lines.append(stripped)
    lines += ["", "<i>Research by 5-Bereich System</i>"]
    return "\n".join(lines)


def _format_msg4(part4: str, today: str) -> str:
    field_map = {
        "TICKER":     ("🎯", "Ticker"),
        "RICHTUNG":   ("📍", "Richtung"),
        "EINSTIEG":   ("💰", "Einstieg"),
        "ZIEL":       ("🏁", "Ziel"),
        "STOP":       ("🛑", "Stop"),
        "POSITION":   ("📦", "Position (1000€)"),
        "GRUND":      ("📝", "Grund"),
        "KATALYSATOR":("⚡", "Katalysator"),
    }
    lines = [f"⚡️ <b>Trade-Idee des Tages — {today}</b>", "━━━━━━━━━━━━━━━━━━━━", ""]
    for raw in part4.strip().splitlines():
        stripped = raw.strip()
        matched = False
        for key, (emoji, label) in field_map.items():
            if stripped.upper().startswith(f"{key}:"):
                value = stripped[len(key)+1:].strip()
                lines.append(f"{emoji} <b>{label}:</b>  {value}")
                matched = True
                break
        if not matched and stripped:
            lines.append(stripped)
    return "\n".join(lines)


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
