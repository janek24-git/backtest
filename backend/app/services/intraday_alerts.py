"""
Intraday EMA200 Alerts — DE40 + US100
Timeframes: 30m / 1h / 12h
Nur Alert bei frischem Crossover (bullish oder bearish)
"""

import os
import logging
import httpx
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

INDICES = {
    "DE40":  "^GDAXI",
    "US100": "^NDX",
}

TIMEFRAMES = {
    "30m":  {"interval": "30m",  "period": "60d",  "ema": 200},
    "1h":   {"interval": "1h",   "period": "60d",  "ema": 200},
    "12h":  {"interval": "1d",   "period": "2y",   "ema": 50},   # 1d candles, EMA50 ≈ 50 Handelstage ≈ ~12h×50
}

# Für 12h nutzen wir EMA50 auf Tagesdaten — das entspricht ~50 Handelstagen Trend


def _calc_ema(prices: pd.Series, period: int) -> pd.Series:
    k = 2.0 / (period + 1)
    vals = prices.values
    result = np.full(len(vals), np.nan)
    if len(vals) < period:
        return pd.Series(result, index=prices.index)
    result[period - 1] = vals[:period].mean()
    for i in range(period, len(vals)):
        result[i] = vals[i] * k + result[i - 1] * (1 - k)
    return pd.Series(result, index=prices.index)


def _fetch_intraday(symbol: str, interval: str, period: str) -> pd.DataFrame:
    raw = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)
    df = raw[["Close"]].copy()
    df.columns = ["close"]
    df = df.dropna()
    return df


def check_intraday_crossovers() -> list[dict]:
    signals = []

    for name, symbol in INDICES.items():
        for tf_label, cfg in TIMEFRAMES.items():
            try:
                df = _fetch_intraday(symbol, cfg["interval"], cfg["period"])
                if df is None or len(df) < cfg["ema"] + 2:
                    logger.warning("%s %s: not enough data", name, tf_label)
                    continue

                df["ema"] = _calc_ema(df["close"], cfg["ema"])
                df = df.dropna(subset=["ema"])

                if len(df) < 2:
                    continue

                prev = df.iloc[-2]
                curr = df.iloc[-1]

                prev_above = float(prev["close"]) > float(prev["ema"])
                curr_above = float(curr["close"]) > float(curr["ema"])

                if prev_above == curr_above:
                    continue  # kein Crossover

                direction = "bullish" if curr_above else "bearish"
                close = round(float(curr["close"]), 2)
                ema_val = round(float(curr["ema"]), 2)
                pct = round((close - ema_val) / ema_val * 100, 2)
                ts = curr.name
                if hasattr(ts, 'strftime'):
                    ts_str = ts.strftime("%d.%m.%Y %H:%M")
                else:
                    ts_str = str(ts)

                signals.append({
                    "index": name,
                    "symbol": symbol,
                    "timeframe": tf_label,
                    "direction": direction,
                    "close": close,
                    "ema": ema_val,
                    "pct": pct,
                    "timestamp": ts_str,
                })
                logger.info("%s %s %s crossover @ %s", name, tf_label, direction, close)

            except Exception as e:
                logger.warning("%s %s error: %s", name, tf_label, e)

    return signals


def _build_intraday_message(signals: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    lines = [f"📊 <b>Intraday EMA Signal</b>  —  {today}", ""]

    for s in signals:
        icon = "🟢" if s["direction"] == "bullish" else "🔴"
        direction_text = "ÜBER EMA" if s["direction"] == "bullish" else "UNTER EMA"
        pct_str = f"+{s['pct']}%" if s["pct"] >= 0 else f"{s['pct']}%"
        lines.append(
            f"{icon} <b>{s['index']}</b>  ·  {s['timeframe']} Timeframe\n"
            f"   {direction_text}  ({pct_str})\n"
            f"   Kurs: <b>{s['close']:,.0f}</b>  |  EMA: {s['ema']:,.0f}\n"
            f"   {s['timestamp']}"
        )
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def send_intraday_alert() -> dict:
    signals = check_intraday_crossovers()
    if not signals:
        return {"sent": False, "signals": 0}

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError("Telegram credentials missing")

    text = _build_intraday_message(signals)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()

    return {"sent": True, "signals": len(signals), "crossovers": signals}
