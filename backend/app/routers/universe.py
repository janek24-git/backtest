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
