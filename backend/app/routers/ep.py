import logging
from fastapi import APIRouter, HTTPException
from app.services.ep_scanner import scan_ep, send_ep_alert
from app.services.ep_backtest import run_ep_backtest
from app.models.schemas import EPScanResponse, EPBacktestRequest, EPBacktestResponse, EPBacktestMetrics

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scan", response_model=EPScanResponse)
def ep_scan():
    """Heutiger EP-Scan: Gap-ups > 10% mit Score >= 5."""
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
    """EP Backtest 2016-2026 auf S&P500-Universum."""
    try:
        data = run_ep_backtest(
            from_date=req.from_date,
            to_date=req.to_date,
            min_gap_pct=req.min_gap_pct,
            min_rel_vol=req.min_rel_vol,
            require_earnings=req.require_earnings,
        )
        return EPBacktestResponse(
            trades=data["trades"],
            metrics=EPBacktestMetrics(**data["metrics"]),
            from_date=req.from_date,
            to_date=req.to_date,
        )
    except Exception as e:
        logger.exception("EP backtest failed")
        raise HTTPException(status_code=500, detail=str(e))
