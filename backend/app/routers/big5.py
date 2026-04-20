import logging
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    Big5BacktestRequest, Big5BacktestResponse,
    Big5ComboResult, Big5ComboMetrics, Big5Trade,
)
from app.services.big5_top5 import fetch_candidate_data, compute_top5_history
from app.services.big5_engine import run_all_combinations

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run", response_model=Big5BacktestResponse)
async def run_big5_backtest(req: Big5BacktestRequest):
    try:
        # Fetch price data for all candidates
        price_data = await fetch_candidate_data(req.from_date, req.to_date)
        if not price_data:
            raise HTTPException(status_code=500, detail="No price data available")

        # Build daily top5 history
        top5_history = compute_top5_history(price_data)

        # Run all 8 combinations
        raw_results = run_all_combinations(
            price_data, top5_history,
            indicator=req.indicator,
            period=req.period,
        )

        results = []
        for r in raw_results:
            trades = [Big5Trade(**t) for t in r["trades"]]
            metrics = Big5ComboMetrics(**r["metrics"])
            results.append(Big5ComboResult(kombination=r["kombination"], trades=trades, metrics=metrics))

        return Big5BacktestResponse(
            results=results,
            indicator=req.indicator,
            period=req.period,
            from_date=req.from_date,
            to_date=req.to_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Big5 backtest failed")
        raise HTTPException(status_code=500, detail=str(e))
