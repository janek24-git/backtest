# Backtesting Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web-based EMA200 backtesting platform for NAS100 Top5/10/20 with FastAPI backend, React frontend, Massive API data, and Claude AI analysis.

**Architecture:** FastAPI (Python) backend serves REST API with backtest engine + Massive data fetcher. React + Vite frontend renders AG Grid results table, TradingView charts, and AI analysis tab. Deployed separately: backend → Railway, frontend → Vercel.

**Tech Stack:** Python 3.11+, FastAPI, pandas, pyarrow, httpx, anthropic SDK / React 18, Vite, TypeScript, Tailwind CSS, AG Grid Community, TradingView Lightweight Charts

---

## File Map

```
stocks-backtest/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── backtest.py
│   │   │   └── universe.py
│   │   ├── services/
│   │   │   ├── universe.py
│   │   │   ├── data_fetcher.py
│   │   │   ├── backtest_engine.py
│   │   │   └── ai_analyst.py
│   │   └── models/
│   │       └── schemas.py
│   ├── cache/                   # gitignored Parquet files
│   ├── tests/
│   │   ├── test_universe.py
│   │   ├── test_backtest_engine.py
│   │   └── test_data_fetcher.py
│   ├── .env.example
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── Dashboard.tsx
    │   │   └── StockDetail.tsx
    │   ├── components/
    │   │   ├── UniverseSelector.tsx
    │   │   ├── PeriodSelector.tsx
    │   │   ├── ResultsTable.tsx
    │   │   ├── CandleChart.tsx
    │   │   ├── TradeHistory.tsx
    │   │   └── OptimizationBook.tsx
    │   ├── api/
    │   │   └── client.ts
    │   ├── types/
    │   │   └── index.ts
    │   ├── App.tsx
    │   └── main.tsx
    ├── index.html
    ├── vite.config.ts
    ├── tailwind.config.ts
    └── package.json
```

---

## Task 1: Backend project setup

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/main.py`
- Create: `backend/cache/.gitkeep`

- [ ] **Step 1: Create backend directory structure**

```bash
cd /Users/janekstrobel/stocks-backtest
mkdir -p backend/app/routers backend/app/services backend/app/models backend/tests backend/cache
touch backend/cache/.gitkeep
```

- [ ] **Step 2: Create requirements.txt**

```
# backend/requirements.txt
fastapi==0.111.0
uvicorn[standard]==0.29.0
httpx==0.27.0
pandas==2.2.2
pyarrow==16.0.0
numpy==1.26.4
python-dotenv==1.0.1
anthropic==0.28.0
pytest==8.2.0
pytest-asyncio==0.23.6
httpx==0.27.0
```

- [ ] **Step 3: Create .env.example**

```
# backend/.env.example
MASSIVE_API_KEY=your_key_here
MASSIVE_BASE_URL=https://api.polygon.io
ANTHROPIC_API_KEY=your_key_here
```

> Note: Verify MASSIVE_BASE_URL from your Massive dashboard — may differ from Polygon's old URL.

- [ ] **Step 4: Create main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.routers import backtest, universe

app = FastAPI(title="Backtesting Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(universe.router, prefix="/universe", tags=["universe"])
app.include_router(backtest.router, prefix="/backtest", tags=["backtest"])


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Install dependencies**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 6: Verify server starts**

```bash
uvicorn app.main:app --reload
```

Expected: `Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: backend project setup"
```

---

## Task 2: Universe service

**Files:**
- Create: `backend/app/services/universe.py`
- Create: `backend/tests/test_universe.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_universe.py
from app.services.universe import get_tickers

def test_top5_returns_5_tickers():
    tickers = get_tickers(5)
    assert len(tickers) == 5
    assert "AAPL" in tickers
    assert "NVDA" in tickers

def test_top10_returns_10_tickers():
    tickers = get_tickers(10)
    assert len(tickers) == 10

def test_top20_returns_20_tickers():
    tickers = get_tickers(20)
    assert len(tickers) == 20

def test_top10_includes_top5():
    top5 = set(get_tickers(5))
    top10 = set(get_tickers(10))
    assert top5.issubset(top10)

def test_invalid_size_raises():
    import pytest
    with pytest.raises(ValueError):
        get_tickers(99)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && source venv/bin/activate
pytest tests/test_universe.py -v
```

Expected: FAIL with `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Implement universe service**

```python
# backend/app/services/universe.py

NAS100_TOP5 = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]

NAS100_TOP10 = NAS100_TOP5 + ["GOOGL", "AVGO", "TSLA", "COST", "NFLX"]

NAS100_TOP20 = NAS100_TOP10 + [
    "AMD", "ADBE", "PEP", "CSCO", "INTC",
    "CMCSA", "TMUS", "QCOM", "TXN", "GOOG"
]

VALID_SIZES = {5: NAS100_TOP5, 10: NAS100_TOP10, 20: NAS100_TOP20}


def get_tickers(size: int) -> list[str]:
    if size not in VALID_SIZES:
        raise ValueError(f"size must be one of {list(VALID_SIZES.keys())}, got {size}")
    return VALID_SIZES[size]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_universe.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/universe.py backend/tests/test_universe.py
git commit -m "feat: universe service with NAS100 Top5/10/20"
```

---

## Task 3: Backtest engine — EMA + signals

