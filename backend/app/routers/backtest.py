import pandas as pd
from fastapi import APIRouter, HTTPException
from app.models.schemas import BacktestRequest, BacktestResponse, TickerResult, TickerMetrics, TradeRecord, SignalPoint
from app.services.universe import get_tickers
from app.services.data_fetcher import fetch_universe_data
from app.services.backtest_engine import run_backtest

router = APIRouter()


@router.post("/run", response_model=BacktestResponse)
async def run_backtest_endpoint(req: BacktestRequest):
    try:
        tickers = get_tickers(req.universe_size, req.universe_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    data = await fetch_universe_data(tickers)

    results = []
    for ticker in tickers:
        if ticker not in data or data[ticker].empty:
            continue
        df = data[ticker]

        # Calculate EMA on full history first (TradingView-compatible: more history = more stable EMA)
        from_date = pd.to_datetime(req.from_date).date()
        result = run_backtest(df, ema_period=req.ema_period, from_date=from_date)

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
        universe_type=req.universe_type,
        ema_period=req.ema_period,
    )


from app.services.ai_analyst import analyze_backtest_results


@router.post("/analyze")
async def analyze_endpoint(req: BacktestResponse):
    results_dicts = [r.model_dump() for r in req.results]
    analysis = await analyze_backtest_results(results_dicts)
    return {"analysis": analysis}
