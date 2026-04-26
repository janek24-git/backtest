"""
Optionsschein-Finder
Generiert gefilterte Such-Links für Calls/Puts auf deutschen Börsenplattformen.
Direkte Buttons in Telegram statt fragile API-Calls.
"""

import logging
import yfinance as yf
from datetime import datetime, timezone
from urllib.parse import quote

logger = logging.getLogger(__name__)

TARGET_LEVERAGE = "8-12"


def _get_isin(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        return info.get("isin") or ""
    except Exception:
        return ""


def _get_price(ticker: str) -> float:
    try:
        info = yf.Ticker(ticker).info
        return float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
    except Exception:
        return 0.0


def build_warrant_links(ticker: str, direction: str) -> dict:
    """
    Gibt Such-Links für Calls/Puts auf großen deutschen Plattformen zurück.
    direction: "LONG" → CALL | "SHORT" → PUT
    """
    call_put   = "CALL" if direction.upper() == "LONG" else "PUT"
    cp_lower   = call_put.lower()
    isin       = _get_isin(ticker)
    price      = _get_price(ticker)

    links = {
        "comdirect": (
            f"https://www.comdirect.de/inf/derivate/warrants.html?"
            f"UNDERLYING_ISIN={isin}&CALL_PUT={call_put}"
            if isin else
            f"https://www.comdirect.de/inf/derivate/warrants.html?UNDERLYING_SEARCH={ticker}&CALL_PUT={call_put}"
        ),
        "onvista": (
            f"https://www.onvista.de/hebelprodukte/suche/?"
            f"underlyingIsin={isin}&derivateType={call_put}_WARRANT"
            if isin else
            f"https://www.onvista.de/hebelprodukte/suche/?searchValue={ticker}&derivateType={call_put}_WARRANT"
        ),
        "boerse_frankfurt": (
            f"https://www.boerse-frankfurt.de/derivate?"
            f"searchTerms={ticker}&type={call_put}&category=Optionsschein"
        ),
        "finanzen_net": (
            f"https://www.finanzen.net/hebelprodukte/optionsscheine/{ticker.lower()}-{cp_lower}-optionsscheine"
        ),
    }

    return {
        "ticker":    ticker,
        "direction": direction.upper(),
        "call_put":  call_put,
        "isin":      isin,
        "price":     round(price, 2),
        "links":     links,
    }


def build_warrant_message(ticker: str, direction: str, target_pct: float,
                           budget: float = 1000.0) -> str:
    """Telegram-Nachricht mit Such-Links als klickbare Buttons."""
    data     = build_warrant_links(ticker, direction)
    today    = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    icon     = "🟢" if direction.upper() == "LONG" else "🔴"
    cp       = data["call_put"]

    price_str = f"{data['price']}€" if data["price"] else "–"

    lines = [
        f"🎰 <b>Optionsschein-Finder — {today}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"{icon} <b>{ticker}</b>  ·  {cp}  ·  Ziel: +{target_pct:.0f}%",
        f"Kurs: {price_str}  ·  Budget: {budget:.0f}€",
        "",
        f"Empfehlung: <b>Hebel {TARGET_LEVERAGE}x</b>, Fälligkeit <b>3-9 Monate</b>",
        f"",
        "Klicke zum Suchen:",
        f'· <a href="{data["links"]["comdirect"]}">comdirect Derivate</a>',
        f'· <a href="{data["links"]["onvista"]}">Onvista {cp}s</a>',
        f'· <a href="{data["links"]["boerse_frankfurt"]}">Börse Frankfurt</a>',
        f'· <a href="{data["links"]["finanzen_net"]}">finanzen.net</a>',
        "",
        "⚠️ Optionsscheine = Totalverlust möglich.",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)


def build_warrant_buttons(ticker: str, direction: str) -> dict:
    """Telegram inline_keyboard mit Such-Buttons."""
    data    = build_warrant_links(ticker, direction)
    cp      = data["call_put"]
    links   = data["links"]
    return {
        "inline_keyboard": [
            [
                {"text": f"📋 comdirect {cp}s", "url": links["comdirect"]},
                {"text": f"📊 Onvista",          "url": links["onvista"]},
            ],
            [
                {"text": f"🏛 Börse Frankfurt",  "url": links["boerse_frankfurt"]},
                {"text": f"📰 finanzen.net",     "url": links["finanzen_net"]},
            ],
        ]
    }