**Files:**
- Create: `backend/app/services/backtest_engine.py`
- Create: `backend/tests/test_backtest_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_backtest_engine.py
import pandas as pd
import numpy as np
import pytest
from app.services.backtest_engine import calculate_ema, generate_signals, extract_trades

def make_df(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=len(closes), freq="B")
    opens = [c * 0.999 for c in closes]
    return pd.DataFrame({"open": opens, "close": closes}, index=dates)


def test_ema_length_matches_input():
    df = make_df([100.0] * 250)
    ema = calculate_ema(df["close"], period=200)
    assert len(ema) == 250


def test_ema_constant_series_equals_constant():
    df = make_df([100.0] * 300)
    ema = calculate_ema(df["close"], period=200)
    assert abs(ema.iloc[-1] - 100.0) < 0.01


def test_generate_signals_columns():
    df = make_df([100.0] * 300)
    result = generate_signals(df.copy())
    assert "ema200" in result.columns
    assert "signal" in result.columns


def test_signal_long_when_close_above_ema():
    closes = [90.0] * 200 + [110.0] * 50
    df = make_df(closes)
    result = generate_signals(df.copy())
    assert result["signal"].iloc[-1] == 1


def test_signal_flat_when_close_below_ema():
    closes = [110.0] * 200 + [90.0] * 50
    df = make_df(closes)
    result = generate_signals(df.copy())
    assert result["signal"].iloc[-1] == 0


def test_extract_trades_returns_list():
    closes = [90.0] * 200 + [110.0] * 50 + [90.0] * 50
    df = make_df(closes)
    df_signals = generate_signals(df.copy())
    trades = extract_trades(df_signals)
    assert isinstance(trades, list)
    assert len(trades) >= 1


def test_trade_has_required_keys():
    closes = [90.0] * 200 + [110.0] * 50 + [90.0] * 50
    df = make_df(closes)
    df_signals = generate_signals(df.copy())
    trades = extract_trades(df_signals)
    trade = trades[0]
    for key in ["entry_date", "exit_date", "entry_price", "exit_price", "return_pct", "hold_days"]:
        assert key in trade, f"Missing key: {key}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_backtest_engine.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement backtest engine**

```python
# backend/app/services/backtest_engine.py
import pandas as pd
import numpy as np
from datetime import date


def calculate_ema(prices: pd.Series, period: int = 200) -> pd.Series:
    return prices.ewm(span=period, adjust=False).mean()


def generate_signals(df: pd.DataFrame, ema_period: int = 200) -> pd.DataFrame:
    df = df.copy()
    df["ema200"] = calculate_ema(df["close"], period=ema_period)
    df["signal"] = (df["close"] > df["ema200"]).astype(int)
    return df


def extract_trades(df: pd.DataFrame) -> list[dict]:
    trades = []
    in_trade = False
    entry_date = None
    entry_price = None

    for i in range(1, len(df)):
        prev_signal = df["signal"].iloc[i - 1]
        curr_open = df["open"].iloc[i]
        curr_date = df.index[i]

        if prev_signal == 1 and not in_trade:
            in_trade = True
            entry_date = curr_date
            entry_price = curr_open

        elif prev_signal == 0 and in_trade:
            exit_price = curr_open
            return_pct = (exit_price - entry_price) / entry_price * 100
            hold_days = (curr_date - entry_date).days
            trades.append({
                "entry_date": entry_date.date().isoformat(),
                "exit_date": curr_date.date().isoformat(),
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "return_pct": round(return_pct, 4),
                "hold_days": hold_days,
            })
            in_trade = False

    return trades
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_backtest_engine.py -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/backtest_engine.py backend/tests/test_backtest_engine.py
git commit -m "feat: backtest engine EMA200 signal + trade extraction"
```

---

## Task 4: Backtest engine — metrics

**Files:**
- Modify: `backend/app/services/backtest_engine.py`
- Modify: `backend/tests/test_backtest_engine.py`

- [ ] **Step 1: Add failing metric tests**

Append to `backend/tests/test_backtest_engine.py`:

```python
from app.services.backtest_engine import calculate_metrics, run_backtest


def test_metrics_keys():
    trades = [
        {"return_pct": 10.0, "hold_days": 20, "entry_date": "2021-01-01",
         "exit_date": "2021-01-21", "entry_price": 100, "exit_price": 110},
        {"return_pct": -5.0, "hold_days": 10, "entry_date": "2021-02-01",
         "exit_date": "2021-02-11", "entry_price": 110, "exit_price": 104.5},
    ]
    metrics = calculate_metrics(trades)
    for key in ["win_rate", "total_return", "max_drawdown", "sharpe_ratio",
                "num_trades", "avg_hold_days", "best_trade", "worst_trade"]:
        assert key in metrics, f"Missing metric: {key}"


def test_win_rate_calculation():
    trades = [
        {"return_pct": 10.0, "hold_days": 5, "entry_date": "2021-01-01",
         "exit_date": "2021-01-06", "entry_price": 100, "exit_price": 110},
        {"return_pct": -5.0, "hold_days": 5, "entry_date": "2021-02-01",
         "exit_date": "2021-02-06", "entry_price": 100, "exit_price": 95},
        {"return_pct": 8.0, "hold_days": 5, "entry_date": "2021-03-01",
         "exit_date": "2021-03-06", "entry_price": 100, "exit_price": 108},
    ]
    metrics = calculate_metrics(trades)
    assert abs(metrics["win_rate"] - 66.67) < 0.1


def test_empty_trades_returns_none():
    metrics = calculate_metrics([])
    assert metrics is None


def test_run_backtest_returns_result():
    closes = [90.0] * 210 + [110.0] * 60 + [90.0] * 60
    opens = [c * 0.999 for c in closes]
    dates = pd.date_range("2020-01-01", periods=len(closes), freq="B")
    df = pd.DataFrame({"open": opens, "close": closes}, index=dates)
    result = run_backtest(df, ema_period=200)
    assert "trades" in result
    assert "metrics" in result
    assert "signals" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_backtest_engine.py::test_metrics_keys -v
```

Expected: FAIL

- [ ] **Step 3: Add metrics + run_backtest to engine**

Append to `backend/app/services/backtest_engine.py`:

```python
def calculate_metrics(trades: list[dict]) -> dict | None:
    if not trades:
        return None

    returns = [t["return_pct"] for t in trades]
    winning = [r for r in returns if r > 0]

    win_rate = round(len(winning) / len(trades) * 100, 2)
    total_return = round(sum(returns), 4)
    best_trade = round(max(returns), 4)
    worst_trade = round(min(returns), 4)
    avg_hold_days = round(sum(t["hold_days"] for t in trades) / len(trades), 1)

    # Max drawdown on equity curve
    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))
    peak = equity[0]
    max_dd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd
    max_drawdown = round(-max_dd, 4)

    # Sharpe ratio (annualised, risk-free = 2%)
    returns_arr = np.array(returns) / 100
    excess = returns_arr - 0.02 / 252
    sharpe = 0.0
    if len(excess) > 1 and excess.std() > 0:
        sharpe = round(float(np.sqrt(252) * excess.mean() / excess.std()), 4)

    return {
        "win_rate": win_rate,
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe,
        "num_trades": len(trades),
        "avg_hold_days": avg_hold_days,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
    }


