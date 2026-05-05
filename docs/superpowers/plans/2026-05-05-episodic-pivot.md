# Episodic Pivot Screener + Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Episodic Pivot (EP) strategy to the existing platform — daily Telegram screener at 20:00 UTC and a 10-year backtest with a new frontend tab.

**Architecture:** New `ep_scanner.py` + `ep_backtest.py` services follow the exact same patterns as `telegram_alerts.py` and `big5_engine.py`. A new `ep.py` router registers under `/ep`. Frontend adds `/ep` route with `EPPage.tsx` alongside the existing Big5Page.

**Tech Stack:** FastAPI, Python 3.14, yfinance, httpx, Polygon.io, Finnhub, Black-Scholes (math stdlib), React + TypeScript + Vite, Axios, TradingView Lightweight Charts v5.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `backend/app/services/ep_scanner.py` | Gap screening, score, invest proposal, Telegram message |
| Create | `backend/app/services/ep_backtest.py` | 10-year backtest engine (2016–2026) |
| Create | `backend/app/routers/ep.py` | API routes: /ep/scan, /ep/backtest, /ep/alert |
| Modify | `backend/app/main.py` | Register ep router |
| Modify | `backend/app/models/schemas.py` | Add EP Pydantic schemas |
| Create | `.github/workflows/ep-alert.yml` | Cron 20:00 UTC Mo-Fr |
| Create | `frontend/src/pages/EPPage.tsx` | EP Scanner + Backtest tab |
| Modify | `frontend/src/api/client.ts` | Add EP API functions |
| Modify | `frontend/src/App.tsx` | Add /ep route |

---

## Task 1: Pydantic Schemas

**Files:**
- Modify: `backend/app/models/schemas.py`

- [ ] **Step 1: Add EP schemas at end of file**

```python
# ── Episodic Pivot ─────────────────────────────────────────────────────────────

class EPCandidate(BaseModel):
    ticker: str
    name: str
    sector: str
    mcap: str
    gap_pct: float           # Gap-up % (open vs prev close)
    rel_vol: float           # Relatives Volumen vs 20T-Schnitt
    catalyst: str            # "Earnings", "News", "Unknown"
    catalyst_detail: str     # Earnings EPS detail oder News-Titel
    base_days: int           # Tage in Konsolidierung vor Gap
    score: float             # 0–10
    score_comment: str
    entry_zone_low: float    # Tages-Open als ORB-Proxy
    entry_zone_high: float   # Open + 0.5%
    lotd_stop: float         # Tages-Low (vorheriger Tag als Proxy)
    price: float
    date: str


class EPInvestProposal(BaseModel):
    kapital: float
    safe_play_shares: int
    safe_play_cost: float
    safe_play_max_loss: float
    safe_play_target_gain: float
    yolo_play_budget: float
    yolo_play_delta_low: float
    yolo_play_delta_high: float
    yolo_play_target_gain: float


class EPScanResponse(BaseModel):
    candidates: list[EPCandidate]
    proposals: dict[str, EPInvestProposal]   # ticker → proposal
    timestamp: str


class EPBacktestRequest(BaseModel):
    from_date: str = "2016-01-01"
    to_date: str = "2026-01-01"
    min_gap_pct: float = 0.10
    min_rel_vol: float = 2.0
    require_earnings: bool = False


class EPBacktestTrade(BaseModel):
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    stop_price: float
    gap_pct: float
    rel_vol: float
    catalyst: str
    hold_days: int
    perf_pct: float
    hit_stop: bool


class EPBacktestMetrics(BaseModel):
    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    expectancy: float
    sharpe: float
    max_drawdown: float
    total_return: float
    pead_5d: float    # avg return after 5 trading days
    pead_20d: float   # avg return after 20 trading days


class EPBacktestResponse(BaseModel):
    trades: list[EPBacktestTrade]
    metrics: EPBacktestMetrics
    from_date: str
    to_date: str
```

