"""
Episodic Pivot Screener
========================
Pipeline:
1. Polygon grouped daily → alle Stocks mit Gap-up > 10%
2. Finnhub earnings calendar ±1 Tag → Katalysator
3. Finnhub company news (24h) → News-Katalysator
4. Volume: relatives Volumen > 2× 20T-Schnitt via yfinance
5. Base-Check: ATR-Kontraktion vor dem Gap
6. Score 0–10, Alert wenn Score ≥ 5
7. Invest-Vorschlag: Safe Play (IB) + YOLO Play (TR)
"""

import os
import logging
import httpx
import numpy as np
import pandas as pd
import yfinance as yf
from math import log, sqrt, erf
from datetime import date, timedelta, datetime, timezone
from app.services.warrant_finder import _bs_delta, RISK_FREE_RATE

logger = logging.getLogger(__name__)

MIN_GAP_PCT      = 0.10
MIN_REL_VOL      = 2.0
MIN_PRICE        = 5.0
MAX_TICKER_LEN   = 5
TOP_N_POLYGON    = 100   # Top-N nach Volumen aus Polygon
MIN_SCORE        = 5.0
EP_KAPITAL       = float(os.environ.get("EP_KAPITAL", "1000"))
SAFE_RISK_PCT    = 0.05
YOLO_RISK_PCT    = 0.10


# ── Polygon ───────────────────────────────────────────────────────────────────

def _get_polygon_daily(target: date) -> list[dict]:
    api_key = os.environ.get("MASSIVE_API_KEY", "")
    try:
        r = httpx.get(
            f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{target}",
            params={"apiKey": api_key, "adjusted": "true"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        logger.warning("Polygon grouped daily %s failed: %s", target, e)
        return []


def _find_gap_ups(today: date) -> list[dict]:
    """Vergleiche heutigen Open mit gestrigem Close via Polygon."""
    yesterday = today - timedelta(days=1)
    if yesterday.weekday() == 5:
        yesterday -= timedelta(days=1)
    elif yesterday.weekday() == 6:
        yesterday -= timedelta(days=2)

    today_data    = _get_polygon_daily(today)
    yesterday_data = _get_polygon_daily(yesterday)

    prev_close = {r["T"]: r["c"] for r in yesterday_data if r.get("T") and r.get("c")}

    gaps = []
    for r in today_data:
        ticker = r.get("T", "")
        if not (1 <= len(ticker) <= MAX_TICKER_LEN and ticker.isalpha()):
            continue
        if r.get("c", 0) < MIN_PRICE:
            continue
        prev = prev_close.get(ticker)
        if not prev or prev <= 0:
            continue
        gap_pct = (r["o"] - prev) / prev   # open vs prev close
        if gap_pct >= MIN_GAP_PCT:
            gaps.append({
                "ticker":   ticker,
                "gap_pct":  round(gap_pct, 4),
                "open":     r["o"],
                "close":    r["c"],
                "low":      r["l"],
                "volume":   r["v"],
                "prev_close": prev,
            })

    gaps.sort(key=lambda x: x["gap_pct"], reverse=True)
    return gaps[:TOP_N_POLYGON]


# ── Finnhub ───────────────────────────────────────────────────────────────────

def _finnhub_earnings(ticker: str, today: date) -> dict | None:
    """Prüft ob Earnings ±1 Tag um today für ticker."""
    token = os.environ.get("FINNHUB_API_KEY", "")
    from_d = (today - timedelta(days=1)).isoformat()
    to_d   = (today + timedelta(days=1)).isoformat()
    try:
        r = httpx.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"symbol": ticker, "from": from_d, "to": to_d, "token": token},
            timeout=8,
        )
        r.raise_for_status()
        items = r.json().get("earningsCalendar", [])
        if items:
            item = items[0]
            eps_actual   = item.get("epsActual")
            eps_estimate = item.get("epsEstimate")
            if eps_actual is not None and eps_estimate and eps_estimate != 0:
                surprise = round((eps_actual - eps_estimate) / abs(eps_estimate) * 100, 1)
                return {"detail": f"EPS Surprise {surprise:+.1f}%", "surprise_pct": surprise}
            return {"detail": "Earnings reported", "surprise_pct": None}
    except Exception as e:
        logger.debug("Finnhub earnings %s: %s", ticker, e)
    return None


