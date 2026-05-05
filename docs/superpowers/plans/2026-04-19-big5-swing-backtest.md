# Big 5 Swing Backtest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the Big 5 Swing Backtest strategy (8 combinations, S&P500 Top-5 by market cap, 2000–2025) as a separate `/big5` page in the existing stocks-backtest project.

**Architecture:** New backend services (`sp500_universe.py`, `big5_engine.py`) + router (`big5.py`) alongside existing NAS100 code. Data layer migrated from Massive to yfinance (free, 25-year history). New frontend page `/big5` with combo comparison table and trade history.

**Tech Stack:** FastAPI, yfinance, pandas, React, TypeScript, AG Grid, Tailwind CSS, Axios

---

## File Map

**Create:**
- `backend/app/services/sp500_universe.py` — Historical Top-5 timeline + all-ticker list
- `backend/app/services/big5_engine.py` — 8-combo state machine engine
- `backend/app/routers/big5.py` — POST /big5/run
- `backend/tests/test_sp500_universe.py`
- `backend/tests/test_big5_engine.py`
- `frontend/src/pages/Big5Dashboard.tsx`
- `frontend/src/components/Big5ComboTable.tsx`
- `frontend/src/components/Big5TradeHistory.tsx`

**Modify:**
- `backend/app/services/data_fetcher.py` — replace Massive with yfinance
- `backend/app/models/schemas.py` — add Big5 Pydantic models
- `backend/app/main.py` — register big5 router
- `backend/requirements.txt` — swap massive for yfinance + pandas-market-calendars
- `frontend/src/types/index.ts` — add Big5 TypeScript types
- `frontend/src/api/client.ts` — add runBig5Backtest()
- `frontend/src/App.tsx` — add /big5 route + nav link

---

## Task 1: Update dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Replace `massive>=2.5.0` with yfinance and pandas-market-calendars:

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
httpx==0.27.0
pandas==2.2.2
pyarrow>=16.0.0
numpy==1.26.4
python-dotenv==1.0.1
anthropic==0.28.0
yfinance>=0.2.40
pandas-market-calendars>=4.3.0
```

- [ ] **Step 2: Install new dependencies**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate
pip install yfinance pandas-market-calendars
pip uninstall massive -y
```

Expected: yfinance and pandas-market-calendars install successfully.

- [ ] **Step 3: Verify yfinance works**

```bash
python -c "import yfinance as yf; d = yf.download('AAPL', start='2000-01-01', end='2000-01-10', progress=False); print(d.head())"
```

Expected: Prints 5-7 rows of AAPL OHLCV data from January 2000.

- [ ] **Step 4: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add backend/requirements.txt
git commit -m "chore: replace massive with yfinance, add pandas-market-calendars"
```

---

## Task 2: Migrate data_fetcher.py to yfinance

**Files:**
- Modify: `backend/app/services/data_fetcher.py`

- [ ] **Step 1: Rewrite data_fetcher.py**

```python
import asyncio
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta, timezone

CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

CACHE_MAX_AGE_HOURS = 23


def get_cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}.parquet"


def is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(tz=timezone.utc) - mtime < timedelta(hours=CACHE_MAX_AGE_HOURS)


def _fetch_ticker_sync(ticker: str, from_date: str) -> pd.DataFrame:
    raw = yf.download(ticker, start=from_date, progress=False, auto_adjust=True)
    if raw.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    return df


async def fetch_ticker_data(ticker: str, from_date: str = "2000-01-01") -> pd.DataFrame:
    cache_path = get_cache_path(ticker)

    if is_cache_fresh(cache_path):
        return pd.read_parquet(cache_path)

    df = await asyncio.get_event_loop().run_in_executor(
        None, _fetch_ticker_sync, ticker, from_date
    )

    if len(df) > 0:
        df.to_parquet(cache_path)

    return df


async def fetch_universe_data(tickers: list[str]) -> dict[str, pd.DataFrame]:
    results = await asyncio.gather(
        *[fetch_ticker_data(t) for t in tickers],
        return_exceptions=True,
    )
    out = {}
    for ticker, result in zip(tickers, results):
        if isinstance(result, Exception):
            print(f"[WARN] Failed to fetch {ticker}: {result}")
        else:
            out[ticker] = result
    return out
