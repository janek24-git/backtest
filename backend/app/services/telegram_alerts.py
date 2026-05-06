"""
Telegram EMA-Alert Service

Pipeline:
1. Polygon grouped daily → alle US-Stocks nach Volumen heute
2. Filter: Preis > $10, Ticker 1-5 Zeichen (keine ETF-Ketten, keine Optionen)
3. Top 50 nach absolutem Volumen
4. yfinance: EMA200 berechnen + relatives Volumen (heute vs. 20T-Schnitt)
5. Alert nur bei: bullishes EMA200-Crossover UND rel. Volumen > 1.5×
6. Big 5 immer geprüft (ohne Volumenfilter)
"""

import os
import logging
import httpx
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

logger = logging.getLogger(__name__)

BIG5 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
EMA_PERIOD = 200
FETCH_DAYS = 600
MIN_PRICE = 10.0
MAX_TICKER_LEN = 5
TOP_N_BY_VOLUME = 50
REL_VOL_THRESHOLD = 1.5  # 1.5× 20-Tage-Schnitt = Volumenspike


# ── EMA ───────────────────────────────────────────────────────────────────────

def _calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    k = 2.0 / (period + 1)
    vals = prices.values
    result = np.full(len(vals), np.nan)
    if len(vals) < period:
        return pd.Series(result, index=prices.index)
    result[period - 1] = vals[:period].mean()
    for i in range(period, len(vals)):
        result[i] = vals[i] * k + result[i - 1] * (1 - k)
    return pd.Series(result, index=prices.index)


# ── Polygon: Top-Volumen-Stocks heute ────────────────────────────────────────