- [ ] **Step 2: Verify schemas import cleanly**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate
python -c "from app.models.schemas import EPCandidate, EPBacktestResponse; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/schemas.py
git commit -m "feat(ep): add Pydantic schemas for EP screener and backtest"
```

---

## Task 2: EP Scanner Service

**Files:**
- Create: `backend/app/services/ep_scanner.py`

- [ ] **Step 1: Write ep_scanner.py**

```python
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
    try:
        df = yf.download(price, period="30d", interval="1d",
                         progress=False, auto_adjust=True)
        closes = df["Close"].dropna().values.astype(float) if not df.empty else []
        if len(closes) >= 5:
            rets   = np.diff(np.log(closes[-30:]))
            vol    = float(np.std(rets, ddof=1) * sqrt(252))
        else:
            vol = 0.30
    except Exception:
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
    gap_str = f"+{c['gap_pct']*100:.1f}%"
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
```

- [ ] **Step 2: Quick syntax check**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate
python -c "from app.services.ep_scanner import scan_ep; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/ep_scanner.py
git commit -m "feat(ep): add EP scanner service with Polygon + Finnhub + invest proposal"
```

---

## Task 3: EP Backtest Engine

**Files:**
- Create: `backend/app/services/ep_backtest.py`

- [ ] **Step 1: Write ep_backtest.py**

