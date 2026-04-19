// frontend/src/components/OptimizationBook.tsx
import { useState } from 'react';
import { runBacktest, analyzeResults } from '../api/client';
import type { BacktestResponse, AIAnalysis, TickerMetrics } from '../types';

const EMA_PERIODS = [50, 100, 150, 200, 250];

interface Props {
  universeSize: number;
  currentResults: BacktestResponse | null;
}

interface OptRow {
  period: number;
  avgReturn: number;
  avgWinRate: number;
  avgSharpe: number;
  avgMaxDD: number;
}

export function OptimizationBook({ universeSize, currentResults }: Props) {
  const [optimRows, setOptimRows] = useState<OptRow[]>([]);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [loadingOptim, setLoadingOptim] = useState(false);
  const [loadingAI, setLoadingAI] = useState(false);

  async function runOptimization() {
    setLoadingOptim(true);
    try {
      const rows: OptRow[] = [];
      for (const period of EMA_PERIODS) {
        const res = await runBacktest(universeSize, period);
        const metrics = res.results
          .map(r => r.metrics)
          .filter((m): m is TickerMetrics => m !== null);
        if (metrics.length === 0) continue;
        rows.push({
          period,
          avgReturn: metrics.reduce((a, m) => a + m.total_return, 0) / metrics.length,
          avgWinRate: metrics.reduce((a, m) => a + m.win_rate, 0) / metrics.length,
          avgSharpe: metrics.reduce((a, m) => a + m.sharpe_ratio, 0) / metrics.length,
          avgMaxDD: metrics.reduce((a, m) => a + m.max_drawdown, 0) / metrics.length,
        });
      }
      setOptimRows(rows);
    } finally {
      setLoadingOptim(false);
    }
  }

  async function runAIAnalysis() {
    if (!currentResults) return;
    setLoadingAI(true);
    try {
      const result = await analyzeResults(currentResults);
      setAnalysis(result);
    } finally {
      setLoadingAI(false);
    }
  }

  return (
    <div className="space-y-6 p-4 rounded-lg" style={{ background: '#1A1D27' }}>
      {/* Parameter Optimization */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium" style={{ color: '#E8EAED' }}>Parameter Optimization</h3>
          <button
            onClick={runOptimization}
            disabled={loadingOptim}
            className="px-4 py-2 rounded text-sm font-medium disabled:opacity-50"
            style={{ background: '#00C48C', color: '#000' }}
          >
            {loadingOptim ? 'Running...' : 'Run Optimization'}
          </button>
        </div>

        {optimRows.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b" style={{ color: '#8B8FA8', borderColor: '#2A2D3E' }}>
                <th className="text-left py-2 pr-4">EMA Period</th>
                <th className="text-right py-2 pr-4">Avg Return</th>
                <th className="text-right py-2 pr-4">Win Rate</th>
                <th className="text-right py-2 pr-4">Sharpe</th>
                <th className="text-right py-2">Max DD</th>
              </tr>
            </thead>
            <tbody>
              {optimRows.map((r) => (
                <tr
                  key={r.period}
                  className="border-b"
                  style={{
                    borderColor: '#1E2130',
                    background: r.period === 200 ? '#1E2130' : 'transparent',
                  }}
                >
                  <td className="py-2 pr-4 font-medium" style={{ color: '#E8EAED' }}>
                    {r.period}
                    {r.period === 200 && (
                      <span className="ml-2 text-xs" style={{ color: '#8B8FA8' }}>(current)</span>
                    )}
                  </td>
                  <td
                    className="py-2 pr-4 text-right"
                    style={{ color: r.avgReturn >= 0 ? '#00C48C' : '#FF4757' }}
                  >
                    {r.avgReturn >= 0 ? '+' : ''}{r.avgReturn.toFixed(2)}%
                  </td>
                  <td className="py-2 pr-4 text-right" style={{ color: '#E8EAED' }}>
                    {r.avgWinRate.toFixed(1)}%
                  </td>
                  <td className="py-2 pr-4 text-right" style={{ color: '#E8EAED' }}>
                    {r.avgSharpe.toFixed(2)}
                  </td>
                  <td className="py-2 text-right" style={{ color: '#FF4757' }}>
                    {r.avgMaxDD.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* AI Analysis */}
      <div className="pt-4" style={{ borderTop: '1px solid #2A2D3E' }}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium" style={{ color: '#E8EAED' }}>AI Analysis</h3>
          <button
            onClick={runAIAnalysis}
            disabled={loadingAI || !currentResults}
            className="px-4 py-2 rounded text-sm font-medium disabled:opacity-50"
            style={{ background: '#1E2130', border: '1px solid #00C48C', color: '#00C48C' }}
          >
            {loadingAI ? 'Analyzing...' : 'Run AI Analysis'}
          </button>
        </div>

        {analysis && (
          <div className="space-y-4 text-sm">
            {analysis.patterns && (
              <div>
                <p className="mb-1 uppercase text-xs tracking-wider" style={{ color: '#8B8FA8' }}>Patterns</p>
                <ul className="space-y-1">
                  {analysis.patterns.map((p, i) => (
                    <li key={i} style={{ color: '#E8EAED' }}>• {p}</li>
                  ))}
                </ul>
              </div>
            )}
            {analysis.risk_assessment && (
              <div>
                <p className="mb-1 uppercase text-xs tracking-wider" style={{ color: '#8B8FA8' }}>Risk</p>
                <ul className="space-y-1">
                  {analysis.risk_assessment.map((p, i) => (
                    <li key={i} style={{ color: '#FF4757' }}>• {p}</li>
                  ))}
                </ul>
              </div>
            )}
            {analysis.recommendations && (
              <div>
                <p className="mb-1 uppercase text-xs tracking-wider" style={{ color: '#8B8FA8' }}>Recommendations</p>
                <ul className="space-y-1">
                  {analysis.recommendations.map((p, i) => (
                    <li key={i} style={{ color: '#00C48C' }}>• {p}</li>
                  ))}
                </ul>
              </div>
            )}
            {analysis.benchmark_comment && (
              <div>
                <p className="mb-1 uppercase text-xs tracking-wider" style={{ color: '#8B8FA8' }}>vs Benchmark</p>
                <p style={{ color: '#E8EAED' }}>{analysis.benchmark_comment}</p>
              </div>
            )}
            {analysis.raw && (
              <pre className="text-xs p-2 rounded" style={{ background: '#0F1117', color: '#8B8FA8' }}>
                {analysis.raw}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
