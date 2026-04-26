"""
Optionsschein-Finder
Sucht passende Calls/Puts für eine Trade-Idee.
Quellen: Société Générale → Boerse Frankfurt (Fallback)
"""

import logging
import httpx
import yfinance as yf
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# SG Zertifikate öffentliche Produkt-API
SG_SEARCH = "https://sg-zertifikate.de/Api/ProductSearch"
# Boerse Frankfurt Derivate-Suche als Fallback
BF_SEARCH  = "https://api.boerse-frankfurt.de/v1/search/derivative_search"

TARGET_LEVERAGE = 10.0   # Wunsch-Hebel
MIN_LEVERAGE    = 4.0
MAX_LEVERAGE    = 20.0


def _get_price(ticker: str) -> float:
    try:
        info = yf.Ticker(ticker).info
        return float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
    except Exception:
        return 0.0


def _search_sg(ticker: str, option_type: str) -> list[dict]:
    """Société Générale Produktsuche."""
    try:
        resp = httpx.get(
            SG_SEARCH,
            params={
                "underlyingName": ticker,
                "productType":    "warrant",
                "optionType":     option_type,   # "call" / "put"
                "pageSize":       30,
                "sortBy":         "leverage",
            },
            headers={"User-Agent": "Mozilla/5.0 WarrantBot/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("products") or data.get("items") or data.get("data") or []
        return raw
    except Exception as e:
        logger.warning("SG API failed for %s: %s", ticker, e)
        return []


def _search_boerse_frankfurt(ticker: str, option_type: str) -> list[dict]:
    """Boerse Frankfurt Derivate-Fallback."""
    try:
        resp = httpx.get(
            BF_SEARCH,
            params={
                "searchTerms": ticker,
                "category":    "Optionsschein",
                "type":        option_type,
                "pageSize":    30,
            },
            headers={"User-Agent": "Mozilla/5.0 WarrantBot/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("data") or data.get("results") or []
        return raw
    except Exception as e:
        logger.warning("BF API failed for %s: %s", ticker, e)
        return []


def _parse_product(p: dict, option_type: str, budget: float) -> dict | None:
    """Normalisiert ein Rohprodukt aus verschiedenen Quellen."""
    leverage = (
        p.get("leverage") or p.get("hebel") or
        p.get("Leverage") or p.get("gearing") or 0
    )
    price = (
        p.get("ask") or p.get("askPrice") or
        p.get("price") or p.get("lastPrice") or 0
    )
    wkn = (
        p.get("wkn") or p.get("WKN") or
        p.get("isin") or p.get("ISIN") or ""
    )
    strike = (
        p.get("strike") or p.get("strikePrice") or
        p.get("basispreis") or p.get("exercisePrice") or 0
    )
    maturity = (
        p.get("expiryDate") or p.get("maturity") or
        p.get("expiry") or p.get("Expiry") or ""
    )
    issuer = (
        p.get("issuer") or p.get("emittent") or
        p.get("Issuer") or "SG"
    )

    try:
        leverage = float(leverage)
        price    = float(price)
    except (TypeError, ValueError):
        return None

    if not (MIN_LEVERAGE <= leverage <= MAX_LEVERAGE):
        return None
    if price <= 0:
        return None

    shares = int(budget / price)
    return {
        "wkn":      wkn,
        "type":     option_type.upper(),
        "issuer":   issuer,
        "leverage": round(leverage, 1),
        "price":    round(price, 2),
        "strike":   round(float(strike), 2) if strike else 0.0,
        "maturity": maturity[:10] if maturity else "–",
        "shares":   shares,
        "cost":     round(shares * price, 2),
    }


def find_warrants(ticker: str, direction: str, budget: float = 1000.0) -> list[dict]:
    """
    Findet die 3 besten Optionsscheine für einen Trade.
    direction: "LONG" → Call | "SHORT" → Put
    """
    option_type = "call" if direction.upper() == "LONG" else "put"

    raw = _search_sg(ticker, option_type)
    if not raw:
        raw = _search_boerse_frankfurt(ticker, option_type)

    products = []
    for p in raw:
        parsed = _parse_product(p, option_type, budget)
        if parsed:
            products.append(parsed)

    # Sortiert: nächster Hebel zu Ziel-Hebel (10x)
    products.sort(key=lambda x: abs(x["leverage"] - TARGET_LEVERAGE))
    return products[:3]


def build_warrant_message(ticker: str, direction: str, target_pct: float,
                           budget: float = 1000.0) -> str:
    """Fertige Telegram-Nachricht für Optionsschein-Empfehlung."""
    warrants = find_warrants(ticker, direction, budget)
    today    = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    icon     = "🟢" if direction.upper() == "LONG" else "🔴"

    if not warrants:
        return (
            f"🎰 <b>Optionsschein — {ticker}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Keine passenden Scheine gefunden (API nicht erreichbar).\n"
            f"Manuell suchen: sg-zertifikate.de · derivate.comdirect.de"
        )

    lines = [
        f"🎰 <b>Optionsschein-Finder — {today}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"{icon} Underlying: <b>{ticker}</b>  ·  {direction}  ·  Ziel: +{target_pct:.0f}%",
        f"Budget: {budget:.0f}€",
        "",
    ]

    for i, w in enumerate(warrants, 1):
        expected = round(w["leverage"] * target_pct, 1)
        lines += [
            f"<b>{i}. {w['type']} — WKN: {w['wkn']}</b>  [{w['issuer']}]",
            f"   Hebel: {w['leverage']}x  ·  Strike: {w['strike']}  ·  Fällig: {w['maturity']}",
            f"   Kurs: <b>{w['price']}€</b>  →  {w['shares']} Stück  ({w['cost']}€)",
            f"   Erwarteter Gewinn bei +{target_pct:.0f}%: ~<b>+{expected:.0f}%</b>",
            "",
        ]

    lines.append("⚠️ Optionsscheine = Totalverlust möglich. Nur Risikokapital.")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
