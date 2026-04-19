import type { TickerResult, PeriodKey, TickerMetrics } from '../types';

const PERIOD_DAYS: Record<PeriodKey, number | null> = {
  '1M': 30,
  '3M': 90,
  '6M': 180,
  '1Y': 365,
  '3Y': 1095,
  '5Y': 1825,
  'ALL': null,
};

export function filterByPeriod(result: TickerResult, period: PeriodKey): TickerResult {
  const days = PERIOD_DAYS[period];
  if (!days) return result;

  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffStr = cutoff.toISOString().split('T')[0];

  const filteredTrades = result.trades.filter(t => t.entry_date >= cutoffStr);

  if (filteredTrades.length === 0) {
    return { ...result, trades: [], metrics: null };
  }

  const returns = filteredTrades.map(t => t.return_pct);
  const winning = returns.filter(r => r > 0);

  const metrics: TickerMetrics = {
    win_rate: Math.round((winning.length / filteredTrades.length) * 10000) / 100,
    total_return: Math.round(returns.reduce((a, b) => a + b, 0) * 10000) / 10000,
    max_drawdown: 0,
    sharpe_ratio: 0,
    num_trades: filteredTrades.length,
    avg_hold_days: Math.round(filteredTrades.reduce((a, t) => a + t.hold_days, 0) / filteredTrades.length * 10) / 10,
    best_trade: Math.max(...returns),
    worst_trade: Math.min(...returns),
  };

  return { ...result, trades: filteredTrades, metrics };
}
