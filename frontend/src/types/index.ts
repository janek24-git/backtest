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