def run_backtest(df: pd.DataFrame, ema_period: int = 200) -> dict:
    df_signals = generate_signals(df, ema_period=ema_period)
    trades = extract_trades(df_signals)
    metrics = calculate_metrics(trades)

    signals_out = df_signals[["open", "close", "ema200", "signal"]].copy()
    signals_out.index = signals_out.index.strftime("%Y-%m-%d")

    return {
        "trades": trades,
        "metrics": metrics,
        "signals": signals_out.reset_index().rename(columns={"index": "date"}).to_dict(orient="records"),
    }
```

- [ ] **Step 4: Run all backtest engine tests**

```bash
pytest tests/test_backtest_engine.py -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/backtest_engine.py backend/tests/test_backtest_engine.py
git commit -m "feat: backtest metrics + run_backtest orchestrator"
```

---

## Task 5: Data fetcher — Massive API + Parquet cache

**Files:**
- Create: `backend/app/services/data_fetcher.py`
- Create: `backend/tests/test_data_fetcher.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_data_fetcher.py
import pandas as pd
import pytest
from unittest.mock import patch, AsyncMock
from app.services.data_fetcher import parse_massive_response, get_cache_path, is_cache_fresh


def test_parse_massive_response_returns_dataframe():
    raw = {
        "results": [
            {"t": 1609459200000, "o": 130.0, "h": 133.0, "l": 129.0, "c": 132.0, "v": 1000000},
            {"t": 1609545600000, "o": 132.0, "h": 135.0, "l": 131.0, "c": 134.0, "v": 1100000},
        ]
    }
    df = parse_massive_response(raw)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df.index.name == "date"


def test_parse_empty_response_returns_empty_df():
    raw = {"results": []}
    df = parse_massive_response(raw)
    assert len(df) == 0


def test_get_cache_path_contains_ticker():
    path = get_cache_path("AAPL")
    assert "AAPL" in str(path)
    assert str(path).endswith(".parquet")


def test_is_cache_fresh_returns_false_for_nonexistent(tmp_path):
    from pathlib import Path
    result = is_cache_fresh(tmp_path / "nonexistent.parquet")
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_data_fetcher.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement data fetcher**

```python
# backend/app/services/data_fetcher.py
import os
import pandas as pd
import httpx
from pathlib import Path
from datetime import datetime, timedelta, timezone

CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

MASSIVE_BASE_URL = os.getenv("MASSIVE_BASE_URL", "https://api.polygon.io")
MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY", "")
CACHE_MAX_AGE_HOURS = 23


def get_cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}.parquet"


def is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(tz=timezone.utc) - mtime
    return age < timedelta(hours=CACHE_MAX_AGE_HOURS)


def parse_massive_response(raw: dict) -> pd.DataFrame:
    results = raw.get("results", [])
    if not results:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    rows = []
    for r in results:
        rows.append({
            "date": pd.to_datetime(r["t"], unit="ms", utc=True).date(),
            "open": r["o"],
            "high": r["h"],
            "low": r["l"],
            "close": r["c"],
            "volume": r["v"],
        })
    df = pd.DataFrame(rows).set_index("date")
    df.index.name = "date"
    return df


async def fetch_ticker_data(ticker: str, from_date: str = "2010-01-01") -> pd.DataFrame:
    cache_path = get_cache_path(ticker)

    if is_cache_fresh(cache_path):
        return pd.read_parquet(cache_path)

    url = (
        f"{MASSIVE_BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/"
        f"{datetime.now().strftime('%Y-%m-%d')}"
        f"?adjusted=true&sort=asc&limit=50000&apiKey={MASSIVE_API_KEY}"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        raw = response.json()

    df = parse_massive_response(raw)
    if len(df) > 0:
        df.to_parquet(cache_path)

    return df


async def fetch_universe_data(tickers: list[str]) -> dict[str, pd.DataFrame]:
    import asyncio
    results = await asyncio.gather(
        *[fetch_ticker_data(t) for t in tickers],
        return_exceptions=True
    )
    out = {}
    for ticker, result in zip(tickers, results):
        if isinstance(result, Exception):
            print(f"[WARN] Failed to fetch {ticker}: {result}")
        else:
            out[ticker] = result
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_data_fetcher.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data_fetcher.py backend/tests/test_data_fetcher.py
git commit -m "feat: data fetcher with Massive API + Parquet cache"
```

---

## Task 6: Pydantic schemas + routers

**Files:**
- Create: `backend/app/models/schemas.py`
- Create: `backend/app/routers/universe.py`
- Create: `backend/app/routers/backtest.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/models/__init__.py`

- [ ] **Step 1: Create __init__ files**

```bash
touch backend/app/routers/__init__.py
touch backend/app/services/__init__.py
touch backend/app/models/__init__.py
touch backend/app/__init__.py
touch backend/tests/__init__.py
```

- [ ] **Step 2: Create schemas**

```python
# backend/app/models/schemas.py
from pydantic import BaseModel
from typing import Optional


class TradeRecord(BaseModel):
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    return_pct: float
    hold_days: int


class TickerMetrics(BaseModel):
    win_rate: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    num_trades: int
    avg_hold_days: float
    best_trade: float
    worst_trade: float


class SignalPoint(BaseModel):
    date: str
    open: float
    close: float
    ema200: float
    signal: int


class TickerResult(BaseModel):
    ticker: str
    last_signal: int
    trades: list[TradeRecord]
    metrics: Optional[TickerMetrics]
    signals: list[SignalPoint]


class BacktestRequest(BaseModel):
    universe_size: int  # 5, 10, or 20
    ema_period: int = 200
    from_date: str = "2010-01-01"


class BacktestResponse(BaseModel):
    results: list[TickerResult]
    universe_size: int
    ema_period: int
```

- [ ] **Step 3: Create universe router**

```python
# backend/app/routers/universe.py
from fastapi import APIRouter, HTTPException
from app.services.universe import get_tickers

router = APIRouter()


@router.get("/{size}")
def get_universe(size: int):
    try:
        tickers = get_tickers(size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"size": size, "tickers": tickers}
```

- [ ] **Step 4: Create backtest router**