```python
"""
Episodic Pivot Backtest Engine — 2016–2026
==========================================
Datenquellen:
- yfinance daily OHLCV (10 Jahre, kein API-Limit)
- S&P500-Constituents (aktuelle Liste als Proxy)
- Finnhub earnings history für Katalysator-Check

Entry: Tages-Open + 0.1% Slippage (ORB-Proxy)
Stop:  Tages-Low
Exit:  Nach 20 Handelstagen ODER Stop getroffen
"""

import logging
import os
import httpx
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

logger = logging.getLogger(__name__)

HOLD_DAYS  = 20     # Maximale Haltedauer Handelstage
SLIPPAGE   = 0.001  # 0.1% Slippage auf Entry


def _get_sp500_tickers() -> list[str]:
    """Holt aktuelle S&P500-Ticker von Wikipedia."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        )
        return tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception as e:
        logger.warning("SP500 fetch failed: %s", e)
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
                "JPM", "V", "UNH", "XOM", "MA", "AVGO", "PG", "HD"]


def _fetch_ohlcv(ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
    try:
        df = yf.download(ticker, start=from_date, end=to_date,
                         progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.rename(columns={
            "Open": "open", "High": "high",
            "Low": "low",   "Close": "close", "Volume": "volume"
        })
        df.index = pd.to_datetime(df.index).date
        return df.dropna()
    except Exception:
        return pd.DataFrame()


def _check_finnhub_earnings_history(ticker: str, event_date: date) -> bool:
    """Prüft ob Earnings ±2 Tage um event_date."""
    token = os.environ.get("FINNHUB_API_KEY", "")
    from_d = (event_date - timedelta(days=2)).isoformat()
    to_d   = (event_date + timedelta(days=2)).isoformat()
    try:
        r = httpx.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"symbol": ticker, "from": from_d, "to": to_d, "token": token},
            timeout=8,
        )
        r.raise_for_status()
        return len(r.json().get("earningsCalendar", [])) > 0
    except Exception:
        return False


def _find_gap_events(df: pd.DataFrame, min_gap: float) -> list[dict]:
    """Findet alle Gap-up > min_gap im DataFrame."""
    events = []
    closes = df["close"].values
    opens  = df["open"].values
    dates  = list(df.index)
    for i in range(1, len(df)):
        if closes[i-1] <= 0:
            continue
        gap = (opens[i] - closes[i-1]) / closes[i-1]
        if gap >= min_gap:
            events.append({
                "idx":        i,
                "date":       dates[i],
                "gap_pct":    round(gap * 100, 2),
                "open":       opens[i],
                "low":        df["low"].values[i],
                "prev_close": closes[i-1],
            })
    return events


def _calc_rel_vol(df: pd.DataFrame, idx: int) -> float:
    if idx < 21:
        return 0.0
    vol_today = float(df["volume"].values[idx])
    vol_avg   = float(np.mean(df["volume"].values[idx-20:idx]))
    return round(vol_today / vol_avg, 2) if vol_avg > 0 else 0.0


def _simulate_trade(df: pd.DataFrame, entry_idx: int) -> dict:
    """
    Entry: open[entry_idx] * (1 + SLIPPAGE)
    Stop:  low[entry_idx]
    Exit:  nach HOLD_DAYS oder Stop getroffen
    """
    closes = df["close"].values
    lows   = df["low"].values
    dates  = list(df.index)

    entry_price = float(df["open"].values[entry_idx]) * (1 + SLIPPAGE)
    stop_price  = float(lows[entry_idx])
    n = len(df)

    for j in range(1, HOLD_DAYS + 1):
        idx = entry_idx + j
        if idx >= n:
            # End of data — exit at last close
            exit_price = float(closes[n-1])
            exit_date  = dates[n-1]
            hit_stop   = False
            break
        if lows[idx] <= stop_price:
            exit_price = stop_price
            exit_date  = dates[idx]
            hit_stop   = True
            break
        if j == HOLD_DAYS:
            exit_price = float(closes[idx])
            exit_date  = dates[idx]
            hit_stop   = False

    perf_pct = round((exit_price - entry_price) / entry_price * 100, 4)
    hold_days = (exit_date - dates[entry_idx]).days

    return {
        "entry_price": round(entry_price, 4),
        "exit_price":  round(exit_price, 4),
        "stop_price":  round(stop_price, 4),
        "exit_date":   str(exit_date),
        "hold_days":   hold_days,
        "perf_pct":    perf_pct,
        "hit_stop":    hit_stop,
    }


def _pead_avg(df: pd.DataFrame, entry_idx: int, days: int) -> float | None:
    closes = df["close"].values
    entry  = float(df["open"].values[entry_idx]) * (1 + SLIPPAGE)
    target_idx = entry_idx + days
    if target_idx >= len(closes):
        return None
    return round((float(closes[target_idx]) - entry) / entry * 100, 4)


def _calc_metrics(trades: list[dict]) -> dict:
    if not trades:
        return {
            "num_trades": 0, "win_rate": 0.0,
            "avg_win": 0.0,  "avg_loss": 0.0,
            "expectancy": 0.0, "sharpe": 0.0,
            "max_drawdown": 0.0, "total_return": 0.0,
            "pead_5d": 0.0, "pead_20d": 0.0,
        }

    returns   = [t["perf_pct"] for t in trades]
    winners   = [r for r in returns if r > 0]
    losers    = [r for r in returns if r <= 0]
    win_rate  = len(winners) / len(returns) * 100
    avg_win   = float(np.mean(winners)) if winners else 0.0
    avg_loss  = float(np.mean(losers))  if losers  else 0.0
    expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)

    arr    = np.array(returns) / 100
    excess = arr - 0.02 / 252
    sharpe = float(np.sqrt(252) * excess.mean() / excess.std()) if excess.std() > 0 else 0.0

    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = max(max_dd, (peak - v) / peak * 100)

    pead5  = [t.get("pead_5d")  for t in trades if t.get("pead_5d")  is not None]
    pead20 = [t.get("pead_20d") for t in trades if t.get("pead_20d") is not None]

    return {
        "num_trades":    len(trades),
        "win_rate":      round(win_rate, 2),
        "avg_win":       round(avg_win, 4),
        "avg_loss":      round(avg_loss, 4),
        "expectancy":    round(expectancy, 4),
        "sharpe":        round(sharpe, 4),
        "max_drawdown":  round(-max_dd, 4),
        "total_return":  round(sum(returns), 4),
        "pead_5d":       round(float(np.mean(pead5)),  4) if pead5  else 0.0,
        "pead_20d":      round(float(np.mean(pead20)), 4) if pead20 else 0.0,
    }


def run_ep_backtest(
    from_date: str = "2016-01-01",
    to_date: str   = "2026-01-01",
    min_gap_pct: float = 0.10,
    min_rel_vol: float = 2.0,
    require_earnings: bool = False,
    max_tickers: int = 100,
) -> dict:
    tickers = _get_sp500_tickers()[:max_tickers]
    all_trades: list[dict] = []

    for ticker in tickers:
        df = _fetch_ohlcv(ticker, from_date, to_date)
        if df.empty or len(df) < 25:
            continue

        events = _find_gap_events(df, min_gap_pct / 100 if min_gap_pct > 1 else min_gap_pct)
        for ev in events:
            idx = ev["idx"]
            rel_vol = _calc_rel_vol(df, idx)
            if rel_vol < min_rel_vol:
                continue

            catalyst = "Unknown"
            if require_earnings:
                has_earnings = _check_finnhub_earnings_history(ticker, ev["date"])
                if not has_earnings:
                    continue
                catalyst = "Earnings"

            trade = _simulate_trade(df, idx)
            trade.update({
                "ticker":     ticker,
                "entry_date": str(ev["date"]),
                "gap_pct":    ev["gap_pct"],
                "rel_vol":    rel_vol,
                "catalyst":   catalyst,
                "pead_5d":    _pead_avg(df, idx, 5),
                "pead_20d":   _pead_avg(df, idx, 20),
            })
            all_trades.append(trade)

        logger.info("EP backtest %s: %d gap events", ticker, len(events))

    metrics = _calc_metrics(all_trades)
    return {
        "trades":    all_trades,
        "metrics":   metrics,
        "from_date": from_date,
        "to_date":   to_date,
    }
```

