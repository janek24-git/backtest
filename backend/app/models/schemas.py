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
