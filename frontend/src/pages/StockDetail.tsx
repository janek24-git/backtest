import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { CandleChart } from '../components/CandleChart';
import { TradeHistory } from '../components/TradeHistory';
import { runBacktest } from '../api/client';
import type { TickerResult } from '../types';

interface MetricCardProps {
  label: string;
  value: string;
  color?: string;
}

function MetricCard({ label, value, color }: MetricCardProps) {
  return (
    <div className="rounded p-4" style={{ background: '#1E2130' }}>
      <p className="text-xs uppercase tracking-wider mb-1" style={{ color: '#8B8FA8' }}>{label}</p>
      <p className="text-xl font-semibold" style={{ color: color ?? '#E8EAED' }}>{value}</p>
    </div>
  );
}

export function StockDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const [result, setResult] = useState<TickerResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        // Fetch Top20 to ensure the ticker is included regardless of universe
        const data = await runBacktest(20);
        const found = data.results.find(r => r.ticker === ticker);
        setResult(found ?? null);
        if (!found) setError(`Ticker ${ticker} not found in Top20 universe`);
      } catch (e: any) {
        setError(e?.message ?? 'Failed to load data');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [ticker]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#0F1117' }}>
        <p style={{ color: '#8B8FA8' }}>Loading {ticker}...</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen p-6" style={{ background: '#0F1117' }}>
        <button onClick={() => navigate('/')} className="text-sm mb-4 block" style={{ color: '#8B8FA8' }}>
          ← Back
        </button>
        <p style={{ color: '#FF4757' }}>{error ?? 'Not found'}</p>
      </div>
    );
  }

  const m = result.metrics;

  return (
    <div className="min-h-screen p-6" style={{ background: '#0F1117' }}>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/')} className="text-sm" style={{ color: '#8B8FA8' }}>
            ← Back
          </button>
          <h1 className="text-xl font-semibold" style={{ color: '#E8EAED' }}>{ticker}</h1>
          <span
            className="px-2 py-1 rounded text-xs font-medium"
            style={{
              background: result.last_signal === 1 ? '#00C48C20' : '#FF475720',
              color: result.last_signal === 1 ? '#00C48C' : '#FF4757',
            }}
          >
            {result.last_signal === 1 ? 'LONG' : 'FLAT'}
          </span>
        </div>

        {/* Metrics */}
        {m && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard
              label="Total Return"
              value={`${m.total_return >= 0 ? '+' : ''}${m.total_return.toFixed(2)}%`}
              color={m.total_return >= 0 ? '#00C48C' : '#FF4757'}
            />
            <MetricCard label="Win Rate" value={`${m.win_rate.toFixed(1)}%`} />
            <MetricCard label="Sharpe" value={m.sharpe_ratio.toFixed(2)} />
            <MetricCard
              label="Max DD"
              value={`${m.max_drawdown.toFixed(2)}%`}
              color="#FF4757"
            />
          </div>
        )}

        {/* Chart */}
        <div className="rounded-lg p-4" style={{ background: '#1A1D27' }}>
          <CandleChart signals={result.signals} trades={result.trades} />
        </div>

        {/* Trade History */}
        <div className="rounded-lg p-4" style={{ background: '#1A1D27' }}>
          <h3 className="font-medium mb-3" style={{ color: '#E8EAED' }}>
            Trade History ({result.trades.length} trades)
          </h3>
          <TradeHistory trades={result.trades} />
        </div>

      </div>
    </div>
  );
}