- [ ] **Step 2: Syntax check**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate
python -c "from app.services.ep_backtest import run_ep_backtest; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/ep_backtest.py
git commit -m "feat(ep): add EP backtest engine (2016-2026, S&P500, yfinance)"
```

---

## Task 4: EP Router

**Files:**
- Create: `backend/app/routers/ep.py`

- [ ] **Step 1: Write ep.py**

```python
import logging
from fastapi import APIRouter, HTTPException, Query
from app.services.ep_scanner import scan_ep, send_ep_alert
from app.services.ep_backtest import run_ep_backtest
from app.models.schemas import EPScanResponse, EPBacktestRequest, EPBacktestResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scan", response_model=EPScanResponse)
def ep_scan():
    """Heutiger EP-Scan: Gap-ups > 10% mit Score ≥ 5."""
    try:
        data = scan_ep()
        return EPScanResponse(**data)
    except Exception as e:
        logger.exception("EP scan failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alert")
async def ep_alert():
    """Trigger EP Telegram Alert (täglich via GitHub Actions)."""
    try:
        return await send_ep_alert()
    except Exception as e:
        logger.exception("EP alert failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest", response_model=EPBacktestResponse)
def ep_backtest(req: EPBacktestRequest):
    """EP Backtest 2016–2026 auf S&P500-Universum."""
    try:
        data = run_ep_backtest(
            from_date=req.from_date,
            to_date=req.to_date,
            min_gap_pct=req.min_gap_pct,
            min_rel_vol=req.min_rel_vol,
            require_earnings=req.require_earnings,
        )
        trades  = data["trades"]
        metrics = data["metrics"]
        return EPBacktestResponse(
            trades=[t for t in trades],
            metrics=metrics,
            from_date=req.from_date,
            to_date=req.to_date,
        )
    except Exception as e:
        logger.exception("EP backtest failed")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 2: Register in main.py**

In `backend/app/main.py`, add after the journal router line:

```python
from app.routers import backtest, universe, big5, journal, ep   # add ep

# and below the journal include_router line:
app.include_router(ep.router, prefix="/ep", tags=["ep"])
```

- [ ] **Step 3: Start backend and test endpoints**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

In a second terminal:
```bash
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}

curl -s http://localhost:8000/ep/scan | python3 -m json.tool | head -30
# Expected: JSON with candidates array
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/ep.py backend/app/main.py
git commit -m "feat(ep): add EP router and register in main.py"
```

---

## Task 5: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/ep-alert.yml`

- [ ] **Step 1: Write workflow**

