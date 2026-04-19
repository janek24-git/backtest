# Backtesting Platform — Design Spec
**Date:** 2026-04-19
**Status:** Approved

---

## Overview

Web-based backtesting platform for EMA200 strategy on NAS100 universe (Top5/10/20). FastAPI backend + React frontend. Local-first, deployable. Foundation for future strategies and AI-driven analysis.

---

## Architecture

```
stocks-backtest/
├── backend/                        # FastAPI (Python)
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── backtest.py         # POST /backtest/run, GET /backtest/results/{id}
│   │   │   └── universe.py         # GET /universe/nas100?size=5|10|20
│   │   ├── services/
│   │   │   ├── data_fetcher.py     # Massive API wrapper + Parquet cache
│   │   │   ├── backtest_engine.py  # EMA calc, signal gen, metrics
│   │   │   ├── universe.py         # NAS100 constituent lists
│   │   │   └── ai_analyst.py       # Claude API integration
│   │   └── models/
│   │       └── schemas.py          # Pydantic models
│   ├── cache/                      # Parquet matrix (Date × Ticker)
│   ├── .env                        # MASSIVE_API_KEY, ANTHROPIC_API_KEY
│   └── requirements.txt
│
└── frontend/                       # React + Vite + TypeScript
    ├── src/
    │   ├── pages/
    │   │   ├── Dashboard.tsx       # Main view
    │   │   └── StockDetail.tsx     # Per-ticker deep dive
    │   ├── components/
    │   │   ├── UniverseSelector.tsx # Top5 / Top10 / Top20
    │   │   ├── PeriodSelector.tsx   # 1M 3M 6M 1Y 3Y 5Y ALL
    │   │   ├── ResultsTable.tsx     # AG Grid
    │   │   ├── CandleChart.tsx      # TradingView Lightweight Charts
    │   │   ├── TradeHistory.tsx     # Per-stock trade log
    │   │   └── OptimizationBook.tsx # Tab: param grid + AI analysis
    │   └── api/
    │       └── client.ts            # Axios client
    └── package.json
```

**Deploy:** Backend → Railway, Frontend → Vercel
**Local:** `uvicorn app.main:app` + `npm run dev`

---

## Data Layer

**Source:** Massive (ex-Polygon.io), Starter plan ~$29/mo
**Env var:** `MASSIVE_API_KEY`

- Adjusted OHLCV Daily (corporate actions pre-adjusted)
- Historical index constituents via `/v3/reference/tickers?date=...`
- Storage: Parquet matrix format — rows = dates, columns = tickers
- Cache logic: check last update timestamp → delta-load only
- Delisted/missing tickers: logged, not crashed

**Universe lists (hardcoded, quarterly-reviewable):**

| Universe | Tickers |
|----------|---------|
| Top5 | AAPL, MSFT, NVDA, AMZN, META |
| Top10 | Top5 + GOOGL, GOOG, AVGO, TSLA, COST |
| Top20 | Top10 + NFLX, AMD, ADBE, PEP, CSCO, INTC, CMCSA, TMUS, QCOM, TXN |

---

## Backtest Engine

**Strategy: EMA200 Cross**
```
Signal:   Close[t] > EMA200[t]  → LONG
          Close[t] < EMA200[t]  → FLAT
Entry:    Open[t+1] after signal day
Exit:     Open[t+1] after opposite signal
```

**Assumptions (MVP):**
- No leverage
- No slippage, no transaction costs
- Fully in / fully out per position
- 1 position per ticker

**Metrics per ticker:**
- Win Rate
- Total Return
- Max Drawdown
- Sharpe Ratio
- Number of Trades
- Avg. Holding Period (days)
- Best Trade / Worst Trade
- Benchmark: Index Buy & Hold comparison

---

## Frontend — Pages & Components

### Dashboard (`/`)

**Controls (top bar):**
- Universe selector: `Top5` | `Top10` | `Top20`
- Period selector: `1M` | `3M` | `6M` | `1Y` | `3Y` | `5Y` | `ALL`
- Run Backtest button → POST `/backtest/run`

**Results Table (AG Grid):**

| Ticker | Last Signal | Buy Date | Sell Date | Hold (days) | Return % | vs Index % | Win Rate | Sharpe | Max DD |
|--------|-------------|----------|-----------|-------------|----------|------------|----------|--------|--------|

- Sortierbar nach jeder Spalte
- Grün/Rot Färbung (Return, Signal)
- Klick → StockDetail

**Optimization Book Tab (lazy-loaded on selection):**
- Parameter Grid: EMA period 50/100/150/200/250 × Metric matrix
- Run-Button für custom Parameter-Backtest
- AI Analysis section: Claude analysiert Ergebnisse, gibt strukturierten Report

### StockDetail (`/stock/:ticker`)
- TradingView Lightweight Chart: Candlestick + EMA200 + Buy/Sell markers
- Metriken-Cards: Win Rate, Sharpe, Max DD, Total Return
- Trade History Table: Entry Date | Exit Date | Return % | Hold Days

---

## AI Analysis (Optimierungsbuch)

**Env var:** `ANTHROPIC_API_KEY`
**Trigger:** User clicks "AI Analysis" in Optimization Book tab
**Input to Claude:** Full backtest results JSON per ticker
**Output sections:**
1. Auffälligkeiten (Patterns, Anomalien)
2. Risiko-Einschätzung (Drawdown, Volatilität)
3. Empfehlungen (EMA-Periode, Marktregime)
4. Benchmark-Vergleich Kommentar

---

## Styling

- Dark Mode (trading terminal aesthetic)
- Tailwind CSS
- Color system: green `#00C48C`, red `#FF4757`, background `#0F1117`

---

## Environment Variables

```env
MASSIVE_API_KEY=...
ANTHROPIC_API_KEY=...
```

---

## Out of Scope (MVP)

- SP500 universe (NAS100 only for MVP)
- Correlation / pair trading analysis
- Live/real-time data
- User authentication
- Multiple simultaneous strategies
