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
    optimized: bool = False


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
    optimized: bool = False


class Big5AnalysisRequest(BaseModel):
    results: list[Big5ComboResult]
    indicator: str
    period: int
    from_date: str
    to_date: str
    optimized: bool = False


class Big5AnalysisResponse(BaseModel):
    analysis: str


# ── Episodic Pivot ─────────────────────────────────────────────────────────────

class EPCandidate(BaseModel):
    ticker: str
    name: str
    sector: str
    mcap: str
    gap_pct: float           # Gap-up % (open vs prev close)
    rel_vol: float           # Relatives Volumen vs 20T-Schnitt
    catalyst: str            # "Earnings", "News", "Unknown"
    catalyst_detail: str     # Earnings EPS detail oder News-Titel
    base_days: int           # Tage in Konsolidierung vor Gap
    score: float             # 0–10
    score_comment: str
    entry_zone_low: float    # Tages-Open als ORB-Proxy
    entry_zone_high: float   # Open + 0.5%
    lotd_stop: float         # Tages-Low (vorheriger Tag als Proxy)
    price: float
    date: str


class EPInvestProposal(BaseModel):
    kapital: float
    safe_play_shares: int
    safe_play_cost: float
    safe_play_max_loss: float
    safe_play_target_gain: float
    yolo_play_budget: float
    yolo_play_delta_low: float
    yolo_play_delta_high: float
    yolo_play_target_gain: float


class EPScanResponse(BaseModel):
    candidates: list[EPCandidate]
    proposals: dict[str, EPInvestProposal]   # ticker → proposal
    timestamp: str


class EPBacktestRequest(BaseModel):
    from_date: str = "2016-01-01"
    to_date: str = "2026-01-01"
    min_gap_pct: float = 0.10
    min_rel_vol: float = 2.0
    require_earnings: bool = False


class EPBacktestTrade(BaseModel):
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    stop_price: float
    gap_pct: float
    rel_vol: float
    catalyst: str
    hold_days: int
    perf_pct: float
    hit_stop: bool


class EPBacktestMetrics(BaseModel):
    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    expectancy: float
    sharpe: float
    max_drawdown: float
    total_return: float
    pead_5d: float    # avg return after 5 trading days
    pead_10d: float   # avg return after 10 trading days
    pead_20d: float   # avg return after 20 trading days
    pead_60d: float   # avg return after 60 trading days


class EPBacktestResponse(BaseModel):
    trades: list[EPBacktestTrade]
    metrics: EPBacktestMetrics
    from_date: str
    to_date: str