```yaml
name: EP Scanner (täglich 22 Uhr MESZ)

on:
  schedule:
    # 20:00 UTC = 22:00 MESZ Mo-Fr
    - cron: '0 20 * * 1-5'
  workflow_dispatch:

jobs:
  ep-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger EP Alert
        run: |
          curl -s -X POST \
            "https://stocks-backtest-api-production-0c6a.up.railway.app/ep/alert" \
            --max-time 120 \
            -w "\nHTTP %{http_code}\n"
```

- [ ] **Step 2: Add FINNHUB_API_KEY to Railway env**

In Railway dashboard → Environment Variables → Add:
```
FINNHUB_API_KEY=d7t66f1r01qugn09gve0d7t66f1r01qugn09gveg
EP_KAPITAL=1000
```

- [ ] **Step 3: Commit and push**

```bash
git add .github/workflows/ep-alert.yml
git commit -m "feat(ep): add GitHub Actions workflow for daily EP alert at 20:00 UTC"
git push
```

- [ ] **Step 4: Verify workflow appears in GitHub Actions**

```bash
gh workflow list
# Expected: ep-alert.yml in list
```

---

## Task 6: Frontend Types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Read existing types file**

```bash
cat /Users/janekstrobel/stocks-backtest/frontend/src/types/index.ts
```

- [ ] **Step 2: Add EP types at end of file**

```typescript
// ── Episodic Pivot ────────────────────────────────────────────────────────────

export interface EPInvestProposal {
  kapital: number;
  safe_play_shares: number;
  safe_play_cost: number;
  safe_play_max_loss: number;
  safe_play_target_gain: number;
  yolo_play_budget: number;
  yolo_play_delta_low: number;
  yolo_play_delta_high: number;
  yolo_play_target_gain: number;
}

export interface EPCandidate {
  ticker: string;
  name: string;
  sector: string;
  mcap: string;
  gap_pct: number;
  rel_vol: number;
  catalyst: string;
  catalyst_detail: string;
  base_days: number;
  score: number;
  score_comment: string;
  entry_zone_low: number;
  entry_zone_high: number;
  lotd_stop: number;
  price: number;
  date: string;
}

export interface EPScanResponse {
  candidates: EPCandidate[];
  proposals: Record<string, EPInvestProposal>;
  timestamp: string;
}

export interface EPBacktestTrade {
  ticker: string;
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  stop_price: number;
  gap_pct: number;
  rel_vol: number;
  catalyst: string;
  hold_days: number;
  perf_pct: number;
  hit_stop: boolean;
}

export interface EPBacktestMetrics {
  num_trades: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  expectancy: number;
  sharpe: number;
  max_drawdown: number;
  total_return: number;
  pead_5d: number;
  pead_20d: number;
}

export interface EPBacktestResponse {
  trades: EPBacktestTrade[];
  metrics: EPBacktestMetrics;
  from_date: string;
  to_date: string;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(ep): add TypeScript types for EP screener and backtest"
```

---

## Task 7: Frontend API Client Functions

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add EP API functions at end of client.ts**

```typescript
import type {
  BacktestResponse, AIAnalysis,
  Big5BacktestResponse, Big5AnalysisResponse,
  EPScanResponse, EPBacktestResponse,   // add these
} from '../types';

// ... existing functions unchanged ...

export async function scanEP(): Promise<EPScanResponse> {
  const { data } = await api.get<EPScanResponse>('/ep/scan');
  return data;
}

export async function runEPBacktest(
  fromDate: string = '2016-01-01',
  toDate: string = '2026-01-01',
  minGapPct: number = 0.10,
  minRelVol: number = 2.0,
  requireEarnings: boolean = false,
): Promise<EPBacktestResponse> {
  const { data } = await api.post<EPBacktestResponse>('/ep/backtest', {
    from_date: fromDate,
    to_date: toDate,
    min_gap_pct: minGapPct,
    min_rel_vol: minRelVol,
    require_earnings: requireEarnings,
  });
  return data;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(ep): add scanEP and runEPBacktest API client functions"
```

---

## Task 8: Frontend EPPage

**Files:**
- Create: `frontend/src/pages/EPPage.tsx`

