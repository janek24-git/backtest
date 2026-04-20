from pydantic import BaseModel
from typing import Literal, Optional


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
    universe_size: int  # 5 or 10 for SP500; 5, 10, or 20 for NAS100
    universe_type: str = "SP500"  # "SP500" | "NAS100"
    ema_period: int = 200
    from_date: str = "2000-01-01"


class BacktestResponse(BaseModel):
    results: list[TickerResult]
    universe_size: int
    universe_type: str
    ema_period: int


class Big5BacktestRequest(BaseModel):
    indicator: Literal["EMA", "SMA"] = "EMA"
    period: int = 200
    from_date: str = "2000-01-01"
    to_date: str = "2025-12-31"


class Big5Trade(BaseModel):
    nr: int
    typ: Literal["KAUF", "VERKAUF"]
    ticker: str
    datum: str           # Ausführungsdatum (nächster Handelstag nach Signal)
    haltdauer: int       # Handelstage gehalten (0 bei KAUF)
    open_preis: float    # Ausführungspreis (9:30 ET Open = 9:00 MESZ Näherung)
    perf_pct: float      # % Return dieser Halteperiode (0 bei KAUF)
    kum_perf_pct: float  # Kumulierte Performance aller abgeschlossenen Trades


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


class Big5AnalysisRequest(BaseModel):
    results: list[Big5ComboResult]
    indicator: str
    period: int
    from_date: str
    to_date: str


class Big5AnalysisResponse(BaseModel):
    analysis: str
