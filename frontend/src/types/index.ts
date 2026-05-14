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
  universe_type: string;
  ema_period: number;
}

export interface AIAnalysis {
  patterns?: string[];
  risk_assessment?: string[];
  recommendations?: string[];
  benchmark_comment?: string;
  raw?: string;
}

export type UniverseType = 'SP500' | 'NAS100';

// ── Big5 Backtest ──────────────────────────────────────────────────────────

export interface Big5Trade {
  nr: number;
  typ: 'KAUF' | 'VERKAUF';
  ticker: string;
  datum: string;
  haltdauer: number;
  open_preis: number;
  perf_pct: number;
  kum_perf_pct: number;
  kapital_eur: number;
}

export interface Big5ComboMetrics {
  num_trades: number;
  win_rate: number;
  total_return: number;
  sharpe: number;
  max_drawdown: number;
  portfolio_end_eur: number;
  slots_used: number;
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
  optimized?: boolean;
  universe?: string;
}

export interface Big5AnalysisResponse {
  analysis: string;
}
export type UniverseSize = 5 | 10 | 20;
export type PeriodKey = '1M' | '3M' | '6M' | '1Y' | '3Y' | '5Y' | 'ALL';

// ── Journal ────────────────────────────────────────────────────────────────

export interface JournalTrade {
  id: string;
  datum: string;
  ticker: string;
  richtung: 'LONG' | 'SHORT';
  einstieg: number;
  ausstieg: number | null;
  stueck: number;
  signal: string | null;
  notiz: string | null;
}

export interface JournalEquityPoint {
  date: string;
  ticker: string;
  equity: number;
}

export interface JournalStats {
  total_trades: number;
  closed_trades: number;
  open_trades: number;
  total_pnl: number;
  win_rate: number;
  avg_return_pct: number;
  best_trade_pct: number;
  worst_trade_pct: number;
  equity_curve: JournalEquityPoint[];
}

// ── Episodic Pivot ────────────────────────────────────────────────────────────

export interface EPInvestProposal {
  kapital: number;
  safe_play_shares: number;
  safe_play_cost: number;
  safe_play_max_loss: number;
  safe_play_target_gain: number;
  yolo_play_budget: number;
  yolo_play_delta_low: number;
  yolo_play_delta_high: number;
  yolo_play_target_gain: number;
}

export interface EPCandidate {
  ticker: string;
  name: string;
  sector: string;
  mcap: string;
  gap_pct: number;
  rel_vol: number;
  catalyst: string;
  catalyst_detail: string;
  base_days: number;
  score: number;
  score_comment: string;
  entry_zone_low: number;
  entry_zone_high: number;
  lotd_stop: number;
  price: number;
  date: string;
  vol_trend_7d: number;
}

export interface EPScanResponse {
  candidates: EPCandidate[];
  proposals: Record<string, EPInvestProposal>;
  timestamp: string;
}

export interface EPBacktestTrade {
  ticker: string;
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  stop_price: number;
  gap_pct: number;
  rel_vol: number;
  catalyst: string;
  hold_days: number;
  perf_pct: number;
  hit_stop: boolean;
}

export interface EPBacktestMetrics {
  num_trades: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  expectancy: number;
  sharpe: number;
  max_drawdown: number;
  total_return: number;
  pead_5d: number;
  pead_10d: number;
  pead_20d: number;
  pead_60d: number;
}

export interface EPBacktestResponse {
  trades: EPBacktestTrade[];
  metrics: EPBacktestMetrics;
  from_date: string;
  to_date: string;
}

// ── Forward Testing ──────────────────────────────────────────────────────────

export interface ForwardTrade {
  id: string;
  ticker: string;
  signal_date: string;
  entry_price: number;
  ema200: number;
  tp_price: number;
  sl_price: number;
  tp_pct: number;
  sl_pct: number;
  status: 'OPEN' | 'TP_HIT' | 'SL_HIT' | 'MANUALLY_CLOSED';
  exit_price: number | null;
  exit_date: string | null;
  result_pct: number | null;
  source: 'BIG5' | 'MARKET';
  signal_type: string;
  rel_vol: number | null;
  pct_above_ema: number | null;
  created_at: string;
}

export interface ForwardTradesResponse {
  trades: ForwardTrade[];
}
