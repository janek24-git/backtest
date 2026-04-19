import axios from 'axios';
import type { BacktestResponse, AIAnalysis } from '../types';

const api = axios.create({ baseURL: '/api' });

export async function runBacktest(
  universeSize: number,
  emaPeriod: number = 200,
  fromDate: string = '2010-01-01'
): Promise<BacktestResponse> {
  const { data } = await api.post<BacktestResponse>('/backtest/run', {
    universe_size: universeSize,
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