- [ ] **Step 1: Write EPPage.tsx**

```tsx
import { useState } from 'react';
import { scanEP, runEPBacktest } from '../api/client';
import type { EPScanResponse, EPBacktestResponse, EPCandidate } from '../types';

type Tab = 'scanner' | 'backtest';

function ScoreBar({ score }: { score: number }) {
  const color = score >= 7 ? '#22c55e' : score >= 5 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: `${score * 10}%`, height: 6,
        background: color, borderRadius: 3,
        transition: 'width 0.3s',
      }} />
      <span style={{ color, fontWeight: 600 }}>{score}/10</span>
    </div>
  );
}

function CandidateCard({ c, proposal }: {
  c: EPCandidate;
  proposal?: { safe_play_shares: number; safe_play_cost: number; safe_play_max_loss: number; yolo_play_budget: number; yolo_play_delta_low: number; yolo_play_delta_high: number };
}) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      background: '#1a1a2e', border: '1px solid #333',
      borderRadius: 8, padding: 16, marginBottom: 12,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
           onClick={() => setOpen(o => !o)}>
        <div>
          <span style={{ fontWeight: 700, fontSize: 18, color: '#e2e8f0' }}>{c.ticker}</span>
          <span style={{ color: '#94a3b8', marginLeft: 8 }}>{c.name}</span>
          <span style={{
            marginLeft: 12, padding: '2px 8px', borderRadius: 4,
            background: c.catalyst === 'Earnings' ? '#166534' : '#1e3a5f',
            color: '#fff', fontSize: 12,
          }}>{c.catalyst}</span>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <span style={{ color: '#22c55e', fontWeight: 600 }}>+{c.gap_pct}%</span>
          <span style={{ color: '#94a3b8' }}>Vol {c.rel_vol}×</span>
          <ScoreBar score={c.score} />
          <span style={{ color: '#94a3b8' }}>{open ? '▲' : '▼'}</span>
        </div>
      </div>

      {open && (
        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 4 }}>ENTRY</div>
            <div>Zone: <b>${c.entry_zone_low.toFixed(2)} – ${c.entry_zone_high.toFixed(2)}</b></div>
            <div>Stop: <b style={{ color: '#ef4444' }}>${c.lotd_stop.toFixed(2)}</b> (LOTD)</div>
            <div style={{ marginTop: 8, color: '#94a3b8', fontSize: 12 }}>{c.catalyst_detail}</div>
            <div style={{ marginTop: 8, fontStyle: 'italic', color: '#64748b' }}>{c.score_comment}</div>
          </div>
          {proposal && (
            <div>
              <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 4 }}>INVEST-VORSCHLAG (€{proposal.safe_play_cost < 1000 ? '1.000' : '1.000'})</div>
              <div style={{ marginBottom: 8 }}>
                <span style={{ color: '#22c55e', fontWeight: 600 }}>Safe Play (IB)</span>
                <div>{proposal.safe_play_shares} Stück · €{proposal.safe_play_cost} · Max Loss €{proposal.safe_play_max_loss}</div>
              </div>
              <div>
                <span style={{ color: '#f59e0b', fontWeight: 600 }}>YOLO Play (TR)</span>
                <div>€{proposal.yolo_play_budget} · Call · Delta {proposal.yolo_play_delta_low.toFixed(2)}–{proposal.yolo_play_delta_high.toFixed(2)} · 6M</div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{
      background: '#1a1a2e', border: '1px solid #333',
      borderRadius: 8, padding: 16, textAlign: 'center',
    }}>
      <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0' }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: 11, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export function EPPage() {
  const [tab, setTab] = useState<Tab>('scanner');
  const [scanData, setScanData]       = useState<EPScanResponse | null>(null);
  const [btData,   setBtData]         = useState<EPBacktestResponse | null>(null);
  const [loading, setLoading]         = useState(false);
  const [error,   setError]           = useState<string | null>(null);
  const [requireEarnings, setRequireEarnings] = useState(false);

  async function handleScan() {
    setLoading(true); setError(null);
    try { setScanData(await scanEP()); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function handleBacktest() {
    setLoading(true); setError(null);
    try { setBtData(await runEPBacktest('2016-01-01', '2026-01-01', 0.10, 2.0, requireEarnings)); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  const m = btData?.metrics;

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24, fontFamily: 'monospace', color: '#e2e8f0' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>EP Scanner</h1>
      <p style={{ color: '#64748b', marginBottom: 24 }}>Episodic Pivot — Gap-up {'>'} 10% mit Katalysator</p>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {(['scanner', 'backtest'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
            background: tab === t ? '#3b82f6' : '#1e293b',
            color: '#fff', fontWeight: tab === t ? 700 : 400,
          }}>{t === 'scanner' ? 'Heutiger Scan' : '10J Backtest'}</button>
        ))}
      </div>

      {/* Scanner Tab */}
      {tab === 'scanner' && (
        <div>
          <button onClick={handleScan} disabled={loading} style={{
            padding: '10px 24px', borderRadius: 6, border: 'none',
            background: '#3b82f6', color: '#fff', cursor: 'pointer',
            fontWeight: 600, marginBottom: 20,
          }}>{loading ? 'Scanne...' : 'Scan starten'}</button>

          {error && <div style={{ color: '#ef4444', marginBottom: 12 }}>{error}</div>}

          {scanData && (
            <div>
              <div style={{ color: '#64748b', marginBottom: 16 }}>
                {scanData.candidates.length} Kandidaten · {scanData.timestamp}
              </div>
              {scanData.candidates.length === 0
                ? <div style={{ color: '#64748b' }}>Heute keine EP-Kandidaten (Score {'<'} 5)</div>
                : scanData.candidates.map(c => (
                  <CandidateCard
                    key={c.ticker}
                    c={c}
                    proposal={scanData.proposals[c.ticker]}
                  />
                ))
              }
            </div>
          )}
        </div>
      )}

      {/* Backtest Tab */}
      {tab === 'backtest' && (
        <div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 20 }}>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
              <input type="checkbox" checked={requireEarnings}
                     onChange={e => setRequireEarnings(e.target.checked)} />
              Nur Earnings-Katalysator
            </label>
            <button onClick={handleBacktest} disabled={loading} style={{
              padding: '10px 24px', borderRadius: 6, border: 'none',
              background: '#3b82f6', color: '#fff', cursor: 'pointer', fontWeight: 600,
            }}>{loading ? 'Berechne...' : 'Backtest 2016–2026'}</button>
          </div>

          {error && <div style={{ color: '#ef4444', marginBottom: 12 }}>{error}</div>}

          {m && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
                <MetricCard label="Trades" value={String(m.num_trades)} />
                <MetricCard label="Win Rate" value={`${m.win_rate.toFixed(1)}%`} />
                <MetricCard label="Expectancy" value={`${m.expectancy.toFixed(2)}%`} sub="pro Trade" />
                <MetricCard label="Sharpe" value={m.sharpe.toFixed(2)} />
                <MetricCard label="Max DD" value={`${m.max_drawdown.toFixed(1)}%`} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
                <MetricCard label="Avg Win" value={`+${m.avg_win.toFixed(2)}%`} />
                <MetricCard label="Avg Loss" value={`${m.avg_loss.toFixed(2)}%`} />
                <MetricCard label="PEAD +5T" value={`${m.pead_5d.toFixed(2)}%`} sub="Ø nach 5 Tagen" />
                <MetricCard label="PEAD +20T" value={`${m.pead_20d.toFixed(2)}%`} sub="Ø nach 20 Tagen" />
              </div>

              {/* Trade Table */}
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #333', color: '#64748b' }}>
                      {['Ticker','Entry','Exit','Gap%','RelVol','Catalyst','Hold','Perf%','Stop hit'].map(h => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {btData!.trades.slice(0, 100).map((t, i) => (
                      <tr key={i} style={{
                        borderBottom: '1px solid #1e293b',
                        color: t.perf_pct > 0 ? '#22c55e' : '#ef4444',
                      }}>
                        <td style={{ padding: '6px 12px', fontWeight: 700 }}>{t.ticker}</td>
                        <td style={{ padding: '6px 12px' }}>{t.entry_date}</td>
                        <td style={{ padding: '6px 12px' }}>{t.exit_date}</td>
                        <td style={{ padding: '6px 12px' }}>+{t.gap_pct}%</td>
                        <td style={{ padding: '6px 12px' }}>{t.rel_vol}×</td>
                        <td style={{ padding: '6px 12px' }}>{t.catalyst}</td>
                        <td style={{ padding: '6px 12px' }}>{t.hold_days}d</td>
                        <td style={{ padding: '6px 12px', fontWeight: 700 }}>{t.perf_pct > 0 ? '+' : ''}{t.perf_pct.toFixed(2)}%</td>
                        <td style={{ padding: '6px 12px' }}>{t.hit_stop ? '🛑' : '–'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {btData!.trades.length > 100 && (
                  <div style={{ color: '#64748b', marginTop: 8, fontSize: 12 }}>
                    Zeige 100 von {btData!.trades.length} Trades
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/EPPage.tsx
git commit -m "feat(ep): add EPPage with scanner + backtest tab"
```

