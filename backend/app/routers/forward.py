from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from app.services.forward_db import (
    init_db, add_trade, list_trades, update_trade, delete_trade,
    close_trade, check_and_update_exits,
)

router = APIRouter()
init_db()


class ForwardTradeIn(BaseModel):
    ticker: str
    signal_date: str
    entry_price: float
    ema200: float
    tp_pct: float = 10.0
    sl_pct: float = 5.0
    source: str = "MARKET"
    rel_vol: Optional[float] = None
    pct_above_ema: Optional[float] = None


class ForwardTradeUpdate(BaseModel):
    ticker: Optional[str] = None
    signal_date: Optional[str] = None
    entry_price: Optional[float] = None
    ema200: Optional[float] = None
    tp_pct: Optional[float] = None
    sl_pct: Optional[float] = None
    status: Optional[str] = None
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    source: Optional[str] = None
    rel_vol: Optional[float] = None
    pct_above_ema: Optional[float] = None


@router.get("/trades")
def get_trades(status: Optional[str] = Query(None)):
    trades = list_trades(status=status)
    return {"trades": trades}


@router.post("/trades")
def create_trade(body: ForwardTradeIn):
    try:
        trade = add_trade(
            ticker=body.ticker,
            signal_date=body.signal_date,
            entry_price=body.entry_price,
            ema200=body.ema200,
            tp_pct=body.tp_pct,
            sl_pct=body.sl_pct,
            source=body.source,
            rel_vol=body.rel_vol,
            pct_above_ema=body.pct_above_ema,
        )
        return trade
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/trades/{trade_id}")
def patch_trade(trade_id: str, body: ForwardTradeUpdate):
    updated = update_trade(trade_id, **body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Trade not found")
    return updated


@router.delete("/trades/{trade_id}")
def remove_trade(trade_id: str):
    if not delete_trade(trade_id):
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"ok": True}


@router.post("/check-exits")
async def trigger_check_exits():
    closed = check_and_update_exits()
    return {"closed": closed, "count": len(closed)}
