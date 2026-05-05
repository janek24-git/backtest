import axios from 'axios';
import type { BacktestResponse, AIAnalysis, Big5BacktestResponse, Big5AnalysisResponse, EPScanResponse, EPBacktestResponse } from '../types';

const api = axios.create({ baseURL: '/api' });

export async function runBacktest(
  universeSize: number,
  universeType: string = 'SP500',
  emaPeriod: number = 200,
  fromDate: string = '2000-01-01'
): Promise<BacktestResponse> {
  const { data } = await api.post<BacktestResponse>('/backtest/run', {
    universe_size: universeSize,
    universe_type: universeType,
    ema_period: emaPeriod,
    from_date: fromDate,
  });
  return data;
}

export async function analyzeResults(results: BacktestResponse): Promise<AIAnalysis> {
  const { data } = await api.post<{ analysis: AIAnalysis }>('/backtest/analyze', results);
  return data.analysis;
}

export async function getUniverse(size: number): Promise<string[]> {
  const { data } = await api.get<{ tickers: string[] }>(`/universe/${size}`);
  return data.tickers;
}

export async function analyzeBig5(data: Big5BacktestResponse): Promise<Big5AnalysisResponse> {
  const { data: res } = await api.post<Big5AnalysisResponse>('/big5/analyze', {
    results: data.results,
    indicator: data.indicator,
    period: data.period,
    from_date: data.from_date,
    to_date: data.to_date,
    optimized: data.optimized ?? false,
  });
  return res;
}

export async function runBig5Backtest(
  indicator: 'EMA' | 'SMA' = 'EMA',
  period: number = 200,
  fromDate: string = '2000-01-01',
  toDate: string = '2025-12-31',
  optimized: boolean = false,
): Promise<Big5BacktestResponse> {
  const { data } = await api.post<Big5BacktestResponse>('/big5/run', {
    indicator,
    period,
    from_date: fromDate,
    to_date: toDate,
    optimized,
  });
  return data;
}

export async function scanEP(): Promise<EPScanResponse> {
  const { data } = await api.get<EPScanResponse>('/ep/scan');
  return data;
}

export async function runEPBacktest(
  fromDate: string = '2016-01-01',
  toDate: string = '2026-01-01',
  minGapPct: number = 0.10,
  minRelVol: number = 2.0,
  requireEarnings: boolean = false,
  universe: 'sp500' | 'nasdaq100' | 'both' = 'both',
): Promise<EPBacktestResponse> {
  const { data } = await api.post<EPBacktestResponse>('/ep/backtest', {
    from_date: fromDate,
    to_date: toDate,
    min_gap_pct: minGapPct,
    min_rel_vol: minRelVol,
    require_earnings: requireEarnings,
    universe,
  });
  return data;
}
