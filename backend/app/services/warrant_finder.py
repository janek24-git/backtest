"""
Optionsschein-Finder
Generiert gefilterte Such-Links für Calls/Puts auf deutschen Börsenplattformen.
Direkte Buttons in Telegram statt fragile API-Calls.
"""

import logging
import numpy as np
import yfinance as yf
from math import log, sqrt, erf
from datetime import datetime, timezone
from urllib.parse import quote

logger = logging.getLogger(__name__)

TARGET_LEVERAGE = "8-12"
RISK_FREE_RATE  = 0.04   # ~4% EUR Risikoloser Zinssatz


# ── Black-Scholes ──────────────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    """Standard-Normalverteilung CDF via math.erf."""
    return 0.5 * (1.0 + erf(x / sqrt(2)))


def _bs_delta(S: float, K: float, T: float, sigma: float, is_call: bool = True) -> float:
    """Black-Scholes Delta für Call oder Put."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.5
    d1 = (log(S / K) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    delta = _norm_cdf(d1)
    return round(delta if is_call else delta - 1.0, 2)


def get_delta_profile(ticker: str, direction: str) -> dict:
    """
    Berechnet Black-Scholes Delta für ATM / 5% OTM / 10% OTM
    bei 3M / 6M / 9M Laufzeit. Historische 30-Tage-Vol als IV-Proxy.
    """
    is_call = direction.upper() == "LONG"
    try:
        df = yf.download(ticker, period="90d", interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty:
            raise ValueError("No data")
        if isinstance(df.columns, __import__("pandas").MultiIndex):
            df.columns = df.columns.droplevel(1)
        closes = df["Close"].dropna().values.flatten().astype(float)
        if len(closes) < 5:
            raise ValueError("Not enough data")
        price  = float(closes[-1])
        rets   = np.diff(np.log(closes))
        sample = rets[-30:] if len(rets) >= 30 else rets
        vol    = float(np.std(sample, ddof=1) * sqrt(252))
    except Exception as e:
        logger.warning("Delta profile failed for %s: %s", ticker, e)
        return {}

    maturities  = {"3M": 3/12, "6M": 6/12, "9M": 9/12}
    moneynesses = {"ATM (0%)": 1.0, "5% OTM": 1.05 if is_call else 0.95,
                   "10% OTM": 1.10 if is_call else 0.90}

    table: dict[str, dict[str, float]] = {}
    for m_label, moneyness in moneynesses.items():
        K = price * moneyness
        table[m_label] = {
            t_label: _bs_delta(price, K, T, vol, is_call)
            for t_label, T in maturities.items()
        }

    # Empfohlener Delta-Bereich (5% OTM, 6M = guter Hebel-Kompromiss)
    target_delta = table["5% OTM"]["6M"]
    delta_range  = (round(target_delta - 0.08, 2), round(target_delta + 0.08, 2))

    return {
        "price":       round(price, 2),
        "vol_30d":     round(vol * 100, 1),
        "table":       table,
        "target":      target_delta,
        "delta_range": delta_range,
    }


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
    """Telegram-Nachricht mit Delta-Tabelle + Such-Links."""
    data     = build_warrant_links(ticker, direction)
    dp       = get_delta_profile(ticker, direction)
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
    ]

    # Delta-Tabelle
    if dp:
        dr = dp["delta_range"]
        risk_labels = {
            "ATM (0%)":  ("🟢 Low Risk",    "sicherer, weniger Hebel"),
            "5% OTM":    ("🟡 Mid Risk",    "Empfehlung — guter Kompromiss"),
            "10% OTM":   ("🔴 High Risk",   "mehr Hebel, Aktie muss mehr laufen"),
        }
        lines += [
            f"<b>Delta-Guide</b>  (IV: ~{dp['vol_30d']}% 30d-Vol)",
            "",
        ]
        for m_label, row in dp["table"].items():
            risk, hint = risk_labels.get(m_label, ("·", ""))
            lines += [
                f"{risk}  <b>{m_label}</b>  —  {hint}",
                f"  Delta:  3M {row['3M']:.2f}  ·  6M {row['6M']:.2f}  ·  9M {row['9M']:.2f}",
                "",
            ]
        lines += [
            f"🎯 TR-Filter: <b>Delta {dr[0]:.2f} – {dr[1]:.2f}</b>  (Mid Risk · 6M · Hebel {TARGET_LEVERAGE}x)",
            "",
        ]
    else:
        lines += [
            f"Empfehlung: <b>Delta 0.35–0.50</b>  ·  Hebel {TARGET_LEVERAGE}x  ·  6M",
            "",
        ]

    lines += [
        "Suchen auf:",
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