```python
# backend/app/routers/backtest.py
from fastapi import APIRouter, HTTPException
from app.models.schemas import BacktestRequest, BacktestResponse, TickerResult, TickerMetrics, TradeRecord, SignalPoint
from app.services.universe import get_tickers
from app.services.data_fetcher import fetch_universe_data
from app.services.backtest_engine import run_backtest

router = APIRouter()


@router.post("/run", response_model=BacktestResponse)
async def run_backtest_endpoint(req: BacktestRequest):
    try:
        tickers = get_tickers(req.universe_size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    data = await fetch_universe_data(tickers)

    results = []
    for ticker in tickers:
        if ticker not in data or data[ticker].empty:
            continue
        df = data[ticker]

        # Filter by from_date
        df = df[df.index >= req.from_date] if hasattr(df.index, '__ge__') else df

        result = run_backtest(df, ema_period=req.ema_period)

        results.append(TickerResult(
            ticker=ticker,
            last_signal=result["signals"][-1]["signal"] if result["signals"] else 0,
            trades=[TradeRecord(**t) for t in result["trades"]],
            metrics=TickerMetrics(**result["metrics"]) if result["metrics"] else None,
            signals=[SignalPoint(**s) for s in result["signals"]],
        ))

    return BacktestResponse(
        results=results,
        universe_size=req.universe_size,
        ema_period=req.ema_period,
    )
```

- [ ] **Step 5: Start server and test endpoints**

```bash
cd backend && source venv/bin/activate
uvicorn app.main:app --reload
```

In a new terminal:
```bash
curl http://localhost:8000/universe/5
```

Expected:
```json
{"size": 5, "tickers": ["AAPL", "MSFT", "NVDA", "AMZN", "META"]}
```

```bash
curl http://localhost:8000/health
```

Expected: `{"status": "ok"}`

- [ ] **Step 6: Run all backend tests**

```bash
pytest tests/ -v
```

Expected: all PASSED

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: schemas + API routers for universe and backtest"
```

---

## Task 7: AI analyst service

**Files:**
- Create: `backend/app/services/ai_analyst.py`
- Modify: `backend/app/routers/backtest.py`

- [ ] **Step 1: Implement AI analyst**

```python
# backend/app/services/ai_analyst.py
import os
import json
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

ANALYSIS_PROMPT = """You are a professional quantitative analyst reviewing backtesting results.

Backtest data:
{data}

Provide a structured analysis in JSON with these exact keys:
- "patterns": 2-3 bullet points on notable patterns/anomalies observed
- "risk_assessment": 2-3 bullet points on risk, drawdown, volatility concerns
- "recommendations": 2-3 bullet points on EMA period, market regime considerations
- "benchmark_comment": 1-2 sentences comparing strategy vs buy-and-hold

Be concise, professional, and data-driven. No generic advice."""


async def analyze_backtest_results(results: list[dict]) -> dict:
    summary = []
    for r in results:
        if r.get("metrics"):
            summary.append({
                "ticker": r["ticker"],
                "metrics": r["metrics"],
                "num_trades": len(r.get("trades", [])),
                "last_signal": r["last_signal"],
            })

    data_str = json.dumps(summary, indent=2)
    prompt = ANALYSIS_PROMPT.format(data=data_str)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
```

- [ ] **Step 2: Add AI analysis endpoint to backtest router**

Add to `backend/app/routers/backtest.py` (append at end of file):

```python
from app.services.ai_analyst import analyze_backtest_results


@router.post("/analyze")
async def analyze_endpoint(req: BacktestResponse):
    results_dicts = [r.model_dump() for r in req.results]
    analysis = await analyze_backtest_results(results_dicts)
    return {"analysis": analysis}
```

Also add the import at the top of the file — `from app.models.schemas import BacktestResponse` is already there.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/ai_analyst.py backend/app/routers/backtest.py
git commit -m "feat: AI analyst endpoint via Claude API"
```

---

## Task 8: Frontend project setup

**Files:**
- Create: `frontend/` (Vite scaffold)
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/src/index.css`

- [ ] **Step 1: Scaffold React + Vite + TypeScript**

```bash
cd /Users/janekstrobel/stocks-backtest
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Install dependencies**

```bash
npm install @ag-grid-community/core @ag-grid-community/react @ag-grid-community/client-side-row-model
npm install lightweight-charts
npm install axios
npm install tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: Configure Tailwind**

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

`frontend/src/index.css`:
```css
@import "tailwindcss";

:root {
  --bg-primary: #0F1117;
  --bg-secondary: #1A1D27;
  --bg-card: #1E2130;
  --green: #00C48C;
  --red: #FF4757;
  --text-primary: #E8EAED;
  --text-secondary: #8B8FA8;
  --border: #2A2D3E;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Inter', system-ui, sans-serif;
}
```

- [ ] **Step 4: Verify dev server starts**

```bash
npm run dev
```

Expected: `Local: http://localhost:5173/`

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat: frontend Vite + React + Tailwind setup"
```

---

## Task 9: Types + API client

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/types/index.ts

export interface TradeRecord {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  return_pct: number;
  hold_days: number;
}

export interface TickerMetrics {
  win_rate: number;
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  num_trades: number;
  avg_hold_days: number;
  best_trade: number;
  worst_trade: number;
}

export interface SignalPoint {
  date: string;
  open: number;
  close: number;
  ema200: number;
  signal: number;
}

export interface TickerResult {
  ticker: string;
  last_signal: number;
  trades: TradeRecord[];
  metrics: TickerMetrics | null;
  signals: SignalPoint[];
}

export interface BacktestResponse {
  results: TickerResult[];
  universe_size: number;
  ema_period: number;
}

export interface AIAnalysis {
  patterns?: string[];
  risk_assessment?: string[];
  recommendations?: string[];
  benchmark_comment?: string;
  raw?: string;
}

export type UniverseSize = 5 | 10 | 20;
export type PeriodKey = '1M' | '3M' | '6M' | '1Y' | '3Y' | '5Y' | 'ALL';
```

- [ ] **Step 2: Create API client**

```typescript
// frontend/src/api/client.ts
import axios from 'axios';
import type { BacktestResponse, AIAnalysis } from '../types';

const api = axios.create({ baseURL: '/api' });

export async function runBacktest(
  universeSize: number,
  emaPeriod: number = 200,
  fromDate: string = '2010-01-01'
): Promise<BacktestResponse> {
  const { data } = await api.post<BacktestResponse>('/backtest/run', {
    universe_size: universeSize,
    ema_period: emaPeriod,
    from_date: fromDate,
  });
  return data;
}

export async function analyzeResults(results: BacktestResponse): Promise<AIAnalysis> {
  const { data } = await api.post<{ analysis: AIAnalysis }>('/backtest/analyze', results);
  return data.analysis;
}

export async function getUniverse(size: number): Promise<string[]> {
  const { data } = await api.get<{ tickers: string[] }>(`/universe/${size}`);
  return data.tickers;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/ frontend/src/api/
git commit -m "feat: TypeScript types + API client"
```

