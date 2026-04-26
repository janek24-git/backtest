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
}

export interface Big5ComboMetrics {
  num_trades: number;
  win_rate: number;
  total_return: number;
  sharpe: number;
  max_drawdown: number;
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