def _finnhub_news(ticker: str, today: date) -> str | None:
    """Holt neueste Schlagzeile aus den letzten 24h."""
    token = os.environ.get("FINNHUB_API_KEY", "")
    from_d = (today - timedelta(days=1)).isoformat()
    to_d   = today.isoformat()
    try:
        r = httpx.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": from_d, "to": to_d, "token": token},
            timeout=8,
        )
        r.raise_for_status()
        items = r.json()
        if items:
            return items[0].get("headline", "")[:80]
    except Exception as e:
        logger.debug("Finnhub news %s: %s", ticker, e)
    return None


# ── yfinance: Volume + Base ───────────────────────────────────────────────────

def _yf_analysis(ticker: str) -> dict | None:
    """Holt 60T daily OHLCV. Berechnet rel. Vol + ATR-Kontraktion."""
    try:
        df = yf.download(ticker, period="60d", interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 22:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.rename(columns={"Close": "close", "High": "high",
                                  "Low": "low", "Volume": "volume"})

        # Relatives Volumen: letzter Tag vs. 20T-Schnitt
        vol_today = float(df["volume"].iloc[-1])
        vol_avg20 = float(df["volume"].iloc[-21:-1].mean())
        rel_vol   = round(vol_today / vol_avg20, 2) if vol_avg20 > 0 else 0.0

        # ATR-Kontraktion: ATR(5) der letzten 5T vs. ATR(20) der letzten 20T
        high = df["high"].values
        low  = df["low"].values
        close = df["close"].values

        def atr_n(n: int) -> float:
            trs = [max(high[-i]-low[-i], abs(high[-i]-close[-i-1]),
                       abs(low[-i]-close[-i-1])) for i in range(1, n+1)]
            return float(np.mean(trs))

        atr5  = atr_n(5)
        atr20 = atr_n(20)
        # Base-Tage: wie lange war ATR unter 60% des heutigen ATR
        base_days = 0
        for i in range(2, min(len(df), 40)):
            day_atr = max(high[-i]-low[-i], abs(high[-i]-close[-i-1]),
                          abs(low[-i]-close[-i-1]))
            if day_atr < atr5 * 1.5:
                base_days += 1
            else:
                break

        info   = yf.Ticker(ticker).info
        mcap   = info.get("marketCap", 0)
        mcap_str = (f"${mcap/1e12:.1f}T" if mcap >= 1e12
                    else f"${mcap/1e9:.1f}B" if mcap >= 1e9
                    else f"${mcap/1e6:.0f}M")

        return {
            "rel_vol":   rel_vol,
            "atr5":      round(atr5, 4),
            "atr20":     round(atr20, 4),
            "base_days": base_days,
            "price":     round(float(close[-1]), 2),
            "prev_low":  round(float(low[-2]), 2),
            "name":      info.get("longName") or info.get("shortName") or ticker,
            "sector":    info.get("sector") or "–",
            "mcap":      mcap_str,
        }
    except Exception as e:
        logger.warning("yf_analysis %s: %s", ticker, e)
        return None


# ── Score ─────────────────────────────────────────────────────────────────────

def _calc_score(gap_pct: float, rel_vol: float, base_days: int,
                catalyst: str) -> tuple[float, str]:
    score = 0.0
    if catalyst == "Earnings":
        score += 3
    elif catalyst == "News":
        score += 2

    if rel_vol >= 3.0:
        score += 2
    elif rel_vol >= 2.0:
        score += 1

    if base_days >= 20:
        score += 2
    elif base_days >= 10:
        score += 1

    gap_abs = gap_pct
    if 0.10 <= gap_abs <= 0.20:
        score += 2
    elif gap_abs > 0.20:
        score += 1

    if score >= 9:
        comment = "Perfektes Setup — alle Signale grün."
    elif score >= 7:
        comment = "Guter Trend, solide Basis."
    else:
        comment = "Hohes Risiko, aber im Marktfluss."

    return round(score, 1), comment


# ── Invest Proposal ───────────────────────────────────────────────────────────

def _invest_proposal(price: float, lotd_stop: float, kapital: float) -> dict:
    stop_pct = (price - lotd_stop) / price if price > lotd_stop > 0 else 0.05

    # Safe Play (IB) — Aktie
    safe_budget   = kapital * SAFE_RISK_PCT
    safe_shares   = max(1, int(safe_budget / (price * stop_pct))) if stop_pct > 0 else 1
    safe_cost     = round(safe_shares * price, 2)
    safe_max_loss = round(safe_shares * (price - lotd_stop), 2)
    safe_target   = round(safe_cost * 0.20, 2)

    # YOLO Play (TR) — Optionsschein
    yolo_budget = round(kapital * YOLO_RISK_PCT, 2)

    # Use fixed vol of 0.30 as default (avoids incorrect yf.download usage)
    vol = 0.30

    delta_mid  = _bs_delta(price, price * 1.05, 0.5, vol, is_call=True)
    delta_low  = round(max(0.10, delta_mid - 0.08), 2)
    delta_high = round(min(0.90, delta_mid + 0.08), 2)
    yolo_target = round(yolo_budget * 2.0, 2)

    return {
        "kapital":             kapital,
        "safe_play_shares":    safe_shares,
        "safe_play_cost":      safe_cost,
        "safe_play_max_loss":  safe_max_loss,
        "safe_play_target_gain": safe_target,
        "yolo_play_budget":    yolo_budget,
        "yolo_play_delta_low": delta_low,
        "yolo_play_delta_high": delta_high,
        "yolo_play_target_gain": yolo_target,
    }


# ── Telegram Message ──────────────────────────────────────────────────────────

def _build_ep_message(c: dict, proposal: dict) -> str:
    today = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    # gap_pct in candidate dict is already a percentage value (e.g. 12.5 for 12.5%)
    gap_str = f"+{c['gap_pct']:.1f}%"
    score_icon = "🔥" if c["score"] >= 7 else "⚡"
    score_label = "STARK" if c["score"] >= 7 else "SOLIDE" if c["score"] >= 5 else "RISKANT"
    cat_icon = "📊" if c["catalyst"] == "Earnings" else "📰"

    earn_ok  = "✓" if c["catalyst"] == "Earnings" else "✗"
    vol_ok   = "✓" if c["rel_vol"] >= 2.0 else "✗"
    base_lbl = f"lang ({c['base_days']}T)" if c["base_days"] >= 20 else f"kurz ({c['base_days']}T)"

    return (
        f"🚀 <b>YOLO STRATEGIE BUY</b>  —  {today}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>{c['ticker']}</b>  ·  {c['name']}\n"
        f"{cat_icon} Katalysator: {c['catalyst_detail']}\n"
        f"📊 Gap-up: <b>{gap_str}</b>  |  Vol: <b>{c['rel_vol']}×</b> Schnitt\n"
        f"🏦 {c['mcap']}  ·  {c['sector']}\n\n"
        f"── ENTRY ──────────────────\n"
        f"⏱ Morgen 9:30 ET — ORB-Einstieg\n"
        f"📐 Entry-Zone: <b>${c['entry_zone_low']:.2f} – ${c['entry_zone_high']:.2f}</b>\n"
        f"🛑 Stop: <b>${c['lotd_stop']:.2f}</b>  (LOTD)\n\n"
        f"── SAFE PLAY (IB) ──────────\n"
        f"📈 Aktie direkt\n"
        f"💰 Position: <b>{proposal['safe_play_shares']} Stück</b>  ≈ €{proposal['safe_play_cost']:.0f}\n"
        f"⚠️  Max Verlust: <b>€{proposal['safe_play_max_loss']:.0f}</b>  (5% von €{proposal['kapital']:.0f})\n"
        f"🎯 Ziel +20%: €{proposal['safe_play_target_gain']:.0f} Gewinn\n\n"
        f"── YOLO PLAY (TR) ──────────\n"
        f"🎰 Optionsschein CALL\n"
        f"💰 Budget: <b>€{proposal['yolo_play_budget']:.0f}</b>  (10% von €{proposal['kapital']:.0f})\n"
        f"🔧 Delta {proposal['yolo_play_delta_low']:.2f}–{proposal['yolo_play_delta_high']:.2f}  ·  6M  ·  Hebel ~10×\n"
        f"🎯 Ziel: +20% Aktie → ~+200% Schein → €{proposal['yolo_play_target_gain']:.0f}\n\n"
        f"── RISIKO-AMPEL ────────────\n"
        f"{'🟢' if earn_ok == '✓' else '🔴'} Katalysator: {c['catalyst']} {earn_ok}\n"
        f"{'🟢' if vol_ok == '✓' else '🟡'} Volumen: {c['rel_vol']}× {vol_ok}\n"
        f"🟡 Base: {base_lbl}\n"
        f"🟢 Gap-Größe: {gap_str}\n\n"
        f"{score_icon} Score: <b>{c['score']}/10</b>  —  {score_label}\n"
        f"<i>{c['score_comment']}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


# ── Main Scan ─────────────────────────────────────────────────────────────────

def scan_ep(today: date | None = None) -> dict:
    if today is None:
        today = date.today()

    gaps = _find_gap_ups(today)
    candidates = []
    proposals  = {}

    for g in gaps:
        ticker = g["ticker"]
        yf_data = _yf_analysis(ticker)
        if not yf_data:
            continue
        if yf_data["rel_vol"] < MIN_REL_VOL:
            continue

        earnings = _finnhub_earnings(ticker, today)
        if earnings:
            catalyst        = "Earnings"
            catalyst_detail = earnings["detail"]
        else:
            news_headline = _finnhub_news(ticker, today)
            if news_headline:
                catalyst        = "News"
                catalyst_detail = news_headline
            else:
                catalyst        = "Unknown"
                catalyst_detail = "Kein Katalysator verifiziert"

        score, comment = _calc_score(
            g["gap_pct"], yf_data["rel_vol"], yf_data["base_days"], catalyst
        )
        if score < MIN_SCORE:
            continue

        entry_low  = round(g["open"], 2)
        entry_high = round(g["open"] * 1.005, 2)
        lotd_stop  = yf_data["prev_low"]

        c = {
            "ticker":           ticker,
            "name":             yf_data["name"],
            "sector":           yf_data["sector"],
            "mcap":             yf_data["mcap"],
            "gap_pct":          round(g["gap_pct"] * 100, 2),
            "rel_vol":          yf_data["rel_vol"],
            "catalyst":         catalyst,
            "catalyst_detail":  catalyst_detail,
            "base_days":        yf_data["base_days"],
            "score":            score,
            "score_comment":    comment,
            "entry_zone_low":   entry_low,
            "entry_zone_high":  entry_high,
            "lotd_stop":        lotd_stop,
            "price":            yf_data["price"],
            "date":             today.isoformat(),
        }
        candidates.append(c)
        proposals[ticker] = _invest_proposal(
            yf_data["price"], lotd_stop, EP_KAPITAL
        )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return {
        "candidates": candidates,
        "proposals":  proposals,
        "timestamp":  datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
    }


async def send_ep_alert() -> dict:
    import httpx as _httpx
    data = scan_ep()
    if not data["candidates"]:
        return {"sent": False, "reason": "No EP candidates today"}

    token   = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError("Telegram credentials missing")

    sent = 0
    async with _httpx.AsyncClient() as client:
        for c in data["candidates"][:3]:   # max 3 Alerts pro Tag
            proposal = data["proposals"].get(c["ticker"], {})
            text = _build_ep_message(c, proposal)
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            resp.raise_for_status()
            sent += 1

    return {
        "sent":       True,
        "count":      sent,
        "candidates": [c["ticker"] for c in data["candidates"][:3]],
    }