---

## Task 9: Wire Frontend Route

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add EP route**

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { StockDetail } from './pages/StockDetail';
import { Big5Page } from './pages/Big5Page';
import { JournalPage } from './pages/JournalPage';
import { EPPage } from './pages/EPPage';   // add this
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Big5Page />} />
        <Route path="/screener" element={<Dashboard />} />
        <Route path="/stock/:ticker" element={<StockDetail />} />
        <Route path="/big5" element={<Big5Page />} />
        <Route path="/journal" element={<JournalPage />} />
        <Route path="/ep" element={<EPPage />} />   {/* add this */}
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Add EP tab link in Big5Page nav (or add a shared Nav component)**

In `frontend/src/pages/Big5Page.tsx`, find the navigation/header area and add a link. Look for existing nav links and add alongside them:

```tsx
// Existing nav pattern — find where other page links are and add:
<a href="/ep" style={{ color: '#94a3b8', textDecoration: 'none', padding: '6px 12px' }}>
  EP Scanner
</a>
```

- [ ] **Step 3: Start frontend and verify**

```bash
cd /Users/janekstrobel/stocks-backtest/frontend
npm run dev
# Open http://localhost:5200/ep
# Expected: EP Scanner page loads with two tabs
```

- [ ] **Step 4: Commit and push**