def _get_polygon_top_volume(n: int = TOP_N_BY_VOLUME) -> list[str]:
    """
    Holt alle US-Stocks von gestern via Polygon grouped daily,
    filtert und gibt Top-N nach Volumen zurück.
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "")
    if not api_key:
        logger.warning("MASSIVE_API_KEY not set")
        return []

    # Letzten Handelstag bestimmen (Freitag wenn Wochenende)
    today = date.today()
    target = today - timedelta(days=1)
    if target.weekday() == 5:   # Samstag
        target -= timedelta(days=1)
    elif target.weekday() == 6:  # Sonntag
        target -= timedelta(days=2)

    try:
        r = httpx.get(
            f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{target}",
            params={"apiKey": api_key, "adjusted": "true"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
    except Exception as e:
        logger.warning("Polygon grouped daily failed: %s", e)
        return []

    # Filter: Preis > $10, Ticker 1–5 Zeichen (keine Leerzeichen, keine Punkte)
    filtered = [
        r for r in results
        if r.get("c", 0) >= MIN_PRICE
        and 1 <= len(r.get("T", "")) <= MAX_TICKER_LEN
        and r.get("T", "").isalpha()
        and r.get("v", 0) > 0
    ]

    # Top N nach Volumen
    top = sorted(filtered, key=lambda x: x["v"], reverse=True)[:n]
    tickers = [r["T"] for r in top]
    logger.info("Polygon top %d volume stocks: %s", len(tickers), tickers[:10])
    return tickers


# ── Stock-Info ────────────────────────────────────────────────────────────────

def _fetch_stock_info(ticker: str) -> dict:
    """Name, Sektor, MarktKap, Short-Ratio via yfinance."""
    try:
        info = yf.Ticker(ticker).info
        mcap = info.get("marketCap", 0)
        if mcap >= 1e12:
            mcap_str = f"${mcap/1e12:.1f}T"
        elif mcap >= 1e9:
            mcap_str = f"${mcap/1e9:.1f}B"
        else:
            mcap_str = f"${mcap/1e6:.0f}M"
        return {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector") or "–",
            "industry": info.get("industry") or "–",
            "mcap": mcap_str,
            "short_ratio": info.get("shortRatio") or 0,
        }
    except Exception:
        return {"name": ticker, "sector": "–", "industry": "–", "mcap": "–", "short_ratio": 0}


# ── yfinance: EMA200 + relatives Volumen ─────────────────────────────────────

def _fetch_ohlcv(ticker: str, from_date: str) -> pd.DataFrame:
    raw = yf.download(ticker, start=from_date, progress=False, auto_adjust=True)
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)
    df = raw[["Close", "Volume"]].copy()
    df.columns = ["close", "volume"]
    df.index = pd.to_datetime(df.index).date
    return df


def _analyze_ticker(ticker: str, check_vol_spike: bool = True) -> dict | None:
    """
    Gibt Signal-Dict zurück wenn bullishes EMA200-Crossover vorliegt,
    optional mit Volumenspike-Filter.
    Gibt None zurück wenn kein Signal.
    """
    from_date = (date.today() - timedelta(days=FETCH_DAYS)).isoformat()
    try:
        df = _fetch_ohlcv(ticker, from_date)
        if df is None or len(df) < EMA_PERIOD + 2:
            return None

        df["ema200"] = _calculate_ema(df["close"], EMA_PERIOD)
        df = df.dropna(subset=["ema200"])

        if len(df) < 22:
            return None

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        prev_above = prev["close"] > prev["ema200"]
        curr_above = curr["close"] > curr["ema200"]

        # Nur bullishes Crossover
        if prev_above or not curr_above:
            return None

        close = float(curr["close"])
        ema = float(curr["ema200"])
        pct_above = round((close - ema) / ema * 100, 2)

        # Relatives Volumen: heute vs. 20T-Schnitt
        vol_today = float(curr["volume"])
        vol_avg20 = float(df["volume"].iloc[-21:-1].mean())
        rel_vol = round(vol_today / vol_avg20, 2) if vol_avg20 > 0 else 0.0

        if check_vol_spike and rel_vol < REL_VOL_THRESHOLD:
            return None

        info = _fetch_stock_info(ticker)
        return {
            "ticker": ticker,
            "name": info["name"],
            "sector": info["sector"],
            "industry": info["industry"],
            "mcap": info["mcap"],
            "short_ratio": info["short_ratio"],
            "close": round(close, 2),
            "ema200": round(ema, 2),
            "pct_above": pct_above,
            "rel_vol": rel_vol,
            "date": str(df.index[-1]),
        }
    except Exception as e:
        logger.warning("Analyze %s failed: %s", ticker, e)
        return None


# ── Telegram ──────────────────────────────────────────────────────────────────

def _format_signal(s: dict, label: str = "") -> str:
    short_line = f"\n📉 Short-Ratio  {s['short_ratio']}×" if s.get("short_ratio", 0) >= 3 else ""
    shares_1k = int(1000 / s["close"]) if s["close"] > 0 else 0
    cost_1k = round(shares_1k * s["close"], 0)
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>{s['ticker']}</b>  ·  {s['name']}\n"
        f"🏭 {s['sector']}  ·  {s['mcap']}\n"
        f"\n"
        f"📈 Close      <b>${s['close']}</b>\n"
        f"〰️ EMA200     ${s['ema200']}\n"
        f"📐 Abstand    <b>+{s['pct_above']}%</b>\n"
        f"🔊 Volumen    <b>{s['rel_vol']}×</b> Schnitt{short_line}\n"
        f"💰 Pos. €1k   <b>{shares_1k} Stück</b>  ≈ €{cost_1k:.0f}\n"
        f"📅 {s['date']}"
    )


def _build_message(big5_signals: list[dict], market_signals: list[dict]) -> str:
    today = date.today().strftime("%d.%m.%Y")
    lines = [f"🔔 <b>EMA200 Bullish Signal</b>  —  {today}", ""]

    if big5_signals:
        lines.append("⭐ <b>Big 5</b>")
        for s in big5_signals:
            lines.append(_format_signal(s, "big5"))
        lines.append("")

    if market_signals:
        lines.append("🌍 <b>Markt  ·  Vol-Spike + Crossover</b>")
        for s in market_signals:
            lines.append(_format_signal(s, "market"))

    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()


async def send_telegram_alert() -> dict:
    """
    Hauptfunktion:
    - Big 5 immer prüfen (kein Volumenfilter)
    - Top-50-Volumen-Stocks via Polygon mit Volumenspike-Filter
    - Nur senden wenn mindestens ein bullishes Signal
    """
    # Big 5 ohne Volumenfilter
    big5_signals = []
    for ticker in BIG5:
        sig = _analyze_ticker(ticker, check_vol_spike=False)
        if sig:
            big5_signals.append(sig)

    # Markt-Kandidaten via Polygon
    candidates = _get_polygon_top_volume()
    # Big5 nicht doppelt auswerten
    candidates = [t for t in candidates if t not in BIG5]

    market_signals = []
    for ticker in candidates:
        sig = _analyze_ticker(ticker, check_vol_spike=True)
        if sig:
            market_signals.append(sig)

    # Auto-save signals as forward trades
    from app.services.forward_db import add_trade as _add_forward
    for sig in big5_signals:
        try:
            _add_forward(ticker=sig["ticker"], signal_date=sig["date"], entry_price=sig["close"],
                         ema200=sig["ema200"], tp_pct=10.0, sl_pct=5.0, source="BIG5",
                         rel_vol=sig.get("rel_vol"), pct_above_ema=sig.get("pct_above"))
        except Exception:
            pass
    for sig in market_signals:
        try:
            _add_forward(ticker=sig["ticker"], signal_date=sig["date"], entry_price=sig["close"],
                         ema200=sig["ema200"], tp_pct=10.0, sl_pct=5.0, source="MARKET",
                         rel_vol=sig.get("rel_vol"), pct_above_ema=sig.get("pct_above"))
        except Exception:
            pass

    total = len(big5_signals) + len(market_signals)
    if total == 0:
        return {"sent": False, "signals": 0, "message": "No bullish crossovers today"}

    text = _build_message(big5_signals, market_signals)
    await _send_telegram(text)

    return {
        "sent": True,
        "signals": total,
        "big5": big5_signals,
        "market": market_signals,
    }


def get_current_status() -> list[dict]:
    """EMA200-Status der Big 5 (für den /ema-status Endpoint)."""
    from_date = (date.today() - timedelta(days=FETCH_DAYS)).isoformat()
    status = []
    for ticker in BIG5:
        try:
            df = _fetch_ohlcv(ticker, from_date)
            if df is None or len(df) < EMA_PERIOD:
                continue
            df["ema200"] = _calculate_ema(df["close"], EMA_PERIOD)
            df = df.dropna(subset=["ema200"])
            if df.empty:
                continue
            curr = df.iloc[-1]
            close = float(curr["close"])
            ema = float(curr["ema200"])
            status.append({
                "ticker": ticker,
                "close": round(close, 2),
                "ema200": round(ema, 2),
                "above": close > ema,
                "pct_from_ema": round((close - ema) / ema * 100, 2),
                "date": str(df.index[-1]),
            })
        except Exception as e:
            logger.warning("Status error %s: %s", ticker, e)
    return status