---

## Task 10: UniverseSelector + PeriodSelector components

**Files:**
- Create: `frontend/src/components/UniverseSelector.tsx`
- Create: `frontend/src/components/PeriodSelector.tsx`

- [ ] **Step 1: Create UniverseSelector**

```typescript
// frontend/src/components/UniverseSelector.tsx
import type { UniverseSize } from '../types';

interface Props {
  value: UniverseSize;
  onChange: (size: UniverseSize) => void;
}

const sizes: UniverseSize[] = [5, 10, 20];

export function UniverseSelector({ value, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {sizes.map((s) => (
        <button
          key={s}
          onClick={() => onChange(s)}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
            value === s
              ? 'bg-[#00C48C] text-black'
              : 'bg-[#1E2130] text-[#8B8FA8] hover:bg-[#2A2D3E]'
          }`}
        >
          Top {s}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create PeriodSelector**

```typescript
// frontend/src/components/PeriodSelector.tsx
import type { PeriodKey } from '../types';

interface Props {
  value: PeriodKey;
  onChange: (period: PeriodKey) => void;
}

const periods: PeriodKey[] = ['1M', '3M', '6M', '1Y', '3Y', '5Y', 'ALL'];

export function PeriodSelector({ value, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {periods.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
            value === p
              ? 'bg-[#1E2130] text-[#00C48C] border border-[#00C48C]'
              : 'bg-[#1E2130] text-[#8B8FA8] hover:text-[#E8EAED]'
          }`}
        >
          {p}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/UniverseSelector.tsx frontend/src/components/PeriodSelector.tsx
git commit -m "feat: UniverseSelector + PeriodSelector components"
```

---

## Task 11: ResultsTable component (AG Grid)

**Files:**
- Create: `frontend/src/components/ResultsTable.tsx`

- [ ] **Step 1: Create ResultsTable**

```typescript
// frontend/src/components/ResultsTable.tsx
import { AgGridReact } from '@ag-grid-community/react';
import { ClientSideRowModelModule } from '@ag-grid-community/client-side-row-model';
import '@ag-grid-community/styles/ag-grid.css';
import '@ag-grid-community/styles/ag-theme-alpine.css';
import { useMemo } from 'react';
import type { TickerResult, PeriodKey } from '../types';
import { useNavigate } from 'react-router-dom';
import { filterByPeriod } from '../utils/period';

interface Props {
  results: TickerResult[];
  period: PeriodKey;
}

function colorCell(value: number | null) {
  if (value === null || value === undefined) return {};
  return { color: value >= 0 ? '#00C48C' : '#FF4757' };
}