```bash
git add frontend/src/App.tsx frontend/src/pages/Big5Page.tsx
git commit -m "feat(ep): wire /ep route and add nav link"
git push
```

---

## Self-Review

**Spec coverage check:**
- ✅ EP Screener täglich 20:00 UTC → Task 5 (workflow)
- ✅ Gap > 10% + Polygon → Task 2 (`_find_gap_ups`)
- ✅ Finnhub earnings ±1T → Task 2 (`_finnhub_earnings`)
- ✅ Finnhub news → Task 2 (`_finnhub_news`)
- ✅ Volume > 2× + Base-Check → Task 2 (`_yf_analysis`)
- ✅ Score 0–10, threshold ≥ 5 → Task 2 (`_calc_score`)
- ✅ Score-Kommentar → Task 2 (in `_calc_score`)
- ✅ Safe Play 5% Kapital (IB) → Task 2 (`_invest_proposal`)
- ✅ YOLO Play 10% Kapital (TR) → Task 2 (`_invest_proposal`)
- ✅ Telegram "YOLO STRATEGIE BUY" → Task 2 (`_build_ep_message`)
- ✅ Backtest 2016–2026 S&P500 → Task 3
- ✅ PEAD +5T / +20T Metrics → Task 3
- ✅ Frontend neuer Tab EP Scanner → Task 8
- ✅ Frontend Backtest Tab mit Metrics → Task 8
- ✅ Nav-Link → Task 9
- ✅ `EP_KAPITAL` ENV default 1000 → Task 2 + Task 5
- ✅ `FINNHUB_API_KEY` in env → Task 1 (.env already updated)
