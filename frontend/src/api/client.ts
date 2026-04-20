import axios from 'axios';
import type { BacktestResponse, AIAnalysis, Big5BacktestResponse, Big5AnalysisResponse } from '../types';

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
  });
  return res;
}

export async function runBig5Backtest(
  indicator: 'EMA' | 'SMA' = 'EMA',
  period: number = 200,
  fromDate: string = '2000-01-01',
  toDate: string = '2025-12-31',
): Promise<Big5BacktestResponse> {
  const { data } = await api.post<Big5BacktestResponse>('/big5/run', {
    indicator,
    period,
    from_date: fromDate,
    to_date: toDate,
  });
  return data;
}
