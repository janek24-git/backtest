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

  // Max Drawdown auf Equity-Kurve
  let equity = 100, peak = 100, maxDD = 0;
  for (const r of returns) {
    equity *= (1 + r / 100);
    if (equity > peak) peak = equity;
    const dd = (peak - equity) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  // Sharpe annualisiert (rf=2%)
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length / 100;
  const variance = returns.map(r => Math.pow(r / 100 - mean, 2)).reduce((a, b) => a + b, 0) / returns.length;
  const sharpe = variance > 0 ? Math.round(Math.sqrt(252) * (mean - 0.02 / 252) / Math.sqrt(variance) * 100) / 100 : 0;

  const metrics: TickerMetrics = {
    win_rate: Math.round((winning.length / filteredTrades.length) * 10000) / 100,
    total_return: Math.round(returns.reduce((a, b) => a + b, 0) * 10000) / 10000,
    max_drawdown: Math.round(-maxDD * 100) / 100,
    sharpe_ratio: sharpe,
    num_trades: filteredTrades.length,
    avg_hold_days: Math.round(filteredTrades.reduce((a, t) => a + t.hold_days, 0) / filteredTrades.length * 10) / 10,
    best_trade: Math.max(...returns),
    worst_trade: Math.min(...returns),
  };

  return { ...result, trades: filteredTrades, metrics };
}