```

- [ ] **Step 2: Clear old Parquet cache (Massive format may differ)**

```bash
rm /Users/janekstrobel/stocks-backtest/backend/cache/*.parquet 2>/dev/null || true
```

- [ ] **Step 3: Start backend and verify NAS100 backtest still works**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate
uvicorn app.main:app --port 8000 --reload &
sleep 3
curl -s -X POST http://localhost:8000/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"universe_size": 5, "ema_period": 200, "from_date": "2020-01-01"}' \
  | python3 -m json.tool | head -30
```

Expected: JSON with `results` array containing ticker data. No errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add backend/app/services/data_fetcher.py
git commit -m "feat: migrate data_fetcher to yfinance (25yr history, no API key needed)"
```

---

## Task 3: Create sp500_universe.py

**Files:**
- Create: `backend/app/services/sp500_universe.py`
- Create: `backend/tests/test_sp500_universe.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/__init__.py` (empty) and `backend/tests/test_sp500_universe.py`:

```python
import pytest
from app.services.sp500_universe import get_top5, ALL_TICKERS

def test_get_top5_2000():
    result = get_top5(2000)
    assert len(result) == 5
    assert "GE" in result
    assert "MSFT" in result

def test_get_top5_2024():
    result = get_top5(2024)
    assert "NVDA" in result
    assert "AAPL" in result
    assert len(result) == 5

def test_get_top5_unknown_year_raises():
    with pytest.raises(ValueError):
        get_top5(1999)

def test_all_tickers_contains_19():
    assert len(ALL_TICKERS) == 19
    assert "BRK-B" in ALL_TICKERS
    assert "GOOGL" in ALL_TICKERS
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate
pip install pytest -q
pytest tests/test_sp500_universe.py -v
```

Expected: `ModuleNotFoundError` — sp500_universe not found.

- [ ] **Step 3: Create sp500_universe.py**

```python
SP500_TOP5_HISTORY: dict[int, list[str]] = {
    2000: ["GE", "XOM", "PFE", "CSCO", "MSFT"],
    2001: ["GE", "MSFT", "XOM", "WMT", "C"],
    2002: ["MSFT", "XOM", "WMT", "C", "PFE"],
    2003: ["MSFT", "XOM", "PFE", "C", "WMT"],
    2004: ["GE", "MSFT", "C", "XOM", "WMT"],
    2005: ["GE", "XOM", "MSFT", "C", "WMT"],
    2006: ["XOM", "MSFT", "C", "BAC", "GE"],
    2007: ["XOM", "MSFT", "PG", "GE", "GOOGL"],
    2008: ["XOM", "WMT", "PG", "MSFT", "JNJ"],
    2009: ["XOM", "MSFT", "WMT", "GOOGL", "AAPL"],
    2010: ["XOM", "AAPL", "MSFT", "BRK-B", "WMT"],
    2011: ["XOM", "AAPL", "MSFT", "CVX", "GOOGL"],
    2012: ["AAPL", "XOM", "GOOGL", "WMT", "MSFT"],
    2013: ["AAPL", "XOM", "GOOGL", "MSFT", "BRK-B"],
    2014: ["AAPL", "XOM", "MSFT", "BRK-B", "GOOGL"],
    2015: ["AAPL", "GOOGL", "MSFT", "BRK-B", "XOM"],
    2016: ["AAPL", "GOOGL", "MSFT", "BRK-B", "XOM"],
    2017: ["AAPL", "GOOGL", "MSFT", "AMZN", "META"],
    2018: ["MSFT", "AAPL", "AMZN", "GOOGL", "BRK-B"],
    2019: ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    2020: ["AAPL", "MSFT", "AMZN", "GOOGL", "META"],
    2021: ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
    2022: ["AAPL", "MSFT", "GOOGL", "AMZN", "BRK-B"],
    2023: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
    2024: ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN"],
    2025: ["NVDA", "AAPL", "GOOGL", "MSFT", "AMZN"],
}

ALL_TICKERS: list[str] = sorted(set(
    ticker
    for tickers in SP500_TOP5_HISTORY.values()
    for ticker in tickers
))


def get_top5(year: int) -> list[str]:
    if year not in SP500_TOP5_HISTORY:
        raise ValueError(f"No Top-5 data for year {year}. Supported: 2000–2025.")
    return SP500_TOP5_HISTORY[year]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sp500_universe.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add backend/app/services/sp500_universe.py backend/tests/
git commit -m "feat: add sp500_universe with curated 2000-2025 Top-5 timeline"
```

---

## Task 4: Add Big5 Pydantic models to schemas.py

**Files:**
- Modify: `backend/app/models/schemas.py`

- [ ] **Step 1: Append Big5 models to schemas.py**

Add at the end of `backend/app/models/schemas.py`:

```python
from typing import Literal


class Big5BacktestRequest(BaseModel):
    indicator: Literal["EMA", "SMA"] = "EMA"
    period: int = 200
    from_date: str = "2000-01-01"
    to_date: str = "2025-12-31"


class Big5Trade(BaseModel):
    nr: int
    typ: Literal["KAUF", "VERKAUF"]
    ticker: str
    datum: str
    haltdauer: int
    open_preis: float
    perf_pct: float
    kum_perf_pct: float


class Big5ComboMetrics(BaseModel):
    num_trades: int
    win_rate: float
    total_return: float
    sharpe: float
    max_drawdown: float


class Big5ComboResult(BaseModel):
    kombination: str
    trades: list[Big5Trade]
    metrics: Big5ComboMetrics


class Big5BacktestResponse(BaseModel):
    results: list[Big5ComboResult]
    indicator: str
    period: int
    from_date: str
    to_date: str
```

- [ ] **Step 2: Verify import works**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate
python -c "from app.models.schemas import Big5BacktestRequest, Big5BacktestResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add backend/app/models/schemas.py
git commit -m "feat: add Big5 Pydantic models (request, trade, combo result, response)"
```

---

## Task 5: Create big5_engine.py

**Files:**
- Create: `backend/app/services/big5_engine.py`
- Create: `backend/tests/test_big5_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_big5_engine.py
import pandas as pd
import numpy as np
import pytest
from datetime import date
from app.services.big5_engine import run_big5_backtest

def make_df(closes: list[float], opens: list[float] | None = None) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame with given closes. Opens default to close."""
    n = len(closes)
    dates = pd.bdate_range("2010-01-01", periods=n).date  # business days
    if opens is None:
        opens = closes
    return pd.DataFrame({
        "open": opens,
        "close": closes,
    }, index=dates)


def test_no_trades_when_always_below_ema():
    """If close is always below EMA200, no trade should be generated."""
    # 250 days all at price 50, EMA200 will converge to 50 — use downtrend
    closes = [100 - i * 0.1 for i in range(250)]
    df = make_df(closes)
    all_data = {"AAPL": df}
    results = run_big5_backtest(all_data, indicator="SMA", period=10, from_date="2010-01-01", to_date="2010-12-31")
    # All combos should have 0 trades for AAPL
    total_trades = sum(len(r["trades"]) for r in results)
    assert total_trades == 0


def test_returns_eight_combos():
    """Engine always returns results for all 8 combinations."""
    closes = [100.0] * 250
    df = make_df(closes)
    all_data = {"AAPL": df}
    results = run_big5_backtest(all_data, indicator="SMA", period=5, from_date="2010-01-01", to_date="2010-12-31")
    combos = {r["kombination"] for r in results}
    assert combos == {"ACE", "ACF", "ADE", "ADF", "BCE", "BCF", "BDE", "BDF"}


def test_kauf_before_verkauf():
    """Every KAUF must be followed by a VERKAUF in the trade list."""
    closes = [90.0] * 10 + [110.0] * 50 + [90.0] * 10 + [110.0] * 200
    df = make_df(closes)
    all_data = {"AAPL": df}
    results = run_big5_backtest(all_data, indicator="SMA", period=5, from_date="2010-01-01", to_date="2011-06-30")
    for r in results:
        typs = [t["typ"] for t in r["trades"]]
        for i, typ in enumerate(typs):
            if typ == "VERKAUF":
                assert i > 0 and typs[i - 1] == "KAUF", f"VERKAUF without preceding KAUF in {r['kombination']}"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
pytest tests/test_big5_engine.py -v
```

Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Create big5_engine.py**

```python
from dataclasses import dataclass, field
from datetime import date
import pandas as pd
import numpy as np
from app.services.sp500_universe import get_top5, ALL_TICKERS

COMBOS = ["ACE", "ACF", "ADE", "ADF", "BCE", "BCF", "BDE", "BDF"]


@dataclass
class _TickerState:
    consecutive: int = 0
    in_trade: bool = False
    entry_price: float = 0.0
    entry_day_idx: int = 0
    kum_perf: float = 0.0


def _calc_indicator(series: pd.Series, indicator: str, period: int) -> pd.Series:
    if indicator == "EMA":
        return series.ewm(span=period, adjust=False).mean()
    return series.rolling(window=period).mean()


def _calc_metrics(trades: list[dict]) -> dict:
    verkauf = [t for t in trades if t["typ"] == "VERKAUF"]
    if not verkauf:
        return {"num_trades": 0, "win_rate": 0.0, "total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}

    returns = [t["perf_pct"] for t in verkauf]
    wins = sum(1 for r in returns if r > 0)

    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))
    peak, max_dd = equity[0], 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd

    arr = np.array(returns) / 100
    excess = arr - 0.02 / 252
    sharpe = 0.0
    if len(excess) > 1 and excess.std() > 0:
        sharpe = round(float(np.sqrt(252) * excess.mean() / excess.std()), 4)

    return {
        "num_trades": len(verkauf),
        "win_rate": round(wins / len(verkauf) * 100, 2),
        "total_return": round(sum(returns), 4),
        "sharpe": sharpe,
        "max_drawdown": round(-max_dd, 4),
    }


def run_big5_backtest(
    all_data: dict[str, pd.DataFrame],
    indicator: str = "EMA",
    period: int = 200,
    from_date: str = "2000-01-01",
    to_date: str = "2025-12-31",
) -> list[dict]:
    from_d = pd.to_datetime(from_date).date()
    to_d = pd.to_datetime(to_date).date()

    # Pre-calculate indicators for all tickers
    ind_series: dict[str, pd.Series] = {}
    for ticker, df in all_data.items():
        ind_series[ticker] = _calc_indicator(df["close"], indicator, period)

    # Unified sorted trading-day index across all tickers
    all_dates = sorted(
        d for df in all_data.values() for d in df.index
        if from_d <= d <= to_d
    )

    # States: combo → ticker → _TickerState
    states = {combo: {t: _TickerState() for t in all_data} for combo in COMBOS}
    # Trades: combo → list of trade dicts
    combo_trades: dict[str, list[dict]] = {c: [] for c in COMBOS}
    trade_nr = {c: 0 for c in COMBOS}

    valid_years = set(range(2000, 2026))

    for i, day in enumerate(all_dates):
        year = day.year
        if year not in valid_years:
            continue

        top5 = get_top5(year)

        # Next trading day for execution
        next_day = all_dates[i + 1] if i + 1 < len(all_dates) else None

        for ticker, df in all_data.items():
            if day not in df.index:
                continue
            if next_day is None or next_day not in df.index:
                continue

            close = df.loc[day, "close"]
            ind_val = ind_series[ticker].get(day)
            if pd.isna(ind_val):
                continue

            signal = bool(close > ind_val)
            in_top5 = ticker in top5
            next_open = float(df.loc[next_day, "open"])

            for combo in COMBOS:
                has_A = "A" in combo
                has_C = "C" in combo
                has_E = "E" in combo
                state = states[combo][ticker]

                prev_consec = state.consecutive
                state.consecutive = state.consecutive + 1 if in_top5 else 0

                qualified = state.consecutive >= 1 if has_E else state.consecutive >= 5

                # --- EXIT ---
                if state.in_trade:
                    should_exit = (not signal) if has_C else (not signal or not in_top5)
                    if should_exit:
                        perf = (next_open - state.entry_price) / state.entry_price * 100
                        state.kum_perf += perf
                        haltdauer = i + 1 - state.entry_day_idx
                        trade_nr[combo] += 1
                        combo_trades[combo].append({
                            "nr": trade_nr[combo],
                            "typ": "VERKAUF",
                            "ticker": ticker,
                            "datum": next_day.isoformat(),
                            "haltdauer": haltdauer,
                            "open_preis": round(next_open, 4),
                            "perf_pct": round(perf, 4),
                            "kum_perf_pct": round(state.kum_perf, 4),
                        })
                        state.in_trade = False

                # --- ENTRY ---
                if not state.in_trade and qualified:
                    if has_A:
                        should_enter = signal
                    else:
                        # B: only on the first qualifying day
                        first_day = (prev_consec == 0 and state.consecutive == 1) if has_E \
                            else (prev_consec == 4 and state.consecutive == 5)
                        should_enter = first_day and signal

                    if should_enter:
                        state.in_trade = True
                        state.entry_price = next_open
                        state.entry_day_idx = i + 1
                        trade_nr[combo] += 1
                        combo_trades[combo].append({
                            "nr": trade_nr[combo],
                            "typ": "KAUF",
                            "ticker": ticker,
                            "datum": next_day.isoformat(),
                            "haltdauer": 0,
                            "open_preis": round(next_open, 4),
                            "perf_pct": 0.0,
                            "kum_perf_pct": round(state.kum_perf, 4),
                        })

    return [
        {
            "kombination": combo,
            "trades": combo_trades[combo],
            "metrics": _calc_metrics(combo_trades[combo]),
        }
        for combo in COMBOS
    ]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_big5_engine.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add backend/app/services/big5_engine.py backend/tests/test_big5_engine.py
git commit -m "feat: add big5_engine with 8-combo state machine (ACE/ACF/ADE/ADF/BCE/BCF/BDE/BDF)"
```

---

## Task 6: Create big5.py router

**Files:**
- Create: `backend/app/routers/big5.py`

- [ ] **Step 1: Create the router**

```python
# backend/app/routers/big5.py
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    Big5BacktestRequest, Big5BacktestResponse,
    Big5ComboResult, Big5ComboMetrics, Big5Trade,
)
from app.services.sp500_universe import ALL_TICKERS
from app.services.data_fetcher import fetch_universe_data
from app.services.big5_engine import run_big5_backtest

router = APIRouter()


@router.post("/run", response_model=Big5BacktestResponse)
async def run_big5_endpoint(req: Big5BacktestRequest):
    all_data = await fetch_universe_data(ALL_TICKERS)

    raw_results = run_big5_backtest(
        all_data=all_data,
        indicator=req.indicator,
        period=req.period,
        from_date=req.from_date,
        to_date=req.to_date,
    )

    results = []
    for r in raw_results:
        results.append(Big5ComboResult(
            kombination=r["kombination"],
            trades=[Big5Trade(**t) for t in r["trades"]],
            metrics=Big5ComboMetrics(**r["metrics"]),
        ))

    return Big5BacktestResponse(
        results=results,
        indicator=req.indicator,
        period=req.period,
        from_date=req.from_date,
        to_date=req.to_date,
    )
```

- [ ] **Step 2: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add backend/app/routers/big5.py
git commit -m "feat: add /big5/run router endpoint"
```

---

## Task 7: Register big5 router in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add big5 router import and registration**

In `backend/app/main.py`, add after the existing router imports:

```python
from app.routers import backtest, universe, big5  # add big5
```

And after `app.include_router(backtest.router, ...)`:

```python
app.include_router(big5.router, prefix="/big5", tags=["big5"])
```

- [ ] **Step 2: Verify endpoint shows in OpenAPI docs**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate
uvicorn app.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/openapi.json | python3 -c "import sys,json; paths=json.load(sys.stdin)['paths']; print([p for p in paths if 'big5' in p])"
```

Expected: `['/big5/run']`

- [ ] **Step 3: Commit**

```bash
kill %1 2>/dev/null || true
cd /Users/janekstrobel/stocks-backtest
git add backend/app/main.py
git commit -m "feat: register big5 router at /big5"
```

---

## Task 8: Add Big5 TypeScript types and API client

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Append Big5 types to types/index.ts**

Add at the end of `frontend/src/types/index.ts`:

```typescript
export interface Big5Trade {
  nr: number;
  typ: 'KAUF' | 'VERKAUF';
  ticker: string;
  datum: string;
  haltdauer: number;
  open_preis: number;
  perf_pct: number;
  kum_perf_pct: number;
}

export interface Big5ComboMetrics {
  num_trades: number;
  win_rate: number;
  total_return: number;
  sharpe: number;
  max_drawdown: number;
}

export interface Big5ComboResult {
  kombination: string;
  trades: Big5Trade[];
  metrics: Big5ComboMetrics;
}

export interface Big5BacktestResponse {
  results: Big5ComboResult[];
  indicator: string;
  period: number;
  from_date: string;
  to_date: string;
}
```

- [ ] **Step 2: Add runBig5Backtest to api/client.ts**

Add at the end of `frontend/src/api/client.ts`:

```typescript
import type { BacktestResponse, AIAnalysis, Big5BacktestResponse } from '../types';

export async function runBig5Backtest(
  indicator: 'EMA' | 'SMA' = 'EMA',
  period: number = 200,
  fromDate: string = '2000-01-01',
  toDate: string = '2025-12-31',
): Promise<Big5BacktestResponse> {
  const { data } = await api.post<Big5BacktestResponse>('/big5/run', {
    indicator,
    period,
    from_date: fromDate,
    to_date: toDate,
  });
  return data;
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat: add Big5 TypeScript types and API client function"
```

---

## Task 9: Create Big5TradeHistory.tsx

**Files:**
- Create: `frontend/src/components/Big5TradeHistory.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/components/Big5TradeHistory.tsx
import type { Big5Trade } from '../types';

interface Props {
  trades: Big5Trade[];
  kombination: string;
}

export function Big5TradeHistory({ trades, kombination }: Props) {
  if (trades.length === 0) {
    return (
      <div className="py-4 text-center text-sm" style={{ color: '#8B8FA8' }}>
        Keine Trades für Kombination {kombination}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs" style={{ color: '#E8EAED' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #2A2D3A' }}>
            {['Nr', 'Typ', 'Ticker', 'Datum', 'Haltedauer', 'Open', 'Perf %', 'Kum. %'].map((h) => (
              <th key={h} className="py-2 px-3 text-left font-medium" style={{ color: '#8B8FA8' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.nr} style={{ borderBottom: '1px solid #1E2030' }}>
              <td className="py-1.5 px-3">{t.nr}</td>
              <td
                className="py-1.5 px-3 font-medium"
                style={{ color: t.typ === 'KAUF' ? '#00C48C' : '#FF4757' }}
              >
                {t.typ}
              </td>
              <td className="py-1.5 px-3">{t.ticker}</td>
              <td className="py-1.5 px-3">{t.datum}</td>
              <td className="py-1.5 px-3">{t.haltdauer}d</td>
              <td className="py-1.5 px-3">${t.open_preis.toFixed(2)}</td>
              <td
                className="py-1.5 px-3"
                style={{ color: t.perf_pct >= 0 ? '#00C48C' : '#FF4757' }}
              >
                {t.perf_pct > 0 ? '+' : ''}{t.perf_pct.toFixed(2)}%
              </td>
              <td
                className="py-1.5 px-3"
                style={{ color: t.kum_perf_pct >= 0 ? '#00C48C' : '#FF4757' }}
              >
                {t.kum_perf_pct > 0 ? '+' : ''}{t.kum_perf_pct.toFixed(2)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/src/components/Big5TradeHistory.tsx
git commit -m "feat: add Big5TradeHistory component"
```

---

## Task 10: Create Big5ComboTable.tsx

**Files:**
- Create: `frontend/src/components/Big5ComboTable.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/components/Big5ComboTable.tsx
import { useState } from 'react';
import type { Big5ComboResult } from '../types';
import { Big5TradeHistory } from './Big5TradeHistory';

interface Props {
  results: Big5ComboResult[];
}

const COMBO_LABELS: Record<string, string> = {
  ACE: 'A·C·E — Klassisch',
  ACF: 'A·C·F — Klassisch, 5-Tage Filter',
  ADE: 'A·D·E — Sofortausstieg',
  ADF: 'A·D·F — Sofortausstieg, 5-Tage Filter',
  BCE: 'B·C·E — Einstieg am Eintrittstag',
  BCF: 'B·C·F — Einstieg am Eintrittstag, 5-Tage Filter',
  BDE: 'B·D·E — Einstieg & Sofortausstieg',
  BDF: 'B·D·F — Einstieg & Sofortausstieg, 5-Tage Filter',
};

function fmt(v: number, suffix = '') {
  const color = v >= 0 ? '#00C48C' : '#FF4757';
  return <span style={{ color }}>{v > 0 ? '+' : ''}{v.toFixed(2)}{suffix}</span>;
}

export function Big5ComboTable({ results }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="rounded-lg overflow-hidden" style={{ border: '1px solid #2A2D3A' }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: '#1A1D2E', borderBottom: '1px solid #2A2D3A' }}>
            {['Kombination', 'Trades', 'Win Rate', 'Total Return', 'Sharpe', 'Max DD'].map((h) => (
              <th key={h} className="py-3 px-4 text-left font-medium" style={{ color: '#8B8FA8' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <>
              <tr
                key={r.kombination}
                onClick={() => setExpanded(expanded === r.kombination ? null : r.kombination)}
                className="cursor-pointer transition-colors"
                style={{
                  background: expanded === r.kombination ? '#1A1D2E' : 'transparent',
                  borderBottom: '1px solid #1E2030',
                  color: '#E8EAED',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#1A1D2E')}
                onMouseLeave={(e) => (e.currentTarget.style.background = expanded === r.kombination ? '#1A1D2E' : 'transparent')}
              >
                <td className="py-3 px-4">
                  <div className="font-semibold">{r.kombination}</div>
                  <div className="text-xs mt-0.5" style={{ color: '#8B8FA8' }}>
                    {COMBO_LABELS[r.kombination]}
                  </div>
                </td>
                <td className="py-3 px-4">{r.metrics.num_trades}</td>
                <td className="py-3 px-4">{fmt(r.metrics.win_rate, '%')}</td>
                <td className="py-3 px-4">{fmt(r.metrics.total_return, '%')}</td>
                <td className="py-3 px-4">{fmt(r.metrics.sharpe)}</td>
                <td className="py-3 px-4">{fmt(r.metrics.max_drawdown, '%')}</td>
              </tr>
              {expanded === r.kombination && (
                <tr key={`${r.kombination}-detail`}>
                  <td colSpan={6} style={{ background: '#12141F', padding: 0 }}>
                    <div className="p-4">
                      <Big5TradeHistory trades={r.trades} kombination={r.kombination} />
                    </div>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/src/components/Big5ComboTable.tsx
git commit -m "feat: add Big5ComboTable with expandable trade history rows"
```

---

## Task 11: Create Big5Dashboard.tsx

**Files:**
- Create: `frontend/src/pages/Big5Dashboard.tsx`

- [ ] **Step 1: Create page**

```tsx
// frontend/src/pages/Big5Dashboard.tsx
import { useState } from 'react';
import { runBig5Backtest } from '../api/client';
import { Big5ComboTable } from '../components/Big5ComboTable';
import type { Big5BacktestResponse } from '../types';

export function Big5Dashboard() {
  const [indicator, setIndicator] = useState<'EMA' | 'SMA'>('EMA');
  const [results, setResults] = useState<Big5BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const data = await runBig5Backtest(indicator);
      setResults(data);
    } catch (e: any) {
      setError(e?.message ?? 'Backtest fehlgeschlagen');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen p-6" style={{ background: '#0F1117' }}>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div>
          <h1 className="text-xl font-semibold tracking-tight" style={{ color: '#E8EAED' }}>
            Big 5 Swing Backtest
          </h1>
          <p className="text-xs mt-0.5" style={{ color: '#8B8FA8' }}>
            S&amp;P500 Top-5 · 2000–2025 · 8 Strategie-Kombinationen
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4 flex-wrap">
          <div>
            <p className="text-xs mb-1.5" style={{ color: '#8B8FA8' }}>Indikator</p>
            <div className="flex gap-1">
              {(['EMA', 'SMA'] as const).map((ind) => (
                <button
                  key={ind}
                  onClick={() => setIndicator(ind)}
                  className="px-4 py-1.5 rounded text-sm font-medium transition-colors"
                  style={{
                    background: indicator === ind ? '#00C48C22' : '#1A1D2E',
                    color: indicator === ind ? '#00C48C' : '#8B8FA8',
                    border: `1px solid ${indicator === ind ? '#00C48C' : '#2A2D3A'}`,
                  }}
                >
                  {ind} 200
                </button>
              ))}
            </div>
          </div>

          <div style={{ color: '#8B8FA8', fontSize: '0.75rem' }}>
            <p className="mb-1.5">Zeitraum</p>
            <span
              className="px-4 py-1.5 rounded text-sm"
              style={{ background: '#1A1D2E', border: '1px solid #2A2D3A', color: '#E8EAED' }}
            >
              2000 – 2025
            </span>
          </div>

          <div className="ml-auto mt-5">
            <button
              onClick={handleRun}
              disabled={loading}
              className="px-6 py-2 rounded font-medium text-sm disabled:opacity-50"
              style={{ background: '#00C48C', color: '#0F1117' }}
            >
              {loading ? 'Berechne…' : 'Run Backtest'}
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded px-4 py-3 text-sm" style={{ background: '#FF475722', color: '#FF4757' }}>
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="text-sm" style={{ color: '#8B8FA8' }}>
            Lade 25 Jahre Daten für 19 Ticker und berechne 8 Kombinationen…
          </div>
        )}

        {/* Results */}
        {results && !loading && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs" style={{ color: '#8B8FA8' }}>
                {results.indicator}200 · Klick auf Zeile für Trade-History
              </p>
            </div>
            <Big5ComboTable results={results.results} />
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/src/pages/Big5Dashboard.tsx
git commit -m "feat: add Big5Dashboard page with EMA/SMA toggle and combo table"
```

---

## Task 12: Wire /big5 route and nav link in App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add route and nav link**

Replace the entire `frontend/src/App.tsx` with:

```tsx
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { StockDetail } from './pages/StockDetail';
import { Big5Dashboard } from './pages/Big5Dashboard';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <nav
        className="flex gap-4 px-6 py-3 text-sm"
        style={{ background: '#12141F', borderBottom: '1px solid #2A2D3A' }}
      >
        <NavLink
          to="/"
          end
          style={({ isActive }) => ({ color: isActive ? '#00C48C' : '#8B8FA8' })}
        >
          NAS100
        </NavLink>
        <NavLink
          to="/big5"
          style={({ isActive }) => ({ color: isActive ? '#00C48C' : '#8B8FA8' })}
        >
          Big 5
        </NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/stock/:ticker" element={<StockDetail />} />
        <Route path="/big5" element={<Big5Dashboard />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Verify frontend builds without errors**

```bash
cd /Users/janekstrobel/stocks-backtest/frontend
npm run build 2>&1 | tail -10
```

Expected: `built in Xs` with no TypeScript errors.

- [ ] **Step 3: Open browser and verify**

Navigate to `http://localhost:5200/big5` — should show Big 5 Dashboard with EMA/SMA toggle and Run button. Nav shows "NAS100" and "Big 5" links.

- [ ] **Step 4: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/src/App.tsx
git commit -m "feat: add /big5 route and nav link — Big 5 Swing Backtest complete"
```

---

## Self-Review

**Spec coverage check:**
- ✅ 8 Kombinationen (ACE/ACF/ADE/ADF/BCE/BCF/BDE/BDF) — Task 5
- ✅ EMA + SMA wählbar — Task 5 + Task 11
- ✅ S&P500 Top-5 historisch 2000–2025 (19 Tickers) — Task 3
- ✅ Execution auf Open des nächsten Handelstags — Task 5 (yfinance index = trading days only)
- ✅ Holiday-Handling implizit (yfinance liefert nur Handelstage) — Task 5
- ✅ Trade-Felder: nr, typ, datum, haltdauer, open_preis, perf_pct, kum_perf_pct — Task 4 + 5
- ✅ Kumulierte % Performance pro Kombination — Task 5 (`kum_perf`)
- ✅ Separate Seite /big5, getrennt von NAS100 — Task 12
- ✅ yfinance Migration (25yr History) — Task 2
- ✅ Metriken: Trades, Win Rate, Total Return, Sharpe, Max DD — Task 5 + 4

**Type consistency check:**
- `Big5Trade` fields in schemas.py (Task 4) match `big5_engine.py` dict keys (Task 5) ✅
- `Big5ComboMetrics` fields in schemas.py match `_calc_metrics()` return keys ✅
- TypeScript `Big5Trade` interface (Task 8) matches backend model ✅
- `runBig5Backtest()` in client.ts uses `/big5/run` endpoint registered in Task 7 ✅