export function ResultsTable({ results, period }: Props) {
  const navigate = useNavigate();

  const rowData = useMemo(() =>
    results.map((r) => {
      const filtered = filterByPeriod(r, period);
      const lastTrade = filtered.trades[filtered.trades.length - 1];
      return {
        ticker: r.ticker,
        last_signal: r.last_signal === 1 ? 'LONG' : 'FLAT',
        buy_date: lastTrade?.entry_date ?? '-',
        sell_date: lastTrade?.exit_date ?? '-',
        hold_days: lastTrade?.hold_days ?? '-',
        return_pct: filtered.metrics?.total_return ?? null,
        win_rate: filtered.metrics?.win_rate ?? null,
        sharpe: filtered.metrics?.sharpe_ratio ?? null,
        max_dd: filtered.metrics?.max_drawdown ?? null,
        num_trades: filtered.metrics?.num_trades ?? 0,
        _original: r,
      };
    }),
    [results, period]
  );

  const columnDefs = useMemo(() => [
    { field: 'ticker', headerName: 'Ticker', width: 100, pinned: 'left' as const },
    {
      field: 'last_signal', headerName: 'Signal', width: 90,
      cellStyle: (p: any) => ({ color: p.value === 'LONG' ? '#00C48C' : '#FF4757' }),
    },
    { field: 'buy_date', headerName: 'Buy Date', width: 120 },
    { field: 'sell_date', headerName: 'Sell Date', width: 120 },
    { field: 'hold_days', headerName: 'Hold (d)', width: 90 },
    {
      field: 'return_pct', headerName: 'Return %', width: 110,
      valueFormatter: (p: any) => p.value != null ? `${p.value.toFixed(2)}%` : '-',
      cellStyle: (p: any) => colorCell(p.value),
    },
    {
      field: 'win_rate', headerName: 'Win Rate', width: 100,
      valueFormatter: (p: any) => p.value != null ? `${p.value.toFixed(1)}%` : '-',
    },
    {
      field: 'sharpe', headerName: 'Sharpe', width: 90,
      valueFormatter: (p: any) => p.value != null ? p.value.toFixed(2) : '-',
    },
    {
      field: 'max_dd', headerName: 'Max DD', width: 100,
      valueFormatter: (p: any) => p.value != null ? `${p.value.toFixed(2)}%` : '-',
      cellStyle: (p: any) => colorCell(p.value),
    },
    { field: 'num_trades', headerName: 'Trades', width: 80 },
  ], []);

  return (
    <div className="ag-theme-alpine-dark w-full" style={{ height: 420 }}>
      <AgGridReact
        modules={[ClientSideRowModelModule]}
        rowData={rowData}
        columnDefs={columnDefs}
        defaultColDef={{ sortable: true, resizable: true }}
        onRowClicked={(e) => navigate(`/stock/${e.data.ticker}`)}
        rowStyle={{ cursor: 'pointer' }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Create period filter utility**

```typescript
// frontend/src/utils/period.ts
import type { TickerResult, PeriodKey } from '../types';
import { run_backtest_on_filtered } from './backtest_local';

const PERIOD_DAYS: Record<PeriodKey, number | null> = {
  '1M': 30,
  '3M': 90,
  '6M': 180,
  '1Y': 365,
  '3Y': 1095,
  '5Y': 1825,
  'ALL': null,
};

export function filterByPeriod(result: TickerResult, period: PeriodKey): TickerResult {
  const days = PERIOD_DAYS[period];
  if (!days) return result;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffStr = cutoff.toISOString().split('T')[0];

  const filteredTrades = result.trades.filter(t => t.entry_date >= cutoffStr);
  const returns = filteredTrades.map(t => t.return_pct);
  const winning = returns.filter(r => r > 0);

  const metrics = filteredTrades.length === 0 ? null : {
    win_rate: winning.length / filteredTrades.length * 100,
    total_return: returns.reduce((a, b) => a + b, 0),
    max_drawdown: 0, // simplified for period filter
    sharpe_ratio: 0,
    num_trades: filteredTrades.length,
    avg_hold_days: filteredTrades.reduce((a, t) => a + t.hold_days, 0) / filteredTrades.length,
    best_trade: Math.max(...returns, 0),
    worst_trade: Math.min(...returns, 0),
  };

  return { ...result, trades: filteredTrades, metrics };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ResultsTable.tsx frontend/src/utils/
git commit -m "feat: ResultsTable with AG Grid + period filtering"
```

---

## Task 12: CandleChart component (TradingView)

**Files:**
- Create: `frontend/src/components/CandleChart.tsx`

- [ ] **Step 1: Create CandleChart**

```typescript
// frontend/src/components/CandleChart.tsx
import { useEffect, useRef } from 'react';
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';
import type { SignalPoint } from '../types';

interface Props {
  signals: SignalPoint[];
  trades: { entry_date: string; exit_date: string; return_pct: number }[];
}

export function CandleChart({ signals, trades }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || signals.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0F1117' },
        textColor: '#8B8FA8',
      },
      grid: {
        vertLines: { color: '#1E2130' },
        horzLines: { color: '#1E2130' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      width: containerRef.current.clientWidth,
      height: 400,
    });

    // Candle series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00C48C',
      downColor: '#FF4757',
      borderUpColor: '#00C48C',
      borderDownColor: '#FF4757',
      wickUpColor: '#00C48C',
      wickDownColor: '#FF4757',
    });

    candleSeries.setData(
      signals.map((s) => ({
        time: s.date as any,
        open: s.open,
        high: Math.max(s.open, s.close),
        low: Math.min(s.open, s.close),
        close: s.close,
      }))
    );

    // EMA200 line
    const emaSeries = chart.addLineSeries({
      color: '#F59E0B',
      lineWidth: 2,
      title: 'EMA 200',
    });

    emaSeries.setData(
      signals.map((s) => ({ time: s.date as any, value: s.ema200 }))
    );

    // Buy/Sell markers
    const markers = trades.flatMap((t) => [
      {
        time: t.entry_date as any,
        position: 'belowBar' as const,
        color: '#00C48C',
        shape: 'arrowUp' as const,
        text: 'BUY',
      },
      {
        time: t.exit_date as any,
        position: 'aboveBar' as const,
        color: '#FF4757',
        shape: 'arrowDown' as const,
        text: `SELL ${t.return_pct >= 0 ? '+' : ''}${t.return_pct.toFixed(1)}%`,
      },
    ]);
    candleSeries.setMarkers(markers);

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [signals, trades]);

  return <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/CandleChart.tsx
git commit -m "feat: CandleChart with TradingView Lightweight Charts + EMA + markers"
```

---

## Task 13: TradeHistory component

**Files:**
- Create: `frontend/src/components/TradeHistory.tsx`

- [ ] **Step 1: Create TradeHistory**

```typescript
// frontend/src/components/TradeHistory.tsx
import type { TradeRecord } from '../types';

interface Props {
  trades: TradeRecord[];
}

export function TradeHistory({ trades }: Props) {
  const sorted = [...trades].reverse();

  return (
    <div className="overflow-auto max-h-72">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[#8B8FA8] border-b border-[#2A2D3E]">
            <th className="text-left py-2 pr-4">Entry Date</th>
            <th className="text-left py-2 pr-4">Exit Date</th>
            <th className="text-right py-2 pr-4">Hold (d)</th>
            <th className="text-right py-2 pr-4">Entry</th>
            <th className="text-right py-2 pr-4">Exit</th>
            <th className="text-right py-2">Return</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t, i) => (
            <tr key={i} className="border-b border-[#1E2130] hover:bg-[#1E2130]">
              <td className="py-2 pr-4 text-[#8B8FA8]">{t.entry_date}</td>
              <td className="py-2 pr-4 text-[#8B8FA8]">{t.exit_date}</td>
              <td className="py-2 pr-4 text-right">{t.hold_days}</td>
              <td className="py-2 pr-4 text-right">${t.entry_price.toFixed(2)}</td>
              <td className="py-2 pr-4 text-right">${t.exit_price.toFixed(2)}</td>
              <td
                className="py-2 text-right font-medium"
                style={{ color: t.return_pct >= 0 ? '#00C48C' : '#FF4757' }}
              >
                {t.return_pct >= 0 ? '+' : ''}{t.return_pct.toFixed(2)}%
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
git add frontend/src/components/TradeHistory.tsx
git commit -m "feat: TradeHistory table component"
```

---

## Task 14: OptimizationBook component

**Files:**
- Create: `frontend/src/components/OptimizationBook.tsx`

- [ ] **Step 1: Create OptimizationBook**

```typescript
// frontend/src/components/OptimizationBook.tsx
import { useState } from 'react';
import { runBacktest, analyzeResults } from '../api/client';
import type { BacktestResponse, AIAnalysis } from '../types';

const EMA_PERIODS = [50, 100, 150, 200, 250];

interface Props {
  universeSize: number;
  currentResults: BacktestResponse | null;
}

interface OptRow {
  period: number;
  avgReturn: number;
  avgWinRate: number;
  avgSharpe: number;
  avgMaxDD: number;
}

export function OptimizationBook({ universeSize, currentResults }: Props) {
  const [optimRows, setOptimRows] = useState<OptRow[]>([]);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [loadingOptim, setLoadingOptim] = useState(false);
  const [loadingAI, setLoadingAI] = useState(false);

  async function runOptimization() {
    setLoadingOptim(true);
    const rows: OptRow[] = [];
    for (const period of EMA_PERIODS) {
      const res = await runBacktest(universeSize, period);
      const metrics = res.results.map(r => r.metrics).filter(Boolean) as any[];
      if (metrics.length === 0) continue;
      rows.push({
        period,
        avgReturn: metrics.reduce((a, m) => a + m.total_return, 0) / metrics.length,
        avgWinRate: metrics.reduce((a, m) => a + m.win_rate, 0) / metrics.length,
        avgSharpe: metrics.reduce((a, m) => a + m.sharpe_ratio, 0) / metrics.length,
        avgMaxDD: metrics.reduce((a, m) => a + m.max_drawdown, 0) / metrics.length,
      });
    }
    setOptimRows(rows);
    setLoadingOptim(false);
  }

  async function runAIAnalysis() {
    if (!currentResults) return;
    setLoadingAI(true);
    const result = await analyzeResults(currentResults);
    setAnalysis(result);
    setLoadingAI(false);
  }

  return (
    <div className="space-y-6 p-4 bg-[#1A1D27] rounded-lg">
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[#E8EAED] font-medium">Parameter Optimization</h3>
          <button
            onClick={runOptimization}
            disabled={loadingOptim}
            className="px-4 py-2 bg-[#00C48C] text-black rounded text-sm font-medium disabled:opacity-50"
          >
            {loadingOptim ? 'Running...' : 'Run Optimization'}
          </button>
        </div>

        {optimRows.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[#8B8FA8] border-b border-[#2A2D3E]">
                <th className="text-left py-2 pr-4">EMA Period</th>
                <th className="text-right py-2 pr-4">Avg Return</th>
                <th className="text-right py-2 pr-4">Avg Win Rate</th>
                <th className="text-right py-2 pr-4">Avg Sharpe</th>
                <th className="text-right py-2">Avg Max DD</th>
              </tr>
            </thead>
            <tbody>
              {optimRows.map((r) => (
                <tr key={r.period} className={`border-b border-[#1E2130] ${r.period === 200 ? 'bg-[#1E2130]' : ''}`}>
                  <td className="py-2 pr-4 font-medium">{r.period} {r.period === 200 && <span className="text-[#8B8FA8] text-xs">(current)</span>}</td>
                  <td className="py-2 pr-4 text-right" style={{ color: r.avgReturn >= 0 ? '#00C48C' : '#FF4757' }}>
                    {r.avgReturn.toFixed(2)}%
                  </td>
                  <td className="py-2 pr-4 text-right">{r.avgWinRate.toFixed(1)}%</td>
                  <td className="py-2 pr-4 text-right">{r.avgSharpe.toFixed(2)}</td>
                  <td className="py-2 text-right" style={{ color: '#FF4757' }}>{r.avgMaxDD.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="border-t border-[#2A2D3E] pt-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[#E8EAED] font-medium">AI Analysis</h3>
          <button
            onClick={runAIAnalysis}
            disabled={loadingAI || !currentResults}
            className="px-4 py-2 bg-[#1E2130] border border-[#00C48C] text-[#00C48C] rounded text-sm font-medium disabled:opacity-50"
          >
            {loadingAI ? 'Analyzing...' : 'Run AI Analysis'}
          </button>
        </div>

        {analysis && (
          <div className="space-y-4 text-sm">
            {analysis.patterns && (
              <div>
                <p className="text-[#8B8FA8] mb-1 uppercase text-xs tracking-wider">Patterns</p>
                <ul className="space-y-1">
                  {analysis.patterns.map((p, i) => <li key={i} className="text-[#E8EAED]">• {p}</li>)}
                </ul>
              </div>
            )}
            {analysis.risk_assessment && (
              <div>
                <p className="text-[#8B8FA8] mb-1 uppercase text-xs tracking-wider">Risk</p>
                <ul className="space-y-1">
                  {analysis.risk_assessment.map((p, i) => <li key={i} className="text-[#FF4757]">• {p}</li>)}
                </ul>
              </div>
            )}
            {analysis.recommendations && (
              <div>
                <p className="text-[#8B8FA8] mb-1 uppercase text-xs tracking-wider">Recommendations</p>
                <ul className="space-y-1">
                  {analysis.recommendations.map((p, i) => <li key={i} className="text-[#00C48C]">• {p}</li>)}
                </ul>
              </div>
            )}
            {analysis.benchmark_comment && (
              <div>
                <p className="text-[#8B8FA8] mb-1 uppercase text-xs tracking-wider">vs Benchmark</p>
                <p className="text-[#E8EAED]">{analysis.benchmark_comment}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/OptimizationBook.tsx
git commit -m "feat: OptimizationBook with parameter grid + AI analysis"
```

---

## Task 15: Dashboard + StockDetail pages + App routing

**Files:**
- Create: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/pages/StockDetail.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/index.html`

- [ ] **Step 1: Install react-router-dom**

```bash
cd frontend && npm install react-router-dom
```

- [ ] **Step 2: Create Dashboard page**

```typescript
// frontend/src/pages/Dashboard.tsx
import { useState } from 'react';
import { UniverseSelector } from '../components/UniverseSelector';
import { PeriodSelector } from '../components/PeriodSelector';
import { ResultsTable } from '../components/ResultsTable';
import { OptimizationBook } from '../components/OptimizationBook';
import { runBacktest } from '../api/client';
import type { UniverseSize, PeriodKey, BacktestResponse } from '../types';

export function Dashboard() {
  const [universeSize, setUniverseSize] = useState<UniverseSize>(10);
  const [period, setPeriod] = useState<PeriodKey>('1Y');
  const [results, setResults] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [showOptim, setShowOptim] = useState(false);

  async function handleRun() {
    setLoading(true);
    try {
      const data = await runBacktest(universeSize);
      setResults(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#0F1117] p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-[#E8EAED] tracking-tight">
            EMA200 Backtest
          </h1>
          <span className="text-xs text-[#8B8FA8]">NAS100 · Daily Close · Massive</span>
        </div>

        <div className="flex items-center gap-4 flex-wrap">
          <UniverseSelector value={universeSize} onChange={setUniverseSize} />
          <PeriodSelector value={period} onChange={setPeriod} />
          <button
            onClick={handleRun}
            disabled={loading}
            className="px-6 py-2 bg-[#00C48C] text-black rounded font-medium text-sm disabled:opacity-50 ml-auto"
          >
            {loading ? 'Running...' : 'Run Backtest'}
          </button>
        </div>

        {results && (
          <>
            <div className="bg-[#1A1D27] rounded-lg p-4">
              <ResultsTable results={results.results} period={period} />
            </div>

            <div>
              <button
                onClick={() => setShowOptim(!showOptim)}
                className="text-sm text-[#8B8FA8] hover:text-[#E8EAED] underline"
              >
                {showOptim ? 'Hide' : 'Show'} Optimization Book
              </button>
              {showOptim && (
                <div className="mt-3">
                  <OptimizationBook universeSize={universeSize} currentResults={results} />
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create StockDetail page**

```typescript
// frontend/src/pages/StockDetail.tsx
import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { CandleChart } from '../components/CandleChart';
import { TradeHistory } from '../components/TradeHistory';
import { runBacktest } from '../api/client';
import type { TickerResult } from '../types';

function MetricCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-[#1E2130] rounded p-4">
      <p className="text-[#8B8FA8] text-xs uppercase tracking-wider mb-1">{label}</p>
      <p className="text-xl font-semibold" style={{ color: color ?? '#E8EAED' }}>{value}</p>
    </div>
  );
}

export function StockDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const [result, setResult] = useState<TickerResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const data = await runBacktest(20);
      const found = data.results.find(r => r.ticker === ticker);
      setResult(found ?? null);
      setLoading(false);
    }
    load();
  }, [ticker]);

  if (loading) return <div className="p-6 text-[#8B8FA8]">Loading...</div>;
  if (!result) return <div className="p-6 text-[#FF4757]">Ticker not found.</div>;

  const m = result.metrics;

  return (
    <div className="min-h-screen bg-[#0F1117] p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/')} className="text-[#8B8FA8] hover:text-[#E8EAED] text-sm">
            ← Back
          </button>
          <h1 className="text-xl font-semibold text-[#E8EAED]">{ticker}</h1>
          <span
            className="px-2 py-1 rounded text-xs font-medium"
            style={{
              background: result.last_signal === 1 ? '#00C48C20' : '#FF475720',
              color: result.last_signal === 1 ? '#00C48C' : '#FF4757',
            }}
          >
            {result.last_signal === 1 ? 'LONG' : 'FLAT'}
          </span>
        </div>

        {m && (
          <div className="grid grid-cols-4 gap-3">
            <MetricCard label="Total Return" value={`${m.total_return >= 0 ? '+' : ''}${m.total_return.toFixed(2)}%`} color={m.total_return >= 0 ? '#00C48C' : '#FF4757'} />
            <MetricCard label="Win Rate" value={`${m.win_rate.toFixed(1)}%`} />
            <MetricCard label="Sharpe" value={m.sharpe_ratio.toFixed(2)} />
            <MetricCard label="Max DD" value={`${m.max_drawdown.toFixed(2)}%`} color="#FF4757" />
          </div>
        )}

        <div className="bg-[#1A1D27] rounded-lg p-4">
          <CandleChart signals={result.signals} trades={result.trades} />
        </div>

        <div className="bg-[#1A1D27] rounded-lg p-4">
          <h3 className="text-[#E8EAED] font-medium mb-3">Trade History</h3>
          <TradeHistory trades={result.trades} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Update App.tsx**

```typescript
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { StockDetail } from './pages/StockDetail';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/stock/:ticker" element={<StockDetail />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 5: Update index.html title**

```html
<!-- frontend/index.html — update <title> -->
<title>Backtest Terminal</title>
```

- [ ] **Step 6: Build and verify**

```bash
cd frontend && npm run build
```

Expected: no errors, `dist/` folder created

- [ ] **Step 7: Full smoke test**

1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:5173`
4. Add `MASSIVE_API_KEY` and `ANTHROPIC_API_KEY` to `backend/.env`
5. Click "Run Backtest" → table populates
6. Click a ticker → chart loads
7. Click "Show Optimization Book" → visible

- [ ] **Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat: Dashboard + StockDetail pages, full app routing"
```

---

## Task 16: Deployment configuration

**Files:**
- Create: `backend/railway.json`
- Create: `frontend/vercel.json`
- Create: `.gitignore`

- [ ] **Step 1: Create root .gitignore**

```
# .gitignore (root)
backend/venv/
backend/cache/*.parquet
backend/.env
frontend/node_modules/
frontend/dist/
**/__pycache__/
**/*.pyc
.env
```

- [ ] **Step 2: Create Railway config**

```json
// backend/railway.json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

- [ ] **Step 3: Create Vercel config**

```json
// frontend/vercel.json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://YOUR_RAILWAY_URL/:path*" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

> Replace `YOUR_RAILWAY_URL` with actual Railway deployment URL after backend deploy.

- [ ] **Step 4: Deploy backend to Railway**

```bash
# Install Railway CLI if not installed
npm install -g @railway/cli
railway login
cd backend
railway init
railway up
```

Set env vars in Railway dashboard: `MASSIVE_API_KEY`, `ANTHROPIC_API_KEY`, `MASSIVE_BASE_URL`

- [ ] **Step 5: Deploy frontend to Vercel**

```bash
npm install -g vercel
cd frontend && npm run build
vercel --prod
```

- [ ] **Step 6: Final commit**

```bash
git add .gitignore backend/railway.json frontend/vercel.json
git commit -m "feat: Railway + Vercel deployment config"
```

---

## Self-Review

**Spec coverage check:**
- [x] FastAPI + React, separate deploy → Task 1, 8, 16
- [x] Massive API data + Parquet cache → Task 5
- [x] NAS100 Top5/10/20 universes → Task 2
- [x] EMA200 signal engine → Task 3
- [x] Metrics (Win Rate, Sharpe, Max DD, etc.) → Task 4
- [x] AG Grid table with Buy/Sell date, hold, return, index → Task 11
- [x] Period selector 1M/3M/6M/1Y/3Y/5Y/ALL → Task 10, 11
- [x] TradingView chart + EMA line + markers → Task 12
- [x] Trade history table → Task 13
- [x] Optimization Book (parameter grid + AI analysis) → Task 14
- [x] Dark mode terminal styling → Task 8, all components
- [x] Claude AI analysis via Anthropic API → Task 7

**Missing:** Index (Buy & Hold) comparison column in ResultsTable — the `vs Index %` column defined in spec requires fetching QQQ/SPY data as benchmark. This is addable post-MVP without breaking architecture. Noted as known gap.
